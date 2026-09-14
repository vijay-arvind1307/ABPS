import React, { useState, useEffect } from 'react';
import {
  PlusCircle,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Shield,
  Wrench,
  Layers,
  Send,
  Edit3,
  Calendar,
  FileText,
  Info,
  Check,
  X,
  Radio,
  Play,
  CheckSquare,
  RotateCcw,
  Bell,
  History,
  Activity,
  ArrowRight,
  TrendingUp,
  AlertCircle
} from 'lucide-react';
import {
  getMaintenanceJobs,
  createMaintenanceJob,
  updateMaintenanceJob,
  getBlockRequests,
  createBlockRequest,
  submitBlockRequest,
  acceptBlockRequest,
  requestChangeBlockRequest,
  startBlockRequest,
  completeBlockRequest,
  getBlockRequestAudit,
  getCorridors,
  getSections,
  resolveStation,
  validateRoute,
  getJobPriorityExplanation,
  getActivePlan,
  departmentAcceptPlan,
  departmentRequestChange,
  departmentDeclinePlan,
  getExecutionRecords,
  startExecution,
  updateExecutionProgress,
  completeExecution,
  getNotifications,
  markNotificationRead
} from '../services/api';
import { getCurrentUser } from '../services/auth';
import StationAutocomplete from '../components/StationAutocomplete';

export default function DepartmentDashboard() {
  const user = getCurrentUser();
  const [jobs, setJobs] = useState([]);
  const [activePlan, setActivePlan] = useState(null);
  const [executionRecords, setExecutionRecords] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [corridors, setCorridors] = useState([]);
  const [corridorSections, setCorridorSections] = useState([]);
  const [loading, setLoading] = useState(true);

  // 11 Operational Control Panel Positions:
  // MY_REQUESTS, NEW_DEMAND, PENDING, APPROVED_PLANS, WORK_ACCEPTED, IN_PROGRESS, COMPLETED, BLOCK_STATUS, EXECUTION_STATUS, NOTIFICATIONS, HISTORY
  const [activeTab, setActiveTab] = useState('MY_REQUESTS');

  // Modals
  const [showNewDemandModal, setShowNewDemandModal] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [showChangeRequestModal, setShowChangeRequestModal] = useState(false);
  const [changeRequestPlanId, setChangeRequestPlanId] = useState(null);
  const [changeRequestRemarks, setChangeRequestRemarks] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Audit trail modal
  const [auditJob, setAuditJob] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [showAuditModal, setShowAuditModal] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);

  // Execution Modals
  const [showExecutionModal, setShowExecutionModal] = useState(false);
  const [executingJob, setExecutingJob] = useState(null);
  const [execActionType, setExecActionType] = useState('START'); // START, PROGRESS, COMPLETE
  const [execStartMin, setExecStartMin] = useState(600);
  const [execEndMin, setExecEndMin] = useState(660);
  const [execProgressPct, setExecProgressPct] = useState(50);
  const [execRemarks, setExecRemarks] = useState('');

  // Explainability modal
  const [explainJob, setExplainJob] = useState(null);
  const [explainLoading, setExplainLoading] = useState(false);

  // Department metadata derived directly from authenticated user
  const roleCode = (user?.role || '').toUpperCase();
  const deptCode = user?.department_code || (
    roleCode.includes('SNT') || roleCode.includes('SIGNAL') ? 'SNT' :
    roleCode.includes('TRD') || roleCode.includes('TRACTION') ? 'TRD' :
    roleCode.includes('PLAN') || roleCode.includes('OPERAT') ? 'OPERATIONS' : 'ENGG'
  );
  const deptName = user?.department_name || (
    deptCode === 'ENGG' ? 'Civil Engineering (Track / P-Way)' :
    deptCode === 'SNT' ? 'Signal & Telecommunication' :
    deptCode === 'TRD' ? 'Traction Distribution (25kV OHE)' : 'Operations & Planning'
  );

  // Work type suggestions per department
  const workTypeSuggestions = {
    ENGG: ['TRACK_TAMPING', 'RAIL_REPLACEMENT', 'BALLAST_CLEANING', 'TRACK_SURFACING', 'TURNOUT_RENEWAL', 'WELD_REPAIR'],
    SNT: ['SIGNAL_POINT_OVERHAUL', 'TRACK_CIRCUIT_REPAIR', 'AXLE_COUNTER_CALIBRATION', 'SIGNAL_CABLE_MEGGERING', 'INTERLOCKING_TEST'],
    TRD: ['OHE_INSPECTION', 'CANTILEVER_ADJUSTMENT', 'OHE_POWER_BLOCK', 'OHE_ANNUAL_MAINTENANCE', 'OHE_BONDING', 'INSULATOR_REPLACEMENT'],
    OPERATIONS: ['TRACK_PATROLLING', 'TRAIN_MOVEMENT_SAFETY_CHECK', 'PLATFORM_MAINTENANCE']
  };

  const currentSuggestions = workTypeSuggestions[deptCode] || workTypeSuggestions.ENGG;

  // Station resolution & route validation states for modal
  const [startResolution, setStartResolution] = useState({ loading: false, valid: null, name: '' });
  const [endResolution, setEndResolution] = useState({ loading: false, valid: null, name: '' });
  const [routeStatus, setRouteStatus] = useState({ checking: false, valid: null, message: '', corridor: '' });

  const getInitialJobState = () => ({
    job_code: `REQ-${Math.floor(100000 + Math.random() * 900000)}`,
    work_title: '',
    work_type: currentSuggestions[0] || 'TRACK_TAMPING',
    description: '',
    corridor_id: null,
    start_station_code: '',
    end_station_code: '',
    section_id: null,
    requested_date: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    requested_start_time: '10:00',
    requested_end_time: '12:00',
    user_priority: 'HIGH',
    due_date: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    estimated_duration_min: 90,
    preferred_start_min: 600,
    preferred_end_min: 720,
    safety_impact_info: '',
    additional_remarks: '',
    is_emergency: false,
    status: 'SUBMITTED'
  });

  const [formData, setFormData] = useState(getInitialJobState());

  const loadData = async () => {
    setLoading(true);
    try {
      const [jobsRes, planRes, execRes, notifRes, corrRes] = await Promise.all([
        getBlockRequests().catch(() => getMaintenanceJobs({ department_id: user?.department_id })),
        getActivePlan('PLAN_A').catch(() => ({ data: null })),
        getExecutionRecords().catch(() => ({ data: [] })),
        getNotifications().catch(() => ({ data: [] })),
        getCorridors().catch(() => ({ data: [] }))
      ]);

      setJobs(jobsRes.data || []);
      setActivePlan(planRes.data);
      setExecutionRecords(execRes.data || []);
      setNotifications(notifRes.data || []);
      setCorridors(corrRes.data || []);
    } catch (err) {
      console.error('[ABPS Department] Load failure:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(() => {
      loadData();
    }, 20000);
    return () => clearInterval(timer);
  }, []);

  // Station resolution handler
  const handleResolveStation = async (code, isStart) => {
    const norm = (code || '').trim().toUpperCase();
    if (isStart) {
      setFormData(prev => ({ ...prev, start_station_code: norm }));
      if (norm.length < 2) {
        setStartResolution({ loading: false, valid: null, name: '' });
        return;
      }
      setStartResolution({ loading: true, valid: null, name: '' });
      try {
        const res = await resolveStation(norm);
        if (res.data && res.data.valid) {
          setStartResolution({ loading: false, valid: true, name: res.data.name });
        } else {
          setStartResolution({ loading: false, valid: false, name: res.data.message || 'Unknown Station' });
        }
      } catch {
        setStartResolution({ loading: false, valid: false, name: 'Lookup failed' });
      }
    } else {
      setFormData(prev => ({ ...prev, end_station_code: norm }));
      if (norm.length < 2) {
        setEndResolution({ loading: false, valid: null, name: '' });
        return;
      }
      setEndResolution({ loading: true, valid: null, name: '' });
      try {
        const res = await resolveStation(norm);
        if (res.data && res.data.valid) {
          setEndResolution({ loading: false, valid: true, name: res.data.name });
        } else {
          setEndResolution({ loading: false, valid: false, name: res.data.message || 'Unknown Station' });
        }
      } catch {
        setEndResolution({ loading: false, valid: false, name: 'Lookup failed' });
      }
    }
  };

  // Trigger route validation when start/end station change
  useEffect(() => {
    const s = (formData.start_station_code || '').trim().toUpperCase();
    const e = (formData.end_station_code || '').trim().toUpperCase();

    if (!s || !e || s.length < 2 || e.length < 2) {
      setRouteStatus({ checking: false, valid: null, message: '', corridor: '' });
      return;
    }

    if (s === e) {
      setRouteStatus({
        checking: false,
        valid: false,
        message: 'Start and end stations must be different.',
        corridor: ''
      });
      return;
    }

    const timer = setTimeout(async () => {
      setRouteStatus({ checking: true, valid: null, message: 'Validating route on railway network...', corridor: '' });
      try {
        const res = await validateRoute(s, e);
        if (res.data && res.data.valid) {
          setRouteStatus({
            checking: false,
            valid: true,
            message: `Route Verified: ${res.data.corridor_name || res.data.corridor_code} (${res.data.distance_km} km)`,
            corridor: res.data.corridor_name
          });
        } else {
          setRouteStatus({
            checking: false,
            valid: false,
            message: res.data?.message || 'ROUTE NOT CONFIGURED ON RAILWAY GRAPH',
            corridor: ''
          });
        }
      } catch (err) {
        setRouteStatus({
          checking: false,
          valid: false,
          message: 'Route validation network error',
          corridor: ''
        });
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [formData.start_station_code, formData.end_station_code]);

  // Real-time Preview Priority Calculation
  const calculatePreviewPriority = () => {
    let crit = 50.0;
    let critLabel = 'MEDIUM';
    const wt = (formData.work_type || '').toUpperCase();

    if (formData.is_emergency) {
      crit = 95.0;
      critLabel = 'CRITICAL';
    } else if (wt.includes('RAIL_REPLACEMENT') || wt.includes('FRACTURE') || wt.includes('TURNOUT') || wt.includes('INTERLOCKING')) {
      crit = 85.0;
      critLabel = 'HIGH';
    } else if (wt.includes('TAMPING') || wt.includes('BALLAST') || wt.includes('POINT') || wt.includes('OHE_POWER')) {
      crit = 75.0;
      critLabel = 'HIGH';
    } else if (wt.includes('SURFACING') || wt.includes('CIRCUIT') || wt.includes('CANTILEVER')) {
      crit = 62.0;
      critLabel = 'MEDIUM';
    } else {
      crit = 45.0;
      critLabel = 'LOW';
    }

    let safety = 50.0;
    let safetyLabel = 'MEDIUM';
    if (formData.is_emergency) {
      safety = 95.0;
      safetyLabel = 'HIGH';
    } else if (wt.includes('FRACTURE') || wt.includes('RAIL_REPLACEMENT') || wt.includes('POINT_MACHINE') || wt.includes('OHE_POWER_BLOCK')) {
      safety = 90.0;
      safetyLabel = 'HIGH';
    } else if (wt.includes('TAMPING') || wt.includes('POINT_OVERHAUL') || wt.includes('TRACK_CIRCUIT') || wt.includes('AXLE_COUNTER')) {
      safety = 78.0;
      safetyLabel = 'HIGH';
    } else if (wt.includes('INSPECTION') || wt.includes('BONDING') || wt.includes('MEGGERING')) {
      safety = 52.0;
      safetyLabel = 'MEDIUM';
    } else {
      safety = 35.0;
      safetyLabel = 'LOW';
    }

    let urgency = 50.0;
    let urgencyLabel = 'MEDIUM';
    const prioMap = { LOW: 33.33, MEDIUM: 66.67, HIGH: 100.0 };
    const userPrioVal = prioMap[formData.user_priority] || 66.67;

    if (formData.is_emergency) {
      urgency = 98.0;
      urgencyLabel = 'CRITICAL';
    } else {
      const now = new Date();
      const due = formData.due_date ? new Date(formData.due_date) : null;
      let days = 3;
      if (due) {
        days = (due - now) / (1000 * 60 * 60 * 24);
      }
      if (days < 0) {
        urgency = 95.0;
        urgencyLabel = 'CRITICAL';
      } else if (days <= 1) {
        urgency = 85.0;
        urgencyLabel = 'HIGH';
      } else if (days <= 2) {
        urgency = 70.0;
        urgencyLabel = 'HIGH';
      } else if (days <= 5) {
        urgency = 50.0;
        urgencyLabel = 'MEDIUM';
      } else {
        urgency = 30.0;
        urgencyLabel = 'LOW';
      }
    }

    const raw = (crit * 0.30) + (safety * 0.30) + (urgency * 0.25) + (userPrioVal * 0.15);
    const score = formData.is_emergency ? Math.max(raw, 95.0) : Math.min(100.0, Math.max(0.0, raw));

    return {
      criticality: crit.toFixed(1),
      criticalityLabel: critLabel,
      safety: safety.toFixed(1),
      safetyLabel: safetyLabel,
      urgency: urgency.toFixed(1),
      urgencyLabel: urgencyLabel,
      score: score.toFixed(1)
    };
  };

  const preview = calculatePreviewPriority();

  const handleOpenCreateModal = () => {
    setEditingJob(null);
    const init = getInitialJobState();
    setFormData(init);
    handleResolveStation(init.start_station_code, true);
    handleResolveStation(init.end_station_code, false);
    setShowNewDemandModal(true);
  };

  const handleSubmitDemand = async (e) => {
    if (e) e.preventDefault();

    if (routeStatus.valid === false) {
      alert(`Cannot submit demand: ${routeStatus.message}`);
      return;
    }

    const payload = {
      ...formData,
      job_code: formData.job_code,
      start_station_code: formData.start_station_code.toUpperCase(),
      end_station_code: formData.end_station_code.toUpperCase(),
      user_priority: formData.user_priority,
      status: 'SUBMITTED',
      due_date: formData.due_date ? new Date(formData.due_date).toISOString() : null,
      department_id: user?.department_id
    };

    setActionLoading(true);
    try {
      if (editingJob) {
        await updateMaintenanceJob(editingJob.id, payload);
      } else {
        await createMaintenanceJob(payload);
      }
      setShowNewDemandModal(false);
      loadData();
      alert(`Maintenance Demand ${formData.job_code} successfully submitted and persisted.`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Error saving maintenance demand.');
    } finally {
      setActionLoading(false);
    }
  };

  // Plan Handshake Actions
  const handleAcceptPlan = async (planId) => {
    if (!confirm('Formally ACCEPT this master block schedule? This confirms field crew readiness.')) return;
    setActionLoading(true);
    try {
      await departmentAcceptPlan(planId, { remarks: 'Senior Section Engineer formal acceptance of possession timings' });
      alert('Plan successfully ACCEPTED. Status transitioned to DEPARTMENT_ACCEPTED and field teams placed in READY status.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to accept plan.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenChangeRequest = (planId) => {
    setChangeRequestPlanId(planId);
    setChangeRequestRemarks('');
    setShowChangeRequestModal(true);
  };

  const handleSubmitChangeRequest = async (e) => {
    e.preventDefault();
    if (!changeRequestRemarks.trim()) {
      alert('Operational remarks/justification is required when requesting changes.');
      return;
    }
    setActionLoading(true);
    try {
      await departmentRequestChange(changeRequestPlanId, { remarks: changeRequestRemarks.trim() });
      setShowChangeRequestModal(false);
      alert('Change request sent to Chief Section Controller / Railway Planner.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit change request.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeclinePlan = async (planId) => {
    const reason = prompt('Please specify reason for declining this block plan:');
    if (!reason) return;
    setActionLoading(true);
    try {
      await departmentDeclinePlan(planId, { remarks: reason });
      alert('Block plan declined. Jobs reverted to DRAFT status.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to decline plan.');
    } finally {
      setActionLoading(false);
    }
  };

  // Dedicated Block Request Workflow Handlers (SIH26027)
  const handleAcceptBlockRequest = async (jobId) => {
    if (!confirm('Formally ACCEPT this planner-approved block plan? This transitions status to ACCEPTED / READY FOR EXECUTION.')) return;
    setActionLoading(true);
    try {
      await acceptBlockRequest(jobId, { remarks: 'Senior Section Engineer formal acceptance of authorized block timings' });
      alert('Plan ACCEPTED! Status: ACCEPTED / READY FOR EXECUTION.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to accept plan.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRequestChangeBlockRequest = async (jobId) => {
    const reason = prompt('Specify operational reason / proposed alternative window:');
    if (!reason || !reason.trim()) return;
    setActionLoading(true);
    try {
      await requestChangeBlockRequest(jobId, { reason: reason.trim() });
      alert('Change request sent to Chief Section Controller / Railway Planner.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to request change.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartBlockExecution = async (jobId) => {
    if (!confirm('Commence physical track possession? This will mark the block IN_PROGRESS.')) return;
    setActionLoading(true);
    try {
      await startBlockRequest(jobId, { remarks: 'Track block possession commenced by maintenance squad' });
      alert('Track possession started. Status: IN_PROGRESS.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to start execution.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCompleteBlockExecution = async (jobId) => {
    if (!confirm('Complete maintenance work and cancel track possession?')) return;
    setActionLoading(true);
    try {
      await completeBlockRequest(jobId, { remarks: 'Track machine cleared, block cancelled, section clear for traffic' });
      alert('Maintenance block COMPLETED. Section restored for traffic.');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to complete execution.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewAuditTrail = async (job) => {
    setAuditJob(job);
    setAuditLoading(true);
    setShowAuditModal(true);
    try {
      const res = await getBlockRequestAudit(job.id);
      setAuditLogs(res.data || []);
    } catch (err) {
      console.error(err);
      setAuditLogs([]);
    } finally {
      setAuditLoading(false);
    }
  };

  // Execution Handlers
  const handleOpenExecution = (job, actionType) => {
    setExecutingJob(job);
    setExecActionType(actionType);
    const now = new Date();
    const currMin = now.getHours() * 60 + now.getMinutes();
    setExecStartMin(job.actual_start_min || currMin);
    setExecEndMin(currMin + job.estimated_duration_min);
    setExecProgressPct(job.completion_pct || 10);
    setExecRemarks('');
    setShowExecutionModal(true);
  };

  const handleSubmitExecution = async (e) => {
    e.preventDefault();
    if (!executingJob) return;
    setActionLoading(true);
    try {
      if (execActionType === 'START') {
        await startExecution({
          job_id: executingJob.id,
          actual_start_min: parseInt(execStartMin),
          remarks: execRemarks || 'Possession taken on track by maintenance squad'
        });
        alert(`Possession commenced for ${executingJob.job_code}. Status: IN_PROGRESS.`);
      } else if (execActionType === 'PROGRESS') {
        await updateExecutionProgress({
          job_id: executingJob.id,
          completion_pct: parseFloat(execProgressPct),
          remarks: execRemarks || `Progress update: ${execProgressPct}%`
        });
        alert(`Progress updated to ${execProgressPct}%.`);
      } else if (execActionType === 'COMPLETE') {
        await completeExecution({
          job_id: executingJob.id,
          actual_end_min: parseInt(execEndMin),
          completion_pct: 100.0,
          status: 'COMPLETED',
          remarks: execRemarks || 'Track cleared and handed back to Traffic Control'
        });
        alert(`Block completed and track cleared for ${executingJob.job_code}.`);
      }
      setShowExecutionModal(false);
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Execution action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleShowExplanation = async (job) => {
    setExplainJob({ ...job });
    setExplainLoading(true);
    try {
      const res = await getJobPriorityExplanation(job.id);
      setExplainJob(res.data);
    } catch {
      // Keep existing job data
    } finally {
      setExplainLoading(false);
    }
  };

  const handleMarkNotificationRead = async (id) => {
    try {
      await markNotificationRead(id);
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const getPriorityBadge = (prio) => {
    switch ((prio || '').toUpperCase()) {
      case 'HIGH':
        return <span className="bg-red-100 text-red-800 border border-red-300 px-1 py-0.2 text-[10px] font-bold">HIGH</span>;
      case 'MEDIUM':
        return <span className="bg-amber-100 text-amber-800 border border-amber-300 px-1 py-0.2 text-[10px] font-bold">MED</span>;
      case 'LOW':
        return <span className="bg-slate-100 text-slate-700 border border-slate-300 px-1 py-0.2 text-[10px] font-bold">LOW</span>;
      default:
        return <span className="text-slate-600 text-[10px]">{prio || 'MED'}</span>;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'DRAFT':
        return <span className="bg-slate-200 text-slate-700 px-1.5 py-0.5 text-[10px] font-bold border border-slate-300">DRAFT</span>;
      case 'SUBMITTED':
        return <span className="bg-blue-100 text-blue-800 px-1.5 py-0.5 text-[10px] font-bold border border-blue-300 animate-pulse">SUBMITTED</span>;
      case 'UNDER_REVIEW':
      case 'PLANNING':
        return <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 text-[10px] font-bold border border-amber-300">UNDER REVIEW</span>;
      case 'APPROVED':
        return <span className="bg-emerald-100 text-emerald-800 px-1.5 py-0.5 text-[10px] font-bold border border-emerald-300 font-mono">APPROVED</span>;
      case 'DEPARTMENT_ACCEPTED':
      case 'SCHEDULED':
        return <span className="bg-teal-100 text-teal-800 px-1.5 py-0.5 text-[10px] font-bold border border-teal-300 font-mono">ACCEPTED</span>;
      case 'READY':
        return <span className="bg-indigo-100 text-indigo-800 px-1.5 py-0.5 text-[10px] font-bold border border-indigo-300 font-mono">READY</span>;
      case 'IN_PROGRESS':
        return <span className="bg-orange-100 text-orange-800 px-1.5 py-0.5 text-[10px] font-bold border border-orange-300 animate-pulse">IN PROGRESS</span>;
      case 'COMPLETED':
        return <span className="bg-slate-100 text-slate-800 px-1.5 py-0.5 text-[10px] font-bold border border-slate-300">COMPLETED</span>;
      case 'CHANGE_REQUESTED':
        return <span className="bg-purple-100 text-purple-800 px-1.5 py-0.5 text-[10px] font-bold border border-purple-300">CHANGE REQ</span>;
      case 'REJECTED':
        return <span className="bg-red-100 text-red-800 px-1.5 py-0.5 text-[10px] font-bold border border-red-300">REJECTED</span>;
      default:
        return <span className="bg-slate-100 text-slate-800 px-1.5 py-0.5 text-[10px] font-bold">{status}</span>;
    }
  };

  // Tab data partitions
  const myRequests = jobs;
  const pendingRequests = jobs.filter(j => ['SUBMITTED', 'PLANNING', 'UNDER_REVIEW'].includes(j.status));
  const approvedJobs = jobs.filter(j => j.status === 'APPROVED');
  const acceptedJobs = jobs.filter(j => ['DEPARTMENT_ACCEPTED', 'SCHEDULED', 'READY'].includes(j.status));
  const inProgressJobs = jobs.filter(j => j.status === 'IN_PROGRESS' || j.execution_status === 'IN_PROGRESS');
  const completedJobs = jobs.filter(j => j.status === 'COMPLETED' || j.execution_status === 'COMPLETED');

  // Find approved plan matching active plan
  const isPlanApprovedForDept = activePlan && activePlan.approval_status === 'APPROVED' &&
    activePlan.plan_jobs?.some(pj => pj.is_scheduled && pj.job && (pj.job.department_id === user?.department_id || !user?.department_id));

  return (
    <div className="p-3 space-y-3">
      {/* Top CRIS Command Header */}
      <div className="bg-white p-3 border border-slate-300 shadow-xs flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-[#0B2545] text-white">
            <Wrench className="w-5 h-5 text-[#FFB703]" />
          </div>
          <div>
            <h2 className="font-bold text-sm text-[#0B2545] uppercase tracking-wide">
              DEPARTMENT MAINTENANCE CONTROL PANEL &bull; {deptName} ({deptCode})
            </h2>
            <div className="flex items-center space-x-2 text-[11px] text-slate-600">
              <span>Section Engineer: <strong className="text-slate-800">{user?.full_name}</strong></span>
              <span>&bull;</span>
              <span>Active Demands: <strong className="text-slate-800">{jobs.length}</strong></span>
              <span>&bull;</span>
              <span>Pending Planner: <strong className="text-amber-700">{pendingRequests.length}</strong></span>
              <span>&bull;</span>
              <span>Track Possessions Active: <strong className="text-orange-700">{inProgressJobs.length}</strong></span>
            </div>
          </div>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="bg-[#134074] hover:bg-[#0B2545] text-white font-bold px-3 py-1.5 text-xs flex items-center space-x-1.5 transition-colors border border-[#0B2545] shadow-xs"
        >
          <PlusCircle className="w-4 h-4 text-[#FFB703]" />
          <span>NEW MAINTENANCE DEMAND</span>
        </button>
      </div>

      {/* 11 Section 5 Navigation Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-slate-300 bg-white p-1 text-xs">
        {[
          { id: 'MY_REQUESTS', label: `My Requests (${myRequests.length})`, icon: FileText },
          { id: 'PENDING', label: `Pending (${pendingRequests.length})`, icon: Clock },
          { id: 'APPROVED_PLANS', label: `Approved Plans (${approvedJobs.length})`, icon: CheckCircle2, highlight: approvedJobs.length > 0 },
          { id: 'WORK_ACCEPTED', label: `Work Accepted (${acceptedJobs.length})`, icon: CheckSquare },
          { id: 'IN_PROGRESS', label: `In Progress (${inProgressJobs.length})`, icon: Radio, pulse: inProgressJobs.length > 0 },
          { id: 'COMPLETED', label: `Completed (${completedJobs.length})`, icon: Check },
          { id: 'BLOCK_STATUS', label: 'Block Status', icon: Layers },
          { id: 'EXECUTION_STATUS', label: 'Execution Tracker', icon: Activity },
          { id: 'NOTIFICATIONS', label: `Notifications (${notifications.filter(n => !n.is_read).length})`, icon: Bell, badge: notifications.filter(n => !n.is_read).length },
          { id: 'HISTORY', label: 'Request History', icon: History }
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 font-bold uppercase flex items-center space-x-1.5 transition-colors border ${
                isActive
                  ? 'bg-[#0B2545] text-white border-[#0B2545]'
                  : tab.highlight
                  ? 'bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100 font-bold'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#FFB703]' : tab.pulse ? 'text-orange-600 animate-pulse' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
              {tab.badge > 0 && (
                <span className="bg-red-600 text-white rounded-full px-1 py-0.2 text-[9px]">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Main Panel Content */}
      <div className="bg-white border border-slate-300 p-3 shadow-xs min-h-[420px]">
        {/* TAB 1: MY REQUESTS */}
        {activeTab === 'MY_REQUESTS' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">ALL DEPARTMENT DEMANDS & POSSESSIONS</h3>
              <span className="text-[11px] text-slate-500 font-mono">Persisted in PostgreSQL/SQLite</span>
            </div>
            {jobs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <FileText className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO DATA AVAILABLE</div>
                <div className="text-xs text-slate-400 mt-1">No maintenance demands have been submitted yet. Click "NEW MAINTENANCE DEMAND" to create one.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Job Code</th>
                      <th>Work Type</th>
                      <th>Corridor / Route</th>
                      <th>Duration</th>
                      <th>Priority</th>
                      <th>Criticality</th>
                      <th>Safety Impact</th>
                      <th>Urgency</th>
                      <th>Composite Score</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map(j => (
                      <tr key={j.id}>
                        <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                        <td>{j.work_type}</td>
                        <td className="font-mono font-bold text-blue-900">{j.start_station_code} &rarr; {j.end_station_code}</td>
                        <td className="font-mono">{j.estimated_duration_min} min</td>
                        <td>{getPriorityBadge(j.user_priority)}</td>
                        <td>
                          <span className="font-mono text-[11px] font-semibold">{j.calculated_criticality?.toFixed(0) || 50}</span>
                          <span className="text-[9px] text-slate-500 ml-1">({j.criticality_label})</span>
                        </td>
                        <td>
                          <span className="font-mono text-[11px] font-semibold">{j.calculated_safety_impact?.toFixed(0) || 50}</span>
                          <span className="text-[9px] text-slate-500 ml-1">({j.safety_impact_label})</span>
                        </td>
                        <td>
                          <span className="font-mono text-[11px] font-semibold">{j.calculated_urgency?.toFixed(0) || 50}</span>
                          <span className="text-[9px] text-slate-500 ml-1">({j.urgency_label})</span>
                        </td>
                        <td className="font-mono font-bold text-emerald-800">{j.priority_score?.toFixed(1) || '50.0'}</td>
                        <td>{getStatusBadge(j.status)}</td>
                        <td>
                          <button
                            onClick={() => handleShowExplanation(j)}
                            className="text-blue-700 hover:text-blue-900 font-bold text-[10px] underline"
                          >
                            WHY PRIORITY?
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PENDING REQUESTS */}
        {activeTab === 'PENDING' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">PENDING PLANNER ALLOCATION & OPTIMIZATION</h3>
              <span className="text-[11px] text-amber-700 font-bold font-mono">Awaiting CP-SAT Schedule Authorization</span>
            </div>
            {pendingRequests.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2" />
                <div className="font-bold text-sm">NO PENDING REQUESTS</div>
                <div className="text-xs text-slate-400 mt-1">All submitted demands have been processed or scheduled.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Job Code</th>
                      <th>Work Type</th>
                      <th>Section / Stations</th>
                      <th>Required Duration</th>
                      <th>Priority</th>
                      <th>Score</th>
                      <th>Due Date</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingRequests.map(j => (
                      <tr key={j.id}>
                        <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                        <td>{j.work_type}</td>
                        <td className="font-mono">{j.start_station_code} &rarr; {j.end_station_code}</td>
                        <td className="font-mono">{j.estimated_duration_min}m</td>
                        <td>{getPriorityBadge(j.user_priority)}</td>
                        <td className="font-mono font-bold text-slate-800">{j.priority_score?.toFixed(1)}</td>
                        <td className="font-mono text-slate-600">{j.due_date ? new Date(j.due_date).toLocaleDateString() : 'N/A'}</td>
                        <td>{getStatusBadge(j.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: APPROVED PLANS (Section 25 Specification) */}
        {activeTab === 'APPROVED_PLANS' && (
          <div className="space-y-3">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">APPROVED MAINTENANCE PLANS & BLOCK POSSESSION OFFERS</h3>
              <span className="text-[11px] text-slate-500 font-mono">Section 25: Accept Plan / Request Change / Decline</span>
            </div>

            {approvedJobs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <Info className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO APPROVED PLANS AWAITING ACCEPTANCE</div>
                <div className="text-xs text-slate-400 mt-1">Once the Railway Chief Controller / Planner formally approves a block plan, it will appear here for departmental acceptance.</div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Individual Approved Block Requests (Section 13) */}
                {approvedJobs.map(j => {
                  const startH = Math.floor((j.preferred_start_min || 645) / 60);
                  const startM = (j.preferred_start_min || 645) % 60;
                  const endH = Math.floor((j.preferred_end_min || 735) / 60);
                  const endM = (j.preferred_end_min || 735) % 60;
                  const timeWindowStr = j.requested_start_time && j.requested_end_time
                    ? `${j.requested_start_time} – ${j.requested_end_time}`
                    : `${startH.toString().padStart(2, '0')}:${startM.toString().padStart(2, '0')} – ${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`;

                  return (
                    <div key={j.id} className="bg-emerald-50 border-2 border-emerald-600 p-3 shadow-xs">
                      <div className="flex flex-wrap items-center justify-between border-b border-emerald-300 pb-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="bg-emerald-700 text-white font-bold px-2 py-0.5 text-[10px] tracking-wider">PLAN APPROVED</span>
                          <span className="font-mono font-bold text-emerald-950 text-xs">{j.job_code}</span>
                          {j.coordinated_plan_id && (
                            <span className="bg-purple-100 text-purple-900 border border-purple-400 font-bold px-1.5 py-0.5 text-[9px] tracking-wider">
                              COMMON BLOCK CBP-{j.coordinated_plan_id}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-emerald-900 font-semibold">
                          Planner: <strong>Chief Section Controller / Railway Planner</strong>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs mb-2">
                        <div><span className="text-slate-500">Request:</span> <strong className="font-mono">{j.job_code}</strong></div>
                        <div><span className="text-slate-500">Approved Window:</span> <strong className="font-mono text-emerald-800">{timeWindowStr}</strong></div>
                        <div><span className="text-slate-500">Section:</span> <strong className="font-mono text-[#134074]">{j.start_station_code} ↔ {j.end_station_code}</strong></div>
                        <div>
                          <span className="text-slate-500">Block Mode:</span>{' '}
                          <strong className={j.coordinated_plan_id ? 'text-purple-800 font-bold' : 'text-emerald-800 font-bold'}>
                            {j.coordinated_plan_id ? `CBP-${j.coordinated_plan_id} (Coordinated)` : 'Individual Block'}
                          </strong>
                        </div>
                      </div>

                      <div className="text-xs text-slate-700 bg-white p-2 border border-emerald-200 mb-2">
                        <div><strong>Work Title:</strong> {j.work_title || j.work_type}</div>
                        <div className="text-[11px] text-slate-600 mt-0.5">Planner Remarks: {j.planner_remarks || 'Authorized without condition'}</div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleAcceptBlockRequest(j.id)}
                          disabled={actionLoading}
                          className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold px-3 py-1 text-xs flex items-center space-x-1 shadow-xs"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>ACCEPT PLAN</span>
                        </button>
                        <button
                          onClick={() => handleRequestChangeBlockRequest(j.id)}
                          disabled={actionLoading}
                          className="bg-amber-600 hover:bg-amber-700 text-white font-bold px-3 py-1 text-xs flex items-center space-x-1 shadow-xs"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          <span>REQUEST CHANGE</span>
                        </button>
                        <button
                          onClick={() => handleViewAuditTrail(j)}
                          className="p-1 border text-xs bg-white text-slate-700 hover:bg-slate-100 font-bold flex items-center gap-1 ml-auto"
                        >
                          <History className="w-3.5 h-3.5" /> AUDIT TRAIL
                        </button>
                      </div>
                    </div>
                  );
                })}
                {activePlan && (
                  <div className="bg-emerald-50 border-2 border-emerald-500 p-3 shadow-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-emerald-300">
                      <div>
                        <div className="text-xs font-bold text-emerald-950 flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                          <span>MASTER BLOCK PLAN: <strong className="font-mono text-emerald-900">{activePlan.plan_code}</strong></span>
                        </div>
                        <div className="text-[11px] text-emerald-800 mt-0.5">
                          Strategy: <strong className="font-mono">{activePlan.strategy}</strong> &bull; Utilization: <strong className="font-mono">{activePlan.block_utilization_pct}%</strong> &bull; Approved At: <strong className="font-mono">{activePlan.approved_at ? new Date(activePlan.approved_at).toLocaleString() : 'Recent'}</strong>
                        </div>
                      </div>

                      {/* Action Handshake Buttons (Section 25) */}
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleAcceptPlan(activePlan.id)}
                          disabled={actionLoading}
                          className="bg-emerald-700 hover:bg-emerald-800 text-white font-bold px-3 py-1.5 text-xs flex items-center space-x-1 transition-colors shadow-xs"
                        >
                          <Check className="w-4 h-4" />
                          <span>ACCEPT PLAN</span>
                        </button>
                        <button
                          onClick={() => handleOpenChangeRequest(activePlan.id)}
                          disabled={actionLoading}
                          className="bg-amber-600 hover:bg-amber-700 text-white font-bold px-3 py-1.5 text-xs flex items-center space-x-1 transition-colors shadow-xs"
                        >
                          <RotateCcw className="w-4 h-4" />
                          <span>REQUEST CHANGE</span>
                        </button>
                        <button
                          onClick={() => handleDeclinePlan(activePlan.id)}
                          disabled={actionLoading}
                          className="bg-red-700 hover:bg-red-800 text-white font-bold px-3 py-1.5 text-xs flex items-center space-x-1 transition-colors shadow-xs"
                        >
                          <X className="w-4 h-4" />
                          <span>DECLINE</span>
                        </button>
                      </div>
                    </div>

                    {/* Detailed Jobs in Plan */}
                    <div className="mt-3 overflow-x-auto">
                      <table className="cris-table">
                        <thead>
                          <tr>
                            <th>Job Code</th>
                            <th>Section / Location</th>
                            <th>Block Window Start</th>
                            <th>Block Window End</th>
                            <th>Allocated Duration</th>
                            <th>Coordinated Block</th>
                            <th>Planner Remarks</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activePlan.plan_jobs?.filter(pj => pj.is_scheduled && pj.job && (pj.job.department_id === user?.department_id || !user?.department_id)).map(pj => {
                            const startH = Math.floor((pj.scheduled_start_min || 0) / 60);
                            const startM = (pj.scheduled_start_min || 0) % 60;
                            const endH = Math.floor((pj.scheduled_end_min || 0) / 60);
                            const endM = (pj.scheduled_end_min || 0) % 60;
                            return (
                              <tr key={pj.id}>
                                <td className="font-mono font-bold text-slate-900">{pj.job?.job_code}</td>
                                <td className="font-mono text-blue-900">{pj.job?.start_station_code} &rarr; {pj.job?.end_station_code}</td>
                                <td className="font-mono font-bold text-emerald-800">{startH.toString().padStart(2, '0')}:{startM.toString().padStart(2, '0')} IST</td>
                                <td className="font-mono font-bold text-emerald-800">{endH.toString().padStart(2, '0')}:{endM.toString().padStart(2, '0')} IST</td>
                                <td className="font-mono">{pj.scheduled_duration_min} min</td>
                                <td className="font-mono text-purple-900 font-bold">{pj.block_code || 'SINGLE_BLOCK'}</td>
                                <td className="text-slate-600 text-[11px]">{pj.job?.planner_remarks || 'Authorized without condition'}</td>
                                <td>{getStatusBadge(pj.job?.status)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: WORK ACCEPTED */}
        {activeTab === 'WORK_ACCEPTED' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">ACCEPTED POSSESSION BLOCKS &bull; READY FOR FIELD EXECUTION</h3>
              <span className="text-[11px] text-teal-700 font-mono font-bold">Crew Readiness Verified</span>
            </div>
            {acceptedJobs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <CheckSquare className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO ACCEPTED BLOCKS PENDING EXECUTION</div>
                <div className="text-xs text-slate-400 mt-1">When you click "ACCEPT PLAN" on approved offers, work transfers here ready to begin.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Job Code</th>
                      <th>Work Type</th>
                      <th>Section</th>
                      <th>Duration</th>
                      <th>Field Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {acceptedJobs.map(j => (
                      <tr key={j.id}>
                        <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                        <td>{j.work_type}</td>
                        <td className="font-mono font-bold text-blue-900">{j.start_station_code} &rarr; {j.end_station_code}</td>
                        <td className="font-mono">{j.estimated_duration_min} min</td>
                        <td><span className="bg-indigo-100 text-indigo-800 px-1.5 py-0.5 text-[10px] font-bold border border-indigo-300">READY</span></td>
                        <td>
                          <button
                            onClick={() => handleOpenExecution(j, 'START')}
                            className="bg-emerald-700 hover:bg-emerald-800 text-white px-2 py-1 text-[11px] font-bold flex items-center space-x-1"
                          >
                            <Play className="w-3 h-3 text-[#FFB703]" />
                            <span>COMMENCE POSSESSION</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: WORK IN PROGRESS */}
        {activeTab === 'IN_PROGRESS' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">ACTIVE FIELD TRACK POSSESSIONS &bull; LIVE WORK IN PROGRESS</h3>
              <span className="text-[11px] text-orange-700 font-mono font-bold animate-pulse">Possession Active On Track</span>
            </div>
            {inProgressJobs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <Radio className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO ACTIVE FIELD POSSESSIONS CURRENTLY RUNNING</div>
                <div className="text-xs text-slate-400 mt-1">Commence work on accepted blocks to monitor live execution here.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Job Code</th>
                      <th>Work Type</th>
                      <th>Section</th>
                      <th>Actual Start</th>
                      <th>Duration Target</th>
                      <th>Progress %</th>
                      <th>Current Delay</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inProgressJobs.map(j => {
                      const startH = Math.floor((j.actual_start_min || 0) / 60);
                      const startM = (j.actual_start_min || 0) % 60;
                      return (
                        <tr key={j.id} className="bg-orange-50/50">
                          <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                          <td>{j.work_type}</td>
                          <td className="font-mono font-bold text-blue-900">{j.start_station_code} &rarr; {j.end_station_code}</td>
                          <td className="font-mono font-bold text-orange-900">{startH.toString().padStart(2, '0')}:{startM.toString().padStart(2, '0')} IST</td>
                          <td className="font-mono">{j.estimated_duration_min} min</td>
                          <td>
                            <div className="flex items-center space-x-1.5">
                              <div className="w-16 bg-slate-200 h-2 rounded overflow-hidden">
                                <div className="bg-orange-600 h-full" style={{ width: `${j.completion_pct || 10}%` }}></div>
                              </div>
                              <span className="font-mono text-xs font-bold">{j.completion_pct || 10}%</span>
                            </div>
                          </td>
                          <td className="font-mono text-red-700 font-bold">{j.delay_minutes || 0}m</td>
                          <td className="space-x-1">
                            <button
                              onClick={() => handleOpenExecution(j, 'PROGRESS')}
                              className="bg-blue-700 hover:bg-blue-800 text-white px-2 py-1 text-[10px] font-bold"
                            >
                              UPDATE %
                            </button>
                            <button
                              onClick={() => handleOpenExecution(j, 'COMPLETE')}
                              className="bg-emerald-700 hover:bg-emerald-800 text-white px-2 py-1 text-[10px] font-bold"
                            >
                              COMPLETE & CLEAR
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 6: COMPLETED WORK */}
        {activeTab === 'COMPLETED' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">COMPLETED MAINTENANCE BLOCKS &bull; ACTUAL DURATION & VARIANCE</h3>
              <span className="text-[11px] text-slate-500 font-mono">Permanent Way Track Restored</span>
            </div>
            {completedJobs.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <Check className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO COMPLETED WORK RECORDED YET</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Job Code</th>
                      <th>Work Type</th>
                      <th>Section</th>
                      <th>Planned Duration</th>
                      <th>Actual Start</th>
                      <th>Actual End</th>
                      <th>Variance</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {completedJobs.map(j => {
                      const sH = Math.floor((j.actual_start_min || 0) / 60);
                      const sM = (j.actual_start_min || 0) % 60;
                      const eH = Math.floor((j.actual_end_min || 0) / 60);
                      const eM = (j.actual_end_min || 0) % 60;
                      return (
                        <tr key={j.id}>
                          <td className="font-mono font-bold text-slate-900">{j.job_code}</td>
                          <td>{j.work_type}</td>
                          <td className="font-mono">{j.start_station_code} &rarr; {j.end_station_code}</td>
                          <td className="font-mono">{j.estimated_duration_min}m</td>
                          <td className="font-mono">{sH.toString().padStart(2, '0')}:{sM.toString().padStart(2, '0')}</td>
                          <td className="font-mono">{eH.toString().padStart(2, '0')}:{eM.toString().padStart(2, '0')}</td>
                          <td className={`font-mono font-bold ${j.variance_minutes > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
                            {j.variance_minutes > 0 ? `+${j.variance_minutes}m (OVERRUN)` : `${j.variance_minutes || 0}m (ON TIME)`}
                          </td>
                          <td><span className="bg-slate-200 text-slate-800 px-1.5 py-0.5 text-[10px] font-bold">COMPLETED</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 7: BLOCK STATUS */}
        {activeTab === 'BLOCK_STATUS' && (
          <div className="space-y-3">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">OPERATIONAL BLOCK STATUS & CORRIDOR POSSESSIONS</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div className="bg-slate-50 p-3 border border-slate-300">
                <div className="text-[10px] text-slate-500 font-bold uppercase">Total Demands</div>
                <div className="text-2xl font-bold font-mono text-slate-800 mt-1">{jobs.length}</div>
              </div>
              <div className="bg-amber-50 p-3 border border-amber-300">
                <div className="text-[10px] text-amber-700 font-bold uppercase">Pending Planning</div>
                <div className="text-2xl font-bold font-mono text-amber-900 mt-1">{pendingRequests.length}</div>
              </div>
              <div className="bg-emerald-50 p-3 border border-emerald-300">
                <div className="text-[10px] text-emerald-700 font-bold uppercase">Approved / Accepted</div>
                <div className="text-2xl font-bold font-mono text-emerald-900 mt-1">{approvedJobs.length + acceptedJobs.length}</div>
              </div>
              <div className="bg-orange-50 p-3 border border-orange-300">
                <div className="text-[10px] text-orange-700 font-bold uppercase">Live In Progress</div>
                <div className="text-2xl font-bold font-mono text-orange-900 mt-1">{inProgressJobs.length}</div>
              </div>
            </div>

            {activePlan && (
              <div className="cris-panel p-3">
                <div className="font-bold text-xs text-slate-800 uppercase mb-2">Current Active Corridor Plan Overview</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                  <div>Plan Code: <strong className="font-mono">{activePlan.plan_code}</strong></div>
                  <div>Objective Score: <strong className="font-mono">{activePlan.objective_score}</strong></div>
                  <div>Block Utilization: <strong className="font-mono text-emerald-700">{activePlan.block_utilization_pct}%</strong></div>
                  <div>Validation Status: <strong className="font-mono text-emerald-700">{activePlan.validation_status}</strong></div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 8: EXECUTION TRACKER (Section 26) */}
        {activeTab === 'EXECUTION_STATUS' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">FIELD EXECUTION LOGS & VARIANCE RECORDS</h3>
              <span className="text-[11px] text-slate-500 font-mono">Track Possession Timeline</span>
            </div>
            {executionRecords.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <Activity className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO EXECUTION RECORDS LOGGED YET</div>
                <div className="text-xs text-slate-400 mt-1">Commencing work on accepted blocks generates immutable execution log entries here.</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="cris-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Job Code</th>
                      <th>Status</th>
                      <th>Planned Window</th>
                      <th>Actual Start</th>
                      <th>Actual End</th>
                      <th>Variance</th>
                      <th>Progress %</th>
                      <th>Remarks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executionRecords.map(r => {
                      const pSH = r.planned_start_min !== null ? Math.floor(r.planned_start_min / 60) : null;
                      const pSM = r.planned_start_min !== null ? r.planned_start_min % 60 : null;
                      const aSH = r.actual_start_min !== null ? Math.floor(r.actual_start_min / 60) : null;
                      const aSM = r.actual_start_min !== null ? r.actual_start_min % 60 : null;
                      const aEH = r.actual_end_min !== null ? Math.floor(r.actual_end_min / 60) : null;
                      const aEM = r.actual_end_min !== null ? r.actual_end_min % 60 : null;
                      return (
                        <tr key={r.id}>
                          <td className="font-mono text-slate-500 text-[10px]">{new Date(r.timestamp).toLocaleTimeString()}</td>
                          <td className="font-mono font-bold text-slate-900">{r.job?.job_code || `Job #${r.job_id}`}</td>
                          <td>{getStatusBadge(r.status)}</td>
                          <td className="font-mono text-slate-700">
                            {pSH !== null ? `${pSH.toString().padStart(2, '0')}:${pSM.toString().padStart(2, '0')}` : 'N/A'}
                          </td>
                          <td className="font-mono font-bold text-slate-800">
                            {aSH !== null ? `${aSH.toString().padStart(2, '0')}:${aSM.toString().padStart(2, '0')}` : '—'}
                          </td>
                          <td className="font-mono font-bold text-slate-800">
                            {aEH !== null ? `${aEH.toString().padStart(2, '0')}:${aEM.toString().padStart(2, '0')}` : '—'}
                          </td>
                          <td className={`font-mono font-bold ${r.variance_min > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
                            {r.variance_min > 0 ? `+${r.variance_min}m` : `${r.variance_min}m`}
                          </td>
                          <td className="font-mono font-bold">{r.completion_pct}%</td>
                          <td className="text-slate-600 text-[11px] max-w-xs truncate">{r.remarks || r.notes}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 9: NOTIFICATIONS */}
        {activeTab === 'NOTIFICATIONS' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">OFFICIAL OPERATIONAL NOTIFICATIONS & ALERTS</h3>
              <span className="text-[11px] text-slate-500 font-mono">Authenticated Department Feed</span>
            </div>
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-300">
                <Bell className="w-8 h-8 mx-auto text-slate-400 mb-2" />
                <div className="font-bold text-sm">NO NOTIFICATIONS RECEIVED</div>
              </div>
            ) : (
              <div className="space-y-2">
                {notifications.map(n => (
                  <div
                    key={n.id}
                    className={`p-2.5 border text-xs flex justify-between items-start ${
                      n.is_read ? 'bg-slate-50 border-slate-200 text-slate-600' : 'bg-blue-50 border-blue-300 text-blue-950 font-medium'
                    }`}
                  >
                    <div>
                      <div className="font-bold text-xs">{n.title}</div>
                      <div className="mt-0.5">{n.message}</div>
                      <div className="text-[10px] text-slate-400 mt-1 font-mono">{new Date(n.created_at).toLocaleString()}</div>
                    </div>
                    {!n.is_read && (
                      <button
                        onClick={() => handleMarkNotificationRead(n.id)}
                        className="text-blue-700 hover:text-blue-900 font-bold text-[10px] underline ml-2 shrink-0"
                      >
                        MARK READ
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 10: REQUEST HISTORY */}
        {activeTab === 'HISTORY' && (
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-xs font-bold text-slate-800 uppercase">IMMUTABLE STATE TRANSITION AUDIT TRAIL</h3>
              <span className="text-[11px] text-slate-500 font-mono">Timestamped Actor Logs</span>
            </div>
            <div className="space-y-3">
              {jobs.filter(j => j.state_history_json && j.state_history_json.length > 0).map(j => (
                <div key={j.id} className="p-2.5 border border-slate-300 bg-slate-50">
                  <div className="font-bold text-xs text-slate-900 mb-1">
                    {j.job_code} &bull; {j.work_type} ({j.start_station_code} &rarr; {j.end_station_code})
                  </div>
                  <div className="space-y-1">
                    {j.state_history_json.map((h, idx) => (
                      <div key={idx} className="text-[11px] font-mono flex items-center space-x-2 text-slate-700 bg-white p-1 border border-slate-200">
                        <span className="text-slate-400">{new Date(h.timestamp).toLocaleTimeString()}</span>
                        <span className="font-bold text-slate-900">{h.acting_user}</span>
                        <span>:</span>
                        <span className="bg-slate-100 px-1 font-bold">{h.from_state}</span>
                        <span>&rarr;</span>
                        <span className="bg-blue-100 text-blue-900 px-1 font-bold">{h.to_state}</span>
                        <span className="text-slate-500 italic">({h.reason})</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* MODAL 1: NEW MAINTENANCE DEMAND */}
      {showNewDemandModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl max-w-2xl w-full max-h-[92vh] flex flex-col">
            <div className="bg-[#0B2545] text-white p-3 flex justify-between items-center">
              <div className="font-bold text-xs uppercase tracking-wide flex items-center gap-1.5">
                <PlusCircle className="w-4 h-4 text-[#FFB703]" />
                <span>NEW RAILWAY MAINTENANCE DEMAND &bull; {deptName}</span>
              </div>
              <button onClick={() => setShowNewDemandModal(false)} className="text-slate-300 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmitDemand} className="p-4 space-y-3 overflow-y-auto flex-1 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">REQUEST ID / CODE</label>
                  <input
                    type="text"
                    value={formData.job_code}
                    onChange={(e) => setFormData({ ...formData, job_code: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-mono font-bold bg-slate-50"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">DEPARTMENT (AUTHENTICATED)</label>
                  <input
                    type="text"
                    value={`${deptName} (${deptCode})`}
                    disabled
                    className="w-full border border-slate-300 p-1.5 font-bold bg-slate-100 text-slate-700 cursor-not-allowed"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">WORK TITLE</label>
                <input
                  type="text"
                  value={formData.work_title}
                  onChange={(e) => setFormData({ ...formData, work_title: e.target.value })}
                  placeholder="e.g. Track Tamping & Alignment Kovilpatti - Tirunelveli Section"
                  className="w-full border border-slate-300 p-1.5 font-bold"
                  required
                />
              </div>

              {/* Corridor Selector (Tamil Nadu Network C01-C20) */}
              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  CORRIDOR SELECTION (TAMIL NADU PROTOTYPE NETWORK C01–C20)
                </label>
                <select
                  value={formData.corridor_id || ''}
                  onChange={async (e) => {
                    const cId = e.target.value ? parseInt(e.target.value) : null;
                    const selCorr = corridors.find(c => c.id === cId);
                    setFormData(prev => ({
                      ...prev,
                      corridor_id: cId,
                      start_station_code: selCorr ? selCorr.start_station_code : prev.start_station_code,
                      end_station_code: selCorr ? selCorr.end_station_code : prev.end_station_code,
                      section_id: null
                    }));
                    if (selCorr) {
                      handleResolveStation(selCorr.start_station_code, true);
                      handleResolveStation(selCorr.end_station_code, false);
                      try {
                        const secRes = await getSections(selCorr.id);
                        setCorridorSections(secRes.data || []);
                      } catch { setCorridorSections([]); }
                    } else {
                      setCorridorSections([]);
                    }
                  }}
                  className="w-full border border-slate-300 p-1.5 font-bold bg-white text-slate-900"
                >
                  <option value="">[ -- SELECT TAMIL NADU CORRIDOR (C01–C20) -- ]</option>
                  {corridors.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.prototype_code ? `${c.prototype_code}: ` : ''}{c.name} ({c.start_station_code} ↔ {c.end_station_code}) — {c.sections_count || 0} Sections
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">WORK TYPE</label>
                  <select
                    value={formData.work_type}
                    onChange={(e) => setFormData({ ...formData, work_type: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold"
                  >
                    {currentSuggestions.map(wt => (
                      <option key={wt} value={wt}>{wt}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">RAILWAY SECTION (OPTIONAL)</label>
                  <select
                    value={formData.section_id || ''}
                    onChange={(e) => setFormData({ ...formData, section_id: e.target.value ? parseInt(e.target.value) : null })}
                    className="w-full border border-slate-300 p-1.5 font-bold"
                  >
                    <option value="">[ All Sections on Corridor / Auto ]</option>
                    {corridorSections.map(s => (
                      <option key={s.id} value={s.id}>{s.section_id} ({s.from_station_code} ↔ {s.to_station_code})</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Station Autocomplete (Authentic Railway Station Master) */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">START STATION</label>
                  <StationAutocomplete
                    value={formData.start_station_code}
                    onChange={(code) => handleResolveStation(code, true)}
                    placeholder="e.g. CVP, MDU"
                  />
                  {startResolution.valid === true && (
                    <div className="text-[10px] text-emerald-700 font-bold mt-0.5">{startResolution.name}</div>
                  )}
                  {startResolution.valid === false && (
                    <div className="text-[10px] text-red-600 font-bold mt-0.5">Invalid Station Code</div>
                  )}
                </div>

                <div>
                  <label className="font-bold text-slate-700 block mb-1">END STATION</label>
                  <StationAutocomplete
                    value={formData.end_station_code}
                    onChange={(code) => handleResolveStation(code, false)}
                    placeholder="e.g. TEN, TPJ"
                  />
                  {endResolution.valid === true && (
                    <div className="text-[10px] text-emerald-700 font-bold mt-0.5">{endResolution.name}</div>
                  )}
                  {endResolution.valid === false && (
                    <div className="text-[10px] text-red-600 font-bold mt-0.5">Invalid Station Code</div>
                  )}
                </div>
              </div>

              {/* Real Railway Network Route Validation Result */}
              {routeStatus.message && (
                <div className={`p-2 text-[11px] font-bold border ${
                  routeStatus.valid ? 'bg-emerald-50 text-emerald-900 border-emerald-300' : 'bg-red-50 text-red-900 border-red-300'
                }`}>
                  {routeStatus.message}
                </div>
              )}

              {/* Requested Date & Time Window */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">REQUESTED DATE</label>
                  <input
                    type="date"
                    value={formData.requested_date}
                    onChange={(e) => setFormData({ ...formData, requested_date: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">START TIME</label>
                  <input
                    type="time"
                    value={formData.requested_start_time}
                    onChange={(e) => setFormData({ ...formData, requested_start_time: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">END TIME</label>
                  <input
                    type="time"
                    value={formData.requested_end_time}
                    onChange={(e) => setFormData({ ...formData, requested_end_time: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold font-mono"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">DURATION (MINUTES)</label>
                  <input
                    type="number"
                    min="15"
                    max="480"
                    step="5"
                    value={formData.estimated_duration_min}
                    onChange={(e) => setFormData({ ...formData, estimated_duration_min: parseInt(e.target.value) || 90 })}
                    className="w-full border border-slate-300 p-1.5 font-mono font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">DUE DATE</label>
                  <input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">DEPARTMENT PRIORITY</label>
                  <select
                    value={formData.user_priority}
                    onChange={(e) => setFormData({ ...formData, user_priority: e.target.value })}
                    className="w-full border border-slate-300 p-1.5 font-bold text-slate-900"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">WORK DESCRIPTION</label>
                <textarea
                  rows="2"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Detailed work description, asset details, track equipment required..."
                  className="w-full border border-slate-300 p-1.5"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">SAFETY & ASSET IMPACT INFO</label>
                  <input
                    type="text"
                    value={formData.safety_impact_info}
                    onChange={(e) => setFormData({ ...formData, safety_impact_info: e.target.value })}
                    placeholder="e.g. Prevents 30 km/h PSR; curve realignment"
                    className="w-full border border-slate-300 p-1.5"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">ADDITIONAL REMARKS</label>
                  <input
                    type="text"
                    value={formData.additional_remarks}
                    onChange={(e) => setFormData({ ...formData, additional_remarks: e.target.value })}
                    placeholder="e.g. BCM-415 and 8 staff mobilized at Kovilpatti"
                    className="w-full border border-slate-300 p-1.5"
                  />
                </div>
              </div>

              {/* Deterministic System Priority Calculation Explanation */}
              <div className="bg-slate-50 border border-slate-300 p-2.5">
                <div className="font-bold text-slate-800 uppercase text-[11px] mb-1 flex items-center justify-between">
                  <span>SYSTEM PLANNING PRIORITY (DETERMINISTIC FORMULA)</span>
                  <span className="text-[10px] text-slate-500 font-mono">Formula: 30% Crit + 20% Urg + 15% Overdue + 20% Safety + 15% Ops</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-[10px] font-mono">
                  <div className="bg-white p-1 border">
                    <div className="text-slate-500">Criticality (30%)</div>
                    <div className="font-bold text-xs mt-0.5">{preview.criticality} ({preview.criticalityLabel})</div>
                  </div>
                  <div className="bg-white p-1 border">
                    <div className="text-slate-500">Safety (20%)</div>
                    <div className="font-bold text-xs mt-0.5">{preview.safety} ({preview.safetyLabel})</div>
                  </div>
                  <div className="bg-white p-1 border">
                    <div className="text-slate-500">Urgency (20%)</div>
                    <div className="font-bold text-xs mt-0.5">{preview.urgency} ({preview.urgencyLabel})</div>
                  </div>
                  <div className="bg-blue-50 border-blue-300 p-1 border">
                    <div className="text-blue-700 font-bold">Priority Score</div>
                    <div className="font-bold text-xs text-blue-900 mt-0.5">{preview.score} / 100</div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-300">
                <button
                  type="button"
                  onClick={() => setShowNewDemandModal(false)}
                  className="px-3 py-1.5 border border-slate-300 text-slate-700 font-bold hover:bg-slate-100"
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || routeStatus.valid === false}
                  className="px-4 py-1.5 bg-[#0B2545] hover:bg-[#134074] text-white font-bold flex items-center space-x-1.5 shadow-xs"
                >
                  <Send className="w-3.5 h-3.5 text-[#FFB703]" />
                  <span>SUBMIT BLOCK REQUEST</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: REQUEST CHANGE MODAL */}
      {showChangeRequestModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl max-w-md w-full">
            <div className="bg-[#0B2545] text-white p-3 flex justify-between items-center">
              <span className="font-bold text-xs uppercase">REQUEST SCHEDULE CHANGE &bull; PLANNER NOTIFICATION</span>
              <button onClick={() => setShowChangeRequestModal(false)}><X className="w-4 h-4" /></button>
            </div>
            <form onSubmit={handleSubmitChangeRequest} className="p-4 space-y-3 text-xs">
              <p className="text-slate-600 text-[11px]">
                Specify why this approved block schedule cannot be accepted. The Chief Section Controller will review your remarks and trigger dynamic re-planning.
              </p>
              <div>
                <label className="font-bold text-slate-700 block mb-1">OPERATIONAL JUSTIFICATION / REMARKS</label>
                <textarea
                  rows="3"
                  value={changeRequestRemarks}
                  onChange={(e) => setChangeRequestRemarks(e.target.value)}
                  placeholder="e.g. Machinery breakdown, crew shortage, request shift to afternoon window 14:00-16:00..."
                  className="w-full border border-slate-300 p-2 font-mono"
                  required
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2 border-t">
                <button
                  type="button"
                  onClick={() => setShowChangeRequestModal(false)}
                  className="px-3 py-1.5 border font-bold text-slate-700"
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-3 py-1.5 bg-amber-700 hover:bg-amber-800 text-white font-bold"
                >
                  SEND CHANGE REQUEST
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: EXECUTION ACTION MODAL (Section 26) */}
      {showExecutionModal && executingJob && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl max-w-md w-full">
            <div className="bg-[#0B2545] text-white p-3 flex justify-between items-center">
              <span className="font-bold text-xs uppercase">
                {execActionType === 'START' && `COMMENCE POSSESSION: ${executingJob.job_code}`}
                {execActionType === 'PROGRESS' && `UPDATE PROGRESS: ${executingJob.job_code}`}
                {execActionType === 'COMPLETE' && `COMPLETE BLOCK & CLEAR: ${executingJob.job_code}`}
              </span>
              <button onClick={() => setShowExecutionModal(false)}><X className="w-4 h-4" /></button>
            </div>

            <form onSubmit={handleSubmitExecution} className="p-4 space-y-3 text-xs">
              <div className="bg-slate-50 p-2 border font-mono text-[11px]">
                <div>Job: <strong>{executingJob.job_code}</strong> ({executingJob.work_type})</div>
                <div>Route: <strong>{executingJob.start_station_code} &rarr; {executingJob.end_station_code}</strong></div>
                <div>Estimated Duration: <strong>{executingJob.estimated_duration_min} min</strong></div>
              </div>

              {execActionType === 'START' && (
                <div>
                  <label className="font-bold text-slate-700 block mb-1">ACTUAL START TIME (MIN OF DAY, e.g. 600 = 10:00)</label>
                  <input
                    type="number"
                    value={execStartMin}
                    onChange={(e) => setExecStartMin(e.target.value)}
                    className="w-full border p-1.5 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">
                    Time: {Math.floor(execStartMin / 60).toString().padStart(2, '0')}:{(execStartMin % 60).toString().padStart(2, '0')} IST
                  </span>
                </div>
              )}

              {execActionType === 'PROGRESS' && (
                <div>
                  <label className="font-bold text-slate-700 block mb-1">COMPLETION PERCENTAGE (0 - 100%)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={execProgressPct}
                    onChange={(e) => setExecProgressPct(e.target.value)}
                    className="w-full border p-1.5 font-mono font-bold"
                    required
                  />
                </div>
              )}

              {execActionType === 'COMPLETE' && (
                <div>
                  <label className="font-bold text-slate-700 block mb-1">ACTUAL END TIME (MIN OF DAY, e.g. 660 = 11:00)</label>
                  <input
                    type="number"
                    value={execEndMin}
                    onChange={(e) => setExecEndMin(e.target.value)}
                    className="w-full border p-1.5 font-mono font-bold"
                    required
                  />
                  <span className="text-[10px] text-slate-500 font-mono">
                    Time: {Math.floor(execEndMin / 60).toString().padStart(2, '0')}:{(execEndMin % 60).toString().padStart(2, '0')} IST
                  </span>
                </div>
              )}

              <div>
                <label className="font-bold text-slate-700 block mb-1">FIELD LOG REMARKS</label>
                <textarea
                  rows="2"
                  value={execRemarks}
                  onChange={(e) => setExecRemarks(e.target.value)}
                  placeholder="Record track parameters, machine progress, speed restrictions..."
                  className="w-full border p-1.5 font-mono"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t">
                <button type="button" onClick={() => setShowExecutionModal(false)} className="px-3 py-1.5 border font-bold">CANCEL</button>
                <button type="submit" disabled={actionLoading} className="px-4 py-1.5 bg-[#0B2545] text-white font-bold">
                  {execActionType === 'START' ? 'COMMENCE WORK' : execActionType === 'PROGRESS' ? 'SAVE PROGRESS' : 'CLEAR & COMPLETE'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: EXPLAINABILITY DRAWER */}
      {explainJob && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl max-w-lg w-full p-4 space-y-3 text-xs">
            <div className="flex justify-between items-center border-b pb-2">
              <span className="font-bold text-sm text-[#0B2545]">WHY DID THIS JOB RECEIVE THIS PRIORITY?</span>
              <button onClick={() => setExplainJob(null)}><X className="w-4 h-4" /></button>
            </div>
            <div className="space-y-2">
              <div className="bg-slate-50 p-2 border font-mono">
                <div>Job: <strong>{explainJob.job_code}</strong></div>
                <div>Calculated Score: <strong className="text-blue-900">{explainJob.priority_score?.toFixed(1) || explainJob.score}</strong></div>
              </div>
              <div className="space-y-1">
                <div className="font-bold text-slate-800">Scoring Factor Breakdown:</div>
                <div className="p-2 border bg-white space-y-1 text-[11px]">
                  <div>Criticality: <strong>{explainJob.criticality?.score || explainJob.calculated_criticality || 50}</strong> ({explainJob.criticality?.reason || 'Work criticality'})</div>
                  <div>Safety Impact: <strong>{explainJob.safety_impact?.score || explainJob.calculated_safety_impact || 50}</strong> ({explainJob.safety_impact?.reason || 'Safety impact'})</div>
                  <div>Urgency: <strong>{explainJob.urgency?.score || explainJob.calculated_urgency || 50}</strong> ({explainJob.urgency?.reason || 'Due date proximity'})</div>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 italic">
                Disclaimer: Planning heuristic / decision-support scoring formula, not an official statutory Indian Railways safety manual rule.
              </p>
            </div>
            <div className="flex justify-end">
              <button onClick={() => setExplainJob(null)} className="px-3 py-1 bg-[#0B2545] text-white font-bold">CLOSE</button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 5: AUDIT TRAIL MODAL */}
      {showAuditModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-3">
          <div className="bg-white border-2 border-[#0B2545] shadow-2xl max-w-xl w-full p-4 space-y-3 text-xs flex flex-col max-h-[85vh]">
            <div className="flex justify-between items-center border-b pb-2">
              <div className="font-bold text-sm text-[#0B2545] flex items-center gap-1.5">
                <History className="w-4 h-4 text-[#134074]" />
                <span>AUDIT TRAIL — {auditJob?.job_code}</span>
              </div>
              <button onClick={() => setShowAuditModal(false)}><X className="w-4 h-4" /></button>
            </div>

            <div className="overflow-y-auto flex-1 space-y-2">
              {auditLoading ? (
                <div className="text-center py-6 text-slate-500">Loading audit history...</div>
              ) : auditLogs.length === 0 ? (
                <div className="text-center py-6 text-slate-400">No audit log entries recorded for this request.</div>
              ) : (
                auditLogs.map((a, i) => (
                  <div key={i} className="p-2 border border-slate-200 bg-slate-50 text-[11px] font-mono">
                    <div className="flex justify-between text-slate-500 text-[10px] mb-1">
                      <span>{a.timestamp ? new Date(a.timestamp).toLocaleString() : '—'}</span>
                      <strong className="text-slate-800">{a.user_name}</strong>
                    </div>
                    <div className="font-bold text-blue-900 mb-0.5">{a.action}</div>
                    {a.details && (
                      <div className="text-slate-700 bg-white p-1.5 border border-slate-200 text-[10px]">
                        {Object.entries(a.details).map(([k, v]) => (
                          <div key={k}><span className="text-slate-500">{k}:</span> {typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end pt-2 border-t">
              <button onClick={() => setShowAuditModal(false)} className="px-3 py-1 bg-[#0B2545] text-white font-bold">CLOSE</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
