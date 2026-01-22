"""
Backup worker that executes backup jobs
"""
import logging
import os
import json
from datetime import datetime
from typing import Optional

from app.database import SessionLocal, Job, BackupRun, Snapshot, BackupStatus, StorageClass
from app.engines.dataset_backup import DatasetBackupEngine
from app.engines.incremental_backup import IncrementalBackupEngine
from app.engines.restic_backup import ResticBackupEngine
from app.notifications import notification_service
from app.logging_utils import setup_backup_logger

logger = logging.getLogger(__name__)

class BackupWorker:
    def __init__(self):
        self.dataset_engine = DatasetBackupEngine()
        self.incremental_engine = IncrementalBackupEngine()
        self.restic_engine = ResticBackupEngine()
        self.running_backups = {}  # job_id -> backup_run_id
        self.cancellation_flags = {}  # backup_run_id -> bool (True means cancel requested)
        self._recover_orphaned_backups()
    
    def _recover_orphaned_backups(self):
        """Recover backup runs that were marked as RUNNING but aren't actually running
        (e.g., after server restart)
        """
        db = SessionLocal()
        try:
            # Find all backup runs that are marked as RUNNING
            orphaned_runs = db.query(BackupRun).filter(
                BackupRun.status == BackupStatus.RUNNING
            ).all()
            
            if orphaned_runs:
                logger.warning(f"Found {len(orphaned_runs)} orphaned backup runs (marked as RUNNING but not actually running)")
                
                for run in orphaned_runs:
                    # Mark as failed with recovery message
                    run.status = BackupStatus.FAILED
                    run.completed_at = datetime.utcnow()
                    if run.started_at:
                        run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    run.error_message = "Backup was interrupted (server restart or crash)"
                    
                    # Update job status
                    job = db.query(Job).filter(Job.id == run.job_id).first()
                    if job:
                        job.last_run_status = BackupStatus.FAILED
                    
                    logger.info(f"Recovered orphaned backup run {run.id} for job {run.job_id}")
                
                db.commit()
                logger.info(f"Recovered {len(orphaned_runs)} orphaned backup runs")
        except Exception as e:
            logger.error(f"Error recovering orphaned backups: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    def execute_backup(self, job_id: int, backup_run_id: Optional[int] = None):
        """Execute a backup job"""
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            # Check if backup is already running
            if job_id in self.running_backups:
                logger.warning(f"Backup for job {job_id} is already running")
                return
            
            # Create backup run if not provided
            if not backup_run_id:
                backup_run = BackupRun(
                    job_id=job_id,
                    status=BackupStatus.PENDING,
                    manual_trigger=False
                )
                db.add(backup_run)
                db.commit()
                db.refresh(backup_run)
                backup_run_id = backup_run.id
            else:
                backup_run = db.query(BackupRun).filter(BackupRun.id == backup_run_id).first()
            
            self.running_backups[job_id] = backup_run_id
            self.cancellation_flags[backup_run_id] = False  # Initialize cancellation flag
            
            # Set up logging for this backup run
            backup_logger, log_file_path = setup_backup_logger(backup_run_id, job.name)
            backup_run.log_path = log_file_path
            
            # Update job last_run_at
            job.last_run_at = datetime.utcnow()
            job.last_run_status = BackupStatus.RUNNING
            
            # Update backup run
            backup_run.status = BackupStatus.RUNNING
            backup_run.started_at = datetime.utcnow()
            db.commit()
            
            backup_logger.info(f"Starting backup for job '{job.name}' (ID: {job_id})")
            backup_logger.info(f"Job type: {job.job_type.value}")
            backup_logger.info(f"Source paths: {json.loads(job.source_paths)}")
            backup_logger.info(f"Storage class: {job.storage_class.value}")
            backup_logger.info(f"S3 bucket: {job.s3_bucket}, prefix: {job.s3_prefix}")
            
                # Execute backup based on job type
            try:
                # Check for cancellation before starting
                if self.cancellation_flags.get(backup_run_id, False):
                    backup_logger.warning("Backup was cancelled before execution started")
                    raise InterruptedError("Backup cancelled by user")
                
                if job.job_type.value == "dataset":
                    # Use incremental engine if enabled, otherwise full backup
                    if job.incremental_enabled:
                        backup_logger.info("Using incremental backup engine (only new/changed files)")
                        result = self.incremental_engine.backup(job, backup_run, db, backup_logger, self.cancellation_flags, backup_run_id)
                    else:
                        backup_logger.info("Using full backup engine (all files)")
                        result = self.dataset_engine.backup(job, backup_run, db, backup_logger, self.cancellation_flags, backup_run_id)
                elif job.job_type.value == "host":
                    backup_logger.info("Using restic backup engine")
                    result = self.restic_engine.backup(job, backup_run, db, backup_logger, self.cancellation_flags, backup_run_id)
                else:
                    raise ValueError(f"Unknown job type: {job.job_type}")
                
                # Check for partial success (upload errors in incremental backups)
                upload_errors_count = result.get("upload_errors", 0)
                files_count = result.get("files_count", 0)
                total_files_scanned = result.get("total_files_scanned", files_count)
                
                # Determine if backup is successful or partial
                is_partial_success = upload_errors_count > 0
                success_rate = (files_count / total_files_scanned * 100) if total_files_scanned > 0 else 100.0
                
                # Mark as success if >95% of files uploaded, otherwise mark as failed
                if is_partial_success and success_rate < 95.0:
                    # Too many failures - mark as failed
                    backup_run.status = BackupStatus.FAILED
                    backup_run.completed_at = datetime.utcnow()
                    backup_run.duration_seconds = (backup_run.completed_at - backup_run.started_at).total_seconds()
                    backup_run.error_message = (
                        f"Backup partially failed: {upload_errors_count} files failed to upload "
                        f"({success_rate:.1f}% success rate)"
                    )
                    job.last_run_status = BackupStatus.FAILED
                    backup_logger.error("=" * 60)
                    backup_logger.error("BACKUP FAILED (Too many upload errors)")
                    backup_logger.error(f"Files uploaded: {files_count:,} / {total_files_scanned:,} ({success_rate:.1f}%)")
                    backup_logger.error(f"Upload errors: {upload_errors_count}")
                    backup_logger.error("=" * 60)
                    db.commit()
                    notification_service.send_backup_failure(job, backup_run, backup_run.error_message)
                    return
                else:
                    # Success or acceptable partial success
                    backup_run.status = BackupStatus.SUCCESS
                    backup_run.completed_at = datetime.utcnow()
                    backup_run.duration_seconds = (backup_run.completed_at - backup_run.started_at).total_seconds()
                    
                    if is_partial_success:
                        backup_run.error_message = (
                            f"Partial success: {upload_errors_count} files failed to upload "
                            f"({success_rate:.1f}% success rate)"
                        )
                
                backup_run.snapshot_id = result.get("snapshot_id")
                backup_run.size_bytes = result.get("size_bytes")
                backup_run.files_count = result.get("files_count")
                backup_run.s3_key = result.get("s3_key")
                backup_run.storage_class = job.storage_class
                
                # Log success summary
                size_gb = (result.get("size_bytes", 0) / (1024**3))
                backup_logger.info("=" * 60)
                if is_partial_success:
                    backup_logger.info("BACKUP COMPLETED WITH WARNINGS")
                    backup_logger.warning(f"⚠️  {upload_errors_count} files failed to upload ({success_rate:.1f}% success rate)")
                else:
                    backup_logger.info("BACKUP COMPLETED SUCCESSFULLY")
                backup_logger.info(f"Snapshot ID: {result.get('snapshot_id')}")
                backup_logger.info(f"Files backed up: {result.get('files_count', 0):,}")
                if total_files_scanned > files_count:
                    backup_logger.info(f"Total files scanned: {total_files_scanned:,}")
                backup_logger.info(f"Total size: {size_gb:.2f} GB ({result.get('size_bytes', 0):,} bytes)")
                backup_logger.info(f"S3 location: s3://{job.s3_bucket}/{result.get('s3_key')}")
                backup_logger.info(f"Duration: {backup_run.duration_seconds:.2f} seconds")
                if is_partial_success:
                    backup_logger.warning("Some files failed to upload. Check logs for details.")
                backup_logger.info("=" * 60)
                
                # Create snapshot record
                snapshot = Snapshot(
                    job_id=job_id,
                    backup_run_id=backup_run_id,
                    snapshot_id=result.get("snapshot_id"),
                    size_bytes=result.get("size_bytes"),
                    files_count=result.get("files_count"),
                    s3_key=result.get("s3_key") or "N/A",  # Handle case where no files to backup
                    manifest_key=result.get("manifest_key"),
                    storage_class=job.storage_class,
                    is_incremental=result.get("incremental", False),
                    files_unchanged=result.get("files_unchanged", 0),
                    retained=True
                )
                db.add(snapshot)
                
                # Update job status
                job.last_run_status = BackupStatus.SUCCESS
                
                # Apply retention policy
                self._apply_retention(job, db, backup_logger)
                
                db.commit()
                
                logger.info(f"Backup {backup_run_id} completed successfully for job {job_id}")
                
                # Send success notification (optional)
                # notification_service.send_backup_success(job, backup_run)
                
            except (InterruptedError, KeyboardInterrupt) as e:
                # Handle cancellation
                error_msg = "Backup cancelled by user"
                backup_logger.warning("=" * 60)
                backup_logger.warning("BACKUP CANCELLED")
                backup_logger.warning(f"Reason: {error_msg}")
                backup_logger.warning("=" * 60)
                
                backup_run.status = BackupStatus.CANCELLED
                backup_run.completed_at = datetime.utcnow()
                backup_run.duration_seconds = (backup_run.completed_at - backup_run.started_at).total_seconds()
                backup_run.error_message = error_msg
                
                job.last_run_status = BackupStatus.CANCELLED
                
                db.commit()
                
                logger.info(f"Backup {backup_run_id} cancelled for job {job_id}")
                
            except Exception as e:
                error_msg = str(e)
                backup_logger.error("=" * 60)
                backup_logger.error("BACKUP FAILED")
                backup_logger.error(f"Error: {error_msg}", exc_info=True)
                backup_logger.error("=" * 60)
                
                logger.error(f"Backup {backup_run_id} failed for job {job_id}: {e}", exc_info=True)
                
                backup_run.status = BackupStatus.FAILED
                backup_run.completed_at = datetime.utcnow()
                backup_run.duration_seconds = (backup_run.completed_at - backup_run.started_at).total_seconds()
                backup_run.error_message = error_msg
                
                job.last_run_status = BackupStatus.FAILED
                
                db.commit()
                
                # Send failure notification
                notification_service.send_backup_failure(job, backup_run, error_msg)
            
            finally:
                # Update next run time
                from app.scheduler import scheduler
                job.next_run_at = scheduler.get_next_run_time(job_id)
                db.commit()
                
                # Remove from running backups and cancellation flags
                if job_id in self.running_backups:
                    del self.running_backups[job_id]
                if backup_run_id in self.cancellation_flags:
                    del self.cancellation_flags[backup_run_id]
        
        except Exception as e:
            logger.error(f"Error executing backup for job {job_id}: {e}", exc_info=True)
        finally:
            db.close()
    
    def cancel_backup(self, job_id: int) -> bool:
        """Cancel a running backup job
        
        Returns:
            bool: True if cancellation was requested, False if backup not found or not running
        """
        if job_id not in self.running_backups:
            return False
        
        backup_run_id = self.running_backups[job_id]
        self.cancellation_flags[backup_run_id] = True
        
        logger.info(f"Cancellation requested for backup {backup_run_id} (job {job_id})")
        return True
    
    def _apply_retention(self, job: Job, db, backup_logger=None):
        """Apply retention policy to snapshots"""
        if backup_logger is None:
            backup_logger = logger
        
        backup_logger.info("Applying retention policy...")
        
        # Get all snapshots for this job, ordered by date
        snapshots = db.query(Snapshot).filter(
            Snapshot.job_id == job.id,
            Snapshot.retained == True
        ).order_by(Snapshot.created_at.desc()).all()
        
        backup_logger.info(f"Total snapshots: {len(snapshots)}, keeping last {job.keep_last_n}")
        
        if len(snapshots) <= job.keep_last_n:
            backup_logger.info("No snapshots to delete (within retention limit)")
            return
        
        # Mark excess snapshots for deletion
        to_delete = snapshots[job.keep_last_n:]
        
        # TODO: Implement GFS (Grandfather-Father-Son) retention
        # For now, just keep last N
        
        for snapshot in to_delete:
            snapshot.retained = False
            snapshot.retention_reason = "keep_last_n_exceeded"
            backup_logger.info(f"Marked snapshot {snapshot.snapshot_id} for deletion")
        
        backup_logger.info(f"Marked {len(to_delete)} snapshots for deletion due to retention policy")

backup_worker = BackupWorker()
