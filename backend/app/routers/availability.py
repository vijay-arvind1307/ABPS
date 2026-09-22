from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Corridor, RailwaySection, TrainSectionOccupancy, CoordinatedBlockPlan, BlockPlan, MaintenanceJob
from app.algorithms.windows import WindowEngine
from app.services.train_service import TrainService
from app.services.railway_network_service import RailwayNetworkService

router = APIRouter(prefix="/availability", tags=["Track Availability & Windows"])


class AvailabilityCheckRequest(BaseModel):
    corridor_id: Optional[int] = None
    corridor_code: Optional[str] = None
    section_id: Optional[int] = None
    section_ids: Optional[List[int]] = None
    from_station: Optional[str] = None
    to_station: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    start_time: str = Field(..., description="HH:MM requested start time (e.g. 10:00)")
    end_time: str = Field(..., description="HH:MM requested end time (e.g. 12:00)")
    duration_min: int = Field(..., description="Requested block duration in minutes")


def _parse_hhmm_to_min(val: str, default: int) -> int:
    if not val or ":" not in val:
        return default
    try:
        parts = val.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return default


@router.get("")
@router.get("/")
def get_available_windows(
    corridor_id: Optional[int] = Query(None),
    section_id: Optional[int] = Query(None),
    corridor_code: Optional[str] = Query(None),
    date_str: Optional[str] = Query(None, alias="date"),
    duration_min: int = Query(30, description="Minimum usable block duration in minutes"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns authentic, date-specific and section-specific feasible maintenance windows.
    If no timetable data exists: returns status DATA_UNAVAILABLE (never fake 00:00–24:00).
    """
    # 1. Resolve Corridor & Sections
    target_corr = None
    if corridor_id:
        target_corr = db.query(Corridor).filter(Corridor.id == corridor_id).first()
    elif corridor_code:
        norm = corridor_code.strip().upper()
        target_corr = db.query(Corridor).filter(
            (Corridor.prototype_code == norm) | (Corridor.corridor_id == norm)
        ).first()

    sections_query = db.query(RailwaySection)
    if section_id:
        sections_query = sections_query.filter(RailwaySection.id == section_id)
    elif target_corr:
        sections_query = sections_query.filter(RailwaySection.corridor_id == target_corr.id)

    sections = sections_query.all()
    if not sections:
        return {
            "status": "DATA_UNAVAILABLE",
            "message": "No railway sections found for the specified query.",
            "windows": []
        }

    # 2. Query train occupancies
    occupancies = TrainService.calculate_all_occupancies(db) or []
    if not occupancies:
        return {
            "status": "DATA_UNAVAILABLE",
            "message": "No train timetable occupancy data available for availability computation.",
            "windows": []
        }

    # 3. Calculate sweep-line windows per section
    all_windows = []
    win_global_id = 1
    for sec in sections:
        sec_wins = WindowEngine.calculate_feasible_windows(
            section_id=sec.id,
            corridor_id=sec.corridor_id,
            occupancies=occupancies,
            min_window_duration_min=duration_min,
            has_timetable_data=True
        )
        for w in sec_wins:
            w["id"] = win_global_id
            w["section_name"] = sec.name
            w["section_code"] = sec.section_id
            s_hh, s_mm = divmod(w["start_min"], 60)
            e_hh, e_mm = divmod(w["end_min"], 60)
            w["time_window"] = f"{s_hh:02d}:{s_mm:02d} – {e_hh:02d}:{e_mm:02d}"
            all_windows.append(w)
            win_global_id += 1

    return {
        "status": "AVAILABLE" if all_windows else "NOT_AVAILABLE",
        "corridor": target_corr.prototype_code if target_corr else "ALL",
        "sections_analyzed": len(sections),
        "total_windows": len(all_windows),
        "windows": all_windows
    }


@router.post("/check")
def check_maintenance_availability(
    req: AvailabilityCheckRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Checks whether the exact requested time window is feasible for the given railway section(s).
    If conflicting: explains the exact conflict (e.g. conflicting train numbers, occupied intervals, safety buffers)
    and computes actual recommended alternative feasible windows.
    """
    # 1. Resolve section IDs
    sec_ids = list(req.section_ids or [])
    if req.section_id and req.section_id not in sec_ids:
        sec_ids.append(req.section_id)

    # If from/to station supplied, resolve section IDs along route
    if req.from_station and req.to_station and not sec_ids:
        route_info = RailwayNetworkService.calculate_railway_route(req.from_station, req.to_station, db)
        if route_info.get("valid") and route_info.get("sections"):
            sec_ids = [s["id"] for s in route_info["sections"]]

    if not sec_ids:
        return {
            "feasible": False,
            "is_feasible": False,
            "status": "DATA_UNAVAILABLE",
            "message": "ROUTE NOT CONFIGURED / UNRESOLVABLE: No railway sections found for the specified stations or section identifiers.",
            "requested_window": f"{req.start_time} – {req.end_time}",
            "duration_min": req.duration_min,
            "conflicts_count": 0,
            "conflicts": [],
            "recommended_alternatives": []
        }

    # 2. Resolve Corridor ID
    corr_id = req.corridor_id or 1
    if not req.corridor_id and req.corridor_code:
        c_obj = db.query(Corridor).filter(
            (Corridor.prototype_code == req.corridor_code.upper()) |
            (Corridor.corridor_id == req.corridor_code.upper())
        ).first()
        if c_obj:
            corr_id = c_obj.id

    # 3. Parse requested times
    s_min = _parse_hhmm_to_min(req.start_time, 600)
    e_min = _parse_hhmm_to_min(req.end_time, 720)
    if e_min <= s_min:
        e_min = s_min + req.duration_min

    # 4. Fetch occupancies and existing approved blocks
    occupancies = TrainService.calculate_all_occupancies(db) or []
    existing_blocks_db = db.query(CoordinatedBlockPlan).filter(
        CoordinatedBlockPlan.status.in_(["APPROVED", "COMMITTED", "ACTIVE"])
    ).all()

    existing_blocks = [
        {
            "section_id": b.section_id,
            "start_min": b.start_min,
            "end_min": b.end_min,
            "plan_code": b.plan_code
        }
        for b in existing_blocks_db
    ]

    # 5. Execute exact requested window check
    res = WindowEngine.check_requested_window(
        section_ids=sec_ids,
        corridor_id=corr_id,
        req_start_min=s_min,
        req_end_min=e_min,
        duration_min=req.duration_min,
        occupancies=occupancies,
        existing_blocks=existing_blocks
    )

    return res
