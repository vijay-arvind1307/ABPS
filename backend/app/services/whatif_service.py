from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import BlockPlan, MaintenanceJob, WhatIfScenario, User, RailwaySection
from app.schemas.schemas import WhatIfRequest
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.windows import WindowEngine
from app.services.train_service import TrainService
from app.services.planning_service import PlanningService


class WhatIfService:
    @staticmethod
    def simulate_scenario(db: Session, request: WhatIfRequest, user: Optional[User] = None) -> Dict[str, Any]:
        """
        Executes a sandboxed What-If simulation by perturbing operating conditions without altering master active plan.
        """
        base_plan = db.query(BlockPlan).filter(BlockPlan.id == request.base_plan_id).first()
        if not base_plan:
            base_plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).first()

        # 1. Fetch base jobs and apply perturbations
        jobs_db = db.query(MaintenanceJob).all()
        perturbed_jobs = []
        for j in jobs_db:
            dur = int(j.estimated_duration_min * request.duration_multiplier)
            is_em = j.is_emergency
            if request.emergency_job_id and j.id == request.emergency_job_id:
                is_em = True

            perturbed_jobs.append({
                "id": j.id,
                "job_code": j.job_code,
                "department_code": j.department.code if j.department else "ENGG",
                "section_id": j.section_id,
                "location_km": j.location_km,
                "work_type": j.work_type,
                "criticality": j.criticality,
                "safety_impact": 95.0 if is_em else j.safety_impact,
                "operational_impact": j.operational_impact,
                "urgency": 95.0 if is_em else j.urgency,
                "overdue_days": j.overdue_days,
                "priority_score": 95.0 if is_em else j.priority_score,
                "safety_tier": "Tier 1 (Emergency)" if is_em else j.safety_tier,
                "estimated_duration_min": dur,
                "is_emergency": is_em,
                "is_locked": j.is_locked,
                "locked_start_min": j.locked_start_min,
                "status": j.status
            })

        # 2. Derive windows with train delay perturbation if requested
        occupancies = TrainService.calculate_all_occupancies(db)
        if request.train_delay_min > 0 and request.train_delay_train_no:
            for occ in occupancies:
                if occ["train_number"] == request.train_delay_train_no:
                    occ["estimated_entry_min"] += request.train_delay_min
                    occ["estimated_exit_min"] += request.train_delay_min

        # Generate perturbed windows
        sections = db.query(RailwaySection).all()
        sec_map = {s.id: s.corridor_id for s in sections}
        job_sec_ids = set([j["section_id"] for j in perturbed_jobs if j.get("section_id")])
        if not job_sec_ids:
            job_sec_ids = set([s.id for s in sections])

        sim_windows = []
        for sid in job_sec_ids:
            corr_id = sec_map.get(sid, 1)
            sim_windows.extend(
                WindowEngine.calculate_feasible_windows(
                    section_id=sid,
                    corridor_id=corr_id,
                    occupancies=occupancies
                )
            )

        # 3. Run CP-SAT on sandboxed scenario
        solver = CPSATSolver(time_limit_seconds=10)
        sim_result = solver.solve(
            jobs=perturbed_jobs,
            windows=sim_windows,
            strategy="PLAN_A"
        )

        # 4. Compare metrics against base plan
        comparison = {
            "scenario_name": request.scenario_name,
            "description": request.description,
            "perturbations": request.model_dump(),
            "base_metrics": {
                "critical_jobs_completed": base_plan.critical_jobs_completed if base_plan else 0,
                "total_jobs_completed": base_plan.total_jobs_completed if base_plan else 0,
                "total_blocks_count": base_plan.total_blocks_count if base_plan else 0,
                "block_utilization_pct": base_plan.block_utilization_pct if base_plan else 0.0,
                "train_impact_score": base_plan.train_impact_score if base_plan else 0.0,
                "asset_availability_proxy": base_plan.asset_availability_proxy if base_plan else 0.0
            },
            "scenario_metrics": {
                "critical_jobs_completed": sim_result["critical_jobs_completed"],
                "total_jobs_completed": sim_result["total_jobs_completed"],
                "total_blocks_count": sim_result["total_blocks_count"],
                "block_utilization_pct": sim_result["block_utilization_pct"],
                "train_impact_score": sim_result["train_impact_score"],
                "asset_availability_proxy": sim_result["asset_availability_proxy"],
                "solver_status": sim_result["solver_status"],
                "computation_time_ms": sim_result["computation_time_ms"]
            },
            "scheduled_jobs": sim_result["scheduled_jobs"],
            "deferred_jobs": sim_result["deferred_jobs"]
        }

        # Store scenario record in DB
        scenario_record = WhatIfScenario(
            scenario_name=request.scenario_name,
            description=request.description,
            base_plan_id=base_plan.id if base_plan else 1,
            perturbations_json=request.model_dump(),
            result_metrics_json=comparison,
            created_by_id=user.id if user else None
        )
        db.add(scenario_record)
        db.commit()

        return comparison
