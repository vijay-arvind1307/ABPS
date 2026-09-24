import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop, Station

db = SessionLocal()
try:
    print(f"Total Trains in DB: {db.query(Train).count()}")
    
    # Check stops for train 20665, 06020, 17235
    for t_num in ['20665', '06020', '17235']:
        t = db.query(Train).filter(Train.train_number == t_num).first()
        if not t:
            print(f"Train {t_num} not found in DB")
            continue
        print(f"\nTrain {t.train_number} ({t.train_name}) | type={t.train_type} | origin={t.source_code} -> dest={t.destination_code}")
        stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == t_num).order_by(TrainRouteStop.sequence).all()
        print(f"  Stops ({len(stops)}):")
        for st in stops:
            stn = st.station
            print(f"    Seq {st.sequence}: {stn.code if stn else st.station_id} ({stn.name if stn else '?'}) | arr={st.arrival_min} ({st.arrival_min//60:02d}:{st.arrival_min%60:02d}), dep={st.departure_min} ({st.departure_min//60:02d}:{st.departure_min%60:02d}), km={st.distance_km}")
finally:
    db.close()
