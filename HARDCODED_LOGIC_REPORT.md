# HARDCODED / FAKE LOGIC AUDIT REPORT
## SIH26027 — AI-Powered Automatic Block Planning System (IR-ABPS)
**Audit Date:** 2026-09-22  
**Scope:** Complete Codebase Audit for Fake Data, Hardcoded Heuristics, Synthetic Scores, and Mock Fallbacks  

---

## 1. Executive Summary

This report catalogues all occurrences of hardcoded coordinates, synthetic scores, static optimization metrics, fake replanning, dummy what-if calculations, and universal 24-hour window fallbacks.

Every instance is classified into:
- **LEGITIMATE_CONFIGURATION**: Valid operational parameter (e.g. standard safety buffer, timeout).
- **DEMO_DATA**: Explicit fixtures for development or offline demonstration.
- **LOGIC_DEFECT_MUST_REMOVE**: Deceptive or hardcoded heuristic that bypasses real mathematical optimization or falsifies railway data.

---

## 2. Hardcoded & Fake Logic Itemization

| Item # | File | Line | Current Behavior | Classification | Action Required |
|---|---|---|---|---|---|
| **HK-01** | `backend/app/algorithms/coordination.py` | 400 | `plan_a_score = 96.0` hardcoded static score | LOGIC_DEFECT_MUST_REMOVE | Remove. Calculate score from CP-SAT objective function. |
| **HK-02** | `backend/app/algorithms/coordination.py` | 403 | `plan_b_start = max(780, win_start + 135)` arbitrary time shift (+135 min) | LOGIC_DEFECT_MUST_REMOVE | Remove. Derive Plan B from next feasible sweep-line window. |
| **HK-03** | `backend/app/algorithms/coordination.py` | 406 | `plan_b_score = 89.0` hardcoded static score | LOGIC_DEFECT_MUST_REMOVE | Remove. Compute actual objective evaluation for Plan B. |
| **HK-04** | `backend/app/algorithms/coordination.py` | 409 | `plan_c_score = 72.0` hardcoded static score | LOGIC_DEFECT_MUST_REMOVE | Remove. Compute actual uncoordinated multi-block score. |
| **HK-05** | `backend/app/algorithms/coordination.py` | 410 | `plan_c_time = "Separate staggered blocks (10:00–11:30, 12:30–13:30, 14:00–15:15)"` hardcoded string | LOGIC_DEFECT_MUST_REMOVE | Remove. Generate genuine time breakdown for individual possessions. |
| **HK-06** | `backend/app/algorithms/coordination.py` | 450 | `block_utilization_pct = 100.0` hardcoded | LOGIC_DEFECT_MUST_REMOVE | Remove. Calculate: $(\sum \text{job duration} / \text{window duration}) \times 100$. |
| **HK-07** | `backend/app/algorithms/coordination.py` | 466 | `block_utilization_pct = 92.0` hardcoded | LOGIC_DEFECT_MUST_REMOVE | Remove. Calculate dynamically from Plan B window allocation. |
| **HK-08** | `backend/app/algorithms/coordination.py` | 711-715 | `default_section_starts = {"SECTION-103": 645, "SECTION-204": 780, "SECTION-305": 900}` hardcoded section start times | LOGIC_DEFECT_MUST_REMOVE | Remove. Allocate start time based on verified available windows from `WindowEngine`. |
| **HK-09** | `backend/app/routers/block_requests.py` | 594-606 | Single-job optimization uses fixed score formula `plan_a_score = job.priority_score + 12.0`, `plan_b_score = plan_a_score - 6.0`, `plan_c_score = plan_b_score - 7.0` | LOGIC_DEFECT_MUST_REMOVE | Remove. Compute authentic scores from constraint satisfaction metrics. |
| **HK-10** | `backend/app/routers/block_requests.py` | 597 | `plan_b_start = max(780, win_start + 135)` arbitrary time shift | LOGIC_DEFECT_MUST_REMOVE | Remove. Derive from genuine alternative window. |
| **HK-11** | `backend/app/routers/block_requests.py` | 603 | `plan_c_start = max(930, plan_b_start + 150)` arbitrary time shift | LOGIC_DEFECT_MUST_REMOVE | Remove. Derive from genuine alternative window. |
| **HK-12** | `backend/app/routers/block_requests.py` | 626, 637, 648 | `utilization_pct: 91.0`, `utilization_pct: 84.0`, `utilization_pct: 78.0` hardcoded | LOGIC_DEFECT_MUST_REMOVE | Remove. Calculate mathematically. |
| **HK-13** | `backend/app/routers/block_requests.py` | 1540-1554 | What-If simulation simply shifts start time by perturbation value (`new_start = orig_start + shift`) | LOGIC_DEFECT_MUST_REMOVE | Remove. Invoke `WhatIfService` to run sandboxed CP-SAT. |
| **HK-14** | `backend/app/routers/block_requests.py` | 1583 | `score = max(70.0, plan.objective_score - 3.0)` fake What-If score reduction | LOGIC_DEFECT_MUST_REMOVE | Remove. Compute actual solver score from perturbed run. |
| **HK-15** | `backend/app/routers/block_requests.py` | 1581 | `hard_conflicts = 0`, `feasibility = "FEASIBLE"` unconditionally returned | LOGIC_DEFECT_MUST_REMOVE | Remove. Perform real conflict check against perturbed train paths. |
| **HK-16** | `backend/app/routers/block_requests.py` | 1624-1626 | Dynamic replanning simply adds 45 minutes (`new_start = plan.start_min + 45`) without re-solving | LOGIC_DEFECT_MUST_REMOVE | Remove. Must call `DynamicReplanningEngine.re_optimize()` to rerun CP-SAT. |
| **HK-17** | `backend/app/algorithms/windows.py` | 61-62 | Generates `train_before_no: "START_OF_DAY"`, `train_after_no: "END_OF_DAY"`, creating `00:00-24:00` window when no occupancies exist | LOGIC_DEFECT_MUST_REMOVE | Remove. Return `DATA_UNAVAILABLE` unless verified timetable explicitly proves 24h zero traffic. |
| **HK-18** | `backend/app/routers/availability.py` | 137-141 | Fallback to CVP-TEN canonical section when route or section cannot be resolved | LOGIC_DEFECT_MUST_REMOVE | Remove. Must return HTTP 400 Bad Request or `DATA_UNAVAILABLE`. |
| **HK-19** | `backend/app/providers/mock_provider.py` | 18-59 | Hardcoded train positions for Delhi-Kanpur corridor (NDLS, GZB, ALJN, TDL, CNB, PRYJ) | DEMO_DATA | Retain strictly for offline DEV_MOCK mode; clearly label `MODE: DEMO / STATIC`. |
| **HK-20** | `backend/app/providers/mock_provider.py` | 73-75 | Random simulated GPS jitter `(random.random() - 0.5) * 0.002` | DEMO_DATA | Label as simulated jitter; never present as authentic live radar data. |
| **HK-21** | `backend/app/algorithms/priority.py` | 55, 59, 63, 67 | Static base criticality scores: `88.0`, `76.0`, `55.0`, `40.0` from keyword regex | LOGIC_DEFECT_MUST_REMOVE | Refactor to multi-factor asset condition and consequence scoring model. |
| **HK-22** | `backend/app/algorithms/priority.py` | 109, 113, 117, 121 | Static base safety scores: `90.0`, `78.0`, `52.0`, `30.0` from keyword regex | LOGIC_DEFECT_MUST_REMOVE | Refactor to explainable safety sub-factor calculation ($S_1, S_2, S_3$). |
| **HK-23** | `backend/app/services/train_service.py` | 94 | `src_code = str(meta.get("source_code") or meta.get("source") ...)` evaluates to `"RAILRADAR"` | LOGIC_DEFECT_MUST_REMOVE | Fix. Origin station code must be derived from route stops or station code fields. |
| **HK-24** | `backend/app/core/config.py` | 48-49 | `BUFFER_BEFORE_MIN: int = 5`, `BUFFER_AFTER_MIN: int = 5` | LEGITIMATE_CONFIGURATION | Keep as configurable planning safety parameters. |
| **HK-25** | `backend/app/core/config.py` | 50-52 | `PLANNING_HORIZON_HOURS: int = 24`, `SOLVER_TIME_LIMIT_SECONDS: int = 15` | LEGITIMATE_CONFIGURATION | Keep as operational solver parameters. |

---

## 3. Summary of Violations Against Absolute Rules

1. **Absolute Rule**: *Never generate 00:00–24:00 as a generic availability fallback.*
   - **Violation Found**: `windows.py:61-62` defaults to 00:00–24:00 whenever a section has no trains mapped.
2. **Absolute Rule**: *Never allow dynamic replanning to simply change displayed time.*
   - **Violation Found**: `block_requests.py:1624` adds 45 minutes to `plan.start_min` and hardcodes `conflicts_count = 0` without invoking CP-SAT.
3. **Absolute Rule**: *Never generate fake optimization results.*
   - **Violation Found**: `coordination.py:400-470` assigns arbitrary static numbers (96.0, 89.0, 72.0) and fixed utilization percentages.
4. **Absolute Rule**: *Every critical calculation must be explainable.*
   - **Violation Found**: Priority sub-factors (75 criticality, 78 safety) are magic numbers generated by regex instead of explainable equations.
