from typing import List, Dict, Any, Tuple
from app.core.config import settings


class WindowEngine:
    """
    Mathematical Sweep-Line Maintenance Window Extraction Engine.
    Processes sorted train section occupancy intervals, applies safety buffers,
    intersects with corridor availability, and computes feasible block windows.
    """

    @classmethod
    def calculate_feasible_windows(
        cls,
        section_id: int,
        corridor_id: int,
        occupancies: List[Dict[str, Any]],
        horizon_start_min: int = 0,
        horizon_end_min: int = 1440,
        buffer_before_min: int = None,
        buffer_after_min: int = None,
        min_window_duration_min: int = 30,
        corridor_opening_start_min: int = 0,
        corridor_opening_end_min: int = 1440
    ) -> List[Dict[str, Any]]:
        b_before = buffer_before_min if buffer_before_min is not None else settings.BUFFER_BEFORE_MIN
        b_after = buffer_after_min if buffer_after_min is not None else settings.BUFFER_AFTER_MIN

        # Filter occupancies for this section
        sec_occ = [
            o for o in occupancies
            if o["section_id"] == section_id and o["estimated_exit_min"] > horizon_start_min and o["estimated_entry_min"] < horizon_end_min
        ]

        # If no train occupancies exist on this section, the track is unobstructed and available for maintenance
        if not sec_occ:
            eff_start = max(horizon_start_min, corridor_opening_start_min)
            eff_end = min(horizon_end_min, corridor_opening_end_min)
            eff_duration = eff_end - eff_start
            if eff_duration >= min_window_duration_min:
                return [{
                    "id": 1,
                    "window_code": f"WIN_SEC{section_id}_01",
                    "section_id": section_id,
                    "corridor_id": corridor_id,
                    "start_min": eff_start,
                    "end_min": eff_end,
                    "usable_duration_min": eff_duration,
                    "raw_gap_min": eff_duration,
                    "train_before_no": "START_OF_DAY",
                    "train_after_no": "END_OF_DAY",
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after,
                        "corridor_start": corridor_opening_start_min,
                        "corridor_end": corridor_opening_end_min,
                        "traffic_status": "UNOBSTRUCTED"
                    },
                    "feasibility": "FEASIBLE",
                    "source": "UNOBSTRUCTED_TRACK_WINDOW"
                }]
            return []

        # Merge overlapping/adjacent train occupancies into unified blocked intervals
        # Train interval = [entry, exit]
        intervals = []
        for o in sec_occ:
            intervals.append({
                "start": max(horizon_start_min, o["estimated_entry_min"]),
                "end": min(horizon_end_min, o["estimated_exit_min"]),
                "train_no": o["train_number"]
            })

        # Sort by start time
        intervals.sort(key=lambda x: x["start"])

        # Merge overlapping train occupancy intervals
        merged_train_blocks = []
        for iv in intervals:
            if not merged_train_blocks:
                merged_train_blocks.append(iv)
            else:
                last = merged_train_blocks[-1]
                if iv["start"] <= last["end"]:
                    # Overlap
                    last["end"] = max(last["end"], iv["end"])
                    last["train_no"] = f"{last['train_no']}, {iv['train_no']}"
                else:
                    merged_train_blocks.append(iv)

        # Sweep-line to find gaps
        candidate_windows = []
        current_time = horizon_start_min
        window_idx = 1

        # Virtual initial train before horizon
        train_before = "START_OF_DAY"

        for blk in merged_train_blocks:
            train_start = blk["start"]
            raw_gap = train_start - current_time

            # Compute usable window after applying safety buffers
            usable_start = current_time + (b_before if current_time > horizon_start_min else 0)
            usable_end = train_start - b_after

            # Intersect with corridor opening hours
            eff_start = max(usable_start, corridor_opening_start_min)
            eff_end = min(usable_end, corridor_opening_end_min)
            eff_duration = eff_end - eff_start

            if eff_duration >= min_window_duration_min:
                candidate_windows.append({
                    "id": window_idx,
                    "window_code": f"WIN_SEC{section_id}_{window_idx:02d}",
                    "section_id": section_id,
                    "corridor_id": corridor_id,
                    "start_min": eff_start,
                    "end_min": eff_end,
                    "usable_duration_min": eff_duration,
                    "raw_gap_min": raw_gap,
                    "train_before_no": train_before,
                    "train_after_no": blk["train_no"],
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after,
                        "corridor_start": corridor_opening_start_min,
                        "corridor_end": corridor_opening_end_min
                    },
                    "feasibility": "FEASIBLE",
                    "source": "SWEEP_LINE_DERIVED"
                })
                window_idx += 1

            current_time = blk["end"]
            train_before = blk["train_no"]

        # Final trailing window from last train to horizon end
        if current_time < horizon_end_min:
            usable_start = current_time + b_before
            usable_end = horizon_end_min
            eff_start = max(usable_start, corridor_opening_start_min)
            eff_end = min(usable_end, corridor_opening_end_min)
            eff_duration = eff_end - eff_start

            if eff_duration >= min_window_duration_min:
                candidate_windows.append({
                    "id": window_idx,
                    "window_code": f"WIN_SEC{section_id}_{window_idx:02d}",
                    "section_id": section_id,
                    "corridor_id": corridor_id,
                    "start_min": eff_start,
                    "end_min": eff_end,
                    "usable_duration_min": eff_duration,
                    "raw_gap_min": horizon_end_min - current_time,
                    "train_before_no": train_before,
                    "train_after_no": "END_OF_DAY",
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after
                    },
                    "feasibility": "FEASIBLE",
                    "source": "SWEEP_LINE_DERIVED"
                })

        return candidate_windows
