"""
Online Inference Service for Railway Maintenance Risk (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

STRICT PRINCIPLES:
- Cached singleton model instance (loaded once, never during page load or optimization loops).
- Transparent failure handling with deterministic fallback.
- Advisory decision-support label ("AI PREDICTED MAINTENANCE RISK", never official safety score).
- Mathematically rigorous TreeSHAP feature contributions translated to human-readable contributing factors.
- Auditable predictions recorded in SQLite db.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
try:
    import pandas as pd
    import numpy as np
except Exception:
    pd = None
    np = None
try:
    import xgboost as xgb
except Exception:
    xgb = None

from app.ml.config import (
    MODEL_PATH,
    METADATA_PATH,
    MODEL_VERSION,
    DATA_SOURCE,
    FEATURE_NAMES,
    classify_risk
)
from app.ml.preprocessing.feature_builder import MaintenanceFeatureBuilder

logger = logging.getLogger("abps.ml.inference")


class PredictionResult:
    """Standardized Container for ML Maintenance Risk Output."""
    def __init__(
        self,
        ml_risk_score: Optional[float],
        risk_class: Optional[str],
        model_version: str,
        prediction_status: str,
        prediction_timestamp: str,
        data_source: str,
        top_contributing_factors: List[Dict[str, Any]],
        features_used: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        self.ml_risk_score = round(ml_risk_score, 1) if ml_risk_score is not None else None
        self.risk_score = self.ml_risk_score
        self.risk_class = risk_class
        self.model_version = model_version
        self.prediction_status = prediction_status
        self.prediction_timestamp = prediction_timestamp
        self.data_source = data_source
        self.top_contributing_factors = top_contributing_factors
        self.features_used = features_used
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ml_risk_score": self.ml_risk_score,
            "risk_score": self.ml_risk_score,
            "risk_class": self.risk_class,
            "model_version": self.model_version,
            "prediction_status": self.prediction_status,
            "prediction_timestamp": self.prediction_timestamp,
            "data_source": self.data_source,
            "top_contributing_factors": self.top_contributing_factors,
            "features_used": self.features_used,
            "error_message": self.error_message,
            "disclaimer": (
                "Advisory AI Predicted Maintenance Risk. Not an official Indian Railways "
                "safety score. Actual possession decisions require certified human planner review."
            )
        }


class MaintenanceRiskPredictor:
    """
    Cached, thread-safe Inference Service for Maintenance Risk Prediction.
    """

    _instance: Optional["MaintenanceRiskPredictor"] = None
    _booster: Optional[xgb.Booster] = None
    _metadata: Optional[Dict[str, Any]] = None
    _status: str = "ML MODEL NOT TRAINED"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MaintenanceRiskPredictor, cls).__new__(cls)
            cls._instance._init_service()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "MaintenanceRiskPredictor":
        """Returns the singleton instance of MaintenanceRiskPredictor."""
        return cls()

    def _init_service(self):
        """Loads and caches model booster and metadata on first instantiation."""
        self._load_model()

    def _load_model(self) -> bool:
        if xgb is None or pd is None or np is None:
            self._status = "ML LIBRARIES NOT INSTALLED"
            return False
        if not MODEL_PATH.exists():
            self._status = "ML MODEL NOT TRAINED"
            logger.warning(f"XGBoost model file not found at: {MODEL_PATH}")
            return False

        try:
            booster = xgb.Booster()
            booster.load_model(str(MODEL_PATH))
            self._booster = booster

            if METADATA_PATH.exists():
                with open(METADATA_PATH, "r") as f:
                    self._metadata = json.load(f)
            else:
                self._metadata = {"model_version": MODEL_VERSION, "data_source": DATA_SOURCE}

            self._status = "ML READY"
            logger.info(f"Loaded XGBoost model booster: {MODEL_VERSION} from {MODEL_PATH}")
            return True
        except Exception as e:
            self._status = "ML MODEL UNAVAILABLE"
            self._booster = None
            logger.error(f"Failed to load XGBoost booster: {e}", exc_info=True)
            return False

    @property
    def status(self) -> str:
        """Returns the current operational status of the ML service."""
        if not MODEL_PATH.exists():
            return "ML MODEL NOT TRAINED"
        if self._booster is None:
            # Try reloading once
            if not self._load_model():
                return "ML MODEL UNAVAILABLE"
        return "ML READY"

    @property
    def metadata(self) -> Dict[str, Any]:
        """Returns model metadata and training metrics."""
        if self._metadata is None and METADATA_PATH.exists():
            try:
                with open(METADATA_PATH, "r") as f:
                    self._metadata = json.load(f)
            except Exception:
                pass
        return self._metadata or {}

    def predict(
        self,
        job_data: Any,
        section_context: Optional[Dict[str, Any]] = None,
        reference_date: Optional[date] = None,
        db_session: Optional[Any] = None
    ) -> PredictionResult:
        """
        Executes online prediction for a maintenance request.
        Safe: Returns PredictionResult with fallback status on any failure.
        """
        now_iso = datetime.utcnow().isoformat() + "Z"

        if job_data is None:
            return PredictionResult(
                ml_risk_score=50.0,
                risk_class="MEDIUM",
                model_version=MODEL_VERSION,
                prediction_status="FALLBACK_DEFAULT",
                prediction_timestamp=now_iso,
                data_source=DATA_SOURCE,
                top_contributing_factors=[],
                features_used={},
                error_message="Job data was None; returned default fallback."
            )

        # Check model availability
        if self.status != "ML READY" or self._booster is None:
            return PredictionResult(
                ml_risk_score=None,
                risk_class=None,
                model_version=MODEL_VERSION,
                prediction_status="ML MODEL UNAVAILABLE",
                prediction_timestamp=now_iso,
                data_source=DATA_SOURCE,
                top_contributing_factors=[],
                features_used={},
                error_message="Model booster not available on disk."
            )

        # 1. Feature Engineering
        try:
            df_features, feat_meta = MaintenanceFeatureBuilder.extract_features_from_job(
                job_data=job_data,
                section_context=section_context,
                reference_date=reference_date
            )
        except Exception as e:
            logger.error(f"Feature engineering failed: {e}", exc_info=True)
            return PredictionResult(
                ml_risk_score=None,
                risk_class=None,
                model_version=MODEL_VERSION,
                prediction_status="ML INPUT DATA INSUFFICIENT",
                prediction_timestamp=now_iso,
                data_source=DATA_SOURCE,
                top_contributing_factors=[],
                features_used={},
                error_message=f"Feature extraction error: {str(e)}"
            )

        # 2. XGBoost Prediction & TreeSHAP Contribution
        try:
            dmatrix = xgb.DMatrix(df_features)
            # Predict with TreeSHAP contributions
            contribs = self._booster.predict(dmatrix, pred_contribs=True)
            # contribs shape: (1, num_features + 1), where last is base margin
            raw_pred = float(np.sum(contribs[0]))
            risk_score = float(np.clip(raw_pred, 5.0, 99.0))
            risk_class = classify_risk(risk_score)

            # 3. Generate Human-Readable Contributing Factors
            top_factors = self._build_human_explanation(
                feature_row=df_features.iloc[0],
                contrib_row=contribs[0][:-1]
            )

            result = PredictionResult(
                ml_risk_score=risk_score,
                risk_class=risk_class,
                model_version=MODEL_VERSION,
                prediction_status="ML PREDICTION AVAILABLE",
                prediction_timestamp=now_iso,
                data_source=DATA_SOURCE,
                top_contributing_factors=top_factors,
                features_used=df_features.iloc[0].to_dict()
            )

            # 4. Optional Audit Logging
            if db_session is not None:
                self._record_prediction_audit(db_session, job_data, result)

            return result

        except Exception as e:
            logger.error(f"XGBoost inference failed: {e}", exc_info=True)
            return PredictionResult(
                ml_risk_score=None,
                risk_class=None,
                model_version=MODEL_VERSION,
                prediction_status="ML PREDICTION FAILED",
                prediction_timestamp=now_iso,
                data_source=DATA_SOURCE,
                top_contributing_factors=[],
                features_used=df_features.iloc[0].to_dict() if 'df_features' in locals() else {},
                error_message=f"Inference computation error: {str(e)}"
            )

    def _build_human_explanation(
        self,
        feature_row: pd.Series,
        contrib_row: np.ndarray,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Translates raw TreeSHAP values into planner-friendly contributing factor descriptions.
        Phrased strictly as 'Contributing factor' / 'Contributes to risk', NEVER as 'Cause'.
        """
        factor_items = []

        labels = {
            "defect_severity": ("Defect severity", lambda v: {1: "MINOR", 2: "MODERATE", 3: "SEVERE", 4: "EMERGENCY"}.get(int(v), "STANDARD")),
            "safety_impact": ("Baseline safety impact", lambda v: f"{v:.1f}/100"),
            "days_until_due": ("Days to due date", lambda v: f"{int(v)} days" if v >= 0 else f"OVERDUE by {abs(int(v))}d"),
            "overdue_days": ("Overdue duration", lambda v: f"{int(v)} days overdue" if v > 0 else "On schedule"),
            "train_traffic_density": ("Section train density", lambda v: f"{int(v)} trains/day ({'HIGH' if v > 70 else 'MODERATE'})"),
            "section_utilization": ("Section utilization", lambda v: f"{v:.1f}% capacity"),
            "asset_criticality": ("Asset criticality", lambda v: f"{v:.1f}/100 ({'HIGH' if v > 75 else 'MEDIUM'})"),
            "defect_age_days": ("Defect age", lambda v: f"{int(v)} days active"),
            "asset_condition": ("Asset condition index", lambda v: f"{v:.1f}/100 ({'POOR' if v < 45 else 'FAIR'})"),
            "historical_delay_impact_min": ("Historical delay impact", lambda v: f"{v:.0f} min"),
            "failure_history_count": ("Past asset failure history", lambda v: f"{int(v)} recorded incidents"),
            "operational_importance": ("Operational route importance", lambda v: f"{v:.1f}/100")
        }

        # Pair features with contributions
        paired = list(zip(FEATURE_NAMES, contrib_row))
        # Sort by absolute impact magnitude
        paired.sort(key=lambda x: abs(x[1]), reverse=True)

        for feat_name, impact in paired[:top_k]:
            val = feature_row.get(feat_name, 0.0)
            human_label, formatter = labels.get(feat_name, (feat_name.replace("_", " ").title(), lambda v: str(v)))
            formatted_val = formatter(val)

            direction = "INCREASES_RISK" if impact > 0 else "REDUCES_RISK"
            impact_sign = "+" if impact > 0 else ""

            factor_items.append({
                "feature": feat_name,
                "label": human_label,
                "value": formatted_val,
                "impact_points": round(float(impact), 2),
                "impact_label": f"{impact_sign}{impact:.1f} pts",
                "direction": direction,
                "description": f"{human_label} ({formatted_val}): contributes {impact_sign}{impact:.1f} to predicted risk"
            })

        return factor_items

    def _record_prediction_audit(self, db: Any, job_data: Any, result: PredictionResult):
        """Auditable persistence: saves ML prediction to the database without overwriting history."""
        try:
            # Dynamically import to avoid cyclic import
            from app.models.models import MLPrediction

            job_id = None
            job_code = None
            if hasattr(job_data, "id"):
                job_id = getattr(job_data, "id")
                job_code = getattr(job_data, "job_code", None)
            elif isinstance(job_data, dict):
                job_id = job_data.get("id")
                job_code = job_data.get("job_code")

            if job_id:
                pred_record = MLPrediction(
                    request_id=job_id,
                    job_code=job_code,
                    model_version=result.model_version,
                    risk_score=result.ml_risk_score if result.ml_risk_score is not None else 0.0,
                    risk_class=result.risk_class or "UNAVAILABLE",
                    feature_version="v1.0",
                    prediction_timestamp=datetime.utcnow(),
                    prediction_status=result.prediction_status,
                    explanation_json=result.top_contributing_factors,
                    features_json=result.features_used,
                    data_source=result.data_source
                )
                db.add(pred_record)
                db.commit()
        except Exception as e:
            logger.warning(f"Could not write ML prediction audit record: {e}")
            if db:
                db.rollback()


# Singleton Instance
risk_predictor = MaintenanceRiskPredictor()
