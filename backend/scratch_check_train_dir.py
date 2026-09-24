import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import Train, TrainMovement, RailwaySection

db = SessionLocal()
try:
    for t_num in ["20665", "06020", "17235", "20666"]:
        t = db.query(Train).filter(Train.train_number == t_num).first()
        m = db.query(TrainMovement).filter(TrainMovement.train_number == t_num).first()
        print(f"Train {t_num}: name={t.train_name if t else '?'}, type={t.train_type if t else '?'}, source={t.source_code if t else '?'}->{t.destination_code if t else '?'}")
        if m:
            print(f"  Movement: dir={m.direction}, speed={m.speed_kmh}, status={m.status}")
finally:
    db.close()
