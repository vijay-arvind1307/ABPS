from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# C:\ABPS\backend\app\core\config.py
# parents[0] = core
# parents[1] = app
# parents[2] = backend
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Railway Maintenance Block Planning System (IR-ABPS)"
    API_V1_STR: str = "/api"

    SECRET_KEY: str = "ir-abps-railway-operations-secret-key-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Database
    DATABASE_URL: str = "sqlite:///./abps.db"

    # Train Data Provider
    TRAIN_DATA_MODE: str = "live"
    RAILRADAR_API_KEY: str = ""
    RAILRADAR_BASE_URL: str = "https://api.railradar.in"

    RAILRADAR_POLL_INTERVAL_SECONDS: int = 45
    RAILRADAR_CACHE_TTL_LIVE: int = 45
    RAILRADAR_CACHE_TTL_DISCOVERY: int = 300
    RAILRADAR_CACHE_TTL_ROUTE: int = 1800
    RAILRADAR_CACHE_TTL_STATION: int = 180

    # Controlled Live Telemetry & TN Scoping
    LIVE_POLL_INTERVAL_SECONDS: int = 45
    LIVE_REQUEST_COOLDOWN_SECONDS: int = 30
    LIVE_DATA_STALE_AFTER_SECONDS: int = 120
    TN_LIVE_MAX_TRAINS: int = 15
    LIVE_BACKGROUND_POLLING_ENABLED: bool = True

    # Planning & Safety Buffers
    BUFFER_BEFORE_MIN: int = 5
    BUFFER_AFTER_MIN: int = 5
    PLANNING_HORIZON_HOURS: int = 24
    PLANNING_HORIZON_DAYS: int = 7
    SOLVER_TIME_LIMIT_SECONDS: int = 15

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*",
    ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()