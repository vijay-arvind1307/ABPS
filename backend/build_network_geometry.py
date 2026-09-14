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
    query = f"""[out:json][timeout:25];
    (
      way["railway"="rail"]{bbox};
    );
    out geom;
    """
    url = "https://overpass-api.de/api/interpreter"
    req = urllib.request.Request(url, data=query.encode('utf-8'), headers={'User-Agent': 'ABPS-IR-Route/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
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

if __name__ == '__main__':
    # Test CVP - KDU - MEJ - TEN
    bbox_cvp_ten = "(8.70,77.68,9.20,77.90)"
    print("Fetching OSM tracks for CVP - TEN corridor...")
    elements = query_overpass_track(bbox_cvp_ten)
    G = build_track_graph(elements)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    cvp = (9.1725, 77.8687)
    kdu = (8.9833, 77.8667)
    mej = (8.8667, 77.8000)
    ten = (8.7300, 77.7289)
    
    p1, d1 = get_track_geometry(G, cvp, kdu)
    p2, d2 = get_track_geometry(G, kdu, mej)
    p3, d3 = get_track_geometry(G, mej, ten)
    
    print(f"CVP -> KDU: {len(p1) if p1 else 0} pts, {d1:.2f} km")
    print(f"KDU -> MEJ: {len(p2) if p2 else 0} pts, {d2:.2f} km")
    print(f"MEJ -> TEN: {len(p3) if p3 else 0} pts, {d3:.2f} km")
