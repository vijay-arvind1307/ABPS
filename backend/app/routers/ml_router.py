"""
ML API Router for Railway Maintenance Risk (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

Advisory Decision-Support Endpoints:
- GET  /api/ml/model-status
- GET  /api/ml/model-metadata
- GET  /api/ml/evaluation
- GET  /api/ml/prediction/{request_id}
- POST /api/ml/predict/{request_id}
- GET  /api/ml/explanation/{request_id}
- GET  /api/ml/config
- POST /api/ml/toggle-ai
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from app.db.session import get_db
from app.models.models import MaintenanceJob, MLPrediction, SystemConfig, RailwaySection
from app.ml.inference.risk_predictor import risk_predictor
from app.ml.config import (
    MODEL_VERSION,
    DATASET_VERSION,
    DATA_SOURCE,
    ALGORITHM_NAME,
    EVALUATION_REPORT_PATH,
    classify_risk
)
from app.algorithms.priority import PriorityEngine

router = APIRouter()


class ToggleAIRequest(BaseModel):
    enabled: bool
    ml_weight: Optional[float] = None


@router.get("/model-status")
def get_model_status(db: Session = Depends(get_db)):
    """
    Returns current status and provenance of the XGBoost maintenance risk model.
    """
    meta = risk_predictor.metadata
    ai_enabled, ml_weight = PriorityEngine.get_ai_config(db)

    # Fetch latest prediction timestamp from db
    last_pred = db.query(MLPrediction).order_by(MLPrediction.prediction_timestamp.desc()).first()

    return {
        "model_name": "AI Maintenance Risk Predictor",
        "algorithm": ALGORITHM_NAME,
        "model_version": meta.get("model_version", MODEL_VERSION),
        "status": risk_predictor.status,
        "is_ready": (risk_predictor.status == "ML READY"),
        "ai_priority_enabled": ai_enabled,
        "ml_risk_weight": ml_weight,
        "feature_count": meta.get("feature_count", 19),
        "data_source": meta.get("data_source", DATA_SOURCE),
        "dataset_version": meta.get("dataset_version", DATASET_VERSION),
        "training_timestamp": meta.get("training_timestamp"),
        "test_metrics": meta.get("evaluation_metrics", {}),
        "last_prediction_timestamp": last_pred.prediction_timestamp.isoformat() if last_pred else None,
        "disclaimer": (
            "Advisory AI Predicted Maintenance Risk. Not an official Indian Railways "
            "safety score. Planning decisions must follow certified safety rules."
        )
    }


@router.get("/model-metadata")
def get_model_metadata():
    """Returns detailed offline training metadata and hyperparameter configuration."""
    meta = risk_predictor.metadata
    if not meta:
        return {
            "model_version": MODEL_VERSION,
            "status": "UNAVAILABLE",
            "message": "Metadata not found. Model training required."
        }
    return meta


@router.get("/evaluation")
def get_model_evaluation():
    """Returns held-out test evaluation report and baseline heuristic comparison."""
    import json
    if not EVALUATION_REPORT_PATH.exists():
        # Fall back to metadata metrics if report file not generated
        meta = risk_predictor.metadata
        return meta.get("evaluation_metrics", {"status": "EVALUATION_PENDING"})
    try:
        with open(EVALUATION_REPORT_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read evaluation report: {str(e)}")


@router.get("/config")
def get_ai_config(db: Session = Depends(get_db)):
    """Returns central AI Priority configuration."""
    enabled, weight = PriorityEngine.get_ai_config(db)
    return {
        "ai_priority_enabled": enabled,
        "ml_risk_weight": weight,
        "deterministic_weight": round(1.0 - weight, 2),
        "model_version": MODEL_VERSION
    }


@router.post("/toggle-ai")
def toggle_ai(req: ToggleAIRequest, db: Session = Depends(get_db)):
    """Toggles AI Assisted Priority Mode ON/OFF and optionally adjusts ML weight."""
    cfg_en = db.query(SystemConfig).filter(SystemConfig.key == "AI_PRIORITY_ENABLED").first()
    if not cfg_en:
        cfg_en = SystemConfig(key="AI_PRIORITY_ENABLED", value=str(req.enabled).lower(), description="Enable AI Priority")
        db.add(cfg_en)
    else:
        cfg_en.value = str(req.enabled).lower()

    if req.ml_weight is not None:
        clamped_weight = min(0.50, max(0.05, float(req.ml_weight)))
        cfg_wt = db.query(SystemConfig).filter(SystemConfig.key == "ML_RISK_WEIGHT").first()
        if not cfg_wt:
            cfg_wt = SystemConfig(key="ML_RISK_WEIGHT", value=str(clamped_weight), description="ML Risk Weight")
            db.add(cfg_wt)
        else:
            cfg_wt.value = str(clamped_weight)

    db.commit()

    enabled, weight = PriorityEngine.get_ai_config(db)
    return {
        "message": f"AI Mode successfully toggled to {'ON' if enabled else 'OFF'}",
        "ai_priority_enabled": enabled,
        "ml_risk_weight": weight
    }


@router.get("/prediction/{request_id}")
def get_prediction(request_id: int, db: Session = Depends(get_db)):
    """
    Returns latest ML prediction for a maintenance request.
    Computes and records prediction if not previously cached.
    """
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == request_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Maintenance request {request_id} not found")

    # Check for existing prediction record
    pred = db.query(MLPrediction).filter(
        MLPrediction.request_id == request_id,
        MLPrediction.model_version == MODEL_VERSION
    ).order_by(MLPrediction.prediction_timestamp.desc()).first()

    if pred and job.ml_risk_score is not None:
        ai_enabled, ml_weight = PriorityEngine.get_ai_config(db)
        det_score = job.priority_score if not ai_enabled else (
            job.calculated_criticality * 0.30 + job.calculated_urgency * 0.20 +
            (job.overdue_risk_score or 0) * 0.15 + job.calculated_safety_impact * 0.20 +
            (job.operational_impact or 50.0) * 0.15
        )
        ai_score = round((1.0 - ml_weight) * det_score + ml_weight * pred.risk_score, 1) if ai_enabled else det_score

        return {
            "request_id": job.id,
            "job_code": job.job_code,
            "ml_risk_score": pred.risk_score,
            "risk_class": pred.risk_class,
            "model_version": pred.model_version,
            "prediction_status": pred.prediction_status,
            "prediction_timestamp": pred.prediction_timestamp.isoformat() if pred.prediction_timestamp else None,
            "data_source": pred.data_source,
            "top_contributing_factors": pred.explanation_json or [],
            "deterministic_priority_score": round(det_score, 1),
            "ai_assisted_priority_score": ai_score,
            "ai_priority_enabled": ai_enabled,
            "formula_breakdown": (
                f"{det_score:.1f} * {(1.0 - ml_weight)*100:.0f}% (Deterministic) + "
                f"{pred.risk_score:.1f} * {ml_weight*100:.0f}% (AI Risk) = {ai_score:.1f}"
            ) if ai_enabled else f"100% Deterministic: {det_score:.1f}"
        }

    # Otherwise compute online
    sec = db.query(RailwaySection).filter(RailwaySection.id == job.section_id).first() if job.section_id else None
    sec_ctx = {"trains_per_day": getattr(sec, "trains_per_day", 55), "utilization_pct": getattr(sec, "utilization_pct", 68.0)}

    res = risk_predictor.predict(job_data=job, section_context=sec_ctx, db_session=db)

    # Update job columns
    ai_enabled, ml_weight = PriorityEngine.get_ai_config(db)
    det_score = job.priority_score or 50.0
    if res.ml_risk_score is not None:
        job.ml_risk_score = res.ml_risk_score
        job.ml_risk_class = res.risk_class
        job.ml_model_version = res.model_version
        job.ml_explanation = res.top_contributing_factors
        if ai_enabled:
            job.ai_assisted_priority_score = round((1.0 - ml_weight) * det_score + ml_weight * res.ml_risk_score, 1)
        else:
            job.ai_assisted_priority_score = det_score
        db.commit()

    return {
        "request_id": job.id,
        "job_code": job.job_code,
        "ml_risk_score": res.ml_risk_score,
        "risk_class": res.risk_class,
        "model_version": res.model_version,
        "prediction_status": res.prediction_status,
        "prediction_timestamp": res.prediction_timestamp,
        "data_source": res.data_source,
        "top_contributing_factors": res.top_contributing_factors,
        "deterministic_priority_score": round(det_score, 1),
        "ai_assisted_priority_score": job.ai_assisted_priority_score,
        "ai_priority_enabled": ai_enabled
    }


@router.post("/predict/{request_id}")
def predict_request(request_id: int, db: Session = Depends(get_db)):
    """Forces an online prediction for the specified maintenance request."""
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == request_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Maintenance request {request_id} not found")

    sec = db.query(RailwaySection).filter(RailwaySection.id == job.section_id).first() if job.section_id else None
    sec_ctx = {"trains_per_day": getattr(sec, "trains_per_day", 55), "utilization_pct": getattr(sec, "utilization_pct", 68.0)}

    res = risk_predictor.predict(job_data=job, section_context=sec_ctx, db_session=db)

    ai_enabled, ml_weight = PriorityEngine.get_ai_config(db)
    det_score = job.priority_score or 50.0

    if res.ml_risk_score is not None:
        job.ml_risk_score = res.ml_risk_score
        job.ml_risk_class = res.risk_class
        job.ml_model_version = res.model_version
        job.ml_explanation = res.top_contributing_factors
        job.ai_assisted_priority_score = round(
            (1.0 - ml_weight) * det_score + ml_weight * res.ml_risk_score, 1
        ) if ai_enabled else det_score
        db.commit()

    return res.to_dict()


@router.get("/explanation/{request_id}")
def get_explanation(request_id: int, db: Session = Depends(get_db)):
    """
    Returns explainable AI breakdown and contributing factors for a maintenance demand.
    """
    job = db.query(MaintenanceJob).filter(MaintenanceJob.id == request_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Maintenance request {request_id} not found")

    ai_enabled, ml_weight = PriorityEngine.get_ai_config(db)
    det_score = job.priority_score or 50.0

    # Retrieve cached explanation or predict
    if job.ml_explanation and job.ml_risk_score is not None:
        factors = job.ml_explanation
        risk_score = job.ml_risk_score
        risk_class = job.ml_risk_class or classify_risk(risk_score)
    else:
        sec = db.query(RailwaySection).filter(RailwaySection.id == job.section_id).first() if job.section_id else None
        sec_ctx = {"trains_per_day": getattr(sec, "trains_per_day", 55), "utilization_pct": getattr(sec, "utilization_pct", 68.0)}
        res = risk_predictor.predict(job_data=job, section_context=sec_ctx, db_session=db)
        factors = res.top_contributing_factors
        risk_score = res.ml_risk_score
        risk_class = res.risk_class

    ai_assisted_score = round((1.0 - ml_weight) * det_score + ml_weight * (risk_score or det_score), 1) if ai_enabled else det_score

    return {
        "job_code": job.job_code,
        "work_type": job.work_type,
        "model_version": MODEL_VERSION,
        "ml_risk_score": risk_score,
        "risk_class": risk_class,
        "data_source": DATA_SOURCE,
        "deterministic_priority": round(det_score, 1),
        "ai_assisted_priority": ai_assisted_score,
        "ai_priority_enabled": ai_enabled,
        "ml_risk_weight": ml_weight,
        "formula_breakdown": (
            f"{det_score:.1f} * {(1.0 - ml_weight)*100:.0f}% (Deterministic) + "
            f"{(risk_score or 0):.1f} * {ml_weight*100:.0f}% (AI Risk) = {ai_assisted_score:.1f}"
        ) if ai_enabled else f"100% Deterministic: {det_score:.1f}",
        "top_contributing_factors": factors,
        "disclaimer": (
            "Advisory AI Predicted Maintenance Risk. Not an official Indian Railways "
            "safety score. Official safety decisions require certified human planner review."
        )
    }
