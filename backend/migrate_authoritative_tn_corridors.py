"""
Safe Non-Destructive Database Migration for Authoritative 46-Corridor Tamil Nadu Network
Complies with SIH26027 specifications and requirements:
- Upserts C01 to C46 corridors with stable IDs and prototype codes
- Preserves referential integrity for maintenance_jobs, block_plans, coordinated_block_plans
- Reuses existing stations and sections without duplication
- Stores high-resolution multi-point geometry in railway_sections.geometry_geojson
"""

import json
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "c:/ABPS/backend/abps.db"
NET_JSON_PATH = "c:/ABPS/backend/app/data/railway_network_geometry.json"

def run_migration():
    print("[MIGRATION] Starting authoritative 46-corridor network migration...")
    
    if not os.path.exists(NET_JSON_PATH):
        raise FileNotFoundError(f"Missing {NET_JSON_PATH}. Run build_canonical_tn_network.py first.")

    with open(NET_JSON_PATH, "r", encoding="utf-8") as f:
        net_data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Step 1: Ensure columns exist in corridors table
    cur.execute("PRAGMA table_info(corridors)")
    existing_cols = [r[1] for r in cur.fetchall()]
    new_cols = {
        "prototype_code": "VARCHAR(10)",
        "start_station_code": "VARCHAR(10)",
        "end_station_code": "VARCHAR(10)",
        "total_distance_km": "FLOAT DEFAULT 0.0",
        "status": "VARCHAR(20) DEFAULT 'ACTIVE'",
        "description": "VARCHAR(255)"
    }
    for col, col_def in new_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE corridors ADD COLUMN {col} {col_def}")
            print(f"  Added column {col} to corridors table")

    # Step 2: Ensure all stations exist in railway_stations and stations tables with valid coords
    print("[MIGRATION] Synchronizing canonical stations...")
    stn_id_map = {} # code -> stations.id
    
    for code, s_info in net_data.get("stations", {}).items():
        lat = s_info["latitude"]
        lon = s_info["longitude"]
        name = s_info.get("name", code)
        div = s_info.get("division", "SR")

        # Update railway_stations coordinates ONLY (preserve canonical 726 master integrity & states)
        cur.execute("UPDATE railway_stations SET latitude = ?, longitude = ? WHERE station_code = ? AND (latitude IS NULL OR longitude IS NULL)", (lat, lon, code))

        # Update or insert into stations table
        cur.execute("SELECT id FROM stations WHERE code = ?", (code,))
        s_row = cur.fetchone()
        if s_row:
            stn_id = s_row[0]
            cur.execute("UPDATE stations SET latitude = ?, longitude = ?, name = ?, division = ? WHERE id = ?", (lat, lon, name, div, stn_id))
            stn_id_map[code] = stn_id
        else:
            cur.execute("""
                INSERT INTO stations (code, name, division, zone, latitude, longitude, total_platforms)
                VALUES (?, ?, ?, 'SR', ?, ?, 4)
            """, (code, name, div, lat, lon))
            stn_id_map[code] = cur.lastrowid

    conn.commit()
    print(f"  Synchronized {len(stn_id_map)} canonical stations.")

    # Step 3: Upsert Corridors C01 to C46
    print("[MIGRATION] Upserting 46 Operational Corridors (C01 to C46)...")
    
    # Check existing references in maintenance_jobs
    cur.execute("SELECT DISTINCT corridor_id FROM maintenance_jobs")
    mj_cids = [r[0] for r in cur.fetchall() if r[0] is not None]
    print(f"  Existing corridor IDs referenced by maintenance_jobs: {mj_cids}")

    # Map legacy corridor 30 -> C40 (Madurai - Tirunelveli)
    # Map legacy corridor 25 -> C21 (Erode - Coimbatore)
    corr_db_ids = {}  # prototype_code (e.g. C40) -> database corridors.id

    # Handle special mapping for ID 30 -> C40
    if 30 in mj_cids:
        cur.execute("SELECT id FROM corridors WHERE id = 30")
        if cur.fetchone():
            c40_info = net_data["corridors"]["C40"]
            cur.execute("""
                UPDATE corridors
                SET corridor_id = ?, prototype_code = 'C40', name = ?, division = ?, zone = ?,
                    start_station_code = ?, end_station_code = ?, total_distance_km = ?, status = 'ACTIVE'
                WHERE id = 30
            """, (c40_info["corridor_id"], c40_info["name"], c40_info["division"], c40_info["zone"],
                  c40_info["start_station_code"], c40_info["end_station_code"], c40_info["total_distance_km"]))
            corr_db_ids["C40"] = 30
            print("  Preserved referential integrity: Corridor ID 30 mapped to C40 (Madurai → Tirunelveli).")

    # Handle special mapping for ID 25 -> C21
    if 25 in mj_cids:
        cur.execute("SELECT id FROM corridors WHERE id = 25")
        if cur.fetchone():
            c21_info = net_data["corridors"]["C21"]
            cur.execute("""
                UPDATE corridors
                SET corridor_id = ?, prototype_code = 'C21', name = ?, division = ?, zone = ?,
                    start_station_code = ?, end_station_code = ?, total_distance_km = ?, status = 'ACTIVE'
                WHERE id = 25
            """, (c21_info["corridor_id"], c21_info["name"], c21_info["division"], c21_info["zone"],
                  c21_info["start_station_code"], c21_info["end_station_code"], c21_info["total_distance_km"]))
            corr_db_ids["C21"] = 25
            print("  Preserved referential integrity: Corridor ID 25 mapped to C21 (Erode → Coimbatore).")

    # Upsert all corridors C01 to C46
    for proto_code, c_info in net_data["corridors"].items():
        if proto_code in corr_db_ids:
            continue

        # Look for existing corridor by prototype_code or corridor_id
        cur.execute("SELECT id FROM corridors WHERE prototype_code = ? OR corridor_id = ?", (proto_code, c_info["corridor_id"]))
        row = cur.fetchone()
        if row:
            cid = row[0]
            cur.execute("""
                UPDATE corridors
                SET corridor_id = ?, prototype_code = ?, name = ?, division = ?, zone = ?,
                    start_station_code = ?, end_station_code = ?, total_distance_km = ?, status = 'ACTIVE'
                WHERE id = ?
            """, (c_info["corridor_id"], proto_code, c_info["name"], c_info["division"], c_info["zone"],
                  c_info["start_station_code"], c_info["end_station_code"], c_info["total_distance_km"], cid))
            corr_db_ids[proto_code] = cid
        else:
            cur.execute("""
                INSERT INTO corridors (corridor_id, prototype_code, name, division, zone, start_station_code, end_station_code, total_distance_km, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """, (c_info["corridor_id"], proto_code, c_info["name"], c_info["division"], c_info["zone"],
                  c_info["start_station_code"], c_info["end_station_code"], c_info["total_distance_km"]))
            corr_db_ids[proto_code] = cur.lastrowid

    # Preserve Delhi-DDU test fixture
    cur.execute("UPDATE corridors SET status = 'FIXTURE' WHERE corridor_id = 'CORR_DLI_DDU'")
    conn.commit()
    print(f"  Synchronized {len(corr_db_ids)} corridors in database.")

    # Step 4: Upsert RailwaySections with Authentic Geometries
    # Query legacy CORR_MDU_TEN id
    cur.execute("SELECT id FROM corridors WHERE corridor_id = 'CORR_MDU_TEN'")
    mdu_ten_row = cur.fetchone()
    legacy_mdu_ten_id = mdu_ten_row[0] if mdu_ten_row else None
    mdu_ten_canonical = {"SEC_MDU_TDN", "SEC_TDN_TMQ", "SEC_TMQ_VPT", "SEC_VPT_SRT", "SEC_SRT_CVP", "SEC_CVP_KDU", "SEC_KDU_MEJ", "SEC_MEJ_TEN", "SEC_MEJ_TN"}

    sec_count = 0
    cur.execute("SELECT id FROM corridors WHERE corridor_id = 'CORR_MAS_TPJ'")
    r_tpj = cur.fetchone()
    mas_tpj_id = r_tpj[0] if r_tpj else 1

    for sec_id, s_data in net_data.get("sections", {}).items():
        proto = s_data["prototype_code"]
        if sec_id in mdu_ten_canonical and legacy_mdu_ten_id:
            db_corr_id = legacy_mdu_ten_id
        elif proto == "TRUNK":
            db_corr_id = mas_tpj_id
        else:
            db_corr_id = corr_db_ids.get(proto, 1)
        u_id = stn_id_map.get(s_data["from_station_code"])
        v_id = stn_id_map.get(s_data["to_station_code"])

        if not u_id or not v_id:
            continue

        coords = s_data["coordinates"] # [[lat, lon], ...]
        coords_json = json.dumps(coords)

        cur.execute("SELECT id FROM railway_sections WHERE section_id = ?", (sec_id,))
        sec_row = cur.fetchone()
        if sec_row:
            cur.execute("""
                UPDATE railway_sections
                SET name = ?, corridor_id = ?, from_station_id = ?, to_station_id = ?, length_km = ?,
                    track_type = ?, direction = ?, max_speed_kmh = ?, is_electrified = ?, geometry_geojson = ?
                WHERE section_id = ?
            """, (s_data["name"], db_corr_id, u_id, v_id, s_data["length_km"],
                  s_data["track_type"], s_data["direction"], s_data["max_speed_kmh"],
                  1 if s_data["is_electrified"] else 0, coords_json, sec_id))
        else:
            cur.execute("""
                INSERT INTO railway_sections (section_id, name, corridor_id, from_station_id, to_station_id, length_km, track_type, direction, max_speed_kmh, is_electrified, geometry_geojson)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sec_id, s_data["name"], db_corr_id, u_id, v_id, s_data["length_km"],
                  s_data["track_type"], s_data["direction"], s_data["max_speed_kmh"],
                  1 if s_data["is_electrified"] else 0, coords_json))
        sec_count += 1

    # Update dummy sections (SECTION-103, SECTION-204, SECTION-305) geometry so existing jobs have valid geometry
    # SECTION-103 was CVP-TEN: attach C40 geometry
    c40_geom = json.dumps(net_data["corridors"]["C40"]["leaflet_latlngs"])
    cur.execute("UPDATE railway_sections SET geometry_geojson = ? WHERE section_id = 'SECTION-103' AND geometry_geojson IS NULL", (c40_geom,))
    cur.execute("UPDATE railway_sections SET geometry_geojson = ? WHERE section_id = 'SECTION-204' AND geometry_geojson IS NULL", (c40_geom,))
    c21_geom = json.dumps(net_data["corridors"]["C21"]["leaflet_latlngs"])
    cur.execute("UPDATE railway_sections SET geometry_geojson = ? WHERE section_id = 'SECTION-305' AND geometry_geojson IS NULL", (c21_geom,))

    conn.commit()
    conn.close()

    print(f"  Synchronized {sec_count} railway sections with authentic geometry.")
    print("[MIGRATION COMPLETE] All 46 corridors and track geometries successfully migrated!\n")

if __name__ == "__main__":
    run_migration()
