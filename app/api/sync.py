"""
API endpoints for sync and reconciliation
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.sync import sync_worker
from app.database import SessionLocal, Job

router = APIRouter()


@router.post("/jobs/{job_id}/sync")
def sync_job(job_id: int, dry_run: bool = Query(True, description="If true, only report issues without fixing")):
    """
    Synchronize a job's database state with S3 storage
    
    This checks for:
    - Missing backup files in S3
    - Orphaned files in S3 not tracked in database
    - Mismatched file sizes
    - Missing or corrupted manifests
    
    Use dry_run=true first to see what would be fixed, then dry_run=false to apply fixes.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        result = sync_worker.sync_job(job_id, dry_run=dry_run)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        db.close()


@router.get("/jobs/{job_id}/sync")
def get_sync_status(job_id: int):
    """
    Get sync status for a job (dry run only, no changes made)
    """
    return sync_job(job_id, dry_run=True)
