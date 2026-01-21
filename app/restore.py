"""
Restore functionality
"""
import os
import json
import logging
import tarfile
import tempfile
from pathlib import Path

from app.database import SessionLocal, Snapshot, Job
from app.aws import s3_client
from app.encryption import decrypt_file
from app.config import settings

logger = logging.getLogger(__name__)

class RestoreWorker:
    def restore_snapshot(self, snapshot_id: int, restore_path: str, file_paths: list = None):
        """Restore a snapshot (handles both full and incremental backups)"""
        db = SessionLocal()
        try:
            snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
            if not snapshot:
                raise Exception(f"Snapshot {snapshot_id} not found")
            
            job = db.query(Job).filter(Job.id == snapshot.job_id).first()
            if not job:
                raise Exception(f"Job not found for snapshot {snapshot_id}")
            
            # Check if restore is needed (Glacier)
            if snapshot.storage_class and "GLACIER" in snapshot.storage_class.value:
                # Initiate restore
                logger.info(f"Snapshot is in Glacier, initiating restore...")
                s3_client.initiate_restore(
                    job.s3_bucket,
                    snapshot.s3_key,
                    tier="Expedited"  # Could be configurable
                )
                raise Exception("Snapshot is in Glacier. Restore initiated. Please wait and retry later.")
            
            # For incremental backups, we need to restore all snapshots up to this point
            if snapshot.is_incremental:
                logger.info("Incremental backup detected. Restoring all snapshots up to this point...")
                self._restore_incremental(job, snapshot, restore_path, file_paths, db)
            else:
                # Full backup - restore single snapshot
                self._restore_full(snapshot, job, restore_path, file_paths)
            
            logger.info(f"Restored snapshot {snapshot.snapshot_id} to {restore_path}")
        
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise
        finally:
            db.close()
    
    def _restore_full(self, snapshot, job, restore_path: str, file_paths: list = None):
        """Restore a full backup snapshot"""
        # Download from S3
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            
            s3_client.download_file(
                job.s3_bucket,
                snapshot.s3_key,
                temp_path
            )
            
            # Decrypt if needed
            if job.encryption_enabled:
                decrypted_path = temp_path + ".decrypted"
                decrypt_file(temp_path, decrypted_path, settings.encryption_key)
                temp_path = decrypted_path
            
            # Extract archive
            if snapshot.s3_key.endswith('.tar.gz') or snapshot.s3_key.endswith('.tar'):
                with tarfile.open(temp_path, 'r:*') as tar:
                    if file_paths:
                        # Extract specific files
                        for file_path in file_paths:
                            try:
                                tar.extract(file_path, restore_path)
                            except KeyError:
                                logger.warning(f"File {file_path} not found in archive")
                    else:
                        # Extract all
                        tar.extractall(restore_path)
            
            # Cleanup
            os.unlink(temp_path)
            if job.encryption_enabled and os.path.exists(temp_path + ".decrypted"):
                os.unlink(temp_path + ".decrypted")
    
    def _restore_incremental(self, job, target_snapshot, restore_path: str, file_paths: list = None, db=None):
        """Restore incremental backup - downloads files directly from S3"""
        # Get all snapshots up to and including the target snapshot
        snapshots = db.query(Snapshot).filter(
            Snapshot.job_id == job.id,
            Snapshot.retained == True,
            Snapshot.created_at <= target_snapshot.created_at
        ).order_by(Snapshot.created_at.asc()).all()
        
        logger.info(f"Restoring {len(snapshots)} incremental snapshots...")
        
        # Load manifest from the target snapshot (it contains all files up to that point)
        manifest_key = target_snapshot.manifest_key
        if not manifest_key:
            raise Exception(f"No manifest found for snapshot {target_snapshot.snapshot_id}")
        
        # Download manifest
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
            temp_manifest = f.name
        
        s3_client.download_file(job.s3_bucket, manifest_key, temp_manifest)
        
        # Decrypt manifest if needed (all files are encrypted if encryption is enabled)
        if job.encryption_enabled:
            decrypted_manifest = temp_manifest + ".decrypted"
            decrypt_file(temp_manifest, decrypted_manifest, settings.encryption_key)
            os.unlink(temp_manifest)
            temp_manifest = decrypted_manifest
        
        # Load manifest
        with open(temp_manifest, 'r') as f:
            manifest = json.load(f)
        
        os.unlink(temp_manifest)
        
        files = manifest.get('files', {})
        logger.info(f"Manifest contains {len(files)} files")
        
        # Filter files if specific paths requested
        if file_paths:
            files = {rel_path: file_data for rel_path, file_data in files.items() 
                    if any(rel_path.startswith(fp) or fp in rel_path for fp in file_paths)}
            logger.info(f"Filtered to {len(files)} files matching requested paths")
        
        # Download files in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        downloaded_count = 0
        total_files = len(files)
        
        def download_file(rel_path: str, file_data: dict):
            """Download a single file from S3"""
            s3_key = file_data.get('s3_key')
            if not s3_key:
                logger.warning(f"No S3 key for {rel_path}, skipping")
                return False
            
            try:
                # Create local path preserving directory structure
                local_file_path = os.path.join(restore_path, rel_path)
                local_dir = os.path.dirname(local_file_path)
                os.makedirs(local_dir, exist_ok=True)
                
                # Download to temp file first
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                s3_client.download_file(job.s3_bucket, s3_key, temp_path)
                
                # Decrypt if needed (all files are encrypted if encryption is enabled)
                if job.encryption_enabled:
                    decrypted_path = temp_path + ".decrypted"
                    decrypt_file(temp_path, decrypted_path, settings.encryption_key)
                    os.unlink(temp_path)
                    temp_path = decrypted_path
                
                # Move to final location
                os.rename(temp_path, local_file_path)
                return True
            except Exception as e:
                logger.error(f"Failed to download {rel_path}: {e}")
                return False
        
        # Download files in parallel
        max_workers = min(10, total_files)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(download_file, rel_path, file_data): rel_path
                for rel_path, file_data in files.items()
            }
            
            for future in as_completed(future_to_path):
                rel_path = future_to_path[future]
                try:
                    if future.result():
                        downloaded_count += 1
                        if downloaded_count % 100 == 0 or downloaded_count == total_files:
                            logger.info(f"Downloaded {downloaded_count}/{total_files} files...")
                except Exception as e:
                    logger.error(f"Error downloading {rel_path}: {e}")
        
        logger.info(f"Restore complete: {downloaded_count}/{total_files} files downloaded")

restore_worker = RestoreWorker()
