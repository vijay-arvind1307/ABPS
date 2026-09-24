import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from app.main import app
from app.db.session import SessionLocal
from app.models.models import RailwayStation

client = TestClient(app)


def test_station_master_count_and_no_duplicates():
    """Verify all authoritative stations exist and no duplicate codes exist."""
    db = SessionLocal()
    try:
        total = db.query(RailwayStation).count()
        assert total >= 726, f"Expected at least 726 stations in canonical master, got {total}"

        # SQL duplicate check
        dups = (
            db.query(RailwayStation.station_code, func.count(RailwayStation.id))
            .group_by(RailwayStation.station_code)
            .having(func.count(RailwayStation.id) > 1)
            .all()
        )
        assert len(dups) == 0, f"Found duplicate station codes: {dups}"

        # State counts
        tn_count = db.query(RailwayStation).filter(RailwayStation.state == "Tamil Nadu").count()
        assert tn_count >= 530, f"Expected at least 530 Tamil Nadu stations, got {tn_count}"
        other_count = db.query(RailwayStation).filter(RailwayStation.state != "Tamil Nadu").count()
        assert other_count >= 196, f"Expected at least 196 other-state stations, got {other_count}"
    finally:
        db.close()


def test_station_code_lookup_case_insensitive():
    """Test MAS, mas, Mas, mAs resolution."""
    for query_code in ["MAS", "mas", "Mas"]:
        res = client.get(f"/api/stations/{query_code}")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["station"]["code"] == "MAS"
        assert "Chennai" in data["station"]["name"]
        assert data["station"]["state"] == "Tamil Nadu"
        assert data["station"]["division"] == "MAS"


def test_cvp_and_ten_lookup():
    """Test CVP -> Kovilpatti and TEN -> Tirunelveli."""
    # CVP
    res_cvp = client.get("/api/stations/CVP")
    assert res_cvp.status_code == 200
    d_cvp = res_cvp.json()
    assert d_cvp["success"] is True
    assert d_cvp["station"]["code"] == "CVP"
    assert "Kovilpatti" in d_cvp["station"]["name"]
    assert d_cvp["station"]["division"] == "MDU"
    assert d_cvp["station"]["state"] == "Tamil Nadu"

    # TEN
    res_ten = client.get("/api/stations/ten")
    assert res_ten.status_code == 200
    d_ten = res_ten.json()
    assert d_ten["success"] is True
    assert d_ten["station"]["code"] == "TEN"
    assert "Tirunelveli" in d_ten["station"]["name"]


def test_invalid_station_code():
    """Test that invalid station codes return 404 with success=False."""
    res = client.get("/api/stations/XXXX")
    assert res.status_code == 404
    data = res.json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()


def test_station_name_search():
    """Test searching by station name."""
    for name in ["Madurai", "Kovilpatti", "Chennai", "Coimbatore", "Kumbakonam"]:
        res = client.get(f"/api/stations/search?q={name}")
        assert res.status_code == 200
        results = res.json()
        assert len(results) > 0
        names = [r["name"].lower() for r in results]
        assert any(name.lower() in n for n in names)


def test_small_halt_flag_stations():
    """Verify smaller stations from the PDF (HALT, FLAG) resolve correctly."""
    small_codes = {
        "PML": "Papanasam",
        "PRGL": "Perungalathur",
        "ANNR": "Annanur",
        "EGT": "Egattur",
        "PTLR": "Putlur",
        "MCRD": "Mecheri Road",
        "MTDM": "Mettur",
        "KAY": "Karamadai",
        "KIC": "Kallidaikurichi",
        "NMKL": "Namakkal",
        "SMM": "Saliyamangalam",
        "SRGM": "Srirangam",
        "VLNK": "Velanganni"
    }
    for code, expected_name_part in small_codes.items():
        res = client.get(f"/api/stations/{code}")
        assert res.status_code == 200, f"Code {code} not resolved"
        data = res.json()
        assert data["success"] is True
        assert data["station"]["code"] == code
        assert expected_name_part.lower() in data["station"]["name"].lower()


def test_tamil_nadu_stations_endpoint():
    """Test /api/stations/tamil-nadu returns only TN stations."""
    res = client.get("/api/stations/tamil-nadu")
    assert res.status_code == 200
    stns = res.json()
    assert len(stns) >= 530
    for s in stns:
        assert s["state"] == "Tamil Nadu"


def test_dynamic_route_cvp_to_ten():
    """Test that CVP to TEN creates dynamic corridor and route."""
    res = client.get("/api/railway/routes/validate?start=CVP&end=TEN")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["start_station_code"] == "CVP"
    assert data["end_station_code"] == "TEN"
    assert data["distance_km"] > 50.0  # Approx 61 km
    assert len(data["sections"]) > 0
    assert data["corridor_id"] is not None


def test_route_same_station_rejection():
    """Test that identical start and end stations are rejected."""
    res = client.get("/api/railway/routes/validate?start=CVP&end=CVP")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "must be different" in data["message"]
