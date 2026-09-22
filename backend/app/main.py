from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.models import User
from app.seed_data import seed_database
from app.routers import (
    auth_router,
    maintenance_router,
    railway_router,
    planning_router,
    dynamic_router,
    whatif_router,
    reports_router,
    scenario_router,
    stations_router,
    trains_router,
    execution_router,
    notifications_router,
    block_requests_router,
    coordinated_block_plans_router,
    live_router,
    availability_router,
    standard_api_router
)
from app.models.models import User, RailwayStation, Train

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Railway Maintenance Block Planning API (IR-ABPS)",
    description="AI-Assisted Maintenance Block Planning and Constraint Optimization Platform for Indian Railways",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup - support localhost frontend and credentials properly
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(maintenance_router, prefix=settings.API_V1_STR)
app.include_router(block_requests_router, prefix=settings.API_V1_STR)
app.include_router(coordinated_block_plans_router, prefix=settings.API_V1_STR)
app.include_router(railway_router, prefix=settings.API_V1_STR)
app.include_router(trains_router, prefix=settings.API_V1_STR)
app.include_router(planning_router, prefix=settings.API_V1_STR)
app.include_router(execution_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(dynamic_router, prefix=settings.API_V1_STR)
app.include_router(whatif_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(scenario_router, prefix=settings.API_V1_STR)
app.include_router(stations_router, prefix=settings.API_V1_STR)
app.include_router(stations_router)  # Also allow direct /stations paths
app.include_router(live_router, prefix=settings.API_V1_STR)
app.include_router(live_router)  # Allow direct /live paths
app.include_router(availability_router, prefix=settings.API_V1_STR)
app.include_router(availability_router)  # Allow direct /availability paths
app.include_router(standard_api_router, prefix=settings.API_V1_STR)
app.include_router(standard_api_router)  # Allow direct standard REST paths (/requests, /plans/..., etc.)


from app.routers.block_requests import optimize_request_pool, PoolOptimizeRequest
from app.routers.auth import get_current_user
from app.db.session import get_db
from fastapi import Depends
from typing import Optional
from sqlalchemy.orm import Session

@app.post("/api/block-planning/optimize", tags=["Block Planning & Optimization"])
def api_block_planning_optimize(
    req: Optional[PoolOptimizeRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Global multi-department block pool optimization endpoint alias."""
    return optimize_request_pool(req=req, db=db, current_user=current_user)




@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        # Check if users already exist, if not seed initial operational data
        user_count = db.query(User).count()
        if user_count == 0:
            seed_database(db)

        # Check if railway station master is populated; if not, import from PDF
        stn_count = db.query(RailwayStation).count()
        if stn_count == 0:
            try:
                import sys
                import os
                # Find PDF path
                pdf_candidates = [
                    "documents/TN-station list.pdf",
                    "../documents/TN-station list.pdf",
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "documents", "TN-station list.pdf")
                ]
                pdf_found = None
                for c in pdf_candidates:
                    if os.path.exists(c):
                        pdf_found = c
                        break
                if pdf_found:
                    from scripts.import_station_master import import_station_master
                    print(f"[STARTUP] Auto-importing Station Master from {pdf_found}...")
                    import_station_master(pdf_found)
            except Exception as e:
                print(f"[STARTUP] Station Master auto-import notice: {e}")

        # Check if train master is populated; if not, import railway documents
        train_count = db.query(Train).count()
        if train_count == 0:
            try:
                from app.scripts.import_railway_documents import run_import
                print("[STARTUP] Auto-importing Railway Documents...")
                run_import()
            except Exception as e:
                print(f"[STARTUP] Railway documents auto-import notice: {e}")
    finally:
        db.close()

    # Start controlled live telemetry background poller for Tamil Nadu network
    try:
        from app.services.live_poller import start_live_poller
        start_live_poller()
    except Exception as e:
        print(f"[STARTUP] Live poller init notice: {e}")


@app.on_event("shutdown")
def shutdown_event():
    try:
        from app.services.live_poller import stop_live_poller
        stop_live_poller()
    except Exception as e:
        print(f"[SHUTDOWN] Live poller shutdown notice: {e}")


from sqlalchemy import text
from datetime import datetime
from fastapi import Response, status as http_status

@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "HEALTHY"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"UNHEALTHY: {str(e)}"

    solver_status = "READY"
    try:
        from ortools.sat.python import cp_model
        _m = cp_model.CpModel()
        _s = cp_model.CpSolver()
    except Exception as e:
        solver_status = f"UNAVAILABLE: {str(e)}"

    provider_status = "CONFIGURED" if settings.RAILRADAR_API_KEY else "NO_KEY (STATIC/DEMO READY)"

    is_overall_healthy = (db_status == "HEALTHY" and solver_status == "READY")
    return {
        "status": "HEALTHY" if is_overall_healthy else "DEGRADED",
        "service": "Railway Maintenance Block Planning System (IR-ABPS)",
        "components": {
            "database": db_status,
            "optimizer": solver_status,
            "live_train_provider": provider_status,
            "train_data_mode": settings.TRAIN_DATA_MODE,
        },
        "safety_validator": "DeterministicHardSafetyValidator (15 Rules Active)",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/live")
def health_liveness():
    return {"status": "LIVE", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/ready")
def health_readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "READY", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return Response(
            content=f'{{"status": "NOT_READY", "error": "{str(e)}"}}',
            media_type="application/json",
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE
        )
