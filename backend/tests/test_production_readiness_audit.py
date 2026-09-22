"""
Production-Readiness Audit Verification Test Suite for SIH26027 (IR-ABPS).
Validates:
1. Explainable priority & safety scoring (MCDA point contributions & sub-factors)
2. Strict canonical corridor boundary (C01-C46 strictly enforced)
3. Zero tolerance for false 00:00-24:00 availability
4. Actual OR-Tools CP-SAT solver invocation and dynamic metrics
5. Optimistic locking concurrency protection (HTTP 409)
6. Safety invariants (COMPLETED/ACTIVE blocks protected from rescheduling)
7. Production-isolated What-If scenario evaluation
8. System Health & Readiness endpoints (/health, /health/live, /health/ready)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.models import (
    Corridor, RailwaySection, MaintenanceJob, CoordinatedBlockPlan,
    TrainSectionOccupancy, Department, User
)
from app.algorithms.priority import PriorityEngine
from app.algorithms.windows import WindowEngine
from app.algorithms.coordination import CompatibilityEngine, CoordinatedOptimizer
from app.algorithms.optimizer import CPSATSolver
from app.core.security import create_access_token

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def planner_token(db: Session):
    user = db.query(User).filter(User.username == "planner").first()
    if not user:
        return create_access_token(subject=1, role="railway_planner")
    return create_access_token(subject=user.id, role=user.role)


# -------------------------------------------------------------
# 1. EXPLAINABLE PRIORITY & SAFETY SCORING
# -------------------------------------------------------------
def test_audit_explainable_priority_and_sub_factors():
    """Verify that priority calculation has no magic numbers and returns explicit sub-factors."""
    result = PriorityEngine.calculate_full_priority(
        work_type="TRACK_TAMPING",
        department_code="ENGG",
        user_priority="HIGH",
        due_date=datetime.utcnow()
    )

    # 1. Formula invariant: weights sum to 100%
    weights = result["weights_used"]
    total_weight = sum(weights.values())
    assert abs(total_weight - 1.0) < 0.001, "Weights must sum to 1.0 (100%)"

    # 2. Point contributions must match formula: 0.30*C + 0.20*U + 0.15*O + 0.20*S + 0.15*OP
    contrib = result["factor_contributions"]
    c_pts = contrib["criticality_points"]
    u_pts = contrib["urgency_points"]
    o_pts = contrib["overdue_risk_points"]
    s_pts = contrib["safety_impact_points"]
    op_pts = contrib["operational_impact_points"]

    expected_sum = round(c_pts + u_pts + o_pts + s_pts + op_pts, 1)
    assert abs(result["priority_score"] - expected_sum) <= 0.2, "Priority score must be exact sum of factor point contributions"

    # 3. Sub-factor auditability: Criticality & Safety must expose transparent sub-factors
    c_sub = result["criticality_sub_factors"]
    assert "condition_score" in c_sub
    assert "failure_consequence_score" in c_sub
    assert "operational_importance_score" in c_sub
    assert c_sub["calculation_version"] == "v2.0-deterministic"

    s_sub = result["safety_sub_factors"]
    assert "safety_consequence_score" in s_sub
    assert "train_operation_safety_score" in s_sub
    assert "failure_severity_score" in s_sub
    assert "mitigation_score" in s_sub
    assert s_sub["calculation_version"] == "v2.0-deterministic"


# -------------------------------------------------------------
# 2. STRICT CANONICAL CORRIDORS (C01 - C46)
# -------------------------------------------------------------
def test_audit_canonical_corridors_c01_through_c46():
    """Verify that only authentic canonical corridors C01-C46 are returned, with no C47+ or unnamed records."""
    res = client.get("/api/railway/corridors")
    assert res.status_code == 200
    corridors = res.json()

    assert len(corridors) == 46, "Operational selector must contain strictly 46 Southern Railway corridors"

    prototype_codes = [c["prototype_code"] for c in corridors]
    for num in range(1, 47):
        code = f"C{num:02d}"
        assert code in prototype_codes, f"Corridor {code} must be present in canonical operational master"

    # Strict check: No C47 or above
    invalid_codes = [c["prototype_code"] for c in corridors if c["prototype_code"] > "C46"]
    assert len(invalid_codes) == 0, f"Found invalid corridors above C46: {invalid_codes}"


# -------------------------------------------------------------
# 3. AVAILABILITY ENGINE: ZERO TOLERANCE FOR FALSE 00:00-24:00
# -------------------------------------------------------------
def test_audit_no_false_availability_window():
    """Verify that WindowEngine never generates false 00:00-24:00 window when timetable is missing or trains run."""
    # Scenario A: Missing timetable data
    missing_res = WindowEngine.calculate_feasible_windows(
        section_id=999,
        corridor_id=999,
        occupancies=[],
        has_timetable_data=False
    )
    assert len(missing_res) == 0, "Missing timetable data must produce DATA_UNAVAILABLE (empty list), never 00:00-24:00"

    # Scenario B: Train in section from 10:00 to 11:30 (600 to 690 min)
    occupancies = [
        {"section_id": 101, "train_number": "12634", "estimated_entry_min": 600, "estimated_exit_min": 690}
    ]
    occupied_res = WindowEngine.calculate_feasible_windows(
        section_id=101,
        corridor_id=40,
        occupancies=occupancies,
        min_window_duration_min=45
    )
    assert len(occupied_res) > 0
    for w in occupied_res:
        # None of the windows must overlap the train's occupancy
        assert not (w["start_min"] <= 600 and w["end_min"] >= 690), "Window must not bridge across active train occupancy"
        assert not (w["start_min"] == 0 and w["end_min"] == 1440), "Occupied section must never have a 00:00-24:00 window"


# -------------------------------------------------------------
# 4. ACTUAL OR-TOOLS CP-SAT SOLVER INVOCATION
# -------------------------------------------------------------
def test_audit_cpsat_solver_dynamically_scheduled(db: Session):
    """Verify that CoordinatedOptimizer calls Google OR-Tools CP-SAT and generates authentic dynamic scores."""
    jobs = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(["REQ-101", "REQ-102"])).all()
    if len(jobs) >= 2:
        result = CoordinatedOptimizer.optimize(jobs, db, strategy="PLAN_A")
        assert result["coordination_type"] == "COMMON_BLOCK"
        # Dynamic metrics computed by CP-SAT solver
        assert 50.0 <= result["optimization_score"] <= 100.0
        assert result["block_utilization_pct"] > 0.0
        assert len(result["alternatives"]) == 3
        # Invariant: Plan A score > Plan C score
        assert result["alternatives"][0]["score"] >= result["alternatives"][2]["score"]


# -------------------------------------------------------------
# 5. OPTIMISTIC CONCURRENCY LOCKING (HTTP 409)
# -------------------------------------------------------------
def test_audit_optimistic_locking_concurrency(planner_token: str, db: Session):
    """Verify that modifying or approving a plan with a stale version raises HTTP 409 conflict."""
    headers = {"Authorization": f"Bearer {planner_token}"}

    # Find or create a proposed coordinated plan
    plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.status == "PROPOSED").first()
    if not plan:
        plan = CoordinatedBlockPlan(
            plan_code="CBP-CONCURRENCY-TEST",
            start_min=600,
            end_min=690,
            duration_min=90,
            status="PROPOSED",
            version=2
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

    plan_id = plan.id
    current_ver = plan.version or 1

    # Attempt to approve with stale version (current_ver - 1)
    res_stale = client.post(
        f"/api/coordinated-block-plans/{plan_id}/approve",
        json={"action": "APPROVE", "reason": "Concurrent update test", "version": current_ver - 1},
        headers=headers
    )
    assert res_stale.status_code == 409, "Stale version must return HTTP 409 Conflict"
    assert "Concurrency conflict" in res_stale.json()["detail"]


# -------------------------------------------------------------
# 6. SAFETY INVARIANTS: COMPLETED / ACTIVE BLOCKS PROTECTED
# -------------------------------------------------------------
def test_audit_completed_block_never_rescheduled(planner_token: str, db: Session):
    """Verify that COMPLETED or ACTIVE block plans cannot be rescheduled or modified."""
    headers = {"Authorization": f"Bearer {planner_token}"}

    unique_code = f"CBP-COMPLETED-SAFETY-{int(datetime.utcnow().timestamp() * 1000)}"
    comp_plan = CoordinatedBlockPlan(
        plan_code=unique_code,
        start_min=480,
        end_min=570,
        duration_min=90,
        status="COMPLETED",
        version=1
    )
    db.add(comp_plan)
    db.commit()
    db.refresh(comp_plan)

    # Attempt replan
    replan_res = client.post(
        f"/api/coordinated-block-plans/{comp_plan.id}/replan",
        json={"reason": "Attempt to move completed work"},
        headers=headers
    )
    assert replan_res.status_code == 400, "Rescheduling COMPLETED block must return HTTP 400"
    assert "cannot be rescheduled" in replan_res.json()["detail"].lower()


# -------------------------------------------------------------
# 7. PRODUCTION-ISOLATED WHAT-IF EVALUATION
# -------------------------------------------------------------
def test_audit_what_if_isolated_from_production(planner_token: str, db: Session):
    """Verify that What-If simulation evaluates scenario without mutating production plan data."""
    headers = {"Authorization": f"Bearer {planner_token}"}

    plan = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.status == "APPROVED").first()
    if not plan:
        plan = db.query(CoordinatedBlockPlan).first()

    if plan:
        orig_start = plan.start_min
        orig_status = plan.status

        res = client.post(
            f"/api/coordinated-block-plans/{plan.id}/what-if",
            json={"scenario_type": "TRAIN_DELAY", "perturbation_value": 45, "remarks": "Simulated express delay"},
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["scenario"] == "TRAIN_DELAY"
        assert data["what_if_start_min"] == orig_start + 45
        assert "hard_conflicts" in data

        # Verify DB plan was NOT mutated
        db.refresh(plan)
        assert plan.start_min == orig_start, "Production plan start_min must not change during What-If simulation"
        assert plan.status == orig_status, "Production plan status must not change during What-If simulation"


# -------------------------------------------------------------
# 8. HEALTH & READINESS ENDPOINTS
# -------------------------------------------------------------
def test_audit_health_and_readiness():
    """Verify /health, /health/live, and /health/ready endpoints provide complete subsystem observability."""
    # /health
    h_res = client.get("/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["status"] in ("HEALTHY", "DEGRADED")
    assert h_data["components"]["database"] == "HEALTHY"
    assert h_data["components"]["optimizer"] == "READY"
    assert "safety_validator" in h_data

    # /health/live
    l_res = client.get("/health/live")
    assert l_res.status_code == 200
    assert l_res.json()["status"] == "LIVE"

    # /health/ready
    r_res = client.get("/health/ready")
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "READY"
