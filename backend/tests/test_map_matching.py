import pytest
from app.algorithms.map_matching import TrainSectionMatcher


def test_geometric_train_section_mapping():
    candidate_sections = [
        {
            "id": 1,
            "section_id": "SEC_NDLS_GZB_UP",
            "name": "New Delhi - Ghaziabad UP",
            "from_lat": 28.6139, "from_lon": 77.2090,
            "to_lat": 28.6692, "to_lon": 77.4538,
            "direction": "UP"
        },
        {
            "id": 2,
            "section_id": "SEC_GZB_ALJN_UP",
            "name": "Ghaziabad - Aligarh UP",
            "from_lat": 28.6692, "from_lon": 77.4538,
            "to_lat": 27.8974, "to_lon": 78.0880,
            "direction": "UP"
        }
    ]

    # Train located near Anand Vihar / midway along SEC 1
    train_lat = 28.6400
    train_lon = 77.3100
    match = TrainSectionMatcher.match_train_to_section(
        train_lat=train_lat,
        train_lon=train_lon,
        direction="UP",
        candidate_sections=candidate_sections
    )

    assert match["section_id"] == 1
    assert match["confidence"] > 0.80
    assert match["distance_to_track_km"] < 2.0
