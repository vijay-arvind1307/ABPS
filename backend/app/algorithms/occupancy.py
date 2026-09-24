from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque


class OccupancyEngine:
    """
    Computes precise Train Section Occupancy intervals [entry_min, exit_min]
    across railway sections based on timetable stops, live RailRadar delays,
    speed curves, and geometric track section interpolation.

    Per IR Operational Safety Principles:
    - Traversal times across non-stop intermediate block sections are derived
      from enclosing timetable halts, line speed limits, and section distance.
    - Reverse-direction (DOWN) movements are correctly calculated with physical
      traversal durations, never arbitrary 3-minute clampings.
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
        1. Direct stop-to-stop sections (UP and DOWN directions)
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

        # Fast O(V + E) BFS distance propagation for intermediate stations
        adj = {}
        sec_lookup = {}
        for sec in sections:
            f_id = sec.get("from_station_id")
            t_id = sec.get("to_station_id")
            s_len = float(sec.get("length_km", 15.0))
            if f_id and t_id:
                adj.setdefault(f_id, []).append((t_id, s_len))
                adj.setdefault(t_id, []).append((f_id, -s_len))
                sec_lookup[(f_id, t_id)] = sec
                sec_lookup[(t_id, f_id)] = sec

        queue = deque(list(stn_dist_map.keys()))
        while queue:
            curr_id = queue.popleft()
            curr_dist = stn_dist_map[curr_id]
            for neighbor_id, delta in adj.get(curr_id, []):
                if neighbor_id not in stn_dist_map:
                    stn_dist_map[neighbor_id] = max(0.0, curr_dist + delta)
                    queue.append(neighbor_id)

        # Check for active movement
        active_sec_id = None
        active_speed = 70.0
        if active_movement:
            active_sec_id = active_movement.get("current_section_id")
            active_speed = max(20.0, float(active_movement.get("speed_kmh") or 70.0))

        matched_sec_ids = set()

        # 1. First Pass: Direct stop-to-stop sections (Handles UP and DOWN)
        for sec in sections:
            from_stn_id = sec.get("from_station_id")
            to_stn_id = sec.get("to_station_id")
            s_len = float(sec.get("length_km", 15.0))
            max_speed = float(sec.get("max_speed_kmh", 110.0)) or 110.0
            nominal_transit_min = max(6, int((s_len / max_speed) * 60.0))

            if from_stn_id in stop_dict and to_stn_id in stop_dict:
                stop_a = stop_dict[from_stn_id]
                stop_b = stop_dict[to_stn_id]

                if stop_a["sequence"] < stop_b["sequence"]:
                    # Train travels along corridor graph (e.g. MDU -> TEN): Indian Railways DOWN movement (↓ DOWN)
                    dep_a = int(stop_a["departure_min"]) + current_delay_min
                    arr_b = int(stop_b["arrival_min"]) + current_delay_min

                    raw_entry = dep_a
                    raw_exit = max(raw_entry + nominal_transit_min, arr_b)
                    direction = "DOWN"
                elif stop_b["sequence"] < stop_a["sequence"]:
                    # Train travels against corridor graph (e.g. TEN -> MDU): Indian Railways UP movement (↑ UP)
                    dep_b = int(stop_b["departure_min"]) + current_delay_min
                    arr_a = int(stop_a["arrival_min"]) + current_delay_min

                    raw_entry = dep_b
                    raw_exit = max(raw_entry + nominal_transit_min, arr_a)
                    direction = "UP"
                else:
                    continue

                dur = max(1, raw_exit - raw_entry)
                # Normalize multi-day arrival/departure minutes to 24-hour target date cycle
                norm_entry = raw_entry % 1440
                norm_exit = norm_entry + dur

                is_active = (active_sec_id == sec["id"])
                confidence = 0.98 if is_active else (0.95 if current_delay_min == 0 else 0.90)

                occupancies.append({
                    "train_number": train["train_number"],
                    "train_name": train.get("train_name", f"Train {train['train_number']}"),
                    "train_type": train.get("train_type", "EXPRESS"),
                    "priority_level": train.get("priority_level", 2),
                    "section_id": sec["id"],
                    "section_code": sec.get("section_id", f"SEC_{sec['id']}"),
                    "section_name": sec.get("name", f"Section {sec['id']}"),
                    "from_station_code": sec.get("from_station_code"),
                    "to_station_code": sec.get("to_station_code"),
                    "direction": direction,
                    "estimated_entry_min": norm_entry,
                    "estimated_exit_min": norm_exit,
                    "raw_entry_min": raw_entry,
                    "raw_exit_min": raw_exit,
                    "day_offset": raw_entry // 1440,
                    "traversal_duration_min": dur,
                    "delay_applied_min": current_delay_min,
                    "confidence": confidence,
                    "is_active_position": is_active,
                    "data_quality_state": "AUTHORITATIVE_WTT",
                    "source": "RAILRADAR_ACTIVE_POSITION" if is_active else "TIMETABLE_WTT"
                })
                matched_sec_ids.add(sec["id"])

        # 2. Second Pass: Intermediate block sections without scheduled halts
        first_stop = sorted_stops[0]
        last_stop = sorted_stops[-1]
        route_min_km = min(float(first_stop.get("distance_km", 0.0)), float(last_stop.get("distance_km", 0.0)))
        route_max_km = max(float(first_stop.get("distance_km", 0.0)), float(last_stop.get("distance_km", 500.0)))
        is_route_decreasing = float(first_stop.get("distance_km", 0.0)) > float(last_stop.get("distance_km", 0.0))

        for sec in sections:
            if sec["id"] in matched_sec_ids:
                continue

            sec_from_id = sec.get("from_station_id")
            sec_to_id = sec.get("to_station_id")
            sec_len = float(sec.get("length_km", 15.0))
            sec_speed = float(sec.get("max_speed_kmh", 100.0)) or 100.0
            nominal_transit_min = max(6, int((sec_len / sec_speed) * 60.0))

            from_km = stn_dist_map.get(sec_from_id)
            to_km = stn_dist_map.get(sec_to_id)

            if from_km is None and to_km is not None:
                from_km = max(0.0, to_km - sec_len)
            elif to_km is None and from_km is not None:
                to_km = from_km + sec_len

            if from_km is None or to_km is None:
                continue

            sec_min_km = min(from_km, to_km)
            sec_max_km = max(from_km, to_km)

            # Check if section lies within route span
            if sec_max_km < route_min_km or sec_min_km > route_max_km:
                continue

            # Find enclosing timetable stops
            prev_stop = None
            next_stop = None

            if not is_route_decreasing:
                # Forward distance order along corridor: DOWN movement (↓ DOWN)
                for s in sorted_stops:
                    s_dist = float(s.get("distance_km", 0.0))
                    if s_dist <= sec_min_km:
                        prev_stop = s
                    elif s_dist >= sec_max_km and next_stop is None:
                        next_stop = s
                        break
                direction = "DOWN"
            else:
                # Reverse distance order along corridor: UP movement (↑ UP)
                for s in sorted_stops:
                    s_dist = float(s.get("distance_km", 0.0))
                    if s_dist >= sec_max_km:
                        prev_stop = s
                    elif s_dist <= sec_min_km and next_stop is None:
                        next_stop = s
                        break
                direction = "UP"

            if prev_stop and next_stop and prev_stop["station_id"] != next_stop["station_id"]:
                p_dist = float(prev_stop.get("distance_km", 0.0))
                n_dist = float(next_stop.get("distance_km", 0.0))
                dist_span = max(1.0, abs(n_dist - p_dist))

                p_dep = int(prev_stop.get("departure_min", 0)) + current_delay_min
                n_arr = int(next_stop.get("arrival_min", 0)) + current_delay_min
                time_span = max(nominal_transit_min, n_arr - p_dep)

                # Traversal ratio along train direction
                if not is_route_decreasing:
                    t_in_ratio = max(0.0, min(1.0, (sec_min_km - p_dist) / dist_span))
                    t_out_ratio = max(0.0, min(1.0, (sec_max_km - p_dist) / dist_span))
                else:
                    t_in_ratio = max(0.0, min(1.0, (p_dist - sec_max_km) / dist_span))
                    t_out_ratio = max(0.0, min(1.0, (p_dist - sec_min_km) / dist_span))

                raw_entry = int(p_dep + t_in_ratio * time_span)
                raw_exit = max(raw_entry + nominal_transit_min, int(p_dep + t_out_ratio * time_span))
                dur = max(1, raw_exit - raw_entry)

                norm_entry = raw_entry % 1440
                norm_exit = norm_entry + dur

                is_active = (active_sec_id == sec["id"])
                confidence = 0.90 if is_active else 0.85

                occupancies.append({
                    "train_number": train["train_number"],
                    "train_name": train.get("train_name", f"Train {train['train_number']}"),
                    "train_type": train.get("train_type", "EXPRESS"),
                    "priority_level": train.get("priority_level", 2),
                    "section_id": sec["id"],
                    "section_code": sec.get("section_id", f"SEC_{sec['id']}"),
                    "section_name": sec.get("name", f"Section {sec['id']}"),
                    "from_station_code": sec.get("from_station_code"),
                    "to_station_code": sec.get("to_station_code"),
                    "direction": direction,
                    "estimated_entry_min": norm_entry,
                    "estimated_exit_min": norm_exit,
                    "raw_entry_min": raw_entry,
                    "raw_exit_min": raw_exit,
                    "day_offset": raw_entry // 1440,
                    "traversal_duration_min": dur,
                    "delay_applied_min": current_delay_min,
                    "confidence": confidence,
                    "is_active_position": is_active,
                    "data_quality_state": "INTERPOLATED_SPEED_PROFILE",
                    "source": "RAILRADAR_ACTIVE_POSITION" if is_active else "INTERPOLATED_WTT"
                })
                matched_sec_ids.add(sec["id"])

        # 3. Third Pass: Active GPS train position anchoring
        if active_sec_id and active_sec_id not in matched_sec_ids:
            target_sec = next((s for s in sections if s["id"] == active_sec_id), None)
            if target_sec:
                cur_min = (datetime.utcnow().hour * 60 + datetime.utcnow().minute)
                sec_len = float(target_sec.get("length_km", 15.0))
                remaining_min = max(5, int((sec_len / max(20.0, active_speed)) * 60.0))

                norm_entry = max(0, cur_min - 5) % 1440
                dur = remaining_min + 5
                norm_exit = norm_entry + dur

                occupancies.append({
                    "train_number": train["train_number"],
                    "train_name": train.get("train_name", f"Train {train['train_number']}"),
                    "train_type": train.get("train_type", "EXPRESS"),
                    "priority_level": train.get("priority_level", 2),
                    "section_id": target_sec["id"],
                    "section_code": target_sec.get("section_id", f"SEC_{target_sec['id']}"),
                    "section_name": target_sec.get("name", f"Section {target_sec['id']}"),
                    "from_station_code": target_sec.get("from_station_code"),
                    "to_station_code": target_sec.get("to_station_code"),
                    "direction": active_movement.get("direction", "DOWN"),
                    "estimated_entry_min": norm_entry,
                    "estimated_exit_min": norm_exit,
                    "raw_entry_min": max(0, cur_min - 5),
                    "raw_exit_min": cur_min + remaining_min,
                    "day_offset": 0,
                    "traversal_duration_min": dur,
                    "delay_applied_min": current_delay_min,
                    "confidence": 0.98,
                    "is_active_position": True,
                    "data_quality_state": "LIVE_ANCHORED",
                    "source": "RAILRADAR_ACTIVE_POSITION"
                })

        return occupancies
