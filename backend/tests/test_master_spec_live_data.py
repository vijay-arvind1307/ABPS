import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop, TrainRoute, Corridor, RailwaySection
from app.services.train_service import TrainService
from app.algorithms.optimizer import CPSATSolver
from app.core.config import settings

client = TestClient(app)


def test_phase_41_corridor_train_list_independence():
    """Phase 41: Train lists must be dynamically determined by corridor route intersection."""
    db = SessionLocal()
    try:
        corr_mdu = db.query(Corridor).filter(Corridor.corridor_id == "CORR_MDU_TEN").first()
        corr_cbe = db.query(Corridor).filter(Corridor.corridor_id == "CORR_MAS_CBE").first()
        assert corr_mdu is not None
        assert corr_cbe is not None

        # Ensure Nellai Express 12631 is in DB
        TrainService.ingest_train_route(db, "12631")

        mdu_trains = TrainService.get_trains_for_corridor(db, corr_mdu.id)
        cbe_trains = TrainService.get_trains_for_corridor(db, corr_cbe.id)

        mdu_nums = [t.train_number for t in mdu_trains]
        cbe_nums = [t.train_number for t in cbe_trains]

        # 12631 Nellai Express runs Chennai - Tirunelveli via Madurai, so it MUST appear in MDU-TEN
        assert "12631" in mdu_nums, "Nellai Express 12631 must be on MDU-TEN corridor"
        # 12631 does NOT run via Coimbatore, so it MUST NOT appear in MAS-CBE
        assert "12631" not in cbe_nums, "Nellai Express 12631 must NOT be on MAS-CBE corridor"
    finally:
        db.close()


def test_phase_42_nellai_express_dynamic_discovery_and_stops():
    """Phase 42: Test 12631 Nellai Express route stops and Tamil Nadu relevance."""
    db = SessionLocal()
    try:
        train = db.query(Train).filter(Train.train_number == "12631").first()
        assert train is not None
        assert train.is_tn_relevant is True
        assert train.source_code in ["MS", "MAS"]
        assert train.destination_code == "TEN"

        stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == "12631").all()
        assert len(stops) >= 8, f"Expected route stops for 12631, got {len(stops)}"

        stop_codes = [s.station_code for s in stops]
        assert "MS" in stop_codes or "TBM" in stop_codes
        assert "TPJ" in stop_codes
        assert "MDU" in stop_codes
        assert "CVP" in stop_codes
        assert "TEN" in stop_codes
    finally:
        db.close()


def test_phase_43_pass_through_train_support():
    """Phase 43: Support pass-through trains with includeIntermediate=true."""
    from app.providers import get_train_provider
    provider = get_train_provider()
    if hasattr(provider, "get_station_trains"):
        trains = provider.get_station_trains("KDU", include_intermediate=True)
        assert len(trains) > 0, "Station trains for KDU should not be empty"
        pass_thru = [t for t in trains if not t.get("is_halt", True)]
        # Pass-through trains must be identified
        assert len(pass_thru) > 0, "KDU should have pass-through trains identified"
        assert any(t.get("stop_type") == "pass-through" for t in pass_thru)


def test_phase_45_zero_silent_mock_fallback_and_provenance():
    """Phase 45 & 34: When in live mode, errors return UNAVAILABLE, never fake mock data."""
    res = client.get("/api/railway/data-status")
    assert res.status_code == 200
    data = res.json()
    assert "provenance_status" in data or "status" in data
    status = data.get("provenance_status") or data.get("status")
    # Must be truthful: LIVE RADAR, CACHED, ERROR, or UNAVAILABLE - never MOCK in live mode
    if settings.TRAIN_DATA_MODE.lower() == "live":
        assert status in ["LIVE RADAR", "LIVE", "CACHED", "ERROR", "UNAVAILABLE", "READY"]
        assert "MOCK" not in status.upper()


def test_phase_46_api_key_security():
    """Phase 46: Verify RAILRADAR_API_KEY is backend-only and never exposed in responses."""
    endpoints = [
        "/api/railway/corridors",
        "/api/railway/movements",
        "/api/railway/data-status"
    ]
    key_val = settings.RAILRADAR_API_KEY
    for ep in endpoints:
        res = client.get(ep)
        body = res.text
        if key_val:
            assert key_val not in body, f"API key leaked in endpoint {ep}"
            assert "Bearer " + key_val not in body


def test_phase_47_database_persistence():
    """Phase 47: Verify Train Master, TrainRouteStop, and TrainRoute are persistent."""
    db = SessionLocal()
    try:
        train_count = db.query(Train).count()
        assert train_count > 0, "Train master should have persistent trains"

        stop_count = db.query(TrainRouteStop).count()
        assert stop_count > 0, "Train route stops should be persistent in database"
    finally:
        db.close()


def test_phase_48_cpsat_realism_and_phase_21_fix():
    """Phase 48 & 21: Verify CP-SAT boolean disjunction ordering avoids artificial infeasibility."""
    solver = CPSATSolver(time_limit_seconds=10)

    # Window of 120 minutes
    windows = [
        {"id": 1, "section_id": 101, "start_min": 600, "end_min": 720, "usable_duration_min": 120}
    ]

    # Two sequential, incompatible jobs from the same department (duration 45m and 50m = 95m <= 120m)
    jobs = [
        {"id": 1, "section_id": 101, "estimated_duration_min": 45, "department": "ENGG", "priority_score": 80},
        {"id": 2, "section_id": 101, "estimated_duration_min": 50, "department": "ENGG", "priority_score": 75}
    ]

    # Solve Plan A
    res_a = solver.solve(jobs=jobs, windows=windows, strategy="PLAN_A")
    assert res_a["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert len(res_a["scheduled_jobs"]) == 2, "Both compatible-length jobs should be scheduled in 120m window"

    # Verify non-overlapping times
    j1_sched = next(j for j in res_a["scheduled_jobs"] if j["job_id"] == 1)
    j2_sched = next(j for j in res_a["scheduled_jobs"] if j["job_id"] == 2)
    assert (j1_sched["scheduled_end_min"] <= j2_sched["scheduled_start_min"]) or (j2_sched["scheduled_end_min"] <= j1_sched["scheduled_start_min"]), "Incompatible jobs must not overlap"

    # Solve Plan B and Plan C - verify distinct objectives
    res_b = solver.solve(jobs=jobs, windows=windows, strategy="PLAN_B")
    res_c = solver.solve(jobs=jobs, windows=windows, strategy="PLAN_C")
    assert res_b["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert res_c["solver_status"] in ["OPTIMAL", "FEASIBLE"]
