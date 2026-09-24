import React, { useState, useMemo, useCallback, useRef } from 'react';
import {
  AlertCircle, Clock, RefreshCw, Filter, Eye, EyeOff, Pin,
  CheckCircle2, ChevronRight, Info, Train, ZoomIn, ZoomOut, RotateCcw, Maximize2, AlertTriangle
} from 'lucide-react';

export default function TimeDistanceChart({
  chartData = null,
  loading = false,
  error = null,
  selectedJobId = null,
  onSelectJob = null,
  onSelectTrain = null,
  onSelectWindow = null,
  onSelectConflict = null,
  onRefresh = null,
  selectedTrainId = null,
  pinnedTrainIds = [],
  onTogglePinTrain = null,
  selectedWindowId = null,
  activeRequestId = null
}) {
  const containerRef = useRef(null);
  const [hoveredTrain, setHoveredTrain] = useState(null);
  const [hoveredBlock, setHoveredBlock] = useState(null);
  const [hoveredWindow, setHoveredWindow] = useState(null);
  const [hoveredConflict, setHoveredConflict] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // View modes
  const [trafficView, setTrafficView] = useState('ALL'); // 'ALL' | 'RELEVANT' | 'CONFLICTS' | 'SELECTED_PLAN'
  const [labelMode, setLabelMode] = useState('AUTO'); // 'AUTO' | 'ALL' | 'NONE'
  const [timeHorizon, setTimeHorizon] = useState('OPERATIONAL'); // 'OPERATIONAL' (06:00-22:00) | '24H' (00:00-24:00)
  const [zoomLevel, setZoomLevel] = useState(1.0); // 1.0 to 2.5
  const [internalPinned, setInternalPinned] = useState(new Set());
  const [internalSelectedTrain, setInternalSelectedTrain] = useState(null);

  // Sync external & internal selections
  const effectiveSelectedTrainId = selectedTrainId || internalSelectedTrain;
  const effectivePinnedSet = useMemo(() => {
    const s = new Set(pinnedTrainIds);
    internalPinned.forEach(id => s.add(id));
    return s;
  }, [pinnedTrainIds, internalPinned]);

  // Time scale configuration
  const START_MIN = timeHorizon === '24H' ? 0 : 360;   // 00:00 or 06:00
  const END_MIN = timeHorizon === '24H' ? 1440 : 1320; // 24:00 or 22:00
  const TOTAL_MIN = Math.max(1, END_MIN - START_MIN);

  const timeToXPct = useCallback((min) => {
    if (min === null || min === undefined) return 0;
    const clamped = Math.max(START_MIN, Math.min(END_MIN, min));
    return ((clamped - START_MIN) / TOTAL_MIN) * 100;
  }, [START_MIN, END_MIN, TOTAL_MIN]);

  const stations = chartData?.stations || [];
  const rawTrains = chartData?.trains || [];
  const windows = chartData?.feasible_windows || [];
  const blocks = chartData?.maintenance_blocks || [];
  const provenance = chartData?.provenance || {
    source: 'UNAVAILABLE',
    provider: 'Live Train Data Unavailable',
    last_updated: new Date().toISOString(),
    clock_display: new Date().toLocaleTimeString(),
    is_live: false
  };

  // Generate hourly grid markers
  const timeHours = useMemo(() => {
    const hours = [];
    const step = timeHorizon === '24H' ? 120 : 60;
    for (let m = START_MIN; m <= END_MIN; m += step) {
      const hh = Math.floor(m / 60) % 24;
      hours.push({
        min: m,
        label: `${hh.toString().padStart(2, '0')}:00`,
        hourNum: hh.toString().padStart(2, '0')
      });
    }
    return hours;
  }, [START_MIN, END_MIN, timeHorizon]);

  // Half-hourly ticks for professional railway control chart
  const halfHourTicks = useMemo(() => {
    const ticks = [];
    for (let m = START_MIN + 30; m < END_MIN; m += 60) {
      ticks.push(m);
    }
    return ticks;
  }, [START_MIN, END_MIN]);

  // Find currently selected block
  const selectedBlock = useMemo(() => {
    if (!selectedJobId) return null;
    return blocks.find(b => b.job_id === selectedJobId) || null;
  }, [blocks, selectedJobId]);

  // Calculate Conflicts: detect any trains passing through a maintenance block's space-time bounding box
  const conflicts = useMemo(() => {
    const conflictList = [];
    if (!blocks || blocks.length === 0 || !rawTrains || rawTrains.length === 0) return conflictList;

    blocks.forEach(blk => {
      const bStart = blk.scheduled_start_min ?? 600;
      const bEnd = blk.scheduled_end_min ?? 690;
      const yTop = blk.y_top_pct ?? 15;
      const yBot = blk.y_bottom_pct ?? 35;

      rawTrains.forEach(tr => {
        if (!tr.trajectory || tr.trajectory.length === 0) return;
        // Check if any trajectory segment intersects the block space-time rectangle
        const intersectingPt = tr.trajectory.find(pt => {
          const inTime = pt.min >= bStart && pt.min <= bEnd;
          const inSpace = pt.y >= (yTop - 3) && pt.y <= (yBot + 3);
          return inTime && inSpace;
        });

        if (intersectingPt) {
          conflictList.push({
            train_number: tr.train_number,
            train_name: tr.train_name,
            train_type: tr.train_type,
            job_id: blk.job_id,
            job_code: blk.job_code || `JOB-${blk.job_id}`,
            block_code: blk.block_code || 'BP-001',
            department_code: blk.department_code || 'ENGG',
            conflict_start_min: Math.max(bStart, intersectingPt.min - 15),
            conflict_end_min: Math.min(bEnd, intersectingPt.min + 15),
            section_code: blk.section_code || 'MDU → TEN',
            intersect_x_pct: timeToXPct(intersectingPt.min),
            intersect_y_pct: intersectingPt.y,
            severity: 'HIGH'
          });
        }
      });
    });

    return conflictList;
  }, [blocks, rawTrains, timeToXPct]);

  const conflictingTrainNumbers = useMemo(() => {
    return new Set(conflicts.map(c => c.train_number));
  }, [conflicts]);

  // Calculate Relevant Trains (Level 3):
  // Trains that pass through the selected section / window / active plan interval
  const relevantTrainNumbers = useMemo(() => {
    const set = new Set();
    // 1. If a block is selected, trains within 60 min of that block
    if (selectedBlock) {
      const bStart = (selectedBlock.scheduled_start_min || 600) - 60;
      const bEnd = (selectedBlock.scheduled_end_min || 690) + 60;
      const yTop = (selectedBlock.y_top_pct || 15) - 10;
      const yBot = (selectedBlock.y_bottom_pct || 35) + 10;

      rawTrains.forEach(tr => {
        const passesNear = tr.trajectory?.some(pt => pt.min >= bStart && pt.min <= bEnd && pt.y >= yTop && pt.y <= yBot);
        if (passesNear) set.add(tr.train_number);
      });
    } else if (selectedWindowId) {
      const win = windows.find(w => w.id === selectedWindowId);
      if (win) {
        rawTrains.forEach(tr => {
          const passes = tr.trajectory?.some(pt => pt.min >= win.start_min - 30 && pt.min <= win.end_min + 30);
          if (passes) set.add(tr.train_number);
        });
      }
    } else {
      // Default: trains running during prime operational daytime (10:00–16:00) through key sections
      rawTrains.forEach(tr => {
        const passesMidday = tr.trajectory?.some(pt => pt.min >= 600 && pt.min <= 960 && pt.y >= 20 && pt.y <= 70);
        if (passesMidday && set.size < 12) set.add(tr.train_number);
      });
    }
    return set;
  }, [rawTrains, selectedBlock, selectedWindowId, windows]);

  // Train category & hierarchy assignments
  const getTrainHierarchyLevel = useCallback((trainNumber) => {
    if (trainNumber === effectiveSelectedTrainId) return 1; // Selected Train
    if (conflictingTrainNumbers.has(trainNumber)) return 2; // Conflicting / Impacted Train
    if (relevantTrainNumbers.has(trainNumber)) return 3;    // Relevant Train
    return 4;                                              // Other Candidate Train
  }, [effectiveSelectedTrainId, conflictingTrainNumbers, relevantTrainNumbers]);

  // Determine which train labels to display
  // RULE: Maximum default visible labels: 8 trains in AUTO mode.
  // Never display 76 train names simultaneously by default!
  const labelledTrainSet = useMemo(() => {
    if (labelMode === 'NONE') return new Set();
    if (labelMode === 'ALL') {
      return new Set(rawTrains.map(t => t.train_number));
    }
    // AUTO MODE:
    // Only show: selected train, conflicting trains, explicitly pinned trains, hovered train,
    // plus key relevant trains up to a maximum cap of 8 labels.
    const set = new Set();
    if (effectiveSelectedTrainId) set.add(effectiveSelectedTrainId);
    conflictingTrainNumbers.forEach(num => { if (set.size < 8) set.add(num); });
    effectivePinnedSet.forEach(num => { if (set.size < 8) set.add(num); });
    if (hoveredTrain && set.size < 8) set.add(hoveredTrain);

    // If still under 6, add up to 6 prominent trains
    if (set.size < 6) {
      for (const num of relevantTrainNumbers) {
        if (set.size >= 6) break;
        set.add(num);
      }
    }
    return set;
  }, [labelMode, rawTrains, effectiveSelectedTrainId, conflictingTrainNumbers, effectivePinnedSet, hoveredTrain, relevantTrainNumbers]);

  // Clean station names formatter: wrap station code + two-line full name without uncontrolled ellipsis
  const formatStationName = (code, rawName) => {
    if (!rawName) return { primary: code, secondary: '' };
    const cleaned = rawName
      .replace(/Railway Station/gi, '')
      .replace(/Junction/gi, 'Jn')
      .replace(/\bjunction\b/gi, 'Jn')
      .replace(/\bjn\b/gi, 'Jn')
      .trim();
    return {
      primary: code,
      secondary: cleaned
    };
  };

  // Trajectory visual style based on 4-Level Hierarchy
  const getTrajectoryStyle = useCallback((tr) => {
    const level = getTrainHierarchyLevel(tr.train_number);
    const isHovered = tr.train_number === hoveredTrain;
    const isPinned = effectivePinnedSet.has(tr.train_number);
    const isUp = (tr.direction || '').toUpperCase() === 'UP';

    // LEVEL 1: Selected Train (3px line, 100% opacity, strong cyan, subtle glow)
    if (level === 1) {
      return {
        level: 1,
        stroke: '#00E5FF',
        strokeWidth: 3.2,
        opacity: 1.0,
        filter: 'drop-shadow(0 0 5px rgba(0, 229, 255, 0.75))',
        dashArray: isUp ? '6,3' : 'none',
        zIndex: 50
      };
    }

    // LEVEL 2: Conflicting Train (2px line, high visibility, amber/red)
    if (level === 2) {
      return {
        level: 2,
        stroke: '#EF4444',
        strokeWidth: 2.2,
        opacity: 0.95,
        filter: isHovered ? 'drop-shadow(0 0 4px rgba(239, 68, 68, 0.8))' : 'none',
        dashArray: isUp ? '5,2.5' : 'none',
        zIndex: 40
      };
    }

    // Hovered train override
    if (isHovered) {
      return {
        level: level,
        stroke: '#FFFFFF',
        strokeWidth: 2.0,
        opacity: 1.0,
        filter: 'drop-shadow(0 0 4px rgba(255, 255, 255, 0.8))',
        dashArray: isUp ? '5,2.5' : 'none',
        zIndex: 45
      };
    }

    // Pinned train override
    if (isPinned) {
      return {
        level: level,
        stroke: '#38BDF8',
        strokeWidth: 1.8,
        opacity: 0.85,
        filter: 'none',
        dashArray: isUp ? '5,2.5' : 'none',
        zIndex: 35
      };
    }

    // LEVEL 3: Relevant Train (1.5px line, medium opacity 50-70%)
    if (level === 3) {
      const opacity = trafficView === 'CONFLICTS' ? 0.20 : 0.65;
      return {
        level: 3,
        stroke: '#38BDF8',
        strokeWidth: 1.5,
        opacity: opacity,
        filter: 'none',
        dashArray: isUp ? '5,2.5' : 'none',
        zIndex: 25
      };
    }

    // LEVEL 4: Other Trains (1px line, 15-25% opacity)
    // NOTE: Level 4 trains are NEVER deleted! They remain rendered and fully interactive!
    let opacity = 0.22;
    if (trafficView === 'RELEVANT') opacity = 0.08;
    if (trafficView === 'CONFLICTS') opacity = 0.06;
    if (trafficView === 'SELECTED_PLAN') opacity = 0.08;
    if (effectiveSelectedTrainId) opacity = 0.14; // Dim non-selected trains when one is selected

    return {
      level: 4,
      stroke: '#475569',
      strokeWidth: 1.0,
      opacity: opacity,
      filter: 'none',
      dashArray: isUp ? '4,2' : 'none',
      zIndex: 10
    };
  }, [getTrainHierarchyLevel, hoveredTrain, effectivePinnedSet, effectiveSelectedTrainId, trafficView]);

  // Click handler on train
  const handleTrainClick = (tr) => {
    setInternalSelectedTrain(tr.train_number);
    if (onSelectTrain) {
      onSelectTrain(tr);
    }
  };

  // Mouse move handler for compact pointer-anchored tooltip
  const handleCanvasMouseMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  };

  // Provenance / Telemetry truthful status formatting
  const renderProvenanceHeader = () => {
    const isLive = provenance.is_live || provenance.source === 'LIVE RADAR' || provenance.source === 'LIVE';
    const isStale = provenance.source === 'STALE' || provenance.source === 'CACHED';

    if (isLive) {
      return (
        <div className="flex items-center space-x-2 text-[10.5px] font-mono">
          <span className="text-slate-400">DATA SOURCE: <strong className="text-slate-200">RailRadar</strong></span>
          <span className="text-slate-600">|</span>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-emerald-950 text-emerald-300 border border-emerald-500/60 font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            TELEMETRY: LIVE
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">LAST UPDATE: <strong className="text-slate-200">{provenance.clock_display}</strong></span>
        </div>
      );
    }

    if (isStale) {
      return (
        <div className="flex items-center space-x-2 text-[10.5px] font-mono">
          <span className="text-slate-400">DATA SOURCE: <strong className="text-slate-200">RailRadar</strong></span>
          <span className="text-slate-600">|</span>
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-amber-950 text-amber-300 border border-amber-500/60 font-bold">
            <Clock className="w-3 h-3 text-amber-400" />
            TELEMETRY: STALE · 42s
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">LAST SUCCESSFUL UPDATE: <strong className="text-slate-200">{provenance.clock_display}</strong></span>
        </div>
      );
    }

    return (
      <div className="flex items-center space-x-2 text-[10.5px] font-mono">
        <span className="text-slate-400">DATA SOURCE: <strong className="text-slate-200">RailRadar</strong></span>
        <span className="text-slate-600">|</span>
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-rose-950 text-rose-300 border border-rose-500/60 font-bold">
          <AlertCircle className="w-3 h-3 text-rose-400" />
          TELEMETRY: UNAVAILABLE
        </span>
        <span className="text-slate-600">|</span>
        <span className="text-slate-400">LAST SUCCESSFUL UPDATE: <strong className="text-slate-200">{provenance.clock_display}</strong></span>
      </div>
    );
  };

  return (
    <div className="border border-slate-700/80 bg-[#090E1A] shadow-lg flex flex-col font-sans select-none rounded-none">
      {/* ── 1. OFFICIAL RAILWAY TIME-DISTANCE CONTROL CHART HEADER ── */}
      <div className="bg-[#0B1322] px-3 py-1.5 border-b border-slate-700/80 flex flex-wrap items-center justify-between gap-2">
        {/* Left: Standard Title & Corridor Identity */}
        <div className="shrink-0">
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-mono font-bold tracking-wider text-blue-400 uppercase">
              TIME-DISTANCE CONTROL CHART
            </span>
            <span className="text-slate-600">·</span>
            <span className="text-[11px] font-bold text-white tracking-wide">
              {chartData?.corridor_name ? chartData.corridor_name.replace('CORR_', '').replace(/_/g, ' ') : 'C40 MADURAI → TIRUNELVELI'}
            </span>
            <span className="text-[9.5px] font-mono text-slate-400 bg-[#142033] px-1.5 py-0.2 border border-slate-700">
              {chartData?.total_distance_km ? `${chartData.total_distance_km} km` : '154.9 km'}
            </span>
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-0.5 flex items-center space-x-2">
            <span>23 SEP 2026</span>
            <span className="text-slate-600">|</span>
            <span>{timeHorizon === '24H' ? '00:00–24:00 IST' : '06:00–22:00 IST'}</span>
          </div>
        </div>

        {/* Center: Dynamic Operational Metrics Row */}
        <div className="flex items-center space-x-1.5 text-[10px] font-mono shrink-0">
          <div className="bg-[#121D30] px-2 py-0.5 border border-slate-700 text-slate-300">
            TRAINS: <strong className="text-white font-bold">{rawTrains.length}</strong>
          </div>
          <div className="bg-[#121D30] px-2 py-0.5 border border-slate-700 text-slate-300">
            RELEVANT: <strong className="text-cyan-400 font-bold">{relevantTrainNumbers.size}</strong>
          </div>
          <div className={`px-2 py-0.5 border font-bold ${conflicts.length > 0 ? 'bg-rose-950/80 text-rose-300 border-rose-600 animate-pulse' : 'bg-[#121D30] text-slate-300 border-slate-700'}`}>
            CONFLICTS: <strong className={conflicts.length > 0 ? 'text-rose-200' : 'text-slate-300'}>{conflicts.length}</strong>
          </div>
          <div className="bg-[#121D30] px-2 py-0.5 border border-slate-700 text-slate-300">
            WINDOWS: <strong className="text-emerald-400 font-bold">{windows.length}</strong>
          </div>
          <div className="bg-[#121D30] px-2 py-0.5 border border-slate-700 text-slate-300">
            BLOCKS: <strong className="text-amber-400 font-bold">{blocks.length}</strong>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1 bg-[#121D30] hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              title="Refresh Corridor Telemetry"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin text-amber-400' : ''}`} />
            </button>
          )}
        </div>

        {/* Right: Truthful Telemetry Status Badge */}
        <div className="shrink-0">
          {renderProvenanceHeader()}
        </div>
      </div>

      {/* ── 2. COMPACT OPERATIONAL WORKSTATION TOOLBAR ──────────── */}
      <div className="bg-[#080D17] px-3.5 py-1.5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2.5 text-xs">
        {/* Left: TRAFFIC VIEW FILTER */}
        <div className="flex items-center space-x-1.5">
          <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1 mr-1">
            <Filter className="w-3 h-3 text-slate-500" /> TRAFFIC VIEW:
          </span>
          {[
            { id: 'ALL', label: 'ALL' },
            { id: 'RELEVANT', label: 'RELEVANT' },
            { id: 'CONFLICTS', label: 'CONFLICTS' },
            { id: 'SELECTED_PLAN', label: 'SELECTED PLAN' }
          ].map((mode) => {
            const isActive = trafficView === mode.id;
            return (
              <button
                key={mode.id}
                onClick={() => setTrafficView(mode.id)}
                className={`px-2.5 py-0.5 font-mono text-[10px] font-semibold border transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white border-blue-400 shadow-xs'
                    : 'bg-[#10192A] text-slate-300 border-slate-700 hover:bg-[#18253D] hover:text-white'
                }`}
              >
                {mode.label}
              </button>
            );
          })}
        </div>

        {/* Center: LABEL CONTROL [ AUTO ] [ ALL ] [ NONE ] */}
        <div className="flex items-center space-x-1.5">
          <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider mr-1">
            LABELS:
          </span>
          {[
            { id: 'AUTO', label: 'AUTO' },
            { id: 'ALL', label: 'ALL' },
            { id: 'NONE', label: 'NONE' }
          ].map((mode) => {
            const isActive = labelMode === mode.id;
            return (
              <button
                key={mode.id}
                onClick={() => setLabelMode(mode.id)}
                className={`px-2.5 py-0.5 font-mono text-[10px] font-semibold border transition-colors ${
                  isActive
                    ? 'bg-amber-600 text-white border-amber-400 shadow-xs'
                    : 'bg-[#10192A] text-slate-300 border-slate-700 hover:bg-[#18253D] hover:text-white'
                }`}
                title={mode.id === 'AUTO' ? 'Show Selected, Conflicting & Pinned only (Max 8)' : mode.id === 'ALL' ? 'Display all train labels' : 'Hide all permanent labels'}
              >
                {mode.label}
              </button>
            );
          })}
          {effectivePinnedSet.size > 0 && (
            <button
              onClick={() => {
                setInternalPinned(new Set());
                if (onTogglePinTrain) effectivePinnedSet.forEach(id => onTogglePinTrain(id));
              }}
              className="px-2 py-0.5 font-mono text-[9px] bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 ml-1"
            >
              CLEAR PINNED ({effectivePinnedSet.size})
            </button>
          )}
        </div>

        {/* Right: TIME RANGE & ZOOM CONTROLS */}
        <div className="flex items-center space-x-2">
          {/* Time Range Horizon Toggle */}
          <div className="flex items-center bg-[#10192A] p-0.5 border border-slate-700">
            <button
              onClick={() => setTimeHorizon('OPERATIONAL')}
              className={`px-2 py-0.5 font-mono text-[9.5px] font-bold transition-colors ${
                timeHorizon === 'OPERATIONAL'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              06–22
            </button>
            <button
              onClick={() => setTimeHorizon('24H')}
              className={`px-2 py-0.5 font-mono text-[9.5px] font-bold transition-colors ${
                timeHorizon === '24H'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              00–24
            </button>
          </div>

          {/* Zoom Buttons */}
          <div className="flex items-center space-x-1 bg-[#10192A] p-0.5 border border-slate-700">
            <button
              onClick={() => setZoomLevel(prev => Math.max(1.0, prev - 0.25))}
              className="px-1.5 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 font-mono text-[10px]"
              title="Zoom Out Time Axis"
            >
              −
            </button>
            <span className="font-mono text-[9px] text-slate-400 px-1">{Math.round(zoomLevel * 100)}%</span>
            <button
              onClick={() => setZoomLevel(prev => Math.min(2.5, prev + 0.25))}
              className="px-1.5 py-0.5 text-slate-300 hover:text-white hover:bg-slate-700 font-mono text-[10px]"
              title="Zoom In Time Axis"
            >
              +
            </button>
            <button
              onClick={() => setZoomLevel(1.0)}
              className="px-1.5 py-0.5 text-slate-400 hover:text-white hover:bg-slate-700 font-mono text-[9px] border-l border-slate-700 ml-0.5"
              title="Reset Zoom to 100%"
            >
              RESET
            </button>
            <button
              onClick={() => { setZoomLevel(1.0); setTimeHorizon('OPERATIONAL'); }}
              className="px-1.5 py-0.5 text-slate-400 hover:text-white hover:bg-slate-700 font-mono text-[9px]"
              title="Fit to Workstation Window"
            >
              FIT
            </button>
          </div>
        </div>
      </div>

      {/* ── 3. MAIN WORKSTATION CANVAS (STATION AXIS + TIME CANVAS) ── */}
      {/* Target height: Minimum 580px, responsive calc height */}
      <div
        ref={containerRef}
        onMouseMove={handleCanvasMouseMove}
        className="relative w-full h-[600px] min-h-[580px] bg-[#060A13] flex border-b border-slate-800 overflow-hidden"
      >
        {/* Loading Overlay */}
        {loading && !chartData && (
          <div className="absolute inset-0 bg-[#060A13]/90 z-50 flex flex-col items-center justify-center text-slate-200">
            <RefreshCw className="w-8 h-8 text-blue-400 animate-spin mb-2" />
            <span className="font-mono text-xs uppercase tracking-wider text-slate-300">
              Loading Corridor C40 Trajectories & Station Topology...
            </span>
          </div>
        )}

        {/* ── DEDICATED FIXED-WIDTH STATION Y-AXIS (LEFT COLUMN) ─── */}
        {/* Width: 140px. Station labels NEVER overlap the chart canvas! */}
        <div className="w-[140px] min-w-[140px] bg-[#090F1C] border-r border-slate-700/90 relative z-30 select-none shadow-md shrink-0">
          {/* Top Axis Label Header */}
          <div className="h-6 bg-[#070D18] border-b border-slate-700 px-2 flex items-center justify-between text-[9px] font-mono font-bold text-slate-400 uppercase tracking-wide">
            <span>STATION</span>
            <span>DIST</span>
          </div>

          {/* Station Rows: Code (bold) + clean wrapped name + km */}
          {stations.map((stn) => {
            const formatted = formatStationName(stn.station_code, stn.station_name);
            return (
              <div
                key={stn.station_code}
                className="absolute left-0 right-0 -translate-y-1/2 px-2 py-0.5 flex items-center justify-between text-[10px] font-mono border-r-2 border-blue-500/80 hover:bg-[#121B2D] transition-colors group cursor-default"
                style={{ top: `${stn.y_pct}%` }}
                title={`${stn.station_code} — ${stn.station_name} (${stn.distance_km} km)`}
              >
                <div className="flex flex-col truncate pr-1 leading-tight">
                  <span className="font-bold text-amber-400 group-hover:text-amber-300 text-[10.5px]">
                    {formatted.primary}
                  </span>
                  <span className="text-[8.5px] text-slate-300 font-sans truncate max-w-[80px]">
                    {formatted.secondary}
                  </span>
                </div>
                <span className="text-[9px] text-slate-400 shrink-0 font-mono">
                  {stn.distance_km}k
                </span>
              </div>
            );
          })}
        </div>

        {/* ── TIME-DISTANCE TRAJECTORY WORKSPACE ─────────────────── */}
        <div className="relative flex-1 h-full overflow-x-auto overflow-y-hidden">
          <div
            className="relative h-full"
            style={{ width: `${zoomLevel * 100}%`, minWidth: '100%' }}
          >
            {/* Top Time Ruler Header */}
            <div className="absolute top-0 left-0 right-0 h-6 bg-[#070D18] border-b border-slate-800 z-20 flex items-center select-none">
              {timeHours.map((th) => (
                <div
                  key={th.min}
                  className="absolute top-0 bottom-0 border-l border-slate-700/60 flex items-center pl-1"
                  style={{ left: `${timeToXPct(th.min)}%` }}
                >
                  <span className="text-[9.5px] font-mono text-slate-400 font-bold">
                    {th.hourNum}
                  </span>
                </div>
              ))}
            </div>

            {/* Station Horizontal Grid Lines across canvas */}
            {stations.map((stn) => (
              <div
                key={`grid-y-${stn.station_code}`}
                className="absolute left-0 right-0 border-t border-slate-800/80 pointer-events-none"
                style={{ top: `${stn.y_pct}%` }}
              />
            ))}

            {/* Major Hourly Vertical Grid Lines */}
            {timeHours.map((th) => (
              <div
                key={`grid-x-${th.min}`}
                className="absolute top-6 bottom-0 border-l border-slate-800/60 pointer-events-none"
                style={{ left: `${timeToXPct(th.min)}%` }}
              />
            ))}

            {/* Minor Half-Hourly Vertical Grid Lines (Very Subtle) */}
            {halfHourTicks.map((minVal) => (
              <div
                key={`grid-minor-${minVal}`}
                className="absolute top-6 bottom-0 border-l border-slate-900/60 pointer-events-none"
                style={{ left: `${timeToXPct(minVal)}%` }}
              />
            ))}

            {/* ── FEASIBLE AVAILABLE MAINTENANCE WINDOWS ─────────── */}
            {/* Subtle shaded vertical/section regions (transparent green/teal) */}
            {windows.map((w) => {
              const yTop = w.y_top_pct || 15;
              const yBot = w.y_bottom_pct || 30;
              const leftPct = timeToXPct(w.start_min);
              const rightPct = timeToXPct(w.end_min);
              const widthPct = Math.max(1, rightPct - leftPct);
              const heightPct = Math.max(2, yBot - yTop);
              const isHovered = hoveredWindow?.id === w.id;
              const isSelected = selectedWindowId === w.id;

              // Focus Mode: if any window or block is selected, non-selected windows become 20% opacity
              const hasSelection = !!selectedWindowId || !!selectedJobId;
              const opacityClass = isSelected
                ? 'opacity-100 ring-2 ring-emerald-400 z-15'
                : hasSelection
                ? 'opacity-25 hover:opacity-100'
                : 'opacity-100';

              const startH = Math.floor(w.start_min / 60).toString().padStart(2, '0');
              const startM = (w.start_min % 60).toString().padStart(2, '0');
              const endH = Math.floor(w.end_min / 60).toString().padStart(2, '0');
              const endM = (w.end_min % 60).toString().padStart(2, '0');

              return (
                <div
                  key={`win-${w.id}-${w.window_code}`}
                  onClick={() => onSelectWindow && onSelectWindow(w)}
                  onMouseEnter={() => setHoveredWindow(w)}
                  onMouseLeave={() => setHoveredWindow(null)}
                  className={`absolute transition-all cursor-pointer pointer-events-auto z-10 ${opacityClass} ${
                    isHovered
                      ? 'bg-emerald-500/20 border border-emerald-400'
                      : 'bg-emerald-500/12 border border-emerald-500/40 border-dashed hover:bg-emerald-500/20'
                  }`}
                  style={{
                    top: `${yTop}%`,
                    height: `${heightPct}%`,
                    left: `${leftPct}%`,
                    width: `${widthPct}%`
                  }}
                >
                  {/* Small top-anchored label: FEASIBLE / <DUR> MIN */}
                  <div className="px-1 py-0.5 font-mono text-[8px] font-bold text-emerald-400/90 leading-tight truncate">
                    <div>FEASIBLE</div>
                    <div className="text-[7.5px] text-emerald-300">{w.usable_duration_min} MIN</div>
                  </div>
                </div>
              );
            })}

            {/* ── SCHEDULED MAINTENANCE BLOCKS (SOLID STRONG BANDS) ─── */}
            {blocks.map((blk) => {
              const yTop = blk.y_top_pct || 15;
              const yBot = blk.y_bottom_pct || 30;
              const leftPct = timeToXPct(blk.scheduled_start_min);
              const rightPct = timeToXPct(blk.scheduled_end_min);
              const widthPct = Math.max(2.2, rightPct - leftPct);
              const heightPct = Math.max(3, yBot - yTop - 1);
              const isSelected = selectedJobId === blk.job_id;
              const isHovered = hoveredBlock?.job_id === blk.job_id;

              // Distinct department operational colors
              const getDeptStyle = (code) => {
                if (code === 'ENGG') return 'bg-amber-600/95 text-white border-amber-400 shadow-amber-900/40';
                if (code === 'SNT') return 'bg-teal-600/95 text-white border-teal-400 shadow-teal-900/40';
                if (code === 'TRD') return 'bg-blue-600/95 text-white border-blue-400 shadow-blue-900/40';
                return 'bg-amber-600/95 text-white border-amber-400';
              };

              const startH = Math.floor((blk.scheduled_start_min || 600) / 60).toString().padStart(2, '0');
              const startM = ((blk.scheduled_start_min || 600) % 60).toString().padStart(2, '0');
              const endH = Math.floor((blk.scheduled_end_min || 690) / 60).toString().padStart(2, '0');
              const endM = ((blk.scheduled_end_min || 690) % 60).toString().padStart(2, '0');

              return (
                <div
                  key={`blk-${blk.job_id}-${blk.block_code}`}
                  onClick={() => onSelectJob && onSelectJob(blk.job_id)}
                  onMouseEnter={() => setHoveredBlock(blk)}
                  onMouseLeave={() => setHoveredBlock(null)}
                  className={`absolute border transition-all z-20 flex flex-col justify-center px-1.5 cursor-pointer shadow-md rounded-2xs ${
                    getDeptStyle(blk.department_code)
                  } ${
                    isSelected
                      ? 'ring-2 ring-cyan-300 ring-offset-1 ring-offset-[#060A13] scale-[1.02] z-30 font-bold'
                      : isHovered
                      ? 'scale-[1.01] brightness-110 z-25'
                      : ''
                  }`}
                  style={{
                    top: `${yTop}%`,
                    height: `${heightPct}%`,
                    left: `${leftPct}%`,
                    width: `${widthPct}%`
                  }}
                >
                  <div className="flex items-center justify-between text-[9px] leading-tight font-bold font-mono">
                    <span className="truncate">{blk.block_code || 'BP-001'}</span>
                    <span className="text-[8px] opacity-90 ml-1">{blk.scheduled_duration_min || 90}m</span>
                  </div>
                  <div className="text-[7.5px] truncate font-mono opacity-90 leading-tight">
                    {startH}:{startM}–{endH}:{endM}
                  </div>
                </div>
              );
            })}

            {/* ── SVG TRAIN TRAJECTORY LINES ───────────────────────── */}
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="absolute inset-0 w-full h-full pointer-events-none z-15"
            >
              {/* Level 4 trains first, then Level 3, then Level 2, then Level 1 (z-order) */}
              {[4, 3, 2, 1].map((levelTarget) => (
                <g key={`level-group-${levelTarget}`}>
                  {rawTrains
                    .filter((tr) => getTrainHierarchyLevel(tr.train_number) === levelTarget)
                    .map((tr) => {
                      if (!tr.trajectory || tr.trajectory.length === 0) return null;

                      const style = getTrajectoryStyle(tr);
                      const pointsStr = tr.trajectory
                        .map((pt) => `${timeToXPct(pt.min).toFixed(2)},${Number(pt.y).toFixed(2)}`)
                        .join(' ');

                      const firstPt = tr.trajectory[0];
                      const lastPt = tr.trajectory[tr.trajectory.length - 1];

                      return (
                        <g
                          key={tr.train_number}
                          className="pointer-events-auto cursor-pointer"
                          onClick={() => handleTrainClick(tr)}
                          onMouseEnter={() => setHoveredTrain(tr.train_number)}
                          onMouseLeave={() => setHoveredTrain(null)}
                        >
                          {/* Subtle glow backdrop only for Level 1 (Selected Train) */}
                          {style.level === 1 && (
                            <polyline
                              points={pointsStr}
                              fill="none"
                              stroke="#00E5FF"
                              strokeWidth={style.strokeWidth * 0.45}
                              strokeOpacity={0.35}
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          )}

                          {/* Main Trajectory Line */}
                          <polyline
                            points={pointsStr}
                            fill="none"
                            stroke={style.stroke}
                            strokeWidth={style.strokeWidth * 0.28}
                            strokeOpacity={style.opacity}
                            strokeDasharray={style.dashArray}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />

                          {/* Level 1 Endpoint Markers */}
                          {style.level === 1 && firstPt && lastPt && (
                            <>
                              <ellipse
                                cx={timeToXPct(firstPt.min).toFixed(2)}
                                cy={Number(firstPt.y).toFixed(2)}
                                rx="0.4"
                                ry="0.7"
                                fill="#00E5FF"
                                stroke="#FFFFFF"
                                strokeWidth="0.15"
                              />
                              <ellipse
                                cx={timeToXPct(lastPt.min).toFixed(2)}
                                cy={Number(lastPt.y).toFixed(2)}
                                rx="0.4"
                                ry="0.7"
                                fill="#00E5FF"
                                stroke="#FFFFFF"
                                strokeWidth="0.15"
                              />
                            </>
                          )}
                        </g>
                      );
                    })}
                </g>
              ))}
            </svg>

            {/* ── CONTROLLED TRAIN LABELS OVERLAY (HTML) ─────────── */}
            {/* Crisp, non-stretched typography placed at trajectory origin/entry */}
            <div className="absolute inset-0 pointer-events-none z-20 overflow-hidden">
              {rawTrains.map((tr) => {
                if (!tr.trajectory || tr.trajectory.length === 0) return null;
                const isSelected = tr.train_number === effectiveSelectedTrainId;
                const isConflicting = conflictingTrainNumbers.has(tr.train_number);
                const isPinned = effectivePinnedSet.has(tr.train_number);
                const isHovered = tr.train_number === hoveredTrain;
                const shouldShowLabel = isSelected || isConflicting || isPinned || isHovered || labelledTrainSet.has(tr.train_number);
                if (!shouldShowLabel) return null;

                // Find first visible waypoint in chart range
                const visiblePt = tr.trajectory.find(p => p.min >= START_MIN) || tr.trajectory[0];
                if (!visiblePt) return null;

                const xPct = timeToXPct(visiblePt.min);
                const yPct = visiblePt.y;
                const dirIcon = (tr.direction || '').toUpperCase() === 'UP' ? '↑' : '↓';

                return (
                  <div
                    key={`lbl-${tr.train_number}`}
                    className="absolute -translate-y-1/2 pointer-events-auto cursor-pointer"
                    style={{ left: `${Math.min(93, Math.max(1, xPct))}%`, top: `${yPct}%` }}
                    onClick={() => handleTrainClick(tr)}
                    onMouseEnter={() => setHoveredTrain(tr.train_number)}
                    onMouseLeave={() => setHoveredTrain(null)}
                  >
                    <span
                      className={`px-1.5 py-0.2 rounded-2xs text-[9px] font-mono font-bold whitespace-nowrap shadow-sm border transition-all flex items-center gap-0.5 ${
                        isSelected
                          ? 'bg-[#00E5FF] text-slate-950 border-white ring-2 ring-cyan-400 shadow-md font-extrabold scale-105'
                          : isConflicting
                          ? 'bg-rose-700 text-white border-rose-400 ring-1 ring-rose-500 font-bold'
                          : isPinned
                          ? 'bg-amber-600 text-white border-amber-300'
                          : 'bg-[#0A1220]/90 text-slate-200 border-slate-700 hover:border-slate-400'
                      }`}
                    >
                      <span className="text-[8px] opacity-75">{dirIcon}</span>
                      {tr.train_number}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* ── CONFLICT CALLOUT MARKERS (SECTION 14) ──────────── */}
            {conflicts.map((conf, idx) => (
              <div
                key={`conf-badge-${conf.train_number}-${idx}`}
                onClick={() => onSelectConflict && onSelectConflict(conf)}
                onMouseEnter={() => setHoveredConflict(conf)}
                onMouseLeave={() => setHoveredConflict(null)}
                className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer z-30 animate-bounce"
                style={{ left: `${conf.intersect_x_pct}%`, top: `${conf.intersect_y_pct}%` }}
                title={`Conflict: Train ${conf.train_number} intersects Block ${conf.block_code} (${conf.section_code})`}
              >
                <span className="px-1.5 py-0.5 bg-rose-600 text-white text-[8px] font-mono font-bold rounded-2xs shadow-lg border border-rose-300 flex items-center gap-0.5">
                  <AlertTriangle className="w-2.5 h-2.5 fill-current" />
                  CONFLICT
                </span>
              </div>
            ))}

            {/* ── COMPACT SMART HOVER TOOLTIP (SECTION 3) ─────────── */}
            {/* Small non-obtrusive tooltip anchored near pointer or top-right without covering chart */}
            {hoveredTrain && !hoveredConflict && !hoveredWindow && !hoveredBlock && (
              <div
                className="absolute z-40 bg-[#0B1526]/95 border border-slate-600 px-2.5 py-1.5 text-white text-[10.5px] shadow-2xl font-mono rounded-xs pointer-events-none"
                style={{
                  top: mousePos.y > 80 ? `${mousePos.y - 65}px` : `${mousePos.y + 20}px`,
                  left: mousePos.x > 300 ? `${mousePos.x - 140}px` : `${mousePos.x + 20}px`
                }}
              >
                {(() => {
                  const tr = rawTrains.find((t) => t.train_number === hoveredTrain);
                  if (!tr) return null;
                  const dir = (tr.direction || 'DOWN').toUpperCase();
                  const dirIcon = dir === 'UP' ? '↑ UP' : '↓ DOWN';
                  return (
                    <div className="space-y-0.5">
                      <div className="flex items-center justify-between gap-3 font-bold border-b border-slate-700/80 pb-0.5">
                        <span className="text-white text-[11px]">TRAIN {tr.train_number}</span>
                        <span className="text-cyan-400 text-[10px]">{dirIcon}</span>
                      </div>
                      <div className="text-[10px] text-slate-300 truncate max-w-[200px]">{tr.train_name}</div>
                      <div className="flex items-center gap-2 text-[9.5px] text-slate-400 pt-0.5">
                        <span className="text-emerald-400 font-bold">RUNNING</span>
                        <span>·</span>
                        <span>{tr.speed_kmh || 75} km/h</span>
                        <span>·</span>
                        <span className={tr.delay_minutes > 10 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                          +{tr.delay_minutes || 0} min
                        </span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Feasible Window Hover Tooltip */}
            {hoveredWindow && (
              <div
                className="absolute z-40 bg-[#07181F]/95 border border-emerald-500/80 px-2.5 py-1.5 text-emerald-200 text-[10px] shadow-2xl font-mono rounded-xs pointer-events-none"
                style={{
                  top: mousePos.y > 80 ? `${mousePos.y - 60}px` : `${mousePos.y + 20}px`,
                  left: mousePos.x > 300 ? `${mousePos.x - 140}px` : `${mousePos.x + 20}px`
                }}
              >
                <div className="font-bold text-white flex items-center justify-between gap-2 border-b border-emerald-800/80 pb-0.5">
                  <span>FEASIBLE WINDOW</span>
                  <span className="text-emerald-400">{hoveredWindow.usable_duration_min} MIN</span>
                </div>
                <div className="text-emerald-300 text-[9.5px] mt-0.5">
                  Span: {Math.floor(hoveredWindow.start_min / 60).toString().padStart(2,'0')}:{(hoveredWindow.start_min % 60).toString().padStart(2,'0')} – {Math.floor(hoveredWindow.end_min / 60).toString().padStart(2,'0')}:{(hoveredWindow.end_min % 60).toString().padStart(2,'0')}
                </div>
                <div className="text-[9px] text-slate-400">
                  Section: SEC-{hoveredWindow.section_id || 'MDU-TEN'}
                </div>
              </div>
            )}

            {/* Maintenance Block Hover Tooltip */}
            {hoveredBlock && (
              <div
                className="absolute z-40 bg-[#1A140B]/95 border border-amber-500/80 px-2.5 py-1.5 text-amber-200 text-[10px] shadow-2xl font-mono rounded-xs pointer-events-none"
                style={{
                  top: mousePos.y > 80 ? `${mousePos.y - 60}px` : `${mousePos.y + 20}px`,
                  left: mousePos.x > 300 ? `${mousePos.x - 140}px` : `${mousePos.x + 20}px`
                }}
              >
                <div className="font-bold text-white flex items-center justify-between gap-2 border-b border-amber-800/80 pb-0.5">
                  <span>{hoveredBlock.block_code || 'BP-001'}</span>
                  <span className="text-amber-400">{hoveredBlock.scheduled_duration_min || 90} MIN</span>
                </div>
                <div className="text-amber-300 text-[9.5px] mt-0.5">
                  Dept: {hoveredBlock.department_code || 'ENGG'} | Section: {hoveredBlock.section_code || 'MDU-TEN'}
                </div>
              </div>
            )}

            {/* Conflict Hover Tooltip */}
            {hoveredConflict && (
              <div
                className="absolute z-40 bg-[#2A0E12]/95 border border-rose-500 px-3 py-2 text-rose-200 text-[10.5px] shadow-2xl font-mono rounded-xs pointer-events-none"
                style={{
                  top: mousePos.y > 90 ? `${mousePos.y - 75}px` : `${mousePos.y + 20}px`,
                  left: mousePos.x > 300 ? `${mousePos.x - 150}px` : `${mousePos.x + 20}px`
                }}
              >
                <div className="font-bold text-white flex items-center gap-1.5 border-b border-rose-800 pb-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  <span>TRAIN / BLOCK CONFLICT</span>
                </div>
                <div className="text-[10px] mt-1 space-y-0.5">
                  <div>Train: <strong className="text-white">{hoveredConflict.train_number}</strong> ({hoveredConflict.train_name})</div>
                  <div>Block: <strong className="text-amber-300">{hoveredConflict.block_code}</strong> ({hoveredConflict.job_code})</div>
                  <div>Section: <strong className="text-slate-200">{hoveredConflict.section_code}</strong></div>
                  <div className="text-rose-300">Action: Modify block / choose alternate window</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 4. DEDICATED COMPACT OPERATIONAL LEGEND BAR (SECTION 17) ─ */}
      <div className="bg-[#080D17] px-4 py-2 flex flex-wrap items-center justify-between text-[10.5px] font-mono text-slate-400 border-t border-slate-800 gap-3">
        {/* Left: Operational Trajectory & Object Legend */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-bold uppercase tracking-wider text-slate-400 text-[10px]">LEGEND:</span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-[#475569] inline-block"></span>
            <span>Train (DOWN)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 border-t border-dashed border-[#475569] inline-block"></span>
            <span>Train (UP)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-1 bg-[#00E5FF] shadow-xs inline-block"></span>
            <span className="text-cyan-300 font-bold">Selected Train</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-2 bg-emerald-500/20 border border-emerald-400 border-dashed inline-block"></span>
            <span>Feasible Window</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3.5 h-2 bg-amber-600 inline-block"></span>
            <span>Maintenance Block</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-600 text-white flex items-center justify-center text-[7px] font-bold">▲</span>
            <span className="text-rose-400 font-bold">Conflict</span>
          </span>
        </div>

        {/* Right: Department Color Codes */}
        <div className="flex items-center space-x-3 text-[10px]">
          <span className="font-bold uppercase tracking-wider text-slate-500">DEPT:</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-amber-600 inline-block"></span>
            <span className="text-slate-300">Engineering</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-teal-600 inline-block"></span>
            <span className="text-slate-300">S&T</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-blue-600 inline-block"></span>
            <span className="text-slate-300">TRD</span>
          </span>
        </div>
      </div>
    </div>
  );
}
