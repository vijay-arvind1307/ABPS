import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop, RailwaySection, Corridor
from app.algorithms.occupancy import OccupancyEngine

db = SessionLocal()
try:
    c40 = db.query(Corridor).filter(Corridor.id == 30).first()
    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == 30).all()
    print(f"Sections for C40 in DB: {len(sections)}")
    sec_dicts = [
        {
            "id": s.id,
            "section_id": s.section_id,
            "name": s.name,
            "from_station_id": s.from_station_id,
            "to_station_id": s.to_station_id,
            "from_station_code": s.from_station.code if s.from_station else None,
            "to_station_code": s.to_station.code if s.to_station else None,
            "length_km": s.length_km,
            "max_speed_kmh": s.max_speed_kmh or 100.0
        }
        for s in sections
    ]

    for t_num in ["20665", "06020", "17235"]:
        t = db.query(Train).filter(Train.train_number == t_num).first()
        stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == t_num).order_by(TrainRouteStop.sequence).all()
        stops_dicts = [
            {
                "station_id": st.station_id,
                "station_code": st.station.code if st.station else st.station_code,
                "sequence": st.sequence,
                "arrival_min": st.arrival_min,
                "departure_min": st.departure_min,
                "halt_min": st.halt_min,
                "distance_km": st.distance_km
            }
            for st in stops
        ]

        train_dict = {
            "train_number": t.train_number,
            "train_name": t.train_name,
            "train_type": t.train_type,
            "priority_level": t.priority_level
        }

        occs = OccupancyEngine.calculate_section_occupancies(
            train=train_dict,
            route_stops=stops_dicts,
            sections=sec_dicts
        )

        print(f"\n--- Train {t_num} ({t.train_name}) Section Occupancies ({len(occs)}) ---")
        for o in sorted(occs, key=lambda x: x["estimated_entry_min"]):
            sec_name = o.get("section_code") or o.get("section_name")
            e_min = o["estimated_entry_min"]
            x_min = o["estimated_exit_min"]
            norm_e = e_min % 1440
            norm_x = x_min % 1440
            print(f"  {sec_name:12s} | raw: {e_min}m->{x_min}m | daily: {norm_e//60:02d}:{norm_e%60:02d} -> {norm_x//60:02d}:{norm_x%60:02d} | dur={o['traversal_duration_min']}m | dir={o['direction']}")
finally:
    db.close()
