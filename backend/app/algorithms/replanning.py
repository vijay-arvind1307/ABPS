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
        # COMPLETED -> FREEZE / EXCLUDE from future possession
        # IN_PROGRESS / ACTIVE -> REASON ABOUT REMAINING WORK
        # COMMITTED / PENDING -> RE-OPTIMIZE under rolling horizon

        job_dict = {}
        for j in jobs:
            jd = dict(j)
            st = str(jd.get("status", jd.get("execution_status", ""))).upper()
            if st == "COMPLETED":
                # Completed jobs are permanently frozen
                continue
            elif st in ("IN_PROGRESS", "ACTIVE"):
                # Reason about remaining duration rather than locking historical start time
                actual_st = jd.get("actual_start_min", jd.get("scheduled_start_min", 0))
                elapsed = max(0, jd.get("elapsed_min", 0))
                orig_dur = jd.get("estimated_duration_min", 60)
                remaining_dur = max(15, orig_dur - elapsed)
                jd["estimated_duration_min"] = remaining_dur
                jd["is_locked"] = True
                jd["locked_start_min"] = actual_st + elapsed
            job_dict[jd["id"]] = jd

        for pj in current_plan_jobs:
            j_id = pj["job_id"]
            if j_id in job_dict:
                exec_st = str(pj.get("execution_status", "PENDING")).upper()
                if exec_st == "COMPLETED":
                    job_dict.pop(j_id, None)
                elif exec_st in ("IN_PROGRESS", "ACTIVE") or pj.get("is_locked"):
                    job_dict[j_id]["is_locked"] = True
                    if pj.get("scheduled_start_min") is not None and not job_dict[j_id].get("locked_start_min"):
                        job_dict[j_id]["locked_start_min"] = pj.get("scheduled_start_min")

        frozen_completed_jobs = []
        for pj in current_plan_jobs:
            exec_st = str(pj.get("execution_status", "")).upper()
            j_info = next((j for j in jobs if j.get("id") == pj.get("job_id")), {})
            st = str(j_info.get("status", "")).upper()
            if exec_st == "COMPLETED" or st == "COMPLETED":
                s_min = pj.get("actual_start_min") if pj.get("actual_start_min") is not None else pj.get("scheduled_start_min")
                e_min = pj.get("actual_end_min") if pj.get("actual_end_min") is not None else pj.get("scheduled_end_min")
                dur = pj.get("scheduled_duration_min") or ((e_min - s_min) if (e_min is not None and s_min is not None) else 60)
                frozen_completed_jobs.append({
                    "job_id": pj["job_id"],
                    "job_code": pj.get("job_code", f"JOB_{pj['job_id']}"),
                    "window_id": pj.get("window_id"),
                    "section_id": pj.get("section_id", j_info.get("section_id")),
                    "work_type": j_info.get("work_type"),
                    "scheduled_start_min": s_min,
                    "scheduled_end_min": e_min,
                    "scheduled_duration_min": dur,
                    "block_code": pj.get("block_code"),
                    "is_locked": True,
                    "is_scheduled": True,
                    "execution_status": "COMPLETED"
                })

        # Run CP-SAT on updated state
        solver = CPSATSolver(time_limit_seconds=solver_time_limit)
        result = solver.solve(
            jobs=list(job_dict.values()),
            windows=new_windows,
            strategy=strategy,
            enforce_locks=True
        )

        result["scheduled_jobs"] = frozen_completed_jobs + result["scheduled_jobs"]

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
