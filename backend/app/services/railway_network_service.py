import json
import math
import os
import networkx as nx
from typing import Dict, Any, List, Optional, Tuple


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute spherical distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    return 2 * R * math.asin(math.sqrt(a))


class RailwayNetworkService:
    """
    Canonical Railway Network Graph and Track Geometry Service for IR-ABPS.
    Replaces straight-line approximations with actual railway network topology,
    NetworkX shortest path finding, and authentic railway track geometries.
    """

    _network_data: Optional[Dict[str, Any]] = None
    _graph: Optional[nx.Graph] = None

    @classmethod
    def _load_network(cls):
        if cls._network_data is not None and cls._graph is not None:
            return

        json_path = os.path.join(os.path.dirname(__file__), "..", "data", "railway_network_geometry.json")
        if not os.path.exists(json_path):
            # Fallback path if run from root or tests
            json_path = os.path.join(os.getcwd(), "backend", "app", "data", "railway_network_geometry.json")
            if not os.path.exists(json_path):
                json_path = os.path.join(os.getcwd(), "app", "data", "railway_network_geometry.json")

        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Railway network geometry file not found at {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            cls._network_data = json.load(f)

        G = nx.Graph()
        stations = cls._network_data.get("stations", {})
        sections = cls._network_data.get("sections", {})

        for code, s in stations.items():
            G.add_node(
                code,
                code=code,
                name=s.get("name", code),
                division=s.get("division", "SR"),
                category=s.get("category", "NSG"),
                latitude=float(s["latitude"]) if s.get("latitude") is not None else None,
                longitude=float(s["longitude"]) if s.get("longitude") is not None else None,
            )

        for sec_id, sec in sections.items():
            u = sec["from_station_code"]
            v = sec["to_station_code"]
            G.add_edge(
                u,
                v,
                section_id=sec_id,
                name=sec.get("name", f"{u} - {v}"),
                distance_km=float(sec.get("distance_km", 10.0)),
                corridor_id=sec.get("corridor_id", "CORR_SR"),
                track_type=sec.get("track_type", "DOUBLE_UP"),
                direction=sec.get("direction", "BOTH"),
                max_speed_kmh=float(sec.get("max_speed_kmh", 110.0)),
                is_electrified=sec.get("is_electrified", True),
                coordinates=sec.get("coordinates", []),  # [[lat, lon], ...]
                geometry_geojson=sec.get("geometry_geojson", {}),  # GeoJSON LineString
            )

        cls._graph = G

    @classmethod
    def get_graph(cls) -> nx.Graph:
        cls._load_network()
        return cls._graph

    @classmethod
    def get_station(cls, code: str) -> Optional[Dict[str, Any]]:
        cls._load_network()
        c = (code or "").strip().upper()
        return cls._network_data.get("stations", {}).get(c)

    @classmethod
    def get_corridor(cls, ident: str) -> Optional[Dict[str, Any]]:
        cls._load_network()
        corridors = cls._network_data.get("corridors", {})
        norm = (ident or "").strip().upper()
        if norm in corridors:
            return corridors[norm]
        for c in corridors.values():
            if c.get("corridor_id") == norm or c.get("prototype_code") == norm:
                return c
        return None

    @classmethod
    def get_all_corridors(cls) -> Dict[str, Any]:
        cls._load_network()
        return cls._network_data.get("corridors", {})

    @classmethod
    def get_corridor_geometry(cls, ident: str) -> Optional[Dict[str, Any]]:
        corr = cls.get_corridor(ident)
        if not corr:
            return None
        return {
            "type": "Feature",
            "properties": {
                "corridor_id": corr["corridor_id"],
                "prototype_code": corr["prototype_code"],
                "name": corr["name"],
                "division": corr["division"],
                "start_station_code": corr.get("start_station_code", corr["stations"][0] if corr.get("stations") else ""),
                "end_station_code": corr.get("end_station_code", corr["stations"][-1] if corr.get("stations") else ""),
                "total_distance_km": corr["total_distance_km"],
                "stations_count": corr["stations_count"],
                "sections_count": corr["sections_count"],
                "points_count": corr["points_count"]
            },
            "geometry": corr["geometry"],
            "leaflet_latlngs": corr["leaflet_latlngs"],
            "stations": corr["stations"],
            "sections": corr["sections"],
            "station_nodes": [
                {
                    "code": s_code,
                    "station_code": s_code,
                    "name": cls._network_data.get("stations", {}).get(s_code, {}).get("name", s_code),
                    "station_name": cls._network_data.get("stations", {}).get(s_code, {}).get("name", s_code),
                    "latitude": cls._network_data.get("stations", {}).get(s_code, {}).get("latitude"),
                    "longitude": cls._network_data.get("stations", {}).get(s_code, {}).get("longitude"),
                    "sequence": idx + 1,
                    "division": cls._network_data.get("stations", {}).get(s_code, {}).get("division", corr.get("division", "SR"))
                }
                for idx, s_code in enumerate(corr.get("stations", []))
                if cls._network_data.get("stations", {}).get(s_code)
            ],
            "section_nodes": [
                {
                    "section_id": sec_id,
                    "name": cls._network_data.get("sections", {}).get(sec_id, {}).get("name", sec_id),
                    "from_station_code": cls._network_data.get("sections", {}).get(sec_id, {}).get("from_station_code"),
                    "to_station_code": cls._network_data.get("sections", {}).get(sec_id, {}).get("to_station_code"),
                    "length_km": cls._network_data.get("sections", {}).get(sec_id, {}).get("distance_km", 10.0),
                    "coordinates": cls._network_data.get("sections", {}).get(sec_id, {}).get("coordinates", [])
                }
                for sec_id in corr.get("sections", [])
                if cls._network_data.get("sections", {}).get(sec_id)
            ]
        }

    @classmethod
    def calculate_railway_route(
        cls,
        start_code: str,
        end_code: str,
        db_session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates the authentic railway route along the connected railway track network.
        Follows Section 4, 10, 11, 20, 21, 22 of SIH26027 specifications:
        1. Validates presence and non-identical station codes.
        2. Finds connecting path on railway graph using NetworkX.
        3. Retrieves railway sections in path.
        4. Reverses section geometry if traversed in reverse.
        5. Removes duplicate boundary points and checks continuity.
        6. Returns complete GeoJSON LineString, Leaflet polyline, intermediate stations, and network distance.
        """
        cls._load_network()
        G = cls._graph

        s_code = (start_code or "").strip().upper()
        e_code = (end_code or "").strip().upper()

        if not s_code or not e_code:
            return {
                "success": False,
                "valid": False,
                "message": "Both start and end station codes are required.",
                "start_station_code": s_code,
                "end_station_code": e_code,
            }

        if s_code == e_code:
            return {
                "success": False,
                "valid": False,
                "message": f"Start and end stations must be different ({s_code}).",
                "start_station_code": s_code,
                "end_station_code": e_code,
            }

        # Resolve station records from network or database
        stn_start = cls._network_data.get("stations", {}).get(s_code)
        stn_end = cls._network_data.get("stations", {}).get(e_code)

        # Fallback to database if station not in primary graph
        if db_session:
            from app.models.models import RailwayStation, Station
            if not stn_start:
                db_stn = db_session.query(RailwayStation).filter(RailwayStation.station_code == s_code).first()
                if not db_stn:
                    db_stn = db_session.query(Station).filter(Station.code == s_code).first()
                if db_stn:
                    stn_start = {
                        "code": s_code,
                        "name": getattr(db_stn, "station_name", None) or getattr(db_stn, "name", s_code),
                        "division": getattr(db_stn, "division", "SR"),
                        "category": getattr(db_stn, "category", "NSG"),
                        "latitude": db_stn.latitude or 11.0,
                        "longitude": db_stn.longitude or 78.0
                    }
            if not stn_end:
                db_stn = db_session.query(RailwayStation).filter(RailwayStation.station_code == e_code).first()
                if not db_stn:
                    db_stn = db_session.query(Station).filter(Station.code == e_code).first()
                if db_stn:
                    stn_end = {
                        "code": e_code,
                        "name": getattr(db_stn, "station_name", None) or getattr(db_stn, "name", e_code),
                        "division": getattr(db_stn, "division", "SR"),
                        "category": getattr(db_stn, "category", "NSG"),
                        "latitude": db_stn.latitude or 11.0,
                        "longitude": db_stn.longitude or 78.0
                    }

        if not stn_start:
            return {
                "success": False,
                "valid": False,
                "message": f"Invalid railway station code: {s_code}",
                "start_station_code": s_code,
                "end_station_code": e_code,
            }

        if not stn_end:
            return {
                "success": False,
                "valid": False,
                "message": f"Invalid railway station code: {e_code}",
                "start_station_code": s_code,
                "end_station_code": e_code,
            }

        # If station is not directly in G, snap to nearest network junction
        graph_start_node = s_code
        graph_end_node = e_code

        if graph_start_node not in G:
            # find closest station in G
            best_node = None
            min_d = 999.0
            for node, d in G.nodes(data=True):
                if d.get("latitude") and d.get("longitude"):
                    dist = haversine_km(stn_start["latitude"], stn_start["longitude"], d["latitude"], d["longitude"])
                    if dist < min_d:
                        min_d = dist
                        best_node = node
            if best_node:
                graph_start_node = best_node

        if graph_end_node not in G:
            best_node = None
            min_d = 999.0
            for node, d in G.nodes(data=True):
                if d.get("latitude") and d.get("longitude"):
                    dist = haversine_km(stn_end["latitude"], stn_end["longitude"], d["latitude"], d["longitude"])
                    if dist < min_d:
                        min_d = dist
                        best_node = node
            if best_node:
                graph_end_node = best_node

        # Pathfinding on NetworkX graph
        try:
            stn_path = nx.shortest_path(G, graph_start_node, graph_end_node, weight="distance_km")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {
                "success": False,
                "valid": False,
                "message": f"No railway route could be generated between {s_code} and {e_code}.",
                "start_station_code": s_code,
                "start_station_name": stn_start["name"],
                "end_station_code": e_code,
                "end_station_name": stn_end["name"],
            }

        # If we had snapped start or end, attach them
        if s_code != graph_start_node:
            stn_path = [s_code] + stn_path
        if e_code != graph_end_node and (not stn_path or stn_path[-1] != e_code):
            stn_path = stn_path + [e_code]

        # Retrieve every railway section in the path and combine track geometries
        combined_coords_latlon: List[List[float]] = []
        path_sections: List[Dict[str, Any]] = []
        total_distance_km = 0.0

        for i in range(len(stn_path) - 1):
            u = stn_path[i]
            v = stn_path[i + 1]

            edge_data = G.get_edge_data(u, v)
            if not edge_data:
                # Direct edge not found in undirected graph, search by reverse or create bridge
                edge_data = G.get_edge_data(v, u)

            sec_coords: List[List[float]] = []
            sec_dist = 0.0
            sec_name = f"{u} - {v}"
            sec_id = f"SEC_{u}_{v}"
            sec_track_type = "DOUBLE_UP"
            sec_dir = "BOTH"

            if edge_data:
                sec_dist = float(edge_data.get("distance_km", 10.0))
                sec_name = edge_data.get("name", sec_name)
                sec_id = edge_data.get("section_id", sec_id)
                sec_track_type = edge_data.get("track_type", "DOUBLE_UP")
                sec_dir = edge_data.get("direction", "BOTH")
                raw_coords = edge_data.get("coordinates", [])

                if raw_coords and len(raw_coords) >= 2:
                    u_node = G.nodes[u] if u in G else stn_start
                    # Check direction (Section 21): Does raw_coords start near u and end near v?
                    first_pt = raw_coords[0]
                    last_pt = raw_coords[-1]
                    d_first_to_u = haversine_km(first_pt[0], first_pt[1], u_node["latitude"], u_node["longitude"])
                    d_last_to_u = haversine_km(last_pt[0], last_pt[1], u_node["latitude"], u_node["longitude"])

                    if d_last_to_u < d_first_to_u:
                        # Traversing in reverse: reverse coordinates
                        sec_coords = [list(pt) for pt in reversed(raw_coords)]
                    else:
                        sec_coords = [list(pt) for pt in raw_coords]
                else:
                    u_data = G.nodes[u] if u in G else stn_start
                    v_data = G.nodes[v] if v in G else stn_end
                    sec_coords = [[u_data["latitude"], u_data["longitude"]], [v_data["latitude"], v_data["longitude"]]]
            else:
                # Synthesize connected station geometry if snapped
                u_data = G.nodes.get(u, stn_start)
                v_data = G.nodes.get(v, stn_end)
                sec_dist = round(haversine_km(u_data["latitude"], u_data["longitude"], v_data["latitude"], v_data["longitude"]), 1)
                sec_coords = [[u_data["latitude"], u_data["longitude"]], [v_data["latitude"], v_data["longitude"]]]

            total_distance_km += sec_dist

            # Combine section geometry (Section 20 & 22)
            # Remove duplicate boundary points
            for pt_idx, pt in enumerate(sec_coords):
                if combined_coords_latlon:
                    last_pt = combined_coords_latlon[-1]
                    # Check if identical to last point
                    if abs(last_pt[0] - pt[0]) < 1e-5 and abs(last_pt[1] - pt[1]) < 1e-5:
                        continue
                combined_coords_latlon.append([round(pt[0], 6), round(pt[1], 6)])

            path_sections.append({
                "id": i + 1,
                "section_id": sec_id,
                "name": sec_name,
                "from_station_code": u,
                "to_station_code": v,
                "length_km": round(sec_dist, 2),
                "track_type": sec_track_type,
                "direction": sec_dir,
                "coordinates": sec_coords,
                "geometry_geojson": {
                    "type": "LineString",
                    "coordinates": [[round(pt[1], 6), round(pt[0], 6)] for pt in sec_coords]
                }
            })

        # Assemble full ordered station metadata list including all intermediate stations (Section 5)
        path_stations: List[Dict[str, Any]] = []
        accum_km = 0.0

        for idx, code in enumerate(stn_path):
            stn_meta = cls._network_data.get("stations", {}).get(code)
            if not stn_meta and db_session:
                from app.models.models import RailwayStation
                db_s = db_session.query(RailwayStation).filter(RailwayStation.station_code == code).first()
                if db_s:
                    stn_meta = {
                        "code": code,
                        "name": db_s.station_name,
                        "division": db_s.division,
                        "category": db_s.category,
                        "latitude": db_s.latitude,
                        "longitude": db_s.longitude,
                    }

            if not stn_meta:
                stn_meta = {
                    "code": code,
                    "name": code,
                    "division": "SR",
                    "category": "REGULAR",
                    "latitude": stn_start["latitude"] if idx == 0 else stn_end["latitude"],
                    "longitude": stn_start["longitude"] if idx == 0 else stn_end["longitude"],
                }

            if idx > 0 and idx - 1 < len(path_sections):
                accum_km += path_sections[idx - 1]["length_km"]

            path_stations.append({
                "id": idx + 1,
                "code": code,
                "station_code": code,
                "name": stn_meta.get("name", code),
                "station_name": stn_meta.get("name", code),
                "division": stn_meta.get("division", "SR"),
                "category": stn_meta.get("category", "NSG"),
                "latitude": float(stn_meta["latitude"]),
                "longitude": float(stn_meta["longitude"]),
                "sequence": idx + 1,
                "distance_km": round(accum_km, 1),
                "is_junction": (G.degree(code) > 2 if code in G else False)
            })

        # GeoJSON standard: [longitude, latitude]
        geojson_coords = [[pt[1], pt[0]] for pt in combined_coords_latlon]

        intermediate_count = max(0, len(path_stations) - 2)

        return {
            "success": True,
            "valid": True,
            "from": {
                "code": s_code,
                "name": stn_start["name"],
                "division": stn_start.get("division", "SR"),
                "latitude": stn_start["latitude"],
                "longitude": stn_start["longitude"],
            },
            "to": {
                "code": e_code,
                "name": stn_end["name"],
                "division": stn_end.get("division", "SR"),
                "latitude": stn_end["latitude"],
                "longitude": stn_end["longitude"],
            },
            "start_station_code": s_code,
            "start_station_name": stn_start["name"],
            "end_station_code": e_code,
            "end_station_name": stn_end["name"],
            "corridor_id": path_sections[0]["id"] if path_sections else 1,
            "corridor_code": f"CORR_{s_code}_{e_code}",
            "corridor_name": f"{stn_start['name']} ↔ {stn_end['name']} Network Path",
            "distance_km": round(total_distance_km, 1),
            "stations_count": len(path_stations),
            "intermediate_stations_count": intermediate_count,
            "sections_count": len(path_sections),
            "stations": path_stations,
            "sections": path_sections,
            "geometry": {
                "type": "LineString",
                "coordinates": geojson_coords,
            },
            "polyline": combined_coords_latlon,  # [ [lat, lon], ... ] ready for Leaflet
            "status": "VALID",
            "source": "Southern Railway Network Model (NetworkX Topological Routing)"
        }
