// Application state management
export const state = {
    // Dashboard stats
    dashboard: {
        jobs: { total: 0 },
        backups: { successful: 0, failed: 0 },
        storage: { total_bytes: 0 },
        costs: { monthly_estimate: 0 }
    },
    
    // Jobs
    jobs: [],
    expandedLogs: new Set(),
    logRefreshIntervals: {},
    
    // Current editing job
    editingJobId: null,
    
    // Current sync job
    currentSyncJobId: null,
    
    // Chart instances
    charts: {
        storage: null,
        cost: null,
        history: null
    },
    
    // Active tabs
    activeMainTab: 'jobs',
    activeMetricsTab: 'overview'
};

/**
 * Update dashboard stats
 */
export function updateDashboard(data) {
    state.dashboard = { ...state.dashboard, ...data };
}

/**
 * Update jobs list
 */
export function updateJobs(jobs) {
    state.jobs = jobs;
}

/**
 * Add expanded log
 */
export function addExpandedLog(jobId) {
    state.expandedLogs.add(jobId);
}

/**
 * Remove expanded log
 */
export function removeExpandedLog(jobId) {
    state.expandedLogs.delete(jobId);
}

/**
 * Check if log is expanded
 */
export function isLogExpanded(jobId) {
    return state.expandedLogs.has(jobId);
}

/**
 * Set log refresh interval
 */
export function setLogRefreshInterval(jobId, intervalId) {
    if (!state.logRefreshIntervals) {
        state.logRefreshIntervals = {};
    }
    state.logRefreshIntervals[jobId] = intervalId;
}

/**
 * Clear log refresh interval
 */
export function clearLogRefreshInterval(jobId) {
    if (state.logRefreshIntervals && state.logRefreshIntervals[jobId]) {
        clearInterval(state.logRefreshIntervals[jobId]);
        delete state.logRefreshIntervals[jobId];
    }
}

/**
 * Set editing job ID
 */
export function setEditingJobId(jobId) {
    state.editingJobId = jobId;
}

/**
 * Clear editing job ID
 */
export function clearEditingJobId() {
    state.editingJobId = null;
}

/**
 * Set current sync job ID
 */
export function setCurrentSyncJobId(jobId) {
    state.currentSyncJobId = jobId;
}

/**
 * Clear current sync job ID
 */
export function clearCurrentSyncJobId() {
    state.currentSyncJobId = null;
}

/**
 * Set chart instance
 */
export function setChart(name, chartInstance) {
    if (state.charts[name]) {
        state.charts[name].destroy();
    }
    state.charts[name] = chartInstance;
}

/**
 * Set active main tab
 */
export function setActiveMainTab(tab) {
    state.activeMainTab = tab;
}

/**
 * Set active metrics tab
 */
export function setActiveMetricsTab(tab) {
    state.activeMetricsTab = tab;
}
