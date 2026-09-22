# SYSTEM AUDIT REPORT
## SIH26027 — AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways
**Audit Date:** 2026-09-22  
**Audit Scope:** Complete Full-Stack Production-Readiness, Architecture, Algorithmic Integrity, Safety, and Data Quality Audit  
**Audit Status:** AUDIT COMPLETE — CRITICAL VULNERABILITIES & LOGIC DEFECTS IDENTIFIED  

---

## 1. Executive Summary

A comprehensive production-readiness audit of the **AI-Powered Automatic Block Planning System (IR-ABPS)** was conducted across frontend, backend, database, optimization engines, railway master datasets, real-time telemetry providers, and operational workflows.

The system features a clean CRIS-inspired UI, deterministic safety validation routines, and real mathematical foundations (e.g. Google OR-Tools CP-SAT integration in `backend/app/algorithms/optimizer.py`). However, **the system in its current state CANNOT be certified as production-ready or pilot-ready for Indian Railways**. 

Critical audit findings include:
1. **Optimization Bypass in Primary Workflow**: The primary coordinated block planning endpoints (`/block-requests/coordination/optimize`, `/block-requests/pool/optimize`, and `/block-requests/{id}/optimize`) completely bypass Google OR-Tools CP-SAT and return hardcoded scores (e.g. `plan_a_score = 96.0`, `plan_b_score = 89.0`), fixed time shifts (`+135 min`, `+150 min`), and dummy block utilization percentages (`91.0%`, `84.0%`, `78.0%`).
2. **Fake Dynamic Replanning**: When disturbances or train delays occur, `/coordinated-plans/{id}/replan` simply adds 45 minutes to `start_min` without recalculating section occupancy or rerunning the CP-SAT solver.
3. **Fake What-If Simulation**: The coordinated what-if endpoint adds arbitrary offsets to start times and hardcodes `conflicts: 0, feasibility: FEASIBLE, score: plan.score - 3.0` without evaluating railway physics or timetable feasibility.
4. **Universal 00:00–24:00 Window Flaw**: In `WindowEngine.calculate_feasible_windows()`, when static timetable data is loaded but a section has no trains mapped in that window, it generates a synthetic window from `00:00` to `24:00` (`START_OF_DAY` to `END_OF_DAY`), falsely indicating unconditional 24-hour line possession availability.
5. **Station Code Corruption**: In `TrainService`, train origin station codes were corrupted to `"RAILRADAR"` due to an ambiguous dictionary lookup key `meta.get("source")`.
6. **Corridor Layer Impurities**: The database contains 10 legacy generic corridor records (`CORR_MAS_TPJ`, `CORR_DLI_DDU`, etc.) without prototype codes, with 48 railway sections mapped to them, violating the strict Southern Railway C01–C46 canonical boundary.
7. **Unexplained Scoring**: Criticality and Safety Impact scores rely on coarse keyword regex matching with static magic numbers (e.g., 76, 78, 88) rather than multi-attribute asset condition and operational consequence formulations.
8. **Missing Concurrency Protection**: No optimistic locking or version checks exist on `CoordinatedBlockPlan`, enabling silent overwrites between concurrent railway controllers.

---

## 2. Current Architecture

The system is organized into a decoupled 3-tier architecture:
- **Presentation Tier**: React 18 SPA built with Vite, TailwindCSS, Lucide-react, React-Leaflet GIS mapping, and custom SVG Gantt/Time-Distance visualizers.
- **Application Tier**: FastAPI (Python 3.11) with modular routing (`/api/v1` and direct REST aliases), Pydantic v2 data transfer schemas, and SQLAlchemy 2.0 ORM.
- **Persistence Tier**: SQLite database (`abps.db`) for development/prototyping, with SQLAlchemy models structured for PostgreSQL migration.
- **Telemetry Tier**: RailRadar v1 REST API client with local in-memory cache and background polling worker (`live_poller.py`).
- **Optimization Tier**: Google OR-Tools CP-SAT (installed and working in `optimizer.py`), but partially bypassed in `coordination.py`.

```
                    ┌────────────────────────────┐
                    │      React 18 Web UI       │
                    │ (Control Room / Telemetry) │
                    └──────────────┬─────────────┘
                                   │ HTTP/REST (JWT)
                                   ▼
                    ┌────────────────────────────┐
                    │       FastAPI Backend      │
                    │   (/api/v1 Standard REST)  │
                    └──────┬──────────────┬──────┘
                           │              │
             ┌─────────────┴────┐   ┌─────┴───────────────┐
             │  Planning Layer  │   │   Telemetry Layer   │
             │  - WindowEngine  │   │  - RailRadar Client │
             │  - Compatibility │   │  - Timetable Cache  │
             │  - CP-SAT Solver │   │  - Section Occupancy│
             │  - Safety Rules  │   └─────────────────────┘
             └─────────────┬────┘
                           │
             ┌─────────────┴─────────────┐
             │  Database (abps.db)       │
             │  - C01-C46 Master Data    │
             │  - 253 Trains / Timetables│
             │  - 154 Railway Sections   │
             │  - Maintenance Jobs       │
             └───────────────────────────┘
```

---

## 3. Current Data Architecture

The current data model (`backend/app/models/models.py`) consists of 28 tables:
- **Core Organization**: `departments`, `users`
- **Railway Infrastructure Master**: `stations`, `railway_stations` (PDF source), `corridors`, `railway_sections`, `assets`
- **Train Schedules & Movement**: `trains`, `train_route_stops`, `train_routes`, `train_movements`, `train_section_occupancies`, `train_position_snapshots`
- **Maintenance & Demands**: `maintenance_jobs`, `maintenance_dependencies`, `resources`, `maintenance_job_resources`, `block_demands`
- **Block Planning & Windows**: `block_windows`, `block_plans`, `plan_jobs`, `plan_versions`, `coordinated_block_plans`
- **Operations, Simulation & Audit**: `what_if_scenarios`, `execution_records`, `notifications`, `planner_actions`, `audit_logs`, `system_configs`, `api_health_status`

### Key Data Architecture Deficiencies:
- **Dual Plan Entities**: `BlockPlan` (individual CP-SAT plans) and `CoordinatedBlockPlan` (multi-department grouped plans) exist side-by-side with separate lifecycles and schemas, creating architectural redundancy.
- **Single Section ForeignKey**: `MaintenanceJob.section_id` only links to a single section, failing to represent multi-section possession possessions natively (`MaintenanceRequestSection` table is missing).
- **Missing Versioning on Coordinated Plans**: `CoordinatedBlockPlan` lacks a `version` column and optimistic locking token.

---

## 4. Current Railway Data Sources

The repository incorporates authentic Southern Railway and Tamil Nadu datasets:
1. `documents/TN-station list.pdf`: Authoritative Southern Railway Station Master (01.04.2025) parsed by `scripts/import_station_master.py` (500+ stations).
2. `documents/*.xlsx` & `documents/*.csv`: Station-to-station train schedule sheets:
   - `Madurai_to_TVL_train_details.xlsx`
   - `AJJ_to_JTJ_Train_Detailed_Data-6.xlsx`
   - `Chennai_to_Gudur_Detailed_Train_Data-2.xlsx`
   - `Where_Is_My_Train_Detailed_Data.xlsx`
   - `erode_karur_tiruchirappalli_final.csv`
   - `karur_to_dindigul_trains.csv`
   - `salem_namakkal_karur_final.csv`
3. `backend/app/data/railway_network_geometry.json`: Authentic OSM railway track geometry with 33,000+ line coordinates for Southern Railway corridors.
4. Total database records currently loaded:
   - 253 Trains
   - 6,691 Route Stops
   - 1,415 Train Section Routes
   - 11,941 Section Occupancies

---

## 5. Current Live Train Architecture

- **Provider**: RailRadar REST API (`https://api.railradar.in/v1`).
- **Endpoints**: `GET /v1/trains/{number}/live` for real-time telemetry; station boards; train route geometries.
- **Security**: The API key is loaded into backend memory via `settings.RAILRADAR_API_KEY` from `backend/.env`. The key is never returned to the frontend.
- **Resilience**: A background poller (`live_poller.py`) maintains telemetry for candidate trains in Tamil Nadu with a 45-second cache TTL.
- **Fallback**: If `RAILRADAR_API_KEY` is empty, `ConfigErrorProvider` is returned with clean `is_live: false, status: UNAVAILABLE` states.

---

## 6. Current Availability Engine

- Located in `backend/app/algorithms/windows.py` (`WindowEngine`) and exposed via `backend/app/routers/availability.py`.
- Employs a mathematical sweep-line algorithm that merges train occupancy envelopes and computes free intervals after applying safety buffers (`BUFFER_BEFORE_MIN=5`, `BUFFER_AFTER_MIN=5`).
- **Defect Identified**: If timetable data is loaded but zero trains run across a specific section, it yields a 24-hour block (`00:00` to `24:00`, `START_OF_DAY` to `END_OF_DAY`).
- **Defect Identified**: In `availability.py:137`, if route resolution returns no sections, it falls back to a hardcoded CVP-TEN section instead of returning an error or `DATA_UNAVAILABLE`.

---

## 7. Current Priority Engine

- Located in `backend/app/algorithms/priority.py` (`PriorityEngine`).
- Computes composite priority as:
  $$\text{Priority} = 0.30 \times C + 0.20 \times U + 0.15 \times O + 0.20 \times S + 0.15 \times OP$$
- **Defect Identified**: Sub-factors (asset condition score, failure consequence, operational importance, safety consequence, train operation impact, failure severity, mitigation) are NOT saved in structured database columns or exposed in a transparent granular breakdown.
- Base criticality and safety scores are derived from rigid regex keyword checks in `work_type` (e.g. "TAMPING" $\to$ 76/78).

---

## 8. Current Compatibility Engine

- Located in `backend/app/algorithms/coordination.py` (`CompatibilityEngine`).
- Evaluates departmental work types for parallel co-location feasibility using a static matrix `PARALLEL_COMPATIBLE_WORK_TYPES`.
- Verifies common section, date, and corridor boundaries.
- Explains why jobs are grouped or rejected (e.g. date mismatch, geographic mismatch).

---

## 9. Current Optimization Engine

- Real solver: `backend/app/algorithms/optimizer.py` (`CPSATSolver`) using Google OR-Tools CP-SAT with constraints for non-overlapping execution, resource capacity, precedence dependencies, locked jobs, and multi-objective balancing.
- **CRITICAL DEFECT**: `CoordinatedOptimizer` in `coordination.py` and `block_requests.py` bypasses this solver and returns mock heuristics with hardcoded values.

---

## 10. Current Dynamic Replanning

- Intended engine: `backend/app/algorithms/replanning.py` (`DynamicReplanningEngine`), which freezes in-progress jobs and reruns CP-SAT.
- **CRITICAL DEFECT**: The primary endpoint `/coordinated-plans/{id}/replan` simply shifts the start time by 45 minutes without calling `DynamicReplanningEngine`.

---

## 11. Current Security

- **Authentication**: JWT HS256 tokens with 24-hour expiration (`app/core/security.py`).
- **Password Hashing**: Passlib bcrypt.
- **Role Enforcement**: `require_role()` dependency checking `railway_planner`, `admin`, and departmental user roles.
- **CORS**: `backend/.env` has `*` in `CORS_ORIGINS`, which is unsafe for production.
- **Secret Keys**: Default development secret key is stored in `.env`.

---

## 12. Current Error Handling

- Custom exception handlers in `app/main.py`.
- Pydantic validation on API request payloads.
- RailRadar HTTP failure mapping (401, 404, 429, 503, timeout) implemented in `railradar.py` and `live.py`.

---

## 13. Current Testing

- Test suite located in `backend/tests/` with 17 test files and 102 automated tests.
- All 102 tests pass in 36.70s.
- However, existing tests assert the legacy mock behaviors in `block_requests.py` rather than validating end-to-end CP-SAT solver execution for coordinated pools.

---

## 14. Current Deployment Architecture

- Dockerfile in `backend/Dockerfile` using `python:3.11-slim`.
- Root `docker-compose.yml` defining `backend`, `frontend`, and `postgres` services.
- Currently defaulting to SQLite for zero-setup execution.

---

## 15. Critical Problems

### PROBLEM ID: PRB-CRIT-01
- **Severity**: CRITICAL
- **Current Behavior**: `/block-requests/coordination/optimize`, `/block-requests/pool/optimize`, and `/block-requests/{id}/optimize` generate static mock plans with hardcoded scores (`plan_a_score = 96.0`, `plan_b_score = 89.0`, `plan_c_score = 72.0`), static utilization (`91.0%`, `84.0%`, `78.0%`), and fixed time shifts (+135 min).
- **Expected Behavior**: Must invoke Google OR-Tools CP-SAT (`CPSATSolver`), passing actual candidate windows, occupancies, resource limits, and dependencies, and computing mathematical objective scores.
- **Root Cause**: `CoordinatedOptimizer.optimize` and `optimize_single_job` in `coordination.py` bypass `CPSATSolver`.
- **Impact**: Falsifies AI optimization capabilities to railway controllers.
- **Recommended Fix**: Refactor `CoordinatedOptimizer` to pass clustered requests and verified sweep-line windows into `CPSATSolver` and compute metrics from solver variable assignments.
- **Files Affected**: `backend/app/algorithms/coordination.py`, `backend/app/routers/block_requests.py`.
- **Database Impact**: Stores genuine CP-SAT start/end minutes and objective scores in `coordinated_block_plans`.
- **API Impact**: Response reflects genuine solver status (`OPTIMAL`, `FEASIBLE`).
- **Test Required**: Automated CP-SAT pool optimization test with 3+ distinct departmental requests.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-CRIT-02
- **Severity**: CRITICAL
- **Current Behavior**: Dynamic replanning `/coordinated-plans/{id}/replan` adds a flat 45 minutes to `plan.start_min` and hardcodes `conflicts_count = 0`.
- **Expected Behavior**: When a disturbance occurs, the system must update train positions, recalculate section occupancies, freeze completed/active jobs, recalculate future feasible windows via `WindowEngine`, rerun `CPSATSolver`, and produce a revised plan for planner approval.
- **Root Cause**: `replan_coordinated_block_plan` in `block_requests.py` uses hardcoded arithmetic `new_start = plan.start_min + 45`.
- **Impact**: Generates collision-prone maintenance block schedules during real-time train delay disturbances.
- **Recommended Fix**: Integrate `DynamicReplanningEngine.re_optimize` into `replan_coordinated_block_plan`.
- **Files Affected**: `backend/app/routers/block_requests.py`, `backend/app/algorithms/replanning.py`.
- **Database Impact**: Updates `CoordinatedBlockPlan` with verified solver results and links new state history.
- **API Impact**: Returns genuine replanned window with conflict analysis.
- **Test Required**: Simulate +30m train delay on active corridor and verify solver reruns and shifts window appropriately.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-CRIT-03
- **Severity**: CRITICAL
- **Current Behavior**: What-If scenario endpoint `/coordinated-plans/{id}/what-if` adds a flat offset and hardcodes `feasibility = "FEASIBLE"`, `score = plan.score - 3.0`.
- **Expected Behavior**: Must execute a sandboxed simulation by perturbing timetable occupancy and running `CPSATSolver` without modifying the live production database schedule.
- **Root Cause**: `what_if_coordinated_block_plan` in `block_requests.py` has mock branch statements.
- **Impact**: Planner receives fake feasibility indicators for critical operational what-if queries.
- **Recommended Fix**: Delegate scenario evaluation to `WhatIfService.simulate_scenario()`.
- **Files Affected**: `backend/app/routers/block_requests.py`, `backend/app/services/whatif_service.py`.
- **Database Impact**: Creates isolated `WhatIfScenario` record without altering production plan.
- **API Impact**: Returns authentic baseline vs scenario KPI comparison.
- **Test Required**: What-If simulation test with conflicting train delay.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-CRIT-04
- **Severity**: CRITICAL
- **Current Behavior**: `WindowEngine.calculate_feasible_windows` returns `00:00` to `24:00` (`START_OF_DAY` to `END_OF_DAY`) when no train occupancies exist for a section.
- **Expected Behavior**: If no trains are mapped or timetable data is incomplete, return `DATA_UNAVAILABLE`. A full 24-hour block should only be declared if authoritative timetable data confirms zero train movements for the entire horizon.
- **Root Cause**: `windows.py:45-73` creates a full-day window when `not sec_occ`.
- **Impact**: Provides false sense of total track possession availability.
- **Recommended Fix**: Distinguish between empty section in verified complete timetable vs unmapped/incomplete timetable. Flag unmapped sections as `DATA_UNAVAILABLE`.
- **Files Affected**: `backend/app/algorithms/windows.py`, `backend/app/routers/availability.py`.
- **Database Impact**: None.
- **API Impact**: `status: DATA_UNAVAILABLE` when timetable coverage is missing.
- **Test Required**: Test window extraction on section with missing timetable.
- **Status**: OPEN.

---

## 16. Major Problems

### PROBLEM ID: PRB-MAJ-01
- **Severity**: HIGH
- **Current Behavior**: Train origin station code corrupted to `"RAILRADAR"` in `trains.source_code`.
- **Expected Behavior**: `source_code` must be the authentic origin station code (e.g., `MAS`, `MS`, `MDU`, `TEN`).
- **Root Cause**: `train_service.py:94` prioritized `meta.get("source")` (which was `"RAILRADAR"`) over the origin station code.
- **Impact**: Breaks station-based filtering and route matching.
- **Recommended Fix**: Fix fallback logic in `train_service.py` to extract origin station code from route stops or `source_station_code`.
- **Files Affected**: `backend/app/services/train_service.py`.
- **Database Impact**: Fix corrupted rows in `trains` table.
- **API Impact**: `source_code` returns valid 3-4 letter station code.
- **Test Required**: Verify `GET /api/railway/trains` returns valid station codes.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-MAJ-02
- **Severity**: HIGH
- **Current Behavior**: Database contains 10 legacy generic corridors without prototype codes (`CORR_MAS_TPJ`, `CORR_DLI_DDU`, etc.) with 48 sections pointing to them.
- **Expected Behavior**: The operational corridor layer must strictly contain C01 through C46.
- **Root Cause**: Legacy seed fixtures were left in `abps.db`.
- **Impact**: Corrupts corridor analytics and causes orphan/duplicate sections.
- **Recommended Fix**: Remap all sections pointing to legacy corridors to their canonical C01–C46 counterparts, and purge legacy corridor records.
- **Files Affected**: `backend/abps.db`, `backend/app/routers/railway.py`.
- **Database Impact**: Deletes 10 legacy records, updates section foreign keys.
- **API Impact**: Strictly 46 corridors returned across all endpoints.
- **Test Required**: Verify `GET /api/railway/corridors` count is exactly 46 with no null prototype codes.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-MAJ-03
- **Severity**: HIGH
- **Current Behavior**: Criticality and Safety Impact scores are opaque numbers (75, 78) computed from regex keyword matching without explainable sub-factor breakdown.
- **Expected Behavior**: Scores must be derived from explainable sub-factors (asset condition, failure consequence, operational importance, safety consequence, train operation impact, failure severity, mitigation) and stored in structured form.
- **Root Cause**: `PriorityEngine` in `priority.py` assigns static numbers like `base = 76.0`, `base = 78.0`.
- **Impact**: Railway planners cannot explain or defend AI priority rankings during board or safety reviews.
- **Recommended Fix**: Implement transparent multi-attribute scoring model in `priority.py` storing all sub-factors and weights.
- **Files Affected**: `backend/app/algorithms/priority.py`, `backend/app/models/models.py`, `backend/app/schemas/schemas.py`.
- **Database Impact**: Store sub-factors in `priority_explanation` JSON column.
- **API Impact**: Returns full explainability breakdown in `/requests/{id}` and `/maintenance/jobs`.
- **Test Required**: Verify formula reproduction: $0.30 \times C + 0.20 \times U + 0.15 \times O + 0.20 \times S + 0.15 \times OP$.
- **Status**: OPEN.

---

### PROBLEM ID: PRB-MAJ-04
- **Severity**: HIGH
- **Current Behavior**: No concurrency protection on `CoordinatedBlockPlan`. Simultaneous planner decisions overwrite each other.
- **Expected Behavior**: Optimistic concurrency control using a version token to detect and prevent concurrent overwrite.
- **Root Cause**: Missing `version` column and check on `CoordinatedBlockPlan`.
- **Impact**: Risk of two section controllers approving conflicting blocks simultaneously.
- **Recommended Fix**: Add `version` column to `CoordinatedBlockPlan` and enforce check-and-increment on update.
- **Files Affected**: `backend/app/models/models.py`, `backend/app/routers/block_requests.py`.
- **Database Impact**: Add integer `version` column.
- **API Impact**: Returns HTTP 409 Conflict if plan version is stale.
- **Test Required**: Concurrent modification test.
- **Status**: OPEN.

---

## 17. Minor Problems

### PROBLEM ID: PRB-MIN-01
- **Severity**: MEDIUM
- **Current Behavior**: `CORS_ORIGINS` includes `*` in `.env` and `config.py`.
- **Expected Behavior**: Explicitly restrict CORS origins to trusted frontend domains (`http://localhost:5173`, `http://127.0.0.1:5173`).
- **Files Affected**: `backend/app/core/config.py`, `backend/.env`.
- **Status**: OPEN.

### PROBLEM ID: PRB-MIN-02
- **Severity**: MEDIUM
- **Current Behavior**: Fallback to CVP-TEN in `availability.py:139` when no route or section is found.
- **Expected Behavior**: Return HTTP 400 or `DATA_UNAVAILABLE` error instead of silently defaulting to Kovilpatti–Tirunelveli.
- **Files Affected**: `backend/app/routers/availability.py`.
- **Status**: OPEN.

### PROBLEM ID: PRB-MIN-03
- **Severity**: LOW
- **Current Behavior**: Deprecation warnings for FastAPI `@app.on_event("startup")` and `@app.on_event("shutdown")`.
- **Expected Behavior**: Migrate to FastAPI `lifespan` context manager.
- **Files Affected**: `backend/app/main.py`.
- **Status**: OPEN.

---

## 18. Missing Features for Railway Operations

1. **Section Possession Boundary Interlocking**: System lacks interface to track possession permit/token exchange.
2. **Multi-Section Possession Span**: No support for compound section requests spanning multiple consecutive block sections.
3. **Crew & Machine Depots Travel Time**: Optimizer considers resource count but does not model transit time of heavy tamping machines (TTM/BCM) from depot to work site.
4. **Speed Restriction Imposition & Clearance**: Maintenance blocks often require Temporary Speed Restrictions (TSR) post-possession; not tracked in system.
5. **Traction Power Isolation Handshake**: Lack of explicit OHE permit-to-work (PTW) isolation workflow with Traction Power Controller (TPC).

---

## 19. Fake/Hardcoded Logic Inventory

See `HARDCODED_LOGIC_REPORT.md` for complete file and line itemization. Key highlights:
- `coordination.py:400`: `plan_a_score = 96.0`
- `coordination.py:406`: `plan_b_score = 89.0`
- `coordination.py:409`: `plan_c_score = 72.0`
- `coordination.py:450`: `block_utilization_pct = 100.0`
- `block_requests.py:594-606`: Fixed score arithmetic `priority_score + 12.0`
- `block_requests.py:648`: `utilization_pct: 78.0`
- `block_requests.py:1583`: `score = max(70.0, plan.objective_score - 3.0)`
- `block_requests.py:1624`: `new_start = plan.start_min + 45`
- `windows.py:61-62`: `START_OF_DAY` / `END_OF_DAY` 24-hour fallback
- `mock_provider.py:19-59`: Static train coordinates for Delhi-Kanpur corridor with random jitter

---

## 20. Railway Integration Gaps

1. **FOIS (Freight Operations Information System)**: No live API integration; freight train paths are currently estimated or absent.
2. **ICMS (Integrated Coaching Management System)**: Coaching timetables are imported from offline sheets rather than a real-time ICMS sync feed.
3. **COA (Control Office Application)**: Official train movement logs and section controller decisions are in COA; our prototype operates as an external advisory system.
4. **BDMS (Block Disconnection Management System)**: The official Indian Railways system for maintenance block requisition. ABPS must serve as the intelligent optimization layer feeding approved proposals into BDMS.

---

## 21. Recommended Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA & TELEMETRY LAYER                          │
│  Authoritative Timetable + RailRadar/Official Feed + Master Geometry    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      SECTION OCCUPANCY ENGINE                          │
│  Train-to-Section Mapping + Safety Buffers + Blocked Intervals         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     TRACK AVAILABILITY ENGINE                          │
│  Mathematical Sweep-Line (Date/Section Specific; DATA_UNAVAILABLE state)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   COMPATIBILITY & CLUSTERING ENGINE                    │
│  Cross-Department Compatibility Matrix (Section, Date, Work Profiles)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  GOOGLE OR-TOOLS CP-SAT OPTIMIZER                      │
│  Hard Constraints: Zero Train Clashes, Resource Limits, Dependencies   │
│  Objectives: Maximize Utilization, Minimize Disruptions, Group Blocks  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     DETERMINISTIC SAFETY VALIDATOR                     │
│  15 Explicit Railway Operating Rule Checks (Pre-Approval Gate)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   HUMAN CONTROLLER DECISION WORKSTATION                │
│  Review Plan A/B/C -> Verify Explainability -> Approve / Modify / Reject│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 22. Implementation Plan

1. **Phase 46 Implementation**:
   - Refactor `CoordinatedOptimizer` to call `CPSATSolver` with actual candidate windows and constraints.
   - Replace fake replanning (`+45 min`) with real CP-SAT re-optimization.
   - Replace fake what-if with sandboxed CP-SAT simulation.
   - Eliminate `00:00–24:00` false availability fallback in `WindowEngine`.
   - Purge 10 legacy corridors and enforce clean C01–C46 mapping.
   - Fix origin station code parsing in `TrainService`.
   - Implement transparent multi-attribute scoring in `PriorityEngine`.
   - Add optimistic locking version checks on `CoordinatedBlockPlan`.
2. **Phase 47 Verification**: Run backend test suite, frontend build, and end-to-end multi-department scenario.
3. **Phase 48-50 Production Readiness**: Final quality checklist, demo checklist, and formal pilot readiness statement.

---

## 23. Production Readiness Checklist

- [ ] Optimization runs real CP-SAT: **FAIL (Pending Fix)**
- [ ] Replanning reruns real solver: **FAIL (Pending Fix)**
- [ ] What-if runs sandboxed simulation: **FAIL (Pending Fix)**
- [ ] No fake 00:00–24:00 fallback: **FAIL (Pending Fix)**
- [ ] Strict C01–C46 corridor boundary: **FAIL (Pending Fix)**
- [ ] Explainable priority formula: **FAIL (Pending Fix)**
- [ ] Station codes clean: **FAIL (Pending Fix)**
- [ ] Concurrency protection active: **FAIL (Pending Fix)**
- [ ] Live API failure fails safe: **PASS**
- [ ] Control room has no live map: **PASS**
- [ ] Frontend builds cleanly: **PASS**
- [ ] Test suite passing: **PASS (102 tests)**
- [ ] Authoritative BDMS interface: **INTEGRATION REQUIRED**
- [ ] Official Railway Network feed: **PILOT INTEGRATION REQUIRED**
