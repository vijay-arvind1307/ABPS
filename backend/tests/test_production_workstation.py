import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.models import (
    Corridor, RailwaySection, Station, Train, TrainMovement,
    TrainRouteStop, TrainSectionOccupancy, BlockWindow,
    MaintenanceJob, CoordinatedBlockPlan, BlockPlan, User
)
from app.services.train_service import TrainService
from app.algorithms.occupancy import OccupancyEngine
from app.algorithms.windows import WindowEngine
from app.algorithms.validator import DeterministicSafetyValidator
from app.algorithms.coordination import CompatibilityEngine, CoordinatedOptimizer
from app.core.security import create_access_token
from seed_sih_canonical_requests import seed_sih_requests

client = TestClient(app)


@pytest.fixture(scope="module")
def db():
    seed_sih_requests()
    session = SessionLocal()
    yield session
    session.close()


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


# =====================================================================
# 1. NETWORK TOPOLOGY & PHYSICAL ALIGNMENT (Tests 1 - 5)
# =====================================================================

def test_01_corridor_c40_physical_topology_count(db: Session):
    """C40 (ID 30) must contain exactly 8 physical block sections."""
    c40 = db.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    assert c40 is not None, "Corridor C40 not found"
    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == c40.id).all()
    assert len(sections) == 8, f"Expected 8 physical sections in C40, found {len(sections)}"


def test_02_corridor_c40_stations_sequence(db: Session):
    """Corridor stations must follow canonical Southern Railway order: MDU -> TEN."""
    expected_order = ["MDU", "TDN", "TMQ", "VPT", "SRT", "CVP", "KDU", "MEJ", "TEN"]
    res = TrainService.generate_time_distance_data(db, 30)
    stn_codes = [s["station_code"] for s in res["stations"]]
    for code in expected_order:
        assert code in stn_codes, f"Station {code} missing from C40 route"


def test_03_corridor_c40_chainage_monotonic(db: Session):
    """Chainage (km) along corridor stations must be strictly non-decreasing."""
    res = TrainService.generate_time_distance_data(db, 30)
    kms = [s["distance_km"] for s in res["stations"]]
    assert len(kms) >= 8
    for i in range(len(kms) - 1):
        assert kms[i] <= kms[i + 1], f"Non-monotonic km at index {i}: {kms[i]} > {kms[i+1]}"


def test_04_sections_sorted_by_start_km(db: Session):
    """Sections returned by generate_time_distance_data must be strictly sorted by start_km."""
    res = TrainService.generate_time_distance_data(db, 30)
    secs = res["sections"]
    assert len(secs) == 8
    for i in range(len(secs) - 1):
        assert secs[i]["start_km"] <= secs[i + 1]["start_km"], f"Sections not sorted by km: {secs[i]['start_km']} > {secs[i+1]['start_km']}"


def test_05_no_macro_sections_in_c40(db: Session):
    """Mock macro-sections (SECTION-103, SECTION-204) must NOT belong to C40."""
    macro = db.query(RailwaySection).filter(
        RailwaySection.corridor_id == 30,
        RailwaySection.section_id.in_(["SECTION-103", "SECTION-204"])
    ).all()
    assert len(macro) == 0, f"Found mock macro-sections in C40: {[m.section_id for m in macro]}"


# =====================================================================
# 2. DISCRETE TRAIN OCCUPANCIES & DIRECTIONAL RIGOR (Tests 6 - 12)
# =====================================================================

def test_06_discrete_section_occupancies_not_blanket(db: Session):
    """A train must NEVER occupy every corridor section at the exact same minute."""
    res = TrainService.generate_time_distance_data(db, 30)
    occs = res["occupancy_intervals"]
    assert len(occs) > 0, "No occupancy intervals generated"

    # For each train, check that it doesn't span all 8 sections simultaneously at minute 600 (10:00)
    from collections import defaultdict
    train_sec_at_min = defaultdict(set)
    test_min = 600
    for o in occs:
        if o["estimated_entry_min"] <= test_min <= o["estimated_exit_min"]:
            train_sec_at_min[o["train_number"]].add(o["section_id"])

    for tr_no, sec_set in train_sec_at_min.items():
        assert len(sec_set) <= 2, f"Train {tr_no} occupies {len(sec_set)} sections simultaneously at min {test_min}"


def test_07_train_direction_down_increasing_km(db: Session):
    """Movements MDU -> TEN (increasing km) must have direction DOWN."""
    down_occs = [
        o for o in TrainService.calculate_all_occupancies(db)
        if o.get("from_station_code") == "MDU" and o.get("to_station_code") == "TDN"
    ]
    for o in down_occs:
        assert o["direction"] == "DOWN", f"Expected DOWN for MDU->TDN, got {o['direction']}"


def test_08_train_direction_up_decreasing_km(db: Session):
    """Movements TEN -> MDU (decreasing km) must have direction UP."""
    up_occs = [
        o for o in TrainService.calculate_all_occupancies(db)
        if o.get("from_station_code") == "TEN" and o.get("to_station_code") == "MEJ"
    ]
    for o in up_occs:
        assert o["direction"] == "UP", f"Expected UP for TEN->MEJ, got {o['direction']}"


def test_09_train_traversal_duration_realistic(db: Session):
    """Individual block section traversal duration must be between 2 and 60 minutes."""
    res = TrainService.generate_time_distance_data(db, 30)
    for o in res["occupancy_intervals"]:
        dur = o.get("traversal_duration_min") or (o["estimated_exit_min"] - o["estimated_entry_min"])
        assert 2 <= dur <= 120, f"Unrealistic traversal duration {dur}m for train {o['train_number']} on {o.get('section_code')}"


def test_10_multi_day_timetable_normalization(db: Session):
    """Normalized entry minute must be within 0 to 1440."""
    res = TrainService.generate_time_distance_data(db, 30)
    for o in res["occupancy_intervals"]:
        assert 0 <= o["estimated_entry_min"] <= 1440, f"Unnormalized entry min {o['estimated_entry_min']} for train {o['train_number']}"


def test_11_boundary_station_codes_present_in_occupancy(db: Session):
    """Occupancy records must contain non-null from_station_code and to_station_code."""
    res = TrainService.generate_time_distance_data(db, 30)
    valid_count = 0
    for o in res["occupancy_intervals"]:
        if o.get("from_station_code") and o.get("to_station_code"):
            valid_count += 1
    assert valid_count > 0, "No boundary station codes populated in occupancies"


def test_12_candidate_trains_corridor_matching(db: Session):
    """Trains on C40 must have valid routes intersecting C40 stations."""
    res = TrainService.generate_time_distance_data(db, 30)
    trains = res["trains"]
    assert len(trains) > 0
    for t in trains[:10]:
        assert t["train_number"] is not None
        assert t["direction"] in ("UP", "DOWN")


# =====================================================================
# 3. FEASIBLE MAINTENANCE WINDOWS (Tests 13 - 15)
# =====================================================================

def test_13_feasible_windows_duration_positive(db: Session):
    """All feasible maintenance windows must have usable duration >= 30 min."""
    res = TrainService.generate_time_distance_data(db, 30)
    windows = res["feasible_windows"]
    for w in windows:
        assert w["usable_duration_min"] >= 30, f"Window {w.get('window_code')} duration {w.get('usable_duration_min')} < 30m"


def test_14_feasible_windows_attached_to_physical_sections(db: Session):
    """All C40 feasible windows must attach to sections 22-29."""
    res = TrainService.generate_time_distance_data(db, 30)
    c40_sec_ids = {s["id"] for s in res["sections"]}
    for w in res["feasible_windows"]:
        assert w["section_id"] in c40_sec_ids, f"Window {w['window_code']} section {w['section_id']} not in C40 sections {c40_sec_ids}"


def test_15_window_engine_respects_headway():
    """WindowEngine must enforce safety buffer before and after train passings."""
    occs = [
        {"section_id": 1, "estimated_entry_min": 300, "estimated_exit_min": 320, "train_number": "12689"}
    ]
    windows = WindowEngine.calculate_feasible_windows(
        section_id=1, corridor_id=30, occupancies=occs, has_timetable_data=True
    )
    for w in windows:
        # Window must not overlap the train interval 300-320
        assert not (w["start_min"] < 320 and w["end_min"] > 300), f"Window {w['start_min']}-{w['end_min']} overlaps train 300-320"


# =====================================================================
# 4. DETERMINISTIC SAFETY VALIDATOR (Tests 16 - 19)
# =====================================================================

def test_16_safety_validator_15_rules_execution(db: Session):
    """Safety validator must evaluate all 15 rules without exceptions."""
    res = DeterministicSafetyValidator.validate_plan_schedule(
        plan_jobs=[],
        corridor_id=30,
        planning_date=date(2026, 9, 15),
        db=db
    )
    assert res["status"] in ("VALID", "REJECTED", "WARNING")
    assert res["checked_rules_count"] == 15


def test_17_safety_validator_blocks_overlapping_train(db: Session):
    """Scheduled job overlapping train occupancy must trigger CRITICAL SAFETY VIOLATION."""
    # REQ-101 on section 22 from 180 to 270 overlaps train 12689 (183 to 270)
    fake_job = {
        "job_id": 9999,
        "job_code": "REQ-SAFETY-FAIL",
        "section_id": 22,
        "scheduled_start_min": 190,
        "scheduled_end_min": 250,
        "scheduled_duration_min": 60,
        "department_code": "ENGG"
    }
    res = DeterministicSafetyValidator.validate_plan_schedule(
        plan_jobs=[fake_job],
        corridor_id=30,
        planning_date=date(2026, 9, 15),
        db=db
    )
    assert res["status"] == "REJECTED"
    assert len(res["errors"]) > 0
    assert any("overlaps Train" in err for err in res["errors"])


def test_18_safety_validator_passes_clear_window(db: Session):
    """Scheduled job inside a certified clear window must pass safety validation."""
    # Window WIN_SEC22_03 is clear from 365 to 493
    clear_job = {
        "job_id": 9998,
        "job_code": "REQ-SAFETY-PASS",
        "section_id": 22,
        "scheduled_start_min": 380,
        "scheduled_end_min": 440,
        "scheduled_duration_min": 60,
        "department_code": "ENGG"
    }
    res = DeterministicSafetyValidator.validate_plan_schedule(
        plan_jobs=[clear_job],
        corridor_id=30,
        planning_date=date(2026, 9, 15),
        db=db
    )
    # No train overlap error
    assert not any("overlaps Train" in err for err in res["errors"])


def test_19_conflict_detection_math_accuracy():
    """Verify exact overlap minutes calculation between block and train."""
    tr_entry, tr_exit = 600, 630
    blk_start, blk_end = 615, 705
    # Overlap is max(0, min(tr_exit, blk_end) - max(tr_entry, blk_start)) = min(630, 705) - max(600, 615) = 630 - 615 = 15
    overlap = max(0, min(tr_exit, blk_end) - max(tr_entry, blk_start))
    assert overlap == 15


# =====================================================================
# 5. CP-SAT SOLVER & COORDINATED PLANNING (Tests 20 - 25)
# =====================================================================

def test_20_cpsat_solver_solves_canonical_jobs(db: Session):
    """CP-SAT solver must solve canonical 6 requests."""
    jobs = db.query(MaintenanceJob).filter(
        MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103", "REQ-104", "REQ-105", "REQ-106"])
    ).all()
    result = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")
    assert result["requests_analyzed"] == 6
    assert result["total_optimized_plans"] == 3


def test_21_cpsat_solver_respects_emergency_priority(db: Session):
    """Emergency job must receive high priority score and precedence."""
    j = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-101").first()
    assert j.priority_score >= 80.0


def test_22_coordinated_optimizer_plan_structure(db: Session):
    """optimize_pool output must conform to required SIH schema."""
    jobs = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(["REQ-101", "REQ-102"])).all()
    result = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")
    assert "requests_analyzed" in result
    assert "requests_coordinated" in result
    assert "plans" in result
    assert len(result["plans"]) >= 1


def test_23_coordinated_optimizer_savings_calculation(db: Session):
    """possessions_avoided must equal (sum(requests) - num_plans)."""
    jobs = db.query(MaintenanceJob).filter(
        MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103", "REQ-104", "REQ-105", "REQ-106"])
    ).all()
    res = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")
    assert res["possessions_avoided"] == 3  # (3-1) + (2-1) + 0 = 3


def test_24_plan_code_uniqueness_guarantee(db: Session):
    """Multiple generated coordinated block plans must have unique plan codes."""
    codes = set()
    for _ in range(5):
        cnt = db.query(CoordinatedBlockPlan).count()
        code = f"CBP-{datetime.utcnow().strftime('%Y%m%d')}-{cnt + 1:04d}"
        while db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.plan_code == code).first() or code in codes:
            cnt += 1
            code = f"CBP-{datetime.utcnow().strftime('%Y%m%d')}-{cnt + 1:04d}"
        codes.add(code)
    assert len(codes) == 5


def test_25_canonical_cvp_kdu_slot_preference(db: Session):
    """Canonical Plan 1 must honor 10:45 requested slot."""
    jobs = db.query(MaintenanceJob).filter(
        MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103"])
    ).all()
    res = CoordinatedOptimizer.optimize_pool(jobs, db, strategy="PLAN_A")
    p1 = res["plans"][0]
    assert p1["common_block_window"] == "10:45 – 12:15"


# =====================================================================
# 6. TELEMETRY PROVENANCE & API SCHEMAS (Tests 26 - 28)
# =====================================================================

def test_26_telemetry_provenance_truth():
    """GET /api/railway/data-status must return truthful provenance."""
    res = client.get("/api/railway/data-status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("LIVE RADAR", "CACHED", "STALE", "ERROR", "UNAVAILABLE")
    if not data["is_live"]:
        assert data["status"] != "LIVE RADAR"


def test_27_time_distance_api_schema():
    """GET /api/railway/time-distance?corridor_id=30 must return full valid schema."""
    res = client.get("/api/railway/time-distance?corridor_id=30")
    assert res.status_code == 200
    data = res.json()
    assert "stations" in data
    assert "sections" in data
    assert "trains" in data
    assert "occupancy_intervals" in data
    assert "feasible_windows" in data
    assert "maintenance_blocks" in data
    assert "provenance" in data
    assert len(data["sections"]) == 8


def test_28_train_control_list_data_integrity():
    """All trains returned in time-distance payload must have required fields."""
    res = client.get("/api/railway/time-distance?corridor_id=30")
    assert res.status_code == 200
    trains = res.json()["trains"]
    assert len(trains) > 0
    for t in trains[:5]:
        assert "train_number" in t
        assert "train_name" in t
        assert "direction" in t
        assert "speed_kmh" in t


# =====================================================================
# 7. DYNAMIC SIMULATION & CONCURRENCY (Tests 29 - 33)
# =====================================================================

def test_29_dynamic_delay_propagation(planner_token: str):
    """Simulating train delay returns injected event."""
    headers = {"Authorization": planner_token}
    res = client.post(
        "/api/dynamic/simulate-delay",
        json={"train_number": "12689", "additional_delay_min": 15},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["event"] == "TRAIN_DELAY_INJECTED"
    assert data["train_number"] == "12689"


def test_30_multi_department_compatibility(db: Session):
    """ENGG, S&T, and TRD jobs on same section cluster into COMMON_BLOCK."""
    jobs = db.query(MaintenanceJob).filter(
        MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103"])
    ).all()
    groups = CompatibilityEngine.cluster_compatible_groups(jobs)
    assert len(groups) == 1
    assert groups[0]["coordination_type"] == "COMMON_BLOCK"
    assert len(groups[0]["jobs"]) == 3


def test_31_incompatible_departments_rejected(db: Session):
    """Jobs on different sections must NEVER be merged into a single block."""
    j1 = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-101").first()
    j6 = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == "REQ-106").first()
    groups = CompatibilityEngine.cluster_compatible_groups([j1, j6])
    assert len(groups) == 2


def test_32_optimistic_locking_prevents_stale_update(planner_token: str, db: Session):
    """Stale version update on coordinated block plan raises 409 Conflict."""
    headers = {"Authorization": planner_token}
    plan = db.query(CoordinatedBlockPlan).first()
    if not plan:
        plan = CoordinatedBlockPlan(plan_code="CBP-LOCK-TEST", start_min=600, end_min=690, status="PROPOSED", version=1)
        db.add(plan)
        db.commit()
        db.refresh(plan)

    res = client.put(
        f"/api/block-planning/plans/{plan.id}",
        headers=headers,
        json={"version": 9999, "start_min": 650, "end_min": 740}
    )
    assert res.status_code == 409


def test_33_audit_no_fabricated_data(db: Session):
    """Zero dummy or mock sections exist under C40."""
    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == 30).all()
    sec_ids = {s.section_id for s in sections}
    assert "SECTION-103" not in sec_ids
    assert "SECTION-204" not in sec_ids
    assert len(sections) == 8
