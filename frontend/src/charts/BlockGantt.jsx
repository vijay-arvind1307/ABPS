import React, { useMemo } from 'react';
import { Layers, Clock, AlertTriangle, CheckCircle2, ChevronRight } from 'lucide-react';

export default function BlockGantt({
  planJobs = [],
  sections = [],
  timeRange = { start_min: 360, end_min: 1320 },
  onSelectJob = null,
  selectedJobId = null,
  conflictsCount = 0
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
    const code = (deptCode || '').toUpperCase();
    switch (code) {
      case 'ENGG':
        return {
          bg: 'bg-amber-600 hover:bg-amber-500 text-white border-amber-400',
          label: 'Engineering'
        };
      case 'SNT':
        return {
          bg: 'bg-teal-600 hover:bg-teal-500 text-white border-teal-400',
          label: 'S&T'
        };
      case 'TRD':
        return {
          bg: 'bg-blue-600 hover:bg-blue-500 text-white border-blue-400',
          label: 'TRD'
        };
      default:
        return {
          bg: 'bg-slate-700 hover:bg-slate-600 text-white border-slate-500',
          label: deptCode || 'MAINT'
        };
    }
  };

  const scheduledJobs = useMemo(() => {
    return planJobs.filter((pj) => pj.is_scheduled && pj.scheduled_start_min !== null);
  }, [planJobs]);

  const activeCount = scheduledJobs.filter(pj => pj.approval_status === 'APPROVED' || pj.status === 'ACTIVE').length;
  const proposedCount = scheduledJobs.length > 0 ? scheduledJobs.filter(pj => pj.approval_status !== 'APPROVED').length : 0;

  // Time grid markers every 1 hour (matching chart 06 to 22)
  const timeHours = useMemo(() => {
    const hours = [];
    for (let m = START_MIN; m <= END_MIN; m += 60) {
      const hh = Math.floor(m / 60) % 24;
      hours.push({
        min: m,
        hourNum: hh.toString().padStart(2, '0')
      });
    }
    return hours;
  }, [START_MIN, END_MIN]);

  // Clean deduplicated section label
  const formatSectionHeader = (sec) => {
    let rawCode = sec.section_id || `SEC-${sec.id}`;
    let rawName = sec.name || '';
    // Strip duplicated "SECTION-XXX SECTION-XXX"
    rawName = rawName.replace(new RegExp(`^${rawCode}\\s*`, 'i'), '').trim();
    if (rawName.startsWith('SECTION-')) {
      rawName = rawName.replace(/^SECTION-\d+\s*/i, '').trim();
    }
    return {
      code: rawCode.replace('SECTION-', 'SEC-'),
      name: rawName || `${sec.start_station_code || 'MDU'} – ${sec.end_station_code || 'TEN'}`
    };
  };

  return (
    <div className="border border-slate-700/80 bg-[#090E1A] shadow-lg flex flex-col font-sans select-none rounded-none">
      {/* ── HEADER & OPERATIONAL METRICS ─────────────────────── */}
      <div className="bg-[#0B1322] px-4 py-2 border-b border-slate-700/80 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-2">
          <Layers className="w-4 h-4 text-amber-400" />
          <span className="font-mono font-bold text-slate-200 uppercase tracking-wider text-[11px]">
            COORDINATED MAINTENANCE BLOCKS (SYNCHRONIZED OCCUPANCY)
          </span>
        </div>

        {/* Operational Metrics Chips */}
        <div className="flex items-center space-x-2 text-[10.5px] font-mono">
          <span className="bg-[#121D30] px-2.5 py-1 border border-slate-700 text-slate-300">
            ACTIVE: <strong className="text-emerald-400 font-bold">{activeCount}</strong>
          </span>
          <span className="bg-[#121D30] px-2.5 py-1 border border-slate-700 text-slate-300">
            PROPOSED: <strong className="text-amber-400 font-bold">{proposedCount}</strong>
          </span>
          <span className={`px-2.5 py-1 border font-bold ${conflictsCount > 0 ? 'bg-rose-950/80 text-rose-300 border-rose-600 animate-pulse' : 'bg-[#121D30] text-slate-300 border-slate-700'}`}>
            CONFLICTS: <strong className={conflictsCount > 0 ? 'text-rose-200' : 'text-slate-300'}>{conflictsCount}</strong>
          </span>
        </div>

        {/* Department Colors Legend */}
        <div className="flex items-center space-x-3 text-[10px] font-mono">
          <span className="text-slate-500 font-bold uppercase">DEPT:</span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-amber-600 inline-block"></span>
            <span className="text-slate-300">Engineering</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-teal-600 inline-block"></span>
            <span className="text-slate-300">S&T</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 bg-blue-600 inline-block"></span>
            <span className="text-slate-300">TRD</span>
          </span>
        </div>
      </div>

      {/* ── TIME AXIS RULER ─────────────────────────────────── */}
      <div className="relative h-6 bg-[#070D18] text-slate-400 border-b border-slate-800 px-2 flex items-center select-none shrink-0">
        <span className="text-[9.5px] font-mono text-slate-400 font-bold uppercase tracking-wide w-[140px] shrink-0 pl-1">
          CORRIDOR SECTION
        </span>
        <div className="relative flex-1 h-full">
          {timeHours.map((th) => (
            <div
              key={th.min}
              className="absolute top-0 bottom-0 border-l border-slate-700/60 flex items-center pl-1"
              style={{ left: `${timeToPct(th.min)}%` }}
            >
              <span className="text-[9.5px] font-mono text-slate-400 font-bold">{th.hourNum}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── SECTIONS & GANTT CONTENT ────────────────────────── */}
      <div className="p-2 bg-[#060A13] space-y-1.5 max-h-[280px] overflow-y-auto">
        {sections.length === 0 ? (
          <div className="text-center py-5 text-slate-500 italic text-xs font-mono">
            No corridor sections loaded
          </div>
        ) : (
          sections.map((sec) => {
            const secInfo = formatSectionHeader(sec);
            const secJobs = scheduledJobs.filter(
              (pj) =>
                ((pj.job && pj.job.section_id === sec.id) || pj.section_id === sec.id)
            );

            return (
              <div key={sec.id} className="border border-slate-800 bg-[#090F1C]">
                {/* Section Header */}
                <div className="flex items-center justify-between px-2.5 py-1 bg-[#0D1526] border-b border-slate-800/80 text-[10px] font-mono">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-cyan-400">{secInfo.code}</span>
                    <span className="text-slate-300 font-sans font-medium">{secInfo.name}</span>
                    {sec.length_km && <span className="text-[9px] text-slate-500">({sec.length_km} km)</span>}
                  </div>
                  <span className={`px-2 py-0.2 ${secJobs.length > 0 ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/60 font-bold' : 'text-slate-600'}`}>
                    {secJobs.length} {secJobs.length === 1 ? 'Job' : 'Jobs'} Scheduled
                  </span>
                </div>

                {/* Timeline Bar Container */}
                <div className="relative h-9 bg-[#060A13] select-none overflow-hidden">
                  {/* Vertical hour guidelines */}
                  {timeHours.map((th) => (
                    <div
                      key={th.min}
                      className="absolute top-0 bottom-0 border-l border-slate-800/60 pointer-events-none"
                      style={{ left: `${timeToPct(th.min)}%` }}
                    />
                  ))}

                  {secJobs.length === 0 ? (
                    <div className="text-[9px] text-slate-600 italic px-3 py-2 font-mono">
                      No blocks on this section
                    </div>
                  ) : (
                    secJobs.map((pj) => {
                      const jCode = pj.job ? pj.job.job_code : (pj.job_code || `J${pj.job_id}`);
                      const deptCode = pj.job && pj.job.department ? pj.job.department.code : (pj.department_code || 'ENGG');
                      const deptInfo = getDeptBadge(deptCode);
                      const left = timeToPct(pj.scheduled_start_min);
                      const right = timeToPct(pj.scheduled_end_min);
                      const width = Math.max(2.4, right - left);
                      const isSel = selectedJobId === pj.job_id;

                      const startH = Math.floor(pj.scheduled_start_min / 60).toString().padStart(2, '0');
                      const startM = (pj.scheduled_start_min % 60).toString().padStart(2, '0');
                      const endH = Math.floor(pj.scheduled_end_min / 60).toString().padStart(2, '0');
                      const endM = (pj.scheduled_end_min % 60).toString().padStart(2, '0');

                      return (
                        <div
                          key={`gantt-${pj.id || pj.job_id}-${pj.block_code}`}
                          onClick={() => onSelectJob && onSelectJob(pj.job_id)}
                          className={`absolute top-0.5 bottom-0.5 px-2 py-0.5 border text-[9px] font-bold rounded-2xs cursor-pointer transition-all flex flex-col justify-center shadow-md ${
                            deptInfo.bg
                          } ${isSel ? 'ring-2 ring-cyan-300 ring-offset-1 ring-offset-[#060A13] z-20 scale-[1.02] shadow-lg' : 'opacity-95 hover:brightness-110'}`}
                          style={{ left: `${left}%`, width: `${width}%` }}
                          title={`${pj.block_code || 'BP-001'} | ${jCode} [${deptCode}] ${startH}:${startM} - ${endH}:${endM} (${pj.scheduled_duration_min || 90}m)`}
                        >
                          <div className="flex items-center justify-between leading-none font-mono">
                            <span className="truncate">{pj.block_code || 'BP-001'}</span>
                            <span className="text-[8px] font-mono ml-1 shrink-0">{pj.scheduled_duration_min || 90}m</span>
                          </div>
                          <div className="text-[7.5px] truncate font-mono opacity-90 leading-none mt-0.5">
                            {startH}:{startM}–{endH}:{endM}
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
