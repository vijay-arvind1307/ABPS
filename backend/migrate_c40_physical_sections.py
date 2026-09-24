import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import RailwaySection, BlockWindow, MaintenanceJob, Corridor

def align_c40_physical_sections():
    db = SessionLocal()
    try:
        c40 = db.query(Corridor).filter(Corridor.id == 30).first()
        if not c40:
            print("ERROR: Corridor 30 (C40) not found!")
            return

        print(f"Target Corridor: {c40.name} (id={c40.id}, code={c40.prototype_code})")

        # 1. Update sections 22-29 to corridor_id = 30
        c40_sec_codes = [
            "SEC_MDU_TDN", "SEC_TDN_TMQ", "SEC_TMQ_VPT", "SEC_VPT_SRT",
            "SEC_SRT_CVP", "SEC_CVP_KDU", "SEC_KDU_MEJ", "SEC_MEJ_TEN"
        ]
        sections = db.query(RailwaySection).filter(RailwaySection.section_id.in_(c40_sec_codes)).all()
        sec_id_map = {}
        for s in sections:
            old_cid = s.corridor_id
            s.corridor_id = 30
            sec_id_map[s.section_id] = s.id
            print(f"  Section {s.section_id} (id={s.id}): corridor_id updated {old_cid} -> 30")

        # 2. Update BlockWindows for these sections to corridor_id = 30
        sec_ids = [s.id for s in sections]
        windows = db.query(BlockWindow).filter(BlockWindow.section_id.in_(sec_ids)).all()
        for w in windows:
            w.corridor_id = 30
        print(f"  Updated {len(windows)} BlockWindows to corridor_id = 30")

        # 3. Align canonical requests REQ-101, 102, 103 to physical section SEC_CVP_KDU
        cvp_kdu_sec_id = sec_id_map.get("SEC_CVP_KDU") or 22
        jobs = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(["REQ-101", "REQ-102", "REQ-103"])).all()
        for j in jobs:
            old_sid = j.section_id
            j.corridor_id = 30
            j.section_id = cvp_kdu_sec_id
            j.start_station_code = "CVP"
            j.end_station_code = "KDU"
            print(f"  Job {j.job_code}: section_id updated {old_sid} -> {cvp_kdu_sec_id} (CVP-KDU), corridor_id -> 30")

        # 4. Also align REQ-104 and REQ-105 to SEC_MDU_TDN
        mdu_tdn_sec_id = sec_id_map.get("SEC_MDU_TDN") or 25
        jobs_mdu = db.query(MaintenanceJob).filter(MaintenanceJob.job_code.in_(["REQ-104", "REQ-105"])).all()
        for j in jobs_mdu:
            j.corridor_id = 30
            j.section_id = mdu_tdn_sec_id
            j.start_station_code = "MDU"
            j.end_station_code = "TDN"
            print(f"  Job {j.job_code}: section_id updated -> {mdu_tdn_sec_id} (MDU-TDN), corridor_id -> 30")

        db.commit()
        print("\nSuccessfully aligned Corridor C40 physical sections, windows, and canonical requests!")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    align_c40_physical_sections()
