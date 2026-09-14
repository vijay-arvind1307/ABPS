import React from 'react';
import { Layers, CheckCircle2, Clock, Info } from 'lucide-react';

export default function BlockGantt({
  planJobs = [],
  sections = [],
  timeRange = { start_min: 360, end_min: 1320 },
  onSelectJob,
  selectedJobId
}) {
  const START_MIN = timeRange.start_min || 360; // 06:00
  const END_MIN = timeRange.end_min || 1320;   // 22:00
  const TOTAL_MIN = Math.max(1, END_MIN - START_MIN);

  const timeToPct = (min) => {
    if (min === null || min === undefined) return 0;
    const clamped = Math.max(START_MIN, Math.min(END_MIN, min));
    return ((clamped - START_MIN) / TOTAL_MIN) * 100;
  };

  const getDeptBadge = (deptCode) => {
    switch (deptCode) {
      case 'ENGG':
        return { bg: 'bg-amber-600 hover:bg-amber-500 text-white border-amber-800', label: 'ENGG (Track)' };
      case 'SNT':
        return { bg: 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-800', label: 'S&T (Signals)' };
      case 'TRD':
        return { bg: 'bg-blue-600 hover:bg-blue-500 text-white border-blue-800', label: 'TRD (OHE)' };
      default:
        return { bg: 'bg-slate-600 hover:bg-slate-500 text-white border-slate-800', label: deptCode || 'MAINT' };
    }
  };

  const scheduledJobsCount = planJobs.filter((pj) => pj.is_scheduled && pj.scheduled_start_min !== null).length;

  // Time grid markers every 2 hours
  const timeHours = [];
  for (let m = START_MIN; m <= END_MIN; m += 120) {
    const hh = Math.floor(m / 60);
    timeHours.push({ min: m, label: `${hh.toString().padStart(2, '0')}:00` });
  }

  return (
    <div className="cris-panel overflow-hidden border border-slate-300 bg-white">
      {/* Header */}
      <div className="cris-panel-header flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <span>MULTI-DEPARTMENT COORDINATED BLOCK GANTT (SYNCHRONIZED TRACK OCCUPANCY)</span>
          <span className="text-[10px] bg-emerald-100 text-emerald-900 border border-emerald-300 font-mono px-1.5 py-0.2">
            {scheduledJobsCount} Total Maintenance Blocks Active
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[11px] font-normal">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-amber-600 inline-block"></span>
            <span>ENGG (Civil / Track)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-emerald-600 inline-block"></span>
            <span>S&T (Signals / Point)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-blue-600 inline-block"></span>
            <span>TRD (OHE / 25kV)</span>
          </span>
        </div>
      </div>

      {/* Time axis ruler */}
      <div className="relative h-6 bg-slate-900 text-slate-400 border-b border-slate-700 px-2 flex items-center select-none">
        <span className="text-[10px] font-mono text-slate-300 uppercase tracking-wide w-48 shrink-0">
          CORRIDOR SECTION
        </span>
        <div className="relative flex-1 h-full">
          {timeHours.map((th) => (
            <div
              key={th.min}
              className="absolute top-0 bottom-0 border-l border-slate-700 flex items-center pl-1"
              style={{ left: `${timeToPct(th.min)}%` }}
            >
              <span className="text-[9px] font-mono text-slate-400">{th.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-2 bg-slate-50 space-y-2 max-h-[380px] overflow-y-auto">
        {sections.length === 0 ? (
          <div className="text-center py-8 text-slate-400 italic text-xs font-mono">
            Loading corridor section infrastructure...
          </div>
        ) : scheduledJobsCount === 0 ? (
          <div className="text-center py-8 text-slate-500 space-y-2 bg-white border border-slate-300 p-4">
            <Clock className="w-6 h-6 text-slate-400 mx-auto" />
            <div className="font-bold text-xs text-slate-700 uppercase">
              No maintenance blocks generated
            </div>
            <p className="text-[11px] text-slate-500">
              Maintenance blocks appear here once the planning engine optimizes and schedules authorized department demands.
            </p>
          </div>
        ) : (
          sections.map((sec) => {
            const secJobs = planJobs.filter(
              (pj) =>
                pj.is_scheduled &&
                pj.scheduled_start_min !== null &&
                ((pj.job && pj.job.section_id === sec.id) || pj.section_id === sec.id)
            );

            return (
              <div key={sec.id} className="border border-slate-300 bg-white shadow-xs">
                <div className="flex items-center justify-between px-2 py-1 bg-slate-100/90 border-b border-slate-200 text-[11px] font-bold text-slate-800">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-[#0B2545]">{sec.section_id || `SEC-${sec.id}`}</span>
                    <span className="text-slate-700 font-semibold">{sec.name}</span>
                    <span className="text-[10px] text-slate-500 font-mono">({sec.length_km} km)</span>
                  </div>
                  <span className={`text-[10px] font-mono px-1.5 py-0.2 ${secJobs.length > 0 ? 'bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold' : 'text-slate-400'}`}>
                    {secJobs.length} {secJobs.length === 1 ? 'Job' : 'Jobs'} Scheduled
                  </span>
                </div>

                {/* Timeline Bar Container */}
                <div className="relative h-11 bg-slate-100 border-t border-slate-200 select-none overflow-hidden">
                  {/* Hourly subtle divider lines */}
                  {timeHours.map((th) => (
                    <div
                      key={th.min}
                      className="absolute top-0 bottom-0 border-l border-slate-300/80 pointer-events-none"
                      style={{ left: `${timeToPct(th.min)}%` }}
                    />
                  ))}

                  {secJobs.length === 0 ? (
                    <div className="text-[10px] text-slate-400 italic px-3 py-2.5 font-mono">
                      No maintenance blocks allocated on this section
                    </div>
                  ) : (
                    secJobs.map((pj) => {
                      const jCode = pj.job ? pj.job.job_code : `J${pj.job_id}`;
                      const deptCode = pj.job && pj.job.department ? pj.job.department.code : (pj.department_code || 'ENGG');
                      const deptInfo = getDeptBadge(deptCode);
                      const left = timeToPct(pj.scheduled_start_min);
                      const right = timeToPct(pj.scheduled_end_min);
                      const width = Math.max(2.2, right - left);
                      const isSel = selectedJobId === pj.job_id;

                      const startH = Math.floor(pj.scheduled_start_min / 60).toString().padStart(2, '0');
                      const startM = (pj.scheduled_start_min % 60).toString().padStart(2, '0');
                      const endH = Math.floor(pj.scheduled_end_min / 60).toString().padStart(2, '0');
                      const endM = (pj.scheduled_end_min % 60).toString().padStart(2, '0');

                      return (
                        <div
                          key={`gantt-${pj.id || pj.job_id}-${pj.block_code}`}
                          onClick={() => onSelectJob && onSelectJob(pj.job_id)}
                          className={`absolute top-1 bottom-1 px-1.5 py-0.5 border text-[10px] font-bold rounded-none cursor-pointer transition-all flex flex-col justify-center shadow ${
                            deptInfo.bg
                          } ${isSel ? 'ring-2 ring-amber-400 z-20 scale-[1.03] shadow-md' : 'opacity-95'}`}
                          style={{ left: `${left}%`, width: `${width}%` }}
                          title={`${jCode} [${deptCode}] ${startH}:${startM} - ${endH}:${endM} (${pj.scheduled_duration_min}m) ${pj.block_code || ''}`}
                        >
                          <div className="flex items-center justify-between leading-none truncate font-mono">
                            <span className="truncate">{jCode}</span>
                            <span className="text-[8px] font-mono ml-1 shrink-0">{pj.scheduled_duration_min}m</span>
                          </div>
                          <div className="text-[8px] truncate font-mono opacity-90 leading-none mt-0.5">
                            {pj.block_code || 'BLOCK'}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
