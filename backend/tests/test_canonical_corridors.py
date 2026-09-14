import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_canonical_corridors():
    """Verify that GET /api/railway/corridors returns only the 9 active Southern Railway corridors by default."""
    res = client.get("/api/railway/corridors")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 9

    corridor_ids = [c["corridor_id"] for c in data]
    # Verify canonical SR corridors are present
    assert "CORR_MDU_TEN" in corridor_ids
    assert "CORR_MAS_TPJ" in corridor_ids
    assert "CORR_MAS_CBE" in corridor_ids
    assert "CORR_CBE_SA" in corridor_ids
    assert "CORR_TPJ_MDU" in corridor_ids
    assert "CORR_TEN_CAPE" in corridor_ids
    assert "CORR_VPT_TEN_CHORD" in corridor_ids
    assert "CORR_TPJ_DELTA" in corridor_ids
    assert "CORR_MDU_RMM" in corridor_ids

    # Verify Delhi fixture is NOT in active list
    assert "CORR_DLI_DDU" not in corridor_ids

    # Verify obsolete duplicates are not present
    assert "CORR_CVP_TEN" not in corridor_ids
    assert "CORR_MDU_CVP" not in corridor_ids
    assert "CORR_TPJ_NGT" not in corridor_ids


def test_corridor_fixture_filter():
    """Verify that include_fixtures=True includes CORR_DLI_DDU."""
    res = client.get("/api/railway/corridors?include_fixtures=true")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 10
    assert any(c["corridor_id"] == "CORR_DLI_DDU" for c in data)


def test_corridor_subresources_mdu_ten():
    """Verify stations, sections, and geometry endpoints for Madurai - Tirunelveli Main Line."""
    # 1. Detail endpoint
    res = client.get("/api/railway/corridors/CORR_MDU_TEN")
    assert res.status_code == 200
    detail = res.json()
    assert detail["corridor_id"] == "CORR_MDU_TEN"
    assert detail["start_station_code"] == "MDU"
    assert detail["end_station_code"] == "TEN"
    assert detail["sections_count"] == 9

    # 2. Sequential stations endpoint
    res_stn = client.get("/api/railway/corridors/CORR_MDU_TEN/stations")
    assert res_stn.status_code == 200
    stn_data = res_stn.json()
    assert stn_data["total_stations"] == 9
    stn_codes = [s["station_code"] for s in stn_data["stations"]]
    assert stn_codes == ["MDU", "TDN", "TMQ", "VPT", "SRT", "CVP", "KDU", "MEJ", "TEN"]
    # Stations must have increasing cumulative distances
    distances = [s["distance_km"] for s in stn_data["stations"]]
    assert distances == sorted(distances)
    assert distances[0] == 0.0
    assert distances[-1] > 150.0

    # 3. Sections endpoint
    res_sec = client.get("/api/railway/corridors/CORR_MDU_TEN/sections")
    assert res_sec.status_code == 200
    sec_data = res_sec.json()
    assert len(sec_data) == 9

    # 4. Geometry endpoint
    res_geo = client.get("/api/railway/corridors/CORR_MDU_TEN/geometry")
    assert res_geo.status_code == 200
    geo_data = res_geo.json()
    assert geo_data["geometry"]["type"] == "LineString"
    assert len(geo_data["leaflet_latlngs"]) > 50
