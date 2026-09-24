from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings


class WindowEngine:
    """
    Interval Sweep-Line Maintenance Window Extraction Engine for Indian Railways (SIH26027).

    Safety Principles Enforced:
    1. MISSING DATA != FREE TRACK:
       If train timetable or occupancy data is unavailable for a section, the system
       returns DATA_UNAVAILABLE and never a fake 00:00–24:00 window.
    2. VERIFIED_EMPTY_INTERVAL:
       A full-day gap is only generated if the section has verified timetable coverage
       and zero train movements operate on the target date.
    3. EXISTING BLOCKS SUBTRACTION:
       Active, committed, and approved maintenance possessions are treated as hard
       blocked intervals alongside train movements.
    4. MULTI-SECTION COMMON WINDOWS:
       Multi-section demands require mathematically continuous intersection across ALL sections.
    """

    @classmethod
    def derive_windows_for_section(
        cls,
        section_id: int,
        corridor_id: int,
        occupancies: List[Dict[str, Any]],
        existing_blocks: Optional[List[Dict[str, Any]]] = None,
        has_verified_timetable: bool = True,
        has_timetable_data: Optional[bool] = None,
        corridor_opening_start_min: int = 0,
        corridor_opening_end_min: int = 1440,
        buffer_before_min: Optional[int] = None,
        buffer_after_min: Optional[int] = None,
        min_window_duration_min: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Derives feasible maintenance gap windows using interval sweep-line algorithm.
        Applies configurable safety buffers before and after train occupancies and existing blocks.
        """
        if has_timetable_data is not None:
            has_verified_timetable = has_timetable_data

        return cls.calculate_feasible_windows(
            section_id=section_id,
            corridor_id=corridor_id,
            occupancies=occupancies,
            existing_blocks=existing_blocks,
            has_verified_timetable=has_verified_timetable,
            has_timetable_data=has_timetable_data,
            horizon_start_min=0,
            horizon_end_min=1440,
            corridor_opening_start_min=corridor_opening_start_min,
            corridor_opening_end_min=corridor_opening_end_min,
            buffer_before_min=buffer_before_min,
            buffer_after_min=buffer_after_min,
            min_window_duration_min=min_window_duration_min
        )

    @classmethod
    def calculate_feasible_windows(
        cls,
        section_id: int,
        corridor_id: int,
        occupancies: List[Dict[str, Any]],
        existing_blocks: Optional[List[Dict[str, Any]]] = None,
        has_verified_timetable: bool = True,
        has_timetable_data: Optional[bool] = None,
        horizon_start_min: int = 0,
        horizon_end_min: int = 1440,
        corridor_opening_start_min: int = 0,
        corridor_opening_end_min: int = 1440,
        buffer_before_min: Optional[int] = None,
        buffer_after_min: Optional[int] = None,
        min_window_duration_min: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Computes mathematically verified feasible maintenance windows for a specific railway section.
        """
        if has_timetable_data is not None:
            has_verified_timetable = has_timetable_data

        b_before = buffer_before_min if buffer_before_min is not None else settings.BUFFER_BEFORE_MIN
        b_after = buffer_after_min if buffer_after_min is not None else settings.BUFFER_AFTER_MIN

        if horizon_end_min <= horizon_start_min:
            return []

        # CRITICAL SAFETY RULE: Missing Timetable Data != Free Track
        # If timetable data is not verified, no feasible windows can be certified.
        if not has_verified_timetable:
            return []

        # Filter train occupancies for this section
        sec_occ = [
            o for o in occupancies
            if o.get("section_id") == section_id and
            o.get("estimated_exit_min", 0) > horizon_start_min and
            o.get("estimated_entry_min", 0) < horizon_end_min
        ]

        # Filter existing blocks for this section
        sec_blocks = [
            b for b in (existing_blocks or [])
            if b.get("section_id") == section_id and
            b.get("end_min", 0) > horizon_start_min and
            b.get("start_min", 0) < horizon_end_min
        ]

        # Verified quiet section (True empty network)
        if not sec_occ and not sec_blocks and has_verified_timetable:
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
                        "traffic_status": "VERIFIED_EMPTY_INTERVAL"
                    },
                    "feasibility": "FEASIBLE",
                    "source": "VERIFIED_EMPTY_INTERVAL"
                }]
            return []

        # Build blocked intervals from both train occupancies and existing blocks
        intervals = []
        for o in sec_occ:
            intervals.append({
                "start": max(horizon_start_min, o["estimated_entry_min"]),
                "end": min(horizon_end_min, o["estimated_exit_min"]),
                "identifier": str(o.get("train_number", "TRAIN")),
                "type": "TRAIN"
            })

        for b in sec_blocks:
            intervals.append({
                "start": max(horizon_start_min, b["start_min"]),
                "end": min(horizon_end_min, b["end_min"]),
                "identifier": str(b.get("block_code", "EXISTING_BLOCK")),
                "type": "BLOCK"
            })

        # Sort blocked intervals by start time
        intervals.sort(key=lambda x: x["start"])

        # Merge overlapping blocked intervals
        merged_blocks = []
        for iv in intervals:
            if not merged_blocks:
                merged_blocks.append(iv)
            else:
                last = merged_blocks[-1]
                if iv["start"] <= last["end"]:
                    last["end"] = max(last["end"], iv["end"])
                    last["identifier"] = f"{last['identifier']}, {iv['identifier']}"
                else:
                    merged_blocks.append(iv)

        # Sweep-line to extract feasible gaps
        candidate_windows = []
        current_time = horizon_start_min
        window_idx = 1
        item_before = "HEAD_OF_SCHEDULE"

        has_live = any(
            o.get("data_quality_state") in ("LIVE", "LIVE_TELEMETRY") or 
            o.get("source") in ("LIVE", "LIVE_TELEMETRY") or
            o.get("is_live") is True
            for o in sec_occ
        )
        source_label = "LIVE TELEMETRY + STATIC TIMETABLE" if has_live else "STATIC TIMETABLE + EXISTING BLOCKS"

        for blk in merged_blocks:
            block_start = blk["start"]
            raw_gap = block_start - current_time

            usable_start = current_time + (b_before if current_time > horizon_start_min else 0)
            usable_end = block_start - b_after

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
                    "train_before_no": item_before,
                    "train_after_no": blk["identifier"],
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after,
                        "corridor_start": corridor_opening_start_min,
                        "corridor_end": corridor_opening_end_min
                    },
                    "feasibility": "FEASIBLE",
                    "source": source_label
                })
                window_idx += 1

            current_time = blk["end"]
            item_before = blk["identifier"]

        # Final trailing window
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
                    "train_before_no": item_before,
                    "train_after_no": "TAIL_OF_SCHEDULE",
                    "constraints_applied_json": {
                        "buffer_before_min": b_before,
                        "buffer_after_min": b_after
                    },
                    "feasibility": "FEASIBLE",
                    "source": source_label
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
        first_sec_wins = [w for w in section_windows_map[section_ids[0]] if w.get("feasibility") == "FEASIBLE"]
        if not first_sec_wins:
            return []

        current_intervals = [(w["start_min"], w["end_min"]) for w in first_sec_wins]

        for sec_id in section_ids[1:]:
            sec_wins = [w for w in section_windows_map[sec_id] if w.get("feasibility") == "FEASIBLE"]
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
        has_verified_timetable: bool = True,
        buffer_before_min: Optional[int] = None,
        buffer_after_min: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validates whether the requested window [req_start_min, req_end_min] is feasible across ALL affected sections.
        Detects conflicting train movements or blocks, applies safety buffers, and generates actual recommended alternative windows.
        """
        b_before = buffer_before_min if buffer_before_min is not None else settings.BUFFER_BEFORE_MIN
        b_after = buffer_after_min if buffer_after_min is not None else settings.BUFFER_AFTER_MIN

        if not has_verified_timetable:
            return {
                "is_feasible": False,
                "reason": "DATA_UNAVAILABLE: Timetable data not verified for affected sections.",
                "conflicts": [],
                "feasible_alternatives": [],
                "affected_sections": section_ids
            }

        affected_sec_set = set(section_ids) if section_ids else set()
        conflicts = []

        # Check train conflicts
        for o in occupancies:
            if not affected_sec_set or o.get("section_id") in affected_sec_set:
                t_start = o.get("estimated_entry_min", 0) - b_after
                t_end = o.get("estimated_exit_min", 0) + b_before
                if max(req_start_min, t_start) < min(req_end_min, t_end):
                    conflicts.append({
                        "type": "TRAIN_CONFLICT",
                        "train_number": o.get("train_number"),
                        "train_name": o.get("train_name"),
                        "section_id": o.get("section_id"),
                        "entry_min": o.get("estimated_entry_min"),
                        "exit_min": o.get("estimated_exit_min")
                    })

        # Check existing block conflicts
        for b in (existing_blocks or []):
            if not affected_sec_set or b.get("section_id") in affected_sec_set:
                b_start = b.get("start_min", 0) - b_after
                b_end = b.get("end_min", 0) + b_before
                if max(req_start_min, b_start) < min(req_end_min, b_end):
                    conflicts.append({
                        "type": "EXISTING_BLOCK_CONFLICT",
                        "block_code": b.get("block_code"),
                        "section_id": b.get("section_id"),
                        "start_min": b.get("start_min"),
                        "end_min": b.get("end_min")
                    })

        # Calculate feasible alternatives across all affected sections
        sec_map = {}
        for s_id in (section_ids or [1]):
            sec_map[s_id] = cls.derive_windows_for_section(
                section_id=s_id,
                corridor_id=corridor_id,
                occupancies=occupancies,
                existing_blocks=existing_blocks,
                has_verified_timetable=has_verified_timetable,
                min_window_duration_min=duration_min
            )

        if len(sec_map) > 1:
            alternatives = cls.intersect_windows_for_sections(sec_map, min_duration_min=duration_min)
        else:
            first_id = list(sec_map.keys())[0]
            alternatives = [w for w in sec_map[first_id] if w.get("feasibility") == "FEASIBLE"]

        is_feasible = (len(conflicts) == 0 and (req_end_min - req_start_min) >= duration_min)

        return {
            "is_feasible": is_feasible,
            "conflicts_count": len(conflicts),
            "conflicts": conflicts,
            "feasible_alternatives": alternatives,
            "recommended_alternatives": alternatives,
            "alternatives": alternatives,
            "requested_start_min": req_start_min,
            "requested_end_min": req_end_min,
            "requested_duration_min": duration_min,
            "affected_sections": section_ids
        }
