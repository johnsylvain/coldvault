"""
Diagnostic endpoints for troubleshooting
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.aws import s3_client
from app.config import settings

router = APIRouter()

class DiagnosticsResponse(BaseModel):
    aws_configured: bool
    s3_client_initialized: bool
    bucket_configured: bool
    encryption_key_configured: bool
    issues: list[str]
    recommendations: list[str]

@router.get("/diagnostics")
def get_diagnostics():
    """Get diagnostic information about configuration"""
    issues = []
    recommendations = []
    
    # Check AWS credentials
    aws_configured = bool(settings.aws_access_key_id and settings.aws_secret_access_key)
    if not aws_configured:
        issues.append("AWS credentials not configured (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)")
        recommendations.append("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file")
    
    # Check S3 client
    s3_client_initialized = s3_client.client is not None
    if not s3_client_initialized:
        issues.append("S3 client not initialized")
        recommendations.append("Check AWS credentials and region configuration")
    
    # Check bucket
    bucket_configured = bool(settings.aws_s3_bucket)
    if not bucket_configured:
        issues.append("S3 bucket not configured (AWS_S3_BUCKET)")
        recommendations.append("Set AWS_S3_BUCKET in .env file")
    
    # Check encryption key
    encryption_key_configured = bool(settings.encryption_key)
    if not encryption_key_configured:
        issues.append("Encryption key not configured (ENCRYPTION_KEY)")
        recommendations.append("Set ENCRYPTION_KEY in .env file (required for encrypted backups)")
    
    # Test S3 connectivity if credentials are set
    s3_test_result = None
    if aws_configured and bucket_configured and s3_client_initialized:
        try:
            # Try to list objects (minimal permission check)
            s3_client.client.list_objects_v2(Bucket=settings.aws_s3_bucket, MaxKeys=1)
            s3_test_result = "success"
        except Exception as e:
            error_msg = str(e)
            s3_test_result = f"failed: {error_msg}"
            issues.append(f"S3 connectivity test failed: {error_msg}")
            
            if "AccessDenied" in error_msg or "403" in error_msg:
                recommendations.append("Check IAM permissions - your AWS user needs s3:ListBucket permission")
            elif "NoSuchBucket" in error_msg or "404" in error_msg:
                recommendations.append(f"Bucket '{settings.aws_s3_bucket}' does not exist. Create it in AWS Console or check the bucket name")
            elif "InvalidAccessKeyId" in error_msg:
                recommendations.append("Invalid AWS Access Key ID. Check AWS_ACCESS_KEY_ID in .env")
            elif "SignatureDoesNotMatch" in error_msg:
                recommendations.append("Invalid AWS Secret Access Key. Check AWS_SECRET_ACCESS_KEY in .env")
            elif "region" in error_msg.lower():
                recommendations.append(f"Check AWS_REGION setting. Bucket might be in a different region than {settings.aws_region}")
            elif "account" in error_msg.lower() or "billing" in error_msg.lower() or "payment" in error_msg.lower():
                recommendations.append("AWS account may need billing information. Check AWS Console -> Billing & Cost Management")
            elif "InvalidRequest" in error_msg or "InvalidParameter" in error_msg:
                recommendations.append("Check that your AWS account supports the requested storage class (Glacier requires account activation)")
    
    return {
        "aws_configured": aws_configured,
        "s3_client_initialized": s3_client_initialized,
        "bucket_configured": bucket_configured,
        "encryption_key_configured": encryption_key_configured,
        "aws_region": settings.aws_region,
        "s3_bucket": settings.aws_s3_bucket,
        "s3_test": s3_test_result,
        "issues": issues,
        "recommendations": recommendations,
        "status": "ok" if not issues else "issues_found"
    }

@router.get("/diagnostics/aws-test")
def test_aws_connection():
    """Test AWS S3 connection with detailed error information"""
    if not s3_client.client:
        raise HTTPException(
            status_code=500,
            detail="S3 client not initialized. Check AWS credentials."
        )
    
    if not settings.aws_s3_bucket:
        raise HTTPException(
            status_code=400,
            detail="No S3 bucket configured. Set AWS_S3_BUCKET in .env"
        )
    
    results = {
        "bucket": settings.aws_s3_bucket,
        "region": settings.aws_region,
        "tests": {}
    }
    
    # Test 1: List bucket
    try:
        response = s3_client.client.list_objects_v2(Bucket=settings.aws_s3_bucket, MaxKeys=1)
        results["tests"]["list_bucket"] = {
            "success": True,
            "message": "Can list objects in bucket"
        }
    except Exception as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
        results["tests"]["list_bucket"] = {
            "success": False,
            "error": str(e),
            "error_code": error_code,
            "message": f"Failed to list bucket: {error_code}"
        }
    
    # Test 2: Get bucket location
    try:
        response = s3_client.client.get_bucket_location(Bucket=settings.aws_s3_bucket)
        location = response.get('LocationConstraint') or 'us-east-1'
        results["tests"]["bucket_location"] = {
            "success": True,
            "location": location,
            "message": f"Bucket is in region: {location}"
        }
        if location != settings.aws_region:
            results["tests"]["bucket_location"]["warning"] = f"Bucket region ({location}) differs from configured region ({settings.aws_region})"
    except Exception as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
        results["tests"]["bucket_location"] = {
            "success": False,
            "error": str(e),
            "error_code": error_code
        }
    
    # Test 3: Check permissions
    try:
        # Try to get bucket ACL (requires s3:GetBucketAcl permission)
        s3_client.client.get_bucket_acl(Bucket=settings.aws_s3_bucket)
        results["tests"]["permissions"] = {
            "success": True,
            "message": "Has read permissions on bucket"
        }
    except Exception as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
        results["tests"]["permissions"] = {
            "success": False,
            "error": str(e),
            "error_code": error_code,
            "message": f"Permission check failed: {error_code} (this is OK if you don't have ACL permissions)"
        }
    
    return results
