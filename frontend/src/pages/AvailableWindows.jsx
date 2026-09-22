import React, { useState, useEffect } from 'react';
import { Clock, Shield, Sliders, CheckCircle, RefreshCw, GitBranch } from 'lucide-react';
import { getWindows, getSections, getCorridors } from '../services/api';

export default function AvailableWindows() {
  const [windows, setWindows] = useState([]);
  const [sections, setSections] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [selectedCorridorId, setSelectedCorridorId] = useState('');
  const [loading, setLoading] = useState(true);

  const loadData = async (corrId = selectedCorridorId) => {
    setLoading(true);
    try {
      const parsedId = corrId ? parseInt(corrId) : null;
      const [winRes, secRes, corrRes] = await Promise.all([
        getWindows(parsedId),
        getSections(parsedId),
        getCorridors()
      ]);
      setWindows(winRes.data || []);
      setSections(secRes.data || []);
      setCorridors(corrRes.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCorridorChange = (e) => {
    const val = e.target.value;
    setSelectedCorridorId(val);
    loadData(val);
  };

  const formatMinToTime = (min) => {
    const hh = Math.floor(min / 60);
    const mm = min % 60;
    return `${hh.toString().padStart(2, '0')}:${mm.toString().padStart(2, '0')}`;
  };

  return (
    <div className="p-3 space-y-3">
      <div className="bg-white p-3 border border-slate-300 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-[#134074]" />
            MATHEMATICALLY DERIVED MAINTENANCE WINDOWS (SWEEP-LINE ENGINE)
          </h2>
          <p className="text-[11px] text-slate-500">
            W = TrainFreeWindow ∩ CorridorAvailability ∩ OperationalAvailability (5 min safety buffers applied).
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 bg-slate-100 p-1 border border-slate-300">
            <span className="text-[10px] font-bold text-slate-600 uppercase px-1 flex items-center gap-1">
              <GitBranch className="w-3 h-3 text-slate-500" />
              CORRIDOR:
            </span>
            <select
              value={selectedCorridorId}
              onChange={handleCorridorChange}
              className="text-[11px] font-bold bg-white border border-slate-300 px-2 py-0.5 cursor-pointer text-slate-900"
            >
              <option value="">[ ALL ACTIVE CORRIDORS (C01–C46) ]</option>
              {corridors
                .filter(c => c.prototype_code && /^C(0[1-9]|[1-3][0-9]|4[0-6])$/.test(c.prototype_code))
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    [{c.prototype_code}] {c.name}
                  </option>
                ))}
            </select>
          </div>

          <button onClick={() => loadData()} className="cris-btn cris-btn-secondary text-[11px]">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-500' : ''}`} />
            Re-Calculate Windows
          </button>
        </div>
      </div>

      <div className="cris-panel overflow-hidden">
        <div className="cris-panel-header flex items-center justify-between">
          <span>FEASIBLE MAINTENANCE GAP SLOTS ACROSS CORRIDOR SECTIONS</span>
          <span className="text-[10px] text-slate-500 font-mono">{windows.length} Usable Windows Extracted</span>
        </div>

        <div className="overflow-x-auto">
          {windows.length === 0 ? (
            <div className="text-center py-16 text-slate-500 space-y-2">
              <Clock className="w-10 h-10 text-slate-400 mx-auto" />
              <div className="font-bold text-slate-700 text-sm">No feasible maintenance windows available (Awaiting live train traffic data)</div>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                No active train traffic detected. Maintenance windows are derived dynamically from gaps between live train movements and safety buffers.
              </p>
            </div>
          ) : (
            <table className="cris-table">
              <thead>
                <tr>
                  <th>Window Code</th>
                  <th>Railway Section</th>
                  <th>Usable Window (IST)</th>
                  <th>Usable Span (Min)</th>
                  <th>Preceding Train</th>
                  <th>Succeeding Train</th>
                  <th>Buffer Constraints Applied</th>
                  <th>Feasibility Status</th>
                  <th>Derivation Engine</th>
                </tr>
              </thead>
              <tbody>
                {windows.map((w) => (
                  <tr key={w.window_code}>
                    <td className="font-mono font-bold text-slate-900">{w.window_code}</td>
                    <td>
                      <strong className="text-slate-800">{w.section?.name || `Section ${w.section_id}`}</strong>
                    </td>
                    <td className="font-mono font-bold text-[#134074]">
                      {formatMinToTime(w.start_min)} - {formatMinToTime(w.end_min)} ({w.start_min}m - {w.end_min}m)
                    </td>
                    <td>
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-900 font-mono font-bold border border-emerald-300">
                        {w.usable_duration_min} min
                      </span>
                    </td>
                    <td className="font-mono text-slate-700">{w.train_before_no || 'None'}</td>
                    <td className="font-mono text-slate-700">{w.train_after_no || 'None'}</td>
                    <td className="text-[11px] text-slate-600 font-mono">
                      Before: 5m | After: 5m
                    </td>
                    <td>
                      <span className="badge-high">
                        {w.feasibility}
                      </span>
                    </td>
                    <td className="font-mono text-[10px] text-slate-500">
                      {w.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
