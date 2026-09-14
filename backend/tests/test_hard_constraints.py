import pytest
from app.algorithms.optimizer import CPSATSolver
from app.algorithms.validator import DeterministicSafetyValidator
from app.algorithms.priority import PriorityEngine
from app.algorithms.replanning import DynamicReplanningEngine


# ----------------------------------------------------
# TEST 1: Maintenance overlaps train -> Expected: REJECT / INVALID
# ----------------------------------------------------
def test_hard_constraint_train_overlap_rejection():
    # Job scheduled 600-660 (10:00-11:00) on Section 2
    scheduled_jobs = [
        {"job_id": 101, "job_code": "E101", "section_id": 2, "scheduled_start_min": 600, "scheduled_end_min": 660, "scheduled_duration_min": 60, "is_scheduled": True}
    ]
    windows = [{"id": 1, "section_id": 2, "start_min": 500, "end_min": 800, "usable_duration_min": 300}]
    # Train occupies 630-650 (10:30-10:50) on Section 2 (Direct 20-minute overlap)
    occupancies = [
        {"section_id": 2, "train_number": "12919", "estimated_entry_min": 630, "estimated_exit_min": 650}
    ]

    is_valid, errors, warnings = DeterministicSafetyValidator.validate_plan(
        scheduled_jobs=scheduled_jobs,
        windows=windows,
        occupancies=occupancies
    )
    assert is_valid is False
    assert any("overlaps Train" in err for err in errors)


# ----------------------------------------------------
# TEST 2: Maintenance duration > available window -> Expected: REJECT
# ----------------------------------------------------
def test_hard_constraint_duration_exceeds_window():
    # Job requires 90 min, but window only has 60 min
    jobs = [
        {"id": 102, "job_code": "E102", "section_id": 1, "estimated_duration_min": 90, "priority_score": 80.0, "is_emergency": False}
    ]
    windows = [
        {"id": 1, "section_id": 1, "start_min": 600, "end_min": 660, "usable_duration_min": 60}
    ]

    solver = CPSATSolver(time_limit_seconds=5)
    res = solver.solve(jobs=jobs, windows=windows)
    # The solver must NOT assign the job to this insufficient window
    assert len(res["scheduled_jobs"]) == 0
    assert 102 in res["deferred_jobs"]


# ----------------------------------------------------
# TEST 3: Resource conflict -> Expected: REJECT concurrent assignment exceeding capacity
# ----------------------------------------------------
def test_hard_constraint_resource_conflict():
    scheduled_jobs = [
        {"job_id": 1, "job_code": "E101", "section_id": 1, "window_id": 1, "scheduled_start_min": 600, "scheduled_end_min": 660, "scheduled_duration_min": 60, "is_scheduled": True, "assigned_resource_ids": [10]},
        {"job_id": 2, "job_code": "E104", "section_id": 2, "window_id": 2, "scheduled_start_min": 610, "scheduled_end_min": 670, "scheduled_duration_min": 60, "is_scheduled": True, "assigned_resource_ids": [10]}
    ]
    windows = [
        {"id": 1, "section_id": 1, "start_min": 500, "end_min": 800, "usable_duration_min": 300},
        {"id": 2, "section_id": 2, "start_min": 500, "end_min": 800, "usable_duration_min": 300}
    ]
    # Only 1 Tamping machine available
    resources = [{"id": 10, "name": "CSM_TAMP_01", "total_quantity": 1}]

    is_valid, errors, _ = DeterministicSafetyValidator.validate_plan(
        scheduled_jobs=scheduled_jobs,
        windows=windows,
        occupancies=[],
        resources=resources
    )
    assert is_valid is False
    assert any("RESOURCE OVERALLOCATION" in err for err in errors)


# ----------------------------------------------------
# TEST 4: Two compatible jobs fit in one block -> Expected: COORDINATION POSSIBLE
# ----------------------------------------------------
def test_compatible_jobs_coordination():
    jobs = [
        {"id": 1, "job_code": "E101", "section_id": 2, "estimated_duration_min": 60, "priority_score": 85.0, "is_emergency": False},
        {"id": 2, "job_code": "S201", "section_id": 2, "estimated_duration_min": 30, "priority_score": 80.0, "is_emergency": False}
    ]
    # Window of 100 minutes (enough for 60 + 30 = 90 min)
    windows = [
        {"id": 1, "section_id": 2, "start_min": 600, "end_min": 700, "usable_duration_min": 100}
    ]

    solver = CPSATSolver(time_limit_seconds=5)
    res = solver.solve(jobs=jobs, windows=windows, strategy="PLAN_A")
    assert res["total_jobs_completed"] == 2
    assert len(res["blocks"]) == 1  # Packed into 1 coordinated block


# ----------------------------------------------------
# TEST 5: Emergency job -> Expected: Higher scheduling priority (Tier 1)
# ----------------------------------------------------
def test_emergency_job_priority():
    score_em, tier_em, _ = PriorityEngine.calculate_priority(criticality=50, urgency=50, overdue_days=0, safety_impact=50, operational_impact=50, is_emergency=True)
    score_norm, tier_norm, _ = PriorityEngine.calculate_priority(criticality=80, urgency=70, overdue_days=1, safety_impact=70, operational_impact=60, is_emergency=False)

    assert "Tier 1" in tier_em
    assert score_em >= 95.0


# ----------------------------------------------------
# TEST 6: Train delay -> Expected: Dynamic re-planning resolves conflict
# ----------------------------------------------------
def test_dynamic_replanning_on_train_delay():
    # Original scheduled job 600-660
    current_pjs = [
        {"job_id": 1, "job_code": "E101", "scheduled_start_min": 600, "scheduled_end_min": 660, "window_id": 1, "is_scheduled": True, "execution_status": "PENDING"}
    ]
    jobs = [
        {"id": 1, "job_code": "E101", "section_id": 2, "estimated_duration_min": 60, "priority_score": 85.0, "status": "SCHEDULED"}
    ]
    # Due to delay, window 1 is shifted to 700-780
    new_windows = [
        {"id": 1, "section_id": 2, "start_min": 700, "end_min": 780, "usable_duration_min": 80}
    ]
    new_occs = [
        {"section_id": 2, "train_number": "12919", "estimated_entry_min": 620, "estimated_exit_min": 680}
    ]

    replan = DynamicReplanningEngine.re_optimize(
        current_plan_jobs=current_pjs,
        jobs=jobs,
        new_windows=new_windows,
        new_occupancies=new_occs,
        trigger_event="TRAIN_DELAY"
    )

    assert replan["is_valid"] is True
    assert replan["total_jobs_completed"] == 1
    # Scheduled start should have shifted to >= 700
    assert replan["scheduled_jobs"][0]["scheduled_start_min"] >= 700


# ----------------------------------------------------
# TEST 7: Completed job -> Expected: Cannot move / fixed
# ----------------------------------------------------
def test_completed_job_immutability():
    current_pjs = [
        {"job_id": 1, "job_code": "E101", "scheduled_start_min": 600, "scheduled_end_min": 660, "window_id": 1, "is_scheduled": True, "execution_status": "COMPLETED"}
    ]
    jobs = [
        {"id": 1, "job_code": "E101", "section_id": 2, "estimated_duration_min": 60, "priority_score": 85.0, "status": "COMPLETED"}
    ]
    windows = [
        {"id": 1, "section_id": 2, "start_min": 600, "end_min": 750, "usable_duration_min": 150}
    ]
    replan = DynamicReplanningEngine.re_optimize(
        current_plan_jobs=current_pjs,
        jobs=jobs,
        new_windows=windows,
        new_occupancies=[],
        trigger_event="ROUTINE"
    )
    # Start time must remain locked at 600
    assert replan["scheduled_jobs"][0]["scheduled_start_min"] == 600


# ----------------------------------------------------
# TEST 8: Locked job -> Expected: Remains fixed
# ----------------------------------------------------
def test_locked_job_preservation():
    jobs = [
        {"id": 1, "job_code": "E101", "section_id": 2, "estimated_duration_min": 60, "priority_score": 85.0, "is_locked": True, "locked_start_min": 650}
    ]
    windows = [
        {"id": 1, "section_id": 2, "start_min": 600, "end_min": 750, "usable_duration_min": 150}
    ]
    solver = CPSATSolver(time_limit_seconds=5)
    res = solver.solve(jobs=jobs, windows=windows, enforce_locks=True)
    assert res["scheduled_jobs"][0]["scheduled_start_min"] == 650


# ----------------------------------------------------
# TEST 9: No feasible plan -> Expected: Clear explanation
# ----------------------------------------------------
def test_no_feasible_plan_handling():
    # Job duration 120 min, but no windows available on section 3
    jobs = [
        {"id": 1, "job_code": "E103", "section_id": 3, "estimated_duration_min": 120, "priority_score": 75.0}
    ]
    windows = [
        {"id": 1, "section_id": 1, "start_min": 600, "end_min": 700, "usable_duration_min": 100}
    ]
    solver = CPSATSolver(time_limit_seconds=5)
    res = solver.solve(jobs=jobs, windows=windows)
    assert len(res["scheduled_jobs"]) == 0
    assert 1 in res["deferred_jobs"]
    assert res["total_jobs_completed"] == 0
