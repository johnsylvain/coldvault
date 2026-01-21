// Jobs component using Alpine.js
import { 
    getJobs, getJob, createJob, updateJob, deleteJob,
    triggerBackup, getBackupRuns, cancelBackupRun, getBackupLog
} from '../api.js';
import { formatDate, escapeHtml } from '../utils/helpers.js';
import { 
    updateJobs, addExpandedLog, removeExpandedLog, isLogExpanded,
    setLogRefreshInterval, clearLogRefreshInterval, setEditingJobId, clearEditingJobId
} from '../state.js';
import { showNotification, showError } from './notifications.js';

export function jobsComponent() {
    return {
        jobs: [],
        loading: false,
        expandedLogs: new Set(),
        logRefreshIntervals: {},
        
        async init() {
            await this.load();
            // Auto-refresh every 10 seconds
            setInterval(() => this.load(), 10000);
        },
        
        async load() {
            try {
                this.loading = true;
                const jobs = await getJobs();
                this.jobs = jobs;
                updateJobs(jobs);
                
                // Load logs for expanded jobs
                jobs.forEach(job => {
                    if (this.isLogExpanded(job.id)) {
                        const isRunning = job.last_run_status === 'running';
                        this.loadJobLogs(job.id, isRunning);
                    } else if (job.last_run_status !== 'running') {
                        this.clearLogRefresh(job.id);
                    }
                });
                
                this.loading = false;
            } catch (error) {
                this.loading = false;
                showError(`Failed to load jobs: ${error.message}`);
            }
        },
        
        async triggerBackup(jobId) {
            try {
                const result = await triggerBackup(jobId);
                showNotification(`Backup triggered! Run ID: ${result.backup_run_id}`, 'info');
                this.expandLog(jobId);
                await this.load();
            } catch (error) {
                showError(`Failed to trigger backup: ${error.message}`);
            }
        },
        
        async cancelBackup(jobId) {
            try {
                const runs = await getBackupRuns(jobId, 1);
                if (runs.length === 0) {
                    showError('No backup runs found for this job');
                    await this.load();
                    return;
                }
                
                const run = runs[0];
                if (run.status !== 'running' && run.status !== 'pending') {
                    showError(`Cannot cancel backup with status: ${run.status}`);
                    await this.load();
                    return;
                }
                
                await cancelBackupRun(run.id);
                showNotification('Backup cancellation requested', 'info');
                await this.load();
            } catch (error) {
                showError(`Failed to cancel backup: ${error.message}`);
                await this.load();
            }
        },
        
        toggleLogs(jobId) {
            if (this.isLogExpanded(jobId)) {
                this.collapseLog(jobId);
            } else {
                this.expandLog(jobId);
                const job = this.jobs.find(j => j.id === jobId);
                const isRunning = job?.last_run_status === 'running';
                this.loadJobLogs(jobId, isRunning);
            }
        },
        
        expandLog(jobId) {
            this.expandedLogs.add(jobId);
            addExpandedLog(jobId);
        },
        
        collapseLog(jobId) {
            this.expandedLogs.delete(jobId);
            removeExpandedLog(jobId);
            this.clearLogRefresh(jobId);
        },
        
        isLogExpanded(jobId) {
            return this.expandedLogs.has(jobId) || isLogExpanded(jobId);
        },
        
        async loadJobLogs(jobId, autoRefresh = false) {
            try {
                const runs = await getBackupRuns(jobId, 1);
                const logContent = document.getElementById(`log-content-${jobId}`);
                
                if (!logContent) return;
                
                if (runs.length === 0) {
                    logContent.textContent = 'No backup runs found for this job.';
                    return;
                }
                
                const run = runs[0];
                const logData = await getBackupLog(run.id, 500);
                
                if (logData.log) {
                    logContent.textContent = logData.log;
                    logContent.scrollTop = logContent.scrollHeight;
                } else {
                    logContent.textContent = 'No log available for this backup run.';
                }
                
                if (autoRefresh && run.status === 'running') {
                    this.clearLogRefresh(jobId);
                    const intervalId = setInterval(() => {
                        this.loadJobLogs(jobId, false);
                    }, 2000);
                    this.logRefreshIntervals[jobId] = intervalId;
                    setLogRefreshInterval(jobId, intervalId);
                } else if (run.status !== 'running') {
                    this.clearLogRefresh(jobId);
                }
            } catch (error) {
                const logContent = document.getElementById(`log-content-${jobId}`);
                if (logContent) {
                    logContent.textContent = `Error loading logs: ${error.message}`;
                }
            }
        },
        
        clearLogRefresh(jobId) {
            if (this.logRefreshIntervals[jobId]) {
                clearInterval(this.logRefreshIntervals[jobId]);
                delete this.logRefreshIntervals[jobId];
            }
            clearLogRefreshInterval(jobId);
        },
        
        getStatusIcon(status) {
            if (status === 'running') return '<i class="ph ph-circle-notch"></i>';
            if (status === 'success') return '<i class="ph ph-check-circle"></i>';
            if (status === 'failed') return '<i class="ph ph-x-circle"></i>';
            return '<i class="ph ph-clock"></i>';
        },
        
        getStatusClass(status) {
            return status ? status.toLowerCase() : 'pending';
        },
        
        formatDate,
        escapeHtml
    };
}

// Global functions for backward compatibility (will be called from HTML)
export async function triggerBackupGlobal(jobId) {
    // This will be handled by Alpine component
    const event = new CustomEvent('trigger-backup', { detail: { jobId } });
    document.dispatchEvent(event);
}

export async function cancelBackupGlobal(jobId) {
    const event = new CustomEvent('cancel-backup', { detail: { jobId } });
    document.dispatchEvent(event);
}

export function toggleJobLogsGlobal(jobId) {
    const event = new CustomEvent('toggle-logs', { detail: { jobId } });
    document.dispatchEvent(event);
}

export function toggleMenu(jobId) {
    const menu = document.getElementById(`menu-${jobId}`);
    const isOpen = menu?.classList.contains('show');
    
    document.querySelectorAll('.dropdown-menu').forEach(m => {
        if (m.id !== `menu-${jobId}`) {
            m.classList.remove('show');
        }
    });
    
    if (menu) {
        menu.classList.toggle('show', !isOpen);
    }
}

export function closeMenu(jobId) {
    const menu = document.getElementById(`menu-${jobId}`);
    if (menu) {
        menu.classList.remove('show');
    }
}
