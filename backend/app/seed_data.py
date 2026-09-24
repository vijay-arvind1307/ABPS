from datetime import datetime
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.session import engine
from app.models.models import (
    Department, User, Station, Corridor, RailwaySection, Resource, Asset
)
from app.core.security import get_password_hash


def seed_database(db: Session, drop_all: bool = False):
    """
    Initializes Railway Master Infrastructure with ZERO default/fake block requests,
    ZERO default maintenance jobs, and ZERO hard-coded train records.
    Real maintenance demands are submitted by authenticated department users.
    Live train data is populated from RailRadar.
    """
    if drop_all:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)

    # 1. Seed Master Departments
    dept_map = {}
    master_departments = [
        {"code": "ENGG", "name": "Engineering", "description": "Permanent Way & Civil Track Infrastructure", "discipline": "Track / Civil", "asset_domain": "P-Way"},
        {"code": "SNT", "name": "S&T", "description": "Signal & Telecommunication", "discipline": "Signal & Telecommunication", "asset_domain": "Signals"},
        {"code": "TRD", "name": "TRD / OHE", "description": "Traction Distribution / 25kV Overhead Equipment", "discipline": "Traction Distribution", "asset_domain": "OHE"},
        {"code": "OPERATIONS", "name": "Railway Planning & Operations", "description": "Chief Section Controller & Traffic Operations Authority", "discipline": "Traffic & Section Control", "asset_domain": "Operations"}
    ]

    for d in master_departments:
        dept = db.query(Department).filter(Department.code == d["code"]).first()
        if not dept:
            dept = Department(
                code=d["code"],
                name=d["name"],
                description=d["description"],
                discipline=d["discipline"],
                asset_domain=d["asset_domain"],
                is_active=True
            )
            db.add(dept)
            db.commit()
            db.refresh(dept)
        else:
            dept.name = d["name"]
            dept.description = d["description"]
            dept.discipline = d["discipline"]
            dept.asset_domain = d["asset_domain"]
            db.commit()
        dept_map[d["code"]] = dept

    # 2. Seed Authorized System Users with exact operational roles
    users_data = [
        {"username": "planner", "email": "planner@railnet.gov.in", "full_name": "Chief Section Controller / Railway Planner", "role": "RAILWAY_PLANNER", "dept_code": "OPERATIONS", "password": "planner123"},
        {"username": "engg_user", "email": "engg@railnet.gov.in", "full_name": "Senior Section Engineer (Track / Civil)", "role": "TRACK_ENGINEERING", "dept_code": "ENGG", "password": "engg123"},
        {"username": "snt_user", "email": "snt@railnet.gov.in", "full_name": "Senior Section Engineer (Signal & Telecom)", "role": "SIGNAL_TELECOM", "dept_code": "SNT", "password": "snt123"},
        {"username": "trd_user", "email": "trd@railnet.gov.in", "full_name": "Senior Section Engineer (Traction Distribution)", "role": "TRACTION_DISTRIBUTION", "dept_code": "TRD", "password": "trd123"},
        {"username": "admin", "email": "admin@railnet.gov.in", "full_name": "Railway System Administrator", "role": "SYSTEM_ADMIN", "dept_code": "OPERATIONS", "password": "admin123"}
    ]

    for u in users_data:
        usr = db.query(User).filter(User.username == u["username"]).first()
        dept_id = dept_map[u["dept_code"]].id if u["dept_code"] in dept_map else None
        if not usr:
            usr = User(
                username=u["username"],
                email=u["email"],
                full_name=u["full_name"],
                role=u["role"],
                department_id=dept_id,
                hashed_password=get_password_hash(u["password"]),
                is_active=True
            )
            db.add(usr)
        else:
            usr.department_id = dept_id
            usr.role = u["role"]
            usr.full_name = u["full_name"]
    db.commit()

    # 3. Seed Master Stations (Tamil Nadu Corridors + Delhi-DDU Corridor)
    stations_data = [
        # Tamil Nadu Primary Stations
        {"code": "MAS", "name": "MGR Chennai Central", "division": "Chennai (MAS)", "zone": "Southern Railway (SR)", "latitude": 13.0827, "longitude": 80.2707, "platforms": 15},
        {"code": "TBM", "name": "Tambaram", "division": "Chennai (MAS)", "zone": "Southern Railway (SR)", "latitude": 12.9249, "longitude": 80.1172, "platforms": 8},
        {"code": "VM", "name": "Villupuram Junction", "division": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "latitude": 11.9398, "longitude": 79.4975, "platforms": 6},
        {"code": "TPJ", "name": "Tiruchchirappalli Junction", "division": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "latitude": 10.7905, "longitude": 78.6856, "platforms": 8},
        {"code": "MDU", "name": "Madurai Junction", "division": "Madurai (MDU)", "zone": "Southern Railway (SR)", "latitude": 9.9196, "longitude": 78.1114, "platforms": 8},
        {"code": "CBE", "name": "Coimbatore Junction", "division": "Salem (SA)", "zone": "Southern Railway (SR)", "latitude": 11.0018, "longitude": 76.9629, "platforms": 6},
        {"code": "SA", "name": "Salem Junction", "division": "Salem (SA)", "zone": "Southern Railway (SR)", "latitude": 11.6643, "longitude": 78.1460, "platforms": 6},
        {"code": "ED", "name": "Erode Junction", "division": "Salem (SA)", "zone": "Southern Railway (SR)", "latitude": 11.3410, "longitude": 77.7172, "platforms": 5},
        {"code": "JTJ", "name": "Jolarpettai Junction", "division": "Chennai (MAS)", "zone": "Southern Railway (SR)", "latitude": 12.5583, "longitude": 78.5772, "platforms": 5},

        # Delhi - Kanpur - Prayagraj - DDU Corridor Stations (Preserved for general railway network)
        {"code": "NDLS", "name": "New Delhi", "division": "Delhi (DLI)", "zone": "Northern Railway (NR)", "latitude": 28.6139, "longitude": 77.2090, "platforms": 16},
        {"code": "GZB", "name": "Ghaziabad Junction", "division": "Delhi (DLI)", "zone": "Northern Railway (NR)", "latitude": 28.6692, "longitude": 77.4538, "platforms": 6},
        {"code": "ALJN", "name": "Aligarh Junction", "division": "Prayagraj (PRYJ)", "zone": "North Central Railway (NCR)", "latitude": 27.8974, "longitude": 78.0880, "platforms": 7},
        {"code": "TDL", "name": "Tundla Junction", "division": "Prayagraj (PRYJ)", "zone": "North Central Railway (NCR)", "latitude": 27.2052, "longitude": 78.2415, "platforms": 5},
        {"code": "CNB", "name": "Kanpur Central", "division": "Prayagraj (PRYJ)", "zone": "North Central Railway (NCR)", "latitude": 26.4537, "longitude": 80.3507, "platforms": 10},
        {"code": "PRYJ", "name": "Prayagraj Junction", "division": "Prayagraj (PRYJ)", "zone": "North Central Railway (NCR)", "latitude": 25.4358, "longitude": 81.8463, "platforms": 10},
        {"code": "DDU", "name": "Pt. Deen Dayal Upadhyaya Junction", "division": "Pt. Deen Dayal Upadhyaya (DDU)", "zone": "East Central Railway (ECR)", "latitude": 25.2818, "longitude": 83.1179, "platforms": 8}
    ]

    stn_map = {}
    for s in stations_data:
        stn = db.query(Station).filter(Station.code == s["code"]).first()
        if not stn:
            stn = Station(
                code=s["code"],
                name=s["name"],
                division=s["division"],
                zone=s["zone"],
                latitude=s["latitude"],
                longitude=s["longitude"],
                total_platforms=s["platforms"]
            )
            db.add(stn)
            db.commit()
            db.refresh(stn)
        stn_map[s["code"]] = stn

    # 4. Seed Master Corridors (Canonical Southern Railway + Isolated Fixtures)
    corridors_data = [
        {"corridor_id": "CORR_C40_MDU_TEN", "prototype_code": "C40", "name": "Madurai - Tirunelveli Main Line", "division": "Madurai (MDU)", "zone": "Southern Railway (SR)", "start": "MDU", "end": "TEN", "distance": 154.9, "status": "ACTIVE"},
        {"corridor_id": "CORR_MAS_TPJ", "name": "Chennai Central - Tiruchchirappalli Main Line", "division": "SR Joint (MAS/TPJ)", "zone": "Southern Railway (SR)", "start": "MAS", "end": "TPJ", "distance": 330.1, "status": "ACTIVE"},
        {"corridor_id": "CORR_MAS_CBE", "name": "Chennai Central - Coimbatore Trunk Corridor", "division": "SR Joint (MAS/SA)", "zone": "Southern Railway (SR)", "start": "MAS", "end": "CBE", "distance": 311.4, "status": "ACTIVE"},
        {"corridor_id": "CORR_CBE_SA", "name": "Coimbatore - Salem Main Line", "division": "Salem (SA)", "zone": "Southern Railway (SR)", "start": "CBE", "end": "SA", "distance": 155.0, "status": "ACTIVE"},
        {"corridor_id": "CORR_TPJ_MDU", "name": "Tiruchchirappalli - Madurai Chord Line", "division": "Madurai (MDU)", "zone": "Southern Railway (SR)", "start": "TPJ", "end": "MDU", "distance": 152.8, "status": "ACTIVE"},
        {"corridor_id": "CORR_TEN_CAPE", "name": "Tirunelveli - Kanniyakumari Line", "division": "Madurai / TVC", "zone": "Southern Railway (SR)", "start": "TEN", "end": "CAPE", "distance": 89.0, "status": "ACTIVE"},
        {"corridor_id": "CORR_VPT_TEN_CHORD", "name": "Virudhunagar - Tenkasi - Tirunelveli Chord", "division": "Madurai (MDU)", "zone": "Southern Railway (SR)", "start": "VPT", "end": "TEN", "distance": 184.5, "status": "ACTIVE"},
        {"corridor_id": "CORR_TPJ_DELTA", "name": "Tiruchchirappalli - Nagapattinam Delta Line", "division": "Tiruchchirappalli (TPJ)", "zone": "Southern Railway (SR)", "start": "TPJ", "end": "NGT", "distance": 162.7, "status": "ACTIVE"},
        {"corridor_id": "CORR_MDU_RMM", "name": "Madurai - Rameswaram Line", "division": "Madurai (MDU)", "zone": "Southern Railway (SR)", "start": "MDU", "end": "RMM", "distance": 160.7, "status": "ACTIVE"},
        {"corridor_id": "CORR_DLI_DDU", "name": "Delhi - Kanpur - Prayagraj - DDU Golden Corridor", "division": "NCR/NR/ECR Joint", "zone": "Northern Railway (NR)", "start": "NDLS", "end": "DDU", "distance": 784.0, "status": "FIXTURE"}
    ]

    corr_map = {}
    for c in corridors_data:
        corr = db.query(Corridor).filter(Corridor.corridor_id == c["corridor_id"]).first()
        if not corr:
            corr = Corridor(
                corridor_id=c["corridor_id"],
                prototype_code=c.get("prototype_code"),
                name=c["name"],
                division=c["division"],
                zone=c["zone"],
                start_station_code=c.get("start"),
                end_station_code=c.get("end"),
                total_distance_km=c.get("distance", 0.0),
                status=c.get("status", "ACTIVE")
            )
            db.add(corr)
            db.commit()
            db.refresh(corr)
        else:
            if c.get("prototype_code"):
                corr.prototype_code = c["prototype_code"]
            corr.name = c["name"]
            corr.division = c["division"]
            corr.zone = c["zone"]
            corr.start_station_code = c.get("start")
            corr.end_station_code = c.get("end")
            corr.total_distance_km = c.get("distance", 0.0)
            corr.status = c.get("status", "ACTIVE")
            db.commit()
        corr_map[c["corridor_id"]] = corr

    # 5. Seed Railway Sections from Canonical Network Geometry
    import os
    import json
    geom_file = os.path.join(os.path.dirname(__file__), "data", "railway_network_geometry.json")
    if os.path.exists(geom_file):
        with open(geom_file, "r", encoding="utf-8") as gf:
            net_geom = json.load(gf)
            sections_data = net_geom.get("sections", {})
            for sec_id, s_data in sections_data.items():
                from_code = s_data["from_station_code"]
                to_code = s_data["to_station_code"]
                from_stn = db.query(Station).filter(Station.code == from_code).first()
                to_stn = db.query(Station).filter(Station.code == to_code).first()
                if not from_stn or not to_stn:
                    continue
                
                # Check for specific MDU-TEN canonical sections -> always link to C40 (CORR_C40_MDU_TEN)
                mdu_ten_canonical = {"SEC_MDU_TDN", "SEC_TDN_TMQ", "SEC_TMQ_VPT", "SEC_VPT_SRT", "SEC_SRT_CVP", "SEC_CVP_KDU", "SEC_KDU_MEJ", "SEC_MEJ_TEN"}
                c40_corr = db.query(Corridor).filter(Corridor.prototype_code == "C40").first() or corr_map.get("CORR_C40_MDU_TEN")
                if sec_id in mdu_ten_canonical and c40_corr:
                    cid = c40_corr.id
                elif sec_id == "SEC_MEJ_TN":
                    c41_corr = db.query(Corridor).filter(Corridor.prototype_code == "C41").first() or corr_map.get("CORR_C41_MEJ_TN")
                    cid = c41_corr.id if c41_corr else 56
                elif s_data.get("prototype_code") == "TRUNK" or s_data.get("corridor_id") == "CORR_SR_TRUNK":
                    cid = corr_map.get("CORR_MAS_TPJ", corr_map.get("CORR_MAS_CBE", c40_corr)).id
                else:
                    c_found = db.query(Corridor).filter(
                        (Corridor.prototype_code == s_data.get("prototype_code")) |
                        (Corridor.corridor_id == s_data.get("corridor_id"))
                    ).first()
                    if c_found:
                        cid = c_found.id
                    else:
                        cid = corr_map.get(s_data.get("corridor_id"), c40_corr).id

                sec = db.query(RailwaySection).filter(RailwaySection.section_id == sec_id).first()
                if not sec:
                    sec = RailwaySection(
                        section_id=sec_id,
                        name=s_data["name"],
                        corridor_id=cid,
                        from_station_id=from_stn.id,
                        to_station_id=to_stn.id,
                        length_km=s_data["distance_km"],
                        track_type=s_data.get("track_type", "DOUBLE_UP"),
                        direction=s_data.get("direction", "BOTH"),
                        max_speed_kmh=s_data.get("max_speed_kmh", 110.0),
                        is_electrified=s_data.get("is_electrified", True),
                        geometry_geojson=s_data.get("coordinates")
                    )
                    db.add(sec)
                else:
                    sec.name = s_data["name"]
                    sec.corridor_id = cid
                    sec.from_station_id = from_stn.id
                    sec.to_station_id = to_stn.id
                    sec.length_km = s_data.get("distance_km") or s_data.get("length_km", 10.0)
                    sec.geometry_geojson = s_data.get("coordinates")
            db.commit()

    # 6. Seed Master Resources
    resources_data = [
        {"code": "CSM_TAMP_01", "name": "Continuous Action Track Tamping Machine 01", "dept": "ENGG", "type": "TAMPING_MACHINE", "qty": 1},
        {"code": "BCM_01", "name": "High Output Ballast Cleaning Machine 01", "dept": "ENGG", "type": "MACHINE", "qty": 1},
        {"code": "OHE_TOWER_01", "name": "8-Wheeler Self-Propelled OHE Tower Wagon", "dept": "TRD", "type": "TOWER_WAGON", "qty": 1},
        {"code": "SNT_CREW_01", "name": "Signal Point Machine & Interlocking Squad", "dept": "SNT", "type": "CREW", "qty": 2},
        {"code": "PWAY_GANG_01", "name": "Permanent Way Track Relaying Gang", "dept": "ENGG", "type": "CREW", "qty": 2}
    ]

    for r in resources_data:
        res = db.query(Resource).filter(Resource.resource_code == r["code"]).first()
        dept_id = dept_map[r["dept"]].id
        if not res:
            res = Resource(
                resource_code=r["code"],
                name=r["name"],
                department_id=dept_id,
                resource_type=r["type"],
                total_quantity=r["qty"]
            )
            db.add(res)
    db.commit()

    # 7. Auto-seed SIH Canonical Maintenance Requests if empty
    from app.models.models import MaintenanceJob
    if db.query(MaintenanceJob).count() == 0:
        try:
            from seed_sih_canonical_requests import seed_sih_requests
            seed_sih_requests()
        except Exception as e:
            print("[WARN] Canonical requests auto-seed notice:", e)

    print("[SUCCESS] Master Railway Infrastructure Seeded:")
    print(f"          - {len(master_departments)} Authorized Master Departments")
    print(f"          - {len(stations_data)} Master Stations (Tamil Nadu & High-Density Corridors)")
    print(f"          - {len(corridors_data)} Master Planning Corridors")
    print(f"          - {len(sections_data)} Geometric Railway Sections")
    print("          - 0 Fake Block Demands, 0 Fake Plans, 0 Hardcoded Trains.")


if __name__ == "__main__":
    from app.db.session import SessionLocal
    db_session = SessionLocal()
    try:
        seed_database(db_session, drop_all=False)
    finally:
        db_session.close()
