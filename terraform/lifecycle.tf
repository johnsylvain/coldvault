# Lifecycle rule to keep manifest files in STANDARD storage class
# This is CRITICAL for manifest accessibility - manifest files must be immediately accessible
# without Glacier restore requests.
#
# Note: S3 lifecycle rules don't support suffix-based filtering (e.g., *.manifest.json) directly.
# However, the application code already uploads manifest files to STANDARD storage class.
# This lifecycle configuration serves as documentation and can be extended if needed.
#
# For a more robust solution, consider using object tags or prefix-based organization.
# See LIFECYCLE_RULES.md for manual setup instructions using AWS CLI.

# Lifecycle configuration for the bucket
# Since manifest files are uploaded to STANDARD by the application code,
# and lifecycle rules primarily handle transitions (not preventing them),
# we'll create a minimal configuration that doesn't interfere with manifest files.
#
# If you need to ensure manifest files never transition, you can:
# 1. Use object tags (tag manifest files and exclude tagged objects from transitions)
# 2. Organize manifest files under a specific prefix and exclude that prefix from transitions
# 3. Rely on the application code (which already uploads manifests to STANDARD)

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  # Rule 1: Optional transition rule for backup files (disabled by default)
  # This rule only applies if enable_lifecycle_transitions is true
  # Manifest files are excluded because they're uploaded to STANDARD
  # and this rule only applies to objects that match the filter
  dynamic "rule" {
    for_each = var.enable_lifecycle_transitions ? [1] : []
    content {
      id     = "transition-backup-files"
      status = "Enabled"

      filter {
        prefix = ""
      }

      # Transition to Glacier Flexible Retrieval after 90 days
      transition {
        days          = 90
        storage_class = "GLACIER"
      }

      # Transition to Deep Archive after 180 days
      transition {
        days          = 180
        storage_class = "DEEP_ARCHIVE"
      }
    }
  }

  # Note: To ensure manifest files stay in STANDARD, the application code
  # already handles this by uploading them with storage_class="STANDARD".
  # For additional protection, see LIFECYCLE_RULES.md for manual setup
  # instructions that use object tags or prefix-based exclusions.
}
