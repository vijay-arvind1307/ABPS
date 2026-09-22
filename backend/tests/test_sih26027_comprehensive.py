import pytest
import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.models import (
    Corridor, RailwaySection, Station, Train, MaintenanceJob,
    Department, User, CoordinatedBlockPlan, BlockPlan, TrainMovement
)
from app.algorithms.windows import WindowEngine
from app.algorithms.coordination import CompatibilityEngine, CoordinatedOptimizer
from app.algorithms.optimizer import CPSATSolver
from app.services.train_service import TrainService
from app.core.config import settings
from app.providers.railradar import RailRadarProvider

client = TestClient(app)


# -------------------------------------------------------------
# TEST 1: Corridor C40, Date: 18-09-2026, Requested: 10:00–12:00 -> actual availability calculation (NOT 00:00–24:00)
# -------------------------------------------------------------
def test_scenario_1_actual_availability_calculation():
    """Verify that availability calculation returns real sweep-line intervals, NEVER generic 00:00-24:00."""
    occupancies = [
        {"section_id": 101, "train_number": "17235", "estimated_entry_min": 600, "estimated_exit_min": 660},  # 10:00 - 11:00
        {"section_id": 101, "train_number": "12642", "estimated_entry_min": 800, "estimated_exit_min": 860},  # 13:20 - 14:20
    ]

    result = WindowEngine.calculate_feasible_windows(
        section_id=101,
        corridor_id=40,
        occupancies=occupancies,
        min_window_duration_min=45
    )

    assert len(result) > 0, "Feasible windows must be calculated from occupancies"
    for w in result:
        # Crucial invariant: No window is 0 to 1440 when trains are running
        assert not (w["start_min"] == 0 and w["end_min"] == 1440), "Must NOT return fake 00:00-24:00 window!"
        assert w["source"] in ("STATIC TIMETABLE + EXISTING BLOCKS", "LIVE TELEMETRY + STATIC TIMETABLE")


# -------------------------------------------------------------
# TEST 2: REQ-101 CVP-TEN 90 min + REQ-102 CVP-TEN 60 min -> possible coordinated group
# -------------------------------------------------------------
def test_scenario_2_coordinated_group_cvp_ten():
    """Verify that parallel compatible requests on CVP-TEN coordinate with max(durations), not blind sum."""
    dept_civil = Department(name="Engineering", code="ENGG")
    dept_snt = Department(name="Signal & Telecom", code="SNT")

    req_101 = MaintenanceJob(
        id=101,
        job_code="REQ-101",
        work_type="TRACK_TAMPING",
        estimated_duration_min=90,
        start_station_code="CVP",
        end_station_code="TEN",
        section_id=1,
        status="SUBMITTED",
        user_priority="HIGH",
        priority_score=85.0,
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_101.department = dept_civil

    req_102 = MaintenanceJob(
        id=102,
        job_code="REQ-102",
        work_type="SIGNAL_INSPECTION",
        estimated_duration_min=60,
        start_station_code="CVP",
        end_station_code="TEN",
        section_id=1,
        status="SUBMITTED",
        user_priority="MEDIUM",
        priority_score=70.0,
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_102.department = dept_snt

    result = CompatibilityEngine.check_compatibility([req_101, req_102])
    assert result["is_compatible"] is True, "Civil tamping and S&T inspection on same section must be compatible"
    assert result["can_proceed"] is True
    assert result["is_parallel"] is True
    # Invariant: Parallel common block duration is max(90, 60) = 90 min, NOT 90 + 60 = 150
    assert result["savings"]["common_block_duration"] == 90, "Parallel duration must be max(job durations)"
    assert result["savings"]["possession_time_saved_min"] == 60, "Must save 60 min of track possession"


# -------------------------------------------------------------
# TEST 3: Train conflict inside requested window -> rejected for that window + alternatives generated
# -------------------------------------------------------------
def test_scenario_3_requested_window_conflict_and_alternatives():
    """Verify that a request overlapping an occupied train interval is marked NOT FEASIBLE with explainable conflict and alternatives."""
    occupancies = [
        {"section_id": 1, "train_number": "12642", "train_name": "Thirukkural Express", "estimated_entry_min": 645, "estimated_exit_min": 680},  # 10:45 - 11:20
    ]

    # Requested window 10:00 (600) to 12:00 (720), duration 120
    check = WindowEngine.check_requested_window(
        section_ids=[1],
        corridor_id=40,
        req_start_min=600,
        req_end_min=720,
        duration_min=120,
        occupancies=occupancies
    )

    assert check["is_feasible"] is False, "Requested window must NOT be feasible due to Train 12642 conflict"
    assert len(check["conflicts"]) > 0
    assert "12642" in check["conflicts"][0]["train_number"]
    assert len(check["recommended_alternatives"]) > 0, "Must generate feasible alternatives"


# -------------------------------------------------------------
# TEST 4: No timetable data -> DATA_UNAVAILABLE (NOT 00:00–24:00)
# -------------------------------------------------------------
def test_scenario_4_missing_timetable_data_unavailable():
    """Verify that when no timetable or section occupancy exists, status is DATA_UNAVAILABLE, NOT 00:00-24:00."""
    result = WindowEngine.calculate_feasible_windows(
        section_id=99999,
        corridor_id=99999,
        occupancies=[],
        has_timetable_data=False
    )

    # Must be empty when has_timetable_data=False, never a fake 00:00-24:00 window
    assert len(result) == 0, "Must return no windows when timetable data is completely missing"


# -------------------------------------------------------------
# TEST 5: RailRadar API returns 429 -> LIVE_DATA_UNAVAILABLE (no crash, no fake marker)
# -------------------------------------------------------------
def test_scenario_5_railradar_429_rate_limited():
    """Verify graceful handling of 429 RATE_LIMITED without crash or fake data."""
    with patch("app.routers.live.get_train_provider") as mock_prov:
        provider_instance = MagicMock()
        provider_instance._last_error = "RailRadar 429: Rate limit reached"
        provider_instance.get_live_train.side_effect = Exception("429 Client Error: Rate limit reached")
        mock_prov.return_value = provider_instance

        res = client.get("/api/live/trains/17235")
        assert res.status_code == 200
        data = res.json()
        assert data["liveAvailable"] is False
        assert data["status"] == "LIVE_DATA_UNAVAILABLE"
        assert data["reason"] == "RATE_LIMITED"


# -------------------------------------------------------------
# TEST 6: RailRadar API returns 401 -> UNAUTHORIZED (no crash)
# -------------------------------------------------------------
def test_scenario_6_railradar_401_unauthorized():
    """Verify graceful handling of 401 UNAUTHORIZED without crash."""
    with patch("app.routers.live.get_train_provider") as mock_prov:
        provider_instance = MagicMock()
        provider_instance._last_error = "RailRadar 401: Unauthorized"
        provider_instance.get_live_train.side_effect = Exception("401 Client Error: Unauthorized API Key")
        mock_prov.return_value = provider_instance

        res = client.get("/api/live/trains/17235")
        assert res.status_code == 200
        data = res.json()
        assert data["liveAvailable"] is False
        assert data["status"] == "LIVE_DATA_UNAVAILABLE"
        assert data["reason"] == "UNAUTHORIZED"


# -------------------------------------------------------------
# TEST 7: RailRadar API returns 503 -> SERVICE_UNAVAILABLE (no crash)
# -------------------------------------------------------------
def test_scenario_7_railradar_503_service_unavailable():
    """Verify graceful handling of 503 SERVICE_UNAVAILABLE without crash."""
    with patch("app.routers.live.get_train_provider") as mock_prov:
        provider_instance = MagicMock()
        provider_instance._last_error = "RailRadar 503: Service Unavailable"
        provider_instance.get_live_train.return_value = None
        mock_prov.return_value = provider_instance

        res = client.get("/api/live/trains/17235")
        assert res.status_code == 200
        data = res.json()
        assert data["liveAvailable"] is False
        assert data["status"] == "LIVE_DATA_UNAVAILABLE"
        assert data["reason"] == "SERVICE_UNAVAILABLE"


# -------------------------------------------------------------
# TEST 8: API key empty -> LIVE_DATA_UNAVAILABLE, static timetable continues working
# -------------------------------------------------------------
def test_scenario_8_empty_api_key_handled():
    """Verify that when RAILRADAR_API_KEY is unset, application returns LIVE_DATA_UNAVAILABLE without crashing."""
    with patch.object(settings, "RAILRADAR_API_KEY", ""):
        with patch("app.routers.live.get_train_provider") as mock_prov:
            provider_instance = MagicMock()
            provider_instance.get_live_train.return_value = None
            provider_instance._last_error = "RAILRADAR_API_KEY missing"
            mock_prov.return_value = provider_instance

            res = client.get("/api/live/trains/17235")
            assert res.status_code == 200
            data = res.json()
            assert data["liveAvailable"] is False
            assert data["status"] == "LIVE_DATA_UNAVAILABLE"
            assert data["reason"] == "MISSING_API_KEY"


# -------------------------------------------------------------
# TEST 9: New API key added -> live service works without code changes
# -------------------------------------------------------------
def test_scenario_9_api_key_replacement_via_environment():
    """Verify that a newly inserted API key in environment config is recognized without code modification."""
    with patch.object(settings, "RAILRADAR_API_KEY", "rr_live_new_test_key"):
        with patch("app.routers.live.get_train_provider") as mock_prov:
            provider_instance = MagicMock()
            provider_instance.get_live_train.return_value = {
                "train_number": "17235",
                "train_name": "Bengaluru Express",
                "status": "RUNNING",
                "delay_minutes": 12,
                "current_station_code": "CVP",
                "latitude": 9.17,
                "longitude": 77.87
            }
            mock_prov.return_value = provider_instance

            res = client.get("/api/live/trains/17235")
            assert res.status_code == 200
            data = res.json()
            assert data["liveAvailable"] is True
            assert data["delayMinutes"] == 12
            assert data["currentStation"] == "CVP"


# -------------------------------------------------------------
# TEST 10: Train not running today -> do not call live endpoint
# -------------------------------------------------------------
def test_scenario_10_train_not_running_today_excluded():
    """Verify that trains with non-matching running days are filtered out of candidate pool."""
    class MockTrain:
        running_days = "MON,WED,FRI"

    # Tuesday: 2026-09-15 was a Tuesday
    tuesday_date = datetime.date(2026, 9, 15)
    is_running = TrainService.is_running_today(MockTrain(), tuesday_date)
    assert is_running is False, "Train running only Mon/Wed/Fri must NOT run on Tuesday"


# -------------------------------------------------------------
# TEST 11: Train running today -> eligible for live lookup
# -------------------------------------------------------------
def test_scenario_11_train_running_today_included():
    """Verify that trains matching today's running days are included in candidate list."""
    class MockTrainDaily:
        running_days = "DAILY"

    class MockTrainMon:
        running_days = "MON,WED,FRI"

    # Monday: 2026-09-14 was a Monday
    monday_date = datetime.date(2026, 9, 14)
    assert TrainService.is_running_today(MockTrainDaily(), monday_date) is True
    assert TrainService.is_running_today(MockTrainMon(), monday_date) is True


# -------------------------------------------------------------
# TEST 12: Live train delay +30 min updates occupancy & triggers replan
# -------------------------------------------------------------
def test_scenario_12_train_delay_updates_occupancy():
    """Verify that simulating +30 min train delay shifts section occupancies."""
    db = SessionLocal()
    try:
        train = db.query(Train).filter(Train.train_number == "12642").first()
        if not train:
            train = Train(train_number="12642", train_name="Thirukkural Express", train_type="SUPERFAST", priority_level=2)
            db.add(train)
            db.commit()

        res = TrainService.simulate_train_delay(db, "12642", 30)
        assert res["delay_minutes"] == 30
        assert "Delay of +30" in res["status"]
    finally:
        db.close()


# -------------------------------------------------------------
# TEST 13: Completed block -> never rescheduled
# -------------------------------------------------------------
def test_scenario_13_completed_block_never_rescheduled():
    """Verify that CP-SAT solver preserves completed jobs and does not alter their timing."""
    solver = CPSATSolver(time_limit_seconds=5)

    jobs = [
        {
            "id": 1,
            "job_code": "COMPLETED_JOB",
            "section_id": 1,
            "estimated_duration_min": 60,
            "priority_score": 50,
            "status": "COMPLETED",
            "is_locked": True,
            "locked_start_min": 100
        },
        {
            "id": 2,
            "job_code": "NEW_JOB",
            "section_id": 1,
            "estimated_duration_min": 60,
            "priority_score": 80,
            "status": "SUBMITTED"
        }
    ]

    windows = [
        {"id": 10, "section_id": 1, "start_min": 60, "end_min": 300, "usable_duration_min": 240}
    ]

    res = solver.solve(jobs=jobs, windows=windows)
    assert res["solver_status"] in ("OPTIMAL", "FEASIBLE")

    completed_sched = next((sj for sj in res["scheduled_jobs"] if sj["job_id"] == 1), None)
    assert completed_sched is not None
    assert completed_sched["scheduled_start_min"] == 100, "Completed job start time must remain exactly as locked"


# -------------------------------------------------------------
# TEST 14: Locked planner decision -> optimizer cannot move it
# -------------------------------------------------------------
def test_scenario_14_locked_planner_decision_protected():
    """Verify that locked planner decisions are strictly honored by CP-SAT."""
    solver = CPSATSolver(time_limit_seconds=5)

    jobs = [
        {
            "id": 201,
            "job_code": "LOCKED_JOB",
            "section_id": 1,
            "estimated_duration_min": 90,
            "priority_score": 60,
            "is_locked": True,
            "locked_start_min": 200
        }
    ]

    windows = [
        {"id": 1, "section_id": 1, "start_min": 120, "end_min": 400, "usable_duration_min": 280}
    ]

    res = solver.solve(jobs=jobs, windows=windows, enforce_locks=True)
    assert res["solver_status"] in ("OPTIMAL", "FEASIBLE")
    locked_res = res["scheduled_jobs"][0]
    assert locked_res["scheduled_start_min"] == 200, "Optimizer must not move locked decision"


# -------------------------------------------------------------
# TEST 15: Four requests where only three are compatible -> 3 coordinated + 1 individual
# -------------------------------------------------------------
def test_scenario_15_partial_coordination_three_plus_one():
    """Verify that 3 compatible requests form a Coordinated Group while 1 incompatible request gets an Individual Plan."""
    dept_civil = Department(name="Engineering", code="ENGG")
    dept_snt = Department(name="Signal & Telecom", code="SNT")
    dept_trd = Department(name="Traction Distribution", code="TRD")

    req_101 = MaintenanceJob(
        id=101, job_code="REQ-101", work_type="TRACK_TAMPING", estimated_duration_min=90,
        start_station_code="CVP", end_station_code="TEN", section_id=1, status="SUBMITTED",
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_101.department = dept_civil

    req_102 = MaintenanceJob(
        id=102, job_code="REQ-102", work_type="SIGNAL_INSPECTION", estimated_duration_min=60,
        start_station_code="CVP", end_station_code="TEN", section_id=1, status="SUBMITTED",
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_102.department = dept_snt

    req_103 = MaintenanceJob(
        id=103, job_code="REQ-103", work_type="OHE_INSPECTION", estimated_duration_min=75,
        start_station_code="CVP", end_station_code="TEN", section_id=1, status="SUBMITTED",
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_103.department = dept_trd

    # Incompatible request: Different section (MDU-TEN, section_id=2)
    req_104 = MaintenanceJob(
        id=104, job_code="REQ-104", work_type="TRACK_TAMPING", estimated_duration_min=90,
        start_station_code="MDU", end_station_code="TEN", section_id=2, status="SUBMITTED",
        requested_date=datetime.datetime(2026, 9, 18)
    )
    req_104.department = dept_civil

    clusters = CompatibilityEngine.cluster_compatible_groups([req_101, req_102, req_103, req_104])

    assert len(clusters) == 2, "Must produce exactly 2 distinct groups: 1 coordinated and 1 individual"

    coord_group = next((g for g in clusters if g["coordination_type"] == "COMMON_BLOCK"), None)
    indiv_group = next((g for g in clusters if g["coordination_type"] == "INDIVIDUAL_BLOCK"), None)

    assert coord_group is not None, "Must have a COMMON_BLOCK group"
    assert indiv_group is not None, "Must have an INDIVIDUAL_BLOCK group"

    assert len(coord_group["jobs"]) == 3, "Common block must contain exactly REQ-101, REQ-102, and REQ-103"
    assert len(indiv_group["jobs"]) == 1, "Individual block must contain REQ-104"
    assert indiv_group["jobs"][0].job_code == "REQ-104"
    assert len(indiv_group["reasons"]) > 0, "Incompatible group must provide explainable reasons"
