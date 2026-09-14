import json
import sqlite3

with open('c:/ABPS/backend/app/data/railway_network_geometry.json', 'r') as f:
    net = json.load(f)

stations = net['stations']
sections = net['sections']

conn = sqlite3.connect('c:/ABPS/backend/abps.db')
cursor = conn.cursor()

# 1. Ensure Corridors exist
corridors = {
    "CORR_MDU_TEN": "Madurai - Tirunelveli Main Line",
    "CORR_TPJ_MDU": "Tiruchchirappalli - Madurai Chord Line",
    "CORR_MAS_TPJ": "Chennai Central - Tiruchchirappalli Main Line",
    "CORR_CBE_SA": "Coimbatore - Salem Main Line",
    "CORR_MAS_CBE": "Chennai - Jolarpettai - Salem Trunk Corridor",
    "CORR_TEN_CAPE": "Tirunelveli - Kanniyakumari Line",
    "CORR_VPT_TEN_CHORD": "Virudhunagar - Tenkasi - Tirunelveli Chord",
    "CORR_TPJ_DELTA": "Tiruchchirappalli - Thanjavur - Nagapattinam Delta Line",
    "CORR_MDU_RMM": "Madurai - Rameswaram Line"
}

corr_id_map = {}
for cid, cname in corridors.items():
    cursor.execute("SELECT id FROM corridors WHERE corridor_id = ?", (cid,))
    r = cursor.fetchone()
    if r:
        corr_id_map[cid] = r[0]
    else:
        cursor.execute("INSERT INTO corridors (corridor_id, name, division, zone) VALUES (?, ?, ?, ?)",
                       (cid, cname, "SR Joint", "Southern Railway (SR)"))
        corr_id_map[cid] = cursor.lastrowid

# 2. Ensure Stations exist in `stations` table
stn_id_map = {}
for code, s in stations.items():
    cursor.execute("SELECT id FROM stations WHERE code = ?", (code,))
    r = cursor.fetchone()
    if r:
        stn_id_map[code] = r[0]
        # Update lat/lon
        cursor.execute("UPDATE stations SET latitude = ?, longitude = ? WHERE id = ?",
                       (s['latitude'], s['longitude'], r[0]))
    else:
        cursor.execute("""
            INSERT INTO stations (code, name, division, zone, latitude, longitude, total_platforms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, s['name'], s.get('division', 'SR'), 'Southern Railway (SR)', s['latitude'], s['longitude'], 4))
        stn_id_map[code] = cursor.lastrowid

# Also ensure in railway_stations
for code, s in stations.items():
    cursor.execute("SELECT id FROM railway_stations WHERE station_code = ?", (code,))
    r = cursor.fetchone()
    if r:
        cursor.execute("UPDATE railway_stations SET latitude = ?, longitude = ? WHERE id = ?",
                       (s['latitude'], s['longitude'], r[0]))

# 3. Upsert Sections in `railway_sections`
for sec_id, s in sections.items():
    from_id = stn_id_map.get(s['from_station_code'])
    to_id = stn_id_map.get(s['to_station_code'])
    cid = corr_id_map.get(s.get('corridor_id'), 1)
    
    cursor.execute("SELECT id FROM railway_sections WHERE section_id = ?", (sec_id,))
    r = cursor.fetchone()
    geo_json = json.dumps(s['coordinates'])
    
    if r:
        cursor.execute("""
            UPDATE railway_sections 
            SET name = ?, corridor_id = ?, from_station_id = ?, to_station_id = ?, 
                length_km = ?, track_type = ?, direction = ?, max_speed_kmh = ?, 
                is_electrified = ?, geometry_geojson = ?
            WHERE id = ?
        """, (s['name'], cid, from_id, to_id, s['distance_km'], s['track_type'], 
              s['direction'], s['max_speed_kmh'], s['is_electrified'], geo_json, r[0]))
    else:
        cursor.execute("""
            INSERT INTO railway_sections 
            (section_id, name, corridor_id, from_station_id, to_station_id, length_km, track_type, direction, max_speed_kmh, is_electrified, geometry_geojson)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sec_id, s['name'], cid, from_id, to_id, s['distance_km'], s['track_type'], 
              s['direction'], s['max_speed_kmh'], s['is_electrified'], geo_json))

conn.commit()
print("Synchronized all canonical stations, corridors, and railway sections to abps.db!")
cursor.execute("SELECT COUNT(*) FROM railway_sections")
print(f"Total railway_sections in abps.db: {cursor.fetchone()[0]}")
