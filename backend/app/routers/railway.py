import math
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.session import get_db
from app.models.models import Station, RailwayStation, RailwaySection, Corridor, Train, TrainMovement, User
from app.schemas.schemas import (
    StationResponse, SectionResponse, CorridorResponse, TrainResponse,
    TimeDistanceResponse, StationResolveResponse, RouteValidateResponse
)
from app.services.train_service import TrainService
from app.services.railway_network_service import RailwayNetworkService
from app.providers import get_train_provider, railradar_provider_instance
from app.core.config import settings

router = APIRouter(prefix="/railway", tags=["Railway Infrastructure & Movements"])


def compute_haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km, adjusted for track curvature."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    crow_dist = R * c
    return max(5.0, round(crow_dist * 1.20, 1))


# -------------------------------------------------------------
# 1. Station Resolution & Autocomplete Search (Parts 5, 6, 7, 8)
# -------------------------------------------------------------
@router.get("/stations/resolve")
def resolve_station(
    code: str = Query(..., description="Railway station code (e.g. MAS, CVP, TEN, TPJ)"),
    db: Session = Depends(get_db)
):
    """
    Resolves railway station code to official station record.
    Case-insensitive, whitespace-trimmed (e.g. mas -> MAS,  cvp  -> CVP).
    Queries authoritative RailwayStation master first.
    """
    if not code or not code.strip():
        return {"valid": False, "code": "", "message": "Station code is required"}

    norm_code = code.strip().upper()

    # 1. Query local authoritative RailwayStation master
    rstn = db.query(RailwayStation).filter(RailwayStation.station_code == norm_code).first()
    if rstn:
        return {
            "valid": True,
            "code": rstn.station_code,
            "name": rstn.station_name,
            "division": rstn.division,
            "state": rstn.state,
            "category": rstn.category,
            "district": rstn.district,
            "latitude": rstn.latitude,
            "longitude": rstn.longitude
        }

    # 2. Check legacy Station table
    stn = db.query(Station).filter(Station.code == norm_code).first()
    if stn:
        return {
            "valid": True,
            "code": stn.code,
            "name": stn.name,
            "division": stn.division,
            "zone": stn.zone,
            "latitude": stn.latitude,
            "longitude": stn.longitude
        }

    # 3. Query RailRadar Station Directory Lookup & Cache in DB
    try:
        results = railradar_provider_instance.search_stations(norm_code)
        match = None
        for r in results:
            r_code = str(r.get("code") or r.get("station_code") or "").upper()
            if r_code == norm_code:
                match = r
                break

        if match:
            stn_name = str(match.get("name") or match.get("station_name") or f"Station {norm_code}")
            div = str(match.get("division") or "SR")
            zone = str(match.get("zone") or "Southern Railway (SR)")
            lat = float(match.get("latitude") or match.get("lat") or 11.0)
            lng = float(match.get("longitude") or match.get("lon") or match.get("lng") or 78.0)

            # Persist to local station master cache
            new_rstn = RailwayStation(
                station_code=norm_code,
                station_name=stn_name,
                normalized_station_name=stn_name.lower(),
                division=div,
                state="Tamil Nadu",
                category="NSG 4",
                latitude=lat,
                longitude=lng
            )
            db.add(new_rstn)

            new_stn = Station(
                code=norm_code,
                name=stn_name,
                division=div,
                zone=zone,
                latitude=lat,
                longitude=lng,
                total_platforms=int(match.get("platforms") or 4)
            )
            db.add(new_stn)
            db.commit()

            return {
                "valid": True,
                "code": norm_code,
                "name": stn_name,
                "division": div,
                "state": "Tamil Nadu",
                "category": "NSG 4",
                "latitude": lat,
                "longitude": lng
            }
    except Exception as e:
        print(f"[RESOLVE] RailRadar lookup fallback warning for {norm_code}: {e}")

    # Station unknown
    return {
        "valid": False,
        "code": norm_code,
        "message": "Invalid railway station code"
    }


@router.get("/stations/search")
def search_stations(
    q: str = Query(..., min_length=1, description="Search query by station code or name"),
    db: Session = Depends(get_db)
):
    """
    Searches stations by code or name using the Railway Station Master.
    """
    term = q.strip()
    if not term:
        return []

    code_candidate = term.upper()
    name_pattern = f"%{term.lower()}%"

    results = []
    seen = set()

    # Exact code match first
    exact_rstn = db.query(RailwayStation).filter(RailwayStation.station_code == code_candidate).first()
    if exact_rstn:
        results.append({
            "code": exact_rstn.station_code,
            "name": exact_rstn.station_name,
            "division": exact_rstn.division,
            "state": exact_rstn.state,
            "category": exact_rstn.category
        })
        seen.add(exact_rstn.station_code)

    # Prefix/Substring matches in RailwayStation
    more_rstns = db.query(RailwayStation).filter(
        or_(
            RailwayStation.station_code.like(f"{code_candidate}%"),
            func.lower(RailwayStation.station_name).like(name_pattern),
            RailwayStation.normalized_station_name.like(name_pattern)
        ),
        ~RailwayStation.station_code.in_(seen) if seen else True
    ).limit(15).all()

    for s in more_rstns:
        results.append({
            "code": s.station_code,
            "name": s.station_name,
            "division": s.division,
            "state": s.state,
            "category": s.category
        })
        seen.add(s.station_code)

    return results


# -------------------------------------------------------------
# 2. Station Route & Network Track Geometry API (Sections 4, 10, 11)
# -------------------------------------------------------------
@router.get("/route")
def get_railway_route(
    from_station: Optional[str] = Query(None, alias="from", description="Start Station Code (e.g. CVP)"),
    to_station: Optional[str] = Query(None, alias="to", description="End Station Code (e.g. TEN)"),
    start: Optional[str] = Query(None, description="Start Station Code alias"),
    end: Optional[str] = Query(None, description="End Station Code alias"),
    start_code: Optional[str] = Query(None, description="Start code alias"),
    end_code: Optional[str] = Query(None, description="End code alias"),
    db: Session = Depends(get_db)
):
    """
    Computes authentic railway route along the connected railway network graph.
    Returns ordered stations (with intermediate stations), sections, and real track geometry.
    """
    s = from_station or start or start_code or ""
    e = to_station or end or end_code or ""
    return RailwayNetworkService.calculate_railway_route(s, e, db)


@router.get("/routes/validate")
def validate_route(
    start: Optional[str] = Query(None, description="Start Station Code (e.g. MAS)"),
    end: Optional[str] = Query(None, description="End Station Code (e.g. TPJ)"),
    start_code: Optional[str] = Query(None, description="Alternative alias for start"),
    end_code: Optional[str] = Query(None, description="Alternative alias for end"),
    from_stn: Optional[str] = Query(None, alias="from"),
    to_stn: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db)
):
    """
    Validates whether the requested start/end station pair represents a valid railway planning corridor.
    Calculates actual connected railway sections, intermediate stations, and real track geometry.
    """
    s = start or start_code or from_stn or ""
    e = end or end_code or to_stn or ""
    res = RailwayNetworkService.calculate_railway_route(s, e, db)
    if res.get("valid"):
        try:
            corr_code = res.get("corridor_code")
            corr = db.query(Corridor).filter(Corridor.corridor_id == corr_code).first()
            if corr:
                TrainService.discover_corridor_trains(db, corridor=corr, from_station=s, to_station=e)
        except Exception:
            pass
    return res


# -------------------------------------------------------------
# 3. Dynamic Corridor Train Discovery (Parts 11, 15)
# -------------------------------------------------------------
@router.get("/trains/between")
def get_trains_between_stations(
    start: Optional[str] = Query(None, alias="from", description="Start Station Code (e.g. MAS)"),
    end: Optional[str] = Query(None, alias="to", description="End Station Code (e.g. AJJ)"),
    from_station: Optional[str] = Query(None, description="Start Station Code alias"),
    to_station: Optional[str] = Query(None, description="End Station Code alias"),
    db: Session = Depends(get_db)
):
    """
    Discovers trains relevant to the selected corridor via RailRadar trains-between endpoint.
    Delegates to unified /api/trains/between implementation.
    """
    s_code = (from_station or start or "").strip().upper()
    e_code = (to_station or end or "").strip().upper()

    from app.routers.trains import get_trains_between
    return get_trains_between(
        from_station=s_code,
        to_station=e_code,
        from_stn=s_code,
        to_stn=e_code,
        start=s_code,
        end=e_code,
        db=db
    )


# -------------------------------------------------------------
# 4. Master Infrastructure & Live Telemetry
# -------------------------------------------------------------
@router.get("/stations", response_model=List[StationResponse])
def get_stations(db: Session = Depends(get_db)):
    return db.query(Station).order_by(Station.id).all()


@router.get("/sections", response_model=List[SectionResponse])
def get_sections(corridor_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(RailwaySection)
    if corridor_id:
        query = query.filter(RailwaySection.corridor_id == corridor_id)
    return query.order_by(RailwaySection.id).all()


@router.get("/corridors", response_model=List[CorridorResponse])
def get_corridors(
    zone: Optional[str] = Query(None, description="Filter by railway zone (e.g. Southern Railway (SR))"),
    division: Optional[str] = Query(None, description="Filter by railway division"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, FIXTURE, ALL)"),
    include_fixtures: bool = Query(False, description="Include test fixture corridors"),
    canonical_only: bool = Query(True, description="Return strictly authoritative C01-C46 operational corridors"),
    db: Session = Depends(get_db)
):
    """
    Returns authentic railway operational corridors.
    By default filters to ACTIVE Southern Railway canonical C01-C46 corridors.
    """
    query = db.query(Corridor)
    if zone:
        query = query.filter(Corridor.zone.ilike(f"%{zone}%"))
    if division:
        query = query.filter(Corridor.division.ilike(f"%{division}%"))
    if status and status.upper() != "ALL":
        query = query.filter(Corridor.status == status.upper())
    elif not include_fixtures and (not status or status.upper() != "ALL"):
        # By default only return ACTIVE corridors (excludes FIXTURE like Delhi-DDU and NETWORK_METADATA)
        query = query.filter(Corridor.status == "ACTIVE")

    if canonical_only:
        query = query.filter(Corridor.prototype_code.isnot(None))

    def proto_sort_key(c):
        p = getattr(c, "prototype_code", "") or ""
        if p.startswith("C") and p[1:].isdigit():
            return (0, int(p[1:]))
        return (1, c.id)

    corrs = query.all()
    if canonical_only:
        corrs = [c for c in corrs if getattr(c, "prototype_code", "") and getattr(c, "prototype_code", "").startswith("C") and getattr(c, "prototype_code", "")[1:].isdigit() and 1 <= int(getattr(c, "prototype_code", "")[1:]) <= 46]

    corrs.sort(key=proto_sort_key)
    results = []
    for c in corrs:
        proto = getattr(c, "prototype_code", None)
        net_c = RailwayNetworkService.get_corridor(proto) if proto else None
        sec_cnt = net_c.get("sections_count") if net_c else (len(c.sections) if c.sections else 0)
        stn_cnt = net_c.get("stations_count") if net_c else (sec_cnt + 1 if sec_cnt > 0 else 2)

        results.append({
            "id": c.id,
            "corridor_id": c.corridor_id,
            "name": c.name,
            "division": c.division,
            "zone": c.zone,
            "start_station_code": c.start_station_code,
            "end_station_code": c.end_station_code,
            "total_distance_km": c.total_distance_km,
            "status": c.status,
            "prototype_code": getattr(c, "prototype_code", None),
            "description": getattr(c, "description", None),
            "sections_count": sec_cnt,
            "stations_count": stn_cnt
        })
    return results


def _resolve_corridor(corridor_ident: str, db: Session) -> Optional[Corridor]:
    if not corridor_ident:
        return None
    s = str(corridor_ident).strip()
    if s.isdigit():
        return db.query(Corridor).filter(Corridor.id == int(s)).first()
    norm = s.upper()

    # 1. Exact match on corridor_id or prototype_code
    exact = db.query(Corridor).filter(
        or_(
            Corridor.corridor_id == norm,
            Corridor.prototype_code == norm
        )
    ).first()
    if exact:
        return exact

    # 2. Fallback to mapped canonical prototype code
    legacy_map = {
        "CORR_MDU_TEN": "CORR_C40_MDU_TEN",
        "CORR_MAS_AJJ": "CORR_C01_MAS_AJJ",
        "CORR_AJJ_JTJ": "CORR_C02_AJJ_JTJ",
        "CORR_MAS_GDR": "CORR_C03_MAS_GDR"
    }
    eff = legacy_map.get(norm, norm)
    return db.query(Corridor).filter(
        or_(
            Corridor.corridor_id == eff,
            Corridor.prototype_code == eff
        )
    ).first()


@router.get("/corridors/{corridor_ident}")
def get_corridor_by_id(corridor_ident: str, db: Session = Depends(get_db)):
    """Fetch single corridor by integer ID or string code with ordered stations, sections, and geometry."""
    corr = _resolve_corridor(corridor_ident, db)
    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).order_by(RailwaySection.id).all()
    
    # Retrieve authoritative network metadata and geometry
    proto = getattr(corr, "prototype_code", None)
    geom_data = RailwayNetworkService.get_corridor_geometry(proto) if proto else None
    if not geom_data:
        geom_data = RailwayNetworkService.get_corridor_geometry(corr.corridor_id)

    stations_list = []
    if geom_data and "stations" in geom_data:
        stations_list = geom_data["stations"]
    else:
        stn_set = []
        for s in sections:
            if s.from_station and s.from_station.code and s.from_station.code not in stn_set:
                stn_set.append(s.from_station.code)
            if s.to_station and s.to_station.code and s.to_station.code not in stn_set:
                stn_set.append(s.to_station.code)
        stations_list = stn_set

    sections_list = [
        {
            "id": s.id,
            "section_id": s.section_id,
            "name": s.name,
            "from_station_code": s.from_station.code if s.from_station else None,
            "to_station_code": s.to_station.code if s.to_station else None,
            "from_station_name": s.from_station.name if s.from_station else None,
            "to_station_name": s.to_station.name if s.to_station else None,
            "length_km": s.length_km,
            "track_type": s.track_type,
            "direction": s.direction,
            "coordinates": s.geometry_geojson if isinstance(s.geometry_geojson, list) else []
        }
        for s in sections
    ]

    geometry_obj = geom_data.get("geometry") if geom_data else {
        "type": "LineString",
        "coordinates": []
    }

    return {
        "id": corr.id,
        "corridor_id": corr.corridor_id,
        "name": corr.name,
        "division": corr.division,
        "zone": corr.zone,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "total_distance_km": corr.total_distance_km,
        "status": corr.status,
        "prototype_code": getattr(corr, "prototype_code", None),
        "description": getattr(corr, "description", None),
        "sections_count": len(sections_list),
        "stations_count": len(stations_list),
        "stations": stations_list,
        "sections": sections_list,
        "geometry": geometry_obj,
        "leaflet_latlngs": geom_data.get("leaflet_latlngs") if geom_data else []
    }


@router.get("/corridors/{corridor_ident}/stations")
def get_corridor_stations(corridor_ident: str, db: Session = Depends(get_db)):
    """Returns ordered list of stations along this corridor with cumulative distance."""
    corr = _resolve_corridor(corridor_ident, db)
    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    # If corridor has start and end stations, use canonical network graph path for sequential alignment
    if corr.start_station_code and corr.end_station_code:
        try:
            route = RailwayNetworkService.calculate_railway_route(corr.start_station_code, corr.end_station_code, db)
            if route.get("valid") and route.get("stations"):
                stn_list = [
                    {
                        "station_code": s["code"],
                        "station_name": s["name"],
                        "distance_km": round(s.get("distance_km", 0.0), 2),
                        "sequence": idx,
                        "latitude": s.get("latitude"),
                        "longitude": s.get("longitude"),
                        "division": s.get("division"),
                        "zone": corr.zone
                    }
                    for idx, s in enumerate(route["stations"], start=1)
                ]
                return {
                    "corridor_id": corr.corridor_id,
                    "corridor_name": corr.name,
                    "start_station_code": corr.start_station_code,
                    "end_station_code": corr.end_station_code,
                    "total_distance_km": round(float(route.get("distance_km", 0.0)), 2),
                    "total_stations": len(stn_list),
                    "stations": stn_list
                }
        except Exception:
            pass

    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).order_by(RailwaySection.id).all()
    stn_map = {}
    stn_list = []
    curr_km = 0.0

    for sec in sections:
        if sec.from_station and sec.from_station.id not in stn_map:
            stn_map[sec.from_station.id] = {
                "station_code": sec.from_station.code,
                "station_name": sec.from_station.name,
                "distance_km": round(curr_km, 2),
                "station_id": sec.from_station.id,
                "latitude": sec.from_station.latitude,
                "longitude": sec.from_station.longitude,
                "division": sec.from_station.division,
                "zone": sec.from_station.zone
            }
            stn_list.append(stn_map[sec.from_station.id])

        curr_km += sec.length_km

        if sec.to_station and sec.to_station.id not in stn_map:
            stn_map[sec.to_station.id] = {
                "station_code": sec.to_station.code,
                "station_name": sec.to_station.name,
                "distance_km": round(curr_km, 2),
                "station_id": sec.to_station.id,
                "latitude": sec.to_station.latitude,
                "longitude": sec.to_station.longitude,
                "division": sec.to_station.division,
                "zone": sec.to_station.zone
            }
            stn_list.append(stn_map[sec.to_station.id])

    return {
        "corridor_id": corr.corridor_id,
        "corridor_name": corr.name,
        "start_station_code": corr.start_station_code,
        "end_station_code": corr.end_station_code,
        "total_distance_km": round(curr_km, 2),
        "total_stations": len(stn_list),
        "stations": stn_list
    }


@router.get("/corridors/{corridor_ident}/sections")
def get_corridor_sections(corridor_ident: str, db: Session = Depends(get_db)):
    """Returns ordered list of railway sections belonging to this corridor."""
    corr = _resolve_corridor(corridor_ident, db)
    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).order_by(RailwaySection.id).all()
    return [
        {
            "id": s.id,
            "section_id": s.section_id,
            "name": s.name,
            "corridor_id": s.corridor_id,
            "from_station_code": s.from_station.code if s.from_station else None,
            "to_station_code": s.to_station.code if s.to_station else None,
            "from_station_name": s.from_station.name if s.from_station else None,
            "to_station_name": s.to_station.name if s.to_station else None,
            "length_km": s.length_km,
            "track_type": s.track_type,
            "direction": s.direction,
            "max_speed_kmh": s.max_speed_kmh,
            "is_electrified": s.is_electrified,
            "coordinates": s.geometry_geojson if isinstance(s.geometry_geojson, list) else []
        }
        for s in sections
    ]


@router.get("/corridors/{corridor_ident}/geometry")
def get_corridor_geometry(corridor_ident: str, db: Session = Depends(get_db)):
    """Returns continuous GeoJSON LineString track geometry stitched along the entire corridor."""
    corr = _resolve_corridor(corridor_ident, db)

    proto = getattr(corr, "prototype_code", None) if corr else corridor_ident.strip().upper()
    geom_data = RailwayNetworkService.get_corridor_geometry(proto) if proto else None
    if not geom_data and corr:
        geom_data = RailwayNetworkService.get_corridor_geometry(corr.corridor_id)

    if geom_data:
        return geom_data

    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).order_by(RailwaySection.id).all()
    continuous_coords = []
    for s in sections:
        coords = s.geometry_geojson if isinstance(s.geometry_geojson, list) else []
        if isinstance(coords, str):
            try:
                import json
                coords = json.loads(coords)
            except Exception:
                coords = []
        for pt in coords:
            if continuous_coords and continuous_coords[-1] == pt:
                continue
            continuous_coords.append(pt)

    return {
        "type": "Feature",
        "properties": {
            "corridor_id": corr.corridor_id,
            "prototype_code": getattr(corr, "prototype_code", None),
            "name": corr.name,
            "total_distance_km": corr.total_distance_km,
            "points_count": len(continuous_coords)
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[pt[1], pt[0]] for pt in continuous_coords]
        },
        "leaflet_latlngs": continuous_coords
    }


@router.get("/corridors/validate/all")
def validate_all_corridors_endpoint():
    """Runs automated geometry, continuity, and topology verification across all 46 corridors."""
    from validate_corridors import validate_all_corridors
    is_valid = validate_all_corridors()
    return {
        "valid": is_valid,
        "total_corridors": 46,
        "status": "PASS" if is_valid else "FAIL",
        "specification": "SIH26027 Southern Railway System Map (01-04-2025)"
    }


@router.get("/trains", response_model=List[TrainResponse])
def get_trains(db: Session = Depends(get_db)):
    return TrainService.get_all_trains(db)


@router.get("/movements")
@router.get("/trains/live")
def get_live_train_movements(
    corridor_id: Optional[int] = None,
    refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Return persisted train movement data from database cache.
    Fast, safe, zero external calls by default.
    Use refresh=true to trigger targeted TN/corridor telemetry update.
    """
    return TrainService.get_train_movements(db, corridor_id=corridor_id, refresh=refresh)


@router.get("/corridors/{corridor_ident}/trains")
def get_corridor_trains(corridor_ident: str, db: Session = Depends(get_db)):
    """
    Returns all trains whose route intersects the specified corridor.
    """
    corr = _resolve_corridor(corridor_ident, db)
    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    trains = TrainService.get_trains_for_corridor(db, corr.id)
    return [
        {
            "train_number": t.train_number,
            "train_name": t.train_name,
            "train_type": t.train_type,
            "category": t.category,
            "source_code": t.source_code,
            "source_name": t.source_name,
            "destination_code": t.destination_code,
            "destination_name": t.destination_name,
            "is_tn_relevant": t.is_tn_relevant,
            "running_days": t.running_days
        }
        for t in trains
    ]


@router.get("/corridors/{corridor_ident}/trains/live")
def get_corridor_trains_live(
    corridor_ident: str,
    refresh: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Returns live train movements for trains on this corridor from DB cache.
    """
    corr = _resolve_corridor(corridor_ident, db)
    if not corr:
        raise HTTPException(status_code=404, detail=f"Corridor '{corridor_ident}' not found")

    return TrainService.get_train_movements(db, corridor_id=corr.id, refresh=refresh)


@router.get("/trains/{train_number}/live")
def get_single_train_live(train_number: str, db: Session = Depends(get_db)):
    """
    Returns live telemetry for a specific train from backend provider.
    Directly persists telemetry into TrainMovement and TrainPositionSnapshot in DB.
    """
    provider = get_train_provider()
    live = provider.get_live_train(train_number)
    if not live:
        raise HTTPException(status_code=404, detail=f"No live telemetry available for Train {train_number}")

    # Immediately persist into TrainMovement cache and Snapshot
    try:
        lat = live.get("latitude")
        lng = live.get("longitude")
        matched_sec_id = None
        match_confidence = live.get("confidence", 0.95)

        if lat is not None and lng is not None:
            sections = db.query(RailwaySection).all()
            sec_candidates = [
                {
                    "id": s.id,
                    "section_id": s.section_id,
                    "name": s.name,
                    "direction": s.direction,
                    "from_lat": s.from_station.latitude if s.from_station else 0.0,
                    "from_lon": s.from_station.longitude if s.from_station else 0.0,
                    "to_lat": s.to_station.latitude if s.to_station else 0.0,
                    "to_lon": s.to_station.longitude if s.to_station else 0.0,
                    "geometry_geojson": s.geometry_geojson
                }
                for s in sections
            ]
            if sec_candidates:
                from app.algorithms.map_matching import TrainSectionMatcher
                match_res = TrainSectionMatcher.match_train_to_section(
                    train_lat=lat,
                    train_lon=lng,
                    direction=live.get("direction", "UP"),
                    candidate_sections=sec_candidates
                )
                matched_sec_id = match_res.get("section_id")
                match_confidence = match_res.get("confidence", match_confidence)

        tm = db.query(TrainMovement).filter(TrainMovement.train_number == train_number).first()
        if not tm:
            tm = TrainMovement(train_number=train_number)
            db.add(tm)

        tm.latitude = lat if lat is not None else (tm.latitude if tm else 0.0)
        tm.longitude = lng if lng is not None else (tm.longitude if tm else 0.0)
        tm.speed_kmh = live.get("speed_kmh", 0.0)
        tm.direction = live.get("direction", "UP")
        tm.delay_minutes = live.get("delay_minutes", 0)
        tm.status = live.get("status", "RUNNING")
        tm.current_station_code = live.get("current_station_code", "")
        tm.next_halt = live.get("next_halt", "")
        tm.previous_halt = live.get("previous_halt", "")
        tm.current_section_id = matched_sec_id
        tm.source = live.get("source", "LIVE RADAR")
        tm.provenance_status = live.get("provenance_status", "LIVE")
        tm.is_live = bool(live.get("is_live", True))
        tm.mapping_confidence = match_confidence
        tm.last_updated = datetime.utcnow()

        # Ensure Train master record exists with TN relevance
        t_rec = db.query(Train).filter(Train.train_number == train_number).first()
        if not t_rec:
            t_rec = Train(
                train_number=train_number,
                train_name=live.get("train_name", f"Express {train_number}"),
                train_type=live.get("train_type", "SUPERFAST"),
                category=live.get("train_type", "SUPERFAST"),
                priority_level=1 if "VANDE" in live.get("train_name", "").upper() else 2,
                is_tn_relevant=True,
                active=True,
                source="RailRadar",
                last_verified_at=datetime.utcnow()
            )
            db.add(t_rec)
        else:
            if live.get("train_name"):
                t_rec.train_name = live.get("train_name")
            t_rec.is_tn_relevant = True

        db.commit()

        if lat is not None and lng is not None:
            from app.models.models import TrainPositionSnapshot
            snap = TrainPositionSnapshot(
                train_number=train_number,
                timestamp=datetime.utcnow(),
                latitude=lat,
                longitude=lng,
                speed_kmh=live.get("speed_kmh", 0.0),
                bearing_degrees=live.get("bearing_degrees", 0.0),
                delay_minutes=live.get("delay_minutes", 0),
                section_id=matched_sec_id,
                source=live.get("source", "LIVE RADAR"),
                confidence=match_confidence
            )
            db.add(snap)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[SINGLE LIVE] DB persist notice: {e}")

    return live


@router.get("/trains/{train_number}/route")
def get_train_route(train_number: str, db: Session = Depends(get_db)):
    """
    Returns route stops for a specific train.
    """
    provider = get_train_provider()
    route = provider.get_train_route(train_number)
    return route


@router.get("/occupancy")
def get_train_section_occupancy(db: Session = Depends(get_db)):
    """
    Returns calculated train section occupancy intervals across all corridor sections.
    Uses database movements without calling external provider.
    """
    return TrainService.calculate_all_occupancies(db)


@router.get("/time-distance", response_model=TimeDistanceResponse)
def get_time_distance_chart_data(corridor_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Returns complete data-driven Time-Distance String Chart payload.
    Includes exact train trajectories, dynamic station/section positions, occupancies,
    feasible maintenance windows, active block plan jobs, and truthful data provenance.
    """
    return TrainService.generate_time_distance_data(db, corridor_id)


@router.get("/stations/{station_code}/live")
def get_station_live_board(station_code: str, hours: int = 4, db: Session = Depends(get_db)):
    """
    Returns live arrivals and departures board for a station from backend provider.
    """
    provider = get_train_provider()
    return provider.get_station_board(station_code, hours=hours)


@router.get("/trains/{train_number}/geometry")
def get_train_route_geometry(train_number: str, db: Session = Depends(get_db)):
    """
    Returns authentic GeoJSON track geometry and Leaflet-ready coordinates for a train.
    """
    provider = get_train_provider()
    route = provider.get_train_route(train_number)
    if not route:
        raise HTTPException(status_code=404, detail=f"No route geometry found for Train {train_number}")
    return route


@router.get("/data-status")
def get_railway_data_status(db: Session = Depends(get_db)):
    """
    Returns current train data provenance status (LIVE RADAR, CACHED, STALE, ERROR, UNAVAILABLE).
    Never claims LIVE unless current provider data was successfully received and within freshness threshold.
    """
    now = datetime.utcnow()
    clock_str = datetime.now().strftime("%H:%M:%S IST")
    mode = settings.TRAIN_DATA_MODE.lower()
    has_key = bool(settings.RAILRADAR_API_KEY)
    provider = get_train_provider()

    prov_info = provider.get_provenance_status() if hasattr(provider, "get_provenance_status") else {}
    movements = db.query(TrainMovement).all()
    train_count = len(movements)

    stale_threshold = getattr(settings, "LIVE_DATA_STALE_AFTER_SECONDS", 120)
    live_count = sum(
        1
        for movement in movements
        if (
            (getattr(movement, "is_live", False) or str(getattr(movement, "source", "")).upper().startswith("LIVE"))
            and movement.last_updated
            and (now - movement.last_updated).total_seconds() <= stale_threshold
        )
    )

    if not has_key and mode == "live":
        status = "ERROR"
        is_live = False
        provider_str = "RAILRADAR CONFIGURATION ERROR (API Key Missing in .env)"
    elif has_key and live_count > 0:
        status = "LIVE RADAR"
        is_live = True
        provider_str = "RailRadar (IR-Telematics Gateway)"
    elif prov_info.get("status") == "ERROR":
        status = "ERROR"
        is_live = False
        provider_str = f"RailRadar Notice: {prov_info.get('last_error', 'API Issue')}"
    elif has_key and train_count > 0:
        status = "STALE" if live_count == 0 else "CACHED"
        is_live = False
        provider_str = "RailRadar (Persisted Telemetry Cache)"
    elif has_key and train_count == 0:
        status = "UNAVAILABLE"
        is_live = False
        provider_str = "RailRadar (No Active Corridor Trains Detected)"
    else:
        status = "UNAVAILABLE"
        is_live = False
        provider_str = "Live Train Data Unavailable"

    return {
        "status": status,
        "mode": mode,
        "provider": provider_str,
        "train_count": train_count,
        "live_count": live_count,
        "has_api_key": has_key,
        "is_live": is_live,
        "last_updated": now.isoformat(),
        "clock_display": clock_str
    }
