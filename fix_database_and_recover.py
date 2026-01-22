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
from sqlalchemy import text
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
    
    with engine.begin() as conn:
        try:
            # Alter backup_runs.size_bytes
            conn.execute(text("""
                ALTER TABLE backup_runs 
                ALTER COLUMN size_bytes TYPE BIGINT;
            """))
            logger.info("✓ Fixed backup_runs.size_bytes")
            
            # Alter snapshots.size_bytes
            conn.execute(text("""
                ALTER TABLE snapshots 
                ALTER COLUMN size_bytes TYPE BIGINT;
            """))
            logger.info("✓ Fixed snapshots.size_bytes")
            
            logger.info("Database schema fixed successfully!")
        except Exception as e:
            logger.error(f"Error fixing schema: {e}")
            error_msg = str(e).lower()
            if "already" in error_msg or "does not exist" in error_msg:
                logger.info("Columns may already be BIGINT or table structure is different")
            else:
                logger.info("This might be okay if columns are already BIGINT")
            raise  # Re-raise to trigger rollback

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
            
            logger.info(f"Found backup run {backup_run_id} (status: {backup_run.status.value})")
            
            # Check if there's a snapshot even if status is not RUNNING
            snapshot = db.query(Snapshot).filter(
                Snapshot.backup_run_id == backup_run_id
            ).first()
            
            if snapshot and backup_run.status != BackupStatus.SUCCESS:
                logger.info(f"Found snapshot for backup run {backup_run_id} but status is {backup_run.status.value}")
                logger.info("This backup likely completed but failed to update status. Recovering...")
            elif backup_run.status != BackupStatus.RUNNING:
                logger.info(f"Backup run {backup_run_id} is not in RUNNING status (current: {backup_run.status.value})")
                if not snapshot:
                    logger.info("No snapshot found - backup may have actually failed")
                    return
        else:
            # Find all stuck backup runs (RUNNING status)
            stuck_runs = db.query(BackupRun).filter(
                BackupRun.status == BackupStatus.RUNNING
            ).all()
            
            # Also check for runs with snapshots but wrong status (failed due to DB error)
            # Use explicit join condition for SQLAlchemy 2.0+
            runs_with_snapshots = db.query(BackupRun).join(
                Snapshot, BackupRun.id == Snapshot.backup_run_id
            ).filter(
                BackupRun.status != BackupStatus.SUCCESS
            ).all()
            
            all_runs_to_recover = list(set(stuck_runs + runs_with_snapshots))
            
            if not all_runs_to_recover:
                logger.info("No stuck backup runs found")
                logger.info("Checking for backup runs that may need recovery...")
                # List recent backup runs
                recent_runs = db.query(BackupRun).order_by(BackupRun.id.desc()).limit(5).all()
                if recent_runs:
                    logger.info("Recent backup runs:")
                    for run in recent_runs:
                        snapshot_count = db.query(Snapshot).filter(
                            Snapshot.backup_run_id == run.id
                        ).count()
                        logger.info(f"  - ID: {run.id}, Status: {run.status.value}, Job: {run.job_id}, Snapshots: {snapshot_count}")
                return
            
            logger.info(f"Found {len(all_runs_to_recover)} backup run(s) that may need recovery")
            for run in all_runs_to_recover:
                snapshot_count = db.query(Snapshot).filter(
                    Snapshot.backup_run_id == run.id
                ).count()
                logger.info(f"  - Backup run {run.id} for job {run.job_id} (status: {run.status.value}, snapshots: {snapshot_count})")
            
            if len(all_runs_to_recover) > 1:
                logger.info("Multiple runs found. Please specify backup_run_id to recover a specific one.")
                logger.info("Or run with --recover <id> for each one.")
                return
            
            backup_run = all_runs_to_recover[0]
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
