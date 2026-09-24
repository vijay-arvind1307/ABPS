import React, { useState, useMemo } from 'react';
import {
  Train, ArrowDown, ArrowUp, Search, Filter, ShieldCheck,
  AlertTriangle, Clock, Radio, Activity, ChevronRight, Gauge
} from 'lucide-react';

export default function TrainControlList({
  trains = [],
  selectedTrainId = null,
  onSelectTrain = () => {},
  occupancies = []
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL'); // 'ALL', 'DOWN', 'UP', 'DELAYED', 'HIGH_PRIORITY'

  // Pre-calculate occupancies count per train
  const occCountMap = useMemo(() => {
    const map = new Map();
    occupancies.forEach(o => {
      const num = o.train_number;
      map.set(num, (map.get(num) || 0) + 1);
    });
    return map;
  }, [occupancies]);

  // Counts for filter pills
  const counts = useMemo(() => {
    let down = 0;
    let up = 0;
    let delayed = 0;
    let highPri = 0;

    trains.forEach(t => {
      if (t.direction === 'DOWN') down++;
      if (t.direction === 'UP') up++;
      if ((t.delay_minutes || 0) > 0) delayed++;
      if (t.priority_level === 1 || t.train_type === 'VANDE_BHARAT' || t.train_type === 'RAJDHANI') highPri++;
    });

    return { total: trains.length, down, up, delayed, highPri };
  }, [trains]);

  // Filtered and sorted train list
  const filteredTrains = useMemo(() => {
    return trains.filter(t => {
      // Search match
      const q = searchTerm.trim().toLowerCase();
      const numMatch = (t.train_number || '').toLowerCase().includes(q);
      const nameMatch = (t.train_name || '').toLowerCase().includes(q);
      const secMatch = (t.current_section_name || t.current_section_code || '').toLowerCase().includes(q);
      if (q && !numMatch && !nameMatch && !secMatch) return false;

      // Filter match
      if (filterType === 'DOWN' && t.direction !== 'DOWN') return false;
      if (filterType === 'UP' && t.direction !== 'UP') return false;
      if (filterType === 'DELAYED' && (t.delay_minutes || 0) <= 0) return false;
      if (filterType === 'HIGH_PRIORITY' && t.priority_level !== 1 && t.train_type !== 'VANDE_BHARAT' && t.train_type !== 'RAJDHANI') return false;

      return true;
    });
  }, [trains, searchTerm, filterType]);

  return (
    <div className="flex flex-col h-full bg-[#070D18] text-slate-100 overflow-hidden select-none">
      {/* ── TOP CONTROL BAR ─────────────────────────────────────── */}
      <div className="bg-[#091120] border-b border-slate-700/80 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center space-x-2">
          <Train className="w-5 h-5 text-cyan-400" />
          <div>
            <h2 className="text-xs font-black text-white tracking-wider uppercase flex items-center gap-1.5">
              <span>ACTIVE CORRIDOR TRAIN MOVEMENTS</span>
              <span className="bg-cyan-950 text-cyan-300 border border-cyan-500/80 px-1.5 py-0.2 text-[9px] font-bold">
                {counts.total} ACTIVE
              </span>
            </h2>
            <p className="text-[10px] text-slate-400">
              Discrete physical block section occupancies and real-time telemetry
            </p>
          </div>
        </div>

        {/* Search & Quick Filters */}
        <div className="flex items-center space-x-2 flex-1 max-w-xl justify-end">
          {/* Search Box */}
          <div className="relative w-48 min-w-[160px]">
            <Search className="w-3.5 h-3.5 absolute left-2 top-2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search train no / name..."
              className="w-full bg-[#050A14] border border-slate-700 focus:border-cyan-400 pl-7 pr-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-hidden"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center space-x-1 text-[10px] font-bold">
            <button
              onClick={() => setFilterType('ALL')}
              className={`px-2 py-1 border transition-colors ${
                filterType === 'ALL'
                  ? 'bg-cyan-500 text-slate-950 border-cyan-400 font-black'
                  : 'bg-[#0B1528] text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              ALL ({counts.total})
            </button>
            <button
              onClick={() => setFilterType('DOWN')}
              className={`px-2 py-1 border transition-colors flex items-center gap-0.5 ${
                filterType === 'DOWN'
                  ? 'bg-cyan-950 text-cyan-300 border-cyan-400 font-black'
                  : 'bg-[#0B1528] text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              <ArrowDown className="w-2.5 h-2.5 text-cyan-400" />
              DOWN ({counts.down})
            </button>
            <button
              onClick={() => setFilterType('UP')}
              className={`px-2 py-1 border transition-colors flex items-center gap-0.5 ${
                filterType === 'UP'
                  ? 'bg-amber-950 text-amber-300 border-amber-400 font-black'
                  : 'bg-[#0B1528] text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              <ArrowUp className="w-2.5 h-2.5 text-amber-400" />
              UP ({counts.up})
            </button>
            <button
              onClick={() => setFilterType('DELAYED')}
              className={`px-2 py-1 border transition-colors ${
                filterType === 'DELAYED'
                  ? 'bg-red-950 text-red-300 border-red-500 font-black'
                  : 'bg-[#0B1528] text-slate-400 border-slate-700 hover:text-white'
              }`}
            >
              DELAYED ({counts.delayed})
            </button>
          </div>
        </div>
      </div>

      {/* ── TRAIN TELEMETRY DATA TABLE ───────────────────────────── */}
      <div className="flex-1 overflow-x-auto overflow-y-auto min-h-0">
        <table className="w-full text-left text-xs border-collapse font-sans">
          <thead className="bg-[#0A1426] text-slate-400 text-[10px] uppercase font-bold sticky top-0 z-10 border-b border-slate-700 shadow-md">
            <tr>
              <th className="py-2 px-3">TRAIN NUMBER</th>
              <th className="py-2 px-3">SERVICE / NAME</th>
              <th className="py-2 px-3">CATEGORY</th>
              <th className="py-2 px-3 text-center">DIRECTION</th>
              <th className="py-2 px-3">CURRENT OCCUPIED SECTION</th>
              <th className="py-2 px-3 text-right">SPEED</th>
              <th className="py-2 px-3 text-right">PUNCTUALITY</th>
              <th className="py-2 px-3 text-center">OCC. BLOCKS</th>
              <th className="py-2 px-3 text-center">ACTION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {filteredTrains.length === 0 ? (
              <tr>
                <td colSpan="9" className="text-center py-12 text-slate-500 font-medium">
                  No train movements match the current filter or search criteria.
                </td>
              </tr>
            ) : (
              filteredTrains.map((tr, idx) => {
                const isSelected = selectedTrainId === tr.train_number;
                const isDown = tr.direction === 'DOWN';
                const delay = tr.delay_minutes || 0;
                const isDelayed = delay > 0;
                const occCount = occCountMap.get(tr.train_number) || (tr.trajectory?.length || 0);

                return (
                  <tr
                    key={tr.train_number}
                    id={`train-row-${tr.train_number}`}
                    onClick={() => onSelectTrain(tr)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-blue-950/80 text-white border-l-4 border-l-cyan-400 shadow-inner'
                        : idx % 2 === 0
                          ? 'bg-[#080E1C]/90 hover:bg-[#101D38]'
                          : 'bg-[#091122]/90 hover:bg-[#101D38]'
                    }`}
                  >
                    {/* Train Number */}
                    <td className="py-2 px-3 font-mono font-black text-cyan-300 text-sm">
                      {tr.train_number}
                    </td>

                    {/* Train Name */}
                    <td className="py-2 px-3 font-bold text-slate-100 max-w-[200px] truncate" title={tr.train_name}>
                      {tr.train_name || `Train ${tr.train_number}`}
                    </td>

                    {/* Type / Class */}
                    <td className="py-2 px-3">
                      <span className={`px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider rounded-xs ${
                        tr.train_type === 'VANDE_BHARAT'
                          ? 'bg-sky-950 text-sky-300 border border-sky-500'
                          : tr.train_type === 'RAJDHANI'
                            ? 'bg-purple-950 text-purple-300 border border-purple-500'
                            : tr.train_type === 'FREIGHT'
                              ? 'bg-slate-800 text-slate-300 border border-slate-600'
                              : 'bg-blue-950 text-blue-300 border border-blue-600'
                      }`}>
                        {tr.train_type || 'EXPRESS'}
                      </span>
                    </td>

                    {/* Direction */}
                    <td className="py-2 px-3 text-center">
                      <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[9px] font-black uppercase rounded-xs ${
                        isDown
                          ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/70'
                          : 'bg-amber-950/80 text-amber-300 border border-amber-500/70'
                      }`}>
                        {isDown ? <ArrowDown className="w-2.5 h-2.5 text-cyan-400" /> : <ArrowUp className="w-2.5 h-2.5 text-amber-400" />}
                        {isDown ? '↓ DOWN' : '↑ UP'}
                      </span>
                    </td>

                    {/* Current Section */}
                    <td className="py-2 px-3 font-medium text-slate-300">
                      {tr.current_section_name || tr.current_section_code || (
                        <span className="text-slate-500 italic">En route</span>
                      )}
                    </td>

                    {/* Speed */}
                    <td className="py-2 px-3 text-right font-mono font-bold text-emerald-400">
                      {(tr.speed_kmh || 75).toFixed(0)} <span className="text-[10px] text-slate-500">km/h</span>
                    </td>

                    {/* Punctuality / Delay */}
                    <td className="py-2 px-3 text-right font-mono font-bold">
                      {isDelayed ? (
                        <span className="text-red-400 bg-red-950/60 px-1.5 py-0.5 border border-red-800">
                          +{delay} min
                        </span>
                      ) : (
                        <span className="text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 border border-emerald-800">
                          ON TIME
                        </span>
                      )}
                    </td>

                    {/* Section Occupancies Count */}
                    <td className="py-2 px-3 text-center font-mono font-bold text-slate-300">
                      <span className="bg-slate-900 border border-slate-700 px-1.5 py-0.2">
                        {occCount} sections
                      </span>
                    </td>

                    {/* Action Button */}
                    <td className="py-2 px-3 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectTrain(tr);
                        }}
                        className="bg-[#0F1E36] hover:bg-cyan-600 hover:text-slate-950 text-cyan-300 border border-cyan-500/60 text-[10px] font-bold px-2 py-0.5 transition-colors flex items-center gap-1 mx-auto"
                      >
                        <span>INSPECT</span>
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ── FOOTER STATUS STRIP ──────────────────────────────────── */}
      <div className="bg-[#091120] border-t border-slate-700/80 px-4 py-1.5 flex items-center justify-between text-[10px] text-slate-400">
        <div className="flex items-center space-x-3">
          <span className="font-bold text-slate-300">TELEMETRY PROVENANCE:</span>
          <span className="text-cyan-400 font-bold">RailRadar Gateway & Working Time Table (WTT)</span>
          <span>·</span>
          <span>Showing {filteredTrains.length} of {trains.length} total corridor trains</span>
        </div>
        <div className="font-mono text-slate-400">
          Selected: <strong className="text-white">{selectedTrainId || 'None'}</strong>
        </div>
      </div>
    </div>
  );
}
