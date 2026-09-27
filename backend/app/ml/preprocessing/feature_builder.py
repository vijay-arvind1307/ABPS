"""
Feature Engineering and Preprocessing Pipeline for Railway Maintenance Risk (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

STRICT CONSTRAINTS:
- No data leakage: only pre-possession / request-time features are used.
- No free-text fields fed directly to model.
- Documented deterministic categorical encodings.
- Missing value imputation with principled railway domain defaults.
"""

from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import numpy as np

from app.ml.config import (
    FEATURE_NAMES,
    DEPARTMENT_MAP,
    WORK_TYPE_MAP,
    USER_PRIORITY_MAP
)


class MaintenanceFeatureBuilder:
    """
    Constructs normalized, non-leaking feature vectors for the XGBoost Maintenance Risk Model.
    Accepts MaintenanceJob instances (SQLAlchemy or dict) and optional corridor/section context.
    """

    @classmethod
    def extract_features_from_job(
        cls,
        job_data: Any,
        section_context: Optional[Dict[str, Any]] = None,
        reference_date: Optional[date] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Extracts structured feature vector from MaintenanceJob object or dict.
        Returns:
            df: Single-row pandas DataFrame matching exact FEATURE_NAMES order.
            metadata: Diagnostic dict containing imputation log and feature summary.
        """
        if reference_date is None:
            reference_date = datetime.utcnow().date()

        # Handle both dict and ORM model
        if hasattr(job_data, "__dict__"):
            j = {k: v for k, v in job_data.__dict__.items() if not k.startswith("_")}
            # Also extract relationship hints if available
            if hasattr(job_data, "department") and job_data.department:
                j["department_code"] = getattr(job_data.department, "code", "ENGG")
            if hasattr(job_data, "section") and job_data.section:
                sec = job_data.section
                j["section_train_density"] = getattr(sec, "trains_per_day", None)
                j["section_utilization"] = getattr(sec, "utilization_pct", None)
        else:
            j = dict(job_data)

        imputations: List[str] = []

        # 1. Department & Work Type Encodings
        dept = str(j.get("department_code") or j.get("department") or "ENGG").upper()
        if dept not in DEPARTMENT_MAP:
            dept_enc = DEPARTMENT_MAP["OTHER"]
            imputations.append(f"Unmapped department '{dept}', used default OTHER")
        else:
            dept_enc = DEPARTMENT_MAP[dept]

        wt = str(j.get("work_type") or "TRACK_TAMPING").upper()
        # Find closest match or unmapped
        wt_enc = WORK_TYPE_MAP.get(wt)
        if wt_enc is None:
            # check substring
            for k, code in WORK_TYPE_MAP.items():
                if k in wt:
                    wt_enc = code
                    break
            if wt_enc is None:
                wt_enc = WORK_TYPE_MAP["OTHER"]
                imputations.append(f"Unmapped work_type '{wt}', used default OTHER")

        prio = str(j.get("user_priority") or "MEDIUM").upper()
        prio_enc = USER_PRIORITY_MAP.get(prio, 1)

        # 2. Asset Condition & Criticality
        raw_cond = j.get("asset_condition_score")
        if raw_cond is not None and not np.isnan(float(raw_cond)):
            asset_condition = float(raw_cond)
        else:
            # Deterministic default based on work type severity
            if any(term in wt for term in ["FRACTURE", "DEFECT", "RAIL_REPLACEMENT"]):
                asset_condition = 32.0
            elif any(term in wt for term in ["TAMPING", "SURFACING", "POINT_OVERHAUL"]):
                asset_condition = 55.0
            else:
                asset_condition = 70.0
            imputations.append("asset_condition inferred from work type profile")

        raw_crit = j.get("calculated_criticality") or j.get("criticality")
        if raw_crit is not None and not np.isnan(float(raw_crit)):
            asset_criticality = float(raw_crit)
        else:
            asset_criticality = 60.0
            imputations.append("asset_criticality default 60.0")

        # 3. Defect Severity & Age
        # Derive severity (1-4)
        if j.get("is_emergency", False):
            defect_severity = 4
        elif asset_condition < 35.0 or "FRACTURE" in wt or "REPLACEMENT" in wt:
            defect_severity = 3
        elif asset_condition < 65.0 or prio == "HIGH":
            defect_severity = 2
        else:
            defect_severity = 1

        # Defect age days (from request submission or created_at)
        created_at = j.get("created_at") or j.get("submitted_at")
        if created_at:
            try:
                if isinstance(created_at, str):
                    c_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
                elif isinstance(created_at, datetime):
                    c_date = created_at.date()
                elif isinstance(created_at, date):
                    c_date = created_at
                else:
                    c_date = reference_date
                defect_age_days = max(0, (reference_date - c_date).days)
            except Exception:
                defect_age_days = 7
        else:
            defect_age_days = 7

        # 4. Due Date Dynamics
        due_date_raw = j.get("due_date")
        if due_date_raw:
            try:
                if isinstance(due_date_raw, str):
                    d_date = datetime.fromisoformat(due_date_raw.replace("Z", "+00:00")).date()
                elif isinstance(due_date_raw, datetime):
                    d_date = due_date_raw.date()
                elif isinstance(due_date_raw, date):
                    d_date = due_date_raw
                else:
                    d_date = None
            except Exception:
                d_date = None
        else:
            d_date = None

        if d_date:
            days_until_due = (d_date - reference_date).days
            overdue_days = max(0, -days_until_due)
        else:
            # Fallback based on user priority
            overdue_days = int(j.get("overdue_days") or 0)
            days_until_due = -overdue_days if overdue_days > 0 else (3 if prio == "HIGH" else 7)

        # 5. Asset Age & Maintenance History
        asset_age_years = float(j.get("asset_age_years") or 12.0)
        failure_history_count = int(j.get("failure_history_count") or (2 if asset_condition < 50 else 1))
        maintenance_frequency_days = int(j.get("maintenance_frequency_days") or 60)
        last_maintenance_age_days = int(j.get("last_maintenance_age_days") or 45)

        # 6. Operational & Section Traffic Context
        ctx = section_context or {}
        traffic_density = int(
            j.get("section_train_density") or
            ctx.get("trains_per_day") or
            ctx.get("train_traffic_density") or
            55
        )
        section_util = float(
            j.get("section_utilization") or
            ctx.get("utilization_pct") or
            ctx.get("section_utilization") or
            68.0
        )
        operational_importance = float(
            j.get("operational_importance_score") or
            j.get("operational_impact") or
            ctx.get("operational_importance") or
            70.0
        )
        historical_delay = float(j.get("historical_delay_impact_min") or (failure_history_count * 12.0))
        duration_min = int(j.get("estimated_duration_min") or 120)
        safety_impact = float(j.get("calculated_safety_impact") or j.get("safety_impact") or 65.0)

        # 7. Construct Feature Dictionary in Exact Order
        feature_dict = {
            "asset_condition": float(asset_condition),
            "asset_age_years": float(asset_age_years),
            "asset_criticality": float(asset_criticality),
            "defect_severity": int(defect_severity),
            "defect_age_days": int(defect_age_days),
            "days_until_due": int(days_until_due),
            "overdue_days": int(overdue_days),
            "failure_history_count": int(failure_history_count),
            "maintenance_frequency_days": int(maintenance_frequency_days),
            "last_maintenance_age_days": int(last_maintenance_age_days),
            "operational_importance": float(operational_importance),
            "train_traffic_density": int(traffic_density),
            "section_utilization": float(section_util),
            "historical_delay_impact_min": float(historical_delay),
            "maintenance_duration_min": int(duration_min),
            "safety_impact": float(safety_impact),
            "department_code_enc": int(dept_enc),
            "work_type_enc": int(wt_enc),
            "user_priority_enc": int(prio_enc)
        }

        # Convert to single-row DataFrame with strict column order
        df = pd.DataFrame([feature_dict])[FEATURE_NAMES]

        metadata = {
            "job_code": j.get("job_code", "UNKNOWN"),
            "work_type": wt,
            "department": dept,
            "user_priority": prio,
            "is_emergency": bool(j.get("is_emergency", False)),
            "imputations": imputations,
            "feature_count": len(FEATURE_NAMES)
        }

        return df, metadata

    @classmethod
    def build_features(
        cls,
        job_data: Any,
        section_context: Optional[Dict[str, Any]] = None,
        reference_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Convenience method returning dictionary of feature values."""
        df, _ = cls.extract_features_from_job(job_data, section_context, reference_date)
        return df.iloc[0].to_dict()
