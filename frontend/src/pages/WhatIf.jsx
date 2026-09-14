import React, { useState, useEffect } from 'react';
import { Cpu, Play, Sliders, ArrowRight, ShieldCheck, TrendingUp, Layers, AlertCircle } from 'lucide-react';
import { simulateWhatIf, getActivePlan, getLiveTrainMovements } from '../services/api';
import KPIComparison from '../charts/KPIComparison';

export default function WhatIf() {
  const [activePlan, setActivePlan] = useState(null);
  const [scenarioName, setScenarioName] = useState('Stress Test: High Duration + Congestion');
  const [trainDelayTrainNo, setTrainDelayTrainNo] = useState('');
  const [trainDelayMin, setTrainDelayMin] = useState(30);
  const [durationMultiplier, setDurationMultiplier] = useState(1.2); // +20% duration
  const [emergencyJob, setEmergencyJob] = useState(false);
  const [loading, setLoading] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);
  const [availableTrains, setAvailableTrains] = useState([]);

  useEffect(() => {
    const checkPlan = async () => {
      try {
        const [planRes, movesRes] = await Promise.all([
          getActivePlan('PLAN_A').catch(() => ({ data: null })),
          getLiveTrainMovements().catch(() => ({ data: [] }))
        ]);
        setActivePlan(planRes.data);
        const trains = movesRes.data || [];
        if (trains.length > 0) {
          setAvailableTrains(trains);
          setTrainDelayTrainNo(trains[0].train_number);
        }
      } catch (err) {
        console.error(err);
      }
    };
    checkPlan();
  }, []);

  const handleRunSimulation = async (e) => {
    e.preventDefault();
    if (!activePlan) {
      alert('No active master plan available for What-If simulation. Please generate a plan in the planner dashboard first.');
      return;
    }
    setLoading(true);
    try {
      const res = await simulateWhatIf({
        base_plan_id: activePlan.id,
        scenario_name: scenarioName,
        train_delay_train_no: trainDelayTrainNo.trim() || undefined,
        train_delay_min: parseInt(trainDelayMin),
        duration_multiplier: parseFloat(durationMultiplier),
        emergency_job_id: emergencyJob ? 1 : null
      });

      setSimulationResult(res.data);
    } catch (err) {
      alert('What-If simulation failed.');
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="p-3 space-y-3">
      {/* Header */}
      <div className="bg-white p-3 border border-slate-300 flex flex-wrap items-center justify-between gap-2 shadow-xs">
        <div>
          <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-[#134074]" />
            WHAT-IF SCENARIO SIMULATION STUDIO
          </h2>
          <p className="text-[11px] text-slate-500">
            Sandbox simulation of operational disruptions (overrun duration, train congestion, emergency insertions) without altering live production schedules.
          </p>
        </div>

        <span className="bg-amber-100 text-amber-900 border border-amber-300 px-2 py-0.5 font-mono text-[10px] font-bold">
          SANDBOX ISOLATION ACTIVE
        </span>
      </div>

      {!activePlan && (
        <div className="bg-amber-50 border border-amber-300 p-3 text-amber-900 flex items-center gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-amber-700 shrink-0" />
          <span>No active master plan available for What-If simulation. Please generate and approve a plan in the Railway Planner dashboard first.</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        {/* Left: What-If Parameter Controls (4 cols) */}
        <div className="lg:col-span-4 cris-panel p-3.5 space-y-3">
          <div className="cris-panel-header -mx-3.5 -mt-3.5 mb-3">
            <span>SCENARIO PERTURBATION PARAMETERS</span>
          </div>

          <form onSubmit={handleRunSimulation} className="space-y-3 text-xs">
            <div>
              <label className="font-bold text-slate-700 uppercase">Scenario Name:</label>
              <input
                type="text"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                className="w-full border border-slate-300 p-1.5 bg-slate-50 font-semibold"
                required
              />
            </div>

            <div>
              <label className="font-bold text-slate-700 uppercase">Maintenance Duration Overrun Factor:</label>
              <div className="grid grid-cols-3 gap-1 mt-1">
                {[
                  { label: 'Normal (1.0x)', val: 1.0 },
                  { label: '+20% (1.2x)', val: 1.2 },
                  { label: '+50% (1.5x)', val: 1.5 }
                ].map((item) => (
                  <button
                    key={item.val}
                    type="button"
                    onClick={() => setDurationMultiplier(item.val)}
                    className={`py-1 text-[11px] font-bold border ${durationMultiplier === item.val
                        ? 'bg-[#134074] text-white border-[#0B2545]'
                        : 'bg-slate-100 text-slate-800 border-slate-300 hover:bg-slate-200'
                      }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="font-bold text-slate-700 uppercase">Simulated Delayed Train (Optional):</label>
              {availableTrains.length > 0 ? (
                <select
                  value={trainDelayTrainNo}
                  onChange={(e) => setTrainDelayTrainNo(e.target.value)}
                  className="w-full border border-slate-300 p-1.5 bg-slate-50 font-mono text-xs mt-1"
                >
                  <option value="">None (No Train Delayed)</option>
                  {availableTrains.map((tr) => (
                    <option key={tr.train_number} value={tr.train_number}>
                      {tr.train_number} - {tr.train_name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="Enter train number (e.g. 12622)..."
                  value={trainDelayTrainNo}
                  onChange={(e) => setTrainDelayTrainNo(e.target.value)}
                  className="w-full border border-slate-300 p-1.5 bg-slate-50 font-mono text-xs mt-1"
                />
              )}
            </div>

            <div>
              <label className="font-bold text-slate-700 uppercase">Simulated Train Delay (Minutes):</label>
              <div className="grid grid-cols-3 gap-1 mt-1">
                {[
                  { label: '0 min', val: 0 },
                  { label: '+30 min', val: 30 },
                  { label: '+60 min', val: 60 }
                ].map((item) => (
                  <button
                    key={item.val}
                    type="button"
                    onClick={() => setTrainDelayMin(item.val)}
                    className={`py-1 text-[11px] font-bold border ${trainDelayMin === item.val
                        ? 'bg-red-600 text-white border-red-800'
                        : 'bg-slate-100 text-slate-800 border-slate-300 hover:bg-slate-200'
                      }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center space-x-2 pt-1">
              <input
                type="checkbox"
                id="em-sim-check"
                checked={emergencyJob}
                onChange={(e) => setEmergencyJob(e.target.checked)}
              />
              <label htmlFor="em-sim-check" className="font-bold text-red-600 uppercase text-[11px]">
                Inject Sudden Emergency Job Requirement
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full cris-btn cris-btn-primary justify-center py-2 text-xs font-bold uppercase mt-2"
            >
              <Play className="w-3.5 h-3.5 fill-current text-emerald-400" />
              {loading ? 'Simulating in Sandbox...' : 'Run What-If Simulation'}
            </button>
          </form>
        </div>

        {/* Right: What-If Comparison Results (8 cols) */}
        <div className="lg:col-span-8 space-y-3">
          {simulationResult ? (
            <div className="space-y-3">
              <div className="cris-panel p-3 bg-white">
                <div className="flex items-center justify-between border-b pb-2 mb-2">
                  <span className="font-bold text-slate-900 uppercase text-xs">
                    SCENARIO: {simulationResult.scenario_name}
                  </span>
                  <span className="badge-high">
                    SOLVER: {simulationResult.scenario_metrics?.solver_status} ({simulationResult.scenario_metrics?.computation_time_ms}ms)
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                  <div className="bg-slate-50 p-2 border border-slate-200">
                    <div className="text-[10px] text-slate-500 uppercase font-bold">Base Blocks</div>
                    <div className="text-lg font-bold font-mono text-slate-700">
                      {simulationResult.base_metrics?.total_blocks_count}
                    </div>
                  </div>
                  <div className="bg-amber-50 p-2 border border-amber-200">
                    <div className="text-[10px] text-amber-700 uppercase font-bold">Scenario Blocks</div>
                    <div className="text-lg font-bold font-mono text-amber-900">
                      {simulationResult.scenario_metrics?.total_blocks_count}
                    </div>
                  </div>
                  <div className="bg-slate-50 p-2 border border-slate-200">
                    <div className="text-[10px] text-slate-500 uppercase font-bold">Base Utilization</div>
                    <div className="text-lg font-bold font-mono text-slate-700">
                      {simulationResult.base_metrics?.block_utilization_pct}%
                    </div>
                  </div>
                  <div className="bg-emerald-50 p-2 border border-emerald-200">
                    <div className="text-[10px] text-emerald-700 uppercase font-bold">Scenario Utilization</div>
                    <div className="text-lg font-bold font-mono text-emerald-900">
                      {simulationResult.scenario_metrics?.block_utilization_pct}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Scheduled Jobs in Scenario */}
              <div className="cris-panel overflow-hidden">
                <div className="cris-panel-header">
                  <span>SCENARIO BLOCK ASSIGNMENTS ({simulationResult.scheduled_jobs?.length} JOBS FEASIBLY SCHEDULED)</span>
                </div>
                <div className="overflow-x-auto max-h-[260px]">
                  <table className="cris-table">
                    <thead>
                      <tr>
                        <th>Job Code</th>
                        <th>Assigned Block</th>
                        <th>Simulated Start</th>
                        <th>Simulated End</th>
                        <th>Duration (with factor)</th>
                        <th>Safety Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {simulationResult.scheduled_jobs?.map((sj, idx) => (
                        <tr key={idx}>
                          <td className="font-mono font-bold text-slate-900">{sj.job_code}</td>
                          <td className="font-mono font-bold text-blue-900">{sj.block_code}</td>
                          <td className="font-mono">{sj.scheduled_start_min}m</td>
                          <td className="font-mono">{sj.scheduled_end_min}m</td>
                          <td className="font-mono font-bold text-amber-800">{sj.scheduled_duration_min}m</td>
                          <td><span className="badge-high">FEASIBLE</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="cris-panel p-12 text-center text-slate-500 bg-white space-y-2">
              <Cpu className="w-10 h-10 text-slate-400 mx-auto" />
              <div className="font-bold text-slate-700 text-sm">No Active What-If Simulation Running</div>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Adjust the perturbation factors on the left and click <strong>"Run What-If Simulation"</strong> to evaluate schedule resilience.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
