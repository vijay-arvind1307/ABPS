import time
from typing import List, Dict, Any, Optional, Tuple
from ortools.sat.python import cp_model
from app.algorithms.coordination import CompatibilityEngine


class CPSATSolver:
    """
    Google OR-Tools CP-SAT Constraint Optimization Solver for IR-ABPS (SIH26027).
    Solves Multi-Department Maintenance Block Scheduling with verified physical safety constraints,
    resource capacities, precedence dependencies, locked planner decisions, and distinct objective strategies (Plan A/B/C).

    Safety Principles Enforced:
    1. Cross-department tasks overlap ONLY if work types are verified as physically compatible.
    2. Multi-section demands are scheduled across common feasible intervals.
    3. INFEASIBLE, MODEL_INVALID, and UNKNOWN solver statuses return complete, non-crashing responses.
    4. Metric proxies are derived from verifiable operational facts, never fabricated curve fits.
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
                "critical_jobs_completed": 0,
                "total_critical_jobs": sum(1 for j in jobs if ("Tier 1" in j.get("safety_tier", "") or "Tier 2" in j.get("safety_tier", "") or j.get("is_emergency", False))),
                "total_jobs_completed": 0,
                "total_jobs_demanded": len(jobs),
                "total_blocks_count": 0,
                "block_utilization_pct": 0.0,
                "train_impact_score": None,
                "asset_availability_proxy": None,
                "scheduled_jobs": [],
                "deferred_jobs": [j["id"] for j in jobs],
                "blocks": [],
                "computation_time_ms": round((time.time() - start_wall_time) * 1000, 2),
                "status_message": "No maintenance requests or feasible windows available for optimization."
            }

        # Index data
        job_map = {j["id"]: j for j in jobs}
        window_map = {w["id"]: w for w in windows}

        # Map candidate windows per job (matches physical section / affected sections and duration)
        candidate_windows_for_job: Dict[int, List[int]] = {}
        for j in jobs:
            cands = []
            j_sec = j.get("section_id")
            aff_secs = set(j.get("affected_section_ids") or [])
            if j_sec:
                aff_secs.add(j_sec)

            for w in windows:
                if w.get("feasibility") and w.get("feasibility") not in ("FEASIBLE", "SWEEP_LINE_DERIVED", "VERIFIED_EMPTY_INTERVAL"):
                    continue
                w_sec = w.get("section_id")
                w_secs = set(w.get("section_ids") or ([w_sec] if w_sec else []))
                w_dur = w.get("usable_duration_min", 0)

                # Geographic match: job sections must intersect window sections
                sec_match = bool(aff_secs & w_secs) if aff_secs else (j_sec == w_sec if j_sec and w_sec else False)
                if sec_match and w_dur >= j["estimated_duration_min"]:
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
                s_opt = model.NewIntVar(w["start_min"], max(w["start_min"], w["end_min"] - dur), f"s_{j_id}_{w_id}")
                e_opt = model.NewIntVar(min(w["end_min"], w["start_min"] + dur), w["end_min"], f"e_{j_id}_{w_id}")
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

            # Locked decisions: preserve planned or committed start
            if enforce_locks and j.get("is_locked", False):
                model.Add(is_sched == 1)
                if j.get("locked_start_min") is not None:
                    model.Add(s_var == j["locked_start_min"])

            # Completed jobs cannot be moved
            if j.get("status") == "COMPLETED" or j.get("execution_status") == "COMPLETED":
                model.Add(is_sched == 1)
                if j.get("actual_start_min") is not None:
                    model.Add(s_var == j["actual_start_min"])

        # ----------------------------------------------------
        # HARD CONSTRAINT 1: Work-Type Compatibility on Track Section
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

                    dept1 = str(j1.get("department_code") or j1.get("department") or "").upper()
                    dept2 = str(j2.get("department_code") or j2.get("department") or "").upper()
                    wt1 = str(j1.get("work_type") or "").upper()
                    wt2 = str(j2.get("work_type") or "").upper()

                    comp_ids1 = j1.get("compatible_job_ids", [])
                    comp_ids2 = j2.get("compatible_job_ids", [])

                    # Physical compatibility requires explicit work-type safety check
                    both_insp = ("INSPECTION" in wt1 and "INSPECTION" in wt2)
                    is_work_compatible = (
                        both_insp or
                        (wt1, wt2) in CompatibilityEngine.PARALLEL_COMPATIBLE_WORK_TYPES or
                        (wt2, wt1) in CompatibilityEngine.PARALLEL_COMPATIBLE_WORK_TYPES
                    )

                    is_compatible = is_work_compatible and (
                        (j2_id in comp_ids1 or j1_id in comp_ids2) or
                        (dept1 != dept2) or
                        (j1.get("is_shadow_compatible", False) and j2.get("is_shadow_compatible", False))
                    )

                    if not is_compatible:
                        # Incompatible jobs must NOT overlap: either j1 before j2 OR j2 before j1
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
                    model.Add(end_time[p_id] + min_gap <= start_time[s_id]).OnlyEnforceIf([is_scheduled[p_id], is_scheduled[s_id]])
                    model.AddImplication(is_scheduled[s_id], is_scheduled[p_id])

        # ----------------------------------------------------
        # HARD CONSTRAINT 3: Exclusive Resource Capacities
        # ----------------------------------------------------
        if resources:
            for res in resources:
                res_id = res["id"]
                capacity = res.get("total_quantity", 1)
                res_intervals = []
                for j in jobs:
                    j_id = j["id"]
                    reqs = j.get("required_resource_ids", [])
                    if res_id in reqs:
                        for w in windows:
                            w_id = w["id"]
                            if (j_id, w_id) in job_window_intervals:
                                res_intervals.append((job_window_intervals[(j_id, w_id)][0], 1))

                if res_intervals and capacity > 0:
                    intervals_only = [item[0] for item in res_intervals]
                    demands = [item[1] for item in res_intervals]
                    model.AddCumulative(intervals_only, demands, capacity)

        # Window usage variables (for block consolidation)
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
            priority = int(float(j.get("priority_score", 50.0)) * 10)  # Integer scale 0 - 1000
            is_emergency = j.get("is_emergency", False)
            safety_tier = str(j.get("safety_tier", ""))
            is_critical = ("Tier 1" in safety_tier or "Tier 2" in safety_tier or is_emergency)

            sched_weight = priority
            if is_emergency:
                sched_weight += 5000
            elif is_critical:
                sched_weight += 2000

            obj_terms.append(sched_weight * is_scheduled[j_id])

        if strategy == "PLAN_A":
            # Maximize Multi-Department Coordination & Critical Asset Availability
            for w in windows:
                w_id = w["id"]
                w_jobs = [x[(j["id"], w_id)] for j in jobs if (j["id"], w_id) in x]
                if len(w_jobs) > 1:
                    obj_terms.append(100 * sum(w_jobs))

        elif strategy == "PLAN_B":
            # Minimize Train Disruption & Favor Off-Peak Large Windows
            for w in windows:
                w_id = w["id"]
                # Penalty for using windows close to high train volume
                raw_gap = w.get("raw_gap_min", w.get("usable_duration_min", 60))
                train_impact_penalty = max(10, 180 - raw_gap)
                obj_terms.append(-1 * train_impact_penalty * window_used[w_id])

        elif strategy == "PLAN_C":
            # Minimize Block Count & Maximize Track Utilization
            for w in windows:
                w_id = w["id"]
                obj_terms.append(-400 * window_used[w_id])
                for j in jobs:
                    j_id = j["id"]
                    if (j_id, w_id) in x:
                        obj_terms.append(3 * job_map[j_id]["estimated_duration_min"] * x[(j_id, w_id)])

        model.Maximize(sum(obj_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_workers = 4

        status = solver.Solve(model)
        comp_time = (time.time() - start_wall_time) * 1000
        status_name = solver.StatusName(status)

        critical_jobs_count = sum(
            1 for j in jobs
            if ("Tier 1" in str(j.get("safety_tier", "")) or "Tier 2" in str(j.get("safety_tier", "")) or j.get("is_emergency", False))
        )

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "solver_status": status_name,
                "objective_score": 0.0,
                "critical_jobs_completed": 0,
                "total_critical_jobs": critical_jobs_count,
                "total_jobs_completed": 0,
                "total_jobs_demanded": len(jobs),
                "total_blocks_count": 0,
                "block_utilization_pct": 0.0,
                "train_impact_score": None,
                "asset_availability_proxy": None,
                "scheduled_jobs": [],
                "deferred_jobs": [j["id"] for j in jobs],
                "blocks": [],
                "computation_time_ms": round(comp_time, 2),
                "status_message": f"NO_FEASIBLE_PLAN: Solver returned {status_name}. Hard safety or resource constraints prevent scheduling.",
                "blocking_constraints": [
                    "Required maintenance duration exceeds available gap windows",
                    "Headway safety buffer conflicts with train paths",
                    "Inter-departmental work-type incompatibility",
                    "Resource capacity limits or predecessor dependency restrictions"
                ]
            }

        # Extract Solution
        scheduled_jobs_result = []
        deferred_jobs_result = []
        block_assignments = {}

        for j in jobs:
            j_id = j["id"]
            assigned_w_id = None
            if solver.Value(is_scheduled[j_id]) == 1:
                for w_id in candidate_windows_for_job[j_id]:
                    if (j_id, w_id) in x and solver.Value(x[(j_id, w_id)]) == 1:
                        assigned_w_id = w_id
                        break

            if assigned_w_id is not None and assigned_w_id in window_map:
                s_val = solver.Value(start_time[j_id])
                e_val = solver.Value(end_time[j_id])
                blk_code = f"BLK_SEC{j.get('section_id', 1)}_W{assigned_w_id}"

                scheduled_jobs_result.append({
                    "job_id": j_id,
                    "job_code": j.get("job_code", f"JOB_{j_id}"),
                    "window_id": assigned_w_id,
                    "section_id": j.get("section_id"),
                    "affected_section_ids": j.get("affected_section_ids", []),
                    "work_type": j.get("work_type"),
                    "department_code": j.get("department_code"),
                    "scheduled_start_min": s_val,
                    "scheduled_end_min": e_val,
                    "scheduled_duration_min": j["estimated_duration_min"],
                    "block_code": blk_code,
                    "is_locked": j.get("is_locked", False),
                    "is_scheduled": True
                })

                if blk_code not in block_assignments:
                    w_info = window_map[assigned_w_id]
                    block_assignments[blk_code] = {
                        "block_code": blk_code,
                        "window_id": assigned_w_id,
                        "section_id": j.get("section_id"),
                        "jobs": [],
                        "total_duration": 0,
                        "window_start": w_info["start_min"],
                        "window_end": w_info["end_min"],
                        "usable_duration": w_info["usable_duration_min"]
                    }
                block_assignments[blk_code]["jobs"].append(j_id)
                block_assignments[blk_code]["total_duration"] += j["estimated_duration_min"]
            else:
                deferred_jobs_result.append(j_id)

        # Compute Verified Block Metrics
        total_blocks = len(block_assignments)
        total_used_duration = sum(b["total_duration"] for b in block_assignments.values())
        total_available_duration = sum(b["usable_duration"] for b in block_assignments.values())
        utilization_pct = round((total_used_duration / max(1, total_available_duration)) * 100, 1)

        critical_completed = sum(
            1 for sj in scheduled_jobs_result
            if ("Tier 1" in str(job_map[sj["job_id"]].get("safety_tier", "")) or
                "Tier 2" in str(job_map[sj["job_id"]].get("safety_tier", "")) or
                job_map[sj["job_id"]].get("is_emergency", False))
        )

        return {
            "solver_status": status_name,
            "objective_score": round(solver.ObjectiveValue(), 2),
            "critical_jobs_completed": critical_completed,
            "total_critical_jobs": critical_jobs_count,
            "total_jobs_completed": len(scheduled_jobs_result),
            "total_jobs_demanded": len(jobs),
            "total_blocks_count": total_blocks,
            "block_utilization_pct": utilization_pct,
            "train_impact_score": None,  # Explicitly None: requires live delay telemetry or COA
            "asset_availability_proxy": utilization_pct,  # Track possession utilization percentage
            "computation_time_ms": round(comp_time, 2),
            "scheduled_jobs": scheduled_jobs_result,
            "deferred_jobs": deferred_jobs_result,
            "blocks": list(block_assignments.values()),
            "status_message": f"{status_name} block schedule generated in {round(comp_time, 1)}ms."
        }
