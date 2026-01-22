"""
Tests for jobs API endpoints
"""
import pytest
from fastapi import status
from app.database import Job, JobType, StorageClass, BackupStatus


class TestJobsAPI:
    """Test jobs API endpoints"""
    
    def test_list_jobs_empty(self, client):
        """Test listing jobs when none exist"""
        response = client.get("/api/jobs/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
    
    def test_create_job(self, client, sample_job_data):
        """Test creating a new job"""
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_201_CREATED
        
        data = response.json()
        assert data["name"] == sample_job_data["name"]
        assert data["job_type"] == sample_job_data["job_type"]
        assert data["s3_bucket"] == sample_job_data["s3_bucket"]
        assert data["id"] is not None
    
    def test_create_job_duplicate_name(self, client, sample_job_data):
        """Test creating a job with duplicate name fails"""
        # Create first job
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_201_CREATED
        
        # Try to create another with same name
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_get_job(self, client, sample_job):
        """Test getting a specific job"""
        response = client.get(f"/api/jobs/{sample_job.id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == sample_job.id
        assert data["name"] == sample_job.name
    
    def test_get_job_not_found(self, client):
        """Test getting a non-existent job"""
        response = client.get("/api/jobs/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_list_jobs(self, client, sample_job):
        """Test listing all jobs"""
        response = client.get("/api/jobs/")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_job.id
    
    def test_update_job(self, client, sample_job):
        """Test updating a job"""
        update_data = {
            "description": "Updated description",
            "enabled": False,
        }
        
        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["enabled"] is False
    
    def test_update_job_not_found(self, client):
        """Test updating a non-existent job"""
        update_data = {"description": "Updated"}
        response = client.put("/api/jobs/99999", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_job(self, client, sample_job):
        """Test deleting a job"""
        response = client.delete(f"/api/jobs/{sample_job.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify job is deleted
        response = client.get(f"/api/jobs/{sample_job.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_job_not_found(self, client):
        """Test deleting a non-existent job"""
        response = client.delete("/api/jobs/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_create_job_invalid_job_type(self, client, sample_job_data):
        """Test creating job with invalid job type"""
        sample_job_data["job_type"] = "invalid_type"
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_job_invalid_storage_class(self, client, sample_job_data):
        """Test creating job with invalid storage class"""
        sample_job_data["storage_class"] = "INVALID_CLASS"
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_update_job_invalid_storage_class(self, client, sample_job):
        """Test updating job with invalid storage class"""
        update_data = {"storage_class": "INVALID_CLASS"}
        response = client.put(f"/api/jobs/{sample_job.id}", json=update_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_job_source_paths_serialization(self, client, sample_job_data):
        """Test that source_paths are properly serialized/deserialized"""
        sample_job_data["source_paths"] = ["/path1", "/path2", "/path3"]
        response = client.post("/api/jobs/", json=sample_job_data)
        assert response.status_code == status.HTTP_201_CREATED
        
        data = response.json()
        assert data["source_paths"] == ["/path1", "/path2", "/path3"]
        
        # Verify it's stored correctly
        job_id = data["id"]
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["source_paths"] == ["/path1", "/path2", "/path3"]
