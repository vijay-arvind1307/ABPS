from typing import Optional
from app.core.config import settings
from app.providers.train_provider import TrainDataProvider
from app.providers.railradar import RailRadarProvider, RailRadarConfigError
from app.providers.mock_provider import MockTrainProvider

railradar_provider_instance = RailRadarProvider()
mock_provider_instance = MockTrainProvider()


class ConfigErrorProvider(TrainDataProvider):
    """
    Sentinel provider returned when TRAIN_DATA_MODE is 'live' but RAILRADAR_API_KEY is not configured.
    Strictly refuses to fabricate fake/mock train data silently.
    """
    def get_live_train(self, train_number: str) -> Optional[dict]:
        return {
            "train_number": str(train_number),
            "status": "CONFIG_ERROR",
            "error": "RailRadar integration is not configured.",
            "message": "RailRadar integration is not configured.",
            "source": "RailRadar integration is not configured.",
            "is_live": False,
            "provenance_status": "ERROR"
        }

    def get_station_board(self, station_code: str) -> list:
        return []

    def get_trains_between(self, from_station: str, to_station: str, raise_on_error: bool = False) -> list:
        # Always raise so the router maps this to HTTP 503 with the exact Section 16 message.
        raise RailRadarConfigError("RailRadar integration is not configured.")

    def get_train_route(self, train_number: str) -> dict:
        return {}


config_error_provider_instance = ConfigErrorProvider()


def get_train_provider() -> TrainDataProvider:
    """
    Selects the active train data provider according to TRAIN_DATA_MODE and security settings.
    - If mode == 'mock': returns MockTrainProvider for development/testing.
    - If mode == 'live': returns RailRadarProvider if API key is present;
      otherwise returns ConfigErrorProvider (never silently falsifies mock data).
    """
    mode = settings.TRAIN_DATA_MODE.lower().strip()
    if mode == "mock":
        return mock_provider_instance

    if not settings.RAILRADAR_API_KEY or not settings.RAILRADAR_API_KEY.strip():
        return config_error_provider_instance

    return railradar_provider_instance
