import networkx as nx
from typing import List, Dict, Any, Set, Tuple


class CompatibilityGraphEngine:
    """
    NetworkX-based multi-department compatibility graph.
    Builds candidate coordination edges between maintenance jobs across Engineering, S&T, and TRD.
    Does NOT declare operationally safe on its own—passes candidate clusters to CP-SAT & Deterministic Validator.
    """

    # Department compatibility matrix: which works can safely co-occur in the same track/OHE block
    COMPATIBLE_WORK_PAIRS = {
        ("TRACK_TAMPING", "OHE_INSPECTION"),
        ("TRACK_TAMPING", "SIGNAL_POINT_OVERHAUL"),
        ("RAIL_REPLACEMENT", "OHE_POWER_BLOCK"),
        ("BALLAST_CLEANING", "CANTILEVER_ADJUSTMENT"),
        ("TRACK_CIRCUIT_REPAIR", "POINT_MACHINE_TESTING"),
        ("OHE_ANNUAL_MAINTENANCE", "TRACK_INSPECTION"),
        ("POINT_OVERHAUL", "OHE_INSPECTION"),
        ("AXLE_COUNTER_CALIBRATION", "TRACK_SURFACING")
    }

    @classmethod
    def build_graph(cls, jobs: List[Dict[str, Any]]) -> nx.Graph:
        G = nx.Graph()

        # Add nodes
        for job in jobs:
            G.add_node(
                job["id"],
                job_code=job["job_code"],
                department=job["department_code"],
                section_id=job["section_id"],
                location_km=job["location_km"],
                duration=job["estimated_duration_min"],
                work_type=job["work_type"],
                is_emergency=job.get("is_emergency", False)
            )

        # Add edges between compatible candidates
        n = len(jobs)
        for i in range(n):
            for j in range(i + 1, n):
                job_a = jobs[i]
                job_b = jobs[j]

                is_compatible, reason, score = cls._check_candidate_compatibility(job_a, job_b)
                if is_compatible:
                    G.add_edge(
                        job_a["id"],
                        job_b["id"],
                        weight=score,
                        reason=reason
                    )

        return G

    @classmethod
    def _check_candidate_compatibility(
        cls, job_a: Dict[str, Any], job_b: Dict[str, Any]
    ) -> Tuple[bool, str, float]:
        # 1. Must be in same section or directly adjacent locations (within 5 km)
        same_section = (job_a["section_id"] == job_b["section_id"])
        close_location = (abs(job_a["location_km"] - job_b["location_km"]) <= 5.0)

        if not (same_section or close_location):
            return False, "Different sections / distant locations", 0.0

        # 2. Check if distinct departments (multi-department synergy)
        dept_a = job_a.get("department_code", "")
        dept_b = job_b.get("department_code", "")

        synergy_score = 1.0
        reasons = []

        if dept_a != dept_b:
            reasons.append(f"Multi-department synergy ({dept_a} + {dept_b})")
            synergy_score += 2.0
        else:
            reasons.append(f"Same department batching ({dept_a})")

        # 3. Check specific work compatibility
        w_a = job_a.get("work_type", "").upper()
        w_b = job_b.get("work_type", "").upper()

        if (w_a, w_b) in cls.COMPATIBLE_WORK_PAIRS or (w_b, w_a) in cls.COMPATIBLE_WORK_PAIRS:
            reasons.append(f"Compatible technical work profiles ({w_a} & {w_b})")
            synergy_score += 3.0

        # 4. Check duration balance (if one is 60m and another is 65m, high synergy)
        dur_ratio = min(job_a["estimated_duration_min"], job_b["estimated_duration_min"]) / max(job_a["estimated_duration_min"], job_b["estimated_duration_min"])
        synergy_score += (dur_ratio * 2.0)

        return True, "; ".join(reasons), round(synergy_score, 2)

    @classmethod
    def get_candidate_coordination_groups(cls, G: nx.Graph) -> List[List[int]]:
        """Find candidate cliques / connected components of compatible jobs."""
        # Find maximum cliques for coordination candidate blocks
        cliques = list(nx.find_cliques(G))
        # Filter singletons
        multi_cliques = [c for c in cliques if len(c) > 1]
        return multi_cliques
