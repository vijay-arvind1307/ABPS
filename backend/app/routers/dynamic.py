from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import BlockPlan, PlanJob, PlanVersion, MaintenanceJob, User, PlannerAction, AuditLog
from app.schemas.schemas import DelaySimulationRequest, DynamicReplanRequest
from app.services.train_service import TrainService
from app.services.planning_service import PlanningService
from app.algorithms.replanning import DynamicReplanningEngine
from app.routers.auth import get_current_user, require_role

router = APIRouter(prefix="/dynamic", tags=["Dynamic Re-Planning & Disturbance Management"])


@router.post("/simulate-delay")
def simulate_train_delay(
    req: DelaySimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """
    Simulates a live train delay event.
    Updates train telemetry, recalculates section occupancies, and identifies impacted blocks.
    """
    res = TrainService.simulate_train_delay(db, req.train_number, req.additional_delay_min)

    # Find affected sections & blocks
    occupancies = TrainService.calculate_all_occupancies(db)
    affected_occs = [o for o in occupancies if o["train_number"] == req.train_number]
    affected_section_ids = list(set([o["section_id"] for o in affected_occs]))

    # Find affected active plan jobs
    active_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).first()
    affected_jobs = []
    if active_plan:
        plan_jobs = db.query(PlanJob).filter(PlanJob.plan_id == active_plan.id, PlanJob.is_scheduled == True).all()
        for pj in plan_jobs:
            if pj.job and pj.job.section_id in affected_section_ids:
                # Check timing clash with delayed train
                for occ in affected_occs:
                    if occ["section_id"] == pj.job.section_id:
                        if max(pj.scheduled_start_min, occ["estimated_entry_min"]) < min(pj.scheduled_end_min, occ["estimated_exit_min"]):
                            affected_jobs.append({
                                "job_id": pj.job_id,
                                "job_code": pj.job.job_code,
                                "section_id": pj.job.section_id,
                                "scheduled_start_min": pj.scheduled_start_min,
                                "scheduled_end_min": pj.scheduled_end_min,
                                "conflicting_train": req.train_number,
                                "train_occupancy": f"{occ['estimated_entry_min']}-{occ['estimated_exit_min']}m"
                            })

    return {
        "event": "TRAIN_DELAY_INJECTED",
        "train_number": req.train_number,
        "additional_delay_min": req.additional_delay_min,
        "affected_sections": affected_section_ids,
        "conflicting_scheduled_jobs": affected_jobs,
        "action_required": "Trigger Dynamic Re-Planning to resolve conflicts." if affected_jobs else "No direct maintenance collision."
    }


@router.post("/replan")
def dynamic_replan(
    req: DynamicReplanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["railway_planner", "admin"]))
):
    """
    Executes rolling-horizon dynamic re-planning after disturbance.
    Freezes completed & protected decisions, generates revised Plan Version, and computes old vs new delta diff.
    """
    base_plan = db.query(BlockPlan).filter(BlockPlan.id == req.base_plan_id).first()
    if not base_plan:
        base_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).first()
    if not base_plan:
        raise HTTPException(status_code=404, detail="Base plan not found for dynamic re-planning.")

    current_pjs = [
        {
            "job_id": pj.job_id,
            "job_code": pj.job.job_code if pj.job else f"JOB_{pj.job_id}",
            "scheduled_start_min": pj.scheduled_start_min,
            "scheduled_end_min": pj.scheduled_end_min,
            "window_id": pj.window_id,
            "block_code": pj.block_code,
            "is_scheduled": pj.is_scheduled,
            "is_locked": pj.is_locked,
            "execution_status": pj.execution_status
        }
        for pj in base_plan.plan_jobs
    ]

    jobs_db = db.query(MaintenanceJob).all()
    jobs = [
        {
            "id": j.id,
            "job_code": j.job_code,
            "department_code": j.department.code if j.department else "ENGG",
            "section_id": j.section_id,
            "location_km": j.location_km,
            "work_type": j.work_type,
            "criticality": j.criticality,
            "safety_impact": j.safety_impact,
            "operational_impact": j.operational_impact,
            "urgency": j.urgency,
            "overdue_days": j.overdue_days,
            "priority_score": j.priority_score,
            "safety_tier": j.safety_tier,
            "estimated_duration_min": j.estimated_duration_min,
            "is_emergency": j.is_emergency,
            "is_locked": j.is_locked,
            "locked_start_min": j.locked_start_min,
            "status": j.status
        }
        for j in jobs_db
    ]

    new_windows = PlanningService.generate_windows(db)
    new_occupancies = TrainService.calculate_all_occupancies(db)

    replan_res = DynamicReplanningEngine.re_optimize(
        current_plan_jobs=current_pjs,
        jobs=jobs,
        new_windows=new_windows,
        new_occupancies=new_occupancies,
        trigger_event=req.trigger_event,
        affected_train_number=req.affected_train_number,
        affected_section_id=req.affected_section_id,
        strategy=base_plan.strategy
    )

    # Create new BlockPlan Version V(n+1)
    new_version_num = base_plan.version + 1
    new_plan_code = f"{base_plan.plan_code}_V{new_version_num}"

    # Deactivate previous
    db.query(BlockPlan).filter(BlockPlan.strategy == base_plan.strategy).update({"is_active": False})

    new_plan = BlockPlan(
        plan_code=new_plan_code,
        plan_name=f"{base_plan.plan_name} (Re-planned V{new_version_num})",
        strategy=base_plan.strategy,
        solver_status=replan_res["solver_status"],
        objective_score=replan_res["objective_score"],
        critical_jobs_completed=replan_res["critical_jobs_completed"],
        total_critical_jobs=replan_res["total_critical_jobs"],
        total_jobs_completed=replan_res["total_jobs_completed"],
        total_jobs_demanded=replan_res["total_jobs_demanded"],
        total_blocks_count=replan_res["total_blocks_count"],
        block_utilization_pct=replan_res["block_utilization_pct"],
        train_impact_score=replan_res["train_impact_score"],
        asset_availability_proxy=replan_res["asset_availability_proxy"],
        computation_time_ms=replan_res["computation_time_ms"],
        validation_status="VALID" if replan_res["is_valid"] else "INVALID",
        validation_errors_json=replan_res["validation_errors"] if not replan_res["is_valid"] else None,
        approval_status="PROPOSED",
        version=new_version_num,
        is_active=True,
        created_by_id=current_user.id
    )
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)

    # Add plan jobs
    for sj in replan_res["scheduled_jobs"]:
        pj = PlanJob(
            plan_id=new_plan.id,
            job_id=sj["job_id"],
            window_id=sj["window_id"],
            scheduled_start_min=sj["scheduled_start_min"],
            scheduled_end_min=sj["scheduled_end_min"],
            scheduled_duration_min=sj["scheduled_duration_min"],
            block_code=sj["block_code"],
            is_scheduled=True,
            is_locked=sj.get("is_locked", False),
            execution_status="PENDING"
        )
        db.add(pj)

    for def_j_id in replan_res["deferred_jobs"]:
        pj = PlanJob(
            plan_id=new_plan.id,
            job_id=def_j_id,
            window_id=None,
            scheduled_start_min=None,
            scheduled_end_min=None,
            scheduled_duration_min=None,
            block_code=None,
            is_scheduled=False,
            is_locked=False,
            execution_status="PENDING"
        )
        db.add(pj)

    # Save PlanVersion record
    p_ver = PlanVersion(
        original_plan_id=base_plan.id,
        version_number=new_version_num,
        trigger_event=req.trigger_event,
        changes_summary_json=replan_res["delta_changes"],
        created_by_id=current_user.id
    )
    db.add(p_ver)
    db.commit()

    return {
        "new_plan_id": new_plan.id,
        "new_plan_code": new_plan.plan_code,
        "version": new_version_num,
        "solver_status": new_plan.solver_status,
        "validation_status": new_plan.validation_status,
        "delta_changes": replan_res["delta_changes"],
        "summary": f"Dynamic Re-Planning generated Plan {new_plan.plan_code} (Version {new_version_num}) resolving all train delay conflicts."
    }
