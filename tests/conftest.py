"""
Pytest configuration and fixtures
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

# Set test environment variables before importing app modules
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database import Base, get_db
from app.main import app
from app.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Test settings with in-memory database"""
    return Settings(
        database_url="sqlite:///:memory:",
        aws_access_key_id="test_key",
        aws_secret_access_key="test_secret",
        aws_region="us-east-1",
        aws_s3_bucket="test-bucket",
        encryption_key="test-encryption-key-32-chars-long!!",
        config_path=tempfile.mkdtemp(),
        cache_path=tempfile.mkdtemp(),
    )


@pytest.fixture(scope="function")
def db_session(test_settings):
    """Create a fresh database session for each test"""
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override"""
    # Mock scheduler and worker to avoid starting background processes in tests
    with patch('app.main.scheduler') as mock_scheduler, \
         patch('app.api.backups.backup_worker') as mock_worker:
        mock_scheduler.start = Mock()
        mock_scheduler.stop = Mock()
        mock_scheduler.add_job = Mock()
        mock_scheduler.update_job = Mock()
        mock_scheduler.remove_job = Mock()
        
        mock_worker.execute_backup = Mock()
        mock_worker.cancel_backup = Mock(return_value=False)
        mock_worker.running_backups = {}
        mock_worker._recover_orphaned_backups = Mock()
        
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            yield test_client
        
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="function")
def mock_s3_client():
    """Mock S3 client for testing"""
    with patch('app.aws.s3_client') as mock_client:
        mock_client.client = MagicMock()
        mock_client.upload_file = Mock()
        mock_client.download_file = Mock()
        mock_client.object_exists = Mock(return_value=True)
        mock_client.get_object_info = Mock(return_value={
            'exists': True,
            'size': 1024,
            'storage_class': 'DEEP_ARCHIVE',
            'last_modified': None,
            'etag': 'test-etag'
        })
        mock_client.list_objects = Mock(return_value=[])
        mock_client.initiate_restore = Mock()
        mock_client.check_restore_status = Mock(return_value=None)
        yield mock_client


@pytest.fixture(scope="function")
def sample_job_data():
    """Sample job data for testing"""
    return {
        "name": "test-job",
        "job_type": "dataset",
        "description": "Test backup job",
        "source_paths": ["/test/path"],
        "schedule": "0 0 * * *",
        "enabled": True,
        "s3_bucket": "test-bucket",
        "s3_prefix": "backups/test",
        "storage_class": "DEEP_ARCHIVE",
        "keep_last_n": 30,
        "gfs_daily": 7,
        "gfs_weekly": 4,
        "gfs_monthly": 12,
        "encryption_enabled": True,
        "incremental_enabled": True,
    }


@pytest.fixture(scope="function")
def sample_job(db_session, sample_job_data):
    """Create a sample job in the database"""
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
        keep_last_n=sample_job_data["keep_last_n"],
        gfs_daily=sample_job_data["gfs_daily"],
        gfs_weekly=sample_job_data["gfs_weekly"],
        gfs_monthly=sample_job_data["gfs_monthly"],
        encryption_enabled=sample_job_data["encryption_enabled"],
        incremental_enabled=sample_job_data["incremental_enabled"],
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job
