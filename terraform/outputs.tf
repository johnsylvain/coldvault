output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.backups.id
}

output "bucket_region" {
  description = "AWS region of the S3 bucket"
  value       = aws_s3_bucket.backups.region
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.backups.arn
}

output "iam_user_name" {
  description = "Name of the IAM user"
  value       = aws_iam_user.backup_user.name
}

output "iam_user_arn" {
  description = "ARN of the IAM user"
  value       = aws_iam_user.backup_user.arn
}

output "access_key_id" {
  description = "Access Key ID for the IAM user"
  value       = aws_iam_access_key.backup_user.id
  sensitive   = false
}

output "access_key_secret_instructions" {
  description = "Instructions for retrieving the secret access key"
  value       = "The secret access key cannot be retrieved after creation. You must save it immediately after running 'terraform apply'. To retrieve it, use: terraform output -raw access_key_secret (if saved) or create a new access key via AWS Console/IAM."
}

output "access_key_secret" {
  description = "Secret Access Key (only available immediately after creation)"
  value       = aws_iam_access_key.backup_user.secret
  sensitive   = true
}

output "env_file_template" {
  description = "Template for .env file configuration"
  value = <<-EOT
    # Add these to your .env file:
    AWS_ACCESS_KEY_ID=${aws_iam_access_key.backup_user.id}
    AWS_SECRET_ACCESS_KEY=<retrieve from terraform output -raw access_key_secret or AWS Console>
    AWS_REGION=${aws_s3_bucket.backups.region}
    AWS_S3_BUCKET=${aws_s3_bucket.backups.id}
  EOT
}
