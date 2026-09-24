import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import RailwaySection, Station, Corridor

db = SessionLocal()
try:
    all_sections = db.query(RailwaySection).all()
    print(f"Total railway sections in DB: {len(all_sections)}")
    
    # Check for sections with MDU, TDN, TMQ, VPT, SRT, CVP, KDU, MEJ, TEN
    c40_stn_codes = {'MDU', 'TDN', 'TMQ', 'VPT', 'SRT', 'CVP', 'KDU', 'MEJ', 'TEN'}
    matching_secs = []
    for s in all_sections:
        f = s.from_station.code if s.from_station else ''
        t = s.to_station.code if s.to_station else ''
        if f in c40_stn_codes or t in c40_stn_codes:
            matching_secs.append((s.id, s.section_id, s.name, f, t, s.corridor_id, s.length_km))
            
    print(f"\nSections matching C40 station codes: {len(matching_secs)}")
    for sid, scode, sname, f, t, cid, km in matching_secs:
        print(f"  ID {sid}: {scode} | {f} -> {t} | cid={cid} | {km}km | {sname}")
        
    print("\nAll Corridors:")
    for c in db.query(Corridor).all():
        print(f"  Corridor {c.id} ({c.prototype_code}): {c.name} ({c.start_station_code} -> {c.end_station_code})")
finally:
    db.close()
