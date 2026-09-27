"""
Test Command for ML Inference.
SIH26027 Section 44:
    python -m ml.inference.test_prediction
    or
    python -m app.ml.inference.test_prediction

Loads sample railway maintenance requests and tests online inference,
risk classification, and TreeSHAP contributing factors.
"""

from app.ml.inference.risk_predictor import risk_predictor


def run_test_prediction():
    print("=" * 65)
    print("TESTING ONLINE XGBOOST MAINTENANCE RISK INFERENCE")
    print("=" * 65)

    sample_requests = [
        {
            "id": 101,
            "job_code": "REQ-101",
            "work_type": "RAIL_REPLACEMENT",
            "department_code": "ENGG",
            "user_priority": "HIGH",
            "asset_condition_score": 25.0,
            "calculated_criticality": 88.0,
            "calculated_safety_impact": 85.0,
            "due_date": "2026-09-10T00:00:00Z",  # Overdue
            "overdue_days": 14,
            "estimated_duration_min": 180,
            "is_emergency": False,
            "section_train_density": 85,
            "section_utilization": 88.5
        },
        {
            "id": 102,
            "job_code": "REQ-102",
            "work_type": "TRACK_TAMPING",
            "department_code": "ENGG",
            "user_priority": "MEDIUM",
            "asset_condition_score": 58.0,
            "calculated_criticality": 60.0,
            "calculated_safety_impact": 55.0,
            "due_date": "2026-09-28T00:00:00Z",  # Due in future
            "overdue_days": 0,
            "estimated_duration_min": 120,
            "is_emergency": False,
            "section_train_density": 50,
            "section_utilization": 60.0
        },
        {
            "id": 103,
            "job_code": "REQ-103",
            "work_type": "OHE_INSPECTION",
            "department_code": "TRD",
            "user_priority": "LOW",
            "asset_condition_score": 85.0,
            "calculated_criticality": 40.0,
            "calculated_safety_impact": 35.0,
            "due_date": "2026-10-15T00:00:00Z",  # Plenty of time
            "overdue_days": 0,
            "estimated_duration_min": 90,
            "is_emergency": False,
            "section_train_density": 35,
            "section_utilization": 42.0
        }
    ]

    for req in sample_requests:
        res = risk_predictor.predict(req)
        print(f"\nRequest: {req['job_code']} ({req['work_type']}) - Priority: {req['user_priority']}")
        print(f"  Status:               {res.prediction_status}")
        print(f"  AI Risk Score:        {res.ml_risk_score} / 100")
        print(f"  Risk Class:           {res.risk_class}")
        print(f"  Model Version:        {res.model_version}")
        print(f"  Data Source:          {res.data_source}")
        print("  Top Contributing Factors:")
        for factor in res.top_contributing_factors[:4]:
            print(f"    - {factor['label']}: {factor['value']} ({factor['impact_label']} -> {factor['direction']})")

    print("\n" + "=" * 65)
    print("[SUCCESS] All test predictions executed successfully.")


if __name__ == "__main__":
    run_test_prediction()
