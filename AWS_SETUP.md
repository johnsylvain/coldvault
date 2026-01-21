# AWS Setup Guide for ColdVault

## Billing Requirements

**Yes, you need billing set up on your AWS account** to use S3 and Glacier storage, even though Glacier Deep Archive is very inexpensive (~$0.00099/GB/month).

### Why Billing is Required

- AWS requires a valid payment method (credit card) on your account
- This is required even for free tier services
- Glacier storage classes are not part of the free tier, so billing must be active

### Cost Estimates

For Glacier Deep Archive (cheapest option):
- **Storage**: ~$0.00099 per GB per month
- **Example**: 1 TB (1024 GB) = ~$1.01/month
- **Retrieval costs**: Vary by retrieval tier (Expedited, Standard, Bulk)

## Setup Steps

### 1. Create AWS Account
1. Go to https://aws.amazon.com/
2. Sign up for an account
3. **Add a payment method** (credit card required)

### 2. Create S3 Bucket
1. Go to AWS Console → S3
2. Click "Create bucket"
3. Choose a unique bucket name (e.g., `your-name-coldvault-backups`)
4. Select a region (remember this for `AWS_REGION` in .env)
5. **Important**: Uncheck "Block all public access" if you want (or leave it checked for security)
6. Click "Create bucket"

### 3. Create IAM User and Access Keys

**Option A: Use IAM User (Recommended for Security)**

1. Go to AWS Console → IAM
2. Click "Users" → "Add users"
3. Username: `coldvault-backup-user`
4. Select "Programmatic access"
5. Click "Next: Permissions"
6. Click "Attach policies directly"
7. Search for and select: `AmazonS3FullAccess` (or create a custom policy with minimal permissions)
8. Click "Next" → "Create user"
9. **IMPORTANT**: Copy the Access Key ID and Secret Access Key immediately (you won't see the secret again!)

**Option B: Use Root Account (Not Recommended)**
- You can use your root account credentials, but this is less secure
- Go to IAM → Security credentials → Create access key

### 4. Minimal IAM Policy (If Creating Custom Policy)

If you want to limit permissions (recommended), use this policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject",
                "s3:RestoreObject",
                "s3:GetObjectVersion"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name/*",
                "arn:aws:s3:::your-bucket-name"
            ]
        }
    ]
}
```

### 5. Configure ColdVault

Add to your `.env` file:

```bash
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1  # Match your bucket region
AWS_S3_BUCKET=your-bucket-name
```

### 6. Test Configuration

Use the diagnostic endpoint:

```bash
curl http://localhost:8088/api/diagnostics
```

Or test upload:

```bash
curl -X POST "http://localhost:8088/api/test-upload?bucket=your-bucket-name"
```

## Common Issues

### "InvalidAccessKeyId"
- Check that `AWS_ACCESS_KEY_ID` is correct
- Make sure there are no extra spaces in .env file

### "SignatureDoesNotMatch"
- Check that `AWS_SECRET_ACCESS_KEY` is correct
- Make sure the secret key wasn't truncated when copying

### "AccessDenied" or "403 Forbidden"
- Check IAM permissions
- Make sure the IAM user has `s3:PutObject` permission
- Verify the bucket name is correct

### "NoSuchBucket" or "404"
- Bucket doesn't exist
- Check bucket name spelling
- Make sure bucket is in the correct region

### "InvalidRequest" for Glacier Storage Class
- Your account might not be fully activated
- Check AWS Console → Billing to ensure payment method is verified
- Some accounts need to be active for 24-48 hours before Glacier is available

### Billing/Payment Issues
- AWS requires a valid payment method even for very low-cost services
- Check AWS Console → Billing & Cost Management
- Ensure your payment method is active and not expired

## Cost Monitoring

### Set Up Billing Alerts

1. Go to AWS Console → Billing & Cost Management
2. Click "Budgets" → "Create budget"
3. Set a monthly budget (e.g., $5)
4. Configure alerts at 50%, 80%, 100% of budget

### Estimate Costs

Use the ColdVault dashboard to see cost estimates, or use AWS Calculator:
https://calculator.aws/

## Security Best Practices

1. **Never commit credentials to git** - Use .env file (already in .gitignore)
2. **Use IAM users** - Don't use root account credentials
3. **Minimal permissions** - Only grant S3 permissions needed
4. **Rotate keys** - Change access keys periodically
5. **Enable MFA** - Use multi-factor authentication on AWS account

## Free Tier Note

AWS Free Tier includes:
- 5 GB of S3 Standard storage
- **Does NOT include Glacier storage classes**
- Glacier requires billing to be set up

Even with billing set up, Glacier Deep Archive is extremely cheap for long-term backups.
