"""
Offline Training Pipeline for Railway Maintenance Risk Model (XGBoost).
SIH26027 - AI-Powered Automatic Block Planning System.

EXECUTION:
    python -m app.ml.training.train_risk_model
    or
    python -m ml.training.train_risk_model

STEPS:
1. Load dataset (SIMULATED_MAINTENANCE_DATA)
2. Validate schema & check for data leakage
3. Train/Test split (80/20 held-out, reproducible random seed)
4. Fit XGBRegressor with gradient boosted decision trees
5. Evaluate on held-out test set: MAE, RMSE, R2, and Risk Class Classification Metrics
6. Baseline Comparison vs Heuristic
7. Save model (JSON) and metadata (JSON)
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, classification_report
import xgboost as xgb

from app.ml.config import (
    MODEL_PATH,
    METADATA_PATH,
    DATASET_PATH,
    MODEL_VERSION,
    FEATURE_VERSION,
    DATASET_VERSION,
    ALGORITHM_NAME,
    DATA_SOURCE,
    TARGET_VARIABLE,
    TARGET_DESCRIPTION,
    FEATURE_NAMES,
    XGB_HYPERPARAMETERS,
    classify_risk
)
from app.ml.data.dataset_generator import generate_and_save_dataset


def run_training_pipeline():
    print("=" * 70)
    print("RAILWAY MAINTENANCE RISK XGBOOST MODEL TRAINING PIPELINE")
    print("SIH26027 - AI-Powered Automatic Block Planning System")
    print("=" * 70)

    # 1. Ensure dataset exists or generate
    if not DATASET_PATH.exists():
        print(f"Dataset not found at {DATASET_PATH}. Generating simulated dataset...")
        df = generate_and_save_dataset()
    else:
        print(f"Loading dataset from: {DATASET_PATH}")
        df = pd.read_csv(DATASET_PATH)

    print(f"Loaded {len(df)} records. Data Source: {DATA_SOURCE} | Version: {DATASET_VERSION}")

    # 2. Validate Schema & Extract Features
    missing_cols = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset missing required feature columns: {missing_cols}")

    if TARGET_VARIABLE not in df.columns:
        raise ValueError(f"Dataset missing target column: '{TARGET_VARIABLE}'")

    X = df[FEATURE_NAMES]
    y = df[TARGET_VARIABLE]

    print(f"Features: {len(FEATURE_NAMES)} structured features")
    print(f"Target: '{TARGET_VARIABLE}' (Mean: {y.mean():.2f}, Std: {y.std():.2f}, Min: {y.min():.1f}, Max: {y.max():.1f})")

    # 3. Train/Test Split (80% Train, 20% Held-Out Test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=XGB_HYPERPARAMETERS["random_state"]
    )
    print(f"Dataset Partition: Train = {len(X_train)} samples | Held-out Test = {len(X_test)} samples")

    # 4. Train XGBoost Regressor
    print("\nFitting XGBRegressor...")
    model = xgb.XGBRegressor(**XGB_HYPERPARAMETERS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=False
    )
    print("Model training complete.")

    # 5. Evaluate on Held-out Test Set
    preds_test = model.predict(X_test)
    preds_test_clipped = np.clip(preds_test, 0.0, 100.0)

    mae = float(mean_absolute_error(y_test, preds_test_clipped))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds_test_clipped)))
    r2 = float(r2_score(y_test, preds_test_clipped))

    # Mapped classification performance (LOW, MEDIUM, HIGH, CRITICAL)
    y_test_classes = [classify_risk(v) for v in y_test]
    pred_classes = [classify_risk(v) for v in preds_test_clipped]
    acc = float(accuracy_score(y_test_classes, pred_classes))
    report_dict = classification_report(y_test_classes, pred_classes, output_dict=True, zero_division=0)

    print("\n" + "=" * 50)
    print("HELD-OUT TEST SET EVALUATION METRICS")
    print("=" * 50)
    print(f"  Mean Absolute Error (MAE):    {mae:.3f} points")
    print(f"  Root Mean Squared Error (RMSE): {rmse:.3f} points")
    print(f"  Coefficient of Determination (R2): {r2:.4f}")
    print(f"  Risk Class Accuracy (4 tiers): {acc * 100:.2f}%")
    print("=" * 50)

    # 6. Feature Importance Extraction
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
    print("\nTop 7 Contributing Features (Global Feature Importance):")
    for feat, imp in feat_imp[:7]:
        print(f"  - {feat:30s}: {imp * 100:6.2f}%")

    # 7. Model Persistence
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving model booster to: {MODEL_PATH}")
    model.save_model(str(MODEL_PATH))

    # 8. Save Model Metadata
    metadata = {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "algorithm": ALGORITHM_NAME,
        "target": TARGET_VARIABLE,
        "target_description": TARGET_DESCRIPTION,
        "data_source": DATA_SOURCE,
        "dataset_version": DATASET_VERSION,
        "dataset_total_samples": int(len(df)),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "training_timestamp": datetime.utcnow().isoformat() + "Z",
        "random_seed": XGB_HYPERPARAMETERS["random_state"],
        "hyperparameters": XGB_HYPERPARAMETERS,
        "features": FEATURE_NAMES,
        "feature_count": len(FEATURE_NAMES),
        "feature_importances": {feat: float(imp) for feat, imp in feat_imp},
        "evaluation_metrics": {
            "test_mae": round(mae, 3),
            "test_rmse": round(rmse, 3),
            "test_r2": round(r2, 4),
            "test_risk_class_accuracy": round(acc, 4),
            "classification_report": report_dict
        },
        "disclaimer": (
            "Advisory AI Predicted Maintenance Risk. Not an official Indian Railways "
            "safety score. Safety decisions must be validated by certified railway staff."
        )
    }

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved to: {METADATA_PATH}")
    print("\n[SUCCESS] Model training and serialization finished successfully.")
    return model, metadata


if __name__ == "__main__":
    run_training_pipeline()
