import time
from typing import List, Dict, Any, Optional, Tuple
from ortools.sat.python import cp_model


class CPSATSolver:
    """
    Google OR-Tools CP-SAT Constraint Optimization Solver for IR-ABPS.
    Solves Multi-Department Maintenance Block Scheduling with hard safety constraints,
    resource limits, precedence dependencies, locked planner decisions, and multiple objective strategies (Plan A/B/C).
    """

    def __init__(self, time_limit_seconds: int = 15):
        self.time_limit_seconds = time_limit_seconds

    def solve(
        self,
        jobs: List[Dict[str, Any]],
        windows: List[Dict[str, Any]],
        resources: List[Dict[str, Any]] = None,
        dependencies: List[Dict[str, Any]] = None,
        strategy: str = "PLAN_A",
        enforce_locks: bool = True,
        custom_weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        start_wall_time = time.time()
        model = cp_model.CpModel()

        if not jobs or not windows:
            return {
                "solver_status": "NO_INPUT_DATA",
                "objective_score": 0.0,
                "scheduled_jobs": [],
                "deferred_jobs": [j["id"] for j in jobs],
                "blocks": [],
                "computation_time_ms": (time.time() - start_wall_time) * 1000,
                "status_message": "No jobs or windows available for optimization."
            }

        # Index data
        job_map = {j["id"]: j for j in jobs}
        window_map = {w["id"]: w for w in windows}

        # Map candidate windows per job (matches section_id if set, and window duration >= job duration)
        candidate_windows_for_job: Dict[int, List[int]] = {}
        for j in jobs:
            cands = []
            j_sec = j.get("section_id")
            for w in windows:
                if (j_sec is None or w["section_id"] == j_sec) and w["usable_duration_min"] >= j["estimated_duration_min"]:
                    cands.append(w["id"])
            candidate_windows_for_job[j["id"]] = cands

        # Decision Variables
        # x[j, w] in {0, 1}: 1 if job j is assigned to window w
        x = {}
        # is_scheduled[j] in {0, 1}: 1 if job j is scheduled in ANY window
        is_scheduled = {}
        # start_time[j], end_time[j]
        start_time = {}
        end_time = {}
        # Optional intervals per job per window
        job_window_intervals = {}

        for j in jobs:
            j_id = j["id"]
            dur = j["estimated_duration_min"]
            is_sched = model.NewBoolVar(f"sched_{j_id}")
            is_scheduled[j_id] = is_sched

            s_var = model.NewIntVar(0, 1440, f"start_{j_id}")
            e_var = model.NewIntVar(0, 1440, f"end_{j_id}")
            start_time[j_id] = s_var
            end_time[j_id] = e_var

            cands = candidate_windows_for_job[j_id]
            win_vars = []

            for w_id in cands:
                w = window_map[w_id]
                x_jw = model.NewBoolVar(f"x_{j_id}_{w_id}")
                x[(j_id, w_id)] = x_jw
                win_vars.append(x_jw)

                # Optional interval for window assignment
                s_opt = model.NewIntVar(w["start_min"], w["end_min"] - dur, f"s_{j_id}_{w_id}")
                e_opt = model.NewIntVar(w["start_min"] + dur, w["end_min"], f"e_{j_id}_{w_id}")
                interval = model.NewOptionalIntervalVar(s_opt, dur, e_opt, x_jw, f"interval_{j_id}_{w_id}")
                job_window_intervals[(j_id, w_id)] = (interval, s_opt, e_opt)

                # Connect optional start/end to master start/end when active
                model.Add(s_var == s_opt).OnlyEnforceIf(x_jw)
                model.Add(e_var == e_opt).OnlyEnforceIf(x_jw)

            # Constraint: A job can be assigned to at most ONE window
            if win_vars:
                model.Add(sum(win_vars) == is_sched)
            else:
                model.Add(is_sched == 0)

            # Locked decisions
            if enforce_locks and j.get("is_locked", False):
                model.Add(is_sched == 1)
                if j.get("locked_start_min") is not None:
                    model.Add(s_var == j["locked_start_min"])

            # Completed jobs cannot be moved / must be preserved
            if j.get("status") == "COMPLETED":
                model.Add(is_sched == 1)

        # ----------------------------------------------------
        # HARD CONSTRAINT 1: Window Capacity and Non-Overlapping Execution (Phase 21 Fix)
        # ----------------------------------------------------
        for w in windows:
            w_id = w["id"]
            w_jobs = [j for j in jobs if (j["id"], w_id) in job_window_intervals]

            for i in range(len(w_jobs)):
                for k in range(i + 1, len(w_jobs)):
                    j1 = w_jobs[i]
                    j2 = w_jobs[k]
                    j1_id = j1["id"]
                    j2_id = j2["id"]

                    dept1 = str(j1.get("department") or "").upper()
                    dept2 = str(j2.get("department") or "").upper()
                    comp_ids1 = j1.get("compatible_job_ids", [])
                    comp_ids2 = j2.get("compatible_job_ids", [])
                    is_compatible = (
                        (dept1 and dept2 and dept1 != dept2) or
                        (j2_id in comp_ids1 or j1_id in comp_ids2) or
                        (j1.get("is_shadow_compatible", False) and j2.get("is_shadow_compatible", False))
                    )

                    if not is_compatible:
                        # Incompatible jobs must not overlap:
                        # Either j1 before j2 OR j2 before j1.
                        # Modeled via boolean disjunction b to avoid simultaneous ordering infeasibility (Phase 21)
                        b = model.NewBoolVar(f"order_{j1_id}_{j2_id}_{w_id}")
                        _, s1, e1 = job_window_intervals[(j1_id, w_id)]
                        _, s2, e2 = job_window_intervals[(j2_id, w_id)]

                        model.Add(e1 <= s2).OnlyEnforceIf([x[(j1_id, w_id)], x[(j2_id, w_id)], b])
                        model.Add(e2 <= s1).OnlyEnforceIf([x[(j1_id, w_id)], x[(j2_id, w_id)], b.Not()])



        # ----------------------------------------------------
        # HARD CONSTRAINT 2: Dependencies (Finish-to-Start)
        # ----------------------------------------------------
        if dependencies:
            for dep in dependencies:
                p_id = dep.get("predecessor_job_id")
                s_id = dep.get("successor_job_id")
                min_gap = dep.get("min_gap_min", 0)

                if p_id in is_scheduled and s_id in is_scheduled:
                    # If both scheduled, predecessor must finish before successor starts
                    model.Add(end_time[p_id] + min_gap <= start_time[s_id]).OnlyEnforceIf([is_scheduled[p_id], is_scheduled[s_id]])
                    # If successor is scheduled, predecessor MUST be scheduled
                    model.AddImplication(is_scheduled[s_id], is_scheduled[p_id])

        # ----------------------------------------------------
        # HARD CONSTRAINT 3: Exclusive Resource Availability
        # ----------------------------------------------------
        if resources:
            for res in resources:
                res_id = res["id"]
                capacity = res.get("total_quantity", 1)
                # Find all jobs requiring this resource
                res_intervals = []
                for j in jobs:
                    j_id = j["id"]
                    reqs = j.get("required_resource_ids", [])
                    if res_id in reqs:
                        # Add intervals
                        for w in windows:
                            w_id = w["id"]
                            if (j_id, w_id) in job_window_intervals:
                                res_intervals.append((job_window_intervals[(j_id, w_id)][0], 1))

                if res_intervals and capacity > 0:
                    intervals_only = [item[0] for item in res_intervals]
                    demands = [item[1] for item in res_intervals]
                    model.AddCumulative(intervals_only, demands, capacity)

        # ----------------------------------------------------
        # WINDOW USAGE VARIABLES (For block minimization)
        # ----------------------------------------------------
        window_used = {}
        for w in windows:
            w_id = w["id"]
            w_used = model.NewBoolVar(f"w_used_{w_id}")
            window_used[w_id] = w_used
            active_vars = [x[(j["id"], w_id)] for j in jobs if (j["id"], w_id) in x]
            if active_vars:
                model.AddMaxEquality(w_used, active_vars)
            else:
                model.Add(w_used == 0)

        # ----------------------------------------------------
        # OBJECTIVE FORMULATION (PLAN A / PLAN B / PLAN C)
        # ----------------------------------------------------
        obj_terms = []

        for j in jobs:
            j_id = j["id"]
            priority = int(j.get("priority_score", 50) * 10)  # Integer scale 0 - 1000
            is_emergency = j.get("is_emergency", False)
            safety_tier = j.get("safety_tier", "")
            is_critical = ("Tier 1" in safety_tier or "Tier 2" in safety_tier or is_emergency)

            # Heavy bonus for scheduling critical / emergency jobs
            sched_weight = priority
            if is_emergency:
                sched_weight += 5000
            elif is_critical:
                sched_weight += 2000

            obj_terms.append(sched_weight * is_scheduled[j_id])

        # Plan-specific objectives
        if strategy == "PLAN_A":
            # Maximize Asset Availability / Critical Work Completion + Multi-Dept Coordination
            for w in windows:
                w_id = w["id"]
                # Bonus for packing multiple jobs into the same window (coordination)
                w_jobs = [x[(j["id"], w_id)] for j in jobs if (j["id"], w_id) in x]
                if len(w_jobs) > 1:
                    obj_terms.append(50 * sum(w_jobs))

        elif strategy == "PLAN_B":
            # Minimize Train Disruption: prefer windows with larger raw gaps / lower traffic impact
            for w in windows:
                w_id = w["id"]
                train_impact_penalty = int(max(10, 100 - w["usable_duration_min"]))
                obj_terms.append(-1 * train_impact_penalty * window_used[w_id])

        elif strategy == "PLAN_C":
            # Minimize Number of Separate Blocks / Maximize Block Utilization
            for w in windows:
                w_id = w["id"]
                # Strong penalty for each separate window opened
                obj_terms.append(-300 * window_used[w_id])
                # Reward total duration utilized
                for j in jobs:
                    j_id = j["id"]
                    if (j_id, w_id) in x:
                        obj_terms.append(2 * job_map[j_id]["estimated_duration_min"] * x[(j_id, w_id)])

        model.Maximize(sum(obj_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_workers = 4

        status = solver.Solve(model)
        comp_time = (time.time() - start_wall_time) * 1000

        status_name = solver.StatusName(status)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "solver_status": status_name,
                "objective_score": 0.0,
                "scheduled_jobs": [],
                "deferred_jobs": [j["id"] for j in jobs],
                "blocks": [],
                "computation_time_ms": round(comp_time, 2),
                "status_message": "No feasible plan satisfies all hard safety and resource constraints."
            }

        # Extract Solution
        scheduled_jobs_result = []
        deferred_jobs_result = []
        block_assignments = {}

        for j in jobs:
            j_id = j["id"]
            if solver.Value(is_scheduled[j_id]) == 1:
                assigned_w_id = None
                for w_id in candidate_windows_for_job[j_id]:
                    if (j_id, w_id) in x and solver.Value(x[(j_id, w_id)]) == 1:
                        assigned_w_id = w_id
                        break

                s_val = solver.Value(start_time[j_id])
                e_val = solver.Value(end_time[j_id])
                blk_code = f"BLK_SEC{j['section_id']}_W{assigned_w_id}"

                scheduled_jobs_result.append({
                    "job_id": j_id,
                    "job_code": j.get("job_code", f"JOB_{j_id}"),
                    "window_id": assigned_w_id,
                    "section_id": j["section_id"],
                    "scheduled_start_min": s_val,
                    "scheduled_end_min": e_val,
                    "scheduled_duration_min": j["estimated_duration_min"],
                    "block_code": blk_code,
                    "is_locked": j.get("is_locked", False),
                    "is_scheduled": True
                })

                if blk_code not in block_assignments:
                    block_assignments[blk_code] = {
                        "block_code": blk_code,
                        "window_id": assigned_w_id,
                        "section_id": j["section_id"],
                        "jobs": [],
                        "total_duration": 0,
                        "window_start": window_map[assigned_w_id]["start_min"],
                        "window_end": window_map[assigned_w_id]["end_min"],
                        "usable_duration": window_map[assigned_w_id]["usable_duration_min"]
                    }
                block_assignments[blk_code]["jobs"].append(j_id)
                block_assignments[blk_code]["total_duration"] += j["estimated_duration_min"]
            else:
                deferred_jobs_result.append(j_id)

        # Compute Block Metrics
        total_blocks = len(block_assignments)
        total_used_duration = sum(b["total_duration"] for b in block_assignments.values())
        total_available_duration = sum(b["usable_duration"] for b in block_assignments.values())
        utilization_pct = round((total_used_duration / max(1, total_available_duration)) * 100, 1)

        critical_jobs_count = sum(
            1 for j in jobs
            if ("Tier 1" in j.get("safety_tier", "") or "Tier 2" in j.get("safety_tier", "") or j.get("is_emergency", False))
        )
        critical_completed = sum(
            1 for sj in scheduled_jobs_result
            if ("Tier 1" in job_map[sj["job_id"]].get("safety_tier", "") or
                "Tier 2" in job_map[sj["job_id"]].get("safety_tier", "") or
                job_map[sj["job_id"]].get("is_emergency", False))
        )

        # Train Disruption Proxy (0 - 100, lower is better)
        train_impact = max(5.0, round(30.0 - (total_blocks * 2.5) + (len(deferred_jobs_result) * 2.0), 1))

        # Asset Availability Proxy Score (0 - 100, higher is better)
        asset_availability = round(min(98.5, 60.0 + (len(scheduled_jobs_result) / max(1, len(jobs))) * 35.0 + (critical_completed / max(1, critical_jobs_count)) * 5.0), 1)

        return {
            "solver_status": status_name,
            "objective_score": round(solver.ObjectiveValue(), 2),
            "critical_jobs_completed": critical_completed,
            "total_critical_jobs": critical_jobs_count,
            "total_jobs_completed": len(scheduled_jobs_result),
            "total_jobs_demanded": len(jobs),
            "total_blocks_count": total_blocks,
            "block_utilization_pct": utilization_pct,
            "train_impact_score": train_impact,
            "asset_availability_proxy": asset_availability,
            "computation_time_ms": round(comp_time, 2),
            "scheduled_jobs": scheduled_jobs_result,
            "deferred_jobs": deferred_jobs_result,
            "blocks": list(block_assignments.values()),
            "status_message": f"{status_name} block schedule generated in {round(comp_time, 1)}ms."
        }
