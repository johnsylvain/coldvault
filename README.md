# ColdVault

**Self-Hosted Scheduled Backups to AWS Cold Storage**

ColdVault is a Docker-based application that provides automated, encrypted, scheduled backups from a single host to AWS cold storage (S3 Glacier classes). It supports multiple datasets with independent schedules, manual backup triggers, host-level backups (via restic), and a dashboard for monitoring.

## Features

- ✅ Multiple backup jobs with independent schedules
- ✅ Dataset-level backups (media, Immich, app data)
- ✅ Host-level backups using restic
- ✅ AWS Glacier support (Instant Retrieval, Flexible Retrieval, Deep Archive)
- ✅ Client-side encryption
- ✅ Web dashboard for monitoring and control
- ✅ Manual backup triggers
- ✅ Retention policies
- ✅ Email and webhook notifications
- ✅ Cost estimation

## Quick Start

### Prerequisites

- Docker and Docker Compose
- AWS account with **billing set up** (payment method required)
- S3 bucket created in AWS Console
- AWS credentials (Access Key ID and Secret Access Key)

**Note**: AWS requires a valid payment method even for Glacier storage. See [AWS_SETUP.md](AWS_SETUP.md) for detailed setup instructions.

### Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd coldvault
```

2. Create a `.env` file:
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-bucket-name

# Encryption (required for encrypted backups)
ENCRYPTION_KEY=your-encryption-key-here

# Database (optional, defaults to SQLite)
DB_PASSWORD=changeme

# Timezone
TZ=America/Chicago

# Optional: Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com

# Optional: Webhook notifications
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

3. Start the application:
```bash
docker-compose up -d
```

4. Access the dashboard:
Open http://localhost:8088 in your browser

## Usage

### Creating a Backup Job

1. Click "New Job" in the dashboard
2. Fill in the job details:
   - **Name**: Unique name for the job
   - **Job Type**: Dataset or Host (Restic)
   - **Source Paths**: One path per line (e.g., `/mnt/media`, `/mnt/immich`)
   - **Schedule**: Hourly, Daily, Weekly, or Monthly
   - **S3 Bucket**: Your AWS S3 bucket name
   - **S3 Prefix**: Path prefix in the bucket (e.g., `backups/media`)
   - **Storage Class**: Glacier Instant Retrieval, Flexible Retrieval, or Deep Archive

### Manual Backup

Click "Run Now" on any job in the dashboard to trigger an immediate backup.

### Restore

Use the API endpoint `/api/restore/restore` to initiate a restore operation. Glacier snapshots may require retrieval time.

## API Endpoints

- `GET /api/jobs/` - List all jobs
- `POST /api/jobs/` - Create a new job
- `GET /api/jobs/{id}` - Get job details
- `PUT /api/jobs/{id}` - Update a job
- `DELETE /api/jobs/{id}` - Delete a job
- `POST /api/backups/{job_id}/run` - Trigger manual backup
- `GET /api/backups/runs` - List backup runs
- `GET /api/dashboard/overview` - Dashboard statistics
- `GET /api/restore/jobs/{job_id}/snapshots` - List snapshots

## Architecture

- **Web UI + API**: FastAPI-based REST API with HTML dashboard
- **Scheduler**: APScheduler for cron-like job scheduling
- **Worker**: Executes backup jobs using appropriate engine
- **Backup Engines**:
  - Dataset engine: Creates tar.gz archives
  - Restic engine: Uses restic for host backups
- **AWS Integration**: Boto3 for S3 uploads with Glacier support
- **Database**: PostgreSQL (or SQLite for MVP)

## Storage Classes

- **Glacier Instant Retrieval**: Fast retrieval, higher cost
- **Glacier Flexible Retrieval**: Standard retrieval (3-5 hours), lower cost
- **Glacier Deep Archive**: Longest retrieval (12 hours), lowest cost

## Security

- Client-side encryption enabled by default
- Encryption key should be stored securely (Docker secrets recommended)
- Least-privilege IAM policy recommended for AWS access

## Development

### Quick Start for Development

1. **Setup development environment:**
   ```bash
   ./dev.sh setup
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run development server:**
   ```bash
   ./dev.sh run
   ```

The API will be available at:
- Dashboard: http://localhost:8088
- API Docs: http://localhost:8088/docs
- ReDoc: http://localhost:8088/redoc

### Development Commands

- `./dev.sh setup` - Set up virtual environment and install dependencies
- `./dev.sh run` - Run development server with auto-reload
- `./dev.sh lint` - Run code linters
- `./dev.sh format` - Format code with black and isort
- `./dev.sh test` - Run tests (when implemented)
- `./dev.sh clean` - Clean Python cache files
- `./dev.sh shell` - Start Python shell with app context

For detailed development setup instructions, see [DEV_SETUP.md](DEV_SETUP.md).

For troubleshooting common issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
