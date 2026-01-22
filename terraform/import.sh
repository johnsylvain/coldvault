#!/bin/bash

# Script to import existing S3 bucket into Terraform
# This script helps safely import an existing bucket without losing data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}ColdVault Terraform Import Helper${NC}"
echo "=================================="
echo ""

# Check if bucket name is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Bucket name is required${NC}"
    echo "Usage: ./import.sh <bucket-name>"
    echo "Example: ./import.sh my-coldvault-backups"
    exit 1
fi

BUCKET_NAME=$1

echo -e "${YELLOW}Importing bucket: ${BUCKET_NAME}${NC}"
echo ""

# Check if bucket exists
echo "Checking if bucket exists..."
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo -e "${RED}Error: Bucket '$BUCKET_NAME' does not exist or is not accessible${NC}"
    echo "Please verify:"
    echo "  1. Bucket name is correct"
    echo "  2. AWS credentials are configured"
    echo "  3. You have permissions to access the bucket"
    exit 1
fi

echo -e "${GREEN}✓ Bucket exists${NC}"
echo ""

# Check if terraform.tfvars exists
if [ ! -f "terraform.tfvars" ]; then
    echo -e "${YELLOW}Warning: terraform.tfvars not found${NC}"
    echo "Creating terraform.tfvars from example..."
    if [ -f "terraform.tfvars.example" ]; then
        cp terraform.tfvars.example terraform.tfvars
        # Update bucket name in the file
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/bucket_name = .*/bucket_name = \"$BUCKET_NAME\"/" terraform.tfvars
        else
            # Linux
            sed -i "s/bucket_name = .*/bucket_name = \"$BUCKET_NAME\"/" terraform.tfvars
        fi
        echo -e "${GREEN}✓ Created terraform.tfvars${NC}"
    else
        echo -e "${RED}Error: terraform.tfvars.example not found${NC}"
        exit 1
    fi
    echo ""
fi

# Initialize Terraform if needed
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
    echo ""
fi

# Import the bucket
echo -e "${YELLOW}Importing bucket into Terraform...${NC}"
echo "Running: terraform import aws_s3_bucket.backups $BUCKET_NAME"
echo ""

if terraform import aws_s3_bucket.backups "$BUCKET_NAME"; then
    echo ""
    echo -e "${GREEN}✓ Bucket imported successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'terraform plan' to see what Terraform wants to create"
    echo "  2. Review the plan carefully"
    echo "  3. Run 'terraform apply' to create IAM user and other resources"
    echo ""
    echo -e "${YELLOW}Note: The bucket itself should show no changes in the plan${NC}"
    echo "      Only new resources (IAM, lifecycle rules, etc.) will be created"
else
    echo ""
    echo -e "${RED}Error: Import failed${NC}"
    echo "Possible reasons:"
    echo "  1. Bucket is already managed by Terraform"
    echo "  2. Terraform state file has conflicts"
    echo "  3. AWS credentials/permissions issue"
    exit 1
fi
