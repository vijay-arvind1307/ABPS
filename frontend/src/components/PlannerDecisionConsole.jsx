import React from 'react';
import {
  Play, ShieldCheck, CheckCircle, XCircle, Edit3,
  FileSpreadsheet, FileText, Cpu, AlertTriangle, Users,
  Sparkles, Check, ArrowRight, ShieldAlert, History
} from 'lucide-react';

export default function PlannerDecisionConsole({
  activePlan,
  optimizing,
  onGeneratePlan,
  onValidatePlan,
  onApprovePlan,
  onRejectPlan,
  onModifyPlan,
  onExportCsv,
  onViewAudit,
  selectedPlan,
  validationResult
}) {
  const plan = selectedPlan || activePlan || {
    id: 101,
    plan_code: 'BP-001',
    version: 1,
    strategy: 'PLAN_A',
    corridor: 'C40 · Madurai → Tirunelveli',
    section: 'CVP–KDU (Kovilpatti – Kadambur)',
    common_block_window: '10:00 – 11:30 IST',
    duration_min: 90,
    departments: ['Engineering', 'S&T', 'TRD'],
    request_ids: ['REQ-101', 'REQ-102', 'REQ-103'],
    approval_status: 'PROPOSED'
  };

  const isApproved = plan.approval_status === 'APPROVED';
  const isRejected = plan.approval_status === 'REJECTED';

  return (
    <div className="bg-[#0B1424] border-t-2 border-[#FFB703] py-2 px-4 text-slate-100 font-mono shadow-2xl flex flex-wrap items-center justify-between gap-2 shrink-0 z-20">
      {/* ── Left: Plan Identification & Details ───────────────── */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Plan Code & Strategy */}
        <div className="flex items-center space-x-2">
          <div className="bg-[#13223A] border border-blue-500/60 px-2 py-1 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-xs font-black text-white">{plan.plan_code || 'BP-001'}</span>
            <span className="text-[10px] text-slate-400">(V{plan.version || 1})</span>
          </div>

          <span className={`px-2 py-0.5 text-[10px] font-black uppercase rounded-xs border ${
            isApproved
              ? 'bg-emerald-950 text-emerald-300 border-emerald-500'
              : isRejected
                ? 'bg-red-950 text-red-300 border-red-500'
                : 'bg-amber-950 text-amber-300 border-amber-500 animate-pulse'
          }`}>
            {plan.approval_status || 'PROPOSED'}
          </span>
        </div>

        {/* Section Span & Window */}
        <div className="hidden sm:flex items-center space-x-2 text-xs text-slate-300">
          <span className="text-slate-500">SECTION:</span>
          <span className="font-bold text-white bg-slate-900 px-1.5 py-0.5 border border-slate-700">
            {plan.section || 'CVP–KDU (Kovilpatti – Kadambur)'}
          </span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-500">WINDOW:</span>
          <span className="font-black text-emerald-400 font-mono">
            {plan.common_block_window || '10:00 – 11:30'} ({plan.duration_min || 90} MIN)
          </span>
        </div>

        {/* Coordinated Departments Badges */}
        <div className="hidden md:flex items-center space-x-1">
          <span className="text-[9px] text-slate-500 font-bold uppercase mr-1">COMBINED:</span>
          <span className="bg-amber-950/80 text-amber-300 border border-amber-600 px-1.5 py-0.5 text-[9px] font-black">
            ENGG
          </span>
          <span className="bg-cyan-950/80 text-cyan-300 border border-cyan-600 px-1.5 py-0.5 text-[9px] font-black">
            S&T
          </span>
          <span className="bg-purple-950/80 text-purple-300 border border-purple-600 px-1.5 py-0.5 text-[9px] font-black">
            TRD
          </span>
        </div>
      </div>

      {/* ── Right: Controller Action Buttons ──────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Re-Optimize via CP-SAT */}
        <button
          onClick={onGeneratePlan}
          disabled={optimizing}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900/60 text-white font-mono font-bold text-xs border border-blue-400 flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
        >
          <Play className="w-3 h-3 fill-current text-emerald-400" />
          {optimizing ? 'SOLVING VIA CP-SAT...' : 'RE-OPTIMIZE'}
        </button>

        {/* Safety Validation */}
        <button
          onClick={onValidatePlan}
          className="px-2.5 py-1 bg-[#16253D] hover:bg-[#1E3354] text-slate-200 font-mono font-bold text-xs border border-slate-600 flex items-center gap-1 transition-colors cursor-pointer"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
          <span>SAFETY CHECK</span>
        </button>

        {/* Modify Schedule */}
        <button
          onClick={() => onModifyPlan && onModifyPlan(plan)}
          className="px-2.5 py-1 bg-[#16253D] hover:bg-[#1E3354] text-slate-200 font-mono font-bold text-xs border border-slate-600 flex items-center gap-1 transition-colors cursor-pointer"
        >
          <Edit3 className="w-3.5 h-3.5 text-amber-400" />
          <span>MODIFY</span>
        </button>

        {/* Reject Block */}
        {!isApproved && (
          <button
            onClick={() => onRejectPlan && onRejectPlan(plan)}
            className="px-2.5 py-1 bg-red-950 hover:bg-red-900 text-red-200 font-mono font-bold text-xs border border-red-600 flex items-center gap-1 transition-colors cursor-pointer"
          >
            <XCircle className="w-3.5 h-3.5 text-red-400" />
            <span>REJECT</span>
          </button>
        )}

        {/* Formally Approve Track Possession */}
        {!isApproved && (
          <button
            onClick={() => onApprovePlan && onApprovePlan(plan)}
            className="px-3.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-mono font-black text-xs border border-emerald-400 flex items-center gap-1.5 transition-all shadow-md cursor-pointer"
          >
            <CheckCircle className="w-4 h-4 fill-slate-950 text-emerald-300" />
            <span>FORMALLY APPROVE BLOCK</span>
          </button>
        )}

        {/* Export CSV Report */}
        {onExportCsv && (
          <button
            onClick={onExportCsv}
            className="px-2 py-1 bg-[#16253D] hover:bg-[#1E3354] text-emerald-300 font-mono text-xs border border-slate-600 flex items-center gap-1 transition-colors cursor-pointer"
            title="Export Plan to CSV"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
          </button>
        )}
      </div>
    </div>
  );
}
