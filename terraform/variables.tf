variable "bucket_name" {
  description = "Name of the S3 bucket for ColdVault backups"
  type        = string
}

variable "aws_region" {
  description = "AWS region for the S3 bucket"
  type        = string
  default     = "us-east-1"
}

variable "iam_user_name" {
  description = "Name of the IAM user for ColdVault backups"
  type        = string
  default     = "coldvault-backup-user"
}

variable "enable_lifecycle_transitions" {
  description = "Enable automatic storage class transitions for backup files (optional)"
  type        = bool
  default     = false
}

variable "budget_limit" {
  description = "Monthly budget limit in USD for cost monitoring"
  type        = number
  default     = 5
}

variable "budget_email" {
  description = "Email address for budget alerts"
  type        = string
  default     = ""
}

variable "enable_budget" {
  description = "Enable AWS Budget for cost monitoring"
  type        = bool
  default     = true
}
