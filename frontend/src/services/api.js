import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('abps_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Maintenance Endpoints
export const getMaintenanceJobs = (params) => api.get('/maintenance/jobs', { params });
export const createMaintenanceJob = (data) => api.post('/maintenance/jobs', data);
export const updateMaintenanceJob = (id, data) => api.put(`/maintenance/jobs/${id}`, data);
export const submitMaintenanceJob = (id) => api.post(`/maintenance/jobs/${id}/submit`);
export const getDefectPosition = () => api.get('/maintenance/defects');
export const getOverduePosition = () => api.get('/maintenance/overdue');
export const getAssets = () => api.get('/maintenance/assets').catch(() => ({ data: [] }));
export const getResources = () => api.get('/maintenance/resources').catch(() => ({ data: [] }));

// Dedicated Block Request Workflow Endpoints (SIH26027)
export const getBlockRequests = (params) => api.get('/block-requests', { params });
export const createBlockRequest = (data) => api.post('/block-requests', data);
export const getBlockRequestById = (id) => api.get(`/block-requests/${id}`);
export const submitBlockRequest = (id) => api.post(`/block-requests/${id}/submit`);
export const optimizeBlockRequest = (id) => api.post(`/block-requests/${id}/optimize`);
export const approveBlockRequest = (id, data = {}) => api.post(`/block-requests/${id}/approve`, data);
export const modifyBlockRequest = (id, data) => api.post(`/block-requests/${id}/modify`, data);
export const rejectBlockRequest = (id, data) => api.post(`/block-requests/${id}/reject`, data);
export const requestChangeBlockRequest = (id, data) => api.post(`/block-requests/${id}/request-change`, data);
export const acceptBlockRequest = (id, data = {}) => api.post(`/block-requests/${id}/accept`, data);
export const startBlockRequest = (id, data = {}) => api.post(`/block-requests/${id}/start`, data);
export const completeBlockRequest = (id, data = {}) => api.post(`/block-requests/${id}/complete`, data);
export const getBlockRequestAudit = (id) => api.get(`/block-requests/${id}/audit`);

// Multi-Department Coordinated Block Planning Endpoints (SIH26027)
export const checkCoordinationCompatibility = (jobIds) =>
  api.post('/block-requests/coordination/check', { job_ids: jobIds });
export const optimizeCoordinatedBlock = (data) =>
  api.post('/block-requests/coordination/optimize', data);
export const optimizeRequestPool = (data = {}) =>
  api.post('/block-requests/pool/optimize', data);
export const getCoordinatedBlockPlan = (id) =>
  api.get(`/coordinated-block-plans/${id}`);
export const approveCoordinatedBlockPlan = (id, data = {}) =>
  api.post(`/coordinated-block-plans/${id}/approve`, data);
export const modifyCoordinatedBlockPlan = (id, data) =>
  api.post(`/coordinated-block-plans/${id}/modify`, data);
export const rejectCoordinatedBlockPlan = (id, data) =>
  api.post(`/coordinated-block-plans/${id}/reject`, data);
export const whatIfCoordinatedBlockPlan = (id, data) =>
  api.post(`/coordinated-block-plans/${id}/what-if`, data);
export const replanCoordinatedBlockPlan = (id, data = {}) =>
  api.post(`/coordinated-block-plans/${id}/replan`, data);
export const getCoordinatedPlanAudit = (id) =>
  api.get(`/coordinated-block-plans/${id}/audit`);


// Departments Master
export const getDepartments = () => api.get('/departments');

// Railway Infrastructure & Movement Endpoints
export const getStations = () => api.get('/railway/stations');
export const resolveStation = (code) => api.get('/railway/stations/resolve', { params: { code } });
export const searchStations = (q) => api.get('/railway/stations/search', { params: { q } });
export const validateRoute = (start, end) => api.get('/railway/routes/validate', { params: { start, end } });
export const getRailwayRoute = (start, end) => api.get('/railway/route', { params: { from: start, to: end } });
export const getSections = (corridorId) => api.get('/railway/sections', { params: { corridor_id: corridorId } });
export const getCorridors = (params) => api.get('/railway/corridors', { params: { canonical_only: true, ...params } });
export const getCorridorById = (id) => api.get(`/railway/corridors/${id}`);
export const getCorridorStations = (id) => api.get(`/railway/corridors/${id}/stations`);
export const getCorridorSections = (id) => api.get(`/railway/corridors/${id}/sections`);
export const getCorridorGeometry = (id) => api.get(`/railway/corridors/${id}/geometry`);
export const getTrains = () => api.get('/railway/trains');
export const getTrainsBetween = (fromStation, toStation) =>
  api.get('/trains/between', { params: { from_station: fromStation, to_station: toStation } });
export const getLiveTrainMovements = (corridorId = null, refresh = false) =>
  api.get('/railway/movements', {
    params: {
      ...(corridorId ? { corridor_id: corridorId } : {}),
      ...(refresh ? { refresh: true } : {})
    }
  });
export const getCorridorTrains = (corridorId) => api.get(`/railway/corridors/${corridorId}/trains`);
export const getCorridorLiveTrains = (corridorId) => api.get(`/railway/corridors/${corridorId}/trains/live`);
export const getTrainOccupancies = () => api.get('/railway/occupancy');
export const getTimeDistanceData = (corridorId) => api.get('/railway/time-distance', { params: { corridor_id: corridorId } });
export const getDataStatus = () => api.get('/railway/data-status');
export const getStationLiveBoard = (code, hours = 4) => api.get(`/railway/stations/${code}/live`, { params: { hours } });
export const getTrainRouteGeometry = (number) => api.get(`/railway/trains/${number}/geometry`);

// Maintenance Priority & Override Endpoints
export const getJobPriorityExplanation = (id) => api.get(`/maintenance/requests/${id}/explanation`);
export const overrideJobPriority = (id, data) => api.post(`/maintenance/requests/${id}/override`, data);


// Planning & Optimization Endpoints
export const getWindows = (corridorId) => api.get('/planning/windows', { params: { corridor_id: corridorId } });
export const runOptimization = (data) => api.post('/planning/optimize', data);
export const getActivePlan = (strategy = 'PLAN_A') => api.get('/planning/plans/active', { params: { strategy } });
export const getPlanById = (id) => api.get(`/planning/plans/${id}`);
export const getKPIComparison = () => api.get('/planning/comparison');
export const validatePlan = (id) => api.post(`/planning/plans/${id}/validate`);
export const approvePlan = (id, data) => api.post(`/planning/plans/${id}/approve`, data);
export const lockJob = (data) => api.post('/planning/jobs/lock', data);
export const getJobExplanation = (id, planId) => api.get(`/planning/jobs/${id}/explanation`, { params: { plan_id: planId } });
export const getCompatibilityGraph = () => api.get('/planning/compatibility');
export const getPlannerRequestReview = (jobId) => api.get(`/planning/requests/${jobId}/planner-review`);

// Department Plan Handshake
export const departmentAcceptPlan = (planId, data = {}) => api.post(`/planning/plans/${planId}/department-accept`, data);
export const departmentRequestChange = (planId, data) => api.post(`/planning/plans/${planId}/department-request-change`, data);
export const departmentDeclinePlan = (planId, data) => api.post(`/planning/plans/${planId}/department-decline`, data);

// Execution Management Endpoints
export const getExecutionRecords = (params) => api.get('/execution/records', { params });
export const getJobExecution = (jobId) => api.get(`/execution/${jobId}`);
export const startExecution = (data) => api.post('/execution/start', data);
export const updateExecutionProgress = (data) => api.post('/execution/progress', data);
export const completeExecution = (data) => api.post('/execution/complete', data);
export const cancelExecution = (data) => api.post('/execution/cancel', data);

// Notification Endpoints
export const getNotifications = (limit = 50) => api.get('/notifications', { params: { limit } });
export const getUnreadNotificationCount = () => api.get('/notifications/unread-count');
export const markNotificationRead = (id) => api.post(`/notifications/${id}/read`);
export const markAllNotificationsRead = () => api.post('/notifications/read-all');

// Dynamic Replanning & Disturbance Endpoints
export const simulateTrainDelay = (data) => api.post('/dynamic/simulate-delay', data);
export const dynamicReplan = (data) => api.post('/dynamic/replan', data);
export const runDynamicReplanning = (data) => api.post('/replanning/run', data);

// What-If Simulation
export const simulateWhatIf = (data) => api.post('/whatif/simulate', data);
export const createWhatIfScenario = (data) => api.post('/what-if', data);
export const getWhatIfScenario = (id) => api.get(`/what-if/${id}`);

// Live Telemetry & Health Endpoints (Section 45)
export const getLiveHealth = () => api.get('/live/health');
export const getLiveCorridorData = (corridorId, refresh = false) => api.get(`/live/corridors/${corridorId}`, { params: refresh ? { refresh: true } : {} });
export const getLiveTrainTelemetry = (trainNumber) => api.get(`/live/trains/${trainNumber}`);

// Availability Engine Endpoints (Section 45)
export const getAvailability = (params) => api.get('/availability', { params });
export const checkAvailabilityFeasibility = (data) => api.post('/availability/check', data);

// Global CP-SAT Optimization Endpoints (Section 45)
export const runStandardOptimization = (data) => api.post('/optimization/run', data);
export const getStandardOptimizationPlans = (params) => api.get('/optimization/plans', { params });

// Railway Station Master Endpoints (Primary Source: documents/TN-station list.pdf)
export const getStationMaster = (code) => api.get(`/stations/${code}`);
export const searchStationsV2 = (q, state = '', limit = 30) => api.get('/stations/search', { params: { q, state, limit } });
export const getTamilNaduStations = () => api.get('/stations/tamil-nadu');
export const getStationAudit = () => api.get('/stations/audit');

// Reports & Audit
export const getWeeklyReport = () => api.get('/reports/weekly');
export const getMonthlyReport = () => api.get('/reports/monthly');
export const getOverdueReport = () => api.get('/reports/overdue');
export const getCriticalReport = () => api.get('/reports/critical');
export const getMaintenancePositionReport = () => api.get('/reports/position');
export const getAuditLogs = () => api.get('/reports/audit');
export const getPlannerActions = () => api.get('/reports/actions');
export const getPlanExportUrl = (id) => `${API_BASE_URL}/reports/plans/${id}/export-csv`;

// Planning Scenario Ingestion & Reset
export const resetPlanningScenario = () => api.post('/scenario/load-corridor-scenario');

export default api;

