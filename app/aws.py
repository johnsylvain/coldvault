"""
AWS S3 integration
"""
import os
import boto3
import logging
from typing import Optional, Dict, List
from botocore.exceptions import ClientError
from botocore.config import Config

from app.config import settings
from app.retry_utils import (
    retry_with_backoff,
    is_retryable_error,
    RetryContext,
    exponential_backoff
)

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        self.client = None
        self.multipart_uploads: Dict[str, str] = {}  # Track multipart upload IDs
        self._initialize()
    
    def _get_client_config(self) -> Config:
        """Get boto3 client configuration with timeouts and retries"""
        return Config(
            connect_timeout=settings.s3_connect_timeout,
            read_timeout=settings.s3_read_timeout,
            retries={
                'max_attempts': 0,  # We handle retries ourselves
                'mode': 'standard'
            }
        )
    
    def _initialize(self):
        """Initialize S3 client with custom configuration"""
        try:
            config = self._get_client_config()
            
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                self.client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region,
                    config=config
                )
                logger.info(
                    f"S3 client initialized with credentials for region {settings.aws_region} "
                    f"(connect_timeout={settings.s3_connect_timeout}s, read_timeout={settings.s3_read_timeout}s)"
                )
            else:
                # Use default credentials (IAM role, etc.)
                self.client = boto3.client('s3', region_name=settings.aws_region, config=config)
                logger.info(
                    f"S3 client initialized with default credentials for region {settings.aws_region} "
                    f"(connect_timeout={settings.s3_connect_timeout}s, read_timeout={settings.s3_read_timeout}s)"
                )
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.client = None
    
    def check_connection(self) -> bool:
        """Check if S3 connection is healthy"""
        if not self.client:
            return False
        
        try:
            # Try a simple operation (list buckets with limit 1)
            self.client.list_buckets()
            return True
        except Exception as e:
            logger.warning(f"S3 connection check failed: {e}")
            # Try to reinitialize
            try:
                self._initialize()
                if self.client:
                    self.client.list_buckets()
                    return True
            except Exception:
                pass
            return False
    
    def _cleanup_multipart_uploads(self, bucket: str, key: str):
        """Clean up any orphaned multipart uploads for a key"""
        try:
            upload_id = self.multipart_uploads.get(f"{bucket}/{key}")
            if upload_id:
                # List all parts and abort
                try:
                    parts = self.client.list_parts(Bucket=bucket, Key=key, UploadId=upload_id)
                    if parts.get('Parts'):
                        self.client.abort_multipart_upload(
                            Bucket=bucket, Key=key, UploadId=upload_id
                        )
                        logger.info(f"Cleaned up multipart upload {upload_id} for {key}")
                except ClientError:
                    pass  # Upload may already be cleaned up
                finally:
                    del self.multipart_uploads[f"{bucket}/{key}"]
        except Exception as e:
            logger.warning(f"Error cleaning up multipart upload: {e}")
    
    def upload_file(self, local_path: str, bucket: str, key: str, storage_class: str = "DEEP_ARCHIVE"):
        """Upload file to S3 with specified storage class (with retry logic)"""
        return self.upload_file_with_retry(local_path, bucket, key, storage_class)
    
    def upload_file_with_retry(
        self, 
        local_path: str, 
        bucket: str, 
        key: str, 
        storage_class: str = "DEEP_ARCHIVE",
        max_retries: Optional[int] = None
    ):
        """
        Upload file to S3 with retry logic and exponential backoff.
        
        Args:
            local_path: Path to local file
            bucket: S3 bucket name
            key: S3 object key
            storage_class: S3 storage class
            max_retries: Override default max retries from settings
        """
        if not self.client:
            # Try to reinitialize on first attempt
            self._initialize()
            if not self.client:
                raise Exception("S3 client not initialized. Check AWS credentials.")
        
        # Verify file exists
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Backup file not found: {local_path}")
        
        file_size = os.path.getsize(local_path)
        logger.info(f"Uploading {file_size / (1024**2):.2f} MB to s3://{bucket}/{key}")
        
        max_retries = max_retries or settings.s3_upload_max_retries
        extra_args = {'StorageClass': storage_class}
        
        # Use retry context for upload attempts
        with RetryContext(
            max_retries=max_retries,
            base_delay=settings.s3_upload_retry_backoff_base,
            max_delay=settings.s3_upload_retry_backoff_max,
            on_retry=lambda e, attempt, delay: logger.warning(
                f"Upload retry {attempt}/{max_retries + 1} for {key} after {delay:.2f}s: {e}"
            )
        ) as retry:
            for attempt in retry:
                try:
                    # Check connection health before retry
                    if attempt > 0 and not self.check_connection():
                        logger.warning("S3 connection unhealthy, reinitializing...")
                        self._initialize()
                        if not self.client:
                            raise Exception("Failed to reinitialize S3 client")
                    
                    # Use upload_fileobj with progress callback for large files
                    from boto3.s3.transfer import TransferConfig
                    
                    # Configure multipart upload using settings
                    config = TransferConfig(
                        multipart_threshold=settings.s3_multipart_threshold,
                        max_concurrency=10,
                        multipart_chunksize=settings.s3_multipart_chunksize,
                        use_threads=True
                    )
                    
                    # Upload with progress tracking
                    uploaded_bytes = [0]  # Use list to allow modification in nested function
                    total_bytes = file_size
                    last_logged = [0]
                    
                    def upload_progress(bytes_amount):
                        uploaded_bytes[0] += bytes_amount
                        # Log every 10MB or at completion
                        if uploaded_bytes[0] - last_logged[0] >= 10 * 1024 * 1024 or uploaded_bytes[0] >= total_bytes:
                            percent = (uploaded_bytes[0] / total_bytes) * 100 if total_bytes > 0 else 0
                            logger.info(
                                f"📤 Upload progress: {uploaded_bytes[0] / (1024**2):.2f} MB / "
                                f"{total_bytes / (1024**2):.2f} MB ({percent:.1f}%)"
                            )
                            last_logged[0] = uploaded_bytes[0]
                    
                    with open(local_path, 'rb') as f:
                        self.client.upload_fileobj(
                            f,
                            bucket,
                            key,
                            ExtraArgs=extra_args,
                            Config=config,
                            Callback=upload_progress
                        )
                    
                    logger.info(f"Successfully uploaded to s3://{bucket}/{key} with storage class {storage_class}")
                    
                    # Clean up any tracked multipart uploads
                    self._cleanup_multipart_uploads(bucket, key)
                    
                    # Verify upload
                    try:
                        response = self.client.head_object(Bucket=bucket, Key=key)
                        uploaded_size = response.get('ContentLength', 0)
                        actual_storage_class = response.get('StorageClass', storage_class)
                        logger.info(
                            f"Upload verified: {uploaded_size} bytes, storage class: {actual_storage_class}"
                        )
                        
                        if uploaded_size != file_size:
                            logger.warning(
                                f"Size mismatch: uploaded {uploaded_size} bytes, expected {file_size} bytes"
                            )
                    except ClientError as e:
                        logger.warning(f"Could not verify upload: {e}")
                    
                    # Success - break out of retry loop
                    return
                    
                except Exception as e:
                    # Check if error is retryable
                    if not retry.should_retry(e):
                        # Non-retryable error - clean up and raise
                        self._cleanup_multipart_uploads(bucket, key)
                        error_code = 'Unknown'
                        error_msg = str(e)
                        if isinstance(e, ClientError):
                            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                            error_msg = e.response.get('Error', {}).get('Message', str(e))
                        logger.error(f"Non-retryable error uploading to S3: {error_code} - {error_msg}")
                        raise Exception(f"S3 upload failed: {error_code} - {error_msg}")
                    
                    # Retryable error - wait and retry
                    retry.wait(e)
            
            # If we get here, all retries exhausted
            self._cleanup_multipart_uploads(bucket, key)
            raise Exception(f"S3 upload failed after {max_retries + 1} attempts")
    
    def download_file(self, bucket: str, key: str, local_path: str):
        """Download file from S3"""
        if not self.client:
            raise Exception("S3 client not initialized")
        
        try:
            self.client.download_file(bucket, key, local_path)
            logger.info(f"Downloaded s3://{bucket}/{key} to {local_path}")
        except ClientError as e:
            logger.error(f"Failed to download from S3: {e}")
            raise
    
    def initiate_restore(self, bucket: str, key: str, tier: str = "Expedited"):
        """Initiate Glacier restore request"""
        if not self.client:
            raise Exception("S3 client not initialized")
        
        try:
            response = self.client.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    'Days': 7,
                    'GlacierJobParameters': {
                        'Tier': tier
                    }
                }
            )
            logger.info(f"Initiated restore for s3://{bucket}/{key}")
            return response
        except ClientError as e:
            logger.error(f"Failed to initiate restore: {e}")
            raise
    
    def check_restore_status(self, bucket: str, key: str) -> Optional[str]:
        """Check restore status of an object"""
        if not self.client:
            raise Exception("S3 client not initialized")
        
        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
            restore_status = response.get('Restore')
            if restore_status:
                if 'ongoing-request="true"' in restore_status:
                    return "in_progress"
                elif 'ongoing-request="false"' in restore_status:
                    return "ready"
            return None
        except ClientError as e:
            logger.error(f"Failed to check restore status: {e}")
            return None
    
    def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an object exists in S3"""
        if not self.client:
            return False
        
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            logger.error(f"Error checking object existence: {e}")
            return False
    
    def get_object_info(self, bucket: str, key: str) -> Optional[dict]:
        """Get information about an S3 object"""
        if not self.client:
            return None
        
        try:
            response = self.client.head_object(Bucket=bucket, Key=key)
            return {
                'exists': True,
                'size': response.get('ContentLength', 0),
                'storage_class': response.get('StorageClass', 'STANDARD'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"')
            }
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return {'exists': False}
            logger.error(f"Error getting object info: {e}")
            return None
    
    def list_objects(self, bucket: str, prefix: str = "", limit: int = 100) -> list:
        """List objects in S3 bucket with given prefix"""
        if not self.client:
            return []
        
        try:
            response = self.client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=limit
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })
            
            return objects
        except ClientError as e:
            logger.error(f"Error listing objects: {e}")
            return []

s3_client = S3Client()
