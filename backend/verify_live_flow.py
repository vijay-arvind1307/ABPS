import sys
import os
import requests
from app.db.session import SessionLocal
from app.models.models import MaintenanceJob, BlockPlan, Train, TrainMovement
from app.seed_data import seed_database
from app.core.config import settings

BASE_URL = "http://127.0.0.1:8000/api"

def run_tests():
    print("==================================================")
    print("IR-ABPS END-TO-END VERIFICATION SUITE")
    print("==================================================")

    # 1. Fresh Database Verification
    print("\n--- TEST 1: Fresh Database Master Seed State ---")
    db = SessionLocal()
    seed_database(db)
    
    jobs_count = db.query(MaintenanceJob).count()
    plans_count = db.query(BlockPlan).count()
    trains_count = db.query(Train).count()
    movements_count = db.query(TrainMovement).count()
    db.close()

    print(f"Maintenance Jobs in DB: {jobs_count} (Expected: 0)")
    print(f"Block Plans in DB: {plans_count} (Expected: 0)")
    print(f"Trains in Master DB: {trains_count} (Expected: 0)")
    print(f"Train Movements in DB: {movements_count} (Expected: 0)")
    assert jobs_count == 0, "Jobs must be 0 on fresh seed"
    assert plans_count == 0, "Plans must be 0 on fresh seed"
    assert trains_count == 0, "Trains must be 0 on fresh seed"
    print("[PASS] TEST 1: Fresh DB is clean (0 fake jobs, 0 fake plans, 0 fake trains).")

    # 2. Login as Engineering and Create Request
    print("\n--- TEST 2: Login as ENGG & Submit Request ---")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": "engg_user", "password": "engg123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    engg_token = res.json()["access_token"]

    engg_req_data = {
        "job_code": "ENG-2026-SEC01",
        "department_id": 1,
        "section_id": 1,
        "location_km": 15.5,
        "work_type": "TRACK_TAMPING",
        "description": "High-density plain track tamping after oscillation check",
        "criticality": 80.0,
        "safety_impact": 85.0,
        "operational_impact": 70.0,
        "urgency": 75.0,
        "estimated_duration_min": 60,
        "status": "SUBMITTED"
    }
    res_engg = requests.post(
        f"{BASE_URL}/maintenance/requests",
        json=engg_req_data,
        headers={"Authorization": f"Bearer {engg_token}"}
    )
    assert res_engg.status_code == 200, f"Create ENGG failed: {res_engg.text}"
    engg_job = res_engg.json()
    print(f"[PASS] Created ENGG Request: {engg_job['job_code']} (ID: {engg_job['id']}, Status: {engg_job['status']})")

    # 3. Login as S&T and Create Request
    print("\n--- TEST 3: Login as S&T & Submit Request ---")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": "snt_user", "password": "snt123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    snt_token = res.json()["access_token"]

    snt_req_data = {
        "job_code": "SNT-2026-SEC01",
        "department_id": 2,
        "section_id": 1,
        "location_km": 16.0,
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "description": "Digital point machine 102 overhaul and detection slide testing",
        "criticality": 75.0,
        "safety_impact": 80.0,
        "operational_impact": 65.0,
        "urgency": 70.0,
        "estimated_duration_min": 45,
        "status": "SUBMITTED"
    }
    res_snt = requests.post(
        f"{BASE_URL}/maintenance/requests",
        json=snt_req_data,
        headers={"Authorization": f"Bearer {snt_token}"}
    )
    assert res_snt.status_code == 200, f"Create S&T failed: {res_snt.text}"
    snt_job = res_snt.json()
    print(f"[PASS] Created S&T Request: {snt_job['job_code']} (ID: {snt_job['id']}, Status: {snt_job['status']})")

    # 4. Login as TRD and Create Request
    print("\n--- TEST 4: Login as TRD & Submit Request ---")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": "trd_user", "password": "trd123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    trd_token = res.json()["access_token"]

    trd_req_data = {
        "job_code": "TRD-2026-SEC01",
        "department_id": 3,
        "section_id": 1,
        "location_km": 16.2,
        "work_type": "OHE_INSPECTION",
        "description": "OHE contact wire dropper alignment and pantograph test",
        "criticality": 70.0,
        "safety_impact": 75.0,
        "operational_impact": 60.0,
        "urgency": 65.0,
        "estimated_duration_min": 45,
        "status": "SUBMITTED"
    }
    res_trd = requests.post(
        f"{BASE_URL}/maintenance/requests",
        json=trd_req_data,
        headers={"Authorization": f"Bearer {trd_token}"}
    )
    assert res_trd.status_code == 200, f"Create TRD failed: {res_trd.text}"
    trd_job = res_trd.json()
    print(f"[PASS] Created TRD Request: {trd_job['job_code']} (ID: {trd_job['id']}, Status: {trd_job['status']})")

    # 5. Planner sees all 3 requests
    print("\n--- TEST 5: Planner View of Multi-Department Requests ---")
    res = requests.post(f"{BASE_URL}/auth/login", json={"username": "planner", "password": "planner123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    planner_token = res.json()["access_token"]

    res_planner_jobs = requests.get(
        f"{BASE_URL}/maintenance/requests",
        headers={"Authorization": f"Bearer {planner_token}"}
    )
    all_jobs = res_planner_jobs.json()
    print(f"Total Requests visible to Planner: {len(all_jobs)}")
    for j in all_jobs:
        print(f"  - [{j['department']['code']}] {j['job_code']} | {j['work_type']} | Sec: {j['section_id']} | Dur: {j['estimated_duration_min']}m | Status: {j['status']}")
    assert len(all_jobs) == 3, f"Expected 3 jobs, got {len(all_jobs)}"
    print("[PASS] Planner successfully receives all submitted department requests.")

    # 6. Test RBAC: Department User Cannot Approve Plan
    print("\n--- TEST 6: RBAC Enforcement ---")
    res_forbidden = requests.post(
        f"{BASE_URL}/planning/approve",
        json={"action": "APPROVE", "reason": "Illegal department approval"},
        headers={"Authorization": f"Bearer {engg_token}"}
    )
    assert res_forbidden.status_code == 403, f"Expected 403 Forbidden, got {res_forbidden.status_code}"
    print("[PASS] Department user approval correctly blocked with 403 Forbidden.")

    # 7. Time-Distance & Data Status with Live Mode
    print("\n--- TEST 7: Time-Distance & Data Provenance Status ---")
    res_status = requests.get(f"{BASE_URL}/railway/data-status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    print(f"Data Status: {status_data['status']} | Provider: {status_data['provider']} | Train Count: {status_data['train_count']}")

    res_td = requests.get(f"{BASE_URL}/railway/time-distance")
    assert res_td.status_code == 200
    td_data = res_td.json()
    print(f"Time-Distance Stations: {len(td_data['stations'])} | Sections: {len(td_data['sections'])} | Trains: {len(td_data['trains'])}")
    print(f"Data Provenance: {td_data['provenance']['source']} ({td_data['provenance']['provider']})")

    # 8. Planner CP-SAT Generation with Real Demands
    print("\n--- TEST 8: CP-SAT Optimization on Real Department Demands ---")
    res_opt = requests.post(
        f"{BASE_URL}/planning/optimize",
        json={"strategy": "PLAN_A", "planning_horizon_hours": 24, "time_limit_seconds": 15},
        headers={"Authorization": f"Bearer {planner_token}"}
    )
    assert res_opt.status_code == 200, f"Optimization failed: {res_opt.text}"
    plan = res_opt.json()
    print(f"Generated Plan: {plan['plan_code']} | Solver Status: {plan['solver_status']} | Scheduled Jobs: {len(plan['plan_jobs'])}")
    for pj in plan['plan_jobs']:
        print(f"  - Job {pj['job']['job_code']} scheduled at {pj['scheduled_start_min']}m-{pj['scheduled_end_min']}m in window {pj['window_id']}")

    # 9. Planner Safety Validation
    print("\n--- TEST 9: Safety Validation ---")
    res_val = requests.post(
        f"{BASE_URL}/planning/plans/{plan['id']}/validate",
        headers={"Authorization": f"Bearer {planner_token}"}
    )
    assert res_val.status_code == 200
    val_data = res_val.json()
    print(f"Safety Validation: {val_data['status']} ({val_data['checked_rules_count']} safety rules verified)")
    assert val_data["status"] == "VALID"

    # 10. Planner Plan Approval
    print("\n--- TEST 10: Planner Plan Approval ---")
    res_app = requests.post(
        f"{BASE_URL}/planning/plans/{plan['id']}/approve",
        json={"action": "APPROVE", "reason": "Chief Controller Golden Corridor Optimization Approval"},
        headers={"Authorization": f"Bearer {planner_token}"}
    )
    assert res_app.status_code == 200
    app_data = res_app.json()
    print(f"Plan Approval Status: {app_data['approval_status']} (Approved by: Chief Section Controller)")
    assert app_data["approval_status"] == "APPROVED"

    print("\n==================================================")
    print("ALL 10 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
