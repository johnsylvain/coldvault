// API client module
const API_BASE = '/api';

/**
 * Fetch JSON from API endpoint
 */
export async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

/**
 * POST JSON to API endpoint
 */
export async function postJSON(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

/**
 * PUT JSON to API endpoint
 */
export async function putJSON(url, data) {
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

/**
 * DELETE request to API endpoint
 */
export async function deleteJSON(url) {
    const response = await fetch(url, {
        method: 'DELETE'
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

// Dashboard API
export async function getDashboardOverview() {
    return fetchJSON(`${API_BASE}/dashboard/overview`);
}

// Jobs API
export async function getJobs() {
    return fetchJSON(`${API_BASE}/jobs/`);
}

export async function getJob(jobId) {
    return fetchJSON(`${API_BASE}/jobs/${jobId}`);
}

export async function createJob(jobData) {
    return postJSON(`${API_BASE}/jobs/`, jobData);
}

export async function updateJob(jobId, jobData) {
    return putJSON(`${API_BASE}/jobs/${jobId}`, jobData);
}

export async function deleteJob(jobId) {
    return deleteJSON(`${API_BASE}/jobs/${jobId}`);
}

// Backups API
export async function triggerBackup(jobId) {
    return postJSON(`${API_BASE}/backups/${jobId}/run`, {});
}

export async function getBackupRuns(jobId, limit = 1) {
    return fetchJSON(`${API_BASE}/backups/runs?job_id=${jobId}&limit=${limit}`);
}

export async function cancelBackupRun(runId) {
    return postJSON(`${API_BASE}/backups/runs/${runId}/cancel`, {});
}

export async function getBackupLog(runId, tail = 500) {
    return fetchJSON(`${API_BASE}/backups/runs/${runId}/log?tail=${tail}`);
}

// Sync API
export async function syncJob(jobId, dryRun = true) {
    if (dryRun) {
        return fetchJSON(`${API_BASE}/jobs/${jobId}/sync?dry_run=true`);
    } else {
        return postJSON(`${API_BASE}/jobs/${jobId}/sync?dry_run=false`, {});
    }
}

// Metrics API
export async function getMetricsSummary(days = 30) {
    return fetchJSON(`${API_BASE}/metrics/summary?days=${days}`);
}

export async function getMetricsHistory(days = 30) {
    return fetchJSON(`${API_BASE}/metrics/history?days=${days}`);
}

export async function getMetricsProjection(daysAhead = 30) {
    return fetchJSON(`${API_BASE}/metrics/projection?days_ahead=${daysAhead}`);
}
