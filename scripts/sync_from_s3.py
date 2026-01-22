#!/usr/bin/env python3
"""
Sync backup information from S3 to database.

This script:
1. Scans S3 for backup files
2. Creates/updates snapshot records in database
3. Updates storage metrics
"""
import sys
import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, Snapshot, Job, BackupRun, BackupStatus, StorageClass
from app.aws import s3_client
from app.metrics import metrics_service
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_job_from_s3(job_id: int, dry_run: bool = False) -> Dict:
    """Sync a job's backup information from S3 to database"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")
        
        logger.info(f"Syncing job '{job.name}' (ID: {job_id}) from S3...")
        logger.info(f"  S3 bucket: {job.s3_bucket}")
        logger.info(f"  S3 prefix: {job.s3_prefix}")
        logger.info(f"  Dry run: {dry_run}")
        
        if job.job_type.value == "dataset" and not job.incremental_enabled:
            return sync_full_backup_from_s3(job, db, dry_run)
        else:
            return sync_incremental_backup_from_s3(job, db, dry_run)
    
    except Exception as e:
        logger.error(f"Error syncing job: {e}", exc_info=True)
        raise
    finally:
        db.close()


def sync_incremental_backup_from_s3(job: Job, db, dry_run: bool) -> Dict:
    """Sync incremental backup from S3 manifest"""
    # Check for manifest
    manifest_key = f"{job.s3_prefix}/{job.name}.manifest.json"
    
    logger.info(f"Looking for manifest: s3://{job.s3_bucket}/{manifest_key}")
    
    manifest_exists = s3_client.object_exists(job.s3_bucket, manifest_key)
    
    if not manifest_exists:
        logger.warning(f"Manifest not found at {manifest_key}")
        logger.info("Scanning S3 for files...")
        
        # List files in S3
        s3_prefix = f"{job.s3_prefix}/{job.name}/"
        files = list_s3_files(job.s3_bucket, s3_prefix)
        
        if not files:
            return {
                "status": "no_files",
                "message": "No files found in S3",
                "files_found": 0
            }
        
        logger.info(f"Found {len(files)} files in S3")
        
        # Calculate total size
        total_size = sum(size for size in files.values())
        total_files = len([k for k in files.keys() if not k.endswith('.manifest.json')])
        
        logger.info(f"Total size: {total_size / (1024**3):.2f} GB")
        logger.info(f"Total files: {total_files:,}")
        
        # Check if snapshot exists
        existing_snapshot = db.query(Snapshot).filter(
            Snapshot.job_id == job.id,
            Snapshot.retained == True
        ).order_by(Snapshot.created_at.desc()).first()
        
        if existing_snapshot:
            logger.info(f"Found existing snapshot ID: {existing_snapshot.snapshot_id}")
            if not dry_run:
                # Update existing snapshot
                existing_snapshot.size_bytes = total_size
                existing_snapshot.files_count = total_files
                existing_snapshot.s3_key = f"{job.s3_prefix}/{job.name}/"
                existing_snapshot.manifest_key = manifest_key if manifest_exists else None
                db.commit()
                logger.info("✓ Updated existing snapshot")
        else:
            # Create new snapshot
            snapshot_id = f"{job.name}_synced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Creating new snapshot: {snapshot_id}")
            
            if not dry_run:
                snapshot = Snapshot(
                    job_id=job.id,
                    snapshot_id=snapshot_id,
                    size_bytes=total_size,
                    files_count=total_files,
                    s3_key=f"{job.s3_prefix}/{job.name}/",
                    manifest_key=manifest_key if manifest_exists else None,
                    storage_class=job.storage_class,
                    is_incremental=True,
                    retained=True
                )
                db.add(snapshot)
                db.commit()
                logger.info("✓ Created new snapshot")
        
        return {
            "status": "synced",
            "snapshot_id": existing_snapshot.snapshot_id if existing_snapshot else snapshot_id,
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2),
            "files_count": total_files,
            "manifest_exists": manifest_exists
        }
    
    # Manifest exists - load it
    logger.info("Loading manifest from S3...")
    manifest = load_manifest(job, manifest_key)
    
    if not manifest:
        logger.error("Failed to load manifest")
        return {
            "status": "error",
            "message": "Manifest exists but could not be loaded"
        }
    
    files = manifest.get('files', {})
    total_size = sum(f.get('size', 0) for f in files.values())
    total_files = len(files)
    
    logger.info(f"Manifest loaded: {total_files:,} files, {total_size / (1024**3):.2f} GB")
    
    # Check if snapshot exists
    existing_snapshot = db.query(Snapshot).filter(
        Snapshot.job_id == job.id,
        Snapshot.retained == True
    ).order_by(Snapshot.created_at.desc()).first()
    
    if existing_snapshot:
        logger.info(f"Found existing snapshot ID: {existing_snapshot.snapshot_id}")
        if not dry_run:
            existing_snapshot.size_bytes = total_size
            existing_snapshot.files_count = total_files
            existing_snapshot.manifest_key = manifest_key
            db.commit()
            logger.info("✓ Updated existing snapshot")
        snapshot_id = existing_snapshot.snapshot_id
    else:
        snapshot_id = manifest.get('snapshot_id', f"{job.name}_synced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        logger.info(f"Creating new snapshot: {snapshot_id}")
        
        if not dry_run:
            snapshot = Snapshot(
                job_id=job.id,
                snapshot_id=snapshot_id,
                size_bytes=total_size,
                files_count=total_files,
                s3_key=f"{job.s3_prefix}/{job.name}/",
                manifest_key=manifest_key,
                storage_class=job.storage_class,
                is_incremental=True,
                retained=True
            )
            db.add(snapshot)
            db.commit()
            logger.info("✓ Created new snapshot")
    
    return {
        "status": "synced",
        "snapshot_id": snapshot_id,
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024**3), 2),
        "files_count": total_files,
        "manifest_exists": True
    }


def sync_full_backup_from_s3(job: Job, db, dry_run: bool) -> Dict:
    """Sync full backup from S3"""
    expected_s3_key = f"{job.s3_prefix}/{job.name}.tar.gz"
    if job.encryption_enabled:
        expected_s3_key += ".encrypted"
    
    logger.info(f"Looking for backup file: s3://{job.s3_bucket}/{expected_s3_key}")
    
    exists = s3_client.object_exists(job.s3_bucket, expected_s3_key)
    
    if not exists:
        return {
            "status": "not_found",
            "message": f"Backup file not found: {expected_s3_key}"
        }
    
    # Get file info from S3
    info = s3_client.get_object_info(job.s3_bucket, expected_s3_key)
    
    if not info or not info.get('exists'):
        return {
            "status": "error",
            "message": "Could not get file info from S3"
        }
    
    size_bytes = info.get('size', 0)
    
    logger.info(f"Found backup file: {size_bytes / (1024**3):.2f} GB")
    
    # Check if snapshot exists
    existing_snapshot = db.query(Snapshot).filter(
        Snapshot.job_id == job.id,
        Snapshot.retained == True
    ).order_by(Snapshot.created_at.desc()).first()
    
    if existing_snapshot:
        logger.info(f"Found existing snapshot ID: {existing_snapshot.snapshot_id}")
        if not dry_run:
            existing_snapshot.size_bytes = size_bytes
            existing_snapshot.s3_key = expected_s3_key
            db.commit()
            logger.info("✓ Updated existing snapshot")
        snapshot_id = existing_snapshot.snapshot_id
    else:
        snapshot_id = f"{job.name}_synced_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Creating new snapshot: {snapshot_id}")
        
        if not dry_run:
            snapshot = Snapshot(
                job_id=job.id,
                snapshot_id=snapshot_id,
                size_bytes=size_bytes,
                files_count=0,  # Full backups don't track individual files
                s3_key=expected_s3_key,
                storage_class=job.storage_class,
                is_incremental=False,
                retained=True
            )
            db.add(snapshot)
            db.commit()
            logger.info("✓ Created new snapshot")
    
    return {
        "status": "synced",
        "snapshot_id": snapshot_id,
        "total_size_bytes": size_bytes,
        "total_size_gb": round(size_bytes / (1024**3), 2)
    }


def list_s3_files(bucket: str, prefix: str) -> Dict[str, int]:
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


def load_manifest(job: Job, manifest_key: str) -> Optional[Dict]:
    """Load manifest from S3"""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
            temp_manifest = f.name
        
        s3_client.download_file(job.s3_bucket, manifest_key, temp_manifest)
        
        # Decrypt if needed
        if job.encryption_enabled:
            from app.encryption import decrypt_file
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


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync backup information from S3 to database")
    parser.add_argument("--job-id", type=int, required=True, help="Job ID to sync")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just report")
    parser.add_argument("--update-metrics", action="store_true", help="Update storage metrics after sync")
    
    args = parser.parse_args()
    
    try:
        result = sync_job_from_s3(args.job_id, dry_run=args.dry_run)
        
        print("\n" + "="*60)
        print("SYNC RESULTS")
        print("="*60)
        print(f"Status: {result.get('status')}")
        if result.get('snapshot_id'):
            print(f"Snapshot ID: {result.get('snapshot_id')}")
        if result.get('total_size_gb'):
            print(f"Total Size: {result.get('total_size_gb')} GB")
        if result.get('files_count'):
            print(f"Files: {result.get('files_count'):,}")
        print("="*60)
        
        if args.update_metrics and not args.dry_run:
            logger.info("\nUpdating storage metrics...")
            db = SessionLocal()
            try:
                metrics_service.record_daily_metrics(db)
                logger.info("✓ Metrics updated")
            finally:
                db.close()
    
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
