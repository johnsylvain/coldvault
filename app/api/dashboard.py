"""
Dashboard API endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any

from app.database import get_db, Job, BackupRun, Snapshot, BackupStatus, StorageClass

router = APIRouter()

def calculate_projected_completion(job_id: int, current_run_id: int, db: Session) -> str | None:
    """Calculate projected completion time for a running backup based on historical data"""
    # Get current running backup run
    current_run = db.query(BackupRun).filter(BackupRun.id == current_run_id).first()
    if not current_run or not current_run.started_at:
        return None
    
    # Get average duration from successful historical runs (last 10, excluding current)
    historical_runs = db.query(BackupRun).filter(
        BackupRun.job_id == job_id,
        BackupRun.status == BackupStatus.SUCCESS,
        BackupRun.duration_seconds.isnot(None),
        BackupRun.id != current_run_id
    ).order_by(BackupRun.started_at.desc()).limit(10).all()
    
    if historical_runs:
        avg_duration = sum(r.duration_seconds for r in historical_runs) / len(historical_runs)
        projected_completion_at = current_run.started_at.replace(tzinfo=None) + timedelta(seconds=avg_duration)
        return projected_completion_at.isoformat()
    else:
        # If no historical data, estimate based on elapsed time (assume 50% progress)
        elapsed = (datetime.utcnow() - current_run.started_at).total_seconds()
        if elapsed > 0:
            projected_completion = elapsed * 2
            projected_completion_at = current_run.started_at.replace(tzinfo=None) + timedelta(seconds=projected_completion)
            return projected_completion_at.isoformat()
    
    return None

@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """Get dashboard overview statistics"""
    # Job statistics
    total_jobs = db.query(Job).count()
    enabled_jobs = db.query(Job).filter(Job.enabled == True).count()
    
    # Backup run statistics
    total_runs = db.query(BackupRun).count()
    successful_runs = db.query(BackupRun).filter(BackupRun.status == BackupStatus.SUCCESS).count()
    failed_runs = db.query(BackupRun).filter(BackupRun.status == BackupStatus.FAILED).count()
    
    # Recent activity
    recent_runs = db.query(BackupRun).order_by(BackupRun.started_at.desc()).limit(10).all()
    
    # Storage statistics
    total_size = db.query(func.sum(Snapshot.size_bytes)).scalar() or 0
    
    # Cost estimation (rough estimates)
    cost_estimates = estimate_costs(db)
    
    return {
        "jobs": {
            "total": total_jobs,
            "enabled": enabled_jobs,
            "disabled": total_jobs - enabled_jobs
        },
        "backups": {
            "total": total_runs,
            "successful": successful_runs,
            "failed": failed_runs,
            "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0
        },
        "storage": {
            "total_bytes": total_size,
            "total_gb": round(total_size / (1024**3), 2),
            "total_tb": round(total_size / (1024**4), 2)
        },
        "costs": cost_estimates,
        "recent_activity": [
            {
                "id": run.id,
                "job_id": run.job_id,
                "status": run.status.value if run.status else None,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "duration_seconds": run.duration_seconds,
                "elapsed_seconds": (datetime.utcnow() - run.started_at).total_seconds() if run.status == BackupStatus.RUNNING and run.started_at else None,
                "projected_completion_at": calculate_projected_completion(run.job_id, run.id, db) if run.status == BackupStatus.RUNNING else None
            }
            for run in recent_runs
        ]
    }

@router.get("/jobs/{job_id}/stats")
def get_job_stats(job_id: int, db: Session = Depends(get_db)):
    """Get statistics for a specific job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return {"error": "Job not found"}
    
    # Backup runs
    total_runs = db.query(BackupRun).filter(BackupRun.job_id == job_id).count()
    successful_runs = db.query(BackupRun).filter(
        BackupRun.job_id == job_id,
        BackupRun.status == BackupStatus.SUCCESS
    ).count()
    
    # Snapshots
    snapshots = db.query(Snapshot).filter(Snapshot.job_id == job_id).all()
    total_size = sum(s.size_bytes or 0 for s in snapshots)
    
    # Last run
    last_run = db.query(BackupRun).filter(
        BackupRun.job_id == job_id
    ).order_by(BackupRun.started_at.desc()).first()
    
    return {
        "job_id": job_id,
        "job_name": job.name,
        "backups": {
            "total": total_runs,
            "successful": successful_runs,
            "failed": total_runs - successful_runs
        },
        "snapshots": {
            "count": len(snapshots),
            "total_size_bytes": total_size,
            "total_size_gb": round(total_size / (1024**3), 2)
        },
        "last_run": {
            "id": last_run.id if last_run else None,
            "status": last_run.status.value if last_run and last_run.status else None,
            "started_at": last_run.started_at.isoformat() if last_run and last_run.started_at else None,
            "duration_seconds": last_run.duration_seconds if last_run else None
        },
        "next_run": job.next_run_at.isoformat() if job.next_run_at else None
    }

def estimate_costs(db: Session) -> Dict[str, Any]:
    """Estimate monthly storage costs based on AWS Glacier pricing"""
    # Rough pricing (as of 2024, adjust as needed)
    # Prices per GB per month
    pricing = {
        StorageClass.GLACIER_IR: 0.004,  # $0.004/GB
        StorageClass.GLACIER_FLEXIBLE: 0.0036,  # $0.0036/GB
        StorageClass.DEEP_ARCHIVE: 0.00099,  # $0.00099/GB
        StorageClass.STANDARD: 0.023,  # $0.023/GB
    }
    
    # Get size by storage class
    size_by_class = {}
    for storage_class in StorageClass:
        total = db.query(func.sum(Snapshot.size_bytes)).filter(
            Snapshot.storage_class == storage_class
        ).scalar() or 0
        # Convert to float to avoid Decimal issues
        size_by_class[storage_class.value] = float(total) / (1024**3)  # Convert to GB
    
    # Calculate costs
    monthly_cost = 0.0
    cost_breakdown = {}
    for storage_class, price_per_gb in pricing.items():
        gb = size_by_class.get(storage_class.value, 0.0)
        cost = float(gb) * float(price_per_gb)  # Ensure both are floats
        monthly_cost += cost
        cost_breakdown[storage_class.value] = {
            "size_gb": round(gb, 2),
            "monthly_cost": round(cost, 2)
        }
    
    return {
        "monthly_estimate": round(monthly_cost, 2),
        "breakdown": cost_breakdown,
        "note": "Estimates based on standard AWS pricing. Actual costs may vary."
    }
