"""
Railway Maintenance Risk ML Module for SIH26027.
XGBoost-powered Maintenance Urgency and Risk Decision-Support Component.
"""

from .config import (
    MODEL_VERSION,
    DATASET_VERSION,
    DATA_SOURCE,
    DEFAULT_AI_PRIORITY_ENABLED,
    DEFAULT_ML_RISK_WEIGHT,
    classify_risk
)

__all__ = [
    "MODEL_VERSION",
    "DATASET_VERSION",
    "DATA_SOURCE",
    "DEFAULT_AI_PRIORITY_ENABLED",
    "DEFAULT_ML_RISK_WEIGHT",
    "classify_risk"
]
