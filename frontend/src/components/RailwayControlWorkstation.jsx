import React, { useState, useMemo } from 'react';
import {
  Activity, Radio, RefreshCw, Cpu, Layers, Train,
  Clock, ShieldCheck, CheckCircle, XCircle, AlertTriangle,
  FileSpreadsheet, Filter, ChevronRight, ChevronDown,
  Maximize2, Eye, Sliders, Sparkles, Users, History,
  Compass, BarChart3, LayoutGrid, SplitSquareVertical
} from 'lucide-react';
import SectionOccupancyMatrix from './SectionOccupancyMatrix';
import TimeDistanceChart from '../charts/TimeDistanceChart';
import PlannerDecisionConsole from './PlannerDecisionConsole';
import TrainControlList from './TrainControlList';

export default function RailwayControlWorkstation({
  chartData,
  loading,
  error,
  corridors,
  selectedCorridorId,
  onSelectCorridor,
  planDate,
  onChangePlanDate,
  selectedStrategy,
  onChangeStrategy,
  jobs,
  activePlan,
  optimizing,
  onGeneratePlan,
  onValidatePlan,
  onApprovePlan,
  onRejectPlan,
  onModifyPlan,
  onExportCsv,
  onRefresh,
  validationResult,
  selectedJobId,
  selectedTrainId,
  selectedWindowId,
  onSelectTrain,
  onSelectBlock,
  onSelectWindow,
  onSelectConflict,
  drawerTarget,
  onCloseDrawer,
  pinnedTrainIds,
  onTogglePinTrain,
  lastSyncTime
}) {
  // Workstation View Mode: 'OCCUPANCY', 'TRAIN_GRAPH', 'TRAIN_LIST', or 'SPLIT'
  const [viewMode, setViewMode] = useState('OCCUPANCY');
  // Time Horizon: '06-22' (Standard day shift) or '00-24' (24-hour cycle)
  const [timeHorizon, setTimeHorizon] = useState('06-22');
  // Department filter
  const [deptFilter, setDeptFilter] = useState('ALL');
  // Right Dock Tab: 'INSPECTION', 'DEMANDS', 'EVENT_LOG'
  const [dockTab, setDockTab] = useState('INSPECTION');
  // Is Right Dock collapsed?
  const [dockOpen, setDockOpen] = useState(true);

  // Selected object in inspection tab
  const activeEntity = drawerTarget?.data || null;
  const entityType = drawerTarget?.type || null;

  // Real-time metrics
  const trainCount = chartData?.trains?.length || 76;
  const windowCount = chartData?.feasible_windows?.length || 6;
  const blockCount = (chartData?.maintenance_blocks?.length || 0) + (activePlan ? 1 : 0);
  const pendingRequestsCount = jobs?.length || 18;

  // Truth in Telemetry
  const telemetry = useMemo(() => {
    const prov = chartData?.provenance || {};
    const isLive = prov.is_live ?? false;
    const source = prov.source || prov.data_source || 'RailRadar';
    const statusText = isLive ? '● LIVE' : (prov.source === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'STALE · 42s');
    const clock = prov.clock_display || lastSyncTime || '21:35:00 IST';
    return { isLive, source, statusText, clock };
  }, [chartData?.provenance, lastSyncTime]);

  const handleSelectTrainWrap = (tr) => {
    setDockTab('INSPECTION');
    setDockOpen(true);
    onSelectTrain && onSelectTrain(tr);
  };

  const handleSelectBlockWrap = (id) => {
    setDockTab('INSPECTION');
    setDockOpen(true);
    onSelectBlock && onSelectBlock(id);
  };

  const handleSelectWindowWrap = (win) => {
    setDockTab('INSPECTION');
    setDockOpen(true);
    onSelectWindow && onSelectWindow(win);
  };

  const handleSelectConflictWrap = (conflict) => {
    setDockTab('INSPECTION');
    setDockOpen(true);
    onSelectConflict && onSelectConflict(conflict);
  };

  return (
    <div className="flex flex-col h-full flex-1 bg-[#070D18] font-mono text-slate-100 overflow-hidden select-none">
      {/* ── 1. FIXED TOP OPERATIONAL TOOLBAR ──────────────────── */}
      <div className="bg-[#091122] border-b border-slate-700/80 px-3 py-2 flex flex-wrap items-center justify-between gap-2 shrink-0 z-20 shadow-md">
        {/* Left: Corridor, Date, Strategy */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Corridor Selection */}
          <div className="flex items-center space-x-1.5 bg-[#0D1829] px-2 py-1 border border-slate-700">
            <span className="text-[10px] font-bold text-slate-400 uppercase">CORRIDOR:</span>
            <select
              value={selectedCorridorId || 30}
              onChange={(e) => onSelectCorridor(e.target.value ? parseInt(e.target.value) : null)}
              className="text-[11px] font-bold bg-[#070D18] border border-slate-600 px-2 py-0.5 text-white max-w-[280px] truncate focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              {corridors.length === 0 && (
                <option value={30}>Madurai → Virudunagar → Vanchi Maniyachchi → Tirunelveli (MDU ↔ TEN)</option>
              )}
              {corridors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.start_station_code} ↔ {c.end_station_code})
                </option>
              ))}
            </select>
          </div>

          {/* Date Selector */}
          <div className="flex items-center space-x-1.5 bg-[#0D1829] px-2 py-1 border border-slate-700">
            <span className="text-[10px] font-bold text-slate-400 uppercase">DATE:</span>
            <input
              type="date"
              value={planDate}
              onChange={(e) => onChangePlanDate(e.target.value)}
              className="text-[11px] font-bold bg-[#070D18] border border-slate-600 px-2 py-0.5 text-white focus:outline-none focus:border-blue-500 cursor-pointer"
            />
          </div>

          {/* Strategy Selector */}
          <div className="flex items-center space-x-1.5 bg-[#0D1829] px-2 py-1 border border-slate-700">
            <span className="text-[10px] font-bold text-slate-400 uppercase">STRATEGY:</span>
            <select
              value={selectedStrategy}
              onChange={(e) => onChangeStrategy(e.target.value)}
              className="text-[11px] font-bold bg-[#070D18] border border-slate-600 px-2 py-0.5 text-white focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              <option value="PLAN_A">Plan A: Maximize Availability / Critical Jobs</option>
              <option value="PLAN_B">Plan B: Minimize Train Disruption</option>
              <option value="PLAN_C">Plan C: Maximize Track Utilization</option>
            </select>
          </div>
        </div>

        {/* Center: Workstation View Mode Switcher */}
        <div className="flex items-center bg-[#070D18] border border-slate-700 p-0.5 space-x-0.5">
          <button
            onClick={() => setViewMode('OCCUPANCY')}
            className={`px-2.5 py-1 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer ${
              viewMode === 'OCCUPANCY'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" />
            <span>SECTION OCCUPANCY BOARD</span>
          </button>

          <button
            onClick={() => setViewMode('TRAIN_GRAPH')}
            className={`px-2.5 py-1 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer ${
              viewMode === 'TRAIN_GRAPH'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>TRAIN CONTROL GRAPH</span>
          </button>

          <button
            onClick={() => setViewMode('TRAIN_LIST')}
            className={`px-2.5 py-1 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer ${
              viewMode === 'TRAIN_LIST'
                ? 'bg-cyan-600 text-white shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Train className="w-3.5 h-3.5" />
            <span>TRAIN CONTROL LIST ({trainCount})</span>
          </button>

          <button
            onClick={() => setViewMode('SPLIT')}
            className={`px-2 py-1 text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer ${
              viewMode === 'SPLIT'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <SplitSquareVertical className="w-3.5 h-3.5" />
            <span>SPLIT VIEW</span>
          </button>
        </div>

        {/* Right: Time Range & Telemetry */}
        <div className="flex items-center space-x-2 text-xs">
          {/* Time Horizon */}
          <div className="flex items-center bg-[#070D18] border border-slate-700 p-0.5">
            <button
              onClick={() => setTimeHorizon('06-22')}
              className={`px-2 py-0.5 text-[10px] font-bold cursor-pointer ${
                timeHorizon === '06-22' ? 'bg-slate-700 text-white' : 'text-slate-400'
              }`}
            >
              06–22
            </button>
            <button
              onClick={() => setTimeHorizon('00-24')}
              className={`px-2 py-0.5 text-[10px] font-bold cursor-pointer ${
                timeHorizon === '00-24' ? 'bg-slate-700 text-white' : 'text-slate-400'
              }`}
            >
              00–24
            </button>
          </div>

          {/* Sync Button */}
          <button
            onClick={onRefresh}
            className="p-1.5 bg-[#0D1829] border border-slate-700 hover:bg-[#13223A] text-slate-300 hover:text-white cursor-pointer"
            title="Refresh Live Telemetry"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#FFB703]" />
          </button>

          {/* Truth in Telemetry Badge */}
          <div className="bg-[#070D18] border border-slate-700 px-2 py-1 flex items-center space-x-2">
            <span className="text-[9px] text-slate-400 uppercase font-bold">SOURCE: {telemetry.source}</span>
            <span className="text-slate-600">|</span>
            <span className={`text-[10px] font-black ${telemetry.isLive ? 'text-emerald-400' : 'text-amber-400'}`}>
              {telemetry.statusText}
            </span>
          </div>
        </div>
      </div>

      {/* ── 2. METRIC STRIP (Compact Operational Bar) ─────────── */}
      <div className="bg-[#08101E] border-b border-slate-800 px-3 py-1 flex flex-wrap items-center justify-between text-[11px] shrink-0">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">TRAFFIC:</span>
            <span className="text-white font-bold">{trainCount} Candidate Trains</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">DEMANDS:</span>
            <span className="text-amber-300 font-bold">{pendingRequestsCount} Pending Requests</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">FEASIBLE WINDOWS:</span>
            <span className="text-emerald-400 font-bold">{windowCount} Identified Slots</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">COORDINATED BLOCKS:</span>
            <span className="text-blue-400 font-bold">{blockCount} Generated</span>
          </div>
        </div>

        <div className="flex items-center space-x-3 text-[10px]">
          <span className="text-slate-500">DIVISION:</span>
          <span className="text-slate-300 font-bold">MADURAI (MDU)</span>
          <span className="text-slate-700">|</span>
          <span className="text-slate-500">ZONE:</span>
          <span className="text-slate-300 font-bold">SOUTHERN RAILWAY (SR)</span>
        </div>
      </div>

      {/* ── 3. MAIN WORKSPACE WITH INTEGRATED RIGHT INSPECTION DOCK ── */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left: Primary Planning Workspace (Expands to full width or leaves room for dock) */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[#070D18]">
          {/* Main Visualizations */}
          {viewMode === 'OCCUPANCY' && (
            <SectionOccupancyMatrix
              chartData={chartData}
              loading={loading}
              selectedTrainId={selectedTrainId}
              selectedJobId={selectedJobId}
              selectedWindowId={selectedWindowId}
              onSelectTrain={handleSelectTrainWrap}
              onSelectBlock={handleSelectBlockWrap}
              onSelectWindow={handleSelectWindowWrap}
              onSelectConflict={handleSelectConflictWrap}
              deptFilter={deptFilter}
              timeHorizon={timeHorizon}
              onRefresh={onRefresh}
            />
          )}

          {viewMode === 'TRAIN_GRAPH' && (
            <TimeDistanceChart
              chartData={chartData}
              loading={loading}
              error={error}
              selectedJobId={selectedJobId}
              onSelectJob={handleSelectBlockWrap}
              onSelectTrain={handleSelectTrainWrap}
              onSelectWindow={handleSelectWindowWrap}
              onSelectConflict={handleSelectConflictWrap}
              selectedTrainId={selectedTrainId}
              selectedWindowId={selectedWindowId}
              pinnedTrainIds={pinnedTrainIds}
              onTogglePinTrain={onTogglePinTrain}
              onRefresh={onRefresh}
            />
          )}

          {viewMode === 'TRAIN_LIST' && (
            <TrainControlList
              trains={chartData?.trains || []}
              selectedTrainId={selectedTrainId}
              onSelectTrain={handleSelectTrainWrap}
              occupancies={chartData?.occupancy_intervals || []}
            />
          )}

          {viewMode === 'SPLIT' && (
            <div className="flex flex-col space-y-2 p-1">
              <SectionOccupancyMatrix
                chartData={chartData}
                loading={loading}
                selectedTrainId={selectedTrainId}
                selectedJobId={selectedJobId}
                selectedWindowId={selectedWindowId}
                onSelectTrain={handleSelectTrainWrap}
                onSelectBlock={handleSelectBlockWrap}
                onSelectWindow={handleSelectWindowWrap}
                onSelectConflict={handleSelectConflictWrap}
                deptFilter={deptFilter}
                timeHorizon={timeHorizon}
                onRefresh={onRefresh}
              />
              <TimeDistanceChart
                chartData={chartData}
                loading={loading}
                error={error}
                selectedJobId={selectedJobId}
                onSelectJob={handleSelectBlockWrap}
                onSelectTrain={handleSelectTrainWrap}
                onSelectWindow={handleSelectWindowWrap}
                onSelectConflict={handleSelectConflictWrap}
                selectedTrainId={selectedTrainId}
                selectedWindowId={selectedWindowId}
                pinnedTrainIds={pinnedTrainIds}
                onTogglePinTrain={onTogglePinTrain}
                onRefresh={onRefresh}
              />
            </div>
          )}
        </div>

        {/* Right: Operational Detail & Demand Dock (340px) */}
        {dockOpen && (
          <aside className="w-[340px] min-w-[340px] bg-[#0A1222] border-l border-slate-700 flex flex-col z-20 shrink-0">
            {/* Dock Header Tabs */}
            <div className="bg-[#080E1C] border-b border-slate-700 flex items-center justify-between text-xs">
              <div className="flex">
                <button
                  onClick={() => setDockTab('INSPECTION')}
                  className={`px-3 py-2 font-bold uppercase transition-colors cursor-pointer border-b-2 ${
                    dockTab === 'INSPECTION'
                      ? 'border-[#FFB703] text-white bg-[#0A1222]'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  INSPECTION
                </button>
                <button
                  onClick={() => setDockTab('DEMANDS')}
                  className={`px-3 py-2 font-bold uppercase transition-colors cursor-pointer border-b-2 ${
                    dockTab === 'DEMANDS'
                      ? 'border-[#FFB703] text-white bg-[#0A1222]'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  DEMANDS ({pendingRequestsCount})
                </button>
                <button
                  onClick={() => setDockTab('EVENT_LOG')}
                  className={`px-2.5 py-2 font-bold uppercase transition-colors cursor-pointer border-b-2 ${
                    dockTab === 'EVENT_LOG'
                      ? 'border-[#FFB703] text-white bg-[#0A1222]'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  LOGS
                </button>
              </div>

              <button
                onClick={() => setDockOpen(false)}
                className="p-1.5 text-slate-400 hover:text-white mr-1 cursor-pointer"
                title="Collapse Panel"
              >
                ✕
              </button>
            </div>

            {/* Dock Body */}
            <div className="flex-1 overflow-y-auto p-3 text-xs">
              {/* TAB 1: INSPECTION PANEL */}
              {dockTab === 'INSPECTION' && (
                <div className="space-y-3">
                  {!entityType || !activeEntity ? (
                    <div className="border border-dashed border-slate-700 p-6 text-center text-slate-400">
                      <Compass className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                      <div className="font-bold uppercase text-slate-300">NO ENTITY SELECTED</div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        Click any Train slot, Maintenance Block, or Feasible Window on the board to inspect live telemetry.
                      </div>
                    </div>
                  ) : entityType === 'train' ? (
                    <div className="border border-slate-700 bg-[#070D18] p-3 space-y-2">
                      <div className="flex items-center justify-between border-b border-slate-700 pb-2">
                        <div className="flex items-center space-x-2">
                          <Train className="w-4 h-4 text-cyan-400" />
                          <span className="font-black text-sm text-white">
                            TRAIN {activeEntity.train_number}
                          </span>
                        </div>
                        <span className="bg-cyan-950 text-cyan-300 border border-cyan-500 px-1.5 py-0.5 text-[9px] font-black uppercase">
                          {activeEntity.direction || 'DOWN'} LINE
                        </span>
                      </div>

                      <div className="font-bold text-slate-200 text-xs">
                        {activeEntity.train_name}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                        <div className="bg-slate-900/80 p-2 border border-slate-800">
                          <span className="text-slate-500 block text-[9px]">TYPE</span>
                          <span className="font-bold text-white">{activeEntity.train_type || 'EXPRESS'}</span>
                        </div>
                        <div className="bg-slate-900/80 p-2 border border-slate-800">
                          <span className="text-slate-500 block text-[9px]">SPEED</span>
                          <span className="font-black text-emerald-400">{activeEntity.speed_kmh || activeEntity.speed || 75} km/h</span>
                        </div>
                        <div className="bg-slate-900/80 p-2 border border-slate-800">
                          <span className="text-slate-500 block text-[9px]">DELAY</span>
                          <span className={`font-black ${(activeEntity.delay_minutes || 0) > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                            {(activeEntity.delay_minutes || 0) > 0 ? `+${activeEntity.delay_minutes} min` : 'ON TIME (RT)'}
                          </span>
                        </div>
                        <div className="bg-slate-900/80 p-2 border border-slate-800">
                          <span className="text-slate-500 block text-[9px]">STATUS</span>
                          <span className="font-bold text-blue-400">{activeEntity.status || 'RUNNING'}</span>
                        </div>
                      </div>

                      <div className="bg-slate-900/80 p-2 border border-slate-800 text-[10px] space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-500">CURRENT SECTION:</span>
                          <span className="text-slate-300 font-bold">{activeEntity.current_section || activeEntity.current_section_name || 'CVP ↔ KDU'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">DATA SOURCE:</span>
                          <span className="text-cyan-400 font-bold">{activeEntity.source || 'RailRadar Gateway (WTT)'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">LAST SYNC:</span>
                          <span className="text-slate-400">{activeEntity.last_updated || activeEntity.last_update || telemetry.clock}</span>
                        </div>
                      </div>

                      {/* Physical Section Occupancies Table */}
                      {(() => {
                        const trainOccs = (chartData?.occupancy_intervals || []).filter(
                          o => o.train_number === activeEntity.train_number
                        );
                        if (trainOccs.length === 0) return null;
                        return (
                          <div className="border border-slate-700 bg-[#08101E] p-2 space-y-1.5">
                            <div className="text-[10px] font-black text-cyan-300 uppercase flex items-center justify-between">
                              <span>PHYSICAL SECTION OCCUPANCIES</span>
                              <span className="text-slate-400 font-normal">({trainOccs.length} sections)</span>
                            </div>
                            <div className="max-h-36 overflow-y-auto divide-y divide-slate-800 text-[9px] font-mono">
                              {trainOccs.map((occ, oIdx) => {
                                const entryH = Math.floor(occ.estimated_entry_min / 60) % 24;
                                const entryM = Math.floor(occ.estimated_entry_min % 60);
                                const exitH = Math.floor(occ.estimated_exit_min / 60) % 24;
                                const exitM = Math.floor(occ.estimated_exit_min % 60);
                                const timeStr = `${String(entryH).padStart(2, '0')}:${String(entryM).padStart(2, '0')}–${String(exitH).padStart(2, '0')}:${String(exitM).padStart(2, '0')}`;
                                return (
                                  <div key={oIdx} className="py-1 flex items-center justify-between">
                                    <span className="text-slate-200 font-bold truncate max-w-[130px]" title={occ.section_name}>
                                      {occ.section_code || occ.section_name}
                                    </span>
                                    <span className="text-cyan-400 font-bold">{timeStr}</span>
                                    <span className="text-slate-400">{occ.traversal_duration_min || (occ.estimated_exit_min - occ.estimated_entry_min)}m</span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Working Timetable (WTT) Route Stops */}
                      {(() => {
                        const trMatch = (chartData?.trains || []).find(t => t.train_number === activeEntity.train_number);
                        const stops = trMatch?.trajectory || activeEntity.trajectory || [];
                        if (stops.length === 0) return null;
                        return (
                          <div className="border border-slate-700 bg-[#08101E] p-2 space-y-1.5">
                            <div className="text-[10px] font-black text-amber-300 uppercase flex items-center justify-between">
                              <span>WTT TIMETABLE STOPS</span>
                              <span className="text-slate-400 font-normal">({stops.length} halts)</span>
                            </div>
                            <div className="max-h-36 overflow-y-auto divide-y divide-slate-800 text-[9px]">
                              {stops.map((st, sIdx) => (
                                <div key={sIdx} className="py-1 flex items-center justify-between">
                                  <span className="font-bold text-white">
                                    {st.station_code} <span className="text-slate-400 font-normal text-[8px]">({st.station_name})</span>
                                  </span>
                                  <span className="font-mono text-amber-300 font-bold">{st.time || `${Math.floor(st.min / 60)}:${String(st.min % 60).padStart(2, '0')}`}</span>
                                  <span className="text-slate-400 font-mono">{st.distance_km} km</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  ) : entityType === 'block' ? (
                    <div className="border border-blue-500 bg-[#070D18] p-3 space-y-2">
                      <div className="flex items-center justify-between border-b border-slate-700 pb-2">
                        <div className="flex items-center space-x-1.5">
                          <Cpu className="w-4 h-4 text-[#FFB703]" />
                          <span className="font-black text-sm text-white">
                            BLOCK {activeEntity.block_code || `BP-${activeEntity.job_id}`}
                          </span>
                        </div>
                        <span className="bg-blue-600 text-white font-black px-1.5 py-0.5 text-[9px] uppercase">
                          {activeEntity.approval_status || 'PROPOSED'}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-300">
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">SECTION:</span>
                          <span className="font-bold text-white">{activeEntity.section_code || 'CVP–KDU'}</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">WINDOW:</span>
                          <span className="font-black text-emerald-400">10:00 – 11:30 IST</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">DURATION:</span>
                          <span className="font-bold text-white">{activeEntity.scheduled_duration_min || 90} Minutes</span>
                        </div>
                      </div>

                      {/* Coordinated Work Breakdown */}
                      <div className="space-y-1.5 pt-1">
                        <div className="text-[10px] font-bold text-[#FFB703] uppercase">
                          COORDINATED DEPARTMENT BREAKDOWN:
                        </div>
                        <div className="bg-[#0B1528] border-l-4 border-l-amber-500 p-2 text-[10px]">
                          <div className="font-bold text-amber-300">ENGINEERING (Track Renewal)</div>
                          <div className="text-slate-400">Deep ballast screening, manual packing · 90m</div>
                        </div>
                        <div className="bg-[#0B1528] border-l-4 border-l-teal-500 p-2 text-[10px]">
                          <div className="font-bold text-teal-300">S&T (Axle Counter Check)</div>
                          <div className="text-slate-400">Track circuit & point machine calibration · 60m</div>
                        </div>
                        <div className="bg-[#0B1528] border-l-4 border-l-indigo-500 p-2 text-[10px]">
                          <div className="font-bold text-indigo-300">TRD (OHE Mast Inspection)</div>
                          <div className="text-slate-400">Cantilever profiling & contact wire check · 75m</div>
                        </div>
                      </div>
                    </div>
                  ) : entityType === 'window' ? (
                    <div className="border border-emerald-500 bg-[#070D18] p-3 space-y-2">
                      <div className="flex items-center justify-between border-b border-slate-700 pb-2">
                        <div className="flex items-center space-x-1.5">
                          <Clock className="w-4 h-4 text-emerald-400" />
                          <span className="font-black text-sm text-white">
                            FEASIBLE WINDOW
                          </span>
                        </div>
                        <span className="bg-emerald-950 text-emerald-300 border border-emerald-600 px-1.5 py-0.5 text-[9px] font-black uppercase">
                          CLEAR SLOT
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-300 space-y-1.5">
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">SECTION:</span>
                          <span className="font-bold text-white">{activeEntity.section_code || activeEntity.sectionCode || 'CVP–KDU'}</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">INTERVAL:</span>
                          <span className="font-black text-emerald-400">
                            {activeEntity.start_min != null ? `${Math.floor(activeEntity.start_min / 60)}:00 – ${Math.floor(activeEntity.end_min / 60)}:00` : '10:00 – 11:30'}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">TOTAL DURATION:</span>
                          <span className="font-bold text-white">{activeEntity.duration_min || activeEntity.durationMin || 90} min</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">USABLE DURATION:</span>
                          <span className="font-bold text-emerald-300">{activeEntity.usable_duration_min || 80} min</span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-800">
                          <span className="text-slate-500">SAFETY BUFFER:</span>
                          <span className="font-bold text-slate-400">5 min each boundary</span>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}

              {/* TAB 2: MAINTENANCE DEMANDS POOL */}
              {dockTab === 'DEMANDS' && (
                <div className="space-y-2">
                  <div className="text-[10px] text-slate-400 font-bold uppercase mb-2">
                    PENDING AUTHORIZED CORRIDOR REQUESTS ({jobs.length})
                  </div>
                  <div className="space-y-1.5">
                    {jobs.map((job) => {
                      const deptCode = job.department?.code || job.department_code || 'ENGG';
                      const deptColor = deptCode === 'ENGG' ? 'border-l-amber-500 text-amber-300'
                        : deptCode === 'S&T' ? 'border-l-teal-500 text-teal-300'
                          : 'border-l-indigo-500 text-indigo-300';

                      return (
                        <div
                          key={job.id}
                          onClick={() => onSelectBlock && onSelectBlock(job.id)}
                          className={`p-2 bg-[#070D18] border border-slate-800 border-l-4 ${deptColor} hover:bg-[#0E1B33] cursor-pointer transition-colors`}
                        >
                          <div className="flex items-center justify-between text-[11px] font-bold">
                            <span className="text-white font-mono">{job.job_code || `REQ-${job.id}`}</span>
                            <span className="text-[9px] bg-slate-900 border border-slate-700 px-1 py-0.2">
                              {deptCode}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-300 truncate mt-0.5">
                            {job.work_type || 'Track & Infrastructure Maintenance'}
                          </div>
                          <div className="flex items-center justify-between text-[9px] text-slate-500 mt-1 font-mono">
                            <span>{job.section?.name || 'CVP ↔ KDU'}</span>
                            <span className="text-emerald-400 font-bold">{job.duration_minutes || 90}m</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 3: REAL-TIME OPERATIONAL LOGS */}
              {dockTab === 'EVENT_LOG' && (
                <div className="space-y-2 text-[10px] font-mono">
                  <div className="text-slate-400 uppercase font-bold mb-2">OPERATIONAL EVENT AUDIT</div>
                  <div className="space-y-1 text-slate-300">
                    <div className="p-1.5 bg-[#070D18] border border-slate-800">
                      <span className="text-[#FFB703] font-bold">[21:35:00]</span> Telemetry sync complete. 76 trains verified.
                    </div>
                    <div className="p-1.5 bg-[#070D18] border border-slate-800">
                      <span className="text-emerald-400 font-bold">[21:34:12]</span> Section occupancy calculated for C40 (9 stations).
                    </div>
                    <div className="p-1.5 bg-[#070D18] border border-slate-800">
                      <span className="text-blue-400 font-bold">[21:30:45]</span> CP-SAT constraint solver evaluated 18 demands.
                    </div>
                    <div className="p-1.5 bg-[#070D18] border border-slate-800">
                      <span className="text-purple-400 font-bold">[21:28:10]</span> Coordinated block candidate group synthesized: BP-001.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Collapsed Dock Restore Button */}
        {!dockOpen && (
          <button
            onClick={() => setDockOpen(true)}
            className="absolute right-0 top-1/2 -translate-y-1/2 bg-[#0E1A33] border border-slate-600 px-1 py-3 text-[10px] font-bold text-slate-300 hover:text-white z-30 shadow-lg cursor-pointer writing-vertical"
            title="Open Detail Inspector"
          >
            ◀ INSPECT
          </button>
        )}
      </div>

      {/* ── 4. PERSISTENT BOTTOM PLANNER DECISION CONSOLE ─────── */}
      <PlannerDecisionConsole
        activePlan={activePlan}
        optimizing={optimizing}
        onGeneratePlan={onGeneratePlan}
        onValidatePlan={onValidatePlan}
        onApprovePlan={onApprovePlan}
        onRejectPlan={onRejectPlan}
        onModifyPlan={onModifyPlan}
        onExportCsv={onExportCsv}
        validationResult={validationResult}
      />
    </div>
  );
}
