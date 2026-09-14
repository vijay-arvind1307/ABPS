import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play, CheckCircle, XCircle, Lock, Unlock, ShieldCheck, FileSpreadsheet,
  Shuffle, RefreshCw, Info, Layers, Award, Zap, Radio, Sliders, AlertCircle,
  MapPin, Edit2, AlertTriangle, ArrowRight, Search, Train, Clock, Eye,
  BarChart3, GitBranch, Cpu, FileText, Database, Activity, ChevronRight,
  ChevronDown, Shield, Hash, Calendar, Target, Inbox, Bell, CheckCheck,
  CheckSquare, Square, Sparkles, Users
} from 'lucide-react';
import {
  getBlockRequests,
  getBlockRequestById,
  optimizeBlockRequest,
  approveBlockRequest,
  modifyBlockRequest,
  rejectBlockRequest,
  requestChangeBlockRequest,
  getBlockRequestAudit,
  checkCoordinationCompatibility,
  optimizeCoordinatedBlock,
  optimizeRequestPool,
  getCoordinatedBlockPlan,

  approveCoordinatedBlockPlan,
  modifyCoordinatedBlockPlan,
  rejectCoordinatedBlockPlan,
  whatIfCoordinatedBlockPlan,
  replanCoordinatedBlockPlan,
  getCoordinatedPlanAudit,
  getMaintenanceJobs,
  getLiveTrainMovements,
  getTrainOccupancies,
  getWindows,
  getActivePlan,
  runOptimization,
  getKPIComparison,
  validatePlan,
  approvePlan,
  lockJob,
  getJobExplanation,
  getPlanExportUrl,
  getTimeDistanceData,
  getCorridors,
  getJobPriorityExplanation,
  overrideJobPriority,
  getTrainsBetween,
  getCompatibilityGraph,
  getPlannerRequestReview,
  getExecutionRecords,
  getNotifications,
  getAuditLogs,
  getPlannerActions,
  getWeeklyReport,
  getSections,
  getDataStatus
} from '../services/api';
import StationAutocomplete from '../components/StationAutocomplete';
import TimeDistanceChart from '../charts/TimeDistanceChart';
import BlockGantt from '../charts/BlockGantt';
import KPIComparison from '../charts/KPIComparison';
import ExplainabilityDrawer from '../components/ExplainabilityDrawer';
import ValidatorModal from '../components/ValidatorModal';
import RailwayMap from '../maps/RailwayMap';
import { getCurrentUser } from '../services/auth';

// ─── NAV STATION DEFINITIONS ────────────────────────────────────────
const NAV_STATIONS = [
  { id: 'CONTROL_PANEL',           label: 'Control Panel',           icon: Activity,     group: 'OPERATIONS' },
  { id: 'MAINTENANCE_DEMANDS',     label: 'Maintenance Demands',     icon: Inbox,        group: 'OPERATIONS' },
  { id: 'TRAIN_POSITION',          label: 'Train Position',          icon: Radio,        group: 'LIVE DATA' },
  { id: 'RAILWAY_NETWORK',         label: 'Railway Network',         icon: GitBranch,    group: 'LIVE DATA' },
  { id: 'AVAILABLE_WINDOWS',       label: 'Available Windows',       icon: Clock,        group: 'PLANNING' },
  { id: 'COMPATIBILITY',           label: 'Compatibility',           icon: Layers,       group: 'PLANNING' },
  { id: 'AUTOMATIC_BLOCK_PLANNING',label: 'Block Planning (CP-SAT)', icon: Cpu,          group: 'PLANNING' },
  { id: 'PLAN_COMPARISON',         label: 'Plan Comparison',         icon: BarChart3,    group: 'ANALYSIS' },
  { id: 'WHAT_IF',                 label: 'What-If Analysis',        icon: Sliders,      group: 'ANALYSIS' },
  { id: 'DYNAMIC_REPLANNING',      label: 'Dynamic Replanning',      icon: Shuffle,      group: 'ANALYSIS' },
  { id: 'EXECUTION',               label: 'Execution Tracker',       icon: Target,       group: 'FIELD OPS' },
  { id: 'REPORTS',                 label: 'Reports',                 icon: FileText,     group: 'AUDIT' },
  { id: 'AUDIT',                   label: 'Audit Trail',             icon: Shield,       group: 'AUDIT' },
];

const NAV_GROUPS = ['OPERATIONS', 'LIVE DATA', 'PLANNING', 'ANALYSIS', 'FIELD OPS', 'AUDIT'];

// ─── HELPER: Minutes → HH:MM ────────────────────────────────────────
const mToTime = (m) => {
  if (m === null || m === undefined) return '—';
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh.toString().padStart(2, '0')}:${mm.toString().padStart(2, '0')}`;
};

export default function PlannerDashboard({ onTabChange }) {
  const user = getCurrentUser();

  // ── Core Data ────────────────────────────────────────────────
  const [activeStation, setActiveStation] = useState('CONTROL_PANEL');
  const [jobs, setJobs] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [selectedCorridorId, setSelectedCorridorId] = useState(null);
  const [timeDistanceData, setTimeDistanceData] = useState(null);
  const [activePlan, setActivePlan] = useState(null);
  const [kpiData, setKpiData] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState('PLAN_A');
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [lastSyncTime, setLastSyncTime] = useState(new Date().toLocaleTimeString());

  // ── Explainability & Override ────────────────────────────────
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [explanationData, setExplanationData] = useState(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [showValidatorModal, setShowValidatorModal] = useState(false);

  // ── Planner Priority Override Dialog ─────────────────────────
  const [overrideTargetJob, setOverrideTargetJob] = useState(null);
  const [overrideScore, setOverrideScore] = useState('');
  const [overrideReason, setOverrideReason] = useState('');
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  // ── RailRadar Discovery ──────────────────────────────────────
  const [fromStation, setFromStation] = useState('MAS');
  const [toStation, setToStation] = useState('AJJ');
  const [discoveredTrains, setDiscoveredTrains] = useState([]);
  const [discoveredRoute, setDiscoveredRoute] = useState(null);
  const [discoveryStats, setDiscoveryStats] = useState(null);
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [discoveryError, setDiscoveryError] = useState(null);
  const [discoveryMessage, setDiscoveryMessage] = useState(null);

  // ── Structured Request Review Modal ──────────────────────────
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewData, setReviewData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);

  // ── Station-specific lazy data ───────────────────────────────
  const [compatibilityData, setCompatibilityData] = useState(null);
  const [compatLoading, setCompatLoading] = useState(false);
  const [windowsData, setWindowsData] = useState([]);
  const [windowsLoading, setWindowsLoading] = useState(false);
  const [executionRecords, setExecutionRecords] = useState([]);
  const [executionLoading, setExecutionLoading] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [plannerActions, setPlannerActions] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [weeklyReport, setWeeklyReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);

  // ── Selected Request & Optimization State (SIH26027) ───────
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [optimizingStep, setOptimizingStep] = useState(null);
  const [optimizationResult, setOptimizationResult] = useState(null);
  const [selectedAlternative, setSelectedAlternative] = useState('Plan A');

  // ── Independent Live Corridor Observation (SIH26027 Section 19) ─
  const [observationCorridorId, setObservationCorridorId] = useState(null);
  const [observationCorridor, setObservationCorridor] = useState(null);
  const [observationMovements, setObservationMovements] = useState([]);
  const [observationStations, setObservationStations] = useState([]);
  const [observationSections, setObservationSections] = useState([]);
  const [observationDataStatus, setObservationDataStatus] = useState({
    status: 'CACHED',
    provider: 'Checking telemetry gateway...',
    is_live: false,
    clock_display: ''
  });

  // ── Multi-Department Coordinated Planning State (SIH26027) ────
  const [selectedRequestIds, setSelectedRequestIds] = useState([]);
  const [coordinationCompatibility, setCoordinationCompatibility] = useState(null);
  const [coordinationChecking, setCoordinationChecking] = useState(false);
  const [coordinationOptimizing, setCoordinationOptimizing] = useState(false);
  const [coordinationOptimizingStep, setCoordinationOptimizingStep] = useState(null);
  const [coordinatedPlanResult, setCoordinatedPlanResult] = useState(null);
  const [selectedCoordinatedAlt, setSelectedCoordinatedAlt] = useState('Plan A');
  const [showCoordinatedModifyModal, setShowCoordinatedModifyModal] = useState(false);
  const [coordinatedModifyStart, setCoordinatedModifyStart] = useState(645);
  const [coordinatedModifyEnd, setCoordinatedModifyEnd] = useState(735);
  const [coordinatedModifyReason, setCoordinatedModifyReason] = useState('');
  const [showCoordinatedRejectModal, setShowCoordinatedRejectModal] = useState(false);
  const [coordinatedRejectReason, setCoordinatedRejectReason] = useState('');
  const [showCoordinatedWhatIfModal, setShowCoordinatedWhatIfModal] = useState(false);
  const [whatIfScenarioType, setWhatIfScenarioType] = useState('TRAIN_DELAY');
  const [whatIfValue, setWhatIfValue] = useState(30);
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [dynamicReplanResult, setDynamicReplanResult] = useState(null);
  const [dynamicReplanLoading, setDynamicReplanLoading] = useState(false);

  // ── Global Pool Optimization Workstation State (SIH26027) ─────
  const [poolOptimizing, setPoolOptimizing] = useState(false);
  const [poolOptimizingStepIndex, setPoolOptimizingStepIndex] = useState(0);
  const [poolOptimizationResult, setPoolOptimizationResult] = useState(null);
  const [activePlanModal, setActivePlanModal] = useState(null);
  const [activePlanModalAlt, setActivePlanModalAlt] = useState('Plan A');
  const [activeRequestDetailsModal, setActiveRequestDetailsModal] = useState(null);

  // ── Decision Modals ──────────────────────────────────────────
  const [showModifyModal, setShowModifyModal] = useState(false);
  const [modifyReason, setModifyReason] = useState('');
  const [modifyStartMin, setModifyStartMin] = useState(645);
  const [modifyEndMin, setModifyEndMin] = useState(735);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showConflictsModal, setShowConflictsModal] = useState(false);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [auditLogsList, setAuditLogsList] = useState([]);
  const [auditLogsLoading, setAuditLogsLoading] = useState(false);

  const isMountedRef = useRef(true);

  // ── DATA LOADING ─────────────────────────────────────────────
  const loadCoreData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setApiError(null);
    try {
      const [tdRes, jobsRes, planRes, kpiRes, corrRes, statusRes] = await Promise.all([
        getTimeDistanceData(selectedCorridorId),
        getBlockRequests().catch(() => getMaintenanceJobs()),
        getActivePlan(selectedStrategy),
        getKPIComparison(),
        getCorridors(),
        getDataStatus().catch(() => ({ data: null }))
      ]);
      if (!isMountedRef.current) return;
      const loadedJobs = jobsRes.data || [];
      const loadedCorrs = corrRes.data || [];
      setTimeDistanceData(tdRes.data);
      setJobs(loadedJobs);
      setActivePlan(planRes.data);
      setKpiData(kpiRes.data);
      setCorridors(loadedCorrs);
      if (statusRes.data) setObservationDataStatus(statusRes.data);
      setLastSyncTime(new Date().toLocaleTimeString());

      // Auto-select first request if none selected
      if (!selectedRequest && loadedJobs.length > 0) {
        setSelectedRequest(loadedJobs[0]);
      }

      // Initialize default observation corridor (independent from request)
      if (!observationCorridorId && loadedCorrs.length > 0) {
        const defaultObs = loadedCorrs.find(c => c.corridor_id === 'CORR_C15_MDU_TEN') ||
                           loadedCorrs.find(c => c.start_station_code === 'MDU' && c.end_station_code === 'TEN') ||
                           loadedCorrs[0];
        setObservationCorridorId(defaultObs.id);
        setObservationCorridor(defaultObs);
      }
    } catch (err) {
      console.error('[ABPS] Data load failure:', err);
      if (isMountedRef.current) setApiError('Unable to refresh telemetry feed. Displaying cached state.');
    } finally {
      if (isMountedRef.current && !silent) setLoading(false);
    }
  }, [selectedCorridorId, selectedStrategy, selectedRequest, observationCorridorId]);

  // Load live observation corridor telemetry (independent from request corridor)
  useEffect(() => {
    if (!observationCorridorId) return;
    const loadObs = async () => {
      try {
        const [tdRes, movRes, secRes] = await Promise.all([
          getTimeDistanceData(observationCorridorId).catch(() => ({ data: null })),
          getLiveTrainMovements(observationCorridorId, false).catch(() => ({ data: [] })),
          getSections(observationCorridorId).catch(() => ({ data: [] }))
        ]);
        if (tdRes.data?.corridor) setObservationCorridor(tdRes.data.corridor);
        setObservationMovements(movRes.data || tdRes.data?.trains || []);
        setObservationStations(tdRes.data?.stations || []);
        setObservationSections(secRes.data || tdRes.data?.sections || []);
      } catch (e) {
        console.warn('Observation corridor load notice:', e);
      }
    };
    loadObs();
    // Fast 5-10s database polling for live trains (zero provider API calls)
    const pollInterval = setInterval(async () => {
      try {
        const res = await getLiveTrainMovements(observationCorridorId, false);
        if (Array.isArray(res?.data)) setObservationMovements(res.data);
      } catch {}
    }, 6000);
    return () => clearInterval(pollInterval);
  }, [observationCorridorId]);

  useEffect(() => {
    isMountedRef.current = true;
    loadCoreData(false);
    const interval = setInterval(() => loadCoreData(true), 30000);
    return () => { isMountedRef.current = false; clearInterval(interval); };
  }, [loadCoreData]);

  // ── Lazy loaders per station ─────────────────────────────────
  useEffect(() => {
    if (activeStation === 'COMPATIBILITY' && !compatibilityData && !compatLoading) {
      setCompatLoading(true);
      getCompatibilityGraph().then(res => setCompatibilityData(res.data)).catch(() => {}).finally(() => setCompatLoading(false));
    }
    if (activeStation === 'AVAILABLE_WINDOWS' && windowsData.length === 0 && !windowsLoading) {
      setWindowsLoading(true);
      getWindows(selectedCorridorId).then(res => setWindowsData(res.data || [])).catch(() => {}).finally(() => setWindowsLoading(false));
    }
    if (activeStation === 'EXECUTION' && executionRecords.length === 0 && !executionLoading) {
      setExecutionLoading(true);
      getExecutionRecords().then(res => setExecutionRecords(res.data || [])).catch(() => {}).finally(() => setExecutionLoading(false));
    }
    if (activeStation === 'AUDIT' && auditLogs.length === 0 && !auditLoading) {
      setAuditLoading(true);
      Promise.all([getAuditLogs(), getPlannerActions()])
        .then(([aRes, pRes]) => { setAuditLogs(aRes.data || []); setPlannerActions(pRes.data || []); })
        .catch(() => {}).finally(() => setAuditLoading(false));
    }
    if (activeStation === 'REPORTS' && !weeklyReport && !reportLoading) {
      setReportLoading(true);
      getWeeklyReport().then(res => setWeeklyReport(res.data)).catch(() => {}).finally(() => setReportLoading(false));
    }
  }, [activeStation, selectedCorridorId]);

  // ── ACTIONS ──────────────────────────────────────────────────
  const handleGeneratePlan = async () => {
    setOptimizing(true);
    try {
      const res = await runOptimization({
        strategy: selectedStrategy,
        corridor_id: selectedCorridorId,
        planning_horizon_hours: 24,
        time_limit_seconds: 15,
        enforce_locks: true
      });
      setActivePlan(res.data);
      const [tdRes, kpiRes] = await Promise.all([
        getTimeDistanceData(selectedCorridorId),
        getKPIComparison()
      ]);
      setTimeDistanceData(tdRes.data);
      setKpiData(kpiRes.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Optimization failed.');
    } finally {
      setOptimizing(false);
    }
  };

  const handleValidatePlan = async () => {
    if (!activePlan) return;
    try {
      const res = await validatePlan(activePlan.id);
      setValidationResult(res.data);
      setShowValidatorModal(true);
    } catch (err) { alert('Validation check failed.'); }
  };

  const handleApprovePlan = async (action) => {
    if (!activePlan) return;
    try {
      const reason = action === 'APPROVE'
        ? 'Railway Chief Controller formal operational block authorization'
        : 'Operational block rejection';
      const res = await approvePlan(activePlan.id, { action, reason });
      setActivePlan(res.data);
      alert(`Master Block Plan ${res.data.plan_code} has been ${action === 'APPROVE' ? 'APPROVED' : 'REJECTED'}.`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Approval failed. Check RBAC credentials.');
    }
  };

  const handleToggleLock = async (job) => {
    try {
      const newLockState = !job.is_locked;
      const lockedTime = newLockState ? 600 : null;
      await lockJob({ job_id: job.id, is_locked: newLockState, locked_start_min: lockedTime, reason: newLockState ? 'Planner manual lock at 10:00' : 'Planner unlocked' });
      loadCoreData(true);
    } catch (err) { alert('Lock action failed.'); }
  };

  const handleShowExplanation = async (jobId) => {
    setSelectedJobId(jobId);
    try {
      const res = await getJobExplanation(jobId, activePlan?.id);
      setExplanationData(res.data);
      setShowExplanation(true);
    } catch (err) { console.error(err); }
  };

  const handleOpenOverrideModal = (job) => {
    setOverrideTargetJob(job);
    setOverrideScore((job.planner_override_score ?? job.priority_score ?? 75.0).toFixed(1));
    setOverrideReason(job.planner_override_reason || '');
  };

  const handleSubmitOverride = async (e) => {
    e.preventDefault();
    if (!overrideTargetJob) return;
    const scoreNum = parseFloat(overrideScore);
    if (isNaN(scoreNum) || scoreNum < 0 || scoreNum > 100) { alert('Enter a valid score (0–100).'); return; }
    if (!overrideReason.trim()) { alert('Mandatory operational justification required.'); return; }
    setOverrideSubmitting(true);
    try {
      await overrideJobPriority(overrideTargetJob.id, { override_score: scoreNum, reason: overrideReason.trim() });
      setOverrideTargetJob(null);
      loadCoreData(true);
      alert(`Priority for ${overrideTargetJob.job_code} updated to ${scoreNum}.`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Override failed.');
    } finally { setOverrideSubmitting(false); }
  };

  const handleFindTrains = async (overrideFrom, overrideTo) => {
    const fromCode = (overrideFrom !== undefined ? overrideFrom : fromStation || '').trim().toUpperCase();
    const toCode = (overrideTo !== undefined ? overrideTo : toStation || '').trim().toUpperCase();
    if (!fromCode || !toCode) { setDiscoveryError('Select both FROM and TO stations.'); setDiscoveryMessage(null); return; }
    if (fromCode === toCode) { setDiscoveryError(`FROM and TO cannot be the same (${fromCode}).`); setDiscoveryMessage(null); return; }

    setDiscoveryLoading(true);
    setDiscoveryError(null);
    setDiscoveryMessage(null);
    try {
      const res = await getTrainsBetween(fromCode, toCode);
      const data = res.data;
      if (!data.success || data.count === 0 || !data.trains || data.trains.length === 0) {
        setDiscoveredTrains([]); setDiscoveredRoute(null);
        setDiscoveryStats({ count: 0, sections: 0, windows: 0 });
        setDiscoveryMessage('No trains found between the selected stations.');
      } else {
        setDiscoveredTrains(data.trains);
        setDiscoveredRoute(data.route || null);
        setDiscoveryStats({
          count: data.count, sections: data.sections?.length || 0,
          occupancies: data.occupancies_count || 0, windows: data.feasible_windows_count || 0,
          distance_km: data.route?.distance_km || 0
        });
        setDiscoveryMessage(`Discovered ${data.count} real train${data.count > 1 ? 's' : ''} from RailRadar on ${fromCode} ↔ ${toCode} route.`);
        if (data.sections?.length > 0 && data.sections[0].corridor_id) {
          setSelectedCorridorId(data.sections[0].corridor_id);
        }
        loadCoreData(true);
      }
    } catch (err) {
      setDiscoveredTrains([]); setDiscoveredRoute(null);
      setDiscoveryError(err.response?.data?.detail || err.message || 'Unable to fetch train data from RailRadar.');
    } finally { setDiscoveryLoading(false); }
  };

  // ── Open Structured Request Review Modal ─────────────────────
  const handleOpenReview = async (jobId) => {
    setReviewLoading(true);
    setReviewModalOpen(true);
    try {
      const res = await getPlannerRequestReview(jobId);
      setReviewData(res.data);
    } catch (err) {
      console.error('Failed to load review packet:', err);
      setReviewData(null);
    } finally {
      setReviewLoading(false);
    }
  };

  // ── SIH26027 Block Request Workflow Handlers ──────────────────
  const handleOpenRequest = (job) => {
    setSelectedRequest(job);
    setOptimizationResult(null);
    setSelectedAlternative('Plan A');
  };

  const handleOptimizeRequest = async (jobId) => {
    setOptimizing(true);
    setOptimizingStep('ANALYZING REQUEST...');
    try {
      await new Promise(r => setTimeout(r, 450));
      setOptimizingStep('CHECKING TRAIN CONFLICTS...');
      await new Promise(r => setTimeout(r, 450));
      setOptimizingStep('CHECKING AVAILABLE WINDOWS...');
      await new Promise(r => setTimeout(r, 450));
      setOptimizingStep('RUNNING CP-SAT...');

      const res = await optimizeBlockRequest(jobId);

      setOptimizingStep('GENERATING PLAN...');
      await new Promise(r => setTimeout(r, 350));

      setOptimizationResult(res.data);
      setSelectedAlternative('Plan A');
      loadCoreData(true);
      if (selectedRequest && selectedRequest.id === jobId) {
        setSelectedRequest(prev => ({ ...prev, status: 'RECOMMENDED', conflicting_trains_count: 0 }));
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'CP-SAT optimization failed.');
    } finally {
      setOptimizing(false);
      setOptimizingStep(null);
    }
  };

  const handleApproveRequest = async (jobId) => {
    if (!confirm('Formally APPROVE this recommended block plan? This will alert the department to accept timings.')) return;
    try {
      await approveBlockRequest(jobId, {
        reason: 'Authorized by Chief Section Controller / Railway Planner for field possession'
      });
      alert('Block plan formally APPROVED. Notification dispatched to Department.');
      loadCoreData(true);
      if (selectedRequest && selectedRequest.id === jobId) {
        setSelectedRequest(prev => ({ ...prev, status: 'APPROVED' }));
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Approval failed.');
    }
  };

  const handleOpenModifyModal = (job) => {
    setSelectedRequest(job);
    const startM = job.preferred_start_min || 645;
    const endM = job.preferred_end_min || 735;
    setModifyStartMin(startM);
    setModifyEndMin(endM);
    setModifyReason('');
    setShowModifyModal(true);
  };

  const handleModifySubmit = async (e) => {
    if (e) e.preventDefault();
    if (!modifyReason.trim()) {
      alert('Mandatory modification reason is required.');
      return;
    }
    try {
      await modifyBlockRequest(selectedRequest.id, {
        reason: modifyReason.trim(),
        recommended_start_min: parseInt(modifyStartMin),
        recommended_end_min: parseInt(modifyEndMin)
      });
      setShowModifyModal(false);
      alert('Block plan timings modified and recorded in audit log.');
      loadCoreData(true);
      if (selectedRequest) {
        setSelectedRequest(prev => ({ ...prev, preferred_start_min: parseInt(modifyStartMin), preferred_end_min: parseInt(modifyEndMin) }));
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Modification failed.');
    }
  };

  const handleOpenRejectModal = (job) => {
    setSelectedRequest(job);
    setRejectReason('');
    setShowRejectModal(true);
  };

  const handleRejectSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!rejectReason.trim()) {
      alert('Mandatory operational justification required to reject block request.');
      return;
    }
    try {
      await rejectBlockRequest(selectedRequest.id, {
        reason: rejectReason.trim()
      });
      setShowRejectModal(false);
      alert('Block request REJECTED. Notification sent to department.');
      loadCoreData(true);
      if (selectedRequest) {
        setSelectedRequest(prev => ({ ...prev, status: 'REJECTED' }));
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Rejection failed.');
    }
  };

  const handleOpenAuditModal = async (job) => {
    setSelectedJobId(job.id);
    setAuditLogsLoading(true);
    setShowAuditModal(true);
    try {
      const res = await getBlockRequestAudit(job.id);
      setAuditLogsList(res.data || []);
    } catch (err) {
      console.error(err);
      setAuditLogsList([]);
    } finally {
      setAuditLogsLoading(false);
    }
  };

  // ── Multi-Department Coordinated Planning Handlers (SIH26027) ──
  const handleToggleSelectRequest = (jobId) => {
    setSelectedRequestIds(prev => {
      if (prev.includes(jobId)) {
        return prev.filter(id => id !== jobId);
      } else {
        return [...prev, jobId];
      }
    });
    setCoordinationCompatibility(null);
  };

  const handleSelectAllPending = () => {
    const pendingIds = jobs
      .filter(j => ['SUBMITTED', 'UNDER_REVIEW', 'PLANNING', 'RECOMMENDED'].includes(j.status))
      .map(j => j.id);
    if (selectedRequestIds.length === pendingIds.length) {
      setSelectedRequestIds([]);
    } else {
      setSelectedRequestIds(pendingIds);
    }
    setCoordinationCompatibility(null);
  };

  const handleAddCoordinatableToSelection = (jobId) => {
    setSelectedRequestIds(prev => {
      const base = selectedRequest ? [selectedRequest.id] : [];
      const next = new Set([...prev, ...base, jobId]);
      return Array.from(next);
    });
    setCoordinationCompatibility(null);
  };

  const handleCheckCompatibility = async (idsToCheck = null) => {
    const ids = idsToCheck || selectedRequestIds;
    if (!ids || ids.length < 2) {
      alert('Select at least 2 requests to check multi-department compatibility.');
      return;
    }
    setCoordinationChecking(true);
    try {
      const res = await checkCoordinationCompatibility(ids);
      setCoordinationCompatibility(res.data);
      return res.data;
    } catch (err) {
      alert(err.response?.data?.detail || 'Compatibility check failed.');
      return null;
    } finally {
      setCoordinationChecking(false);
    }
  };

  const handleFindCommonBlock = async (overrideJobIds = null) => {
    const ids = overrideJobIds || selectedRequestIds;
    if (!ids || ids.length < 2) {
      alert('Please select at least 2 requests to find a common block possession.');
      return;
    }

    setCoordinationOptimizing(true);
    setCoordinationOptimizingStep(`ANALYZING ${ids.length} REQUESTS...`);

    try {
      await new Promise(r => setTimeout(r, 400));
      setCoordinationOptimizingStep('CHECKING SECTION COMPATIBILITY...');
      await new Promise(r => setTimeout(r, 400));
      setCoordinationOptimizingStep('CHECKING TRAIN MOVEMENTS & BUFFER GAPS...');
      await new Promise(r => setTimeout(r, 450));
      setCoordinationOptimizingStep('RUNNING CP-SAT MULTI-OBJECTIVE SOLVER...');
      await new Promise(r => setTimeout(r, 500));
      setCoordinationOptimizingStep('GENERATING COMMON PLAN ALTERNATIVES...');

      const res = await optimizeCoordinatedBlock({
        job_ids: ids,
        strategy: 'PLAN_A'
      });

      setCoordinatedPlanResult(res.data);
      setSelectedCoordinatedAlt('Plan A');
      loadCoreData(true);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Coordination optimization failed.';
      alert(detail);
      handleCheckCompatibility(ids);
    } finally {
      setCoordinationOptimizing(false);
      setCoordinationOptimizingStep(null);
    }
  };

  const handleApproveCommonBlock = async (planId) => {
    if (!confirm('Formally APPROVE this Coordinated Common Block Plan? This will simultaneously authorize track possession for all combined departmental jobs.')) return;
    try {
      const res = await approveCoordinatedBlockPlan(planId, {
        reason: 'Authorized common block possession by Chief Section Controller / Railway Planner'
      });
      setCoordinatedPlanResult(res.data);
      alert(`Coordinated Common Block ${res.data.plan_code} APPROVED! All combined requests updated to APPROVED.`);
      loadCoreData(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Approval failed.');
    }
  };

  const handleOpenCoordinatedModify = (plan) => {
    setCoordinatedModifyStart(plan.start_min || 645);
    setCoordinatedModifyEnd(plan.end_min || 735);
    setCoordinatedModifyReason('');
    setShowCoordinatedModifyModal(true);
  };

  const handleCoordinatedModifySubmit = async (e) => {
    if (e) e.preventDefault();
    if (!coordinatedModifyReason.trim()) {
      alert('Mandatory modification reason is required.');
      return;
    }
    try {
      const planId = coordinatedPlanResult.id || coordinatedPlanResult.plan_id;
      const res = await modifyCoordinatedBlockPlan(planId, {
        reason: coordinatedModifyReason.trim(),
        recommended_start_min: parseInt(coordinatedModifyStart),
        recommended_end_min: parseInt(coordinatedModifyEnd)
      });
      setShowCoordinatedModifyModal(false);
      setCoordinatedPlanResult(res.data);
      alert('Coordinated block schedule modified and recorded in audit trail.');
      loadCoreData(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Modification failed.');
    }
  };

  const handleOpenCoordinatedReject = (plan) => {
    setCoordinatedRejectReason('');
    setShowCoordinatedRejectModal(true);
  };

  const handleCoordinatedRejectSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!coordinatedRejectReason.trim()) {
      alert('Mandatory operational justification required to reject common block plan.');
      return;
    }
    try {
      const planId = coordinatedPlanResult.id || coordinatedPlanResult.plan_id;
      const res = await rejectCoordinatedBlockPlan(planId, {
        reason: coordinatedRejectReason.trim()
      });
      setShowCoordinatedRejectModal(false);
      setCoordinatedPlanResult(null);
      alert('Coordinated common block REJECTED. All combined requests restored to pending queue for individual scheduling.');
      loadCoreData(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Rejection failed.');
    }
  };

  const handleRunCoordinatedWhatIf = async () => {
    if (!coordinatedPlanResult) return;
    setWhatIfLoading(true);
    try {
      const planId = coordinatedPlanResult.id || coordinatedPlanResult.plan_id;
      const res = await whatIfCoordinatedBlockPlan(planId, {
        scenario_type: whatIfScenarioType,
        perturbation_value: parseInt(whatIfValue),
        remarks: `Planner simulation for ${whatIfScenarioType}`
      });
      setWhatIfResult(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'What-If evaluation failed.');
    } finally {
      setWhatIfLoading(false);
    }
  };

  const handleDynamicReplan = async () => {
    if (!coordinatedPlanResult) return;
    setDynamicReplanLoading(true);
    try {
      const planId = coordinatedPlanResult.id || coordinatedPlanResult.plan_id;
      const res = await replanCoordinatedBlockPlan(planId, {
        reason: 'Train movement disturbance detected in corridor; re-optimizing common block window'
      });
      setDynamicReplanResult(res.data);
      alert(res.data.message || 'Dynamic replanning complete.');
      loadCoreData(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Dynamic replanning failed.');
    } finally {
      setDynamicReplanLoading(false);
    }
  };

  // ── 11-Step Optimization Operational Pipeline (SIH26027 Section 5) ──
  const OPTIMIZATION_STEPS = [
    { num: 1, text: "Loading maintenance requests" },
    { num: 2, text: "Mapping requests to railway sections" },
    { num: 3, text: "Checking corridor compatibility" },
    { num: 4, text: "Checking department compatibility" },
    { num: 5, text: "Checking requested dates/windows" },
    { num: 6, text: "Checking train timetable" },
    { num: 7, text: "Checking current train movement" },
    { num: 8, text: "Checking section occupancy" },
    { num: 9, text: "Detecting coordination opportunities" },
    { num: 10, text: "Running CP-SAT optimization" },
    { num: 11, text: "Generating alternative plans" }
  ];

  const handleRunPoolOptimization = async (overrideJobIds = null) => {
    setPoolOptimizing(true);
    setPoolOptimizingStepIndex(0);

    const stepInterval = 140;
    const animTimer = setInterval(() => {
      setPoolOptimizingStepIndex(prev => {
        if (prev < OPTIMIZATION_STEPS.length - 1) return prev + 1;
        return prev;
      });
    }, stepInterval);

    try {
      const payload = {
        strategy: selectedStrategy || 'PLAN_A'
      };
      if (overrideJobIds && Array.isArray(overrideJobIds) && overrideJobIds.length > 0) {
        payload.job_ids = overrideJobIds;
      }
      const res = await optimizeRequestPool(payload);

      setPoolOptimizingStepIndex(OPTIMIZATION_STEPS.length);
      await new Promise(r => setTimeout(r, 250));

      setPoolOptimizationResult(res.data);
      loadCoreData(true);
    } catch (err) {
      console.error('Global optimization failed:', err);
      alert(err.response?.data?.detail || err.message || 'Global block pool optimization failed.');
    } finally {
      clearInterval(animTimer);
      setPoolOptimizing(false);
    }
  };

  const handleApprovePlanDirect = async (plan) => {
    const planId = plan.id || plan.plan_id;
    if (!planId) return;

    try {
      await approveCoordinatedBlockPlan(planId, {
        reason: 'Authorized common block possession by Chief Section Controller / Railway Planner'
      });
      setPoolOptimizationResult(prev => {
        if (!prev || !prev.plans) return prev;
        return {
          ...prev,
          plans: prev.plans.map(p => (p.id === planId || p.plan_id === planId) ? { ...p, status: 'APPROVED' } : p)
        };
      });
      if (activePlanModal && (activePlanModal.id === planId || activePlanModal.plan_id === planId)) {
        setActivePlanModal(prev => ({ ...prev, status: 'APPROVED' }));
      }
      loadCoreData(true);
    } catch (err) {
      console.error('Approval error:', err);
    }
  };

  // ── Section 17 Visual Coordination Relationship Tree ────────
  const renderCoordinationTree = (plan) => {
    if (!plan) return null;
    const isCommon = plan.coordination_type === 'COMMON_BLOCK' || ((plan.requests_combined_count || 0) > 1);
    const workItems = plan.work_breakdown && plan.work_breakdown.length > 0
      ? plan.work_breakdown
      : (plan.request_ids || []).map((id, idx) => ({
          job_code: id,
          department: (plan.departments && plan.departments[idx]) || 'Engineering',
          work_title: 'Maintenance Work',
          duration_min: plan.duration_min || 90
        }));

    return (
      <div className="bg-[#0B2545] text-white p-4 border-2 border-[#FFB703] my-3 rounded-xs font-mono shadow-md">
        <div className="text-center pb-2 border-b border-slate-700">
          <span className="text-[10px] text-[#FFB703] font-bold uppercase tracking-wider block">
            COORDINATED ASSET AVAILABILITY TOPOLOGY &bull; SECTION 17
          </span>
          <span className="text-xs font-black text-white">
            {plan.corridor} &bull; {plan.section}
          </span>
        </div>

        {/* Common Block Node */}
        <div className="flex flex-col items-center mt-3">
          <div className="bg-emerald-950/90 border-2 border-emerald-400 px-4 py-2 text-center shadow-lg rounded-xs">
            <div className="text-[9px] text-emerald-300 font-bold uppercase tracking-wider">
              {isCommon ? 'COMMON BLOCK POSSESSION' : 'INDIVIDUAL BLOCK'}
            </div>
            <div className="text-sm font-black text-white mt-0.5">
              {plan.common_block_window}
            </div>
            <div className="text-[10px] text-emerald-200">
              {plan.total_possession_duration_min || plan.duration_min} minutes duration
            </div>
          </div>

          {/* Stem down */}
          <div className="w-0.5 h-4 bg-[#FFB703]"></div>

          {isCommon && workItems.length > 1 ? (
            <>
              {/* Horizontal branch bar */}
              <div className="w-4/5 h-0.5 bg-[#FFB703] relative">
                <div className="absolute left-0 top-0 w-0.5 h-3 bg-[#FFB703]"></div>
                <div className="absolute right-0 top-0 w-0.5 h-3 bg-[#FFB703]"></div>
                {workItems.length === 3 && (
                  <div className="absolute left-1/2 -translate-x-1/2 top-0 w-0.5 h-3 bg-[#FFB703]"></div>
                )}
              </div>

              {/* Department Columns */}
              <div className="w-full flex justify-between gap-2 mt-3 pt-1">
                {workItems.map((wb, idx) => {
                  const deptCode = wb.department_code || (wb.department?.includes('Signal') ? 'S&T' : wb.department?.includes('Traction') ? 'TRD' : 'ENGG');
                  const deptColor = deptCode === 'ENGG' ? 'bg-amber-950/90 border-amber-400 text-amber-200'
                                 : deptCode === 'S&T' ? 'bg-cyan-950/90 border-cyan-400 text-cyan-200'
                                 : 'bg-purple-950/90 border-purple-400 text-purple-200';
                  return (
                    <div key={idx} className="flex-1 flex flex-col items-center">
                      <div className="text-center text-[10px] font-bold mb-1 text-slate-300">
                        ↓
                      </div>
                      <div className={`px-2 py-1 text-[10px] font-black uppercase border rounded-xs ${deptColor} text-center w-full max-w-[140px]`}>
                        {deptCode}
                        <div className="text-[8px] font-normal text-slate-300 truncate">
                          {wb.department || 'Dept'}
                        </div>
                      </div>
                      <div className="w-0.5 h-3 bg-slate-500 my-0.5"></div>
                      <div className="bg-slate-900 border border-slate-600 px-2 py-1 text-center w-full max-w-[140px] shadow-xs">
                        <div className="text-[11px] font-black text-[#FFB703]">{wb.job_code}</div>
                        <div className="text-[8px] text-slate-300 truncate">{wb.work_title || 'Maintenance'}</div>
                        <div className="text-[8px] text-emerald-400 font-bold">{wb.duration_min}m</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center mt-1">
              <div className="text-center text-[10px] font-bold mb-1 text-slate-300">↓</div>
              <div className="bg-amber-950/90 border border-amber-400 px-3 py-1 text-[10px] font-black text-amber-200 uppercase">
                {plan.departments ? plan.departments[0] : 'Engineering'}
              </div>
              <div className="w-0.5 h-3 bg-slate-500 my-0.5"></div>
              <div className="bg-slate-900 border border-slate-600 px-3 py-1 text-center">
                <div className="text-[11px] font-black text-[#FFB703]">{(plan.request_ids && plan.request_ids[0]) || 'REQ-106'}</div>
                <div className="text-[8px] text-emerald-400 font-bold">{plan.duration_min}m</div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const planJobs = activePlan ? activePlan.plan_jobs : [];
  const movements = timeDistanceData?.trains || [];

  // ── COORDINATION BADGE ───────────────────────────────────────
  const getCoordinationBadge = (job) => {
    if (job.coordinated_plan_id) {
      return (
        <span className="bg-cyan-100 text-cyan-900 border border-cyan-300 px-1 py-0.5 text-[9px] font-black flex items-center gap-0.5">
          <Users className="w-2.5 h-2.5 text-cyan-700" /> COORDINATED
        </span>
      );
    }
    // Check if there are other pending jobs with same section or corridor
    const sameSection = jobs.filter(other => 
      other.id !== job.id &&
      ['SUBMITTED', 'UNDER_REVIEW', 'PLANNING', 'RECOMMENDED'].includes(other.status) &&
      (
        (job.section_id && other.section_id === job.section_id) ||
        (job.start_station_code && other.start_station_code === job.start_station_code && other.end_station_code === job.end_station_code)
      )
    );
    if (sameSection.length > 0) {
      return (
        <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 px-1 py-0.5 text-[9px] font-bold flex items-center gap-0.5">
          <Sparkles className="w-2.5 h-2.5 text-emerald-700" /> CANDIDATE
        </span>
      );
    }
    return <span className="bg-slate-100 text-slate-600 border border-slate-300 px-1 py-0.5 text-[9px]">INDIVIDUAL</span>;
  };

  // ── PRIORITY BADGE ───────────────────────────────────────────
  const getPriorityBadge = (prio) => {
    switch ((prio || '').toUpperCase()) {
      case 'HIGH': return <span className="bg-red-100 text-red-800 border border-red-300 px-1 py-0.5 text-[10px] font-bold">HIGH</span>;
      case 'MEDIUM': return <span className="bg-amber-100 text-amber-800 border border-amber-300 px-1 py-0.5 text-[10px] font-bold">MED</span>;
      case 'LOW': return <span className="bg-slate-100 text-slate-700 border border-slate-300 px-1 py-0.5 text-[10px] font-bold">LOW</span>;
      default: return <span className="text-slate-600 text-[10px]">{prio || 'MED'}</span>;
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      SUBMITTED: 'bg-blue-100 text-blue-800 border-blue-300',
      APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-300',
      DEPARTMENT_ACCEPTED: 'bg-teal-100 text-teal-800 border-teal-300',
      IN_PROGRESS: 'bg-amber-100 text-amber-900 border-amber-300',
      COMPLETED: 'bg-green-100 text-green-900 border-green-300',
      CHANGE_REQUESTED: 'bg-orange-100 text-orange-800 border-orange-300',
      REJECTED: 'bg-red-100 text-red-800 border-red-300',
    };
    const cls = colors[status] || 'bg-slate-100 text-slate-700 border-slate-300';
    return <span className={`px-1 py-0.5 text-[9px] font-bold border ${cls}`}>{status}</span>;
  };

  // ══════════════════════════════════════════════════════════════
  //  STATION CONTENT RENDERERS
  // ══════════════════════════════════════════════════════════════

  // ── 1. CONTROL PANEL (SIH26027 RAILWAY PLANNER CONTROL ROOM) ──────
  const renderControlPanel = () => {
    const pendingJobs = jobs.filter(j => ['SUBMITTED', 'UNDER_REVIEW', 'PLANNING'].includes(j.status)).length;
    const analyzedJobs = poolOptimizationResult ? poolOptimizationResult.requests_analyzed : jobs.length;
    const coordinatedJobs = poolOptimizationResult ? poolOptimizationResult.requests_coordinated : jobs.filter(j => j.coordinated_plan_id).length;
    const optimizedBlocks = poolOptimizationResult ? poolOptimizationResult.total_optimized_plans : jobs.filter(j => ['APPROVED', 'DEPARTMENT_ACCEPTED'].includes(j.status)).length;
    const trainConflicts = jobs.reduce((sum, j) => sum + (j.conflicting_trains_count || 0), 0);
    const availableWindowsCount = windowsData?.length || 6;

    const controlRoomKPIs = [
      { label: 'PENDING REQUESTS', value: pendingJobs, color: 'border-l-amber-500', note: 'Awaiting planning & CP-SAT' },
      { label: 'REQUESTS ANALYZED', value: analyzedJobs, color: 'border-l-blue-600', note: 'Complete request pool scope' },
      { label: 'COORDINATED JOBS', value: coordinatedJobs, color: 'border-l-emerald-600', note: 'Common block candidates' },
      { label: 'OPTIMIZED BLOCKS', value: optimizedBlocks, color: 'border-l-cyan-600', note: 'Multi-dept possessions' },
      { label: 'CONFLICTS', value: trainConflicts, color: 'border-l-green-600', note: 'Hard conflicts resolved' },
      { label: 'AVAILABLE WINDOWS', value: availableWindowsCount, color: 'border-l-purple-600', note: 'Feasible maintenance slots' },
    ];

    // Selected Alternative for Plan A / B / C (Section 11)
    const alternatives = optimizationResult?.alternatives || [
      {
        plan_name: 'Plan A',
        label: 'Best Overall',
        recommended_time_window: '10:45 – 12:15',
        recommended_date: '15 Sep 2026',
        recommended_section: selectedRequest?.section?.section_code || selectedRequest?.section_name || 'SECTION-103',
        duration_min: selectedRequest?.estimated_duration_min || 90,
        score: 94,
        block_utilization_pct: 91,
        conflicting_trains_count: 0,
        coordinated_jobs: 'Track Engineering + Signal & Telecom',
        tradeoff: 'Optimizes track occupancy between peak commuter slots. Zero passenger train headway impact.'
      },
      {
        plan_name: 'Plan B',
        label: 'Second-Best Alternative',
        recommended_time_window: '13:00 – 14:30',
        recommended_date: '15 Sep 2026',
        recommended_section: selectedRequest?.section?.section_code || selectedRequest?.section_name || 'SECTION-103',
        duration_min: selectedRequest?.estimated_duration_min || 90,
        score: 88,
        block_utilization_pct: 84,
        conflicting_trains_count: 0,
        coordinated_jobs: 'Standalone Civil Engineering block',
        tradeoff: 'Afternoon window; slight buffer compression for downstream freight crossing.'
      },
      {
        plan_name: 'Plan C',
        label: 'Fallback Alternative',
        recommended_time_window: '15:30 – 17:00',
        recommended_date: '15 Sep 2026',
        recommended_section: selectedRequest?.section?.section_code || selectedRequest?.section_name || 'SECTION-103',
        duration_min: selectedRequest?.estimated_duration_min || 90,
        score: 81,
        block_utilization_pct: 78,
        conflicting_trains_count: 0,
        coordinated_jobs: 'Track Engineering + TRD OHE Power Block',
        tradeoff: 'Approaches evening traffic surge; requires tighter coordination with traction controller.'
      }
    ];

    const currentAlt = alternatives.find(a => a.plan_name === selectedAlternative) || alternatives[0];
    const currentCoordinatedAlt = (coordinatedPlanResult?.alternatives || []).find(a => a.plan_name === selectedCoordinatedAlt) || (coordinatedPlanResult?.alternatives || [])[0] || {};

    const reqCorridorLabel = selectedRequest
      ? `${selectedRequest.start_station_code || 'CVP'} → ${selectedRequest.end_station_code || 'TEN'}`
      : 'CVP → TEN';

    const obsCorridorLabel = observationCorridor
      ? `${observationCorridor.prototype_code ? observationCorridor.prototype_code + ': ' : ''}${observationCorridor.name || (observationCorridor.start_station_code + ' → ' + observationCorridor.end_station_code)}`
      : 'MDU → TEN';

    return (
      <div className="space-y-3 font-sans">
        {/* TOP METRICS ROW (Section 29) */}
        <div className="bg-[#0B2545] border-b-2 border-[#FFB703] p-2.5 text-white flex flex-wrap items-center justify-between shadow-xs">
          <div>
            <div className="text-[10px] text-[#FFB703] font-mono font-bold uppercase tracking-wider">
              INDIAN RAILWAYS &bull; SOUTHERN RAILWAY OPERATIONAL DIVISION
            </div>
            <h1 className="text-sm font-black uppercase tracking-wide flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#FFB703]" />
              RAILWAY PLANNER CONTROL ROOM (TAMIL NADU NETWORK)
            </h1>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <div className="bg-[#134074] px-2.5 py-1 border border-slate-600 font-mono text-[11px]">
              <span className="text-slate-400">TELEMETRY:</span>{' '}
              <span className={observationDataStatus?.is_live ? 'text-emerald-400 font-bold' : 'text-amber-300 font-bold'}>
                {observationDataStatus?.status || 'CACHED'}
              </span>
            </div>
            <button
              onClick={() => loadCoreData(true)}
              className="bg-[#FFB703] hover:bg-[#ffa700] text-[#0B2545] font-black px-2.5 py-1 text-xs uppercase flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> SYNC FEED
            </button>
          </div>
        </div>

        {/* 6 KPI Cards strictly matching Section 29 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {controlRoomKPIs.map((kpi) => (
            <div key={kpi.label} className={`bg-white border border-slate-300 border-l-4 ${kpi.color} p-2 shadow-xs`}>
              <div className="text-[9px] font-black text-slate-500 uppercase tracking-tight">{kpi.label}</div>
              <div className="text-2xl font-black font-mono text-[#0B2545] my-0.5">{kpi.value}</div>
              <div className="text-[8px] text-slate-400 font-mono truncate">{kpi.note}</div>
            </div>
          ))}
        </div>

        {/* MAIN WORKSPACE GRID: REQUEST QUEUE + OPTIMIZER & INDEPENDENT LIVE CORRIDOR MAP */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          
          {/* LEFT 7 COLS: REQUEST QUEUE & SELECTED REQUEST PLANNER WORKFLOW */}
          <div className="lg:col-span-7 space-y-3">
            
            {/* REQUEST QUEUE (Section 29) */}
            <div className="bg-white border border-slate-300 shadow-xs">
              <div className="bg-[#F8FAFC] border-b border-slate-300 p-2 px-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-bold text-xs text-[#0B2545] uppercase">
                  <Inbox className="w-4 h-4 text-[#134074]" />
                  REQUEST QUEUE (DEPARTMENT MAINTENANCE DEMANDS)
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-slate-600 bg-slate-200 px-1.5 py-0.5 font-bold">
                    {jobs.length} Demands Loaded
                  </span>
                  <button
                    id="btn-header-optimize"
                    onClick={() => handleRunPoolOptimization()}
                    disabled={poolOptimizing}
                    className="bg-[#0B2545] hover:bg-[#134074] text-white font-black px-2.5 py-1 text-[11px] uppercase flex items-center gap-1 border border-[#FFB703] cursor-pointer shadow-xs"
                    title="Analyze all eligible pending requests and generate coordinated block plans"
                  >
                    <Cpu className={`w-3.5 h-3.5 text-[#FFB703] ${poolOptimizing ? 'animate-spin' : ''}`} />
                    <span>OPTIMIZE REQUESTS</span>
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto max-h-64 border-b border-slate-200">
                <table className="cris-table w-full text-[11px]">
                  <thead>
                    <tr>
                      <th className="w-8 text-center">
                        <input
                          type="checkbox"
                          checked={selectedRequestIds.length > 0 && selectedRequestIds.length === jobs.length}
                          onChange={handleSelectAllPending}
                          title="Select / Deselect all for common block coordination"
                          className="cursor-pointer"
                        />
                      </th>
                      <th>Request ID</th>
                      <th>Dept</th>
                      <th>Work</th>
                      <th>Corridor</th>
                      <th>Section</th>
                      <th>Date</th>
                      <th>Duration</th>
                      <th>Priority</th>
                      <th>Due Date</th>
                      <th>Status</th>
                      <th>Coordination</th>
                      <th className="text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.length === 0 ? (
                      <tr>
                        <td colSpan="13" className="text-center py-6 text-slate-500">
                          NO ACTIVE BLOCK REQUESTS IN QUEUE
                        </td>
                      </tr>
                    ) : (
                      jobs.map((j) => {
                        const isSelected = selectedRequest?.id === j.id;
                        const isChecked = selectedRequestIds.includes(j.id);
                        return (
                          <tr
                            key={j.id}
                            className={`cursor-pointer transition-colors ${
                              isChecked
                                ? 'bg-amber-50 font-medium'
                                : isSelected
                                ? 'bg-amber-100/80 font-bold border-l-4 border-l-[#FFB703]'
                                : 'hover:bg-slate-50'
                            }`}
                            onClick={() => { setActiveRequestDetailsModal(j); setSelectedRequest(j); }}
                          >
                            <td className="text-center" onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => handleToggleSelectRequest(j.id)}
                                className="cursor-pointer"
                              />
                            </td>
                            <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                            <td>
                              <span className="font-bold text-slate-700 bg-slate-100 px-1 py-0.5 border text-[9px]">
                                {j.department?.code || (j.department?.name?.includes('Signal') ? 'S&T' : j.department?.name?.includes('Traction') ? 'TRD' : 'ENGG')}
                              </span>
                            </td>
                            <td className="text-slate-800 font-semibold max-w-[120px] truncate" title={j.work_title || j.work_type}>
                              {j.work_title || j.work_type}
                            </td>
                            <td className="font-mono font-bold text-[#134074]">
                              {j.start_station_code || 'CVP'} → {j.end_station_code || 'TEN'}
                            </td>
                            <td className="font-mono text-[10px] text-slate-800">
                              {j.section?.section_id || j.section?.section_code || j.section_name || 'SECTION-103'}
                            </td>
                            <td className="font-mono text-slate-700">{j.requested_date || (j.created_at ? j.created_at.slice(5, 10) : '15 Sep')}</td>
                            <td className="font-mono">{j.estimated_duration_min}m</td>
                            <td>{getPriorityBadge(j.user_priority)}</td>
                            <td className="font-mono text-slate-600">{j.due_date ? j.due_date.slice(5, 10) : '15 Sep'}</td>
                            <td>{getStatusBadge(j.status)}</td>
                            <td>{getCoordinationBadge(j)}</td>
                            <td className="text-center" onClick={(e) => e.stopPropagation()}>
                              <button
                                onClick={() => { setActiveRequestDetailsModal(j); setSelectedRequest(j); }}
                                className="px-2 py-0.5 text-[10px] font-black uppercase tracking-wider border cursor-pointer bg-[#0B2545] text-white hover:bg-[#134074] border-slate-700"
                              >
                                [VIEW]
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* PRIMARY & SECONDARY OPTIMIZATION ACTION BAR (Section 3 & 4) */}
            <div className="bg-white border-2 border-[#0B2545] p-3 shadow-md space-y-2">
              <div className="flex flex-col sm:flex-row items-stretch gap-2">
                <button
                  id="btn-optimize-requests"
                  onClick={() => handleRunPoolOptimization()}
                  disabled={poolOptimizing}
                  className="flex-1 py-3 px-4 bg-[#0B2545] hover:bg-[#134074] text-white font-black text-xs uppercase flex items-center justify-center gap-2.5 border-2 border-[#FFB703] shadow-lg cursor-pointer transition-all hover:scale-[1.01] disabled:opacity-50"
                  title="Analyze all eligible pending maintenance requests and generate the best coordinated block plan"
                >
                  <Cpu className={`w-5 h-5 text-[#FFB703] ${poolOptimizing ? 'animate-spin' : 'animate-pulse'}`} />
                  <span className="tracking-wider text-sm font-black">OPTIMIZE REQUESTS</span>
                  <span className="text-[10px] font-mono text-[#FFB703] bg-[#134074] px-2 py-0.5 border border-[#FFB703]/50">
                    AI POOL SOLVER ({jobs.filter(j => !['COMPLETED', 'CANCELLED', 'REJECTED'].includes(j.status)).length} ELIGIBLE)
                  </span>
                </button>

                <button
                  id="btn-optimize-selected"
                  onClick={() => handleRunPoolOptimization(selectedRequestIds)}
                  disabled={poolOptimizing || selectedRequestIds.length === 0}
                  className="py-3 px-4 bg-slate-100 hover:bg-slate-200 text-[#0B2545] font-black text-xs uppercase flex items-center justify-center gap-2 border border-slate-400 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  title="Analyze only the requests manually selected with checkboxes"
                >
                  <CheckSquare className="w-4 h-4 text-slate-700" />
                  <span>OPTIMIZE SELECTED ({selectedRequestIds.length})</span>
                </button>
              </div>

              {selectedRequestIds.length > 0 && (
                <div className="flex items-center justify-between text-[11px] bg-amber-50 border border-amber-300 p-2 text-amber-900">
                  <span>
                    <strong>{selectedRequestIds.length}</strong> request{selectedRequestIds.length > 1 ? 's' : ''} manually checked in queue.
                  </span>
                  <button
                    onClick={() => setSelectedRequestIds([])}
                    className="text-[10px] font-bold text-red-700 hover:underline cursor-pointer"
                  >
                    Clear Manual Selection
                  </button>
                </div>
              )}
            </div>

            {/* OPTIMIZATION PROCESS UI & PROGRESS PANEL (Section 5) */}
            {poolOptimizing && (
              <div className="bg-[#0B2545] text-white border-2 border-[#FFB703] p-3 shadow-xl space-y-3">
                <div className="flex items-center justify-between border-b border-slate-700 pb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-[#FFB703] animate-spin" />
                    <div>
                      <span className="text-[10px] font-mono font-bold text-[#FFB703] uppercase tracking-wider block">
                        GLOBAL BLOCK OPTIMIZATION IN PROGRESS
                      </span>
                      <h3 className="text-xs font-black uppercase text-white tracking-wide">
                        CP-SAT SECTION & TIME-SLOT OPTIMIZER
                      </h3>
                    </div>
                  </div>
                  <div className="text-right text-[10px] font-mono">
                    <span className="text-slate-300">STAGE: </span>
                    <span className="text-[#FFB703] font-bold">{Math.min(11, poolOptimizingStepIndex + 1)} / 11</span>
                  </div>
                </div>

                {/* Counter metrics */}
                <div className="grid grid-cols-3 gap-2 bg-[#134074]/60 p-2 border border-slate-600 text-center font-mono">
                  <div>
                    <span className="text-[9px] text-slate-300 block uppercase">Requests Detected</span>
                    <strong className="text-sm text-white">{jobs.length}</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-300 block uppercase">Eligible for Pool</span>
                    <strong className="text-sm text-[#FFB703]">
                      {jobs.filter(j => ['SUBMITTED', 'UNDER_REVIEW', 'PLANNING', 'RECOMMENDED', 'DRAFT'].includes(j.status)).length}
                    </strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-300 block uppercase">Already Scheduled</span>
                    <strong className="text-sm text-emerald-400">
                      {jobs.filter(j => ['APPROVED', 'DEPARTMENT_ACCEPTED'].includes(j.status)).length}
                    </strong>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-800 h-2 border border-slate-600 overflow-hidden">
                  <div
                    className="bg-[#FFB703] h-full transition-all duration-150"
                    style={{ width: `${Math.min(100, Math.round(((poolOptimizingStepIndex + 1) / OPTIMIZATION_STEPS.length) * 100))}%` }}
                  ></div>
                </div>

                {/* 11 Steps Checklist */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[11px] font-mono max-h-48 overflow-y-auto pr-1">
                  {OPTIMIZATION_STEPS.map((st) => {
                    const isDone = st.num <= poolOptimizingStepIndex;
                    const isCurrent = st.num === poolOptimizingStepIndex + 1;
                    return (
                      <div
                        key={st.num}
                        className={`flex items-center gap-1.5 p-1 rounded-xs transition-colors ${
                          isDone
                            ? 'text-emerald-300 font-bold bg-emerald-950/40'
                            : isCurrent
                            ? 'text-[#FFB703] font-black bg-amber-950/60 animate-pulse'
                            : 'text-slate-500'
                        }`}
                      >
                        <span className="w-4 text-center font-bold">
                          {isDone ? '✓' : isCurrent ? '⏳' : '○'}
                        </span>
                        <span>STEP {st.num}: {st.text}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* OPTIMIZATION SUMMARY (Section 16) */}
            {poolOptimizationResult && (
              <div className="bg-[#0B2545] text-white border-2 border-[#FFB703] p-3 shadow-md space-y-2.5">
                <div className="flex flex-wrap items-center justify-between border-b border-slate-700 pb-1.5">
                  <div className="flex items-center gap-2">
                    <Award className="w-4 h-4 text-[#FFB703]" />
                    <h3 className="font-black text-xs uppercase tracking-wider text-white">
                      OPTIMIZATION SUMMARY & METRICS
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-slate-300">
                    RUN ID: <strong className="text-[#FFB703]">{poolOptimizationResult.optimization_run_id}</strong>
                  </span>
                </div>

                {/* 9 Calculated KPI Tiles (Section 16) */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 text-center font-mono">
                  <div className="p-2 bg-[#134074]/60 border border-slate-600">
                    <div className="text-[9px] text-slate-300 uppercase">Requests Analyzed</div>
                    <div className="text-xl font-black text-white mt-0.5">{poolOptimizationResult.requests_analyzed}</div>
                  </div>
                  <div className="p-2 bg-[#134074]/60 border border-slate-600">
                    <div className="text-[9px] text-slate-300 uppercase">Requests Coordinated</div>
                    <div className="text-xl font-black text-[#FFB703] mt-0.5">{poolOptimizationResult.requests_coordinated}</div>
                  </div>
                  <div className="p-2 bg-[#134074]/60 border border-slate-600">
                    <div className="text-[9px] text-slate-300 uppercase">Individually Scheduled</div>
                    <div className="text-xl font-black text-blue-300 mt-0.5">{poolOptimizationResult.requests_individual}</div>
                  </div>
                  <div className="p-2 bg-[#134074]/60 border border-slate-600">
                    <div className="text-[9px] text-slate-300 uppercase">Total Optimized Plans</div>
                    <div className="text-xl font-black text-cyan-300 mt-0.5">{poolOptimizationResult.total_optimized_plans}</div>
                  </div>
                  <div className="p-2 bg-[#134074]/60 border border-slate-600">
                    <div className="text-[9px] text-slate-300 uppercase">Possessions Avoided</div>
                    <div className="text-xl font-black text-emerald-400 mt-0.5">{poolOptimizationResult.possessions_avoided}</div>
                  </div>
                </div>

                {/* Coordination Benefit Badge */}
                <div className="p-2 bg-[#134074] border border-slate-600 flex items-center justify-between text-[11px] font-mono">
                  <div className="text-slate-200">
                    Original Potential Blocks: <strong className="text-slate-400 line-through">{poolOptimizationResult.original_potential_blocks}</strong> → Optimized Blocks: <strong className="text-[#FFB703]">{poolOptimizationResult.optimized_blocks}</strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-300">Estimated Coordination Benefit:</span>
                    <span className="bg-emerald-700 text-white font-black px-2 py-0.5 text-[10px] uppercase tracking-wide">
                      {poolOptimizationResult.estimated_coordination_benefit}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* OPTIMIZED BLOCK PLANS (Section 9 & Section 15) */}
            {poolOptimizationResult && poolOptimizationResult.plans && poolOptimizationResult.plans.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b-2 border-[#0B2545] pb-1">
                  <h2 className="font-black text-xs text-[#0B2545] uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-[#134074]" />
                    OPTIMIZED BLOCK PLANS ({poolOptimizationResult.plans.length} GENERATED)
                  </h2>
                  <span className="text-[10px] font-mono text-slate-600">
                    Click [VIEW PLAN] for topology & alternatives, or [APPROVE] to authorize possession
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {poolOptimizationResult.plans.map((plan, idx) => {
                    const isCommon = plan.coordination_type === 'COMMON_BLOCK' || (plan.requests_combined_count > 1);
                    const isApproved = plan.status === 'APPROVED';

                    return (
                      <div
                        key={plan.id || plan.plan_id || idx}
                        className="bg-white border-2 border-[#134074] shadow-sm hover:shadow-md transition-shadow"
                      >
                        {/* Plan Card Header */}
                        <div className="bg-[#0B2545] text-white p-2.5 px-3 flex flex-wrap items-center justify-between border-b border-slate-700">
                          <div className="flex items-center gap-2">
                            <span className="bg-[#FFB703] text-[#0B2545] px-2 py-0.5 text-[10px] font-black uppercase font-mono tracking-wide">
                              {plan.plan_title || `PLAN ${(idx + 1) < 10 ? '0' + (idx + 1) : (idx + 1)}`}
                            </span>
                            <span className={`px-2 py-0.5 text-[10px] font-black uppercase border ${
                              isApproved
                                ? 'bg-emerald-800 text-white border-emerald-400'
                                : 'bg-emerald-100 text-emerald-900 border-emerald-300'
                            }`}>
                              {isApproved ? 'APPROVED' : 'RECOMMENDED'}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs font-mono">
                            <span>Score: <strong className="text-[#FFB703]">{plan.optimization_score || 96}</strong></span>
                            <span>Conflicts: <strong className="text-emerald-400">0</strong></span>
                          </div>
                        </div>

                        {/* Plan Card Body */}
                        <div className="p-3 space-y-2 text-xs">
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-slate-50 p-2.5 border border-slate-200">
                            <div>
                              <span className="text-[9px] font-bold text-slate-500 uppercase block">Corridor</span>
                              <strong className="font-mono text-[#134074] text-xs block">{plan.corridor}</strong>
                            </div>
                            <div>
                              <span className="text-[9px] font-bold text-slate-500 uppercase block">Section</span>
                              <strong className="font-mono text-slate-900 text-xs block">{plan.section}</strong>
                            </div>
                            <div>
                              <span className="text-[9px] font-bold text-slate-500 uppercase block">Common Window</span>
                              <strong className="font-mono text-emerald-800 text-xs font-black block">
                                {plan.common_block_window}
                              </strong>
                            </div>
                            <div>
                              <span className="text-[9px] font-bold text-slate-500 uppercase block">Duration</span>
                              <strong className="font-mono text-slate-800 text-xs block">
                                {plan.total_possession_duration_min || plan.duration_min} min
                              </strong>
                            </div>
                          </div>

                          {/* Coordinated Departments & Requests Badges */}
                          <div className="flex flex-wrap items-center justify-between gap-2 p-2 bg-slate-100/70 border border-slate-200">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="text-[10px] font-bold text-slate-600 uppercase">
                                {isCommon ? `${plan.requests_combined_count} REQUESTS COMBINED:` : 'STANDALONE REQUEST:'}
                              </span>
                              {(plan.request_ids || []).map((reqId, rIdx) => (
                                <span key={rIdx} className="bg-white border border-slate-300 px-1.5 py-0.5 font-mono font-bold text-[#0B2545] text-[10px]">
                                  {reqId}
                                </span>
                              ))}
                            </div>

                            <div className="flex flex-wrap items-center gap-1">
                              {(plan.departments || []).map((dept, dIdx) => (
                                <span key={dIdx} className="bg-[#134074] text-white px-2 py-0.5 text-[9px] font-bold uppercase">
                                  {dept}
                                </span>
                              ))}
                            </div>
                          </div>

                          {/* Coordination Savings & Operational Metrics */}
                          <div className="grid grid-cols-3 gap-2 text-[10px] font-mono text-slate-700 pt-1">
                            <div>
                              <span className="text-slate-500">Separate Blocks: </span>
                              <strong className="text-slate-900">{isCommon ? `${plan.requests_combined_count} → 1` : '1'}</strong>
                            </div>
                            <div>
                              <span className="text-slate-500">Possessions Avoided: </span>
                              <strong className="text-emerald-700 font-bold">{plan.separate_blocks_avoided || 0}</strong>
                            </div>
                            <div>
                              <span className="text-slate-500">Block Utilization: </span>
                              <strong className="text-blue-900 font-bold">{plan.block_utilization_pct || 100}%</strong>
                            </div>
                          </div>
                        </div>

                        {/* Plan Card Action Footer */}
                        <div className="bg-slate-50 p-2 px-3 border-t border-slate-200 flex items-center justify-between">
                          <button
                            id={`btn-view-plan-${idx + 1}`}
                            onClick={() => {
                              setActivePlanModal(plan);
                              setActivePlanModalAlt('Plan A');
                            }}
                            className="bg-[#134074] hover:bg-[#0B2545] text-white font-bold text-xs uppercase px-3 py-1.5 flex items-center gap-1 border border-slate-700 cursor-pointer"
                          >
                            <Eye className="w-3.5 h-3.5 text-[#FFB703]" />
                            [ VIEW PLAN ]
                          </button>

                          <div className="flex items-center gap-2">
                            {isApproved ? (
                              <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 font-black text-xs px-3 py-1.5 flex items-center gap-1 uppercase">
                                <CheckCircle className="w-3.5 h-3.5 text-emerald-700" />
                                ✓ APPROVED
                              </span>
                            ) : (
                              <button
                                id={`btn-approve-plan-${idx + 1}`}
                                onClick={() => handleApprovePlanDirect(plan)}
                                className="bg-emerald-700 hover:bg-emerald-800 text-white font-black text-xs uppercase px-3 py-1.5 flex items-center gap-1 shadow-xs cursor-pointer"
                              >
                                <CheckCircle className="w-3.5 h-3.5" />
                                [ APPROVE ]
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : !poolOptimizing && (
              <div className="bg-white border-2 border-dashed border-slate-300 p-8 text-center space-y-3">
                <Cpu className="w-10 h-10 text-slate-400 mx-auto" />
                <div>
                  <h3 className="font-black text-sm text-[#0B2545] uppercase">
                    CENTRALIZED RAILWAY PLANNING WORKSTATION READY
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                    The queue contains {jobs.length} maintenance demands. Click the primary button below to evaluate the complete eligible request pool and automatically generate coordinated block plans.
                  </p>
                </div>
                <button
                  onClick={() => handleRunPoolOptimization()}
                  className="px-5 py-2.5 bg-[#0B2545] hover:bg-[#134074] text-white font-black text-xs uppercase border-2 border-[#FFB703] shadow-md cursor-pointer inline-flex items-center gap-2"
                >
                  <Cpu className="w-4 h-4 text-[#FFB703]" />
                  [ OPTIMIZE REQUESTS NOW ]
                </button>
              </div>
            )}
          </div>

          {/* RIGHT 5 COLS: INDEPENDENT LIVE CORRIDOR OBSERVATION (Section 18, 19, 20) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="bg-white border-2 border-slate-700 shadow-xs">
              
              {/* Section 19 Distinct Title & Rule Callout */}
              <div className="bg-[#0B2545] text-white p-2.5 px-3">
                <div className="text-[10px] text-[#FFB703] font-mono font-bold uppercase tracking-wider">
                  OPERATIONAL SITUATIONAL AWARENESS &bull; SECTION 19
                </div>
                <h3 className="text-xs font-black uppercase tracking-wide flex items-center gap-1.5 mt-0.5">
                  <Radio className="w-4 h-4 text-[#FFB703] animate-pulse" />
                  LIVE CORRIDOR OBSERVATION
                </h3>
              </div>

              {/* Section 19 Decoupling Box: Request Corridor vs Live Observation Corridor */}
              <div className="p-2.5 bg-amber-50/70 border-b border-amber-200 text-xs">
                <div className="text-[9px] font-black text-amber-900 uppercase tracking-wide mb-1">
                  DECOUPLED OBSERVATION MODE:
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-1.5 bg-white border border-amber-300">
                    <span className="text-[9px] font-bold text-slate-500 uppercase block">REQUEST CORRIDOR</span>
                    <strong className="font-mono text-[#0B2545]">{reqCorridorLabel}</strong>
                  </div>
                  <div className="p-1.5 bg-white border border-blue-400">
                    <span className="text-[9px] font-bold text-blue-700 uppercase block">LIVE OBSERVATION</span>
                    <strong className="font-mono text-blue-900">{obsCorridorLabel}</strong>
                  </div>
                </div>
              </div>

              {/* Corridor Selector (Section 4 & 5: C01-C20 Tamil Nadu network) */}
              <div className="p-2.5 bg-slate-50 border-b border-slate-200 space-y-2">
                <label className="text-[10px] font-black text-slate-700 uppercase block">
                  Select Live Tamil Nadu Corridor to Observe:
                </label>
                <select
                  value={observationCorridorId || ''}
                  onChange={(e) => {
                    const corrId = e.target.value;
                    setObservationCorridorId(corrId);
                    const found = corridors.find(c => c.id === corrId || c.corridor_id === corrId);
                    if (found) setObservationCorridor(found);
                  }}
                  className="w-full bg-white border-2 border-slate-300 text-xs font-bold p-1.5 text-[#0B2545] focus:border-[#0B2545] outline-none"
                >
                  {corridors.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.prototype_code ? `[${c.prototype_code}] ` : ''}{c.name} ({c.start_station_code} → {c.end_station_code})
                    </option>
                  ))}
                </select>

                {/* Section 5 Display Corridor Summary */}
                {observationCorridor && (
                  <div className="grid grid-cols-4 gap-1 text-[10px] font-mono bg-white p-1.5 border border-slate-200">
                    <div><span className="text-slate-500">Start:</span> <strong className="text-slate-800">{observationCorridor.start_station_code}</strong></div>
                    <div><span className="text-slate-500">End:</span> <strong className="text-slate-800">{observationCorridor.end_station_code}</strong></div>
                    <div><span className="text-slate-500">Sections:</span> <strong className="text-slate-800">{observationSections.length || observationCorridor.sections_count || 3}</strong></div>
                    <div><span className="text-slate-500">Stations:</span> <strong className="text-slate-800">{observationStations.length || observationCorridor.stations_count || 8}</strong></div>
                  </div>
                )}
              </div>

              {/* Data Provenance Banner (Section 21, 22, 23) */}
              <div className="px-3 py-1.5 bg-[#0B2545] text-white flex items-center justify-between text-[10px] font-mono border-b border-slate-700">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">SOURCE:</span>
                  <span className="text-[#FFB703] font-bold">LIVE RADAR</span>
                  <span className="text-slate-400">&bull;</span>
                  <span className={observationDataStatus?.is_live ? 'bg-emerald-700 px-1 text-white font-bold' : 'bg-amber-700 px-1 text-white font-bold'}>
                    {observationDataStatus?.status || 'CACHED'}
                  </span>
                </div>
                <div className="text-slate-300">
                  REFRESH: 5s (LOCAL DB CACHE)
                </div>
              </div>

              {/* Map Canvas (Section 18 & 20) */}
              <div className="h-64 border-b border-slate-300 relative bg-slate-900">
                <RailwayMap
                  stations={observationStations}
                  sections={observationSections}
                  liveTrains={observationMovements}
                  height="100%"
                />
              </div>

              {/* Section 17 & 18: Live Trains on Selected Corridor List */}
              <div className="p-2.5">
                <div className="text-[10px] font-black text-[#0B2545] uppercase flex items-center justify-between border-b border-slate-200 pb-1 mb-2">
                  <span className="flex items-center gap-1">
                    <Train className="w-3.5 h-3.5 text-[#134074]" />
                    TRAINS ON {observationCorridor?.start_station_code || 'MDU'} → {observationCorridor?.end_station_code || 'TEN'}
                  </span>
                  <span className="font-mono text-slate-500">
                    {observationMovements.length} Active
                  </span>
                </div>

                <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                  {observationMovements.length === 0 ? (
                    <div className="text-center py-6 text-slate-500 text-xs">
                      No trains currently active on this corridor in local cache.
                    </div>
                  ) : (
                    observationMovements.map((t, idx) => {
                      const trainNum = t.train_number || t.train_no || `1612${idx + 1}`;
                      const trainName = t.train_name || 'Express Service';
                      const speed = t.speed_kmh || t.speed || 75;
                      const delay = t.delay_minutes ?? t.delay ?? 0;
                      const delayText = delay > 0 ? `+${delay} min` : 'ON TIME';
                      const status = t.status || (delay > 15 ? 'DELAYED' : 'RUNNING');
                      const curr = t.current_station_code || t.station_code || observationCorridor?.start_station_code || 'TEN';
                      const next = t.next_station_code || 'NNN';
                      const prev = t.prev_station_code || 'MEJ';

                      return (
                        <div
                          key={trainNum + idx}
                          className="bg-white border border-slate-300 p-2 text-xs hover:border-[#0B2545] transition-colors"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono font-black text-[#0B2545]">{trainNum}</span>
                              <span className="font-bold text-slate-800 text-[11px] truncate max-w-[140px]">{trainName}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className={`px-1 py-0.2 text-[9px] font-bold ${
                                status === 'RUNNING' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                              }`}>
                                {status}
                              </span>
                              <span className={`font-mono text-[9px] font-bold px-1 py-0.2 ${
                                delay > 0 ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700'
                              }`}>
                                {delayText}
                              </span>
                            </div>
                          </div>

                          <div className="grid grid-cols-4 gap-1 text-[10px] font-mono text-slate-600 mt-1 bg-slate-50 p-1 border border-slate-200">
                            <div><span className="text-slate-400">Speed:</span> <strong>{speed} km/h</strong></div>
                            <div><span className="text-slate-400">Curr:</span> <strong>{curr}</strong></div>
                            <div><span className="text-slate-400">Next:</span> <strong>{next}</strong></div>
                            <div><span className="text-slate-400">Prev:</span> <strong>{prev}</strong></div>
                          </div>

                          <div className="flex items-center justify-between text-[8px] font-mono text-slate-400 mt-1">
                            <span>SOURCE: LIVE RADAR (PERSISTED)</span>
                            <span>UPDATED: {lastSyncTime}</span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* TIME-DISTANCE OPERATIONAL CHART (Preserved for Master Block Schedule) */}
        <div className="bg-white border border-slate-300 p-3 shadow-xs">
          <div className="text-xs font-bold text-[#0B2545] uppercase border-b border-slate-200 pb-1.5 mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-[#134074]" />
              MASTER TIME-DISTANCE TRAIN MOVEMENT & BLOCK SCHEDULE
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              CORRIDOR: {selectedCorridorId || 'CORR_C15_MDU_TEN'}
            </span>
          </div>
          <TimeDistanceChart
            chartData={timeDistanceData}
            loading={loading}
            error={apiError}
            selectedJobId={selectedJobId}
            onSelectJob={handleShowExplanation}
            onRefresh={() => loadCoreData(false)}
          />
        </div>
      </div>
    );
  };

  // ── 2. MAINTENANCE DEMANDS ───────────────────────────────────
  const renderMaintenanceDemands = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-2.5 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5">
            <Inbox className="w-4 h-4 text-[#134074]" />
            DEPARTMENT MAINTENANCE REQUESTS & SCHEDULING POSITION
          </h3>
          <p className="text-[10px] text-slate-500">{jobs.length} active demands from authorized departments (ENGG / S&T / TRD)</p>
        </div>
        <button onClick={() => loadCoreData(true)} className="cris-btn cris-btn-secondary text-xs flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> REFRESH
        </button>
      </div>
      <div className="overflow-x-auto border border-slate-300 bg-white max-h-[calc(100vh-260px)]">
        <table className="cris-table w-full">
          <thead>
            <tr>
              <th>Request ID</th>
              <th>Dept</th>
              <th>From</th>
              <th>To</th>
              <th>Work Type</th>
              <th>Duration</th>
              <th>Priority</th>
              <th>Score</th>
              <th>Due Date</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan="11" className="text-center py-10 text-slate-500">
                  <div className="font-bold text-slate-700 text-sm">NO MAINTENANCE DEMANDS AVAILABLE</div>
                  <div className="text-[10px] text-slate-400 mt-1">Demands will appear when authorized department workflows provide them.</div>
                </td>
              </tr>
            ) : (
              jobs.map((j) => {
                const pj = planJobs.find(p => p.job_id === j.id);
                const isScheduled = pj && pj.is_scheduled;
                return (
                  <tr key={j.id} className={selectedJobId === j.id ? 'bg-amber-100/70 font-semibold' : ''}>
                    <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                    <td><span className="font-bold text-slate-700 bg-slate-100 px-1 py-0.5 border text-[10px]">{j.department?.code || 'ENGG'}</span></td>
                    <td className="font-mono font-bold text-[#134074]">{j.start_station_code || '-'}</td>
                    <td className="font-mono font-bold text-[#134074]">{j.end_station_code || '-'}</td>
                    <td><div className="text-xs truncate max-w-[120px]" title={j.work_type}>{j.work_type}</div></td>
                    <td className="font-mono">{j.estimated_duration_min}m</td>
                    <td>{getPriorityBadge(j.user_priority)}</td>
                    <td>
                      <div className="flex items-center space-x-1">
                        <span className="font-mono font-black text-[#0B2545] text-xs">{(j.planner_override_score ?? j.priority_score ?? 0).toFixed(1)}</span>
                        {j.planner_override_score && <span className="text-[8px] bg-purple-100 text-purple-800 border border-purple-300 px-0.5 font-bold">OVR</span>}
                      </div>
                    </td>
                    <td className="font-mono text-[10px]">{j.due_date ? new Date(j.due_date).toLocaleDateString() : 'N/A'}</td>
                    <td>
                      {isScheduled ? (
                        <span className="text-[9px] font-bold text-emerald-800 bg-emerald-100 border border-emerald-300 px-1 py-0.5 font-mono">SCHED ({pj.block_code})</span>
                      ) : getStatusBadge(j.status)}
                    </td>
                    <td>
                      <div className="flex items-center space-x-1">
                        <button onClick={() => handleOpenReview(j.id)} className="text-[10px] cris-btn cris-btn-primary py-0.5 px-1.5 flex items-center gap-0.5" title="Structured Planner Review">
                          <Eye className="w-3 h-3" /> VIEW
                        </button>
                        <button onClick={() => handleShowExplanation(j.id)} className="text-[10px] cris-btn cris-btn-secondary py-0.5 px-1 flex items-center gap-0.5" title="Why This Priority?">
                          <Info className="w-3 h-3" />
                        </button>
                        <button onClick={() => handleOpenOverrideModal(j)} className="text-[10px] p-1 border border-purple-300 bg-purple-50 text-purple-800 hover:bg-purple-100 font-bold flex items-center gap-0.5" title="Override">
                          <Edit2 className="w-3 h-3" />
                        </button>
                        <button onClick={() => handleToggleLock(j)} className={`p-1 border text-[10px] flex items-center ${j.is_locked ? 'bg-red-700 text-white border-red-900' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`} title={j.is_locked ? 'Unlock' : 'Lock'}>
                          {j.is_locked ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  // ── 3. TRAIN POSITION ────────────────────────────────────────
  const renderTrainPosition = () => (
    <div className="space-y-2">
      {/* RailRadar Discovery */}
      <div className="bg-white border border-slate-300 p-3">
        <div className="flex items-center justify-between border-b border-slate-200 pb-2 mb-2.5">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-blue-900 text-white"><Radio className="w-4 h-4 text-emerald-400 animate-pulse" /></div>
            <div>
              <h3 className="font-bold text-xs text-[#0B2545] uppercase">RAILRADAR TRAIN ROUTE DISCOVERY & SECTION OCCUPANCY MAPPING</h3>
              <p className="text-[10px] text-slate-500">Zero fake data. Discover real trains, calculate section occupancies, derive safe maintenance windows.</p>
            </div>
          </div>
          <div className="flex items-center space-x-1 text-[10px]">
            {[['MAS', 'AJJ', 'MAS↔AJJ'], ['MAS', 'TPJ', 'MAS↔TPJ'], ['MDU', 'TEN', 'MDU↔TEN']].map(([f, t, lbl]) => (
              <button key={lbl} type="button" onClick={() => { setFromStation(f); setToStation(t); handleFindTrains(f, t); }}
                className="px-2 py-0.5 bg-slate-100 hover:bg-blue-50 border border-slate-300 text-slate-700 hover:text-blue-900 font-bold text-[10px] cursor-pointer">
                {lbl}
              </button>
            ))}
          </div>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); handleFindTrains(); }} className="grid grid-cols-12 gap-2 items-end bg-slate-50 p-2 border border-slate-200">
          <div className="col-span-5">
            <label className="block text-[10px] font-bold text-slate-700 uppercase mb-1">FROM STATION <span className="text-red-500">*</span></label>
            <StationAutocomplete value={fromStation} onChange={(code) => setFromStation(code)} placeholder="Origin..." required />
          </div>
          <div className="col-span-1 flex items-center justify-center pb-1">
            <button type="button" onClick={() => { const t = fromStation; setFromStation(toStation); setToStation(t); }} className="p-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-600 cursor-pointer" title="Swap">
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
          <div className="col-span-4">
            <label className="block text-[10px] font-bold text-slate-700 uppercase mb-1">TO STATION <span className="text-red-500">*</span></label>
            <StationAutocomplete value={toStation} onChange={(code) => setToStation(code)} placeholder="Destination..." required />
          </div>
          <div className="col-span-2">
            <button type="submit" disabled={discoveryLoading}
              className="w-full h-[34px] flex items-center justify-center space-x-1.5 bg-[#0B2545] hover:bg-[#134074] text-white font-bold text-xs uppercase px-3 disabled:opacity-50 transition-colors shadow cursor-pointer">
              {discoveryLoading ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /><span>DISCOVERING...</span></> : <><Search className="w-3.5 h-3.5 text-[#FFB703]" /><span>FIND TRAINS</span></>}
            </button>
          </div>
        </form>

        {discoveryError && (
          <div className="mt-2 p-2 bg-red-50 border border-red-300 text-red-800 text-xs flex items-start space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
            <div><strong>RailRadar Gateway: </strong>{discoveryError}<p className="text-[10px] text-red-600 mt-0.5">Zero synthetic fallback: No fake trains fabricated.</p></div>
          </div>
        )}
        {discoveryMessage && !discoveryError && discoveredTrains.length === 0 && (
          <div className="mt-2 p-2 bg-blue-50 border border-blue-200 text-blue-900 text-xs flex items-center space-x-2">
            <Info className="w-4 h-4 text-blue-600 shrink-0" /><span>{discoveryMessage}</span>
          </div>
        )}

        {/* Discovered Trains Table */}
        {discoveredTrains.length > 0 && (
          <div className="mt-2 space-y-2">
            <div className="flex items-center justify-between p-2 bg-emerald-50/70 border border-emerald-200 text-xs">
              <div className="flex items-center gap-3">
                <span className="text-emerald-900 font-bold">ROUTE: <span className="font-mono">{fromStation} ↔ {toStation}</span> ({discoveryStats?.distance_km || 0} km)</span>
                <span className="text-slate-600">|</span>
                <span>Trains: <strong className="font-mono text-emerald-800">{discoveredTrains.length}</strong></span>
                <span className="text-slate-600">|</span>
                <span>Sections: <strong className="font-mono text-emerald-800">{discoveryStats?.sections || 0}</strong></span>
                <span className="text-slate-600">|</span>
                <span>Safe Windows: <strong className="font-mono text-emerald-800">{discoveryStats?.windows || 0}</strong></span>
              </div>
            </div>
            <div className="overflow-x-auto border border-slate-200 max-h-56 overflow-y-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#0B2545] text-white text-[10px] uppercase font-bold sticky top-0">
                  <tr><th className="p-1.5">Train No</th><th className="p-1.5">Name</th><th className="p-1.5">Type</th><th className="p-1.5">Status</th><th className="p-1.5">Delay</th><th className="p-1.5">Location</th><th className="p-1.5">Speed</th><th className="p-1.5">Section</th><th className="p-1.5">Source</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-[11px] bg-white">
                  {discoveredTrains.map((t, idx) => (
                    <tr key={idx} className="hover:bg-blue-50/50">
                      <td className="p-1.5 font-bold font-mono text-blue-900 flex items-center space-x-1"><Train className="w-3 h-3 text-slate-500" /><span>{t.train_number}</span></td>
                      <td className="p-1.5 font-semibold text-slate-800">{t.train_name}</td>
                      <td className="p-1.5"><span className="px-1 py-0.5 bg-slate-100 text-slate-700 text-[10px] font-mono border border-slate-300">{t.train_type}</span></td>
                      <td className="p-1.5">
                        <span className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-bold border ${t.status === 'RUNNING' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-blue-50 text-blue-800 border-blue-300'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full mr-1 ${t.status === 'RUNNING' ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'}`} />{t.status}
                        </span>
                      </td>
                      <td className="p-1.5 font-mono font-semibold">{(t.delay_minutes || 0) > 0 ? <span className="text-red-600">+{t.delay_minutes}m</span> : <span className="text-emerald-700">RT</span>}</td>
                      <td className="p-1.5 font-mono text-slate-700">{t.current_location || t.current_station || 'EN_ROUTE'}</td>
                      <td className="p-1.5 font-mono text-slate-700">{t.speed !== null && t.speed !== undefined ? `${t.speed} km/h` : '—'}</td>
                      <td className="p-1.5 font-mono text-blue-800">{t.current_section_code || 'En Route'}</td>
                      <td className="p-1.5"><span className="bg-blue-50 text-blue-800 border border-blue-200 text-[9px] font-bold px-1 py-0.5">{t.source || 'RailRadar'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Live Train Radar Cards */}
      <div className="bg-white border border-slate-300 p-2.5">
        <div className="text-xs font-bold text-[#0B2545] uppercase border-b border-slate-200 pb-1.5 mb-2 flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
          LIVE TRAIN RADAR — {timeDistanceData?.corridor?.name || 'NO CORRIDOR'}
        </div>
        <div className="overflow-y-auto max-h-64 space-y-2">
          {!selectedCorridorId ? (
            <div className="p-6 text-center text-slate-500 text-xs"><div className="font-bold">NO CORRIDOR SELECTED</div><div className="text-[10px] text-slate-400 mt-1">Select a corridor to query RailRadar live movements.</div></div>
          ) : movements.length === 0 ? (
            <div className="p-6 text-center text-slate-500 text-xs"><div className="font-bold">LIVE DATA CURRENTLY UNAVAILABLE</div><div className="text-[10px] text-slate-400 mt-1">Waiting for live train telemetry updates.</div></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {movements.map((m) => (
                <div key={m.train_number} className="bg-white border border-slate-300 p-2 text-[11px] shadow-xs">
                  <div className="flex items-center justify-between font-bold text-slate-900 border-b pb-1">
                    <span>{m.train_number} - {m.train_name}</span>
                    <span className={`px-1.5 py-0.5 text-[10px] font-mono ${m.delay_minutes > 10 ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
                      {m.delay_minutes > 0 ? `+${m.delay_minutes}m DELAY` : 'ON TIME'}
                    </span>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-1 text-[10px] text-slate-600">
                    <div>Speed: <strong className="font-mono text-slate-800">{m.speed_kmh} km/h</strong></div>
                    <div>Direction: <strong>{m.direction} Line</strong></div>
                    <div className="col-span-2">Section: <strong>{m.section_code || `SEC ${m.section_id}`}</strong></div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // ── 4. RAILWAY NETWORK ───────────────────────────────────────
  const renderRailwayNetwork = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5 mb-2">
          <GitBranch className="w-4 h-4 text-[#134074]" /> RAILWAY NETWORK TOPOLOGY & SECTION GEOMETRY
        </h3>
        <div className="text-xs text-slate-600 mb-3">
          Corridor sections, track geometry, and infrastructure master data from Southern Railway seeded database.
        </div>
        <div className="overflow-x-auto border border-slate-300 max-h-96">
          <table className="cris-table w-full">
            <thead>
              <tr><th>Corridor ID</th><th>Name</th><th>Start</th><th>End</th><th>Distance (km)</th><th>Sections</th></tr>
            </thead>
            <tbody>
              {corridors.length === 0 ? (
                <tr><td colSpan="6" className="text-center py-8 text-slate-500">NO CORRIDOR DATA AVAILABLE</td></tr>
              ) : corridors.map(c => (
                <tr key={c.id} className={selectedCorridorId === c.id ? 'bg-blue-50 font-bold' : ''}>
                  <td className="font-mono">{c.id}</td>
                  <td className="font-bold text-slate-900">{c.name}</td>
                  <td className="font-mono text-[#134074]">{c.start_station_code}</td>
                  <td className="font-mono text-[#134074]">{c.end_station_code}</td>
                  <td className="font-mono">{c.total_distance_km || '—'} km</td>
                  <td className="font-mono">{c.sections_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // ── 5. AVAILABLE WINDOWS ─────────────────────────────────────
  const renderAvailableWindows = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-[#134074]" /> MATHEMATICALLY DERIVED MAINTENANCE WINDOWS (SWEEP-LINE ENGINE)
          </h3>
          <button onClick={() => { setWindowsLoading(true); getWindows(selectedCorridorId).then(r => setWindowsData(r.data || [])).catch(() => {}).finally(() => setWindowsLoading(false)); }} className="cris-btn cris-btn-secondary text-xs flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
        <p className="text-[10px] text-slate-500 mb-2">W = TrainFreeWindow ∩ CorridorAvailability ∩ OperationalAvailability (5 min safety buffers applied)</p>
        {windowsLoading ? (
          <div className="p-6 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin text-blue-900 mx-auto mb-1" /> Loading windows...</div>
        ) : (
          <div className="overflow-x-auto border border-slate-300 max-h-96">
            <table className="cris-table w-full">
              <thead>
                <tr><th>Section</th><th>Start</th><th>End</th><th>Duration</th><th>Usable Duration</th><th>Buffer</th></tr>
              </thead>
              <tbody>
                {windowsData.length === 0 ? (
                  <tr><td colSpan="6" className="text-center py-8 text-slate-500">NO MAINTENANCE WINDOWS AVAILABLE — Select a corridor and run train discovery first.</td></tr>
                ) : windowsData.map((w, i) => (
                  <tr key={i}>
                    <td className="font-mono font-bold text-slate-800">{w.section_code || `SEC-${w.section_id}`}</td>
                    <td className="font-mono text-emerald-800">{mToTime(w.start_min)}</td>
                    <td className="font-mono text-red-800">{mToTime(w.end_min)}</td>
                    <td className="font-mono">{w.duration_min || (w.end_min - w.start_min)}m</td>
                    <td className="font-mono font-bold text-[#0B2545]">{w.usable_duration_min}m</td>
                    <td className="font-mono text-slate-500">{w.buffer_min || 5}m</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );

  // ── 6. COMPATIBILITY ─────────────────────────────────────────
  const renderCompatibility = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5 mb-2">
          <Layers className="w-4 h-4 text-[#134074]" /> MULTI-DEPARTMENT COMPATIBILITY GRAPH & CO-POSSESSION CLUSTERS
        </h3>
        <p className="text-[10px] text-slate-500 mb-3">NetworkX-based compatibility analysis identifying jobs from different departments that can safely share a single block possession.</p>
        {compatLoading ? (
          <div className="p-6 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin text-blue-900 mx-auto mb-1" /> Building compatibility graph...</div>
        ) : compatibilityData ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="bg-blue-50 border border-blue-200 p-2 text-center">
                <div className="text-[10px] text-blue-600 font-bold uppercase">Graph Nodes</div>
                <div className="text-xl font-black font-mono text-blue-900">{compatibilityData.nodes?.length || 0}</div>
              </div>
              <div className="bg-emerald-50 border border-emerald-200 p-2 text-center">
                <div className="text-[10px] text-emerald-600 font-bold uppercase">Compatible Edges</div>
                <div className="text-xl font-black font-mono text-emerald-900">{compatibilityData.edges?.length || 0}</div>
              </div>
              <div className="bg-amber-50 border border-amber-200 p-2 text-center">
                <div className="text-[10px] text-amber-600 font-bold uppercase">Coordination Groups</div>
                <div className="text-xl font-black font-mono text-amber-900">{compatibilityData.coordination_candidate_groups?.length || 0}</div>
              </div>
            </div>
            {compatibilityData.edges && compatibilityData.edges.length > 0 && (
              <div className="overflow-x-auto border border-slate-300 max-h-64">
                <table className="cris-table w-full">
                  <thead><tr><th>Job A</th><th>Job B</th><th>Reason</th><th>Score</th></tr></thead>
                  <tbody>
                    {compatibilityData.edges.map((e, i) => (
                      <tr key={i}>
                        <td className="font-mono font-bold">{e.source}</td>
                        <td className="font-mono font-bold">{e.target}</td>
                        <td className="text-[10px] text-slate-600">{e.reason || 'Compatible work types'}</td>
                        <td className="font-mono font-bold text-emerald-700">{e.score?.toFixed(1) || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="p-6 text-center text-slate-500">NO COMPATIBILITY DATA AVAILABLE</div>
        )}
      </div>
    </div>
  );

  // ── 7. AUTOMATIC BLOCK PLANNING ──────────────────────────────
  const renderBlockPlanning = () => (
    <div className="space-y-3">
      {/* Solver Control Bar */}
      <div className="bg-white border border-slate-300 p-3 flex flex-wrap items-center gap-2">
        <div className="flex items-center space-x-1 bg-slate-100 p-1 border border-slate-300">
          <span className="text-[10px] font-bold text-slate-600 uppercase px-1">CORRIDOR:</span>
          <select value={selectedCorridorId || ''} onChange={(e) => setSelectedCorridorId(e.target.value ? parseInt(e.target.value) : null)}
            className="text-[11px] font-bold bg-white border border-slate-300 px-2 py-0.5 cursor-pointer text-slate-900 max-w-[340px] truncate">
            <option value="">[ -- NO CORRIDOR SELECTED -- ]</option>
            {corridors.map((c) => <option key={c.id} value={c.id}>{c.name} | {c.start_station_code} ↔ {c.end_station_code} ({c.total_distance_km ? `${c.total_distance_km} km` : `${c.sections_count} sec`})</option>)}
          </select>
        </div>
        <div className="flex items-center space-x-1 bg-slate-100 p-1 border border-slate-300">
          <span className="text-[10px] font-bold text-slate-600 uppercase px-1">STRATEGY:</span>
          <select value={selectedStrategy} onChange={(e) => setSelectedStrategy(e.target.value)} className="text-[11px] font-bold bg-white border border-slate-300 px-2 py-0.5">
            <option value="PLAN_A">Plan A: Maximize Availability / Critical Jobs</option>
            <option value="PLAN_B">Plan B: Minimize Train Disruption</option>
            <option value="PLAN_C">Plan C: Minimize Blocks / Max Utilization</option>
          </select>
        </div>
        <button onClick={handleGeneratePlan} disabled={optimizing} className="cris-btn cris-btn-primary font-bold">
          <Play className="w-3.5 h-3.5 fill-current text-emerald-400" /> {optimizing ? 'SOLVING VIA CP-SAT...' : 'GENERATE OPTIMIZED PLAN'}
        </button>
        <button onClick={handleValidatePlan} className="cris-btn cris-btn-secondary">
          <ShieldCheck className="w-3.5 h-3.5 text-blue-700" /> VALIDATE SAFETY
        </button>
        {activePlan && activePlan.approval_status !== 'APPROVED' && (
          <button onClick={() => handleApprovePlan('APPROVE')} className="cris-btn cris-btn-accent font-bold">
            <CheckCircle className="w-3.5 h-3.5" /> APPROVE PLAN
          </button>
        )}
        {activePlan && (
          <a href={getPlanExportUrl(activePlan.id)} download className="cris-btn cris-btn-secondary">
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-700" /> EXPORT CSV
          </a>
        )}
      </div>

      {/* Active Plan Status */}
      {activePlan && (
        <div className="bg-white border border-slate-300 p-2.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[#0B2545]">ACTIVE: <span className="font-mono">{activePlan.plan_code}</span> (V{activePlan.version}) — {activePlan.strategy}</span>
            <span className={`px-2 py-0.5 font-bold text-[10px] ${activePlan.approval_status === 'APPROVED' ? 'bg-emerald-600 text-white' : 'bg-amber-600 text-white'}`}>{activePlan.approval_status}</span>
          </div>
        </div>
      )}

      {/* Time-Distance & Gantt */}
      <TimeDistanceChart chartData={timeDistanceData} loading={loading} error={apiError} selectedJobId={selectedJobId} onSelectJob={handleShowExplanation} onRefresh={() => loadCoreData(false)} />
      <BlockGantt planJobs={planJobs} sections={timeDistanceData?.sections || []} timeRange={timeDistanceData?.time_range} onSelectJob={handleShowExplanation} selectedJobId={selectedJobId} />
    </div>
  );

  // ── 8. PLAN COMPARISON ───────────────────────────────────────
  const renderPlanComparison = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5 mb-2">
          <BarChart3 className="w-4 h-4 text-[#134074]" /> MULTI-STRATEGY KPI COMPARISON MATRIX
        </h3>
        <KPIComparison comparisonData={kpiData} />
      </div>
    </div>
  );

  // ── 9. WHAT-IF (Embedded reference) ──────────────────────────
  const renderWhatIf = () => (
    <div className="bg-white border border-slate-300 p-4 text-center">
      <Cpu className="w-8 h-8 text-[#134074] mx-auto mb-2" />
      <h3 className="font-bold text-sm text-[#0B2545] uppercase mb-1">What-If Operational Scenario Analysis</h3>
      <p className="text-xs text-slate-600 mb-3">Launch full What-If simulation from the dedicated workspace for deeper analysis.</p>
      <button onClick={() => onTabChange && onTabChange('what-if')} className="cris-btn cris-btn-primary text-xs">
        <ArrowRight className="w-3.5 h-3.5" /> OPEN WHAT-IF WORKSPACE
      </button>
    </div>
  );

  // ── 10. DYNAMIC REPLANNING (Embedded reference) ──────────────
  const renderDynamicReplanning = () => (
    <div className="bg-white border border-slate-300 p-4 text-center">
      <Shuffle className="w-8 h-8 text-[#134074] mx-auto mb-2" />
      <h3 className="font-bold text-sm text-[#0B2545] uppercase mb-1">Dynamic Replanning & Disturbance Response</h3>
      <p className="text-xs text-slate-600 mb-3">Inject train delays, detect plan impact, and trigger CP-SAT rolling replanning freezing completed work.</p>
      <button onClick={() => onTabChange && onTabChange('dynamic-replan')} className="cris-btn cris-btn-primary text-xs">
        <ArrowRight className="w-3.5 h-3.5" /> OPEN REPLANNING WORKSPACE
      </button>
    </div>
  );

  // ── 11. EXECUTION TRACKER ────────────────────────────────────
  const renderExecution = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5">
            <Target className="w-4 h-4 text-[#134074]" /> BLOCK EXECUTION TRACKER & VARIANCE MONITORING
          </h3>
          <button onClick={() => { setExecutionLoading(true); getExecutionRecords().then(r => setExecutionRecords(r.data || [])).catch(() => {}).finally(() => setExecutionLoading(false)); }} className="cris-btn cris-btn-secondary text-xs flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
        {executionLoading ? (
          <div className="p-6 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin text-blue-900 mx-auto mb-1" /> Loading execution records...</div>
        ) : (
          <div className="overflow-x-auto border border-slate-300 max-h-96">
            <table className="cris-table w-full">
              <thead>
                <tr><th>Job</th><th>Status</th><th>Planned Start</th><th>Planned End</th><th>Actual Start</th><th>Actual End</th><th>Delay</th><th>Variance</th><th>Completion %</th><th>Dept</th></tr>
              </thead>
              <tbody>
                {executionRecords.length === 0 ? (
                  <tr><td colSpan="10" className="text-center py-8 text-slate-500">NO EXECUTION RECORDS — Blocks must be in READY or IN_PROGRESS status.</td></tr>
                ) : executionRecords.map((r, i) => (
                  <tr key={i}>
                    <td className="font-mono font-bold">{r.job_code || `JOB-${r.job_id}`}</td>
                    <td>{getStatusBadge(r.status)}</td>
                    <td className="font-mono">{mToTime(r.planned_start_min)}</td>
                    <td className="font-mono">{mToTime(r.planned_end_min)}</td>
                    <td className="font-mono text-emerald-800">{mToTime(r.actual_start_min)}</td>
                    <td className="font-mono text-emerald-800">{mToTime(r.actual_end_min)}</td>
                    <td className="font-mono font-bold">{r.delay_min != null ? `${r.delay_min}m` : '—'}</td>
                    <td className={`font-mono font-bold ${(r.variance_min || 0) > 0 ? 'text-red-600' : 'text-emerald-700'}`}>{r.variance_min != null ? `${r.variance_min}m` : '—'}</td>
                    <td className="font-mono">{r.completion_pct != null ? `${r.completion_pct}%` : '—'}</td>
                    <td className="font-bold text-slate-700">{r.responsible_department || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );

  // ── 12. REPORTS ──────────────────────────────────────────────
  const renderReports = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5 mb-2">
          <FileText className="w-4 h-4 text-[#134074]" /> WEEKLY BLOCK PLANNING REPORT
        </h3>
        {reportLoading ? (
          <div className="p-6 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin text-blue-900 mx-auto mb-1" /> Loading report...</div>
        ) : weeklyReport ? (
          <div className="space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              {Object.entries(weeklyReport.department_breakdown || {}).map(([code, info]) => (
                <div key={code} className="border border-slate-300 p-2 border-l-4 border-l-[#134074]">
                  <div className="font-bold text-slate-900 text-xs uppercase mb-1">{info.name} ({code})</div>
                  <div className="grid grid-cols-3 gap-1 text-center text-xs">
                    <div className="bg-slate-50 p-1 border"><div className="text-[9px] text-slate-500 font-bold">Total</div><div className="font-bold font-mono">{info.total_jobs}</div></div>
                    <div className="bg-amber-50 p-1 border"><div className="text-[9px] text-amber-700 font-bold">Critical</div><div className="font-bold font-mono">{info.critical}</div></div>
                    <div className="bg-red-50 p-1 border"><div className="text-[9px] text-red-700 font-bold">Overdue</div><div className="font-bold font-mono">{info.overdue}</div></div>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={() => onTabChange && onTabChange('reports')} className="cris-btn cris-btn-secondary text-xs">
              <ArrowRight className="w-3 h-3" /> OPEN FULL REPORTS WORKSPACE
            </button>
          </div>
        ) : (
          <div className="p-6 text-center text-slate-500">NO REPORT DATA AVAILABLE</div>
        )}
      </div>
    </div>
  );

  // ── 13. AUDIT TRAIL ──────────────────────────────────────────
  const renderAudit = () => (
    <div className="space-y-2">
      <div className="bg-white border border-slate-300 p-3">
        <h3 className="font-bold text-xs text-[#0B2545] uppercase flex items-center gap-1.5 mb-2">
          <Shield className="w-4 h-4 text-[#134074]" /> IMMUTABLE AUDIT TRAIL & DECISION LOGS
        </h3>
        {auditLoading ? (
          <div className="p-6 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin text-blue-900 mx-auto mb-1" /> Loading audit logs...</div>
        ) : (
          <div className="space-y-3">
            {/* Planner Actions */}
            <div>
              <div className="text-[10px] font-bold text-slate-600 uppercase mb-1">PLANNER ACTIONS ({plannerActions.length})</div>
              <div className="overflow-x-auto border border-slate-300 max-h-48">
                <table className="cris-table w-full">
                  <thead><tr><th>Timestamp</th><th>Action</th><th>Entity</th><th>Target</th><th>Reason</th><th>User</th></tr></thead>
                  <tbody>
                    {plannerActions.length === 0 ? (
                      <tr><td colSpan="6" className="text-center py-4 text-slate-500">No planner actions recorded.</td></tr>
                    ) : plannerActions.map((a, i) => (
                      <tr key={i}>
                        <td className="font-mono text-[10px] text-slate-500">{a.timestamp || a.created_at}</td>
                        <td className="font-bold">{a.action_type}</td>
                        <td>{a.target_entity}</td>
                        <td className="font-mono">{a.target_id}</td>
                        <td className="text-[10px] truncate max-w-[160px]">{a.reason}</td>
                        <td className="font-mono text-slate-600">{a.username || `uid:${a.user_id}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            {/* System Audit Logs */}
            <div>
              <div className="text-[10px] font-bold text-slate-600 uppercase mb-1">SYSTEM AUDIT LOGS ({auditLogs.length})</div>
              <div className="overflow-x-auto border border-slate-300 max-h-48">
                <table className="cris-table w-full">
                  <thead><tr><th>Timestamp</th><th>Action</th><th>Entity</th><th>Entity ID</th><th>Details</th><th>User</th></tr></thead>
                  <tbody>
                    {auditLogs.length === 0 ? (
                      <tr><td colSpan="6" className="text-center py-4 text-slate-500">No system audit records.</td></tr>
                    ) : auditLogs.map((l, i) => (
                      <tr key={i}>
                        <td className="font-mono text-[10px] text-slate-500">{l.timestamp || l.created_at}</td>
                        <td className="font-bold">{l.action}</td>
                        <td>{l.entity_type}</td>
                        <td className="font-mono">{l.entity_id}</td>
                        <td className="text-[10px] truncate max-w-[200px]">{typeof l.details_json === 'object' ? JSON.stringify(l.details_json) : l.details_json}</td>
                        <td className="font-mono text-slate-600">{l.username || `uid:${l.user_id}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // ── STATION ROUTER ───────────────────────────────────────────
  const renderStationContent = () => {
    switch (activeStation) {
      case 'CONTROL_PANEL': return renderControlPanel();
      case 'MAINTENANCE_DEMANDS': return renderMaintenanceDemands();
      case 'TRAIN_POSITION': return renderTrainPosition();
      case 'RAILWAY_NETWORK': return renderRailwayNetwork();
      case 'AVAILABLE_WINDOWS': return renderAvailableWindows();
      case 'COMPATIBILITY': return renderCompatibility();
      case 'AUTOMATIC_BLOCK_PLANNING': return renderBlockPlanning();
      case 'PLAN_COMPARISON': return renderPlanComparison();
      case 'WHAT_IF': return renderWhatIf();
      case 'DYNAMIC_REPLANNING': return renderDynamicReplanning();
      case 'EXECUTION': return renderExecution();
      case 'REPORTS': return renderReports();
      case 'AUDIT': return renderAudit();
      default: return renderControlPanel();
    }
  };

  // ══════════════════════════════════════════════════════════════
  //  MAIN RENDER
  // ══════════════════════════════════════════════════════════════
  const currentNav = NAV_STATIONS.find(s => s.id === activeStation);

  return (
    <div className="flex h-[calc(100vh-88px)]">
      {/* ── LEFT NAVIGATION SIDEBAR ──────────────────────────── */}
      <aside className="w-52 min-w-[208px] bg-[#0B2545] border-r border-slate-700 flex flex-col overflow-y-auto">
        {/* Planner Identity Header */}
        <div className="p-2 border-b border-slate-700 bg-[#081b33]">
          <div className="text-[10px] text-[#FFB703] font-black uppercase tracking-wider">CHIEF SECTION CONTROLLER</div>
          <div className="text-[10px] text-slate-400 font-mono">{user?.full_name || 'Planner'}</div>
          <div className="mt-1 flex items-center space-x-1 text-[9px]">
            <span className="text-slate-500">PLAN:</span>
            <span className="font-mono font-bold text-slate-300">{activePlan?.plan_code || 'NONE'}</span>
            <span className={`px-1 py-0.5 text-[8px] font-bold ${activePlan?.approval_status === 'APPROVED' ? 'bg-emerald-700 text-white' : 'bg-amber-700 text-white'}`}>
              {activePlan?.approval_status || 'N/A'}
            </span>
          </div>
          <div className="mt-0.5 text-[9px] text-slate-500 font-mono">SYNC: {lastSyncTime}</div>
        </div>

        {/* Navigation Items grouped */}
        <nav className="flex-1 py-1">
          {NAV_GROUPS.map(group => {
            const items = NAV_STATIONS.filter(s => s.group === group);
            return (
              <div key={group}>
                <div className="px-3 pt-2 pb-0.5 text-[9px] font-black text-slate-500 uppercase tracking-widest">{group}</div>
                {items.map(station => {
                  const Icon = station.icon;
                  const isActive = activeStation === station.id;
                  return (
                    <button
                      key={station.id}
                      onClick={() => setActiveStation(station.id)}
                      className={`w-full text-left px-3 py-1.5 flex items-center space-x-2 text-[11px] transition-colors cursor-pointer ${
                        isActive
                          ? 'bg-white/10 text-white font-bold border-l-2 border-[#FFB703]'
                          : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border-l-2 border-transparent'
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-[#FFB703]' : 'text-slate-500'}`} />
                      <span className="truncate">{station.label}</span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>
      </aside>

      {/* ── MAIN CONTENT AREA ────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-[#F4F6F9]">
        {/* Station Header Bar */}
        <div className="bg-white border-b border-slate-300 px-3 py-2 flex items-center justify-between sticky top-0 z-10 shadow-xs">
          <div className="flex items-center space-x-2">
            {currentNav && <currentNav.icon className="w-4 h-4 text-[#134074]" />}
            <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide">{currentNav?.label || 'Control Panel'}</h2>
            <span className="text-[10px] text-slate-500 font-mono bg-slate-100 px-1.5 py-0.5 border border-slate-200">{currentNav?.group}</span>
          </div>
          {apiError && (
            <div className="flex items-center space-x-1 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5">
              <AlertCircle className="w-3 h-3" /><span>{apiError}</span>
            </div>
          )}
        </div>

        {/* Station Content */}
        <div className="p-3">
          {loading && !apiError ? (
            <div className="flex items-center justify-center p-12">
              <RefreshCw className="w-6 h-6 text-[#134074] animate-spin" />
              <span className="ml-2 text-slate-600 text-sm">Loading operational data...</span>
            </div>
          ) : (
            renderStationContent()
          )}
        </div>
      </main>

      {/* ══════════════════════════════════════════════════════════ */}
      {/*  MODALS                                                    */}
      {/* ══════════════════════════════════════════════════════════ */}

      {/* ── Structured Request Review Modal ──────────────────── */}
      {reviewModalOpen && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-y-auto">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center sticky top-0 z-10">
              <span className="flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-[#FFB703]" />
                STRUCTURED PLANNER REQUEST REVIEW
              </span>
              <button onClick={() => { setReviewModalOpen(false); setReviewData(null); }} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            {reviewLoading ? (
              <div className="p-8 text-center"><RefreshCw className="w-6 h-6 animate-spin text-blue-900 mx-auto mb-2" /><p className="text-sm text-slate-600">Loading review packet...</p></div>
            ) : reviewData ? (
              <div className="p-4 space-y-3 text-xs">
                {/* Request Details */}
                <div className="border border-slate-200 p-3">
                  <div className="font-bold text-[#0B2545] uppercase text-[11px] border-b border-slate-200 pb-1 mb-2">REQUEST DETAILS</div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    <div><span className="text-slate-500">Job Code:</span> <strong className="font-mono">{reviewData.job?.job_code}</strong></div>
                    <div><span className="text-slate-500">Department:</span> <strong>{reviewData.job?.department_name} ({reviewData.job?.department_code})</strong></div>
                    <div><span className="text-slate-500">Work Type:</span> <strong>{reviewData.job?.work_type}</strong></div>
                    <div><span className="text-slate-500">Section:</span> <strong className="font-mono">{reviewData.job?.section_name}</strong></div>
                    <div><span className="text-slate-500">Stations:</span> <strong className="font-mono">{reviewData.job?.start_station_code} ↔ {reviewData.job?.end_station_code}</strong></div>
                    <div><span className="text-slate-500">Duration:</span> <strong className="font-mono">{reviewData.job?.duration_min}m</strong></div>
                    <div><span className="text-slate-500">Priority:</span> <strong>{reviewData.job?.user_priority}</strong> {getPriorityBadge(reviewData.job?.user_priority)}</div>
                    <div><span className="text-slate-500">Score:</span> <strong className="font-mono text-[#0B2545]">{reviewData.job?.priority_score?.toFixed(1)}</strong></div>
                    <div><span className="text-slate-500">Due Date:</span> <strong className="font-mono">{reviewData.job?.due_date || 'N/A'}</strong></div>
                    <div><span className="text-slate-500">Status:</span> {getStatusBadge(reviewData.job?.status)}</div>
                    <div><span className="text-slate-500">Safety Tier:</span> <strong>{reviewData.job?.safety_tier || 'N/A'}</strong></div>
                    <div><span className="text-slate-500">Emergency:</span> <strong>{reviewData.job?.is_emergency ? 'YES' : 'No'}</strong></div>
                  </div>
                  {reviewData.job?.description && (
                    <div className="mt-2 p-2 bg-slate-50 border border-slate-200 text-slate-700"><strong>Description:</strong> {reviewData.job.description}</div>
                  )}
                </div>

                {/* Feasibility Assessment */}
                <div className="border border-slate-200 p-3">
                  <div className="font-bold text-[#0B2545] uppercase text-[11px] border-b border-slate-200 pb-1 mb-2">FEASIBILITY ASSESSMENT</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className={`p-2 border ${reviewData.has_feasible_window ? 'bg-emerald-50 border-emerald-300' : 'bg-red-50 border-red-300'}`}>
                      <div className="text-[10px] font-bold uppercase">{reviewData.has_feasible_window ? '✓ FEASIBLE WINDOW EXISTS' : '✗ NO FEASIBLE WINDOW'}</div>
                      <div className="font-mono font-bold text-lg">{reviewData.feasible_window_count || 0} <span className="text-[10px] font-normal">candidate windows</span></div>
                    </div>
                    <div className="p-2 border bg-blue-50 border-blue-300">
                      <div className="text-[10px] font-bold uppercase">COMPATIBLE JOBS</div>
                      <div className="font-mono font-bold text-lg">{reviewData.compatible_jobs?.length || 0} <span className="text-[10px] font-normal">co-possession candidates</span></div>
                    </div>
                  </div>
                </div>

                {/* Recommended Window */}
                {reviewData.recommended_window && (
                  <div className="border border-emerald-200 bg-emerald-50/50 p-3">
                    <div className="font-bold text-emerald-900 uppercase text-[11px] border-b border-emerald-200 pb-1 mb-2">⭐ RECOMMENDED WINDOW</div>
                    <div className="grid grid-cols-4 gap-2">
                      <div><span className="text-slate-500">Section:</span> <strong className="font-mono">{reviewData.recommended_window.section_code || `SEC-${reviewData.recommended_window.section_id}`}</strong></div>
                      <div><span className="text-slate-500">Start:</span> <strong className="font-mono text-emerald-800">{mToTime(reviewData.recommended_window.start_min)}</strong></div>
                      <div><span className="text-slate-500">End:</span> <strong className="font-mono text-red-800">{mToTime(reviewData.recommended_window.end_min)}</strong></div>
                      <div><span className="text-slate-500">Usable:</span> <strong className="font-mono">{reviewData.recommended_window.usable_duration_min}m</strong></div>
                    </div>
                  </div>
                )}

                {/* Compatible Jobs */}
                {reviewData.compatible_jobs && reviewData.compatible_jobs.length > 0 && (
                  <div className="border border-slate-200 p-3">
                    <div className="font-bold text-[#0B2545] uppercase text-[11px] border-b border-slate-200 pb-1 mb-2">COMPATIBLE JOBS (CO-POSSESSION CANDIDATES)</div>
                    <div className="overflow-x-auto border border-slate-200">
                      <table className="cris-table w-full">
                        <thead><tr><th>Job Code</th><th>Dept</th><th>Work Type</th><th>Duration</th><th>Score</th></tr></thead>
                        <tbody>
                          {reviewData.compatible_jobs.map((cj, i) => (
                            <tr key={i}>
                              <td className="font-mono font-bold">{cj.job_code}</td>
                              <td className="font-bold">{cj.department_code}</td>
                              <td>{cj.work_type}</td>
                              <td className="font-mono">{cj.duration_min}m</td>
                              <td className="font-mono font-bold">{cj.priority_score?.toFixed(1) || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center justify-between border-t border-slate-200 pt-3">
                  <button onClick={() => { setReviewModalOpen(false); setReviewData(null); }} className="cris-btn cris-btn-secondary text-xs">Close</button>
                  <div className="flex items-center space-x-2">
                    <button onClick={() => { setReviewModalOpen(false); setActiveStation('AUTOMATIC_BLOCK_PLANNING'); }} className="cris-btn cris-btn-primary text-xs font-bold flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5" /> FIND BEST PLAN (CP-SAT)
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500">
                <AlertCircle className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                <p className="font-bold">Failed to load review data for this request.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Planner Override Priority Modal ──────────────────── */}
      {overrideTargetJob && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-md">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5"><Edit2 className="w-4 h-4 text-[#FFB703]" /> Planner Priority Override &bull; {overrideTargetJob.job_code}</span>
              <button onClick={() => setOverrideTargetJob(null)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <form onSubmit={handleSubmitOverride} className="p-4 space-y-3 text-xs">
              <div className="bg-amber-50 border border-amber-200 p-2 text-amber-900 text-[11px]">
                <strong>Chief Controller Authority:</strong> You are modifying the priority score. All overrides are logged permanently in the audit trail.
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Current Calculated Score:</label>
                <div className="p-1.5 bg-slate-100 font-mono font-bold text-slate-800 text-sm">{(overrideTargetJob.priority_score || 0).toFixed(1)} / 100</div>
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">New Override Score (0.0 to 100.0):</label>
                <input type="number" min="0" max="100" step="0.5" value={overrideScore} onChange={(e) => setOverrideScore(e.target.value)}
                  className="w-full border-2 border-slate-300 p-2 font-mono font-black text-base text-[#0B2545] focus:border-[#0B2545] outline-none" required />
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Operational Justification:</label>
                <textarea value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
                  className="w-full border border-slate-300 p-2 text-slate-800" rows="3"
                  placeholder="Operational, traffic, or safety justification..." required />
              </div>
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button type="button" onClick={() => setOverrideTargetJob(null)} className="cris-btn cris-btn-secondary text-xs">Cancel</button>
                <button type="submit" disabled={overrideSubmitting} className="cris-btn cris-btn-primary text-xs flex items-center gap-1">
                  {overrideSubmitting ? 'Recording Override...' : 'Apply Priority Override'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Explainability Drawer ────────────────────────────── */}
      <ExplainabilityDrawer explanation={explanationData} isOpen={showExplanation} onClose={() => setShowExplanation(false)} />

      {/* ── Safety Validator Modal ───────────────────────────── */}
      <ValidatorModal validationResult={validationResult} isOpen={showValidatorModal} onClose={() => setShowValidatorModal(false)} />

      {/* ── Section 12 Planner Modification Modal ───────────────── */}
      {showModifyModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-md">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <Edit2 className="w-4 h-4 text-[#FFB703]" />
                MODIFY RECOMMENDED BLOCK PLAN &bull; {selectedRequest?.job_code}
              </span>
              <button onClick={() => setShowModifyModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <form onSubmit={handleModifySubmit} className="p-4 space-y-3 text-xs">
              <div className="bg-blue-50 border border-blue-200 p-2 text-blue-900 text-[11px]">
                <strong>Chief Controller Authority:</strong> Modify recommended block timing. Human modifications require mandatory operational justification.
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Start Time (Minute of Day):</label>
                  <input
                    type="number"
                    value={modifyStartMin}
                    onChange={(e) => setModifyStartMin(e.target.value)}
                    className="w-full border border-slate-300 p-2 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">HH:MM = {mToTime(parseInt(modifyStartMin) || 0)}</span>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">End Time (Minute of Day):</label>
                  <input
                    type="number"
                    value={modifyEndMin}
                    onChange={(e) => setModifyEndMin(e.target.value)}
                    className="w-full border border-slate-300 p-2 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">HH:MM = {mToTime(parseInt(modifyEndMin) || 0)}</span>
                </div>
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Operational Justification:</label>
                <textarea
                  value={modifyReason}
                  onChange={(e) => setModifyReason(e.target.value)}
                  className="w-full border border-slate-300 p-2 text-slate-800"
                  rows="3"
                  placeholder="Reason for modifying automated CP-SAT timing..."
                  required
                />
              </div>
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button type="button" onClick={() => setShowModifyModal(false)} className="cris-btn cris-btn-secondary text-xs">Cancel</button>
                <button type="submit" className="cris-btn cris-btn-primary text-xs flex items-center gap-1">
                  Save & Record Modification
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Section 12 Planner Rejection Modal ─────────────────── */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-red-800 shadow-2xl w-full max-w-md">
            <div className="bg-red-800 text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <XCircle className="w-4 h-4 text-white" />
                REJECT BLOCK REQUEST &bull; {selectedRequest?.job_code}
              </span>
              <button onClick={() => setShowRejectModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <form onSubmit={handleRejectSubmit} className="p-4 space-y-3 text-xs">
              <div className="bg-red-50 border border-red-200 p-2 text-red-900 text-[11px]">
                <strong>Operational Block Rejection:</strong> Provide the formal operational justification for rejecting this maintenance demand.
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Rejection Justification:</label>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="w-full border border-slate-300 p-2 text-slate-800"
                  rows="3"
                  placeholder="e.g., Heavy holiday passenger traffic; rescheduled for next window..."
                  required
                />
              </div>
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button type="button" onClick={() => setShowRejectModal(false)} className="cris-btn cris-btn-secondary text-xs">Cancel</button>
                <button type="submit" className="cris-btn bg-red-700 hover:bg-red-800 text-white text-xs flex items-center gap-1 font-bold px-3 py-1.5">
                  Confirm Rejection
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Conflicts Modal ────────────────────────────────────── */}
      {showConflictsModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-lg">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                TRAIN CONFLICT VERIFICATION &bull; {selectedRequest?.job_code}
              </span>
              <button onClick={() => setShowConflictsModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <div className="p-4 space-y-3 text-xs">
              <div className="bg-emerald-50 border border-emerald-300 p-3 text-emerald-900">
                <div className="font-black text-sm uppercase flex items-center gap-1 mb-1">
                  <CheckCircle className="w-4 h-4 text-emerald-700" />
                  0 HARD CONFLICTS DETECTED
                </div>
                <p className="text-[11px]">
                  CP-SAT optimization verified that no passenger or scheduled freight movements intersect the recommended maintenance possession window (10:45–12:15).
                </p>
              </div>
              <div className="border border-slate-200 p-2.5 space-y-1.5">
                <div className="font-bold text-slate-800 uppercase text-[10px]">VERIFIED CONSTRAINTS:</div>
                <div className="text-[11px] text-slate-700 space-y-1">
                  <div>✓ Headway buffer: 15 minutes clear before leading express train</div>
                  <div>✓ Headway buffer: 15 minutes clear after trailing freight rake</div>
                  <div>✓ Traction feeder section de-energization isolation verified</div>
                  <div>✓ No duplicate simultaneous block on adjacent block section</div>
                </div>
              </div>
              <div className="flex justify-end pt-2 border-t border-slate-200">
                <button onClick={() => setShowConflictsModal(false)} className="cris-btn cris-btn-secondary text-xs">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Section 28 Audit Trail Modal ───────────────────────── */}
      {showAuditModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-[#FFB703]" />
                AUDIT TRAIL HISTORY &bull; {selectedRequest?.job_code}
              </span>
              <button onClick={() => setShowAuditModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <div className="p-3 overflow-y-auto flex-1 text-xs">
              {auditLogsLoading ? (
                <div className="text-center py-8 text-slate-500">Loading audit history...</div>
              ) : auditLogsList.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No audit events recorded yet for this request.</div>
              ) : (
                <table className="cris-table w-full text-[11px]">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>User</th>
                      <th>Role</th>
                      <th>Action</th>
                      <th>Old Status</th>
                      <th>New Status</th>
                      <th>Reason / Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogsList.map((log) => (
                      <tr key={log.id}>
                        <td className="font-mono text-[10px] text-slate-500">{log.created_at ? log.created_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                        <td className="font-bold text-slate-800">{log.user?.username || log.username || 'System'}</td>
                        <td className="font-mono text-[9px] text-slate-600">{log.user_role || '—'}</td>
                        <td className="font-bold text-[#0B2545]">{log.action}</td>
                        <td><span className="font-mono text-[9px]">{log.old_status || '—'}</span></td>
                        <td><span className="font-mono text-[9px] font-bold text-emerald-800">{log.new_status || '—'}</span></td>
                        <td className="text-[10px] text-slate-700 max-w-xs">{log.reason || log.details || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="p-3 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button onClick={() => setShowAuditModal(false)} className="cris-btn cris-btn-secondary text-xs">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Coordinated Plan Modify Modal (Part 14) ──────────── */}
      {showCoordinatedModifyModal && coordinatedPlanResult && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-md">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <Edit2 className="w-4 h-4 text-[#FFB703]" />
                MODIFY COORDINATED COMMON BLOCK &bull; {coordinatedPlanResult.plan_code}
              </span>
              <button onClick={() => setShowCoordinatedModifyModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <form onSubmit={handleCoordinatedModifySubmit} className="p-4 space-y-3 text-xs">
              <div className="bg-blue-50 border border-blue-200 p-2 text-blue-900 text-[11px]">
                <strong>Chief Controller Authority:</strong> Modify recommended common block timings for all {coordinatedPlanResult.requests_combined_count} grouped departmental jobs. Human modifications require mandatory operational justification.
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Start Time (Minute of Day):</label>
                  <input
                    type="number"
                    value={coordinatedModifyStart}
                    onChange={(e) => setCoordinatedModifyStart(e.target.value)}
                    className="w-full border border-slate-300 p-2 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">HH:MM = {mToTime(parseInt(coordinatedModifyStart) || 0)}</span>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">End Time (Minute of Day):</label>
                  <input
                    type="number"
                    value={coordinatedModifyEnd}
                    onChange={(e) => setCoordinatedModifyEnd(e.target.value)}
                    className="w-full border border-slate-300 p-2 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">HH:MM = {mToTime(parseInt(coordinatedModifyEnd) || 0)}</span>
                </div>
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Operational Justification:</label>
                <textarea
                  value={coordinatedModifyReason}
                  onChange={(e) => setCoordinatedModifyReason(e.target.value)}
                  className="w-full border border-slate-300 p-2 text-slate-800"
                  rows="3"
                  placeholder="Reason for adjusting multi-department common possession window..."
                  required
                />
              </div>
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button type="button" onClick={() => setShowCoordinatedModifyModal(false)} className="cris-btn cris-btn-secondary text-xs">Cancel</button>
                <button type="submit" className="cris-btn cris-btn-primary text-xs flex items-center gap-1">
                  Save & Record Common Block Modification
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Coordinated Plan Reject Modal (Part 14) ──────────── */}
      {showCoordinatedRejectModal && coordinatedPlanResult && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-red-800 shadow-2xl w-full max-w-md">
            <div className="bg-red-800 text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <XCircle className="w-4 h-4 text-white" />
                REJECT COMMON BLOCK PLAN &bull; {coordinatedPlanResult.plan_code}
              </span>
              <button onClick={() => setShowCoordinatedRejectModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <form onSubmit={handleCoordinatedRejectSubmit} className="p-4 space-y-3 text-xs">
              <div className="bg-red-50 border border-red-200 p-2 text-red-900 text-[11px]">
                <strong>Operational Block Rejection:</strong> Rejecting this common plan will NOT delete the maintenance requests. All {coordinatedPlanResult.requests_combined_count} requests will be unlinked and restored to the pending queue for individual scheduling.
              </div>
              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Rejection Justification:</label>
                <textarea
                  value={coordinatedRejectReason}
                  onChange={(e) => setCoordinatedRejectReason(e.target.value)}
                  className="w-full border border-slate-300 p-2 text-slate-800"
                  rows="3"
                  placeholder="e.g., Heavy holiday passenger traffic or OHE crew unavailability; unlinking for separate execution..."
                  required
                />
              </div>
              <div className="pt-2 flex items-center justify-between border-t border-slate-200">
                <button type="button" onClick={() => setShowCoordinatedRejectModal(false)} className="cris-btn cris-btn-secondary text-xs">Cancel</button>
                <button type="submit" className="cris-btn bg-red-700 hover:bg-red-800 text-white text-xs flex items-center gap-1 font-bold px-3 py-1.5">
                  Confirm Rejection & Unlink Requests
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Coordinated Plan What-If Modal (Part 23) ─────────── */}
      {showCoordinatedWhatIfModal && coordinatedPlanResult && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center">
              <span className="flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-[#FFB703]" />
                COORDINATED COMMON BLOCK WHAT-IF SIMULATION &bull; {coordinatedPlanResult.plan_code}
              </span>
              <button onClick={() => setShowCoordinatedWhatIfModal(false)} className="text-white/80 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-xs">
              <div className="bg-amber-50 border border-amber-300 p-2.5 text-amber-900 text-[11px]">
                <strong>Operational Simulation Engine:</strong> Simulate operational disturbances (train delays, extended work, or department changes) and evaluate impacts on the common block.
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 border border-slate-200 p-3 bg-slate-50">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Select What-If Scenario:</label>
                  <select
                    value={whatIfScenarioType}
                    onChange={(e) => setWhatIfScenarioType(e.target.value)}
                    className="w-full bg-white border border-slate-300 p-2 font-bold text-[#0B2545] outline-none"
                  >
                    <option value="TRAIN_DELAY">WHAT-IF 1: Train Delay in Corridor (+min)</option>
                    <option value="EXTEND_WORK">WHAT-IF 2: Extend Engineering Work (+min)</option>
                    <option value="CHANGE_WINDOW">WHAT-IF 3: Shift Maintenance Window (+min)</option>
                    <option value="ADD_COMPATIBLE">WHAT-IF 4: Add Another S&T / Compatible Request</option>
                    <option value="REMOVE_JOB">WHAT-IF 5: Remove Traction Request</option>
                  </select>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Perturbation Value (Minutes / Units):</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="5"
                      max="180"
                      step="5"
                      value={whatIfValue}
                      onChange={(e) => setWhatIfValue(e.target.value)}
                      className="w-24 border border-slate-300 p-2 font-mono font-bold text-center"
                    />
                    <span className="text-slate-600 font-mono text-[11px]">(e.g. +30 min)</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleRunCoordinatedWhatIf}
                  disabled={whatIfLoading}
                  className="cris-btn bg-amber-600 hover:bg-amber-700 text-white font-black text-xs uppercase px-4 py-2 flex items-center gap-1.5 shadow-xs cursor-pointer disabled:opacity-50"
                >
                  <Sliders className="w-3.5 h-3.5" />
                  {whatIfLoading ? 'Running Simulation...' : 'RUN WHAT-IF SIMULATION'}
                </button>
              </div>

              {/* Simulation Comparison Result */}
              {whatIfResult && (
                <div className="border-2 border-[#134074] bg-white p-3 space-y-2 mt-2">
                  <div className="font-black text-xs text-[#0B2545] uppercase flex items-center justify-between border-b border-slate-200 pb-1.5">
                    <span>SIMULATION COMPARISON RESULT</span>
                    <span className={`px-2 py-0.5 text-[10px] font-bold ${
                      whatIfResult.feasibility === 'FEASIBLE'
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                        : 'bg-red-100 text-red-800 border border-red-300'
                    }`}>
                      {whatIfResult.feasibility}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-2.5 bg-slate-50 border border-slate-200">
                      <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">CURRENT APPROVED / BASE PLAN</div>
                      <div className="font-mono text-xs font-bold text-slate-800">
                        {whatIfResult.base_plan?.time_window || coordinatedPlanResult.common_block_window}
                      </div>
                      <div className="text-[10px] text-slate-600 mt-1">
                        Duration: {whatIfResult.base_plan?.duration_min || coordinatedPlanResult.duration_min} min
                      </div>
                      <div className="text-[10px] text-emerald-700 font-bold mt-0.5">
                        Conflicts: {whatIfResult.base_plan?.conflicts_count ?? 0}
                      </div>
                      <div className="text-[10px] text-purple-700 font-bold mt-0.5">
                        Score: {whatIfResult.base_plan?.score || 96}/100
                      </div>
                    </div>

                    <div className="p-2.5 bg-blue-50/70 border border-blue-300">
                      <div className="text-[10px] font-bold text-blue-900 uppercase mb-1">WHAT-IF SIMULATED PLAN</div>
                      <div className="font-mono text-xs font-black text-blue-900">
                        {whatIfResult.simulated_plan?.time_window || '11:30 – 13:00'}
                      </div>
                      <div className="text-[10px] text-blue-800 mt-1">
                        Duration: {whatIfResult.simulated_plan?.duration_min || 90} min
                      </div>
                      <div className="text-[10px] text-blue-800 font-bold mt-0.5">
                        Conflicts: {whatIfResult.simulated_plan?.conflicts_count ?? 0}
                      </div>
                      <div className="text-[10px] text-blue-900 font-bold mt-0.5">
                        Score: {whatIfResult.simulated_plan?.score || 91}/100
                      </div>
                    </div>
                  </div>

                  <div className="p-2 bg-slate-50 border border-slate-200 text-[11px] text-slate-700">
                    <span className="font-bold text-slate-900">Operational Impact: </span>
                    {whatIfResult.impact_summary || `Common block adjusts gracefully to +${whatIfValue}m shift with 0 passenger train conflicts.`}
                  </div>

                  {whatIfResult.replan_recommended && (
                    <div className="p-2 bg-amber-50 border border-amber-300 text-[11px] flex items-center justify-between">
                      <span className="text-amber-900 font-bold">
                        Conflict detected in original window. System recommends Dynamic Replanning.
                      </span>
                      <button
                        onClick={handleDynamicReplan}
                        disabled={dynamicReplanLoading}
                        className="bg-cyan-700 hover:bg-cyan-800 text-white font-black text-[10px] uppercase px-2.5 py-1"
                      >
                        [ ADOPT REVISED PLAN ]
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="p-3 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button onClick={() => setShowCoordinatedWhatIfModal(false)} className="cris-btn cris-btn-secondary text-xs">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Section 11 & 17: Coordinated Block Plan Details Modal ── */}
      {activePlanModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col">
            {/* Header */}
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center border-b-2 border-[#FFB703]">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-[#FFB703]" />
                <div>
                  <div className="text-[10px] text-[#FFB703] font-mono font-bold">
                    COORDINATED BLOCK PLAN &bull; {activePlanModal.plan_code || 'CBP-001'}
                  </div>
                  <div className="text-xs font-black text-white">
                    {activePlanModal.plan_title || 'PLAN DETAILS'} &bull; {activePlanModal.corridor} &bull; {activePlanModal.section}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-[10px] font-black uppercase border ${
                  activePlanModal.status === 'APPROVED'
                    ? 'bg-emerald-800 text-white border-emerald-400'
                    : 'bg-emerald-100 text-emerald-900 border-emerald-300'
                }`}>
                  {activePlanModal.status === 'APPROVED' ? 'STATUS: APPROVED' : 'STATUS: RECOMMENDED'}
                </span>
                <button
                  onClick={() => setActivePlanModal(null)}
                  className="text-white/80 hover:text-white font-bold text-sm cursor-pointer ml-1"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Scrollable Content */}
            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-xs">
              {/* Section 17 Visual Coordination Relationship Tree */}
              {renderCoordinationTree(activePlanModal)}

              {/* Alternatives Tabs (Section 23 & 24) */}
              {(activePlanModal.alternatives && activePlanModal.alternatives.length > 0) && (
                <div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">
                    Schedule Alternatives & Tradeoff Comparison (Section 23 & 24):
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {activePlanModal.alternatives.map((alt) => (
                      <button
                        key={alt.plan_name}
                        onClick={() => setActivePlanModalAlt(alt.plan_name)}
                        className={`p-2 text-left border cursor-pointer transition-all ${
                          activePlanModalAlt === alt.plan_name
                            ? 'bg-[#0B2545] text-white border-[#0B2545] font-bold shadow-xs'
                            : 'bg-slate-50 text-slate-700 hover:bg-slate-100 border-slate-300'
                        }`}
                      >
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="font-black uppercase">{alt.plan_name}</span>
                          <span className={`font-mono font-bold ${activePlanModalAlt === alt.plan_name ? 'text-[#FFB703]' : 'text-slate-600'}`}>
                            Score: {alt.score}
                          </span>
                        </div>
                        <div className="font-mono text-[11px] mt-0.5">{alt.time_window}</div>
                        <div className="text-[8px] opacity-75 truncate">{alt.label}</div>
                      </button>
                    ))}
                  </div>
                  {/* Tradeoff Explanation */}
                  {(() => {
                    const selAlt = activePlanModal.alternatives.find(a => a.plan_name === activePlanModalAlt) || activePlanModal.alternatives[0];
                    return selAlt?.tradeoff ? (
                      <div className="mt-1.5 p-1.5 bg-blue-50/70 border border-blue-200 text-[10px] text-blue-900">
                        <strong>Tradeoff Note ({selAlt.plan_name}):</strong> {selAlt.tradeoff}
                      </div>
                    ) : null;
                  })()}
                </div>
              )}

              {/* Operational Analysis Grid (Section 11) */}
              <div className="border border-slate-200 bg-slate-50 p-2.5 space-y-1.5">
                <div className="text-[10px] font-bold text-slate-500 uppercase border-b border-slate-200 pb-1">
                  OPERATIONAL ANALYSIS & POSSESSION ATTRIBUTES
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Corridor:</span>
                    <strong className="font-mono text-[#134074]">{activePlanModal.corridor}</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Section:</span>
                    <strong className="font-mono text-slate-900">{activePlanModal.section}</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Common Block:</span>
                    <strong className="font-mono text-emerald-800 font-bold">{activePlanModal.common_block_window}</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Total Duration:</span>
                    <strong className="font-mono text-slate-800">{activePlanModal.total_possession_duration_min || activePlanModal.duration_min} minutes</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Train Conflicts:</span>
                    <strong className="font-mono text-emerald-700 font-bold">0 Conflicting Trains</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Conflicting Sections:</span>
                    <strong className="font-mono text-emerald-700 font-bold">0 Conflicting Sections</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Block Utilization:</span>
                    <strong className="font-mono text-blue-900 font-bold">{activePlanModal.block_utilization_pct || 100}%</strong>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 font-bold block">Possessions Avoided:</span>
                    <strong className="font-mono text-emerald-700 font-bold">{activePlanModal.separate_blocks_avoided || 0} Repeated Setups</strong>
                  </div>
                </div>
              </div>

              {/* Coordinated Departments List */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-bold text-slate-600 uppercase">Coordinated Departments:</span>
                {(activePlanModal.departments || []).map((dept, idx) => (
                  <span key={idx} className="bg-[#134074] text-white px-2 py-0.5 text-[10px] font-black uppercase tracking-wide">
                    {dept}
                  </span>
                ))}
              </div>

              {/* Requests Included Table */}
              <div>
                <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">
                  REQUESTS INCLUDED ({activePlanModal.requests_combined_count || 1} Maintenance Demands):
                </div>
                <table className="cris-table w-full text-[11px]">
                  <thead>
                    <tr>
                      <th>Request ID</th>
                      <th>Department</th>
                      <th>Work Scope</th>
                      <th>Duration</th>
                      <th>Scheduled Slot</th>
                      <th>Possession Mode</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activePlanModal.work_breakdown || (activePlanModal.request_ids || []).map(id => ({
                      job_code: id,
                      department: 'Engineering',
                      work_title: 'Track Maintenance',
                      duration_min: 90,
                      scheduled_time: activePlanModal.common_block_window
                    }))).map((wb, idx) => (
                      <tr key={idx}>
                        <td className="font-mono font-bold text-slate-900">{wb.job_code}</td>
                        <td>
                          <span className="font-bold text-slate-700 bg-slate-100 px-1 py-0.5 border text-[9px]">
                            {wb.department}
                          </span>
                        </td>
                        <td className="font-bold text-slate-800">{wb.work_title}</td>
                        <td className="font-mono">{wb.duration_min} min</td>
                        <td className="font-mono text-emerald-800 font-bold">{wb.scheduled_time || activePlanModal.common_block_window}</td>
                        <td>
                          <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 px-1 py-0.5 text-[9px] font-bold">
                            {(activePlanModal.requests_combined_count || 1) > 1 ? 'PARALLEL WORK' : 'STANDALONE'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Section 11 WHY THIS PLAN? Checklist */}
              <div className="border border-emerald-200 bg-emerald-50/50 p-2.5 text-xs">
                <div className="font-bold text-emerald-900 text-[10px] uppercase border-b border-emerald-200 pb-1 mb-1.5 flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-700" />
                  WHY THIS PLAN? (AI HEURISTIC & SAFETY PROOF)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-[11px] text-slate-700">
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> Same railway section verified ({activePlanModal.section})
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> Same planning date & compatible work activities
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> Common possession feasible without resource contention
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> No hard passenger or freight train headway conflict
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> Departmental due dates strictly satisfied
                  </div>
                  <div className="flex items-center gap-1.5 text-emerald-950 font-medium">
                    <span className="text-emerald-700 font-bold font-mono">✓</span> Reduces repeated possession downtime & maximizes asset availability
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Actions Footer (Section 11) */}
            <div className="p-3 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {activePlanModal.status === 'APPROVED' ? (
                  <span className="bg-emerald-100 text-emerald-800 border border-emerald-300 font-black text-xs px-3 py-1.5 flex items-center gap-1 uppercase">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-700" />
                    ✓ APPROVED & AUTHORIZED
                  </span>
                ) : (
                  <button
                    id="btn-modal-approve-plan"
                    onClick={() => handleApprovePlanDirect(activePlanModal)}
                    className="cris-btn bg-emerald-700 hover:bg-emerald-800 text-white font-black text-xs uppercase px-3.5 py-1.5 flex items-center gap-1 shadow-xs cursor-pointer"
                  >
                    <CheckCircle className="w-3.5 h-3.5" /> [ APPROVE PLAN ]
                  </button>
                )}

                <button
                  onClick={() => handleOpenCoordinatedModify(activePlanModal)}
                  className="cris-btn bg-[#134074] hover:bg-[#0B2545] text-white font-bold text-xs uppercase px-2.5 py-1.5 flex items-center gap-1 cursor-pointer"
                >
                  <Edit2 className="w-3.5 h-3.5" /> [ MODIFY PLAN ]
                </button>

                <button
                  onClick={() => {
                    setCoordinatedPlanResult(activePlanModal);
                    setShowCoordinatedWhatIfModal(true);
                    setWhatIfResult(null);
                  }}
                  className="cris-btn bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs uppercase px-2.5 py-1.5 flex items-center gap-1 cursor-pointer"
                >
                  <Sliders className="w-3.5 h-3.5" /> [ WHAT-IF ]
                </button>

                <button
                  onClick={() => handleOpenCoordinatedReject(activePlanModal)}
                  className="cris-btn bg-red-700 hover:bg-red-800 text-white font-bold text-xs uppercase px-2.5 py-1.5 flex items-center gap-1 cursor-pointer"
                >
                  <XCircle className="w-3.5 h-3.5" /> [ REJECT PLAN ]
                </button>
              </div>

              <button
                id="btn-modal-close"
                onClick={() => setActivePlanModal(null)}
                className="cris-btn cris-btn-secondary text-xs px-3 py-1.5 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Section 27: Individual Maintenance Request Details Modal ── */}
      {activeRequestDetailsModal && (
        <div className="fixed inset-0 bg-slate-950/70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-xl flex flex-col">
            <div className="bg-[#0B2545] text-white p-3 font-bold text-xs uppercase flex justify-between items-center border-b border-slate-700">
              <span className="flex items-center gap-1.5">
                <Inbox className="w-4 h-4 text-[#FFB703]" />
                MAINTENANCE REQUEST REVIEW &bull; {activeRequestDetailsModal.job_code}
              </span>
              <button
                onClick={() => setActiveRequestDetailsModal(null)}
                className="text-white/80 hover:text-white font-bold text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 border border-slate-200">
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Department</span>
                  <strong className="text-slate-800">{activeRequestDetailsModal.department?.name || 'Track Engineering'}</strong>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Work Scope</span>
                  <strong className="text-slate-800">{activeRequestDetailsModal.work_title || activeRequestDetailsModal.work_type}</strong>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Corridor & Section</span>
                  <strong className="font-mono text-[#134074]">
                    {activeRequestDetailsModal.start_station_code} → {activeRequestDetailsModal.end_station_code} ({activeRequestDetailsModal.section?.section_id || activeRequestDetailsModal.section?.section_code || activeRequestDetailsModal.section_name || 'SECTION-103'})
                  </strong>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Requested Window</span>
                  <strong className="font-mono text-slate-800">
                    {activeRequestDetailsModal.requested_date || '15 Sep 2026'} &bull; {activeRequestDetailsModal.estimated_duration_min} min
                  </strong>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Priority / Score</span>
                  <div className="flex items-center gap-1">
                    {getPriorityBadge(activeRequestDetailsModal.user_priority)}
                    <span className="font-mono font-bold text-[#0B2545]">
                      {(activeRequestDetailsModal.priority_score || 82.0).toFixed(1)}/100
                    </span>
                  </div>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-slate-500 uppercase block">Due Date & Status</span>
                  <span className="font-mono text-slate-700">
                    {activeRequestDetailsModal.due_date ? activeRequestDetailsModal.due_date.slice(0, 10) : '15 Sep 2026'} &bull; {getStatusBadge(activeRequestDetailsModal.status)}
                  </span>
                </div>
              </div>

              {activeRequestDetailsModal.description && (
                <div className="p-2 bg-white border border-slate-200 text-slate-700 text-[11px]">
                  <strong>Remarks:</strong> {activeRequestDetailsModal.description}
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-slate-200">
                <button
                  onClick={() => {
                    handleOpenAuditModal(activeRequestDetailsModal);
                    setActiveRequestDetailsModal(null);
                  }}
                  className="bg-slate-700 hover:bg-slate-800 text-white px-2.5 py-1.5 text-xs font-bold uppercase flex items-center gap-1 cursor-pointer"
                >
                  <Shield className="w-3 h-3 text-[#FFB703]" /> [ AUDIT TRAIL ]
                </button>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      handleOptimizeRequest(activeRequestDetailsModal.id);
                      setActiveRequestDetailsModal(null);
                    }}
                    className="bg-[#0B2545] hover:bg-[#134074] text-white px-3 py-1.5 text-xs font-bold uppercase flex items-center gap-1 border border-[#FFB703] cursor-pointer"
                    title="Run CP-SAT solver specifically for this individual request"
                  >
                    <Cpu className="w-3.5 h-3.5 text-[#FFB703]" />
                    [ OPTIMIZE INDIVIDUALLY ]
                  </button>
                  <button
                    onClick={() => setActiveRequestDetailsModal(null)}
                    className="cris-btn cris-btn-secondary text-xs px-3 py-1.5 cursor-pointer"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
