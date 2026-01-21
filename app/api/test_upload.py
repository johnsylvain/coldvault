"""
Test upload endpoint for validating S3 connectivity
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import tempfile
import os
from datetime import datetime

from app.aws import s3_client
from app.config import settings

router = APIRouter()

class TestUploadResponse(BaseModel):
    success: bool
    message: str
    bucket: str
    key: str
    object_info: dict | None = None

@router.post("/test-upload")
def test_s3_upload(bucket: str | None = None, prefix: str = "test/"):
    """Test S3 upload functionality
    
    Creates a small test file and uploads it to verify S3 connectivity.
    """
    if not s3_client.client:
        raise HTTPException(
            status_code=500,
            detail="S3 client not initialized. Check AWS credentials in .env file"
        )
    
    test_bucket = bucket or settings.aws_s3_bucket
    if not test_bucket:
        raise HTTPException(
            status_code=400,
            detail="No bucket specified. Provide bucket parameter or set AWS_S3_BUCKET in .env"
        )
    
    # Create a small test file
    test_content = f"ColdVault test upload - {datetime.utcnow().isoformat()}\n"
    test_key = f"{prefix}test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(test_content)
            temp_path = f.name
        
        try:
            # Upload test file
            s3_client.upload_file(
                temp_path,
                test_bucket,
                test_key,
                storage_class="STANDARD"  # Use STANDARD for test (faster, cheaper)
            )
            
            # Verify upload
            info = s3_client.get_object_info(test_bucket, test_key)
            
            return TestUploadResponse(
                success=True,
                message=f"Test upload successful! File uploaded to s3://{test_bucket}/{test_key}",
                bucket=test_bucket,
                key=test_key,
                object_info=info
            )
        finally:
            # Clean up temp file
            os.unlink(temp_path)
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test upload failed: {str(e)}"
        )

@router.get("/test-upload/list")
def list_test_uploads(bucket: str | None = None, prefix: str = "test/"):
    """List test uploads in S3"""
    test_bucket = bucket or settings.aws_s3_bucket
    if not test_bucket:
        raise HTTPException(
            status_code=400,
            detail="No bucket specified. Provide bucket parameter or set AWS_S3_BUCKET in .env"
        )
    
    objects = s3_client.list_objects(test_bucket, prefix=prefix, limit=50)
    
    return {
        "bucket": test_bucket,
        "prefix": prefix,
        "count": len(objects),
        "objects": objects
    }
