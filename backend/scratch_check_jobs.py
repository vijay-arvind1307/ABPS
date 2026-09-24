import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath('c:/ABPS/backend'))

from app.db.session import SessionLocal
from app.models.models import MaintenanceJob, BlockPlan, PlanJob

db = SessionLocal()
try:
    jobs = db.query(MaintenanceJob).all()
    print(f"Total MaintenanceJobs in DB: {len(jobs)}")
    for j in jobs:
        sec = j.section
        sec_name = f"{sec.name} (id={sec.id}, {sec.section_id})" if sec else "None"
        print(f"  Job {j.id}: {j.job_code} | dept={j.department.code if j.department else '?'} | sec={sec_name} | dur={j.estimated_duration_min}m | work={j.work_type} | prio={j.priority_score}")
        
    print("\nActive Block Plans:")
    plans = db.query(BlockPlan).filter(BlockPlan.is_active == True).all()
    print(f"Total active BlockPlans: {len(plans)}")
    for p in plans:
        print(f"  Plan {p.id}: {p.plan_code} | corr_id={p.corridor_id} | strategy={p.strategy} | jobs={len(p.plan_jobs)}")
        for pj in p.plan_jobs:
            print(f"    PlanJob {pj.id}: job_id={pj.job_id} | blk={pj.block_code} | sec_id={pj.job.section_id if pj.job else '?'} | start={pj.scheduled_start_min} | end={pj.scheduled_end_min}")
finally:
    db.close()
