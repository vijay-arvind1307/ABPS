import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status
from app.models.models import (
    MaintenanceJob, Department, Asset, RailwaySection, Corridor,
    MaintenanceJobResource, Resource, User, Station, AuditLog
)
from app.schemas.schemas import MaintenanceJobCreate, MaintenanceJobUpdate
from app.algorithms.priority import PriorityEngine


class MaintenanceService:
    @staticmethod
    def get_jobs(
        db: Session,
        department_id: Optional[int] = None,
        section_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[MaintenanceJob]:
        query = db.query(MaintenanceJob)
        if department_id:
            query = query.filter(MaintenanceJob.department_id == department_id)
        if section_id:
            query = query.filter(MaintenanceJob.section_id == section_id)
        if status:
            query = query.filter(MaintenanceJob.status == status)
        return query.order_by(MaintenanceJob.priority_score.desc()).all()

    @staticmethod
    def get_job_by_id(db: Session, job_id: int) -> Optional[MaintenanceJob]:
        job = db.query(MaintenanceJob).filter(MaintenanceJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Maintenance Request {job_id} not found")
        return job

    @staticmethod
    def create_job(db: Session, job_in: MaintenanceJobCreate, user: User) -> MaintenanceJob:
        # Enforce department assignment from user or request
        dept_id = job_in.department_id or user.department_id
        if not dept_id:
            r = (user.role or "").upper()
            if "ENGG" in r or "TRACK" in r or "CIVIL" in r:
                d = db.query(Department).filter(Department.code == "ENGG").first()
                dept_id = d.id if d else 1
            elif "SIGNAL" in r or "SNT" in r:
                d = db.query(Department).filter(Department.code == "SNT").first()
                dept_id = d.id if d else 2
            elif "TRACTION" in r or "TRD" in r:
                d = db.query(Department).filter(Department.code == "TRD").first()
                dept_id = d.id if d else 3
            else:
                dept_id = 1

        dept = db.query(Department).filter(Department.id == dept_id).first()
        dept_code = dept.code if dept else "ENGG"

        # 1. Normalize and validate Station Codes
        s_code = (job_in.start_station_code or "").strip().upper()
        e_code = (job_in.end_station_code or "").strip().upper()

        if not s_code or not e_code:
            raise HTTPException(status_code=400, detail="Start Station Code and End Station Code are both required.")

        if s_code == e_code:
            raise HTTPException(status_code=400, detail="Start and end stations must be different.")

        # Resolve stations
        stn_start = db.query(Station).filter(Station.code == s_code).first()
        stn_end = db.query(Station).filter(Station.code == e_code).first()

        if not stn_start or not stn_end:
            raise HTTPException(status_code=400, detail="Unknown railway station code. Please enter valid station codes.")

        # 2. Validate Corridor / Route Connection (Part 10)
        matched_section_id = job_in.section_id
        matched_corridor_id = None

        # Phase 3: Exact physical section identification without arbitrary guessing
        matched_section_id = None
        matched_corridor_id = None
        affected_section_ids = []
        location_status = "CONFIRMED"

        if job_in.section_id:
            specified_sec = db.query(RailwaySection).filter(RailwaySection.id == job_in.section_id).first()
            if specified_sec:
                matched_section_id = specified_sec.id
                matched_corridor_id = specified_sec.corridor_id
                affected_section_ids = [specified_sec.id]
        elif job_in.start_station_code and job_in.end_station_code and job_in.start_station_code == job_in.end_station_code:
            # Single station yard/point work
            stn_sec = db.query(RailwaySection).filter(
                or_(
                    RailwaySection.from_station_id == stn_start.id,
                    RailwaySection.to_station_id == stn_start.id
                )
            ).first()
            if stn_sec:
                matched_section_id = stn_sec.id
                matched_corridor_id = stn_sec.corridor_id
                affected_section_ids = [stn_sec.id]
        else:
            # Check for direct section between stations
            direct_sec = db.query(RailwaySection).filter(
                or_(
                    (RailwaySection.from_station_id == stn_start.id) & (RailwaySection.to_station_id == stn_end.id),
                    (RailwaySection.from_station_id == stn_end.id) & (RailwaySection.to_station_id == stn_start.id)
                )
            ).first()

            if direct_sec:
                matched_section_id = direct_sec.id
                matched_corridor_id = direct_sec.corridor_id
                affected_section_ids = [direct_sec.id]
            else:
                # Contiguous section path along corridor
                corr_id = job_in.corridor_id
                if not corr_id:
                    cand_corr = db.query(Corridor).all()
                    for c in cand_corr:
                        c_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == c.id).all()
                        stn_ids = {s.from_station_id for s in c_secs} | {s.to_station_id for s in c_secs}
                        if stn_start.id in stn_ids and stn_end.id in stn_ids:
                            corr_id = c.id
                            break

                if corr_id:
                    matched_corridor_id = corr_id
                    corr_secs = db.query(RailwaySection).filter(RailwaySection.corridor_id == corr_id).order_by(RailwaySection.id).all()
                    import networkx as nx
                    G = nx.Graph()
                    for cs in corr_secs:
                        G.add_edge(cs.from_station_id, cs.to_station_id, section=cs)
                    try:
                        if nx.has_path(G, stn_start.id, stn_end.id):
                            path_nodes = nx.shortest_path(G, stn_start.id, stn_end.id)
                            path_sec_ids = []
                            for idx in range(len(path_nodes) - 1):
                                edge_data = G.get_edge_data(path_nodes[idx], path_nodes[idx + 1])
                                if edge_data and "section" in edge_data:
                                    path_sec_ids.append(edge_data["section"].id)
                            if path_sec_ids:
                                affected_section_ids = path_sec_ids
                                matched_section_id = path_sec_ids[0]
                                location_status = "CONFIRMED"
                    except Exception:
                        pass

                if not matched_section_id:
                    import networkx as nx
                    G_all = nx.Graph()
                    all_secs = db.query(RailwaySection).all()
                    for cs in all_secs:
                        G_all.add_edge(cs.from_station_id, cs.to_station_id, section=cs)
                    try:
                        if nx.has_path(G_all, stn_start.id, stn_end.id):
                            path_nodes = nx.shortest_path(G_all, stn_start.id, stn_end.id)
                            path_sec_ids = []
                            for idx in range(len(path_nodes) - 1):
                                edge_data = G_all.get_edge_data(path_nodes[idx], path_nodes[idx + 1])
                                if edge_data and "section" in edge_data:
                                    path_sec_ids.append(edge_data["section"].id)
                            if path_sec_ids:
                                affected_section_ids = path_sec_ids
                                matched_section_id = path_sec_ids[0]
                                first_sec = db.query(RailwaySection).filter(RailwaySection.id == matched_section_id).first()
                                if first_sec:
                                    matched_corridor_id = first_sec.corridor_id
                                location_status = "CONFIRMED"
                    except Exception:
                        pass

        # STRICT SAFETY RULE: NEVER guess corr_secs[0]!
        if not matched_section_id:
            location_status = "LOCATION_REQUIRES_CONFIRMATION"
            matched_section_id = None

        # 3. Deterministic Priority Engine Calculation (Parts 17-23)
        raw_prio = job_in.user_priority or job_in.priority or "MEDIUM"
        user_prio = raw_prio.upper()
        if user_prio not in ("LOW", "MEDIUM", "HIGH"):
            user_prio = "MEDIUM"

        scoring = PriorityEngine.calculate_full_priority(
            work_type=job_in.work_type,
            department_code=dept_code,
            user_priority=user_prio,
            due_date=job_in.due_date,
            is_emergency=job_in.is_emergency
        )

        final_corridor_id = job_in.corridor_id or matched_corridor_id

        req_status = job_in.status if job_in.status in ("DRAFT", "SUBMITTED") else "SUBMITTED"
        submitted_at = datetime.utcnow() if req_status == "SUBMITTED" else None

        if job_in.job_code:
            generated_code = job_in.job_code
        else:
            job_count = db.query(MaintenanceJob).count()
            generated_code = f"REQ-{job_count + 101:06d}"

        w_title = job_in.work_title or (job_in.work_type.replace('_', ' ').title() if job_in.work_type else "Track Maintenance Block")

        job = MaintenanceJob(
            job_code=generated_code,
            work_title=w_title,
            department_id=dept_id,
            corridor_id=final_corridor_id,
            asset_id=job_in.asset_id,
            section_id=matched_section_id,
            location_km=job_in.location_km or 0.0,
            work_type=job_in.work_type,
            description=job_in.description,
            start_station_code=s_code,
            start_station_name=stn_start.name,
            end_station_code=e_code,
            end_station_name=stn_end.name,
            requested_date=job_in.requested_date or job_in.due_date,
            requested_start_time=job_in.requested_start_time,
            requested_end_time=job_in.requested_end_time,
            safety_impact_info=job_in.safety_impact_info,
            additional_remarks=job_in.additional_remarks,
            user_priority=user_prio,
            due_date=job_in.due_date,
            overdue_days=0,
            calculated_criticality=scoring["criticality"],
            calculated_safety_impact=scoring["safety_impact"],
            calculated_urgency=scoring["urgency"],
            overdue_risk_score=scoring.get("overdue_risk", 0.0),
            criticality_label=scoring["criticality_label"],
            safety_impact_label=scoring["safety_impact_label"],
            urgency_label=scoring["urgency_label"],
            criticality=scoring["criticality"],
            safety_impact=scoring["safety_impact"],
            urgency=scoring["urgency"],
            operational_impact=scoring.get("operational_impact", 50.0),
            priority_score=scoring["priority_score"],
            safety_tier=scoring["safety_tier"],
            priority_explanation=scoring,
            estimated_duration_min=job_in.estimated_duration_min,
            preferred_start_min=job_in.preferred_start_min,
            preferred_end_min=job_in.preferred_end_min,
            affected_sections_json=affected_section_ids if affected_section_ids else None,
            location_status=location_status,
            version_number=1,
            status=req_status,
            is_emergency=job_in.is_emergency,
            created_by_id=user.id,
            submitted_at=submitted_at
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Add resources if any
        if job_in.required_resource_ids:
            for r_id in job_in.required_resource_ids:
                jr = MaintenanceJobResource(job_id=job.id, resource_id=r_id, quantity_required=1)
                db.add(jr)
            db.commit()

        return job

    @staticmethod
    def update_job(db: Session, job_id: int, job_update: MaintenanceJobUpdate, user: User) -> MaintenanceJob:
        job = MaintenanceService.get_job_by_id(db, job_id)

        # Enforce RBAC: department users can only update their own department's jobs
        user_role = (user.role or "").upper()
        dept_roles = {"DEPARTMENT_USER", "TRACK_ENGINEERING", "SIGNAL_TELECOM", "TRACTION_DISTRIBUTION"}
        if user_role in dept_roles:
            if user.department_id != job.department_id:
                raise HTTPException(status_code=403, detail="Department users can only edit requests in their own department.")
            if job_update.status in ("APPROVED", "REJECTED", "SCHEDULED"):
                raise HTTPException(status_code=403, detail="Department users are not authorized to approve, reject, or schedule requests.")
            if job.status not in ("DRAFT", "SUBMITTED"):
                raise HTTPException(status_code=403, detail=f"Request cannot be modified in '{job.status}' state.")

        # Optimistic Concurrency Control (Phase 16)
        if hasattr(job_update, "version_number") and job_update.version_number is not None:
            if job_update.version_number != job.version_number:
                raise HTTPException(
                    status_code=409,
                    detail=f"Conflict: Maintenance request {job.job_code} was modified by another user (current version: {job.version_number}, your version: {job_update.version_number}). Please refresh."
                )

        job.version_number = (job.version_number or 1) + 1

        update_data = job_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field in ("priority", "user_priority") and value:
                job.user_priority = value.upper()
            elif field == "start_station_code" and value:
                job.start_station_code = value.upper()
                stn = db.query(Station).filter(Station.code == job.start_station_code).first()
                if stn:
                    job.start_station_name = stn.name
            elif field == "end_station_code" and value:
                job.end_station_code = value.upper()
                stn = db.query(Station).filter(Station.code == job.end_station_code).first()
                if stn:
                    job.end_station_name = stn.name
            else:
                setattr(job, field, value)

        if job.status == "SUBMITTED" and not job.submitted_at:
            job.submitted_at = datetime.utcnow()

        # Recalculate priority automatically
        dept_code = job.department.code if job.department else "ENGG"
        scoring = PriorityEngine.calculate_full_priority(
            work_type=job.work_type,
            department_code=dept_code,
            user_priority=job.user_priority,
            due_date=job.due_date,
            is_emergency=job.is_emergency
        )

        job.calculated_criticality = scoring["criticality"]
        job.calculated_safety_impact = scoring["safety_impact"]
        job.calculated_urgency = scoring["urgency"]
        job.criticality_label = scoring["criticality_label"]
        job.safety_impact_label = scoring["safety_impact_label"]
        job.urgency_label = scoring["urgency_label"]
        job.criticality = scoring["criticality"]
        job.safety_impact = scoring["safety_impact"]
        job.urgency = scoring["urgency"]

        # If planner override is not active, use calculated score
        if job.planner_override_score is None:
            job.priority_score = scoring["priority_score"]
            job.safety_tier = scoring["safety_tier"]

        job.priority_explanation = scoring
        job.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def override_priority(db: Session, job_id: int, override_score: float, reason: str, user: User) -> MaintenanceJob:
        """
        Allows Railway Planner authority to override a system-generated priority score with formal audit logging.
        """
        user_role = (user.role or "").upper()
        if user_role not in ("RAILWAY_PLANNER", "PLANNER", "SYSTEM_ADMIN", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only Railway Planners are authorized to override priority scores.")

        job = MaintenanceService.get_job_by_id(db, job_id)
        old_score = job.priority_score

        job.planner_override_score = round(override_score, 1)
        job.planner_override_reason = reason
        job.planner_override_by_id = user.id
        job.planner_override_at = datetime.utcnow()
        job.priority_score = round(override_score, 1)
        job.updated_at = datetime.utcnow()

        audit = AuditLog(
            user_id=user.id,
            action="OVERRIDE_PRIORITY_SCORE",
            entity_type="MAINTENANCE_JOB",
            entity_id=str(job.id),
            details_json={
                "job_code": job.job_code,
                "old_score": old_score,
                "new_score": job.priority_score,
                "reason": reason
            }
        )
        db.add(audit)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def submit_job(db: Session, job_id: int, user: User) -> MaintenanceJob:
        job = MaintenanceService.get_job_by_id(db, job_id)
        user_role = (user.role or "").upper()
        if user_role in ("TRACK_ENGINEERING", "SIGNAL_TELECOM", "TRACTION_DISTRIBUTION", "DEPARTMENT_USER") and user.department_id != job.department_id:
            raise HTTPException(status_code=403, detail="Department users can only submit requests for their own department.")

        job.status = "SUBMITTED"
        job.submitted_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job
