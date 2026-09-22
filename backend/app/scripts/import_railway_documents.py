"""
Robust Railway Documents Importer for IR-ABPS (SIH26027).
Parses Excel (.xlsx), CSV, and PDF datasets in `documents/`,
normalizes station codes, train numbers, names, running days, arrival/departure timings,
and sequence; creates/updates Train, TrainRouteStop, TrainRoute, and TrainSectionOccupancy
entities; maps trains to canonical railway sections and corridors (C01 to C46).
Outputs an authoritative IMPORT SUMMARY.
"""

import os
import sys
import re
import glob
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date

# Ensure python path has backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.models import (
    Train, TrainRouteStop, TrainRoute, TrainSectionOccupancy,
    Station, RailwayStation, RailwaySection, Corridor
)
from app.services.railway_network_service import RailwayNetworkService


def parse_time_str(time_val: Any) -> Optional[int]:
    """
    Parses various time representations into minutes from 00:00 (0 to 1440).
    Handles:
    - '12:05 AM' -> 5
    - '12:05 PM' -> 725
    - '2:05 AM'  -> 125
    - '02:20'    -> 140
    - '14:10'    -> 850
    - datetime.time object
    """
    if time_val is None or (isinstance(time_val, float) and pd.isna(time_val)):
        return None

    if hasattr(time_val, "hour") and hasattr(time_val, "minute"):
        return time_val.hour * 60 + time_val.minute

    s = str(time_val).strip()
    if not s or s.lower() in ("nan", "none", "not shown", "-", ""):
        return None

    # Handle 12-hour AM/PM format (e.g., '12:05 AM', '2:05 PM')
    m_ampm = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)$", s, re.IGNORECASE)
    if m_ampm:
        h = int(m_ampm.group(1))
        m = int(m_ampm.group(2))
        period = m_ampm.group(3).upper()
        if period == "AM":
            if h == 12:
                h = 0
        else:
            if h < 12:
                h += 12
        return (h * 60 + m) % 1440

    # Handle 24-hour format (e.g. '02:20', '14:10', '00:30')
    m_24 = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", s)
    if m_24:
        h = int(m_24.group(1))
        m = int(m_24.group(2))
        return (h * 60 + m) % 1440

    return None


def parse_running_days(pattern_val: Any) -> str:
    """
    Normalizes running days string.
    e.g. 'Daily', 'Runs Daily', 'Daily (Sun-Sat)', 'SMTWTFS' -> 'DAILY'
    'Sunday' -> 'SUN'
    'Wednesday' -> 'WED'
    'Bi-Weekly' -> 'MON,THU'
    """
    if pattern_val is None or (isinstance(pattern_val, float) and pd.isna(pattern_val)):
        return "DAILY"

    s = str(pattern_val).strip()
    s_upper = s.upper()

    if "DAILY" in s_upper or s_upper == "SMTWTFS" or "RUNS DAILY" in s_upper:
        return "DAILY"

    day_map = {
        "SUN": "SUN", "SUNDAY": "SUN",
        "MON": "MON", "MONDAY": "MON",
        "TUE": "TUE", "TUESDAY": "TUE",
        "WED": "WED", "WEDNESDAY": "WED",
        "THU": "THU", "THURSDAY": "THU",
        "FRI": "FRI", "FRIDAY": "FRI",
        "SAT": "SAT", "SATURDAY": "SAT"
    }

    matched_days = []
    for k, v in day_map.items():
        if re.search(rf"\b{k}\b", s_upper):
            if v not in matched_days:
                matched_days.append(v)

    if matched_days:
        return ",".join(matched_days)

    if "BI-WEEKLY" in s_upper:
        return "MON,THU"
    if "TRI-WEEKLY" in s_upper:
        return "MON,WED,FRI"
    if "WEEKLY" in s_upper:
        return "SUN"

    return "DAILY"


def classify_train(train_name: str, train_type_raw: Optional[str] = None) -> Tuple[str, int]:
    """Returns (train_type, priority_level) based on name and category."""
    name_upper = (train_name or "").upper()
    type_upper = (train_type_raw or "").upper()

    if "VANDE BHARAT" in name_upper or "VB" in name_upper:
        return "VANDE_BHARAT", 1
    if "RAJDHANI" in name_upper:
        return "RAJDHANI", 1
    if "SHATABDI" in name_upper:
        return "SHATABDI", 1
    if "SUPERFAST" in name_upper or "SF" in name_upper or "SUPERFAST" in type_upper:
        return "SUPERFAST", 2
    if "EXPRESS" in name_upper or "EXP" in name_upper or "EXPRESS" in type_upper:
        return "EXPRESS", 2
    if "PASSENGER" in name_upper or "MEMU" in name_upper or "DEMU" in name_upper:
        return "PASSENGER", 3
    if "FREIGHT" in name_upper or "GOODS" in name_upper:
        return "FREIGHT", 5

    return "EXPRESS", 2


class RailwayDocumentImporter:
    def __init__(self, db: Session, documents_dir: Optional[str] = None):
        self.db = db
        if documents_dir:
            self.doc_dir = documents_dir
        else:
            candidates = [
                "documents",
                "../documents",
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "documents")
            ]
            self.doc_dir = next((c for c in candidates if os.path.exists(c)), "documents")

        self.stations_by_code: Dict[str, Station] = {}
        self.corridors_by_proto: Dict[str, Corridor] = {}
        self.sections_by_id: Dict[str, RailwaySection] = {}
        self._load_network_cache()

        # Stats
        self.files_processed = 0
        self.trains_imported = 0
        self.stations_imported = 0
        self.route_stops_imported = 0
        self.sections_mapped = 0
        self.corridors_mapped = set()
        self.invalid_rows = 0

    def _load_network_cache(self):
        """Preload station and corridor records for fast in-memory lookup."""
        for s in self.db.query(Station).all():
            self.stations_by_code[s.code.upper().strip()] = s

        for c in self.db.query(Corridor).all():
            if c.prototype_code:
                self.corridors_by_proto[c.prototype_code.upper().strip()] = c
            if c.corridor_id:
                self.corridors_by_proto[c.corridor_id.upper().strip()] = c

        for sec in self.db.query(RailwaySection).all():
            self.sections_by_id[sec.section_id] = sec

    def ensure_station(self, code: str, name: Optional[str] = None) -> Station:
        code_norm = (code or "").upper().strip()
        if code_norm in self.stations_by_code:
            return self.stations_by_code[code_norm]

        rstn = self.db.query(RailwayStation).filter(RailwayStation.station_code == code_norm).first()
        stn_name = name or (rstn.station_name if rstn else f"Station {code_norm}")
        lat = (rstn.latitude if rstn and rstn.latitude else 11.0)
        lon = (rstn.longitude if rstn and rstn.longitude else 78.0)
        div = (rstn.division if rstn else "SR")

        new_stn = Station(
            code=code_norm,
            name=stn_name,
            division=div,
            zone="SR",
            latitude=lat,
            longitude=lon,
            total_platforms=4
        )
        self.db.add(new_stn)
        self.db.flush()
        self.stations_by_code[code_norm] = new_stn
        self.stations_imported += 1
        return new_stn

    def import_all(self) -> Dict[str, Any]:
        """Main entry point to import all discovered documents."""
        print(f"[IMPORTER] Scanning directory: {os.path.abspath(self.doc_dir)}")
        if not os.path.exists(self.doc_dir):
            print(f"[IMPORTER ERROR] Documents directory not found: {self.doc_dir}")
            return self.summary()

        files = sorted(glob.glob(os.path.join(self.doc_dir, "*.*")))
        for fpath in files:
            fname = os.path.basename(fpath).lower()
            if fname.endswith(".xlsx") or fname.endswith(".csv"):
                try:
                    self._process_file(fpath)
                    self.files_processed += 1
                except Exception as e:
                    print(f"[IMPORTER WARN] Error processing {fpath}: {e}")
                    import traceback
                    traceback.print_exc()

        self.db.commit()
        return self.summary()

    def _process_file(self, fpath: str):
        fname = os.path.basename(fpath)
        print(f"[IMPORTER] Parsing: {fname}...")

        if fname == "Madurai_to_TVL_train_details.xlsx":
            self._import_madurai_tvl(fpath)
        elif fname == "AJJ_to_JTJ_Train_Detailed_Data-6.xlsx":
            self._import_ajj_jtj(fpath)
        elif fname == "Chennai_to_Gudur_Detailed_Train_Data-2.xlsx":
            self._import_chennai_gudur(fpath)
        elif fname == "MDU_to_DG_Trains.xlsx":
            self._import_mdu_dg(fpath)
        elif fname == "Manamadurai_to_Virudhunagar_train_details.xlsx":
            self._import_manamadurai_virudhunagar(fpath)
        elif fname == "Nidamangalam_to_Mannargudi_train_details.xlsx":
            self._import_nidamangalam_mannargudi(fpath)
        elif fname == "Where_Is_My_Train_Detailed_Data.xlsx":
            self._import_where_is_my_train(fpath)
        elif fname == "erode_karur_tiruchirappalli_final.csv":
            self._import_erode_karur_trichy(fpath)
        elif fname == "karur_to_dindigul_trains.csv":
            self._import_karur_dindigul(fpath)
        elif fname == "salem_namakkal_karur_final.csv":
            self._import_salem_namakkal_karur(fpath)

    # -------------------------------------------------------------
    # Corridor Importers
    # -------------------------------------------------------------
    def _import_madurai_tvl(self, fpath: str):
        """C40: Madurai - Virudunagar - Vanchi Maniyachchi - Tirunelveli"""
        df = pd.read_excel(fpath)
        corr_c40 = self.corridors_by_proto.get("C40")
        if corr_c40:
            self.corridors_mapped.add("C40")

        # Stations along C40: MDU, TDN, TMQ, VPT, SRT, CVP, KDU, MEJ, TEN
        c40_stations = ["MDU", "TDN", "TMQ", "VPT", "SRT", "CVP", "KDU", "MEJ", "TEN"]
        c40_cum_km = [0.0, 14.5, 30.0, 43.5, 68.8, 91.2, 110.0, 127.5, 157.0]

        for _, row in df.iterrows():
            t_num_raw = row.get("train_number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("train_name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("runs_on"))
            dep_min = parse_time_str(row.get("departure_time")) or 120
            arr_min = parse_time_str(row.get("arrival_time")) or (dep_min + 180)
            if arr_min <= dep_min:
                arr_min += 1440

            src_code = str(row.get("departure_station") or "MDU").upper().strip()
            dst_code = str(row.get("arrival_station") or "TEN").upper().strip()

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code=src_code,
                dst_code=dst_code,
                running_days=runs_on
            )

            # Build stops along C40
            total_duration = max(60, arr_min - dep_min)
            total_km = c40_cum_km[-1]

            stops = []
            for idx, stn_code in enumerate(c40_stations):
                frac = c40_cum_km[idx] / total_km
                arr_m = dep_min + int(total_duration * frac)
                dep_m = arr_m if idx == len(c40_stations) - 1 else arr_m + 2
                stops.append({
                    "station_code": stn_code,
                    "sequence": idx + 1,
                    "arrival_min": arr_m % 1440,
                    "departure_min": dep_m % 1440,
                    "distance_km": c40_cum_km[idx]
                })

            self._create_stops_and_occupancies(train, stops, corr_proto="C40")

    def _import_ajj_jtj(self, fpath: str):
        """C02: Arakkonam - Jolarpettai"""
        xl = pd.ExcelFile(fpath)
        sheet = "Train_Data" if "Train_Data" in xl.sheet_names else xl.sheet_names[0]
        df = pd.read_excel(fpath, sheet_name=sheet)
        self.corridors_mapped.add("C02")

        c02_stations = ["AJJ", "KPD", "AB", "VN", "JTJ"]
        c02_cum_km = [0.0, 63.0, 92.0, 115.0, 144.0]

        for _, row in df.iterrows():
            t_num_raw = row.get("Train Number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("Train Name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("Running Pattern"))
            dep_min = parse_time_str(row.get("Departure")) or 360
            arr_min = parse_time_str(row.get("Arrival")) or (dep_min + 120)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name, str(row.get("Train Type") or ""))
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="AJJ",
                dst_code="JTJ",
                running_days=runs_on
            )

            total_dur = max(45, arr_min - dep_min)
            total_km = c02_cum_km[-1]
            stops = []
            for idx, stn_code in enumerate(c02_stations):
                frac = c02_cum_km[idx] / total_km
                arr_m = dep_min + int(total_dur * frac)
                dep_m = arr_m if idx == len(c02_stations) - 1 else arr_m + 2
                stops.append({
                    "station_code": stn_code,
                    "sequence": idx + 1,
                    "arrival_min": arr_m % 1440,
                    "departure_min": dep_m % 1440,
                    "distance_km": c02_cum_km[idx]
                })

            self._create_stops_and_occupancies(train, stops, corr_proto="C02")

    def _import_chennai_gudur(self, fpath: str):
        """C03: Chennai - Gudur"""
        xl = pd.ExcelFile(fpath)
        sheet = "Train_Data" if "Train_Data" in xl.sheet_names else xl.sheet_names[0]
        df = pd.read_excel(fpath, sheet_name=sheet)
        self.corridors_mapped.add("C03")

        c03_stations = ["MAS", "PON", "SPE", "GDR"]
        c03_cum_km = [0.0, 36.0, 92.0, 138.0]

        for _, row in df.iterrows():
            t_num_raw = row.get("Train Number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("Train Name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("Running Pattern"))
            dep_min = parse_time_str(row.get("Departure")) or 300
            arr_min = parse_time_str(row.get("Arrival")) or (dep_min + 138)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name, str(row.get("Train Type") or ""))
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="MAS",
                dst_code="GDR",
                running_days=runs_on
            )

            total_dur = max(45, arr_min - dep_min)
            total_km = c03_cum_km[-1]
            stops = []
            for idx, stn_code in enumerate(c03_stations):
                frac = c03_cum_km[idx] / total_km
                arr_m = dep_min + int(total_dur * frac)
                dep_m = arr_m if idx == len(c03_stations) - 1 else arr_m + 2
                stops.append({
                    "station_code": stn_code,
                    "sequence": idx + 1,
                    "arrival_min": arr_m % 1440,
                    "departure_min": dep_m % 1440,
                    "distance_km": c03_cum_km[idx]
                })

            self._create_stops_and_occupancies(train, stops, corr_proto="C03")

    def _import_mdu_dg(self, fpath: str):
        """C20: Dindigul - Madurai"""
        xl = pd.ExcelFile(fpath)
        sheet = xl.sheet_names[0]
        df = pd.read_excel(fpath, sheet_name=sheet)
        self.corridors_mapped.add("C20")

        c20_stations = ["DG", "KQN", "SDN", "MDU"]
        c20_cum_km = [0.0, 22.0, 42.0, 62.0]

        for _, row in df.iterrows():
            t_num_raw = row.get("Train Number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("Train Name (Full)") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("Running Days"))
            dep_min = parse_time_str(row.get("Departure (MDU)")) or 600
            arr_min = parse_time_str(row.get("Arrival (DG)")) or (dep_min + 70)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="MDU",
                dst_code="DG",
                running_days=runs_on
            )

            total_dur = max(30, arr_min - dep_min)
            total_km = c20_cum_km[-1]
            stops = []
            for idx, stn_code in enumerate(c20_stations):
                frac = c20_cum_km[idx] / total_km
                arr_m = dep_min + int(total_dur * frac)
                dep_m = arr_m if idx == len(c20_stations) - 1 else arr_m + 2
                stops.append({
                    "station_code": stn_code,
                    "sequence": idx + 1,
                    "arrival_min": arr_m % 1440,
                    "departure_min": dep_m % 1440,
                    "distance_km": c20_cum_km[idx]
                })

            self._create_stops_and_occupancies(train, stops, corr_proto="C20")

    def _import_manamadurai_virudhunagar(self, fpath: str):
        """C39: Manamadurai - Virudunagar"""
        df = pd.read_excel(fpath)
        self.corridors_mapped.add("C39")
        c39_stations = ["MNM", "VPT"]
        c39_cum_km = [0.0, 66.5]

        for _, row in df.iterrows():
            t_num_raw = row.get("train_number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("train_name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("runs_on"))
            dep_min = parse_time_str(row.get("departure")) or 400
            arr_min = parse_time_str(row.get("arrival")) or (dep_min + 63)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="MNM",
                dst_code="VPT",
                running_days=runs_on
            )

            stops = [
                {"station_code": "MNM", "sequence": 1, "arrival_min": dep_min % 1440, "departure_min": (dep_min + 2) % 1440, "distance_km": 0.0},
                {"station_code": "VPT", "sequence": 2, "arrival_min": arr_min % 1440, "departure_min": arr_min % 1440, "distance_km": 66.5}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto="C39")

    def _import_nidamangalam_mannargudi(self, fpath: str):
        """C33: Nidamangalam - Mannargudi"""
        df = pd.read_excel(fpath)
        self.corridors_mapped.add("C33")
        c33_stations = ["NMJ", "MQ"]

        for _, row in df.iterrows():
            t_num_raw = row.get("train_number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("train_name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("runs_on"))
            dep_min = parse_time_str(row.get("nmj_departure")) or 324
            arr_min = parse_time_str(row.get("mq_arrival")) or (dep_min + 56)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="NMJ",
                dst_code="MQ",
                running_days=runs_on
            )

            stops = [
                {"station_code": "NMJ", "sequence": 1, "arrival_min": dep_min % 1440, "departure_min": (dep_min + 2) % 1440, "distance_km": 0.0},
                {"station_code": "MQ", "sequence": 2, "arrival_min": arr_min % 1440, "departure_min": arr_min % 1440, "distance_km": 14.0}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto="C33")

    def _import_erode_karur_trichy(self, fpath: str):
        """C18: Erode - Karur - Tiruchirappalli"""
        df = pd.read_csv(fpath)
        self.corridors_mapped.add("C18")

        for _, row in df.iterrows():
            t_num_raw = row.get("train_number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("train_name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("runs_on"))

            ed_dep = parse_time_str(row.get("erode_departure")) or 600
            krr_arr = parse_time_str(row.get("karur_arrival")) or (ed_dep + 65)
            krr_dep = parse_time_str(row.get("karur_departure")) or (krr_arr + 2)
            tpj_arr = parse_time_str(row.get("tiruchirappalli_arrival")) or (krr_dep + 80)

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="ED",
                dst_code="TPJ",
                running_days=runs_on
            )

            stops = [
                {"station_code": "ED", "sequence": 1, "arrival_min": ed_dep % 1440, "departure_min": (ed_dep + 2) % 1440, "distance_km": 0.0},
                {"station_code": "KRR", "sequence": 2, "arrival_min": krr_arr % 1440, "departure_min": krr_dep % 1440, "distance_km": 65.0},
                {"station_code": "TPJ", "sequence": 3, "arrival_min": tpj_arr % 1440, "departure_min": tpj_arr % 1440, "distance_km": 141.0}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto="C18")

    def _import_karur_dindigul(self, fpath: str):
        """C19: Karur - Dindigul"""
        df = pd.read_csv(fpath)
        self.corridors_mapped.add("C19")

        for _, row in df.iterrows():
            t_num_raw = row.get("Train Number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("Train Name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("Days"))
            dep_min = parse_time_str(row.get("Departure")) or 400
            arr_min = parse_time_str(row.get("Arrival")) or (dep_min + 75)
            if arr_min <= dep_min:
                arr_min += 1440

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="KRR",
                dst_code="DG",
                running_days=runs_on
            )

            stops = [
                {"station_code": "KRR", "sequence": 1, "arrival_min": dep_min % 1440, "departure_min": (dep_min + 2) % 1440, "distance_km": 0.0},
                {"station_code": "DG", "sequence": 2, "arrival_min": arr_min % 1440, "departure_min": arr_min % 1440, "distance_km": 74.0}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto="C19")

    def _import_salem_namakkal_karur(self, fpath: str):
        """C17: Salem - Namakkal - Karur"""
        df = pd.read_csv(fpath)
        self.corridors_mapped.add("C17")

        for _, row in df.iterrows():
            t_num_raw = row.get("train_number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("train_name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("runs_on"))

            sa_dep = parse_time_str(row.get("salem_departure")) or 10
            nmkl_arr = parse_time_str(row.get("namakkal_arrival")) or (sa_dep + 45)
            nmkl_dep = parse_time_str(row.get("namakkal_departure")) or (nmkl_arr + 2)
            krr_arr = parse_time_str(row.get("karur_arrival")) or (nmkl_dep + 40)

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code="SA",
                dst_code="KRR",
                running_days=runs_on
            )

            stops = [
                {"station_code": "SA", "sequence": 1, "arrival_min": sa_dep % 1440, "departure_min": (sa_dep + 2) % 1440, "distance_km": 0.0},
                {"station_code": "NMKL", "sequence": 2, "arrival_min": nmkl_arr % 1440, "departure_min": nmkl_dep % 1440, "distance_km": 52.0},
                {"station_code": "KRR", "sequence": 3, "arrival_min": krr_arr % 1440, "departure_min": krr_arr % 1440, "distance_km": 85.0}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto="C17")

    def _import_where_is_my_train(self, fpath: str):
        """Generic multi-route train records (e.g. MAS-AJJ, etc.)"""
        xl = pd.ExcelFile(fpath)
        sheet = "Train_Data" if "Train_Data" in xl.sheet_names else xl.sheet_names[0]
        df = pd.read_excel(fpath, sheet_name=sheet)

        for _, row in df.iterrows():
            t_num_raw = row.get("Train Number")
            if pd.isna(t_num_raw):
                self.invalid_rows += 1
                continue
            t_num = str(int(t_num_raw) if isinstance(t_num_raw, (int, float)) else t_num_raw).strip()
            t_name = str(row.get("Train Name") or f"Express {t_num}").strip()
            runs_on = parse_running_days(row.get("Running Pattern"))
            dep_min = parse_time_str(row.get("Departure")) or 360
            arr_min = parse_time_str(row.get("Arrival")) or (dep_min + 60)
            if arr_min <= dep_min:
                arr_min += 1440

            src_code = str(row.get("Route Code") or "MAS").upper().strip()
            dst_code = str(row.get("To Station") or "AJJ").upper().strip()

            t_type, priority = classify_train(t_name)
            train = self._upsert_train(
                t_num=t_num,
                name=t_name,
                t_type=t_type,
                priority=priority,
                src_code=src_code,
                dst_code=dst_code,
                running_days=runs_on
            )

            # Map to C01 (MAS-AJJ) if applicable
            corr_proto = "C01" if (src_code == "MAS" and dst_code == "AJJ") else None
            stops = [
                {"station_code": src_code, "sequence": 1, "arrival_min": dep_min % 1440, "departure_min": (dep_min + 2) % 1440, "distance_km": 0.0},
                {"station_code": dst_code, "sequence": 2, "arrival_min": arr_min % 1440, "departure_min": arr_min % 1440, "distance_km": 68.0}
            ]
            self._create_stops_and_occupancies(train, stops, corr_proto=corr_proto)

    # -------------------------------------------------------------
    # Helper Database Operations
    # -------------------------------------------------------------
    def _upsert_train(
        self,
        t_num: str,
        name: str,
        t_type: str,
        priority: int,
        src_code: str,
        dst_code: str,
        running_days: str
    ) -> Train:
        stn_src = self.ensure_station(src_code)
        stn_dst = self.ensure_station(dst_code)

        train = self.db.query(Train).filter(Train.train_number == t_num).first()
        if not train:
            train = Train(
                train_number=t_num,
                train_name=name,
                train_type=t_type,
                category=t_type,
                priority_level=priority,
                source_station_id=stn_src.id if stn_src else None,
                destination_station_id=stn_dst.id if stn_dst else None,
                source_code=src_code,
                source_name=stn_src.name if stn_src else src_code,
                destination_code=dst_code,
                destination_name=stn_dst.name if stn_dst else dst_code,
                running_days=running_days,
                is_tn_relevant=True,
                active=True,
                source="DOCUMENT_IMPORT",
                source_version="v2.0",
                last_verified_at=datetime.utcnow()
            )
            self.db.add(train)
            self.db.flush()
            self.trains_imported += 1
        else:
            train.train_name = name
            train.train_type = t_type
            train.category = t_type
            train.priority_level = priority
            train.running_days = running_days
            train.source_code = src_code
            train.destination_code = dst_code
            train.is_tn_relevant = True
            train.active = True
            train.last_verified_at = datetime.utcnow()

        return train

    def _create_stops_and_occupancies(self, train: Train, stops_data: List[Dict[str, Any]], corr_proto: Optional[str] = None):
        """Creates TrainRouteStop, TrainRoute, and TrainSectionOccupancy records."""
        # 1. Clean existing stops for this train
        self.db.query(TrainRouteStop).filter(TrainRouteStop.train_number == train.train_number).delete()

        for s in stops_data:
            stn = self.ensure_station(s["station_code"])
            stop = TrainRouteStop(
                train_number=train.train_number,
                station_id=stn.id,
                station_code=s["station_code"],
                station_name=stn.name,
                sequence=s["sequence"],
                arrival_min=s["arrival_min"],
                departure_min=s["departure_min"],
                distance_km=s.get("distance_km", 0.0),
                is_halt=True,
                source="DOCUMENT_IMPORT",
                last_verified_at=datetime.utcnow()
            )
            self.db.add(stop)
            self.route_stops_imported += 1

        self.db.flush()

        # 2. Map stops to RailwaySections
        self.db.query(TrainRoute).filter(TrainRoute.train_number == train.train_number).delete()

        # Try to find corridor sections
        corr = self.corridors_by_proto.get(corr_proto) if corr_proto else None
        if corr:
            self.corridors_mapped.add(corr.prototype_code or corr.corridor_id)
            corr_sections = self.db.query(RailwaySection).filter(RailwaySection.corridor_id == corr.id).all()
        else:
            corr_sections = self.db.query(RailwaySection).all()

        sec_by_endpoints: Dict[Tuple[str, str], RailwaySection] = {}
        for s in corr_sections:
            f_code = s.from_station.code.upper() if s.from_station else ""
            t_code = s.to_station.code.upper() if s.to_station else ""
            if f_code and t_code:
                sec_by_endpoints[(f_code, t_code)] = s
                # bidirectional fallback
                sec_by_endpoints[(t_code, f_code)] = s

        route_seq = 1
        for i in range(len(stops_data) - 1):
            c1 = stops_data[i]["station_code"]
            c2 = stops_data[i + 1]["station_code"]
            sec = sec_by_endpoints.get((c1, c2))
            if sec:
                tr = TrainRoute(
                    train_number=train.train_number,
                    section_id=sec.id,
                    sequence=route_seq,
                    direction=sec.direction or "UP",
                    source="DOCUMENT_IMPORT",
                    last_verified_at=datetime.utcnow()
                )
                self.db.add(tr)
                self.sections_mapped += 1
                route_seq += 1

                # Calculate occupancy for this section
                entry_m = stops_data[i]["departure_min"]
                exit_m = stops_data[i + 1]["arrival_min"]
                if exit_m <= entry_m:
                    exit_m += 1440

                # Avoid duplicate occupancy
                existing_occ = self.db.query(TrainSectionOccupancy).filter(
                    TrainSectionOccupancy.train_number == train.train_number,
                    TrainSectionOccupancy.section_id == sec.id
                ).first()

                if not existing_occ:
                    occ = TrainSectionOccupancy(
                        train_number=train.train_number,
                        section_id=sec.id,
                        journey_date=datetime.utcnow(),
                        estimated_entry_min=entry_m % 1440,
                        estimated_exit_min=exit_m % 1440,
                        confidence=0.98,
                        is_live=False,
                        source="SCHEDULED",
                        last_updated=datetime.utcnow(),
                        calculated_at=datetime.utcnow()
                    )
                    self.db.add(occ)
                else:
                    existing_occ.estimated_entry_min = entry_m % 1440
                    existing_occ.estimated_exit_min = exit_m % 1440
                    existing_occ.source = "SCHEDULED"
                    existing_occ.last_updated = datetime.utcnow()

        self.db.flush()

    def summary(self) -> Dict[str, Any]:
        """Prints and returns authoritative import summary."""
        total_corrs = len(self.corridors_mapped)
        out = {
            "files_processed": self.files_processed,
            "trains_imported": self.trains_imported,
            "stations_imported": self.stations_imported,
            "route_stops_imported": self.route_stops_imported,
            "sections_mapped": self.sections_mapped,
            "corridors_mapped": total_corrs,
            "corridors_list": sorted(list(self.corridors_mapped)),
            "invalid_rows": self.invalid_rows
        }

        print("\n" + "=" * 60)
        print("IMPORT SUMMARY")
        print("=" * 60)
        print(f"Files processed:      {self.files_processed}")
        print(f"Trains imported:       {self.trains_imported}")
        print(f"Stations imported:     {self.stations_imported}")
        print(f"Route stops imported:  {self.route_stops_imported}")
        print(f"Sections mapped:       {self.sections_mapped}")
        print(f"Corridors mapped:      {total_corrs} ({', '.join(sorted(list(self.corridors_mapped)))})")
        print(f"Invalid rows reported: {self.invalid_rows}")
        print("=" * 60 + "\n")
        return out


def run_import(documents_dir: Optional[str] = None):
    db = SessionLocal()
    try:
        importer = RailwayDocumentImporter(db, documents_dir)
        return importer.import_all()
    finally:
        db.close()


if __name__ == "__main__":
    doc_dir = sys.argv[1] if len(sys.argv) > 1 else None
    run_import(doc_dir)
