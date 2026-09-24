import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.models import User, BlockPlan, TrainMovement, MaintenanceJob
from app.core.security import create_access_token

client = TestClient(app)


@pytest.fixture
def planner_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "planner").first()
        if not user:
            token = create_access_token(subject=1, role="railway_planner")
        else:
            token = create_access_token(subject=user.id, role=user.role)
        return token
    finally:
        db.close()


def test_time_distance_endpoint():
    # 1. Without corridor selection -> Truthful empty state
    res_empty = client.get("/api/railway/time-distance")
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["corridor"] is None
    assert data_empty["stations"] == []
    assert data_empty["trains"] == []
    assert data_empty["provenance"]["source"] == "UNAVAILABLE"

    # 2. With selected corridor (corridor_id=1) -> Loads corridor stations dynamically
    res_corr = client.get("/api/railway/time-distance?corridor_id=1")
    assert res_corr.status_code == 200
    data_corr = res_corr.json()
    assert data_corr["corridor"] is not None
    assert len(data_corr["stations"]) >= 4
    assert isinstance(data_corr["trains"], list)

    # Verify first train has trajectory points if any trains are active
    if len(data_corr["trains"]) > 0:
        tr = data_corr["trains"][0]
        assert "train_number" in tr
        assert "trajectory" in tr
        assert len(tr["trajectory"]) > 0
        assert "min" in tr["trajectory"][0]
        assert "y" in tr["trajectory"][0]


def test_optimization_generates_jobs(planner_token):
    headers = {"Authorization": f"Bearer {planner_token}"}
    response = client.post(
        "/api/planning/optimize",
        json={"strategy": "PLAN_A", "planning_horizon_hours": 24, "time_limit_seconds": 10},
        headers=headers
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert len(plan["plan_jobs"]) > 0

    # Validate Safety
    plan_id = plan["id"]
    val_res = client.post(f"/api/planning/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["status"] == "VALID"
    assert val_data["checked_rules_count"] == 15


def test_delay_simulation_and_dynamic_replanning(planner_token):
    headers = {"Authorization": f"Bearer {planner_token}"}
    # 1. Simulate Train Delay on 12919
    delay_res = client.post(
        "/api/dynamic/simulate-delay",
        json={"train_number": "12919", "additional_delay_min": 30},
        headers=headers
    )
    assert delay_res.status_code == 200
    delay_data = delay_res.json()
    assert delay_data["event"] == "TRAIN_DELAY_INJECTED"
    assert delay_data["train_number"] == "12919"

    # 2. Trigger Dynamic Re-planning
    from app.db.session import SessionLocal
    from app.models.models import BlockPlan
    db = SessionLocal()
    bp = db.query(BlockPlan).order_by(BlockPlan.id.desc()).first()
    base_plan_id = bp.id if bp else 1
    db.close()

    replan_res = client.post(
        "/api/dynamic/replan",
        json={"base_plan_id": base_plan_id, "trigger_event": "TRAIN_DELAY", "affected_train_number": "12919"},
        headers=headers
    )
    assert replan_res.status_code == 200
    replan_data = replan_res.json()
    assert "new_plan_id" in replan_data
    assert replan_data["validation_status"] == "VALID"
