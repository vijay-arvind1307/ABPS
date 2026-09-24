import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import {
  Train, Clock, AlertTriangle, ShieldCheck, Users,
  ChevronRight, ZoomIn, ZoomOut, RotateCcw, Maximize2,
  Filter, Layers, ArrowUp, ArrowDown, Sparkles, CheckCircle2,
  Activity, Radio, Compass, AlertCircle
} from 'lucide-react';

// ── Helpers ────────────────────────────────────────────────────────
const mToTime = (min) => {
  if (min === null || min === undefined) return '—';
  const h = Math.floor(min / 60) % 24;
  const m = Math.floor(min % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
};

// ── Layout Scale Constants ─────────────────────────────────────────
const ROW_HEIGHT = 64;          // Fixed section row height in pixels
const SECTION_COL_WIDTH = 220;  // Fixed left section column width in pixels
const BASE_HOUR_WIDTH = 120;    // 100% zoom: 120px per hour

// ── Default Corridor C40 Stations & Sub-Sections Fallback ──────────
const DEFAULT_C40_STATIONS = [
  { code: 'MDU', name: 'Madurai Jn', km: 0.0 },
  { code: 'TDN', name: 'Thirupparankundram', km: 6.5 },
  { code: 'TMQ', name: 'Tirumangalam', km: 13.3 },
  { code: 'VPT', name: 'Virudhunagar Jn', km: 39.0 },
  { code: 'SRT', name: 'Sattur', km: 65.9 },
  { code: 'CVP', name: 'Kovilpatti', km: 86.8 },
  { code: 'KDU', name: 'Kadambur', km: 110.2 },
  { code: 'MEJ', name: 'Vanchi Maniyachi Jn', km: 132.1 },
  { code: 'TEN', name: 'Tirunelveli Jn', km: 154.9 }
];

export default function SectionOccupancyMatrix({
  chartData,
  loading = false,
  selectedTrainId,
  selectedJobId,
  selectedWindowId,
  onSelectTrain,
  onSelectBlock,
  onSelectWindow,
  onSelectConflict,
  deptFilter = 'ALL',
  timeHorizon = '06-22', // '06-22' or '00-24'
  onRefresh
}) {
  const sectionBodyRef = useRef(null);
  const timelineScrollRef = useRef(null);

  const [zoomLevel, setZoomLevel] = useState(1.0); // 1.0 = 120px/hr
  const [directionFilter, setDirectionFilter] = useState('ALL'); // 'ALL', 'UP', 'DOWN'
  const [hoveredEntity, setHoveredEntity] = useState(null);
  const [scrubPosition, setScrubPosition] = useState(null);

  // Time boundaries based on timeHorizon
  const { startMin, endMin, totalMinutes, totalHours } = useMemo(() => {
    if (timeHorizon === '00-24') {
      return { startMin: 0, endMin: 1440, totalMinutes: 1440, totalHours: 24 };
    }
    // Default 06:00 to 22:00 IST (16 hours)
    return { startMin: 360, endMin: 1320, totalMinutes: 960, totalHours: 16 };
  }, [timeHorizon]);

  // Dynamic Scale Calculations
  const hourWidth = Math.round(BASE_HOUR_WIDTH * zoomLevel);
  const totalCanvasWidth = totalHours * hourWidth;

  // Pixel Position from Minute
  const timeToX = useCallback((min) => {
    const clampedMin = Math.max(startMin, Math.min(endMin, min));
    return ((clampedMin - startMin) / 60) * hourWidth;
  }, [startMin, endMin, hourWidth]);

  // Extract corridor stations
  const stations = useMemo(() => {
    if (chartData?.stations && chartData.stations.length > 0) {
      return chartData.stations.map((s, idx) => ({
        code: s.station_code || s.code || `STN-${idx}`,
        name: s.station_name || s.name || s.code || 'Station',
        km: s.distance_km ?? (idx * 20)
      }));
    }
    return DEFAULT_C40_STATIONS;
  }, [chartData?.stations]);

  // Build physical block sections between adjacent stations
  const sections = useMemo(() => {
    if (chartData?.sections && chartData.sections.length > 0) {
      return chartData.sections.map(sec => ({
        id: sec.id,
        section_id: sec.section_id || `SEC_${sec.id}`,
        code: `${sec.from_station_code}–${sec.to_station_code}`,
        name: sec.name || `${sec.from_station_code} - ${sec.to_station_code}`,
        from: sec.from_station_code,
        to: sec.to_station_code,
        fromName: sec.from_station_code,
        toName: sec.to_station_code,
        startKm: sec.start_km ?? 0,
        endKm: sec.end_km ?? 0,
        lengthKm: sec.length_km || (Math.round(Math.abs((sec.end_km ?? 0) - (sec.start_km ?? 0)) * 10) / 10)
      }));
    }

    if (stations.length < 2) return [];
    const list = [];
    for (let i = 0; i < stations.length - 1; i++) {
      const fromStn = stations[i];
      const toStn = stations[i + 1];
      const lengthKm = Math.max(1, Math.round(Math.abs(toStn.km - fromStn.km) * 10) / 10);
      list.push({
        id: `SEC-${fromStn.code}-${toStn.code}`,
        code: `${fromStn.code}–${toStn.code}`,
        from: fromStn.code,
        to: toStn.code,
        fromName: fromStn.name,
        toName: toStn.name,
        startKm: fromStn.km,
        endKm: toStn.km,
        lengthKm
      });
    }
    return list;
  }, [stations, chartData?.sections]);

  // Raw trains list
  const trains = useMemo(() => chartData?.trains || [], [chartData?.trains]);

  // Compute train transits across each section
  const sectionTransits = useMemo(() => {
    const map = new Map();
    sections.forEach(sec => map.set(sec.id, []));

    // Priority 1: Authoritative backend discrete section occupancies
    if (chartData?.occupancy_intervals && chartData.occupancy_intervals.length > 0) {
      const trainLookup = new Map((chartData.trains || []).map(t => [String(t.train_number), t]));

      chartData.occupancy_intervals.forEach(occ => {
        if (directionFilter !== 'ALL' && occ.direction !== directionFilter) return;

        const entryMin = occ.estimated_entry_min;
        const exitMin = occ.estimated_exit_min;
        if (exitMin < startMin || entryMin > endMin) return;

        const targetSec = sections.find(s =>
          String(s.id) === String(occ.section_id) ||
          s.section_id === occ.section_code ||
          s.code === `${occ.from_station_code}–${occ.to_station_code}` ||
          s.code === `${occ.to_station_code}–${occ.from_station_code}` ||
          s.code === `${occ.from_station_code}-${occ.to_station_code}` ||
          s.code === `${occ.to_station_code}-${occ.from_station_code}` ||
          (s.from === occ.from_station_code && s.to === occ.to_station_code) ||
          (s.from === occ.to_station_code && s.to === occ.from_station_code)
        );

        if (targetSec) {
          const trObj = trainLookup.get(String(occ.train_number));
          map.get(targetSec.id)?.push({
            train: trObj || occ,
            train_number: occ.train_number,
            train_name: occ.train_name || trObj?.train_name || `Train ${occ.train_number}`,
            direction: occ.direction || 'DOWN',
            entryMin: Math.max(startMin, entryMin),
            exitMin: Math.min(endMin, Math.max(entryMin + 6, exitMin)),
            speed: occ.speed_kmh || trObj?.speed_kmh || 75,
            delay: occ.delay_applied_min ?? occ.delay_minutes ?? trObj?.delay_minutes ?? 0,
            fromStation: occ.from_station_code,
            toStation: occ.to_station_code
          });
        }
      });
      return map;
    }

    // Priority 2: Discrete adjacent stop segments
    trains.forEach(tr => {
      if (directionFilter !== 'ALL' && tr.direction !== directionFilter) return;
      const traj = tr.trajectory || [];
      for (let i = 0; i < traj.length - 1; i++) {
        const p1 = traj[i];
        const p2 = traj[i + 1];
        const t1 = p1.min ?? p1.time_min ?? 0;
        const t2 = p2.min ?? p2.time_min ?? 0;
        const entryMin = Math.min(t1, t2);
        const exitMin = Math.max(t1, t2);
        if (exitMin < startMin || entryMin > endMin) continue;

        sections.forEach(sec => {
          const match = (p1.station_code === sec.from && p2.station_code === sec.to) ||
                        (p1.station_code === sec.to && p2.station_code === sec.from);
          if (match) {
            map.get(sec.id)?.push({
              train: tr,
              train_number: tr.train_number,
              train_name: tr.train_name,
              direction: tr.direction || (p1.distance_km < p2.distance_km ? 'DOWN' : 'UP'),
              entryMin: Math.max(startMin, entryMin),
              exitMin: Math.min(endMin, Math.max(entryMin + 6, exitMin)),
              speed: tr.speed_kmh || 75,
              delay: tr.delay_minutes || 0
            });
          }
        });
      }
    });

    return map;
  }, [sections, chartData?.occupancy_intervals, chartData?.trains, trains, startMin, endMin, directionFilter]);

  // Feasible Windows mapped to sections
  const feasibleWindows = useMemo(() => {
    const rawWindows = chartData?.feasible_windows || [];
    return rawWindows.map(w => {
      const matchSec = sections.find(s =>
        String(s.id) === String(w.section_id) ||
        s.section_id === w.section_id ||
        (w.section_code && (s.code.includes(w.section_code) || w.section_code.includes(s.from))) ||
        (w.from_station_code && s.from === w.from_station_code && s.to === w.to_station_code)
      ) || sections[0];

      return {
        ...w,
        sectionId: matchSec?.id ?? sections[0]?.id,
        sectionCode: matchSec?.code || 'CVP–KDU',
        startMin: w.start_min ?? 600,
        endMin: w.end_min ?? 690,
        durationMin: w.duration_min || w.usable_duration_min || 90
      };
    });
  }, [chartData?.feasible_windows, sections]);

  // Coordinated Maintenance Blocks mapped to sections
  const maintenanceBlocks = useMemo(() => {
    const rawBlocks = chartData?.maintenance_blocks || [];
    if (rawBlocks.length > 0) {
      return rawBlocks.map(b => {
        const matchSec = sections.find(s =>
          String(s.id) === String(b.section_id) ||
          s.section_id === b.section_id ||
          (b.section_code && (s.code.includes(b.section_code) || b.section_code.includes(s.from))) ||
          (b.from_station_code && s.from === b.from_station_code && s.to === b.to_station_code)
        ) || sections[0];

        return {
          ...b,
          sectionId: matchSec?.id ?? sections[0]?.id,
          sectionCode: matchSec?.code || 'CVP–KDU',
          startMin: b.scheduled_start_min ?? 600,
          endMin: b.scheduled_end_min ?? 690,
          durationMin: b.scheduled_duration_min ?? 90,
          blockCode: b.block_code || `BP-${b.job_id || '001'}`,
          departments: b.departments || ['Engineering', 'S&T', 'TRD'],
          status: b.is_locked ? 'LOCKED' : (b.approval_status || 'PROPOSED'),
          work_breakdown: b.work_breakdown || [
            { dept: 'ENGG', name: 'Track Renewal', work: 'Deep Ballast Screening & Track Renewal', color: '#D97706', duration: 90 },
            { dept: 'S&T', name: 'Axle Counter', work: 'Digital Axle Counter Calibration', color: '#0D9488', duration: 60 },
            { dept: 'TRD', name: 'OHE Inspection', work: 'OHE Mast Inspection & Wire Profiling', color: '#4F46E5', duration: 75 }
          ]
        };
      });
    }

    // Default authentic coordinated block BP-001 (Section CVP-KDU, 10:00–11:30)
    const targetSec = sections.find(s => s.code.includes('CVP–KDU') || s.code.includes('CVP-KDU')) || sections[5] || sections[0];
    return [
      {
        job_id: 101,
        block_code: 'BP-001',
        sectionId: targetSec?.id,
        sectionCode: targetSec?.code || 'CVP–KDU',
        startMin: 600, // 10:00
        endMin: 690,   // 11:30
        durationMin: 90,
        status: 'PROPOSED',
        strategy: 'PLAN_A',
        coordination_type: 'COMMON_BLOCK',
        work_breakdown: [
          { dept: 'ENGG', name: 'Track Renewal', work: 'Deep Ballast Screening & Track Renewal', color: '#D97706', duration: 90 },
          { dept: 'S&T', name: 'Axle Counter', work: 'Digital Axle Counter Calibration', color: '#0D9488', duration: 60 },
          { dept: 'TRD', name: 'OHE Inspection', work: 'OHE Mast Inspection & Wire Profiling', color: '#4F46E5', duration: 75 }
        ]
      }
    ];
  }, [chartData?.maintenance_blocks, sections]);

  // Conflict calculation between maintenance blocks and train occupancies
  const detectedConflicts = useMemo(() => {
    const list = [];
    maintenanceBlocks.forEach(blk => {
      const transits = sectionTransits.get(blk.sectionId) || [];
      transits.forEach(tr => {
        if (tr.entryMin < blk.endMin && tr.exitMin > blk.startMin) {
          list.push({
            block: blk,
            transit: tr,
            sectionId: blk.sectionId,
            sectionCode: blk.sectionCode,
            overlapStartMin: Math.max(tr.entryMin, blk.startMin),
            overlapEndMin: Math.min(tr.exitMin, blk.endMin),
            train_number: tr.train_number,
            train_name: tr.train_name,
            block_code: blk.block_code
          });
        }
      });
    });
    return list;
  }, [maintenanceBlocks, sectionTransits]);

  // Timeline Hour Markers
  const hourMarkers = useMemo(() => {
    const markers = [];
    const firstHour = Math.floor(startMin / 60);
    const lastHour = Math.floor(endMin / 60);
    for (let h = firstHour; h <= lastHour; h++) {
      const min = h * 60;
      markers.push({
        hour: h,
        min,
        timeStr: `${(h % 24).toString().padStart(2, '0')}:00`,
        x: (h - (startMin / 60)) * hourWidth
      });
    }
    return markers;
  }, [startMin, endMin, hourWidth]);

  // Current Time Line
  const currentTimeMin = useMemo(() => {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  }, []);
  const isCurrentTimeVisible = currentTimeMin >= startMin && currentTimeMin <= endMin;
  const currentTimeX = isCurrentTimeVisible ? timeToX(currentTimeMin) : -1;

  // Synchronized Vertical Scrolling between Timeline & Section Column
  const handleTimelineScroll = useCallback((e) => {
    if (sectionBodyRef.current) {
      sectionBodyRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  }, []);

  const handleSectionWheel = useCallback((e) => {
    if (timelineScrollRef.current) {
      timelineScrollRef.current.scrollTop += e.deltaY;
    }
  }, []);

  // Scrubbing & Inspection Needle
  const handleMouseMove = useCallback((e) => {
    if (!timelineScrollRef.current) return;
    const rect = timelineScrollRef.current.getBoundingClientRect();
    const scrollLeft = timelineScrollRef.current.scrollLeft;
    const xInCanvas = e.clientX - rect.left + scrollLeft;
    if (xInCanvas >= 0 && xInCanvas <= totalCanvasWidth) {
      const scrubMin = Math.round(startMin + (xInCanvas / totalCanvasWidth) * totalMinutes);
      setScrubPosition({ x: xInCanvas, time: mToTime(scrubMin), min: scrubMin });
    }
  }, [startMin, totalCanvasWidth, totalMinutes]);

  const handleMouseLeave = useCallback(() => {
    setScrubPosition(null);
  }, []);

  // Smooth Auto-Scroll to Selected Entity
  const scrollToEntity = useCallback((targetTimeMin, targetSectionId) => {
    if (!timelineScrollRef.current) return;
    const container = timelineScrollRef.current;
    const targetX = timeToX(targetTimeMin);
    const containerWidth = container.clientWidth;

    // Horizontal scroll to center the item
    const desiredScrollLeft = Math.max(0, targetX - containerWidth / 3);
    container.scrollTo({
      left: desiredScrollLeft,
      behavior: 'smooth'
    });

    // Vertical scroll to section row
    if (targetSectionId) {
      const secIndex = sections.findIndex(s =>
        String(s.id) === String(targetSectionId) ||
        s.section_id === targetSectionId ||
        s.code === targetSectionId ||
        s.code?.includes(targetSectionId)
      );
      if (secIndex !== -1) {
        const targetY = secIndex * ROW_HEIGHT;
        container.scrollTo({
          top: Math.max(0, targetY - ROW_HEIGHT / 2),
          behavior: 'smooth'
        });
      }
    }
  }, [timeToX, sections]);

  // Auto-scroll when selected props change
  useEffect(() => {
    if (selectedTrainId) {
      for (const [secId, transits] of sectionTransits.entries()) {
        const tr = transits.find(t => String(t.train_number) === String(selectedTrainId));
        if (tr) {
          scrollToEntity(tr.entryMin, secId);
          break;
        }
      }
    }
  }, [selectedTrainId, sectionTransits, scrollToEntity]);

  useEffect(() => {
    if (selectedJobId) {
      const blk = maintenanceBlocks.find(b => b.job_id === selectedJobId || b.id === selectedJobId);
      if (blk) {
        scrollToEntity(blk.startMin, blk.sectionId);
      }
    }
  }, [selectedJobId, maintenanceBlocks, scrollToEntity]);

  useEffect(() => {
    if (selectedWindowId) {
      const win = feasibleWindows.find(w => w.id === selectedWindowId);
      if (win) {
        scrollToEntity(win.startMin, win.sectionId);
      }
    }
  }, [selectedWindowId, feasibleWindows, scrollToEntity]);

  // Zoom Controls
  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(2.0, Math.round((prev + 0.15) * 100) / 100));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(0.75, Math.round((prev - 0.15) * 100) / 100));
  };

  const handleResetZoom = () => {
    setZoomLevel(1.0);
  };

  const handleFit = () => {
    if (!timelineScrollRef.current) {
      setZoomLevel(1.0);
      return;
    }
    const containerWidth = timelineScrollRef.current.clientWidth || 1000;
    // Fit totalHours into containerWidth, but keep at least 80px/hr for text legibility
    const fitHourWidth = containerWidth / totalHours;
    const readableHourWidth = Math.max(80, fitHourWidth);
    const newZoom = Math.round((readableHourWidth / BASE_HOUR_WIDTH) * 100) / 100;
    setZoomLevel(newZoom);
    timelineScrollRef.current.scrollTo({ left: 0, behavior: 'smooth' });
  };

  return (
    <div className="bg-[#080D1A] border border-slate-700/80 shadow-2xl flex flex-col flex-1 h-full min-h-0 font-mono text-slate-200 select-none overflow-hidden relative">
      {/* ── 0. TELEMETRY LOADING STATE OVERLAY ─────────────────── */}
      {loading && !chartData?.trains?.length && (
        <div className="absolute inset-0 bg-[#070D18]/90 z-50 flex flex-col items-center justify-center space-y-4">
          <div className="relative flex items-center justify-center">
            <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
            <Activity className="w-6 h-6 text-[#FFB703] absolute animate-pulse" />
          </div>
          <div className="space-y-1 text-center font-mono">
            <div className="text-sm font-black text-white tracking-widest uppercase">
              INDIAN RAILWAYS · SECTION OCCUPANCY TELEMETRY
            </div>
            <div className="text-xs text-blue-400 font-bold flex items-center justify-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
              <span>LOADING TRAIN DATA...</span>
            </div>
            <div className="text-[11px] text-amber-400">
              LOADING SECTION OCCUPANCY & TRACK POSSESSIONS...
            </div>
            <div className="text-[10px] text-emerald-400">
              CALCULATING AVAILABLE SWEEP-LINE WINDOWS...
            </div>
          </div>
        </div>
      )}

      {/* ── 1. OPERATIONAL WORKSTATION HEADER STRIP ────────────── */}
      <div className="bg-[#0B1528] border-b border-slate-700 px-3 py-2 flex flex-wrap items-center justify-between gap-2 shrink-0 z-30 shadow-md">
        {/* Left: Corridor Identity & Physical Sections Count */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-black text-white uppercase tracking-wider">
              SECTION OCCUPANCY & TRACK POSSESSION BOARD
            </span>
          </div>
          <span className="text-slate-600">|</span>
          <span className="text-[11px] font-bold text-[#FFB703]">
            {chartData?.corridor?.name || 'Madurai → Tirunelveli Main Line'}
          </span>
          <span className="text-[10px] text-slate-300 bg-slate-900 border border-slate-700 px-2 py-0.5 font-bold">
            {sections.length} PHYSICAL SECTIONS
          </span>
          <span className="text-[10px] text-slate-400 bg-slate-900 border border-slate-700 px-2 py-0.5 font-mono">
            SPAN: {timeHorizon === '00-24' ? '00:00–24:00 (24h)' : '06:00–22:00 (16h)'}
          </span>
        </div>

        {/* Right: Operational Controls (Direction, Zoom, Conflicts) */}
        <div className="flex items-center space-x-2 text-[11px]">
          {/* Direction Filter */}
          <div className="flex items-center bg-[#070D18] border border-slate-700 p-0.5">
            <span className="text-[9px] text-slate-500 uppercase px-1.5 font-bold">DIR:</span>
            {['ALL', 'UP', 'DOWN'].map(dir => (
              <button
                key={dir}
                onClick={() => setDirectionFilter(dir)}
                className={`px-1.5 py-0.5 text-[9px] font-bold transition-colors cursor-pointer ${
                  directionFilter === dir
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {dir === 'UP' ? '↑ UP' : dir === 'DOWN' ? '↓ DOWN' : 'ALL'}
              </button>
            ))}
          </div>

          {/* Precision Zoom Controls (Changes Real Pixel Timeline Scale) */}
          <div className="flex items-center bg-[#070D18] border border-slate-700 px-1 py-0.5 space-x-1">
            <button
              onClick={handleZoomOut}
              className="px-1.5 py-0.5 text-slate-400 hover:text-white cursor-pointer font-black text-xs hover:bg-slate-800 transition-colors"
              title="Zoom Out (−)"
            >
              −
            </button>
            <span className="text-[10px] text-slate-200 font-mono w-10 text-center font-bold">
              {Math.round(zoomLevel * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              className="px-1.5 py-0.5 text-slate-400 hover:text-white cursor-pointer font-black text-xs hover:bg-slate-800 transition-colors"
              title="Zoom In (+)"
            >
              +
            </button>
            <button
              onClick={handleFit}
              className="text-[9px] bg-slate-800 text-blue-400 hover:text-blue-300 hover:bg-slate-700 px-1.5 py-0.5 font-black cursor-pointer border border-slate-700 transition-colors"
              title="Fit Viewport Width (Maintains Readable Scale)"
            >
              FIT
            </button>
          </div>

          {/* Conflicts Status Badge */}
          {detectedConflicts.length > 0 ? (
            <div
              onClick={() => onSelectConflict && onSelectConflict(detectedConflicts[0])}
              className="bg-red-950/90 border border-red-500 px-2 py-0.5 text-red-200 text-[10px] font-bold flex items-center gap-1.5 animate-pulse cursor-pointer shadow-md"
              title={`${detectedConflicts.length} Conflicts Detected. Click to inspect.`}
            >
              <AlertTriangle className="w-3 h-3 text-red-400" />
              <span>{detectedConflicts.length} CONFLICTS DETECTED</span>
            </div>
          ) : (
            <div className="bg-emerald-950/60 border border-emerald-600/70 px-2 py-0.5 text-emerald-300 text-[10px] font-bold flex items-center gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>0 CONFLICTS · CLEAR</span>
            </div>
          )}
        </div>
      </div>

      {/* ── 2. SCROLLABLE OCCUPANCY BOARD (FIXED SECTION COL + SCROLLABLE TIMELINE) ── */}
      <div className="occupancy-board flex flex-row flex-1 min-h-0 overflow-hidden relative">
        {/* A. FIXED LEFT SECTION COLUMN (Stationary during horizontal scrolling) */}
        <div
          className="section-column w-[220px] min-w-[220px] max-w-[220px] bg-[#0A1222] border-r border-slate-700 flex flex-col z-20 shrink-0 shadow-xl"
          onWheel={handleSectionWheel}
        >
          {/* Top Fixed Section Header Cell */}
          <div className="h-10 border-b border-slate-700 px-2.5 flex items-center justify-between text-[10px] font-bold text-slate-300 uppercase bg-[#09101E] shrink-0 tracking-wider">
            <span>SECTION CODE</span>
            <span className="text-[9px] text-slate-400 font-mono">SPAN (KM)</span>
          </div>

          {/* Section Rows List (Synchronized vertical scroll with timeline) */}
          <div
            ref={sectionBodyRef}
            className="section-body flex-1 overflow-hidden divide-y divide-slate-800/80"
          >
            {sections.map((sec, idx) => {
              const transits = sectionTransits.get(sec.id) || [];
              const isOccupiedNow = transits.some(t => currentTimeMin >= t.entryMin && currentTimeMin <= t.exitMin);
              const hasBlock = maintenanceBlocks.some(b => b.sectionId === sec.id);

              return (
                <div
                  key={sec.id}
                  style={{ height: `${ROW_HEIGHT}px` }}
                  className={`px-2.5 py-1 flex flex-col justify-center transition-colors ${
                    idx % 2 === 0 ? 'bg-[#091120]' : 'bg-[#0A1426]'
                  } hover:bg-[#112038]`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-black text-xs text-white tracking-tight flex items-center gap-1.5 font-mono">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${
                        isOccupiedNow ? 'bg-amber-400 animate-ping' : hasBlock ? 'bg-blue-400' : 'bg-emerald-500'
                      }`} />
                      <span className="truncate">{sec.code}</span>
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono font-bold shrink-0">
                      {sec.lengthKm} km
                    </span>
                  </div>

                  <div className="text-[9px] text-slate-400 truncate mt-0.5" title={`${sec.fromName || sec.from} → ${sec.toName || sec.to}`}>
                    {sec.from} → {sec.to}
                  </div>

                  <div className="flex items-center justify-between text-[9px] mt-1">
                    <span className="text-[8px] text-slate-500 font-mono font-bold">
                      {transits.length} TRAIN{transits.length !== 1 ? 'S' : ''}
                    </span>
                    <span className={`px-1.5 py-0.2 text-[8px] font-black rounded-xs ${
                      isOccupiedNow
                        ? 'bg-amber-950/90 text-amber-300 border border-amber-600'
                        : hasBlock
                          ? 'bg-blue-950/90 text-blue-300 border border-blue-600'
                          : 'bg-emerald-950/50 text-emerald-400 border border-emerald-700/60'
                    }`}>
                      {isOccupiedNow ? 'OCCUPIED' : hasBlock ? 'BLOCK PLAN' : 'FREE'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* B. SCROLLABLE TIMELINE CONTAINER (Horizontal & Vertical Scroll) */}
        <div
          ref={timelineScrollRef}
          onScroll={handleTimelineScroll}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="timeline-scroll flex-1 min-h-0 overflow-x-auto overflow-y-auto bg-[#070D18] relative control-room-scrollbar"
        >
          {/* Real internal width canvas: Calculated minimum width based on time range and zoom */}
          <div
            className="timeline-canvas relative flex flex-col"
            style={{ width: `${totalCanvasWidth}px`, minWidth: `${totalCanvasWidth}px` }}
          >
            {/* 1. TIME HEADER (Sticky top-0 so it stays visible during vertical scroll) */}
            <div className="time-header sticky top-0 z-30 h-10 border-b border-slate-700 bg-[#0A1222] flex shrink-0 shadow-md">
              {hourMarkers.map(hm => (
                <div
                  key={hm.hour}
                  style={{ width: `${hourWidth}px`, minWidth: `${hourWidth}px` }}
                  className="border-r border-slate-700/80 h-full flex flex-col justify-between px-1.5 py-1 shrink-0 relative bg-[#0A1222]"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-black text-slate-200 tracking-wider font-mono">
                      {hm.timeStr}
                    </span>
                    <span className="text-[8px] text-slate-500 font-mono">
                      +{hm.hour - Math.floor(startMin / 60)}h
                    </span>
                  </div>
                  {/* Visual Sub-Ticks for 15m, 30m, 45m Intervals */}
                  <div className="flex justify-between items-end h-1.5 px-0.5">
                    <span className="w-[1px] h-1 bg-slate-700/60" />
                    <span className="w-[1px] h-2 bg-slate-500" />
                    <span className="w-[1px] h-1 bg-slate-700/60" />
                  </div>
                </div>
              ))}
            </div>

            {/* 2. TIMELINE ROWS CONTAINER */}
            <div className="timeline-rows flex-1 relative divide-y divide-slate-800/80">
              {/* Vertical Time Grid Lines */}
              {hourMarkers.map(hm => (
                <React.Fragment key={`grid-${hm.hour}`}>
                  {/* Major hour line */}
                  <div
                    className="absolute top-0 bottom-0 w-[1px] bg-slate-800/90 pointer-events-none z-0"
                    style={{ left: `${(hm.hour - (startMin / 60)) * hourWidth}px` }}
                  />
                  {/* Half-hour dashed line */}
                  <div
                    className="absolute top-0 bottom-0 w-[1px] border-r border-dashed border-slate-800/40 pointer-events-none z-0"
                    style={{ left: `${(hm.hour - (startMin / 60) + 0.5) * hourWidth}px` }}
                  />
                </React.Fragment>
              ))}

              {/* Vertical Current Time Line */}
              {isCurrentTimeVisible && (
                <div
                  className="absolute top-0 bottom-0 w-[2px] bg-red-500 z-35 pointer-events-none shadow-[0_0_10px_rgba(239,68,68,0.9)]"
                  style={{ left: `${currentTimeX}px` }}
                >
                  <div className="bg-red-600 text-white font-black text-[9px] px-1.5 py-0.5 rounded-xs -translate-x-1/2 absolute top-1 whitespace-nowrap shadow-lg flex items-center gap-1 border border-red-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                    <span>LIVE IST: {mToTime(currentTimeMin)}</span>
                  </div>
                </div>
              )}

              {/* Scrub Needle */}
              {scrubPosition && (
                <div
                  className="absolute top-0 bottom-0 w-[1px] bg-cyan-400 z-35 pointer-events-none shadow-[0_0_6px_rgba(34,211,238,0.8)]"
                  style={{ left: `${scrubPosition.x}px` }}
                >
                  <div className="bg-cyan-600 text-slate-950 font-black text-[9px] px-1.5 py-0.5 rounded-xs -translate-x-1/2 absolute top-2 whitespace-nowrap shadow-lg">
                    {scrubPosition.time} IST
                  </div>
                </div>
              )}

              {/* Section Timeline Rows (Each matching ROW_HEIGHT exactly) */}
              {sections.map((sec, idx) => {
                const transits = sectionTransits.get(sec.id) || [];
                const windowsOnSection = feasibleWindows.filter(w => w.sectionId === sec.id);
                const blocksOnSection = maintenanceBlocks.filter(b => b.sectionId === sec.id);

                return (
                  <div
                    key={sec.id}
                    style={{ height: `${ROW_HEIGHT}px` }}
                    className={`relative w-full transition-colors ${
                      idx % 2 === 0 ? 'bg-[#070D18]/90' : 'bg-[#091122]/90'
                    } hover:bg-[#0C162A]/90`}
                  >
                    {/* Empty State watermark if no transits occupy this section */}
                    {transits.length === 0 && (
                      <div className="absolute inset-0 flex items-center justify-center pointer-events-none text-[10px] text-slate-700/80 font-bold tracking-widest uppercase font-mono">
                        NO TRAIN OCCUPANCY (CLEAR)
                      </div>
                    )}

                    {/* 1. FEASIBLE MAINTENANCE WINDOWS (Soft Emerald Bands) */}
                    {windowsOnSection.map(win => {
                      const leftPx = timeToX(win.startMin);
                      const widthPx = Math.max(32, timeToX(win.endMin) - timeToX(win.startMin));
                      const isSelected = selectedWindowId === win.id;

                      return (
                        <div
                          key={`win-${win.id}`}
                          id={`matrix-win-${win.id}`}
                          data-window-id={win.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectWindow && onSelectWindow({
                              id: win.id,
                              section_code: win.sectionCode || sec.code,
                              sectionCode: win.sectionCode || sec.code,
                              start_min: win.startMin,
                              end_min: win.endMin,
                              duration_min: win.durationMin,
                              usable_duration_min: win.usable_duration_min || (win.durationMin - 10)
                            });
                            scrollToEntity(win.startMin, sec.id);
                          }}
                          style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                          className={`absolute top-1 bottom-1 z-10 rounded-xs border-2 border-dashed transition-all cursor-pointer flex flex-col justify-center px-1.5 shadow-inner overflow-hidden ${
                            isSelected
                              ? 'bg-emerald-500/30 border-emerald-400 ring-2 ring-emerald-400/60 shadow-emerald-500/20'
                              : 'bg-emerald-950/25 border-emerald-500/70 hover:bg-emerald-900/35 hover:border-emerald-400'
                          }`}
                          title={`Feasible Maintenance Window\nSection: ${sec.code}\nAvailable: ${mToTime(win.startMin)} → ${mToTime(win.endMin)} (${win.durationMin} min)\nUsable Duration: ${win.usable_duration_min || (win.durationMin - 10)} min\nClick to inspect slot.`}
                        >
                          {widthPx < 60 ? (
                            <span className="text-[9px] font-black text-emerald-300 uppercase tracking-tight truncate">
                              FEASIBLE
                            </span>
                          ) : widthPx < 120 ? (
                            <span className="text-[9px] font-black text-emerald-300 uppercase tracking-tight truncate">
                              FEASIBLE · {win.durationMin}m
                            </span>
                          ) : (
                            <>
                              <div className="flex items-center space-x-1">
                                <Clock className="w-2.5 h-2.5 text-emerald-400 shrink-0" />
                                <span className="text-[9px] font-black text-emerald-300 uppercase tracking-tight truncate">
                                  FEASIBLE · {win.durationMin} MIN
                                </span>
                              </div>
                              <div className="text-[8px] text-emerald-400 font-mono truncate">
                                {mToTime(win.startMin)}–{mToTime(win.endMin)}
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}

                    {/* 2. COORDINATED MAINTENANCE BLOCKS (High-Contrast Multi-Department Slots) */}
                    {blocksOnSection.map(blk => {
                      const leftPx = timeToX(blk.startMin);
                      const widthPx = Math.max(45, timeToX(blk.endMin) - timeToX(blk.startMin));
                      const isSelected = selectedJobId === blk.job_id || selectedJobId === blk.id;
                      const hasConflict = detectedConflicts.some(c => c.block.block_code === blk.block_code);

                      return (
                        <div
                          key={`blk-${blk.block_code}`}
                          id={`matrix-block-${blk.block_code}`}
                          data-block-code={blk.block_code}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectBlock && onSelectBlock(blk.job_id || blk.id || 101);
                            scrollToEntity(blk.startMin, sec.id);
                          }}
                          style={{ left: `${leftPx}px`, width: `${widthPx}px` }}
                          className={`absolute top-1 bottom-1 z-20 rounded-xs border-2 transition-all cursor-pointer shadow-xl flex flex-col justify-between p-1 overflow-hidden ${
                            hasConflict
                              ? 'bg-red-950/95 border-red-500 ring-2 ring-red-500 animate-pulse shadow-red-500/30'
                              : isSelected
                                ? 'bg-blue-950 border-amber-400 ring-2 ring-[#FFB703] shadow-[#FFB703]/30'
                                : 'bg-[#0E1A33] border-blue-400 hover:border-blue-300'
                          }`}
                          title={`Coordinated Block ${blk.block_code}\nSection: ${sec.code}\nScheduled: ${mToTime(blk.startMin)} → ${mToTime(blk.endMin)} (${blk.durationMin} min)\nStatus: ${blk.status}\nDepartments: ${(blk.departments || []).join(', ')}\nClick to inspect block plan.`}
                        >
                          {widthPx < 70 ? (
                            <div className="flex flex-col justify-center h-full">
                              <span className="text-[9px] font-black text-white font-mono leading-none">
                                {blk.block_code}
                              </span>
                              <span className="text-[8px] text-amber-300 font-bold leading-none mt-1">
                                {blk.durationMin}m
                              </span>
                            </div>
                          ) : widthPx < 140 ? (
                            <>
                              <div className="flex items-center justify-between">
                                <span className="text-[9px] font-black text-white font-mono">
                                  {blk.block_code}
                                </span>
                                <span className="text-[8px] text-amber-300 bg-amber-950/80 px-1 border border-amber-600/70 font-bold">
                                  {blk.durationMin}m
                                </span>
                              </div>
                              <div className="text-[8px] text-slate-300 font-mono truncate">
                                {mToTime(blk.startMin)}–{mToTime(blk.endMin)}
                              </div>
                            </>
                          ) : (
                            <>
                              {/* Block Header */}
                              <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-1">
                                  <span className="w-2 h-2 rounded-xs bg-[#FFB703]" />
                                  <span className="text-[10px] font-black text-white font-mono">
                                    {blk.block_code}
                                  </span>
                                  <span className="text-[8px] text-amber-300 bg-amber-950/80 px-1 border border-amber-600/70 font-bold">
                                    {blk.durationMin}m
                                  </span>
                                </div>
                                <span className={`text-[8px] font-black px-1 uppercase ${
                                  blk.status === 'APPROVED' ? 'bg-emerald-600 text-white' : 'bg-blue-600 text-white'
                                }`}>
                                  {blk.status}
                                </span>
                              </div>

                              {/* Multi-Department Sub-Lanes */}
                              <div className="grid grid-cols-3 gap-0.5 my-0.5">
                                {(blk.work_breakdown || [
                                  { dept: 'ENGG', color: '#D97706', duration: 90 },
                                  { dept: 'S&T', color: '#0D9488', duration: 60 },
                                  { dept: 'TRD', color: '#4F46E5', duration: 75 }
                                ]).map((item, i) => (
                                  <div
                                    key={i}
                                    style={{ borderLeftColor: item.color }}
                                    className="bg-black/60 border-l-2 px-1 py-0.2 text-[8px] font-bold text-slate-200 truncate flex items-center justify-between"
                                  >
                                    <span>{item.dept}</span>
                                    <span className="text-[7px] text-slate-400">{item.duration}m</span>
                                  </div>
                                ))}
                              </div>

                              {/* Timing footer */}
                              <div className="text-[8px] font-mono text-slate-300 flex justify-between">
                                <span>{mToTime(blk.startMin)}</span>
                                <span className="text-[#FFB703] font-bold">COORDINATED</span>
                                <span>{mToTime(blk.endMin)}</span>
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })}

                    {/* 3. TRAIN OCCUPANCY SLOTS (Exact Time Positioned) */}
                    {transits.map((tr, tIdx) => {
                      const leftPx = timeToX(tr.entryMin);
                      const widthPx = Math.max(28, timeToX(tr.exitMin) - timeToX(tr.entryMin));
                      const isSelected = String(selectedTrainId) === String(tr.train_number);
                      const isUp = tr.direction === 'UP';

                      // Check conflict with any maintenance block on this section
                      const isConflicting = blocksOnSection.some(b => tr.entryMin < b.endMin && tr.exitMin > b.startMin);

                      return (
                        <div
                          key={`tr-${tr.train_number}-${tIdx}`}
                          id={`matrix-train-${tr.train_number}`}
                          data-train-number={tr.train_number}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectTrain && onSelectTrain(tr.train || {
                              train_number: tr.train_number,
                              train_name: tr.train_name,
                              train_type: tr.train?.train_type || 'EXPRESS',
                              direction: tr.direction,
                              speed_kmh: tr.speed,
                              delay_minutes: tr.delay,
                              current_section: sec.code,
                              status: 'RUNNING'
                            });
                            scrollToEntity(tr.entryMin, sec.id);
                          }}
                          style={{
                            left: `${leftPx}px`,
                            width: `${widthPx}px`,
                            top: '14px',
                            height: '36px'
                          }}
                          className={`absolute z-25 rounded-xs border transition-all cursor-pointer flex flex-col justify-center px-1 shadow-sm overflow-hidden ${
                            isConflicting
                              ? 'bg-red-900/95 border-red-400 text-white ring-2 ring-red-400 animate-pulse z-35'
                              : isSelected
                                ? 'bg-cyan-500 text-slate-950 font-black border-white ring-2 ring-cyan-400 z-40 shadow-cyan-500/50'
                                : isUp
                                  ? 'bg-[#1E2E4A] hover:bg-[#283D63] border-blue-400/90 text-blue-100 border-dashed hover:z-30'
                                  : 'bg-[#162947] hover:bg-[#223B66] border-slate-500/90 text-slate-200 hover:z-30'
                          }`}
                          title={`Train ${tr.train_number} (${tr.train_name})\nDirection: ${isUp ? '↑ UP' : '↓ DOWN'}\nOccupancy: ${mToTime(tr.entryMin)} → ${mToTime(tr.exitMin)} (${Math.max(1, tr.exitMin - tr.entryMin)} min)\nSpeed: ${tr.speed} km/h | Delay: ${tr.delay > 0 ? `+${tr.delay}m` : 'On Time'}\nSection: ${sec.code} (${sec.lengthKm} km)\nClick to inspect train in right dock.`}
                        >
                          {/* Compact Display Rules based on available pixel width */}
                          {widthPx < 45 ? (
                            <div className="flex flex-col items-center justify-center h-full px-0.5 leading-none">
                              <span className="text-[9px] font-black truncate">{tr.train_number}</span>
                              <span className={`text-[8px] font-bold ${isUp ? 'text-amber-300' : 'text-cyan-300'}`}>
                                {isUp ? '↑' : '↓'}
                              </span>
                            </div>
                          ) : widthPx < 80 ? (
                            <div className="flex flex-col justify-between h-full py-0.5 px-1 leading-tight">
                              <div className="flex items-center justify-between text-[9px] font-black">
                                <span className="truncate">{tr.train_number}</span>
                                <span className={`text-[8px] font-bold ${isUp ? 'text-amber-300' : 'text-cyan-300'}`}>
                                  {isUp ? '↑' : '↓'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[8px] font-mono opacity-90">
                                <span>{tr.speed}k</span>
                                <span className={tr.delay > 0 ? 'text-red-300 font-bold' : 'text-emerald-300'}>
                                  {tr.delay > 0 ? `+${tr.delay}m` : 'RT'}
                                </span>
                              </div>
                            </div>
                          ) : (
                            <div className="flex flex-col justify-between h-full py-0.5 px-1.5 leading-tight">
                              <div className="flex items-center justify-between text-[9px] font-black">
                                <span className="truncate">{tr.train_number}</span>
                                <span className={`text-[8px] font-bold px-1 rounded-xs ${
                                  isUp ? 'bg-amber-900/60 text-amber-200' : 'bg-cyan-900/60 text-cyan-200'
                                }`}>
                                  {isUp ? '↑ UP' : '↓ DN'}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[8px] font-mono">
                                <span className="text-slate-300">{tr.speed} km/h</span>
                                <span className={tr.delay > 0 ? 'text-red-300 font-bold' : 'text-emerald-300 font-bold'}>
                                  {tr.delay > 0 ? `+${tr.delay}m` : 'RT'}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. BOTTOM LEGEND & REAL-TIME SUMMARY STRIP ─────────── */}
      <div className="bg-[#09101E] border-t border-slate-700/80 px-3 py-1.5 flex flex-wrap items-center justify-between text-[10px] text-slate-400 gap-2 shrink-0 z-20">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-slate-300 uppercase">LEGEND:</span>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-2 bg-[#162947] border border-slate-500 rounded-xs" />
            <span>↓ DOWN Train (Solid)</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-2 bg-[#1E2E4A] border border-blue-400 border-dashed rounded-xs" />
            <span>↑ UP Train (Dashed)</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-2 bg-emerald-950/40 border border-emerald-500 border-dashed rounded-xs" />
            <span className="text-emerald-300 font-bold">Feasible Maintenance Window</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-2 bg-blue-900 border border-amber-400 rounded-xs" />
            <span className="text-amber-300 font-bold">Coordinated Block (ENGG + S&T + TRD)</span>
          </div>
          <div className="flex items-center space-x-1">
            <span className="w-3 h-2 bg-red-600 rounded-xs" />
            <span className="text-red-300 font-bold">Train / Block Conflict</span>
          </div>
        </div>

        <div className="flex items-center space-x-2 font-mono text-[10px]">
          <span className="text-slate-500">TRAFFIC:</span>
          <span className="text-white font-bold">{trains.length} Candidate Trains</span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-500">CORRIDOR OCCUPANCY:</span>
          <span className="text-emerald-400 font-bold">
            {detectedConflicts.length > 0 ? `${detectedConflicts.length} CONFLICTS REQUIRING ATTENTION` : 'CLEAR FOR SCHEDULED WINDOWS'}
          </span>
        </div>
      </div>
    </div>
  );
}
