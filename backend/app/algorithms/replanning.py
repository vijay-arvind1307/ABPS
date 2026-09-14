from typing import List, Dict, Any, Tuple
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.validator import DeterministicSafetyValidator


class DynamicReplanningEngine:
    """
    Rolling-Horizon Dynamic Re-Planning Engine.
    Handles real-time operational disturbances (train delays, emergency jobs, maintenance overruns),
    identifies affected planning sectors, freezes protected/in-progress work, and computes a revised conflict-free plan.
    """

    @classmethod
    def re_optimize(
        cls,
        current_plan_jobs: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
        new_windows: List[Dict[str, Any]],
        new_occupancies: List[Dict[str, Any]],
        trigger_event: str,
        affected_train_number: str = None,
        affected_section_id: int = None,
        strategy: str = "PLAN_A",
        solver_time_limit: int = 15
    ) -> Dict[str, Any]:
        # Partition jobs based on execution status
        # COMPLETED -> FIXED
        # IN_PROGRESS -> PROTECTED
        # COMMITTED / PENDING -> RE-OPTIMIZABLE unless locked

        job_dict = {j["id"]: dict(j) for j in jobs}

        # Check jobs list itself
        for j_id, j_data in job_dict.items():
            if j_data.get("status") in ("COMPLETED", "IN_PROGRESS") or j_data.get("execution_status") in ("COMPLETED", "IN_PROGRESS"):
                j_data["is_locked"] = True
                if j_data.get("actual_start_min") is not None:
                    j_data["locked_start_min"] = j_data["actual_start_min"]

        for pj in current_plan_jobs:
            j_id = pj["job_id"]
            if j_id in job_dict:
                exec_st = pj.get("execution_status", "PENDING")
                if exec_st in ("COMPLETED", "IN_PROGRESS") or pj.get("is_locked"):
                    job_dict[j_id]["is_locked"] = True
                    job_dict[j_id]["locked_start_min"] = pj.get("scheduled_start_min")

        # Run CP-SAT on updated state
        solver = CPSATSolver(time_limit_seconds=solver_time_limit)
        result = solver.solve(
            jobs=list(job_dict.values()),
            windows=new_windows,
            strategy=strategy,
            enforce_locks=True
        )

        # Validate result against safety constraints
        is_valid, errors, warnings = DeterministicSafetyValidator.validate_plan(
            scheduled_jobs=result["scheduled_jobs"],
            windows=new_windows,
            occupancies=new_occupancies
        )

        result["is_valid"] = is_valid
        result["validation_errors"] = errors
        result["validation_warnings"] = warnings
        result["trigger_event"] = trigger_event
        result["affected_train_number"] = affected_train_number
        result["affected_section_id"] = affected_section_id

        # Compute delta changes compared to previous plan
        old_scheduled_map = {pj["job_id"]: pj for pj in current_plan_jobs if pj.get("is_scheduled")}
        new_scheduled_map = {sj["job_id"]: sj for sj in result["scheduled_jobs"]}

        changed_jobs = []
        for j_id, new_sj in new_scheduled_map.items():
            if j_id in old_scheduled_map:
                old_sj = old_scheduled_map[j_id]
                if (old_sj.get("scheduled_start_min") != new_sj["scheduled_start_min"] or
                    old_sj.get("window_id") != new_sj["window_id"]):
                    changed_jobs.append({
                        "job_id": j_id,
                        "job_code": new_sj["job_code"],
                        "change_type": "TIMING_SHIFT",
                        "old_start_min": old_sj.get("scheduled_start_min"),
                        "new_start_min": new_sj["scheduled_start_min"],
                        "old_block": old_sj.get("block_code"),
                        "new_block": new_sj.get("block_code")
                    })
            else:
                changed_jobs.append({
                    "job_id": j_id,
                    "job_code": new_sj["job_code"],
                    "change_type": "NEWLY_SCHEDULED",
                    "new_start_min": new_sj["scheduled_start_min"],
                    "new_block": new_sj.get("block_code")
                })

        for j_id, old_sj in old_scheduled_map.items():
            if j_id not in new_scheduled_map:
                changed_jobs.append({
                    "job_id": j_id,
                    "job_code": old_sj.get("job_code", f"JOB_{j_id}"),
                    "change_type": "DEFERRED_DUE_TO_DISRUPTION",
                    "old_start_min": old_sj.get("scheduled_start_min")
                })

        result["delta_changes"] = changed_jobs
        return result
