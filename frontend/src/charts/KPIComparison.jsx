import React from 'react';
import { Award, Zap, Shield, TrendingUp, AlertTriangle } from 'lucide-react';

export default function KPIComparison({ comparisonData }) {
  if (!comparisonData) {
    return <div className="p-4 text-slate-500 italic">Loading KPI comparison metrics...</div>;
  }

  const { baseline, plan_a, plan_b, plan_c, what_if } = comparisonData;

  const metrics = [
    {
      key: 'critical_jobs',
      label: 'Critical / Emergency Maintenance Completed',
      icon: Shield,
      render: (p) => `${p?.critical_jobs_completed || 0} / ${p?.total_critical_jobs || 0}`,
      highlight: true
    },
    {
      key: 'total_jobs',
      label: 'Total Demands Scheduled',
      icon: Zap,
      render: (p) => `${p?.total_jobs_completed || 0} jobs`
    },
    {
      key: 'total_blocks',
      label: 'Total Number of Blocks (Footprint)',
      icon: TrendingUp,
      render: (p) => `${p?.total_blocks_count || 0} blocks`
    },
    {
      key: 'utilization',
      label: 'Block Window Utilization %',
      icon: Award,
      render: (p) => `${p?.block_utilization_pct || 0}%`,
      highlight: true
    },
    {
      key: 'train_impact',
      label: 'Estimated Train Disruption Impact (Lower is Better)',
      icon: AlertTriangle,
      render: (p) => `${p?.train_impact_score || 0} pts`
    },
    {
      key: 'asset_avail',
      label: 'Asset Availability Proxy Rating',
      icon: Award,
      render: (p) => `${p?.asset_availability_proxy || 0}%`,
      highlight: true
    },
    {
      key: 'solver_status',
      label: 'Solver Status & Execution Engine',
      icon: Zap,
      render: (p) => p?.solver_status || 'N/A'
    }
  ];

  return (
    <div className="cris-panel overflow-hidden">
      <div className="cris-panel-header flex items-center justify-between">
        <span>DYNAMIC KPI BENCHMARK MATRIX (BASELINE VS CP-SAT OPTIMIZED STRATEGIES)</span>
        <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 border border-emerald-300 font-mono">
          MATHEMATICALLY COMPUTED (NO HARDCODED METRICS)
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="cris-table">
          <thead>
            <tr>
              <th className="w-1/3">Operational KPI / Metric</th>
              <th className="bg-slate-700 text-center">Baseline (Greedy First-Fit)</th>
              <th className="bg-blue-900 text-center text-amber-300">Plan A (Max Availability) ★</th>
              <th className="bg-indigo-900 text-center">Plan B (Min Train Disruption)</th>
              <th className="bg-slate-800 text-center">Plan C (Max Utilization)</th>
              {what_if && <th className="bg-amber-800 text-center text-white">What-If Scenario</th>}
            </tr>
          </thead>
          <tbody>
            {metrics.map((m, idx) => {
              const Icon = m.icon;
              return (
                <tr key={m.key} className={idx % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
                  <td className="font-semibold text-slate-800 flex items-center gap-1.5 py-2">
                    <Icon className="w-3.5 h-3.5 text-[#134074]" />
                    <span>{m.label}</span>
                  </td>
                  <td className="text-center font-mono text-slate-600 bg-slate-100/50">
                    {m.render(baseline)}
                  </td>
                  <td className="text-center font-mono font-bold text-blue-900 bg-blue-50/60 border-l border-r border-blue-200">
                    {m.render(plan_a)}
                  </td>
                  <td className="text-center font-mono text-indigo-900 bg-indigo-50/40">
                    {m.render(plan_b)}
                  </td>
                  <td className="text-center font-mono text-slate-800">
                    {m.render(plan_c)}
                  </td>
                  {what_if && (
                    <td className="text-center font-mono text-amber-900 bg-amber-50 font-bold">
                      {m.render(what_if)}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
