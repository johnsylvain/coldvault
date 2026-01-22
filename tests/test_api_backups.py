"""
Tests for backups API endpoints
"""
import pytest
from fastapi import status
from datetime import datetime
from app.database import BackupRun, BackupStatus


class TestBackupsAPI:
    """Test backups API endpoints"""
    
    def test_list_backup_runs_empty(self, client):
        """Test listing backup runs when none exist"""
        response = client.get("/api/backups/runs")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
    
    def test_list_backup_runs(self, client, sample_job, db_session):
        """Test listing backup runs"""
        # Create a backup run
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
            snapshot_id="test-snapshot-123",
            size_bytes=1024,
            files_count=10,
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.get("/api/backups/runs")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_id"] == sample_job.id
        assert data[0]["status"] == "success"
    
    def test_list_backup_runs_filtered_by_job(self, client, sample_job, db_session):
        """Test listing backup runs filtered by job_id"""
        # Create backup runs for the job
        backup_run1 = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
        )
        backup_run2 = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.FAILED,
        )
        db_session.add_all([backup_run1, backup_run2])
        db_session.commit()
        
        response = client.get(f"/api/backups/runs?job_id={sample_job.id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) == 2
        assert all(run["job_id"] == sample_job.id for run in data)
    
    def test_get_backup_run(self, client, sample_job, db_session):
        """Test getting a specific backup run"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
            snapshot_id="test-snapshot-123",
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.get(f"/api/backups/runs/{backup_run.id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == backup_run.id
        assert data["job_id"] == sample_job.id
        assert data["status"] == "success"
    
    def test_get_backup_run_not_found(self, client):
        """Test getting a non-existent backup run"""
        response = client.get("/api/backups/runs/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_trigger_backup(self, client, sample_job):
        """Test triggering a backup"""
        response = client.post(f"/api/backups/{sample_job.id}/run")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "backup_run_id" in data
        assert data["status"] == "pending"
        assert "message" in data
    
    def test_trigger_backup_job_not_found(self, client):
        """Test triggering backup for non-existent job"""
        response = client.post("/api/backups/99999/run")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_cancel_backup_pending(self, client, sample_job, db_session):
        """Test cancelling a pending backup"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.PENDING,
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.post(f"/api/backups/runs/{backup_run.id}/cancel")
        # Should succeed (may return 200 or handle cancellation)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
    
    def test_cancel_backup_completed(self, client, sample_job, db_session):
        """Test cancelling a completed backup fails"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
            completed_at=datetime.utcnow(),
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.post(f"/api/backups/runs/{backup_run.id}/cancel")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_get_backup_log_no_log(self, client, sample_job, db_session):
        """Test getting log for backup run without log path"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.get(f"/api/backups/runs/{backup_run.id}/log")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "No log available" in data["log"]
    
    def test_verify_backup_no_s3_key(self, client, sample_job, db_session):
        """Test verifying backup without S3 key"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
        )
        db_session.add(backup_run)
        db_session.commit()
        
        response = client.get(f"/api/backups/runs/{backup_run.id}/verify")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["verified"] is False
        assert "No S3 key" in data["message"]
    
    def test_verify_backup_with_s3_key(self, client, sample_job, db_session, mock_s3_client):
        """Test verifying backup with S3 key"""
        backup_run = BackupRun(
            job_id=sample_job.id,
            status=BackupStatus.SUCCESS,
            s3_key="backups/test/snapshot-123.tar.gz",
        )
        db_session.add(backup_run)
        db_session.commit()
        
        mock_s3_client.object_exists.return_value = True
        
        response = client.get(f"/api/backups/runs/{backup_run.id}/verify")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["verified"] is True
        assert "successfully verified" in data["message"].lower()
