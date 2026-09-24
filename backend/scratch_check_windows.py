import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import BlockWindow

db = SessionLocal()
try:
    windows = db.query(BlockWindow).all()
    print(f"Total BlockWindows in DB: {len(windows)}")
    for w in windows:
        print(f"  ID {w.id}: {w.window_code} | sec_id={w.section_id} | corr_id={w.corridor_id} | {w.start_min//60:02d}:{w.start_min%60:02d} - {w.end_min//60:02d}:{w.end_min%60:02d} ({w.usable_duration_min}m) | sec={w.section.name if w.section else '?'}")
finally:
    db.close()
