from typing import List, Dict, Any


class BaselineScheduler:
    """
    First-Feasible Priority-Ordered Baseline Scheduler.
    Greedily assigns highest-priority maintenance jobs to the earliest feasible available window.
    Provides the benchmark baseline to mathematically evaluate CP-SAT optimization gains.
    """

    @classmethod
    def schedule(
        cls,
        jobs: List[Dict[str, Any]],
        windows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        if not jobs or not windows:
            return {
                "solver_status": "NO_DATA",
                "critical_jobs_completed": 0,
                "total_critical_jobs": 0,
                "total_jobs_completed": 0,
                "total_jobs_demanded": len(jobs),
                "total_blocks_count": 0,
                "block_utilization_pct": 0.0,
                "train_impact_score": 0.0,
                "asset_availability_proxy": 0.0,
                "scheduled_jobs": [],
                "deferred_jobs": [j["id"] for j in jobs],
                "blocks": []
            }

        # Sort jobs descending by priority_score, then emergency flag
        sorted_jobs = sorted(
            jobs,
            key=lambda x: (x.get("is_emergency", False), x.get("priority_score", 50)),
            reverse=True
        )

        # Sort windows ascending by start_min
        sorted_windows = sorted(windows, key=lambda w: (w["section_id"], w["start_min"]))

        # Window remaining capacity tracker (window_id -> remaining usable minutes)
        window_remaining_capacity = {w["id"]: w["usable_duration_min"] for w in windows}
        window_current_pointer = {w["id"]: w["start_min"] for w in windows}
        window_map = {w["id"]: w for w in windows}

        scheduled_jobs = []
        deferred_jobs = []
        blocks = {}

        for j in sorted_jobs:
            j_id = j["id"]
            dur = j["estimated_duration_min"]
            assigned = False

            # Find first feasible window matching section and having enough capacity
            for w in sorted_windows:
                w_id = w["id"]
                if w["section_id"] == j["section_id"]:
                    if window_remaining_capacity[w_id] >= dur:
                        # Schedule in this window
                        start_time = window_current_pointer[w_id]
                        end_time = start_time + dur
                        blk_code = f"BLK_BASELINE_SEC{j['section_id']}_W{w_id}"

                        scheduled_jobs.append({
                            "job_id": j_id,
                            "job_code": j["job_code"],
                            "window_id": w_id,
                            "section_id": j["section_id"],
                            "scheduled_start_min": start_time,
                            "scheduled_end_min": end_time,
                            "scheduled_duration_min": dur,
                            "block_code": blk_code,
                            "is_scheduled": True
                        })

                        window_remaining_capacity[w_id] -= dur
                        window_current_pointer[w_id] += dur

                        if blk_code not in blocks:
                            blocks[blk_code] = {
                                "block_code": blk_code,
                                "window_id": w_id,
                                "section_id": j["section_id"],
                                "jobs": [],
                                "total_duration": 0,
                                "usable_duration": w["usable_duration_min"]
                            }
                        blocks[blk_code]["jobs"].append(j_id)
                        blocks[blk_code]["total_duration"] += dur

                        assigned = True
                        break

            if not assigned:
                deferred_jobs.append(j_id)

        # Compute real metrics
        total_blocks = len(blocks)
        total_used_duration = sum(b["total_duration"] for b in blocks.values())
        total_available_duration = sum(b["usable_duration"] for b in blocks.values())
        utilization_pct = round((total_used_duration / max(1, total_available_duration)) * 100, 1)

        critical_jobs_count = sum(
            1 for j in jobs
            if ("Tier 1" in j.get("safety_tier", "") or "Tier 2" in j.get("safety_tier", "") or j.get("is_emergency", False))
        )
        critical_completed = sum(
            1 for sj in scheduled_jobs
            if any(
                j["id"] == sj["job_id"] and ("Tier 1" in j.get("safety_tier", "") or "Tier 2" in j.get("safety_tier", "") or j.get("is_emergency", False))
                for j in jobs
            )
        )

        train_impact = round(35.0 + (total_blocks * 3.5), 1)
        asset_avail = round(min(90.0, 50.0 + (len(scheduled_jobs) / max(1, len(jobs))) * 30.0 + (critical_completed / max(1, critical_jobs_count)) * 5.0), 1)

        return {
            "solver_status": "BASELINE_HEURISTIC",
            "critical_jobs_completed": critical_completed,
            "total_critical_jobs": critical_jobs_count,
            "total_jobs_completed": len(scheduled_jobs),
            "total_jobs_demanded": len(jobs),
            "total_blocks_count": total_blocks,
            "block_utilization_pct": utilization_pct,
            "train_impact_score": train_impact,
            "asset_availability_proxy": asset_avail,
            "scheduled_jobs": scheduled_jobs,
            "deferred_jobs": deferred_jobs,
            "blocks": list(blocks.values())
        }
