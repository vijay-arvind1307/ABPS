from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Corridor, RailwaySection, Train, TrainMovement, TrainPositionSnapshot, APIHealthStatus
from app.services.train_service import TrainService
from app.providers import get_train_provider, railradar_provider_instance
from app.core.config import settings

router = APIRouter(prefix="/live", tags=["Live Train Telemetry & Health"])


@router.get("/health")
def get_live_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns the real-time health and operational status of RailRadar live telemetry.
    States: AVAILABLE, DEGRADED, RATE_LIMITED, UNAUTHORIZED, NOT_FOUND, SERVICE_UNAVAILABLE, TIMEOUT, UNAVAILABLE
    """
    provider = get_train_provider()
    status_info = provider.get_provenance_status()
    raw_status = status_info.get("status", "UNAVAILABLE")
    last_err = status_info.get("last_error") or ""

    if not status_info.get("has_api_key"):
        canonical_status = "UNAVAILABLE"
        reason = "KEY_MISSING"
    elif "429" in last_err or raw_status == "RATE_LIMITED":
        canonical_status = "RATE_LIMITED"
        reason = "Rate limit reached on RailRadar live endpoint"
    elif "401" in last_err or raw_status == "UNAUTHORIZED":
        canonical_status = "UNAUTHORIZED"
        reason = "RailRadar authentication failed: Invalid or expired API key"
    elif "503" in last_err or raw_status == "SERVICE_UNAVAILABLE":
        canonical_status = "SERVICE_UNAVAILABLE"
        reason = "RailRadar remote service temporarily unavailable"
    elif "timeout" in last_err.lower() or raw_status == "TIMEOUT":
        canonical_status = "TIMEOUT"
        reason = "Request to RailRadar timed out"
    elif raw_status == "LIVE" or raw_status == "AVAILABLE":
        canonical_status = "AVAILABLE"
        reason = "Connected to RailRadar live train telemetry feed"
    else:
        canonical_status = "UNAVAILABLE"
        reason = last_err or "Live data currently unavailable"

    # Persist or update APIHealthStatus in database
    try:
        health_record = db.query(APIHealthStatus).filter(APIHealthStatus.provider == "RailRadar").first()
        if not health_record:
            health_record = APIHealthStatus(
                provider="RailRadar",
                status=canonical_status,
                last_success=datetime.fromisoformat(status_info["last_success_time"]) if status_info.get("last_success_time") else None,
                failure_reason=reason if canonical_status != "AVAILABLE" else None,
                checked_at=datetime.utcnow()
            )
            db.add(health_record)
        else:
            health_record.status = canonical_status
            if canonical_status == "AVAILABLE":
                health_record.last_success = datetime.utcnow()
            else:
                health_record.last_failure = datetime.utcnow()
                health_record.failure_reason = reason
            health_record.checked_at = datetime.utcnow()
        db.commit()
    except Exception as ex:
        db.rollback()

    return {
        "provider": "RailRadar",
        "status": canonical_status,
        "is_live": canonical_status == "AVAILABLE",
        "has_api_key": bool(getattr(settings, "RAILRADAR_API_KEY", None)),
        "last_success": status_info.get("last_success_time"),
        "last_error": reason if canonical_status != "AVAILABLE" else None,
        "checked_at": datetime.utcnow().isoformat()
    }


@router.get("/corridors/{corridor_id}")
def get_corridor_live_trains(
    corridor_id: str,
    journey_date: Optional[str] = Query(None, description="Journey date YYYY-MM-DD (defaults to today)"),
    refresh: bool = Query(False, description="Whether to trigger live refresh"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns candidate train discovery & live telemetry status for the selected corridor.
    Guarantees:
    - Decoupled candidate discovery: returns ALL trains scheduled today across corridor sections.
    - Honest status: if live telemetry is unavailable or rate-limited, trains remain visible with status 'SCHEDULED — LIVE UNAVAILABLE'.
    - Deterministic mapping confidence: 100, 90, 75, or 50 with explicit method and reason.
    - Zero fake GPS coordinates or fake 0 km/h speeds.
    """
    target_d = None
    if journey_date:
        try:
            target_d = date.fromisoformat(journey_date.strip())
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid journey_date format '{journey_date}'. Use YYYY-MM-DD.")

    result = TrainService.get_corridor_candidate_live_status(
        db=db,
        corridor_ident=corridor_id,
        target_date=target_d,
        refresh=refresh
    )

    if not result or "error" in result:
        raise HTTPException(status_code=404, detail=result.get("error") if result else f"Corridor '{corridor_id}' not found.")

    # Populate top-level backward compatibility attributes
    result["liveAvailable"] = result.get("liveAvailableCount", 0) > 0
    result["candidateTrainsCount"] = result.get("scheduledTrainCount", len(result.get("trains", [])))
    result["status"] = result.get("liveStatus", "UNAVAILABLE")

    return result


@router.get("/trains/{train_number}")
def get_single_train_live(
    train_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns normalized live telemetry for a single train number.
    Returns clean failure structure if telemetry is not available.
    """
    t_num = str(train_number).strip()
    provider = get_train_provider()

    try:
        live = provider.get_live_train(t_num)
        if live:
            return {
                "trainNumber": t_num,
                "trainName": live.get("train_name", f"Train {t_num}"),
                "liveAvailable": True,
                "status": live.get("status", "RUNNING"),
                "delayMinutes": live.get("delay_minutes", 0),
                "speedKmh": live.get("speed_kmh", 0.0),
                "currentStation": live.get("current_station_code") or "EN_ROUTE",
                "nextStation": live.get("next_halt") or "",
                "latitude": live.get("latitude"),
                "longitude": live.get("longitude"),
                "source": "RAILRADAR_LIVE",
                "lastUpdated": live.get("last_updated_at") or datetime.utcnow().isoformat()
            }
    except Exception as ex:
        err_msg = str(ex)
        reason = "RATE_LIMITED" if "429" in err_msg else ("UNAUTHORIZED" if "401" in err_msg else "UNAVAILABLE")
        return {
            "trainNumber": t_num,
            "liveAvailable": False,
            "status": "LIVE_DATA_UNAVAILABLE",
            "reason": reason,
            "message": f"Live telemetry unavailable for Train {t_num}: {err_msg}",
            "source": "RailRadar"
        }

    last_err = str(getattr(provider, "_last_error", "") or "")
    key = str(getattr(settings, "RAILRADAR_API_KEY", "") or "").strip()
    if not key or "missing" in last_err.lower():
        reason = "MISSING_API_KEY"
    elif "429" in last_err or "rate limit" in last_err.lower():
        reason = "RATE_LIMITED"
    elif "401" in last_err or "unauthorized" in last_err.lower():
        reason = "UNAUTHORIZED"
    elif "503" in last_err or "service unavailable" in last_err.lower():
        reason = "SERVICE_UNAVAILABLE"
    else:
        reason = "NOT_FOUND"

    return {
        "trainNumber": t_num,
        "liveAvailable": False,
        "status": "LIVE_DATA_UNAVAILABLE",
        "reason": reason,
        "message": f"Live telemetry unavailable for Train {t_num} ({reason}).",
        "source": "RailRadar",
        "train": {
            "latitude": None,
            "longitude": None
        }
    }
