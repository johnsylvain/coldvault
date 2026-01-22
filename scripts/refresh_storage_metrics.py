#!/usr/bin/env python3
"""
Refresh storage metrics from database snapshots
"""
import sys
import os

# Add parent directory to path so we can import app
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from app.database import SessionLocal, Snapshot, StorageMetrics
from app.metrics import metrics_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Refresh storage metrics"""
    db = SessionLocal()
    try:
        # Check current snapshots
        all_snapshots = db.query(Snapshot).all()
        retained_snapshots = db.query(Snapshot).filter(Snapshot.retained == True).all()
        
        logger.info(f"Total snapshots: {len(all_snapshots)}")
        logger.info(f"Retained snapshots: {len(retained_snapshots)}")
        
        # Calculate total from all snapshots
        total_size_all = sum(s.size_bytes or 0 for s in all_snapshots)
        total_size_retained = sum(s.size_bytes or 0 for s in retained_snapshots)
        
        logger.info(f"Total size (all snapshots): {total_size_all / (1024**3):.2f} GB")
        logger.info(f"Total size (retained only): {total_size_retained / (1024**3):.2f} GB")
        
        # Show breakdown by job
        from app.database import Job
        jobs = db.query(Job).all()
        logger.info("\nBreakdown by job:")
        for job in jobs:
            job_snapshots = db.query(Snapshot).filter(
                Snapshot.job_id == job.id,
                Snapshot.retained == True
            ).all()
            job_size = sum(s.size_bytes or 0 for s in job_snapshots)
            job_files = sum(s.files_count or 0 for s in job_snapshots)
            logger.info(f"  {job.name}: {job_size / (1024**3):.2f} GB, {job_files:,} files, {len(job_snapshots)} snapshots")
        
        # Record metrics
        logger.info("\nRecording metrics...")
        metrics = metrics_service.record_daily_metrics(db)
        
        logger.info(f"\n✓ Metrics recorded:")
        logger.info(f"  Total size: {metrics.total_size_bytes / (1024**3):.2f} GB")
        logger.info(f"  Total files: {metrics.total_files:,}")
        logger.info(f"  Monthly cost: ${metrics.monthly_cost_estimate:.2f}")
        logger.info(f"  Recorded at: {metrics.recorded_at}")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main()
