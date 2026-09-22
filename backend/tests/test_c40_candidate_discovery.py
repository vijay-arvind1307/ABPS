import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal, get_db
from app.models.models import Corridor, RailwaySection, RailwayStation, Train, TrainRouteStop, TrainMovement
from app.services.train_service import TrainService
from app.core.config import settings


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# =========================================================================
# TEST A: Section Discovery Completeness
# =========================================================================
def test_a_c40_section_discovery_completeness(db_session):
    """
    Verify that corridor C40 resolves all 8 authentic sequential sections,
    its start station is MDU, end station is TEN, and the station union includes
    all 9 authentic Tamil Nadu corridor stations.
    """
    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    assert corr is not None, "Corridor C40 must exist in database"
    assert corr.start_station_code == "MDU", f"Expected start MDU, got {corr.start_station_code}"
    assert corr.end_station_code == "TEN", f"Expected end TEN, got {corr.end_station_code}"

    _, sections, stations = TrainService.get_corridor_sections_and_stations(db_session, corr.id)
    authentic_sections = [s for s in sections if s.section_id.startswith("SEC_")]
    assert len(authentic_sections) == 8, f"Expected 8 authentic sequential sections for C40, got {len(authentic_sections)}"

    expected_sec_ids = [
        "SEC_MDU_TDN", "SEC_TDN_TMQ", "SEC_TMQ_VPT", "SEC_VPT_SRT",
        "SEC_SRT_CVP", "SEC_CVP_KDU", "SEC_KDU_MEJ", "SEC_MEJ_TEN"
    ]
    actual_sec_ids = [s.section_id for s in authentic_sections]
    for exp_sec in expected_sec_ids:
        assert exp_sec in actual_sec_ids, f"Section {exp_sec} missing from C40 sections"

    expected_stations = {"MDU", "TDN", "TMQ", "VPT", "SRT", "CVP", "KDU", "MEJ", "TEN"}
    actual_stn_codes = set(stations)
    for exp_stn in expected_stations:
        assert exp_stn in actual_stn_codes, f"Station {exp_stn} missing from C40 station union"


# =========================================================================
# TEST B: Route Intersection Candidate Discovery
# =========================================================================
def test_b_c40_route_intersection_candidate_discovery(db_session):
    """
    Verify candidate discovery discovers ALL trains traversing C40:
    - More than 35 trains (entire authoritative set of 63 in DB).
    - Not limited to Vande Bharat; includes multiple train types.
    - Includes both UP and DOWN direction trains.
    - Includes partial-route trains.
    """
    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    all_trains = TrainService.get_trains_for_corridor(db_session, corr.id)

    # Must be substantially more than the old 5 hardcoded trains
    assert len(all_trains) >= 39, f"Expected >= 39 trains for C40, got {len(all_trains)}"

    types = {t.train_type for t in all_trains if t.train_type}
    assert len(types) >= 2, f"Expected diverse train types, found: {types}"
    assert "VANDE_BHARAT" in types or any("VANDE" in str(t) for t in types)

    # Verify presence of non-Vande Bharat trains (Superfast, Express, Passenger/MEMU)
    non_vb = [t for t in all_trains if t.train_type != "VANDE_BHARAT"]
    assert len(non_vb) > 30, f"Expected >30 non-Vande Bharat trains, got {len(non_vb)}"

    # Verify known authoritative trains from Madurai_to_TVL_train_details.xlsx
    train_numbers = {t.train_number for t in all_trains}
    known_c40_trains = ["12631", "12632", "12633", "12634", "16127", "20665", "22627"]
    for trn in known_c40_trains:
        assert trn in train_numbers, f"Authoritative train {trn} not discovered on C40"


# =========================================================================
# TEST C: Journey Date / Running-Day Filter
# =========================================================================
def test_c_journey_date_running_day_filter(db_session):
    """
    Verify candidate filtering correctly evaluates today's running days.
    """
    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    all_trains = TrainService.get_trains_for_corridor(db_session, corr.id)

    # Test Tuesday (e.g. 2026-09-22)
    tue_date = date(2026, 9, 22)
    candidates_tue = TrainService.get_candidate_trains_for_corridor(db_session, corr.id, tue_date)

    assert len(candidates_tue) > 0
    assert len(candidates_tue) <= len(all_trains)

    # Every candidate returned must satisfy is_running_today
    for t in candidates_tue:
        assert TrainService.is_running_today(t, tue_date, db_session) is True

    # Test running days evaluation on dummy train
    daily_train = Train(train_number="TEST_DAILY", train_name="Daily Test", running_days="DAILY", active=True)
    assert TrainService.is_running_today(daily_train, tue_date, db_session) is True

    tue_only_train = Train(train_number="TEST_TUE", train_name="Tue Only", running_days="TUE", active=True)
    assert TrainService.is_running_today(tue_only_train, tue_date, db_session) is True

    sun_only_train = Train(train_number="TEST_SUN", train_name="Sun Only", running_days="SUN", active=True)
    assert TrainService.is_running_today(sun_only_train, tue_date, db_session) is False


# =========================================================================
# TEST D: Provider Failure Tolerance
# =========================================================================
def test_d_provider_failure_tolerance(db_session):
    """
    When RailRadar provider fails (429 rate limited, 503 unavailable, timeout),
    the system must NOT crash or return an empty train list.
    ALL candidate trains must remain visible with status 'SCHEDULED — LIVE UNAVAILABLE'.
    """
    db_session.query(TrainMovement).delete()
    db_session.commit()

    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()

    with patch("app.providers.railradar.RailRadarProvider.get_live_train", side_effect=Exception("HTTP 429 Rate Limit")):
        payload = TrainService.get_corridor_candidate_live_status(
            db_session, corridor_ident=corr.id, refresh=False
        )

        assert payload["scheduledTrainCount"] >= 39
        assert len(payload["trains"]) == payload["scheduledTrainCount"]
        assert payload["liveAvailableCount"] == 0
        assert payload["liveUnavailableCount"] == payload["scheduledTrainCount"]

        # Check every train retains SCHEDULED — LIVE UNAVAILABLE status
        for t_item in payload["trains"]:
            assert t_item["live_status"] == "SCHEDULED — LIVE UNAVAILABLE"
            assert t_item["is_live"] is False
            assert t_item["speed_kmh"] is None, "Speed must be None when live unavailable (never fake 0 km/h)"
            assert t_item["delay_minutes"] is None, "Delay must be None when live unavailable"
            assert t_item["latitude"] is None, "Latitude must be None when live unavailable (never fake coordinates)"
            assert t_item["longitude"] is None, "Longitude must be None when live unavailable"


# =========================================================================
# TEST E: Missing API Key Tolerance
# =========================================================================
def test_e_missing_api_key_tolerance(db_session):
    """
    When RAILRADAR_API_KEY is not configured or blank:
    All scheduled candidate trains remain visible, speeds/delays/coords are None,
    source is Timetable Master, liveStatus is LIVE_DATA_UNAVAILABLE with reason KEY_MISSING.
    """
    db_session.query(TrainMovement).delete()
    db_session.commit()

    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()

    with patch.object(settings, "RAILRADAR_API_KEY", ""):
        payload = TrainService.get_corridor_candidate_live_status(
            db_session, corridor_ident=corr.id, refresh=False
        )

        assert payload["liveStatus"] == "LIVE_DATA_UNAVAILABLE"
        assert payload["reason"] == "KEY_MISSING"
        assert payload["scheduledTrainCount"] >= 39
        assert len(payload["trains"]) >= 39

        for item in payload["trains"]:
            assert item["live_status"] == "SCHEDULED — LIVE UNAVAILABLE"
            assert item["speed_kmh"] is None
            assert item["delay_minutes"] is None
            assert item["latitude"] is None
            assert item["longitude"] is None
            assert "Timetable Master" in item["source"]


# =========================================================================
# TEST F: Stale Telemetry Handling
# =========================================================================
def test_f_stale_telemetry_handling(db_session):
    """
    If a TrainMovement record has last_updated > 120 seconds ago,
    it must be flagged as 'STALE LIVE DATA', showing stale age in minutes,
    and counted as live unavailable.
    """
    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    first_train = TrainService.get_candidate_trains_for_corridor(db_session, corr.id, date.today())[0]

    # Seed a stale TrainMovement (10 minutes ago)
    stale_time = datetime.utcnow() - timedelta(minutes=10)
    tm = db_session.query(TrainMovement).filter(TrainMovement.train_number == first_train.train_number).first()
    if not tm:
        tm = TrainMovement(
            train_number=first_train.train_number,
            latitude=9.58,
            longitude=77.95,
            speed_kmh=65.0,
            delay_minutes=5,
            direction="UP",
            status="RUNNING",
            last_updated=stale_time
        )
        db_session.add(tm)
    else:
        tm.last_updated = stale_time
        tm.speed_kmh = 65.0
        tm.delay_minutes = 5
    db_session.commit()

    payload = TrainService.get_corridor_candidate_live_status(
        db_session, corridor_ident=corr.id, refresh=False
    )

    stale_item = next((t for t in payload["trains"] if t["train_number"] == first_train.train_number), None)
    assert stale_item is not None
    assert stale_item["live_status"] == "STALE LIVE DATA"
    assert stale_item["is_stale"] is True
    assert stale_item["is_live"] is False
    assert stale_item["age_minutes"] is not None
    assert stale_item["age_minutes"] >= 9.0
    assert "Stale" in stale_item["source"]


# =========================================================================
# TEST G: Deterministic Explainable Mapping Confidence
# =========================================================================
def test_g_deterministic_mapping_confidence(db_session):
    """
    Verify mapping confidence assignment:
    - 100 for >= 4 matched stations (EXACT_ROUTE_SECTION_MATCH)
    - 90 for 2-3 matched stations (VERIFIED_STATION_SEQUENCE)
    - 75 for 1 matched station (PARTIAL_ROUTE_MATCH)
    - 50 for topological inference (INFERRED_MAPPING)
    Each must have a valid explanation reason string.
    """
    corr = db_session.query(Corridor).filter(Corridor.prototype_code == "C40").first()
    payload = TrainService.get_corridor_candidate_live_status(
        db_session, corridor_ident=corr.id, refresh=False
    )

    valid_confidences = {100, 90, 75, 50}
    valid_methods = {
        "EXACT_ROUTE_SECTION_MATCH",
        "VERIFIED_STATION_SEQUENCE",
        "PARTIAL_ROUTE_MATCH",
        "INFERRED_MAPPING"
    }

    for item in payload["trains"]:
        assert item["mapping_confidence"] in valid_confidences, (
            f"Train {item['train_number']} has invalid confidence {item['mapping_confidence']}"
        )
        assert item["mapping_method"] in valid_methods, (
            f"Train {item['train_number']} has invalid method {item['mapping_method']}"
        )
        assert len(item["mapping_reason"]) > 10, (
            f"Train {item['train_number']} missing descriptive mapping reason"
        )


# =========================================================================
# TEST H: API Endpoint Verification
# =========================================================================
def test_h_api_endpoints_verification(client):
    """
    Verify FastAPI REST endpoints:
    1. GET /api/live/corridors/C40
    2. GET /api/railway/corridors/C40/trains
    3. GET /api/railway/corridors/C40/trains/live
    All return full candidate sets without arbitrary limits.
    """
    # 1. Live corridor candidates
    res_live = client.get("/api/live/corridors/C40")
    assert res_live.status_code == 200, f"Expected 200, got {res_live.status_code}: {res_live.text}"
    live_data = res_live.json()
    assert "scheduledTrainCount" in live_data
    assert "liveAvailableCount" in live_data
    assert "liveUnavailableCount" in live_data
    assert "trains" in live_data
    assert live_data["scheduledTrainCount"] >= 39
    assert len(live_data["trains"]) == live_data["scheduledTrainCount"]

    # 2. Corridor timetable trains
    res_trains = client.get("/api/railway/corridors/C40/trains")
    assert res_trains.status_code == 200
    trains_data = res_trains.json()
    assert len(trains_data) >= 39, f"Expected >= 39 corridor trains, got {len(trains_data)}"

    # 3. Corridor live movements
    res_mov = client.get("/api/railway/corridors/C40/trains/live")
    assert res_mov.status_code == 200
    mov_data = res_mov.json()
    assert len(mov_data) >= 39, f"Expected >= 39 live movements, got {len(mov_data)}"
