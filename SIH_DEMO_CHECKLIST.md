# SIH26027 — Automatic Block Planning System (IR-ABPS)
## Complete Production-Readiness Demonstration Runbook & Jury Checklist

> **Problem Statement ID:** SIH26027  
> **Title:** AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways  
> **Organization:** Ministry of Railways / Southern Railway (SR)  
> **System Status:** PILOT READY (All Critical & High Algorithmic / Architectural Invariants Resolved)  
> **Core Solver:** Google OR-Tools CP-SAT Constraint Optimization  

---

## 1. Pre-Demonstration Environment Setup

### 1.1 Start Backend Server
```bash
cd c:\ABPS\backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Verify health status:
- `http://localhost:8000/health` → Status: `"HEALTHY"`, components: `database: HEALTHY`, `optimizer: READY`, `live_train_provider: CONFIGURED / STATIC_READY`.
- `http://localhost:8000/health/ready` → `{"status": "READY"}`.
- `http://localhost:8000/health/live` → `{"status": "LIVE"}`.

### 1.2 Start Frontend Dev Server
```bash
cd c:\ABPS\frontend
npm run dev
```
Open browser at: `http://localhost:5173`.

---

## 2. Demonstration Step-by-Step Sequence

### Step 1: Multi-Department Role-Based Access & Request Creation
1. **Login as Engineering Officer:**
   - **Username:** `engg_user` | **Password:** `engg123`
   - Role displayed: `ENGINEERING`
   - Notice: Department users cannot view private draft demands of S&T or TRD.
2. **Submit Maintenance Demand REQ-101:**
   - **Department:** Engineering (Civil)
   - **Work Type:** `TRACK_TAMPING` (Track Geometry Maintenance)
   - **Corridor:** `C40 (Madurai - Tirunelveli Main Line)`
   - **Section:** `CVP → TEN (Kovilpatti to Tirunelveli Jn)`
   - **Requested Duration:** `90 minutes`
   - **Priority Selection:** `HIGH`
   - **Due Date:** Tomorrow / within 48h
3. **Show Transparent Multi-Factor Priority Breakdown:**
   - Open **Safety & Asset Impact** tab before submitting.
   - Point out that **no magic numbers exist** (neither 75 nor 78 are hardcoded).
   - **Show Explicit Sub-Factor Calculations:**
     - **Criticality (0–100):** Computed from Condition Score + Failure Consequence Score + Operational Importance Score.
     - **Safety Impact (0–100):** Computed from Safety Consequence + Train Operation Safety Risk + Failure Severity + Mitigation Factor.
     - **Urgency (0–100):** Computed from Remaining Planning Horizon to Due Date.
     - **Overdue Risk (0–100):** Computed from Days to Overdue.
     - **Operational Impact (0–100):** Computed from Line Capacity / Traffic Disruption Weight.
   - **Show Contribution Formula:**
     $$\text{Priority Score} = 0.30 \times C + 0.20 \times U + 0.15 \times O + 0.20 \times S + 0.15 \times OP$$
     Example Contribution:
     - Criticality: $75.0 \times 30\% = 22.50\text{ pts}$
     - Safety Impact: $78.0 \times 20\% = 15.60\text{ pts}$
     - Urgency: $90.0 \times 20\% = 18.00\text{ pts}$
     - Overdue Risk: $50.0 \times 15\% = 7.50\text{ pts}$
     - Operational: $80.0 \times 15\% = 12.00\text{ pts}$
     - **Total Deterministic Score:** $\mathbf{75.60}$
   - Submit `REQ-101`.

4. **Repeat / Inspect Other Department Requests:**
   - `REQ-102`: Signal & Telecom (`SIGNAL_INSPECTION`, CVP → TEN, 60 min).
   - `REQ-103`: Traction Distribution (`OHE_INSPECTION`, CVP → TEN, 75 min).

---

### Step 2: Planner Control Room & Automatic Compatibility Detection
1. **Login as Railway Planner / Chief Controller:**
   - **Username:** `planner` | **Password:** `planner123`
   - Role displayed: `RAILWAY_PLANNER` (Full Division Authority).
2. **Open Control Room:**
   - Confirm: **No live map cluttering the Control Room** (focused strictly on scheduling decisions and conflict resolution).
   - Inspect the request queue showing pending demands across Civil, S&T, and TRD.
3. **Trigger Global Multi-Department Optimization:**
   - Click **`OPTIMIZE REQUESTS`**.
   - Explain to the jury:
     > *"The system does not require the human planner to manually cherry-pick compatible requests. The Compatibility Engine automatically partitions the demand pool into common block clusters and dedicated single possessions."*
4. **Inspect Coordination Result:**
   - Automatic grouping of `REQ-101` (90 min), `REQ-102` (60 min), and `REQ-103` (75 min).
   - **Parallel Common Block Duration:** $\max(90, 60, 75) = \mathbf{90\text{ minutes}}$ (NOT $90 + 60 + 75 = 225\text{ min}$).
   - **Track Possession Avoided:** $225 - 90 = \mathbf{135\text{ minutes}}$ of line downtime saved!
   - **Blocks Consolidated:** $3 \to 1$.

---

### Step 3: Google OR-Tools CP-SAT Alternative Formulation
1. **Show Real Feasible Window Derivation:**
   - Explain that the engine swept train occupancies on section CVP–TEN and identified genuine gaps between scheduled express services (e.g. Thirukkural Express and Guruvayur Express).
   - Point out that **`00:00–24:00` false availability is strictly eliminated**.
2. **Review Plan A, Plan B, and Plan C Tradeoff Analysis:**
   - **Plan A (Recommended Best Coordination):**
     - Window: `10:45 – 12:15` (90 min).
     - OR-Tools CP-SAT Objective Score: `~94.5`.
     - Block Utilization: `100.0%`.
     - Train Headway Conflicts: `0`.
   - **Plan B (Alternative Window):**
     - Window: `13:00 – 14:30` (90 min).
     - Tradeoff: Mid-day post-peak slot; avoids passenger express crossings.
   - **Plan C (Fallback / Staggered Blocks):**
     - Tradeoff: Sequential non-overlapping deployment with higher track possession footprint.
3. **Show Deterministic Safety Validation (15 Safety Rules):**
   - Headway clearance $\ge 5\text{ min}$.
   - Traction shut-off permits verified.
   - Resource non-collision verified.

---

### Step 4: Human-in-the-Loop Approval & Concurrency Protection
1. **Planner Decision:**
   - The AI optimizer **never approves directly**.
   - Planner reviews the safety packet, inputs authorization remarks, and clicks **`APPROVE PLAN`**.
   - Plan transitions to `APPROVED`.
2. **Demonstrate Optimistic Locking Concurrency:**
   - If another controller attempts to modify or approve the same plan simultaneously without refreshing, the backend immediately rejects with **`HTTP 409 Conflict: Plan version has been modified by another planner`**.
3. **Demonstrate Safety Protection of Completed Work:**
   - Completed or actively running blocks cannot be rescheduled or modified (`HTTP 400 Bad Request`).

---

### Step 5: Live Train Telemetry & Provenance Integrity
1. **Navigate to Live Train Position:**
   - Select corridor: **`C40 (Madurai - Tirunelveli Main Line)`**.
   - Inspect the railway geometry: Track follows **real Southern Railway GIS geometry** (not synthetic straight lines).
2. **Demonstrate Data Freshness & Provenance:**
   - If RailRadar live key is active: Train markers render with live delay, current section, next halt, and telemetry timestamp (`HH:MM:SS IST`).
   - If API quota is exhausted or key is absent:
     - System **strictly avoids fake synthetic coordinates**.
     - UI displays clear status badge:
       $$\mathbf{MODE:\ STATIC\ /\ DEMO}\quad\vert\quad\mathbf{LIVE\ API:\ UNAVAILABLE}$$
     - Static timetable geometry remains interactive without system crash.

---

### Step 6: Train Delay Simulation & Dynamic Replanning
1. **Inject Perturbation (Train Delay):**
   - In Live View or What-If, simulate upstream passenger express running **+30 minutes late**.
2. **Observe Real-Time Impact:**
   - Section occupancy on CVP–TEN updates automatically.
   - System flags a **headway collision** with the approved 10:45 block.
3. **Trigger Dynamic Replanning:**
   - Click **`RUN DYNAMIC REPLAN`**.
   - System automatically:
     1. Freezes completed and active work.
     2. Recalculates remaining viable gaps using sweep-line.
     3. Reruns Google OR-Tools CP-SAT.
     4. Shifts window forward to next conflict-free gap (e.g. `13:00 – 14:30`).
     5. Routes revised plan back to Planner for review and approval.

---

### Step 7: Immutable Audit Trail & Decision Reproducibility
1. **Open Plan Audit Log:**
   - View complete chronological audit record for the Coordinated Block Plan:
     - `PLAN_GENERATED` by CP-SAT solver with objective score.
     - `PLAN_APPROVED` by `planner` with user ID, timestamp, and justification.
     - `DYNAMIC_REPLAN` recorded with disturbance cause and before/after time deltas.
2. **Highlight Decision Support Boundary:**
   - Explain to the jury:
     > *"IR-ABPS is an intelligent planning and decision-support layer designed to feed into BDMS (Block Demand Management System) and Section Controller consoles. It does not directly command field interlocking or signal equipment."*

---

## 3. Summary of Fixed High-Risk Areas for Presentation

| # | Evaluated Area | Previous Prototype Risk | Fixed Production Behavior |
|---|---|---|---|
| **1** | **Availability Fallback** | Defaulted to false `00:00–24:00` | Sweep-line gaps only; missing timetable returns `DATA_UNAVAILABLE` |
| **2** | **Priority Scoring** | Opaque numbers (e.g. 75, 78) | Fully explainable MCDA formula ($30\%C + 20\%U + 15\%O + 20\%S + 15\%OP$) with transparent sub-factors |
| **3** | **Multi-Dept Optimization** | Bypassed solver with static dummy scores | Google OR-Tools CP-SAT executed directly across real candidate windows |
| **4** | **Corridor Master Data** | Cluttered legacy records & orphan sections | Strictly 46 canonical Southern Railway corridors (`C01`–`C46`) |
| **5** | **Live Train Telemetry** | Risk of synthetic mock markers | Explicit `LIVE DATA UNAVAILABLE` safe fallback; zero fake live markers |
| **6** | **Concurrency** | Silent overwrite risk | Optimistic locking via incremental plan `version` (`HTTP 409`) |
| **7** | **Dynamic Replanning** | Hardcoded `+45 min` time shift | Genuine CP-SAT rolling-horizon re-optimization |
| **8** | **System Observability** | Basic ping endpoint | Multi-component `/health`, `/health/live`, `/health/ready` |
