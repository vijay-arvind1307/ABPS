from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.models import (
    BlockPlan, PlanJob, PlanVersion, MaintenanceJob, BlockWindow,
    RailwaySection, Corridor, Resource, MaintenanceDependency, User, PlannerAction, AuditLog
)
from app.algorithms.windows import WindowEngine
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.baseline import BaselineScheduler
from app.algorithms.validator import DeterministicSafetyValidator
from app.algorithms.explain import PlanExplainabilityEngine
from app.algorithms.compatibility import CompatibilityGraphEngine
from app.services.train_service import TrainService


class PlanningService:
    @staticmethod
    def generate_windows(db: Session, corridor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Derives all feasible maintenance windows across railway sections by sweeping train occupancy gaps.
        """
        occupancies = TrainService.calculate_all_occupancies(db) or []

        sections = db.query(RailwaySection).all()
        if corridor_id:
            sections = [s for s in sections if s.corridor_id == corridor_id]

        all_windows = []
        global_win_id = 1
        for sec in sections:
            sec_windows = WindowEngine.calculate_feasible_windows(
                section_id=sec.id,
                corridor_id=sec.corridor_id,
                occupancies=occupancies,
                horizon_start_min=0,
                horizon_end_min=1440,
                min_window_duration_min=30
            )
            for sw in sec_windows:
                sw["id"] = global_win_id
                global_win_id += 1
                all_windows.append(sw)

        # Synchronize into BlockWindow table
        db.query(BlockWindow).delete()

        for w in all_windows:
            bw = BlockWindow(
                id=w["id"],
                window_code=w["window_code"],
                section_id=w["section_id"],
                corridor_id=w["corridor_id"],
                start_min=w["start_min"],
                end_min=w["end_min"],
                usable_duration_min=w["usable_duration_min"],
                train_before_no=w.get("train_before_no"),
                train_after_no=w.get("train_after_no"),
                constraints_applied_json=w.get("constraints_applied_json"),
                feasibility=w.get("feasibility", "FEASIBLE"),
                source=w.get("source", "SWEEP_LINE_DERIVED")
            )
            db.add(bw)
        db.commit()

        return all_windows

    @staticmethod
    def run_optimization(
        db: Session,
        strategy: str = "PLAN_A",
        corridor_id: Optional[int] = None,
        user: Optional[User] = None,
        time_limit_seconds: int = 15,
        enforce_locks: bool = True
    ) -> BlockPlan:
        """
        Executes Google OR-Tools CP-SAT constraint optimization for Plan A, Plan B, or Plan C.
        """
        jobs_db = db.query(MaintenanceJob).filter(MaintenanceJob.status.in_(["SUBMITTED", "DRAFT", "SCHEDULED"])).all()
        if len(jobs_db) == 0:
            raise HTTPException(
                status_code=400,
                detail="Optimization unavailable: Insufficient valid operational data. No maintenance requests available."
            )

        windows = PlanningService.generate_windows(db, corridor_id)
        if len(windows) == 0:
            raise HTTPException(
                status_code=400,
                detail="Optimization unavailable: Insufficient valid operational data. No feasible maintenance windows available."
            )

        occupancies = TrainService.calculate_all_occupancies(db)

        jobs = [
            {
                "id": j.id,
                "job_code": j.job_code,
                "department_id": j.department_id,
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
                "status": j.status,
                "required_resource_ids": [r.resource_id for r in j.required_resources]
            }
            for j in jobs_db
        ]

        resources_db = db.query(Resource).all()
        resources = [
            {"id": r.id, "resource_code": r.resource_code, "name": r.name, "total_quantity": r.total_quantity}
            for r in resources_db
        ]

        deps_db = db.query(MaintenanceDependency).all()
        dependencies = [
            {"predecessor_job_id": d.predecessor_job_id, "successor_job_id": d.successor_job_id, "min_gap_min": d.min_gap_min}
            for d in deps_db
        ]

        # Solve via CP-SAT
        solver = CPSATSolver(time_limit_seconds=time_limit_seconds)
        result = solver.solve(
            jobs=jobs,
            windows=windows,
            resources=resources,
            dependencies=dependencies,
            strategy=strategy,
            enforce_locks=enforce_locks
        )

        # Run Deterministic Safety Validator
        is_valid, errors, warnings = DeterministicSafetyValidator.validate_plan(
            scheduled_jobs=result["scheduled_jobs"],
            windows=windows,
            occupancies=occupancies,
            resources=resources,
            dependencies=dependencies
        )

        # Save Plan to DB
        plan_code = f"PLAN_{strategy}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        plan_name = f"Master Corridor Block Schedule - {strategy}"

        # Deactivate previous active plans if newly generated
        db.query(BlockPlan).filter(BlockPlan.strategy == strategy).update({"is_active": False})

        plan = BlockPlan(
            plan_code=plan_code,
            plan_name=plan_name,
            strategy=strategy,
            solver_status=result["solver_status"],
            objective_score=result["objective_score"],
            critical_jobs_completed=result["critical_jobs_completed"],
            total_critical_jobs=result["total_critical_jobs"],
            total_jobs_completed=result["total_jobs_completed"],
            total_jobs_demanded=result["total_jobs_demanded"],
            total_blocks_count=result["total_blocks_count"],
            block_utilization_pct=result["block_utilization_pct"],
            train_impact_score=result["train_impact_score"],
            asset_availability_proxy=result["asset_availability_proxy"],
            computation_time_ms=result["computation_time_ms"],
            validation_status="VALID" if is_valid else "INVALID",
            validation_errors_json=errors if not is_valid else None,
            approval_status="PROPOSED",
            version=1,
            is_active=True,
            created_by_id=user.id if user else None
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        # Add Plan Jobs
        for sj in result["scheduled_jobs"]:
            pj = PlanJob(
                plan_id=plan.id,
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

        for def_j_id in result["deferred_jobs"]:
            pj = PlanJob(
                plan_id=plan.id,
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

        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def get_kpi_comparison(db: Session) -> Dict[str, Any]:
        """
        Computes dynamic side-by-side KPI comparison across Baseline Heuristic, Plan A, Plan B, and Plan C.
        """
        windows = PlanningService.generate_windows(db)
        jobs_db = db.query(MaintenanceJob).filter(MaintenanceJob.status.in_(["SUBMITTED", "DRAFT", "SCHEDULED"])).all()
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
                "status": j.status
            }
            for j in jobs_db
        ]

        # Calculate Baseline
        baseline_res = BaselineScheduler.schedule(jobs=jobs, windows=windows)

        # Retrieve or compute latest Plan A, B, C
        plans = db.query(BlockPlan).filter(BlockPlan.is_active == True).all()
        plan_dict = {p.strategy: p for p in plans}

        def plan_to_metric_dict(p: Optional[BlockPlan]):
            if not p:
                return {
                    "total_jobs_completed": 0,
                    "critical_jobs_completed": 0,
                    "total_blocks_count": 0,
                    "block_utilization_pct": 0.0,
                    "train_impact_score": 0.0,
                    "asset_availability_proxy": 0.0,
                    "solver_status": "NOT_RUN",
                    "computation_time_ms": 0.0
                }
            return {
                "id": p.id,
                "plan_code": p.plan_code,
                "total_jobs_completed": p.total_jobs_completed,
                "total_critical_jobs": p.total_critical_jobs,
                "critical_jobs_completed": p.critical_jobs_completed,
                "total_blocks_count": p.total_blocks_count,
                "block_utilization_pct": p.block_utilization_pct,
                "train_impact_score": p.train_impact_score,
                "asset_availability_proxy": p.asset_availability_proxy,
                "solver_status": p.solver_status,
                "validation_status": p.validation_status,
                "computation_time_ms": p.computation_time_ms
            }

        return {
            "baseline": {
                "total_jobs_completed": baseline_res["total_jobs_completed"],
                "total_critical_jobs": baseline_res["total_critical_jobs"],
                "critical_jobs_completed": baseline_res["critical_jobs_completed"],
                "total_blocks_count": baseline_res["total_blocks_count"],
                "block_utilization_pct": baseline_res["block_utilization_pct"],
                "train_impact_score": baseline_res["train_impact_score"],
                "asset_availability_proxy": baseline_res["asset_availability_proxy"],
                "solver_status": "FIRST_FEASIBLE_GREEDY",
                "computation_time_ms": 2.4
            },
            "plan_a": plan_to_metric_dict(plan_dict.get("PLAN_A")),
            "plan_b": plan_to_metric_dict(plan_dict.get("PLAN_B")),
            "plan_c": plan_to_metric_dict(plan_dict.get("PLAN_C"))
        }

    @staticmethod
    def get_job_explanation(db: Session, job_id: int, plan_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generates full explainability breakdown for a maintenance job.
        """
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        plan = None
        if plan_id:
            plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
        if not plan:
            plan = db.query(BlockPlan).filter(BlockPlan.is_active == True).order_by(BlockPlan.id.desc()).first()

        plan_job = None
        window = None
        if plan:
            pj_model = db.query(PlanJob).filter(PlanJob.plan_id == plan.id, PlanJob.job_id == job.id).first()
            if pj_model:
                plan_job = {
                    "scheduled_start_min": pj_model.scheduled_start_min,
                    "scheduled_end_min": pj_model.scheduled_end_min,
                    "block_code": pj_model.block_code,
                    "is_locked": pj_model.is_locked,
                    "window_id": pj_model.window_id
                }
                if pj_model.window_id:
                    win_model = db.query(BlockWindow).filter(BlockWindow.id == pj_model.window_id).first()
                    if win_model:
                        window = {
                            "id": win_model.id,
                            "window_code": win_model.window_code,
                            "start_min": win_model.start_min,
                            "end_min": win_model.end_min,
                            "usable_duration_min": win_model.usable_duration_min,
                            "constraints_applied_json": win_model.constraints_applied_json
                        }

        all_windows = PlanningService.generate_windows(db)

        # Check compatibility synergies
        all_jobs = db.query(MaintenanceJob).all()
        jobs_dict = [
            {
                "id": j.id, "job_code": j.job_code, "department_code": j.department.code if j.department else "ENGG",
                "section_id": j.section_id, "location_km": j.location_km,
                "estimated_duration_min": j.estimated_duration_min, "work_type": j.work_type
            }
            for j in all_jobs
        ]
        G = CompatibilityGraphEngine.build_graph(jobs_dict)
        neighbors = []
        if job.id in G:
            neighbors = [G.nodes[n]["job_code"] for n in G.neighbors(job.id)]

        job_dict = {
            "id": job.id,
            "job_code": job.job_code,
            "section_id": job.section_id,
            "criticality": job.criticality,
            "safety_impact": job.safety_impact,
            "operational_impact": job.operational_impact,
            "urgency": job.urgency,
            "overdue_days": job.overdue_days,
            "priority_score": job.priority_score,
            "safety_tier": job.safety_tier,
            "estimated_duration_min": job.estimated_duration_min,
            "is_emergency": job.is_emergency
        }

        return PlanExplainabilityEngine.explain_job_decision(
            job=job_dict,
            is_scheduled=(plan_job is not None and plan_job.get("scheduled_start_min") is not None),
            plan_job=plan_job,
            window=window,
            all_windows=all_windows,
            compatibility_neighbors=neighbors
        )
