import sys
sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.models.models import Train, TrainRouteStop, RailwaySection, Corridor
from datetime import date

db = SessionLocal()
c40 = db.query(Corridor).filter(Corridor.prototype_code == 'C40').first()
c40_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == c40.id).all() if c40 else []

# Check sections in 62 as well
c62 = db.query(Corridor).filter(Corridor.id == 62).first()
c62_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == 62).all() if c62 else []

all_c40_secs = c40_secs + [s for s in c62_secs if s.section_id != 'SEC_MEJ_TN']
print(f"Total physical C40 sections: {len(all_c40_secs)}")

c40_stns = set()
for s in all_c40_secs:
    if s.from_station: c40_stns.add(s.from_station.code)
    if s.to_station: c40_stns.add(s.to_station.code)

print(f"C40 Stations ({len(c40_stns)}): {sorted(list(c40_stns))}")

c40_trains = (
    db.query(Train)
    .join(TrainRouteStop, Train.train_number == TrainRouteStop.train_number)
    .filter(TrainRouteStop.station_code.in_(list(c40_stns)))
    .distinct()
    .all()
)
print(f"\nTotal C40 trains in DB: {len(c40_trains)}")
type_counts = {}
for t in c40_trains:
    tt = t.train_type or "UNKNOWN"
    type_counts[tt] = type_counts.get(tt, 0) + 1
print("Train Types breakdown:", type_counts)

# Today's date check
today = date.today()
today_name = today.strftime("%a").upper()
print(f"\nToday is: {today.isoformat()} ({today.strftime('%A')})")

from app.services.train_service import TrainService
running_today = [t for t in c40_trains if TrainService.is_running_today(t, today)]
not_running_today = [t for t in c40_trains if not TrainService.is_running_today(t, today)]

print(f"Running today ({today_name}): {len(running_today)}")
print(f"NOT running today: {len(not_running_today)}")

print("\n--- SAMPLE RUNNING TODAY TRAINS ---")
for t in running_today[:15]:
    stops = db.query(TrainRouteStop).filter(TrainRouteStop.train_number == t.train_number).order_by(TrainRouteStop.sequence).all()
    c40_stops_in_train = [s.station_code for s in stops if s.station_code in c40_stns]
    print(f"  {t.train_number:5s} | {t.train_type:12s} | days: {str(t.running_days):15s} | {t.source_code}->{t.destination_code} | C40 stops: {c40_stops_in_train} | {t.train_name}")

print("\n--- NOT RUNNING TODAY TRAINS ---")
for t in not_running_today:
    print(f"  {t.train_number:5s} | {t.train_type:12s} | days: {str(t.running_days):15s} | {t.train_name}")

db.close()
