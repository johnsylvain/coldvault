#!/bin/bash
# ColdVault Setup Script

set -e

echo "🔒 ColdVault Setup"
echo "=================="
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p config cache data/db
chmod 755 config cache data/db

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your configuration."
    else
        echo "❌ .env.example not found. Please create a .env file manually."
        exit 1
    fi
fi

# Check for required environment variables
echo "🔍 Checking configuration..."
source .env

if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "⚠️  Warning: AWS credentials not set in .env"
fi

if [ -z "$AWS_S3_BUCKET" ]; then
    echo "⚠️  Warning: AWS_S3_BUCKET not set in .env"
fi

if [ -z "$ENCRYPTION_KEY" ]; then
    echo "⚠️  Warning: ENCRYPTION_KEY not set in .env"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your AWS credentials and configuration"
echo "2. Run: docker-compose up -d"
echo "3. Access the dashboard at http://localhost:8088"
echo ""
