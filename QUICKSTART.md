# Quick Start Guide

Get ColdVault up and running in minutes!

## Production Deployment (Docker)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd coldvault
./setup.sh
```

### 2. Configure

Edit `.env` file with your AWS credentials and settings.

### 3. Start

```bash
docker-compose up -d
```

### 4. Access

Open http://localhost:8088 in your browser.

## Development Setup

### 1. Setup Environment

```bash
git clone <repository-url>
cd coldvault
./dev.sh setup
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run

```bash
./dev.sh run
```

### 4. Access

- Dashboard: http://localhost:8088
- API Docs: http://localhost:8088/docs

## First Backup Job

1. Open the dashboard at http://localhost:8088
2. Click "New Job"
3. Fill in:
   - **Name**: `media-backup`
   - **Job Type**: `Dataset`
   - **Source Paths**: `/mnt/media` (one per line)
   - **Schedule**: `daily`
   - **S3 Bucket**: Your bucket name
   - **S3 Prefix**: `backups/media`
   - **Storage Class**: `DEEP_ARCHIVE`
4. Click "Create Job"
5. Click "Run Now" to test

## Troubleshooting

### Port Already in Use

Change port in `docker-compose.yml` or use:
```bash
uvicorn app.main:app --reload --port 8089
```

### Database Connection Error

- Check `.env` file has correct `DATABASE_URL`
- For Docker: Ensure PostgreSQL container is running
- For local: SQLite will be created automatically

### AWS Connection Error

- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`
- Check `AWS_REGION` matches your bucket region
- Ensure bucket exists and credentials have access

### Backup Fails

- Check source paths exist and are readable
- Verify S3 bucket exists and is accessible
- Check logs in the dashboard or Docker logs: `docker-compose logs coldvault`

## Next Steps

- Read [README.md](README.md) for detailed documentation
- See [DEV_SETUP.md](DEV_SETUP.md) for development guide
- Check API documentation at http://localhost:8088/docs
