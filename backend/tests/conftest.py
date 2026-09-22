import pytest
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.models import (
    Department, User, Station, Corridor, RailwaySection, Resource, Asset,
    Train, TrainRouteStop, TrainMovement, MaintenanceJob, MaintenanceJobResource, BlockPlan, PlanJob
)
from app.core.security import get_password_hash, create_access_token
from app.core.config import settings
from app.seed_data import seed_database
from app.algorithms.priority import PriorityEngine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Initializes clean database with master infrastructure and isolated test fixtures for testing."""
    # Temporarily set mock mode during test suite execution
    settings.TRAIN_DATA_MODE = "mock"

    db = SessionLocal()
    try:
        db.query(BlockPlan).delete()
        db.query(MaintenanceJobResource).delete()
        db.query(MaintenanceJob).delete()
        db.query(TrainRouteStop).filter(TrainRouteStop.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db.query(TrainMovement).filter(TrainMovement.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db.query(Train).filter(Train.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db.commit()

        seed_database(db)

        if db.query(Train).count() == 0:
            try:
                from app.scripts.import_railway_documents import RailwayDocumentImporter
                RailwayDocumentImporter(db).import_all()
            except Exception as e:
                print(f"[CONFTEST] Document import notice: {e}")


        # Add test trains for algorithm & flow tests
        stn_ndls = db.query(Station).filter(Station.code == "NDLS").first()
        stn_gzb = db.query(Station).filter(Station.code == "GZB").first()
        stn_aljn = db.query(Station).filter(Station.code == "ALJN").first()
        stn_tdl = db.query(Station).filter(Station.code == "TDL").first()
        stn_cnb = db.query(Station).filter(Station.code == "CNB").first()
        stn_pryj = db.query(Station).filter(Station.code == "PRYJ").first()
        stn_ddu = db.query(Station).filter(Station.code == "DDU").first()

        t_12919 = Train(
            train_number="12919",
            train_name="Malwa Superfast Express",
            train_type="SUPERFAST",
            priority_level=2,
            source_station_id=stn_ndls.id,
            destination_station_id=stn_ddu.id
        )
        t_22436 = Train(
            train_number="22436",
            train_name="Vande Bharat Express",
            train_type="VANDE_BHARAT",
            priority_level=1,
            source_station_id=stn_ndls.id,
            destination_station_id=stn_ddu.id
        )
        db.add_all([t_12919, t_22436])
        db.commit()

        stops_12919 = [
            TrainRouteStop(train_number="12919", station_id=stn_ndls.id, sequence=1, arrival_min=630, departure_min=645, distance_km=0),
            TrainRouteStop(train_number="12919", station_id=stn_gzb.id, sequence=2, arrival_min=680, departure_min=690, distance_km=25),
            TrainRouteStop(train_number="12919", station_id=stn_aljn.id, sequence=3, arrival_min=750, departure_min=755, distance_km=131),
            TrainRouteStop(train_number="12919", station_id=stn_tdl.id, sequence=4, arrival_min=810, departure_min=815, distance_km=209),
            TrainRouteStop(train_number="12919", station_id=stn_cnb.id, sequence=5, arrival_min=980, departure_min=990, distance_km=437),
            TrainRouteStop(train_number="12919", station_id=stn_pryj.id, sequence=6, arrival_min=1120, departure_min=1130, distance_km=631),
            TrainRouteStop(train_number="12919", station_id=stn_ddu.id, sequence=7, arrival_min=1250, departure_min=1260, distance_km=784)
        ]
        db.add_all(stops_12919)
        db.commit()

        # Add test maintenance jobs
        dept_engg = db.query(Department).filter(Department.code == "ENGG").first()
        dept_snt = db.query(Department).filter(Department.code == "SNT").first()
        dept_trd = db.query(Department).filter(Department.code == "TRD").first()

        j1 = MaintenanceJob(
            job_code="TEST_ENGG_01",
            department_id=dept_engg.id,
            section_id=2,
            location_km=42.0,
            work_type="TRACK_TAMPING",
            description="Test Track Tamping",
            criticality=80.0,
            safety_impact=85.0,
            operational_impact=70.0,
            urgency=75.0,
            estimated_duration_min=60,
            priority_score=80.0,
            safety_tier="Tier 2",
            status="SUBMITTED"
        )
        j2 = MaintenanceJob(
            job_code="TEST_SNT_01",
            department_id=dept_snt.id,
            section_id=2,
            location_km=42.5,
            work_type="SIGNAL_POINT_OVERHAUL",
            description="Test Point Overhaul",
            criticality=75.0,
            safety_impact=80.0,
            operational_impact=65.0,
            urgency=70.0,
            estimated_duration_min=30,
            priority_score=75.0,
            safety_tier="Tier 2",
            status="SUBMITTED"
        )
        j3 = MaintenanceJob(
            job_code="TEST_TRD_01",
            department_id=dept_trd.id,
            section_id=2,
            location_km=42.8,
            work_type="OHE_INSPECTION",
            description="Test OHE Inspection",
            criticality=70.0,
            safety_impact=75.0,
            operational_impact=60.0,
            urgency=65.0,
            estimated_duration_min=60,
            priority_score=70.0,
            safety_tier="Tier 3",
            status="SUBMITTED"
        )
        db.add_all([j1, j2, j3])
        db.commit()
    finally:
        db.close()
    yield
    db_clean = SessionLocal()
    try:
        db_clean.query(PlanJob).delete()
        db_clean.query(BlockPlan).delete()
        db_clean.query(MaintenanceJobResource).delete()
        db_clean.query(MaintenanceJob).delete()
        db_clean.query(TrainRouteStop).filter(TrainRouteStop.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db_clean.query(TrainMovement).filter(TrainMovement.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db_clean.query(Train).filter(Train.train_number.in_(["12919", "22436"])).delete(synchronize_session=False)
        db_clean.commit()

        # Ensure authoritative timetable trains are present
        if db_clean.query(Train).count() == 0:
            try:
                from app.scripts.import_railway_documents import RailwayDocumentImporter
                RailwayDocumentImporter(db_clean).import_all()
            except Exception as ex:
                print(f"[CONFTEST TEARDOWN] Importer notice: {ex}")
    finally:
        db_clean.close()
    settings.TRAIN_DATA_MODE = "live"

