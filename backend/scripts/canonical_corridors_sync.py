import json
import sqlite3
import os

DB_PATH = "c:/ABPS/backend/abps.db"
NET_JSON_PATH = "c:/ABPS/backend/app/data/railway_network_geometry.json"

def sync_corridors_and_network():
    print(f"[SYNC] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Ensure new columns in `corridors` table
    cursor.execute("PRAGMA table_info(corridors)")
    existing_cols = [r[1] for r in cursor.fetchall()]
    new_cols = {
        "start_station_code": "VARCHAR(10)",
        "end_station_code": "VARCHAR(10)",
        "total_distance_km": "FLOAT DEFAULT 0.0",
        "status": "VARCHAR(20) DEFAULT 'ACTIVE'"
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE corridors ADD COLUMN {col} {col_type}")
            print(f"  Added column {col} to corridors")

    # 2. Canonical Corridors Definitions
    # 9 Southern Railway / Tamil Nadu Active Corridors + 1 Test Fixture (Delhi-DDU)
    canonical_corridors = [
        {
            "corridor_id": "CORR_MDU_TEN",
            "name": "Madurai - Tirunelveli Main Line",
            "division": "Madurai (MDU)",
            "zone": "Southern Railway (SR)",
            "start": "MDU",
            "end": "TEN",
            "distance": 189.5,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_MAS_TPJ",
            "name": "Chennai Central - Tiruchchirappalli Main Line",
            "division": "SR Joint (MAS/TPJ)",
            "zone": "Southern Railway (SR)",
            "start": "MAS",
            "end": "TPJ",
            "distance": 330.1,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_MAS_CBE",
            "name": "Chennai Central - Coimbatore Trunk Corridor",
            "division": "SR Joint (MAS/SA)",
            "zone": "Southern Railway (SR)",
            "start": "MAS",
            "end": "CBE",
            "distance": 311.4,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_CBE_SA",
            "name": "Coimbatore - Salem Main Line",
            "division": "Salem (SA)",
            "zone": "Southern Railway (SR)",
            "start": "CBE",
            "end": "SA",
            "distance": 155.0,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_TPJ_MDU",
            "name": "Tiruchchirappalli - Madurai Chord Line",
            "division": "Madurai (MDU)",
            "zone": "Southern Railway (SR)",
            "start": "TPJ",
            "end": "MDU",
            "distance": 152.8,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_TEN_CAPE",
            "name": "Tirunelveli - Kanniyakumari Line",
            "division": "Madurai / TVC",
            "zone": "Southern Railway (SR)",
            "start": "TEN",
            "end": "CAPE",
            "distance": 89.0,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_VPT_TEN_CHORD",
            "name": "Virudhunagar - Tenkasi - Tirunelveli Chord",
            "division": "Madurai (MDU)",
            "zone": "Southern Railway (SR)",
            "start": "VPT",
            "end": "TEN",
            "distance": 184.5,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_TPJ_DELTA",
            "name": "Tiruchchirappalli - Nagapattinam Delta Line",
            "division": "Tiruchchirappalli (TPJ)",
            "zone": "Southern Railway (SR)",
            "start": "TPJ",
            "end": "NGT",
            "distance": 162.7,
            "status": "ACTIVE"
        },
        {
            "corridor_id": "CORR_MDU_RMM",
            "name": "Madurai - Rameswaram Line",
            "division": "Madurai (MDU)",
            "zone": "Southern Railway (SR)",
            "start": "MDU",
            "end": "RMM",
            "distance": 160.7,
            "status": "ACTIVE"
        },
        # Preserved Test Fixture (Delhi - DDU)
        {
            "corridor_id": "CORR_DLI_DDU",
            "name": "Delhi - Kanpur - Prayagraj - DDU Golden Corridor",
            "division": "NCR/NR/ECR Joint",
            "zone": "Northern Railway (NR)",
            "start": "NDLS",
            "end": "DDU",
            "distance": 784.0,
            "status": "FIXTURE"
        }
    ]

    # Delete obsolete/duplicate corridors
    obsolete_corrs = [
        "CORR_CVP_TEN", "CORR_MDU_CVP", "CORR_TPJ_NGT", "CORR_CBE_MTP", "CORR_MDU_NCJ"
    ]
    for oc in obsolete_corrs:
        cursor.execute("SELECT id FROM corridors WHERE corridor_id = ?", (oc,))
        r = cursor.fetchone()
        if r:
            old_cid = r[0]
            cursor.execute("DELETE FROM railway_sections WHERE corridor_id = ?", (old_cid,))
            cursor.execute("DELETE FROM corridors WHERE id = ?", (old_cid,))
            print(f"  Purged obsolete corridor: {oc} (ID: {old_cid}) and its sections")

    # Delete legacy coarse placeholder sections (these were 2-point straight line approximations)
    coarse_section_ids = [
        "SEC_MAS_TBM_UP", "SEC_TBM_VM_UP", "SEC_VM_TPJ_UP",
        "SEC_MAS_JTJ_UP", "SEC_JTJ_SA_UP", "SEC_SA_ED_UP", "SEC_ED_CBE_UP",
        "SEC_TPJ_MDU_UP", "SEC_CVP_TEN_UP", "SEC_MDU_CVP_UP",
        "SEC_TPJ_TJ_UP", "SEC_TJ_NGT_UP", "SEC_CBE_MTP_UP",
        "SEC_MDU_TEN_UP", "SEC_TEN_NCJ_UP"
    ]
    for sid in coarse_section_ids:
        cursor.execute("DELETE FROM railway_sections WHERE section_id = ?", (sid,))
    print(f"  Purged {len(coarse_section_ids)} legacy coarse straight-line sections.")

    # Upsert Canonical Corridors
    corr_id_map = {}
    for c in canonical_corridors:
        cursor.execute("SELECT id FROM corridors WHERE corridor_id = ?", (c["corridor_id"],))
        row = cursor.fetchone()
        if row:
            cid = row[0]
            cursor.execute("""
                UPDATE corridors 
                SET name = ?, division = ?, zone = ?, start_station_code = ?, end_station_code = ?, total_distance_km = ?, status = ?
                WHERE id = ?
            """, (c["name"], c["division"], c["zone"], c["start"], c["end"], c["distance"], c["status"], cid))
            corr_id_map[c["corridor_id"]] = cid
        else:
            cursor.execute("""
                INSERT INTO corridors (corridor_id, name, division, zone, start_station_code, end_station_code, total_distance_km, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (c["corridor_id"], c["name"], c["division"], c["zone"], c["start"], c["end"], c["distance"], c["status"]))
            corr_id_map[c["corridor_id"]] = cursor.lastrowid
        print(f"  Configured Corridor: {c['corridor_id']} -> DB ID {corr_id_map[c['corridor_id']]} ({c['status']})")

    # 3. Load Canonical Network Geometry
    with open(NET_JSON_PATH, "r", encoding="utf-8") as f:
        net = json.load(f)

    stations = net["stations"]
    sections = net["sections"]

    # Ensure station mapping
    stn_id_map = {}
    for code, s in stations.items():
        cursor.execute("SELECT id FROM stations WHERE code = ?", (code,))
        r = cursor.fetchone()
        if r:
            stn_id_map[code] = r[0]
            cursor.execute("UPDATE stations SET latitude = ?, longitude = ? WHERE id = ?", (s["latitude"], s["longitude"], r[0]))
        else:
            cursor.execute("""
                INSERT INTO stations (code, name, division, zone, latitude, longitude, total_platforms)
                VALUES (?, ?, ?, ?, ?, ?, 4)
            """, (code, s["name"], s.get("division", "SR"), "Southern Railway (SR)", s["latitude"], s["longitude"]))
            stn_id_map[code] = cursor.lastrowid

    # Upsert 56 Canonical Sections
    synced_sec_count = 0
    for sec_id, s in sections.items():
        from_id = stn_id_map.get(s["from_station_code"])
        to_id = stn_id_map.get(s["to_station_code"])
        c_code = s.get("corridor_id", "CORR_MDU_TEN")
        cid = corr_id_map.get(c_code)
        if not cid:
            print(f"Warning: Corridor {c_code} not found for section {sec_id}")
            continue

        geo_json = json.dumps(s["coordinates"])
        cursor.execute("SELECT id FROM railway_sections WHERE section_id = ?", (sec_id,))
        r = cursor.fetchone()
        if r:
            cursor.execute("""
                UPDATE railway_sections
                SET name = ?, corridor_id = ?, from_station_id = ?, to_station_id = ?,
                    length_km = ?, track_type = ?, direction = ?, max_speed_kmh = ?,
                    is_electrified = ?, geometry_geojson = ?
                WHERE id = ?
            """, (s["name"], cid, from_id, to_id, s["distance_km"], s["track_type"],
                  s["direction"], s["max_speed_kmh"], s["is_electrified"], geo_json, r[0]))
        else:
            cursor.execute("""
                INSERT INTO railway_sections
                (section_id, name, corridor_id, from_station_id, to_station_id, length_km, track_type, direction, max_speed_kmh, is_electrified, geometry_geojson)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sec_id, s["name"], cid, from_id, to_id, s["distance_km"], s["track_type"],
                  s["direction"], s["max_speed_kmh"], s["is_electrified"], geo_json))
        synced_sec_count += 1

    # Preserve Delhi-DDU sections mapped to CORR_DLI_DDU
    dli_cid = corr_id_map.get("CORR_DLI_DDU")
    if dli_cid:
        cursor.execute("UPDATE railway_sections SET corridor_id = ? WHERE section_id LIKE 'SEC_NDLS%' OR section_id LIKE 'SEC_GZB%' OR section_id LIKE 'SEC_ALJN%' OR section_id LIKE 'SEC_TDL%' OR section_id LIKE 'SEC_CNB%' OR section_id LIKE 'SEC_PRYJ%'", (dli_cid,))

    conn.commit()
    conn.close()
    print(f"\n[SUCCESS] Canonical Corridor & Network Synchronization Complete:")
    print(f"          - {len(canonical_corridors)} Corridors Configured (9 Active SR, 1 Fixture)")
    print(f"          - {synced_sec_count} High-Resolution Canonical Track Sections Synchronized")

if __name__ == "__main__":
    sync_corridors_and_network()
