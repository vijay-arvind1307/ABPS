from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import MaintenanceJob, User, AuditLog
from app.schemas.schemas import (
    MaintenanceJobCreate, MaintenanceJobUpdate, MaintenanceJobResponse, PlannerOverrideRequest
)
from app.services.maintenance_service import MaintenanceService
from app.algorithms.explain import PlanExplainabilityEngine
from app.routers.auth import get_current_user

router = APIRouter(prefix="/maintenance", tags=["Maintenance Demands & Requests"])


# --- Jobs & Requests GET endpoints ---
@router.get("/jobs", response_model=List[MaintenanceJobResponse])
@router.get("/requests", response_model=List[MaintenanceJobResponse])
def get_jobs(
    department_id: Optional[int] = None,
    section_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Department user automatically filtered to their own department if not specified
    if current_user.role == "department_user" and current_user.department_id:
        department_id = current_user.department_id

    return MaintenanceService.get_jobs(db, department_id=department_id, section_id=section_id, status=status)


# --- Jobs & Requests POST creation ---
@router.post("/jobs", response_model=MaintenanceJobResponse)
@router.post("/requests", response_model=MaintenanceJobResponse)
def create_job(
    job_in: MaintenanceJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = MaintenanceService.create_job(db, job_in, current_user)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="CREATE_MAINTENANCE_REQUEST",
        entity_type="MAINTENANCE_JOB",
        entity_id=str(job.id),
        details_json={
            "job_code": job.job_code,
            "work_type": job.work_type,
            "start": job.start_station_code,
            "end": job.end_station_code,
            "user_priority": job.user_priority,
            "priority_score": job.priority_score,
            "status": job.status
        }
    )
    db.add(audit)
    db.commit()

    return job


# --- Jobs & Requests GET by ID ---
@router.get("/jobs/{id}", response_model=MaintenanceJobResponse)
@router.get("/requests/{id}", response_model=MaintenanceJobResponse)
def get_job(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return MaintenanceService.get_job_by_id(db, id)


# --- Explain Priority Score for Request ---
@router.get("/jobs/{id}/explanation")
@router.get("/requests/{id}/explanation")
def get_request_explanation(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns transparent score breakdown explaining why this maintenance request
    received its calculated Criticality, Safety Impact, Urgency, and composite Priority Score.
    """
    job = MaintenanceService.get_job_by_id(db, id)
    job_dict = {
        "id": job.id,
        "job_code": job.job_code,
        "work_type": job.work_type,
        "department_code": job.department.code if job.department else "ENGG",
        "user_priority": job.user_priority,
        "due_date": job.due_date,
        "is_emergency": job.is_emergency,
        "priority_score": job.priority_score,
        "priority_explanation": job.priority_explanation
    }
    return PlanExplainabilityEngine.explain_job_priority(job_dict)


# --- Planner Override Priority Score (Part 24) ---
@router.post("/jobs/{id}/override", response_model=MaintenanceJobResponse)
@router.post("/requests/{id}/override", response_model=MaintenanceJobResponse)
def override_job_priority(
    id: int,
    override_req: PlannerOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Authorized Chief Controller / Railway Planner override of calculated priority score with mandatory reason.
    """
    return MaintenanceService.override_priority(
        db=db,
        job_id=id,
        override_score=override_req.override_score,
        reason=override_req.reason,
        user=current_user
    )


# --- Jobs & Requests PUT update ---
@router.put("/jobs/{id}", response_model=MaintenanceJobResponse)
@router.put("/requests/{id}", response_model=MaintenanceJobResponse)
def update_job(
    id: int,
    job_update: MaintenanceJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return MaintenanceService.update_job(db, id, job_update, current_user)


# --- Jobs & Requests POST submit ---
@router.post("/jobs/{id}/submit", response_model=MaintenanceJobResponse)
@router.post("/requests/{id}/submit", response_model=MaintenanceJobResponse)
def submit_job(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return MaintenanceService.submit_job(db, id, current_user)


# --- Specialized Views ---
@router.get("/defects", response_model=List[MaintenanceJobResponse])
def get_defect_position(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns critical defects requiring immediate or priority maintenance."""
    query = db.query(MaintenanceJob).filter(
        (MaintenanceJob.is_emergency == True) | (MaintenanceJob.calculated_criticality >= 70.0) | (MaintenanceJob.criticality >= 70.0)
    )
    if current_user.role == "department_user" and current_user.department_id:
        query = query.filter(MaintenanceJob.department_id == current_user.department_id)
    return query.order_by(MaintenanceJob.priority_score.desc()).all()


@router.get("/overdue", response_model=List[MaintenanceJobResponse])
def get_overdue_position(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns maintenance requirements exceeding scheduled due dates."""
    query = db.query(MaintenanceJob).filter(MaintenanceJob.overdue_days > 0)
    if current_user.role == "department_user" and current_user.department_id:
        query = query.filter(MaintenanceJob.department_id == current_user.department_id)
    return query.order_by(MaintenanceJob.overdue_days.desc()).all()


@router.get("/assets")
def get_master_assets(department_id: Optional[int] = None, db: Session = Depends(get_db)):
    from app.models.models import Asset
    query = db.query(Asset)
    if department_id:
        query = query.filter(Asset.department_id == department_id)
    return query.all()


@router.get("/resources")
def get_master_resources(department_id: Optional[int] = None, db: Session = Depends(get_db)):
    from app.models.models import Resource
    query = db.query(Resource)
    if department_id:
        query = query.filter(Resource.department_id == department_id)
    return query.all()
