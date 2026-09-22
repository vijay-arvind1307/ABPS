import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_canonical_corridors():
    """Verify that GET /api/railway/corridors returns strictly the 46 canonical Southern Railway corridors C01-C46."""
    res = client.get("/api/railway/corridors")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 46

    prototype_codes = [c["prototype_code"] for c in data]
    # Verify canonical SR corridors are present
    assert "C01" in prototype_codes
    assert "C02" in prototype_codes
    assert "C15" in prototype_codes
    assert "C23" in prototype_codes
    assert "C31" in prototype_codes
    assert "C37" in prototype_codes
    assert "C40" in prototype_codes
    assert "C45" in prototype_codes
    assert "C46" in prototype_codes

    # Verify every corridor has valid C01-C46 code
    for c in data:
        assert c["prototype_code"] is not None
        assert c["prototype_code"].startswith("C")
        num = int(c["prototype_code"][1:])
        assert 1 <= num <= 46

    # Verify Delhi fixture is NOT in active list
    corridor_ids = [c["corridor_id"] for c in data]
    assert "CORR_DLI_DDU" not in corridor_ids

    # Verify unnumbered / legacy entries are NOT in operational selector list
    assert "CORR_MAS_TPJ" not in corridor_ids
    assert "CORR_MAS_CBE" not in corridor_ids
    assert "CORR_TPJ_MDU" not in corridor_ids
    assert "CORR_MDU_TEN" not in corridor_ids


def test_corridor_fixture_filter():
    """Verify that include_fixtures=True and canonical_only=False includes CORR_DLI_DDU."""
    res = client.get("/api/railway/corridors?include_fixtures=true&canonical_only=false")
    assert res.status_code == 200
    data = res.json()
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
