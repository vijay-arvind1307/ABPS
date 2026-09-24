import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def get_token(username: str, password: str, department: str = None) -> str:
    payload = {"username": username, "password": password}
    if department:
        payload["department"] = department
    res = client.post("/api/auth/login", json=payload)
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def test_full_department_and_planner_lifecycle():
    """
    Validates end-to-end operational lifecycle:
    1. Department creates demand -> status = SUBMITTED
    2. Planner receives request and generates plan
    3. Planner approves plan -> associated job status becomes APPROVED
    4. Department receives notification
    5. Department accepts plan -> status becomes DEPARTMENT_ACCEPTED, execution_status = READY
    6. Field team starts execution -> status becomes IN_PROGRESS, actual_start_min recorded
    7. Field team updates progress (50%)
    8. Field team completes execution -> status becomes COMPLETED, variance calculated
    """
    engg_token = get_token("engg_user", "engg123", "Engineering")
    planner_token = get_token("planner", "planner123", "Railway Operations & Traffic Planning")

    engg_headers = {"Authorization": f"Bearer {engg_token}"}
    planner_headers = {"Authorization": f"Bearer {planner_token}"}

    # 1. Department creates demand
    job_code = f"TEST-LIFE-{int(datetime.utcnow().timestamp())}"
    due = (datetime.utcnow() + timedelta(days=2)).isoformat()
    create_res = client.post("/api/maintenance/requests", json={
        "job_code": job_code,
        "work_type": "TRACK_TAMPING",
        "description": "Lifecycle test track tamping MAS to TPJ",
        "start_station_code": "CVP",
        "end_station_code": "KDU",
        "user_priority": "HIGH",
        "due_date": due,
        "estimated_duration_min": 60,
        "preferred_start_min": 600,
        "is_emergency": False
    }, headers=engg_headers)
    assert create_res.status_code == 200
    job = create_res.json()
    job_id = job["id"]
    assert job["status"] == "SUBMITTED"

    # 2. Planner checks review packet
    rev_res = client.get(f"/api/planning/requests/{job_id}/planner-review", headers=planner_headers)
    assert rev_res.status_code == 200
    packet = rev_res.json()
    assert packet["job"]["job_code"] == job_code
    assert "priority_explanation" in packet

    # 3. Planner runs optimization
    opt_res = client.post("/api/planning/optimize", json={
        "strategy": "PLAN_A",
        "planning_horizon_hours": 24,
        "time_limit_seconds": 10,
        "enforce_locks": True
    }, headers=planner_headers)
    assert opt_res.status_code == 200, f"Optimize failed with {opt_res.status_code}: {opt_res.json()}"
    plan = opt_res.json()
    plan_id = plan["id"]

    # 4. Planner approves plan
    app_res = client.post(f"/api/planning/plans/{plan_id}/approve", json={
        "action": "APPROVE",
        "reason": "Authorized by Chief Section Controller"
    }, headers=planner_headers)
    assert app_res.status_code == 200

    # Verify job status transitioned to APPROVED
    check_job = client.get(f"/api/maintenance/requests/{job_id}", headers=engg_headers).json()
    assert check_job["status"] == "APPROVED"
    assert check_job["approved_at"] is not None

    # Verify department received notification
    notif_res = client.get("/api/notifications", headers=engg_headers)
    assert notif_res.status_code == 200
    notifs = notif_res.json()
    assert len(notifs) > 0
    assert any("Approved" in n["title"] or "approved" in n["message"].lower() for n in notifs)

    # 5. Department accepts plan
    accept_res = client.post(f"/api/planning/plans/{plan_id}/department-accept", json={
        "action": "ACCEPT",
        "remarks": "Senior Section Engineer accepted possession schedule"
    }, headers=engg_headers)
    assert accept_res.status_code == 200

    check_accepted = client.get(f"/api/maintenance/requests/{job_id}", headers=engg_headers).json()
    assert check_accepted["status"] == "DEPARTMENT_ACCEPTED"
    assert check_accepted["execution_status"] == "READY"

    # 6. Field crew starts execution
    start_res = client.post("/api/execution/start", json={
        "job_id": job_id,
        "actual_start_min": 610,
        "remarks": "Possession taken at 10:10 IST"
    }, headers=engg_headers)
    assert start_res.status_code == 200
    exec_rec = start_res.json()
    assert exec_rec["status"] == "IN_PROGRESS"
    assert exec_rec["actual_start_min"] == 610

    check_in_prog = client.get(f"/api/maintenance/requests/{job_id}", headers=engg_headers).json()
    assert check_in_prog["status"] == "IN_PROGRESS"
    assert check_in_prog["execution_status"] == "IN_PROGRESS"

    # 7. Update progress
    prog_res = client.post("/api/execution/progress", json={
        "job_id": job_id,
        "completion_pct": 50.0,
        "delay_min": 5,
        "remarks": "1 km tamping completed"
    }, headers=engg_headers)
    assert prog_res.status_code == 200
    assert prog_res.json()["completion_pct"] == 50.0

    # 8. Complete execution
    comp_res = client.post("/api/execution/complete", json={
        "job_id": job_id,
        "actual_end_min": 680,  # 70 minutes (610 to 680). Estimated was 60 min -> variance = +10 min
        "completion_pct": 100.0,
        "status": "COMPLETED",
        "remarks": "Tamping verified and track speed cleared"
    }, headers=engg_headers)
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["status"] == "COMPLETED"
    assert comp_data["actual_end_min"] == 680
    assert comp_data["variance_min"] == 10

    final_job = client.get(f"/api/maintenance/requests/{job_id}", headers=engg_headers).json()
    assert final_job["status"] == "COMPLETED"
    assert final_job["variance_minutes"] == 10
    assert len(final_job["state_history_json"]) >= 4


def test_department_request_change_flow():
    """
    Validates department change request:
    1. Plan approved
    2. Department requests change with reason
    3. Job and Plan move to CHANGE_REQUESTED
    4. Planner notified with high priority
    """
    engg_token = get_token("engg_user", "engg123", "Engineering")
    planner_token = get_token("planner", "planner123", "Railway Operations & Traffic Planning")

    engg_headers = {"Authorization": f"Bearer {engg_token}"}
    planner_headers = {"Authorization": f"Bearer {planner_token}"}

    job_code = f"TEST-CHANGE-{int(datetime.utcnow().timestamp())}"
    due = (datetime.utcnow() + timedelta(days=3)).isoformat()
    create_res = client.post("/api/maintenance/requests", json={
        "job_code": job_code,
        "work_type": "POINT_OVERHAUL",
        "description": "Point overhaul testing change request",
        "start_station_code": "CVP",
        "end_station_code": "KDU",
        "user_priority": "MEDIUM",
        "due_date": due,
        "estimated_duration_min": 45
    }, headers=engg_headers)
    job_id = create_res.json()["id"]

    opt_res = client.post("/api/planning/optimize", json={
        "strategy": "PLAN_A"
    }, headers=planner_headers)
    plan_id = opt_res.json()["id"]

    client.post(f"/api/planning/plans/{plan_id}/approve", json={"action": "APPROVE"}, headers=planner_headers)

    # Department requests change
    req_change_res = client.post(f"/api/planning/plans/{plan_id}/department-request-change", json={
        "action": "REQUEST_CHANGE",
        "remarks": "Machine breakdown; request shift to evening window 16:00"
    }, headers=engg_headers)
    assert req_change_res.status_code == 200

    plan_state = req_change_res.json()
    assert plan_state["approval_status"] == "CHANGE_REQUESTED"

    job_state = client.get(f"/api/maintenance/requests/{job_id}", headers=engg_headers).json()
    assert job_state["status"] == "CHANGE_REQUESTED"
    assert "Machine breakdown" in job_state["department_remarks"]

    # Check planner notifications
    planner_notifs = client.get("/api/notifications", headers=planner_headers).json()
    assert any("Change Requested" in n["title"] or "Machine breakdown" in n["message"] for n in planner_notifs)
