import io
import csv
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.models import BlockPlan, PlanJob, MaintenanceJob, Department, AuditLog, PlannerAction, RailwaySection


class ReportService:
    @staticmethod
    def get_weekly_summary(db: Session) -> Dict[str, Any]:
        plans = db.query(BlockPlan).order_by(BlockPlan.id.desc()).limit(10).all()
        jobs = db.query(MaintenanceJob).all()
        departments = db.query(Department).all()

        dept_summary = {}
        for d in departments:
            d_jobs = [j for j in jobs if j.department_id == d.id]
            dept_summary[d.code] = {
                "name": d.name,
                "total_jobs": len(d_jobs),
                "critical": sum(1 for j in d_jobs if "Tier 1" in j.safety_tier or "Tier 2" in j.safety_tier),
                "overdue": sum(1 for j in d_jobs if j.overdue_days > 0),
                "completed": sum(1 for j in d_jobs if j.status == "COMPLETED")
            }

        return {
            "total_maintenance_demands": len(jobs),
            "critical_overdue_jobs": sum(1 for j in jobs if j.overdue_days > 0 or "Tier 1" in j.safety_tier),
            "department_breakdown": dept_summary,
            "recent_plans": [
                {
                    "id": p.id,
                    "plan_code": p.plan_code,
                    "strategy": p.strategy,
                    "blocks_count": p.total_blocks_count,
                    "utilization_pct": p.block_utilization_pct,
                    "critical_completed": f"{p.critical_jobs_completed}/{p.total_critical_jobs}",
                    "approval_status": p.approval_status,
                    "created_at": p.created_at.strftime("%Y-%m-%d %H:%M")
                }
                for p in plans
            ]
        }

    @staticmethod
    def get_monthly_summary(db: Session) -> Dict[str, Any]:
        """Aggregates monthly railway maintenance indicators from database."""
        plans = db.query(BlockPlan).order_by(BlockPlan.id.desc()).limit(30).all()
        jobs = db.query(MaintenanceJob).all()
        sections = db.query(RailwaySection).all()

        total_blocks = sum(p.total_blocks_count for p in plans)
        avg_util = round(sum(p.block_utilization_pct for p in plans) / max(1, len(plans)), 1) if plans else 0.0

        # Calculate actual safety compliance rate from validated operational records
        eval_plans = [p for p in plans if getattr(p, 'approval_status', '') in ('APPROVED', 'COMMITTED', 'COMPLETED')]
        valid_plans = [p for p in eval_plans if getattr(p, 'is_valid', True)]
        compliance_rate = round((len(valid_plans) / len(eval_plans)) * 100, 1) if eval_plans else None

        return {
            "month": "Current Operating Period",
            "total_block_plans": len(plans),
            "total_maintenance_blocks_executed": total_blocks,
            "average_block_utilization_pct": avg_util,
            "total_demands_processed": len(jobs),
            "completed_jobs": sum(1 for j in jobs if j.status == "COMPLETED"),
            "active_sections_serviced": len(sections),
            "safety_compliance_rate": compliance_rate if compliance_rate is not None else "DATA_INSUFFICIENT_FOR_VALIDATION",
            "safety_compliance_basis": "VALIDATED_FROM_DATABASE_RECORDS" if compliance_rate is not None else "INSUFFICIENT_OPERATIONAL_RECORDS"
        }

    @staticmethod
    def get_maintenance_position(db: Session) -> List[Dict[str, Any]]:
        """Returns current maintenance backlog & execution position across departments."""
        jobs = db.query(MaintenanceJob).all()
        departments = db.query(Department).all()

        positions = []
        for d in departments:
            d_jobs = [j for j in jobs if j.department_id == d.id]
            positions.append({
                "department_code": d.code,
                "department_name": d.name,
                "total_demanded": len(d_jobs),
                "scheduled": sum(1 for j in d_jobs if j.status == "SCHEDULED"),
                "completed": sum(1 for j in d_jobs if j.status == "COMPLETED"),
                "overdue": sum(1 for j in d_jobs if j.overdue_days > 0),
                "critical": sum(1 for j in d_jobs if "Tier 1" in (j.safety_tier or "") or "Tier 2" in (j.safety_tier or ""))
            })
        return positions

    @staticmethod
    def get_critical_maintenance(db: Session) -> List[Dict[str, Any]]:
        """Returns all Tier 1 & Tier 2 safety-critical maintenance jobs."""
        jobs = db.query(MaintenanceJob).filter(
            or_(
                MaintenanceJob.safety_tier.like("%Tier 1%"),
                MaintenanceJob.safety_tier.like("%Tier 2%"),
                MaintenanceJob.is_emergency == True
            )
        ).order_by(MaintenanceJob.priority_score.desc()).all()

        return [
            {
                "id": j.id,
                "job_code": j.job_code,
                "work_type": j.work_type,
                "department": j.department.code if j.department else "ENGG",
                "start_station_code": j.start_station_code,
                "end_station_code": j.end_station_code,
                "section": j.section.name if j.section else f"{j.start_station_code} - {j.end_station_code}",
                "priority_score": j.priority_score,
                "safety_tier": j.safety_tier,
                "status": j.status,
                "overdue_days": j.overdue_days
            }
            for j in jobs
        ]

    @staticmethod
    def get_overdue_maintenance(db: Session) -> List[Dict[str, Any]]:
        """Returns overdue maintenance jobs with days elapsed."""
        jobs = db.query(MaintenanceJob).filter(MaintenanceJob.overdue_days > 0).order_by(MaintenanceJob.overdue_days.desc()).all()
        return [
            {
                "id": j.id,
                "job_code": j.job_code,
                "work_type": j.work_type,
                "department": j.department.code if j.department else "ENGG",
                "overdue_days": j.overdue_days,
                "priority_score": j.priority_score,
                "safety_tier": j.safety_tier,
                "status": j.status
            }
            for j in jobs
        ]

    @staticmethod
    def export_plan_csv(db: Session, plan_id: int) -> str:
        """Exports approved/scheduled block plan to official CRIS CSV format."""
        plan = db.query(BlockPlan).filter(BlockPlan.id == plan_id).first()
        if not plan:
            return ""

        plan_jobs = db.query(PlanJob).filter(PlanJob.plan_id == plan.id).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Plan Code", "Block Code", "Job Code", "Department",
            "Section", "Work Type", "Scheduled Start (Min)", "Scheduled End (Min)",
            "Duration (Min)", "Priority", "Safety Tier", "Status"
        ])

        for pj in plan_jobs:
            j = pj.job
            sec_name = j.section.name if j and j.section else "N/A"
            dept_code = j.department.code if j and j.department else "N/A"
            writer.writerow([
                plan.plan_code,
                pj.block_code or "DEFERRED",
                j.job_code if j else "N/A",
                dept_code,
                sec_name,
                j.work_type if j else "N/A",
                pj.scheduled_start_min if pj.scheduled_start_min is not None else "N/A",
                pj.scheduled_end_min if pj.scheduled_end_min is not None else "N/A",
                pj.scheduled_duration_min if pj.scheduled_duration_min is not None else "N/A",
                j.priority_score if j else 0.0,
                j.safety_tier if j else "N/A",
                pj.execution_status
            ])

        return output.getvalue()
