"""
Central Configuration for Railway Maintenance Risk ML Module (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

IMPORTANT:
- ML predictions are decision-support heuristics and NOT official Indian Railways safety scores.
- When AI mode is disabled or model fails, the system falls back 100% safely to deterministic priority.
- Features are strictly non-leaking and derived from pre-possession asset and traffic state.
"""

from pathlib import Path
from typing import Dict, List, Any

# Base Directory Resolution
ML_ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_DIR = ML_ROOT_DIR.parent.parent

# Model & Artifact Paths
MODEL_PATH = ML_ROOT_DIR / "models" / "maintenance_risk_v1.json"
METADATA_PATH = ML_ROOT_DIR / "models" / "model_metadata.json"
DATASET_PATH = ML_ROOT_DIR / "data" / "simulated_maintenance_dataset.csv"
EVALUATION_REPORT_PATH = ML_ROOT_DIR / "evaluation" / "evaluation_report.json"

# Model Identification & Provenance
MODEL_VERSION = "MRISK-XGB-1.0"
FEATURE_VERSION = "v1.0-structured"
DATASET_VERSION = "SIM-MRISK-2026.1"
ALGORITHM_NAME = "XGBoost Regressor (GBDT)"
DATA_SOURCE = "SIMULATED"  # Clearly marked: Synthetic railway degradation scenarios
TARGET_VARIABLE = "maintenance_risk"
TARGET_DESCRIPTION = (
    "Estimated multi-factor physical degradation and operational headway risk (0-100) "
    "if the requested maintenance possession is delayed or deferred."
)

# Central AI Weight & Integration Settings
DEFAULT_AI_PRIORITY_ENABLED = True
DEFAULT_ML_RISK_WEIGHT = 0.15  # 15% ML Risk + 85% Deterministic Multi-factor Priority

# Risk Classification Thresholds (0 - 100 Continuous Scale)
RISK_THRESHOLDS = {
    "LOW": (0.0, 40.0),
    "MEDIUM": (40.0, 70.0),
    "HIGH": (70.0, 85.0),
    "CRITICAL": (85.0, 100.0)
}

def classify_risk(risk_score: float) -> str:
    """Classifies continuous risk score into advisory operational risk tier."""
    val = float(risk_score)
    if val >= 85.0:
        return "CRITICAL"
    elif val >= 70.0:
        return "HIGH"
    elif val >= 40.0:
        return "MEDIUM"
    return "LOW"

# Feature Definitions (Zero data leakage: all known at request time)
FEATURE_NAMES: List[str] = [
    "asset_condition",               # 10.0 (failing) - 100.0 (pristine)
    "asset_age_years",               # 0.5 - 35.0 years in track service
    "asset_criticality",             # 10.0 - 100.0 physical asset criticality
    "defect_severity",               # 1: Minor, 2: Moderate, 3: Severe, 4: Emergency
    "defect_age_days",               # Days since initial defect detection
    "days_until_due",                # Target due date minus current date (negative if overdue)
    "overdue_days",                  # Days overdue (>= 0)
    "failure_history_count",         # Historical failure incidence on asset/section
    "maintenance_frequency_days",    # Recommended maintenance interval
    "last_maintenance_age_days",     # Elapsed days since last overhaul
    "operational_importance",        # Section line capacity importance (10 - 100)
    "train_traffic_density",         # Number of daily scheduled trains on section
    "section_utilization",           # Section track capacity utilization % (15 - 98)
    "historical_delay_impact_min",   # Historical delay minutes caused by past failures
    "maintenance_duration_min",      # Estimated possession duration in minutes
    "safety_impact",                 # Deterministic baseline safety consequence
    "department_code_enc",           # Categorical encoding (ENGG=0, TRD=1, SNT=2, OPTG=3, OTHER=4)
    "work_type_enc",                 # Categorical encoding (0-7)
    "user_priority_enc"              # Categorical encoding (LOW=0, MEDIUM=1, HIGH=2)
]

# Categorical Encodings (Deterministic & documented)
DEPARTMENT_MAP: Dict[str, int] = {
    "ENGG": 0,
    "TRD": 1,
    "SNT": 2,
    "OPTG": 3,
    "MECHANICAL": 4,
    "OTHER": 4
}

WORK_TYPE_MAP: Dict[str, int] = {
    "TRACK_TAMPING": 0,
    "RAIL_REPLACEMENT": 1,
    "OHE_INSPECTION": 2,
    "POINT_OVERHAUL": 3,
    "BALLAST_CLEANING": 4,
    "TRACK_CIRCUIT": 5,
    "WELD_REPAIR": 6,
    "OHE_POWER_BLOCK": 2,
    "TURNOUT_RENEWAL": 1,
    "DEEP_SCREENING": 4,
    "SIGNAL_TEST": 5,
    "OTHER": 7
}

USER_PRIORITY_MAP: Dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2
}

# XGBoost Training Hyperparameters (Reproducible & optimized for tabular railway data)
XGB_HYPERPARAMETERS: Dict[str, Any] = {
    "n_estimators": 160,
    "max_depth": 5,
    "learning_rate": 0.07,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "min_child_weight": 3,
    "gamma": 0.1,
    "reg_alpha": 0.05,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1
}

# Compatibility Aliases
FEATURE_COLUMNS = FEATURE_NAMES
get_risk_class = classify_risk
