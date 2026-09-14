import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "abps.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[MIGRATION] Checking table schema alterations...")

    # 1. Add prototype_code & description to corridors if not existing
    cursor.execute("PRAGMA table_info(corridors)")
    corr_cols = [row[1] for row in cursor.fetchall()]
    if "prototype_code" not in corr_cols:
        print("Adding prototype_code column to corridors...")
        cursor.execute("ALTER TABLE corridors ADD COLUMN prototype_code VARCHAR(10)")
    if "description" not in corr_cols:
        print("Adding description column to corridors...")
        cursor.execute("ALTER TABLE corridors ADD COLUMN description VARCHAR(255)")

    # 2. Add columns to maintenance_jobs if not existing
    cursor.execute("PRAGMA table_info(maintenance_jobs)")
    job_cols = [row[1] for row in cursor.fetchall()]
    new_job_cols = [
        ("corridor_id", "INTEGER"),
        ("work_title", "VARCHAR(150)"),
        ("requested_date", "DATETIME"),
        ("requested_start_time", "VARCHAR(10)"),
        ("requested_end_time", "VARCHAR(10)"),
        ("overdue_risk_score", "FLOAT DEFAULT 0.0"),
        ("safety_impact_info", "TEXT"),
        ("additional_remarks", "TEXT"),
        ("conflicting_trains_count", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in new_job_cols:
        if col_name not in job_cols:
            print(f"Adding {col_name} to maintenance_jobs...")
            cursor.execute(f"ALTER TABLE maintenance_jobs ADD COLUMN {col_name} {col_type}")

    conn.commit()

    # 3. Seed / Update Tamil Nadu Prototype Corridors C01 - C20
    # Minimum required:
    # CHENNAI / NORTH:
    # C01: Chennai -> Jolarpettai (MAS -> JTJ)
    # C02: Chennai -> Villupuram (MS -> VM)
    # C03: Chennai -> Chengalpattu (MS -> CGL)
    # C04: Villupuram -> Katpadi (VM -> KPD)
    # CENTRAL:
    # C05: Villupuram -> Tiruchirappalli (VM -> TPJ)
    # C06: Villupuram -> Mayiladuthurai (VM -> MV)
    # C07: Mayiladuthurai -> Thanjavur (MV -> TJ)
    # C08: Thanjavur -> Tiruchirappalli (TJ -> TPJ)
    # C09: Salem -> Tiruchirappalli (SA -> TPJ)
    # WESTERN:
    # C10: Coimbatore -> Salem (CBE -> SA)
    # C11: Coimbatore -> Mettupalayam (CBE -> MTP)
    # C12: Salem -> Karur (SA -> KRR)
    # C13: Dindigul -> Pollachi -> Coimbatore (DG -> CBE)
    # SOUTHERN:
    # C14: Tiruchirappalli -> Madurai (TPJ -> MDU)
    # C15: Madurai -> Tirunelveli (MDU -> TEN)
    # C16: Tirunelveli -> Nagercoil (TEN -> NCJ)
    # C17: Tirunelveli -> Tuticorin (TEN -> TN)
    # C18: Madurai -> Rameswaram (MDU -> RMM)
    # C19: Madurai -> Sengottai (MDU -> SCT)
    # C20: Tirunelveli -> Tiruchendur (TEN -> TCN)

    tn_corridors = [
        # CHENNAI / NORTH
        {"code": "C01", "id": "CORR_C01_MAS_JTJ", "name": "Chennai → Jolarpettai", "start": "MAS", "end": "JTJ", "div": "Chennai (MAS)", "zone": "Southern Railway (SR)", "dist": 213.0, "desc": "Chennai to Jolarpettai Trunk Line via Arakkonam and Katpadi"},
        {"code": "C02", "id": "CORR_C02_MS_VM", "name": "Chennai → Villupuram", "start": "MS", "end": "VM", "div": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "dist": 159.0, "desc": "Chennai Egmore to Villupuram Main Line via Chengalpattu and Tindivanam"},
        {"code": "C03", "id": "CORR_C03_MS_CGL", "name": "Chennai → Chengalpattu", "start": "MS", "end": "CGL", "div": "Chennai (MAS)", "zone": "Southern Railway (SR)", "dist": 56.0, "desc": "Chennai Egmore to Chengalpattu Suburban & Main Corridor"},
        {"code": "C04", "id": "CORR_C04_VM_KPD", "name": "Villupuram → Katpadi", "start": "VM", "end": "KPD", "div": "Tiruchchirappalli / Chennai", "zone": "Southern Railway (SR)", "dist": 160.0, "desc": "Villupuram to Katpadi Junction Cross-Link via Tiruvannamalai"},

        # CENTRAL
        {"code": "C05", "id": "CORR_C05_VM_TPJ", "name": "Villupuram → Tiruchirappalli", "start": "VM", "end": "TPJ", "div": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "dist": 178.0, "desc": "Villupuram to Tiruchchirappalli Chord Line via Vriddhachalam and Ariyalur"},
        {"code": "C06", "id": "CORR_C06_VM_MV", "name": "Villupuram → Mayiladuthurai", "start": "VM", "end": "MV", "div": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "dist": 122.0, "desc": "Villupuram to Mayiladuthurai Main Line via Cuddalore Port and Chidambaram"},
        {"code": "C07", "id": "CORR_C07_MV_TJ", "name": "Mayiladuthurai → Thanjavur", "start": "MV", "end": "TJ", "div": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "dist": 71.0, "desc": "Mayiladuthurai to Thanjavur Delta Line via Kumbakonam"},
        {"code": "C08", "id": "CORR_C08_TJ_TPJ", "name": "Thanjavur → Tiruchirappalli", "start": "TJ", "end": "TPJ", "div": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "dist": 50.0, "desc": "Thanjavur to Tiruchchirappalli Double Track Section"},
        {"code": "C09", "id": "CORR_C09_SA_TPJ", "name": "Salem → Tiruchirappalli", "start": "SA", "end": "TPJ", "div": "Salem / Tiruchchirappalli", "zone": "Southern Railway (SR)", "dist": 141.0, "desc": "Salem to Tiruchchirappalli Section via Namakkal and Karur"},

        # WESTERN
        {"code": "C10", "id": "CORR_C10_CBE_SA", "name": "Coimbatore → Salem", "start": "CBE", "end": "SA", "div": "Salem (SA)", "zone": "Southern Railway (SR)", "dist": 155.0, "desc": "Coimbatore to Salem High Density Trunk Line via Tiruppur and Erode"},
        {"code": "C11", "id": "CORR_C11_CBE_MTP", "name": "Coimbatore → Mettupalayam", "start": "CBE", "end": "MTP", "div": "Salem (SA)", "zone": "Southern Railway (SR)", "dist": 36.0, "desc": "Coimbatore to Mettupalayam Nilgiri Foothills Section"},
        {"code": "C12", "id": "CORR_C12_SA_KRR", "name": "Salem → Karur", "start": "SA", "end": "KRR", "div": "Salem (SA)", "zone": "Southern Railway (SR)", "dist": 85.0, "desc": "Salem to Karur Direct Line via Namakkal"},
        {"code": "C13", "id": "CORR_C13_DG_POY_CBE", "name": "Dindigul → Pollachi → Coimbatore", "start": "DG", "end": "CBE", "div": "Madurai / Salem", "zone": "Southern Railway (SR)", "dist": 166.0, "desc": "Dindigul to Coimbatore Section via Palani and Pollachi"},

        # SOUTHERN
        {"code": "C14", "id": "CORR_C14_TPJ_MDU", "name": "Tiruchirappalli → Madurai", "start": "TPJ", "end": "MDU", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 153.0, "desc": "Tiruchchirappalli to Madurai Chord Line via Dindigul"},
        {"code": "C15", "id": "CORR_C15_MDU_TEN", "name": "Madurai → Tirunelveli", "start": "MDU", "end": "TEN", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 157.0, "desc": "Madurai to Tirunelveli Main Line via Virudhunagar, Sattur, Kovilpatti (CVP), and Vanchi Maniyachi"},
        {"code": "C16", "id": "CORR_C16_TEN_NCJ", "name": "Tirunelveli → Nagercoil", "start": "TEN", "end": "NCJ", "div": "Madurai / Thiruvananthapuram", "zone": "Southern Railway (SR)", "dist": 73.0, "desc": "Tirunelveli to Nagercoil Line via Valliyur"},
        {"code": "C17", "id": "CORR_C17_TEN_TN", "name": "Tirunelveli → Tuticorin", "start": "TEN", "end": "TN", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 54.0, "desc": "Tirunelveli to Tuticorin Port Link via Vanchi Maniyachi (MEJ)"},
        {"code": "C18", "id": "CORR_C18_MDU_RMM", "name": "Madurai → Rameswaram", "start": "MDU", "end": "RMM", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 161.0, "desc": "Madurai to Rameswaram Island Line via Manamadurai and Ramanathapuram"},
        {"code": "C19", "id": "CORR_C19_MDU_SCT", "name": "Madurai → Sengottai", "start": "MDU", "end": "SCT", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 145.0, "desc": "Madurai to Sengottai Western Ghats Chord via Virudhunagar, Rajapalayam, and Tenkasi"},
        {"code": "C20", "id": "CORR_C20_TEN_TCN", "name": "Tirunelveli → Tiruchendur", "start": "TEN", "end": "TCN", "div": "Madurai (MDU)", "zone": "Southern Railway (SR)", "dist": 61.0, "desc": "Tirunelveli to Tiruchendur Coastal Branch Line via Seydunganallur and Kurumbur"}
    ]

    print(f"[MIGRATION] Upserting {len(tn_corridors)} Tamil Nadu Prototype Corridors (C01 - C20)...")
    corr_db_ids = {}

    for c in tn_corridors:
        # Check by prototype_code or corridor_id
        cursor.execute("SELECT id FROM corridors WHERE prototype_code = ? OR corridor_id = ?", (c["code"], c["id"]))
        row = cursor.fetchone()
        if row:
            cid = row[0]
            cursor.execute("""
                UPDATE corridors 
                SET corridor_id = ?, prototype_code = ?, name = ?, division = ?, zone = ?, 
                    start_station_code = ?, end_station_code = ?, total_distance_km = ?, 
                    status = 'ACTIVE', description = ?
                WHERE id = ?
            """, (c["id"], c["code"], c["name"], c["div"], c["zone"], c["start"], c["end"], c["dist"], c["desc"], cid))
            corr_db_ids[c["code"]] = cid
        else:
            cursor.execute("""
                INSERT INTO corridors (corridor_id, prototype_code, name, division, zone, start_station_code, end_station_code, total_distance_km, status, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """, (c["id"], c["code"], c["name"], c["div"], c["zone"], c["start"], c["end"], c["dist"], c["desc"]))
            corr_db_ids[c["code"]] = cursor.lastrowid

    conn.commit()

    # 4. Map Sections to Corridors
    # Make sure stations exist in stations table
    def get_stn_id(stn_code):
        cursor.execute("SELECT id FROM stations WHERE code = ?", (stn_code,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("SELECT station_code, station_name, division, latitude, longitude FROM railway_stations WHERE station_code = ?", (stn_code,))
        rrow = cursor.fetchone()
        if rrow:
            cursor.execute("""
                INSERT INTO stations (code, name, division, zone, latitude, longitude, total_platforms)
                VALUES (?, ?, ?, 'SR', ?, ?, 4)
            """, (rrow[0], rrow[1], rrow[2], rrow[3] or 10.0, rrow[4] or 78.0))
            return cursor.lastrowid
        return None

    # Link sections to their appropriate C01-C20 corridors
    section_mappings = [
        # C15: Madurai -> Tirunelveli (MDU -> TEN), including CVP -> TEN!
        ("SEC_MDU_TDN", "Madurai Jn - Tirupparankundram", "MDU", "TDN", "C15", 6.0),
        ("SEC_TDN_TMQ", "Tirupparankundram - Tirumangalam", "TDN", "TMQ", "C15", 11.0),
        ("SEC_TMQ_VPT", "Tirumangalam - Virudhunagar Jn", "TMQ", "VPT", "C15", 26.0),
        ("SEC_VPT_SRT", "Virudhunagar Jn - Sattur", "VPT", "SRT", "C15", 25.0),
        ("SEC_SRT_CVP", "Sattur - Kovilpatti", "SRT", "CVP", "C15", 21.0),
        ("SEC_CVP_KDU", "Kovilpatti - Kadambur", "CVP", "KDU", "C15", 23.38),
        ("SEC_KDU_MEJ", "Kadambur - Vanchi Maniyachi Jn", "KDU", "MEJ", "C15", 21.94),
        ("SEC_MEJ_TEN", "Vanchi Maniyachi Jn - Tirunelveli Jn", "MEJ", "TEN", "C15", 22.82),

        # C01: Chennai -> Jolarpettai
        ("SEC_MAS_AVD", "MGR Chennai Central - Avadi", "MAS", "AVD", "C01", 21.0),
        ("SEC_AVD_TRL", "Avadi - Tiruvallur", "AVD", "TRL", "C01", 21.0),
        ("SEC_TRL_AJJ", "Tiruvallur - Arakkonam Jn", "TRL", "AJJ", "C01", 27.0),
        ("SEC_AJJ_KPD", "Arakkonam Jn - Katpadi Jn", "AJJ", "KPD", "C01", 61.0),
        ("SEC_KPD_AB", "Katpadi Jn - Ambur", "KPD", "AB", "C01", 52.0),
        ("SEC_AB_VN", "Ambur - Vaniyambadi", "AB", "VN", "C01", 16.0),
        ("SEC_VN_JTJ", "Vaniyambadi - Jolarpettai Jn", "VN", "JTJ", "C01", 16.0),

        # C02: Chennai -> Villupuram
        ("SEC_MS_TBM", "Chennai Egmore - Tambaram", "MS", "TBM", "C02", 25.0),
        ("SEC_TBM_CGL", "Tambaram - Chengalpattu Jn", "TBM", "CGL", "C02", 31.0),
        ("SEC_CGL_TMV", "Chengalpattu Jn - Tindivanam", "CGL", "TMV", "C02", 67.0),
        ("SEC_TMV_VM", "Tindivanam - Villupuram Jn", "TMV", "VM", "C02", 38.0),

        # C03: Chennai -> Chengalpattu
        ("SEC_MS_CGL_SUB", "Chennai Egmore - Chengalpattu Suburban", "MS", "CGL", "C03", 56.0),

        # C04: Villupuram -> Katpadi
        ("SEC_VM_TNM", "Villupuram Jn - Tiruvannamalai", "VM", "TNM", "C04", 67.0),
        ("SEC_TNM_KPD", "Tiruvannamalai - Katpadi Jn", "TNM", "KPD", "C04", 93.0),

        # C05: Villupuram -> Tiruchirappalli
        ("SEC_VM_VRI", "Villupuram Jn - Vriddhachalam Jn", "VM", "VRI", "C05", 55.0),
        ("SEC_VRI_ALU", "Vriddhachalam Jn - Ariyalur", "VRI", "ALU", "C05", 53.0),
        ("SEC_ALU_LLI", "Ariyalur - Lalgudi", "ALU", "LLI", "C05", 41.0),
        ("SEC_LLI_SRGM", "Lalgudi - Srirangam", "LLI", "SRGM", "C05", 15.0),
        ("SEC_SRGM_TPJ", "Srirangam - Tiruchchirappalli Jn", "SRGM", "TPJ", "C05", 12.0),

        # C06: Villupuram -> Mayiladuthurai
        ("SEC_VM_CUPJ", "Villupuram Jn - Cuddalore Port", "VM", "CUPJ", "C06", 44.0),
        ("SEC_CUPJ_CDM", "Cuddalore Port - Chidambaram", "CUPJ", "CDM", "C06", 43.0),
        ("SEC_CDM_MV", "Chidambaram - Mayiladuthurai Jn", "CDM", "MV", "C06", 35.0),

        # C07: Mayiladuthurai -> Thanjavur
        ("SEC_MV_KMU", "Mayiladuthurai Jn - Kumbakonam", "MV", "KMU", "C07", 31.0),
        ("SEC_KMU_TJ", "Kumbakonam - Thanjavur Jn", "KMU", "TJ", "C07", 40.0),

        # C08: Thanjavur -> Tiruchirappalli
        ("SEC_TJ_TPJ", "Thanjavur Jn - Tiruchchirappalli Jn", "TJ", "TPJ", "C08", 50.0),

        # C09: Salem -> Tiruchirappalli
        ("SEC_SA_NMKL", "Salem Jn - Namakkal", "SA", "NMKL", "C09", 52.0),
        ("SEC_NMKL_KRR", "Namakkal - Karur Jn", "NMKL", "KRR", "C09", 33.0),
        ("SEC_KRR_TPJ", "Karur Jn - Tiruchchirappalli Jn", "KRR", "TPJ", "C09", 76.0),

        # C10: Coimbatore -> Salem
        ("SEC_CBE_IGU", "Coimbatore Jn - Irugur Jn", "CBE", "IGU", "C10", 18.0),
        ("SEC_IGU_TUP", "Irugur Jn - Tiruppur", "IGU", "TUP", "C10", 32.0),
        ("SEC_TUP_UKL", "Tiruppur - Uttukuli", "TUP", "UKL", "C10", 14.0),
        ("SEC_UKL_ED", "Uttukuli - Erode Jn", "UKL", "ED", "C10", 36.0),
        ("SEC_ED_SGE", "Erode Jn - Sankaridurg", "ED", "SGE", "C10", 21.0),
        ("SEC_SGE_SA", "Sankaridurg - Salem Jn", "SGE", "SA", "C10", 39.0),

        # C11: Coimbatore -> Mettupalayam
        ("SEC_CBE_MTP", "Coimbatore Jn - Mettupalayam", "CBE", "MTP", "C11", 36.0),

        # C12: Salem -> Karur
        ("SEC_SA_KRR_DIR", "Salem Jn - Karur Jn", "SA", "KRR", "C12", 85.0),

        # C13: Dindigul -> Pollachi -> Coimbatore
        ("SEC_DG_PLNI", "Dindigul Jn - Palani", "DG", "PLNI", "C13", 58.0),
        ("SEC_PLNI_POY", "Palani - Pollachi Jn", "PLNI", "POY", "C13", 63.0),
        ("SEC_POY_CBE", "Pollachi Jn - Coimbatore Jn", "POY", "CBE", "C13", 45.0),

        # C14: Tiruchirappalli -> Madurai
        ("SEC_TPJ_MPA", "Tiruchchirappalli Jn - Manaparai", "TPJ", "MPA", "C14", 37.0),
        ("SEC_MPA_DG", "Manaparai - Dindigul Jn", "MPA", "DG", "C14", 57.0),
        ("SEC_DG_KQN", "Dindigul Jn - Kodaikanal Road", "DG", "KQN", "C14", 22.0),
        ("SEC_KQN_SDN", "Kodaikanal Road - Sholavandan", "KQN", "SDN", "C14", 21.0),
        ("SEC_SDN_MDU", "Sholavandan - Madurai Jn", "SDN", "MDU", "C14", 20.0),

        # C16: Tirunelveli -> Nagercoil
        ("SEC_TEN_VLY", "Tirunelveli Jn - Valliyur", "TEN", "VLY", "C16", 43.0),
        ("SEC_VLY_NCJ", "Valliyur - Nagercoil Jn", "VLY", "NCJ", "C16", 30.0),

        # C17: Tirunelveli -> Tuticorin
        ("SEC_MEJ_TN", "Vanchi Maniyachi Jn - Tuticorin", "MEJ", "TN", "C17", 31.0),

        # C18: Madurai -> Rameswaram
        ("SEC_MDU_MNM", "Madurai Jn - Manamadurai Jn", "MDU", "MNM", "C18", 48.0),
        ("SEC_MNM_PMK", "Manamadurai Jn - Paramakkudi", "MNM", "PMK", "C18", 33.0),
        ("SEC_PMK_RMD", "Paramakkudi - Ramanathapuram", "PMK", "RMD", "C18", 35.0),
        ("SEC_RMD_RMM", "Ramanathapuram - Rameswaram", "RMD", "RMM", "C18", 55.0),

        # C19: Madurai -> Sengottai
        ("SEC_VPT_SVKS", "Virudhunagar Jn - Sivakasi", "VPT", "SVKS", "C19", 24.0),
        ("SEC_SVKS_RJPM", "Sivakasi - Rajapalayam", "SVKS", "RJPM", "C19", 28.0),
        ("SEC_RJPM_SNKL", "Rajapalayam - Sankarankovil", "RJPM", "SNKL", "C19", 35.0),
        ("SEC_SNKL_TSI", "Sankarankovil - Tenkasi Jn", "SNKL", "TSI", "C19", 35.0),
        ("SEC_TSI_SCT", "Tenkasi Jn - Sengottai", "TSI", "SCT", "C19", 8.0),

        # C20: Tirunelveli -> Tiruchendur
        ("SEC_TEN_SDNR", "Tirunelveli Jn - Seydunganallur", "TEN", "SDNR", "C20", 17.0),
        ("SEC_SDNR_KZU", "Seydunganallur - Kurumbur", "SDNR", "KZU", "C20", 25.0),
        ("SEC_KZU_TCN", "Kurumbur - Tiruchendur", "KZU", "TCN", "C20", 19.0)
    ]

    for sec_id, name, from_c, to_c, corr_proto, dist_km in section_mappings:
        f_id = get_stn_id(from_c)
        t_id = get_stn_id(to_c)
        if not f_id or not t_id:
            continue
        corr_id = corr_db_ids.get(corr_proto)
        if not corr_id:
            continue

        cursor.execute("SELECT id FROM railway_sections WHERE section_id = ?", (sec_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE railway_sections
                SET name = ?, corridor_id = ?, from_station_id = ?, to_station_id = ?, length_km = ?
                WHERE id = ?
            """, (name, corr_id, f_id, t_id, dist_km, row[0]))
        else:
            cursor.execute("""
                INSERT INTO railway_sections (section_id, name, corridor_id, from_station_id, to_station_id, length_km, track_type, direction, max_speed_kmh, is_electrified)
                VALUES (?, ?, ?, ?, ?, ?, 'DOUBLE_UP', 'BOTH', 110.0, 1)
            """, (sec_id, name, corr_id, f_id, t_id, dist_km))

    conn.commit()

    # 5. Update Operational Roles for Authentication
    # 1. TRACK ENGINEERING / CIVIL -> 'TRACK_ENGINEERING'
    # 2. SIGNAL & TELECOM -> 'SIGNAL_TELECOM'
    # 3. TRACTION DISTRIBUTION -> 'TRACTION_DISTRIBUTION'
    # 4. RAILWAY PLANNER -> 'RAILWAY_PLANNER'
    # 5. SYSTEM ADMIN -> 'SYSTEM_ADMIN'
    print("[MIGRATION] Updating authenticated users to exact operational roles...")
    users_roles = [
        ("engg_user", "TRACK_ENGINEERING", "ENGG", "Senior Section Engineer (Track / Civil)"),
        ("snt_user", "SIGNAL_TELECOM", "SNT", "Senior Section Engineer (Signal & Telecom)"),
        ("trd_user", "TRACTION_DISTRIBUTION", "TRD", "Senior Section Engineer (Traction Distribution)"),
        ("planner", "RAILWAY_PLANNER", "OPERATIONS", "Chief Section Controller / Railway Planner"),
        ("admin", "SYSTEM_ADMIN", "OPERATIONS", "Railway Systems Administrator")
    ]
    for uname, urole, dept_code, fname in users_roles:
        cursor.execute("SELECT id FROM departments WHERE code = ?", (dept_code,))
        dept_row = cursor.fetchone()
        dept_id = dept_row[0] if dept_row else None
        cursor.execute("""
            UPDATE users
            SET role = ?, full_name = ?, department_id = ?
            WHERE username = ?
        """, (urole, fname, dept_id, uname))

    conn.commit()
    conn.close()
    print("[SUCCESS] Database schema, Tamil Nadu Corridors C01-C20, Sections, and Roles successfully migrated!")

if __name__ == "__main__":
    migrate()
