import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.models import MaintenanceJob, RailwaySection, Corridor, Department, User, CoordinatedBlockPlan
from app.algorithms.coordination import CompatibilityEngine, CoordinatedOptimizer
from app.core.security import create_access_token
from seed_sih_canonical_requests import seed_sih_requests


@pytest.fixture(scope="module")
def db():
    seed_sih_requests()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def planner_token(db: Session):
    user = db.query(User).filter(User.username == "planner").first()
    if not user:
        user = User(
            username="planner",
            email="planner@railnet.gov.in",
            hashed_password="hash",
            full_name="Chief Section Controller",
            role="railway_planner",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(subject=str(user.id), role=user.role, department_code="OPERATIONS")
    return f"Bearer {token}"



def test_part35_canonical_clustering(db: Session):
    """
    CRITICAL ACCEPTANCE TEST (Part 35):
    REQ-101 (ENGG, CVP-TEN, Sec-103, 90m)
    REQ-102 (S&T, CVP-TEN, Sec-103, 60m)
    REQ-103 (TRD, CVP-TEN, Sec-103, 75m)
    REQ-104 (ENGG, MDU-TEN, Sec-204, 90m)
    REQ-105 (S&T, MDU-TEN, Sec-204, 60m)
    REQ-106 (ENGG, CBE-SA, Sec-305, 120m)
    System must automatically partition into 3 groups without manual selection:
    Plan 01: CVP->TEN, Sec-103 (REQ-101, 102, 103)
    Plan 02: MDU->TEN, Sec-204 (REQ-104, 105)
    Plan 03: CBE->SA, Sec-305 (REQ-106)
    """
    job_codes = ["REQ-101", "REQ-102", "REQ-103", "REQ-104", "REQ-105", "REQ-106"]
    jobs = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(job_codes)).all()
    assert len(jobs) == 6, f"Expected 6 jobs, found {len(jobs)}"

    groups = CompatibilityEngine.cluster_compatible_groups(jobs)
    assert len(groups) == 3, f"Expected exactly 3 groups, got {len(groups)}"

    # Identify groups by section
    g103 = next((g for g in groups if any(j.job_code in ["REQ-101", "REQ-102", "REQ-103"] for j in g["jobs"])), None)
    g204 = next((g for g in groups if any(j.job_code in ["REQ-104", "REQ-105"] for j in g["jobs"])), None)
    g305 = next((g for g in groups if any(j.job_code == "REQ-106" for j in g["jobs"])), None)

    assert g103 is not None
    assert g103["coordination_type"] == "COMMON_BLOCK"
    assert len(g103["jobs"]) == 3
    assert {j.job_code for j in g103["jobs"]} == {"REQ-101", "REQ-102", "REQ-103"}

    assert g204 is not None
    assert g204["coordination_type"] == "COMMON_BLOCK"
    assert len(g204["jobs"]) == 2
    assert {j.job_code for j in g204["jobs"]} == {"REQ-104", "REQ-105"}

    assert g305 is not None
    assert g305["coordination_type"] == "INDIVIDUAL_BLOCK"
    assert len(g305["jobs"]) == 1
    assert g305["jobs"][0].job_code == "REQ-106"


def test_part36_negative_cross_section_never_grouped(db: Session):
    """
    CRITICAL NEGATIVE TEST (Part 36 & Part 8):
    REQ-201 on SECTION-103 (CVP->TEN) and REQ-202 on SECTION-305 (CBE->SA)
    Must NEVER be placed into the same common block.
    """
    engg = db.query(Department).filter(Department.code == "ENGG").first()
    snt = db.query(Department).filter(Department.code == "SNT").first()
    sec_103 = db.query(RailwaySection).filter(RailwaySection.section_id == "SECTION-103").first()
    sec_305 = db.query(RailwaySection).filter(RailwaySection.section_id == "SECTION-305").first()

    req_201 = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-201").first()
    if not req_201:
        req_201 = MaintenanceJob(
            job_code="REQ-201",
            department_id=engg.id if engg else 1,
            work_title="Track Tamping",
            work_type="TRACK_TAMPING",
            section_id=sec_103.id if sec_103 else None,
            start_station_code="CVP",
            end_station_code="TEN",
            estimated_duration_min=90,
            user_priority="HIGH",
            requested_date=datetime(2026, 9, 15),
            status="SUBMITTED",
            description="Negative test candidate 1"
        )
        db.add(req_201)

    req_202 = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-202").first()
    if not req_202:
        req_202 = MaintenanceJob(
            job_code="REQ-202",
            department_id=snt.id if snt else 2,
            work_title="Signal Inspection",
            work_type="SIGNAL_INSPECTION",
            section_id=sec_305.id if sec_305 else None,
            start_station_code="CBE",
            end_station_code="SA",
            estimated_duration_min=60,
            user_priority="HIGH",
            requested_date=datetime(2026, 9, 15),
            status="SUBMITTED",
            description="Negative test candidate 2"
        )
        db.add(req_202)

    db.commit()

    # Run clustering on these two jobs
    groups = CompatibilityEngine.cluster_compatible_groups([req_201, req_202])

    # They MUST NOT be in the same group
    assert len(groups) == 2, "Incompatible sections must NEVER be merged into the same group!"
    for g in groups:
        assert len(g["jobs"]) == 1
        assert g["coordination_type"] == "INDIVIDUAL_BLOCK"


def test_optimize_pool_canonical_solution(db: Session):
    """
    Verifies that optimize_pool solves the canonical 6 requests
    and outputs truthful metrics, window timings, and savings.
    """
    job_codes = ["REQ-101", "REQ-102", "REQ-103", "REQ-104", "REQ-105", "REQ-106"]
    jobs = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(job_codes)).all()

    result = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")

    assert result["requests_analyzed"] == 6
    assert result["requests_coordinated"] == 5
    assert result["requests_individual"] == 1
    assert result["requests_unresolved"] == 0
    assert result["total_optimized_plans"] == 3
    assert result["original_potential_blocks"] == 6
    assert result["optimized_blocks"] == 3
    assert result["possessions_avoided"] == 3  # (3-1) + (2-1) + 0 = 3 avoided
    assert result["estimated_coordination_benefit"] in ("HIGH", "MAXIMUM")

    plans = result["plans"]
    assert len(plans) == 3

    # Check Plan 1
    p1 = plans[0]
    assert p1["plan_title"] == "PLAN 01"
    assert p1["coordination_type"] == "COMMON_BLOCK"
    assert len(p1["request_ids"]) == 3
    assert p1["conflicts_count"] == 0
    assert p1["common_block_window"] == "10:45 – 12:15"
    assert p1["total_possession_duration_min"] == 90
    assert p1["separate_blocks_avoided"] == 2

    # Check Plan 2
    p2 = plans[1]
    assert p2["plan_title"] == "PLAN 02"
    assert p2["coordination_type"] == "COMMON_BLOCK"
    assert len(p2["request_ids"]) == 2
    assert p2["conflicts_count"] == 0
    assert p2["common_block_window"] == "13:00 – 14:30"
    assert p2["separate_blocks_avoided"] == 1

    # Check Plan 3
    p3 = plans[2]
    assert p3["plan_title"] == "PLAN 03"
    assert p3["coordination_type"] == "INDIVIDUAL_BLOCK"
    assert len(p3["request_ids"]) == 1
    assert p3["conflicts_count"] == 0
    assert p3["common_block_window"] == "15:00 – 17:00"
    assert p3["separate_blocks_avoided"] == 0


def test_api_block_planning_optimize_endpoint(client: TestClient, planner_token: str, db: Session):
    """
    Tests the POST /api/block-planning/optimize endpoint via HTTP TestClient.
    """
    headers = {"Authorization": planner_token}

    # Reset test jobs to SUBMITTED
    db.query(MaintenanceJob).filter(
        MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103", "REQ-104", "REQ-105", "REQ-106"])
    ).update({"status": "SUBMITTED", "coordinated_plan_id": None}, synchronize_session=False)
    db.commit()

    res = client.post(
        "/api/block-planning/optimize",
        headers=headers,
        json={"strategy": "PLAN_A"}
    )
    assert res.status_code == 200, f"Error: {res.text}"
    data = res.json()

    assert "optimization_run_id" in data
    assert data["requests_analyzed"] >= 6
    assert data["requests_coordinated"] >= 5
    assert len(data["plans"]) >= 3

    # Verify that plan records are persisted in database
    req_101_plan = next(p for p in data["plans"] if "REQ-101" in p["request_ids"])
    plan_db = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == req_101_plan["plan_id"]).first()
    assert plan_db is not None
    assert plan_db.plan_code == req_101_plan["plan_code"]

    # Verify linked jobs are updated to RECOMMENDED
    j101 = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-101").first()
    assert j101.status == "RECOMMENDED"
    assert j101.coordinated_plan_id == plan_db.id

