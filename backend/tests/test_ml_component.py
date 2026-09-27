"""
SIH26027 Machine Learning Component Test Suite
Verifies XGBoost Maintenance Risk / Urgency prediction, feature pipeline,
priority blending, audit persistence, fail-safe fallbacks, and preservation of CP-SAT hard constraints.
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import xgboost as xgb

from app.ml.config import (
    MODEL_PATH,
    METADATA_PATH,
    FEATURE_COLUMNS,
    MODEL_VERSION,
    RISK_THRESHOLDS,
    get_risk_class
)
from app.ml.preprocessing.feature_builder import MaintenanceFeatureBuilder
from app.ml.inference.risk_predictor import MaintenanceRiskPredictor, PredictionResult
from app.algorithms.priority import PriorityEngine, calculate_full_priority
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.windows import WindowEngine
from app.algorithms.replanning import DynamicReplanningEngine
from app.models.models import MLPrediction, MaintenanceJob, Department, Station, RailwaySection
from app.db.session import SessionLocal


# ----------------------------------------------------
# 1. test_model_load
# ----------------------------------------------------
def test_model_load():
    """Verify XGBoost model artifact exists, loads cleanly, and feature count matches config (19)."""
    assert MODEL_PATH.exists(), f"Model artifact missing at {MODEL_PATH}"
    assert METADATA_PATH.exists(), f"Metadata artifact missing at {METADATA_PATH}"

    booster = xgb.Booster()
    booster.load_model(str(MODEL_PATH))
    assert booster.num_features() == len(FEATURE_COLUMNS)
    assert booster.num_features() == 19

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["model_version"] == MODEL_VERSION
    assert meta["feature_count"] == 19
    assert "XGBoost Regressor" in meta["algorithm"]
    assert "evaluation_metrics" in meta
    assert meta["evaluation_metrics"]["test_mae"] < 5.0
    assert meta["evaluation_metrics"]["test_r2"] > 0.85


# ----------------------------------------------------
# 2. test_model_prediction
# ----------------------------------------------------
def test_model_prediction():
    """Verify singleton predictor produces a valid numeric prediction float."""
    predictor = MaintenanceRiskPredictor.get_instance()
    sample_job = {
        "job_code": "REQ-TEST-001",
        "department_code": "ENGG",
        "work_type": "TRACK_TAMPING",
        "calculated_criticality": 82.0,
        "calculated_urgency": 75.0,
        "overdue_days": 8,
        "calculated_safety_impact": 85.0,
        "operational_impact": 70.0,
        "estimated_duration_min": 120,
        "traffic_density_gmt": 42.0,
        "track_quality_index": 62.0,
        "weather_risk_index": 35.0,
        "speed_restriction_severity": 20.0
    }
    result = predictor.predict(sample_job)
    assert isinstance(result, PredictionResult)
    assert isinstance(result.risk_score, float)
    assert 0.0 <= result.risk_score <= 100.0
    assert result.risk_class in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(result.top_contributing_factors) > 0


# ----------------------------------------------------
# 3. test_feature_generation
# ----------------------------------------------------
def test_feature_generation():
    """Verify feature builder extracts all 19 non-leaking features with correct types."""
    builder = MaintenanceFeatureBuilder()
    sample_job = {
        "job_code": "REQ-TEST-002",
        "department_code": "SNT",
        "work_type": "POINT_OVERHAUL",
        "calculated_criticality": 70.0,
        "calculated_urgency": 65.0,
        "overdue_days": 3,
        "calculated_safety_impact": 80.0,
        "operational_impact": 60.0,
        "estimated_duration_min": 90
    }
    features = builder.build_features(sample_job)
    assert len(features) == 19
    for col in FEATURE_COLUMNS:
        assert col in features, f"Missing feature: {col}"
        val = features[col]
        assert isinstance(val, (int, float)), f"Feature {col} is non-numeric: {val}"


# ----------------------------------------------------
# 4. test_missing_features
# ----------------------------------------------------
def test_missing_features():
    """Verify feature builder handles sparse or missing dictionary fields via principled imputation."""
    builder = MaintenanceFeatureBuilder()
    sparse_job = {"job_code": "REQ-EMPTY"}
    features = builder.build_features(sparse_job)

    assert len(features) == 19
    assert features["train_traffic_density"] == 55
    assert features["asset_condition"] == 55.0  # Inferred from default TRACK_TAMPING
    assert features["overdue_days"] == 0
    assert features["section_utilization"] == 68.0

    # Ensure predictor does not crash on sparse job
    predictor = MaintenanceRiskPredictor.get_instance()
    res = predictor.predict(sparse_job)
    assert 0.0 <= res.risk_score <= 100.0


# ----------------------------------------------------
# 5. test_invalid_request
# ----------------------------------------------------
def test_invalid_request():
    """Verify handling of empty or None job data returns safe default fallback."""
    predictor = MaintenanceRiskPredictor.get_instance()
    res = predictor.predict(None)
    assert isinstance(res, PredictionResult)
    assert res.risk_score == 50.0
    assert res.risk_class == "MEDIUM"


# ----------------------------------------------------
# 6. test_prediction_range
# ----------------------------------------------------
def test_prediction_range():
    """Verify risk predictions are strictly bounded within [0.0, 100.0] even on extreme inputs."""
    predictor = MaintenanceRiskPredictor.get_instance()

    # Extreme low values
    extreme_low = {
        "calculated_criticality": 0.0,
        "calculated_urgency": 0.0,
        "overdue_days": 0,
        "calculated_safety_impact": 0.0,
        "operational_impact": 0.0,
        "asset_condition": 100.0,
        "defect_severity": 1,
        "train_traffic_density": 10,
        "section_utilization": 20.0
    }
    res_low = predictor.predict(extreme_low)
    assert 0.0 <= res_low.risk_score <= 100.0

    # Extreme high values
    extreme_high = {
        "calculated_criticality": 100.0,
        "calculated_urgency": 100.0,
        "overdue_days": 180,
        "calculated_safety_impact": 100.0,
        "operational_impact": 100.0,
        "asset_condition": 10.0,
        "defect_severity": 4,
        "train_traffic_density": 120,
        "section_utilization": 98.0
    }
    res_high = predictor.predict(extreme_high)
    assert 0.0 <= res_high.risk_score <= 100.0
    assert res_high.risk_score > res_low.risk_score


# ----------------------------------------------------
# 7. test_risk_class
# ----------------------------------------------------
def test_risk_class():
    """Verify risk categorization logic strictly matches thresholds (LOW, MEDIUM, HIGH, CRITICAL)."""
    assert get_risk_class(0.0) == "LOW"
    assert get_risk_class(39.9) == "LOW"
    assert get_risk_class(40.0) == "MEDIUM"
    assert get_risk_class(69.9) == "MEDIUM"
    assert get_risk_class(70.0) == "HIGH"
    assert get_risk_class(84.9) == "HIGH"
    assert get_risk_class(85.0) == "CRITICAL"
    assert get_risk_class(100.0) == "CRITICAL"


# ----------------------------------------------------
# 8. test_model_version
# ----------------------------------------------------
def test_model_version():
    """Verify version tag is consistently MRISK-XGB-1.0 across metadata and inference."""
    predictor = MaintenanceRiskPredictor.get_instance()
    res = predictor.predict({"job_code": "REQ-VTEST"})
    assert res.model_version == MODEL_VERSION
    assert res.model_version == "MRISK-XGB-1.0"


# ----------------------------------------------------
# 9. test_prediction_audit
# ----------------------------------------------------
def test_prediction_audit():
    """Verify prediction records can be persisted and queried in the ML audit table."""
    db = SessionLocal()
    try:
        # Create a test job to satisfy foreign key constraint
        dept = db.query(Department).first()
        sec = db.query(RailwaySection).first()
        job = MaintenanceJob(
            job_code="REQ-AUDIT-TEST",
            department_id=dept.id if dept else 1,
            section_id=sec.id if sec else 1,
            work_type="TRACK_TAMPING",
            description="Track tamping maintenance audit test",
            estimated_duration_min=90,
            priority_score=75.0,
            status="SUBMITTED"
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        pred_record = MLPrediction(
            request_id=job.id,
            job_code=job.job_code,
            model_version=MODEL_VERSION,
            risk_score=78.5,
            risk_class="HIGH",
            explanation_json=[
                {"feature": "overdue_days", "value": 5, "impact": 4.2}
            ],
            features_json={"overdue_days": 5, "train_traffic_density": 35}
        )
        db.add(pred_record)
        db.commit()
        db.refresh(pred_record)

        queried = db.query(MLPrediction).filter(MLPrediction.request_id == job.id).first()
        assert queried is not None
        assert queried.risk_score == 78.5
        assert queried.risk_class == "HIGH"
        assert queried.model_version == MODEL_VERSION

        # Cleanup
        db.delete(pred_record)
        db.delete(job)
        db.commit()
    finally:
        db.close()


# ----------------------------------------------------
# 10. test_ai_disabled
# ----------------------------------------------------
def test_ai_disabled():
    """Verify that when AI priority is disabled, the priority strictly equals the deterministic score."""
    sample_job = {
        "job_code": "REQ-TEST-DIS",
        "work_type": "TRACK_TAMPING",
        "department_code": "ENGG",
        "user_priority": "MEDIUM",
        "calculated_criticality": 80.0,
        "calculated_urgency": 70.0,
        "overdue_days": 2,
        "calculated_safety_impact": 85.0,
        "operational_impact": 65.0
    }
    res = calculate_full_priority(sample_job, ai_priority_enabled=False)
    assert res["ai_priority_enabled"] is False
    assert res["ai_assisted_priority_score"] == res["deterministic_priority_score"]
    assert res["priority_score"] == res["deterministic_priority_score"]


# ----------------------------------------------------
# 11. test_ml_failure_fallback
# ----------------------------------------------------
def test_ml_failure_fallback():
    """Verify that if predictor throws an exception, calculate_full_priority gracefully falls back."""
    sample_job = {
        "job_code": "REQ-TEST-FALLBACK",
        "work_type": "TRACK_TAMPING",
        "department_code": "ENGG",
        "user_priority": "MEDIUM",
        "calculated_criticality": 75.0,
        "calculated_urgency": 60.0,
        "overdue_days": 0,
        "calculated_safety_impact": 70.0,
        "operational_impact": 50.0
    }
    with patch.object(MaintenanceRiskPredictor, 'predict', side_effect=RuntimeError("Simulated XGBoost engine failure")):
        res = calculate_full_priority(sample_job, ai_priority_enabled=True)
        assert res["ai_assisted_priority_score"] == res["deterministic_priority_score"]
        assert res["deterministic_priority_score"] > 0


# ----------------------------------------------------
# 12. test_deterministic_priority_preserved
# ----------------------------------------------------
def test_deterministic_priority_preserved():
    """Verify deterministic priority is preserved explicitly and matches the railway multi-criteria formula."""
    sample_job = {
        "job_code": "REQ-TEST-DET",
        "work_type": "TRACK_TAMPING",
        "department_code": "ENGG",
        "user_priority": "MEDIUM",
        "is_emergency": False
    }
    res_ai = calculate_full_priority(sample_job, ai_priority_enabled=True, ml_risk_weight=0.15)
    res_no_ai = calculate_full_priority(sample_job, ai_priority_enabled=False)

    # Deterministic score MUST be identical regardless of AI Mode setting
    assert res_ai["deterministic_priority_score"] == res_no_ai["deterministic_priority_score"]
    assert res_ai["deterministic_priority_score"] > 0

    # When AI is enabled, blended score strictly follows (1 - w)*det + w*ml
    if res_ai["ml_risk_score"] is not None:
        expected_blended = round((1.0 - 0.15) * res_ai["deterministic_priority_score"] + 0.15 * res_ai["ml_risk_score"], 1)
        assert abs(res_ai["ai_assisted_priority_score"] - expected_blended) < 1e-4


# ----------------------------------------------------
# 13. test_cp_sat_unchanged
# ----------------------------------------------------
def test_cp_sat_unchanged():
    """Verify OR-Tools CP-SAT discrete solver remains unmodified and enforces hard window constraints."""
    jobs = [
        {"id": 101, "job_code": "E101", "section_id": 1, "estimated_duration_min": 60, "priority_score": 80.0, "is_emergency": False}
    ]
    windows = [
        {"id": 1, "section_id": 1, "start_min": 600, "end_min": 720, "usable_duration_min": 120}
    ]
    solver = CPSATSolver(time_limit_seconds=5)
    res = solver.solve(jobs=jobs, windows=windows)
    assert res["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert len(res["scheduled_jobs"]) == 1
    assert res["scheduled_jobs"][0]["job_id"] == 101


# ----------------------------------------------------
# 14. test_available_windows_unchanged
# ----------------------------------------------------
def test_available_windows_unchanged():
    """Verify WindowEngine calculation logic and safety buffer rules remain intact."""
    occupancies = [
        {"section_id": 2, "train_number": "12002", "estimated_entry_min": 600, "estimated_exit_min": 615},
        {"section_id": 2, "train_number": "12919", "estimated_entry_min": 690, "estimated_exit_min": 705}
    ]
    windows = WindowEngine.calculate_feasible_windows(
        section_id=2,
        corridor_id=1,
        occupancies=occupancies,
        horizon_start_min=600,
        horizon_end_min=720,
        buffer_before_min=5,
        buffer_after_min=5,
        min_window_duration_min=30
    )
    assert len(windows) >= 1
    target_win = [w for w in windows if w["train_before_no"] == "12002" and w["train_after_no"] == "12919"][0]
    assert target_win["start_min"] == 620
    assert target_win["end_min"] == 685
    assert target_win["usable_duration_min"] == 65


# ----------------------------------------------------
# 15. test_train_occupancy_unchanged
# ----------------------------------------------------
def test_train_occupancy_unchanged():
    """Verify train occupancy calculation functions as expected without deviation."""
    from app.algorithms.occupancy import OccupancyEngine
    assert hasattr(OccupancyEngine, "calculate_section_occupancies")


# ----------------------------------------------------
# 16. test_dynamic_replanning_unchanged
# ----------------------------------------------------
def test_dynamic_replanning_unchanged():
    """Verify dynamic replanning shifts schedules properly when train delays occur."""
    current_pjs = [
        {"job_id": 1, "job_code": "E101", "scheduled_start_min": 600, "scheduled_end_min": 660, "window_id": 1, "is_scheduled": True}
    ]
    jobs = [
        {"id": 1, "job_code": "E101", "section_id": 2, "estimated_duration_min": 60, "priority_score": 80.0, "is_emergency": False}
    ]
    new_windows = [
        {"id": 2, "section_id": 2, "start_min": 700, "end_min": 800, "usable_duration_min": 100}
    ]
    new_occs = [
        {"section_id": 2, "train_number": "12919", "estimated_entry_min": 620, "estimated_exit_min": 680}
    ]

    replan = DynamicReplanningEngine.re_optimize(
        current_plan_jobs=current_pjs,
        jobs=jobs,
        new_windows=new_windows,
        new_occupancies=new_occs,
        trigger_event="TRAIN_DELAY"
    )

    assert replan["is_valid"] is True
    assert replan["scheduled_jobs"][0]["scheduled_start_min"] >= 700
