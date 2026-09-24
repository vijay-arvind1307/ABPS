import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from datetime import date
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.services.train_service import TrainService
from app.models.models import Corridor, Train, RailwaySection, TrainRouteStop, TrainSectionOccupancy

db = SessionLocal()
try:
    corridor = db.query(Corridor).filter(Corridor.id == 30).first()
    print(f"Corridor: {corridor.name if corridor else 'None'}")
    
    sections = db.query(RailwaySection).filter(RailwaySection.corridor_id == 30).all()
    print(f"Sections for C40 in DB: {len(sections)}")
    for s in sections:
        print(f"  Sec {s.id}: {s.section_id} ({s.name}) | {s.from_station.code if s.from_station else '?'} -> {s.to_station.code if s.to_station else '?'}")

    occs = TrainService.calculate_all_occupancies(db, target_date=date(2026, 9, 23))
    print(f"\nTotal calculated occupancies: {len(occs)}")
    
    c40_sec_ids = {s.id for s in sections}
    c40_occs = [o for o in occs if o.get('section_id') in c40_sec_ids]
    print(f"Total occupancies on C40 sections: {len(c40_occs)}")
    
    # Check train 06020 and 20665
    for t_num in ['06020', '20665', '17235']:
        t_occs = [o for o in c40_occs if o.get('train_number') == t_num]
        print(f"\nOccupancies for train {t_num}: {len(t_occs)}")
        for o in t_occs:
            print(f"  Sec {o.get('section_id')} ({o.get('section_code')}): entry={o.get('estimated_entry_min')} ({o.get('estimated_entry_min')//60:02d}:{o.get('estimated_entry_min')%60:02d}), exit={o.get('estimated_exit_min')} ({o.get('estimated_exit_min')//60:02d}:{o.get('estimated_exit_min')%60:02d}), dur={o.get('traversal_duration_min')}m, dir={o.get('direction')}")
finally:
    db.close()
