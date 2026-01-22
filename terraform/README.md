# Terraform Infrastructure for ColdVault

**Note: Terraform is OPTIONAL** - You can still set up AWS infrastructure manually via the AWS Console. See [AWS_SETUP.md](../AWS_SETUP.md) for manual setup instructions.

This Terraform configuration automates the creation of AWS infrastructure for ColdVault, including:
- S3 bucket with versioning and encryption
- IAM user with minimal permissions
- Lifecycle rules (optional)
- Cost monitoring budgets (optional)

## Prerequisites

- Terraform >= 1.0 installed
- AWS CLI configured with credentials
- AWS account with billing enabled (required for Glacier storage classes)

## Quick Start

### 1. Configure Variables

Copy the example variables file and edit it:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
bucket_name = "your-bucket-name"
aws_region  = "us-east-1"
```

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Apply Configuration

```bash
terraform apply
```

### 5. Save Access Keys

**IMPORTANT**: The secret access key is only shown once. Save it immediately:

```bash
# Get access key ID
terraform output access_key_id

# Get secret access key (only available immediately after creation)
terraform output -raw access_key_secret
```

Save these values to your `.env` file:

```bash
AWS_ACCESS_KEY_ID=<from terraform output>
AWS_SECRET_ACCESS_KEY=<from terraform output>
AWS_REGION=<from terraform output bucket_region>
AWS_S3_BUCKET=<from terraform output bucket_name>
```

## Importing Existing Buckets

If you already have a bucket with backup data, you can import it into Terraform without losing any data.

### Step 1: Configure Terraform

Set `bucket_name` in `terraform.tfvars` to match your existing bucket name.

### Step 2: Import the Bucket

```bash
terraform import aws_s3_bucket.backups YOUR-BUCKET-NAME
```

### Step 3: Verify Plan

```bash
terraform plan
```

You should see that Terraform wants to create new resources (IAM user, etc.) but won't modify the bucket. If it shows bucket changes, review them carefully.

### Step 4: Apply

```bash
terraform apply
```

This will only add new resources (IAM user, lifecycle rules, etc.) without touching your existing bucket or data.

### Safety Features

- The bucket resource includes `prevent_destroy = true` to prevent accidental deletion
- Importing is read-only - it only brings the bucket under Terraform management
- All existing data remains untouched

## Lifecycle Rules for Manifest Files

**CRITICAL**: Manifest files (`.manifest.json`) must stay in STANDARD storage class for immediate access.

- The application code already uploads manifest files to STANDARD
- Terraform lifecycle rules provide additional protection
- See [LIFECYCLE_RULES.md](LIFECYCLE_RULES.md) for manual setup instructions if you're not using Terraform

## Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|-----------|
| `bucket_name` | S3 bucket name | - | Yes |
| `aws_region` | AWS region | `us-east-1` | No |
| `iam_user_name` | IAM user name | `coldvault-backup-user` | No |
| `enable_lifecycle_transitions` | Enable storage class transitions | `false` | No |
| `enable_budget` | Enable cost monitoring | `true` | No |
| `budget_limit` | Monthly budget limit (USD) | `5` | No |
| `budget_email` | Email for budget alerts | `""` | No |

## Outputs

After running `terraform apply`, you can get output values:

```bash
# Bucket name
terraform output bucket_name

# Bucket region
terraform output bucket_region

# IAM user name
terraform output iam_user_name

# Access key ID
terraform output access_key_id

# Secret access key (only available immediately after creation)
terraform output -raw access_key_secret

# Complete .env file template
terraform output env_file_template
```

## Infrastructure Components

### S3 Bucket

- Versioning enabled (for backup recovery)
- Server-side encryption (SSE-S3)
- Public access blocked (security best practice)
- Protected from accidental deletion (`prevent_destroy = true`)

### IAM User

- Minimal permissions for S3 operations:
  - `s3:PutObject`
  - `s3:GetObject`
  - `s3:ListBucket`
  - `s3:DeleteObject`
  - `s3:RestoreObject`
  - `s3:GetObjectVersion`

### Lifecycle Rules

- Optional transitions for backup files (disabled by default)
- Manifest files are handled by application code (uploaded to STANDARD)

### Cost Monitoring

- AWS Budget with email alerts at 50%, 80%, and 100% of budget
- Optional (can be disabled)

## Troubleshooting

### "InvalidAccessKeyId" Error

- Check that `AWS_ACCESS_KEY_ID` is correct
- Verify there are no extra spaces in `.env` file

### "AccessDenied" Error

- Verify IAM user has correct permissions
- Check bucket name is correct
- Ensure bucket is in the correct region

### Budget Not Working

- Verify email is verified in AWS account
- Check that `budget_email` is set in `terraform.tfvars`
- Ensure `enable_budget = true`

### Import Issues

- Verify bucket name is correct
- Check AWS credentials have permissions to read bucket
- Review `terraform plan` output carefully before applying

## Manual Setup Alternative

If you prefer not to use Terraform, see [AWS_SETUP.md](../AWS_SETUP.md) for manual setup instructions. The manual setup includes:

- Creating S3 bucket via AWS Console
- Creating IAM user and access keys
- Setting up lifecycle rules (see [LIFECYCLE_RULES.md](LIFECYCLE_RULES.md))

## Additional Resources

- [AWS_SETUP.md](../AWS_SETUP.md) - Manual setup guide
- [LIFECYCLE_RULES.md](LIFECYCLE_RULES.md) - Manual lifecycle rule setup
- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
