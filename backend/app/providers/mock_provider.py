import random
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.providers.train_provider import TrainDataProvider


class MockTrainProvider(TrainDataProvider):
    """
    Realistic Indian Railways train simulation provider.
    Simulates high-density train movements along Delhi-Kanpur-Prayagraj-DDU Golden Quadrilateral corridor.
    """

    def __init__(self):
        # In-memory delay overrides for real-time simulation events
        self.delay_overrides: Dict[str, int] = {}

        # Default static train positions and telemetry on the IR network
        self._train_registry = {
            "12919": {  # Malwa Express
                "train_name": "Malwa Express",
                "lat": 28.5200, "lng": 77.4500, "speed": 95.0, "dir": "UP",
                "curr_stn": "GZB", "next_stn": "ALJN", "base_delay": 5
            },
            "22436": {  # Vande Bharat Express
                "train_name": "Vande Bharat Express (NDLS-BSB)",
                "lat": 27.8900, "lng": 78.0800, "speed": 130.0, "dir": "DN",
                "curr_stn": "ALJN", "next_stn": "TDL", "base_delay": 0
            },
            "12002": {  # Bhopal Shatabdi Express
                "train_name": "Bhopal Shatabdi Express",
                "lat": 28.6000, "lng": 77.2500, "speed": 110.0, "dir": "UP",
                "curr_stn": "NDLS", "next_stn": "GZB", "base_delay": 2
            },
            "12424": {  # Dibrugarh Rajdhani
                "train_name": "Dibrugarh Rajdhani Express",
                "lat": 26.4500, "lng": 80.3500, "speed": 120.0, "dir": "DN",
                "curr_stn": "CNB", "next_stn": "PRYJ", "base_delay": 8
            },
            "12556": {  # Gorakhdham Express
                "train_name": "Gorakhdham Express",
                "lat": 25.4300, "lng": 81.8400, "speed": 80.0, "dir": "DN",
                "curr_stn": "PRYJ", "next_stn": "DDU", "base_delay": 15
            },
            "BOXN_FRT_01": {  # Freight Rake
                "train_name": "BOXN Heavy Freight Rake 01",
                "lat": 28.1500, "lng": 77.8500, "speed": 60.0, "dir": "UP",
                "curr_stn": "GZB", "next_stn": "ALJN", "base_delay": 25
            },
            "12398": {  # Mahabodhi Express
                "train_name": "Mahabodhi Express",
                "lat": 26.8500, "lng": 79.8000, "speed": 105.0, "dir": "UP",
                "curr_stn": "TDL", "next_stn": "CNB", "base_delay": 10
            },
            "12601": {  # Mangalore Mail / Express
                "train_name": "Chennai - Mangalore Mail",
                "lat": 25.3000, "lng": 82.9000, "speed": 90.0, "dir": "UP",
                "curr_stn": "PRYJ", "next_stn": "DDU", "base_delay": 0
            }
        }

    def set_delay(self, train_number: str, delay_minutes: int):
        self.delay_overrides[train_number] = delay_minutes

    def get_live_train(self, train_number: str) -> Dict[str, Any]:
        info = self._train_registry.get(train_number, {
            "train_name": f"IR Special {train_number}",
            "lat": 28.6139, "lng": 77.2090, "speed": 75.0, "dir": "UP",
            "curr_stn": "NDLS", "next_stn": "GZB", "base_delay": 0
        })

        delay = self.delay_overrides.get(train_number, info.get("base_delay", 0))

        # Add small simulated GPS jitter
        jitter_lat = (random.random() - 0.5) * 0.002
        jitter_lng = (random.random() - 0.5) * 0.002

        return {
            "train_number": train_number,
            "train_name": info["train_name"],
            "latitude": round(info["lat"] + jitter_lat, 5),
            "longitude": round(info["lng"] + jitter_lng, 5),
            "speed_kmh": info["speed"],
            "direction": info["dir"],
            "current_station_code": info["curr_stn"],
            "next_station_code": info["next_stn"],
            "delay_minutes": delay,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "Mock / IR Simulation",
            "confidence": 0.96
        }

    def get_station_board(self, station_code: str, hours: int = 4) -> List[Dict[str, Any]]:
        return []

    def get_station_trains(self, station_code: str, include_intermediate: bool = True) -> List[Dict[str, Any]]:
        code = str(station_code).upper().strip()
        if code in ["KDU", "CVP", "TEN", "MDU"]:
            return [
                {
                    "train_number": "12631",
                    "train_name": "Nellai Superfast Express",
                    "train_type": "SUPERFAST",
                    "source_code": "MS",
                    "destination_code": "TEN",
                    "run_days": ["daily"],
                    "is_halt": code in ["CVP", "TEN", "MDU"],
                    "stop_type": "halt" if code in ["CVP", "TEN", "MDU"] else "pass-through",
                    "arrival": "06:30",
                    "departure": "06:32",
                    "distance_km": 601.0
                },
                {
                    "train_number": "12632",
                    "train_name": "Nellai Superfast Express",
                    "train_type": "SUPERFAST",
                    "source_code": "TEN",
                    "destination_code": "MS",
                    "run_days": ["daily"],
                    "is_halt": code in ["CVP", "TEN", "MDU"],
                    "stop_type": "halt" if code in ["CVP", "TEN", "MDU"] else "pass-through",
                    "arrival": "20:00",
                    "departure": "20:02",
                    "distance_km": 52.0
                },
                {
                    "train_number": "06070",
                    "train_name": "Tambaram Special Fare Special",
                    "train_type": "EXPRESS",
                    "source_code": "TEN",
                    "destination_code": "TBM",
                    "run_days": ["thu"],
                    "is_halt": False,
                    "stop_type": "pass-through",
                    "arrival": "00:10",
                    "departure": "00:10",
                    "distance_km": 42.5
                }
            ]
        return []

    def get_trains_between(self, from_station: str, to_station: str) -> List[Dict[str, Any]]:
        return []

    def get_train_route(self, train_number: str) -> Dict[str, Any]:
        num = str(train_number).strip()
        if num in ["12631", "12632"]:
            stn_seq = [
                {"code": "MS", "name": "Chennai Egmore", "distance": 0.0, "arrival": "19:50", "departure": "20:10"},
                {"code": "TBM", "name": "Tambaram", "distance": 25.0, "arrival": "20:38", "departure": "20:40"},
                {"code": "VM", "name": "Villupuram", "distance": 159.0, "arrival": "22:28", "departure": "22:30"},
                {"code": "TPJ", "name": "Tiruchchirappalli", "distance": 336.0, "arrival": "01:10", "departure": "01:15"},
                {"code": "DG", "name": "Dindigul", "distance": 430.0, "arrival": "02:32", "departure": "02:35"},
                {"code": "MDU", "name": "Madurai Jn", "distance": 492.0, "arrival": "03:30", "departure": "03:35"},
                {"code": "VPT", "name": "Virudhunagar", "distance": 536.0, "arrival": "04:13", "departure": "04:15"},
                {"code": "CVP", "name": "Kovilpatti", "distance": 601.0, "arrival": "04:53", "departure": "04:55"},
                {"code": "TEN", "name": "Tirunelveli", "distance": 653.0, "arrival": "06:30", "departure": "06:30"}
            ]
            if num == "12632":
                stn_seq = list(reversed(stn_seq))
            return {
                "train_number": num,
                "train_name": "Nellai Superfast Express",
                "stops": stn_seq,
                "format": "geojson",
                "leaflet_latlngs": [[8.72, 77.73], [9.17, 77.87], [9.58, 77.95], [9.92, 78.12], [10.82, 78.69], [11.94, 79.49], [13.08, 80.27]]
            }
        return {}

