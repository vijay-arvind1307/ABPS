import re

with open('tests/test_railradar_integration.py', 'r') as f:
    content = f.read()

# Find where the old endpoint tests start
start_marker = 'def test_endpoint_trains_between_mas_ajj_success'
idx = content.find(start_marker)
assert idx != -1, 'Marker not found'

# Keep everything before the endpoint tests
header = content[:idx].rstrip() + '\n\n'

# New endpoint tests
new_tests = r'''
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
'''

with open('tests/test_railradar_integration.py', 'w') as f:
    f.write(header + new_tests)

print('Done. Lines:', (header + new_tests).count('\n'))
