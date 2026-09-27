"""
End-to-End Test for Planner Modify Alternative Time -> Department Approval Workflow
Tests all 5 key requirements:
1. Feasibility check prior to propose (both conflict detection and feasible pass)
2. Proposal creation without overwriting original requested times
3. Department receipt and viewing of original vs proposed
4. Rejection preservation of original times and plan routing
5. Multi-department coordinated acceptance and final plan updating
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from app.db.session import SessionLocal
from app.models.models import MaintenanceJob, CoordinatedBlockPlan, PlanModificationProposal

BASE_URL = "http://localhost:8000"

def login(username, password=None):
    passwords = {
        "planner": "planner123",
        "engg_user": "engg123",
        "snt_user": "snt123",
        "trd_user": "trd123",
        "admin": "admin123"
    }
    pwd = password or passwords.get(username, "password123")
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": pwd})
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print(f"  [AUTH] Logged in as {username}")
        return {"Authorization": f"Bearer {token}"}
    raise Exception(f"Failed to login as {username}: {resp.status_code} {resp.text}")

def main():
    print("=" * 70)
    print("TESTING PLANNER MODIFY -> DEPARTMENT APPROVAL WORKFLOW")
    print("=" * 70)

    # 1. Login as planner
    print("\n1. Authenticating as Planner...")
    planner_headers = login("planner")

    # 2. Check Plan 664
    plan_id = 664

    # 0. Initialize baseline test state for Plan 664 & Requests 1, 2, 3
    print("\n0. Initializing baseline test state for Plan 664...")
    db = SessionLocal()
    db.query(PlanModificationProposal).filter(PlanModificationProposal.block_plan_id == plan_id).delete()
    plan_rec = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == plan_id).first()
    if plan_rec:
        plan_rec.status = "PROPOSED"
        plan_rec.start_min = 367
        plan_rec.end_min = 455
        plan_rec.duration_min = 88
    for j_id in [1, 2, 3]:
        j = db.query(MaintenanceJob).filter(MaintenanceJob.id == j_id).first()
        if j:
            j.preferred_start_min = 367
            j.preferred_end_min = 455
            j.status = "RECOMMENDED"
    db.commit()
    db.close()
    print("   Baseline test state initialized successfully.")

    # 2a. Test Infeasible Validation Check
    print(f"\n2a. Validating INFEASIBLE window for Plan {plan_id} (08:00 - 09:30, mins 480-570)...")
    val_resp_inf = requests.post(
        f"{BASE_URL}/api/block-plans/{plan_id}/validate-alternative",
        json={"start_min": 480, "end_min": 570},
        headers=planner_headers
    )
    assert val_resp_inf.status_code == 200
    val_data_inf = val_resp_inf.json()
    print(f"   is_feasible: {val_data_inf.get('is_feasible')}, conflicts: {val_data_inf.get('conflicts_count')}")
    assert val_data_inf.get("is_feasible") is False, "Expected infeasible window due to train conflict"
    print("   [PASS] Infeasible window correctly flagged prior to proposing!")

    # 2b. Attempt to propose infeasible window -> Should be rejected with 400
    print("\n2b. Attempting to propose infeasible window...")
    inf_prop_resp = requests.post(
        f"{BASE_URL}/api/block-plans/{plan_id}/modification",
        json={
            "reason": "Test infeasible propose",
            "recommended_start_min": 480,
            "recommended_end_min": 570
        },
        headers=planner_headers
    )
    print(f"   Status code: {inf_prop_resp.status_code}")
    assert inf_prop_resp.status_code == 400
    print(f"   Conflict message: {inf_prop_resp.json().get('detail')}")
    print("   [PASS] System successfully blocked proposing conflicted window!")

    # 2c. Test Feasible Validation Check
    print(f"\n2c. Validating FEASIBLE window for Plan {plan_id} (13:40 - 15:10, mins 820-910)...")
    val_resp_feas = requests.post(
        f"{BASE_URL}/api/block-plans/{plan_id}/validate-alternative",
        json={"start_min": 820, "end_min": 910},
        headers=planner_headers
    )
    assert val_resp_feas.status_code == 200
    val_data_feas = val_resp_feas.json()
    print(f"   is_feasible: {val_data_feas.get('is_feasible')}, message: {val_data_feas.get('message')}")
    assert val_data_feas.get("is_feasible") is True, "Expected feasible window"
    print("   [PASS] Feasible window validated!")

    # 3. Propose Modification with Feasible Window
    print(f"\n3. Proposing modification for Plan {plan_id} (mins 820-910)...")
    prop_resp = requests.post(
        f"{BASE_URL}/api/block-plans/{plan_id}/modification",
        json={
            "reason": "Track tamping machine repositioning for Vande Bharat precedence",
            "recommended_start_min": 820,
            "recommended_end_min": 910
        },
        headers=planner_headers
    )
    print(f"   Status Code: {prop_resp.status_code}")
    assert prop_resp.status_code == 200, f"Propose modification failed: {prop_resp.text}"
    prop_data = prop_resp.json()
    proposals = prop_data.get("proposals", [])
    print(f"   Created {len(proposals)} proposal(s):")
    for p in proposals:
        print(f"     - Proposal #{p['id']}: Dept={p['department_code']}, Req={p['request_code']}, Status={p['status']}, Proposed={p['proposed_time_window']}")

    # Verify original times are preserved in database
    db = SessionLocal()
    req1 = db.query(MaintenanceJob).filter(MaintenanceJob.id == 1).first()
    print(f"   [DB VERIFICATION] Request 1 preferred times: {req1.preferred_start_min} - {req1.preferred_end_min}")
    assert req1.preferred_start_min == 367 and req1.preferred_end_min == 455, "CRITICAL: Original requested times were overwritten prematurely!"
    db.close()
    print("   [PASS] Original requested times are strictly preserved in DB!")

    # 4. Check Block Plan summary
    print(f"\n4. Checking modifications breakdown on Plan {plan_id}...")
    summary_resp = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers)
    summary = summary_resp.json()
    print(f"   Summary: {summary}")
    assert summary["overall_status"] == "WAITING_FOR_RESPONSES"
    print("   [PASS] Plan overall status is WAITING_FOR_RESPONSES")

    # 5. Login as ENGG department user & check proposals
    print("\n5. Department Review: Logging in as engg_user...")
    engg_headers = login("engg_user")
    engg_mod_resp = requests.get(f"{BASE_URL}/api/department/modifications", headers=engg_headers)
    engg_proposals = engg_mod_resp.json()
    print(f"   ENGG user received {len(engg_proposals)} pending proposal(s)")
    engg_prop = next((p for p in engg_proposals if p["block_plan_id"] == plan_id and p["department_code"] == "ENGG"), None)
    assert engg_prop is not None, "ENGG proposal not found in department inbox!"
    print(f"   ENGG proposal #{engg_prop['id']}: Orig={engg_prop['original_time_window']}, Proposed={engg_prop['proposed_time_window']}, Reason='{engg_prop['reason']}'")

    # 6. Test Rejection Flow with S&T
    print("\n6. Testing Rejection Flow: Logging in as snt_user...")
    snt_headers = login("snt_user")
    snt_mod_resp = requests.get(f"{BASE_URL}/api/department/modifications", headers=snt_headers)
    snt_proposals = snt_mod_resp.json()
    snt_prop = next((p for p in snt_proposals if p["block_plan_id"] == plan_id and p["department_code"] == "SNT"), None)
    assert snt_prop is not None, "SNT proposal not found in department inbox!"

    print(f"   SNT rejecting proposal #{snt_prop['id']}...")
    snt_rej_resp = requests.post(
        f"{BASE_URL}/api/modifications/{snt_prop['id']}/reject",
        json={"remarks": "Point machine gang unavailable at 13:40 hrs"},
        headers=snt_headers
    )
    print(f"   Status Code: {snt_rej_resp.status_code}")
    assert snt_rej_resp.status_code == 200, f"Rejection failed: {snt_rej_resp.text}"

    # Check overall status after rejection
    summary_resp = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers)
    assert summary_resp.json()["overall_status"] == "MODIFICATION_REJECTED"
    print("   [PASS] Overall plan status transitioned to MODIFICATION_REJECTED upon rejection!")

    # Verify original times still preserved
    db = SessionLocal()
    req2 = db.query(MaintenanceJob).filter(MaintenanceJob.id == 2).first()
    assert req2.preferred_start_min == 367 and req2.preferred_end_min == 455, "Original times modified upon rejection!"
    db.close()
    print("   [PASS] Original requested times remain untouched after rejection!")

    # 7. Testing Full Multi-Department Acceptance Flow
    print("\n7. Proposing revised window (mins 1045-1135, 17:25-18:55) for Multi-Department Acceptance Test...")
    prop_resp2 = requests.post(
        f"{BASE_URL}/api/block-plans/{plan_id}/modification",
        json={
            "reason": "Rescheduled to evening window 17:25-18:55 per S&T shift alignment",
            "recommended_start_min": 1045,
            "recommended_end_min": 1135
        },
        headers=planner_headers
    )
    assert prop_resp2.status_code == 200
    props2 = prop_resp2.json()["proposals"]
    engg_p2 = next(p for p in props2 if p["department_code"] == "ENGG")
    snt_p2 = next(p for p in props2 if p["department_code"] == "SNT")
    trd_p2 = next(p for p in props2 if p["department_code"] == "TRD")

    # Step 7a: ENGG accepts
    print(f"   Step 7a: ENGG accepting proposal #{engg_p2['id']}...")
    engg_acc = requests.post(
        f"{BASE_URL}/api/modifications/{engg_p2['id']}/accept",
        json={"remarks": "Track gang ready for 17:25 start"},
        headers=engg_headers
    )
    assert engg_acc.status_code == 200
    print(f"     ENGG response: status={engg_acc.json()['status']}")
    assert engg_acc.json()["status"] == "ACCEPTED"
    sum_mid1 = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers).json()
    assert sum_mid1["overall_status"] == "WAITING_FOR_RESPONSES"
    print("     [PASS] Plan remains WAITING_FOR_RESPONSES (independent multi-dept tracking)")

    # Step 7b: SNT accepts
    print(f"   Step 7b: SNT accepting proposal #{snt_p2['id']}...")
    snt_acc = requests.post(
        f"{BASE_URL}/api/modifications/{snt_p2['id']}/accept",
        json={"remarks": "Signal technician shift aligned"},
        headers=snt_headers
    )
    assert snt_acc.status_code == 200
    assert snt_acc.json()["status"] == "ACCEPTED"
    sum_mid2 = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers).json()
    assert sum_mid2["overall_status"] == "WAITING_FOR_RESPONSES"
    print("     [PASS] Plan still WAITING_FOR_RESPONSES pending TRD")

    # Step 7c: TRD accepts
    print("\n   Step 7c: Logging in as trd_user and accepting proposal...")
    trd_headers = login("trd_user")
    trd_acc = requests.post(
        f"{BASE_URL}/api/modifications/{trd_p2['id']}/accept",
        json={"remarks": "Tower wagon power block granted for 17:25-18:55"},
        headers=trd_headers
    )
    assert trd_acc.status_code == 200
    assert trd_acc.json()["status"] == "ACCEPTED"
    sum_final = requests.get(f"{BASE_URL}/api/block-plans/{plan_id}/modifications", headers=planner_headers).json()
    print(f"     TRD response: status={trd_acc.json()['status']}, overall_status={sum_final['overall_status']}")
    assert sum_final["overall_status"] == "ALL_DEPARTMENTS_ACCEPTED"
    print("     [PASS] ALL DEPARTMENTS ACCEPTED! Block plan advanced to ALL_DEPARTMENTS_ACCEPTED!")

    # Verify that now (and ONLY now) the requests and block plan timings are updated
    db = SessionLocal()
    plan_obj = db.query(CoordinatedBlockPlan).filter(CoordinatedBlockPlan.id == plan_id).first()
    r1 = db.query(MaintenanceJob).filter(MaintenanceJob.id == 1).first()
    r2 = db.query(MaintenanceJob).filter(MaintenanceJob.id == 2).first()
    r3 = db.query(MaintenanceJob).filter(MaintenanceJob.id == 3).first()
    print(f"\n   [DB VERIFICATION]")
    print(f"     Block Plan {plan_id} Window: {plan_obj.start_min} - {plan_obj.end_min} (Status: {plan_obj.status})")
    print(f"     REQ-101 Window: {r1.preferred_start_min} - {r1.preferred_end_min}")
    print(f"     REQ-102 Window: {r2.preferred_start_min} - {r2.preferred_end_min}")
    print(f"     REQ-103 Window: {r3.preferred_start_min} - {r3.preferred_end_min}")
    assert plan_obj.start_min == 1045 and plan_obj.end_min == 1135
    assert r1.preferred_start_min == 1045 and r1.preferred_end_min == 1135
    assert r2.preferred_start_min == 1045 and r2.preferred_end_min == 1135
    assert r3.preferred_start_min == 1045 and r3.preferred_end_min == 1135
    db.close()
    print("   [PASS] All requests and block plan updated correctly upon complete acceptance!")

    print("\n" + "=" * 70)
    print("ALL 5 WORKFLOW TESTS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
