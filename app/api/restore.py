"""
Restore API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db, Job, Snapshot
from app.restore import restore_worker

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
