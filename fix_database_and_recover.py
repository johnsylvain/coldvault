#!/usr/bin/env python3
"""
Fix database schema and recover stuck backup job.

This script:
1. Alters the database columns from INTEGER to BIGINT for size_bytes
2. Recovers the stuck backup run by updating it with the correct status
"""
import sys
import os
from datetime import datetime

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, BackupRun, Snapshot, BackupStatus, engine
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_schema():
    """Alter database columns from INTEGER to BIGINT"""
    logger.info("Fixing database schema...")
    
    # Check database type
    database_url = settings.get_database_url()
    
    if database_url.startswith("sqlite"):
        logger.info("SQLite database detected - no schema changes needed (SQLite uses dynamic types)")
        return
    
    # PostgreSQL - need to alter columns
    logger.info("PostgreSQL database detected - altering columns...")
    
    with engine.connect() as conn:
        try:
            # Alter backup_runs.size_bytes
            conn.execute("""
                ALTER TABLE backup_runs 
                ALTER COLUMN size_bytes TYPE BIGINT;
            """)
            logger.info("✓ Fixed backup_runs.size_bytes")
            
            # Alter snapshots.size_bytes
            conn.execute("""
                ALTER TABLE snapshots 
                ALTER COLUMN size_bytes TYPE BIGINT;
            """)
            logger.info("✓ Fixed snapshots.size_bytes")
            
            conn.commit()
            logger.info("Database schema fixed successfully!")
        except Exception as e:
            logger.error(f"Error fixing schema: {e}")
            logger.info("This might be okay if columns are already BIGINT")
            conn.rollback()

def recover_stuck_backup(backup_run_id: int = None):
    """Recover a stuck backup run"""
    db = SessionLocal()
    try:
        if backup_run_id:
            # Recover specific backup run
            backup_run = db.query(BackupRun).filter(BackupRun.id == backup_run_id).first()
            if not backup_run:
                logger.error(f"Backup run {backup_run_id} not found")
                return
            
            if backup_run.status != BackupStatus.RUNNING:
                logger.info(f"Backup run {backup_run_id} is not in RUNNING status (current: {backup_run.status.value})")
                return
            
            logger.info(f"Found stuck backup run {backup_run_id}")
        else:
            # Find all stuck backup runs
            stuck_runs = db.query(BackupRun).filter(
                BackupRun.status == BackupStatus.RUNNING
            ).all()
            
            if not stuck_runs:
                logger.info("No stuck backup runs found")
                return
            
            logger.info(f"Found {len(stuck_runs)} stuck backup run(s)")
            for run in stuck_runs:
                logger.info(f"  - Backup run {run.id} for job {run.job_id} (started: {run.started_at})")
            
            if len(stuck_runs) > 1:
                logger.info("Multiple stuck runs found. Please specify backup_run_id to recover a specific one.")
                return
            
            backup_run = stuck_runs[0]
            backup_run_id = backup_run.id
        
        # Check if there's a corresponding snapshot (indicates backup completed)
        snapshot = db.query(Snapshot).filter(
            Snapshot.backup_run_id == backup_run_id
        ).first()
        
        if snapshot:
            logger.info(f"Found snapshot for backup run {backup_run_id} - backup appears to have completed")
            logger.info(f"  Snapshot ID: {snapshot.snapshot_id}")
            logger.info(f"  Size: {snapshot.size_bytes:,} bytes ({snapshot.size_bytes / (1024**3):.2f} GB)")
            logger.info(f"  Files: {snapshot.files_count:,}")
            
            # Update backup run to match snapshot
            backup_run.status = BackupStatus.SUCCESS
            backup_run.completed_at = snapshot.created_at or datetime.utcnow()
            if backup_run.started_at:
                backup_run.duration_seconds = (
                    backup_run.completed_at - backup_run.started_at
                ).total_seconds()
            backup_run.snapshot_id = snapshot.snapshot_id
            backup_run.size_bytes = snapshot.size_bytes
            backup_run.files_count = snapshot.files_count
            backup_run.s3_key = snapshot.s3_key
            backup_run.storage_class = snapshot.storage_class
            backup_run.error_message = None
            
            db.commit()
            logger.info(f"✓ Recovered backup run {backup_run_id} - marked as SUCCESS")
        else:
            # No snapshot - backup likely failed or was interrupted
            logger.warning(f"No snapshot found for backup run {backup_run_id}")
            logger.warning("This backup may have failed. Marking as FAILED.")
            
            backup_run.status = BackupStatus.FAILED
            backup_run.completed_at = datetime.utcnow()
            if backup_run.started_at:
                backup_run.duration_seconds = (
                    backup_run.completed_at - backup_run.started_at
                ).total_seconds()
            backup_run.error_message = "Backup was interrupted (database error during commit)"
            
            db.commit()
            logger.info(f"✓ Marked backup run {backup_run_id} as FAILED")
    
    except Exception as e:
        logger.error(f"Error recovering backup: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix database schema and recover stuck backups")
    parser.add_argument("--fix-schema", action="store_true", help="Fix database schema (INTEGER -> BIGINT)")
    parser.add_argument("--recover", type=int, metavar="BACKUP_RUN_ID", 
                       help="Recover specific backup run (or omit to find all stuck runs)")
    parser.add_argument("--all", action="store_true", help="Fix schema and recover all stuck backups")
    
    args = parser.parse_args()
    
    if args.all or args.fix_schema:
        fix_database_schema()
    
    if args.all or args.recover is not None:
        recover_stuck_backup(args.recover)
    
    if not (args.all or args.fix_schema or args.recover is not None):
        parser.print_help()
