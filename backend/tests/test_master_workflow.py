import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

client = TestClient(app)


def test_get_departments_list():
    """Verify master departments endpoint returns active departments."""
    response = client.get("/api/departments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    codes = [d["code"] for d in data]
    assert "ENGG" in codes
    assert "SNT" in codes
    assert "TRD" in codes
    assert any(c in ["OPTG", "OPERATIONS"] for c in codes)


def test_direct_role_based_logins():
    """Verify all 4 authorized profiles log in directly without requiring department selection."""
    profiles = [
        {"username": "planner", "password": "planner123", "expected_role": "RAILWAY_PLANNER", "expected_dept": "OPERATIONS"},
        {"username": "engg_user", "password": "engg123", "expected_role": "TRACK_ENGINEERING", "expected_dept": "ENGG"},
        {"username": "snt_user", "password": "snt123", "expected_role": "SIGNAL_TELECOM", "expected_dept": "SNT"},
        {"username": "trd_user", "password": "trd123", "expected_role": "TRACTION_DISTRIBUTION", "expected_dept": "TRD"}
    ]

    for p in profiles:
        res = client.post("/api/auth/login", json={
            "username": p["username"],
            "password": p["password"]
        })
        assert res.status_code == 200, f"Login failed for {p['username']}: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["user"]["role"].upper() == p["expected_role"]
        assert data["user"]["department_code"] == p["expected_dept"]


def test_login_with_department_validation():
    """Verify department login matches user role and returns valid token."""
    # 1. Valid login with matching department
    res = client.post("/api/auth/login", json={
        "username": "engg_user",
        "password": "engg123",
        "department": "Engineering"
    })
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["user"]["role"].upper() in ["TRACK_ENGINEERING", "DEPARTMENT_USER"]
    assert body["user"]["department_code"] == "ENGG"

    # 2. Login with mismatched department for role
    res_mismatch = client.post("/api/auth/login", json={
        "username": "engg_user",
        "password": "engg123",
        "department": "TRD / OHE"
    })
    assert res_mismatch.status_code == 403
    assert "Authorization Mismatch" in res_mismatch.json()["detail"] or "Department mismatch" in res_mismatch.json()["detail"]

    # 3. Planner can access Operations/Planning department
    res_planner = client.post("/api/auth/login", json={
        "username": "planner",
        "password": "planner123",
        "department": "Railway Operations & Traffic Planning"
    })
    assert res_planner.status_code == 200
    assert res_planner.json()["user"]["role"].upper() == "RAILWAY_PLANNER"


def test_station_resolve_and_validation():
    """Verify station resolution converts lowercase to uppercase and fetches metadata."""
    # Resolve 'mas' -> 'MAS'
    res = client.get("/api/railway/stations/resolve?code=mas")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == "MAS"
    assert "Chennai Central" in data["name"]
    assert data["latitude"] is not None

    # Resolve 'tpj' -> 'TPJ'
    res_tpj = client.get("/api/railway/stations/resolve?code=tpj")
    assert res_tpj.status_code == 200
    assert res_tpj.json()["code"] == "TPJ"


def test_route_validation():
    """Verify corridor route checking and same-station rejection."""
    # 1. Identical start and end station rejected
    res_same = client.get("/api/railway/routes/validate?start_code=MAS&end_code=MAS")
    assert res_same.status_code == 200
    data_same = res_same.json()
    assert data_same["valid"] is False
    assert "different" in data_same["message"].lower() or "identical" in data_same["message"].lower()

    # 2. Valid Tamil Nadu route MAS -> TPJ
    res_valid = client.get("/api/railway/routes/validate?start_code=MAS&end_code=TPJ")
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["valid"] is True
    assert data_valid["corridor_code"] is not None


def test_job_submission_with_automated_priority():
    """Verify department user cannot fake priority; system calculates Criticality, Safety, Urgency, Score."""
    # Get auth token for engg_user
    login_res = client.post("/api/auth/login", json={
        "username": "engg_user",
        "password": "engg123",
        "department": "Engineering"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    due = (datetime.utcnow() + timedelta(days=2)).isoformat()

    payload = {
        "work_type": "TRACK_TAMPING",
        "description": "Routine track tamping between MAS and TPJ",
        "start_station_code": "mas",
        "end_station_code": "tpj",
        "user_priority": "HIGH",
        "due_date": due,
        "estimated_duration_min": 90,
        "is_emergency": False,
        "resource_ids": []
    }

    create_res = client.post("/api/maintenance/requests", json=payload, headers=headers)
    assert create_res.status_code == 200
    job = create_res.json()

    assert job["start_station_code"] == "MAS"
    assert job["end_station_code"] == "TPJ"
    assert job["calculated_criticality"] is not None
    assert job["calculated_safety_impact"] is not None
    assert job["calculated_urgency"] is not None
    assert job["priority_score"] is not None
    assert job["criticality_label"] in ["LOW", "MEDIUM", "HIGH"]
    assert job["safety_impact_label"] in ["LOW", "MEDIUM", "HIGH"]
    assert job["urgency_label"] in ["LOW", "MEDIUM", "HIGH"]
    assert job["priority_explanation"] is not None
    assert "factor_contributions" in job["priority_explanation"]

    job_id = job["id"]

    # Test "Why This Priority?" explanation endpoint
    exp_res = client.get(f"/api/maintenance/requests/{job_id}/explanation", headers=headers)
    assert exp_res.status_code == 200
    exp = exp_res.json()
    assert "criticality" in exp
    assert "safety_impact" in exp
    assert "urgency" in exp
    assert "factor_contributions" in exp
    assert "disclaimer" in exp

    # Test Planner Override
    # 1. Non-planner attempt should fail with 403
    override_fail = client.post(
        f"/api/maintenance/requests/{job_id}/override",
        json={"override_score": 92.5, "reason": "Urgent track inspection before VIP train"},
        headers=headers
    )
    assert override_fail.status_code == 403

    # 2. Planner override succeeds
    planner_login = client.post("/api/auth/login", json={
        "username": "planner",
        "password": "planner123",
        "department": "Railway Operations & Traffic Planning"
    })
    planner_token = planner_login.json()["access_token"]
    planner_headers = {"Authorization": f"Bearer {planner_token}"}

    override_res = client.post(
        f"/api/maintenance/requests/{job_id}/override",
        json={"override_score": 92.5, "reason": "Operational imperative for upcoming freight corridor"},
        headers=planner_headers
    )
    assert override_res.status_code == 200
    updated = override_res.json()
    assert updated["priority_score"] == 92.5
    assert updated["planner_override_score"] == 92.5
    assert "Operational imperative" in updated["planner_override_reason"]
