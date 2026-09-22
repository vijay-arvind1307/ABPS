from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    department_code: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str
    department: Optional[str] = None  # Validated against backend department master


# Department & Master Schemas
class DepartmentBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    discipline: Optional[str] = None
    asset_domain: Optional[str] = None
    is_active: bool = True


class DepartmentResponse(DepartmentBase):
    id: int

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    role: str
    department_id: Optional[int] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    created_at: datetime
    department: Optional[DepartmentResponse] = None

    class Config:
        from_attributes = True



class StationResolveResponse(BaseModel):
    code: str
    name: str
    valid: bool = True
    division: Optional[str] = None
    zone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    message: Optional[str] = None


class RouteValidateResponse(BaseModel):
    valid: bool
    start_station_code: str
    start_station_name: Optional[str] = None
    end_station_code: str
    end_station_name: Optional[str] = None
    corridor_id: Optional[int] = None
    corridor_name: Optional[str] = None
    distance_km: Optional[float] = None
    sections: List[Dict[str, Any]] = []
    message: Optional[str] = None


class StationBase(BaseModel):
    code: str
    name: str
    division: str
    zone: str
    latitude: float
    longitude: float
    total_platforms: int = 4


class StationResponse(StationBase):
    id: int

    class Config:
        from_attributes = True


class RailwayStationItem(BaseModel):
    id: Optional[int] = None
    code: str
    station_code: Optional[str] = None
    name: str
    station_name: Optional[str] = None
    normalized_name: Optional[str] = None
    state: str
    district: Optional[str] = None
    division: str
    category: str
    station_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class RailwayStationDetailResponse(BaseModel):
    success: bool
    station: Optional[RailwayStationItem] = None
    message: Optional[str] = None
    query: Optional[str] = None


class CorridorBase(BaseModel):
    corridor_id: str
    prototype_code: Optional[str] = None
    name: str
    division: str
    zone: str
    start_station_code: Optional[str] = None
    end_station_code: Optional[str] = None
    total_distance_km: Optional[float] = 0.0
    status: Optional[str] = "ACTIVE"
    description: Optional[str] = None


class CorridorResponse(CorridorBase):
    id: int
    sections_count: Optional[int] = 0
    stations_count: Optional[int] = 0

    class Config:
        from_attributes = True


class SectionBase(BaseModel):
    section_id: str
    name: str
    corridor_id: int
    from_station_id: int
    to_station_id: int
    length_km: float
    track_type: str = "DOUBLE_UP"
    direction: str = "UP"
    max_speed_kmh: float = 130.0
    is_electrified: bool = True
    geometry_geojson: Optional[Any] = None


class SectionResponse(SectionBase):
    id: int
    from_station: Optional[StationResponse] = None
    to_station: Optional[StationResponse] = None

    class Config:
        from_attributes = True


# Train & Movement Schemas
class TrainRouteStopBase(BaseModel):
    train_number: str
    station_id: int
    sequence: int
    arrival_min: int
    departure_min: int
    halt_min: int = 2
    distance_km: float = 0.0
    day_offset: int = 0


class TrainRouteStopResponse(TrainRouteStopBase):
    id: int
    station: Optional[StationResponse] = None

    class Config:
        from_attributes = True


class TrainBase(BaseModel):
    train_number: str
    train_name: str
    train_type: str
    priority_level: int = 2
    source_station_id: int
    destination_station_id: int
    running_days: str = "DAILY"
    active: bool = True


class TrainResponse(TrainBase):
    id: int
    source_station: Optional[StationResponse] = None
    destination_station: Optional[StationResponse] = None
    route_stops: List[TrainRouteStopResponse] = []

    class Config:
        from_attributes = True


class TrainMovementBase(BaseModel):
    train_number: str
    latitude: float
    longitude: float
    speed_kmh: float = 0.0
    direction: str = "UP"
    current_station_id: Optional[int] = None
    next_station_id: Optional[int] = None
    current_section_id: Optional[int] = None
    delay_minutes: int = 0
    source: str = "mock"


class TrainMovementResponse(TrainMovementBase):
    id: int
    timestamp: datetime
    last_updated: datetime
    train: Optional[TrainResponse] = None
    current_station: Optional[StationResponse] = None
    next_station: Optional[StationResponse] = None
    current_section: Optional[SectionResponse] = None

    class Config:
        from_attributes = True


class TrainSectionOccupancyResponse(BaseModel):
    id: int
    train_number: str
    section_id: int
    estimated_entry_min: int
    estimated_exit_min: int
    confidence: float
    source: str
    calculated_at: datetime
    train: Optional[TrainResponse] = None
    section: Optional[SectionResponse] = None

    class Config:
        from_attributes = True


# Asset & Resource Schemas
class AssetResponse(BaseModel):
    id: int
    asset_code: str
    asset_name: str
    asset_type: str
    department_id: int
    section_id: int
    location_km: float
    condition_score: float
    install_date: Optional[datetime] = None
    last_maintained: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResourceResponse(BaseModel):
    id: int
    resource_code: str
    name: str
    department_id: int
    resource_type: str
    total_quantity: int

    class Config:
        from_attributes = True


# Maintenance Job Schemas
class MaintenanceJobBase(BaseModel):
    job_code: str
    department_id: Optional[int] = None
    corridor_id: Optional[int] = None
    asset_id: Optional[int] = None
    section_id: Optional[int] = None
    location_km: Optional[float] = 0.0
    work_title: Optional[str] = None
    work_type: str
    description: str

    # Station-to-Station corridor scope
    start_station_code: Optional[str] = None
    start_station_name: Optional[str] = None
    end_station_code: Optional[str] = None
    end_station_name: Optional[str] = None

    # Timing & Request
    requested_date: Optional[datetime] = None
    requested_start_time: Optional[str] = None
    requested_end_time: Optional[str] = None
    safety_impact_info: Optional[str] = None
    additional_remarks: Optional[str] = None
    conflicting_trains_count: Optional[int] = 0

    # User Input
    user_priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    due_date: Optional[datetime] = None
    overdue_days: int = 0
    estimated_duration_min: int
    preferred_start_min: Optional[int] = None
    preferred_end_min: Optional[int] = None
    status: str = "SUBMITTED"
    is_emergency: bool = False
    coordinated_plan_id: Optional[int] = None
    coordination_status: Optional[str] = "NOT_CHECKED"


class MaintenanceJobCreate(BaseModel):
    job_code: Optional[str] = None
    work_title: Optional[str] = None
    work_type: str
    description: Optional[str] = "Maintenance request"
    corridor_id: Optional[int] = None
    start_station_code: str
    end_station_code: str
    priority: Optional[str] = "MEDIUM"  # LOW, MEDIUM, HIGH
    user_priority: Optional[str] = None  # Alias for priority
    due_date: Optional[datetime] = None
    requested_date: Optional[datetime] = None
    requested_start_time: Optional[str] = None
    requested_end_time: Optional[str] = None
    estimated_duration_min: int = 60
    preferred_start_min: Optional[int] = None
    preferred_end_min: Optional[int] = None
    department_id: Optional[int] = None
    asset_id: Optional[int] = None
    section_id: Optional[int] = None
    location_km: Optional[float] = 0.0
    is_emergency: bool = False
    safety_impact_info: Optional[str] = None
    additional_remarks: Optional[str] = None
    status: str = "SUBMITTED"
    required_resource_ids: List[int] = []


class MaintenanceJobUpdate(BaseModel):
    work_title: Optional[str] = None
    work_type: Optional[str] = None
    description: Optional[str] = None
    corridor_id: Optional[int] = None
    start_station_code: Optional[str] = None
    end_station_code: Optional[str] = None
    priority: Optional[str] = None
    user_priority: Optional[str] = None
    due_date: Optional[datetime] = None
    requested_date: Optional[datetime] = None
    requested_start_time: Optional[str] = None
    requested_end_time: Optional[str] = None
    estimated_duration_min: Optional[int] = None
    preferred_start_min: Optional[int] = None
    preferred_end_min: Optional[int] = None
    status: Optional[str] = None
    is_emergency: Optional[bool] = None
    is_locked: Optional[bool] = None
    locked_start_min: Optional[int] = None
    safety_impact_info: Optional[str] = None
    additional_remarks: Optional[str] = None


class PlannerOverrideRequest(BaseModel):
    override_score: float
    reason: str


class MaintenanceJobResponse(MaintenanceJobBase):
    id: int
    calculated_criticality: float = 50.0
    calculated_safety_impact: float = 50.0
    calculated_urgency: float = 50.0
    overdue_risk_score: float = 0.0
    criticality_label: str = "MEDIUM"
    safety_impact_label: str = "MEDIUM"
    urgency_label: str = "MEDIUM"
    priority_score: float = 50.0
    safety_tier: str = "Tier 4"
    priority_explanation: Optional[Dict[str, Any]] = None
    planner_override_score: Optional[float] = None
    planner_override_reason: Optional[str] = None
    planner_override_at: Optional[datetime] = None
    is_locked: bool = False
    locked_start_min: Optional[int] = None
    created_by_id: Optional[int] = None
    approved_by_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    planner_remarks: Optional[str] = None
    department_remarks: Optional[str] = None
    state_history_json: Optional[Any] = None
    execution_status: Optional[str] = "NOT_STARTED"
    actual_start_min: Optional[int] = None
    actual_end_min: Optional[int] = None
    completion_pct: Optional[float] = 0.0
    delay_minutes: Optional[int] = 0
    variance_minutes: Optional[int] = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    department: Optional[DepartmentResponse] = None
    corridor: Optional[CorridorResponse] = None
    section: Optional[SectionResponse] = None
    asset: Optional[AssetResponse] = None

    class Config:
        from_attributes = True


# Block Demand Schemas
class BlockDemandCreate(BaseModel):
    department_id: int
    section_id: int
    job_ids: List[int]
    requested_duration_min: int
    submission_notes: Optional[str] = None


class BlockDemandResponse(BaseModel):
    id: int
    demand_code: str
    department_id: int
    section_id: int
    job_ids_json: List[int]
    requested_duration_min: int
    status: str
    submitted_by_id: int
    submission_notes: Optional[str] = None
    created_at: datetime
    department: Optional[DepartmentResponse] = None
    section: Optional[SectionResponse] = None

    class Config:
        from_attributes = True


# Maintenance Window Schemas
class BlockWindowResponse(BaseModel):
    id: int
    window_code: str
    section_id: int
    corridor_id: int
    start_min: int
    end_min: int
    usable_duration_min: int
    train_before_no: Optional[str] = None
    train_after_no: Optional[str] = None
    constraints_applied_json: Optional[Any] = None
    feasibility: str
    source: str
    section: Optional[SectionResponse] = None

    class Config:
        from_attributes = True


# Planning, Optimization & Solution Schemas
class OptimizeRequest(BaseModel):
    strategy: str = "PLAN_A"  # PLAN_A, PLAN_B, PLAN_C
    corridor_id: Optional[int] = None
    section_ids: Optional[List[int]] = None
    planning_horizon_hours: int = 24
    time_limit_seconds: int = 10
    enforce_locks: bool = True
    weights: Optional[Dict[str, float]] = None


class LockJobRequest(BaseModel):
    job_id: int
    locked_start_min: Optional[int] = None
    is_locked: bool = True
    reason: Optional[str] = "Planner manual lock"


class PlanJobResponse(BaseModel):
    id: int
    plan_id: int
    job_id: int
    window_id: Optional[int] = None
    scheduled_start_min: Optional[int] = None
    scheduled_end_min: Optional[int] = None
    scheduled_duration_min: Optional[int] = None
    block_code: Optional[str] = None
    is_scheduled: bool
    is_locked: bool
    execution_status: str
    actual_start_min: Optional[int] = None
    actual_end_min: Optional[int] = None
    job: Optional[MaintenanceJobResponse] = None
    window: Optional[BlockWindowResponse] = None

    class Config:
        from_attributes = True


class BlockPlanResponse(BaseModel):
    id: int
    plan_code: str
    plan_name: str
    strategy: str
    solver_status: str
    objective_score: float
    critical_jobs_completed: int
    total_critical_jobs: int
    total_jobs_completed: int
    total_jobs_demanded: int
    total_blocks_count: int
    block_utilization_pct: float
    train_impact_score: float
    asset_availability_proxy: float
    computation_time_ms: float
    validation_status: str
    validation_errors_json: Optional[List[str]] = None
    approval_status: str
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    version: int
    is_active: bool
    created_at: datetime
    plan_jobs: List[PlanJobResponse] = []

    class Config:
        from_attributes = True


class ValidationResult(BaseModel):
    is_valid: bool
    status: str
    errors: List[str] = []
    warnings: List[str] = []
    checked_rules_count: int = 15


class ApprovalRequest(BaseModel):
    action: str  # APPROVE, REJECT
    reason: Optional[str] = None


# Dynamic Replanning & Simulation Schemas
class DelaySimulationRequest(BaseModel):
    train_number: str
    additional_delay_min: int = 30
    reason: Optional[str] = "Simulated track congestion delay"


class DynamicReplanRequest(BaseModel):
    base_plan_id: int
    trigger_event: str = "TRAIN_DELAY"
    affected_train_number: Optional[str] = None
    affected_section_id: Optional[int] = None


class WhatIfRequest(BaseModel):
    base_plan_id: int
    scenario_name: str
    description: Optional[str] = None
    train_delay_train_no: Optional[str] = None
    train_delay_min: int = 0
    duration_multiplier: float = 1.0  # e.g. 1.2 for +20% duration
    emergency_job_id: Optional[int] = None
    corridor_reduction_min: int = 0


class KPIComparisonResponse(BaseModel):
    baseline: Dict[str, Any]
    plan_a: Dict[str, Any]
    plan_b: Dict[str, Any]
    plan_c: Dict[str, Any]
    what_if: Optional[Dict[str, Any]] = None


class JobExplanationResponse(BaseModel):
    job_id: int
    job_code: str
    is_scheduled: bool
    scheduled_start_min: Optional[int] = None
    scheduled_end_min: Optional[int] = None
    block_code: Optional[str] = None
    selection_reasons: List[str] = []
    rejection_reasons: List[str] = []
    factor_contributions: Dict[str, float] = {}
    compatibility_synergies: List[str] = []
    constraints_satisfied: List[str] = []


class PlannerActionResponse(BaseModel):
    id: int
    user_id: int
    action_type: str
    target_entity: str
    target_id: str
    old_value_json: Optional[Any] = None
    new_value_json: Optional[Any] = None
    reason: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details_json: Optional[Any] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# Time-Distance Chart & Provenance Schemas
class DataProvenance(BaseModel):
    source: str  # LIVE RADAR, SIMULATED, CACHED, TIMETABLE, ERROR
    provider: str
    last_updated: str
    clock_display: str
    is_live: bool = False


class TimeDistanceStation(BaseModel):
    station_code: str
    station_name: str
    distance_km: float
    y_pct: float
    sequence: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    division: Optional[str] = None
    zone: Optional[str] = None


class TimeDistanceSection(BaseModel):
    id: int
    section_id: str
    name: str
    from_station_code: str
    to_station_code: str
    start_km: float
    end_km: float
    y_top_pct: float
    y_bottom_pct: float
    length_km: float
    geometry_geojson: Optional[Any] = None


class TrajectoryPoint(BaseModel):
    min: int
    time: str
    station_code: str
    station_name: str
    distance_km: float
    y: float
    event_type: str = "PASSING"  # ARRIVAL, DEPARTURE, PASSING


class TimeDistanceTrain(BaseModel):
    train_number: str
    train_name: str
    train_type: str
    status: str
    speed_kmh: float
    direction: str
    current_section_id: Optional[int] = None
    current_section_code: Optional[str] = None
    current_section_name: Optional[str] = None
    delay_minutes: int = 0
    source: str
    last_updated: str
    color: str = "#0284C7"
    is_dashed: bool = False
    width: float = 2.5
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    previous_halt: Optional[str] = None
    next_halt: Optional[str] = None
    mapping_confidence: Optional[float] = None
    section_code: Optional[str] = None
    trajectory: List[TrajectoryPoint] = []


class TimeDistanceBlock(BaseModel):
    job_id: int
    job_code: str
    department_code: str
    department_name: str
    work_type: str
    description: str
    section_id: int
    section_code: str
    scheduled_start_min: int
    scheduled_end_min: int
    scheduled_duration_min: int
    block_code: str
    is_locked: bool
    priority_score: float
    safety_tier: str
    y_top_pct: float
    y_bottom_pct: float


class TimeDistanceWindow(BaseModel):
    id: int
    window_code: str
    section_id: int
    corridor_id: int
    start_min: int
    end_min: int
    usable_duration_min: int
    train_before_no: Optional[str] = None
    train_after_no: Optional[str] = None
    y_top_pct: float
    y_bottom_pct: float


class TimeDistanceResponse(BaseModel):
    corridor: Optional[Dict[str, Any]] = None
    time_range: Dict[str, Any]
    stations: List[TimeDistanceStation]
    sections: List[TimeDistanceSection]
    trains: List[TimeDistanceTrain]
    occupancy_intervals: List[Dict[str, Any]]
    maintenance_blocks: List[TimeDistanceBlock]
    feasible_windows: List[TimeDistanceWindow]
    provenance: DataProvenance


# Execution Management Schemas
class ExecutionRecordResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    plan_job_id: Optional[int] = None
    status: str
    planned_start_min: Optional[int] = None
    planned_end_min: Optional[int] = None
    actual_start_min: Optional[int] = None
    actual_end_min: Optional[int] = None
    delay_min: int = 0
    variance_min: int = 0
    completion_pct: float = 0.0
    responsible_department: Optional[str] = None
    remarks: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime
    updated_by: Optional[UserResponse] = None
    job: Optional[MaintenanceJobResponse] = None

    class Config:
        from_attributes = True


class ExecutionStartRequest(BaseModel):
    job_id: int
    actual_start_min: Optional[int] = None
    remarks: Optional[str] = "Field maintenance crew commenced work"


class ExecutionProgressRequest(BaseModel):
    job_id: int
    completion_pct: float
    delay_min: Optional[int] = 0
    remarks: Optional[str] = None


class ExecutionCompleteRequest(BaseModel):
    job_id: int
    actual_end_min: Optional[int] = None
    completion_pct: float = 100.0
    status: Optional[str] = "COMPLETED"  # COMPLETED or PARTIALLY_COMPLETED
    remarks: Optional[str] = "Maintenance block successfully cleared and track restored"


class ExecutionCancelRequest(BaseModel):
    job_id: int
    reason: str


# Notification Schemas
class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    department_id: Optional[int] = None
    title: str
    message: str
    notification_type: str
    target_entity: Optional[str] = None
    target_id: Optional[str] = None
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# Department Action Request
class DepartmentPlanActionRequest(BaseModel):
    action: str  # ACCEPT, REQUEST_CHANGE, DECLINE
    remarks: Optional[str] = None


# -------------------------------------------------------------
# Coordinated Multi-Request Block Planning Schemas (SIH26027)
# -------------------------------------------------------------
class CoordinationCheckRequest(BaseModel):
    job_ids: List[int]


class CoordinationOptimizeRequest(BaseModel):
    job_ids: List[int]
    strategy: Optional[str] = "PLAN_A"
    planner_notes: Optional[str] = None


class CoordinatedPlanDecisionRequest(BaseModel):
    action: Optional[str] = "APPROVE"  # APPROVE, REJECT, MODIFY
    reason: Optional[str] = None
    recommended_start_min: Optional[int] = None
    recommended_end_min: Optional[int] = None
    recommended_section_id: Optional[int] = None
    version: Optional[int] = None


class CoordinatedPlanWhatIfRequest(BaseModel):
    scenario_type: str  # TRAIN_DELAY, EXTEND_DURATION, ADD_JOB, REMOVE_JOB
    perturbation_value: Optional[Any] = None
    remarks: Optional[str] = None


class CoordinatedBlockPlanResponse(BaseModel):
    id: int
    plan_code: str
    corridor_id: Optional[int] = None
    corridor_name: Optional[str] = None
    section_id: Optional[int] = None
    section_name: Optional[str] = None
    plan_date: Optional[datetime] = None
    start_min: int
    end_min: int
    duration_min: int
    status: str
    strategy: str
    objective_score: float
    conflicts_count: int
    blocks_saved: int
    possession_time_saved_min: int
    is_parallel: bool = True
    departments_json: Optional[List[str]] = []
    work_breakdown_json: Optional[List[Dict[str, Any]]] = []
    alternatives_json: Optional[List[Dict[str, Any]]] = []
    reasoning_json: Optional[List[str]] = []
    planner_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    modification_reason: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    jobs: Optional[List[MaintenanceJobResponse]] = []

    class Config:
        from_attributes = True


