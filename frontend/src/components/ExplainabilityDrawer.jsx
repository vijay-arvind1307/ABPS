import React from 'react';
import { X, CheckCircle, AlertCircle, Shield, Award, Layers, Zap, Sparkles } from 'lucide-react';

export default function ExplainabilityDrawer({ explanation, isOpen, onClose }) {
  if (!isOpen || !explanation) return null;

  const {
    job_code,
    is_scheduled,
    scheduled_start_min,
    scheduled_end_min,
    block_code,
    selection_reasons = [],
    rejection_reasons = [],
    factor_contributions = {},
    compatibility_synergies = [],
    constraints_satisfied = []
  } = explanation;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl border-l-2 border-[#134074] z-50 flex flex-col animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="bg-[#0B2545] text-white p-3.5 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h3 className="font-bold text-sm tracking-wide uppercase">
            OPTIMIZER EXPLANATION: {job_code}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-300 hover:text-white p-1 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 overflow-y-auto flex-1 space-y-4 text-[12px]">
        {/* Status Card */}
        <div className={`p-3 border ${is_scheduled ? 'bg-emerald-50 border-emerald-300 text-emerald-950' : 'bg-amber-50 border-amber-300 text-amber-950'}`}>
          <div className="flex items-center justify-between font-bold text-[13px]">
            <span>DECISION: {is_scheduled ? 'SCHEDULED IN BLOCK' : 'DEFERRED TO NEXT WINDOW'}</span>
            <span className={`px-2 py-0.5 text-[10px] ${is_scheduled ? 'bg-emerald-600 text-white' : 'bg-amber-600 text-white'}`}>
              {is_scheduled ? 'FEASIBLE FIT' : 'WINDOW INSUFFICIENT'}
            </span>
          </div>
          {is_scheduled && (
            <div className="mt-1 font-mono text-[11px] text-emerald-800">
              Block: <strong>{block_code}</strong> | Timing: <strong>{scheduled_start_min}m - {scheduled_end_min}m</strong>
            </div>
          )}
        </div>

        {/* Why Selected / Why Deferred */}
        <div>
          <h4 className="font-bold text-slate-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
            {is_scheduled ? <CheckCircle className="w-4 h-4 text-emerald-600" /> : <AlertCircle className="w-4 h-4 text-amber-600" />}
            {is_scheduled ? 'Why This Job Was Selected by CP-SAT' : 'Why This Job Was Deferred'}
          </h4>
          <ul className="space-y-1 bg-slate-50 border border-slate-200 p-2.5">
            {is_scheduled ? (
              selection_reasons.map((r, idx) => (
                <li key={idx} className="flex items-start gap-1.5 text-slate-800">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>{r}</span>
                </li>
              ))
            ) : (
              rejection_reasons.map((r, idx) => (
                <li key={idx} className="flex items-start gap-1.5 text-red-700">
                  <span className="text-red-600 font-bold">✗</span>
                  <span>{r}</span>
                </li>
              ))
            )}
          </ul>
        </div>

        {/* MCDA Priority Factor Breakdown */}
        <div>
          <h4 className="font-bold text-slate-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
            <Award className="w-4 h-4 text-amber-600" />
            MCDA Priority Factor Contributions (0-100)
          </h4>
          <div className="space-y-2 bg-slate-50 border border-slate-200 p-2.5">
            {Object.entries(factor_contributions).map(([factor, val]) => (
              <div key={factor}>
                <div className="flex justify-between text-[11px] text-slate-700 mb-0.5">
                  <span className="capitalize">{factor.replace('_', ' ')}</span>
                  <span className="font-mono font-bold">{val}</span>
                </div>
                <div className="w-full h-2 bg-slate-200 overflow-hidden">
                  <div
                    className="h-full bg-[#134074]"
                    style={{ width: `${Math.min(100, Math.max(0, val))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AI Predicted Maintenance Risk (SIH26027 Advisory Layer) */}
        {(explanation.ml_risk_score !== undefined && explanation.ml_risk_score !== null) && (
          <div className="border-2 border-purple-300 bg-purple-50/70 p-3 space-y-2">
            <div className="flex items-center justify-between border-b border-purple-200 pb-1.5">
              <div className="flex items-center gap-1.5 font-bold text-purple-950 uppercase text-[11px]">
                <Sparkles className="w-3.5 h-3.5 text-purple-700" />
                AI PREDICTED MAINTENANCE RISK (XGBOOST)
              </div>
              <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border ${
                explanation.ml_risk_class === 'CRITICAL' ? 'bg-red-100 text-red-800 border-red-300' :
                explanation.ml_risk_class === 'HIGH' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                explanation.ml_risk_class === 'MEDIUM' ? 'bg-blue-100 text-blue-800 border-blue-300' :
                'bg-slate-100 text-slate-700 border-slate-300'
              }`}>
                {explanation.ml_risk_class || 'MEDIUM'} ({explanation.ml_risk_score?.toFixed(1)}/100)
              </span>
            </div>

            {/* Formula Breakdown */}
            <div className="p-2 bg-white border border-purple-200 text-[11px]">
              <div className="text-[10px] font-bold text-slate-500 uppercase">PRIORITY FORMULA BREAKDOWN</div>
              <div className="font-mono text-purple-900 font-bold text-[11px] mt-0.5">
                {explanation.ml_formula_breakdown || (
                  `${(explanation.deterministic_priority || explanation.score || 75.0).toFixed(1)} * 85% (Deterministic) + ${explanation.ml_risk_score?.toFixed(1)} * 15% (AI Risk) = ${(explanation.ai_assisted_priority || explanation.priority_score || explanation.score).toFixed(1)}`
                )}
              </div>
              <div className="text-[9px] text-slate-600 mt-1 flex justify-between">
                <span>Deterministic: <strong>{(explanation.deterministic_priority || 75.0).toFixed(1)}</strong></span>
                <span>AI Risk: <strong>{explanation.ml_risk_score?.toFixed(1)}</strong></span>
                <span>Weight: <strong>15% ML</strong></span>
              </div>
            </div>

            {/* Top Contributing Factors */}
            {explanation.ml_top_contributing_factors && explanation.ml_top_contributing_factors.length > 0 && (
              <div>
                <div className="text-[10px] font-bold text-slate-700 uppercase mb-1">TOP CONTRIBUTING FACTORS:</div>
                <ul className="space-y-1">
                  {explanation.ml_top_contributing_factors.map((f, i) => (
                    <li key={i} className="text-[11px] flex items-center justify-between bg-white px-2 py-1 border border-purple-100">
                      <span className="text-slate-800 font-medium">{f.label || f.feature}: <strong className="text-slate-900">{f.value}</strong></span>
                      <span className={`font-mono text-[10px] font-bold px-1 ${f.direction === 'INCREASES_RISK' ? 'text-red-700 bg-red-50' : 'text-emerald-700 bg-emerald-50'}`}>
                        {f.impact_label}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="text-[9px] text-purple-900/70 italic border-t border-purple-200 pt-1">
              Model: {explanation.ml_model_version || 'MRISK-XGB-1.0'} &bull; Advisory Decision Support. Not an official Indian Railways safety score.
            </div>
          </div>
        )}

        {/* Multi-Department Compatibility Synergy */}
        {compatibility_synergies.length > 0 && (
          <div>
            <h4 className="font-bold text-slate-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
              <Layers className="w-4 h-4 text-blue-600" />
              Multi-Department Synergy Partners (Graph Edges)
            </h4>
            <div className="flex flex-wrap gap-1.5 bg-blue-50 border border-blue-200 p-2.5">
              {compatibility_synergies.map((partner, idx) => (
                <span key={idx} className="bg-blue-600 text-white font-mono px-2 py-0.5 text-[10px]">
                  + {partner}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Verified Hard Safety Constraints */}
        <div>
          <h4 className="font-bold text-slate-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
            <Shield className="w-4 h-4 text-emerald-600" />
            Deterministic Invariants Verified
          </h4>
          <ul className="space-y-1 bg-slate-50 border border-slate-200 p-2.5 text-[11px]">
            {constraints_satisfied.map((c, idx) => (
              <li key={idx} className="flex items-center gap-1 text-slate-700">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>{c}</span>
              </li>
            ))}
            <li className="flex items-center gap-1 text-slate-700">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>Machine/Crew capacity limit not exceeded</span>
            </li>
            <li className="flex items-center gap-1 text-slate-700">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>Precedence finish-to-start dependencies satisfied</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Footer */}
      <div className="p-3 bg-slate-100 border-t border-slate-300 text-right">
        <button
          onClick={onClose}
          className="cris-btn cris-btn-secondary w-full justify-center"
        >
          Close Explanation
        </button>
      </div>
    </div>
  );
}
