"""
Job scheduler using APScheduler
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
from typing import Dict

from app.database import SessionLocal, Job
from app.worker import backup_worker

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.job_mapping: Dict[int, str] = {}  # job_id -> scheduler_job_id
    
    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        logger.info("Scheduler started")
        
        # Load existing jobs
        self._load_jobs()
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def _load_jobs(self):
        """Load all enabled jobs from database"""
        db = SessionLocal()
        try:
            jobs = db.query(Job).filter(Job.enabled == True).all()
            for job in jobs:
                self.add_job(job)
        except Exception as e:
            logger.error(f"Error loading jobs: {e}")
        finally:
            db.close()
    
    def add_job(self, job: Job):
        """Add a job to the scheduler"""
        if not job.enabled:
            return
        
        # Remove existing job if present
        if job.id in self.job_mapping:
            self.remove_job(job.id)
        
        try:
            # Parse schedule
            trigger = self._parse_schedule(job.schedule)
            
            # Add to scheduler
            scheduler_job_id = f"job_{job.id}"
            self.scheduler.add_job(
                self._run_backup,
                trigger=trigger,
                id=scheduler_job_id,
                args=[job.id],
                replace_existing=True,
                next_run_time=None  # Will be calculated by trigger
            )
            
            self.job_mapping[job.id] = scheduler_job_id
            logger.info(f"Added job {job.id} ({job.name}) to scheduler with schedule: {job.schedule}")
        except Exception as e:
            logger.error(f"Failed to add job {job.id} to scheduler: {e}")
    
    def update_job(self, job: Job):
        """Update a scheduled job"""
        if job.enabled:
            self.add_job(job)
        else:
            self.remove_job(job.id)
    
    def remove_job(self, job_id: int):
        """Remove a job from the scheduler"""
        if job_id in self.job_mapping:
            scheduler_job_id = self.job_mapping[job_id]
            try:
                self.scheduler.remove_job(scheduler_job_id)
                del self.job_mapping[job_id]
                logger.info(f"Removed job {job_id} from scheduler")
            except Exception as e:
                logger.error(f"Failed to remove job {job_id} from scheduler: {e}")
    
    def _parse_schedule(self, schedule: str):
        """Parse cron-like schedule string into APScheduler trigger"""
        schedule = schedule.strip()
        
        # Handle preset schedules
        presets = {
            "hourly": "0 * * * *",
            "daily": "0 0 * * *",
            "weekly": "0 0 * * 0",
            "monthly": "0 0 1 * *"
        }
        
        if schedule.lower() in presets:
            schedule = presets[schedule.lower()]
        
        # Parse cron expression (minute hour day month day_of_week)
        parts = schedule.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )
        elif len(parts) == 1 and schedule.startswith("@every_"):
            # Interval format: @every_1h, @every_30m, etc.
            interval_str = schedule.replace("@every_", "")
            if interval_str.endswith("m"):
                minutes = int(interval_str[:-1])
                return IntervalTrigger(minutes=minutes)
            elif interval_str.endswith("h"):
                hours = int(interval_str[:-1])
                return IntervalTrigger(hours=hours)
            elif interval_str.endswith("d"):
                days = int(interval_str[:-1])
                return IntervalTrigger(days=days)
        
        # Default to daily if parsing fails
        logger.warning(f"Could not parse schedule '{schedule}', defaulting to daily")
        return CronTrigger(hour=0, minute=0)
    
    def _run_backup(self, job_id: int):
        """Execute a backup job"""
        try:
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job or not job.enabled:
                    return
            finally:
                db.close()
            
            logger.info(f"Triggering scheduled backup for job {job_id} ({job.name})")
            backup_worker.execute_backup(job_id, None)
        except Exception as e:
            logger.error(f"Error triggering backup for job {job_id}: {e}")
    
    def get_next_run_time(self, job_id: int) -> datetime | None:
        """Get next scheduled run time for a job"""
        if job_id not in self.job_mapping:
            return None
        
        scheduler_job_id = self.job_mapping[job_id]
        job = self.scheduler.get_job(scheduler_job_id)
        if job:
            return job.next_run_time
        return None

scheduler = JobScheduler()
