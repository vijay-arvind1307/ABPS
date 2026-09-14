from typing import List, Optional
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import AuditLog, PlannerAction, BlockPlan, User
from app.schemas.schemas import AuditLogResponse, PlannerActionResponse
from app.services.report_service import ReportService
from app.routers.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports & Audit"])


@router.get("/weekly")
def get_weekly_report(db: Session = Depends(get_db)):
    return ReportService.get_weekly_summary(db)


@router.get("/monthly")
def get_monthly_report(db: Session = Depends(get_db)):
    return ReportService.get_monthly_summary(db)


@router.get("/position")
def get_maintenance_position_report(db: Session = Depends(get_db)):
    return ReportService.get_maintenance_position(db)


@router.get("/critical")
def get_critical_maintenance_report(db: Session = Depends(get_db)):
    return ReportService.get_critical_maintenance(db)


@router.get("/overdue")
def get_overdue_maintenance_report(db: Session = Depends(get_db)):
    return ReportService.get_overdue_maintenance(db)


@router.get("/plans/{id}/export-csv")
def export_plan_csv(id: int, db: Session = Depends(get_db)):
    csv_content = ReportService.export_plan_csv(db, id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=block_plan_{id}.csv"}
    )


@router.get("/audit", response_model=List[AuditLogResponse])
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()


@router.get("/actions", response_model=List[PlannerActionResponse])
def get_planner_actions(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(PlannerAction).order_by(PlannerAction.id.desc()).limit(limit).all()
