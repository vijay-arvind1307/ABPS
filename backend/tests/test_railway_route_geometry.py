import math
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.railway_network_service import RailwayNetworkService, haversine_km

client = TestClient(app)


def test_cvp_to_ten_actual_railway_route():
    """
    Test authentic railway route pathfinding and track geometry for CVP -> TEN:
    - Must follow actual railway network path through Kadambur (KDU) and Vanchi Maniyachchi Jn (MEJ)
    - Must have real track geometry (LineString with > 400 points)
    - Must NOT be a 2-point straight line
    - Must have valid distance (~68.1 km)
    """
    res = client.get("/api/railway/route?from=CVP&to=TEN")
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["valid"] is True
    assert data["from"]["code"] == "CVP"
    assert data["to"]["code"] == "TEN"
    assert "Kovilpatti" in data["from"]["name"]
    assert "Tirunelveli" in data["to"]["name"]

    # Check intermediate stations
    station_codes = [s["code"] for s in data["stations"]]
    assert station_codes == ["CVP", "KDU", "MEJ", "TEN"], f"Expected ['CVP', 'KDU', 'MEJ', 'TEN'], got {station_codes}"
    assert data["intermediate_stations_count"] == 2

    # Check sections
    assert len(data["sections"]) == 3
    assert data["sections"][0]["from_station_code"] == "CVP"
    assert data["sections"][0]["to_station_code"] == "KDU"
    assert data["sections"][1]["from_station_code"] == "KDU"
    assert data["sections"][1]["to_station_code"] == "MEJ"
    assert data["sections"][2]["from_station_code"] == "MEJ"
    assert data["sections"][2]["to_station_code"] == "TEN"

    # Check real geometry
    geom = data["geometry"]
    assert geom["type"] == "LineString"
    coords = geom["coordinates"]
    assert len(coords) >= 400, f"Expected real track geometry with >= 400 points, got {len(coords)}"

    # Check that polyline coordinates are [lat, lon]
    poly = data["polyline"]
    assert len(poly) == len(coords)
    assert abs(poly[0][0] - coords[0][1]) < 1e-4  # poly lat == geojson lat
    assert abs(poly[0][1] - coords[0][0]) < 1e-4  # poly lon == geojson lon

    # Check continuity: no two consecutive points are further than 2 km apart
    for i in range(len(poly) - 1):
        p1 = poly[i]
        p2 = poly[i + 1]
        dist = haversine_km(p1[0], p1[1], p2[0], p2[1])
        assert dist < 3.0, f"Discontinuity between track points {p1} and {p2}: {dist:.2f} km"

    # Verify realistic distance
    assert 65.0 <= data["distance_km"] <= 72.0


def test_reverse_route_ten_to_cvp():
    """
    Test reversed route TEN -> CVP:
    - Geometry coordinates must be reversed in sequence
    - Intermediate stations must be ['TEN', 'MEJ', 'KDU', 'CVP']
    - Distance must match forward route
    """
    res = client.get("/api/railway/route?from=TEN&to=CVP")
    assert res.status_code == 200
    data = res.json()

    assert data["valid"] is True
    station_codes = [s["code"] for s in data["stations"]]
    assert station_codes == ["TEN", "MEJ", "KDU", "CVP"]
    assert len(data["polyline"]) >= 400
    assert 65.0 <= data["distance_km"] <= 72.0

    # First point must be near TEN, last near CVP
    first_pt = data["polyline"][0]
    last_pt = data["polyline"][-1]
    assert haversine_km(first_pt[0], first_pt[1], 8.729, 77.712) < 5.0  # near TEN
    assert haversine_km(last_pt[0], last_pt[1], 9.172, 77.868) < 5.0  # near CVP


def test_mdu_to_ten_route():
    """
    Test Madurai to Tirunelveli main corridor:
    - Connects MDU -> TMQ -> VPT -> SRT -> CVP -> KDU -> MEJ -> TY -> TEN
    - Real track geometry
    """
    res = client.get("/api/railway/route?from=MDU&to=TEN")
    assert res.status_code == 200
    data = res.json()

    assert data["valid"] is True
    assert data["stations_count"] >= 8
    assert "MDU" in [s["code"] for s in data["stations"]]
    assert "TEN" in [s["code"] for s in data["stations"]]
    assert "CVP" in [s["code"] for s in data["stations"]]
    assert len(data["polyline"]) >= 400
    assert 140.0 <= data["distance_km"] <= 170.0


def test_tpj_to_mdu_route():
    """Test Trichy to Madurai route."""
    res = client.get("/api/railway/route?from=TPJ&to=MDU")
    assert res.status_code == 200
    data = res.json()

    assert data["valid"] is True
    assert len(data["sections"]) >= 4
    assert 140.0 <= data["distance_km"] <= 170.0
    assert len(data["polyline"]) >= 5


def test_mas_to_tpj_route():
    """Test Chennai Central to Trichy main line route."""
    res = client.get("/api/railway/route?from=MAS&to=TPJ")
    assert res.status_code == 200
    data = res.json()

    assert data["valid"] is True
    assert len(data["sections"]) >= 8
    assert 300.0 <= data["distance_km"] <= 360.0
    assert len(data["polyline"]) >= 10


def test_cbe_to_sa_route():
    """Test Coimbatore to Salem route."""
    res = client.get("/api/railway/route?from=CBE&to=SA")
    assert res.status_code == 200
    data = res.json()

    assert data["valid"] is True
    assert len(data["sections"]) >= 5
    assert 140.0 <= data["distance_km"] <= 170.0
    assert len(data["polyline"]) >= 5


def test_invalid_station_code_rejection():
    """Test rejection when nonexistent station code is provided."""
    res = client.get("/api/railway/route?from=XYZNONEXISTENT&to=TEN")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "Invalid" in data["message"] or "unknown" in data["message"].lower()


def test_same_station_rejection():
    """Test rejection when start and end stations are identical."""
    res = client.get("/api/railway/route?from=TEN&to=TEN")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "different" in data["message"].lower()
