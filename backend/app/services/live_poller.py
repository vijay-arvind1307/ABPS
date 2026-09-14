import asyncio
import logging
from typing import Optional
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.train_service import TrainService

logger = logging.getLogger("ir_abps.live_poller")

_poller_task: Optional[asyncio.Task] = None
_is_running: bool = False


def _poll_step():
    """Execute one synchronous poll cycle in a background thread."""
    db = SessionLocal()
    try:
        eligible_trains = TrainService.get_eligible_tn_trains(db)
        if not eligible_trains:
            return

        train_numbers = [t.train_number for t in eligible_trains]
        TrainService.refresh_live_trains(db, train_numbers)
    except Exception as exc:
        print(f"[LIVE POLLER] Background cycle error: {exc}")
    finally:
        db.close()


async def _polling_loop():
    """Continuous controlled background poller for Tamil Nadu operational trains."""
    global _is_running
    interval = getattr(settings, "LIVE_POLL_INTERVAL_SECONDS", 45)
    print(f"[LIVE POLLER] Background live telemetry poller started (interval: {interval}s).")

    # Initial brief pause to let app finish full startup
    await asyncio.sleep(3)

    while _is_running:
        try:
            mode = settings.TRAIN_DATA_MODE.lower()
            if mode == "live" and settings.RAILRADAR_API_KEY:
                await asyncio.to_thread(_poll_step)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[LIVE POLLER] Poller loop error: {e}")

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break

    print("[LIVE POLLER] Background poller stopped.")


def start_live_poller():
    """Start the background poller task if enabled and not already running."""
    global _poller_task, _is_running
    if not getattr(settings, "LIVE_BACKGROUND_POLLING_ENABLED", True):
        print("[LIVE POLLER] Background polling is disabled by configuration.")
        return

    if _is_running and _poller_task and not _poller_task.done():
        return

    _is_running = True
    loop = asyncio.get_event_loop()
    _poller_task = loop.create_task(_polling_loop())


def stop_live_poller():
    """Stop the background poller task."""
    global _poller_task, _is_running
    _is_running = False
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
