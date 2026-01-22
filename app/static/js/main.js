// Main entry point - Initialize Alpine.js and coordinate components
// Note: Alpine.js is loaded via CDN, so we don't need to import it here

// Import API and utility functions
import * as api from './api.js';
import { formatStorage, formatCost } from './utils/formatters.js';
import { showNotification, showError } from './components/notifications.js';
import { router } from './utils/router.js';
import { createClickableDate, initializeClickableDates, formatAbsoluteDate } from './utils/helpers.js';

// Expose router globally for onclick handlers
window.router = router;

// Mobile menu functions
window.toggleMobileMenu = () => {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const toggle = document.getElementById('mobile-menu-toggle');
    const body = document.body;
    
    if (sidebar && overlay) {
        const isOpening = !sidebar.classList.contains('open');
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
        
        // Prevent body scroll when menu is open
        if (isOpening) {
            body.style.overflow = 'hidden';
        } else {
            body.style.overflow = '';
        }
        
        // Update icon
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (icon) {
                if (sidebar.classList.contains('open')) {
                    icon.className = 'ph ph-x';
                } else {
                    icon.className = 'ph ph-list';
                }
            }
        }
    }
};

window.closeMobileMenu = () => {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const toggle = document.getElementById('mobile-menu-toggle');
    const body = document.body;
    
    if (sidebar && overlay) {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
        body.style.overflow = '';
        
        // Update icon
        if (toggle) {
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.className = 'ph ph-list';
            }
        }
    }
};

// Close mobile menu when clicking on a nav item
function setupMobileMenuClose() {
    // Use event delegation for dynamically added nav items
    document.addEventListener('click', (e) => {
        if (e.target.closest('.nav-item') && window.innerWidth <= 768) {
            setTimeout(() => closeMobileMenu(), 100);
        }
    });
    
    // Also close on window resize if switching to desktop
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (window.innerWidth > 768) {
                closeMobileMenu();
            }
        }, 250);
    });
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
    // Set up routes
    setupRoutes();
    
    // Initialize router (this will handle the initial route)
    router.init();
    
    // Set up mobile menu close handlers
    setupMobileMenuClose();
    
    // Auto-refresh every 10 seconds
    setInterval(() => {
        const currentPath = router.getCurrentRoute();
        if (currentPath === '/dashboard' || currentPath === '/') {
            loadDashboard();
        } else if (currentPath === '/jobs') {
            loadJobs();
        }
    }, 10000);
    
    // Update runtime displays every second for running jobs
    setInterval(() => {
        // This will be handled by updateRunningJobRuntimes which sets up per-job intervals
        // But we can also refresh the dashboard activity if on dashboard page
        const currentPath = router.getCurrentRoute();
        if (currentPath === '/dashboard' || currentPath === '/') {
            // Refresh activity display for running jobs
            const activityItems = document.querySelectorAll('.activity-item');
            activityItems.forEach(item => {
                const statusIcon = item.querySelector('.activity-status i');
                if (statusIcon && statusIcon.className.includes('ph-circle-notch')) {
                    // This is a running job, update its display
                    const meta = item.querySelector('.activity-meta');
                    if (meta) {
                        const text = meta.textContent;
                        // Extract start time from the text and recalculate
                        // For now, we'll rely on the 10-second refresh for activity
                    }
                }
            });
        }
    }, 1000);
});

function setupRoutes() {
    // Dashboard route
    router.register('/dashboard', () => {
        showTab('dashboard');
        updateNavActive('dashboard');
        loadDashboard();
    });

    router.register('/', () => {
        router.navigate('/dashboard', true);
    });

    // Jobs route
    router.register('/jobs', () => {
        showTab('jobs');
        updateNavActive('jobs');
        loadJobs();
    });

    // Metrics routes
    router.register('/metrics', () => {
        router.navigate('/metrics/overview', true);
    });

    router.register('/metrics/overview', () => {
        showTab('metrics');
        updateNavActive('metrics');
        showMetricsTab('overview');
    });

    router.register('/metrics/history', () => {
        showTab('metrics');
        updateNavActive('metrics');
        showMetricsTab('history');
    });

    router.register('/metrics/projection', () => {
        showTab('metrics');
        updateNavActive('metrics');
        showMetricsTab('projection');
    });

    // Restore route
    router.register('/restore', () => {
        showTab('restore');
        updateNavActive('restore');
        loadRestorePage();
    });
}

function showTab(tab) {
    // Update content visibility
    document.querySelectorAll('.main-tab-content').forEach(content => content.classList.remove('active'));
    const targetContent = document.getElementById(`main-tab-${tab}`);
    if (targetContent) {
        targetContent.classList.add('active');
    }
    
    // Update nav items (only top-level, not submenu items)
    document.querySelectorAll('.nav-item').forEach(item => {
        if (!item.closest('.submenu') && !item.classList.contains('submenu-item')) {
            item.classList.remove('active');
        }
    });
    
    // Activate the correct nav item
    if (tab === 'dashboard') {
        const dashboardItem = Array.from(document.querySelectorAll('.nav-item')).find(item => {
            const icon = item.querySelector('i');
            return icon && icon.className.includes('ph-gauge');
        });
        if (dashboardItem) dashboardItem.classList.add('active');
    } else if (tab === 'jobs') {
        const jobsItem = Array.from(document.querySelectorAll('.nav-item')).find(item => {
            const icon = item.querySelector('i');
            return icon && icon.className.includes('ph-list-bullets');
        });
        if (jobsItem) jobsItem.classList.add('active');
    } else if (tab === 'metrics') {
        const metricsNav = document.getElementById('metrics-nav-item');
        if (metricsNav) {
            metricsNav.classList.add('active');
            if (!metricsNav.classList.contains('expanded')) {
                metricsNav.classList.add('expanded');
            }
        }
    }
}

function updateNavActive(activeTab) {
    // Update main nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        if (!item.closest('.submenu') && !item.classList.contains('submenu-item')) {
            item.classList.remove('active');
        }
    });

    // Activate the correct nav item
    if (activeTab === 'dashboard') {
        const dashboardItem = Array.from(document.querySelectorAll('.nav-item')).find(item => {
            const icon = item.querySelector('i');
            return icon && icon.className.includes('ph-gauge');
        });
        if (dashboardItem) dashboardItem.classList.add('active');
    } else if (activeTab === 'jobs') {
        const jobsItem = Array.from(document.querySelectorAll('.nav-item')).find(item => {
            const icon = item.querySelector('i');
            return icon && icon.className.includes('ph-list-bullets');
        });
        if (jobsItem) jobsItem.classList.add('active');
    } else if (activeTab === 'metrics') {
        const metricsItem = document.getElementById('metrics-nav-item');
        if (metricsItem) {
            metricsItem.classList.add('active');
            if (!metricsItem.classList.contains('expanded')) {
                metricsItem.classList.add('expanded');
            }
        }
    } else if (activeTab === 'restore') {
        const restoreItem = Array.from(document.querySelectorAll('.nav-item')).find(item => {
            const icon = item.querySelector('i');
            return icon && icon.className.includes('ph-arrow-counter-clockwise');
        });
        if (restoreItem) restoreItem.classList.add('active');
    }
}

// Essential functions for page loading
async function loadDashboard() {
    try {
        const overview = await api.getDashboardOverview();
        
        // Update stat cards
        document.getElementById('stat-jobs').textContent = overview.jobs.total;
        const jobsEnabled = document.getElementById('stat-jobs-enabled');
        if (jobsEnabled) {
            jobsEnabled.textContent = `${overview.jobs.enabled} enabled`;
        }
        
        const successRate = document.getElementById('stat-success-rate');
        if (successRate) {
            successRate.textContent = `${overview.backups.success_rate.toFixed(1)}%`;
        }
        document.getElementById('stat-successful').textContent = `${overview.backups.successful} successful`;
        
        document.getElementById('stat-failed').textContent = overview.backups.failed;
        const totalRuns = document.getElementById('stat-total-runs');
        if (totalRuns) {
            totalRuns.textContent = `${overview.backups.total} total runs`;
        }
        
        document.getElementById('stat-storage').textContent = formatStorage(overview.storage.total_bytes);
        const storageTb = document.getElementById('stat-storage-tb');
        if (storageTb) {
            storageTb.textContent = `${overview.storage.total_tb.toFixed(2)} TB`;
        }
        
        document.getElementById('stat-cost').textContent = formatCost(overview.costs.monthly_estimate);
        const annualCost = document.getElementById('stat-annual-cost');
        if (annualCost) {
            const annual = overview.costs.monthly_estimate * 12;
            annualCost.textContent = `${formatCost(annual)}/year`;
        }
        
        // Load recent activity
        loadRecentActivity(overview.recent_activity || []);
        
        // Load job status overview
        await loadJobStatusOverview();
        
        // Load storage breakdown
        await loadStorageBreakdown();
    } catch (error) {
        showError(`Failed to load dashboard: ${error.message}`);
    }
}

async function loadRecentActivity(activities) {
    const container = document.getElementById('recent-activity');
    if (!container) return;
    
    if (!activities || activities.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">No recent activity</div>';
        return;
    }
    
    // Get job names for display
    const jobs = await api.getJobs();
    const jobMap = new Map(jobs.map(j => [j.id, j.name]));
    
    container.innerHTML = activities.map(activity => {
        const jobName = jobMap.get(activity.job_id) || `Job #${activity.job_id}`;
        const status = activity.status || 'unknown';
        const statusClass = status.toLowerCase();
        const startedAt = activity.started_at ? new Date(activity.started_at) : null;
        
        let durationText = 'N/A';
        if (status === 'running' && activity.elapsed_seconds !== null && activity.elapsed_seconds !== undefined) {
            // Show elapsed time for running jobs
            durationText = formatDuration(activity.elapsed_seconds);
            if (activity.projected_completion_at) {
                const projectedAt = new Date(activity.projected_completion_at);
                const timeUntil = Math.max(0, Math.round((projectedAt - new Date()) / 1000));
                durationText += ` (est. ${formatDuration(timeUntil)} remaining)`;
            }
        } else if (activity.duration_seconds) {
            durationText = formatDuration(activity.duration_seconds);
        }
        
        const statusIcon = status === 'success' ? 'ph-check-circle' :
                          status === 'failed' ? 'ph-x-circle' :
                          status === 'running' ? 'ph-circle-notch' :
                          'ph-clock';
        
        return `
            <div class="activity-item">
                <div class="activity-status status-${statusClass}">
                    <i class="ph ${statusIcon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${jobName}</div>
                    <div class="activity-meta">
                        ${startedAt ? createClickableDate(activity.started_at) : 'Unknown time'} • ${durationText}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Initialize clickable dates
    initializeClickableDates(container);
}

async function loadJobStatusOverview() {
    const container = document.getElementById('job-status-overview');
    if (!container) return;
    
    try {
        const jobs = await api.getJobs();
        
        if (jobs.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">No jobs configured</div>';
            return;
        }
        
        container.innerHTML = jobs.map(job => {
            const status = job.last_run_status || 'pending';
            const statusClass = status.toLowerCase();
            const statusIcon = status === 'success' ? 'ph-check-circle' :
                              status === 'failed' ? 'ph-x-circle' :
                              status === 'running' ? 'ph-circle-notch' :
                              'ph-clock';
            
            const lastRun = job.last_run_at ? createClickableDate(job.last_run_at, { fallback: 'Never' }) : 'Never';
            const nextRun = job.next_run_at ? createClickableDate(job.next_run_at, { fallback: 'N/A' }) : 'N/A';
            
            return `
                <div class="job-status-item">
                    <div class="job-status-info">
                        <div class="job-status-name">${job.name}</div>
                        <div class="job-status-meta">
                            <span><i class="ph ph-calendar"></i> Last: ${lastRun}</span>
                            ${job.next_run_at ? `<span><i class="ph ph-calendar-check"></i> Next: ${nextRun}</span>` : ''}
                        </div>
                    </div>
                    <div class="job-status-badge status-${statusClass}">
                        <i class="ph ${statusIcon}"></i>
                        <span>${status}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        // Initialize clickable dates
        initializeClickableDates(container);
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load jobs: ${error.message}</div>`;
    }
}

async function loadStorageBreakdown() {
    const container = document.getElementById('storage-breakdown');
    if (!container) return;
    
    try {
        const jobs = await api.getJobs();
        const breakdown = [];
        
        for (const job of jobs) {
            try {
                const stats = await api.getJobStats(job.id);
                if (stats.snapshots && stats.snapshots.total_size_bytes > 0) {
                    breakdown.push({
                        name: job.name,
                        size: stats.snapshots.total_size_bytes,
                        count: stats.snapshots.count
                    });
                }
            } catch (error) {
                console.error(`Failed to load stats for job ${job.id}:`, error);
            }
        }
        
        if (breakdown.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted);">No storage data available</div>';
            return;
        }
        
        // Sort by size descending
        breakdown.sort((a, b) => b.size - a.size);
        const totalSize = breakdown.reduce((sum, item) => sum + item.size, 0);
        
        container.innerHTML = breakdown.map(item => {
            const percentage = (item.size / totalSize * 100).toFixed(1);
            return `
                <div class="storage-item">
                    <div class="storage-item-header">
                        <div class="storage-item-name">${item.name}</div>
                        <div class="storage-item-size">${formatStorage(item.size)}</div>
                    </div>
                    <div class="storage-item-bar">
                        <div class="storage-item-bar-fill" style="width: ${percentage}%"></div>
                    </div>
                    <div class="storage-item-meta">
                        <span>${item.count} snapshots</span>
                        <span>${percentage}% of total</span>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load storage breakdown: ${error.message}</div>`;
    }
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

// Track which job logs are expanded
const expandedLogs = new Set();
window.logRefreshIntervals = {};

async function loadJobs() {
    try {
        const jobs = await api.getJobs();
        console.log('loadJobs: Fetched jobs from API:', jobs.length, jobs);
        const jobsList = document.getElementById('jobs-list');
        
        if (!jobsList) {
            console.error('loadJobs: jobs-list element not found!');
            return;
        }
        
        if (jobs.length === 0) {
            jobsList.innerHTML = '<p>No jobs configured. Create your first backup job!</p>';
            return;
        }
        
        console.log('loadJobs: Rendering', jobs.length, 'jobs');
        jobsList.innerHTML = jobs.map(job => {
            const isRunning = job.last_run_status === 'running';
            const wasExpanded = expandedLogs.has(job.id);
            const shouldAutoExpand = isRunning && !wasExpanded;
            
            if (shouldAutoExpand) {
                expandedLogs.add(job.id);
            }
            
            const statusIcon = job.last_run_status === 'running' ? '<i class="ph ph-circle-notch"></i>' : 
                                  job.last_run_status === 'success' ? '<i class="ph ph-check-circle"></i>' :
                                  job.last_run_status === 'failed' ? '<i class="ph ph-x-circle"></i>' :
                                  '<i class="ph ph-clock"></i>';
            const statusText = job.last_run_status || 'Pending';
            const statusClass = job.last_run_status ? job.last_run_status.toLowerCase() : 'pending';
            
            // Build runtime display for running jobs
            // Note: We don't create runtime displays here for running jobs because
            // updateRunningJobRuntimes() will handle it to avoid duplicates
            let runtimeDisplay = '';
            
            return `
                <div class="job-item" id="job-${job.id}">
                    <div class="job-header">
                        <div class="job-status-indicator status-${statusClass}"></div>
                        <span class="status-badge-large status-${statusClass}">
                            ${statusIcon}
                            ${statusText}
                        </span>
                        <div class="job-info">
                            <h4>${job.name}</h4>
                            <div class="meta">
                                <span class="job-meta-item">
                                    <i class="ph ph-folder"></i>
                                    <span>${job.job_type}</span>
                                </span>
                                <span class="job-meta-item">
                                    <i class="ph ph-clock-clockwise"></i>
                                    <span>${job.schedule}</span>
                                </span>
                                ${runtimeDisplay}
                                ${job.last_run_at && !isRunning ? `
                                <span class="job-meta-item">
                                    <i class="ph ph-calendar"></i>
                                    ${createClickableDate(job.last_run_at)}
                                </span>
                                ` : ''}
                            </div>
                        </div>
                        <div class="job-actions">
                            ${isRunning ? 
                                `<button class="btn btn-danger" onclick="cancelBackup(${job.id})"><i class="ph ph-stop"></i> Cancel</button>` :
                                `<button class="btn" onclick="triggerBackup(${job.id})"><i class="ph ph-play"></i> Run</button>`
                            }
                            <div style="position: relative;">
                                <button class="menu-button" onclick="toggleMenu(${job.id})" id="menu-btn-${job.id}">
                                    <i class="ph ph-dots-three-vertical"></i>
                                </button>
                                <div class="dropdown-menu" id="menu-${job.id}">
                                    <button class="dropdown-item" onclick="syncJob(${job.id}); closeMenu(${job.id})">
                                        <i class="ph ph-arrows-clockwise"></i>
                                        <span>Sync with S3</span>
                                    </button>
                                    <button class="dropdown-item warning" onclick="editJob(${job.id}); closeMenu(${job.id})">
                                        <i class="ph ph-pencil"></i>
                                        <span>Edit</span>
                                    </button>
                                    <button class="dropdown-item danger" onclick="deleteJob(${job.id}); closeMenu(${job.id})">
                                        <i class="ph ph-trash"></i>
                                        <span>Delete</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="job-footer">
                        <div class="log-toggle ${wasExpanded || shouldAutoExpand ? 'expanded' : ''}" onclick="toggleJobLogs(${job.id})" id="log-toggle-${job.id}">
                            <i class="ph ph-caret-right"></i>
                            <span>${wasExpanded || shouldAutoExpand ? 'Hide' : 'Show'} logs</span>
                        </div>
                        <div class="job-logs ${wasExpanded || shouldAutoExpand ? 'expanded' : ''}" id="job-logs-${job.id}">
                            <div class="log-content-inline" id="log-content-${job.id}">Loading logs...</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        // Initialize clickable dates
        initializeClickableDates(jobsList);
        
        // Load logs for expanded jobs
        jobs.forEach(job => {
            const logsDiv = document.getElementById(`job-logs-${job.id}`);
            const isExpanded = logsDiv && logsDiv.classList.contains('expanded');
            
            if (isExpanded) {
                const isRunning = job.last_run_status === 'running';
                loadJobLogs(job.id, isRunning);
            } else if (job.last_run_status !== 'running') {
                if (window.logRefreshIntervals && window.logRefreshIntervals[job.id]) {
                    clearInterval(window.logRefreshIntervals[job.id]);
                    delete window.logRefreshIntervals[job.id];
                }
            }
        });
        
        // Set up real-time runtime updates for running jobs
        updateRunningJobRuntimes(jobs);
    } catch (error) {
        document.getElementById('jobs-list').innerHTML = `<div class="error">Failed to load jobs: ${error.message}</div>`;
    }
}

function updateRunningJobRuntimes(jobs) {
    // Clear existing runtime update intervals
    if (window.runtimeUpdateIntervals) {
        Object.values(window.runtimeUpdateIntervals).forEach(interval => clearInterval(interval));
    }
    window.runtimeUpdateIntervals = {};
    
    // Set up intervals for running jobs
    jobs.forEach(job => {
        if (job.last_run_status === 'running' && job.current_run_started_at) {
            const startTime = new Date(job.current_run_started_at);
            const projectedCompletion = job.projected_completion_at ? new Date(job.projected_completion_at) : null;
            
            // Update immediately
            updateJobRuntimeDisplay(job.id, startTime, projectedCompletion);
            
            // Update every second
            window.runtimeUpdateIntervals[job.id] = setInterval(() => {
                updateJobRuntimeDisplay(job.id, startTime, projectedCompletion);
            }, 1000);
        }
    });
}

function updateJobRuntimeDisplay(jobId, startTime, projectedCompletion) {
    const jobItem = document.getElementById(`job-${jobId}`);
    if (!jobItem) return;
    
    const now = new Date();
    // Ensure elapsed time is always positive (handle timezone/clock sync issues)
    const elapsed = Math.max(0, Math.floor((now - startTime) / 1000));
    
    // Find and update runtime display
    const metaContainer = jobItem.querySelector('.job-info .meta');
    if (!metaContainer) return;
    
    // Remove existing runtime displays
    const existingRuntimeDisplays = metaContainer.querySelectorAll('.runtime-display');
    existingRuntimeDisplays.forEach(el => el.remove());
    
    // Create new runtime display
    const runtimeItem = document.createElement('span');
    runtimeItem.className = 'job-meta-item runtime-display';
    runtimeItem.innerHTML = `<i class="ph ph-timer"></i><span>Running: ${formatDuration(elapsed)}</span>`;
    
    // Insert after schedule item
    const scheduleItem = Array.from(metaContainer.children).find(item => {
        const icon = item.querySelector('i');
        return icon && icon.className.includes('ph-clock-clockwise');
    });
    if (scheduleItem) {
        // Insert after schedule item
        if (scheduleItem.nextSibling) {
            metaContainer.insertBefore(runtimeItem, scheduleItem.nextSibling);
        } else {
            metaContainer.appendChild(runtimeItem);
        }
    } else {
        metaContainer.appendChild(runtimeItem);
    }
    
    // Add projected completion if available
    if (projectedCompletion) {
        const timeUntil = Math.max(0, Math.floor((projectedCompletion - now) / 1000));
        const projectedItem = document.createElement('span');
        projectedItem.className = 'job-meta-item runtime-display';
        projectedItem.innerHTML = `<i class="ph ph-hourglass"></i><span>Est. ${formatDuration(timeUntil)} remaining</span>`;
        metaContainer.appendChild(projectedItem);
    }
}

async function loadJobLogs(jobId, autoRefresh = false) {
    try {
        const runs = await api.getBackupRuns(jobId, 1);
        const logContent = document.getElementById(`log-content-${jobId}`);
        
        if (runs.length === 0) {
            logContent.textContent = 'No backup runs found for this job.';
            return;
        }
        
        const run = runs[0];
        const logData = await api.getBackupLog(run.id, 500);
        
        if (logData.log) {
            logContent.textContent = logData.log;
            logContent.scrollTop = logContent.scrollHeight;
        } else {
            logContent.textContent = 'No log available for this backup run.';
        }
        
        if (autoRefresh && run.status === 'running') {
            if (window.logRefreshIntervals && window.logRefreshIntervals[jobId]) {
                clearInterval(window.logRefreshIntervals[jobId]);
            }
            
            if (!window.logRefreshIntervals) {
                window.logRefreshIntervals = {};
            }
            
            window.logRefreshIntervals[jobId] = setInterval(() => {
                loadJobLogs(jobId, false);
            }, 2000);
        } else if (run.status !== 'running') {
            if (window.logRefreshIntervals && window.logRefreshIntervals[jobId]) {
                clearInterval(window.logRefreshIntervals[jobId]);
                delete window.logRefreshIntervals[jobId];
            }
        }
    } catch (error) {
        const logContent = document.getElementById(`log-content-${jobId}`);
        logContent.textContent = `Error loading logs: ${error.message}`;
    }
}

// Global functions for backward compatibility with HTML onclick handlers
window.triggerBackup = async (jobId) => {
    try {
        const result = await api.triggerBackup(jobId);
        showNotification(`Backup triggered! Run ID: ${result.backup_run_id}`, 'info');
        expandedLogs.add(jobId);
        loadJobs();
    } catch (error) {
        showError(`Failed to trigger backup: ${error.message}`);
    }
};

window.cancelBackup = async (jobId) => {
    try {
        const runs = await api.getBackupRuns(jobId, 1);
        if (runs.length === 0) {
            showError('No backup runs found for this job');
            loadJobs();
            return;
        }
        
        const run = runs[0];
        if (run.status !== 'running' && run.status !== 'pending') {
            showError(`Cannot cancel backup with status: ${run.status}`);
            loadJobs();
            return;
        }
        
        const result = await api.cancelBackupRun(run.id);
        showNotification(result.message || `Backup cancellation requested`, 'info');
        loadJobs();
    } catch (error) {
        showError(`Failed to cancel backup: ${error.message}`);
        loadJobs();
    }
};

window.toggleJobLogs = (jobId) => {
    const logsDiv = document.getElementById(`job-logs-${jobId}`);
    const toggle = document.getElementById(`log-toggle-${jobId}`);
    
    if (logsDiv.classList.contains('expanded')) {
        logsDiv.classList.remove('expanded');
        toggle.classList.remove('expanded');
        toggle.innerHTML = '<i class="ph ph-caret-right"></i><span>Show logs</span>';
        expandedLogs.delete(jobId);
        if (window.logRefreshIntervals && window.logRefreshIntervals[jobId]) {
            clearInterval(window.logRefreshIntervals[jobId]);
            delete window.logRefreshIntervals[jobId];
        }
    } else {
        logsDiv.classList.add('expanded');
        toggle.classList.add('expanded');
        toggle.innerHTML = '<i class="ph ph-caret-right"></i><span>Hide logs</span>';
        expandedLogs.add(jobId);
        const job = Array.from(document.querySelectorAll('.job-item')).find(el => el.id === `job-${jobId}`);
        const statusBadge = job?.querySelector('.status-badge-large');
        const isRunning = statusBadge?.textContent.toLowerCase().includes('running');
        loadJobLogs(jobId, isRunning);
    }
};

let editingJobId = null;

window.showCreateJobModal = () => {
    console.log('showCreateJobModal: Clearing editing state');
    editingJobId = null;
    const jobIdField = document.getElementById('job-id-field');
    if (jobIdField) {
        jobIdField.value = '';
    }
    document.getElementById('job-modal-title').textContent = 'Create Backup Job';
    document.getElementById('job-submit-btn').innerHTML = '<i class="ph ph-check"></i> Create Job';
    document.getElementById('create-job-form').reset();
    // Ensure the hidden field is cleared after reset
    if (jobIdField) {
        jobIdField.value = '';
    }
    document.getElementById('create-job-modal').style.display = 'block';
    console.log('showCreateJobModal: editingJobId cleared, modal opened');
};

window.editJob = async (jobId) => {
    try {
        const job = await api.getJob(jobId);
        editingJobId = jobId;
        
        document.getElementById('job-modal-title').textContent = 'Edit Backup Job';
        document.getElementById('job-submit-btn').innerHTML = '<i class="ph ph-check"></i> Update Job';
        document.getElementById('job-id-field').value = jobId;
        
        const form = document.getElementById('create-job-form');
        form.name.value = job.name;
        form.job_type.value = job.job_type;
        form.description.value = job.description || '';
        form.source_paths.value = job.source_paths.join('\n');
        form.schedule.value = job.schedule;
        form.s3_bucket.value = job.s3_bucket;
        form.s3_prefix.value = job.s3_prefix;
        form.storage_class.value = job.storage_class;
        form.incremental_enabled.checked = job.incremental_enabled;
        
        document.getElementById('create-job-modal').style.display = 'block';
    } catch (error) {
        showError(`Failed to load job: ${error.message}`);
    }
};

window.closeCreateJobModal = () => {
    document.getElementById('create-job-modal').style.display = 'none';
    document.getElementById('create-job-form').reset();
    editingJobId = null;
};

window.saveJob = async (event) => {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    // Get the job ID from the hidden field (if editing)
    const jobIdField = document.getElementById('job-id-field');
    const currentEditingJobId = jobIdField ? parseInt(jobIdField.value) || null : null;
    
    console.log('saveJob: editingJobId variable:', editingJobId);
    console.log('saveJob: job-id-field value:', currentEditingJobId);
    
    const jobData = {
        name: formData.get('name'),
        job_type: formData.get('job_type'),
        description: formData.get('description') || null,
        source_paths: formData.get('source_paths').split('\n').filter(p => p.trim()),
        schedule: formData.get('schedule'),
        s3_bucket: formData.get('s3_bucket'),
        s3_prefix: formData.get('s3_prefix'),
        storage_class: formData.get('storage_class'),
        incremental_enabled: formData.get('incremental_enabled') === 'on',
        enabled: true
    };
    
    try {
        let result;
        // Use the field value as the source of truth, but also check the variable
        const isEditing = currentEditingJobId || editingJobId;
        
        if (isEditing) {
            const jobIdToUpdate = currentEditingJobId || editingJobId;
            console.log('saveJob: Updating job', jobIdToUpdate);
            result = await api.updateJob(jobIdToUpdate, jobData);
            showNotification('Job updated successfully!', 'info');
        } else {
            console.log('saveJob: Creating new job', jobData.name);
            result = await api.createJob(jobData);
            console.log('saveJob: Created job result:', result);
            showNotification('Job created successfully!', 'info');
        }
        
        // Always clear editing state after save
        editingJobId = null;
        if (jobIdField) {
            jobIdField.value = '';
        }
        
        closeCreateJobModal();
        console.log('saveJob: Reloading jobs list...');
        await loadJobs();
        await loadDashboard();
        console.log('saveJob: Jobs list reloaded');
    } catch (error) {
        console.error('saveJob: Error:', error);
        showError(`Failed to ${(currentEditingJobId || editingJobId) ? 'update' : 'create'} job: ${error.message}`);
    }
};

window.deleteJob = async (jobId) => {
    if (!confirm('Are you sure you want to delete this job?')) {
        return;
    }
    
    try {
        const { deleteJob } = await import('./api.js');
        const { showNotification, showError } = await import('./components/notifications.js');
        await deleteJob(jobId);
        showNotification('Job deleted successfully!', 'info');
        
        const event = new CustomEvent('reload-jobs');
        document.dispatchEvent(event);
    } catch (error) {
        const { showError } = await import('./components/notifications.js');
        showError(`Failed to delete job: ${error.message}`);
    }
};

let currentSyncJobId = null;

window.syncJob = async (jobId) => {
    currentSyncJobId = jobId;
    const modal = document.getElementById('sync-modal');
    const statusDiv = document.getElementById('sync-status');
    const issuesDiv = document.getElementById('sync-issues');
    const issuesList = document.getElementById('sync-issues-list');
    
    modal.style.display = 'block';
    issuesDiv.style.display = 'none';
    statusDiv.className = 'loading';
    statusDiv.textContent = 'Checking sync status...';
    
    try {
        const dryRunResult = await api.syncJob(jobId, true);
        
        if (!dryRunResult.issues || dryRunResult.issues.length === 0) {
            statusDiv.className = 'success';
            statusDiv.innerHTML = '<i class="ph ph-check-circle"></i> Database and S3 storage are in sync!';
            issuesDiv.style.display = 'none';
            return;
        }
        
        const issuesCount = dryRunResult.issues.length;
        const criticalIssues = dryRunResult.issues.filter(i => i.severity === 'critical').length;
        const warnings = dryRunResult.issues.filter(i => i.severity === 'warning').length;
        
        statusDiv.className = 'warning';
        statusDiv.innerHTML = `<i class="ph ph-warning"></i> Found ${issuesCount} sync issue(s)`;
        if (criticalIssues > 0) {
            statusDiv.innerHTML += ` <span style="color: var(--error);">(${criticalIssues} critical)</span>`;
        }
        if (warnings > 0) {
            statusDiv.innerHTML += ` <span style="color: var(--warning);">(${warnings} warnings)</span>`;
        }
        
        issuesList.innerHTML = dryRunResult.issues.map(issue => {
            const severity = issue.severity || 'info';
            const icon = severity === 'critical' ? 'ph-x-circle' : 
                        severity === 'warning' ? 'ph-warning' : 'ph-info';
            const color = severity === 'critical' ? 'var(--error)' : 
                         severity === 'warning' ? 'var(--warning)' : 'var(--text-secondary)';
            return `
                <div style="padding: 12px; margin: 8px 0; background: rgba(51, 65, 85, 0.3); border-radius: 8px; border-left: 3px solid ${color};">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <i class="ph ${icon}" style="color: ${color};"></i>
                        <strong style="color: ${color}; text-transform: capitalize;">${severity}</strong>
                    </div>
                    <div style="color: var(--text-primary); margin-left: 24px;">
                        ${issue.message || issue.type || 'Unknown issue'}
                    </div>
                    ${issue.s3_key ? `<div style="color: var(--text-secondary); font-size: 0.9em; margin-left: 24px; margin-top: 4px;">S3: ${issue.s3_key}</div>` : ''}
                </div>
            `;
        }).join('');
        
        issuesDiv.style.display = 'block';
    } catch (error) {
        statusDiv.className = 'error';
        statusDiv.innerHTML = `<i class="ph ph-x-circle"></i> Failed to sync: ${error.message}`;
        issuesDiv.style.display = 'none';
    }
};

window.closeSyncModal = () => {
    document.getElementById('sync-modal').style.display = 'none';
    currentSyncJobId = null;
};

window.applySyncFixes = async () => {
    if (!currentSyncJobId) return;
    
    const statusDiv = document.getElementById('sync-status');
    const fixBtn = document.getElementById('sync-fix-btn');
    
    fixBtn.disabled = true;
    fixBtn.textContent = 'Applying fixes...';
    statusDiv.className = 'loading';
    statusDiv.textContent = 'Applying fixes...';
    
    try {
        const fixResult = await api.syncJob(currentSyncJobId, false);
        
        const fixedCount = fixResult.actions?.length || 0;
        statusDiv.className = 'success';
        statusDiv.innerHTML = `<i class="ph ph-check-circle"></i> Sync complete! Applied ${fixedCount} fix(es).`;
        
        fixBtn.style.display = 'none';
        loadJobs();
        
        setTimeout(() => {
            syncJob(currentSyncJobId);
        }, 2000);
    } catch (error) {
        statusDiv.className = 'error';
        statusDiv.innerHTML = `<i class="ph ph-x-circle"></i> Failed to apply fixes: ${error.message}`;
        fixBtn.disabled = false;
        fixBtn.textContent = 'Apply Fixes';
    }
};

window.toggleMenu = (jobId) => {
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
};

window.closeMenu = (jobId) => {
    const menu = document.getElementById(`menu-${jobId}`);
    if (menu) {
        menu.classList.remove('show');
    }
};

// Wait for Chart.js to load
function waitForChart(callback, maxAttempts = 50) {
    if (typeof Chart !== 'undefined') {
        callback();
    } else if (maxAttempts > 0) {
        setTimeout(() => waitForChart(callback, maxAttempts - 1), 100);
    } else {
        console.error('Chart.js failed to load after 5 seconds');
    }
}

// Chart instances
let storageChart = null;
let costChart = null;
let historyChart = null;

window.switchMainTab = (tab, event) => {
    // Navigate using router instead of direct tab switching
    if (tab === 'dashboard') {
        router.navigate('/dashboard');
    } else if (tab === 'jobs') {
        router.navigate('/jobs');
    } else if (tab === 'metrics') {
        router.navigate('/metrics/overview');
    } else if (tab === 'restore') {
        router.navigate('/restore');
    }
};

window.toggleSubmenu = (menuId) => {
    const navItem = document.getElementById(`${menuId}-nav-item`);
    if (navItem) {
        navItem.classList.toggle('expanded');
    }
};

window.switchMetricsTab = (tab, event) => {
    // Navigate using router
    router.navigate(`/metrics/${tab}`);
};

function showMetricsTab(tab) {
    // Update submenu items
    document.querySelectorAll('.submenu-item').forEach(item => item.classList.remove('active'));
    
    // Activate the correct submenu item
    const submenuItems = document.querySelectorAll('.submenu-item');
    submenuItems.forEach((item) => {
        const text = item.textContent.trim().toLowerCase();
        if ((tab === 'overview' && text === 'overview') ||
            (tab === 'history' && text === 'history') ||
            (tab === 'projection' && (text === 'projection' || text === 'projections'))) {
            item.classList.add('active');
        }
    });
    
    // Update content
    document.querySelectorAll('.metrics-content').forEach(content => content.classList.remove('active'));
    const targetContent = document.getElementById(`metrics-${tab}`);
    if (targetContent) {
        targetContent.classList.add('active');
    }
    
    // Load the appropriate data
    if (tab === 'overview') {
        waitForChart(() => {
            loadMetricsSummary();
            loadMetricsCharts();
        });
    } else if (tab === 'history') {
        waitForChart(() => {
            loadHistoryChart();
        });
    } else if (tab === 'projection') {
        loadProjections();
    }
}

async function loadMetricsSummary() {
    const container = document.getElementById('metrics-summary');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading">Loading metrics...</div>';
        const summary = await api.getMetricsSummary(30);
        
        if (summary.error) {
            container.innerHTML = `<div class="error">${summary.error}</div>`;
            return;
        }
        
        if (!summary.current) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <i class="ph ph-chart-line" style="font-size: 48px; opacity: 0.3; margin-bottom: 16px; display: block;"></i>
                    <p>No metrics data available yet. Metrics are recorded daily at midnight UTC.</p>
                </div>
            `;
            return;
        }
        
        const sizeChange = summary.trends?.size_change_gb || 0;
        const costChange = summary.trends?.cost_change || 0;
        const sizeChangePercent = summary.trends?.size_change_percent || 0;
        const costChangePercent = summary.trends?.cost_change_percent || 0;
        
        container.innerHTML = `
            <div class="metrics-summary">
                <div class="summary-card">
                    <div class="summary-label">Current Storage</div>
                    <div class="summary-value">${formatStorage(summary.current.size_gb * 1024**3)}</div>
                    <div class="summary-change">
                        ${sizeChange >= 0 ? '+' : ''}${sizeChange.toFixed(2)} GB 
                        (${sizeChangePercent >= 0 ? '+' : ''}${sizeChangePercent.toFixed(1)}%)
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Monthly Cost</div>
                    <div class="summary-value">${formatCost(summary.current.monthly_cost)}</div>
                    <div class="summary-change">
                        ${costChange >= 0 ? '+' : ''}${formatCost(costChange)} 
                        (${costChangePercent >= 0 ? '+' : ''}${costChangePercent.toFixed(1)}%)
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Annual Cost</div>
                    <div class="summary-value">${formatCost(summary.current.annual_cost)}</div>
                </div>
                <div class="summary-card">
                    <div class="summary-label">Total Files</div>
                    <div class="summary-value">${(summary.current.files || 0).toLocaleString()}</div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load metrics summary: ${error.message}</div>`;
    }
}

window.loadMetricsCharts = async () => {
    const days = parseInt(document.getElementById('storage-days')?.value) || 30;
    
    try {
        const history = await api.getMetricsHistory(days);
        
        if (history.records && history.records.length > 0) {
            if (typeof Chart === 'undefined') {
                throw new Error('Chart.js library is not available.');
            }
            
            const labels = history.records.map(r => new Date(r.date).toLocaleDateString());
            const storageData = history.records.map(r => r.total_size_gb);
            const costData = history.records.map(r => r.monthly_cost);
            
            const storageCtx = document.getElementById('storage-chart').getContext('2d');
            if (storageChart) storageChart.destroy();
            storageChart = new Chart(storageCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Storage (GB)',
                        data: storageData,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#cbd5e1' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8', callback: (v) => v.toFixed(1) + ' GB' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        }
                    }
                }
            });
            
            const costCtx = document.getElementById('cost-chart').getContext('2d');
            if (costChart) costChart.destroy();
            costChart = new Chart(costCtx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Monthly Cost ($)',
                        data: costData,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: { color: '#cbd5e1' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8', callback: (v) => '$' + v.toFixed(2) },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Failed to load charts:', error);
    }
};

window.loadHistoryChart = async () => {
    const days = parseInt(document.getElementById('history-days')?.value) || 30;
    
    try {
        const history = await api.getMetricsHistory(days);
        
        if (history.records && history.records.length > 0) {
            if (typeof Chart === 'undefined') {
                throw new Error('Chart.js library is not available.');
            }
            
            const latest = history.records[history.records.length - 1];
            const labels = Object.keys(latest.size_by_class);
            const data = Object.values(latest.size_by_class);
            const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#10b981'];
            
            const historyCtx = document.getElementById('history-chart').getContext('2d');
            if (historyChart) historyChart.destroy();
            historyChart = new Chart(historyCtx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Storage (GB)',
                        data: data,
                        backgroundColor: colors,
                        borderColor: colors.map(c => c + 'dd'),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#94a3b8', callback: (v) => v.toFixed(1) + ' GB' },
                            grid: { color: 'rgba(148, 163, 184, 0.1)' }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Failed to load history chart:', error);
    }
};

async function loadProjections() {
    const container = document.getElementById('projection-content');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading">Loading projections...</div>';
        const projection = await api.getMetricsProjection(30);
        
        if (projection.note && projection.note.includes('Insufficient')) {
            container.innerHTML = `
                <div class="projection-card">
                    <h3 style="margin-bottom: 16px;">Cost & Storage Projections</h3>
                    <p style="color: var(--text-muted);">${projection.note}</p>
                    <div class="projection-grid" style="margin-top: 24px;">
                        <div class="projection-item">
                            <div class="projection-label">Current Storage</div>
                            <div class="projection-value">${projection.current.size_gb.toFixed(2)} GB</div>
                        </div>
                        <div class="projection-item">
                            <div class="projection-label">Current Monthly Cost</div>
                            <div class="projection-value">${formatCost(projection.current.monthly_cost)}</div>
                        </div>
                    </div>
                </div>
            `;
            return;
        }
        
        // Full projection display would go here
        container.innerHTML = `<div class="projection-card"><p>Projections loaded</p></div>`;
    } catch (error) {
        container.innerHTML = `<div class="error">Failed to load projections: ${error.message}</div>`;
    }
}

// Restore page functions
async function loadRestorePage() {
    await loadRestoreJobs();
}

async function loadRestoreJobs() {
    try {
        const jobs = await api.getJobs();
        const jobSelect = document.getElementById('restore-job-select');
        if (!jobSelect) return;
        
        jobSelect.innerHTML = '<option value="">Select a job...</option>';
        jobs.forEach(job => {
            const option = document.createElement('option');
            option.value = job.id;
            option.textContent = job.name;
            jobSelect.appendChild(option);
        });
    } catch (error) {
        showError(`Failed to load jobs: ${error.message}`);
    }
}

window.loadSnapshotsForJob = async () => {
    const jobId = document.getElementById('restore-job-select').value;
    const snapshotSelect = document.getElementById('restore-snapshot-select');
    
    if (!jobId) {
        snapshotSelect.innerHTML = '<option value="">Select a job first...</option>';
        return;
    }
    
    try {
        snapshotSelect.innerHTML = '<option value="">Loading snapshots...</option>';
        const snapshots = await api.getSnapshots(jobId);
        
        snapshotSelect.innerHTML = '<option value="">Select a snapshot...</option>';
        snapshots.forEach(snapshot => {
            const option = document.createElement('option');
            option.value = snapshot.snapshot_id;
            const date = formatAbsoluteDate(snapshot.created_at);
            const size = formatStorage(snapshot.size_bytes || 0);
            option.textContent = `${date} - ${size} (${snapshot.files_count || 0} files)`;
            option.dataset.snapshot = JSON.stringify(snapshot);
            snapshotSelect.appendChild(option);
        });
        
        // Clear estimates when changing job
        document.getElementById('restore-estimates').style.display = 'none';
    } catch (error) {
        showError(`Failed to load snapshots: ${error.message}`);
        snapshotSelect.innerHTML = '<option value="">Error loading snapshots</option>';
    }
};

window.togglePartialRestore = () => {
    const checkbox = document.getElementById('restore-partial');
    const filesGroup = document.getElementById('restore-files-group');
    filesGroup.style.display = checkbox.checked ? 'block' : 'none';
    if (checkbox.checked) {
        updateRestoreEstimate();
    }
};

window.updateRestoreEstimate = async () => {
    const snapshotId = document.getElementById('restore-snapshot-select').value;
    if (!snapshotId) {
        document.getElementById('restore-estimates').style.display = 'none';
        return;
    }
    
    const filePathsText = document.getElementById('restore-file-paths').value;
    const filePaths = filePathsText ? filePathsText.split('\n').filter(p => p.trim()) : null;
    const tier = document.getElementById('restore-tier').value;
    
    try {
        const estimates = await api.estimateRestore(snapshotId, filePaths);
        
        // Update cost display
        const costEl = document.getElementById('estimate-cost');
        const costNoteEl = document.getElementById('estimate-cost-note');
        if (estimates.costs.total_cost > 0) {
            costEl.textContent = `$${estimates.costs.total_cost.toFixed(4)}`;
            costNoteEl.textContent = estimates.costs.note || '';
        } else {
            costEl.textContent = 'No cost';
            costNoteEl.textContent = 'Standard storage - no restore fees';
        }
        
        // Update time display
        const timeEl = document.getElementById('estimate-time');
        const timeNoteEl = document.getElementById('estimate-time-note');
        const hours = estimates.time_estimates.total_estimated_hours;
        if (hours < 1) {
            timeEl.textContent = `${Math.round(hours * 60)} minutes`;
        } else if (hours < 24) {
            timeEl.textContent = `${hours.toFixed(1)} hours`;
        } else {
            timeEl.textContent = `${(hours / 24).toFixed(1)} days`;
        }
        timeNoteEl.textContent = estimates.time_estimates.note || '';
        
        // Update size display
        const sizeEl = document.getElementById('estimate-size');
        const sizeNoteEl = document.getElementById('estimate-size-note');
        sizeEl.textContent = formatStorage(estimates.estimated_restore_size_bytes);
        sizeNoteEl.textContent = `${estimates.estimated_files_to_restore || 0} files`;
        
        document.getElementById('restore-estimates').style.display = 'block';
        
        // Show warning if Glacier restore needed
        if (estimates.needs_glacier_restore) {
            if (estimates.restore_status === 'in_progress') {
                showNotification('Glacier restore is already in progress. Please wait for it to complete.', 'info');
            } else if (estimates.restore_status === 'ready') {
                showNotification('Glacier restore is ready. You can proceed with the restore.', 'info');
            } else {
                showNotification('This snapshot is in Glacier. A restore request will be initiated.', 'warning');
            }
        }
    } catch (error) {
        showError(`Failed to get estimates: ${error.message}`);
    }
};

window.initiateRestore = async () => {
    const snapshotId = document.getElementById('restore-snapshot-select').value;
    const restorePath = document.getElementById('restore-path').value;
    const filePathsText = document.getElementById('restore-file-paths').value;
    const filePaths = filePathsText ? filePathsText.split('\n').filter(p => p.trim()) : null;
    
    if (!snapshotId || !restorePath) {
        showError('Please select a snapshot and provide a restore path');
        return;
    }
    
    if (!confirm(`Are you sure you want to restore to ${restorePath}?`)) {
        return;
    }
    
    try {
        const result = await api.initiateRestore(snapshotId, restorePath, filePaths);
        showNotification(result.message || 'Restore initiated successfully', 'info');
        if (result.note) {
            showNotification(result.note, 'warning');
        }
        
        // Clear form
        document.getElementById('restore-path').value = '';
        document.getElementById('restore-file-paths').value = '';
        document.getElementById('restore-partial').checked = false;
        document.getElementById('restore-files-group').style.display = 'none';
    } catch (error) {
        showError(`Failed to initiate restore: ${error.message}`);
    }
};

// Close modals on outside click
window.onclick = function(event) {
    const createModal = document.getElementById('create-job-modal');
    const syncModal = document.getElementById('sync-modal');
    if (event.target === createModal) {
        closeCreateJobModal();
    }
    if (event.target === syncModal) {
        closeSyncModal();
    }
};

// Close dropdown menus when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.menu-button') && !event.target.closest('.dropdown-menu')) {
        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
        });
    }
});

console.log('ColdVault frontend initialized');
