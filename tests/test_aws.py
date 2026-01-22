"""
Tests for AWS S3 integration
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from botocore.exceptions import ClientError
from app.aws import S3Client


class TestS3Client:
    """Test S3Client class"""
    
    @pytest.fixture
    def mock_boto3_client(self):
        """Mock boto3 S3 client"""
        with patch('boto3.client') as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            yield mock_s3
    
    @pytest.fixture
    def s3_client_instance(self, mock_boto3_client):
        """Create S3Client instance with mocked boto3"""
        with patch('app.aws.settings') as mock_settings:
            mock_settings.aws_access_key_id = "test_key"
            mock_settings.aws_secret_access_key = "test_secret"
            mock_settings.aws_region = "us-east-1"
            client = S3Client()
            client.client = mock_boto3_client
            return client
    
    def test_upload_file_success(self, s3_client_instance, temp_dir, mock_boto3_client):
        """Test successful file upload"""
        import os
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        
        s3_client_instance.upload_file(
            test_file,
            "test-bucket",
            "test-key",
            "DEEP_ARCHIVE"
        )
        
        # Verify upload_fileobj was called
        mock_boto3_client.upload_fileobj.assert_called_once()
        mock_boto3_client.head_object.assert_called_once()
    
    def test_upload_file_not_found(self, s3_client_instance):
        """Test upload fails when file doesn't exist"""
        with pytest.raises(FileNotFoundError):
            s3_client_instance.upload_file(
                "/nonexistent/file.txt",
                "test-bucket",
                "test-key"
            )
    
    def test_upload_file_client_not_initialized(self):
        """Test upload fails when client not initialized"""
        client = S3Client()
        client.client = None
        
        with pytest.raises(Exception, match="S3 client not initialized"):
            client.upload_file(
                "/some/file.txt",
                "test-bucket",
                "test-key"
            )
    
    def test_download_file_success(self, s3_client_instance, temp_dir, mock_boto3_client):
        """Test successful file download"""
        import os
        download_path = os.path.join(temp_dir, "downloaded.txt")
        
        s3_client_instance.download_file(
            "test-bucket",
            "test-key",
            download_path
        )
        
        mock_boto3_client.download_file.assert_called_once_with(
            "test-bucket",
            "test-key",
            download_path
        )
    
    def test_download_file_client_error(self, s3_client_instance, temp_dir, mock_boto3_client):
        """Test download handles client errors"""
        import os
        error_response = {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}}
        mock_boto3_client.download_file.side_effect = ClientError(error_response, 'HeadObject')
        
        download_path = os.path.join(temp_dir, "downloaded.txt")
        with pytest.raises(Exception):
            s3_client_instance.download_file(
                "test-bucket",
                "test-key",
                download_path
            )
    
    def test_object_exists_true(self, s3_client_instance, mock_boto3_client):
        """Test object_exists returns True when object exists"""
        mock_boto3_client.head_object.return_value = {}
        
        result = s3_client_instance.object_exists("test-bucket", "test-key")
        assert result is True
    
    def test_object_exists_false(self, s3_client_instance, mock_boto3_client):
        """Test object_exists returns False for 404"""
        error_response = {'Error': {'Code': '404'}}
        mock_boto3_client.head_object.side_effect = ClientError(error_response, 'HeadObject')
        
        result = s3_client_instance.object_exists("test-bucket", "test-key")
        assert result is False
    
    def test_object_exists_client_not_initialized(self):
        """Test object_exists returns False when client not initialized"""
        client = S3Client()
        client.client = None
        
        result = client.object_exists("test-bucket", "test-key")
        assert result is False
    
    def test_get_object_info_success(self, s3_client_instance, mock_boto3_client):
        """Test getting object info successfully"""
        from datetime import datetime
        mock_boto3_client.head_object.return_value = {
            'ContentLength': 1024,
            'StorageClass': 'DEEP_ARCHIVE',
            'LastModified': datetime.utcnow(),
            'ETag': '"test-etag"'
        }
        
        info = s3_client_instance.get_object_info("test-bucket", "test-key")
        
        assert info is not None
        assert info['exists'] is True
        assert info['size'] == 1024
        assert info['storage_class'] == 'DEEP_ARCHIVE'
    
    def test_get_object_info_not_found(self, s3_client_instance, mock_boto3_client):
        """Test getting object info for non-existent object"""
        error_response = {'Error': {'Code': '404'}}
        mock_boto3_client.head_object.side_effect = ClientError(error_response, 'HeadObject')
        
        info = s3_client_instance.get_object_info("test-bucket", "test-key")
        
        assert info is not None
        assert info['exists'] is False
    
    def test_list_objects_success(self, s3_client_instance, mock_boto3_client):
        """Test listing objects successfully"""
        from datetime import datetime
        mock_boto3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test-key-1',
                    'Size': 1024,
                    'LastModified': datetime.utcnow(),
                    'StorageClass': 'DEEP_ARCHIVE'
                },
                {
                    'Key': 'test-key-2',
                    'Size': 2048,
                    'LastModified': datetime.utcnow(),
                    'StorageClass': 'STANDARD'
                }
            ]
        }
        
        objects = s3_client_instance.list_objects("test-bucket", "prefix/")
        
        assert len(objects) == 2
        assert objects[0]['key'] == 'test-key-1'
        assert objects[0]['size'] == 1024
    
    def test_list_objects_empty(self, s3_client_instance, mock_boto3_client):
        """Test listing objects when bucket is empty"""
        mock_boto3_client.list_objects_v2.return_value = {'Contents': []}
        
        objects = s3_client_instance.list_objects("test-bucket")
        
        assert objects == []
    
    def test_initiate_restore(self, s3_client_instance, mock_boto3_client):
        """Test initiating a restore request"""
        mock_boto3_client.restore_object.return_value = {}
        
        response = s3_client_instance.initiate_restore(
            "test-bucket",
            "test-key",
            "Expedited"
        )
        
        mock_boto3_client.restore_object.assert_called_once()
        assert response is not None
    
    def test_check_restore_status_in_progress(self, s3_client_instance, mock_boto3_client):
        """Test checking restore status when in progress"""
        mock_boto3_client.head_object.return_value = {
            'Restore': 'ongoing-request="true"'
        }
        
        status = s3_client_instance.check_restore_status("test-bucket", "test-key")
        assert status == "in_progress"
    
    def test_check_restore_status_ready(self, s3_client_instance, mock_boto3_client):
        """Test checking restore status when ready"""
        mock_boto3_client.head_object.return_value = {
            'Restore': 'ongoing-request="false"'
        }
        
        status = s3_client_instance.check_restore_status("test-bucket", "test-key")
        assert status == "ready"
    
    def test_check_restore_status_none(self, s3_client_instance, mock_boto3_client):
        """Test checking restore status when no restore"""
        mock_boto3_client.head_object.return_value = {}
        
        status = s3_client_instance.check_restore_status("test-bucket", "test-key")
        assert status is None
