import urllib.request
import json
import math
import networkx as nx

def haversine(c1, c2):
    R = 6371.0
    dlat = math.radians(c2[0] - c1[0])
    dlon = math.radians(c2[1] - c1[1])
    a = math.sin(dlat/2)**2 + math.cos(math.radians(c1[0]))*math.cos(math.radians(c2[0]))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def query_overpass_track(bbox):
    query = f"""[out:json][timeout:35];
    (
      way["railway"="rail"]{bbox};
    );
    out geom;
    """
    url = "https://overpass-api.de/api/interpreter"
    req = urllib.request.Request(url, data=query.encode('utf-8'), headers={'User-Agent': 'ABPS-IR-Route/1.0'})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode('utf-8')).get('elements', [])

def build_track_graph(elements):
    G = nx.Graph()
    for el in elements:
        tags = el.get('tags', {})
        if tags.get('service') in ['siding', 'yard', 'spur']:
            continue
        geom = el.get('geometry', [])
        if len(geom) < 2:
            continue
        for i in range(len(geom) - 1):
            u = (round(geom[i]['lat'], 5), round(geom[i]['lon'], 5))
            v = (round(geom[i+1]['lat'], 5), round(geom[i+1]['lon'], 5))
            d = haversine(u, v)
            G.add_edge(u, v, weight=d)
    return G

def get_track_geometry(G, start_coord, end_coord):
    best_u, min_du = None, 999.0
    best_v, min_dv = None, 999.0
    for n in G.nodes():
        du = haversine(start_coord, n)
        if du < min_du:
            min_du = du
            best_u = n
        dv = haversine(end_coord, n)
        if dv < min_dv:
            min_dv = dv
            best_v = n
    if not best_u or not best_v:
        return None, 0.0
    try:
        path = nx.shortest_path(G, best_u, best_v, weight='weight')
        dist = nx.shortest_path_length(G, best_u, best_v, weight='weight')
        return path, dist
    except Exception as e:
        return None, 0.0

bbox_cvp_ten = "(8.70,77.68,9.20,77.90)"
print("Fetching CVP - TEN tracks...")
elements = query_overpass_track(bbox_cvp_ten)
G = build_track_graph(elements)

cvp = (9.1725, 77.8687)
kdu = (8.9833, 77.8667)
mej = (8.8667, 77.8000)
ten = (8.7300, 77.7289)

p1, d1 = get_track_geometry(G, cvp, kdu)
p2, d2 = get_track_geometry(G, kdu, mej)
p3, d3 = get_track_geometry(G, mej, ten)

osm_cvp_ten = {
    'SEC_CVP_KDU': {
        'from': 'CVP', 'to': 'KDU', 'distance_km': round(d1, 2),
        'coords_latlon': p1, 'coords_lonlat': [[pt[1], pt[0]] for pt in p1]
    },
    'SEC_KDU_MEJ': {
        'from': 'KDU', 'to': 'MEJ', 'distance_km': round(d2, 2),
        'coords_latlon': p2, 'coords_lonlat': [[pt[1], pt[0]] for pt in p2]
    },
    'SEC_MEJ_TEN': {
        'from': 'MEJ', 'to': 'TEN', 'distance_km': round(d3, 2),
        'coords_latlon': p3, 'coords_lonlat': [[pt[1], pt[0]] for pt in p3]
    }
}

with open('c:/ABPS/backend/osm_cvp_ten_sections.json', 'w') as f:
    json.dump(osm_cvp_ten, f, indent=2)

print("Saved osm_cvp_ten_sections.json successfully!")
print(f"CVP-KDU: {len(p1)} pts, KDU-MEJ: {len(p2)} pts, MEJ-TEN: {len(p3)} pts")
