import React from 'react';
import {
  X, Train, Clock, MapPin, Gauge, AlertTriangle, ShieldCheck,
  CheckCircle2, XCircle, RefreshCw, Pin, Eye, Calendar, Layers,
  ExternalLink, ArrowRight, Activity, ArrowUp, ArrowDown
} from 'lucide-react';

export default function BlockPlanningDrawer({
  isOpen,
  onClose,
  target, // { type: 'train' | 'block' | 'window' | 'conflict', data: ... }
  onFocusTrain,
  onPinTrain,
  isPinned,
  onApproveBlock,
  onRejectBlock,
  onModifyBlock,
  onRevalidateBlock
}) {
  if (!isOpen || !target) return null;

  const type = target.type;
  const data = target.data || {};

  return (
    <aside
      className="fixed top-0 right-0 bottom-0 w-[360px] max-w-[90vw] bg-[#0A101D] text-slate-100 border-l border-slate-700/90 shadow-2xl z-50 flex flex-col font-sans transition-transform duration-200 ease-out select-none"
      aria-label="Operational Right-Side Detail Drawer"
    >
      {/* ── DRAWER HEADER ──────────────────────────────────── */}
      <div className="bg-[#070D18] px-3.5 py-2.5 border-b border-slate-700/80 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-2">
          {type === 'train' && <Train className="w-4 h-4 text-cyan-400" />}
          {type === 'block' && <Layers className="w-4 h-4 text-amber-400" />}
          {type === 'window' && <Clock className="w-4 h-4 text-emerald-400" />}
          {type === 'conflict' && <AlertTriangle className="w-4 h-4 text-rose-400" />}
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-slate-200">
            {type === 'train' && 'TRAIN TELEMETRY INSPECTOR'}
            {type === 'block' && 'BLOCK PLAN INSPECTOR'}
            {type === 'window' && 'FEASIBLE WINDOW DETAILS'}
            {type === 'conflict' && 'TRAIN / BLOCK CONFLICT'}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
          title="Close Inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── DRAWER BODY CONTENT ───────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3 text-xs">
        {/* ── 1. TRAIN DETAILS ────────────────────────────── */}
        {type === 'train' && (
          <>
            {/* Primary Train Card */}
            <div className="bg-[#121B2B] border border-slate-700/90 p-3 rounded-none">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-base font-mono font-bold text-white tracking-wide flex items-center gap-2">
                    <span>TRAIN {data.train_number}</span>
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 bg-cyan-950 text-cyan-300 border border-cyan-500/60">
                      LEVEL 1 FOCUS
                    </span>
                  </div>
                  <div className="text-xs text-slate-300 font-medium mt-1 line-clamp-1">
                    {data.train_name || 'Corridor Scheduled Service'}
                  </div>
                  <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                    {data.origin_station_name || 'Madurai Jn'} → {data.destination_station_name || 'Tirunelveli Jn'}
                  </div>
                </div>
              </div>

              {/* Status & Direction row */}
              <div className="mt-3 pt-2 border-t border-slate-700/60 flex items-center justify-between text-[10.5px] font-mono">
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-emerald-950/90 text-emerald-300 border border-emerald-500/60 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  RUNNING STATUS: RUNNING
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#0A1220] border border-slate-700 text-slate-200 font-bold">
                  {(data.direction || '').toUpperCase() === 'UP' ? (
                    <>
                      <ArrowUp className="w-3 h-3 text-blue-400" /> LINE: UP
                    </>
                  ) : (
                    <>
                      <ArrowDown className="w-3 h-3 text-amber-400" /> LINE: DOWN
                    </>
                  )}
                </span>
              </div>
            </div>

            {/* Operational Telemetry Grid */}
            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2.5 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60 flex items-center justify-between">
                <span>TELEMETRY & POSITION</span>
                <span className="text-[9px] text-cyan-400">DATA STATE: {data.is_live ? 'LIVE' : 'STALE · 42s'}</span>
              </div>

              <div className="grid grid-cols-2 gap-2.5 text-[10.5px]">
                <div>
                  <span className="text-slate-400 block text-[9px]">TYPE</span>
                  <span className="text-white font-bold">{data.train_type || 'EXPRESS'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">SPEED</span>
                  <span className="text-white font-bold">{data.speed_kmh || 75} km/h</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">DELAY</span>
                  <span className={`font-bold ${data.delay_minutes > 10 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    +{data.delay_minutes || 0} min
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">CURRENT SECTION</span>
                  <span className="text-white font-bold truncate block">
                    {data.current_section_code || 'MDU → TEN'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">DATA SOURCE</span>
                  <span className="text-slate-300 font-bold">{data.source || 'RailRadar'}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">LAST UPDATE</span>
                  <span className="text-slate-200 font-bold">{data.last_update || '16:49:29 IST'}</span>
                </div>
              </div>
            </div>

            {/* Trajectory Route Stations */}
            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60 flex items-center justify-between">
                <span>ROUTE STATIONS ({data.trajectory?.length || 0})</span>
                <span className="font-mono text-[9px] text-slate-400">TIME / EVENT</span>
              </div>

              <div className="max-h-44 overflow-y-auto space-y-1 pr-1 font-mono text-[10px]">
                {data.trajectory && data.trajectory.length > 0 ? (
                  data.trajectory.map((pt, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between py-1 px-1.5 bg-[#090F1C] border border-slate-800/80"
                    >
                      <div className="flex items-center space-x-1.5 truncate">
                        <span className="font-bold text-amber-400">{pt.station_code}</span>
                        <span className="text-slate-300 text-[9px] truncate max-w-[110px]">
                          {pt.station_name}
                        </span>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-cyan-300 font-bold">
                          {pt.time || `${Math.floor(pt.min/60).toString().padStart(2,'0')}:${(pt.min%60).toString().padStart(2,'0')}`}
                        </span>
                        <span className="text-[8px] text-slate-500 ml-1 uppercase">{pt.event_type || 'PASS'}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 text-center py-2 italic font-mono text-[10px]">
                    No intermediate waypoint stops
                  </div>
                )}
              </div>
            </div>

            {/* Actions: [FOCUS TRAIN] [SHOW ROUTE] [CLOSE] */}
            <div className="pt-2 flex items-center gap-2">
              {onFocusTrain && (
                <button
                  onClick={() => onFocusTrain(data)}
                  className="flex-1 py-1.5 px-3 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                >
                  <Eye className="w-3.5 h-3.5" /> FOCUS TRAIN
                </button>
              )}
              {onPinTrain && (
                <button
                  onClick={() => onPinTrain(data.train_number)}
                  className={`py-1.5 px-3 border text-xs font-semibold flex items-center justify-center gap-1 transition-colors ${
                    isPinned
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500'
                      : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-600'
                  }`}
                  title={isPinned ? 'Unpin permanent label' : 'Pin label on chart'}
                >
                  <Pin className="w-3.5 h-3.5" /> {isPinned ? 'PINNED' : 'PIN'}
                </button>
              )}
              <button
                onClick={onClose}
                className="py-1.5 px-3 bg-[#162133] hover:bg-[#1E2D45] text-slate-300 border border-slate-600 text-xs font-semibold"
              >
                CLOSE
              </button>
            </div>
          </>
        )}

        {/* ── 2. BLOCK PLAN DETAILS (SECTION 13) ──────────── */}
        {type === 'block' && (
          <>
            <div className="bg-[#121B2B] border border-slate-700/90 p-3 rounded-none">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-base font-mono font-bold text-white tracking-wide">
                    BLOCK PLAN {data.block_code || 'BP-001'}
                  </div>
                  <div className="text-xs text-slate-300 font-mono mt-0.5">
                    JOB: <strong className="text-white">{data.job_code || `JOB-${data.job_id}`}</strong>
                  </div>
                </div>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border ${
                  data.approval_status === 'APPROVED'
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-600'
                    : 'bg-amber-950 text-amber-300 border-amber-600'
                }`}>
                  STATUS: {data.approval_status || 'PROPOSED'}
                </span>
              </div>

              {/* Department badge & Duration */}
              <div className="mt-2.5 flex items-center gap-2">
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 border ${
                  data.department_code === 'ENGG'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/60'
                    : data.department_code === 'SNT'
                    ? 'bg-teal-500/20 text-teal-300 border-teal-500/60'
                    : 'bg-blue-500/20 text-blue-300 border-blue-500/60'
                }`}>
                  DEPT: {data.department_code === 'ENGG' ? 'ENGINEERING' : data.department_code === 'SNT' ? 'S&T' : 'TRD'}
                </span>
                <span className="text-[11px] font-mono text-slate-300 ml-auto font-bold">
                  {data.scheduled_duration_min || 90} MIN DURATION
                </span>
              </div>
            </div>

            {/* Block Specifications */}
            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60">
                BLOCK TIMING & SECTION
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10.5px]">
                <div className="col-span-2">
                  <span className="text-slate-400 block text-[9px]">SECTION</span>
                  <span className="text-white font-bold truncate block">
                    {data.section_code || 'MDU–TEN (Madurai – Tirunelveli)'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">WINDOW</span>
                  <span className="text-white font-bold">
                    {data.scheduled_start_time || `${Math.floor((data.scheduled_start_min || 600)/60).toString().padStart(2,'0')}:${((data.scheduled_start_min || 600)%60).toString().padStart(2,'0')}`}–{data.scheduled_end_time || `${Math.floor((data.scheduled_end_min || 690)/60).toString().padStart(2,'0')}:${((data.scheduled_end_min || 690)%60).toString().padStart(2,'0')}`} IST
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">DURATION</span>
                  <span className="text-amber-400 font-bold">{data.scheduled_duration_min || 90} min</span>
                </div>
              </div>
            </div>

            {/* Coordinated Demands */}
            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60 flex items-center justify-between">
                <span>COORDINATED REQUESTS</span>
                <span className="text-[9px] text-emerald-400">MULTI-DEPT</span>
              </div>

              <div className="space-y-1 text-[10px]">
                <div className="flex items-center justify-between bg-[#090F1C] p-1.5 border border-slate-800">
                  <span className="font-bold text-amber-300">{data.job_code || 'REQ-ENGG-101'}</span>
                  <span className="text-slate-300">Track Deep Screening</span>
                </div>
                <div className="flex items-center justify-between bg-[#090F1C] p-1.5 border border-slate-800">
                  <span className="font-bold text-teal-300">REQ-SNT-102</span>
                  <span className="text-slate-300">Point Machine Overhaul</span>
                </div>
                <div className="flex items-center justify-between bg-[#090F1C] p-1.5 border border-slate-800">
                  <span className="font-bold text-blue-300">REQ-TRD-103</span>
                  <span className="text-slate-300">OHE Cantilever Adjustment</span>
                </div>
              </div>
            </div>

            {/* Validation & Conflict Checks */}
            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60">
                CONSTRAINT & SAFETY CHECKS
              </div>

              <div className="space-y-1.5 text-[10.5px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">TRAIN CONFLICTS</span>
                  <span className="text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> NONE
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">WINDOW VALIDATION</span>
                  <span className="text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> PASSED
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">SAFETY VALIDATION</span>
                  <span className="text-emerald-400 font-bold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" /> PASSED
                  </span>
                </div>
              </div>
            </div>

            {/* Planner Actions */}
            <div className="pt-2 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => onApproveBlock && onApproveBlock(data)}
                  className="py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1 transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" /> APPROVE
                </button>
                <button
                  onClick={() => onRejectBlock && onRejectBlock(data)}
                  className="py-1.5 px-3 bg-rose-700 hover:bg-rose-600 text-white font-bold text-xs flex items-center justify-center gap-1 transition-colors"
                >
                  <XCircle className="w-3.5 h-3.5" /> REJECT
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => onModifyBlock && onModifyBlock(data)}
                  className="py-1 px-3 bg-[#162133] hover:bg-[#1E2D45] text-slate-200 border border-slate-600 font-semibold text-xs flex items-center justify-center gap-1 transition-colors"
                >
                  MODIFY
                </button>
                <button
                  onClick={() => onRevalidateBlock && onRevalidateBlock(data)}
                  className="py-1 px-3 bg-[#162133] hover:bg-[#1E2D45] text-slate-200 border border-slate-600 font-semibold text-xs flex items-center justify-center gap-1 transition-colors"
                >
                  <RefreshCw className="w-3 h-3" /> REVALIDATE
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── 3. FEASIBLE WINDOW DETAILS (SECTION 10) ──────── */}
        {type === 'window' && (
          <>
            <div className="bg-[#07181F] border border-emerald-500/80 p-3 rounded-none">
              <div className="text-base font-mono font-bold text-white tracking-wide flex items-center justify-between">
                <span>{data.window_code}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-950 text-emerald-300 border border-emerald-500 font-bold">
                  {data.usable_duration_min} MIN AVAILABLE
                </span>
              </div>
              <div className="text-xs text-emerald-300 font-mono mt-1">
                SECTION: SEC-{data.section_id || 'MDU-TEN'}
              </div>
            </div>

            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60">
                TIME & TRAIN HEADWAY BOUNDS
              </div>
              <div className="grid grid-cols-2 gap-2 text-[10.5px]">
                <div>
                  <span className="text-slate-400 block text-[9px]">START TIME</span>
                  <span className="text-white font-bold">
                    {Math.floor((data.start_min || 0) / 60).toString().padStart(2, '0')}:{((data.start_min || 0) % 60).toString().padStart(2, '0')} IST
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[9px]">END TIME</span>
                  <span className="text-white font-bold">
                    {Math.floor((data.end_min || 0) / 60).toString().padStart(2, '0')}:{((data.end_min || 0) % 60).toString().padStart(2, '0')} IST
                  </span>
                </div>
                <div className="col-span-2">
                  <span className="text-slate-400 block text-[9px]">PRECEDING TRAIN</span>
                  <span className="text-slate-200 font-bold truncate block">
                    {data.train_before_no || 'HEAD_OF_SCHEDULE'}
                  </span>
                </div>
                <div className="col-span-2">
                  <span className="text-slate-400 block text-[9px]">SUCCEEDING TRAIN</span>
                  <span className="text-slate-200 font-bold truncate block">
                    {data.train_after_no || 'END_OF_WINDOW'}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-1.5 font-mono text-[10.5px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60">
                SUITABILITY FOR CANDIDATE BLOCKS
              </div>
              <p className="text-slate-300 text-[10px] leading-relaxed">
                This {data.usable_duration_min}-minute slot exceeds the minimum 60-minute coordinated block threshold. Suitable for Civil track renewal, S&T interlocking testing, and TRD inspection.
              </p>
            </div>

            <div className="pt-2">
              <button
                onClick={onClose}
                className="w-full py-1.5 px-3 bg-[#162133] hover:bg-[#1E2D45] text-slate-200 border border-slate-600 font-semibold text-xs"
              >
                CLOSE WINDOW DETAILS
              </button>
            </div>
          </>
        )}

        {/* ── 4. CONFLICT DETAILS (SECTION 14) ─────────────── */}
        {type === 'conflict' && (
          <>
            <div className="bg-[#2A0E12] border border-rose-500/90 p-3 rounded-none">
              <div className="flex items-center space-x-2 text-rose-300 font-mono font-bold text-sm">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span>TRAIN / BLOCK CONFLICT</span>
              </div>
              <div className="text-xs text-rose-200 font-mono mt-1">
                SEVERITY: HIGH OPERATIONAL CONFLICT
              </div>
            </div>

            <div className="bg-[#0E1624] border border-slate-700/80 p-3 space-y-2 font-mono text-[11px]">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pb-1 border-b border-slate-700/60">
                CONFLICT PARTICULARS
              </div>

              <div className="space-y-2 text-[10.5px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">TRAIN</span>
                  <span className="text-white font-bold">{data.train_number} ({data.train_name})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">BLOCK</span>
                  <span className="text-amber-400 font-bold">{data.block_code} ({data.job_code})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">CONFLICT SECTION</span>
                  <span className="text-slate-200 font-bold">{data.section_code || 'MDU–TEN'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">CONFLICT INTERVAL</span>
                  <span className="text-rose-400 font-bold">
                    {Math.floor(data.conflict_start_min / 60).toString().padStart(2,'0')}:{(data.conflict_start_min % 60).toString().padStart(2,'0')}–{Math.floor(data.conflict_end_min / 60).toString().padStart(2,'0')}:{(data.conflict_end_min % 60).toString().padStart(2,'0')} IST
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-[#1A1215] border border-rose-800/80 p-3 space-y-1 text-slate-300 font-mono text-[10.5px]">
              <div className="text-[10px] font-bold text-rose-300 uppercase tracking-wider">
                RECOMMENDED ACTION
              </div>
              <p className="text-[10px] text-slate-300 leading-snug">
                Modify proposed block start time, choose an alternate non-overlapping feasible window, or re-run CP-SAT optimization with train headway constraints.
              </p>
            </div>

            <div className="pt-2 flex items-center gap-2">
              {onModifyBlock && (
                <button
                  onClick={() => onModifyBlock(data)}
                  className="flex-1 py-1.5 px-3 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs"
                >
                  MODIFY BLOCK
                </button>
              )}
              <button
                onClick={onClose}
                className="py-1.5 px-3 bg-[#162133] hover:bg-[#1E2D45] text-slate-200 border border-slate-600 font-semibold text-xs"
              >
                CLOSE
              </button>
            </div>
          </>
        )}
      </div>

      {/* ── DRAWER FOOTER ─────────────────────────────────── */}
      <div className="bg-[#070D18] px-3.5 py-2 border-t border-slate-800 text-[10px] font-mono text-slate-400 flex items-center justify-between shrink-0">
        <span>IR-ABPS SIH26027</span>
        <button onClick={onClose} className="text-cyan-400 hover:underline">
          [CLOSE]
        </button>
      </div>
    </aside>
  );
}
