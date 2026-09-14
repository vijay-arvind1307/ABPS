from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.models import (
    MaintenanceJob, PlanJob, ExecutionRecord, User, AuditLog, Notification, RailwaySection
)


class ExecutionService:
    @staticmethod
    def get_current_minute_of_day() -> int:
        now = datetime.now()
        return now.hour * 60 + now.minute

    @staticmethod
    def get_execution_records(
        db: Session,
        department_id: Optional[int] = None,
        status_filter: Optional[str] = None
    ) -> List[ExecutionRecord]:
        query = db.query(ExecutionRecord).order_by(ExecutionRecord.id.desc())
        if department_id:
            query = query.join(MaintenanceJob, ExecutionRecord.job_id == MaintenanceJob.id).filter(
                MaintenanceJob.department_id == department_id
            )
        if status_filter:
            query = query.filter(ExecutionRecord.status == status_filter)
        return query.all()

    @staticmethod
    def start_execution(
        db: Session,
        job_id: int,
        user: User,
        actual_start_min: Optional[int] = None,
        remarks: Optional[str] = None
    ) -> ExecutionRecord:
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Maintenance job not found.")

        # Allow starting from approved or scheduled states
        valid_prev = ["SCHEDULED", "READY", "APPROVED", "DEPARTMENT_ACCEPTED", "SUBMITTED"]
        if job.status not in valid_prev and job.execution_status == "IN_PROGRESS":
            raise HTTPException(
                status_code=400,
                detail=f"Job {job.job_code} is already IN_PROGRESS or completed."
            )

        start_min = actual_start_min if actual_start_min is not None else ExecutionService.get_current_minute_of_day()

        # Find linked plan job
        plan_job = db.query(PlanJob).filter(PlanJob.job_id == job.id).first()
        planned_start = plan_job.scheduled_start_min if plan_job else job.preferred_start_min
        planned_end = plan_job.scheduled_end_min if plan_job else (
            (planned_start + job.estimated_duration_min) if planned_start else None
        )

        delay_calc = max(0, start_min - planned_start) if planned_start else 0

        # Update Job State
        old_status = job.status
        job.status = "IN_PROGRESS"
        job.execution_status = "IN_PROGRESS"
        job.actual_start_min = start_min
        job.delay_minutes = delay_calc

        # State transition history
        history = list(job.state_history_json or [])
        history.append({
            "from_state": old_status,
            "to_state": "IN_PROGRESS",
            "acting_user": user.username,
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": remarks or "Field execution initiated"
        })
        job.state_history_json = history

        # Update PlanJob if exists
        if plan_job:
            plan_job.execution_status = "IN_PROGRESS"
            plan_job.actual_start_min = start_min

        # Create Execution Record
        sec_name = job.section.name if job.section else f"Section {job.start_station_code}-{job.end_station_code}"
        rec = ExecutionRecord(
            job_id=job.id,
            plan_job_id=plan_job.id if plan_job else None,
            status="IN_PROGRESS",
            planned_start_min=planned_start,
            planned_end_min=planned_end,
            actual_start_min=start_min,
            delay_min=delay_calc,
            completion_pct=10.0,
            responsible_department=job.department.code if job.department else "ENGG",
            remarks=remarks or "Maintenance possession taken on track",
            notes=f"Track possession commenced on {sec_name}",
            updated_by_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.add(rec)

        # Create Planner Notification
        notif = Notification(
            title=f"Block In Progress: {job.job_code}",
            message=f"Department {job.department.code if job.department else 'ENGG'} has taken track possession for {job.job_code} on {sec_name}.",
            notification_type="EXECUTION_ALERT",
            target_entity="MAINTENANCE_JOB",
            target_id=str(job.id)
        )
        db.add(notif)

        # Audit Log
        audit = AuditLog(
            user_id=user.id,
            action="START_EXECUTION",
            entity_type="MAINTENANCE_JOB",
            entity_id=str(job.id),
            details_json={
                "job_code": job.job_code,
                "actual_start_min": start_min,
                "delay_min": delay_calc
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def update_progress(
        db: Session,
        job_id: int,
        user: User,
        completion_pct: float,
        delay_min: Optional[int] = 0,
        remarks: Optional[str] = None
    ) -> ExecutionRecord:
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Maintenance job not found.")

        job.completion_pct = min(100.0, max(0.0, completion_pct))
        if delay_min:
            job.delay_minutes = delay_min

        plan_job = db.query(PlanJob).filter(PlanJob.job_id == job.id).first()

        rec = ExecutionRecord(
            job_id=job.id,
            plan_job_id=plan_job.id if plan_job else None,
            status="IN_PROGRESS" if completion_pct < 100 else "COMPLETED",
            actual_start_min=job.actual_start_min,
            delay_min=job.delay_minutes,
            completion_pct=job.completion_pct,
            responsible_department=job.department.code if job.department else "ENGG",
            remarks=remarks or f"Progress updated to {job.completion_pct}%",
            notes=remarks,
            updated_by_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def complete_execution(
        db: Session,
        job_id: int,
        user: User,
        actual_end_min: Optional[int] = None,
        completion_pct: float = 100.0,
        status_val: str = "COMPLETED",
        remarks: Optional[str] = None
    ) -> ExecutionRecord:
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Maintenance job not found.")

        end_min = actual_end_min if actual_end_min is not None else ExecutionService.get_current_minute_of_day()
        start_min = job.actual_start_min if job.actual_start_min is not None else max(0, end_min - job.estimated_duration_min)
        actual_dur = max(0, end_min - start_min)
        variance = actual_dur - job.estimated_duration_min

        old_status = job.status
        final_status = "COMPLETED" if status_val.upper() == "COMPLETED" else "PARTIALLY_COMPLETED"
        job.status = final_status
        job.execution_status = final_status
        job.actual_end_min = end_min
        job.completion_pct = completion_pct
        job.variance_minutes = variance

        # State transition history
        history = list(job.state_history_json or [])
        history.append({
            "from_state": old_status,
            "to_state": final_status,
            "acting_user": user.username,
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": remarks or "Field work concluded and track handed back"
        })
        job.state_history_json = history

        # Update linked plan job
        plan_job = db.query(PlanJob).filter(PlanJob.job_id == job.id).first()
        planned_start = plan_job.scheduled_start_min if plan_job else job.preferred_start_min
        planned_end = plan_job.scheduled_end_min if plan_job else (
            (planned_start + job.estimated_duration_min) if planned_start else None
        )
        if plan_job:
            plan_job.execution_status = final_status
            plan_job.actual_end_min = end_min

        rec = ExecutionRecord(
            job_id=job.id,
            plan_job_id=plan_job.id if plan_job else None,
            status=final_status,
            planned_start_min=planned_start,
            planned_end_min=planned_end,
            actual_start_min=start_min,
            actual_end_min=end_min,
            delay_min=job.delay_minutes,
            variance_min=variance,
            completion_pct=completion_pct,
            responsible_department=job.department.code if job.department else "ENGG",
            remarks=remarks or f"Block cleared. Actual duration: {actual_dur} min (Variance: {variance:+} min)",
            notes=remarks,
            updated_by_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.add(rec)

        # Notify planner
        notif = Notification(
            title=f"Block Cleared: {job.job_code} ({final_status})",
            message=f"Department {job.department.code if job.department else 'ENGG'} has completed work for {job.job_code}. Track restored to normal traffic. Duration: {actual_dur}m (Variance: {variance:+}m).",
            notification_type="EXECUTION_ALERT",
            target_entity="MAINTENANCE_JOB",
            target_id=str(job.id)
        )
        db.add(notif)

        # Audit Log
        audit = AuditLog(
            user_id=user.id,
            action=f"COMPLETE_EXECUTION_{final_status}",
            entity_type="MAINTENANCE_JOB",
            entity_id=str(job.id),
            details_json={
                "job_code": job.job_code,
                "status": final_status,
                "actual_duration_min": actual_dur,
                "variance_min": variance,
                "completion_pct": completion_pct
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def cancel_execution(
        db: Session,
        job_id: int,
        user: User,
        reason: str
    ) -> MaintenanceJob:
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Maintenance job not found.")

        old_status = job.status
        job.status = "CANCELLED"
        job.execution_status = "CANCELLED"
        job.rejection_reason = reason

        history = list(job.state_history_json or [])
        history.append({
            "from_state": old_status,
            "to_state": "CANCELLED",
            "acting_user": user.username,
            "user_id": user.id,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        job.state_history_json = history

        rec = ExecutionRecord(
            job_id=job.id,
            status="CANCELLED",
            remarks=reason,
            notes=f"Execution cancelled: {reason}",
            updated_by_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.add(rec)

        audit = AuditLog(
            user_id=user.id,
            action="CANCEL_EXECUTION",
            entity_type="MAINTENANCE_JOB",
            entity_id=str(job.id),
            details_json={"reason": reason}
        )
        db.add(audit)
        db.commit()
        db.refresh(job)
        return job
