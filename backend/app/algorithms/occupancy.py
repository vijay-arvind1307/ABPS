from typing import List, Dict, Any, Optional
from datetime import datetime


class OccupancyEngine:
    """
    Computes precise Train Section Occupancy intervals [entry_min, exit_min]
    across railway sections based on timetable stops, live RailRadar delays,
    speed curves, and geometric track section interpolation.

    Per IR Operational Safety Principles:
    - Traversal times across non-stop intermediate block sections are interpolated
      from enclosing timetable halts and line speed limits.
    - Active train GPS positions directly anchor current block section occupancy.
    - Estimates are clearly labeled with confidence scores and source metadata.
    """

    @classmethod
    def calculate_section_occupancies(
        cls,
        train: Dict[str, Any],
        route_stops: List[Dict[str, Any]],
        sections: List[Dict[str, Any]],
        current_delay_min: int = 0,
        active_movement: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculates section occupancies across all candidate sections for this train.
        Handles:
        1. Direct stop-to-stop sections
        2. Intermediate non-stop sections via distance-based speed interpolation
        3. Real-time active GPS position anchoring on the current section
        """
        occupancies = []
        if not route_stops or len(route_stops) < 2:
            return occupancies

        # Sort stops by sequence
        sorted_stops = sorted(route_stops, key=lambda s: s.get("sequence", 0))
        stop_dict = {s["station_id"]: s for s in sorted_stops}

        # Build cumulative distance mapping for stations from stops
        stn_dist_map = {}
        for s in sorted_stops:
            stn_dist_map[s["station_id"]] = float(s.get("distance_km", 0.0))

        # Propagate distances along adjacent sections forward and backward
        for _ in range(max(1, len(sections))):
            for sec in sections:
                f_id = sec.get("from_station_id")
                t_id = sec.get("to_station_id")
                s_len = float(sec.get("length_km", 15.0))
                if f_id in stn_dist_map and t_id not in stn_dist_map:
                    stn_dist_map[t_id] = stn_dist_map[f_id] + s_len
                elif t_id in stn_dist_map and f_id not in stn_dist_map:
                    stn_dist_map[f_id] = max(0.0, stn_dist_map[t_id] - s_len)

        # Check for active movement
        active_sec_id = None
        active_speed = 70.0
        if active_movement:
            active_sec_id = active_movement.get("current_section_id")
            active_speed = max(20.0, float(active_movement.get("speed_kmh") or 70.0))

        matched_sec_ids = set()

        # 1. First Pass: Direct stop-to-stop sections
        for sec in sections:
            from_stn_id = sec.get("from_station_id")
            to_stn_id = sec.get("to_station_id")

            if from_stn_id in stop_dict and to_stn_id in stop_dict:
                stop_a = stop_dict[from_stn_id]
                stop_b = stop_dict[to_stn_id]

                if stop_a["sequence"] < stop_b["sequence"]:
                    dep_a = int(stop_a["departure_min"]) + current_delay_min
                    arr_b = int(stop_b["arrival_min"]) + current_delay_min

                    entry_min = dep_a
                    exit_min = max(entry_min + 3, arr_b + 2)

                    confidence = 0.96 if current_delay_min == 0 else 0.92
                    is_active = (active_sec_id == sec["id"])

                    occupancies.append({
                        "train_number": train["train_number"],
                        "train_name": train["train_name"],
                        "train_type": train.get("train_type", "EXPRESS"),
                        "priority_level": train.get("priority_level", 2),
                        "section_id": sec["id"],
                        "section_code": sec.get("section_id", f"SEC_{sec['id']}"),
                        "section_name": sec.get("name", f"Section {sec['id']}"),
                        "estimated_entry_min": entry_min,
                        "estimated_exit_min": exit_min,
                        "delay_applied_min": current_delay_min,
                        "confidence": 0.98 if is_active else confidence,
                        "is_active_position": is_active,
                        "source": "RAILRADAR_ACTIVE_POSITION" if is_active else "TIMETABLE_LIVE_OCCUPANCY_MODEL"
                    })
                    matched_sec_ids.add(sec["id"])

        # 2. Second Pass: Intermediate block sections without scheduled halts
        first_stop = sorted_stops[0]
        last_stop = sorted_stops[-1]
        route_min_km = float(first_stop.get("distance_km", 0.0))
        route_max_km = float(last_stop.get("distance_km", 500.0))

        for sec in sections:
            if sec["id"] in matched_sec_ids:
                continue

            sec_from_id = sec.get("from_station_id")
            sec_to_id = sec.get("to_station_id")
            sec_len = float(sec.get("length_km", 15.0))

            from_km = stn_dist_map.get(sec_from_id)
            to_km = stn_dist_map.get(sec_to_id)

            if from_km is None and to_km is not None:
                from_km = max(0.0, to_km - sec_len)
            elif to_km is None and from_km is not None:
                to_km = from_km + sec_len

            if from_km is None or to_km is None:
                continue

            # Check if section lies within route span
            if to_km < route_min_km or from_km > route_max_km:
                continue

            # Find enclosing stops
            prev_stop = None
            next_stop = None

            for s in sorted_stops:
                s_dist = float(s.get("distance_km", 0.0))
                if s_dist <= from_km:
                    prev_stop = s
                elif s_dist >= to_km and next_stop is None:
                    next_stop = s
                    break

            if prev_stop and next_stop and prev_stop["station_id"] != next_stop["station_id"]:
                p_dist = float(prev_stop.get("distance_km", 0.0))
                n_dist = float(next_stop.get("distance_km", 0.0))
                dist_span = max(1.0, n_dist - p_dist)

                p_dep = int(prev_stop.get("departure_min", 0)) + current_delay_min
                n_arr = int(next_stop.get("arrival_min", 0)) + current_delay_min
                time_span = max(3, n_arr - p_dep)

                t_in_ratio = max(0.0, min(1.0, (from_km - p_dist) / dist_span))
                t_out_ratio = max(0.0, min(1.0, (to_km - p_dist) / dist_span))

                entry_min = int(p_dep + t_in_ratio * time_span)
                exit_min = max(entry_min + 3, int(p_dep + t_out_ratio * time_span) + 2)

                is_active = (active_sec_id == sec["id"])

                occupancies.append({
                    "train_number": train["train_number"],
                    "train_name": train["train_name"],
                    "train_type": train.get("train_type", "EXPRESS"),
                    "priority_level": train.get("priority_level", 2),
                    "section_id": sec["id"],
                    "section_code": sec.get("section_id", f"SEC_{sec['id']}"),
                    "section_name": sec.get("name", f"Section {sec['id']}"),
                    "estimated_entry_min": entry_min,
                    "estimated_exit_min": exit_min,
                    "delay_applied_min": current_delay_min,
                    "confidence": 0.92 if is_active else 0.88,
                    "is_active_position": is_active,
                    "source": "RAILRADAR_ACTIVE_POSITION" if is_active else "INTERPOLATED_CORRIDOR_OCCUPANCY"
                })
                matched_sec_ids.add(sec["id"])

        # 3. Third Pass: Active GPS train position anchoring
        if active_sec_id and active_sec_id not in matched_sec_ids:
            target_sec = next((s for s in sections if s["id"] == active_sec_id), None)
            if target_sec:
                now = datetime.utcnow()
                ist_min = (now.hour * 60 + now.minute + 330) % 1440
                sec_len = float(target_sec.get("length_km", 15.0))
                traverse_min = max(4, int((sec_len / active_speed) * 60.0))

                occupancies.append({
                    "train_number": train["train_number"],
                    "train_name": train["train_name"],
                    "train_type": train.get("train_type", "EXPRESS"),
                    "priority_level": train.get("priority_level", 2),
                    "section_id": target_sec["id"],
                    "section_code": target_sec.get("section_id", f"SEC_{target_sec['id']}"),
                    "section_name": target_sec.get("name", f"Section {target_sec['id']}"),
                    "estimated_entry_min": max(0, ist_min - 2),
                    "estimated_exit_min": min(1440, ist_min + traverse_min + 2),
                    "delay_applied_min": current_delay_min,
                    "confidence": 0.98,
                    "is_active_position": True,
                    "source": "RAILRADAR_GPS_ACTIVE_TRACK"
                })

        return occupancies
