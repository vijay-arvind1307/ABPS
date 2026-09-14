import math
from typing import Dict, Any, List, Optional, Tuple


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute spherical distance between two points in km."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def point_to_segment_distance_km(
    p_lat: float, p_lon: float,
    s1_lat: float, s1_lon: float,
    s2_lat: float, s2_lon: float
) -> Tuple[float, float]:
    """
    Project point P onto segment S1-S2.
    Returns (minimum distance in km, projection scalar t in [0, 1]).
    """
    # Approximate flat earth projection for local section distances
    # Convert lat/lon to local Cartesian dx, dy in km
    mid_lat = (s1_lat + s2_lat) / 2.0
    lat_scale = 111.32
    lon_scale = 111.32 * math.cos(math.radians(mid_lat))

    x1, y1 = 0.0, 0.0
    x2 = (s2_lon - s1_lon) * lon_scale
    y2 = (s2_lat - s1_lat) * lat_scale

    px = (p_lon - s1_lon) * lon_scale
    py = (p_lat - s1_lat) * lat_scale

    seg_len_sq = x2 * x2 + y2 * y2
    if seg_len_sq < 1e-6:
        # S1 and S2 are same point
        dist = math.sqrt(px * px + py * py)
        return dist, 0.0

    # Project P onto S1-S2
    t = max(0.0, min(1.0, (px * x2 + py * y2) / seg_len_sq))
    proj_x = t * x2
    proj_y = t * y2

    dist = math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
    return dist, t


class TrainSectionMatcher:
    """
    Geometric map-matching algorithm:
    Maps live GPS telemetry (lat, lon, direction) to the precise Railway Section along the train's route.
    """

    @classmethod
    def match_train_to_section(
        cls,
        train_lat: float,
        train_lon: float,
        direction: str,
        candidate_sections: List[Dict[str, Any]],
        route_station_sequence: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        P* = argmin distance(train_position, candidate_railway_sections)
        Direction and route order resolve ambiguities.
        """
        if not candidate_sections:
            return {
                "section_id": None,
                "confidence": 0.0,
                "distance_to_track_km": 999.0,
                "match_reason": "No candidate sections available"
            }

        best_section = None
        min_dist = float("inf")
        best_t = 0.0

        for sec in candidate_sections:
            # Each section has from_station and to_station coordinates or geometry
            from_lat = sec.get("from_lat", 0.0)
            from_lon = sec.get("from_lon", 0.0)
            to_lat = sec.get("to_lat", 0.0)
            to_lon = sec.get("to_lon", 0.0)

            # Check track direction alignment bonus
            sec_dir = sec.get("direction", "BOTH")
            dir_penalty = 0.0
            if sec_dir != "BOTH" and direction and sec_dir != direction:
                dir_penalty = 5.0  # 5km virtual penalty for wrong track direction

            # If section has real track polyline geometry in geometry_geojson, test against real track segments
            geo = sec.get("geometry_geojson")
            track_pts = []
            if geo:
                if isinstance(geo, str):
                    try:
                        import json
                        geo = json.loads(geo)
                    except Exception:
                        geo = None
                if isinstance(geo, dict):
                    coords = geo.get("coordinates", [])
                    for pt in coords:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            # GeoJSON standard is [lon, lat] -> convert to (lat, lon)
                            track_pts.append((float(pt[1]), float(pt[0])))
                elif isinstance(geo, (list, tuple)):
                    for pt in geo:
                        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                            # Detect whether [lat, lon] or [lon, lat]
                            if pt[0] > 60.0 and pt[1] < 40.0:
                                track_pts.append((float(pt[1]), float(pt[0])))
                            else:
                                track_pts.append((float(pt[0]), float(pt[1])))

            if len(track_pts) >= 2:
                for idx in range(len(track_pts) - 1):
                    p1 = track_pts[idx]
                    p2 = track_pts[idx + 1]
                    d, t = point_to_segment_distance_km(train_lat, train_lon, p1[0], p1[1], p2[0], p2[1])
                    total_d = d + dir_penalty
                    if total_d < min_dist:
                        min_dist = total_d
                        best_section = sec
                        best_t = t
            else:
                d, t = point_to_segment_distance_km(train_lat, train_lon, from_lat, from_lon, to_lat, to_lon)
                total_d = d + dir_penalty
                if total_d < min_dist:
                    min_dist = total_d
                    best_section = sec
                    best_t = t

        if best_section is None:
            return {
                "section_id": None,
                "confidence": 0.0,
                "distance_to_track_km": 999.0,
                "match_reason": "Matching failed"
            }

        # Calculate confidence score based on distance to track
        # Within 200m (0.2km) -> 0.98 confidence
        # Within 1km -> 0.85 confidence
        # Above 3km -> 0.40 confidence
        actual_dist = max(0.0, min_dist)
        if actual_dist < 0.2:
            confidence = 0.98
        elif actual_dist < 1.0:
            confidence = max(0.70, 0.98 - (actual_dist * 0.2))
        else:
            confidence = max(0.30, 0.70 - ((actual_dist - 1.0) * 0.1))

        return {
            "section_id": best_section["id"],
            "section_code": best_section.get("section_id", f"SEC_{best_section['id']}"),
            "section_name": best_section.get("name", "Unknown Section"),
            "distance_to_track_km": round(actual_dist, 3),
            "confidence": round(confidence, 2),
            "progress_ratio_t": round(best_t, 2),
            "match_reason": f"Geometric projection P* matched with {round(actual_dist*1000, 1)}m cross-track distance."
        }
