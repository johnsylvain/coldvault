"""
Job management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import json

from app.database import get_db, Job, JobType, StorageClass, BackupStatus, BackupRun
from app.scheduler import scheduler

router = APIRouter()

class JobCreate(BaseModel):
    name: str
    job_type: str
    description: Optional[str] = None
    source_paths: List[str]
    schedule: str
    enabled: bool = True
    s3_bucket: str
    s3_prefix: str
    storage_class: str = "DEEP_ARCHIVE"
    keep_last_n: int = 30
    gfs_daily: int = 7
    gfs_weekly: int = 4
    gfs_monthly: int = 12
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    bandwidth_limit: Optional[int] = None
    cpu_priority: int = 5
    encryption_enabled: bool = True
    incremental_enabled: bool = True  # Use incremental backups by default

class JobUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_paths: Optional[List[str]] = None
    schedule: Optional[str] = None
    enabled: Optional[bool] = None
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    storage_class: Optional[str] = None
    keep_last_n: Optional[int] = None
    gfs_daily: Optional[int] = None
    gfs_weekly: Optional[int] = None
    gfs_monthly: Optional[int] = None
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    bandwidth_limit: Optional[int] = None
    cpu_priority: Optional[int] = None
    encryption_enabled: Optional[bool] = None
    incremental_enabled: Optional[bool] = None

class JobResponse(BaseModel):
    id: int
    name: str
    job_type: str
    description: Optional[str]
    source_paths: List[str]
    schedule: str
    enabled: bool
    s3_bucket: str
    s3_prefix: str
    storage_class: str
    keep_last_n: int
    gfs_daily: int
    gfs_weekly: int
    gfs_monthly: int
    include_patterns: Optional[List[str]]
    exclude_patterns: Optional[List[str]]
    bandwidth_limit: Optional[int]
    cpu_priority: int
    encryption_enabled: bool
    incremental_enabled: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    next_run_at: Optional[datetime]
    current_run_elapsed_seconds: Optional[float] = None
    projected_completion_seconds: Optional[float] = None
    projected_completion_at: Optional[str] = None
    current_run_started_at: Optional[str] = None
    
    class Config:
        from_attributes = True

def calculate_projected_time(job_id: int, db: Session) -> dict:
    """Calculate projected completion time for a running job based on historical data"""
    from datetime import datetime
    from sqlalchemy import func
    
    # Get current running backup run
    current_run = db.query(BackupRun).filter(
        BackupRun.job_id == job_id,
        BackupRun.status == BackupStatus.RUNNING
    ).order_by(BackupRun.started_at.desc()).first()
    
    if not current_run or not current_run.started_at:
        return {
            'elapsed_seconds': None,
            'projected_completion_seconds': None,
            'projected_completion_at': None
        }
    
    # Calculate elapsed time (ensure it's always positive to handle edge cases)
    elapsed = max(0, (datetime.utcnow() - current_run.started_at).total_seconds())
    
    # Get average duration from successful historical runs (last 10)
    historical_runs = db.query(BackupRun).filter(
        BackupRun.job_id == job_id,
        BackupRun.status == BackupStatus.SUCCESS,
        BackupRun.duration_seconds.isnot(None)
    ).order_by(BackupRun.started_at.desc()).limit(10).all()
    
    if historical_runs:
        avg_duration = sum(r.duration_seconds for r in historical_runs) / len(historical_runs)
        projected_completion = avg_duration
        projected_completion_at = current_run.started_at.replace(tzinfo=None) + timedelta(seconds=projected_completion)
    else:
        # If no historical data, estimate based on elapsed time (assume 50% progress)
        projected_completion = elapsed * 2 if elapsed > 0 else None
        projected_completion_at = current_run.started_at.replace(tzinfo=None) + timedelta(seconds=projected_completion) if projected_completion else None
    
    return {
        'elapsed_seconds': elapsed,
        'projected_completion_seconds': projected_completion,
        'projected_completion_at': projected_completion_at.isoformat() if projected_completion_at else None
    }

@router.get("/", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """List all backup jobs"""
    import logging
    from datetime import datetime, timedelta
    logger = logging.getLogger(__name__)
    
    jobs = db.query(Job).all()
    logger.info(f"list_jobs: Found {len(jobs)} jobs in database: {[(j.id, j.name) for j in jobs]}")
    result = []
    for job in jobs:
        job_dict = {
            **{k: v for k, v in job.__dict__.items() if not k.startswith('_')},
            'source_paths': json.loads(job.source_paths),
            'job_type': job.job_type.value,
            'storage_class': job.storage_class.value if job.storage_class else None,
            'last_run_status': job.last_run_status.value if job.last_run_status else None,
        'include_patterns': json.loads(job.include_patterns) if job.include_patterns else None,
        'exclude_patterns': json.loads(job.exclude_patterns) if job.exclude_patterns else None,
        'incremental_enabled': job.incremental_enabled if hasattr(job, 'incremental_enabled') else True,
    }
        
        # Add runtime and projection for running jobs
        if job.last_run_status == BackupStatus.RUNNING:
            projection = calculate_projected_time(job.id, db)
            job_dict['current_run_elapsed_seconds'] = projection['elapsed_seconds']
            job_dict['projected_completion_seconds'] = projection['projected_completion_seconds']
            job_dict['projected_completion_at'] = projection['projected_completion_at']
            
            # Get current run start time
            current_run = db.query(BackupRun).filter(
                BackupRun.job_id == job.id,
                BackupRun.status == BackupStatus.RUNNING
            ).order_by(BackupRun.started_at.desc()).first()
            if current_run:
                job_dict['current_run_started_at'] = current_run.started_at.isoformat() if current_run.started_at else None
        else:
            job_dict['current_run_elapsed_seconds'] = None
            job_dict['projected_completion_seconds'] = None
            job_dict['projected_completion_at'] = None
            job_dict['current_run_started_at'] = None
        
        result.append(JobResponse(**job_dict))
    return result

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dict = {
        **{k: v for k, v in job.__dict__.items() if not k.startswith('_')},
        'source_paths': json.loads(job.source_paths),
        'job_type': job.job_type.value,
        'storage_class': job.storage_class.value if job.storage_class else None,
        'last_run_status': job.last_run_status.value if job.last_run_status else None,
        'include_patterns': json.loads(job.include_patterns) if job.include_patterns else None,
        'exclude_patterns': json.loads(job.exclude_patterns) if job.exclude_patterns else None,
    }
    return JobResponse(**job_dict)

@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new backup job"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"create_job: Starting creation of job '{job_data.name}'")
    
    # Count existing jobs before creation
    existing_count = db.query(Job).count()
    logger.info(f"create_job: Current job count in DB: {existing_count}")
    
    # Validate job type
    try:
        job_type = JobType(job_data.job_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid job_type: {job_data.job_type}")
    
    # Validate storage class
    try:
        storage_class = StorageClass(job_data.storage_class)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid storage_class: {job_data.storage_class}")
    
    # Check if job name already exists
    existing = db.query(Job).filter(Job.name == job_data.name).first()
    if existing:
        logger.warning(f"create_job: Job name '{job_data.name}' already exists")
        raise HTTPException(status_code=400, detail="Job name already exists")
    
    # List all existing jobs before creation
    all_jobs_before = db.query(Job).all()
    logger.info(f"create_job: Existing jobs before creation: {[j.id for j in all_jobs_before]}")
    
    # Create job
    job = Job(
        name=job_data.name,
        job_type=job_type,
        description=job_data.description,
        source_paths=json.dumps(job_data.source_paths),
        schedule=job_data.schedule,
        enabled=job_data.enabled,
        s3_bucket=job_data.s3_bucket,
        s3_prefix=job_data.s3_prefix,
        storage_class=storage_class,
        keep_last_n=job_data.keep_last_n,
        gfs_daily=job_data.gfs_daily,
        gfs_weekly=job_data.gfs_weekly,
        gfs_monthly=job_data.gfs_monthly,
        include_patterns=json.dumps(job_data.include_patterns) if job_data.include_patterns else None,
        exclude_patterns=json.dumps(job_data.exclude_patterns) if job_data.exclude_patterns else None,
        bandwidth_limit=job_data.bandwidth_limit,
        cpu_priority=job_data.cpu_priority,
        encryption_enabled=job_data.encryption_enabled,
        incremental_enabled=getattr(job_data, 'incremental_enabled', True),  # Default to True
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    logger.info(f"create_job: Created job with ID {job.id}")
    
    # Count jobs after creation
    jobs_after = db.query(Job).count()
    logger.info(f"create_job: Job count after creation: {jobs_after}")
    
    # List all jobs after creation
    all_jobs_after = db.query(Job).all()
    logger.info(f"create_job: All jobs after creation: {[(j.id, j.name) for j in all_jobs_after]}")
    
    # Schedule the job
    if job.enabled:
        scheduler.add_job(job)
    
    job_dict = {
        **{k: v for k, v in job.__dict__.items() if not k.startswith('_')},
        'source_paths': json.loads(job.source_paths),
        'job_type': job.job_type.value,
        'storage_class': job.storage_class.value if job.storage_class else None,
        'last_run_status': job.last_run_status.value if job.last_run_status else None,
        'include_patterns': json.loads(job.include_patterns) if job.include_patterns else None,
        'exclude_patterns': json.loads(job.exclude_patterns) if job.exclude_patterns else None,
    }
    return JobResponse(**job_dict)

@router.put("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, job_data: JobUpdate, db: Session = Depends(get_db)):
    """Update a backup job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update fields
    if job_data.name is not None:
        job.name = job_data.name
    if job_data.description is not None:
        job.description = job_data.description
    if job_data.source_paths is not None:
        job.source_paths = json.dumps(job_data.source_paths)
    if job_data.schedule is not None:
        job.schedule = job_data.schedule
    if job_data.enabled is not None:
        job.enabled = job_data.enabled
    if job_data.s3_bucket is not None:
        job.s3_bucket = job_data.s3_bucket
    if job_data.s3_prefix is not None:
        job.s3_prefix = job_data.s3_prefix
    if job_data.storage_class is not None:
        try:
            job.storage_class = StorageClass(job_data.storage_class)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid storage_class: {job_data.storage_class}")
    if job_data.keep_last_n is not None:
        job.keep_last_n = job_data.keep_last_n
    if job_data.gfs_daily is not None:
        job.gfs_daily = job_data.gfs_daily
    if job_data.gfs_weekly is not None:
        job.gfs_weekly = job_data.gfs_weekly
    if job_data.gfs_monthly is not None:
        job.gfs_monthly = job_data.gfs_monthly
    if job_data.include_patterns is not None:
        job.include_patterns = json.dumps(job_data.include_patterns)
    if job_data.exclude_patterns is not None:
        job.exclude_patterns = json.dumps(job_data.exclude_patterns)
    if job_data.bandwidth_limit is not None:
        job.bandwidth_limit = job_data.bandwidth_limit
    if job_data.cpu_priority is not None:
        job.cpu_priority = job_data.cpu_priority
    if job_data.encryption_enabled is not None:
        job.encryption_enabled = job_data.encryption_enabled
    if job_data.incremental_enabled is not None:
        job.incremental_enabled = job_data.incremental_enabled
    
    job.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(job)
    
    # Update scheduler
    scheduler.update_job(job)
    
    job_dict = {
        **{k: v for k, v in job.__dict__.items() if not k.startswith('_')},
        'source_paths': json.loads(job.source_paths),
        'job_type': job.job_type.value,
        'storage_class': job.storage_class.value if job.storage_class else None,
        'last_run_status': job.last_run_status.value if job.last_run_status else None,
        'include_patterns': json.loads(job.include_patterns) if job.include_patterns else None,
        'exclude_patterns': json.loads(job.exclude_patterns) if job.exclude_patterns else None,
    }
    return JobResponse(**job_dict)

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Delete a backup job"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Remove from scheduler
    scheduler.remove_job(job_id)
    
    db.delete(job)
    db.commit()
    return None
