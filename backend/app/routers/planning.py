from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import BlockPlan, PlanJob, MaintenanceJob, User, PlannerAction, AuditLog, Notification
from app.schemas.schemas import (
    OptimizeRequest, BlockPlanResponse, BlockWindowResponse,
    ValidationResult, ApprovalRequest, LockJobRequest, JobExplanationResponse, KPIComparisonResponse,
    DepartmentPlanActionRequest
)
from app.services.planning_service import PlanningService
from app.algorithms.validator import DeterministicSafetyValidator
from app.algorithms.compatibility import CompatibilityGraphEngine
from app.services.train_service import TrainService
from app.routers.auth import get_current_user, require_role

router = APIRouter(prefix="/planning", tags=["Block Planning & Optimization"])


@router.get("/windows", response_model=List[BlockWindowResponse])
def get_windows(corridor_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Strictly read-only retrieval of feasible maintenance windows."""
    return PlanningService.get_windows(db, corridor_id)


@router.post("/windows/recalculate", response_model=List[BlockWindowResponse])
def recalculate_windows(
    corridor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """
    Explicit backend operation to recalculate and synchronize feasible maintenance windows.
    Strictly restricted to authorized planners. Never mutates database on GET.
    """
    return PlanningService.recalculate_windows(db, corridor_id)


@router.post("/optimize", response_model=BlockPlanResponse)
@router.post("/generate", response_model=BlockPlanResponse)
def run_optimization(
    req: OptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """Executes Google OR-Tools CP-SAT optimization for Plan A, Plan B, or Plan C."""
    plan = PlanningService.run_optimization(
        db=db,
        strategy=req.strategy,
        corridor_id=req.corridor_id,
        user=current_user,
        time_limit_seconds=req.time_limit_seconds,
        enforce_locks=req.enforce_locks
    )

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="RUN_CPSAT_OPTIMIZATION",
        entity_type="BLOCK_PLAN",
        entity_id=str(plan.id),
        details_json={"strategy": req.strategy, "objective_score": plan.objective_score, "solver_status": plan.solver_status}
    )
    db.add(audit)
    db.commit()

    return plan


@router.get("/comparison", response_model=KPIComparisonResponse)
def get_kpi_comparison(db: Session = Depends(get_db)):
    """Returns dynamic KPI comparison across Baseline Heuristic, Plan A, Plan B, and Plan C."""
    return PlanningService.get_kpi_comparison(db)


@router.get("/plans/active", response_model=Optional[BlockPlanResponse])
def get_active_plan(strategy: str = "PLAN_A", db: Session = Depends(get_db)):
    return db.query(BlockPlan).filter(BlockPlan.is_active == True, BlockPlan.strategy == strategy).order_by(BlockPlan.id.desc()).first()


@router.get("/plans/{id}", response_model=BlockPlanResponse)
def get_plan(id: int, db: Session = Depends(get_db)):
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Block Plan not found")
    return plan


@router.post("/plans/{id}/validate", response_model=ValidationResult)
def validate_plan(id: int, db: Session = Depends(get_db)):
    """Runs independent deterministic safety validator on the plan."""
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Block Plan not found")

    windows = PlanningService.generate_windows(db)
    occupancies = TrainService.calculate_all_occupancies(db)

    scheduled_jobs = []
    for pj in plan.plan_jobs:
        scheduled_jobs.append({
            "job_id": pj.job_id,
            "job_code": pj.job.job_code if pj.job else f"JOB_{pj.job_id}",
            "section_id": pj.job.section_id if pj.job else 1,
            "affected_section_ids": pj.job.affected_sections_json if (pj.job and pj.job.affected_sections_json) else ([pj.job.section_id] if (pj.job and pj.job.section_id) else []),
            "work_type": pj.job.work_type if pj.job else None,
            "department_code": pj.job.department.code if (pj.job and pj.job.department) else None,
            "window_id": pj.window_id,
            "scheduled_start_min": pj.scheduled_start_min,
            "scheduled_end_min": pj.scheduled_end_min,
            "scheduled_duration_min": pj.scheduled_duration_min,
            "is_scheduled": pj.is_scheduled,
            "is_locked": pj.is_locked
        })

    is_valid, errors, warnings = DeterministicSafetyValidator.validate_plan(
        scheduled_jobs=scheduled_jobs,
        windows=windows,
        occupancies=occupancies
    )

    plan.validation_status = "VALID" if is_valid else "INVALID"
    plan.validation_errors_json = errors if not is_valid else None
    db.commit()

    return {
        "is_valid": is_valid,
        "status": "VALID" if is_valid else "INVALID",
        "errors": errors,
        "warnings": warnings,
        "checked_rules_count": 15
    }


@router.post("/plans/{id}/approve", response_model=BlockPlanResponse)
def approve_plan(
    id: int,
    approval_req: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """
    Approves or rejects a master block plan.
    Strictly restricted to Railway Planner / Admin (Department Users receive 403 Forbidden).
    """
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if approval_req.action == "APPROVE":
        if plan.validation_status != "VALID":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve plan: Safety validation status is '{plan.validation_status}'. Only independently validated VALID plans may be approved."
            )
        if plan.solver_status not in ("OPTIMAL", "FEASIBLE"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve plan: Solver status is '{plan.solver_status}'. Infeasible schedules cannot be approved."
            )

        plan.approval_status = "APPROVED"
        plan.approved_by_id = current_user.id
        plan.approved_at = datetime.utcnow()
        plan.decision_reason = approval_req.reason or "Authorized by Railway Planner"
        plan.version = (plan.version or 1) + 1

        # Atomically transition all scheduled jobs in the plan to APPROVED and notify departments
        for pj in plan.plan_jobs:
            if pj.is_scheduled and pj.job:
                j = pj.job
                old_st = j.status
                j.status = "APPROVED"
                j.approved_at = datetime.utcnow()
                j.approved_by_id = current_user.id
                j.planner_remarks = approval_req.reason or "Master block plan authorized by Railway Planner"

                # State history record
                history = list(j.state_history_json or [])
                history.append({
                    "from_state": old_st,
                    "to_state": "APPROVED",
                    "acting_user": current_user.username,
                    "user_id": current_user.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "reason": approval_req.reason or "Master block plan authorized by Railway Planner"
                })
                j.state_history_json = history

                # Send notification to the responsible department
                start_hr, start_m = divmod(pj.scheduled_start_min or 0, 60)
                end_hr, end_m = divmod(pj.scheduled_end_min or 0, 60)
                sec_desc = j.section.name if j.section else f"{j.start_station_code} - {j.end_station_code}"
                notif = Notification(
                    department_id=j.department_id,
                    title=f"Maintenance Plan Approved: {j.job_code}",
                    message=f"Plan {plan.plan_code} authorized by {current_user.full_name}. Block assigned: {start_hr:02d}:{start_m:02d} to {end_hr:02d}:{end_m:02d} IST on {sec_desc}. Please review and accept plan.",
                    notification_type="PLAN_APPROVED",
                    target_entity="BLOCK_PLAN",
                    target_id=str(plan.id)
                )
                db.add(notif)
    else:
        plan.approval_status = "REJECTED"
        plan.rejection_reason = approval_req.reason

        for pj in plan.plan_jobs:
            if pj.job and pj.job.status == "PLANNING":
                pj.job.status = "SUBMITTED"

    # Record planner action
    p_action = PlannerAction(
        user_id=current_user.id,
        action_type=f"{approval_req.action}_PLAN",
        target_entity="BLOCK_PLAN",
        target_id=str(plan.id),
        old_value_json={"status": "PROPOSED"},
        new_value_json={"status": plan.approval_status},
        reason=approval_req.reason
    )
    db.add(p_action)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/jobs/lock")
def lock_job(
    lock_req: LockJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """Locks or unlocks a maintenance job start time in the optimizer."""
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == lock_req.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    old_locked = job.is_locked
    old_start = job.locked_start_min

    job.is_locked = lock_req.is_locked
    job.locked_start_min = lock_req.locked_start_min if lock_req.is_locked else None

    # Update planner action audit
    p_action = PlannerAction(
        user_id=current_user.id,
        action_type="LOCK_JOB" if lock_req.is_locked else "UNLOCK_JOB",
        target_entity="MAINTENANCE_JOB",
        target_id=str(job.id),
        old_value_json={"is_locked": old_locked, "locked_start_min": old_start},
        new_value_json={"is_locked": job.is_locked, "locked_start_min": job.locked_start_min},
        reason=lock_req.reason
    )
    db.add(p_action)
    db.commit()

    return {
        "job_id": job.id,
        "job_code": job.job_code,
        "is_locked": job.is_locked,
        "locked_start_min": job.locked_start_min,
        "message": f"Job {job.job_code} successfully {'locked' if job.is_locked else 'unlocked'}."
    }


@router.get("/jobs/{id}/explanation", response_model=JobExplanationResponse)
def get_job_explanation(id: int, plan_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Returns transparent explainability breakdown for why job was scheduled or deferred."""
    return PlanningService.get_job_explanation(db, id, plan_id)


@router.post("/validate", response_model=ValidationResult)
def validate_active_plan(plan_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Validates the specified or currently active plan."""
    if plan_id:
        target_plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    else:
        target_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).order_by(BlockPlan.id.desc()).first()

    if not target_plan:
        raise HTTPException(status_code=404, detail="No active block plan found to validate.")
    return validate_plan(id=target_plan.id, db=db)


@router.post("/approve", response_model=BlockPlanResponse)
def approve_active_plan(
    approval_req: ApprovalRequest,
    plan_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """Approves specified or currently active plan."""
    if plan_id:
        target_plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    else:
        target_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).order_by(BlockPlan.id.desc()).first()

    if not target_plan:
        raise HTTPException(status_code=404, detail="No active block plan found.")
    return approve_plan(id=target_plan.id, approval_req=approval_req, db=db, current_user=current_user)


@router.post("/reject", response_model=BlockPlanResponse)
def reject_active_plan(
    approval_req: ApprovalRequest,
    plan_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """Rejects specified or currently active plan."""
    if plan_id:
        target_plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
    else:
        target_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).order_by(BlockPlan.id.desc()).first()

    if not target_plan:
        raise HTTPException(status_code=404, detail="No active block plan found.")
    return approve_plan(id=target_plan.id, approval_req=ApprovalRequest(action="REJECT", reason=approval_req.reason), db=db, current_user=current_user)


@router.post("/replan")
def trigger_replan(
    corridor_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """Triggers dynamic replan using current requests and train state."""
    plan = PlanningService.run_optimization(
        db=db,
        strategy="PLAN_A",
        corridor_id=corridor_id,
        user=current_user
    )
    return plan


@router.post("/plans/{id}/department-accept", response_model=BlockPlanResponse)
def department_accept_plan(
    id: int,
    req: Optional[DepartmentPlanActionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Department formally accepts an approved master block schedule."""
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Block Plan not found.")

    dept_id = current_user.department_id if current_user.role == "department_user" else None
    accepted_count = 0

    for pj in plan.plan_jobs:
        if pj.is_scheduled and pj.job:
            if dept_id is None or pj.job.department_id == dept_id:
                j = pj.job
                old_st = j.status
                j.status = "DEPARTMENT_ACCEPTED"
                j.execution_status = "READY"
                history = list(j.state_history_json or [])
                history.append({
                    "from_state": old_st,
                    "to_state": "DEPARTMENT_ACCEPTED",
                    "acting_user": current_user.username,
                    "user_id": current_user.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "reason": req.remarks if req and req.remarks else "Department accepted approved block schedule"
                })
                j.state_history_json = history
                accepted_count += 1

    # Notify Chief Controller / Railway Planner
    notif = Notification(
        title=f"Plan Accepted: {plan.plan_code}",
        message=f"Department {current_user.department.code if current_user.department else 'User'} accepted approved schedule for {accepted_count} job(s) in {plan.plan_code}. Field crews placed in READY status.",
        notification_type="INFO",
        target_entity="BLOCK_PLAN",
        target_id=str(plan.id)
    )
    db.add(notif)

    audit = AuditLog(
        user_id=current_user.id,
        action="DEPARTMENT_ACCEPT_PLAN",
        entity_type="BLOCK_PLAN",
        entity_id=str(plan.id),
        details_json={"accepted_jobs_count": accepted_count, "remarks": req.remarks if req else None}
    )
    db.add(audit)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/plans/{id}/department-request-change", response_model=BlockPlanResponse)
def department_request_change(
    id: int,
    req: DepartmentPlanActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Department requests a schedule change or operational adjustment from the Railway Planner."""
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Block Plan not found.")

    if not req.remarks or not req.remarks.strip():
        raise HTTPException(status_code=400, detail="Operational remarks/justification required when requesting changes.")

    dept_id = current_user.department_id if current_user.role == "department_user" else None
    plan.approval_status = "CHANGE_REQUESTED"
    affected_count = 0

    for pj in plan.plan_jobs:
        if pj.is_scheduled and pj.job:
            if dept_id is None or pj.job.department_id == dept_id:
                j = pj.job
                old_st = j.status
                j.status = "CHANGE_REQUESTED"
                j.department_remarks = req.remarks
                history = list(j.state_history_json or [])
                history.append({
                    "from_state": old_st,
                    "to_state": "CHANGE_REQUESTED",
                    "acting_user": current_user.username,
                    "user_id": current_user.id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "reason": req.remarks
                })
                j.state_history_json = history
                affected_count += 1

    # High Priority Notification to Railway Planner
    notif = Notification(
        title=f"Change Requested: {plan.plan_code}",
        message=f"Department {current_user.department.code if current_user.department else 'User'} requested revision for Plan {plan.plan_code}. Remarks: {req.remarks}",
        notification_type="CHANGE_REQUESTED",
        target_entity="BLOCK_PLAN",
        target_id=str(plan.id)
    )
    db.add(notif)

    audit = AuditLog(
        user_id=current_user.id,
        action="DEPARTMENT_REQUEST_CHANGE",
        entity_type="BLOCK_PLAN",
        entity_id=str(plan.id),
        details_json={"reason": req.remarks, "affected_jobs_count": affected_count}
    )
    db.add(audit)
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/plans/{id}/department-decline", response_model=BlockPlanResponse)
def department_decline_plan(
    id: int,
    req: DepartmentPlanActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Department declines approved block plan."""
    plan = db.query(BlockPlan).filter(BlockPlan.id == id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Block Plan not found.")

    dept_id = current_user.department_id if current_user.role == "department_user" else None
    for pj in plan.plan_jobs:
        if pj.job and (dept_id is None or pj.job.department_id == dept_id):
            pj.job.status = "DRAFT"
            pj.job.department_remarks = req.remarks or "Declined by department"

    notif = Notification(
        title=f"Plan Declined: {plan.plan_code}",
        message=f"Department {current_user.department.code if current_user.department else 'User'} declined Plan {plan.plan_code}. Remarks: {req.remarks}",
        notification_type="CHANGE_REQUESTED",
        target_entity="BLOCK_PLAN",
        target_id=str(plan.id)
    )
    db.add(notif)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/requests/{id}/planner-review")
def get_planner_request_review(id: int, db: Session = Depends(get_db)):
    """
    Returns structured railway-style operational review packet for the Railway Planner.
    Includes request details, asset details, train occupancy, available windows, compatible jobs, and CP-SAT options.
    """
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Maintenance job {id} not found.")

    # Find occupancies on this section/corridor
    all_occs = TrainService.calculate_all_occupancies(db)
    sec_id = job.section_id
    sec_occs = [o for o in all_occs if (sec_id is None or o["section_id"] == sec_id)]

    # Find feasible windows
    all_windows = PlanningService.generate_windows(db)
    candidate_windows = [
        w for w in all_windows
        if (sec_id is None or w["section_id"] == sec_id) and w["usable_duration_min"] >= job.estimated_duration_min
    ]

    # Find compatible jobs on same corridor
    jobs_db = db.query(MaintenanceJob).filter(MaintenanceJob.id != job.id, MaintenanceJob.status.in_(["SUBMITTED", "PLANNING", "UNDER_REVIEW"])).all()
    compatible_jobs = []
    for other in jobs_db:
        if other.section_id == job.section_id or (job.start_station_code == other.start_station_code and job.end_station_code == other.end_station_code):
            compatible_jobs.append({
                "id": other.id,
                "job_code": other.job_code,
                "department_code": other.department.code if other.department else "ENGG",
                "work_type": other.work_type,
                "duration_min": other.estimated_duration_min,
                "priority_score": other.priority_score
            })

    from app.algorithms.explain import PlanExplainabilityEngine
    job_dict = {
        "id": job.id,
        "job_code": job.job_code,
        "work_type": job.work_type,
        "department_code": job.department.code if job.department else "ENGG",
        "user_priority": job.user_priority,
        "due_date": job.due_date,
        "is_emergency": job.is_emergency,
        "priority_score": job.priority_score,
        "priority_explanation": job.priority_explanation
    }
    explanation = PlanExplainabilityEngine.explain_job_priority(job_dict)

    return {
        "job": {
            "id": job.id,
            "job_code": job.job_code,
            "department_code": job.department.code if job.department else "ENGG",
            "department_name": job.department.name if job.department else "Engineering",
            "asset_code": job.asset.asset_code if job.asset else "TRACK_PWAY",
            "asset_name": job.asset.asset_name if job.asset else "Permanent Way Track Section",
            "asset_type": job.asset.asset_type if job.asset else "P-WAY",
            "work_type": job.work_type,
            "description": job.description,
            "start_station_code": job.start_station_code,
            "end_station_code": job.end_station_code,
            "section_name": job.section.name if job.section else f"{job.start_station_code} - {job.end_station_code}",
            "section_id": job.section_id,
            "user_priority": job.user_priority,
            "due_date": job.due_date,
            "overdue_days": job.overdue_days,
            "duration_min": job.estimated_duration_min,
            "preferred_start_min": job.preferred_start_min,
            "preferred_end_min": job.preferred_end_min,
            "status": job.status,
            "is_emergency": job.is_emergency,
            "is_locked": job.is_locked,
            "calculated_criticality": job.calculated_criticality,
            "calculated_safety_impact": job.calculated_safety_impact,
            "calculated_urgency": job.calculated_urgency,
            "priority_score": job.priority_score,
            "safety_tier": job.safety_tier,
            "planner_remarks": job.planner_remarks,
            "department_remarks": job.department_remarks,
            "state_history": job.state_history_json or []
        },
        "priority_explanation": explanation,
        "occupancies": sec_occs,
        "candidate_windows": candidate_windows,
        "compatible_jobs": compatible_jobs,
        "feasible_window_count": len(candidate_windows),
        "has_feasible_window": len(candidate_windows) > 0,
        "recommended_window": candidate_windows[0] if candidate_windows else None
    }

@router.get("/compatibility")
def get_compatibility_graph(db: Session = Depends(get_db)):
    """Returns NetworkX multi-department compatibility graph nodes, edges, and candidate clusters."""
    jobs_db = db.query(MaintenanceJob).all()
    jobs = [
        {
            "id": j.id,
            "job_code": j.job_code,
            "department_code": j.department.code if j.department else "ENGG",
            "section_id": j.section_id,
            "location_km": j.location_km,
            "work_type": j.work_type,
            "estimated_duration_min": j.estimated_duration_min,
            "is_emergency": j.is_emergency
        }
        for j in jobs_db
    ]

    G = CompatibilityGraphEngine.build_graph(jobs)
    nodes = [{"id": n, **G.nodes[n]} for n in G.nodes]
    edges = [{"source": u, "target": v, **G.edges[u, v]} for u, v in G.edges]
    coordination_groups = CompatibilityGraphEngine.get_candidate_coordination_groups(G)

    return {
        "nodes": nodes,
        "edges": edges,
        "coordination_candidate_groups": coordination_groups
    }

