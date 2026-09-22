import pandas as pd
import json
import os
import sys

sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.models.models import Corridor, RailwaySection, Station, Train, TrainRouteStop, TrainRoute, TrainMovement

db = SessionLocal()

print("="*70)
print("AUDIT: DOCUMENTS & MASTER DATASETS")
print("="*70)

# Check Madurai_to_TVL_train_details.xlsx
excel_path = 'documents/Madurai_to_TVL_train_details.xlsx'
if os.path.exists(excel_path):
    df = pd.read_excel(excel_path)
    print(f"\n[XLSX] {excel_path} has {len(df)} trains:")
    print("Columns:", df.columns.tolist())
    for idx, row in df.iterrows():
        tnum = str(row.get('train_number') or row.get('Train Number') or row.get('number') or '')
        tname = str(row.get('train_name') or row.get('Train Name') or row.get('name') or '')
        dep = str(row.get('departure_time') or row.get('Departure Time') or '')
        arr = str(row.get('arrival_time') or row.get('Arrival Time') or '')
        days = str(row.get('running_days') or row.get('Days') or '')
        print(f"  {idx+1:2d}. Train {tnum}: {tname} | {dep} -> {arr} | days={days}")

# Check Where_Is_My_Train_Detailed_Data.xlsx
wimt_path = 'documents/Where_Is_My_Train_Detailed_Data.xlsx'
if os.path.exists(wimt_path):
    xl = pd.ExcelFile(wimt_path)
    print(f"\n[XLSX] {wimt_path} sheets: {xl.sheet_names}")
    for s in xl.sheet_names:
        df_w = pd.read_excel(wimt_path, sheet_name=s)
        print(f"  Sheet '{s}': {len(df_w)} rows, columns: {df_w.columns.tolist()[:6]}")

print("\n" + "="*70)
print("AUDIT: DATABASE INVENTORY")
print("="*70)
total_trains = db.query(Train).count()
total_routes = db.query(TrainRoute).count()
total_stops = db.query(TrainRouteStop).count()
trains_with_stops = db.query(TrainRouteStop.train_number).distinct().count()
trains_with_days = db.query(Train).filter(Train.running_days != None, Train.running_days != '').count()
trains_without_days = db.query(Train).filter((Train.running_days == None) | (Train.running_days == '')).count()

print(f"Total Trains in DB: {total_trains}")
print(f"Total Routes (TrainRoute): {total_routes}")
print(f"Total Route Stops (TrainRouteStop): {total_stops}")
print(f"Trains with Route Stops: {trains_with_stops}")
print(f"Trains without Route Stops: {total_trains - trains_with_stops}")
print(f"Trains with Running Days: {trains_with_days}")
print(f"Trains without Running Days: {trains_without_days}")

# Check Corridor C40
c40 = db.query(Corridor).filter(Corridor.prototype_code == 'C40').first()
print(f"\nCorridor C40 (ID: {c40.id if c40 else 'None'}): {c40.name.encode('ascii', 'replace').decode() if c40 else 'None'}")
c40_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == c40.id).all() if c40 else []
print(f"RailwaySections mapped to C40: {len(c40_secs)}")
for s in c40_secs:
    fc = s.from_station.code if s.from_station else '?'
    tc = s.to_station.code if s.to_station else '?'
    print(f"  {s.id}: {s.section_id} ({fc} -> {tc}) {s.name.encode('ascii', 'replace').decode()}")

# Check sections in Corridor 62 (legacy unnumbered)
c62 = db.query(Corridor).filter(Corridor.id == 62).first()
if c62:
    c62_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == 62).all()
    print(f"\nRailwaySections currently mapped to legacy Corridor 62 ({c62.name.encode('ascii', 'replace').decode()}): {len(c62_secs)}")
    for s in c62_secs:
        fc = s.from_station.code if s.from_station else '?'
        tc = s.to_station.code if s.to_station else '?'
        print(f"  {s.id}: {s.section_id} ({fc} -> {tc}) {s.name.encode('ascii', 'replace').decode()}")

# Station union for all C40 physical sections
c40_stn_codes = {'MDU', 'TDN', 'TMQ', 'VPT', 'SRT', 'CVP', 'KDU', 'MEJ', 'TEN'}
c40_all_matching_trains = (
    db.query(Train)
    .join(TrainRouteStop, Train.train_number == TrainRouteStop.train_number)
    .filter(TrainRouteStop.station_code.in_(list(c40_stn_codes)))
    .distinct()
    .all()
)
print(f"\nTrains with stops matching C40 stations ({c40_stn_codes}): {len(c40_all_matching_trains)}")

db.close()

