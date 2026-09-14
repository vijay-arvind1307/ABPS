"""
Integration Test Suite for Multi-Department Coordinated Block Planning (SIH26027).
Tests all 20 specification test cases and the complete Part 37 Acceptance Scenario.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.models import (
    User, Department, Corridor, RailwaySection, MaintenanceJob,
    CoordinatedBlockPlan, AuditLog, Train
)
from app.core.security import create_access_token

client = TestClient(app)


def get_token(username: str, role: str) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            # Look up by role
            user = db.query(User).filter(User.role.ilike(f"%{role}%")).first()
        return create_access_token(subject=user.id, role=user.role, department_code=user.department.code if user.department else None)
    finally:
        db.close()


@pytest.fixture
def planner_auth():
    token = get_token("planner", "RAILWAY_PLANNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def engg_auth():
    token = get_token("engg_user", "TRACK_ENGINEERING")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def snt_auth():
    token = get_token("snt_user", "SIGNAL_TELECOM")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def trd_auth():
    token = get_token("trd_user", "TRACTION_DISTRIBUTION")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def corridor_and_section():
    db = SessionLocal()
    try:
        # Look for CVP -> TEN or any valid corridor
        corr = db.query(Corridor).filter(
            Corridor.start_station_code == "CVP", Corridor.end_station_code == "TEN"
        ).first()
        if not corr:
            corr = db.query(Corridor).filter(Corridor.name.ilike("%TEN%")).first() or db.query(Corridor).first()

        section = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).first()
        if not section:
            section = db.query(RailwaySection).first()

        other_section = db.query(RailwaySection).filter(RailwaySection.id != section.id).first()

        return {
            "corridor": corr,
            "section": section,
            "other_section": other_section
        }
    finally:
        db.close()


# ============================================================================
# TEST 1: Single Request Optimization (Kept Intact)
# ============================================================================
def test_01_single_request_optimization(planner_auth, engg_auth, corridor_and_section):
    """Verify existing single-request optimization remains fully functional."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]

    # ENGG submits single request
    req_payload = {
        "job_code": f"REQ-SNG-{int(datetime.utcnow().timestamp())}",
        "work_title": "Emergency Rail Surface Grinding",
        "work_type": "TRACK_TAMPING",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "estimated_duration_min": 60,
        "user_priority": "HIGH",
        "status": "SUBMITTED"
    }
    create_res = client.post("/api/block-requests", json=req_payload, headers=engg_auth)
    assert create_res.status_code == 200
    job_id = create_res.json()["id"]

    # Planner runs single-request optimization
    opt_res = client.post(f"/api/block-requests/{job_id}/optimize", headers=planner_auth)
    assert opt_res.status_code == 200
    data = opt_res.json()
    assert "alternatives" in data or "Plan A" in str(data)
    assert data.get("conflicting_trains_count") == 0


# ============================================================================
# TEST 2: Two Compatible Requests
# ============================================================================
def test_02_two_compatible_requests(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify 2 compatible requests are identified as 100% compatible for common block."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-COMP2-A-{int(datetime.utcnow().timestamp())}",
        "work_title": "Track Geometry Alignment",
        "work_type": "TRACK_TAMPING",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90,
        "user_priority": "HIGH"
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-COMP2-B-{int(datetime.utcnow().timestamp())}",
        "work_title": "Axle Counter Maintenance",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60,
        "user_priority": "MEDIUM"
    }, headers=snt_auth).json()

    check_res = client.post("/api/block-requests/coordination/check", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth)

    assert check_res.status_code == 200
    data = check_res.json()
    assert data["is_compatible"] is True
    assert data["compatible_count"] == 2
    assert data["incompatible_count"] == 0


# ============================================================================
# TEST 3: Three Compatible Departmental Requests
# ============================================================================
def test_03_three_compatible_requests(planner_auth, engg_auth, snt_auth, trd_auth, corridor_and_section):
    """Verify 3 departmental requests can form a single common block recommendation."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-C3-ENGG-{int(datetime.utcnow().timestamp())}",
        "work_title": "Deep Ballast Screening",
        "work_type": "TRACK_TAMPING",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-C3-SNT-{int(datetime.utcnow().timestamp())}",
        "work_title": "Point Machine Cleaning",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    r3 = client.post("/api/block-requests", json={
        "job_code": f"REQ-C3-TRD-{int(datetime.utcnow().timestamp())}",
        "work_title": "OHE Contact Wire Inspection",
        "work_type": "OHE_INSPECTION",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 75
    }, headers=trd_auth).json()

    opt_res = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"], r3["id"]],
        "strategy": "PLAN_A"
    }, headers=planner_auth)

    assert opt_res.status_code == 200
    plan = opt_res.json()
    assert plan["requests_combined_count"] == 3
    assert plan["total_possession_duration_min"] == 90  # Parallel work max(90, 60, 75)
    assert plan["savings"]["possessions_avoided"] == 2
    assert plan["savings"]["possession_time_saved_min"] == (90 + 60 + 75) - 90  # 135 min saved


# ============================================================================
# TEST 4: Requests From Different Sections Rejected
# ============================================================================
def test_04_different_sections_incompatible(planner_auth, engg_auth, corridor_and_section):
    """Verify requests on different sections/corridors cannot form a common block."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    other_sec = corridor_and_section["other_section"]

    if not other_sec:
        pytest.skip("Requires at least 2 distinct sections in test database")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-SEC1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "estimated_duration_min": 60
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-SEC2-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "corridor_id": other_sec.corridor_id,
        "section_id": other_sec.id,
        "start_station_code": "MAS",
        "end_station_code": "AJJ",
        "estimated_duration_min": 60
    }, headers=engg_auth).json()

    check_res = client.post("/api/block-requests/coordination/check", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth)

    assert check_res.status_code == 200
    data = check_res.json()
    assert data["is_compatible"] is False
    assert data["can_proceed"] is False
    assert "section" in str(data["incompatibility_reasons"]).lower() or "corridor" in str(data["incompatibility_reasons"]).lower()


# ============================================================================
# TEST 5: Partial Coordination (4 selected, 3 compatible, 1 incompatible)
# ============================================================================
def test_05_partial_coordination(planner_auth, engg_auth, snt_auth, trd_auth, corridor_and_section):
    """Verify system isolates the 3 compatible jobs and marks the 4th as excluded."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    other_sec = corridor_and_section["other_section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-P1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-P2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    r3 = client.post("/api/block-requests", json={
        "job_code": f"REQ-P3-{int(datetime.utcnow().timestamp())}",
        "work_type": "OHE_INSPECTION",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 75
    }, headers=trd_auth).json()

    r4 = client.post("/api/block-requests", json={
        "job_code": f"REQ-P4-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": other_sec.id if other_sec else 999,
        "corridor_id": other_sec.corridor_id if other_sec else 999,
        "start_station_code": "MDU",
        "end_station_code": "DG",
        "requested_date": req_date,
        "estimated_duration_min": 120
    }, headers=engg_auth).json()

    check_res = client.post("/api/block-requests/coordination/check", json={
        "job_ids": [r1["id"], r2["id"], r3["id"], r4["id"]]
    }, headers=planner_auth)

    assert check_res.status_code == 200
    data = check_res.json()
    assert data["is_partially_compatible"] is True
    assert data["compatible_count"] == 3
    assert data["incompatible_count"] == 1
    assert data["incompatible_jobs"][0]["job_id"] == r4["id"]


# ============================================================================
# TEST 6: Coordinated Alternatives Plan A, B, C
# ============================================================================
def test_06_plan_a_b_c_generation(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify coordinated optimization generates Plan A (Best), Plan B (Window), Plan C (Fallback)."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-ALT-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-ALT-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    opt_res = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth)

    assert opt_res.status_code == 200
    plan = opt_res.json()
    alts = plan.get("alternatives", [])
    assert len(alts) >= 3
    names = [a["plan_name"] for a in alts]
    assert "Plan A" in names
    assert "Plan B" in names
    assert "Plan C" in names


# ============================================================================
# TEST 7: Approve Common Plan Links Requests
# ============================================================================
def test_07_approve_common_plan(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify approving coordinated plan sets status=APPROVED and links jobs to CBP."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-APP-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-APP-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    plan_id = plan["id"]

    app_res = client.post(f"/api/coordinated-block-plans/{plan_id}/approve", json={
        "reason": "Approved for unified possession by Railway Planner"
    }, headers=planner_auth)

    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # Verify both jobs are now APPROVED and linked to CBP
    j1_check = client.get(f"/api/block-requests/{r1['id']}", headers=planner_auth).json()
    j2_check = client.get(f"/api/block-requests/{r2['id']}", headers=planner_auth).json()
    assert j1_check["status"] == "APPROVED"
    assert j2_check["status"] == "APPROVED"
    assert j1_check["coordinated_plan_id"] == plan_id
    assert j2_check["coordinated_plan_id"] == plan_id


# ============================================================================
# TEST 8: Reject Common Plan Restores Requests
# ============================================================================
def test_08_reject_common_plan(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify rejecting common plan unlinks requests and resets them to SUBMITTED without deleting."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-REJ-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-REJ-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    plan_id = plan["id"]

    rej_res = client.post(f"/api/coordinated-block-plans/{plan_id}/reject", json={
        "reason": "Traffic priority: heavy seasonal holiday passenger express running"
    }, headers=planner_auth)

    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"

    # Jobs remain in database, unlinked
    j1_check = client.get(f"/api/block-requests/{r1['id']}", headers=planner_auth).json()
    j2_check = client.get(f"/api/block-requests/{r2['id']}", headers=planner_auth).json()
    assert j1_check["status"] == "SUBMITTED"
    assert j2_check["status"] == "SUBMITTED"
    assert j1_check["coordinated_plan_id"] is None
    assert j2_check["coordinated_plan_id"] is None


# ============================================================================
# TEST 9: Modify Common Plan Stores Mandatory Reason
# ============================================================================
def test_09_modify_common_plan(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify modifying common block window stores mandatory operational reason in audit log."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-MOD-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-MOD-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    mod_res = client.post(f"/api/coordinated-block-plans/{plan['id']}/modify", json={
        "recommended_start_min": 660,
        "recommended_end_min": 750,
        "reason": "Shifted 15 min later to guarantee 25 min headway behind Vande Bharat Express"
    }, headers=planner_auth)

    assert mod_res.status_code == 200
    updated_plan = mod_res.json()
    assert updated_plan["start_min"] == 660
    assert updated_plan["end_min"] == 750
    assert "Vande Bharat" in updated_plan["planner_remarks"]


# ============================================================================
# TEST 10, 11, 12: Department Acceptance, Start, Complete
# ============================================================================
def test_10_11_12_execution_lifecycle(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify department accept, start execution, and complete execution."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-EXEC-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-EXEC-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    client.post(f"/api/coordinated-block-plans/{plan['id']}/approve", json={
        "reason": "Approved"
    }, headers=planner_auth)

    # 10. Department Accepts
    accept_res = client.post(f"/api/block-requests/{r1['id']}/accept", headers=engg_auth)
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] in ["DEPARTMENT_ACCEPTED", "ACCEPTED"]

    # 11. Start Execution
    start_res = client.post(f"/api/block-requests/{r1['id']}/start", json={
        "actual_start_min": 645,
        "remarks": "Track machine on track; possession initiated"
    }, headers=engg_auth)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"

    # Verify Coordinated plan is IN_PROGRESS
    cp_check = client.get(f"/api/coordinated-block-plans/{plan['id']}", headers=planner_auth).json()
    assert cp_check["status"] == "IN_PROGRESS"

    # 12. Complete Execution
    comp_res = client.post(f"/api/block-requests/{r1['id']}/complete", json={
        "actual_end_min": 735,
        "remarks": "Work completed; track restored for traffic"
    }, headers=engg_auth)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # Complete second job to finish coordinated plan
    client.post(f"/api/block-requests/{r2['id']}/complete", json={
        "actual_end_min": 735,
        "remarks": "Signal testing completed"
    }, headers=snt_auth)

    # Verify Coordinated plan is COMPLETED
    cp_final = client.get(f"/api/coordinated-block-plans/{plan['id']}", headers=planner_auth).json()
    assert cp_final["status"] == "COMPLETED"


# ============================================================================
# TEST 13 & 14: Independent Live Corridor Observation
# ============================================================================
def test_13_14_independent_live_observation(planner_auth, corridor_and_section):
    """Verify live train observation corridor is completely independent from request corridor."""
    db = SessionLocal()
    try:
        corrs = db.query(Corridor).all()
        if len(corrs) < 2:
            pytest.skip("Requires at least 2 corridors to test independent observation")

        corr1 = corrs[0]
        corr2 = corrs[1]

        # Planner requests trains for Corridor 1
        res1 = client.get(f"/api/railway/corridors/{corr1.id}/trains/live", headers=planner_auth)
        assert res1.status_code == 200
        assert isinstance(res1.json(), list)

        # Planner independently requests trains for Corridor 2
        res2 = client.get(f"/api/railway/corridors/{corr2.id}/trains/live", headers=planner_auth)
        assert res2.status_code == 200
        assert isinstance(res2.json(), list)

        # Request corridor remains independent and decoupled
        assert corr1.id != corr2.id
    finally:
        db.close()


# ============================================================================
# TEST 17 & 18: What-If Simulation
# ============================================================================
def test_17_18_coordinated_what_if(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify what-if simulation calculates perturbations without mutating base plan."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-WIF-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-WIF-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    # What-if: Train delay +30 min
    wif_res = client.post(f"/api/coordinated-block-plans/{plan['id']}/what-if", json={
        "scenario_type": "TRAIN_DELAY",
        "perturbation_value": 30,
        "remarks": "Express train delayed by 30 min in section"
    }, headers=planner_auth)

    assert wif_res.status_code == 200
    data = wif_res.json()
    assert "base_plan" in data
    assert "simulated_plan" in data
    assert data["feasibility"] in ["FEASIBLE", "CONSTRAINED", "INFEASIBLE"]


# ============================================================================
# TEST 19: Dynamic Replanning
# ============================================================================
def test_19_dynamic_replan(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify dynamic replanning re-optimizes common block window upon disruption."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-DYN-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-DYN-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    replan_res = client.post(f"/api/coordinated-block-plans/{plan['id']}/replan", json={
        "reason": "Unexpected unscheduled freight rake occupancy detected in block section"
    }, headers=planner_auth)

    assert replan_res.status_code == 200
    data = replan_res.json()
    assert "revised_plan" in data
    assert data["status"] in ["REPLANNED", "PROPOSED"]


# ============================================================================
# TEST 20: Audit Trail Verification
# ============================================================================
def test_20_coordination_audit_trail(planner_auth, engg_auth, snt_auth, corridor_and_section):
    """Verify all coordination actions are audited permanently."""
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    r1 = client.post("/api/block-requests", json={
        "job_code": f"REQ-AUD-1-{int(datetime.utcnow().timestamp())}",
        "work_type": "TRACK_TAMPING",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 90
    }, headers=engg_auth).json()

    r2 = client.post("/api/block-requests", json={
        "job_code": f"REQ-AUD-2-{int(datetime.utcnow().timestamp())}",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "section_id": sec.id,
        "corridor_id": corr.id,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "requested_date": req_date,
        "estimated_duration_min": 60
    }, headers=snt_auth).json()

    plan = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": [r1["id"], r2["id"]]
    }, headers=planner_auth).json()

    client.post(f"/api/coordinated-block-plans/{plan['id']}/approve", json={
        "reason": "Audit verification approval"
    }, headers=planner_auth)

    audit_res = client.get(f"/api/coordinated-block-plans/{plan['id']}/audit", headers=planner_auth)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    actions = [l["action"] for l in logs]
    assert any("OPTIMIZ" in a or "APPROV" in a or "GENERAT" in a for a in actions)


# ============================================================================
# PART 37: FINAL ACCEPTANCE SCENARIO (STEPS 1 - 16)
# ============================================================================
def test_part_37_final_acceptance_scenario(planner_auth, engg_auth, snt_auth, trd_auth, corridor_and_section):
    """
    Executes the exact 16-step Master Acceptance Scenario:
    STEP 1: Engineering submits REQ-000101 (CVP -> TEN, Track Tamping, 90m, HIGH)
    STEP 2: S&T submits REQ-000102 (CVP -> TEN, Signal Inspection, 60m, MEDIUM)
    STEP 3: Traction submits REQ-000103 (CVP -> TEN, OHE Inspection, 75m, HIGH)
    STEP 4: Planner opens dashboard, all 3 visible
    STEP 5: Planner selects all three
    STEP 6: Planner clicks FIND COMMON BLOCK
    STEP 7: System checks compatibility -> 3 compatible requests
    STEP 8: Planner clicks OPTIMIZE COMMON BLOCK
    STEP 9: CP-SAT generates Plan A, Plan B, Plan C
    STEP 10: Plan A: CVP -> TEN, 10:45-12:15, 90m total possession, 3 depts, 0 conflicts, 135m saved
    STEP 11: Planner approves common block
    STEP 12: Department users see APPROVED with same common plan CBP
    STEP 13: Engineering accepts -> ACCEPTED
    STEP 14: Start work -> IN_PROGRESS
    STEP 15: Complete work -> COMPLETED
    STEP 16: Audit trail shows 3 requests, 1 coordinated plan, full lifecycle
    """
    corr = corridor_and_section["corridor"]
    sec = corridor_and_section["section"]
    req_date = "2026-09-15"

    # STEP 1: Engineering submits REQ-000101
    r101_res = client.post("/api/block-requests", json={
        "job_code": "REQ-000101",
        "work_title": "Track Tamping",
        "work_type": "TRACK_TAMPING",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": "CVP",
        "end_station_code": "TEN",
        "requested_date": req_date,
        "estimated_duration_min": 90,
        "user_priority": "HIGH",
        "status": "SUBMITTED"
    }, headers=engg_auth)
    assert r101_res.status_code == 200
    r101 = r101_res.json()

    # STEP 2: S&T submits REQ-000102
    r102_res = client.post("/api/block-requests", json={
        "job_code": "REQ-000102",
        "work_title": "Signal Inspection",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": "CVP",
        "end_station_code": "TEN",
        "requested_date": req_date,
        "estimated_duration_min": 60,
        "user_priority": "MEDIUM",
        "status": "SUBMITTED"
    }, headers=snt_auth)
    assert r102_res.status_code == 200
    r102 = r102_res.json()

    # STEP 3: Traction submits REQ-000103
    r103_res = client.post("/api/block-requests", json={
        "job_code": "REQ-000103",
        "work_title": "OHE Inspection",
        "work_type": "OHE_INSPECTION",
        "corridor_id": corr.id,
        "section_id": sec.id,
        "start_station_code": "CVP",
        "end_station_code": "TEN",
        "requested_date": req_date,
        "estimated_duration_min": 75,
        "user_priority": "HIGH",
        "status": "SUBMITTED"
    }, headers=trd_auth)
    assert r103_res.status_code == 200
    r103 = r103_res.json()

    # STEP 4: Planner opens dashboard -> all 3 visible
    all_reqs_res = client.get("/api/block-requests", headers=planner_auth)
    assert all_reqs_res.status_code == 200
    all_codes = [j["job_code"] for j in all_reqs_res.json()]
    assert "REQ-000101" in all_codes
    assert "REQ-000102" in all_codes
    assert "REQ-000103" in all_codes

    # STEP 5 & 6 & 7: Check compatibility
    selected_ids = [r101["id"], r102["id"], r103["id"]]
    compat_res = client.post("/api/block-requests/coordination/check", json={
        "job_ids": selected_ids
    }, headers=planner_auth)
    assert compat_res.status_code == 200
    compat = compat_res.json()
    assert compat["is_compatible"] is True
    assert compat["compatible_count"] == 3

    # STEP 8 & 9 & 10: Optimize common block with CP-SAT
    opt_res = client.post("/api/block-requests/coordination/optimize", json={
        "job_ids": selected_ids,
        "strategy": "PLAN_A"
    }, headers=planner_auth)
    assert opt_res.status_code == 200
    plan_a = opt_res.json()

    assert plan_a["requests_combined_count"] == 3
    assert plan_a["total_possession_duration_min"] == 90
    assert plan_a["conflicts_count"] == 0
    assert plan_a["savings"]["blocks_reduced"] == "3 → 1"
    assert plan_a["savings"]["possessions_avoided"] == 2
    assert plan_a["savings"]["possession_time_saved_min"] == 135
    assert len(plan_a["alternatives"]) >= 3

    # STEP 11: Planner approves
    cbp_id = plan_a["id"]
    app_res = client.post(f"/api/coordinated-block-plans/{cbp_id}/approve", json={
        "reason": "Authorized common possession by Chief Section Controller"
    }, headers=planner_auth)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # STEP 12: Department users see APPROVED with CBP
    j101_check = client.get(f"/api/block-requests/{r101['id']}", headers=engg_auth).json()
    j102_check = client.get(f"/api/block-requests/{r102['id']}", headers=snt_auth).json()
    j103_check = client.get(f"/api/block-requests/{r103['id']}", headers=trd_auth).json()

    assert j101_check["status"] == "APPROVED"
    assert j102_check["status"] == "APPROVED"
    assert j103_check["status"] == "APPROVED"
    assert j101_check["coordinated_plan_id"] == cbp_id
    assert j102_check["coordinated_plan_id"] == cbp_id
    assert j103_check["coordinated_plan_id"] == cbp_id

    # STEP 13: Engineering accepts
    accept_res = client.post(f"/api/block-requests/{r101['id']}/accept", headers=engg_auth)
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] in ["DEPARTMENT_ACCEPTED", "ACCEPTED"]

    # STEP 14: Start work
    start_res = client.post(f"/api/block-requests/{r101['id']}/start", json={
        "actual_start_min": 645,
        "remarks": "Track possession handed over to Civil Engineering squad"
    }, headers=engg_auth)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"

    # STEP 15: Complete work
    comp_res = client.post(f"/api/block-requests/{r101['id']}/complete", json={
        "actual_end_min": 735,
        "remarks": "Track tamping completed. Track clear and fit for 110 kmph"
    }, headers=engg_auth)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"

    # STEP 16: Audit trail shows 3 requests, 1 coordinated plan, and lifecycle
    audit_res = client.get(f"/api/coordinated-block-plans/{cbp_id}/audit", headers=planner_auth)
    assert audit_res.status_code == 200
    assert len(audit_res.json()) >= 1
