# IAM User for ColdVault backups
resource "aws_iam_user" "backup_user" {
  name = var.iam_user_name

  tags = {
    Name        = "ColdVault Backup User"
    ManagedBy   = "Terraform"
    Application = "ColdVault"
  }
}

# IAM Policy with minimal permissions for S3 operations
resource "aws_iam_user_policy" "backup_user_policy" {
  name = "${var.iam_user_name}-policy"
  user = aws_iam_user.backup_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject",
          "s3:RestoreObject",
          "s3:GetObjectVersion"
        ]
        Resource = [
          "${aws_s3_bucket.backups.arn}/*",
          aws_s3_bucket.backups.arn
        ]
      }
    ]
  })
}

# IAM Access Key for programmatic access
resource "aws_iam_access_key" "backup_user" {
  user = aws_iam_user.backup_user.name
}
