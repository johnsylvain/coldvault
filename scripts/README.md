# Utility Scripts

One-off utility scripts for maintenance and recovery tasks.

## Scripts

### `fix_database_and_recover.py`

Fixes database schema issues and recovers stuck backup jobs.

**Usage:**
```bash
# Fix database schema (INTEGER -> BIGINT for size_bytes)
docker compose exec coldvault python scripts/fix_database_and_recover.py --fix-schema

# Recover a specific stuck backup run
docker compose exec coldvault python scripts/fix_database_and_recover.py --recover <backup_run_id>

# Fix schema and recover all stuck backups
docker compose exec coldvault python scripts/fix_database_and_recover.py --all
```

**What it does:**
- Alters `backup_runs.size_bytes` and `snapshots.size_bytes` from INTEGER to BIGINT
- Finds stuck backup runs (status = RUNNING but not actually running)
- Recovers backup runs by matching them with snapshots
- Updates backup run status to SUCCESS if snapshot exists

### `fix_schema_direct.sh`

Direct SQL fix for database schema - bypasses Python script issues.

**Usage:**
```bash
./scripts/fix_schema_direct.sh
```

**What it does:**
- Runs SQL directly in the database container to fix schema
- No Python dependencies required
- Useful if the Python script has issues

### `refresh_storage_metrics.py`

Refreshes storage metrics from database snapshots.

**Usage:**
```bash
docker compose exec coldvault python scripts/refresh_storage_metrics.py
```

**What it does:**
- Shows breakdown of all snapshots by job
- Calculates total storage from database
- Records updated metrics
- Useful when dashboard shows incorrect storage totals

## Running Scripts

All scripts should be run from the project root directory. When running in Docker:

```bash
docker compose exec coldvault python scripts/<script_name>.py [args]
```

For shell scripts:
```bash
./scripts/<script_name>.sh
```
