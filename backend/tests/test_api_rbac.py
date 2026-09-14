import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.models import User, BlockPlan


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


def test_unauthorized_department_user_approval_forbidden():
    db = SessionLocal()
    try:
        # Fetch department user and planner
        dept_user = db.query(User).filter(User.role.in_(["TRACK_ENGINEERING", "department_user"])).first()
        planner_user = db.query(User).filter(User.role.in_(["RAILWAY_PLANNER", "railway_planner"])).first()
        plan = db.query(BlockPlan).first()
        if not plan:
            # Create dummy plan if not exists
            plan = BlockPlan(plan_code="PLAN_TEST_01", plan_name="Test Plan", is_active=True)
            db.add(plan)
            db.commit()
            db.refresh(plan)

        # 1. Department user tries to approve plan -> MUST BE 403 FORBIDDEN
        dept_token = create_access_token(subject=dept_user.id, role="department_user")
        res_dept = client.post(
            f"/api/planning/plans/{plan.id}/approve",
            json={"action": "APPROVE", "reason": "Department attempt"},
            headers={"Authorization": f"Bearer {dept_token}"}
        )
        assert res_dept.status_code == 403

        # 2. Planner user approves plan -> MUST BE 200 SUCCESS
        planner_token = create_access_token(subject=planner_user.id, role="railway_planner")
        res_planner = client.post(
            f"/api/planning/plans/{plan.id}/approve",
            json={"action": "APPROVE", "reason": "Authorized planner approval"},
            headers={"Authorization": f"Bearer {planner_token}"}
        )
        assert res_planner.status_code == 200
        assert res_planner.json()["approval_status"] == "APPROVED"
    finally:
        db.close()
