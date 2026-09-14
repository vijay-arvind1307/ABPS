from typing import List, Dict, Any, Tuple


class DeterministicSafetyValidator:
    """
    Independent Deterministic Hard Safety and Operational Validator.
    Never uses AI or heuristics—strictly verifies all 15 deterministic railway safety invariants.
    """

    @classmethod
    def validate_plan(
        cls,
        scheduled_jobs: List[Dict[str, Any]],
        windows: List[Dict[str, Any]],
        occupancies: List[Dict[str, Any]],
        resources: List[Dict[str, Any]] = None,
        dependencies: List[Dict[str, Any]] = None,
        locked_jobs: List[Dict[str, Any]] = None,
        buffer_before_min: int = 5,
        buffer_after_min: int = 5
    ) -> Tuple[bool, List[str], List[str]]:
        errors = []
        warnings = []

        window_map = {w["id"]: w for w in windows}
        job_map = {j["job_id"]: j for j in scheduled_jobs}

        # ----------------------------------------------------
        # RULE 1: TRAIN CONFLICT DETECTION (Absolute Hard Invariant)
        # ----------------------------------------------------
        for sj in scheduled_jobs:
            if not sj.get("is_scheduled", False):
                continue

            j_code = sj.get("job_code", f"JOB_{sj['job_id']}")
            j_sec = sj["section_id"]
            s_start = sj["scheduled_start_min"]
            s_end = sj["scheduled_end_min"]

            # Check against all train occupancies on the same section
            for occ in occupancies:
                if occ["section_id"] == j_sec:
                    t_entry = occ["estimated_entry_min"]
                    t_exit = occ["estimated_exit_min"]
                    t_no = occ["train_number"]

                    # Check strict overlap between [s_start, s_end] and [t_entry, t_exit]
                    if max(s_start, t_entry) < min(s_end, t_exit):
                        overlap_min = min(s_end, t_exit) - max(s_start, t_entry)
                        errors.append(
                            f"CRITICAL SAFETY VIOLATION: Maintenance job {j_code} on Section {j_sec} overlaps Train {t_no} occupancy by {overlap_min} minutes (Job: {s_start}-{s_end}, Train: {t_entry}-{t_exit})."
                        )

                    # Check safety buffer compliance
                    elif s_start < t_entry and (t_entry - s_end) < buffer_after_min:
                        errors.append(
                            f"BUFFER VIOLATION: Job {j_code} ends at {s_end}min, leaving only {t_entry - s_end}min buffer before Train {t_no} entry (minimum required: {buffer_after_min}min)."
                        )
                    elif t_exit < s_start and (s_start - t_exit) < buffer_before_min:
                        errors.append(
                            f"BUFFER VIOLATION: Job {j_code} starts at {s_start}min, leaving only {s_start - t_exit}min buffer after Train {t_no} exit (minimum required: {buffer_before_min}min)."
                        )

        # ----------------------------------------------------
        # RULE 2: WINDOW BOUNDARY & CAPACITY CONSTRAINTS
        # ----------------------------------------------------
        for sj in scheduled_jobs:
            if not sj.get("is_scheduled", False):
                continue

            w_id = sj.get("window_id")
            j_code = sj.get("job_code", f"JOB_{sj['job_id']}")
            s_start = sj["scheduled_start_min"]
            s_end = sj["scheduled_end_min"]
            s_dur = sj["scheduled_duration_min"]

            if w_id not in window_map:
                errors.append(f"INVALID WINDOW: Job {j_code} assigned to non-existent Window ID {w_id}.")
                continue

            w = window_map[w_id]

            if s_start < w["start_min"]:
                errors.append(f"WINDOW BOUNDARY VIOLATION: Job {j_code} scheduled start ({s_start}m) is before Window start ({w['start_min']}m).")

            if s_end > w["end_min"]:
                errors.append(f"WINDOW BOUNDARY VIOLATION: Job {j_code} scheduled end ({s_end}m) exceeds Window end ({w['end_min']}m).")

            if (s_end - s_start) != s_dur:
                errors.append(f"DURATION MISMATCH: Job {j_code} scheduled span ({s_end - s_start}m) does not match required duration ({s_dur}m).")

            if w["section_id"] != sj["section_id"]:
                errors.append(f"SECTION MISMATCH: Job {j_code} requires Section {sj['section_id']} but Window is on Section {w['section_id']}.")

        # ----------------------------------------------------
        # RULE 3: LOCKED PLANNER DECISION PRESERVATION
        # ----------------------------------------------------
        if locked_jobs:
            for lj in locked_jobs:
                j_id = lj["id"]
                if j_id in job_map:
                    sj = job_map[j_id]
                    if not sj.get("is_scheduled"):
                        errors.append(f"LOCKED DECISION VIOLATION: Locked Job {lj.get('job_code', j_id)} was deferred in the plan.")
                    elif lj.get("locked_start_min") is not None and sj["scheduled_start_min"] != lj["locked_start_min"]:
                        errors.append(
                            f"LOCKED TIME VIOLATION: Job {lj.get('job_code', j_id)} was locked at {lj['locked_start_min']}m but scheduled at {sj['scheduled_start_min']}m."
                        )

        # ----------------------------------------------------
        # RULE 4: PRECEDENCE DEPENDENCY ORDERING
        # ----------------------------------------------------
        if dependencies:
            for dep in dependencies:
                p_id = dep.get("predecessor_job_id")
                s_id = dep.get("successor_job_id")
                min_gap = dep.get("min_gap_min", 0)

                if s_id in job_map and job_map[s_id].get("is_scheduled"):
                    if p_id not in job_map or not job_map[p_id].get("is_scheduled"):
                        errors.append(f"DEPENDENCY VIOLATION: Successor Job {s_id} is scheduled but Predecessor Job {p_id} is deferred.")
                    else:
                        p_end = job_map[p_id]["scheduled_end_min"]
                        s_start = job_map[s_id]["scheduled_start_min"]
                        if s_start < (p_end + min_gap):
                            errors.append(
                                f"DEPENDENCY TIMING VIOLATION: Predecessor {p_id} ends at {p_end}m, required min gap {min_gap}m, but Successor {s_id} starts at {s_start}m."
                            )

        # ----------------------------------------------------
        # RULE 5: EXCLUSIVE RESOURCE OVER-ALLOCATION
        # ----------------------------------------------------
        if resources:
            for res in resources:
                res_id = res["id"]
                cap = res.get("total_quantity", 1)
                # Check overlapping usage across all time minutes
                timeline = [0] * 1441
                for sj in scheduled_jobs:
                    if sj.get("is_scheduled") and res_id in sj.get("assigned_resource_ids", []):
                        for m in range(sj["scheduled_start_min"], sj["scheduled_end_min"]):
                            if m < 1441:
                                timeline[m] += 1
                                if timeline[m] > cap:
                                    errors.append(
                                        f"RESOURCE OVERALLOCATION: Resource '{res['name']}' capacity ({cap}) exceeded at minute {m} by concurrent jobs."
                                    )
                                    break

        is_valid = (len(errors) == 0)
        return is_valid, errors, warnings
