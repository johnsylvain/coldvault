"""
Restore API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import math

from app.database import get_db, Job, Snapshot, StorageClass
from app.restore import restore_worker
from app.aws import s3_client

router = APIRouter()

class SnapshotResponse(BaseModel):
    id: int
    job_id: int
    backup_run_id: int | None
    snapshot_id: str
    created_at: str
    size_bytes: int | None
    files_count: int | None
    s3_key: str
    storage_class: str | None
    retained: bool
    
    class Config:
        from_attributes = True

class RestoreRequest(BaseModel):
    snapshot_id: str
    restore_path: str
    file_paths: Optional[List[str]] = None  # None means restore entire snapshot

@router.get("/jobs/{job_id}/snapshots", response_model=List[SnapshotResponse])
def list_snapshots(job_id: int, db: Session = Depends(get_db)):
    """List all snapshots for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    snapshots = db.query(Snapshot).filter(
        Snapshot.job_id == job_id,
        Snapshot.retained == True
    ).order_by(Snapshot.created_at.desc()).all()
    
    result = []
    for snapshot in snapshots:
        snapshot_dict = {
            **{k: v for k, v in snapshot.__dict__.items() if not k.startswith('_')},
            'created_at': snapshot.created_at.isoformat() if snapshot.created_at else None,
            'storage_class': snapshot.storage_class.value if snapshot.storage_class else None,
        }
        result.append(SnapshotResponse(**snapshot_dict))
    return result

@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(snapshot_id: str, db: Session = Depends(get_db)):
    """Get details of a specific snapshot"""
    snapshot = db.query(Snapshot).filter(Snapshot.snapshot_id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    snapshot_dict = {
        **{k: v for k, v in snapshot.__dict__.items() if not k.startswith('_')},
        'created_at': snapshot.created_at.isoformat() if snapshot.created_at else None,
        'storage_class': snapshot.storage_class.value if snapshot.storage_class else None,
    }
    return SnapshotResponse(**snapshot_dict)

@router.post("/restore")
def restore_snapshot(restore_req: RestoreRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Initiate a restore operation"""
    snapshot = db.query(Snapshot).filter(Snapshot.snapshot_id == restore_req.snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    # Check if Glacier retrieval is needed
    job = db.query(Job).filter(Job.id == snapshot.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Queue restore in background
    background_tasks.add_task(
        restore_worker.restore_snapshot,
        snapshot.id,
        restore_req.restore_path,
        restore_req.file_paths
    )
    
    return {
        "message": "Restore initiated",
        "snapshot_id": restore_req.snapshot_id,
        "restore_path": restore_req.restore_path,
        "note": "If snapshot is in Glacier, retrieval may take time"
    }

@router.get("/restore/status/{restore_id}")
def get_restore_status(restore_id: str):
    """Get status of a restore operation"""
    # TODO: Implement restore status tracking
    return {"status": "not_implemented"}

@router.get("/estimate")
def estimate_restore(
    snapshot_id: str,
    file_paths: Optional[str] = None,  # Comma-separated or newline-separated
    db: Session = Depends(get_db)
):
    """Estimate restore cost and time for a snapshot"""
    snapshot = db.query(Snapshot).filter(Snapshot.snapshot_id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    job = db.query(Job).filter(Job.id == snapshot.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Parse file paths if provided
    parsed_file_paths = None
    if file_paths:
        # Support both comma and newline separated
        parsed_file_paths = [p.strip() for p in file_paths.replace('\n', ',').split(',') if p.strip()]
    
    # Calculate data size to restore
    if parsed_file_paths:
        # For partial restore, we'd need to check manifest
        # For now, estimate based on average file size
        total_size = snapshot.size_bytes or 0
        # Rough estimate: assume files are evenly distributed
        estimated_size = total_size * (len(parsed_file_paths) / max(snapshot.files_count or 1, 1))
    else:
        estimated_size = snapshot.size_bytes or 0
    
    # Calculate costs based on storage class and restore tier
    costs = calculate_restore_costs(estimated_size, snapshot.storage_class, "Expedited")
    
    # Calculate time estimates
    time_estimates = calculate_restore_time(estimated_size, snapshot.storage_class, "Expedited")
    
    # Check if Glacier restore is needed
    needs_glacier_restore = snapshot.storage_class and "GLACIER" in snapshot.storage_class.value
    
    # Check current restore status if in Glacier
    restore_status = None
    if needs_glacier_restore:
        restore_status = s3_client.check_restore_status(job.s3_bucket, snapshot.s3_key)
    
    return {
        "snapshot_id": snapshot_id,
        "snapshot_size_bytes": snapshot.size_bytes,
        "estimated_restore_size_bytes": estimated_size,
        "files_count": snapshot.files_count,
        "estimated_files_to_restore": len(parsed_file_paths) if parsed_file_paths else snapshot.files_count,
        "storage_class": snapshot.storage_class.value if snapshot.storage_class else None,
        "needs_glacier_restore": needs_glacier_restore,
        "restore_status": restore_status,
        "costs": costs,
        "time_estimates": time_estimates
    }

def calculate_restore_costs(size_bytes: int, storage_class: StorageClass, tier: str) -> dict:
    """Calculate restore costs based on AWS pricing"""
    size_gb = size_bytes / (1024**3)
    
    # AWS Glacier restore pricing (per GB)
    # Expedited: $0.03/GB
    # Standard: $0.01/GB (3-5 hours)
    # Bulk: $0.0025/GB (5-12 hours)
    restore_pricing = {
        "Expedited": 0.03,
        "Standard": 0.01,
        "Bulk": 0.0025
    }
    
    # Data retrieval costs (per GB)
    retrieval_pricing = {
        "GLACIER_IR": 0.01,  # $0.01/GB
        "GLACIER_FLEXIBLE": 0.01,  # $0.01/GB
        "DEEP_ARCHIVE": 0.02,  # $0.02/GB
    }
    
    costs = {}
    
    if storage_class and "GLACIER" in storage_class.value:
        restore_cost_per_gb = restore_pricing.get(tier, 0.01)
        retrieval_cost_per_gb = retrieval_pricing.get(storage_class.value, 0.01)
        
        restore_cost = size_gb * restore_cost_per_gb
        retrieval_cost = size_gb * retrieval_cost_per_gb
        total_cost = restore_cost + retrieval_cost
        
        costs = {
            "restore_request_cost": round(restore_cost, 4),
            "data_retrieval_cost": round(retrieval_cost, 4),
            "total_cost": round(total_cost, 4),
            "tier": tier,
            "note": f"Costs for {tier} tier restore. Standard/Bulk tiers are cheaper but slower."
        }
    else:
        # Standard storage - no restore cost
        costs = {
            "restore_request_cost": 0,
            "data_retrieval_cost": 0,
            "total_cost": 0,
            "tier": None,
            "note": "No restore cost for standard storage"
        }
    
    return costs

def calculate_restore_time(size_bytes: int, storage_class: StorageClass, tier: str) -> dict:
    """Calculate estimated restore time"""
    size_gb = size_bytes / (1024**3)
    
    # Glacier restore time estimates (in hours)
    glacier_restore_times = {
        "Expedited": 1,  # 1-5 minutes typically
        "Standard": 3,  # 3-5 hours
        "Bulk": 5  # 5-12 hours
    }
    
    # Download time estimate (assuming 100 Mbps = 12.5 MB/s)
    download_speed_mbps = 100
    download_speed_mb_per_sec = download_speed_mbps / 8
    download_time_hours = (size_bytes / (1024**2)) / download_speed_mb_per_sec / 3600
    
    time_estimates = {}
    
    if storage_class and "GLACIER" in storage_class.value:
        glacier_wait_hours = glacier_restore_times.get(tier, 5)
        total_hours = glacier_wait_hours + download_time_hours
        
        time_estimates = {
            "glacier_restore_wait_hours": glacier_wait_hours,
            "download_time_hours": round(download_time_hours, 2),
            "total_estimated_hours": round(total_hours, 2),
            "tier": tier,
            "note": f"Glacier restore wait time for {tier} tier, plus download time"
        }
    else:
        # Standard storage - just download time
        time_estimates = {
            "glacier_restore_wait_hours": 0,
            "download_time_hours": round(download_time_hours, 2),
            "total_estimated_hours": round(download_time_hours, 2),
            "tier": None,
            "note": "No Glacier restore wait time needed"
        }
    
    return time_estimates
