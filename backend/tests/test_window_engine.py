import pytest
from app.algorithms.windows import WindowEngine


def test_sweep_line_gap_calculation_with_buffers():
    occupancies = [
        {"section_id": 2, "train_number": "12002", "estimated_entry_min": 600, "estimated_exit_min": 615},  # 10:00 - 10:15
        {"section_id": 2, "train_number": "12919", "estimated_entry_min": 690, "estimated_exit_min": 705}   # 11:30 - 11:45
    ]
    # Raw gap = 690 - 615 = 75 minutes
    # With 5 min buffer before and 5 min buffer after -> Usable start = 620, Usable end = 685 -> Usable duration = 65 minutes
    windows = WindowEngine.calculate_feasible_windows(
        section_id=2,
        corridor_id=1,
        occupancies=occupancies,
        horizon_start_min=600,
        horizon_end_min=720,
        buffer_before_min=5,
        buffer_after_min=5,
        min_window_duration_min=30
    )

    assert len(windows) >= 1
    target_win = [w for w in windows if w["train_before_no"] == "12002" and w["train_after_no"] == "12919"][0]
    assert target_win["start_min"] == 620
    assert target_win["end_min"] == 685
    assert target_win["usable_duration_min"] == 65
