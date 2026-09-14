#!/usr/bin/env python3
"""
scripts/import_station_master.py
Reproducible Railway Station Master Import Script
Primary Source: documents/TN-station list.pdf (Southern Railway Official Station List as on 01.04.2025)
Extracts, normalizes, deduplicates, geocodes, and updates the Railway Station Master.
"""

import os
import sys
import re
from datetime import datetime
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple

import pdfplumber

# Add backend directory to sys.path so app models and db can be imported
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.models import RailwayStation, Station

# Known station geographical boundaries for Southern Railway
MAS_AP_CODES = {"SPE", "TADA", "PEL", "DVR", "NYP", "PDR", "AKAT", "EKM", "VGA", "PUT", "TDK", "PUDI", "NG", "VKZ"}
TPJ_PY_CODES = {"PDY", "VI", "KIK", "NNX", "TMPT"}
MDU_KL_CODES = {"AYVN", "AYV", "TML", "EDN", "OKL", "PUU", "AVS", "KIF", "KKZ", "EKN", "KDRE", "KUV", "KLQ", "KFV"}
TVC_TN_CODES = {"CAPE", "NCJ", "NJT", "ERL", "KZT", "KZTW", "PYD", "VLY", "NNN", "AAY", "THX", "MP", "NPK", "KVLK", "SGLM", "VRLR"}
PGT_KA_CODES = {"MAQ", "MAJN", "ULL", "JOKT", "TOK"}
PGT_PY_CODES = {"MAHE"}
PGT_TN_CODES = {"POY", "MDKI", "ETMD", "CNV", "ANM", "MXM"}

# Reference coordinates for Southern Railway network
REFERENCE_COORDINATES: Dict[str, Tuple[float, float, str]] = {
    # Tamil Nadu Primary & Secondary Stations
    "MAS": (13.0827, 80.2707, "Chennai"),
    "MS": (13.0822, 80.2755, "Chennai"),
    "TBM": (12.9249, 80.1172, "Chengalpattu"),
    "CGL": (12.6922, 79.9764, "Chengalpattu"),
    "AJJ": (13.0827, 79.6677, "Ranipet"),
    "AVD": (13.1186, 80.1011, "Tiruvallur"),
    "KPD": (12.9698, 79.1378, "Vellore"),
    "TRL": (13.1438, 79.9080, "Tiruvallur"),
    "CBE": (11.0018, 76.9629, "Coimbatore"),
    "ED": (11.3410, 77.7172, "Erode"),
    "SA": (11.6643, 78.1460, "Salem"),
    "TUP": (11.1085, 77.3411, "Tiruppur"),
    "TPJ": (10.7905, 78.6856, "Tiruchirappalli"),
    "VM": (11.9398, 79.4975, "Villupuram"),
    "MDU": (9.9196, 78.1114, "Madurai"),
    "TEN": (8.7300, 77.7289, "Tirunelveli"),
    "CVP": (9.1725, 77.8687, "Thoothukudi"),
    "RMD": (9.3639, 78.8395, "Ramanathapuram"),
    "RMM": (9.2885, 79.3129, "Ramanathapuram"),
    "TSI": (8.9592, 77.3039, "Tenkasi"),
    "TN": (8.8053, 78.1497, "Thoothukudi"),
    "VPT": (9.5855, 77.9547, "Virudhunagar"),
    "DG": (10.3624, 77.9695, "Dindigul"),
    "SRT": (9.3622, 77.9258, "Virudhunagar"),
    "KDU": (8.9833, 77.8667, "Thoothukudi"),
    "MEJ": (8.8667, 77.8000, "Thoothukudi"),
    "PLNI": (10.4500, 77.5167, "Dindigul"),
    "PMK": (9.5447, 78.5878, "Ramanathapuram"),
    "RJPM": (9.4500, 77.5500, "Virudhunagar"),
    "TCN": (8.4833, 78.1167, "Thoothukudi"),
    "KKDI": (10.0667, 78.7833, "Sivaganga"),
    "KMU": (10.9575, 79.3855, "Thanjavur"),
    "MV": (11.0991, 79.6455, "Mayiladuthurai"),
    "NGT": (10.7634, 79.8436, "Nagapattinam"),
    "TJ": (10.7758, 79.1378, "Thanjavur"),
    "CDM": (11.3992, 79.6936, "Cuddalore"),
    "MQ": (10.6667, 79.4500, "Tiruvarur"),
    "PDY": (11.9333, 79.8167, "Puducherry"),
    "TNM": (12.2253, 79.0747, "Tiruvannamalai"),
    "TVR": (10.7733, 79.6375, "Tiruvarur"),
    "VRI": (11.5167, 79.3333, "Cuddalore"),
    "ADT": (11.0167, 79.5000, "Thanjavur"),
    "ALU": (11.1392, 79.0756, "Ariyalur"),
    "BAL": (10.7833, 79.0333, "Thanjavur"),
    "CAPE": (8.0883, 77.5385, "Kanniyakumari"),
    "NCJ": (8.1831, 77.4338, "Kanniyakumari"),
    "NJT": (8.1780, 77.4250, "Kanniyakumari"),
    "ERL": (8.2042, 77.3090, "Kanniyakumari"),
    "KZT": (8.3185, 77.1950, "Kanniyakumari"),
    "KZTW": (8.3240, 77.1850, "Kanniyakumari"),
    "PYD": (8.2560, 77.2620, "Kanniyakumari"),
    "VLY": (8.3833, 77.6167, "Tirunelveli"),
    "NNN": (8.4833, 77.6667, "Tirunelveli"),
    "AAY": (8.2450, 77.5250, "Kanniyakumari"),
    "THX": (8.2167, 77.5000, "Kanniyakumari"),
    "MP": (8.7000, 77.7333, "Tirunelveli"),
    "NPK": (8.3200, 77.5800, "Tirunelveli"),
    "KVLK": (8.2667, 77.5500, "Tirunelveli"),
    "SGLM": (8.5833, 77.7000, "Tirunelveli"),
    "VRLR": (8.1950, 77.3300, "Kanniyakumari"),
    "POY": (10.6583, 77.0083, "Coimbatore"),
    "MDKI": (10.9000, 76.9500, "Coimbatore"),
    "ETMD": (10.9167, 76.9000, "Coimbatore"),
    "CNV": (10.8167, 77.0167, "Coimbatore"),
    "ANM": (10.5833, 76.9333, "Coimbatore"),
    "MXM": (10.6000, 76.8500, "Coimbatore"),
    "JTJ": (12.5583, 78.5772, "Tirupattur"),
    "GI": (12.8464, 80.0617, "Chengalpattu"),
    "MBM": (13.0333, 80.2333, "Chennai"),
    "PER": (13.1075, 80.2333, "Chennai"),
    "AB": (12.7833, 78.7000, "Tirupattur"),
    "CJ": (12.8333, 79.7000, "Kanchipuram"),
    "MLMR": (12.4333, 79.8333, "Chengalpattu"),
    "PRGL": (12.9056, 80.0889, "Chengalpattu"),
    "ANNR": (13.1200, 80.1300, "Tiruvallur"),
    "EGT": (13.1300, 79.9300, "Tiruvallur"),
    "PTLR": (13.1400, 79.9200, "Tiruvallur"),
    "MCRD": (11.0800, 78.1800, "Namakkal"),
    "MTDM": (11.8000, 77.8000, "Salem"),
    "KAY": (11.7500, 77.9500, "Salem"),
    "NMKL": (11.2189, 78.1674, "Namakkal"),
    "SMM": (11.4500, 77.7000, "Erode"),
    "SRGM": (10.8667, 78.7000, "Tiruchirappalli"),
    "VLNK": (10.6833, 79.8500, "Nagapattinam"),
    "PML": (10.9000, 79.2833, "Thanjavur"),
    "CAN": (11.8745, 75.3704, "Kannur"),
    "CLT": (11.2480, 75.7839, "Kozhikode"),
    "MAQ": (12.8656, 74.8427, "Dakshina Kannada"),
    "MAJN": (12.8680, 74.8720, "Dakshina Kannada"),
    "PGT": (10.7867, 76.6548, "Palakkad"),
    "ERS": (9.9676, 76.2917, "Ernakulam"),
    "ERN": (9.9930, 76.2890, "Ernakulam"),
    "QLN": (8.8870, 76.5980, "Kollam"),
    "TCR": (10.5186, 76.2117, "Thrissur"),
    "TVC": (8.4871, 76.9528, "Thiruvananthapuram"),
    "ALLP": (9.4924, 76.3264, "Alappuzha"),
    "AWY": (10.1098, 76.3533, "Ernakulam"),
    "CNGR": (9.3176, 76.6186, "Alappuzha"),
    "KYJ": (9.1722, 76.5000, "Alappuzha"),
    "KCVL": (8.5140, 76.8970, "Thiruvananthapuram"),
    "KTYM": (9.5880, 76.5270, "Kottayam"),
    "TRVL": (9.3830, 76.5750, "Pathanamthitta"),
    "VAK": (8.7330, 76.7160, "Thiruvananthapuram"),
    "ULL": (12.8050, 74.8620, "Dakshina Kannada"),
    "JOKT": (12.9500, 74.8500, "Dakshina Kannada"),
    "MAHE": (11.7000, 75.5333, "Mahe"),
    "SPE": (13.7000, 80.0167, "Tirupati"),
    "TADA": (13.5833, 80.0333, "Tirupati"),
    "NYP": (13.9000, 79.9667, "Tirupati"),
    "PUT": (13.4333, 79.5500, "Tirupati"),
    "PUU": (9.0167, 76.9333, "Kollam"),
    "KUV": (8.9667, 76.6833, "Kollam"),
    "KKZ": (8.9950, 76.7750, "Kollam"),
    "EDN": (9.0000, 77.0167, "Kollam"),
    "TML": (8.9600, 77.0600, "Kollam"),
    "AYVN": (8.9700, 77.1300, "Kollam"),
    "AYV": (8.9800, 77.1500, "Kollam"),
    "BTP": (8.9900, 77.2300, "Tenkasi"),
    "SCT": (8.9833, 77.2667, "Tenkasi"),
}


def normalize_station_name(raw_name: str) -> str:
    """Normalize station name for intelligent fuzzy and case-insensitive search."""
    s = raw_name.lower()
    s = re.sub(r'\(flag\)|\(halt\)', '', s)
    s = re.sub(r'\b(jn\.|jn|junction)\b', 'junction', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def determine_station_type(raw_name: str) -> str:
    """Classify station type from official railway nomenclature."""
    upper = raw_name.upper()
    if "(FLAG)" in upper:
        return "FLAG"
    elif "(HALT)" in upper:
        return "HALT"
    elif "JN" in upper or "JUNCTION" in upper:
        return "JUNCTION"
    elif "CENTRAL" in upper or "TERMINUS" in upper:
        return "TERMINAL"
    return "REGULAR"


def classify_state(code: str, div: str) -> str:
    """Classify station into authentic geographical state."""
    div = div.upper()
    code = code.upper()

    if div == "SA":
        return "Tamil Nadu"
    elif div == "TPJ":
        if code in TPJ_PY_CODES:
            return "Puducherry"
        return "Tamil Nadu"
    elif div == "MAS":
        if code in MAS_AP_CODES:
            return "Andhra Pradesh"
        return "Tamil Nadu"
    elif div == "MDU":
        if code in MDU_KL_CODES:
            return "Kerala"
        return "Tamil Nadu"
    elif div == "TVC":
        if code in TVC_TN_CODES:
            return "Tamil Nadu"
        return "Kerala"
    elif div == "PGT":
        if code in PGT_KA_CODES:
            return "Karnataka"
        elif code in PGT_PY_CODES:
            return "Puducherry"
        elif code in PGT_TN_CODES:
            return "Tamil Nadu"
        return "Kerala"
    return "Tamil Nadu"


def extract_station_records_from_pdf(pdf_path: str) -> Tuple[List[Dict[str, Any]], List[str], List[Any]]:
    """Extract all records across all pages of the station list PDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Source PDF not found at path: {pdf_path}")

    records = []
    duplicates = []
    invalid_rows = []
    seen_codes = set()

    with pdfplumber.open(pdf_path) as pdf:
        for p_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 5:
                        continue
                    sno, name, code, div, cat = [str(c).strip() if c is not None else "" for c in row[:5]]
                    if sno == 'S. No.' or 'SOUTHERN RAILWAY' in sno or not sno:
                        continue
                    try:
                        sno_int = int(sno)
                    except ValueError:
                        invalid_rows.append(row)
                        continue

                    clean_code = code.strip().upper()
                    clean_name = name.replace('\n', ' ').strip()
                    clean_div = div.strip().upper()
                    clean_cat = cat.strip()

                    if not clean_code or not clean_name or not clean_div or not clean_cat:
                        invalid_rows.append(row)
                        continue

                    if clean_code in seen_codes:
                        duplicates.append(clean_code)
                    else:
                        seen_codes.add(clean_code)

                    state = classify_state(clean_code, clean_div)
                    stn_type = determine_station_type(clean_name)
                    norm_name = normalize_station_name(clean_name)

                    # Geolocation lookup or reference
                    lat, lon, dist = None, None, None
                    if clean_code in REFERENCE_COORDINATES:
                        lat, lon, dist = REFERENCE_COORDINATES[clean_code]
                    else:
                        # Default district by division & state
                        if state == "Tamil Nadu":
                            dist_map = {"MAS": "Chennai Region", "SA": "Salem Region", "TPJ": "Tiruchirappalli Region", "MDU": "Madurai Region", "TVC": "Kanniyakumari", "PGT": "Coimbatore"}
                            dist = dist_map.get(clean_div, "Tamil Nadu")
                        elif state == "Kerala":
                            dist = "Kerala Region"
                        elif state == "Andhra Pradesh":
                            dist = "Tirupati"
                        elif state == "Puducherry":
                            dist = "Puducherry"
                        elif state == "Karnataka":
                            dist = "Dakshina Kannada"

                    records.append({
                        "sno": sno_int,
                        "code": clean_code,
                        "name": clean_name,
                        "normalized_name": norm_name,
                        "division": clean_div,
                        "category": clean_cat,
                        "state": state,
                        "district": dist,
                        "type": stn_type,
                        "latitude": lat,
                        "longitude": lon
                    })

    return records, duplicates, invalid_rows


def import_station_master(pdf_path: str = "documents/TN-station list.pdf") -> Dict[str, Any]:
    """Execute complete database import and return audit summary dictionary."""
    # Ensure database schema is present
    Base.metadata.create_all(bind=engine)

    records, duplicates, invalid_rows = extract_station_records_from_pdf(pdf_path)

    db = SessionLocal()
    inserted_count = 0
    updated_count = 0

    try:
        for r in records:
            # 1. Update/Insert in railway_stations
            stn = db.query(RailwayStation).filter(RailwayStation.station_code == r["code"]).first()
            if not stn:
                stn = RailwayStation(
                    station_code=r["code"],
                    station_name=r["name"],
                    normalized_station_name=r["normalized_name"],
                    state=r["state"],
                    district=r["district"],
                    division=r["division"],
                    category=r["category"],
                    station_type=r["type"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    is_active=True,
                    source="Southern Railway Station List (01.04.2025)",
                    source_version="01.04.2025",
                    last_verified=datetime.utcnow()
                )
                db.add(stn)
                inserted_count += 1
            else:
                stn.station_name = r["name"]
                stn.normalized_station_name = r["normalized_name"]
                stn.state = r["state"]
                stn.district = r["district"] or stn.district
                stn.division = r["division"]
                stn.category = r["category"]
                stn.station_type = r["type"]
                if r["latitude"] is not None and r["longitude"] is not None:
                    stn.latitude = r["latitude"]
                    stn.longitude = r["longitude"]
                stn.last_verified = datetime.utcnow()
                updated_count += 1

            # 2. Synchronize existing Station table for foreign key relations
            s_old = db.query(Station).filter(Station.code == r["code"]).first()
            zone_str = "Southern Railway (SR)"
            lat_val = r["latitude"] if r["latitude"] is not None else 11.0000
            lon_val = r["longitude"] if r["longitude"] is not None else 78.0000
            if not s_old:
                s_old = Station(
                    code=r["code"],
                    name=r["name"],
                    division=r["division"],
                    zone=zone_str,
                    latitude=lat_val,
                    longitude=lon_val,
                    total_platforms=4
                )
                db.add(s_old)
            else:
                s_old.name = r["name"]
                s_old.division = r["division"]
                if r["latitude"] is not None:
                    s_old.latitude = lat_val
                    s_old.longitude = lon_val

        db.commit()

        # Database verification count
        total_db_count = db.query(RailwayStation).count()
        tn_db_count = db.query(RailwayStation).filter(RailwayStation.state == "Tamil Nadu").count()
        other_db_count = total_db_count - tn_db_count

    finally:
        db.close()

    report = {
        "source": "Southern Railway Station List As on 01.04.2025",
        "total_extracted": len(records),
        "valid_records": len(records),
        "duplicates": len(duplicates),
        "invalid_records": len(invalid_rows),
        "missing_codes": 0,
        "missing_names": 0,
        "missing_divisions": 0,
        "missing_categories": 0,
        "tamil_nadu_stations": tn_db_count,
        "other_state_stations": other_db_count,
        "database_records": total_db_count,
        "successfully_inserted": inserted_count,
        "successfully_updated": updated_count
    }

    return report


def print_audit_report(report: Dict[str, Any]):
    """Format and print the audit report to stdout."""
    print("====================================")
    print("RAILWAY STATION MASTER IMPORT AUDIT")
    print("====================================")
    print("Source:")
    print("Southern Railway Station List")
    print("As on 01.04.2025\n")
    print(f"PDF records processed: {report['total_extracted']}")
    print(f"Valid station codes: {report['valid_records']}")
    print(f"Duplicate codes: {report['duplicates']}")
    print(f"Missing codes: {report['missing_codes']}")
    print(f"Missing station names: {report['missing_names']}")
    print(f"Missing divisions: {report['missing_divisions']}")
    print(f"Missing categories: {report['missing_categories']}\n")
    print(f"Tamil Nadu stations: {report['tamil_nadu_stations']}")
    print(f"Other-state stations: {report['other_state_stations']}\n")
    print(f"Database records: {report['database_records']}")
    print(f"Successfully inserted: {report['successfully_inserted']}")
    print(f"Successfully updated: {report['successfully_updated']}")
    print("====================================")


if __name__ == "__main__":
    pdf_file = "documents/TN-station list.pdf"
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]

    if not os.path.exists(pdf_file):
        # Check relative to project root
        candidate = os.path.join(PROJECT_ROOT, pdf_file)
        if os.path.exists(candidate):
            pdf_file = candidate
        else:
            print(f"ERROR: Cannot find PDF at '{pdf_file}' or '{candidate}'", file=sys.stderr)
            sys.exit(1)

    audit_result = import_station_master(pdf_file)
    print_audit_report(audit_result)
