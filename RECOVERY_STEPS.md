# Recovery Steps for Stuck Backup Job

## Complete Recovery Flow

### Step 1: Stop the Docker containers

```bash
cd /Users/john/code/coldvault
docker-compose down
```

### Step 2: Rebuild the Docker image (to get updated database.py)

```bash
docker-compose build --no-cache
```

**Note:** The `--no-cache` flag ensures you get the latest code changes. This may take a few minutes.

### Step 3: Start the containers

```bash
docker-compose up -d
```

Wait a few seconds for the containers to start, then verify they're running:

```bash
docker-compose ps
```

### Step 4: Fix the database schema

Run the recovery script inside the container to fix the database columns:

```bash
docker-compose exec coldvault python scripts/fix_database_and_recover.py --fix-schema
```

**Alternative:** If the exec command doesn't work, you can run it directly:

```bash
docker-compose exec coldvault bash
# Then inside the container:
python scripts/fix_database_and_recover.py --fix-schema
exit
```

**Or use the direct SQL script:**

```bash
./scripts/fix_schema_direct.sh
```

### Step 5: Recover the stuck backup job

Recover backup run ID 3 (from your error log):

```bash
docker-compose exec coldvault python scripts/fix_database_and_recover.py --recover 3
```

**Or do both steps 4 and 5 at once:**

```bash
docker-compose exec coldvault python scripts/fix_database_and_recover.py --all
```

### Step 6: Verify the recovery

Check the backup status in the web UI or via API:

```bash
# Check backup runs
curl http://localhost:8088/api/backups/runs?job_id=1 | jq
```

Or visit: http://localhost:8088

## What Each Step Does

1. **Stop containers**: Safely stops running containers
2. **Rebuild**: Compiles new Docker image with BigInteger fix in database.py
3. **Start**: Starts containers with new code
4. **Fix schema**: Alters PostgreSQL columns from INTEGER to BIGINT
5. **Recover job**: Updates the stuck backup run status to SUCCESS (since backup actually completed)

## Expected Output

After step 5, you should see:
```
✓ Recovered backup run 3 - marked as SUCCESS
```

The backup job should now show as SUCCESS in the UI with:
- 2,421 files backed up
- 54.26 GB total
- All files safely in S3

## Troubleshooting

If you get connection errors in step 4/5:
- Wait a bit longer for the database to be ready: `docker-compose logs db`
- Check container is running: `docker-compose ps`
- Try connecting to DB directly: `docker-compose exec db psql -U coldvault -d coldvault`

If the recovery script can't find the backup run:
- Check the backup run ID in the error log (it was 3 in your case)
- List all backup runs: `docker-compose exec coldvault python -c "from app.database import SessionLocal, BackupRun; db = SessionLocal(); runs = db.query(BackupRun).all(); [print(f'ID: {r.id}, Status: {r.status}, Job: {r.job_id}') for r in runs]"`
- Refresh storage metrics: `docker-compose exec coldvault python scripts/refresh_storage_metrics.py`