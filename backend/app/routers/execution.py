from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, ExecutionRecord, MaintenanceJob
from app.schemas.schemas import (
    ExecutionRecordResponse,
    ExecutionStartRequest,
    ExecutionProgressRequest,
    ExecutionCompleteRequest,
    ExecutionCancelRequest,
    MaintenanceJobResponse
)
from app.services.execution_service import ExecutionService
from app.routers.auth import get_current_user

router = APIRouter(prefix="/execution", tags=["Maintenance Block Execution Management"])


@router.get("/records", response_model=List[ExecutionRecordResponse])
def get_execution_records(
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns execution records, filtered by user's department if department_user."""
    dept = department_id
    if current_user.role == "department_user" and current_user.department_id:
        dept = current_user.department_id
    return ExecutionService.get_execution_records(db, department_id=dept, status_filter=status)


@router.get("/{job_id}", response_model=Optional[ExecutionRecordResponse])
def get_job_execution(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns latest execution record for specified maintenance job."""
    rec = db.query(ExecutionRecord).filter(ExecutionRecord.job_id == job_id).order_by(ExecutionRecord.id.desc()).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"No execution record found for Job {job_id}")
    return rec


@router.post("/start", response_model=ExecutionRecordResponse)
def start_execution(
    req: ExecutionStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Commences physical track possession maintenance block execution."""
    return ExecutionService.start_execution(
        db=db,
        job_id=req.job_id,
        user=current_user,
        actual_start_min=req.actual_start_min,
        remarks=req.remarks
    )


@router.post("/progress", response_model=ExecutionRecordResponse)
def update_execution_progress(
    req: ExecutionProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates live block execution progress percentage and remarks."""
    return ExecutionService.update_progress(
        db=db,
        job_id=req.job_id,
        user=current_user,
        completion_pct=req.completion_pct,
        delay_min=req.delay_min,
        remarks=req.remarks
    )


@router.post("/complete", response_model=ExecutionRecordResponse)
def complete_execution(
    req: ExecutionCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Concludes maintenance block, clears track, and calculates variance against schedule."""
    return ExecutionService.complete_execution(
        db=db,
        job_id=req.job_id,
        user=current_user,
        actual_end_min=req.actual_end_min,
        completion_pct=req.completion_pct,
        status_val=req.status or "COMPLETED",
        remarks=req.remarks
    )


@router.post("/cancel", response_model=MaintenanceJobResponse)
def cancel_execution(
    req: ExecutionCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancels maintenance block execution with recorded reason."""
    return ExecutionService.cancel_execution(
        db=db,
        job_id=req.job_id,
        user=current_user,
        reason=req.reason
    )
