"""
Validation Script for Authoritative 46-Corridor Railway Network
Official Reference: Southern Railway System Map (01-04-2025)
Complies with SIH26027 Requirements 26 & 27.
"""

import json
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

NET_JSON_PATH = "c:/ABPS/backend/app/data/railway_network_geometry.json"

def haversine_km(p1, p2):
    R = 6371.0
    dlat = math.radians(p2[0] - p1[0])
    dlon = math.radians(p2[1] - p1[1])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(p1[0]))*math.cos(math.radians(p2[0]))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def validate_all_corridors():
    print("=" * 70)
    print("CRITICAL DATA VALIDATION: 46-CORRIDOR RAILWAY NETWORK (SIH26027)")
    print("=" * 70)

    if not os.path.exists(NET_JSON_PATH):
        print(f"FAILED: Geometry file not found at {NET_JSON_PATH}")
        return False

    with open(NET_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    corridors = data.get("corridors", {})
    sections = data.get("sections", {})
    stations = data.get("stations", {})

    print(f"Loaded {len(corridors)} Corridors, {len(sections)} Sections, {len(stations)} Stations.\n")

    passed_count = 0
    failed_count = 0

    expected_codes = [f"C{i:02d}" for i in range(1, 47)]
    
    for proto in expected_codes:
        if proto not in corridors:
            print(f"[{proto}] FAIL: Missing corridor definition in master file!")
            failed_count += 1
            continue

        c = corridors[proto]
        corr_id = c.get("corridor_id")
        name = c.get("name")
        stns = c.get("stations", [])
        sec_ids = c.get("sections", [])
        geom = c.get("geometry", {})
        coords = geom.get("coordinates", [])

        errors = []

        # 1. Valid ID & Name
        if not corr_id or not name:
            errors.append("Invalid ID or name")

        # 2. At least one section
        if len(sec_ids) < 1:
            errors.append("Has no sections")

        # 3. Ordered stations
        if len(stns) < 2:
            errors.append("Stations count < 2")

        # 4. Valid station codes
        for sc in stns:
            if sc not in stations:
                errors.append(f"Station {sc} missing in station master")

        # 5. Geometry coordinates length >= 3
        if len(coords) < 3:
            errors.append(f"Geometry has only {len(coords)} points (requires >= 3)")

        # 6. Check that geometry is NOT a straight line
        # If all points lie on the exact line between start and end (zero curvature)
        if len(coords) >= 3:
            p_start = (coords[0][1], coords[0][0])
            p_end = (coords[-1][1], coords[-1][0])
            crow_dist = haversine_km(p_start, p_end)
            path_dist = sum(haversine_km((coords[i][1], coords[i][0]), (coords[i+1][1], coords[i+1][0])) for i in range(len(coords) - 1))
            
            # Check if there is any deviation from straight chord
            max_deviation_km = 0.0
            for pt in coords[1:-1]:
                pt_latlon = (pt[1], pt[0])
                d_to_start = haversine_km(pt_latlon, p_start)
                d_to_end = haversine_km(pt_latlon, p_end)
                # Heron's formula / triangle height to measure distance from straight line
                if crow_dist > 0.1:
                    s_peri = (d_to_start + d_to_end + crow_dist) / 2.0
                    area_sq = max(0.0, s_peri * (s_peri - d_to_start) * (s_peri - d_to_end) * (s_peri - crow_dist))
                    h = (2.0 * math.sqrt(area_sq)) / crow_dist
                    if h > max_deviation_km:
                        max_deviation_km = h

            if len(coords) == 2 or (max_deviation_km < 0.05 and crow_dist > 15.0 and path_dist < crow_dist * 1.001):
                errors.append("Geometry appears to be a fake straight line without railway curvature")

        # 7. Section continuity
        for i in range(len(sec_ids) - 1):
            curr_sec = sections.get(sec_ids[i])
            next_sec = sections.get(sec_ids[i+1])
            if curr_sec and next_sec:
                if curr_sec["to_station_code"] != next_sec["from_station_code"]:
                    errors.append(f"Section disconnect: {sec_ids[i]} ({curr_sec['to_station_code']}) != {sec_ids[i+1]} ({next_sec['from_station_code']})")

        if errors:
            print(f"[{proto}] FAIL: {name}")
            for err in errors:
                print(f"    - {err}")
            failed_count += 1
        else:
            stn_str = " → ".join(stns[:4]) + (" → ..." if len(stns) > 4 else "")
            print(f"[{proto}] PASS  Stations: {stn_str:<32} | Sections: {len(sec_ids):2d} | Geometry: VALID ({len(coords):3d} pts) | Connected: YES")
            passed_count += 1

    print("\n" + "=" * 70)
    print(f"VALIDATION SUMMARY: {passed_count}/46 PASSED ({failed_count} FAILED)")
    print("=" * 70)

    return failed_count == 0

if __name__ == "__main__":
    success = validate_all_corridors()
    sys.exit(0 if success else 1)
