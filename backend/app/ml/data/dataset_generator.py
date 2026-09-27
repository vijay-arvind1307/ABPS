"""
Simulation Dataset Generator for Railway Maintenance Risk (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

PROVENANCE:
- Data Source: SIMULATED (Synthetic Physics-Grounded Scenarios)
- Target: maintenance_risk (0 - 100 continuous score)
- NOT real historical outcomes (transparently disclosed for SIH demonstration credibility).
- Non-linear physics & operations deterioration model (distinct from deterministic weighted priority).
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from app.ml.config import (
    DATASET_PATH,
    DATASET_VERSION,
    DATA_SOURCE,
    FEATURE_NAMES,
    DEPARTMENT_MAP,
    WORK_TYPE_MAP,
    USER_PRIORITY_MAP
)


def generate_simulated_dataset(num_samples: int = 3000, random_seed: int = 20260924) -> pd.DataFrame:
    """
    Generates a realistic, physics-grounded synthetic dataset representing
    railway maintenance demand risk scenarios across Indian Railways corridors.
    """
    np.random.seed(random_seed)

    records = []
    dept_choices = ["ENGG", "TRD", "SNT", "OPTG"]
    work_types = [
        "TRACK_TAMPING", "RAIL_REPLACEMENT", "OHE_INSPECTION", "POINT_OVERHAUL",
        "BALLAST_CLEANING", "TRACK_CIRCUIT", "WELD_REPAIR"
    ]

    for i in range(num_samples):
        # 1. Structural Railway Features
        dept = np.random.choice(dept_choices, p=[0.45, 0.25, 0.20, 0.10])
        wt = np.random.choice(work_types)
        user_prio = np.random.choice(["LOW", "MEDIUM", "HIGH"], p=[0.25, 0.50, 0.25])

        # Asset State
        asset_age_years = round(float(np.random.gamma(shape=3.0, scale=3.5)), 1)
        asset_age_years = min(38.0, max(0.5, asset_age_years))

        # Asset condition: 100 is pristine, 10 is failing
        # Older assets trend toward lower condition with variance
        cond_mean = max(20.0, 95.0 - (asset_age_years * 2.2))
        asset_condition = round(float(np.random.normal(loc=cond_mean, scale=12.0)), 1)
        asset_condition = min(100.0, max(10.0, asset_condition))

        # Asset criticality (depends on work type and mainline nature)
        if wt in ["RAIL_REPLACEMENT", "POINT_OVERHAUL", "OHE_POWER_BLOCK"]:
            crit_base = np.random.uniform(70.0, 98.0)
        elif wt in ["TRACK_TAMPING", "BALLAST_CLEANING", "WELD_REPAIR"]:
            crit_base = np.random.uniform(50.0, 85.0)
        else:
            crit_base = np.random.uniform(30.0, 75.0)
        asset_criticality = round(float(crit_base), 1)

        # Defect characteristics
        # 1=Minor, 2=Moderate, 3=Severe, 4=Emergency
        if asset_condition < 35.0:
            defect_severity = int(np.random.choice([2, 3, 4], p=[0.2, 0.5, 0.3]))
        elif asset_condition < 65.0:
            defect_severity = int(np.random.choice([1, 2, 3], p=[0.3, 0.5, 0.2]))
        else:
            defect_severity = int(np.random.choice([1, 2], p=[0.7, 0.3]))

        defect_age_days = int(np.random.exponential(scale=14.0))
        defect_age_days = min(90, max(0, defect_age_days))

        # Due Date / Overdue Dynamics
        days_until_due = int(np.random.normal(loc=5.0, scale=10.0))
        days_until_due = max(-25, min(40, days_until_due))
        overdue_days = max(0, -days_until_due)

        # Maintenance & Failure History
        failure_history_count = int(np.random.poisson(lam=max(0.5, (40.0 - asset_age_years * 0.5) / 10.0 + (100.0 - asset_condition) / 25.0)))
        failure_history_count = min(15, failure_history_count)

        maintenance_frequency_days = int(np.random.choice([30, 45, 60, 90, 180]))
        last_maintenance_age_days = int(np.random.uniform(10, maintenance_frequency_days * 1.6))

        # Operational Corridor Context
        operational_importance = round(float(np.random.uniform(40.0, 98.0)), 1)
        train_traffic_density = int(np.random.uniform(20, 115))  # trains per day
        section_utilization = round(float(min(98.0, 25.0 + train_traffic_density * 0.65 + np.random.normal(0, 5.0))), 1)
        historical_delay_impact_min = round(float(max(0.0, failure_history_count * np.random.uniform(8.0, 25.0) + (100.0 - asset_condition) * 0.4)), 1)
        maintenance_duration_min = int(np.random.choice([60, 90, 120, 150, 180, 240]))
        safety_impact = round(float(min(98.0, 25.0 + defect_severity * 16.0 + (100.0 - asset_condition) * 0.25)), 1)
        current_priority_score = round(float(np.random.uniform(35.0, 95.0)), 1)
        request_age_days = int(np.random.uniform(0, 25))

        # -------------------------------------------------------------
        # Non-linear Physics & Operational Headway Risk Model (Target)
        # -------------------------------------------------------------
        # 1. Structural Defect Threat (accelerates as defect matures on poor condition asset)
        severity_weight = {1: 12.0, 2: 30.0, 3: 55.0, 4: 85.0}[defect_severity]
        defect_escalation = (defect_age_days / 25.0) ** 1.25 * (severity_weight * 0.40)

        # 2. Overdue Penalty (exponential penalty if overdue on high traffic line)
        if overdue_days > 0:
            overdue_factor = min(45.0, 10.0 + (overdue_days ** 1.15) * 3.2 * (operational_importance / 65.0))
        else:
            overdue_factor = max(-12.0, -0.7 * days_until_due)

        # 3. Dynamic Traffic & Line Utilization Risk
        corridor_traffic_risk = (train_traffic_density / 90.0) * (section_utilization / 85.0) * 30.0

        # 4. Asset Degradation Baseline
        condition_deficit = ((100.0 - asset_condition) / 100.0) ** 1.3 * 35.0
        failure_penalty = min(20.0, failure_history_count * 2.5)

        # 5. Composite Risk Calculation
        raw_risk = (
            severity_weight * 0.35 +
            defect_escalation * 0.25 +
            overdue_factor * 0.35 +
            corridor_traffic_risk * 0.25 +
            condition_deficit * 0.30 +
            failure_penalty * 0.20 +
            (asset_criticality / 100.0) * 16.0 +
            (safety_impact / 100.0) * 14.0
        )

        # Add realistic railway measurement noise (Gaussian variance)
        stochastic_noise = np.random.normal(loc=0.0, scale=2.8)
        simulated_risk = round(float(np.clip(raw_risk + stochastic_noise, 6.0, 98.5)), 1)

        row = {
            "record_id": f"SIM-REQ-{i+1:05d}",
            "data_source": DATA_SOURCE,
            "dataset_version": DATASET_VERSION,
            "department": dept,
            "department_code_enc": DEPARTMENT_MAP.get(dept, 4),
            "work_type": wt,
            "work_type_enc": WORK_TYPE_MAP.get(wt, 7),
            "user_priority": user_prio,
            "user_priority_enc": USER_PRIORITY_MAP.get(user_prio, 1),
            "asset_condition": asset_condition,
            "asset_age_years": asset_age_years,
            "asset_criticality": asset_criticality,
            "defect_severity": defect_severity,
            "defect_age_days": defect_age_days,
            "days_until_due": days_until_due,
            "overdue_days": overdue_days,
            "failure_history_count": failure_history_count,
            "maintenance_frequency_days": maintenance_frequency_days,
            "last_maintenance_age_days": last_maintenance_age_days,
            "operational_importance": operational_importance,
            "train_traffic_density": train_traffic_density,
            "section_utilization": section_utilization,
            "historical_delay_impact_min": historical_delay_impact_min,
            "maintenance_duration_min": maintenance_duration_min,
            "safety_impact": safety_impact,
            "current_priority_score": current_priority_score,
            "request_age_days": request_age_days,
            # Target
            "maintenance_risk": simulated_risk
        }
        records.append(row)

    df = pd.DataFrame(records)
    return df


def generate_and_save_dataset():
    """Generates and writes the dataset to the official ML data path."""
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Generating physics-grounded simulated maintenance dataset (N=3000)...")
    df = generate_simulated_dataset(num_samples=3000)
    df.to_csv(DATASET_PATH, index=False)
    print(f"Successfully generated and saved {len(df)} records to: {DATASET_PATH}")
    print(f"Data Source: {DATA_SOURCE} | Version: {DATASET_VERSION}")
    print(f"Maintenance Risk Target Summary:\n{df['maintenance_risk'].describe().to_string()}")
    return df


if __name__ == "__main__":
    generate_and_save_dataset()
