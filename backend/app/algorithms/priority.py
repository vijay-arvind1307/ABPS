from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional


class PriorityEngine:
    """
    Transparent Deterministic Scoring Engine for Railway Maintenance Demands.
    Calculates Criticality, Safety Impact, Urgency, and composite Priority Score (0-100)
    with complete explainability for the Railway Planner.

    DISCLAIMER:
    Planning heuristic / configurable decision-support rule, not an official railway safety standard.
    Actual railway safety operating rules must always take precedence.
    """

    DISCLAIMER = "Planning heuristic / configurable decision-support rule, not an official railway safety standard."

    # Configurable Prototype Weights (Section 8: Sum = 1.00)
    # Priority Score = Criticality*0.30 + Urgency*0.20 + OverdueRisk*0.15 + SafetyImpact*0.20 + OperationalImpact*0.15
    DEFAULT_WEIGHTS = {
        "criticality": 0.30,
        "urgency": 0.20,
        "overdue_risk": 0.15,
        "safety_impact": 0.20,
        "operational_impact": 0.15
    }

    # User priority mapping to 0-100 scale
    USER_PRIORITY_MAP = {
        "LOW": 33.33,
        "MEDIUM": 66.67,
        "HIGH": 100.0
    }

    @classmethod
    @classmethod
    def calculate_criticality(
        cls,
        work_type: str,
        department_code: str = "ENGG",
        user_priority: str = "MEDIUM",
        is_emergency: bool = False,
        asset_condition_score: Optional[float] = None,
        failure_consequence_score: Optional[float] = None,
        operational_importance_score: Optional[float] = None
    ) -> Tuple[float, str, str, Dict[str, Any]]:
        """
        Calculates deterministic Criticality score (0-100) based on explainable sub-factors:
        Criticality = Condition Score * 0.35 + Failure Consequence * 0.35 + Operational Importance * 0.30
        Returns: (score, label, reason, sub_factors_dict)
        """
        wt = (work_type or "").upper()
        prio = (user_priority or "MEDIUM").upper()

        if is_emergency:
            sub = {
                "condition_score": 95.0,
                "failure_consequence_score": 95.0,
                "operational_importance_score": 95.0,
                "criticality_score": 95.0,
                "calculation_version": "v2.0-deterministic"
            }
            return 95.0, "CRITICAL", "Emergency declaration / immediate railway infrastructure failure risk", sub

        # Derive sub-factors deterministically from asset condition, failure consequence, and operational importance
        if asset_condition_score is not None:
            c_cond = min(100.0, max(10.0, float(asset_condition_score)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "WELD_REPAIR", "RAIL_REPLACEMENT"]):
                c_cond = 88.0
            elif any(term in wt for term in ["TAMPING", "BALLAST", "SURFACING", "POINT_OVERHAUL", "OHE_POWER_BLOCK"]):
                c_cond = 80.0
            elif any(term in wt for term in ["INSPECTION", "CALIBRATION", "MEGGERING", "TEST"]):
                c_cond = 60.0
            else:
                c_cond = 45.0

        if failure_consequence_score is not None:
            c_cons = min(100.0, max(10.0, float(failure_consequence_score)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "INTERLOCKING", "POINT_MACHINE", "TRANSFORMER"]):
                c_cons = 90.0
            elif any(term in wt for term in ["TAMPING", "BALLAST_CLEANING", "SURFACING", "POINT_OVERHAUL", "OHE_POWER_BLOCK", "CANTILEVER"]):
                c_cons = 75.0
            elif any(term in wt for term in ["INSPECTION", "TEST", "CALIBRATION"]):
                c_cons = 55.0
            else:
                c_cons = 40.0

        if operational_importance_score is not None:
            c_imp = min(100.0, max(10.0, float(operational_importance_score)))
        else:
            c_imp = 85.0 if prio == "HIGH" else (55.0 if prio == "LOW" else 70.0)

        # Multi-factor formula:
        # Criticality = 35% Asset Condition + 35% Failure Consequence + 30% Operational Importance
        calculated_crit = round(0.35 * c_cond + 0.35 * c_cons + 0.30 * c_imp, 1)

        sub = {
            "condition_score": c_cond,
            "failure_consequence_score": c_cons,
            "operational_importance_score": c_imp,
            "criticality_score": calculated_crit,
            "calculation_version": "v2.0-deterministic"
        }

        if calculated_crit >= 90.0:
            label = "CRITICAL"
        elif calculated_crit >= 70.0:
            label = "HIGH"
        elif calculated_crit >= 50.0:
            label = "MEDIUM"
        else:
            label = "LOW"

        reason = f"{label} criticality: Condition {c_cond} (35%) + Consequence {c_cons} (35%) + Importance {c_imp} (30%)"
        return calculated_crit, label, reason, sub

    @classmethod
    def calculate_safety_impact(
        cls,
        work_type: str,
        department_code: str = "ENGG",
        is_emergency: bool = False,
        safety_consequence_score: Optional[float] = None,
        train_operation_safety_score: Optional[float] = None,
        failure_severity_score: Optional[float] = None,
        mitigation_score: Optional[float] = None
    ) -> Tuple[float, str, str, Dict[str, Any]]:
        """
        Calculates deterministic Safety Impact score (0-100) based on explainable sub-factors:
        Safety = Safety Consequence * 0.40 + Train Operation Impact * 0.35 + Failure Severity * 0.25
        Returns: (score, label, reason, sub_factors_dict)
        """
        wt = (work_type or "").upper()

        if is_emergency:
            sub = {
                "safety_consequence_score": 95.0,
                "train_operation_safety_score": 95.0,
                "failure_severity_score": 95.0,
                "mitigation_score": 60.0,
                "safety_score": 95.0,
                "calculation_version": "v2.0-deterministic"
            }
            return 95.0, "HIGH", "Immediate safety risk to passenger and freight train operations", sub

        # Derive explainable safety sub-factors
        if safety_consequence_score is not None:
            s_cons = min(100.0, max(10.0, float(safety_consequence_score)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "RAIL_REPLACEMENT", "INTERLOCKING", "OHE_POWER_BLOCK"]):
                s_cons = 92.0
            elif any(term in wt for term in ["TAMPING", "SURFACING", "POINT_OVERHAUL", "TRACK_CIRCUIT", "AXLE_COUNTER", "CANTILEVER"]):
                s_cons = 82.0
            elif any(term in wt for term in ["INSPECTION", "BONDING", "MEGGERING"]):
                s_cons = 55.0
            else:
                s_cons = 35.0

        if train_operation_safety_score is not None:
            s_train = min(100.0, max(10.0, float(train_operation_safety_score)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "RAIL_REPLACEMENT"]):
                s_train = 90.0
            elif any(term in wt for term in ["TAMPING", "SURFACING", "POINT_MACHINE", "OHE_POWER_BLOCK"]):
                s_train = 79.0
            elif any(term in wt for term in ["INSPECTION", "TEST", "CALIBRATION"]):
                s_train = 50.0
            else:
                s_train = 30.0

        if failure_severity_score is not None:
            s_sev = min(100.0, max(10.0, float(failure_severity_score)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "INTERLOCKING"]):
                s_sev = 88.0
            elif any(term in wt for term in ["TAMPING", "SURFACING", "POINT_OVERHAUL"]):
                s_sev = 75.0
            elif any(term in wt for term in ["INSPECTION", "CALIBRATION"]):
                s_sev = 50.0
            else:
                s_sev = 25.0

        s_mit = mitigation_score if mitigation_score is not None else 70.0

        # Multi-factor formula:
        # Safety = 40% Safety Consequence + 35% Train Operation Safety Impact + 25% Failure Severity
        calculated_safety = round(0.40 * s_cons + 0.35 * s_train + 0.25 * s_sev, 1)

        sub = {
            "safety_consequence_score": s_cons,
            "train_operation_safety_score": s_train,
            "failure_severity_score": s_sev,
            "mitigation_score": s_mit,
            "safety_score": calculated_safety,
            "calculation_version": "v2.0-deterministic"
        }

        if calculated_safety >= 70.0:
            label = "HIGH"
        elif calculated_safety >= 45.0:
            label = "MEDIUM"
        else:
            label = "LOW"

        reason = f"{label} safety impact: Consequence {s_cons} (40%) + Train Risk {s_train} (35%) + Severity {s_sev} (25%)"
        return calculated_safety, label, reason, sub

    @classmethod
    def calculate_urgency(
        cls,
        due_date: Optional[Any],
        user_priority: str = "MEDIUM",
        is_emergency: bool = False
    ) -> Tuple[float, str, str]:
        """
        Calculates deterministic Urgency score (0-100) based on remaining time until Due Date.
        Returns: (score, label, reason)
        """
        if is_emergency:
            return 98.0, "CRITICAL", "Emergency job requires immediate possession window"

        prio = (user_priority or "MEDIUM").upper()

        # Parse due_date
        diff_days = None
        if due_date:
            try:
                if isinstance(due_date, str):
                    target_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00")).date()
                elif isinstance(due_date, datetime):
                    target_dt = due_date.date()
                elif isinstance(due_date, date):
                    target_dt = due_date
                else:
                    target_dt = None

                if target_dt:
                    today = datetime.utcnow().date()
                    diff_days = (target_dt - today).days
            except Exception:
                diff_days = None

        if diff_days is not None:
            if diff_days < 0:
                score = 96.0
                label = "CRITICAL"
                reason = f"OVERDUE by {abs(diff_days)} day(s) - critical scheduling priority"
            elif diff_days == 0:
                score = 90.0
                label = "CRITICAL"
                reason = "Due today (within 24 hours)"
            elif diff_days == 1:
                score = 82.0
                label = "HIGH"
                reason = "Due tomorrow (within 48 hours)"
            elif diff_days <= 3:
                score = 72.0
                label = "HIGH"
                reason = f"Approaching due date (due within {diff_days} days)"
            elif diff_days <= 7:
                score = 58.0
                label = "MEDIUM"
                reason = f"Due within {diff_days} days"
            else:
                score = 35.0
                label = "LOW"
                reason = f"Due in {diff_days} days (adequate advance planning window)"
        else:
            # Fallback based on user priority
            if prio == "HIGH":
                score = 75.0
                label = "HIGH"
                reason = "High priority operational demand (no explicit due date set)"
            elif prio == "LOW":
                score = 40.0
                label = "LOW"
                reason = "Routine priority demand (no explicit due date set)"
            else:
                score = 60.0
                label = "MEDIUM"
                reason = "Standard priority demand (no explicit due date set)"

        score = round(min(100.0, max(10.0, score)), 1)
        return score, label, reason

    @classmethod
    def calculate_full_priority(
        cls,
        work_type: str,
        department_code: str = "ENGG",
        user_priority: str = "MEDIUM",
        due_date: Optional[Any] = None,
        is_emergency: bool = False,
        custom_weights: Dict[str, float] = None,
        operational_impact_val: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes deterministic multi-criteria scoring according to Section 8:
        Priority Score = Criticality * 0.30 + Urgency * 0.20 + Overdue Risk * 0.15 + Safety Impact * 0.20 + Operational Impact * 0.15
        IMPORTANT: These are configurable prototype weights, not official Indian Railways safety policy.
        """
        weights = custom_weights or cls.DEFAULT_WEIGHTS

        # 1. Criticality & Safety Impact
        c_score, c_label, c_reason, c_sub = cls.calculate_criticality(work_type, department_code, user_priority, is_emergency)
        s_score, s_label, s_reason, s_sub = cls.calculate_safety_impact(work_type, department_code, is_emergency)
        u_score, u_label, u_reason = cls.calculate_urgency(due_date, user_priority, is_emergency)

        # 2. Overdue Risk Score (0 - 100)
        diff_days = None
        if due_date:
            try:
                if isinstance(due_date, str):
                    target_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00")).date()
                elif isinstance(due_date, datetime):
                    target_dt = due_date.date()
                elif isinstance(due_date, date):
                    target_dt = due_date
                else:
                    target_dt = None
                if target_dt:
                    diff_days = (target_dt - datetime.utcnow().date()).days
            except Exception:
                diff_days = None

        if diff_days is not None:
            if diff_days < 0:
                overdue_risk = min(100.0, 90.0 + abs(diff_days) * 3.0)
                overdue_label = "CRITICAL"
                overdue_reason = f"Job is overdue by {abs(diff_days)} day(s)"
            elif diff_days == 0:
                overdue_risk = 88.0
                overdue_label = "HIGH"
                overdue_reason = "Due today (due date imminent)"
            elif diff_days <= 2:
                overdue_risk = 75.0
                overdue_label = "HIGH"
                overdue_reason = f"Due in {diff_days} day(s) - high risk of overdue"
            elif diff_days <= 5:
                overdue_risk = 50.0
                overdue_label = "MEDIUM"
                overdue_reason = f"Due in {diff_days} days"
            else:
                overdue_risk = 25.0
                overdue_label = "LOW"
                overdue_reason = f"Due in {diff_days} days (low overdue risk)"
        else:
            prio_upper = (user_priority or "MEDIUM").upper()
            overdue_risk = 70.0 if prio_upper == "HIGH" else (35.0 if prio_upper == "LOW" else 50.0)
            overdue_label = prio_upper
            overdue_reason = "No explicit due date specified"

        # 3. Operational Impact Score (0 - 100)
        wt = (work_type or "").upper()
        if operational_impact_val is not None:
            op_impact = min(100.0, max(0.0, float(operational_impact_val)))
        else:
            if any(term in wt for term in ["FRACTURE", "DEFECT", "TAMPING", "OHE_POWER_BLOCK", "TURNOUT_RENEWAL", "RAIL_REPLACEMENT"]):
                op_impact = 80.0
            elif any(term in wt for term in ["BALLAST", "SURFACING", "POINT_OVERHAUL", "CANTILEVER"]):
                op_impact = 65.0
            elif any(term in wt for term in ["INSPECTION", "TEST", "MEGGERING", "CALIBRATION"]):
                op_impact = 40.0
            else:
                op_impact = 50.0
            if (user_priority or "").upper() == "HIGH":
                op_impact = min(100.0, op_impact + 10.0)

        op_label = "HIGH" if op_impact >= 75.0 else ("MEDIUM" if op_impact >= 50.0 else "LOW")
        op_reason = f"{op_label.capitalize()} operational impact on corridor capacity and train headways"

        # 4. Composite Formula calculation
        raw_score = (
            weights.get("criticality", 0.30) * c_score +
            weights.get("urgency", 0.20) * u_score +
            weights.get("overdue_risk", 0.15) * overdue_risk +
            weights.get("safety_impact", 0.20) * s_score +
            weights.get("operational_impact", 0.15) * op_impact
        )

        if is_emergency:
            raw_score = max(raw_score, 95.0)

        final_score = round(min(100.0, max(0.0, raw_score)), 1)

        # 5. Safety Tier Assignment
        if is_emergency or s_score >= 90.0 or final_score >= 90.0:
            safety_tier = "Tier 1 (Emergency)"
        elif s_score >= 75.0 or final_score >= 72.0 or u_score >= 85.0 or overdue_risk >= 85.0:
            safety_tier = "Tier 2 (Critical)"
        elif final_score >= 50.0:
            safety_tier = "Tier 3 (High)"
        else:
            safety_tier = "Tier 4 (Normal)"

        # 6. Structured Explainability Reasons (matching Prompt Section 8)
        reasons_list = []
        # Criticality
        if c_score >= 75.0:
            reasons_list.append("High criticality asset/work requirement")
        elif c_score >= 50.0:
            reasons_list.append("Moderate criticality maintenance demand")
        else:
            reasons_list.append("Routine priority asset procedure")

        # Due Date / Urgency / Overdue
        if diff_days is not None and diff_days < 0:
            reasons_list.append(f"OVERDUE by {abs(diff_days)} day(s) - critical scheduling priority")
        elif diff_days is not None and diff_days <= 2:
            reasons_list.append(f"Due date approaching (within {diff_days} day(s))")
        elif u_score >= 75.0:
            reasons_list.append("Urgent time window required")
        else:
            reasons_list.append("Standard advance planning horizon")

        # Safety Impact
        if s_score >= 75.0:
            reasons_list.append("High safety impact (track/signal/traction protection)")
        elif s_score >= 50.0:
            reasons_list.append("Moderate safety impact")
        else:
            reasons_list.append("Low safety risk to passing movements")

        # Operational Impact
        if op_impact >= 70.0:
            reasons_list.append("High operational impact on train headways")
        elif op_impact >= 50.0:
            reasons_list.append("Moderate operational impact")
        else:
            reasons_list.append("Minimal line capacity disruption")

        reasons_list.append("No existing conflict detected in primary target band")

        summary_reason_text = " • ".join(reasons_list)

        return {
            "priority_score": final_score,
            "safety_tier": safety_tier,
            "criticality": c_score,
            "criticality_label": c_label,
            "criticality_reason": c_reason,
            "criticality_sub_factors": c_sub,
            "safety_impact": s_score,
            "safety_impact_label": s_label,
            "safety_impact_reason": s_reason,
            "safety_sub_factors": s_sub,
            "urgency": u_score,
            "urgency_label": u_label,
            "urgency_reason": u_reason,
            "overdue_risk": overdue_risk,
            "overdue_risk_label": overdue_label,
            "overdue_risk_reason": overdue_reason,
            "operational_impact": op_impact,
            "operational_impact_label": op_label,
            "operational_impact_reason": op_reason,
            "user_priority": (user_priority or "MEDIUM").upper(),
            "due_date": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date) if due_date else None,
            "reasons": reasons_list,
            "reason": summary_reason_text,
            "factor_contributions": {
                "criticality_points": round(weights.get("criticality", 0.30) * c_score, 2),
                "urgency_points": round(weights.get("urgency", 0.20) * u_score, 2),
                "overdue_risk_points": round(weights.get("overdue_risk", 0.15) * overdue_risk, 2),
                "safety_impact_points": round(weights.get("safety_impact", 0.20) * s_score, 2),
                "operational_impact_points": round(weights.get("operational_impact", 0.15) * op_impact, 2)
            },
            "weights_used": weights,
            "disclaimer": "Configurable prototype weights; not official Indian Railways safety policy."
        }

    # Backward compatibility helper
    @classmethod
    def calculate_priority(
        cls,
        criticality: float = 50.0,
        urgency: float = 50.0,
        overdue_days: int = 0,
        safety_impact: float = 50.0,
        operational_impact: float = 50.0,
        is_emergency: bool = False,
        custom_weights: Dict[str, float] = None
    ) -> Tuple[float, str, Dict[str, Any]]:
        weights = custom_weights or {
            "criticality": 0.30,
            "urgency": 0.20,
            "overdue": 0.15,
            "safety_impact": 0.20,
            "operational_impact": 0.15
        }
        overdue_score = min(100.0, max(0.0, overdue_days * 10.0))
        c = min(100.0, max(0.0, criticality))
        u = min(100.0, max(0.0, urgency))
        s = min(100.0, max(0.0, safety_impact))
        o = min(100.0, max(0.0, operational_impact))

        raw = (
            weights.get("criticality", 0.3) * c +
            weights.get("urgency", 0.2) * u +
            weights.get("overdue", 0.15) * overdue_score +
            weights.get("safety_impact", 0.2) * s +
            weights.get("operational_impact", 0.15) * o
        )
        if is_emergency:
            raw = max(raw, 95.0)

        score = round(raw, 2)
        if is_emergency or s >= 90.0 or score >= 90.0:
            tier = "Tier 1 (Emergency)"
        elif s >= 75.0 or score >= 72.0 or overdue_days >= 7:
            tier = "Tier 2 (Critical)"
        elif score >= 50.0:
            tier = "Tier 3 (High)"
        else:
            tier = "Tier 4 (Normal)"

        explanation = {
            "score": score,
            "safety_tier": tier,
            "factor_contributions": {
                "criticality": round(weights.get("criticality", 0.3) * c, 2),
                "urgency": round(weights.get("urgency", 0.2) * u, 2),
                "overdue": round(weights.get("overdue", 0.15) * overdue_score, 2),
                "safety_impact": round(weights.get("safety_impact", 0.2) * s, 2),
                "operational_impact": round(weights.get("operational_impact", 0.15) * o, 2)
            },
            "reasons": ["Emergency track requirement flagged"] if is_emergency else ["Calculated based on multi-criteria analysis"]
        }
        return score, tier, explanation


def wt_human(work_type: str) -> str:
    if not work_type:
        return "Maintenance"
    return work_type.replace("_", " ").title()
