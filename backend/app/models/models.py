from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)  # ENGG, SNT, TRD, OPERATIONS
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    discipline = Column(String(100), nullable=True)  # Track / Civil, Signal & Telecommunication, Traction Distribution
    asset_domain = Column(String(50), nullable=True)  # P-Way, Signals, OHE
    is_active = Column(Boolean, default=True)

    users = relationship("User", back_populates="department")
    jobs = relationship("MaintenanceJob", back_populates="department")
    resources = relationship("Resource", back_populates="department")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False)  # department_user, railway_planner, admin
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department", back_populates="users")


class RailwayStation(Base):
    __tablename__ = "railway_stations"

    id = Column(Integer, primary_key=True, index=True)
    station_code = Column(String(10), unique=True, index=True, nullable=False)
    station_name = Column(String(150), nullable=False)
    normalized_station_name = Column(String(150), index=True, nullable=False)
    state = Column(String(50), index=True, nullable=False)
    district = Column(String(100), nullable=True)
    division = Column(String(20), index=True, nullable=False)
    category = Column(String(20), nullable=False)
    station_type = Column(String(30), nullable=True)  # TERMINAL, JUNCTION, REGULAR, FLAG, HALT
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    source = Column(String(150), default="Southern Railway Station List (01.04.2025)")
    source_version = Column(String(50), default="01.04.2025")
    last_verified = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False)  # NDLS, GZB, CNB, PRYJ, DDU
    name = Column(String(100), nullable=False)
    division = Column(String(50), nullable=False)
    zone = Column(String(20), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    total_platforms = Column(Integer, default=4)


class Corridor(Base):
    __tablename__ = "corridors"

    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(String(30), unique=True, index=True, nullable=False)  # e.g. C01, CORR_MDU_TEN
    prototype_code = Column(String(10), nullable=True, index=True)  # C01, C02, ..., C20
    name = Column(String(150), nullable=False)
    division = Column(String(50), nullable=False)
    zone = Column(String(50), nullable=False)
    start_station_code = Column(String(10), nullable=True)
    end_station_code = Column(String(10), nullable=True)
    total_distance_km = Column(Float, default=0.0)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, FIXTURE, INACTIVE
    description = Column(String(255), nullable=True)

    sections = relationship("RailwaySection", back_populates="corridor")


class RailwaySection(Base):
    __tablename__ = "railway_sections"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(String(30), unique=True, index=True, nullable=False)  # SEC_NDLS_GZB_UP
    name = Column(String(150), nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=False)
    from_station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    to_station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    length_km = Column(Float, nullable=False)
    track_type = Column(String(20), default="DOUBLE_UP")  # SINGLE, DOUBLE_UP, DOUBLE_DN, QUAD_UP1, QUAD_DN1
    direction = Column(String(10), default="UP")  # UP, DOWN, BOTH
    max_speed_kmh = Column(Float, default=130.0)
    is_electrified = Column(Boolean, default=True)
    geometry_geojson = Column(JSON, nullable=True)  # List of coordinates or GeoJSON

    corridor = relationship("Corridor", back_populates="sections")
    from_station = relationship("Station", foreign_keys=[from_station_id])
    to_station = relationship("Station", foreign_keys=[to_station_id])
    assets = relationship("Asset", back_populates="section")
    maintenance_jobs = relationship("MaintenanceJob", back_populates="section")


class Train(Base):
    __tablename__ = "trains"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), unique=True, index=True, nullable=False)
    train_name = Column(String(150), nullable=False)
    train_type = Column(String(30), nullable=False)  # VANDE_BHARAT, RAJDHANI, SHATABDI, SUPERFAST, EXPRESS, FREIGHT
    category = Column(String(50), nullable=True)  # SUPERFAST, MAIL_EXPRESS, PASSENGER, etc.
    priority_level = Column(Integer, default=2)  # 1 (Highest, Rajdhani/VB) to 5 (Freight)
    source_station_id = Column(Integer, ForeignKey("stations.id"), nullable=True)
    destination_station_id = Column(Integer, ForeignKey("stations.id"), nullable=True)
    source_code = Column(String(10), nullable=True)
    source_name = Column(String(100), nullable=True)
    destination_code = Column(String(10), nullable=True)
    destination_name = Column(String(100), nullable=True)
    running_days = Column(String(50), default="DAILY")
    is_tn_relevant = Column(Boolean, default=False, index=True)
    active = Column(Boolean, default=True)
    source = Column(String(100), default="RAILRADAR")
    source_version = Column(String(50), default="v1")
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_station = relationship("Station", foreign_keys=[source_station_id])
    destination_station = relationship("Station", foreign_keys=[destination_station_id])
    route_stops = relationship("TrainRouteStop", back_populates="train", order_by="TrainRouteStop.sequence")
    routes = relationship("TrainRoute", back_populates="train", order_by="TrainRoute.sequence")


class TrainRouteStop(Base):
    __tablename__ = "train_route_stops"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), ForeignKey("trains.train_number"), nullable=False)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=True)
    station_code = Column(String(10), nullable=True, index=True)
    station_name = Column(String(100), nullable=True)
    sequence = Column(Integer, nullable=False)
    arrival_min = Column(Integer, nullable=False)  # Minutes from 00:00 of day 0 (e.g. 600 = 10:00)
    departure_min = Column(Integer, nullable=False)
    halt_min = Column(Integer, default=2)
    distance_km = Column(Float, default=0.0)
    day_offset = Column(Integer, default=0)
    is_halt = Column(Boolean, default=True)
    source = Column(String(100), default="RAILRADAR")
    last_verified_at = Column(DateTime, default=datetime.utcnow)

    train = relationship("Train", back_populates="route_stops")
    station = relationship("Station")


class TrainRoute(Base):
    __tablename__ = "train_routes"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), ForeignKey("trains.train_number"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    direction = Column(String(10), default="UP")
    source = Column(String(100), default="RAILRADAR")
    last_verified_at = Column(DateTime, default=datetime.utcnow)

    train = relationship("Train", back_populates="routes")
    section = relationship("RailwaySection")


class TrainMovement(Base):
    __tablename__ = "train_movements"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), ForeignKey("trains.train_number"), unique=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0.0)
    direction = Column(String(10), default="UP")
    current_station_id = Column(Integer, ForeignKey("stations.id"), nullable=True)
    next_station_id = Column(Integer, ForeignKey("stations.id"), nullable=True)
    current_section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=True)
    delay_minutes = Column(Integer, default=0)
    status = Column(String(30), default="RUNNING")
    current_station_code = Column(String(10), nullable=True)
    next_halt = Column(String(100), nullable=True)
    previous_halt = Column(String(100), nullable=True)
    provenance_status = Column(String(20), default="LIVE")
    is_live = Column(Boolean, default=True)
    mapping_confidence = Column(Float, default=0.95)
    source = Column(String(30), default="live")  # live, timetable, estimated
    last_updated = Column(DateTime, default=datetime.utcnow)

    train = relationship("Train")
    current_station = relationship("Station", foreign_keys=[current_station_id])
    next_station = relationship("Station", foreign_keys=[next_station_id])
    current_section = relationship("RailwaySection", foreign_keys=[current_section_id])


class TrainSectionOccupancy(Base):
    __tablename__ = "train_section_occupancies"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), ForeignKey("trains.train_number"), nullable=False)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=False)
    estimated_entry_min = Column(Integer, nullable=False)
    estimated_exit_min = Column(Integer, nullable=False)
    confidence = Column(Float, default=0.95)
    source = Column(String(30), default="calculated")
    calculated_at = Column(DateTime, default=datetime.utcnow)

    train = relationship("Train")
    section = relationship("RailwaySection")


class TrainPositionSnapshot(Base):
    __tablename__ = "train_position_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), ForeignKey("trains.train_number"), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0.0)
    bearing_degrees = Column(Float, default=0.0)
    delay_minutes = Column(Integer, default=0)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=True)
    source = Column(String(50), default="LIVE RADAR")
    confidence = Column(Float, default=0.95)

    train = relationship("Train")
    section = relationship("RailwaySection")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_code = Column(String(50), unique=True, index=True, nullable=False)
    asset_name = Column(String(150), nullable=False)
    asset_type = Column(String(50), nullable=False)  # TRACK_POINT, OHE_CANTILEVER, AXLE_COUNTER, TRACK_CIRCUIT, RAIL_JOINT, TRANSFORMER
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=False)
    location_km = Column(Float, nullable=False)
    condition_score = Column(Float, default=70.0)  # 0 to 100 (100 = brand new, <40 = critical)
    install_date = Column(DateTime, nullable=True)
    last_maintained = Column(DateTime, nullable=True)

    department = relationship("Department")
    section = relationship("RailwaySection", back_populates="assets")
    maintenance_jobs = relationship("MaintenanceJob", back_populates="asset")


class MaintenanceJob(Base):
    __tablename__ = "maintenance_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_code = Column(String(30), unique=True, index=True, nullable=False)
    source_system = Column(String(50), default="INTERNAL", nullable=True)  # INTERNAL, TMS, SMMS, TDLS
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=True)
    location_km = Column(Float, nullable=True, default=0.0)
    work_type = Column(String(100), nullable=False)  # TRACK_TAMPING, POINT_OVERHAUL, OHE_INSPECTION, RAIL_REPLACEMENT
    description = Column(Text, nullable=False)

    # Station-to-Station Corridor Scope
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=True, index=True)
    start_station_code = Column(String(10), nullable=True, index=True)
    start_station_name = Column(String(100), nullable=True)
    end_station_code = Column(String(10), nullable=True, index=True)
    end_station_name = Column(String(100), nullable=True)
    work_title = Column(String(150), nullable=True)
    requested_date = Column(DateTime, nullable=True)
    requested_start_time = Column(String(10), nullable=True)
    requested_end_time = Column(String(10), nullable=True)
    safety_impact_info = Column(Text, nullable=True)
    additional_remarks = Column(Text, nullable=True)
    conflicting_trains_count = Column(Integer, default=0)

    # User Input
    user_priority = Column(String(10), default="MEDIUM")  # LOW, MEDIUM, HIGH
    due_date = Column(DateTime, nullable=True)
    overdue_days = Column(Integer, default=0)

    # System-Calculated Multi-criteria Factors & Ratings
    calculated_criticality = Column(Float, default=50.0)
    calculated_safety_impact = Column(Float, default=50.0)
    calculated_urgency = Column(Float, default=50.0)
    overdue_risk_score = Column(Float, default=0.0)
    criticality_label = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    safety_impact_label = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH
    urgency_label = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL

    # Legacy / compatibility factor columns (mapped to calculated)
    criticality = Column(Float, default=50.0)
    safety_impact = Column(Float, default=50.0)
    operational_impact = Column(Float, default=50.0)
    urgency = Column(Float, default=50.0)

    # Derived composite score, safety tier & explainability
    priority_score = Column(Float, default=50.0)
    safety_tier = Column(String(20), default="Tier 4")
    priority_explanation = Column(JSON, nullable=True)

    # Planner Override
    planner_override_score = Column(Float, nullable=True)
    planner_override_reason = Column(Text, nullable=True)
    planner_override_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    planner_override_at = Column(DateTime, nullable=True)

    # Timing & Status
    estimated_duration_min = Column(Integer, nullable=False)  # in minutes
    preferred_start_min = Column(Integer, nullable=True)
    preferred_end_min = Column(Integer, nullable=True)
    status = Column(String(30), default="SUBMITTED")  # DRAFT, SUBMITTED, UNDER_REVIEW, OPTIMIZING, RECOMMENDED, APPROVED, MODIFICATION_REQUESTED, REJECTED, ACCEPTED, IN_PROGRESS, COMPLETED, CANCELLED

    is_emergency = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    locked_start_min = Column(Integer, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    planner_remarks = Column(Text, nullable=True)
    department_remarks = Column(Text, nullable=True)
    state_history_json = Column(JSON, nullable=True)

    # Execution Tracking
    execution_status = Column(String(30), default="NOT_STARTED")  # NOT_STARTED, READY, IN_PROGRESS, COMPLETED, PARTIALLY_COMPLETED, CANCELLED
    actual_start_min = Column(Integer, nullable=True)
    actual_end_min = Column(Integer, nullable=True)
    completion_pct = Column(Float, default=0.0)
    delay_minutes = Column(Integer, default=0)
    variance_minutes = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    department = relationship("Department", back_populates="jobs")
    corridor = relationship("Corridor", foreign_keys=[corridor_id])
    asset = relationship("Asset", back_populates="maintenance_jobs")
    section = relationship("RailwaySection", back_populates="maintenance_jobs")
    required_resources = relationship("MaintenanceJobResource", back_populates="job")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    planner_override_by = relationship("User", foreign_keys=[planner_override_by_id])

    # Coordinated Multi-Department Block Planning (SIH26027)
    coordinated_plan_id = Column(Integer, ForeignKey("coordinated_block_plans.id"), nullable=True, index=True)
    coordination_status = Column(String(30), default="NOT_CHECKED")  # NOT_CHECKED, COMPATIBLE, PARTIALLY_COMPATIBLE, INCOMPATIBLE, ALREADY_COORDINATED
    coordinated_plan = relationship("CoordinatedBlockPlan", back_populates="jobs", foreign_keys=[coordinated_plan_id])


class MaintenanceDependency(Base):
    __tablename__ = "maintenance_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    predecessor_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    successor_job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    dependency_type = Column(String(30), default="FINISH_TO_START")
    min_gap_min = Column(Integer, default=0)

    predecessor = relationship("MaintenanceJob", foreign_keys=[predecessor_job_id])
    successor = relationship("MaintenanceJob", foreign_keys=[successor_job_id])


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    resource_code = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    resource_type = Column(String(50), nullable=False)  # MACHINE, CREW, TOWER_WAGON, TAMPING_MACHINE, SPENO
    total_quantity = Column(Integer, default=1)

    department = relationship("Department", back_populates="resources")


class MaintenanceJobResource(Base):
    __tablename__ = "maintenance_job_resources"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    quantity_required = Column(Integer, default=1)

    job = relationship("MaintenanceJob", back_populates="required_resources")
    resource = relationship("Resource")


class BlockDemand(Base):
    __tablename__ = "block_demands"

    id = Column(Integer, primary_key=True, index=True)
    demand_code = Column(String(30), unique=True, index=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=False)
    job_ids_json = Column(JSON, nullable=False)
    requested_duration_min = Column(Integer, nullable=False)
    status = Column(String(30), default="SUBMITTED")  # DRAFT, SUBMITTED, APPROVED, REJECTED
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    submission_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    department = relationship("Department")
    section = relationship("RailwaySection")
    submitted_by = relationship("User")


class BlockWindow(Base):
    __tablename__ = "block_windows"

    id = Column(Integer, primary_key=True, index=True)
    window_code = Column(String(40), unique=True, index=True, nullable=False)  # WIN_SEC01_01
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=False)
    start_min = Column(Integer, nullable=False)
    end_min = Column(Integer, nullable=False)
    usable_duration_min = Column(Integer, nullable=False)
    train_before_no = Column(String(20), nullable=True)
    train_after_no = Column(String(20), nullable=True)
    constraints_applied_json = Column(JSON, nullable=True)
    feasibility = Column(String(20), default="FEASIBLE")  # FEASIBLE, RESTRICTED, INFEASIBLE
    source = Column(String(30), default="SWEEP_LINE_DERIVED")

    section = relationship("RailwaySection")
    corridor = relationship("Corridor")


class BlockPlan(Base):
    __tablename__ = "block_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(40), unique=True, index=True, nullable=False)
    plan_name = Column(String(150), nullable=False)
    strategy = Column(String(30), default="PLAN_A")  # PLAN_A, PLAN_B, PLAN_C, BASELINE
    solver_status = Column(String(30), default="OPTIMAL")  # OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN
    objective_score = Column(Float, default=0.0)

    # Computed KPIs
    critical_jobs_completed = Column(Integer, default=0)
    total_critical_jobs = Column(Integer, default=0)
    total_jobs_completed = Column(Integer, default=0)
    total_jobs_demanded = Column(Integer, default=0)
    total_blocks_count = Column(Integer, default=0)
    block_utilization_pct = Column(Float, default=0.0)
    train_impact_score = Column(Float, default=0.0)
    asset_availability_proxy = Column(Float, default=0.0)
    computation_time_ms = Column(Float, default=0.0)

    validation_status = Column(String(20), default="VALID")  # VALID, INVALID, UNCHECKED
    validation_errors_json = Column(JSON, nullable=True)

    approval_status = Column(String(30), default="DRAFT")  # DRAFT, PROPOSED, APPROVED, REJECTED
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan_jobs = relationship("PlanJob", back_populates="plan", cascade="all, delete-orphan")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class CoordinatedBlockPlan(Base):
    __tablename__ = "coordinated_block_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(40), unique=True, index=True, nullable=False)  # CBP-YYYYMMDD-XXX
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=True)
    corridor_name = Column(String(150), nullable=True)
    section_id = Column(Integer, ForeignKey("railway_sections.id"), nullable=True)
    section_name = Column(String(150), nullable=True)
    plan_date = Column(DateTime, nullable=True)
    start_min = Column(Integer, nullable=False)  # e.g. 645 for 10:45
    end_min = Column(Integer, nullable=False)    # e.g. 735 for 12:15
    duration_min = Column(Integer, nullable=False)  # e.g. 90
    status = Column(String(30), default="PROPOSED")  # PROPOSED, APPROVED, REJECTED, MODIFIED, ACCEPTED, IN_PROGRESS, COMPLETED
    strategy = Column(String(30), default="PLAN_A")  # PLAN_A, PLAN_B, PLAN_C
    objective_score = Column(Float, default=96.0)
    conflicts_count = Column(Integer, default=0)
    blocks_saved = Column(Integer, default=0)  # e.g. 2
    possession_time_saved_min = Column(Integer, default=0)  # e.g. 135
    is_parallel = Column(Boolean, default=True)
    departments_json = Column(JSON, nullable=True)  # List of department names
    work_breakdown_json = Column(JSON, nullable=True)  # List of jobs with work type, duration, timing
    alternatives_json = Column(JSON, nullable=True)  # Plan A, Plan B, Plan C comparison objects
    reasoning_json = Column(JSON, nullable=True)  # List of reasoning bullets
    planner_reason = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    modification_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    corridor = relationship("Corridor")
    section = relationship("RailwaySection")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    jobs = relationship("MaintenanceJob", back_populates="coordinated_plan", foreign_keys="MaintenanceJob.coordinated_plan_id")


class PlanJob(Base):
    __tablename__ = "plan_jobs"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("block_plans.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=False)
    window_id = Column(Integer, ForeignKey("block_windows.id"), nullable=True)
    scheduled_start_min = Column(Integer, nullable=True)
    scheduled_end_min = Column(Integer, nullable=True)
    scheduled_duration_min = Column(Integer, nullable=True)
    block_code = Column(String(40), nullable=True)  # Coordinated block group identifier, e.g. BLK_SEC01_W1
    is_scheduled = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    assigned_resources_json = Column(JSON, nullable=True)

    execution_status = Column(String(30), default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, CANCELLED, OVERRUN
    actual_start_min = Column(Integer, nullable=True)
    actual_end_min = Column(Integer, nullable=True)

    plan = relationship("BlockPlan", back_populates="plan_jobs")
    job = relationship("MaintenanceJob")
    window = relationship("BlockWindow")


class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id = Column(Integer, primary_key=True, index=True)
    original_plan_id = Column(Integer, ForeignKey("block_plans.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    trigger_event = Column(String(100), nullable=False)  # TRAIN_DELAY, EMERGENCY_JOB, MAINTENANCE_OVERRUN, MANUAL_REPLAN
    changes_summary_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    original_plan = relationship("BlockPlan")
    created_by = relationship("User")


class WhatIfScenario(Base):
    __tablename__ = "what_if_scenarios"

    id = Column(Integer, primary_key=True, index=True)
    scenario_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    base_plan_id = Column(Integer, ForeignKey("block_plans.id"), nullable=False)
    perturbations_json = Column(JSON, nullable=False)  # {train_delay_min: 30, duration_multiplier: 1.2, emergency_job: true}
    result_metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    base_plan = relationship("BlockPlan")
    created_by = relationship("User")


class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("maintenance_jobs.id"), nullable=True)
    plan_job_id = Column(Integer, ForeignKey("plan_jobs.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(30), nullable=False)  # READY, IN_PROGRESS, COMPLETED, PARTIALLY_COMPLETED, CANCELLED
    planned_start_min = Column(Integer, nullable=True)
    planned_end_min = Column(Integer, nullable=True)
    actual_start_min = Column(Integer, nullable=True)
    actual_end_min = Column(Integer, nullable=True)
    delay_min = Column(Integer, default=0)
    variance_min = Column(Integer, default=0)
    completion_pct = Column(Float, default=0.0)
    responsible_department = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    job = relationship("MaintenanceJob")
    plan_job = relationship("PlanJob")
    updated_by = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="INFO")  # PLAN_APPROVED, CHANGE_REQUESTED, PLAN_REVISED, DISTURBANCE_DETECTED, EXECUTION_ALERT
    target_entity = Column(String(50), nullable=True)
    target_id = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    department = relationship("Department")


class PlannerAction(Base):
    __tablename__ = "planner_actions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # LOCK_JOB, UNLOCK_JOB, MANUAL_MOVE, APPROVE_PLAN, REJECT_PLAN, TRIGGER_REPLAN
    target_entity = Column(String(50), nullable=False)
    target_id = Column(String(50), nullable=False)
    old_value_json = Column(JSON, nullable=True)
    new_value_json = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False)
    value = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
