"""
Indian Railways Enterprise Integration Adapters (SIH26027).
Defines explicit integration boundaries and abstract adapter interfaces for:
1. BDMS (Block Demand Management System)
2. COA (Control Office Application)
3. TMS (Train Management System)
4. SMMS (Track Machine & Maintenance System)
5. TDMS (Traction Distribution Management System)

DISCLAIMER:
The IR-ABPS system is an intelligent planning, multi-department coordination,
train occupancy analysis, and decision-support layer. It does NOT replace BDMS.
Authoritative possession authorization, interlocking controls, and signalling
remain strictly under authoritative Indian Railways systems and human traffic controllers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class BDMSAdapter(ABC):
    """Integration adapter interface for Block Demand Management System (BDMS)."""
    @abstractmethod
    def transmit_planned_block(self, plan_id: int, plan_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Transmits an approved master block plan to BDMS for formal railway operational sanction."""
        pass

    @abstractmethod
    def get_possession_sanction_status(self, sanction_id: str) -> Dict[str, Any]:
        """Queries authoritative possession grant / sanction status from BDMS."""
        pass


class COAAdapter(ABC):
    """Integration adapter interface for Control Office Application (COA)."""
    @abstractmethod
    def get_sectional_speed_restrictions(self, section_id: int) -> List[Dict[str, Any]]:
        """Queries authoritative permanent and temporary speed restrictions (PSR/TSR) from COA."""
        pass

    @abstractmethod
    def get_control_office_delays(self, date_str: str) -> List[Dict[str, Any]]:
        """Queries actual control chart train delays logged in COA."""
        pass


class TMSAdapter(ABC):
    """Integration adapter interface for Train Management System (TMS)."""
    @abstractmethod
    def get_live_berthing_position(self, station_code: str) -> Dict[str, Any]:
        """Queries live platform and loop line berthing telemetry from TMS."""
        pass

    @abstractmethod
    def get_block_section_track_circuit_status(self, section_id: int) -> Dict[str, Any]:
        """Queries axle counter / track circuit occupancy status from TMS."""
        pass


class SMMSAdapter(ABC):
    """Integration adapter interface for Track Machine Management System (SMMS)."""
    @abstractmethod
    def get_track_machine_deployment(self, division_code: str) -> List[Dict[str, Any]]:
        """Queries civil track machines (CSM, BCM, DGS, T-28) deployment schedule."""
        pass

    @abstractmethod
    def update_job_execution_progress(self, job_code: str, progress_km: float) -> Dict[str, Any]:
        """Logs track maintenance execution progress back into SMMS records."""
        pass


class TDMSAdapter(ABC):
    """Integration adapter interface for Traction Distribution Management System (TDMS)."""
    @abstractmethod
    def verify_power_block_isolation(self, section_id: int) -> Dict[str, Any]:
        """Verifies 25kV AC OHE feeder isolation prerequisites before maintenance possession."""
        pass


# ---------------------------------------------------------------------------
# Controlled Prototype / Evaluation Adapters (Explicitly labeled MOCK)
# ---------------------------------------------------------------------------

class MockBDMSAdapter(BDMSAdapter):
    INTEGRATION_STATUS = "MOCK / EVALUATION BOUNDARY"

    def transmit_planned_block(self, plan_id: int, plan_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "integration_status": self.INTEGRATION_STATUS,
            "external_reference": f"BDMS-SIM-{plan_id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
            "sanction_status": "PROPOSED_FOR_SANCTION",
            "message": "Block possession proposal formatted according to BDMS schema. Awaiting controlled departmental evaluation.",
            "transmitted_at": datetime.utcnow().isoformat()
        }

    def get_possession_sanction_status(self, sanction_id: str) -> Dict[str, Any]:
        return {
            "integration_status": self.INTEGRATION_STATUS,
            "sanction_id": sanction_id,
            "status": "CONTROLLED_EVALUATION_ACTIVE",
            "message": "Mock BDMS status response. Authoritative connection requires IR internal network credentials."
        }


class MockCOAAdapter(COAAdapter):
    INTEGRATION_STATUS = "MOCK / EVALUATION BOUNDARY"

    def get_sectional_speed_restrictions(self, section_id: int) -> List[Dict[str, Any]]:
        return [
            {
                "section_id": section_id,
                "restriction_type": "CAUTION_ORDER",
                "speed_limit_kmh": 45,
                "reason": "Track renewal approach caution",
                "integration_status": self.INTEGRATION_STATUS
            }
        ]

    def get_control_office_delays(self, date_str: str) -> List[Dict[str, Any]]:
        return []


class MockTMSAdapter(TMSAdapter):
    INTEGRATION_STATUS = "MOCK / EVALUATION BOUNDARY"

    def get_live_berthing_position(self, station_code: str) -> Dict[str, Any]:
        return {
            "station_code": station_code,
            "berthing_tracks": [],
            "integration_status": self.INTEGRATION_STATUS
        }

    def get_block_section_track_circuit_status(self, section_id: int) -> Dict[str, Any]:
        return {
            "section_id": section_id,
            "track_circuit": "NORMAL",
            "integration_status": self.INTEGRATION_STATUS
        }


class MockSMMSAdapter(SMMSAdapter):
    INTEGRATION_STATUS = "MOCK / EVALUATION BOUNDARY"

    def get_track_machine_deployment(self, division_code: str) -> List[Dict[str, Any]]:
        return []

    def update_job_execution_progress(self, job_code: str, progress_km: float) -> Dict[str, Any]:
        return {
            "job_code": job_code,
            "progress_km": progress_km,
            "recorded_at": datetime.utcnow().isoformat(),
            "integration_status": self.INTEGRATION_STATUS
        }


class MockTDMSAdapter(TDMSAdapter):
    INTEGRATION_STATUS = "MOCK / EVALUATION BOUNDARY"

    def verify_power_block_isolation(self, section_id: int) -> Dict[str, Any]:
        return {
            "section_id": section_id,
            "isolation_verified": True,
            "permit_to_work_ready": True,
            "integration_status": self.INTEGRATION_STATUS
        }
