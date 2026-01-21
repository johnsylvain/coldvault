# Development Setup Guide

This guide will help you set up ColdVault for local development.

## Prerequisites

- **Python 3.11, 3.12, or 3.13** (recommended)
  - Python 3.14+ may work but some packages may require building from source (needs Rust)
- pip (Python package manager)
- PostgreSQL (optional, SQLite is used by default for development)
- AWS account with S3 bucket (for testing backups)
- Git

**Note**: 
- For local development, SQLite is used by default and doesn't require PostgreSQL
- The `psycopg2-binary` package is optional and only needed if you want to use PostgreSQL locally
- If using Python 3.14+, you may need Rust installed: `brew install rust` (macOS) or install via rustup

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd coldvault
./dev.sh setup
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Set up development database (SQLite)
- Create necessary directories

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# For local development, SQLite is used by default
# DATABASE_URL is optional - will default to SQLite if not set

# AWS Configuration (required for backup testing)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-test-bucket-name

# Encryption Key (required)
ENCRYPTION_KEY=your-development-encryption-key-here

# Optional: Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com

# Optional: Webhook notifications
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Logging
LOG_LEVEL=DEBUG
```

### 3. Run Development Server

```bash
./dev.sh run
```

Or manually:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8088
```

The API will be available at:
- API: http://localhost:8088
- Dashboard: http://localhost:8088
- API Docs: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

## Development Workflow

### Running Tests

```bash
./dev.sh test
```

### Code Formatting

```bash
./dev.sh format
```

### Linting

```bash
./dev.sh lint
```

### Database Migrations

If using Alembic (PostgreSQL):

```bash
# Create a migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Running with PostgreSQL

**Note**: PostgreSQL is optional for local development. SQLite works fine for most development tasks.

1. Install PostgreSQL locally:

**macOS (Homebrew):**
```bash
brew install postgresql@15
# Or just: brew install postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql postgresql-contrib
```

**Or use Docker:**
```bash
docker run -d \
  --name coldvault-postgres \
  -e POSTGRES_DB=coldvault \
  -e POSTGRES_USER=coldvault \
  -e POSTGRES_PASSWORD=devpassword \
  -p 5432:5432 \
  postgres:15-alpine
```

2. Install PostgreSQL Python driver:
```bash
pip install psycopg2-binary==2.9.9
```

3. Update `.env`:

```bash
DATABASE_URL=postgresql://coldvault:devpassword@localhost:5432/coldvault
```

4. Run migrations:

```bash
alembic upgrade head
```

## Project Structure

```
coldvault/
├── app/
│   ├── api/              # API endpoints
│   │   ├── jobs.py       # Job management
│   │   ├── backups.py    # Backup execution
│   │   ├── restore.py    # Restore operations
│   │   ├── dashboard.py  # Dashboard API
│   │   └── notifications.py
│   ├── engines/          # Backup engines
│   │   ├── dataset_backup.py
│   │   └── restic_backup.py
│   ├── static/           # Dashboard UI
│   │   └── index.html
│   ├── aws.py           # AWS S3 integration
│   ├── config.py        # Configuration
│   ├── database.py      # Database models
│   ├── encryption.py    # Encryption utilities
│   ├── main.py          # FastAPI app
│   ├── notifications.py # Notification service
│   ├── restore.py       # Restore worker
│   ├── scheduler.py     # Job scheduler
│   └── worker.py        # Backup worker
├── docker-compose.yml    # Docker Compose config
├── Dockerfile           # Docker image
├── requirements.txt     # Python dependencies
├── dev.sh              # Development script
└── setup.sh            # Production setup
```

## Debugging

### Enable Debug Logging

Set in `.env`:
```bash
LOG_LEVEL=DEBUG
```

### View Logs

The application logs to stdout. For more detailed logging, check:
- Application logs: stdout/stderr
- Database: Check SQLite file or PostgreSQL logs
- Backup logs: Stored in backup run records

### Common Issues

**Issue: Import errors**
```bash
# Make sure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

**Issue: Database connection errors**
- Check DATABASE_URL in .env
- Ensure database is running (if using PostgreSQL)
- Check file permissions for SQLite database

**Issue: AWS connection errors**
- Verify AWS credentials in .env
- Check AWS region matches your bucket
- Ensure bucket exists and is accessible

**Issue: Port already in use**
```bash
# Change port in dev.sh or use:
uvicorn app.main:app --reload --port 8089
```

## Testing Backups Locally

### Using Local S3 (MinIO)

For local testing without AWS:

1. Run MinIO locally:
```bash
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

2. Configure AWS CLI to use MinIO:
```bash
aws configure set default.s3.signature_version s3v4
aws configure set default.s3.endpoint_url http://localhost:9000
```

3. Update `.env`:
```bash
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1
AWS_S3_BUCKET=test-bucket
```

Note: You'll need to modify `app/aws.py` to support custom endpoints for MinIO.

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Python Docstring Generator
- SQLAlchemy

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black"
}
```

### PyCharm

1. Open project
2. Configure Python interpreter: `venv/bin/python`
3. Set up run configuration:
   - Script: `app.main`
   - Parameters: `--reload --port 8088`
   - Environment variables: Load from `.env`

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
