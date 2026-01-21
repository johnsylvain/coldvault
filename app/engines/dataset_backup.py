"""
Dataset backup engine - incremental snapshots
"""
import os
import tarfile
import gzip
import hashlib
import logging
from datetime import datetime
from pathlib import Path
import json
import tempfile

from app.aws import s3_client
from app.encryption import encrypt_file
from app.config import settings

logger = logging.getLogger(__name__)

class DatasetBackupEngine:
    """Handles dataset-level incremental backups"""
    
    def backup(self, job, backup_run, db, backup_logger=None, cancellation_flags=None, backup_run_id=None):
        """Execute a dataset backup"""
        if backup_logger is None:
            backup_logger = logger
        
        def check_cancellation():
            """Check if backup should be cancelled"""
            if cancellation_flags and backup_run_id:
                if cancellation_flags.get(backup_run_id, False):
                    backup_logger.warning("Cancellation requested, stopping backup...")
                    raise InterruptedError("Backup cancelled by user")
        
        source_paths = json.loads(job.source_paths)
        # Generate snapshot_id with timestamp for database tracking/logging
        # Note: S3 key will be consistent (no timestamp) for consolidated backup strategy
        snapshot_id = f"{job.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        backup_logger.info(f"Creating backup snapshot: {snapshot_id}")
        backup_logger.info(f"Backup will overwrite previous backup at: s3://{job.s3_bucket}/{job.s3_prefix}/{job.name}.tar.gz")
        
        # Create temporary directory for backup
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = os.path.join(temp_dir, f"{snapshot_id}.tar.gz")
            backup_logger.info(f"Temporary backup file: {backup_file}")
            
            # Create tar archive
            total_size = 0
            file_count = 0
            skipped_files = 0
            last_progress_log = datetime.utcnow()
            start_time = datetime.utcnow()
            
            backup_logger.info("Starting file collection and archiving...")
            backup_logger.info("Note: This creates a single tar.gz archive file. Folder structure is preserved inside the archive.")
            
            # Use compression level 6 (balance between speed and size)
            # For very large backups, consider using 'w:' (no compression) for speed
            # or 'w:gz' with compresslevel=1 for faster compression
            compression_level = 6  # 1-9, higher = smaller but slower
            backup_logger.info(f"Creating tar.gz archive with compression level {compression_level}")
            
            with tarfile.open(backup_file, 'w:gz', compresslevel=compression_level) as tar:
                for idx, source_path in enumerate(source_paths, 1):
                    check_cancellation()  # Check before processing each source path
                    
                    backup_logger.info(f"Processing source path {idx}/{len(source_paths)}: {source_path}")
                    
                    if not os.path.exists(source_path):
                        backup_logger.warning(f"Source path does not exist: {source_path}")
                        continue
                    
                    # Add files to archive
                    for root, dirs, files in os.walk(source_path):
                        check_cancellation()  # Check during file traversal
                        
                        # Apply exclude patterns
                        if job.exclude_patterns:
                            exclude_list = json.loads(job.exclude_patterns)
                            dirs[:] = [d for d in dirs if not any(
                                Path(root, d).match(pattern) for pattern in exclude_list
                            )]
                        
                        for file in files:
                            # Check cancellation every 100 files
                            if file_count % 100 == 0:
                                check_cancellation()
                            
                            file_path = os.path.join(root, file)
                            
                            # Check include/exclude patterns
                            if self._should_include(file_path, job):
                                try:
                                    file_size = os.path.getsize(file_path)
                                    tar.add(file_path, arcname=os.path.relpath(file_path, source_path))
                                    file_count += 1
                                    total_size += file_size
                                    
                                    # Log progress - more frequent for large backups
                                    now = datetime.utcnow()
                                    time_since_last = (now - last_progress_log).total_seconds()
                                    
                                    # Log more frequently for large datasets
                                    should_log = (
                                        file_count % 1000 == 0 or  # Every 1000 files
                                        (file_count <= 100 and file_count % 10 == 0) or  # Every 10 files for first 100
                                        (total_size > 1024**3 and time_since_last >= 30) or  # Every 30s for >1GB datasets
                                        time_since_last >= 10  # Every 10 seconds otherwise
                                    )
                                    if should_log:
                                        size_mb = total_size / (1024**2)
                                        size_gb = total_size / (1024**3)
                                        elapsed = (now - start_time).total_seconds()
                                        rate_mbps = (total_size / (1024**2)) / elapsed if elapsed > 0 else 0
                                        
                                        if size_gb >= 1:
                                            backup_logger.info(f"Progress: {file_count:,} files, {size_gb:.2f} GB processed ({rate_mbps:.1f} MB/s)...")
                                        else:
                                            backup_logger.info(f"Progress: {file_count:,} files, {size_mb:.2f} MB processed ({rate_mbps:.1f} MB/s)...")
                                        last_progress_log = now
                                except Exception as e:
                                    skipped_files += 1
                                    backup_logger.warning(f"Failed to add {file_path}: {e}")
                            else:
                                skipped_files += 1
            
            collection_duration = (datetime.utcnow() - start_time).total_seconds()
            backup_logger.info("=" * 60)
            backup_logger.info("FILE COLLECTION COMPLETE")
            backup_logger.info(f"Files processed: {file_count:,}")
            backup_logger.info(f"Files skipped: {skipped_files:,}")
            backup_logger.info(f"Total data size: {total_size / (1024**2):.2f} MB")
            backup_logger.info(f"Collection time: {collection_duration:.1f} seconds")
            backup_logger.info("=" * 60)
            
            # Get final archive size on disk
            archive_size = os.path.getsize(backup_file)
            backup_logger.info(f"Archive file created: {archive_size / (1024**2):.2f} MB on disk")
            backup_logger.info(f"Compression ratio: {(1 - archive_size/total_size) * 100:.1f}%" if total_size > 0 else "N/A")
            
            check_cancellation()  # Check before encryption/upload
            
            # Encrypt if enabled
            if job.encryption_enabled:
                backup_logger.info("Encrypting backup file...")
                encrypted_file = backup_file + ".encrypted"
                encrypt_file(backup_file, encrypted_file, settings.encryption_key)
                backup_file = encrypted_file
                encrypted_size = os.path.getsize(backup_file)
                backup_logger.info(f"Encryption complete. Encrypted size: {encrypted_size / (1024**2):.2f} MB")
                check_cancellation()  # Check after encryption
            
            # Upload to S3
            # Use consistent S3 key (without timestamp) for consolidated backup strategy
            # This overwrites the previous backup, suitable for 3-2-1 backup strategy
            check_cancellation()  # Check before upload
            s3_key = f"{job.s3_prefix}/{job.name}.tar.gz"
            if job.encryption_enabled:
                s3_key += ".encrypted"
            
            storage_class_map = {
                "STANDARD": "STANDARD",
                "GLACIER_IR": "GLACIER_IR",
                "GLACIER_FLEXIBLE": "GLACIER_FLEXIBLE",
                "DEEP_ARCHIVE": "DEEP_ARCHIVE"
            }
            
            s3_storage_class = storage_class_map.get(job.storage_class.value, "DEEP_ARCHIVE")
            
            backup_logger.info("=" * 60)
            backup_logger.info("STARTING S3 UPLOAD")
            backup_logger.info(f"S3 location: s3://{job.s3_bucket}/{s3_key}")
            backup_logger.info(f"Storage class: {s3_storage_class}")
            
            file_size_mb = os.path.getsize(backup_file) / (1024**2)
            backup_logger.info(f"Upload size: {file_size_mb:.2f} MB")
            backup_logger.info("Note: Upload progress will be logged every 10MB")
            backup_logger.info("=" * 60)
            
            try:
                backup_logger.info("Starting S3 upload...")
                
                # Check S3 client before attempting upload
                if not s3_client.client:
                    error_msg = "S3 client not initialized. Check AWS credentials in .env file."
                    backup_logger.error(error_msg)
                    raise Exception(error_msg)
                
                backup_logger.info(f"S3 client initialized, bucket: {job.s3_bucket}, region: {settings.aws_region}")
                
                s3_client.upload_file(
                    backup_file,
                    job.s3_bucket,
                    s3_key,
                    storage_class=s3_storage_class
                )
                backup_logger.info(f"Upload complete: s3://{job.s3_bucket}/{s3_key}")
            except FileNotFoundError as e:
                backup_logger.error(f"Backup file not found for upload: {e}")
                raise
            except Exception as e:
                error_msg = str(e)
                backup_logger.error(f"S3 upload failed: {error_msg}", exc_info=True)
                
                # Provide helpful error messages
                if "not initialized" in error_msg.lower() or "credentials" in error_msg.lower():
                    backup_logger.error("AWS credentials issue. Check:")
                    backup_logger.error("  - AWS_ACCESS_KEY_ID is set in .env")
                    backup_logger.error("  - AWS_SECRET_ACCESS_KEY is set in .env")
                    backup_logger.error("  - AWS_REGION matches your bucket region")
                elif "NoSuchBucket" in error_msg or "404" in error_msg:
                    backup_logger.error(f"Bucket '{job.s3_bucket}' does not exist. Create it in AWS Console.")
                elif "AccessDenied" in error_msg or "403" in error_msg:
                    backup_logger.error("Access denied. Check IAM permissions:")
                    backup_logger.error("  - s3:PutObject")
                    backup_logger.error("  - s3:PutObjectAcl (if using ACLs)")
                
                raise
            
            return {
                "snapshot_id": snapshot_id,
                "size_bytes": total_size,
                "files_count": file_count,
                "s3_key": s3_key
            }
    
    def _should_include(self, file_path: str, job) -> bool:
        """Check if file should be included based on patterns"""
        # Check exclude patterns
        if job.exclude_patterns:
            exclude_list = json.loads(job.exclude_patterns)
            for pattern in exclude_list:
                if Path(file_path).match(pattern):
                    return False
        
        # Check include patterns
        if job.include_patterns:
            include_list = json.loads(job.include_patterns)
            for pattern in include_list:
                if Path(file_path).match(pattern):
                    return True
            return False
        
        return True
