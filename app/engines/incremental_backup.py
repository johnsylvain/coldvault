"""
Incremental backup engine - only backs up new/changed files
Uploads files directly to S3 preserving directory structure (no tar.gz compression)
"""
import os
import hashlib
import logging
import json
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Dict, Set, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from app.aws import s3_client
from app.encryption import encrypt_file
from app.config import settings
from app.database import SessionLocal, Snapshot, Job
from app.retry_utils import is_retryable_error, RetryContext

logger = logging.getLogger(__name__)

class IncrementalBackupEngine:
    """Handles incremental dataset backups - only new/changed files, uploaded directly to S3"""
    
    def __init__(self):
        self.manifest_cache = {}  # job_id -> manifest data
        self.scan_lock = Lock()
        self.upload_lock = Lock()
    
    def get_file_signature(self, file_path: str) -> Optional[Dict]:
        """Get file signature (size + mtime + hash of first 1MB for quick comparison)"""
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size
            mtime = stat.st_mtime
            
            # For small files, hash the entire file. For large files, hash first 1MB + size
            if file_size < 1024 * 1024:  # < 1MB
                with open(file_path, 'rb') as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
            else:
                # For large files, hash first 1MB + size
                with open(file_path, 'rb') as f:
                    first_mb = f.read(1024 * 1024)
                    content_hash = hashlib.md5(first_mb + str(file_size).encode()).hexdigest()
            
            return {
                'size': file_size,
                'mtime': mtime,
                'hash': content_hash,
                'path': file_path
            }
        except Exception as e:
            logger.warning(f"Failed to get signature for {file_path}: {e}")
            return None
    
    def load_previous_manifest(self, job_id: int, db, job) -> Dict[str, Dict]:
        """Load manifest from the most recent successful backup"""
        # Get the most recent snapshot for this job
        last_snapshot = db.query(Snapshot).filter(
            Snapshot.job_id == job_id,
            Snapshot.retained == True
        ).order_by(Snapshot.created_at.desc()).first()
        
        if not last_snapshot:
            return {}
        
        # Use manifest_key if available, otherwise construct from s3_key
        manifest_key = last_snapshot.manifest_key
        if not manifest_key and last_snapshot.s3_key:
            manifest_key = last_snapshot.s3_key.replace('.tar.gz', '.manifest.json')
            if last_snapshot.s3_key.endswith('.encrypted'):
                manifest_key = manifest_key.replace('.encrypted', '')
        
        if not manifest_key:
            return {}
        
        try:
            # Download manifest from S3
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
                temp_manifest = f.name
            
            s3_client.download_file(job.s3_bucket, manifest_key, temp_manifest)
            
            with open(temp_manifest, 'r') as f:
                manifest = json.load(f)
            
            os.unlink(temp_manifest)
            return manifest.get('files', {})
        except Exception as e:
            logger.warning(f"Could not load previous manifest: {e}. Performing full backup.")
            return {}
    
    def scan_file(self, file_path: str, source_path: str, job, previous_files: Dict) -> Optional[Tuple[str, Dict, bool]]:
        """Scan a single file and return (rel_path, signature, needs_backup) or None"""
        try:
            rel_path = os.path.relpath(file_path, source_path)
            
            # Check include/exclude patterns
            if not self._should_include(file_path, job):
                return None
            
            signature = self.get_file_signature(file_path)
            if not signature:
                return None
            
            # Check if file has changed
            previous_sig = previous_files.get(rel_path)
            needs_backup = True
            if previous_sig:
                # Compare signatures
                if (previous_sig.get('size') == signature['size'] and
                    previous_sig.get('mtime') == signature['mtime'] and
                    previous_sig.get('hash') == signature['hash']):
                    # File unchanged
                    needs_backup = False
            
            return (rel_path, signature, needs_backup)
        except Exception as e:
            logger.warning(f"Failed to scan {file_path}: {e}")
            return None
    
    def scan_directory(self, source_path: str, job, previous_files: Dict, cancellation_flags, backup_run_id, backup_logger) -> Tuple[Dict, int, int, int, int, int]:
        """Scan a directory tree for files to backup (thread-safe)"""
        files_to_backup = {}  # rel_path -> signature
        files_unchanged = 0
        total_size = 0
        new_size = 0
        file_count = 0
        skipped_files = 0
        
        def check_cancellation():
            if cancellation_flags and backup_run_id:
                if cancellation_flags.get(backup_run_id, False):
                    raise InterruptedError("Backup cancelled by user")
        
        # Collect all files first
        all_files = []
        for root, dirs, files in os.walk(source_path):
            check_cancellation()
            
            # Apply exclude patterns
            if job.exclude_patterns:
                exclude_list = json.loads(job.exclude_patterns)
                dirs[:] = [d for d in dirs if not any(
                    Path(root, d).match(pattern) for pattern in exclude_list
                )]
            
            for file in files:
                all_files.append(os.path.join(root, file))
        
        # Scan files in parallel (use configurable limit, but don't exceed file count)
        max_scan_threads = settings.backup_scan_threads
        max_workers = min(max_scan_threads, len(all_files))
        backup_logger.info(f"Scanning with {max_workers} thread(s)")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.scan_file, file_path, source_path, job, previous_files): file_path
                for file_path in all_files
            }
            
            for future in as_completed(future_to_file):
                check_cancellation()
                
                try:
                    result = future.result()
                    if result is None:
                        skipped_files += 1
                        continue
                    
                    rel_path, signature, needs_backup = result
                    file_count += 1
                    total_size += signature['size']
                    
                    if needs_backup:
                        files_to_backup[rel_path] = signature
                        new_size += signature['size']
                    else:
                        files_unchanged += 1
                    
                    # Log progress periodically
                    if file_count % 1000 == 0:
                        with self.scan_lock:
                            new_gb = new_size / (1024**3)
                            total_gb = total_size / (1024**3)
                            backup_logger.info(
                                f"Scanning: {file_count:,} files, "
                                f"{new_gb:.2f} GB new/changed, "
                                f"{total_gb:.2f} GB total, "
                                f"{files_unchanged:,} unchanged"
                            )
                except Exception as e:
                    skipped_files += 1
                    file_path = future_to_file[future]
                    backup_logger.warning(f"Failed to process {file_path}: {e}")
        
        return (files_to_backup, files_unchanged, total_size, new_size, file_count, skipped_files)
    
    def upload_file_to_s3(self, local_path: str, s3_key: str, job, storage_class: str, backup_logger, encryption_enabled: bool) -> Optional[str]:
        """
        Upload a single file to S3, optionally encrypting it first.
        Uses retry logic from S3Client, with additional error handling.
        """
        encrypted_path = None
        try:
            # Encrypt if needed (encrypt to temp file, upload, then delete temp)
            if encryption_enabled:
                with tempfile.NamedTemporaryFile(delete=False) as temp_encrypted:
                    encrypted_path = temp_encrypted.name
                encrypt_file(local_path, encrypted_path, settings.encryption_key)
                upload_path = encrypted_path
            else:
                upload_path = local_path
            
            # Upload to S3 (keep original S3 key, encryption is transparent)
            # S3Client.upload_file now has built-in retry logic
            s3_client.upload_file(upload_path, job.s3_bucket, s3_key, storage_class=storage_class)
            
            return s3_key
        except Exception as e:
            backup_logger.error(f"Failed to upload {local_path} to S3: {e}")
            raise
        finally:
            # Clean up encrypted temp file if created
            if encrypted_path and os.path.exists(encrypted_path):
                try:
                    os.unlink(encrypted_path)
                except Exception as cleanup_error:
                    backup_logger.warning(f"Failed to clean up encrypted temp file: {cleanup_error}")
    
    def backup(self, job, backup_run, db, backup_logger=None, cancellation_flags=None, backup_run_id=None):
        """Execute an incremental backup - uploads files directly to S3"""
        if backup_logger is None:
            backup_logger = logger
        
        def check_cancellation():
            if cancellation_flags and backup_run_id:
                if cancellation_flags.get(backup_run_id, False):
                    backup_logger.warning("Cancellation requested, stopping backup...")
                    raise InterruptedError("Backup cancelled by user")
        
        source_paths = json.loads(job.source_paths)
        # Generate snapshot_id with timestamp for database tracking/logging
        # Note: S3 paths will be consistent (no timestamp) for consolidated backup strategy
        snapshot_id = f"{job.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        backup_logger.info(f"Creating incremental backup snapshot: {snapshot_id}")
        backup_logger.info(f"Backup will overwrite previous backup at: s3://{job.s3_bucket}/{job.s3_prefix}/{job.name}/")
        backup_logger.info("Loading previous backup manifest for comparison...")
        
        # Load previous manifest to compare against
        previous_files = self.load_previous_manifest(job.id, db, job)
        backup_logger.info(f"Previous backup had {len(previous_files)} files tracked")
        
        # Scan all source paths
        all_files_to_backup = {}  # rel_path -> signature
        total_files_unchanged = 0
        total_size_all = 0
        total_new_size = 0
        total_file_count = 0
        total_skipped = 0
        
        backup_logger.info("Scanning files to determine what needs backing up...")
        scan_start = datetime.utcnow()
        
        for source_path in source_paths:
            if not os.path.exists(source_path):
                backup_logger.warning(f"Source path does not exist: {source_path}")
                continue
            
            check_cancellation()
            
            files_to_backup, files_unchanged, total_size, new_size, file_count, skipped = self.scan_directory(
                source_path, job, previous_files, cancellation_flags, backup_run_id, backup_logger
            )
            
            # Merge results
            all_files_to_backup.update(files_to_backup)
            total_files_unchanged += files_unchanged
            total_size_all += total_size
            total_new_size += new_size
            total_file_count += file_count
            total_skipped += skipped
        
        scan_duration = (datetime.utcnow() - scan_start).total_seconds()
        backup_logger.info("=" * 60)
        backup_logger.info("SCAN COMPLETE")
        backup_logger.info(f"Scan duration: {scan_duration:.1f} seconds")
        backup_logger.info(f"Total files scanned: {total_file_count:,}")
        backup_logger.info(f"Files to backup (new/changed): {len(all_files_to_backup):,}")
        backup_logger.info(f"Files unchanged: {total_files_unchanged:,}")
        backup_logger.info(f"New/changed data: {total_new_size / (1024**3):.2f} GB")
        backup_logger.info(f"Total data: {total_size_all / (1024**3):.2f} GB")
        backup_logger.info("=" * 60)
        
        if len(all_files_to_backup) == 0:
            backup_logger.info("No new or changed files. Backup not needed.")
            return {
                "snapshot_id": snapshot_id,
                "size_bytes": 0,
                "files_count": 0,
                "s3_key": None,
                "manifest_key": None,
                "incremental": True,
                "files_unchanged": total_files_unchanged
            }
        
        # Upload files in parallel
        backup_logger.info(f"Uploading {len(all_files_to_backup):,} files to S3...")
        upload_start = datetime.utcnow()
        
        storage_class_map = {
            "STANDARD": "STANDARD",
            "GLACIER_IR": "GLACIER_IR",
            "GLACIER_FLEXIBLE": "GLACIER_FLEXIBLE",
            "DEEP_ARCHIVE": "DEEP_ARCHIVE"
        }
        s3_storage_class = storage_class_map.get(job.storage_class.value, "DEEP_ARCHIVE")
        
        uploaded_files = {}  # rel_path -> s3_key
        upload_errors = []  # (rel_path, error, is_retryable)
        failed_retryable = []  # Files that failed but are retryable
        uploaded_count = 0
        uploaded_bytes = 0
        
        # Prepare upload tasks
        upload_tasks = []
        for rel_path, signature in all_files_to_backup.items():
            # Find the full path
            full_path = None
            for source_path in source_paths:
                candidate = os.path.join(source_path, rel_path)
                if os.path.exists(candidate):
                    full_path = candidate
                    break
            
            if not full_path:
                backup_logger.warning(f"File not found: {rel_path}")
                continue
            
            # Create S3 key preserving directory structure
            # Use consistent S3 key (without timestamp) for consolidated backup strategy
            # This overwrites the previous backup, suitable for 3-2-1 backup strategy
            s3_key = f"{job.s3_prefix}/{job.name}/{rel_path}"
            # Normalize path separators for S3
            s3_key = s3_key.replace('\\', '/')
            
            upload_tasks.append((full_path, s3_key, rel_path, signature))
        
        # Upload files in parallel (use configurable limit, but don't exceed task count)
        max_upload_threads = settings.backup_upload_threads
        max_upload_workers = min(max_upload_threads, len(upload_tasks))
        backup_logger.info(f"Uploading with {max_upload_workers} thread(s)")
        with ThreadPoolExecutor(max_workers=max_upload_workers) as executor:
            future_to_task = {
                executor.submit(
                    self.upload_file_to_s3,
                    full_path,
                    s3_key,
                    job,
                    s3_storage_class,
                    backup_logger,
                    job.encryption_enabled
                ): (rel_path, signature)
                for full_path, s3_key, rel_path, signature in upload_tasks
            }
            
            for future in as_completed(future_to_task):
                check_cancellation()
                
                rel_path, signature = future_to_task[future]
                try:
                    s3_key_uploaded = future.result()
                    uploaded_files[rel_path] = s3_key_uploaded
                    uploaded_count += 1
                    uploaded_bytes += signature['size']
                    
                    # Log progress more frequently
                    # Log every 10 files, or every 5 files for first 50, or at completion
                    should_log = (
                        uploaded_count % 10 == 0 or  # Every 10 files
                        (uploaded_count <= 50 and uploaded_count % 5 == 0) or  # Every 5 files for first 50
                        uploaded_count == len(upload_tasks)  # Always log at completion
                    )
                    if should_log:
                        with self.upload_lock:
                            mb_uploaded = uploaded_bytes / (1024**2)
                            percent = (uploaded_count / len(upload_tasks)) * 100
                            backup_logger.info(
                                f"Upload progress: {uploaded_count:,}/{len(upload_tasks):,} files "
                                f"({percent:.1f}%), {mb_uploaded:.2f} MB uploaded"
                            )
                except Exception as e:
                    error_str = str(e)
                    is_retryable = is_retryable_error(e)
                    upload_errors.append((rel_path, error_str, is_retryable))
                    
                    if is_retryable:
                        # Store for retry after initial batch
                        failed_retryable.append((rel_path, signature, full_path, s3_key))
                        backup_logger.warning(
                            f"Failed to upload {rel_path} (retryable): {e}. Will retry after initial batch."
                        )
                    else:
                        backup_logger.error(f"Failed to upload {rel_path} (non-retryable): {e}")
        
        # Retry failed uploads that are retryable
        if failed_retryable:
            backup_logger.info(f"Retrying {len(failed_retryable)} failed uploads...")
            retry_start = datetime.utcnow()
            
            # Retry failed uploads with exponential backoff
            for rel_path, signature, full_path, s3_key in failed_retryable:
                check_cancellation()
                
                with RetryContext(
                    max_retries=settings.s3_upload_max_retries,
                    base_delay=settings.s3_upload_retry_backoff_base,
                    max_delay=settings.s3_upload_retry_backoff_max,
                    on_retry=lambda e, attempt, delay: backup_logger.warning(
                        f"Retry {attempt} for {rel_path} after {delay:.2f}s: {e}"
                    )
                ) as retry:
                    for attempt in retry:
                        try:
                            s3_key_uploaded = self.upload_file_to_s3(
                                full_path, s3_key, job, s3_storage_class, backup_logger, job.encryption_enabled
                            )
                            uploaded_files[rel_path] = s3_key_uploaded
                            uploaded_count += 1
                            uploaded_bytes += signature['size']
                            
                            # Remove from errors list
                            upload_errors = [(r, e, ret) for r, e, ret in upload_errors if r != rel_path]
                            
                            backup_logger.info(f"Successfully retried upload for {rel_path}")
                            break  # Success, exit retry loop
                        except Exception as e:
                            if not retry.should_retry(e):
                                # Non-retryable on retry - mark as permanent failure
                                backup_logger.error(f"Permanent failure on retry for {rel_path}: {e}")
                                break
                            retry.wait(e)
                    else:
                        # All retries exhausted
                        backup_logger.error(f"Failed to upload {rel_path} after all retries")
            
            retry_duration = (datetime.utcnow() - retry_start).total_seconds()
            backup_logger.info(f"Retry phase complete in {retry_duration:.1f} seconds")
        
        upload_duration = (datetime.utcnow() - upload_start).total_seconds()
        backup_logger.info(f"Upload complete in {upload_duration:.1f} seconds")
        
        if upload_errors:
            backup_logger.warning(f"{len(upload_errors)} files failed to upload")
            for rel_path, error in upload_errors[:10]:  # Show first 10 errors
                backup_logger.warning(f"  - {rel_path}: {error}")
        
        # Create manifest with ALL files (previous + new/changed)
        # Merge previous manifest with new files, updating S3 keys for uploaded files
        current_manifest = previous_files.copy()
        for rel_path, signature in all_files_to_backup.items():
            s3_key = uploaded_files.get(rel_path)
            if s3_key:
                current_manifest[rel_path] = {
                    'size': signature['size'],
                    'mtime': signature['mtime'],
                    'hash': signature['hash'],
                    's3_key': s3_key  # Store S3 key for each file
                }
        
        manifest_data = {
            'snapshot_id': snapshot_id,
            'created_at': datetime.utcnow().isoformat(),
            'job_id': job.id,
            'total_files': len(current_manifest),
            'files': current_manifest
        }
        
        # Save manifest to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            manifest_file = f.name
            json.dump(manifest_data, f, indent=2)
        
        # Upload manifest (encrypt if needed, but keep original key name)
        # Use consistent manifest key (without timestamp) for consolidated backup strategy
        # Manifest files use STANDARD storage class for fast access (not Deep Archive)
        manifest_key = f"{job.s3_prefix}/{job.name}.manifest.json"
        manifest_storage_class = "STANDARD"  # Always use STANDARD for manifest files for fast access
        if job.encryption_enabled:
            # Encrypt manifest to temp file
            encrypted_manifest = manifest_file + ".encrypted"
            encrypt_file(manifest_file, encrypted_manifest, settings.encryption_key)
            # Upload encrypted version but keep original key name
            s3_client.upload_file(encrypted_manifest, job.s3_bucket, manifest_key, storage_class=manifest_storage_class)
            os.unlink(encrypted_manifest)
        else:
            s3_client.upload_file(manifest_file, job.s3_bucket, manifest_key, storage_class=manifest_storage_class)
        
        backup_logger.info("Uploading manifest...")
        backup_logger.info(f"Manifest uploaded: s3://{job.s3_bucket}/{manifest_key}")
        
        # Clean up temp files
        if os.path.exists(manifest_file):
            os.unlink(manifest_file)
        
        return {
            "snapshot_id": snapshot_id,
            "size_bytes": total_new_size,
            "files_count": len(uploaded_files),
            "s3_key": f"{job.s3_prefix}/{job.name}/",  # Directory prefix (consistent, no timestamp)
            "manifest_key": manifest_key,
            "incremental": True,
            "files_unchanged": total_files_unchanged,
            "total_files_scanned": total_file_count,
            "upload_errors": len(upload_errors)
        }
    
    def _should_include(self, file_path: str, job) -> bool:
        """Check if file should be included based on patterns"""
        if job.exclude_patterns:
            exclude_list = json.loads(job.exclude_patterns)
            for pattern in exclude_list:
                if Path(file_path).match(pattern):
                    return False
        
        if job.include_patterns:
            include_list = json.loads(job.include_patterns)
            for pattern in include_list:
                if Path(file_path).match(pattern):
                    return True
            return False
        
        return True
