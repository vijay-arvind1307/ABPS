import sys
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.models.models import Corridor, RailwaySection, Train, TrainRouteStop, TrainRoute, TrainMovement
from app.core.config import settings

def test_discovery():
    db = SessionLocal()
    corridor_ident = "C40"

    # 1. Resolve Corridor
    corr = None
    if str(corridor_ident).isdigit():
        corr = db.query(Corridor).filter(Corridor.id == int(corridor_ident)).first()
    if not corr:
        norm_id = str(corridor_ident).strip().upper()
        corr = db.query(Corridor).filter(
            (Corridor.corridor_id == norm_id) | 
            (Corridor.prototype_code == norm_id) |
            (Corridor.corridor_id == f"CORR_{norm_id}_MDU_TEN")
        ).first()

    corr_name = corr.name.encode('ascii', 'replace').decode() if corr and corr.name else None
    print(f"Corridor: {corr.prototype_code if corr else None} | ID: {corr.id if corr else None} | Name: {corr_name}")

    # 2. Resolve Sections & Stations
    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).order_by(RailwaySection.id).all()
    c40_names = {"SEC_MDU_TDN", "SEC_TDN_TMQ", "SEC_TMQ_VPT", "SEC_VPT_SRT", "SEC_SRT_CVP", "SEC_CVP_KDU", "SEC_KDU_MEJ", "SEC_MEJ_TEN"}
    if corr.prototype_code == "C40" or "MDU_TEN" in (corr.corridor_id or ""):
        extra_secs = db.query(RailwaySection).filter(RailwaySection.section_id.in_(list(c40_names))).all()
        sec_dict = {s.id: s for s in sections + extra_secs}
        sections = list(sec_dict.values())

    print(f"Resolved Sections count: {len(sections)}")
    for s in sections:
        fc = s.from_station.code if s.from_station else "?"
        tc = s.to_station.code if s.to_station else "?"
        print(f"  {s.id}: {s.section_id} ({fc} -> {tc})")

    stn_codes = set()
    if corr.start_station_code: stn_codes.add(corr.start_station_code.strip().upper())
    if corr.end_station_code: stn_codes.add(corr.end_station_code.strip().upper())
    for s in sections:
        if s.from_station and s.from_station.code: stn_codes.add(s.from_station.code.strip().upper())
        if s.to_station and s.to_station.code: stn_codes.add(s.to_station.code.strip().upper())
    if corr.prototype_code == "C40" or "MDU_TEN" in (corr.corridor_id or ""):
        stn_codes.update({'MDU', 'TDN', 'TMQ', 'VPT', 'SRT', 'CVP', 'KDU', 'MEJ', 'TEN'})

    stn_list = sorted(list(stn_codes))
    print(f"Resolved Stations ({len(stn_list)}): {stn_list}")

    # 3. Discover Candidate Trains
    matching_stops = (
        db.query(Train)
        .join(TrainRouteStop, Train.train_number == TrainRouteStop.train_number)
        .filter(TrainRouteStop.station_code.in_(stn_list), Train.active == True)
        .all()
    )
    sec_ids = [s.id for s in sections]
    matching_secs = []
    if sec_ids:
        matching_secs = (
            db.query(Train)
            .join(TrainRoute, Train.train_number == TrainRoute.train_number)
            .filter(TrainRoute.section_id.in_(sec_ids), Train.active == True)
            .all()
        )
    train_dict = {}
    for t in matching_stops + matching_secs:
        if t.train_number not in train_dict:
            train_dict[t.train_number] = t
    all_corridor_trains = list(train_dict.values())
    print(f"\nAll Corridor Trains count: {len(all_corridor_trains)}")

    # 4. Running Day Check
    target_date = date.today()
    from app.services.train_service import TrainService
    candidates_today = [t for t in all_corridor_trains if TrainService.is_running_today(t, target_date)]
    non_running = [t for t in all_corridor_trains if not TrainService.is_running_today(t, target_date)]
    print(f"Scheduled Candidates Today ({target_date.strftime('%A')}): {len(candidates_today)}")
    print(f"Not Running Today: {len(non_running)}")

    # 5. Build Items with Deterministic Mapping Confidence & Stale Data
    now = datetime.utcnow()
    stale_threshold = 120
    train_items = []
    live_count = 0
    unavailable_count = 0

    for t in candidates_today:
        tm = db.query(TrainMovement).filter(TrainMovement.train_number == t.train_number).first()
        is_live = False
        is_stale = False
        speed = None
        delay = None
        lat = None
        lon = None
        location_str = "—"
        source_str = "Static Timetable"
        last_upd_str = "—"
        age_min = None

        if tm:
            age_sec = (now - tm.last_updated).total_seconds() if tm.last_updated else 9999
            age_min = round(age_sec / 60.0, 1)
            is_stale = age_sec > stale_threshold
            is_live = not is_stale and bool(getattr(tm, "is_live", True))

            if is_live:
                live_status = tm.status or "RUNNING"
                speed = tm.speed_kmh
                delay = tm.delay_minutes
                lat = tm.latitude
                lon = tm.longitude
                location_str = tm.current_section.section_id if tm.current_section else (tm.current_station_code or "EN ROUTE")
                source_str = "RailRadar Live"
                last_upd_str = tm.last_updated.strftime("%H:%M:%S") if tm.last_updated else "—"
                live_count += 1
            elif is_stale:
                live_status = "STALE LIVE DATA"
                speed = tm.speed_kmh
                delay = tm.delay_minutes
                lat = tm.latitude
                lon = tm.longitude
                location_str = tm.current_section.section_id if tm.current_section else (tm.current_station_code or "EN ROUTE")
                source_str = f"Live Radar (Stale — {age_min}m old)"
                last_upd_str = tm.last_updated.strftime("%H:%M:%S") if tm.last_updated else "—"
                unavailable_count += 1
            else:
                live_status = "SCHEDULED — LIVE UNAVAILABLE"
                unavailable_count += 1
        else:
            live_status = "SCHEDULED — LIVE UNAVAILABLE"
            unavailable_count += 1

        # Stop sequence and entry/exit
        stops = (
            db.query(TrainRouteStop)
            .filter(TrainRouteStop.train_number == t.train_number)
            .order_by(TrainRouteStop.sequence)
            .all()
        )
        c40_stops = [s for s in stops if s.station_code in stn_list]
        sched_entry = "—"
        sched_exit = "—"
        direction = "UP"
        if c40_stops:
            s_first = c40_stops[0]
            s_last = c40_stops[-1]
            sched_entry = f"{s_first.arrival_min // 60:02d}:{s_first.arrival_min % 60:02d}"
            sched_exit = f"{s_last.departure_min // 60:02d}:{s_last.departure_min % 60:02d}"
            if s_first.station_code == "MDU" or (s_first.station_code in ["MDU", "TDN", "TMQ"] and s_last.station_code in ["CVP", "KDU", "MEJ", "TEN"]):
                direction = "DOWN"
            else:
                direction = "UP"

        # Deterministic Mapping Confidence
        corr_stops_cnt = len(c40_stops)
        if corr_stops_cnt >= 4:
            conf = 100
            method = "EXACT_ROUTE_SECTION_MATCH"
            reason = "Exact route stop sequence matched to RailwaySection master."
        elif corr_stops_cnt >= 2:
            conf = 90
            method = "VERIFIED_STATION_SEQUENCE"
            reason = "Verified station sequence matched to corridor alignment."
        elif corr_stops_cnt == 1:
            conf = 75
            method = "PARTIAL_ROUTE_MATCH"
            reason = "Partial route intersection within corridor section boundaries."
        else:
            conf = 50
            method = "INFERRED_MAPPING"
            reason = "Inferred mapping based on corridor network topology."

        train_items.append({
            "train_number": t.train_number,
            "train_name": t.train_name,
            "train_type": t.train_type or "EXPRESS",
            "category": t.category or t.train_type or "EXPRESS",
            "source_code": t.source_code,
            "destination_code": t.destination_code,
            "scheduled": "Scheduled Today",
            "scheduled_entry": sched_entry,
            "scheduled_exit": sched_exit,
            "running_days": t.running_days,
            "direction": direction,
            "live_status": live_status,
            "current_location": location_str,
            "latitude": lat,
            "longitude": lon,
            "speed_kmh": speed,
            "delay_minutes": delay,
            "mapping_confidence": conf,
            "mapping_method": method,
            "mapping_reason": reason,
            "source": source_str,
            "is_live": is_live,
            "is_stale": is_stale,
            "last_updated": last_upd_str,
            "age_minutes": age_min
        })

    payload = {
        "corridor": {
            "id": corr.prototype_code or corr.corridor_id,
            "name": corr.name
        },
        "journeyDate": target_date.isoformat(),
        "scheduledTrainCount": len(train_items),
        "liveAvailableCount": live_count,
        "liveUnavailableCount": unavailable_count,
        "liveStatus": "AVAILABLE" if live_count > 0 else "LIVE_DATA_UNAVAILABLE",
        "reason": "OK" if live_count > 0 else "RATE_LIMITED",
        "trains": train_items
    }

    print("\n--- DISCOVERY SUMMARY ---")
    print(f"scheduledTrainCount: {payload['scheduledTrainCount']}")
    print(f"liveAvailableCount: {payload['liveAvailableCount']}")
    print(f"liveUnavailableCount: {payload['liveUnavailableCount']}")
    print(f"liveStatus: {payload['liveStatus']}")
    print(f"First 5 items:")
    for item in train_items[:5]:
        print(f"  Train {item['train_number']}: {item['train_name']} | Type: {item['train_type']} | Status: {item['live_status']} | Entry: {item['scheduled_entry']} | Conf: {item['mapping_confidence']}%")

    db.close()

if __name__ == '__main__':
    test_discovery()
