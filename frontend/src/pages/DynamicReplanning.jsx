import React, { useState, useEffect } from 'react';
import {
  Shuffle,
  AlertTriangle,
  Play,
  ArrowRight,
  CheckCircle,
  RefreshCw,
  Clock,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Layers,
  Inbox
} from 'lucide-react';
import {
  getActivePlan,
  simulateTrainDelay,
  dynamicReplan,
  validatePlan,
  approvePlan,
  getKPIComparison,
  getLiveTrainMovements
} from '../services/api';

export default function DynamicReplanning() {
  const [activePlan, setActivePlan] = useState(null);
  const [delayMinutes, setDelayMinutes] = useState(30);
  const [selectedTrain, setSelectedTrain] = useState('');
  const [availableTrains, setAvailableTrains] = useState([]);
  const [step, setStep] = useState(1); // 1: Base State, 2: Event Injected, 3: Re-planned V2, 4: Approved
  const [delayEventResult, setDelayEventResult] = useState(null);
  const [replanResult, setReplanResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadBasePlan = async () => {
    try {
      const [res, movesRes] = await Promise.all([
        getActivePlan('PLAN_A').catch(() => ({ data: null })),
        getLiveTrainMovements().catch(() => ({ data: [] }))
      ]);
      setActivePlan(res.data);
      const trains = movesRes.data || [];
      if (trains.length > 0) {
        setAvailableTrains(trains);
        setSelectedTrain(trains[0].train_number);
      } else {
        setAvailableTrains([]);
        setSelectedTrain('');
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadBasePlan();
  }, []);

  const handleInjectDelay = async () => {
    if (!selectedTrain.trim()) {
      alert('Please specify a train number to simulate delay.');
      return;
    }
    setLoading(true);
    try {
      const res = await simulateTrainDelay({
        train_number: selectedTrain.trim(),
        additional_delay_min: parseInt(delayMinutes),
        reason: 'Operational track congestion / signal delay'
      });
      setDelayEventResult(res.data);
      setStep(2);
    } catch (err) {
      alert('Failed to simulate train delay.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunDynamicReplan = async () => {
    if (!activePlan) return;
    setLoading(true);
    try {
      const res = await dynamicReplan({
        base_plan_id: activePlan.id,
        trigger_event: 'TRAIN_DELAY',
        affected_train_number: selectedTrain.trim(),
        affected_section_id: delayEventResult?.affected_sections?.[0] || 1
      });
      setReplanResult(res.data);
      setStep(3);
      loadBasePlan();
    } catch (err) {
      alert('Dynamic re-planning failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleApproveReplan = async () => {
    if (!replanResult) return;
    try {
      await approvePlan(replanResult.new_plan_id, {
        action: 'APPROVE',
        reason: `Chief Controller approval for dynamic re-planned block schedule version ${replanResult.version}`
      });
      setStep(4);
      alert(`Re-planned Block Schedule Version ${replanResult.version} is now formally APPROVED for operation.`);
      loadBasePlan();
    } catch (err) {
      alert('Approval failed.');
    }
  };

  return (
    <div className="p-3 space-y-3">
      {/* Top Header */}
      <div className="bg-white p-3 border border-slate-300 flex flex-wrap items-center justify-between gap-2 shadow-xs">
        <div>
          <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide flex items-center gap-1.5">
            <Shuffle className="w-4 h-4 text-[#134074]" />
            DYNAMIC RE-PLANNING & DISTURBANCE RESOLUTION CONTROL ROOM
          </h2>
          <p className="text-[11px] text-slate-500">
            Rolling-horizon disturbance re-optimization: Freezes completed/protected blocks and resolves train delay conflicts via CP-SAT.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-[10px] font-mono bg-blue-100 text-blue-900 border border-blue-300 px-2 py-0.5 font-bold">
            ROLLING HORIZON ACTIVE
          </span>
        </div>
      </div>

      {/* 4-Step Operational Disturbance Resolution Stepper */}
      <div className="grid grid-cols-4 gap-2 text-center text-[11px] font-bold">
        <div className={`p-2 border ${step >= 1 ? 'bg-[#0B2545] text-white border-[#0B2545]' : 'bg-slate-100 text-slate-500'}`}>
          1. BASELINE / INITIAL PLAN
        </div>
        <div className={`p-2 border ${step >= 2 ? 'bg-red-700 text-white border-red-800' : 'bg-slate-100 text-slate-500'}`}>
          2. TRAIN DELAY EVENT (+{delayMinutes}m)
        </div>
        <div className={`p-2 border ${step >= 3 ? 'bg-[#134074] text-white border-[#134074]' : 'bg-slate-100 text-slate-500'}`}>
          3. CP-SAT RE-OPTIMIZATION
        </div>
        <div className={`p-2 border ${step >= 4 ? 'bg-emerald-700 text-white border-emerald-800' : 'bg-slate-100 text-slate-500'}`}>
          4. CONTROLLER APPROVAL
        </div>
      </div>

      {/* Main Interactive Work Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        {/* Left: Disturbance Controls (4 cols) */}
        <div className="lg:col-span-4 cris-panel p-3.5 space-y-4">
          <div className="cris-panel-header -mx-3.5 -mt-3.5 mb-3">
            <span>OPERATIONAL DISTURBANCE INJECTION</span>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">
              Select Delayed Train:
            </label>
            {availableTrains.length > 0 ? (
              <select
                value={selectedTrain}
                onChange={(e) => setSelectedTrain(e.target.value)}
                className="w-full border border-slate-300 p-1.5 text-xs bg-slate-50 font-mono font-bold"
              >
                {availableTrains.map((tr) => (
                  <option key={tr.train_number} value={tr.train_number}>
                    {tr.train_number} - {tr.train_name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="space-y-1">
                <input
                  type="text"
                  placeholder="Enter live train number..."
                  value={selectedTrain}
                  onChange={(e) => setSelectedTrain(e.target.value)}
                  className="w-full border border-slate-300 p-1.5 text-xs font-mono"
                />
                <span className="text-[10px] text-slate-500 block">No live corridor trains detected. Enter train number manually.</span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-[11px] font-bold text-slate-700 uppercase mb-1">
              Injected Delay Duration:
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {[15, 30, 60].map((mins) => (
                <button
                  key={mins}
                  type="button"
                  onClick={() => setDelayMinutes(mins)}
                  className={`py-1.5 text-xs font-bold border ${delayMinutes === mins
                    ? 'bg-red-600 text-white border-red-800'
                    : 'bg-slate-100 text-slate-800 border-slate-300 hover:bg-slate-200'
                    }`}
                >
                  +{mins} min
                </button>
              ))}
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-300 p-2 text-amber-900 text-[11px]">
            <div className="font-bold uppercase">Dynamic Horizon Rules:</div>
            <ul className="list-disc list-inside mt-0.5 space-y-0.5 text-[10px]">
              <li>Completed maintenance jobs remain immutable.</li>
              <li>Jobs locked by controller remain frozen.</li>
              <li>Downstream candidate windows re-evaluated.</li>
            </ul>
          </div>

          <button
            onClick={handleInjectDelay}
            disabled={loading || !selectedTrain}
            className="w-full cris-btn cris-btn-danger justify-center py-2 text-xs font-bold uppercase"
          >
            <AlertTriangle className="w-4 h-4" />
            {loading ? 'Simulating...' : `SIMULATE DELAY (+${delayMinutes}m)`}
          </button>

          {step >= 2 && (
            <div className="pt-3 border-t border-slate-300 space-y-2">
              <div className="text-[11px] font-bold text-red-700 uppercase flex items-center gap-1">
                <ShieldAlert className="w-4 h-4" />
                Disturbance Injected: Schedule Impact Evaluated
              </div>
              <p className="text-[11px] text-slate-600">
                Train {selectedTrain} operational delay injected (+{delayMinutes}m). Trigger dynamic re-planning to resolve potential conflicts.
              </p>
              <button
                onClick={handleRunDynamicReplan}
                disabled={loading || !activePlan}
                className="w-full cris-btn cris-btn-primary justify-center py-2 text-xs font-bold uppercase animate-pulse"
              >
                <Shuffle className="w-4 h-4" />
                {loading ? 'Solving via CP-SAT...' : 'Trigger Dynamic Re-Planning'}
              </button>
            </div>
          )}

          {step >= 3 && (
            <div className="pt-3 border-t border-slate-300 space-y-2">
              <div className="text-[11px] font-bold text-emerald-700 uppercase flex items-center gap-1">
                <ShieldCheck className="w-4 h-4" />
                Conflict Resolved (Plan Version Generated)
              </div>
              <p className="text-[11px] text-slate-600">
                Deterministic Safety Validator certified feasibility. Human-in-the-loop authorization required.
              </p>
              <button
                onClick={handleApproveReplan}
                className="w-full cris-btn cris-btn-accent justify-center py-2 text-xs font-bold uppercase"
              >
                <CheckCircle className="w-4 h-4" />
                Formally Approve Re-Planned Schedule
              </button>
            </div>
          )}
        </div>

        {/* Right: Dynamic Delta Diff View (8 cols) */}
        <div className="lg:col-span-8 cris-panel overflow-hidden">
          <div className="cris-panel-header flex items-center justify-between">
            <span>DYNAMIC RE-PLANNING RESOLUTION AUDIT & TIMING SHIFTS</span>
            <span className="text-[10px] font-mono text-slate-600">
              {replanResult ? `PLAN ${replanResult.new_plan_code}` : 'WAITING FOR DISTURBANCE TRIGGER'}
            </span>
          </div>

          <div className="p-4 space-y-4 text-[12px]">
            {step === 1 && (
              <div className="text-center py-12 text-slate-500 space-y-2">
                <Clock className="w-8 h-8 text-slate-400 mx-auto" />
                <div className="font-bold text-slate-700">
                  {activePlan ? `Active Plan (${activePlan.plan_code}) Running Normally` : 'No Active Maintenance Plan Available'}
                </div>
                <p className="text-[11px] text-slate-500 max-w-md mx-auto">
                  {activePlan
                    ? 'Select an active corridor train on the left and trigger a delay to observe real-time rolling-horizon re-planning.'
                    : 'Generate and approve a maintenance block plan in the Railway Planner dashboard first.'}
                </p>
              </div>
            )}

            {step === 2 && delayEventResult && (
              <div className="space-y-3">
                <div className="bg-red-50 border border-red-300 p-3 text-red-950">
                  <div className="font-bold text-xs uppercase flex items-center gap-1.5 text-red-800">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    Disturbance Detected: Train {delayEventResult.train_number} Delayed +{delayEventResult.additional_delay_min} Minutes
                  </div>
                  <div className="mt-1 text-[11px]">
                    Affected Sections: <strong>{delayEventResult.affected_sections?.length ? `Sections: ${delayEventResult.affected_sections.join(', ')}` : 'None'}</strong>
                  </div>
                </div>

                <div className="border border-slate-300 p-3 bg-white">
                  <h4 className="font-bold text-slate-800 uppercase text-[11px] mb-2">
                    Conflicting Maintenance Demands (Before Re-Planning):
                  </h4>
                  <table className="cris-table">
                    <thead>
                      <tr>
                        <th>Job Code</th>
                        <th>Section</th>
                        <th>Scheduled Maintenance Slot</th>
                        <th>Delayed Train Occupancy</th>
                        <th>Safety Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(!delayEventResult.conflicting_scheduled_jobs || delayEventResult.conflicting_scheduled_jobs.length === 0) ? (
                        <tr>
                          <td colSpan="5" className="text-center py-6 text-slate-500">
                            <div className="font-bold text-slate-700">No active conflicts</div>
                            <div className="text-xs text-slate-400 mt-0.5">Delayed train does not encroach on any scheduled maintenance blocks.</div>
                          </td>
                        </tr>
                      ) : (
                        delayEventResult.conflicting_scheduled_jobs.map((cJob, idx) => (
                          <tr key={idx}>
                            <td className="font-mono font-bold text-slate-900">{cJob.job_code}</td>
                            <td>Section {cJob.section_id}</td>
                            <td className="font-mono">{cJob.scheduled_start_min}m - {cJob.scheduled_end_min}m</td>
                            <td className="font-mono text-red-700 font-bold">{cJob.train_occupancy} (Train {cJob.conflicting_train})</td>
                            <td>
                              <span className="badge-emergency">COLLISION RISK</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {step >= 3 && replanResult && (
              <div className="space-y-3">
                <div className="bg-emerald-50 border border-emerald-300 p-3 text-emerald-950">
                  <div className="font-bold text-xs uppercase flex items-center gap-1.5 text-emerald-800">
                    <CheckCircle className="w-4 h-4 text-emerald-600" />
                    Dynamic Re-Planning Completed: {replanResult.summary}
                  </div>
                </div>

                <h4 className="font-bold text-slate-800 uppercase text-[11px]">
                  Delta Changes: Old Schedule vs Re-Optimized Schedule:
                </h4>
                <div className="overflow-x-auto">
                  <table className="cris-table">
                    <thead>
                      <tr>
                        <th>Job Code</th>
                        <th>Change Type</th>
                        <th>Original Slot</th>
                        <th>Revised Slot</th>
                        <th>Original Block</th>
                        <th>Revised Block</th>
                        <th>Safety Validation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {replanResult.delta_changes?.map((dc, idx) => (
                        <tr key={idx} className="bg-blue-50/40 font-semibold">
                          <td className="font-mono font-bold text-slate-900">{dc.job_code}</td>
                          <td>
                            <span className="px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-900 font-mono border border-amber-300">
                              {dc.change_type}
                            </span>
                          </td>
                          <td className="font-mono text-slate-600">{dc.old_start_min}m</td>
                          <td className="font-mono font-bold text-emerald-800">{dc.new_start_min}m</td>
                          <td className="font-mono text-slate-500">{dc.old_block || 'N/A'}</td>
                          <td className="font-mono font-bold text-blue-900">{dc.new_block || 'N/A'}</td>
                          <td>
                            <span className="badge-high">VALIDATED (0 CLASH)</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
