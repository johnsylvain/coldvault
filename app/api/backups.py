"""
Backup execution API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db, Job, BackupRun, BackupStatus
from app.worker import backup_worker

router = APIRouter()

class BackupRunResponse(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    snapshot_id: str | None
    size_bytes: int | None
    files_count: int | None
    s3_key: str | None
    storage_class: str | None
    error_message: str | None
    log_path: str | None
    manual_trigger: bool
    
    class Config:
        from_attributes = True

@router.post("/{job_id}/run")
def trigger_backup(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger a backup for a job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Create backup run record
    backup_run = BackupRun(
        job_id=job_id,
        status=BackupStatus.PENDING,
        manual_trigger=True
    )
    db.add(backup_run)
    db.commit()
    db.refresh(backup_run)
    
    # Queue backup in background
    background_tasks.add_task(backup_worker.execute_backup, job_id, backup_run.id)
    
    return {
        "message": "Backup triggered",
        "backup_run_id": backup_run.id,
        "status": "pending"
    }

@router.get("/runs", response_model=List[BackupRunResponse])
def list_backup_runs(job_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    """List backup runs, optionally filtered by job"""
    query = db.query(BackupRun)
    if job_id:
        query = query.filter(BackupRun.job_id == job_id)
    runs = query.order_by(BackupRun.started_at.desc()).limit(limit).all()
    
    result = []
    for run in runs:
        run_dict = {
            **{k: v for k, v in run.__dict__.items() if not k.startswith('_')},
            'status': run.status.value if run.status else None,
            'storage_class': run.storage_class.value if run.storage_class else None,
        }
        result.append(BackupRunResponse(**run_dict))
    return result

@router.get("/runs/{run_id}", response_model=BackupRunResponse)
def get_backup_run(run_id: int, db: Session = Depends(get_db)):
    """Get details of a specific backup run"""
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    
    run_dict = {
        **{k: v for k, v in run.__dict__.items() if not k.startswith('_')},
        'status': run.status.value if run.status else None,
        'storage_class': run.storage_class.value if run.storage_class else None,
    }
    return BackupRunResponse(**run_dict)

@router.post("/runs/{run_id}/cancel")
def cancel_backup(run_id: int, db: Session = Depends(get_db)):
    """Cancel a running backup"""
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    
    if run.status not in [BackupStatus.PENDING, BackupStatus.RUNNING]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel backup with status: {run.status.value}"
        )
    
    # Check if backup is actually running (in worker's memory)
    if run.job_id not in backup_worker.running_backups:
        # Backup is marked as RUNNING in DB but not actually running (orphaned)
        # Mark it as failed/cancelled
        run.status = BackupStatus.CANCELLED
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
        run.error_message = "Backup was cancelled (not actually running - likely server restart)"
        
        # Update job status
        job = db.query(Job).filter(Job.id == run.job_id).first()
        if job:
            job.last_run_status = BackupStatus.CANCELLED
        
        db.commit()
        
        return {
            "message": "Backup marked as cancelled (was orphaned - not actually running)",
            "backup_run_id": run_id,
            "status": "cancelled"
        }
    
    # Request cancellation for actually running backup
    cancelled = backup_worker.cancel_backup(run.job_id)
    
    if cancelled:
        return {
            "message": "Cancellation requested",
            "backup_run_id": run_id,
            "status": "cancelling"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Backup is not currently running"
        )

@router.get("/runs/{run_id}/log")
def get_backup_log(run_id: int, tail: int = 100, db: Session = Depends(get_db)):
    """Get log content for a backup run
    
    Args:
        run_id: Backup run ID
        tail: Number of lines to return from the end (default: 100, use 0 for all)
    """
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    
    if not run.log_path:
        return {"log": "No log available", "lines": []}
    
    try:
        with open(run.log_path, 'r') as f:
            lines = f.readlines()
            
        if tail > 0 and len(lines) > tail:
            lines = lines[-tail:]
        
        return {
            "log": "".join(lines),
            "lines": [line.rstrip() for line in lines],
            "total_lines": len(lines),
            "log_path": run.log_path
        }
    except FileNotFoundError:
        return {"log": "Log file not found", "lines": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log: {str(e)}")

@router.get("/runs/{run_id}/verify")
def verify_backup_upload(run_id: int, db: Session = Depends(get_db)):
    """Verify that a backup was successfully uploaded to S3"""
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    
    if not run.s3_key:
        return {
            "verified": False,
            "message": "No S3 key recorded for this backup run"
        }
    
    job = db.query(Job).filter(Job.id == run.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    from app.aws import s3_client
    
    # Check if object exists
    exists = s3_client.object_exists(job.s3_bucket, run.s3_key)
    
    if not exists:
        return {
            "verified": False,
            "message": f"Object not found in S3: s3://{job.s3_bucket}/{run.s3_key}",
            "bucket": job.s3_bucket,
            "key": run.s3_key
        }
    
    # Get object details
    info = s3_client.get_object_info(job.s3_bucket, run.s3_key)
    
    return {
        "verified": True,
        "message": "Backup successfully verified in S3",
        "bucket": job.s3_bucket,
        "key": run.s3_key,
        "object_info": info
    }

@router.get("/runs/{run_id}/log/stream")
def stream_backup_log(run_id: int, db: Session = Depends(get_db)):
    """Stream log content for a running backup (Server-Sent Events)"""
    from fastapi.responses import StreamingResponse
    
    run = db.query(BackupRun).filter(BackupRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    
    if not run.log_path:
        raise HTTPException(status_code=404, detail="No log available")
    
    def generate():
        import time
        last_position = 0
        
        while True:
            try:
                with open(run.log_path, 'r') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    if new_content:
                        yield f"data: {new_content}\n\n"
                        last_position = f.tell()
                
                # Check if backup is still running
                db.refresh(run)
                if run.status not in [BackupStatus.RUNNING, BackupStatus.PENDING]:
                    yield f"data: [BACKUP_COMPLETE]\n\n"
                    break
                
                time.sleep(1)  # Poll every second
            except FileNotFoundError:
                yield f"data: [LOG_FILE_NOT_FOUND]\n\n"
                break
            except Exception as e:
                yield f"data: [ERROR: {str(e)}]\n\n"
                break
    
    return StreamingResponse(generate(), media_type="text/event-stream")
