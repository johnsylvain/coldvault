# Manual Lifecycle Rule Setup for Manifest Files

This guide provides instructions for setting up S3 lifecycle rules to ensure manifest files (`.manifest.json`) stay in STANDARD storage class for immediate access. This is **critical** for ColdVault operations.

## Why This Matters

- Manifest files are small metadata files that need frequent access
- If manifest files end up in Deep Archive or Glacier, you'll need to wait hours/days for restore
- STANDARD storage class provides immediate access with no retrieval costs
- The application code already uploads manifest files to STANDARD, but lifecycle rules provide an extra safety net

## Option 1: AWS CLI (Recommended)

### Create Lifecycle Rule Using AWS CLI

Save the following JSON to a file named `lifecycle-rule.json`:

```json
{
  "Rules": [
    {
      "Id": "keep-manifests-in-standard",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Transitions": []
    }
  ]
}
```

**Note**: S3 lifecycle rules don't support suffix-based filtering (e.g., `*.manifest.json`) directly. The application code already handles uploading manifest files to STANDARD. This rule ensures no automatic transitions occur.

### Apply the Rule

```bash
# Replace YOUR-BUCKET-NAME with your actual bucket name
aws s3api put-bucket-lifecycle-configuration \
  --bucket YOUR-BUCKET-NAME \
  --lifecycle-configuration file://lifecycle-rule.json
```

### Verify the Rule

```bash
aws s3api get-bucket-lifecycle-configuration --bucket YOUR-BUCKET-NAME
```

## Option 2: Using Object Tags (More Robust)

If you want a more robust solution that explicitly prevents manifest file transitions, you can use object tags:

### Step 1: Tag Manifest Files

The application would need to tag manifest files during upload. This requires a code change to add tags like `FileType=manifest`.

### Step 2: Create Lifecycle Rule with Tag Filter

```json
{
  "Rules": [
    {
      "Id": "exclude-manifests-from-transitions",
      "Status": "Enabled",
      "Filter": {
        "And": {
          "Prefix": "",
          "Tags": [
            {
              "Key": "FileType",
              "Value": "manifest"
            }
          ]
        }
      },
      "Transitions": []
    },
    {
      "Id": "transition-backup-files",
      "Status": "Enabled",
      "Filter": {
        "And": {
          "Prefix": "",
          "TagFilters": [
            {
              "Key": "FileType",
              "Value": "manifest"
            }
          ]
        }
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

## Option 3: AWS Console

1. Go to AWS Console → S3
2. Select your bucket
3. Go to **Management** tab
4. Click **Create lifecycle rule**
5. Rule name: `keep-manifests-in-standard`
6. **Scope**: Apply to all objects in the bucket
7. **Transitions**: Leave empty (no transitions)
8. Click **Create rule**

## Verification

After setting up the lifecycle rule, verify it's working:

1. Upload a test manifest file
2. Check its storage class (should be STANDARD)
3. Wait a few days and verify it's still in STANDARD
4. Check lifecycle rule status in S3 console

## Important Notes

- **The application code already uploads manifest files to STANDARD** - this is the primary protection
- Lifecycle rules provide defense in depth
- S3 lifecycle rules primarily handle transitions, not preventing them
- If you need to prevent transitions, consider using object tags or organizing files by prefix
- Manifest files should never be deleted automatically - ensure no expiration rules apply to them

## Troubleshooting

### Rule Not Applying

- Check that the rule status is "Enabled"
- Verify the filter matches your file structure
- Check S3 bucket permissions

### Files Still Transitioning

- Verify the lifecycle rule is active
- Check if there are multiple lifecycle rules that might conflict
- Ensure the application code is uploading to STANDARD (check logs)

## Additional Resources

- [AWS S3 Lifecycle Configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS CLI S3 Lifecycle Commands](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-bucket-lifecycle-configuration.html)
