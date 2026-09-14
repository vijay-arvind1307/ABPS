# RAILWAY MAINTENANCE BLOCK PLANNING SYSTEM (IR-ABPS)
### AI-Assisted Maintenance Block Planning & Constraint Optimization Platform
**Maximizing Infrastructure Asset Availability for Train Operations on Indian Railways**

---

## 1. Problem Statement & Operational Context
Indian Railways operates one of the densest, most complex railway networks in the world, running over 13,000 passenger trains and 8,000 freight rakes daily across 68,000+ route kilometers. To maintain track infrastructure, signalling, and 25kV traction overhead equipment (OHE) in a safe operating state, regular **maintenance blocks** (track possession and power isolation windows) are mandatory.

However, maintenance planning faces fundamental conflicts:
- **Engineering (Permanent Way / Track):** Requires continuous track possession for mechanized tamping machines, ballast cleaners, and rail renewals.
- **Signal & Telecom (S&T):** Requires point machine overhauls, track circuit testing, and axle counter calibration.
- **Traction Distribution / OHE (TRD):** Requires 25kV power disconnection and tower wagon possession for cantilever inspection and contact wire maintenance.
- **Traffic Operations:** Strives to minimize passenger train delays, avoid freight congestion, and preserve timetable integrity.

When maintenance blocks are requested independently without multi-department coordination, it causes **excessive track closures, uncoordinated blocks, train delays, and deferred safety-critical maintenance**.

---

## 2. Positioning within Existing Indian Railways Ecosystem
The system does **NOT** replace existing railway platforms such as **BDMS (Block Demand Management System)**, **TMS (Track Management System)**, **SMMS**, **TDMS**, or **COA (Control Office Application)**. 

Instead, **IR-ABPS serves as an intelligent decision-support and mathematical optimization layer**:

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                      EXISTING RAILWAY ECOSYSTEM                        │
 │  - TMS (Track / Engg Demands)     - SMMS (Signal Demands)              │
 │  - TDMS (TRD / OHE Demands)       - COA / Timetable (Train Movements) │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │           IR-ABPS DECISION INTELLIGENCE & OPTIMIZATION LAYER           │
 │  - Multi-Criteria Decision Analysis (MCDA) Maintenance Prioritization  │
 │  - NetworkX Multi-Department Compatibility Graph (Synergy Discovery)  │
 │  - Mathematical Sweep-Line Maintenance Window Extraction               │
 │  - Google OR-Tools CP-SAT Constraint Optimization Solver (Plan A/B/C) │
 │  - Deterministic Hard-Safety Validator (15 Kernel Invariants)          │
 │  - Rolling-Horizon Dynamic Re-Planning upon Live Train Delays          │
 │  - What-If Scenario Simulation Studio & Explainability Engine          │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Approved Optimized Plan Output
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                   BDMS & OPERATIONAL EXECUTION WORKFLOW                │
 │  - Formal Disconnection / Reconnection Notices                        │
 │  - Section Controller Operational Execution                           │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 3. High-Level Architecture & End-to-End Flow

```
DEPARTMENT USERS (Engg, S&T, TRD)
             │ (Submit Maintenance Demands)
             ▼
DATA INTEGRATION & NORMALIZATION
             │
             ├──► 1. MCDA Priority Engine (Safety Tiers 1-4, Weights)
             ├──► 2. NetworkX Compatibility Graph (Multi-Dept Synergy)
             ├──► 3. Train Movement Radar & Geometric Section Mapping
             ├──► 4. Section Occupancy Intervals Calculation
             │
             ▼
SWEEP-LINE MAINTENANCE WINDOW MATHEMATICS ENGINE
             │ (Usable gaps with configured safety buffers)
             ▼
GOOGLE OR-TOOLS CP-SAT OPTIMIZER
             │ (Hard constraints + Multi-objective strategies)
             ▼
DETERMINISTIC HARD-SAFETY VALIDATOR (15 Rules Checked)
             │
             ├──► VALID ──► Plan A / B / C Generated
             └──► INVALID ─► Exact Violation Logged
             │
             ▼
RAILWAY CHIEF CONTROLLER (Human-in-the-Loop Approval & Lock Decisions)
             │ (Approve / Reject / Lock / Simulate)
             ▼
DYNAMIC RE-PLANNING ENGINE (Upon Train Delays, Overruns, Emergencies)
```

---

## 4. User Roles & RBAC (Role-Based Access Control)
The platform enforces strict backend and frontend RBAC with **three operational roles**:

| Role | Permitted Actions | Restrictions |
| :--- | :--- | :--- |
| **1. Department User** (`ENGG`, `SNT`, `TRD`) | Create demands, save drafts, submit maintenance requests, view own department defects/overdue jobs, track approved block windows. | Cannot approve or modify railway-wide master plans (attempting approval returns `403 Forbidden`). |
| **2. Railway Planner / Chief Controller** | Master corridor view, live train movement radar, derive windows, run CP-SAT optimizer, select Plan A/B/C, lock/unlock jobs, validate safety, formally approve/reject plans, trigger dynamic re-planning. | Master operational decision-maker. |
| **3. System Admin** | Manage user accounts, departments, station/section registries, configure buffer parameters (`BUFFER_BEFORE_MIN`, `BUFFER_AFTER_MIN`), view immutable audit logs. | Administration & configuration. |

---

## 5. Key Mathematical Models & Algorithms

### 5.1 MCDA Priority Scoring & Safety Tiers
Priority is computed using Multi-Criteria Decision Analysis:
$$\text{Priority} = 0.30 \cdot \text{Criticality} + 0.20 \cdot \text{Urgency} + 0.15 \cdot \text{OverdueScore} + 0.20 \cdot \text{SafetyImpact} + 0.15 \cdot \text{OperationalImpact}$$

Safety Tiers:
- **Tier 1 (Emergency):** Flagged emergency or $\text{SafetyImpact} \ge 90$ (Forced immediate scheduling priority).
- **Tier 2 (Critical):** Score $\ge 72$ or Overdue $\ge 7$ days.
- **Tier 3 (High):** Score $\ge 50$.
- **Tier 4 (Normal):** Score $< 50$.

### 5.2 Geometric Train-to-Section Mapping
Given train live GPS telemetry $(\text{lat}, \text{lon})$, direction, and route geometry:
$$P^* = \arg\min_{s \in \text{CandidateSections}} \text{Distance}(\text{TrainPosition}, \text{SectionGeometry}_s)$$
Resolved by track direction and route sequence, outputting section ID, distance-to-track, and confidence score.

### 5.3 Sweep-Line Maintenance Window Mathematics
Given consecutive train occupancy intervals on a section $[a_i, d_i]$ and $[a_{i+1}, d_{i+1}]$:
$$\text{RawGap} = a_{i+1} - d_i$$
$$\text{UsableStart} = d_i + \text{BufferBefore}$$
$$\text{UsableEnd} = a_{i+1} - \text{BufferAfter}$$
$$\text{UsableDuration} = \text{UsableEnd} - \text{UsableStart}$$
$$\text{CandidateWindow} = \text{TrainFreeWindow} \cap \text{CorridorAvailability} \cap \text{OperationalAvailability}$$

### 5.4 Google OR-Tools CP-SAT Solver Formulation
- **Decision Variables:**
  - $x[j, w] \in \{0, 1\}$: 1 if maintenance job $j$ is assigned to window $w$.
  - Start time $s_j \in [0, 1440]$, End time $e_j = s_j + D_j$.
  - Optional intervals: $\text{Interval}(s_j, D_j, e_j, x[j, w])$.
- **Hard Safety Constraints:**
  1. No train conflict (cannot overlap train occupancy + safety buffers).
  2. Window bounds: $L_w \le s_j$ and $e_j \le R_w$.
  3. Job assignment uniqueness: $\sum_w x[j, w] \le 1$.
  4. Cumulative machine/crew resource limits across simultaneous jobs: $\text{AddCumulative}$.
  5. Finish-to-start precedence dependencies: $e_{\text{pred}} + \text{gap} \le s_{\text{succ}}$.
  6. Locked planner decisions: $s_j = T_{\text{locked}}$.
  7. Immutability of completed and protected in-progress jobs.
- **Multi-Objective Strategies:**
  - **Plan A (Max Asset Availability):** Maximize critical job completion and multi-department block coordination synergy.
  - **Plan B (Min Train Disruption):** Penalize traffic headway disturbance.
  - **Plan C (Max Utilization):** Minimize total count of opened blocks and maximize utilized track time.

### 5.5 Independent Deterministic Safety Validator
Re-evaluates all 15 safety invariants without AI or heuristics. Outputs `VALID` or `INVALID` with exact violation details (e.g. *"CRITICAL SAFETY VIOLATION: Job E101 overlaps Train 12919 by 18 minutes"*).

---

## 6. Technology Stack
- **Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, Google OR-Tools CP-SAT v9.11, NetworkX, Pandas, NumPy, Scikit-learn, Passlib, Python-Jose.
- **Frontend:** React 18, Vite, Tailwind CSS (CRIS Indian Railways Theme), Lucide Icons, React-Leaflet, Leaflet, Axios.
- **Testing:** Pytest (15 automated unit & integration test suites).
- **Deployment:** Docker, Docker Compose, Nginx, PostgreSQL.

---

## 7. Operational Roles & Accounts
The system is pre-seeded with representative Indian Railways role profiles on the **Delhi - Kanpur - Prayagraj - Pt. Deen Dayal Upadhyaya Golden Quadrilateral Corridor**:

| Role | Username | Password | Email | Access Scope |
| :--- | :--- | :--- | :--- | :--- |
| **Railway Planner / Controller** | `planner` | `planner123` | `planner@railnet.gov.in` | Full master planning, CP-SAT solve, validation, approval, lock/unlock. |
| **Track Engineering User (ENGG)** | `engg_user` | `engg123` | `engg@railnet.gov.in` | Permanent Way demands, track tamping, rail renewals. |
| **Signal & Telecom User (SNT)** | `snt_user` | `snt123` | `snt@railnet.gov.in` | Point machine overhauls, track circuits, axle counters. |
| **Traction Distribution User (TRD)**| `trd_user` | `trd123` | `trd@railnet.gov.in` | 25kV OHE power blocks, tower wagons, cantilevers. |
| **System Administrator** | `admin` | `admin123` | `admin@railnet.gov.in` | Master data, safety buffers, audit logs. |

---

## 8. Installation & Quick Start Guide

### Option A: Local Development (Fastest, Zero Setup)

#### 1. Backend Setup:
```powershell
cd c:\ABPS
python -m venv venv
.\venv\Scripts\pip install -r backend\requirements.txt
```

Initialize & Seed Database:
```powershell
.\venv\Scripts\python.exe -m backend.app.seed_data
```

Run Automated Pytest Test Suite:
```powershell
cd backend
..\venv\Scripts\pytest.exe -v
```

Start Backend Server:
```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Backend API will be available at: `http://127.0.0.1:8000` (Swagger docs: `http://127.0.0.1:8000/docs`).

#### 2. Frontend Setup:
```powershell
cd c:\ABPS\frontend
npm install
npm run dev
```
Frontend web application will be available at: `http://localhost:5173`.

---

### Option B: Docker Compose (Full Containerized Production Stack)
```bash
cd c:\ABPS
docker compose up --build
```
- Frontend UI: `http://localhost`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

---

## 9. Operational Planning Scenario Workflow

1. **Login as Railway Planner:**
   - Select the `★ Railway Planner` profile or enter `planner` / `planner123`.
2. **Review Control Room Dashboard:**
   - Review the **Time-Distance String Chart** displaying train trajectories along Delhi-DDU (NDLS, GZB, ALJN, TDL, CNB, PRYJ, DDU).
   - Review the **Multi-Department Block Gantt** and **KPI Benchmark Matrix**.
3. **Generate Optimized Block Schedule:**
   - Click `GENERATE OPTIMIZED PLAN` (Triggers Google OR-Tools CP-SAT).
   - Observe how compatible jobs across Engg, S&T, and TRD are packed into single coordinated blocks.
4. **Inspect Explainability:**
   - Click `Explain` on job `E101` to view MCDA factor contributions and reasons for selection.
5. **Deterministic Safety Validation:**
   - Click `VALIDATE SAFETY` to view the 15-rule safety certificate.
6. **Inject Operational Disturbance & Dynamic Re-Planning:**
   - Navigate to `Dynamic Re-Planning` tab.
   - Click `Trigger Train 12919 Delay (+30m)`. Observe the immediate conflict warning.
   - Click `Trigger Dynamic Re-Planning`. Observe the rolling-horizon CP-SAT re-optimization resolving the conflict with zero train collisions.
   - Click `Formally Approve Re-Planned Plan V2`.
7. **What-If Analysis Studio:**
   - Navigate to `What-If Analysis` tab.
   - Adjust maintenance duration overrun (+20%) and click `Run What-If Simulation` to evaluate schedule resilience.
8. **Export & Audit:**
   - Navigate to `Reports & Audit Trail` tab to download the approved block schedule CSV and review immutable logs.
9. **Scenario Simulation Runner:**
   - Navigate to `Scenario Simulation` tab (or click `LOAD PLANNING SCENARIO` on the header) to execute the complete end-to-end operational planning sequence.

---

## 10. Summary Statement
> **"We are not replacing Indian Railways' existing operational systems. We are providing an intelligent decision intelligence and constraint optimization layer that mathematically balances multi-department maintenance needs with train traffic flow, protects safety through deterministic rules, and preserves full operational authority with the human Railway Planner."**
