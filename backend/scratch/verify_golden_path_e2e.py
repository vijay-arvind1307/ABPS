import os
import sys
import requests
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000"

def log(msg):
    print(f"[*] {msg}", flush=True)

def get_token(username, password, department=None):
    payload = {"username": username, "password": password}
    if department:
        payload["department"] = department
    res = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]

def main():
    log("=== STARTING FULL 43-STEP GOLDEN PATH VERIFICATION ===")

    # STEP 1: Login as Engineering
    engg_token = get_token("engg_user", "engg123", "Engineering")
    engg_headers = {"Authorization": f"Bearer {engg_token}"}
    log("STEP 1: Logged in as Engineering")

    # Get Corridor C40 ID
    corr_res = requests.get(f"{BASE_URL}/api/railway/corridors", headers=engg_headers)
    assert corr_res.status_code == 200
    corridors = corr_res.json()
    c40 = next((c for c in corridors if "C40" in c.get("corridor_code", "") or "MDU" in c.get("start_station_code", "")), corridors[0])
    c40_id = c40["id"]
    log(f"Found Corridor: ID={c40_id}, Code={c40.get('corridor_code')}")

    # STEP 2 & 3: Create Engineering request (Track Tamping on C40, MDU -> TDN, 90m, 10:00-12:00, HIGH)
    req_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    ts = int(datetime.utcnow().timestamp())
    r_engg = requests.post(f"{BASE_URL}/api/block-requests", json={
        "job_code": f"REQ-ENGG-{ts}",
        "work_title": "Track Tamping MDU-TDN",
        "work_type": "TRACK_TAMPING",
        "corridor_id": c40_id,
        "start_station_code": "MDU",
        "end_station_code": "TDN",
        "requested_date": req_date,
        "preferred_start_min": 600,
        "preferred_end_min": 720,
        "estimated_duration_min": 90,
        "user_priority": "HIGH",
        "is_emergency": False,
        "description": "Routine track tamping and alignment on physical section MDU-TDN"
    }, headers=engg_headers)
    assert r_engg.status_code == 200, f"Engg request creation failed: {r_engg.text}"
    engg_job = r_engg.json()
    engg_job_id = engg_job["id"]
    log(f"STEP 2-3: Engineering request created: ID={engg_job_id}, Code={engg_job['job_code']}, Status={engg_job['status']}")

    # STEP 4 & 5: Login as S&T and create compatible request
    snt_token = get_token("snt_user", "snt123", "Signal & Telecom")
    snt_headers = {"Authorization": f"Bearer {snt_token}"}
    log("STEP 4: Logged in as S&T")

    r_snt = requests.post(f"{BASE_URL}/api/block-requests", json={
        "job_code": f"REQ-SNT-{ts}",
        "work_title": "Signal Point Overhaul MDU-TDN",
        "work_type": "SIGNAL_POINT_OVERHAUL",
        "corridor_id": c40_id,
        "start_station_code": "MDU",
        "end_station_code": "TDN",
        "requested_date": req_date,
        "preferred_start_min": 600,
        "preferred_end_min": 720,
        "estimated_duration_min": 60,
        "user_priority": "MEDIUM",
        "is_emergency": False,
        "description": "Signal and point machine overhaul MDU-TDN"
    }, headers=snt_headers)
    assert r_snt.status_code == 200, f"S&T request creation failed: {r_snt.text}"
    snt_job = r_snt.json()
    snt_job_id = snt_job["id"]
    log(f"STEP 5: S&T request created: ID={snt_job_id}, Code={snt_job['job_code']}, Status={snt_job['status']}")

    # STEP 6 & 7: Login as TRD and create compatible request
    trd_token = get_token("trd_user", "trd123", "Traction Distribution")
    trd_headers = {"Authorization": f"Bearer {trd_token}"}
    log("STEP 6: Logged in as TRD")

    r_trd = requests.post(f"{BASE_URL}/api/block-requests", json={
        "job_code": f"REQ-TRD-{ts}",
        "work_title": "OHE Power Block MDU-TDN",
        "work_type": "OHE_INSPECTION",
        "corridor_id": c40_id,
        "start_station_code": "MDU",
        "end_station_code": "TDN",
        "requested_date": req_date,
        "preferred_start_min": 600,
        "preferred_end_min": 720,
        "estimated_duration_min": 75,
        "user_priority": "HIGH",
        "is_emergency": False,
        "description": "25kV OHE periodic inspection and contact wire checking"
    }, headers=trd_headers)
    assert r_trd.status_code == 200, f"TRD request creation failed: {r_trd.text}"
    trd_job = r_trd.json()
    trd_job_id = trd_job["id"]
    log(f"STEP 7: TRD request created: ID={trd_job_id}, Code={trd_job['job_code']}, Status={trd_job['status']}")

    # STEP 8 & 9: Login as Planner & verify queue
    planner_token = get_token("planner", "planner123", "Railway Operations & Traffic Planning")
    planner_headers = {"Authorization": f"Bearer {planner_token}"}
    log("STEP 8: Logged in as Railway Planner")

    queue_res = requests.get(f"{BASE_URL}/api/block-requests", headers=planner_headers)
    assert queue_res.status_code == 200
    queue = queue_res.json()
    q_ids = [q["id"] for q in queue]
    assert engg_job_id in q_ids
    assert snt_job_id in q_ids
    assert trd_job_id in q_ids
    log(f"STEP 9: All 3 requests verified in central Planner Queue (Total in queue: {len(queue)})")

    # STEP 10, 11, 12: Request review, priority & XGBoost explanation
    rev_res = requests.get(f"{BASE_URL}/api/planning/requests/{engg_job_id}/planner-review", headers=planner_headers)
    assert rev_res.status_code == 200
    review_data = rev_res.json()
    assert "priority_explanation" in review_data

    # XGBoost Inference
    ml_res = requests.post(f"{BASE_URL}/api/ml/predict/{engg_job_id}", headers=planner_headers)
    assert ml_res.status_code == 200
    ml_data = ml_res.json()
    assert "ml_risk_score" in ml_data
    assert "model_version" in ml_data
    assert len(ml_data.get("top_contributing_factors", [])) > 0
    log(f"STEP 10-12: Verified Priority Engine Score: {review_data.get('job', {}).get('priority_score')} and XGBoost Risk Score: {ml_data['ml_risk_score']} ({ml_data['risk_class']}) Model: {ml_data['model_version']}")

    # STEP 13 & 14: Available windows & compatibility check
    comp_check = requests.post(f"{BASE_URL}/api/block-requests/coordination/check", json={
        "job_ids": [engg_job_id, snt_job_id, trd_job_id]
    }, headers=planner_headers)
    assert comp_check.status_code == 200
    comp_data = comp_check.json()
    assert comp_data["is_compatible"] is True
    assert comp_data["compatible_count"] == 3
    log(f"STEP 13-14: Compatibility Engine verified 3 jobs 100% compatible for shared possession")

    # STEP 15, 16, 17: CP-SAT Global Optimization
    opt_res = requests.post(f"{BASE_URL}/api/block-planning/optimize", json={
        "job_ids": [engg_job_id, snt_job_id, trd_job_id],
        "strategy": "PLAN_A"
    }, headers=planner_headers)
    assert opt_res.status_code == 200, f"Optimization failed: {opt_res.text}"
    opt_data = opt_res.json()
    plan_id = opt_data.get("plan_id") or opt_data.get("id") or (opt_data.get("plans")[0]["id"] if opt_data.get("plans") else None)
    assert plan_id is not None, f"No plan_id returned: {opt_data}"
    log(f"STEP 15-17: CP-SAT Optimization succeeded! Generated Coordinated Block Plan ID={plan_id}")

    # STEP 18, 19, 20, 21: Planner Modifies Plan & validates alternative
    # Negative test first: window with trains 1040-1130 must be INFEASIBLE
    neg_alt = requests.post(f"{BASE_URL}/api/block-plans/{plan_id}/validate-alternative", json={
        "recommended_start_min": 1040,
        "recommended_end_min": 1130
    }, headers=planner_headers).json()
    assert neg_alt["is_feasible"] is False
    assert neg_alt["conflicts_count"] > 0
    log(f"STEP 18 (Negative Validation): Correctly flagged infeasible window 1040-1130m with {neg_alt['conflicts_count']} train conflicts")

    # Dynamic feasible alternative selection from system recommendations
    assert len(neg_alt.get("recommended_alternatives", [])) > 0, "No recommended alternatives returned by system"
    alt_cand = next((a for a in neg_alt["recommended_alternatives"] if a["usable_duration_min"] >= 90), neg_alt["recommended_alternatives"][0])
    alt_start = alt_cand["start_min"]
    alt_end = alt_start + 90

    val_alt = requests.post(f"{BASE_URL}/api/block-plans/{plan_id}/validate-alternative", json={
        "recommended_start_min": alt_start,
        "recommended_end_min": alt_end
    }, headers=planner_headers).json()
    assert val_alt["is_feasible"] is True
    assert val_alt["conflicts_count"] == 0
    log(f"STEP 19-20 (Feasible Validation): Validated conflict-free recommended alternative window: {alt_cand.get('window_code', 'ALT')} ({alt_start}-{alt_end}m)")

    mod_res = requests.post(f"{BASE_URL}/api/block-plans/{plan_id}/modification", json={
        "action": "MODIFY",
        "recommended_start_min": alt_start,
        "recommended_end_min": alt_end,
        "reason": "Chief Controller shift adjustment for optimal freight corridor flow"
    }, headers=planner_headers)
    assert mod_res.status_code == 200, f"Modify proposal failed: {mod_res.text}"
    mod_data = mod_res.json()
    assert mod_data["status"] == "MODIFICATION_REQUESTED"
    log(f"STEP 21: Sent modification proposal to departments. Plan status={mod_data['status']}")

    # STEP 22-24: Engineering accepts modification
    engg_mods = requests.get(f"{BASE_URL}/api/department/modifications", headers=engg_headers).json()
    engg_prop = next(m for m in engg_mods if m.get("block_plan_id") == plan_id)
    acc_engg = requests.post(f"{BASE_URL}/api/modifications/{engg_prop['id']}/accept", json={"remarks": "Civil engg accepted timing"}, headers=engg_headers)
    assert acc_engg.status_code == 200
    log("STEP 22-24: Engineering accepted modification proposal")

    # STEP 25-26: S&T accepts modification
    snt_mods = requests.get(f"{BASE_URL}/api/department/modifications", headers=snt_headers).json()
    snt_prop = next(m for m in snt_mods if m.get("block_plan_id") == plan_id)
    acc_snt = requests.post(f"{BASE_URL}/api/modifications/{snt_prop['id']}/accept", json={"remarks": "S&T accepted timing"}, headers=snt_headers)
    assert acc_snt.status_code == 200
    log("STEP 25-26: S&T accepted modification proposal")

    # STEP 27-28: TRD accepts modification
    trd_mods = requests.get(f"{BASE_URL}/api/department/modifications", headers=trd_headers).json()
    trd_prop = next(m for m in trd_mods if m.get("block_plan_id") == plan_id)
    acc_trd = requests.post(f"{BASE_URL}/api/modifications/{trd_prop['id']}/accept", json={"remarks": "TRD accepted timing"}, headers=trd_headers)
    assert acc_trd.status_code == 200
    log("STEP 27-28: TRD accepted modification proposal")

    # STEP 29-30: Planner checks department response breakdown
    breakdown_res = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers)
    assert breakdown_res.status_code == 200
    bd_data = breakdown_res.json()
    assert bd_data["overall_status"] == "ALL_DEPARTMENTS_ACCEPTED"
    assert len(bd_data["proposals"]) == 3
    assert all(p["status"] == "ACCEPTED" for p in bd_data["proposals"])
    log(f"STEP 29-30: Planner verified ALL 3 departments accepted (overall_status={bd_data['overall_status']})")

    # STEP 31-32: Planner approves final block plan
    appr_res = requests.post(f"{BASE_URL}/api/coordinated-block-plans/{plan_id}/approve", json={
        "action": "APPROVE",
        "reason": "All departments agreed; authorized final possession by Chief Section Controller"
    }, headers=planner_headers)
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "APPROVED"
    log(f"STEP 31-32: Final block plan APPROVED! Status={appr_data['status']}")

    # STEP 33-35: Live train position & telemetry
    health_res = requests.get(f"{BASE_URL}/api/live/health", headers=planner_headers)
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert "status" in health_data

    live_res = requests.get(f"{BASE_URL}/api/live/corridors/CORR_C40_MDU_TEN", headers=planner_headers)
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert "trains" in live_data
    log(f"STEP 33-35: Live Train Position verified! Telemetry health: {health_data['status']}, Candidate trains on C40: {len(live_data['trains'])}")

    # STEP 36-39: Dynamic replanning
    replan_res = requests.post(f"{BASE_URL}/api/coordinated-block-plans/{plan_id}/replan", json={
        "reason": "Upstream delay on Train 12689 requiring common block possession adjustment"
    }, headers=planner_headers)
    assert replan_res.status_code == 200
    replan_data = replan_res.json()
    assert replan_data["status"] == "REPLANNED"
    assert "revised_window" in replan_data
    log(f"STEP 36-39: Dynamic Replanning completed! Shifted window: {replan_data['original_window']} -> {replan_data['revised_window']}, Status={replan_data['status']}")

    # STEP 40-41: Reports
    weekly_res = requests.get(f"{BASE_URL}/api/reports/weekly", headers=planner_headers)
    assert weekly_res.status_code == 200
    weekly_report = weekly_res.json()
    assert "total_jobs_demanded" in weekly_report or "total_demanded" in weekly_report or "summary" in weekly_report or len(weekly_report) > 0
    log(f"STEP 40-41: Reports verified! Weekly summary keys: {list(weekly_report.keys()) if isinstance(weekly_report, dict) else len(weekly_report)}")

    # STEP 42-43: Audit Trail
    audit_res = requests.get(f"{BASE_URL}/api/reports/audit", headers=planner_headers)
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) >= 2
    log(f"STEP 42-43: Audit Trail verified! Total audit log events in DB: {len(audits)}")

    log("=== FULL 43-STEP GOLDEN PATH COMPLETED WITH 100% SUCCESS ===")

if __name__ == "__main__":
    main()
