import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.providers.railradar import RailRadarProvider
from app.providers.mock_provider import MockTrainProvider
from app.providers import get_train_provider, ConfigErrorProvider
from app.algorithms.map_matching import TrainSectionMatcher
from app.algorithms.occupancy import OccupancyEngine
from app.algorithms.windows import WindowEngine
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.replanning import DynamicReplanningEngine

client = TestClient(app)


def test_security_and_provider_modes():
    """Verify provider selection conforms to security and mock mode constraints."""
    with patch.object(settings, "TRAIN_DATA_MODE", "mock"):
        p = get_train_provider()
        assert isinstance(p, MockTrainProvider)

    with patch.object(settings, "TRAIN_DATA_MODE", "live"), patch.object(settings, "RAILRADAR_API_KEY", ""):
        p = get_train_provider()
        assert isinstance(p, ConfigErrorProvider)
        live = p.get_live_train("12689")
        assert live["status"] == "CONFIG_ERROR"
        assert live["provenance_status"] == "ERROR"
        assert live["is_live"] is False

    with patch.object(settings, "TRAIN_DATA_MODE", "live"), patch.object(settings, "RAILRADAR_API_KEY", "test_secret_key"):
        p = get_train_provider()
        assert isinstance(p, RailRadarProvider)


def test_railradar_trains_between_parsing():
    """Verify RailRadar trains-between nested {data: {trains: [...]}} schema parsing."""
    provider = RailRadarProvider(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {
            "from": {"code": "MAS", "name": "MGR Chennai Central"},
            "to": {"code": "TPJ", "name": "Tiruchchirappalli Jn"},
            "trains": [
                {
                    "train": {
                        "number": "12689",
                        "name": "Kanniyakumari SF Express",
                        "type": "SUPERFAST",
                        "runDays": ["fri"]
                    },
                    "from": {"code": "MAS"},
                    "to": {"code": "TPJ"}
                }
            ]
        }
    }

    with patch("httpx.Client.get", return_value=mock_response):
        trains = provider.get_trains_between("MAS", "TPJ")
        assert len(trains) == 1
        assert trains[0]["train_number"] == "12689"
        assert trains[0]["train_name"] == "Kanniyakumari SF Express"
        assert trains[0]["train_type"] == "SUPERFAST"


def test_railradar_route_geojson_and_leaflet_coords():
    """Verify RailRadar GeoJSON parsing converts [lon, lat] into Leaflet [lat, lon]."""
    provider = RailRadarProvider(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {
            "trainNumber": "12689",
            "format": "geojson",
            "stops": [
                {"sequence": 1, "code": "MAS", "name": "Chennai Central", "lat": 13.0824, "lng": 80.2759},
                {"sequence": 2, "code": "AJJ", "name": "Arakkonam", "lat": 13.0784, "lng": 79.6672}
            ],
            "geojson": {
                "type": "LineString",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [80.2759, 13.0824],  # [lon, lat]
                        [79.6672, 13.0784]
                    ]
                }
            }
        }
    }

    with patch("httpx.Client.get", return_value=mock_response):
        route = provider.get_train_route("12689")
        assert route["train_number"] == "12689"
        assert len(route["stops"]) == 2
        # Verify Leaflet coordinates conversion to [lat, lon]
        leaflet_coords = route["leaflet_latlngs"]
        assert len(leaflet_coords) == 2
        assert leaflet_coords[0] == [13.0824, 80.2759]
        assert leaflet_coords[1] == [13.0784, 79.6672]


def test_map_matching_geometric_projection():
    """Verify TrainSectionMatcher projects train GPS onto track polyline."""
    candidate_sections = [
        {
            "id": 101,
            "section_id": "SEC_MAS_AVD",
            "name": "Chennai Central - Avadi",
            "direction": "UP",
            "from_lat": 13.0824,
            "from_lon": 80.2759,
            "to_lat": 13.1180,
            "to_lon": 80.1000
        },
        {
            "id": 102,
            "section_id": "SEC_CVP_TEN",
            "name": "Kovilpatti - Tirunelveli",
            "direction": "UP",
            "from_lat": 9.1724,
            "from_lon": 77.8687,
            "to_lat": 8.7288,
            "to_lon": 77.7281
        }
    ]

    # Train is near Basin Bridge (between MAS and AVD)
    match = TrainSectionMatcher.match_train_to_section(
        train_lat=13.0900,
        train_lon=80.2600,
        direction="UP",
        candidate_sections=candidate_sections
    )

    assert match["section_id"] == 101
    assert match["section_code"] == "SEC_MAS_AVD"
    assert match["confidence"] >= 0.80
    assert match["distance_to_track_km"] < 5.0


def test_occupancy_intermediate_interpolation_and_delay():
    """Verify OccupancyEngine interpolates intermediate non-stop sections and shifts by delay."""
    train = {
        "train_number": "12689",
        "train_name": "Kanniyakumari Express",
        "train_type": "SUPERFAST",
        "priority_level": 1
    }

    # Halts only at MAS and AJJ (skipping intermediate stations AVD and TRL)
    route_stops = [
        {"station_id": 1, "sequence": 1, "arrival_min": 600, "departure_min": 600, "distance_km": 0.0},
        {"station_id": 4, "sequence": 2, "arrival_min": 660, "departure_min": 665, "distance_km": 60.0}
    ]

    sections = [
        {"id": 1, "section_id": "SEC_1", "from_station_id": 1, "to_station_id": 2, "length_km": 20.0, "max_speed_kmh": 100},
        {"id": 2, "section_id": "SEC_2", "from_station_id": 2, "to_station_id": 3, "length_km": 20.0, "max_speed_kmh": 100},
        {"id": 3, "section_id": "SEC_3", "from_station_id": 3, "to_station_id": 4, "length_km": 20.0, "max_speed_kmh": 100}
    ]

    # Without delay
    occs = OccupancyEngine.calculate_section_occupancies(
        train=train,
        route_stops=route_stops,
        sections=sections,
        current_delay_min=0
    )

    assert len(occs) == 3
    # First section should start near departure (600)
    assert occs[0]["estimated_entry_min"] == 600
    assert occs[0]["estimated_exit_min"] > 600

    # With +30 min delay
    delayed_occs = OccupancyEngine.calculate_section_occupancies(
        train=train,
        route_stops=route_stops,
        sections=sections,
        current_delay_min=30
    )

    assert len(delayed_occs) == 3
    # Every section occupancy should shift by exactly 30 minutes
    for base, d in zip(occs, delayed_occs):
        assert d["estimated_entry_min"] == base["estimated_entry_min"] + 30
        assert d["estimated_exit_min"] == base["estimated_exit_min"] + 30
        assert d["delay_applied_min"] == 30


def test_window_engine_zero_traffic_unobstructed():
    """Verify WindowEngine creates an unobstructed full-day window when a section has no trains."""
    windows = WindowEngine.calculate_feasible_windows(
        section_id=42,
        corridor_id=1,
        occupancies=[],
        horizon_start_min=0,
        horizon_end_min=1440,
        min_window_duration_min=30
    )

    assert len(windows) == 1
    assert windows[0]["section_id"] == 42
    assert windows[0]["start_min"] == 0
    assert windows[0]["end_min"] == 1440
    assert windows[0]["usable_duration_min"] == 1440
    assert windows[0]["train_before_no"] == "START_OF_DAY"
    assert windows[0]["train_after_no"] == "END_OF_DAY"


def test_cpsat_delay_conflict_replan():
    """Verify live train delay alters feasible windows, triggers conflict detection, and CP-SAT re-optimizes."""
    job = {
        "id": 1,
        "job_code": "JOB_TRACK_01",
        "department_code": "ENGG",
        "section_id": 10,
        "location_km": 15.0,
        "work_type": "TRACK_TAMPING",
        "criticality": "HIGH",
        "priority_score": 85.0,
        "safety_impact": 80.0,
        "operational_impact": 70.0,
        "urgency": 80.0,
        "overdue_days": 5,
        "safety_tier": "Tier 2",
        "estimated_duration_min": 60,
        "is_emergency": False,
        "is_locked": False,
        "status": "SUBMITTED"
    }

    # Initial train: 10:00 to 10:30 (600 - 630 min)
    # Next train: 12:30 to 13:00 (750 - 780 min)
    # Available gap: 630 - 750 (with 5m buffers -> 635 to 745, duration 110m)
    train_occ_normal = [
        {"section_id": 10, "train_number": "12689", "estimated_entry_min": 600, "estimated_exit_min": 630},
        {"section_id": 10, "train_number": "12637", "estimated_entry_min": 750, "estimated_exit_min": 780}
    ]

    normal_windows = WindowEngine.calculate_feasible_windows(
        section_id=10,
        corridor_id=1,
        occupancies=train_occ_normal,
        horizon_start_min=600,
        horizon_end_min=900
    )

    # Job scheduled into the 110m gap [635, 745]
    solver = CPSATSolver(time_limit_seconds=5)
    plan_normal = solver.solve(jobs=[job], windows=normal_windows, strategy="PLAN_A")
    assert plan_normal["solver_status"] in ("OPTIMAL", "FEASIBLE")
    assert len(plan_normal["scheduled_jobs"]) == 1
    scheduled_start = plan_normal["scheduled_jobs"][0]["scheduled_start_min"]
    assert 635 <= scheduled_start <= (745 - 60)

    # Now Train 12689 gets delayed by +70 minutes (670 to 700)!
    # Gap [705, 745] is only 40 min, which is too short for the 60 min job!
    # CP-SAT must shift the job into the post-train window [785, 900]!
    train_occ_delayed = [
        {"section_id": 10, "train_number": "12689", "estimated_entry_min": 670, "estimated_exit_min": 700},
        {"section_id": 10, "train_number": "12637", "estimated_entry_min": 750, "estimated_exit_min": 780}
    ]

    delayed_windows = WindowEngine.calculate_feasible_windows(
        section_id=10,
        corridor_id=1,
        occupancies=train_occ_delayed,
        horizon_start_min=600,
        horizon_end_min=900
    )

    # Re-optimize with DynamicReplanningEngine
    replan_res = DynamicReplanningEngine.re_optimize(
        current_plan_jobs=[{
            "job_id": 1,
            "job_code": "JOB_TRACK_01",
            "scheduled_start_min": scheduled_start,
            "scheduled_end_min": scheduled_start + 60,
            "window_id": normal_windows[0]["id"],
            "block_code": "BLK_01",
            "is_scheduled": True,
            "is_locked": False,
            "execution_status": "PENDING"
        }],
        jobs=[job],
        new_windows=delayed_windows,
        new_occupancies=train_occ_delayed,
        trigger_event="LIVE_TRAIN_DELAY",
        affected_train_number="12689",
        affected_section_id=10
    )

    assert replan_res["solver_status"] in ("OPTIMAL", "FEASIBLE")
    # Verify delta changes detected timing shift
    delta = replan_res["delta_changes"]
    assert len(delta) > 0
    # Scheduled job shifted timing to avoid the delayed train
    new_start = replan_res["scheduled_jobs"][0]["scheduled_start_min"]
    assert new_start != scheduled_start
    assert delta[0]["change_type"] == "TIMING_SHIFT"


# ---------------------------------------------------------------------------
# Endpoint integration tests: patch at provider method level, not httpx.Client.get
# TestClient (Starlette) uses httpx internally, so patching httpx.Client.get at
# module level would intercept the TestClient transport. Patch the provider method.
# ---------------------------------------------------------------------------

_MAS_AJJ_NORMALIZED_TRAINS = [
    {
        'train_number': '12689',
        'train_name': 'Kanniyakumari SF Express',
        'train_type': 'SUPERFAST',
        'run_days': ['daily'],
        'status': 'RUNNING',
        'delay': 5,
        'delay_minutes': 5,
        'current_location': 'AVD',
        'current_station': 'AVD',
        'next_station': 'TRL',
        'next_halt': 'TRL',
        'previous_station': None,
        'previous_halt': None,
        'latitude': 13.118,
        'longitude': 80.100,
        'speed': 75.0,
        'direction': 'UP',
        'route': None,
        'scheduled_timing': None,
        'actual_timing': None,
        'last_updated_at': '2026-09-12T20:00:00Z',
        'source_station': 'MAS',
        'destination_station': 'AJJ',
        'source': 'RailRadar',
        'provenance_status': 'LIVE'
    },
    {
        'train_number': '20607',
        'train_name': 'Vande Bharat Express',
        'train_type': 'VANDE_BHARAT',
        'run_days': ['daily'],
        'status': 'SCHEDULED',
        'delay': 0,
        'delay_minutes': 0,
        'current_location': 'MAS',
        'current_station': 'MAS',
        'next_station': 'AJJ',
        'next_halt': 'AJJ',
        'previous_station': None,
        'previous_halt': None,
        'latitude': 13.082,
        'longitude': 80.270,
        'speed': 0.0,
        'direction': 'UP',
        'route': None,
        'scheduled_timing': None,
        'actual_timing': None,
        'last_updated_at': '2026-09-12T20:00:00Z',
        'source_station': 'MAS',
        'destination_station': 'AJJ',
        'source': 'RailRadar',
        'provenance_status': 'SCHEDULED'
    }
]


def test_endpoint_trains_between_mas_ajj_success():
    """Verify GET /api/trains/between with 2 trains - full pipeline."""
    with patch('app.providers.railradar.RailRadarProvider.get_trains_between',
               return_value=_MAS_AJJ_NORMALIZED_TRAINS), \
         patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', 'test_key'):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 200
        data = res.json()
        assert data['success'] is True
        assert data['count'] == 2
        assert len(data['trains']) == 2
        assert data['trains'][0]['train_number'] == '12689'
        assert data['trains'][0]['train_name'] == 'Kanniyakumari SF Express'
        assert data['trains'][0]['source'] == 'RailRadar'
        assert data['trains'][0]['delay'] == 5
        assert data['trains'][0]['current_location'] == 'AVD'
        assert data['trains'][0]['next_station'] == 'TRL'
        assert data['from_station'] == 'MAS'
        assert data['to_station'] == 'AJJ'
        assert 'sections' in data
        assert 'feasible_windows_count' in data


def test_endpoint_trains_between_zero_trains():
    """Verify Section 15: zero trains -> count=0, no fake data."""
    with patch('app.providers.railradar.RailRadarProvider.get_trains_between',
               return_value=[]), \
         patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', 'test_key'):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 200
        data = res.json()
        assert data['success'] is True
        assert data['count'] == 0
        assert data['trains'] == []
        assert data['message'] == 'No trains found between the selected stations.'


def test_endpoint_trains_between_missing_key():
    """Verify Section 16: missing key -> HTTP 503 'RailRadar integration is not configured.'"""
    with patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', ''):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 503
        assert res.json()['detail'] == 'RailRadar integration is not configured.'


def test_endpoint_trains_between_auth_failed():
    """Verify Section 16: auth failure -> HTTP 502 'RailRadar authentication failed.'"""
    from app.providers.railradar import RailRadarAuthError
    with patch('app.providers.railradar.RailRadarProvider.get_trains_between',
               side_effect=RailRadarAuthError('RailRadar authentication failed.')), \
         patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', 'invalid_key'):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 502
        assert res.json()['detail'] == 'RailRadar authentication failed.'


def test_endpoint_trains_between_unavailable_or_quota():
    """Verify Section 16: quota exceeded -> HTTP 503 'Unable to fetch train data from RailRadar.'"""
    from app.providers.railradar import RailRadarUnavailableError
    with patch('app.providers.railradar.RailRadarProvider.get_trains_between',
               side_effect=RailRadarUnavailableError('Unable to fetch train data from RailRadar.')), \
         patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', 'real_key'):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 503
        assert res.json()['detail'] == 'Unable to fetch train data from RailRadar.'


def test_endpoint_trains_between_timeout():
    """Verify Section 16: timeout -> HTTP 504 'RailRadar request timed out.'"""
    from app.providers.railradar import RailRadarTimeoutError
    with patch('app.providers.railradar.RailRadarProvider.get_trains_between',
               side_effect=RailRadarTimeoutError('RailRadar request timed out.')), \
         patch.object(settings, 'TRAIN_DATA_MODE', 'live'), \
         patch.object(settings, 'RAILRADAR_API_KEY', 'real_key'):
        res = client.get('/api/trains/between?from_station=MAS&to_station=AJJ')
        assert res.status_code == 504
        assert res.json()['detail'] == 'RailRadar request timed out.'


def test_endpoint_trains_between_same_station_rejected():
    """Verify validation rejects identical origin and destination."""
    res = client.get('/api/trains/between?from_station=MAS&to_station=MAS')
    assert res.status_code == 400
    assert 'cannot be the same' in res.json()['detail']


def test_endpoint_trains_between_unknown_station_rejected():
    """Verify validation rejects non-existent station codes."""
    res = client.get('/api/trains/between?from_station=XYZXYZ&to_station=MAS')
    assert res.status_code == 400
    assert 'not found in Railway Station Master' in res.json()['detail']
