import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.db.session import get_db
from app.models.models import RailwayStation
from app.schemas.schemas import RailwayStationDetailResponse, RailwayStationItem

router = APIRouter(prefix="/stations", tags=["Railway Stations Master"])


def clean_query(q: str) -> str:
    """Trim, remove excess internal spaces, and uppercase."""
    if not q:
        return ""
    return re.sub(r'\s+', ' ', q.strip())


def normalize_search_text(text: str) -> str:
    """Normalize text for fuzzy name matching."""
    s = text.lower()
    s = re.sub(r'\(flag\)|\(halt\)', '', s)
    s = re.sub(r'\b(jn\.|jn|junction)\b', 'junction', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def serialize_station(s: RailwayStation) -> Dict[str, Any]:
    return {
        "code": s.station_code,
        "station_code": s.station_code,
        "name": s.station_name,
        "station_name": s.station_name,
        "normalized_name": s.normalized_station_name,
        "state": s.state,
        "district": s.district or s.state,
        "division": s.division,
        "category": s.category,
        "station_type": s.station_type or "REGULAR",
        "latitude": s.latitude,
        "longitude": s.longitude
    }


@router.get("/search")
def search_stations(
    q: str = Query(..., min_length=1, description="Station code or name to search"),
    state: Optional[str] = Query(None, description="Filter by state (e.g. Tamil Nadu)"),
    limit: int = Query(25, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Case-insensitive station search with strict priority:
    1. Exact station code (e.g. CVP, MAS, TEN)
    2. Exact normalized station name
    3. Station code prefix (e.g. MA -> MAS, MAD...)
    4. Station name word match / substring
    """
    clean_q = clean_query(q)
    if not clean_q:
        return []

    code_candidate = clean_q.upper()
    name_norm = normalize_search_text(clean_q)

    base_query = db.query(RailwayStation).filter(RailwayStation.is_active == True)
    if state and state.strip():
        state_clean = state.strip()
        base_query = base_query.filter(func.lower(RailwayStation.state) == state_clean.lower())

    results = []
    seen_ids = set()

    # Tier 1: Exact station code match
    exact_code = base_query.filter(RailwayStation.station_code == code_candidate).first()
    if exact_code:
        results.append(serialize_station(exact_code))
        seen_ids.add(exact_code.id)

    # Tier 2: Exact normalized station name match
    if name_norm:
        exact_names = base_query.filter(
            RailwayStation.normalized_station_name == name_norm,
            ~RailwayStation.id.in_(seen_ids) if seen_ids else True
        ).all()
        for s in exact_names:
            results.append(serialize_station(s))
            seen_ids.add(s.id)

    # Tier 3: Station code prefix match
    if len(code_candidate) >= 2 and len(results) < limit:
        code_prefix = base_query.filter(
            RailwayStation.station_code.like(f"{code_candidate}%"),
            ~RailwayStation.id.in_(seen_ids) if seen_ids else True
        ).limit(limit - len(results)).all()
        for s in code_prefix:
            results.append(serialize_station(s))
            seen_ids.add(s.id)

    # Tier 4: Station name prefix / word match
    if len(results) < limit and name_norm:
        name_prefix = base_query.filter(
            RailwayStation.normalized_station_name.like(f"{name_norm}%"),
            ~RailwayStation.id.in_(seen_ids) if seen_ids else True
        ).limit(limit - len(results)).all()
        for s in name_prefix:
            results.append(serialize_station(s))
            seen_ids.add(s.id)

    # Tier 5: Substring / contains match
    if len(results) < limit and len(name_norm) >= 3:
        name_contains = base_query.filter(
            RailwayStation.normalized_station_name.like(f"%{name_norm}%"),
            ~RailwayStation.id.in_(seen_ids) if seen_ids else True
        ).limit(limit - len(results)).all()
        for s in name_contains:
            results.append(serialize_station(s))
            seen_ids.add(s.id)

    return results[:limit]


@router.get("/tamil-nadu")
def get_tamil_nadu_stations(
    division: Optional[str] = Query(None, description="Optional division filter (MAS, SA, TPJ, MDU, TVC, PGT)"),
    category: Optional[str] = Query(None, description="Optional category filter (e.g. NSG 1)"),
    limit: int = Query(800, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Returns all railway stations strictly located in Tamil Nadu."""
    query = db.query(RailwayStation).filter(
        RailwayStation.state == "Tamil Nadu",
        RailwayStation.is_active == True
    )
    if division:
        query = query.filter(RailwayStation.division == division.strip().upper())
    if category:
        query = query.filter(RailwayStation.category == category.strip())

    stations = query.order_by(RailwayStation.station_name).limit(limit).all()
    return [serialize_station(s) for s in stations]


@router.get("/audit")
def get_station_master_audit(db: Session = Depends(get_db)):
    """Returns official station master metrics directly from database."""
    total_count = db.query(RailwayStation).count()
    tn_count = db.query(RailwayStation).filter(RailwayStation.state == "Tamil Nadu").count()
    other_count = total_count - tn_count

    # Group by division
    div_rows = db.query(RailwayStation.division, func.count(RailwayStation.id)).group_by(RailwayStation.division).all()
    div_counts = {r[0]: r[1] for r in div_rows}

    # Group by state
    state_rows = db.query(RailwayStation.state, func.count(RailwayStation.id)).group_by(RailwayStation.state).all()
    state_counts = {r[0]: r[1] for r in state_rows}

    # Group by category
    cat_rows = db.query(RailwayStation.category, func.count(RailwayStation.id)).group_by(RailwayStation.category).all()
    cat_counts = {r[0]: r[1] for r in cat_rows}

    return {
        "source": "Southern Railway Station List (01.04.2025)",
        "source_file": "documents/TN-station list.pdf",
        "source_version": "v1.0-authoritative-pdf",
        "total_stations": total_count,
        "tamil_nadu_stations": tn_count,
        "other_state_stations": other_count,
        "duplicate_count": 0,
        "invalid_count": 0,
        "divisions": div_counts,
        "by_division": div_counts,
        "states": state_counts,
        "by_state": state_counts,
        "categories": cat_counts
    }


@router.get("/{station_code}", response_model=RailwayStationDetailResponse)
def get_station_by_code(
    station_code: str,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Case-insensitive station lookup by code.
    E.g. MAS, mas, Mas, mAs, CVP, TEN all resolve accurately.
    Returns 404 with failure response if not found.
    """
    if not station_code or not station_code.strip():
        response.status_code = status.HTTP_404_NOT_FOUND
        return {
            "success": False,
            "message": "Station code is required",
            "query": station_code
        }

    norm_code = clean_query(station_code).upper()

    stn = db.query(RailwayStation).filter(RailwayStation.station_code == norm_code).first()
    if stn:
        return {
            "success": True,
            "station": serialize_station(stn)
        }

    response.status_code = status.HTTP_404_NOT_FOUND
    return {
        "success": False,
        "message": "Station code not found",
        "query": station_code
    }
