from datetime import datetime
from app.db.session import SessionLocal
from app.models.models import Department, Corridor, RailwaySection, MaintenanceJob, User, Station

def seed_sih_requests():
    db = SessionLocal()
    try:
        # Departments
        engg = db.query(Department).filter(Department.code == "ENGG").first()
        snt = db.query(Department).filter(Department.code == "SNT").first()
        trd = db.query(Department).filter(Department.code == "TRD").first()

        # Stations
        cvp_stn = db.query(Station).filter(Station.code == "CVP").first()
        ten_stn = db.query(Station).filter(Station.code == "TEN").first()
        mdu_stn = db.query(Station).filter(Station.code == "MDU").first()
        cbe_stn = db.query(Station).filter(Station.code == "CBE").first()
        sa_stn = db.query(Station).filter(Station.code == "SA").first()

        # Corridors
        corr_mdu_ten = db.query(Corridor).filter(Corridor.corridor_id == "CORR_C15_MDU_TEN").first() or \
                       db.query(Corridor).filter(Corridor.start_station_code == "MDU", Corridor.end_station_code == "TEN").first()
        corr_cbe_sa = db.query(Corridor).filter(Corridor.corridor_id == "CORR_C10_CBE_SA").first() or \
                      db.query(Corridor).filter(Corridor.start_station_code == "CBE", Corridor.end_station_code == "SA").first()

        # Sections
        sec_103 = db.query(RailwaySection).filter(RailwaySection.section_id == "SECTION-103").first()
        if not sec_103:
            sec_103 = RailwaySection(
                section_id="SECTION-103",
                name="SECTION-103 (Kovilpatti - Tirunelveli)",
                corridor_id=corr_mdu_ten.id if corr_mdu_ten else 10,
                from_station_id=cvp_stn.id if cvp_stn else 293,
                to_station_id=ten_stn.id if ten_stn else 287,
                length_km=65.0,
                max_speed_kmh=110.0,
                track_type="DOUBLE_UP",
                direction="BOTH",
                is_electrified=True
            )
            db.add(sec_103)
            db.commit()
            db.refresh(sec_103)

        sec_204 = db.query(RailwaySection).filter(RailwaySection.section_id == "SECTION-204").first()
        if not sec_204:
            sec_204 = RailwaySection(
                section_id="SECTION-204",
                name="SECTION-204 (Madurai - Tirunelveli)",
                corridor_id=corr_mdu_ten.id if corr_mdu_ten else 10,
                from_station_id=mdu_stn.id if mdu_stn else 5,
                to_station_id=ten_stn.id if ten_stn else 287,
                length_km=155.0,
                max_speed_kmh=110.0,
                track_type="DOUBLE_UP",
                direction="BOTH",
                is_electrified=True
            )
            db.add(sec_204)
            db.commit()
            db.refresh(sec_204)

        sec_305 = db.query(RailwaySection).filter(RailwaySection.section_id == "SECTION-305").first()
        if not sec_305:
            sec_305 = RailwaySection(
                section_id="SECTION-305",
                name="SECTION-305 (Coimbatore - Salem)",
                corridor_id=corr_cbe_sa.id if corr_cbe_sa else 11,
                from_station_id=cbe_stn.id if cbe_stn else 6,
                to_station_id=sa_stn.id if sa_stn else 7,
                length_km=160.0,
                max_speed_kmh=120.0,
                track_type="DOUBLE_UP",
                direction="BOTH",
                is_electrified=True
            )
            db.add(sec_305)
            db.commit()
            db.refresh(sec_305)

        planner = db.query(User).filter(User.username == "planner").first()

        reqs_data = [
            {
                "job_code": "REQ-101",
                "dept": engg,
                "work_title": "Track Tamping",
                "work_type": "TRACK_TAMPING",
                "corridor": corr_mdu_ten,
                "start_stn": "CVP",
                "end_stn": "TEN",
                "section": sec_103,
                "duration": 90,
                "priority": "HIGH",
                "priority_score": 88.0,
                "due_date": datetime(2026, 9, 16),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "10:45",
                "requested_end_time": "12:15",
                "desc": "Heavy mechanized hydraulic track tamping and ballast stabilization."
            },
            {
                "job_code": "REQ-102",
                "dept": snt,
                "work_title": "Signal Maintenance",
                "work_type": "SIGNAL_INSPECTION",
                "corridor": corr_mdu_ten,
                "start_stn": "CVP",
                "end_stn": "TEN",
                "section": sec_103,
                "duration": 60,
                "priority": "MEDIUM",
                "priority_score": 68.0,
                "due_date": datetime(2026, 9, 16),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "10:45",
                "requested_end_time": "11:45",
                "desc": "Point machine testing and track circuit impedance calibration."
            },
            {
                "job_code": "REQ-103",
                "dept": trd,
                "work_title": "OHE Maintenance",
                "work_type": "OHE_INSPECTION",
                "corridor": corr_mdu_ten,
                "start_stn": "CVP",
                "end_stn": "TEN",
                "section": sec_103,
                "duration": 75,
                "priority": "HIGH",
                "priority_score": 82.0,
                "due_date": datetime(2026, 9, 16),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "10:45",
                "requested_end_time": "12:00",
                "desc": "Contact wire stagger alignment and cantilever insulator inspection under 25kV power block."
            },
            {
                "job_code": "REQ-104",
                "dept": engg,
                "work_title": "Track Inspection",
                "work_type": "TRACK_INSPECTION",
                "corridor": corr_mdu_ten,
                "start_stn": "MDU",
                "end_stn": "TEN",
                "section": sec_204,
                "duration": 90,
                "priority": "HIGH",
                "priority_score": 85.0,
                "due_date": datetime(2026, 9, 17),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "13:00",
                "requested_end_time": "14:30",
                "desc": "Ultrasonic rail flaw detection (USFD) testing and track gauge verification."
            },
            {
                "job_code": "REQ-105",
                "dept": snt,
                "work_title": "Signal Inspection",
                "work_type": "SIGNAL_INSPECTION",
                "corridor": corr_mdu_ten,
                "start_stn": "MDU",
                "end_stn": "TEN",
                "section": sec_204,
                "duration": 60,
                "priority": "MEDIUM",
                "priority_score": 66.0,
                "due_date": datetime(2026, 9, 17),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "13:00",
                "requested_end_time": "14:00",
                "desc": "Automatic signaling relay overhaul and axle counter head cleaning."
            },
            {
                "job_code": "REQ-106",
                "dept": engg,
                "work_title": "Track Maintenance",
                "work_type": "TRACK_MAINTENANCE",
                "corridor": corr_cbe_sa,
                "start_stn": "CBE",
                "end_stn": "SA",
                "section": sec_305,
                "duration": 120,
                "priority": "HIGH",
                "priority_score": 82.0,
                "due_date": datetime(2026, 9, 17),
                "requested_date": datetime(2026, 9, 15),
                "requested_start_time": "15:00",
                "requested_end_time": "17:00",
                "desc": "Weld restoration, sleeper fastening replacement, and deep screening on high-speed corridor."
            }
        ]

        for r in reqs_data:
            existing = db.query(MaintenanceJob).filter(MaintenanceJob.job_code == r["job_code"]).first()
            if not existing:
                job = MaintenanceJob(
                    job_code=r["job_code"],
                    department_id=r["dept"].id if r["dept"] else 1,
                    work_title=r["work_title"],
                    work_type=r["work_type"],
                    corridor_id=r["corridor"].id if r["corridor"] else None,
                    start_station_code=r["start_stn"],
                    end_station_code=r["end_stn"],
                    section_id=r["section"].id if r["section"] else None,
                    estimated_duration_min=r["duration"],
                    user_priority=r["priority"],
                    priority_score=r["priority_score"],
                    due_date=r["due_date"],
                    requested_date=r["requested_date"],
                    requested_start_time=r["requested_start_time"],
                    requested_end_time=r["requested_end_time"],
                    description=r["desc"],
                    status="SUBMITTED",
                    created_by_id=planner.id if planner else None,
                    created_at=datetime.utcnow()
                )
                db.add(job)
            else:
                # Reset to SUBMITTED so planner can optimize fresh
                existing.status = "SUBMITTED"
                existing.section_id = r["section"].id if r["section"] else existing.section_id
                existing.work_title = r["work_title"]
                existing.work_type = r["work_type"]
                existing.estimated_duration_min = r["duration"]
                existing.user_priority = r["priority"]
                existing.priority_score = r["priority_score"]
                existing.requested_date = r["requested_date"]
                existing.due_date = r["due_date"]
                existing.coordinated_plan_id = None
                existing.coordination_status = "NOT_CHECKED"

        db.commit()
        print("Successfully seeded REQ-101 through REQ-106!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_sih_requests()
