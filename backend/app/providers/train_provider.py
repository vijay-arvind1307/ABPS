from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class TrainDataProvider(ABC):
    @abstractmethod
    def get_live_train(self, train_number: str) -> Dict[str, Any]:
        """Fetch live train movement (latitude, longitude, speed, delay, current station, next station, timestamp)."""
        pass

    @abstractmethod
    def get_station_board(self, station_code: str) -> List[Dict[str, Any]]:
        """Fetch live station arrivals/departures."""
        pass

    @abstractmethod
    def get_trains_between(self, from_station: str, to_station: str) -> List[Dict[str, Any]]:
        """Fetch trains running between two stations."""
        pass

    @abstractmethod
    def get_train_route(self, train_number: str) -> Dict[str, Any]:
        """Fetch ordered stops, distances, scheduled arrivals/departures."""
        pass

    def get_station_trains(self, station_code: str, include_intermediate: bool = True) -> List[Dict[str, Any]]:
        """Fetch trains stopping or passing through a station."""
        return []

