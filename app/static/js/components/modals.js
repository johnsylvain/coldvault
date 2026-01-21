// Modals component using Alpine.js
import { getJob, createJob, updateJob, deleteJob, syncJob } from '../api.js';
import { setEditingJobId, clearEditingJobId, setCurrentSyncJobId, clearCurrentSyncJobId } from '../state.js';
import { showNotification, showError } from './notifications.js';

export function jobModalComponent() {
    return {
        show: false,
        editing: false,
        jobId: null,
        form: {
            name: '',
            job_type: 'dataset',
            description: '',
            source_paths: '',
            schedule: 'daily',
            s3_bucket: '',
            s3_prefix: '',
            storage_class: 'DEEP_ARCHIVE',
            incremental_enabled: true
        },
        
        openCreate() {
            this.editing = false;
            this.jobId = null;
            this.resetForm();
            this.show = true;
            clearEditingJobId();
        },
        
        async openEdit(jobId) {
            try {
                this.editing = true;
                this.jobId = jobId;
                setEditingJobId(jobId);
                
                const job = await getJob(jobId);
                this.form = {
                    name: job.name,
                    job_type: job.job_type,
                    description: job.description || '',
                    source_paths: job.source_paths.join('\n'),
                    schedule: job.schedule,
                    s3_bucket: job.s3_bucket,
                    s3_prefix: job.s3_prefix,
                    storage_class: job.storage_class,
                    incremental_enabled: job.incremental_enabled
                };
                this.show = true;
            } catch (error) {
                showError(`Failed to load job: ${error.message}`);
            }
        },
        
        close() {
            this.show = false;
            this.resetForm();
            clearEditingJobId();
        },
        
        resetForm() {
            this.form = {
                name: '',
                job_type: 'dataset',
                description: '',
                source_paths: '',
                schedule: 'daily',
                s3_bucket: '',
                s3_prefix: '',
                storage_class: 'DEEP_ARCHIVE',
                incremental_enabled: true
            };
        },
        
        async save() {
            try {
                const jobData = {
                    name: this.form.name,
                    job_type: this.form.job_type,
                    description: this.form.description || null,
                    source_paths: this.form.source_paths.split('\n').filter(p => p.trim()),
                    schedule: this.form.schedule,
                    s3_bucket: this.form.s3_bucket,
                    s3_prefix: this.form.s3_prefix,
                    storage_class: this.form.storage_class,
                    incremental_enabled: this.form.incremental_enabled,
                    enabled: true
                };
                
                if (this.editing && this.jobId) {
                    await updateJob(this.jobId, jobData);
                    showNotification('Job updated successfully!', 'info');
                } else {
                    await createJob(jobData);
                    showNotification('Job created successfully!', 'info');
                }
                
                this.close();
                
                // Trigger reload
                const event = new CustomEvent('reload-jobs');
                document.dispatchEvent(event);
            } catch (error) {
                showError(`Failed to ${this.editing ? 'update' : 'create'} job: ${error.message}`);
            }
        }
    };
}

export function syncModalComponent() {
    return {
        show: false,
        jobId: null,
        status: 'loading',
        statusMessage: 'Checking sync status...',
        issues: [],
        applying: false,
        
        async open(jobId) {
            this.jobId = jobId;
            this.show = true;
            setCurrentSyncJobId(jobId);
            await this.checkSync();
        },
        
        close() {
            this.show = false;
            this.jobId = null;
            clearCurrentSyncJobId();
        },
        
        async checkSync() {
            try {
                this.status = 'loading';
                this.statusMessage = 'Checking sync status...';
                
                const result = await syncJob(this.jobId, true);
                
                if (!result.issues || result.issues.length === 0) {
                    this.status = 'success';
                    this.statusMessage = 'Database and S3 storage are in sync!';
                    this.issues = [];
                    return;
                }
                
                this.status = 'warning';
                this.statusMessage = `Found ${result.issues.length} sync issue(s)`;
                this.issues = result.issues;
            } catch (error) {
                this.status = 'error';
                this.statusMessage = `Failed to sync: ${error.message}`;
                this.issues = [];
            }
        },
        
        async applyFixes() {
            try {
                this.applying = true;
                const result = await syncJob(this.jobId, false);
                
                const fixedCount = result.actions?.length || 0;
                this.status = 'success';
                this.statusMessage = `Sync complete! Applied ${fixedCount} fix(es).`;
                
                // Reload sync status after a moment
                setTimeout(() => {
                    this.checkSync();
                }, 2000);
                
                // Trigger reload
                const event = new CustomEvent('reload-jobs');
                document.dispatchEvent(event);
            } catch (error) {
                this.status = 'error';
                this.statusMessage = `Failed to apply fixes: ${error.message}`;
            } finally {
                this.applying = false;
            }
        },
        
        getSeverityIcon(severity) {
            if (severity === 'critical') return 'ph-x-circle';
            if (severity === 'warning') return 'ph-warning';
            return 'ph-info';
        },
        
        getSeverityColor(severity) {
            if (severity === 'critical') return 'var(--danger)';
            if (severity === 'warning') return 'var(--warning)';
            return 'var(--text-secondary)';
        }
    };
}

// Global functions for backward compatibility
export function showCreateJobModalGlobal() {
    const event = new CustomEvent('open-create-job-modal');
    document.dispatchEvent(event);
}

export function editJobGlobal(jobId) {
    const event = new CustomEvent('open-edit-job-modal', { detail: { jobId } });
    document.dispatchEvent(event);
}

export function syncJobGlobal(jobId) {
    const event = new CustomEvent('open-sync-modal', { detail: { jobId } });
    document.dispatchEvent(event);
}

export function closeSyncModalGlobal() {
    const event = new CustomEvent('close-sync-modal');
    document.dispatchEvent(event);
}

export function applySyncFixesGlobal() {
    const event = new CustomEvent('apply-sync-fixes');
    document.dispatchEvent(event);
}
