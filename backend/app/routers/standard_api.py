from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.models import (
    MaintenanceJob, Department, Corridor, RailwaySection, BlockPlan,
    CoordinatedBlockPlan, PlanJob, User, AuditLog, Notification, WhatIfScenario,
    TrainMovement, TrainSectionOccupancy
)
from app.schemas.schemas import (
    MaintenanceJobCreate, MaintenanceJobUpdate, MaintenanceJobResponse,
    WhatIfRequest, AuditLogResponse
)
from app.services.maintenance_service import MaintenanceService
from app.services.planning_service import PlanningService
from app.services.train_service import TrainService
from app.services.whatif_service import WhatIfService
from app.algorithms.coordination import CompatibilityEngine, CoordinatedOptimizer
from app.algorithms.priority import PriorityEngine
from app.algorithms.validator import DeterministicSafetyValidator
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.windows import WindowEngine
from app.routers.auth import get_current_user, require_role

router = APIRouter(tags=["Standard Operational REST API (SIH26027)"])


# Helper: Planner role check
def check_planner_role(user: User) -> bool:
    role_norm = (user.role or "").upper()
    return role_norm in ("RAILWAY_PLANNER", "ADMIN", "SYSTEM_ADMIN") or user.role == "railway_planner"


# -------------------------------------------------------------
# PYDANTIC REQUEST / RESPONSE SCHEMAS
# -------------------------------------------------------------
class PriorityOverrideRequest(BaseModel):
    new_priority_score: float = Field(..., ge=0.0, le=100.0, description="Overridden priority score between 0 and 100")
    reason: str = Field(..., min_length=3, description="Operational justification for priority override")


class CompatibilityCheckRequest(BaseModel):
    request_ids: Optional[List[int]] = None
    job_ids: Optional[List[int]] = None


class OptimizationRunRequest(BaseModel):
    request_ids: Optional[List[int]] = None
    job_ids: Optional[List[int]] = None
    corridor_id: Optional[int] = None
    strategy: Optional[str] = "PLAN_A"
    time_limit_seconds: Optional[int] = 15
    enforce_locks: Optional[bool] = True


class PlanActionRequest(BaseModel):
    reason: Optional[str] = None
    remarks: Optional[str] = None
    start_min: Optional[int] = None
    end_min: Optional[int] = None
    section_id: Optional[int] = None


class ReplanningRunRequest(BaseModel):
    base_plan_id: Optional[int] = None
    train_number: Optional[str] = None
    train_delay_min: Optional[int] = 0
    reason: Optional[str] = "Dynamic replanning after train disturbance"


# -------------------------------------------------------------
# 1. REQUESTS: GET /requests, POST /requests, GET /requests/{id}, PATCH /requests/{id}
# -------------------------------------------------------------
@router.get("/requests")
def list_requests(
    department_id: Optional[int] = None,
    corridor_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists maintenance requests with role-based filtering and transparent priority metrics."""
    query = db.query(MaintenanceJob)
    role_norm = (current_user.role or "").upper()
    if role_norm in ("DEPARTMENT_USER", "MAINTENANCE_ENGINEER") and current_user.department_id:
        query = query.filter(MaintenanceJob.department_id == current_user.department_id)

    if department_id:
        query = query.filter(MaintenanceJob.department_id == department_id)
    if corridor_id:
        query = query.filter(MaintenanceJob.corridor_id == corridor_id)
    if status:
        query = query.filter(MaintenanceJob.status == status)

    jobs = query.order_by(MaintenanceJob.priority_score.desc().nullslast(), MaintenanceJob.id.desc()).all()
    results = []
    for j in jobs:
        results.append({
            "id": j.id,
            "job_code": j.job_code,
            "department_id": j.department_id,
            "department_name": j.department.name if j.department else "Engineering",
            "department_code": j.department.code if j.department else "ENGG",
            "corridor_id": j.corridor_id,
            "corridor_name": j.corridor.name if j.corridor else None,
            "corridor_code": j.corridor.code if j.corridor else None,
            "section_id": j.section_id,
            "section_name": j.section.name if j.section else j.section_name,
            "start_station_code": j.start_station_code,
            "end_station_code": j.end_station_code,
            "work_type": j.work_type,
            "description": j.description,
            "user_priority": j.user_priority,
            "priority_score": j.priority_score,
            "criticality": j.criticality,
            "safety_impact": j.safety_impact,
            "urgency": j.urgency,
            "operational_impact": j.operational_impact,
            "is_priority_overridden": getattr(j, "is_priority_overridden", False),
            "requested_date": j.requested_date.isoformat() if j.requested_date else None,
            "requested_start_min": j.requested_start_min,
            "requested_end_min": j.requested_end_min,
            "duration_min": j.estimated_duration_min,
            "due_date": j.due_date.isoformat() if j.due_date else None,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None
        })
    return results


@router.post("/requests")
def create_request(
    request_in: MaintenanceJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Department user creates a maintenance request.
    Department is automatically assigned from the authenticated user's RBAC profile.
    Deterministic priority score is calculated automatically.
    """
    job = MaintenanceService.create_job(db, request_in, current_user)

    audit = AuditLog(
        user_id=current_user.id,
        action="CREATE_REQUEST",
        entity_type="MAINTENANCE_JOB",
        entity_id=str(job.id),
        details_json={
            "job_code": job.job_code,
            "department": job.department.name if job.department else "Engineering",
            "priority": job.user_priority,
            "priority_score": job.priority_score,
            "status": job.status
        }
    )
    db.add(audit)
    db.commit()

    return {
        "id": job.id,
        "job_code": job.job_code,
        "department_name": job.department.name if job.department else "Engineering",
        "priority_score": job.priority_score,
        "status": job.status,
        "message": f"Maintenance request {job.job_code} registered successfully."
    }


@router.get("/requests/{id}")
def get_request_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets details of a single maintenance request."""
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Request with ID {id} not found.")

    return {
        "id": job.id,
        "job_code": job.job_code,
        "department_id": job.department_id,
        "department_name": job.department.name if job.department else "Engineering",
        "department_code": job.department.code if job.department else "ENGG",
        "corridor_id": job.corridor_id,
        "corridor_name": job.corridor.name if job.corridor else None,
        "section_id": job.section_id,
        "section_name": job.section.name if job.section else job.section_name,
        "start_station_code": job.start_station_code,
        "end_station_code": job.end_station_code,
        "work_type": job.work_type,
        "description": job.description,
        "user_priority": job.user_priority,
        "priority_score": job.priority_score,
        "criticality": job.criticality,
        "safety_impact": job.safety_impact,
        "urgency": job.urgency,
        "operational_impact": job.operational_impact,
        "is_priority_overridden": getattr(job, "is_priority_overridden", False),
        "priority_override_reason": getattr(job, "priority_override_reason", None),
        "requested_date": job.requested_date.isoformat() if job.requested_date else None,
        "requested_start_min": job.requested_start_min,
        "requested_end_min": job.requested_end_min,
        "duration_min": job.estimated_duration_min,
        "due_date": job.due_date.isoformat() if job.due_date else None,
        "status": job.status
    }


@router.patch("/requests/{id}")
def patch_request(
    id: int,
    updates: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates fields of a maintenance request."""
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Request with ID {id} not found.")

    allowed_fields = [
        "description", "work_type", "user_priority", "requested_start_min",
        "requested_end_min", "estimated_duration_min", "status", "planner_remarks"
    ]
    old_values = {}
    for f in allowed_fields:
        if f in updates:
            old_values[f] = getattr(job, f, None)
            setattr(job, f, updates[f])

    audit = AuditLog(
        user_id=current_user.id,
        action="PATCH_REQUEST",
        entity_type="MAINTENANCE_JOB",
        entity_id=str(job.id),
        details_json={"old": old_values, "new": {k: updates[k] for k in old_values}}
    )
    db.add(audit)
    db.commit()
    db.refresh(job)

    return {"message": f"Request {job.job_code} updated successfully.", "id": job.id, "status": job.status}


# -------------------------------------------------------------
# 2. PRIORITY: GET /requests/{id}/priority, POST /requests/{id}/priority/override
# -------------------------------------------------------------
@router.get("/requests/{id}/priority")
def get_request_priority(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns transparent deterministic priority breakdown and explainability reasons."""
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Request with ID {id} not found.")

    dept_code = job.department.code if job.department else "ENGG"
    breakdown = PriorityEngine.calculate_full_priority(
        work_type=job.work_type,
        department_code=dept_code,
        user_priority=job.user_priority or "MEDIUM",
        due_date=job.due_date,
        is_emergency=getattr(job, "is_emergency", False),
        operational_impact_val=job.operational_impact
    )

    reasons = breakdown.get("reasons", [])
    if getattr(job, "is_priority_overridden", False):
        reasons.append(f"Planner override active: {getattr(job, 'priority_override_reason', '')}")

    return {
        "requestId": job.id,
        "jobCode": job.job_code,
        "priorityScore": job.priority_score or breakdown["composite_priority_score"],
        "calculatedScore": breakdown["composite_priority_score"],
        "breakdown": {
            "criticality": breakdown["criticality"]["score"],
            "criticalityLabel": breakdown["criticality"]["label"],
            "urgency": breakdown["urgency"]["score"],
            "urgencyLabel": breakdown["urgency"]["label"],
            "overdueRisk": breakdown["overdue_risk"]["score"],
            "overdueDays": breakdown["overdue_risk"]["overdue_days"],
            "safetyImpact": breakdown["safety_impact"]["score"],
            "safetyImpactLabel": breakdown["safety_impact"]["label"],
            "operationalImpact": breakdown["operational_impact"]["score"]
        },
        "weights": breakdown["weights_applied"],
        "reasons": reasons,
        "isOverridden": getattr(job, "is_priority_overridden", False),
        "disclaimer": PriorityEngine.DISCLAIMER
    }


@router.post("/requests/{id}/priority/override")
def override_request_priority(
    id: int,
    req: PriorityOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Planner overrides deterministic priority score with operational justification.
    Audited with planner ID, timestamp, old and new values.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to override priority.")

    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Request with ID {id} not found.")

    old_score = job.priority_score
    job.priority_score = req.new_priority_score
    if hasattr(job, "is_priority_overridden"):
        job.is_priority_overridden = True
    if hasattr(job, "priority_override_reason"):
        job.priority_override_reason = req.reason

    audit = AuditLog(
        user_id=current_user.id,
        action="PRIORITY_OVERRIDE",
        entity_type="MAINTENANCE_JOB",
        entity_id=str(job.id),
        details_json={
            "job_code": job.job_code,
            "old_priority_score": old_score,
            "new_priority_score": req.new_priority_score,
            "reason": req.reason,
            "planner_id": current_user.id,
            "planner_name": current_user.full_name or current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    db.add(audit)
    db.commit()

    return {
        "requestId": job.id,
        "jobCode": job.job_code,
        "newPriorityScore": job.priority_score,
        "reason": req.reason,
        "overriddenBy": current_user.username,
        "message": f"Priority for {job.job_code} successfully updated to {req.new_priority_score}."
    }


# -------------------------------------------------------------
# 3. COMPATIBILITY: POST /compatibility/check
# -------------------------------------------------------------
@router.post("/compatibility/check")
def check_compatibility(
    req: CompatibilityCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Evaluates a set of maintenance requests for common block feasibility.
    Checks section overlap, corridor compatibility, date compatibility, and parallel work rules.
    Outputs explainable reasons.
    """
    j_ids = req.request_ids or req.job_ids or []
    if not j_ids or len(j_ids) < 2:
        return {
            "status": "INSUFFICIENT_REQUESTS",
            "isCompatible": False,
            "canProceed": False,
            "message": "At least 2 maintenance requests are required for coordinated compatibility check.",
            "reasons": ["Select at least two requests to evaluate common block possession."]
        }

    jobs = db.query(MaintenanceJob).filter(MaintenanceJob.id.in_(j_ids)).all()
    comp_result = CompatibilityEngine.check_compatibility(jobs)

    status_str = "COMPATIBLE" if comp_result["is_compatible"] else ("CONDITIONALLY_COMPATIBLE" if comp_result["is_partially_compatible"] else "INCOMPATIBLE")

    return {
        "status": status_str,
        "isCompatible": comp_result["is_compatible"],
        "isPartiallyCompatible": comp_result["is_partially_compatible"],
        "canProceed": comp_result["can_proceed"],
        "isParallel": comp_result.get("is_parallel", True),
        "totalEvaluated": len(jobs),
        "compatibleCount": comp_result["compatible_count"],
        "incompatibleCount": comp_result["incompatible_count"],
        "compatibleJobs": comp_result["compatible_jobs"],
        "incompatibleJobs": comp_result["incompatible_jobs"],
        "reasons": comp_result["reasons"],
        "incompatibilityReasons": comp_result["incompatibility_reasons"],
        "savings": comp_result.get("savings", {})
    }


# -------------------------------------------------------------
# 4. OPTIMIZATION: POST /optimization/run, GET /optimization/plans, GET /optimization/runs/{id}
# -------------------------------------------------------------
@router.post("/optimization/run")
def run_optimization(
    req: Optional[OptimizationRunRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Centralized Railway Planning Workstation - Global Block Optimization (Section 25).
    Uses Google OR-Tools CP-SAT to generate coordinated and individual block plans.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to run optimization.")

    strategy = req.strategy if req and req.strategy else "PLAN_A"
    j_ids = req.request_ids or req.job_ids if req else None

    if j_ids and len(j_ids) > 0:
        jobs = db.query(MaintenanceJob).filter(
            MaintenanceJob.id.in_(j_ids),
            MaintenanceJob.status.notin_(["COMPLETED", "CANCELLED", "REJECTED"])
        ).all()
    else:
        # Fetch all eligible pending requests across Tamil Nadu network
        jobs = db.query(MaintenanceJob).filter(
            MaintenanceJob.status.in_(["SUBMITTED", "UNDER_REVIEW", "PLANNING", "RECOMMENDED", "DRAFT"])
        ).all()
        if not jobs:
            jobs = db.query(MaintenanceJob).filter(
                MaintenanceJob.status.notin_(["COMPLETED", "CANCELLED", "REJECTED"])
            ).all()

    if not jobs:
        raise HTTPException(status_code=400, detail="No eligible maintenance requests available for block optimization.")

    # Audit optimization started
    audit_start = AuditLog(
        user_id=current_user.id,
        action="OPTIMIZATION_STARTED",
        entity_type="OPTIMIZATION_RUN",
        entity_id=f"RUN_{len(jobs)}",
        details_json={"strategy": strategy, "requests_count": len(jobs)}
    )
    db.add(audit_start)
    db.commit()

    # Execute global pool optimization with CP-SAT
    pool_result = CoordinatedOptimizer.optimize_pool(jobs, db, strategy=strategy)

    # Persist plans
    today_str = datetime.utcnow().strftime("%Y%m%d")
    count_today = db.query(CoordinatedBlockPlan).count()
    persisted_plans = []

    for plan_dict in pool_result["plans"]:
        count_today += 1
        plan_code = f"CBP-{today_str}-{count_today:03d}"

        plan_entity = CoordinatedBlockPlan(
            plan_code=plan_code,
            corridor_id=plan_dict.get("corridor_id"),
            corridor_name=plan_dict.get("corridor"),
            section_id=plan_dict.get("section_id"),
            section_name=plan_dict.get("section"),
            plan_date=datetime.utcnow(),
            start_min=plan_dict["start_min"],
            end_min=plan_dict["end_min"],
            duration_min=plan_dict["total_possession_duration_min"],
            status="RECOMMENDED",
            strategy=strategy,
            objective_score=plan_dict["optimization_score"],
            conflicts_count=plan_dict.get("conflicts_count", 0),
            blocks_saved=plan_dict.get("separate_blocks_avoided", 0),
            possession_time_saved_min=plan_dict.get("possession_time_saved_min", 0),
            is_parallel=plan_dict.get("is_parallel", True),
            departments_json=plan_dict.get("departments", []),
            work_breakdown_json=plan_dict.get("work_breakdown", []),
            alternatives_json=plan_dict.get("alternatives", []),
            reasoning_json=plan_dict.get("reasoning", []),
            created_by_id=current_user.id,
            created_at=datetime.utcnow()
        )
        db.add(plan_entity)
        db.flush()

        plan_dict["id"] = plan_entity.id
        plan_dict["plan_id"] = plan_entity.id
        plan_dict["plan_code"] = plan_entity.plan_code

        # Link jobs
        job_entities = plan_dict.pop("job_entities", [])
        for j in job_entities:
            j.coordinated_plan_id = plan_entity.id
            j.status = "RECOMMENDED"
            db.add(j)

        persisted_plans.append(plan_dict)

    audit_end = AuditLog(
        user_id=current_user.id,
        action="OPTIMIZATION_COMPLETED",
        entity_type="OPTIMIZATION_RUN",
        entity_id=f"PLANS_{len(persisted_plans)}",
        details_json={"plans_generated": len(persisted_plans), "strategy": strategy}
    )
    db.add(audit_end)
    db.commit()

    return {
        "status": "OPTIMIZED",
        "solver": "Google OR-Tools CP-SAT",
        "strategy": strategy,
        "plansGenerated": len(persisted_plans),
        "plans": persisted_plans,
        "summary": pool_result.get("summary", {})
    }


@router.get("/optimization/plans")
def list_optimization_plans(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns generated block plans for Planner review."""
    query = db.query(CoordinatedBlockPlan)
    if status:
        query = query.filter(CoordinatedBlockPlan.status == status)

    plans = query.order_by(CoordinatedBlockPlan.id.desc()).limit(limit).all()
    results = []
    for p in plans:
        # Convert start/end min to HH:MM format
        s_hr, s_m = divmod(p.start_min or 0, 60)
        e_hr, e_m = divmod(p.end_min or 0, 60)
        results.append({
            "id": p.id,
            "planCode": p.plan_code,
            "corridorName": p.corridor_name,
            "sectionName": p.section_name,
            "startTime": f"{s_hr:02d}:{s_m:02d}",
            "endTime": f"{e_hr:02d}:{e_m:02d}",
            "durationMin": p.duration_min,
            "status": p.status,
            "strategy": p.strategy,
            "objectiveScore": p.objective_score,
            "conflictsCount": p.conflicts_count,
            "blocksSaved": p.blocks_saved,
            "possessionTimeSavedMin": p.possession_time_saved_min,
            "isParallel": p.is_parallel,
            "departments": p.departments_json or [],
            "workBreakdown": p.work_breakdown_json or [],
            "reasons": p.reasoning_json or [],
            "createdAt": p.created_at.isoformat() if p.created_at else None
        })
    return results


@router.get("/optimization/runs/{id}")
def get_optimization_run(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets details of an optimization plan or run."""
    plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan with ID {id} not found.")

    s_hr, s_m = divmod(plan.start_min or 0, 60)
    e_hr, e_m = divmod(plan.end_min or 0, 60)
    return {
        "id": plan.id,
        "planCode": plan.plan_code,
        "corridorName": plan.corridor_name,
        "sectionName": plan.section_name,
        "startTime": f"{s_hr:02d}:{s_m:02d}",
        "endTime": f"{e_hr:02d}:{e_m:02d}",
        "durationMin": plan.duration_min,
        "status": plan.status,
        "strategy": plan.strategy,
        "objectiveScore": plan.objective_score,
        "conflictsCount": plan.conflicts_count,
        "blocksSaved": plan.blocks_saved,
        "possessionTimeSavedMin": plan.possession_time_saved_min,
        "isParallel": plan.is_parallel,
        "departments": plan.departments_json or [],
        "workBreakdown": plan.work_breakdown_json or [],
        "alternatives": plan.alternatives_json or [],
        "reasons": plan.reasoning_json or []
    }


# -------------------------------------------------------------
# 5. PLANNER DECISIONS: POST /plans/{id}/approve, POST /plans/{id}/modify, POST /plans/{id}/reject
# -------------------------------------------------------------
@router.post("/plans/{id}/approve")
def approve_plan(
    id: int,
    req: Optional[PlanActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Railway Planner formally approves a block plan.
    Transitions constituent requests to APPROVED, creates audit log, and notifies departments.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to approve plan.")

    reason = req.reason if req and req.reason else "Master maintenance block plan authorized by Railway Planner"

    # Check CoordinatedBlockPlan first
    coord_plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == id).first()
    if coord_plan:
        coord_plan.status = "APPROVED"
        coord_plan.approved_by_id = current_user.id
        coord_plan.approved_at = datetime.utcnow()

        # Update constituent jobs
        for job in coord_plan.jobs:
            job.status = "APPROVED"
            job.approved_at = datetime.utcnow()
            job.approved_by_id = current_user.id
            job.planner_remarks = reason

            # Notify department
            notif = Notification(
                department_id=job.department_id,
                title=f"Maintenance Block Approved: {job.job_code}",
                message=f"Plan {coord_plan.plan_code} authorized. Section: {coord_plan.section_name}. Duration: {coord_plan.duration_min} min. Please accept plan.",
                notification_type="PLAN_APPROVED",
                target_entity="COORDINATED_BLOCK_PLAN",
                target_id=str(coord_plan.id)
            )
            db.add(notif)

        audit = AuditLog(
            user_id=current_user.id,
            action="APPROVE_PLAN",
            entity_type="COORDINATED_BLOCK_PLAN",
            entity_id=str(coord_plan.id),
            details_json={"plan_code": coord_plan.plan_code, "reason": reason}
        )
        db.add(audit)
        db.commit()
        return {"status": "APPROVED", "planId": coord_plan.id, "planCode": coord_plan.plan_code, "message": "Plan approved successfully."}

    # Fallback to BlockPlan
    base_plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if base_plan:
        base_plan.approval_status = "APPROVED"
        base_plan.approved_by_id = current_user.id
        base_plan.approved_at = datetime.utcnow()
        for pj in base_plan.plan_jobs:
            if pj.job and pj.is_scheduled:
                pj.job.status = "APPROVED"
        audit = AuditLog(
            user_id=current_user.id,
            action="APPROVE_PLAN",
            entity_type="BLOCK_PLAN",
            entity_id=str(base_plan.id),
            details_json={"plan_code": base_plan.plan_code, "reason": reason}
        )
        db.add(audit)
        db.commit()
        return {"status": "APPROVED", "planId": base_plan.id, "planCode": base_plan.plan_code, "message": "Plan approved successfully."}

    raise HTTPException(status_code=404, detail=f"Plan with ID {id} not found.")


@router.post("/plans/{id}/modify")
def modify_plan(
    id: int,
    req: PlanActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Railway Planner modifies timing or section parameters of a plan.
    Audited with planner remarks and changed values.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to modify plan.")

    coord_plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == id).first()
    if coord_plan:
        old_values = {"start_min": coord_plan.start_min, "end_min": coord_plan.end_min, "duration_min": coord_plan.duration_min}
        if req.start_min is not None:
            coord_plan.start_min = req.start_min
        if req.end_min is not None:
            coord_plan.end_min = req.end_min
        if coord_plan.start_min is not None and coord_plan.end_min is not None:
            coord_plan.duration_min = max(10, coord_plan.end_min - coord_plan.start_min)

        coord_plan.status = "MODIFIED"

        audit = AuditLog(
            user_id=current_user.id,
            action="MODIFY_PLAN",
            entity_type="COORDINATED_BLOCK_PLAN",
            entity_id=str(coord_plan.id),
            details_json={"old": old_values, "new": {"start_min": coord_plan.start_min, "end_min": coord_plan.end_min}, "reason": req.reason or req.remarks}
        )
        db.add(audit)
        db.commit()
        return {"status": "MODIFIED", "planId": coord_plan.id, "planCode": coord_plan.plan_code, "message": "Plan modified successfully."}

    raise HTTPException(status_code=404, detail=f"Plan with ID {id} not found.")


@router.post("/plans/{id}/reject")
def reject_plan(
    id: int,
    req: PlanActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Railway Planner rejects a block plan with required operational justification.
    Reverts jobs to SUBMITTED and audits action.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to reject plan.")

    if not req.reason and not req.remarks:
        raise HTTPException(status_code=400, detail="Operational reason is required to reject a plan.")

    reason = req.reason or req.remarks

    coord_plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == id).first()
    if coord_plan:
        coord_plan.status = "REJECTED"
        coord_plan.rejection_reason = reason

        for job in coord_plan.jobs:
            if job.status == "RECOMMENDED":
                job.status = "SUBMITTED"
                job.planner_remarks = f"Plan {coord_plan.plan_code} rejected: {reason}"

        audit = AuditLog(
            user_id=current_user.id,
            action="REJECT_PLAN",
            entity_type="COORDINATED_BLOCK_PLAN",
            entity_id=str(coord_plan.id),
            details_json={"plan_code": coord_plan.plan_code, "reason": reason}
        )
        db.add(audit)
        db.commit()
        return {"status": "REJECTED", "planId": coord_plan.id, "planCode": coord_plan.plan_code, "reason": reason}

    raise HTTPException(status_code=404, detail=f"Plan with ID {id} not found.")


# -------------------------------------------------------------
# 6. DYNAMIC REPLANNING: POST /replanning/run
# -------------------------------------------------------------
@router.post("/replanning/run")
def run_dynamic_replanning(
    req: ReplanningRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rolling-horizon Dynamic Replanning Engine (Section 30).
    1. Freezes completed & locked decisions.
    2. If train delay provided, updates train telemetry and shifts section occupancies.
    3. Recalculates future section availability.
    4. Reruns CP-SAT optimization on flexible future decisions only.
    5. Audits replanning run.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required for dynamic replanning.")

    # Apply train delay if requested
    affected_sections = []
    if req.train_number and req.train_delay_min:
        TrainService.simulate_train_delay(db, req.train_number, req.train_delay_min)
        occs = TrainService.calculate_all_occupancies(db)
        affected_sections = list(set([o["section_id"] for o in occs if o["train_number"] == req.train_number]))

    # Run global pool optimization preserving completed/locked decisions
    jobs = db.query(MaintenanceJob).filter(
        MaintenanceJob.status.notin_(["COMPLETED", "CANCELLED", "REJECTED"])
    ).all()

    pool_result = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")

    audit = AuditLog(
        user_id=current_user.id,
        action="DYNAMIC_REPLANNING",
        entity_type="REPLAN_RUN",
        entity_id=f"REPLAN_{len(jobs)}",
        details_json={
            "train_number": req.train_number,
            "train_delay_min": req.train_delay_min,
            "affected_sections": affected_sections,
            "reason": req.reason,
            "plans_generated": len(pool_result.get("plans", []))
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "REPLANNED",
        "trainDisturbance": {
            "trainNumber": req.train_number,
            "delayMin": req.train_delay_min,
            "affectedSections": affected_sections
        },
        "revisedPlans": pool_result.get("plans", []),
        "summary": pool_result.get("summary", {}),
        "message": "Dynamic rolling-horizon replanning completed successfully."
    }


# -------------------------------------------------------------
# 7. WHAT-IF ANALYSIS: POST /what-if, GET /what-if/{id}, POST /what-if/{id}/run, DELETE /what-if/{id}
# -------------------------------------------------------------
@router.post("/what-if")
def create_and_run_whatif(
    req: WhatIfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes a sandboxed What-If simulation without altering master active plan (Section 32).
    Recalculates affected windows and compares KPIs side-by-side with baseline.
    """
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required for what-if simulation.")

    result = WhatIfService.simulate_scenario(db, req, current_user)

    audit = AuditLog(
        user_id=current_user.id,
        action="CREATE_WHATIF_SCENARIO",
        entity_type="WHAT_IF_SCENARIO",
        entity_id=str(result.get("scenario_id", "SANDBOX")),
        details_json={"scenario_name": req.scenario_name, "perturbations": req.model_dump()}
    )
    db.add(audit)
    db.commit()

    return result


@router.get("/what-if/{id}")
def get_whatif_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets details and comparison results of a saved What-If scenario."""
    scenario = db.query(WhatIfScenario).filter(WhatIfScenario.id == id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail=f"What-If scenario with ID {id} not found.")

    return {
        "id": scenario.id,
        "scenarioName": scenario.scenario_name,
        "description": scenario.description,
        "basePlanId": scenario.base_plan_id,
        "perturbations": scenario.perturbations_json,
        "resultMetrics": scenario.result_metrics_json,
        "createdAt": scenario.created_at.isoformat() if scenario.created_at else None
    }


@router.post("/what-if/{id}/run")
def rerun_whatif_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-executes a saved What-If scenario."""
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required for what-if simulation.")

    scenario = db.query(WhatIfScenario).filter(WhatIfScenario.id == id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail=f"What-If scenario with ID {id} not found.")

    perturbations = scenario.perturbations_json or {}
    req = WhatIfRequest(
        scenario_name=scenario.scenario_name,
        description=scenario.description,
        base_plan_id=scenario.base_plan_id,
        train_delay_min=perturbations.get("train_delay_min", 0),
        train_delay_train_no=perturbations.get("train_delay_train_no"),
        duration_multiplier=perturbations.get("duration_multiplier", 1.0),
        emergency_job_id=perturbations.get("emergency_job_id")
    )
    return WhatIfService.simulate_scenario(db, req, current_user)


@router.delete("/what-if/{id}")
def delete_whatif_scenario(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Discards a What-If scenario."""
    if not check_planner_role(current_user):
        raise HTTPException(status_code=403, detail="Railway Planner authority required to delete what-if scenario.")

    scenario = db.query(WhatIfScenario).filter(WhatIfScenario.id == id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail=f"What-If scenario with ID {id} not found.")

    db.delete(scenario)
    db.commit()
    return {"message": f"Scenario {id} discarded successfully."}


# -------------------------------------------------------------
# 8. AUDIT LOGS: GET /audit
# -------------------------------------------------------------
@router.get("/audit", response_model=List[AuditLogResponse])
def get_audit_trail(
    limit: int = 50,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns complete chronological audit log trail (Section 37).
    Audits request creation, priority calculation, overrides, optimization, approval, rejection, replan, what-if.
    """
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)

    logs = query.order_by(AuditLog.id.desc()).limit(limit).all()
    return logs
