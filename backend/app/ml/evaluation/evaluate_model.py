"""
Model Evaluation and Baseline Comparison Script.
SIH26027 - AI-Powered Automatic Block Planning System.

Compares:
1. Trained XGBoost Model (MRISK-XGB-1.0)
2. Baseline Deterministic Heuristic

Metrics:
- Regression: MAE, RMSE, R2
- Classification: Accuracy, Precision, Recall, F1 (macro & weighted)
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)
import xgboost as xgb

from app.ml.config import (
    MODEL_PATH,
    DATASET_PATH,
    EVALUATION_REPORT_PATH,
    MODEL_VERSION,
    FEATURE_NAMES,
    TARGET_VARIABLE,
    DATA_SOURCE,
    XGB_HYPERPARAMETERS,
    classify_risk
)


def evaluate_model_and_compare_baseline():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}. Run training first.")
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset file not found at: {DATASET_PATH}.")

    print("Loading test dataset and trained XGBoost booster...")
    df = pd.read_csv(DATASET_PATH)

    X = df[FEATURE_NAMES]
    y = df[TARGET_VARIABLE]

    # Recreate the exact held-out test split (20%)
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.20, random_state=XGB_HYPERPARAMETERS["random_state"]
    )

    # 1. Load Trained XGBoost Model
    model = xgb.XGBRegressor()
    model.load_model(str(MODEL_PATH))

    # Predict using XGBoost
    xgb_preds = np.clip(model.predict(X_test), 0.0, 100.0)

    # 2. Baseline Model (Deterministic Linear Multi-Factor Heuristic)
    # Uses traditional weighted sum: 0.35*condition_inv + 0.25*severity + 0.20*overdue + 0.20*operational
    baseline_preds = []
    for idx, row in X_test.iterrows():
        cond_deficit = max(0.0, 100.0 - row["asset_condition"])
        sev_score = row["defect_severity"] * 25.0
        overdue_score = min(100.0, max(0.0, row["overdue_days"] * 8.0))
        op_score = row["operational_importance"]
        b_val = 0.30 * cond_deficit + 0.25 * sev_score + 0.25 * overdue_score + 0.20 * op_score
        baseline_preds.append(np.clip(b_val, 0.0, 100.0))
    baseline_preds = np.array(baseline_preds)

    # 3. Calculate XGBoost Metrics
    xgb_mae = float(mean_absolute_error(y_test, xgb_preds))
    xgb_rmse = float(np.sqrt(mean_squared_error(y_test, xgb_preds)))
    xgb_r2 = float(r2_score(y_test, xgb_preds))

    y_test_classes = [classify_risk(v) for v in y_test]
    xgb_classes = [classify_risk(v) for v in xgb_preds]
    xgb_acc = float(accuracy_score(y_test_classes, xgb_classes))
    xgb_f1_macro = float(f1_score(y_test_classes, xgb_classes, average="macro", zero_division=0))
    xgb_f1_weighted = float(f1_score(y_test_classes, xgb_classes, average="weighted", zero_division=0))

    # 4. Calculate Baseline Metrics
    base_mae = float(mean_absolute_error(y_test, baseline_preds))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))
    base_r2 = float(r2_score(y_test, baseline_preds))

    base_classes = [classify_risk(v) for v in baseline_preds]
    base_acc = float(accuracy_score(y_test_classes, base_classes))
    base_f1_macro = float(f1_score(y_test_classes, base_classes, average="macro", zero_division=0))
    base_f1_weighted = float(f1_score(y_test_classes, base_classes, average="weighted", zero_division=0))

    # 5. Print Comparison Summary
    print("\n" + "=" * 65)
    print("MODEL EVALUATION & BASELINE COMPARISON REPORT")
    print("=" * 65)
    print(f"{'Metric':<28} | {'XGBoost ML Model':<16} | {'Deterministic Baseline':<16}")
    print("-" * 65)
    print(f"{'MAE (points lower=better)':<28} | {xgb_mae:<16.3f} | {base_mae:<16.3f}")
    print(f"{'RMSE (points lower=better)':<28} | {xgb_rmse:<16.3f} | {base_rmse:<16.3f}")
    print(f"{'R-squared (R2 higher=better)':<28} | {xgb_r2:<16.4f} | {base_r2:<16.4f}")
    print(f"{'Tier Accuracy (4 tiers)':<28} | {xgb_acc * 100:<15.2f}% | {base_acc * 100:<15.2f}%")
    print(f"{'Macro F1-Score':<28} | {xgb_f1_macro:<16.4f} | {base_f1_macro:<16.4f}")
    print(f"{'Weighted F1-Score':<28} | {xgb_f1_weighted:<16.4f} | {base_f1_weighted:<16.4f}")
    print("=" * 65)

    mae_improvement = ((base_mae - xgb_mae) / base_mae) * 100.0
    rmse_improvement = ((base_rmse - xgb_rmse) / base_rmse) * 100.0
    print(f"XGBoost MAE Error Reduction vs Heuristic Baseline: {mae_improvement:.2f}%")
    print(f"XGBoost RMSE Error Reduction vs Heuristic Baseline: {rmse_improvement:.2f}%")

    report = {
        "model_version": MODEL_VERSION,
        "evaluation_timestamp": pd.Timestamp.now().isoformat() + "Z",
        "test_dataset_size": len(y_test),
        "data_source": DATA_SOURCE,
        "xgboost_model": {
            "mae": round(xgb_mae, 3),
            "rmse": round(xgb_rmse, 3),
            "r2": round(xgb_r2, 4),
            "accuracy": round(xgb_acc, 4),
            "macro_f1": round(xgb_f1_macro, 4),
            "weighted_f1": round(xgb_f1_weighted, 4)
        },
        "baseline_heuristic": {
            "mae": round(base_mae, 3),
            "rmse": round(base_rmse, 3),
            "r2": round(base_r2, 4),
            "accuracy": round(base_acc, 4),
            "macro_f1": round(base_f1_macro, 4),
            "weighted_f1": round(base_f1_weighted, 4)
        },
        "comparison": {
            "mae_reduction_percent": round(mae_improvement, 2),
            "rmse_reduction_percent": round(rmse_improvement, 2),
            "accuracy_gain_percent": round((xgb_acc - base_acc) * 100.0, 2)
        }
    }

    EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVALUATION_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Saved evaluation report to: {EVALUATION_REPORT_PATH}")
    return report


if __name__ == "__main__":
    evaluate_model_and_compare_baseline()
