import json
import math
import os
import sqlite3
import networkx as nx

def haversine(c1, c2):
    R = 6371.0
    dlat = math.radians(c2[0] - c1[0])
    dlon = math.radians(c2[1] - c1[1])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(c1[0]))*math.cos(math.radians(c2[0]))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def slice_corridor_coords(corr_coords, start_latlon, end_latlon):
    """
    Given a list of [lon, lat] coordinates for a continuous corridor,
    find the subsegment between start_latlon (lat, lon) and end_latlon (lat, lon).
    Returns list of [lat, lon] coordinates.
    """
    best_s, min_ds = None, 999.0
    best_e, min_de = None, 999.0
    for idx, pt in enumerate(corr_coords):
        pt_latlon = (pt[1], pt[0])
        ds = haversine(pt_latlon, start_latlon)
        if ds < min_ds:
            min_ds = ds
            best_s = idx
        de = haversine(pt_latlon, end_latlon)
        if de < min_de:
            min_de = de
            best_e = idx
    if best_s is None or best_e is None:
        return []
    if best_s < best_e:
        sub = corr_coords[best_s : best_e + 1]
    else:
        sub = list(reversed(corr_coords[best_e : best_s + 1]))
    return [[pt[1], pt[0]] for pt in sub]

# Ensure data directory exists
os.makedirs('c:/ABPS/backend/app/data', exist_ok=True)

# Load existing OSM CVP-TEN high-res tracks
with open('c:/ABPS/backend/osm_cvp_ten_sections.json', 'r') as f:
    osm_cvp_ten = json.load(f)

# Load datameet corridors
with open('c:/ABPS/backend/datameet_sr_corridors.json', 'r') as f:
    datameet_corr = json.load(f)

# Connect to database to query accurate station master records
conn = sqlite3.connect('c:/ABPS/backend/abps.db')
cursor = conn.cursor()

KNOWN_STATION_COORDS = {
    'TDN': (9.8767, 78.0717),
    'TMQ': (9.8167, 77.9833),
    'TY': (9.4833, 77.9333),
    'KGD': (9.6917, 77.9417),
    'NRK': (8.8250, 77.7800),
    'GDN': (8.8000, 77.7550),
    'TAY': (8.7667, 77.7333),
    'MPA': (10.6000, 78.4167),
    'DG': (10.3667, 77.9667),
    'KQN': (10.1833, 77.9167),
    'SDN': (10.0167, 78.0000),
    'MS': (13.0825, 80.2618),
    'CGL': (12.6917, 79.9833),
    'TMV': (12.2333, 79.6500),
    'VRI': (11.5167, 79.3333),
    'ALU': (11.1333, 79.0667),
    'LLI': (10.8667, 78.8167),
    'SRGM': (10.8600, 78.7000),
    'IGU': (11.0167, 77.0667),
    'TUP': (11.1075, 77.3411),
    'UKL': (11.1667, 77.4500),
    'SGE': (11.4833, 77.8667),
    'MAP': (12.1333, 78.4000),
    'VN': (12.6833, 78.6167),
    'AB': (12.7833, 78.7167),
    'KPD': (12.9833, 79.1333),
    'AJJ': (13.0833, 79.6667),
    'TRL': (13.1433, 79.9083),
    'AVD': (13.1167, 80.1000),
    'VLY': (8.3833, 77.6167),
    'NCJ': (8.1833, 77.4333),
    'CAPE': (8.0833, 77.5500),
    'TN': (8.8000, 78.1500),
    'SVKS': (9.4500, 77.8000),
    'RJPM': (9.4500, 77.5500),
    'SNKL': (9.1667, 77.5333),
    'TSI': (8.9667, 77.3167),
    'ASD': (8.7000, 77.4500),
    'TJ': (10.7833, 79.1333),
    'KMU': (10.9667, 79.3833),
    'MV': (11.1000, 79.6500),
    'NGT': (10.7667, 79.8333),
    'MNM': (9.7000, 78.4500),
    'PMK': (9.3667, 78.6000),
    'RMD': (9.3667, 78.8333),
    'RMM': (9.2833, 79.3167)
}

def get_station_info(code):
    cursor.execute("SELECT station_code, station_name, division, category, latitude, longitude FROM railway_stations WHERE station_code = ?", (code,))
    row = cursor.fetchone()
    if row:
        lat = row[4]
        lon = row[5]
        if lat is None and code in KNOWN_STATION_COORDS:
            lat, lon = KNOWN_STATION_COORDS[code]
            # update database
            cursor.execute("UPDATE railway_stations SET latitude = ?, longitude = ? WHERE station_code = ?", (lat, lon, code))
            conn.commit()
        return {
            'code': row[0],
            'name': row[1],
            'division': row[2],
            'category': row[3],
            'latitude': lat,
            'longitude': lon
        }
    cursor.execute("SELECT code, name, division, zone, latitude, longitude FROM stations WHERE code = ?", (code,))
    row2 = cursor.fetchone()
    if row2:
        return {
            'code': row2[0],
            'name': row2[1],
            'division': row2[2],
            'category': 'NSG 3',
            'latitude': row2[4],
            'longitude': row2[5]
        }
    if code in KNOWN_STATION_COORDS:
        lat, lon = KNOWN_STATION_COORDS[code]
        return {
            'code': code,
            'name': code,
            'division': 'SR',
            'category': 'NSG 5',
            'latitude': lat,
            'longitude': lon
        }
    return None

print("Building Canonical Railway Network Topology and Geometry...")

# Define canonical railway section connections in Tamil Nadu & Southern Railway
# Format: (section_id, name, from_code, to_code, corridor_id, fallback_km, track_type, direction)
canonical_edges = [
    # CVP - TEN (High-Resolution OSM track geometry from osm_cvp_ten_sections.json)
    ("SEC_CVP_KDU", "Kovilpatti - Kadambur", "CVP", "KDU", "CORR_MDU_TEN", 23.38, "DOUBLE_UP", "BOTH"),
    ("SEC_KDU_MEJ", "Kadambur - Vanchi Maniyachi Jn", "KDU", "MEJ", "CORR_MDU_TEN", 21.94, "DOUBLE_UP", "BOTH"),
    ("SEC_MEJ_TEN", "Vanchi Maniyachi Jn - Tirunelveli Jn", "MEJ", "TEN", "CORR_MDU_TEN", 22.82, "DOUBLE_UP", "BOTH"),

    # MDU - CVP (Madurai to Kovilpatti sections)
    ("SEC_MDU_TDN", "Madurai Jn - Tirupparankundram", "MDU", "TDN", "CORR_MDU_TEN", 6.0, "DOUBLE_UP", "BOTH"),
    ("SEC_TDN_TMQ", "Tirupparankundram - Tirumangalam", "TDN", "TMQ", "CORR_MDU_TEN", 11.0, "DOUBLE_UP", "BOTH"),
    ("SEC_TMQ_VPT", "Tirumangalam - Virudhunagar Jn", "TMQ", "VPT", "CORR_MDU_TEN", 26.0, "DOUBLE_UP", "BOTH"),
    ("SEC_VPT_SRT", "Virudhunagar Jn - Sattur", "VPT", "SRT", "CORR_MDU_TEN", 25.0, "DOUBLE_UP", "BOTH"),
    ("SEC_SRT_CVP", "Sattur - Kovilpatti", "SRT", "CVP", "CORR_MDU_TEN", 21.0, "DOUBLE_UP", "BOTH"),

    # TPJ - MDU (Tiruchchirappalli to Madurai sections)
    ("SEC_TPJ_MPA", "Tiruchchirappalli Jn - Manaparai", "TPJ", "MPA", "CORR_TPJ_MDU", 37.0, "DOUBLE_UP", "BOTH"),
    ("SEC_MPA_DG", "Manaparai - Dindigul Jn", "MPA", "DG", "CORR_TPJ_MDU", 57.0, "DOUBLE_UP", "BOTH"),
    ("SEC_DG_KQN", "Dindigul Jn - Kodaikanal Road", "DG", "KQN", "CORR_TPJ_MDU", 22.0, "DOUBLE_UP", "BOTH"),
    ("SEC_KQN_SDN", "Kodaikanal Road - Sholavandan", "KQN", "SDN", "CORR_TPJ_MDU", 21.0, "DOUBLE_UP", "BOTH"),
    ("SEC_SDN_MDU", "Sholavandan - Madurai Jn", "SDN", "MDU", "CORR_TPJ_MDU", 20.0, "DOUBLE_UP", "BOTH"),

    # MAS - TPJ (Chennai Central/Egmore to Tiruchchirappalli sections)
    ("SEC_MAS_MS", "MGR Chennai Central - Chennai Egmore", "MAS", "MS", "CORR_MAS_TPJ", 2.0, "QUAD_UP1", "BOTH"),
    ("SEC_MS_TBM", "Chennai Egmore - Tambaram", "MS", "TBM", "CORR_MAS_TPJ", 25.0, "QUAD_UP1", "BOTH"),
    ("SEC_TBM_CGL", "Tambaram - Chengalpattu Jn", "TBM", "CGL", "CORR_MAS_TPJ", 31.0, "DOUBLE_UP", "BOTH"),
    ("SEC_CGL_TMV", "Chengalpattu Jn - Tindivanam", "CGL", "TMV", "CORR_MAS_TPJ", 67.0, "DOUBLE_UP", "BOTH"),
    ("SEC_TMV_VM", "Tindivanam - Villupuram Jn", "TMV", "VM", "CORR_MAS_TPJ", 38.0, "DOUBLE_UP", "BOTH"),
    ("SEC_VM_VRI", "Villupuram Jn - Vriddhachalam Jn", "VM", "VRI", "CORR_MAS_TPJ", 55.0, "DOUBLE_UP", "BOTH"),
    ("SEC_VRI_ALU", "Vriddhachalam Jn - Ariyalur", "VRI", "ALU", "CORR_MAS_TPJ", 53.0, "DOUBLE_UP", "BOTH"),
    ("SEC_ALU_LLI", "Ariyalur - Lalgudi", "ALU", "LLI", "CORR_MAS_TPJ", 41.0, "DOUBLE_UP", "BOTH"),
    ("SEC_LLI_SRGM", "Lalgudi - Srirangam", "LLI", "SRGM", "CORR_MAS_TPJ", 15.0, "DOUBLE_UP", "BOTH"),
    ("SEC_SRGM_TPJ", "Srirangam - Tiruchchirappalli Jn", "SRGM", "TPJ", "CORR_MAS_TPJ", 12.0, "DOUBLE_UP", "BOTH"),

    # CBE - SA (Coimbatore to Salem sections)
    ("SEC_CBE_IGU", "Coimbatore Jn - Irugur Jn", "CBE", "IGU", "CORR_CBE_SA", 18.0, "DOUBLE_UP", "BOTH"),
    ("SEC_IGU_TUP", "Irugur Jn - Tiruppur", "IGU", "TUP", "CORR_CBE_SA", 32.0, "DOUBLE_UP", "BOTH"),
    ("SEC_TUP_UKL", "Tiruppur - Uttukuli", "TUP", "UKL", "CORR_CBE_SA", 14.0, "DOUBLE_UP", "BOTH"),
    ("SEC_UKL_ED", "Uttukuli - Erode Jn", "UKL", "ED", "CORR_CBE_SA", 36.0, "DOUBLE_UP", "BOTH"),
    ("SEC_ED_SGE", "Erode Jn - Sankaridurg", "ED", "SGE", "CORR_CBE_SA", 21.0, "DOUBLE_UP", "BOTH"),
    ("SEC_SGE_SA", "Sankaridurg - Salem Jn", "SGE", "SA", "CORR_CBE_SA", 39.0, "DOUBLE_UP", "BOTH"),

    # SA - JTJ - MAS (Salem to Chennai via Jolarpettai & Katpadi)
    ("SEC_SA_MAP", "Salem Jn - Morappur", "SA", "MAP", "CORR_MAS_CBE", 56.0, "DOUBLE_UP", "BOTH"),
    ("SEC_MAP_JTJ", "Morappur - Jolarpettai Jn", "MAP", "JTJ", "CORR_MAS_CBE", 64.0, "DOUBLE_UP", "BOTH"),
    ("SEC_JTJ_VN", "Jolarpettai Jn - Vaniyambadi", "JTJ", "VN", "CORR_MAS_CBE", 16.0, "DOUBLE_UP", "BOTH"),
    ("SEC_VN_AB", "Vaniyambadi - Ambur", "VN", "AB", "CORR_MAS_CBE", 16.0, "DOUBLE_UP", "BOTH"),
    ("SEC_AB_KPD", "Ambur - Katpadi Jn", "AB", "KPD", "CORR_MAS_CBE", 52.0, "DOUBLE_UP", "BOTH"),
    ("SEC_KPD_AJJ", "Katpadi Jn - Arakkonam Jn", "KPD", "AJJ", "CORR_MAS_CBE", 61.0, "DOUBLE_UP", "BOTH"),
    ("SEC_AJJ_TRL", "Arakkonam Jn - Tiruvallur", "AJJ", "TRL", "CORR_MAS_CBE", 27.0, "QUAD_UP1", "BOTH"),
    ("SEC_TRL_AVD", "Tiruvallur - Avadi", "TRL", "AVD", "CORR_MAS_CBE", 21.0, "QUAD_UP1", "BOTH"),
    ("SEC_AVD_MAS", "Avadi - MGR Chennai Central", "AVD", "MAS", "CORR_MAS_CBE", 21.0, "QUAD_UP1", "BOTH"),

    # TEN - CAPE (Tirunelveli to Kanniyakumari)
    ("SEC_TEN_VLY", "Tirunelveli Jn - Valliyur", "TEN", "VLY", "CORR_TEN_CAPE", 43.0, "DOUBLE_UP", "BOTH"),
    ("SEC_VLY_NCJ", "Valliyur - Nagercoil Jn", "VLY", "NCJ", "CORR_TEN_CAPE", 30.0, "DOUBLE_UP", "BOTH"),
    ("SEC_NCJ_CAPE", "Nagercoil Jn - Kanniyakumari", "NCJ", "CAPE", "CORR_TEN_CAPE", 16.0, "SINGLE", "BOTH"),

    # MEJ - TN (Vanchi Maniyachi to Tuticorin branch)
    ("SEC_MEJ_TN", "Vanchi Maniyachi Jn - Tuticorin", "MEJ", "TN", "CORR_MDU_TEN", 31.0, "SINGLE", "BOTH"),

    # VPT - TSI - TEN (Virudhunagar - Tenkasi - Tirunelveli chord)
    ("SEC_VPT_SVKS", "Virudhunagar Jn - Sivakasi", "VPT", "SVKS", "CORR_VPT_TEN_CHORD", 24.0, "SINGLE", "BOTH"),
    ("SEC_SVKS_RJPM", "Sivakasi - Rajapalayam", "SVKS", "RJPM", "CORR_VPT_TEN_CHORD", 28.0, "SINGLE", "BOTH"),
    ("SEC_RJPM_SNKL", "Rajapalayam - Sankarankovil", "RJPM", "SNKL", "CORR_VPT_TEN_CHORD", 35.0, "SINGLE", "BOTH"),
    ("SEC_SNKL_TSI", "Sankarankovil - Tenkasi Jn", "SNKL", "TSI", "CORR_VPT_TEN_CHORD", 35.0, "SINGLE", "BOTH"),
    ("SEC_TSI_ASD", "Tenkasi Jn - Ambasamudram", "TSI", "ASD", "CORR_VPT_TEN_CHORD", 36.0, "SINGLE", "BOTH"),
    ("SEC_ASD_TEN", "Ambasamudram - Tirunelveli Jn", "ASD", "TEN", "CORR_VPT_TEN_CHORD", 36.0, "SINGLE", "BOTH"),

    # TPJ - TJ - KMU - MV - NGT (Cauvery Delta Main Line)
    ("SEC_TPJ_TJ", "Tiruchchirappalli Jn - Thanjavur Jn", "TPJ", "TJ", "CORR_TPJ_DELTA", 50.0, "DOUBLE_UP", "BOTH"),
    ("SEC_TJ_KMU", "Thanjavur Jn - Kumbakonam", "TJ", "KMU", "CORR_TPJ_DELTA", 40.0, "DOUBLE_UP", "BOTH"),
    ("SEC_KMU_MV", "Kumbakonam - Mayiladuthurai Jn", "KMU", "MV", "CORR_TPJ_DELTA", 32.0, "DOUBLE_UP", "BOTH"),
    ("SEC_MV_NGT", "Mayiladuthurai Jn - Nagapattinam", "MV", "NGT", "CORR_TPJ_DELTA", 48.0, "SINGLE", "BOTH"),

    # MDU - MNM - RMM (Madurai to Rameswaram Line)
    ("SEC_MDU_MNM", "Madurai Jn - Manamadurai Jn", "MDU", "MNM", "CORR_MDU_RMM", 48.0, "SINGLE", "BOTH"),
    ("SEC_MNM_PMK", "Manamadurai Jn - Paramakkudi", "MNM", "PMK", "CORR_MDU_RMM", 33.0, "SINGLE", "BOTH"),
    ("SEC_PMK_RMD", "Paramakkudi - Ramanathapuram", "PMK", "RMD", "CORR_MDU_RMM", 35.0, "SINGLE", "BOTH"),
    ("SEC_RMD_RMM", "Ramanathapuram - Rameswaram", "RMD", "RMM", "CORR_MDU_RMM", 55.0, "SINGLE", "BOTH")
]

# Track coordinates assembly
sections_dict = {}
stations_dict = {}

ms_ten_corr = datameet_corr.get('MS_TEN', {}).get('coordinates', [])
mas_cbe_corr = datameet_corr.get('MAS_CBE', {}).get('coordinates', [])
ms_rmm_corr = datameet_corr.get('MS_RMM', {}).get('coordinates', [])

for sec_id, name, from_c, to_c, corr_id, dist_km, track_type, direction in canonical_edges:
    from_info = get_station_info(from_c)
    to_info = get_station_info(to_c)
    if not from_info or not to_info:
        print(f"Warning: missing station {from_c} or {to_c}")
        continue
    
    stations_dict[from_c] = from_info
    stations_dict[to_c] = to_info
    
    s_latlon = (from_info['latitude'], from_info['longitude'])
    e_latlon = (to_info['latitude'], to_info['longitude'])
    
    # 1. If high-res OSM exists for CVP-TEN, use it directly!
    if sec_id in osm_cvp_ten:
        coords = osm_cvp_ten[sec_id]['coords_latlon']
        actual_dist = osm_cvp_ten[sec_id]['distance_km']
    else:
        # 2. Slice from datameet corridors
        sliced = []
        if any(c in ['MDU', 'TDN', 'TMQ', 'VPT', 'SRT', 'CVP', 'TPJ', 'MPA', 'DG', 'KQN', 'SDN', 'MAS', 'MS', 'TBM', 'CGL', 'TMV', 'VM', 'VRI', 'ALU', 'LLI', 'SRGM'] for c in [from_c, to_c]):
            sliced = slice_corridor_coords(ms_ten_corr, s_latlon, e_latlon)
        if not sliced and any(c in ['CBE', 'IGU', 'TUP', 'UKL', 'ED', 'SGE', 'SA', 'MAP', 'JTJ', 'VN', 'AB', 'KPD', 'AJJ', 'TRL', 'AVD', 'MAS'] for c in [from_c, to_c]):
            sliced = slice_corridor_coords(mas_cbe_corr, s_latlon, e_latlon)
        if not sliced and any(c in ['MNM', 'PMK', 'RMD', 'RMM'] for c in [from_c, to_c]):
            sliced = slice_corridor_coords(ms_rmm_corr, s_latlon, e_latlon)
            
        if sliced and len(sliced) >= 2:
            coords = sliced
            actual_dist = round(sum(haversine(coords[i], coords[i+1]) for i in range(len(coords) - 1)), 2)
            if actual_dist < 1.0:
                actual_dist = dist_km
        else:
            # Multi-point alignment through station bounds
            coords = [
                [s_latlon[0], s_latlon[1]],
                [e_latlon[0], e_latlon[1]]
            ]
            actual_dist = dist_km

    sections_dict[sec_id] = {
        'section_id': sec_id,
        'name': name,
        'from_station_code': from_c,
        'to_station_code': to_c,
        'from_station_name': from_info['name'],
        'to_station_name': to_info['name'],
        'corridor_id': corr_id,
        'distance_km': actual_dist,
        'track_type': track_type,
        'direction': direction,
        'max_speed_kmh': 110.0,
        'is_electrified': True,
        'coordinates': coords,  # [ [lat, lon], ... ]
        'geometry_geojson': {
            'type': 'LineString',
            'coordinates': [[pt[1], pt[0]] for pt in coords]  # GeoJSON standard: [lon, lat]
        }
    }

network_data = {
    'version': '1.0.0',
    'source': 'Southern Railway Network Master + OpenStreetMap Track Alignments',
    'stations': stations_dict,
    'sections': sections_dict
}

output_path = 'c:/ABPS/backend/app/data/railway_network_geometry.json'
with open(output_path, 'w') as out:
    json.dump(network_data, out, indent=2)

print(f"Successfully generated canonical network data at {output_path}!")
print(f"Total Stations in Network: {len(stations_dict)}")
print(f"Total Sections in Network: {len(sections_dict)}")

# Verify NetworkX Pathfinding
G = nx.Graph()
for code, stn in stations_dict.items():
    G.add_node(code, **stn)

for sec_id, sec in sections_dict.items():
    G.add_edge(sec['from_station_code'], sec['to_station_code'],
               section_id=sec_id,
               distance_km=sec['distance_km'],
               name=sec['name'])

test_pairs = [
    ('CVP', 'TEN'),
    ('MDU', 'TEN'),
    ('TPJ', 'MDU'),
    ('MAS', 'TPJ'),
    ('CBE', 'SA'),
    ('TEN', 'CVP'),
    ('RMM', 'MDU'),
    ('TSI', 'TEN')
]

print("\n--- Testing NetworkX Pathfinding on Canonical Graph ---")
for s, e in test_pairs:
    try:
        path = nx.shortest_path(G, s, e, weight='distance_km')
        dist = nx.shortest_path_length(G, s, e, weight='distance_km')
        print(f"Path {s} -> {e} ({dist:.1f} km): {' -> '.join(path)}")
    except Exception as err:
        print(f"FAILED {s} -> {e}: {err}")
