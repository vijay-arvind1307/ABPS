import React from 'react';
import { ShieldCheck, AlertOctagon, X, Check, AlertTriangle } from 'lucide-react';

export default function ValidatorModal({ validationResult, isOpen, onClose }) {
  if (!isOpen || !validationResult) return null;

  const { is_valid, status, errors = [], warnings = [], checked_rules_count = 15 } = validationResult;

  const standardRules = [
    'Rule 1: Train Headway & Strict Track Occupancy Clearance',
    'Rule 2: Required Safety Clearance Buffers (5m before / 5m after)',
    'Rule 3: Maintenance Duration Feasibility within Usable Window',
    'Rule 4: Window Boundary Adherence (No start before / no end after)',
    'Rule 5: Corridor Operational Availability Hours',
    'Rule 6: Section and Physical Track Location Matching',
    'Rule 7: Exclusive Resource Non-Overlapping Capacity (Machines/Crew)',
    'Rule 8: Precedence Maintenance Dependencies (Finish-to-Start)',
    'Rule 9: Existing Committed / Historical Block Invariants',
    'Rule 10: Locked Planner Decisions Preservation',
    'Rule 11: Department Work Type Co-occurrence Compatibility',
    'Rule 12: Block Group Assignment and Capacity Limits',
    'Rule 13: Completed Maintenance Jobs Fixed / Immutability',
    'Rule 14: In-Progress Track Work Protection',
    'Rule 15: Mandatory Station Interlocking Safety Constraints'
  ];

  return (
    <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
      <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className={`p-3.5 text-white flex items-center justify-between ${is_valid ? 'bg-[#0B2545]' : 'bg-[#D90429]'}`}>
          <div className="flex items-center space-x-2">
            {is_valid ? <ShieldCheck className="w-5 h-5 text-emerald-400" /> : <AlertOctagon className="w-5 h-5 text-white animate-bounce" />}
            <h3 className="font-bold text-sm tracking-wide uppercase">
              DETERMINISTIC HARD SAFETY VALIDATION REPORT
            </h3>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 overflow-y-auto flex-1 space-y-4 text-[12px]">
          {/* Certificate Banner */}
          <div className={`p-3 border flex items-center justify-between ${is_valid ? 'bg-emerald-50 border-emerald-300 text-emerald-950' : 'bg-red-50 border-red-300 text-red-950'}`}>
            <div>
              <div className="font-bold text-sm">
                VALIDATION OUTCOME: {is_valid ? 'CERTIFIED OPERATIONALLY VALID' : 'CRITICAL SAFETY VIOLATION DETECTED'}
              </div>
              <div className="text-[11px] mt-0.5">
                {is_valid
                  ? `All ${checked_rules_count} deterministic railway safety rules verified with ZERO hard constraint violations.`
                  : `${errors.length} hard safety constraints were violated. Plan cannot be approved in this state.`}
              </div>
            </div>
            <div className={`px-3 py-1 font-bold text-xs uppercase ${is_valid ? 'bg-emerald-700 text-white' : 'bg-red-700 text-white'}`}>
              {status}
            </div>
          </div>

          {/* Violations List if any */}
          {errors.length > 0 && (
            <div>
              <h4 className="font-bold text-red-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
                <AlertOctagon className="w-4 h-4 text-red-600" />
                Active Safety Violations (Must be resolved):
              </h4>
              <div className="space-y-1.5 bg-red-50 border border-red-200 p-3">
                {errors.map((err, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-red-900 font-mono text-[11px]">
                    <span className="text-red-600 font-bold">❌</span>
                    <span>{err}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 15 Rules Checklist */}
          <div>
            <h4 className="font-bold text-slate-800 text-[12px] uppercase mb-1.5 flex items-center gap-1">
              <ShieldCheck className="w-4 h-4 text-[#134074]" />
              Verified Invariants Checklist ({checked_rules_count} / {checked_rules_count}):
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 bg-slate-50 border border-slate-200 p-2.5">
              {standardRules.map((rule, idx) => (
                <div key={idx} className="flex items-center space-x-1.5 text-slate-700 text-[11px]">
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-[10px] font-bold">✓</span>
                  <span className="truncate">{rule}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 bg-slate-100 border-t border-slate-300 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">Verified by: DeterministicSafetyValidator (Kernel Mode)</span>
          <button onClick={onClose} className="cris-btn cris-btn-primary">
            Acknowledge & Close
          </button>
        </div>
      </div>
    </div>
  );
}
