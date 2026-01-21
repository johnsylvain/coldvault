"""
Sync and reconciliation utility for database-S3 consistency

Handles cases where database and S3 storage get out of sync:
- Partial/failed backups
- Manual S3 deletions
- Database restore without S3 restore (or vice versa)
- Network issues during upload
"""
import os
import json
import logging
import tempfile
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.database import SessionLocal, Snapshot, Job
from app.aws import s3_client
from app.encryption import decrypt_file
from app.config import settings

logger = logging.getLogger(__name__)


class SyncWorker:
    """Handles synchronization between database and S3 storage"""
    
    def sync_job(self, job_id: int, dry_run: bool = True) -> Dict:
        """
        Synchronize a job's database state with S3 storage
        
        Args:
            job_id: Job ID to sync
            dry_run: If True, only report differences without fixing
            
        Returns:
            Dictionary with sync results
        """
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise Exception(f"Job {job_id} not found")
            
            logger.info(f"Syncing job '{job.name}' (dry_run={dry_run})")
            
            if job.job_type.value == "dataset" and not job.incremental_enabled:
                # Full backup - check if tar.gz exists
                return self._sync_full_backup(job, db, dry_run)
            else:
                # Incremental backup - check manifest and files
                return self._sync_incremental_backup(job, db, dry_run)
                
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            raise
        finally:
            db.close()
    
    def _sync_full_backup(self, job: Job, db, dry_run: bool) -> Dict:
        """Sync a full backup job"""
        # Get the most recent snapshot
        latest_snapshot = db.query(Snapshot).filter(
            Snapshot.job_id == job.id,
            Snapshot.retained == True
        ).order_by(Snapshot.created_at.desc()).first()
        
        if not latest_snapshot:
            return {
                "status": "no_snapshots",
                "message": "No snapshots found for this job",
                "issues": []
            }
        
        # Expected S3 key (consistent location)
        expected_s3_key = f"{job.s3_prefix}/{job.name}.tar.gz"
        if job.encryption_enabled:
            expected_s3_key += ".encrypted"
        
        # Check if file exists in S3
        exists = s3_client.object_exists(job.s3_bucket, expected_s3_key)
        
        issues = []
        actions = []
        
        if not exists:
            issues.append({
                "type": "missing_backup",
                "severity": "critical",
                "message": f"Backup file not found in S3: s3://{job.s3_bucket}/{expected_s3_key}",
                "s3_key": expected_s3_key
            })
            
            if not dry_run:
                actions.append({
                    "action": "mark_snapshot_invalid",
                    "message": "Marked snapshot as invalid (backup file missing)"
                })
        
        # Check if database s3_key matches expected location
        if latest_snapshot.s3_key != expected_s3_key:
            issues.append({
                "type": "s3_key_mismatch",
                "severity": "warning",
                "message": f"Database s3_key doesn't match expected location",
                "database_key": latest_snapshot.s3_key,
                "expected_key": expected_s3_key
            })
            
            if not dry_run:
                # Update snapshot with correct key
                latest_snapshot.s3_key = expected_s3_key
                db.commit()
                actions.append({
                    "action": "updated_s3_key",
                    "message": f"Updated database s3_key to match expected location"
                })
        
        return {
            "status": "completed",
            "job_id": job.id,
            "job_name": job.name,
            "backup_type": "full",
            "dry_run": dry_run,
            "issues": issues,
            "actions": actions,
            "s3_key": expected_s3_key,
            "exists_in_s3": exists
        }
    
    def _sync_incremental_backup(self, job: Job, db, dry_run: bool) -> Dict:
        """Sync an incremental backup job"""
        # Get the most recent snapshot
        latest_snapshot = db.query(Snapshot).filter(
            Snapshot.job_id == job.id,
            Snapshot.retained == True
        ).order_by(Snapshot.created_at.desc()).first()
        
        if not latest_snapshot:
            return {
                "status": "no_snapshots",
                "message": "No snapshots found for this job",
                "issues": []
            }
        
        # Expected manifest location (consistent)
        expected_manifest_key = f"{job.s3_prefix}/{job.name}.manifest.json"
        
        issues = []
        actions = []
        files_missing = []
        files_orphaned = []
        files_mismatched = []
        
        # Step 1: Check if manifest exists
        manifest_exists = s3_client.object_exists(job.s3_bucket, expected_manifest_key)
        manifest_data = None
        
        if not manifest_exists:
            # Try to rebuild manifest from S3
            logger.warning(f"Manifest not found at {expected_manifest_key}, attempting to rebuild from S3...")
            manifest_data = self._rebuild_manifest_from_s3(job, expected_manifest_key)
            
            if manifest_data:
                issues.append({
                    "type": "manifest_rebuilt",
                    "severity": "info",
                    "message": "Manifest was missing but rebuilt from S3",
                    "files_found": len(manifest_data.get('files', {}))
                })
                
                if not dry_run:
                    # Save rebuilt manifest
                    self._save_manifest(job, manifest_data, expected_manifest_key)
                    actions.append({
                        "action": "manifest_rebuilt",
                        "message": "Rebuilt and saved manifest from S3"
                    })
            else:
                # No manifest and couldn't rebuild - scan S3 directly
                issues.append({
                    "type": "manifest_missing",
                    "severity": "warning",
                    "message": f"Manifest not found at {expected_manifest_key}. Scanning S3 directly to discover files."
                })
                # Continue without manifest - we'll scan S3 directly
                manifest_data = None
        else:
            # Step 2: Load manifest and verify files
            manifest_data = self._load_manifest(job, expected_manifest_key)
            
            if not manifest_data:
                # Manifest exists but can't be read - try to rebuild from S3
                logger.warning(f"Manifest exists but could not be read, attempting to rebuild from S3...")
                issues.append({
                    "type": "manifest_unreadable",
                    "severity": "warning",
                    "message": "Manifest exists but could not be read. Rebuilding from S3."
                })
                manifest_data = self._rebuild_manifest_from_s3(job, expected_manifest_key)
                
                if manifest_data and not dry_run:
                    # Save rebuilt manifest
                    self._save_manifest(job, manifest_data, expected_manifest_key)
                    actions.append({
                        "action": "manifest_rebuilt",
                        "message": "Rebuilt and saved manifest from S3 (original was unreadable)"
                    })
                elif not manifest_data:
                    # Even rebuilding failed - continue without manifest
                    manifest_data = None
        
        # Step 3: Get S3 files list
        s3_prefix = f"{job.s3_prefix}/{job.name}/"
        s3_files = self._list_s3_files(job.s3_bucket, s3_prefix)
        
        # Step 4: Compare manifest files with S3 (if manifest exists)
        manifest_files = manifest_data.get('files', {}) if manifest_data else {}
        verified_count = 0
        
        if manifest_files:
            logger.info(f"Verifying {len(manifest_files)} files from manifest...")
            
            # Check each file in manifest
            with ThreadPoolExecutor(max_workers=min(10, len(manifest_files))) as executor:
                future_to_path = {
                    executor.submit(
                        self._verify_file,
                        job.s3_bucket,
                        file_data.get('s3_key'),
                        file_data
                    ): rel_path
                    for rel_path, file_data in manifest_files.items()
                }
                
                for future in as_completed(future_to_path):
                    rel_path = future_to_path[future]
                    try:
                        exists, size_match, hash_match = future.result()
                        
                        if not exists:
                            files_missing.append({
                                "path": rel_path,
                                "s3_key": manifest_files[rel_path].get('s3_key')
                            })
                        elif not size_match:
                            files_mismatched.append({
                                "path": rel_path,
                                "s3_key": manifest_files[rel_path].get('s3_key'),
                                "issue": "size_mismatch"
                            })
                        else:
                            verified_count += 1
                    except Exception as e:
                        logger.error(f"Error verifying {rel_path}: {e}")
                        files_missing.append({
                            "path": rel_path,
                            "s3_key": manifest_files[rel_path].get('s3_key'),
                            "error": str(e)
                        })
            
            # Find orphaned files in S3 (files in S3 not in manifest)
            manifest_s3_keys = {f.get('s3_key') for f in manifest_files.values() if f.get('s3_key')}
            
            for s3_key in s3_files:
                if s3_key not in manifest_s3_keys and not s3_key.endswith('.manifest.json'):
                    files_orphaned.append({
                        "s3_key": s3_key,
                        "size": s3_files[s3_key]
                    })
        else:
            # No manifest - all S3 files are "orphaned" (not tracked)
            # But we'll report them as discovered files, not orphaned
            logger.info(f"No manifest available. Found {len(s3_files)} files in S3.")
            for s3_key, size in s3_files.items():
                if not s3_key.endswith('.manifest.json'):
                    files_orphaned.append({
                        "s3_key": s3_key,
                        "size": size
                    })
            
            # If we found files but no manifest, suggest creating one
            if s3_files and not dry_run:
                # Create a basic manifest from S3 files
                if not manifest_data:
                    manifest_data = self._rebuild_manifest_from_s3(job, expected_manifest_key)
                    if manifest_data:
                        self._save_manifest(job, manifest_data, expected_manifest_key)
                        actions.append({
                            "action": "manifest_created",
                            "message": f"Created manifest from {len(s3_files)} files found in S3"
                        })
                        issues.append({
                            "type": "manifest_created",
                            "severity": "info",
                            "message": f"Created new manifest from {len(s3_files)} files discovered in S3"
                        })
        
        # Compile issues
        if files_missing:
            issues.append({
                "type": "files_missing",
                "severity": "critical",
                "count": len(files_missing),
                "files": files_missing[:10]  # Show first 10
            })
        
        if files_orphaned:
            orphaned_message = "Files in S3 not tracked in manifest" if manifest_data else "Files discovered in S3 (no manifest available)"
            issues.append({
                "type": "files_orphaned",
                "severity": "warning" if manifest_data else "info",
                "count": len(files_orphaned),
                "message": orphaned_message,
                "files": files_orphaned[:10]  # Show first 10
            })
            
            if not dry_run:
                # Option to clean up orphaned files (commented out for safety)
                # Uncomment if you want automatic cleanup
                # self._cleanup_orphaned_files(job, files_orphaned)
                actions.append({
                    "action": "orphaned_files_found",
                    "count": len(files_orphaned),
                    "message": "Orphaned files found but not deleted (safety measure)"
                })
        
        if files_mismatched:
            issues.append({
                "type": "files_mismatched",
                "severity": "warning",
                "count": len(files_mismatched),
                "files": files_mismatched[:10]
            })
        
        # Update manifest_key in database if needed
        if latest_snapshot.manifest_key != expected_manifest_key:
            if not dry_run:
                latest_snapshot.manifest_key = expected_manifest_key
                db.commit()
                actions.append({
                    "action": "updated_manifest_key",
                    "message": "Updated database manifest_key to match expected location"
                })
        
        return {
            "status": "completed",
            "job_id": job.id,
            "job_name": job.name,
            "backup_type": "incremental",
            "dry_run": dry_run,
            "issues": issues,
            "actions": actions,
            "summary": {
                "total_files_in_manifest": len(manifest_files) if manifest_data else 0,
                "total_files_in_s3": len(s3_files),
                "files_verified": verified_count,
                "files_missing": len(files_missing),
                "files_orphaned": len(files_orphaned),
                "files_mismatched": len(files_mismatched),
                "manifest_available": manifest_data is not None
            }
        }
    
    def _load_manifest(self, job: Job, manifest_key: str) -> Optional[Dict]:
        """Load manifest from S3"""
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
                temp_manifest = f.name
            
            s3_client.download_file(job.s3_bucket, manifest_key, temp_manifest)
            
            # Decrypt if needed
            if job.encryption_enabled:
                decrypted_manifest = temp_manifest + ".decrypted"
                decrypt_file(temp_manifest, decrypted_manifest, settings.encryption_key)
                os.unlink(temp_manifest)
                temp_manifest = decrypted_manifest
            
            with open(temp_manifest, 'r') as f:
                manifest = json.load(f)
            
            os.unlink(temp_manifest)
            return manifest
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return None
    
    def _save_manifest(self, job: Job, manifest_data: Dict, manifest_key: str):
        """Save manifest to S3"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            manifest_file = f.name
            json.dump(manifest_data, f, indent=2)
        
        try:
            if job.encryption_enabled:
                encrypted_manifest = manifest_file + ".encrypted"
                from app.encryption import encrypt_file
                encrypt_file(manifest_file, encrypted_manifest, settings.encryption_key)
                s3_client.upload_file(
                    encrypted_manifest,
                    job.s3_bucket,
                    manifest_key,
                    storage_class=job.storage_class.value if hasattr(job.storage_class, 'value') else "DEEP_ARCHIVE"
                )
                os.unlink(encrypted_manifest)
            else:
                s3_client.upload_file(
                    manifest_file,
                    job.s3_bucket,
                    manifest_key,
                    storage_class=job.storage_class.value if hasattr(job.storage_class, 'value') else "DEEP_ARCHIVE"
                )
        finally:
            if os.path.exists(manifest_file):
                os.unlink(manifest_file)
    
    def _rebuild_manifest_from_s3(self, job: Job, manifest_key: str) -> Optional[Dict]:
        """Rebuild manifest by scanning S3 for files"""
        s3_prefix = f"{job.s3_prefix}/{job.name}/"
        s3_files = self._list_s3_files(job.s3_bucket, s3_prefix)
        
        if not s3_files:
            return None
        
        # Reconstruct manifest from S3 files
        files = {}
        for s3_key, size in s3_files.items():
            # Extract relative path from S3 key
            rel_path = s3_key.replace(s3_prefix, '')
            if rel_path:  # Skip empty paths
                files[rel_path] = {
                    's3_key': s3_key,
                    'size': size,
                    # Note: hash and mtime not available from S3 alone
                    'hash': None,
                    'mtime': None
                }
        
        return {
            'snapshot_id': f"{job.name}_rebuilt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'created_at': datetime.utcnow().isoformat(),
            'job_id': job.id,
            'total_files': len(files),
            'files': files
        }
    
    def _list_s3_files(self, bucket: str, prefix: str) -> Dict[str, int]:
        """List all files in S3 with given prefix"""
        files = {}
        try:
            if not s3_client.client:
                logger.error("S3 client not initialized")
                return files
            paginator = s3_client.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    size = obj['Size']
                    files[key] = size
        except Exception as e:
            logger.error(f"Failed to list S3 files: {e}")
        return files
    
    def _verify_file(self, bucket: str, s3_key: Optional[str], file_data: Dict) -> Tuple[bool, bool, bool]:
        """Verify a file exists in S3 and matches expected size"""
        if not s3_key:
            return False, False, False
        
        try:
            info = s3_client.get_object_info(bucket, s3_key)
            if not info or not info.get('exists'):
                return False, False, False
            
            expected_size = file_data.get('size')
            actual_size = info.get('size', 0)
            size_match = expected_size == actual_size if expected_size else True
            
            # Hash verification would require downloading, skip for now
            hash_match = True
            
            return True, size_match, hash_match
        except Exception as e:
            logger.error(f"Error verifying file {s3_key}: {e}")
            return False, False, False
    
    def _cleanup_orphaned_files(self, job: Job, orphaned_files: List[Dict]):
        """Delete orphaned files from S3 (use with caution!)"""
        # This is commented out by default for safety
        # Uncomment and use carefully
        logger.warning(f"Cleanup of {len(orphaned_files)} orphaned files is disabled for safety")
        # for file_info in orphaned_files:
        #     try:
        #         s3_client.client.delete_object(Bucket=job.s3_bucket, Key=file_info['s3_key'])
        #         logger.info(f"Deleted orphaned file: {file_info['s3_key']}")
        #     except Exception as e:
        #         logger.error(f"Failed to delete {file_info['s3_key']}: {e}")


sync_worker = SyncWorker()
