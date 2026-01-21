# Troubleshooting Guide

## Common Issues and Solutions

### Python 3.14+ Build Errors

**Problem**: Getting errors about `pydantic-core` or other packages failing to build.

**Solution**: Python 3.14 is very new and some packages need to be built from source, which requires Rust.

**Option 1: Install Rust** (Recommended if you want to use Python 3.14)
```bash
# macOS
brew install rust

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

**Option 2: Use Python 3.11-3.13** (Recommended for better compatibility)
```bash
# macOS with Homebrew
brew install python@3.13

# Create venv with specific Python version
python3.13 -m venv venv
```

### psycopg2-binary Installation Fails

**Problem**: Error about `pg_config` not found when installing `psycopg2-binary`.

**Solution**: This is expected! `psycopg2-binary` is optional and only needed for PostgreSQL. SQLite works fine for development.

- **For SQLite (default)**: Just ignore the error, SQLite will work automatically
- **For PostgreSQL**: Install PostgreSQL first:
  ```bash
  # macOS
  brew install postgresql
  
  # Then install psycopg2-binary
  pip install psycopg2-binary
  ```

### Port Already in Use

**Problem**: `Address already in use` error when starting the server.

**Solution**:
```bash
# Find what's using port 8088
lsof -i :8088

# Kill the process or use a different port
# In dev.sh, change the port or use:
uvicorn app.main:app --reload --port 8089
```

### Database Connection Errors

**Problem**: Can't connect to database.

**Solutions**:

1. **SQLite**: Check file permissions
   ```bash
   ls -la config/coldvault.db
   chmod 644 config/coldvault.db
   ```

2. **PostgreSQL**: 
   - Ensure PostgreSQL is running: `brew services start postgresql`
   - Check connection string in `.env`
   - Verify credentials

### AWS Connection Errors

**Problem**: Can't connect to AWS S3.

**Solutions**:

1. **Check credentials in `.env`**:
   ```bash
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_REGION=us-east-1
   AWS_S3_BUCKET=your-bucket
   ```

2. **Verify bucket exists and is accessible**:
   ```bash
   aws s3 ls s3://your-bucket
   ```

3. **Check IAM permissions**: Your AWS user needs S3 read/write permissions

### Import Errors

**Problem**: `ModuleNotFoundError` or import errors.

**Solutions**:

1. **Ensure virtual environment is activated**:
   ```bash
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows
   ```

2. **Reinstall dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Check PYTHONPATH**:
   ```bash
   export PYTHONPATH=$(pwd)
   ```

### Virtual Environment Issues

**Problem**: Virtual environment not working correctly.

**Solution**: Recreate the virtual environment:
```bash
rm -rf venv
./dev.sh setup
```

### Docker Issues

**Problem**: Docker container won't start or has errors.

**Solutions**:

1. **Check Docker is running**:
   ```bash
   docker ps
   ```

2. **View logs**:
   ```bash
   docker-compose logs coldvault
   ```

3. **Rebuild containers**:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Backup Fails

**Problem**: Backup job fails to execute.

**Solutions**:

1. **Check source paths exist and are readable**:
   ```bash
   ls -la /mnt/media  # or your source path
   ```

2. **Check S3 bucket and permissions**:
   ```bash
   aws s3 ls s3://your-bucket
   ```

3. **Check logs in dashboard** or:
   ```bash
   docker-compose logs coldvault | grep ERROR
   ```

4. **Verify encryption key is set** (if encryption enabled)

### Schedule Not Working

**Problem**: Scheduled backups don't run.

**Solutions**:

1. **Check job is enabled** in dashboard
2. **Verify schedule format** (cron expression or preset)
3. **Check scheduler is running**:
   ```bash
   # In logs, you should see scheduler messages
   docker-compose logs coldvault | grep scheduler
   ```

### Still Having Issues?

1. **Check application logs**:
   ```bash
   # Docker
   docker-compose logs -f coldvault
   
   # Local development
   # Logs go to stdout when running with uvicorn
   ```

2. **Enable debug logging**:
   ```bash
   # In .env
   LOG_LEVEL=DEBUG
   ```

3. **Check database**:
   ```bash
   # SQLite
   sqlite3 config/coldvault.db ".tables"
   
   # PostgreSQL
   psql -U coldvault -d coldvault -c "\dt"
   ```

4. **Open an issue** on GitHub with:
   - Error messages
   - Python version
   - Operating system
   - Steps to reproduce
