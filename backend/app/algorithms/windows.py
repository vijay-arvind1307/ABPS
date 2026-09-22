from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings


class WindowEngine:
    """
    Mathematical Sweep-Line Maintenance Window Extraction & Validation Engine for IR-ABPS.
    Complies with SIH26027 Requirements:
    - Date-specific, section-specific, and request-specific window calculations.
    - True empty network vs DATA_UNAVAILABLE distinction (never defaults to 00:00-24:00).
    - Multi-section interval intersection for multi-section possessions.
    - Exact requested window feasibility checking with explicit train conflict reporting and alternatives.
    """

    @classmethod
    def calculate_feasible_windows(
        cls,
        section_id: int,
        corridor_id: int,
        occupancies: List[Dict[str, Any]],
        horizon_start_min: int = 0,
        horizon_end_min: int = 1440,
        buffer_before_min: Optional[int] = None,
        buffer_after_min: Optional[int] = None,
        min_window_duration_min: int = 30,
        corridor_opening_start_min: int = 0,
        corridor_opening_end_min: int = 1440,
        has_timetable_data: bool = True
    ) -> List[Dict[str, Any]]:
        b_before = buffer_before_min if buffer_before_min is not None else settings.BUFFER_BEFORE_MIN
        b_after = buffer_after_min if buffer_after_min is not None else settings.BUFFER_AFTER_MIN

        # If timetable data is completely missing, do not fabricate 00:00–24:00
        if not has_timetable_data:
            return []

        # Filter occupancies for this section
        sec_occ = [
            o for o in occupancies
            if o.get("section_id") == section_id and o.get("estimated_exit_min", 0) > horizon_start_min and o.get("estimated_entry_min", 0) < horizon_end_min
        ]

        # If no train occupancies exist in this horizon for a verified timetable section:
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
                        "traffic_status": "VERIFIED_QUIET_INTERVAL"
                    },
                    "feasibility": "FEASIBLE",
                    "source": "STATIC_TIMETABLE_VERIFIED"
                }]
            return []

        # Merge overlapping/adjacent train occupancies into unified blocked intervals
        intervals = []
        for o in sec_occ:
            intervals.append({
                "start": max(horizon_start_min, o["estimated_entry_min"]),
                "end": min(horizon_end_min, o["estimated_exit_min"]),
                "train_no": str(o.get("train_number", "UNKNOWN"))
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
                    last["end"] = max(last["end"], iv["end"])
                    last["train_no"] = f"{last['train_no']}, {iv['train_no']}"
                else:
                    merged_train_blocks.append(iv)

        # Sweep-line to find gaps
        candidate_windows = []
        current_time = horizon_start_min
        window_idx = 1
        train_before = "HEAD_OF_SCHEDULE"

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

            if eff_duration >= min_window_duration_min and eff_end > eff_start:
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
                    "source": "LIVE TELEMETRY + STATIC TIMETABLE" if any(o.get("is_live", False) for o in sec_occ) else "STATIC TIMETABLE + EXISTING BLOCKS"
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

            if eff_duration >= min_window_duration_min and eff_end > eff_start:
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
                    "train_after_no": "TAIL_OF_SCHEDULE",
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after
                    },
                    "feasibility": "FEASIBLE",
                    "source": "LIVE TELEMETRY + STATIC TIMETABLE" if any(o.get("is_live", False) for o in sec_occ) else "STATIC TIMETABLE + EXISTING BLOCKS"
                })

        return candidate_windows

    @classmethod
    def intersect_windows_for_sections(
        cls,
        section_windows_map: Dict[int, List[Dict[str, Any]]],
        min_duration_min: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Computes the common feasible intervals across multiple sections.
        For a multi-section possession (Section A + Section B + Section C),
        the available block must satisfy ALL affected sections simultaneously.
        """
        if not section_windows_map:
            return []

        section_ids = list(section_windows_map.keys())
        first_sec_wins = section_windows_map[section_ids[0]]
        if not first_sec_wins:
            return []

        # Start with intervals from first section
        current_intervals = [(w["start_min"], w["end_min"]) for w in first_sec_wins]

        for sec_id in section_ids[1:]:
            sec_wins = section_windows_map[sec_id]
            next_intervals = []
            for s1, e1 in current_intervals:
                for w in sec_wins:
                    s2, e2 = w["start_min"], w["end_min"]
                    inter_s = max(s1, s2)
                    inter_e = min(e1, e2)
                    if inter_e - inter_s >= min_duration_min:
                        next_intervals.append((inter_s, inter_e))
            current_intervals = next_intervals
            if not current_intervals:
                break

        # Deduplicate and sort intervals
        current_intervals.sort(key=lambda x: x[0])
        merged = []
        for s, e in current_intervals:
            if not merged:
                merged.append((s, e))
            else:
                last_s, last_e = merged[-1]
                if s <= last_e:
                    merged[-1] = (last_s, max(last_e, e))
                else:
                    merged.append((s, e))

        res = []
        for idx, (s, e) in enumerate(merged, start=1):
            res.append({
                "id": idx,
                "window_code": f"MULTI_SEC_WIN_{idx:02d}",
                "section_ids": section_ids,
                "start_min": s,
                "end_min": e,
                "usable_duration_min": e - s,
                "feasibility": "FEASIBLE",
                "source": "MULTI_SECTION_INTERSECTION"
            })
        return res

    @classmethod
    def check_requested_window(
        cls,
        section_ids: List[int],
        corridor_id: int,
        req_start_min: int,
        req_end_min: int,
        duration_min: int,
        occupancies: List[Dict[str, Any]],
        existing_blocks: Optional[List[Dict[str, Any]]] = None,
        buffer_before_min: Optional[int] = None,
        buffer_after_min: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validates whether the requested window [req_start_min, req_end_min] is feasible across ALL affected sections.
        Detects conflicting train movements or blocks, applies safety buffers, and generates actual recommended alternative windows.
        """
        b_before = buffer_before_min if buffer_before_min is not None else settings.BUFFER_BEFORE_MIN
        b_after = buffer_after_min if buffer_after_min is not None else settings.BUFFER_AFTER_MIN

        # Filter occupancies and existing blocks for affected sections
        affected_sec_set = set(section_ids) if section_ids else set()

        conflicts = []
        for o in occupancies:
            if not affected_sec_set or o.get("section_id") in affected_sec_set:
                o_entry = o.get("estimated_entry_min", 0)
                o_exit = o.get("estimated_exit_min", 0)
                # Check intersection: max(start1, start2) < min(end1, end2)
                # Train safety envelope = [o_entry - b_after, o_exit + b_before]
                buf_entry = max(0, o_entry - b_after)
                buf_exit = min(1440, o_exit + b_before)
                if max(req_start_min, buf_entry) < min(req_end_min, buf_exit):
                    conflicts.append({
                        "type": "TRAIN_CONFLICT",
                        "train_number": str(o.get("train_number", "UNKNOWN")),
                        "train_name": str(o.get("train_name", "Express")),
                        "section_id": o.get("section_id"),
                        "occupied_from": f"{o_entry // 60:02d}:{o_entry % 60:02d}",
                        "occupied_to": f"{o_exit // 60:02d}:{o_exit % 60:02d}",
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after,
                        "description": (
                            f"Conflict with Train {o.get('train_number')} ({o.get('train_name', 'Express')}) "
                            f"occupying section from {o_entry // 60:02d}:{o_entry % 60:02d} to {o_exit // 60:02d}:{o_exit % 60:02d} "
                            f"(with {b_before}m safety buffer)."
                        )
                    })

        # Check existing blocks
        if existing_blocks:
            for blk in existing_blocks:
                if not affected_sec_set or blk.get("section_id") in affected_sec_set:
                    blk_start = blk.get("start_min", 0)
                    blk_end = blk.get("end_min", 0)
                    if max(req_start_min, blk_start) < min(req_end_min, blk_end):
                        conflicts.append({
                            "type": "EXISTING_BLOCK_CONFLICT",
                            "block_code": blk.get("plan_code") or blk.get("job_code") or "APPROVED_BLOCK",
                            "section_id": blk.get("section_id"),
                            "occupied_from": f"{blk_start // 60:02d}:{blk_start % 60:02d}",
                            "occupied_to": f"{blk_end // 60:02d}:{blk_end % 60:02d}",
                            "description": f"Overlaps with approved maintenance block {blk.get('plan_code', 'COMMITTED')}."
                        })

        # Calculate genuine alternative windows
        sec_wins_map = {}
        for s_id in (section_ids or [0]):
            wins = cls.calculate_feasible_windows(
                section_id=s_id,
                corridor_id=corridor_id,
                occupancies=occupancies,
                min_window_duration_min=duration_min,
                buffer_before_min=b_before,
                buffer_after_min=b_after,
                has_timetable_data=len(occupancies) > 0
            )
            sec_wins_map[s_id] = wins

        if len(sec_wins_map) > 1:
            feasible_alternatives = cls.intersect_windows_for_sections(sec_wins_map, min_duration_min=duration_min)
        else:
            first_s_id = list(sec_wins_map.keys())[0] if sec_wins_map else 0
            feasible_alternatives = sec_wins_map.get(first_s_id, [])

        # Filter out the requested window from alternatives
        formatted_alternatives = []
        for alt in feasible_alternatives[:5]:
            s_hh, s_mm = divmod(alt["start_min"], 60)
            e_hh, e_mm = divmod(alt["end_min"], 60)
            alt_str = f"{s_hh:02d}:{s_mm:02d} – {e_hh:02d}:{e_mm:02d}"
            formatted_alternatives.append({
                "start_min": alt["start_min"],
                "end_min": alt["end_min"],
                "window": alt_str,
                "duration_min": alt["usable_duration_min"]
            })

        is_feasible = (len(conflicts) == 0) and (req_end_min - req_start_min >= duration_min)

        return {
            "feasible": is_feasible,
            "is_feasible": is_feasible,
            "status": "FEASIBLE" if is_feasible else "NOT_FEASIBLE",
            "requested_window": f"{req_start_min // 60:02d}:{req_start_min % 60:02d} – {req_end_min // 60:02d}:{req_end_min % 60:02d}",
            "duration_min": duration_min,
            "conflicts_count": len(conflicts),
            "conflicts": conflicts,
            "recommended_alternatives": formatted_alternatives,
            "message": (
                "Requested maintenance window is fully feasible and conflict-free."
                if is_feasible else
                f"Requested window conflicts with {len(conflicts)} train movement(s) or possession(s)."
            )
        }
