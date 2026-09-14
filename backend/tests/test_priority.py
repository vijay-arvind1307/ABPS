import pytest
from app.algorithms.priority import PriorityEngine


def test_mcda_priority_calculation():
    # Normal job with high safety impact and criticality
    score, tier, exp = PriorityEngine.calculate_priority(
        criticality=80.0,
        urgency=75.0,
        overdue_days=2,
        safety_impact=85.0,
        operational_impact=70.0,
        is_emergency=False
    )
    assert score >= 65.0
    assert "Tier 2" in tier or "Tier 3" in tier
    assert "criticality" in exp["factor_contributions"]
    assert len(exp["reasons"]) > 0


def test_emergency_job_tier_1():
    score, tier, exp = PriorityEngine.calculate_priority(
        criticality=50.0,
        urgency=50.0,
        overdue_days=0,
        safety_impact=50.0,
        operational_impact=50.0,
        is_emergency=True
    )
    assert score >= 95.0
    assert tier == "Tier 1 (Emergency)"
    assert any("Emergency" in r for r in exp["reasons"])
