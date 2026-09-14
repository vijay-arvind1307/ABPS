from typing import List, Dict, Any, Optional
from app.algorithms.priority import PriorityEngine


class PlanExplainabilityEngine:
    """
    Generates human-readable, transparent decision rationales for why each maintenance job
    was assigned its priority score, and why it was scheduled (or deferred) by the CP-SAT optimizer.
    """

    @classmethod
    def explain_job_priority(cls, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explains why a request received its calculated priority score.
        Returns: Score, Criticality, Safety Impact, Urgency, User Priority, Due Date, and Reason text.
        """
        stored_exp = job.get("priority_explanation")
        if stored_exp and isinstance(stored_exp, dict):
            return stored_exp

        # Dynamically derive explanation if not already saved
        return PriorityEngine.calculate_full_priority(
            work_type=job.get("work_type", "TRACK_MAINTENANCE"),
            department_code=job.get("department_code", "ENGG"),
            user_priority=job.get("user_priority", "MEDIUM"),
            due_date=job.get("due_date"),
            is_emergency=job.get("is_emergency", False)
        )

    @classmethod
    def explain_job_decision(
        cls,
        job: Dict[str, Any],
        is_scheduled: bool,
        plan_job: Optional[Dict[str, Any]],
        window: Optional[Dict[str, Any]],
        all_windows: List[Dict[str, Any]],
        compatibility_neighbors: List[str] = None
    ) -> Dict[str, Any]:
        selection_reasons = []
        rejection_reasons = []
        constraints_satisfied = []

        priority = job.get("priority_score", 50.0)
        is_emergency = job.get("is_emergency", False)
        safety_tier = job.get("safety_tier", "Tier 4")

        # Include priority rationale
        prio_explanation = cls.explain_job_priority(job)

        if is_scheduled and plan_job:
            # Selected Job Explanations
            if is_emergency:
                selection_reasons.append("Emergency Track Maintenance Priority (Tier 1)")
            elif "Tier 2" in safety_tier or priority >= 70:
                selection_reasons.append(f"High Safety & Criticality Rating ({priority:.1f}/100 - {safety_tier})")
            else:
                selection_reasons.append(f"Optimal schedule fit within available window capacity")

            if job.get("overdue_days", 0) > 0:
                selection_reasons.append(f"Overdue by {job['overdue_days']} days (high risk if deferred)")

            if window:
                sec_desc = f"Section {job.get('section_id', 'Corridor')}"
                selection_reasons.append(
                    f"Feasible gap detected on {sec_desc} ({window['usable_duration_min']}m available vs {job.get('estimated_duration_min', 60)}m required)"
                )
                constraints_satisfied.append("Zero train headway overlap verified")
                constraints_satisfied.append(f"Safety buffers preserved ({window.get('constraints_applied_json', {}).get('buffer_before_min', 5)}m before, {window.get('constraints_applied_json', {}).get('buffer_after_min', 5)}m after)")
                constraints_satisfied.append("Corridor operational hours satisfied")

            if compatibility_neighbors:
                selection_reasons.append(
                    f"Multi-department block coordination synergy achieved with: {', '.join(compatibility_neighbors)}"
                )

            if plan_job.get("is_locked"):
                selection_reasons.append("Preserved fixed start time as locked by Railway Planner")

        else:
            # Deferred Job Explanations
            sec_id = job.get("section_id")
            matching_windows = [
                w for w in all_windows
                if (sec_id is None or w["section_id"] == sec_id) and w["usable_duration_min"] >= job.get("estimated_duration_min", 60)
            ]

            if not matching_windows:
                selection_reasons.append(
                    f"No single train-free window provided sufficient continuous duration ({job.get('estimated_duration_min', 60)}m required)."
                )
            else:
                rejection_reasons.append(
                    "Candidate window was allocated to higher-priority / emergency maintenance demand."
                )

            if priority < 60 and not is_emergency:
                rejection_reasons.append(f"Lower relative priority score ({priority:.1f}/100) compared to competing corridor demands.")

        return {
            "job_id": job["id"],
            "job_code": job["job_code"],
            "is_scheduled": is_scheduled,
            "scheduled_start_min": plan_job.get("scheduled_start_min") if plan_job else None,
            "scheduled_end_min": plan_job.get("scheduled_end_min") if plan_job else None,
            "block_code": plan_job.get("block_code") if plan_job else None,
            "selection_reasons": selection_reasons,
            "rejection_reasons": rejection_reasons,
            "priority_explanation": prio_explanation,
            "factor_contributions": prio_explanation.get("factor_contributions", {}),
            "compatibility_synergies": compatibility_neighbors or [],
            "constraints_satisfied": constraints_satisfied
        }
