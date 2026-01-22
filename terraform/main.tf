provider "aws" {
  region = var.aws_region
}

# S3 Bucket for ColdVault backups
resource "aws_s3_bucket" "backups" {
  bucket = var.bucket_name

  # Prevent accidental deletion of bucket with data
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "ColdVault Backups"
    ManagedBy   = "Terraform"
    Application = "ColdVault"
  }
}

# Enable versioning for backup recovery
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access (security best practice)
resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls     = true
  restrict_public_buckets = true
}
