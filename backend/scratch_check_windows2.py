import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import BlockWindow

db = SessionLocal()
try:
    sec_ids = [22, 23, 24, 25, 26, 27, 28, 29]
    windows = db.query(BlockWindow).filter(BlockWindow.section_id.in_(sec_ids)).all()
    print(f"BlockWindows for sections 22-29 in DB: {len(windows)}")
    for w in windows:
        print(f"  ID {w.id}: {w.window_code} | sec_id={w.section_id} | corr_id={w.corridor_id} | {w.start_min//60:02d}:{w.start_min%60:02d} - {w.end_min//60:02d}:{w.end_min%60:02d} ({w.usable_duration_min}m) | sec={w.section.name if w.section else '?'}")
finally:
    db.close()
