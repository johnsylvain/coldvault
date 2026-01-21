"""
AWS S3 integration
"""
import os
import boto3
import logging
from typing import Optional
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        self.client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize S3 client"""
        try:
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                self.client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
                logger.info(f"S3 client initialized with credentials for region {settings.aws_region}")
            else:
                # Use default credentials (IAM role, etc.)
                self.client = boto3.client('s3', region_name=settings.aws_region)
                logger.info(f"S3 client initialized with default credentials for region {settings.aws_region}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.client = None
    
    def upload_file(self, local_path: str, bucket: str, key: str, storage_class: str = "DEEP_ARCHIVE"):
        """Upload file to S3 with specified storage class"""
        if not self.client:
            raise Exception("S3 client not initialized. Check AWS credentials.")
        
        # Verify file exists
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Backup file not found: {local_path}")
        
        file_size = os.path.getsize(local_path)
        logger.info(f"Uploading {file_size / (1024**2):.2f} MB to s3://{bucket}/{key}")
        
        extra_args = {
            'StorageClass': storage_class
        }
        
        try:
            # Use upload_fileobj with progress callback for large files
            from boto3.s3.transfer import TransferConfig
            
            # Configure multipart upload for large files (>8MB)
            config = TransferConfig(
                multipart_threshold=8 * 1024 * 1024,  # 8MB
                max_concurrency=10,
                multipart_chunksize=8 * 1024 * 1024,  # 8MB chunks
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
                    logger.info(f"📤 Upload progress: {uploaded_bytes[0] / (1024**2):.2f} MB / {total_bytes / (1024**2):.2f} MB ({percent:.1f}%)")
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
            
            # Verify upload
            try:
                response = self.client.head_object(Bucket=bucket, Key=key)
                uploaded_size = response.get('ContentLength', 0)
                actual_storage_class = response.get('StorageClass', storage_class)
                logger.info(f"Upload verified: {uploaded_size} bytes, storage class: {actual_storage_class}")
                
                if uploaded_size != file_size:
                    logger.warning(f"Size mismatch: uploaded {uploaded_size} bytes, expected {file_size} bytes")
            except ClientError as e:
                logger.warning(f"Could not verify upload: {e}")
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Failed to upload to S3: {error_code} - {error_msg}")
            raise Exception(f"S3 upload failed: {error_code} - {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}", exc_info=True)
            raise
    
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
