import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop

db = SessionLocal()
try:
    t = db.query(Train).filter(Train.train_number == '20665').first()
    print(f"Train 20665: {t.train_name if t else 'Not found'}")
    if t:
        stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == '20665').order_by(TrainRouteStop.sequence).all()
        for st in stops:
            code = st.station.code if st.station else st.station_code
            print(f"  Seq {st.sequence:02d}: {code} | arr={st.arrival_min} ({st.arrival_min//60:02d}:{st.arrival_min%60:02d}), dep={st.departure_min} ({st.departure_min//60:02d}:{st.departure_min%60:02d}), km={st.distance_km}")
finally:
    db.close()
