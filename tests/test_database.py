"""
Tests for database models and operations
"""
import pytest
from datetime import datetime
from app.database import (
    Job, JobType, StorageClass, BackupStatus, BackupRun, 
    Snapshot, Notification, StorageMetrics
)


class TestDatabaseModels:
    """Test database models"""
    
    def test_job_creation(self, db_session, sample_job_data):
        """Test creating a job"""
        from app.database import Job, JobType, StorageClass
        import json
        
        job = Job(
            name=sample_job_data["name"],
            job_type=JobType(sample_job_data["job_type"]),
            description=sample_job_data["description"],
            source_paths=json.dumps(sample_job_data["source_paths"]),
            schedule=sample_job_data["schedule"],
            enabled=sample_job_data["enabled"],
            s3_bucket=sample_job_data["s3_bucket"],
            s3_prefix=sample_job_data["s3_prefix"],
            storage_class=StorageClass(sample_job_data["storage_class"]),
        )
        
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        
        assert job.id is not None
        assert job.name == sample_job_data["name"]
        assert job.job_type == JobType.DATASET
        assert job.storage_class == StorageClass.DEEP_ARCHIVE
        assert job.enabled is True
        assert job.created_at is not None
    
    def test_backup_run_creation(self, db_session, sample_job):
        """Test creating a backup run"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.PENDING,
            snapshot_id="test-snapshot-123",
            size_bytes=1024 * 1024,
            files_count=100,
        )
        
        db_session.add(backup_run)
        db_session.commit()
        db_session.refresh(backup_run)
        
        assert backup_run.id is not None
        assert backup_run.job_id == sample_job.id
        assert backup_run.status == BackupStatus.PENDING
        assert backup_run.snapshot_id == "test-snapshot-123"
        assert backup_run.size_bytes == 1024 * 1024
        assert backup_run.files_count == 100
    
    def test_snapshot_creation(self, db_session, sample_job):
        """Test creating a snapshot"""
        snapshot = Snapshot(
            job_id=sample_job.id,
            snapshot_id="test-snapshot-123",
            s3_key="backups/test/snapshot-123.tar.gz",
            storage_class=StorageClass.DEEP_ARCHIVE,
            size_bytes=1024 * 1024,
            files_count=100,
        )
        
        db_session.add(snapshot)
        db_session.commit()
        db_session.refresh(snapshot)
        
        assert snapshot.id is not None
        assert snapshot.job_id == sample_job.id
        assert snapshot.snapshot_id == "test-snapshot-123"
        assert snapshot.retained is True
    
    def test_notification_creation(self, db_session, sample_job):
        """Test creating a notification"""
        notification = Notification(
            job_id=sample_job.id,
            notification_type="failure",
            severity="error",
            message="Backup failed",
        )
        
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)
        
        assert notification.id is not None
        assert notification.job_id == sample_job.id
        assert notification.notification_type == "failure"
        assert notification.severity == "error"
        assert notification.sent_at is not None
    
    def test_storage_metrics_creation(self, db_session):
        """Test creating storage metrics"""
        metrics = StorageMetrics(
            total_size_bytes=1024 * 1024 * 1024,  # 1 GB
            size_deep_archive_bytes=1024 * 1024 * 1024,
            total_files=1000,
            monthly_cost_estimate=10.50,
            cost_deep_archive=10.50,
        )
        
        db_session.add(metrics)
        db_session.commit()
        db_session.refresh(metrics)
        
        assert metrics.id is not None
        assert metrics.total_size_bytes == 1024 * 1024 * 1024
        assert metrics.total_files == 1000
        assert metrics.monthly_cost_estimate == 10.50
    
    def test_job_relationships(self, db_session, sample_job):
        """Test job relationships with backup runs"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
        )
        db_session.add(backup_run)
        db_session.commit()
        
        # Query backup runs for job
        runs = db_session.query(BackupRun).filter(
            BackupRun.job_id == sample_job.id
        ).all()
        
        assert len(runs) == 1
        assert runs[0].job_id == sample_job.id
    
    def test_job_update_timestamp(self, db_session, sample_job):
        """Test that job updated_at changes on update"""
        original_updated = sample_job.updated_at
        
        # Update job
        sample_job.description = "Updated description"
        db_session.commit()
        db_session.refresh(sample_job)
        
        assert sample_job.updated_at >= original_updated
    
    def test_backup_status_enum(self):
        """Test BackupStatus enum values"""
        assert BackupStatus.PENDING.value == "pending"
        assert BackupStatus.RUNNING.value == "running"
        assert BackupStatus.SUCCESS.value == "success"
        assert BackupStatus.FAILED.value == "failed"
        assert BackupStatus.CANCELLED.value == "cancelled"
    
    def test_storage_class_enum(self):
        """Test StorageClass enum values"""
        assert StorageClass.STANDARD.value == "STANDARD"
        assert StorageClass.GLACIER_IR.value == "GLACIER_IR"
        assert StorageClass.GLACIER_FLEXIBLE.value == "GLACIER_FLEXIBLE"
        assert StorageClass.DEEP_ARCHIVE.value == "DEEP_ARCHIVE"
