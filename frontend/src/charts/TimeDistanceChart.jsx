import React, { useState } from 'react';
import { Radio, AlertCircle, Clock, ShieldCheck, RefreshCw, Layers } from 'lucide-react';

export default function TimeDistanceChart({
  chartData = null,
  loading = false,
  error = null,
  selectedJobId = null,
  onSelectJob = null,
  onRefresh = null
}) {
  const [hoveredTrain, setHoveredTrain] = useState(null);
  const [hoveredBlock, setHoveredBlock] = useState(null);

  // Time scale configuration from backend data (default 06:00 to 22:00 IST)
  const timeRange = chartData?.time_range || { start: '06:00', end: '22:00', start_min: 360, end_min: 1320, total_min: 960 };
  const START_MIN = timeRange.start_min || 360;
  const END_MIN = timeRange.end_min || 1320;
  const TOTAL_MIN = Math.max(1, END_MIN - START_MIN);

  const timeToXPct = (min) => {
    if (min === null || min === undefined) return 0;
    const clamped = Math.max(START_MIN, Math.min(END_MIN, min));
    return ((clamped - START_MIN) / TOTAL_MIN) * 100;
  };

  const stations = chartData?.stations || [];
  const trains = chartData?.trains || [];
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
  const timeHours = [];
  for (let m = START_MIN; m <= END_MIN; m += 60) {
    const hh = Math.floor(m / 60);
    timeHours.push({ min: m, label: `${hh.toString().padStart(2, '0')}:00` });
  }

  const getProvenanceBadge = () => {
    switch (provenance.source) {
      case 'LIVE RADAR':
      case 'LIVE':
        return (
          <span className="bg-emerald-900 text-emerald-300 border border-emerald-500 px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
            <Radio className="w-2.5 h-2.5 text-emerald-400 animate-pulse" />
            DATA PROVENANCE: LIVE RADAR
          </span>
        );
      case 'CACHED':
        return (
          <span className="bg-amber-900 text-amber-300 border border-amber-500 px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
            <Clock className="w-2.5 h-2.5 text-amber-400" />
            DATA PROVENANCE: CACHED TELEMETRY
          </span>
        );
      case 'ERROR':
        return (
          <span className="bg-red-900 text-red-300 border border-red-500 px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
            <AlertCircle className="w-2.5 h-2.5 text-red-400" />
            DATA PROVENANCE: ERROR (OFFLINE)
          </span>
        );
      case 'TIMETABLE':
        return (
          <span className="bg-blue-900 text-blue-300 border border-blue-500 px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
            <Layers className="w-2.5 h-2.5 text-blue-400" />
            DATA PROVENANCE: TIMETABLE
          </span>
        );
      default:
        return (
          <span className="bg-slate-800 text-slate-300 border border-slate-600 px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
            <Radio className="w-2.5 h-2.5 text-slate-400" />
            DATA PROVENANCE: UNAVAILABLE
          </span>
        );
    }
  };

  return (
    <div className="cris-panel overflow-hidden border border-slate-300 bg-white">
      {/* Header */}
      <div className="cris-panel-header flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <span>RAILWAY TIME-DISTANCE STRING CHART (MASTER CORRIDOR TRAJECTORY)</span>
          <span className="text-[10px] bg-blue-100 text-blue-900 px-1.5 py-0.2 border border-blue-300 font-mono">
            X = TIME ({timeRange.start} - {timeRange.end} IST) | Y = {chartData?.corridor?.name || 'NO CORRIDOR SELECTED'}
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[11px]">
          {getProvenanceBadge()}

          {trains.length > 0 && (
            <div className="hidden sm:flex items-center space-x-2 text-[11px] font-normal">
              <span className="w-3 h-0.5 bg-[#0284C7] inline-block"></span>
              <span>Live Train Trajectories ({trains.length})</span>
            </div>
          )}

          {blocks.length > 0 && (
            <div className="flex items-center space-x-1">
              <span className="w-3 h-2 bg-amber-400/80 border border-amber-600 inline-block"></span>
              <span className="capitalize">Maintenance Block</span>
            </div>
          )}

          {windows.length > 0 && (
            <div className="flex items-center space-x-1">
              <span className="w-3 h-2 bg-emerald-500/10 border border-emerald-400 border-dashed inline-block"></span>
              <span className="capitalize">Feasible Window</span>
            </div>
          )}

          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1 hover:bg-slate-700 text-slate-300 transition-colors"
              title="Refresh Chart Telemetry"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-400' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="relative w-full h-[440px] bg-slate-950 border-b border-slate-300 select-none overflow-hidden">
        {/* Loading Overlay */}
        {loading && !chartData && (
          <div className="absolute inset-0 bg-slate-950/80 z-40 flex flex-col items-center justify-center text-slate-200">
            <RefreshCw className="w-8 h-8 text-amber-400 animate-spin mb-2" />
            <span className="font-mono text-xs uppercase tracking-wider">Loading Live Train Trajectories & Section Blocks...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="absolute top-2 left-2 right-2 bg-red-950/90 border border-red-700 p-2 z-30 flex items-center justify-between text-red-200 text-xs font-mono">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <span>LIVE DATA TEMPORARILY UNAVAILABLE — DISPLAYING CACHED STATE</span>
            </div>
            <span>Last Updated: {provenance.clock_display}</span>
          </div>
        )}

        {/* No Corridor Selected State */}
        {stations.length === 0 && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 p-6 text-center z-20">
            <div className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-1">
              NO CORRIDOR SELECTED
            </div>
            <div className="text-xs text-slate-500 max-w-md">
              Please select a railway corridor in the command bar above to view live trains and time-distance diagram.
            </div>
          </div>
        )}

        {/* No Live Trains on Selected Corridor Banner */}
        {stations.length > 0 && trains.length === 0 && !loading && (
          <div className="absolute top-4 right-4 bg-slate-900/90 border border-slate-700 p-2 text-[10px] text-slate-300 font-mono flex items-center gap-2 z-30 shadow-lg">
            <Radio className="w-3.5 h-3.5 text-amber-400" />
            <span>No live train data available. Waiting for live train updates.</span>
          </div>
        )}

        {/* Y-Axis Station Grid Lines & Station Labels */}
        {stations.length === 0 ? (
          <div className="absolute left-2 top-1/2 -translate-y-1/2 text-xs font-mono font-bold text-slate-500 bg-slate-900/90 px-2 py-1 border border-slate-700">
            NO CORRIDOR SELECTED
          </div>
        ) : (
          stations.map((stn) => (
            <div
              key={stn.station_code}
              className="absolute left-0 right-0 border-t border-slate-800/80 flex items-center justify-between px-2 text-[10px] font-mono"
              style={{ top: `${stn.y_pct}%` }}
            >
              <span className="bg-slate-900/90 px-1.5 py-0.5 font-bold text-slate-300 border-l-2 border-amber-400 shadow">
                {stn.station_code} ({stn.station_name}) — {stn.distance_km} km
              </span>
              <span className="text-[9px] text-slate-600 font-mono hidden md:inline">
                {stn.distance_km} km
              </span>
            </div>
          ))
        )}

        {/* X-Axis Time Grid Lines & Hourly Labels */}
        {timeHours.map((th) => (
          <div
            key={th.min}
            className="absolute top-0 bottom-0 border-l border-slate-800/80 pointer-events-none"
            style={{ left: `${timeToXPct(th.min)}%` }}
          >
            <span className="absolute bottom-1 -translate-x-1/2 text-[9px] font-mono text-slate-500 bg-slate-950/70 px-0.5">
              {th.label}
            </span>
          </div>
        ))}

        {/* Feasible Available Maintenance Windows (Shaded green dashed boxes) */}
        {windows.map((w) => {
          const yTop = w.y_top_pct || 15;
          const yBot = w.y_bottom_pct || 30;
          const leftPct = timeToXPct(w.start_min);
          const rightPct = timeToXPct(w.end_min);
          const widthPct = Math.max(1, rightPct - leftPct);
          const heightPct = Math.max(2, yBot - yTop);

          return (
            <div
              key={`win-${w.id}-${w.window_code}`}
              className="absolute bg-emerald-500/10 border border-emerald-500/30 border-dashed transition-all hover:bg-emerald-500/20 hover:border-emerald-400 pointer-events-auto cursor-pointer"
              style={{
                top: `${yTop}%`,
                height: `${heightPct}%`,
                left: `${leftPct}%`,
                width: `${widthPct}%`
              }}
              title={`Available Feasible Window: ${w.window_code} (${w.usable_duration_min}m) Sec ${w.section_id} [Between ${w.train_before_no || 'None'} & ${w.train_after_no || 'None'}]`}
            >
              <span className="text-[8px] font-mono text-emerald-400/80 px-1 truncate block font-bold">
                {w.usable_duration_min}m
              </span>
            </div>
          );
        })}

        {/* SVG Real Train Trajectory Lines */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
          {trains.map((tr) => {
            if (!tr.trajectory || tr.trajectory.length === 0) return null;

            // Generate polyline coordinate string
            const pointsStr = tr.trajectory
              .map((pt) => `${timeToXPct(pt.min)}%,${pt.y}%`)
              .join(' ');

            const firstPt = tr.trajectory[0];
            const isHovered = hoveredTrain === tr.train_number;

            return (
              <g
                key={tr.train_number}
                className="pointer-events-auto cursor-pointer"
                onMouseEnter={() => setHoveredTrain(tr.train_number)}
                onMouseLeave={() => setHoveredTrain(null)}
              >
                {/* Background glow line on hover */}
                {isHovered && (
                  <polyline
                    points={pointsStr}
                    fill="none"
                    stroke={tr.color}
                    strokeWidth={(tr.width || 2.5) + 4}
                    strokeOpacity={0.3}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}

                {/* Main trajectory line */}
                <polyline
                  points={pointsStr}
                  fill="none"
                  stroke={tr.color}
                  strokeWidth={isHovered ? (tr.width || 2.5) + 1 : (tr.width || 2.5)}
                  strokeDasharray={tr.is_dashed ? '5,4' : 'none'}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={isHovered ? 1 : 0.85}
                />

                {/* Train Label at trajectory start */}
                {firstPt && (
                  <text
                    x={`${timeToXPct(firstPt.min) + 0.4}%`}
                    y={`${Math.max(4, firstPt.y - 1)}%`}
                    fill={isHovered ? '#FFFFFF' : tr.color}
                    fontSize="9px"
                    fontFamily="monospace"
                    fontWeight="bold"
                    className="drop-shadow"
                  >
                    {tr.train_number} ({tr.train_name})
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* Active Scheduled Maintenance Blocks Overlays */}
        {blocks.map((blk) => {
          const yTop = blk.y_top_pct || 15;
          const yBot = blk.y_bottom_pct || 30;
          const leftPct = timeToXPct(blk.scheduled_start_min);
          const rightPct = timeToXPct(blk.scheduled_end_min);
          const widthPct = Math.max(1.5, rightPct - leftPct);
          const heightPct = Math.max(3, yBot - yTop - 2);
          const isSelected = selectedJobId === blk.job_id;

          const getDeptBadgeClass = (code) => {
            if (code === 'ENGG') return 'bg-amber-500 text-slate-950 border-amber-300';
            if (code === 'SNT') return 'bg-emerald-600 text-white border-emerald-300';
            if (code === 'TRD') return 'bg-blue-600 text-white border-blue-300';
            return 'bg-amber-500 text-slate-950 border-amber-300';
          };

          return (
            <div
              key={`blk-${blk.job_id}-${blk.block_code}`}
              onClick={() => onSelectJob && onSelectJob(blk.job_id)}
              onMouseEnter={() => setHoveredBlock(blk)}
              onMouseLeave={() => setHoveredBlock(null)}
              className={`absolute rounded-none border transition-all z-20 flex flex-col justify-center px-1.5 shadow-md cursor-pointer ${isSelected
                  ? 'bg-amber-400 text-slate-950 border-white ring-2 ring-amber-300 font-bold scale-[1.02]'
                  : `${getDeptBadgeClass(blk.department_code)} hover:brightness-110`
                }`}
              style={{
                top: `${yTop + 1}%`,
                height: `${heightPct}%`,
                left: `${leftPct}%`,
                width: `${widthPct}%`
              }}
              title={`Scheduled Maintenance Block: ${blk.job_code} [${blk.department_code}] (${blk.scheduled_duration_min}m) - ${blk.block_code}`}
            >
              <div className="flex items-center justify-between text-[10px] leading-tight font-bold">
                <span className="truncate">{blk.job_code}</span>
                <span className="text-[8px] font-mono ml-1">{blk.scheduled_duration_min}m</span>
              </div>
              <div className="text-[8px] truncate font-mono opacity-90">
                {blk.block_code}
              </div>
            </div>
          );
        })}

        {/* Interactive Hover Tooltip for Train */}
        {hoveredTrain && (
          <div className="absolute top-2 right-2 bg-slate-900/95 border border-slate-700 p-2.5 z-30 text-white text-[11px] shadow-xl min-w-[240px]">
            {(() => {
              const tr = trains.find((t) => t.train_number === hoveredTrain);
              if (!tr) return null;
              return (
                <div className="space-y-1">
                  <div className="font-bold text-xs flex items-center justify-between border-b border-slate-700 pb-1" style={{ color: tr.color }}>
                    <span>{tr.train_number} — {tr.train_name}</span>
                    <span className="text-[9px] px-1 py-0.2 bg-slate-800 font-mono text-white">{tr.train_type}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[10px] text-slate-300 font-mono">
                    <div>Speed: <strong className="text-white">{tr.speed_kmh} km/h</strong></div>
                    <div>Line: <strong className="text-white">{tr.direction}</strong></div>
                    <div className="col-span-2">Section: <strong className="text-white">{tr.current_section_code || `SEC ${tr.current_section_id}`}</strong></div>
                    <div className="col-span-2">Delay: <strong className={tr.delay_minutes > 10 ? 'text-red-400' : 'text-emerald-400'}>+{tr.delay_minutes} min</strong></div>
                    <div className="col-span-2 text-[9px] text-slate-400">Source: <strong>{tr.source}</strong></div>
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* Interactive Hover Tooltip for Maintenance Block */}
        {hoveredBlock && (
          <div className="absolute bottom-6 right-2 bg-slate-900/95 border border-amber-500/80 p-2.5 z-30 text-white text-[11px] shadow-xl min-w-[260px]">
            <div className="font-bold text-xs text-amber-400 border-b border-slate-700 pb-1 flex items-center justify-between">
              <span>{hoveredBlock.job_code} [{hoveredBlock.department_code}]</span>
              <span className="text-[9px] font-mono text-slate-300">{hoveredBlock.block_code}</span>
            </div>
            <div className="mt-1 text-[10px] space-y-0.5 text-slate-300">
              <div>Type: <strong className="text-white">{hoveredBlock.work_type}</strong></div>
              <div>Span: <strong className="text-white font-mono">{hoveredBlock.scheduled_start_min}m — {hoveredBlock.scheduled_end_min}m ({hoveredBlock.scheduled_duration_min} min)</strong></div>
              <div>Section: <strong className="text-white font-mono">{hoveredBlock.section_code}</strong></div>
              <div className="text-[9px] text-slate-400 italic mt-1">{hoveredBlock.description}</div>
            </div>
          </div>
        )}
      </div>

      {/* Footer Provenance & Timestamp Bar */}
      <div className="bg-slate-900 px-3 py-1.5 flex flex-wrap items-center justify-between text-[10px] font-mono text-slate-400 border-t border-slate-800">
        <div className="flex items-center space-x-3">
          <span>Active Rakes: <strong className="text-slate-200">{trains.length}</strong></span>
          <span>|</span>
          <span>Candidate Windows: <strong className="text-emerald-400">{windows.length}</strong></span>
          <span>|</span>
          <span>Scheduled Blocks: <strong className="text-amber-400">{blocks.length}</strong></span>
        </div>
        <div className="flex items-center space-x-3">
          <span>Gateway: <strong className="text-slate-300">{provenance.provider}</strong></span>
          <span>|</span>
          <span>Updated: <strong className="text-slate-200">{provenance.clock_display}</strong></span>
        </div>
      </div>
    </div>
  );
}
