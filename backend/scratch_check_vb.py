import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop

db = SessionLocal()
try:
    for t_num in ['20665', '06020']:
        t = db.query(Train).filter(Train.train_number == t_num).first()
        if not t:
            print(f"Train {t_num} not found")
            continue
        print(f"\n=== Train {t.train_number}: {t.train_name} ({t.source_code} -> {t.destination_code}) ===")
        stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == t_num).order_by(TrainRouteStop.sequence).all()
        for st in stops:
            code = st.station.code if st.station else st.station_code
            name = st.station.name if st.station else st.station_name
            print(f"  Seq {st.sequence:02d}: {code} ({name}) | arr={st.arrival_min} ({st.arrival_min//60:02d}:{st.arrival_min%60:02d}), dep={st.departure_min} ({st.departure_min//60:02d}:{st.departure_min%60:02d}), km={st.distance_km}")
finally:
    db.close()
