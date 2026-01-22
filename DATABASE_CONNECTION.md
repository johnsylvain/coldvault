# Database Connection Instructions

ColdVault supports two database backends: **SQLite** (default for development) and **PostgreSQL** (used in Docker/production).

## SQLite (Default for Development)

### Database Location
- **Path**: `./config/coldvault.db` (relative to project root)
- **Full Path**: `/Users/john/code/coldvault/config/coldvault.db`

### Connection Methods

#### 1. Using SQLite Command Line

```bash
# From project root
sqlite3 config/coldvault.db

# Or with full path
sqlite3 /Users/john/code/coldvault/config/coldvault.db
```

#### 2. Using Python (SQLAlchemy)

```python
from sqlalchemy import create_engine
from app.database import SessionLocal, Job, BackupRun, Snapshot

# Create connection
engine = create_engine("sqlite:///./config/coldvault.db", connect_args={"check_same_thread": False})

# Use existing session
db = SessionLocal()
jobs = db.query(Job).all()
db.close()
```

#### 3. Using Python Shell

```bash
# From project root with virtual environment activated
./dev.sh shell

# Or manually
source venv/bin/activate
python -c "from app.database import SessionLocal, Job; db = SessionLocal(); print([j.name for j in db.query(Job).all()])"
```

#### 4. Using Database Browser Tools

**DB Browser for SQLite** (GUI):
- Download: https://sqlitebrowser.org/
- Open: `config/coldvault.db`

**VS Code Extension**:
- Install "SQLite Viewer" extension
- Open `config/coldvault.db` in VS Code

**DBeaver** (Universal):
- Download: https://dbeaver.io/
- Create new connection → SQLite
- Database path: `./config/coldvault.db`

### Common SQLite Commands

```sql
-- List all tables
.tables

-- View schema
.schema jobs

-- Query jobs
SELECT * FROM jobs;

-- Query backup runs
SELECT * FROM backup_runs ORDER BY started_at DESC LIMIT 10;

-- Query snapshots
SELECT * FROM snapshots ORDER BY created_at DESC LIMIT 10;

-- Exit
.quit
```

---

## PostgreSQL (Docker/Production)

### Connection Details

When running with Docker Compose:
- **Host**: `localhost` (from host) or `db` (from within Docker network)
- **Port**: `5432`
- **Database**: `coldvault`
- **User**: `coldvault`
- **Password**: Set via `DB_PASSWORD` environment variable (default: `changeme`)

### Connection String Format

```
postgresql://coldvault:{DB_PASSWORD}@localhost:5432/coldvault
```

### Connection Methods

#### 1. Using psql Command Line

```bash
# From host machine
psql -h localhost -p 5432 -U coldvault -d coldvault

# Or using connection string
psql "postgresql://coldvault:changeme@localhost:5432/coldvault"
```

#### 2. From Within Docker Container

```bash
# Connect to the database container
docker exec -it coldvault-db psql -U coldvault -d coldvault

# Or connect to the app container and use psql
docker exec -it coldvault psql "postgresql://coldvault:changeme@db:5432/coldvault"
```

#### 3. Using Python (SQLAlchemy)

```python
from sqlalchemy import create_engine
from app.database import SessionLocal, Job, BackupRun

# Create connection
engine = create_engine("postgresql://coldvault:changeme@localhost:5432/coldvault")

# Use existing session
db = SessionLocal()
jobs = db.query(Job).all()
db.close()
```

#### 4. Using Database Browser Tools

**DBeaver**:
- Create new connection → PostgreSQL
- Host: `localhost`
- Port: `5432`
- Database: `coldvault`
- Username: `coldvault`
- Password: `changeme` (or your `DB_PASSWORD`)

**pgAdmin**:
- Download: https://www.pgadmin.org/
- Add server with connection details above

**TablePlus** (macOS):
- Download: https://tableplus.com/
- Create PostgreSQL connection with details above

### Common PostgreSQL Commands

```sql
-- List all tables
\dt

-- View table schema
\d jobs

-- Query jobs
SELECT * FROM jobs;

-- Query backup runs
SELECT * FROM backup_runs ORDER BY started_at DESC LIMIT 10;

-- Query snapshots
SELECT * FROM snapshots ORDER BY created_at DESC LIMIT 10;

-- Exit
\q
```

---

## Remote Database Connection via Tailscale

If your ColdVault database is running on a remote server accessible via Tailscale, you can connect from your Mac using the Tailscale network.

### Prerequisites

1. **Tailscale installed on both machines:**
   - Your Mac: Install from https://tailscale.com/download
   - Remote server: Install Tailscale and ensure it's connected

2. **Find the remote server's Tailscale address:**
   ```bash
   # On your Mac, list Tailscale devices
   tailscale status
   
   # Or get the IP/hostname from Tailscale admin console
   # https://login.tailscale.com/admin/machines
   ```

### PostgreSQL on Remote Server

#### Step 1: Configure PostgreSQL on Remote Server

On the remote server, you need to allow connections from Tailscale network:

1. **Edit PostgreSQL configuration:**
   ```bash
   # SSH into remote server
   ssh user@remote-server-tailscale-ip
   
   # If using Docker, edit postgresql.conf
   docker exec -it coldvault-db sh
   # Or if PostgreSQL is installed directly:
   sudo nano /etc/postgresql/15/main/postgresql.conf
   ```

2. **Update `postgresql.conf`:**
   ```conf
   # Allow connections from Tailscale network (100.x.x.x/10)
   listen_addresses = 'localhost,100.0.0.0/10'
   ```

3. **Update `pg_hba.conf` (host-based authentication):**
   ```bash
   # If using Docker:
   docker exec -it coldvault-db sh
   echo "host    all    all    100.0.0.0/10    md5" >> /var/lib/postgresql/data/pg_hba.conf
   
   # Or if installed directly:
   sudo nano /etc/postgresql/15/main/pg_hba.conf
   # Add line:
   # host    all    all    100.0.0.0/10    md5
   ```

4. **Restart PostgreSQL:**
   ```bash
   # If using Docker:
   docker-compose restart db
   
   # Or if installed directly:
   sudo systemctl restart postgresql
   ```

5. **Verify PostgreSQL is listening on Tailscale interface:**
   ```bash
   # On remote server
   sudo netstat -tlnp | grep 5432
   # Should show something like: 0.0.0.0:5432 or 100.x.x.x:5432
   ```

#### Step 2: Connect from Your Mac

**Using psql:**
```bash
# Install PostgreSQL client on Mac (if not already installed)
brew install postgresql@15

# Connect using Tailscale IP or hostname
psql -h remote-server-tailscale-ip -p 5432 -U coldvault -d coldvault

# Or using connection string
psql "postgresql://coldvault:your-password@remote-server-tailscale-ip:5432/coldvault"
```

**Using Python:**
```python
from sqlalchemy import create_engine
from app.database import SessionLocal, Job

# Replace with your remote server's Tailscale IP/hostname
REMOTE_HOST = "100.x.x.x"  # or "remote-server-name"
DB_PASSWORD = "your-password"

engine = create_engine(
    f"postgresql://coldvault:{DB_PASSWORD}@{REMOTE_HOST}:5432/coldvault"
)

# Test connection
db = SessionLocal()
jobs = db.query(Job).all()
print(f"Found {len(jobs)} jobs")
db.close()
```

**Using GUI Tools:**

**DBeaver:**
- Create new connection → PostgreSQL
- Host: `remote-server-tailscale-ip` (e.g., `100.64.1.2` or `remote-server-name`)
- Port: `5432`
- Database: `coldvault`
- Username: `coldvault`
- Password: Your `DB_PASSWORD`

**TablePlus (macOS):**
- New connection → PostgreSQL
- Host: `remote-server-tailscale-ip`
- Port: `5432`
- Database: `coldvault`
- Username: `coldvault`
- Password: Your `DB_PASSWORD`

**pgAdmin:**
- Add server → Connection tab
- Host: `remote-server-tailscale-ip`
- Port: `5432`
- Database: `coldvault`
- Username: `coldvault`
- Password: Your `DB_PASSWORD`

#### Step 3: Update Your Local .env (Optional)

If you want to connect your local development environment to the remote database:

```bash
# In your local .env file
DATABASE_URL=postgresql://coldvault:your-password@remote-server-tailscale-ip:5432/coldvault
```

Then your local app will connect to the remote database:
```bash
./dev.sh run
```

### SQLite on Remote Server

If the remote server uses SQLite, you'll need to access the database file via SSH:

#### Option 1: SSH Tunnel + Local SQLite Access

```bash
# Create SSH tunnel to access remote file system
ssh -L 2222:localhost:22 user@remote-server-tailscale-ip

# In another terminal, mount remote filesystem (macOS)
sshfs user@remote-server-tailscale-ip:/path/to/coldvault/config ./remote-config

# Now access SQLite database
sqlite3 ./remote-config/coldvault.db
```

#### Option 2: SSH + Remote SQLite Command

```bash
# Execute SQLite commands remotely
ssh user@remote-server-tailscale-ip "sqlite3 /path/to/coldvault/config/coldvault.db 'SELECT * FROM jobs;'"

# Or interactive session
ssh -t user@remote-server-tailscale-ip "sqlite3 /path/to/coldvault/config/coldvault.db"
```

#### Option 3: Copy Database Locally (Read-Only)

```bash
# Copy database file to local machine
scp user@remote-server-tailscale-ip:/path/to/coldvault/config/coldvault.db ./config/coldvault.db.remote

# Open locally
sqlite3 ./config/coldvault.db.remote
```

**Note:** If you modify the copied database, you'll need to copy it back, but this is not recommended for production databases.

### Troubleshooting Remote Connections

**Connection timeout:**
```bash
# Verify Tailscale connectivity
ping remote-server-tailscale-ip

# Check if Tailscale is running
tailscale status

# Verify PostgreSQL port is accessible
nc -zv remote-server-tailscale-ip 5432
```

**Authentication failed:**
- Verify password matches `DB_PASSWORD` on remote server
- Check `pg_hba.conf` allows connections from your Tailscale IP range
- Ensure PostgreSQL user exists: `docker exec -it coldvault-db psql -U postgres -c "\du"`

**Connection refused:**
- Verify PostgreSQL is listening on Tailscale interface (not just localhost)
- Check firewall rules on remote server
- Ensure Docker port mapping if using Docker: `docker-compose.yml` should expose port 5432

**Find your Tailscale IP:**
```bash
# On your Mac
tailscale ip

# On remote server
tailscale ip
```

**Test connection from remote server:**
```bash
# SSH into remote server first
ssh user@remote-server-tailscale-ip

# Test PostgreSQL connection locally on remote server
psql -h localhost -U coldvault -d coldvault

# Test from remote server to itself via Tailscale IP
psql -h $(tailscale ip -4) -U coldvault -d coldvault
```

### Security Considerations

1. **Use strong passwords:** Ensure `DB_PASSWORD` is secure
2. **Limit access:** Only allow connections from Tailscale network (100.0.0.0/10) in `pg_hba.conf`
3. **SSL/TLS:** Consider enabling SSL for PostgreSQL connections:
   ```conf
   # In postgresql.conf
   ssl = on
   ```
4. **Firewall:** Ensure your remote server's firewall allows Tailscale traffic
5. **Tailscale ACLs:** Use Tailscale ACLs to restrict which devices can access the database server

---

## Database Schema

### Main Tables

1. **jobs** - Backup job definitions
   - Columns: id, name, job_type, source_paths, schedule, s3_bucket, s3_prefix, storage_class, etc.

2. **backup_runs** - Individual backup execution records
   - Columns: id, job_id, status, started_at, completed_at, snapshot_id, size_bytes, etc.

3. **snapshots** - Backup snapshots metadata
   - Columns: id, job_id, backup_run_id, snapshot_id, s3_key, size_bytes, is_incremental, etc.

4. **notifications** - Notification records
   - Columns: id, job_id, notification_type, severity, message, sent_at, etc.

5. **storage_metrics** - Daily storage usage snapshots
   - Columns: id, recorded_at, total_size_bytes, monthly_cost_estimate, etc.

### View Full Schema

```python
from app.database import Base, engine
from sqlalchemy import inspect

inspector = inspect(engine)
for table_name in inspector.get_table_names():
    print(f"\n{table_name}:")
    for column in inspector.get_columns(table_name):
        print(f"  {column['name']}: {column['type']}")
```

---

## Troubleshooting

### SQLite Issues

**Database file not found:**
```bash
# Check if file exists
ls -la config/coldvault.db

# Check permissions
chmod 644 config/coldvault.db
```

**Database locked:**
- Ensure no other process is using the database
- Check if the application is running and holding a connection

### PostgreSQL Issues

**Connection refused:**
```bash
# Check if container is running
docker ps | grep coldvault-db

# Check container logs
docker logs coldvault-db

# Restart container
docker-compose restart db
```

**Authentication failed:**
- Verify `DB_PASSWORD` in `.env` matches the password used in connection string
- Check `POSTGRES_PASSWORD` in `docker-compose.yml`

**Database doesn't exist:**
```bash
# Connect to PostgreSQL and create database
docker exec -it coldvault-db psql -U coldvault -c "CREATE DATABASE coldvault;"
```

---

## Quick Reference

### Check Current Database Type

```python
from app.config import settings
print(settings.get_database_url())
```

### Switch Between SQLite and PostgreSQL

**To use SQLite:**
- Don't set `DATABASE_URL` in `.env` (or remove it)
- Don't set `POSTGRES_HOST` environment variable

**To use PostgreSQL:**
- Set `DATABASE_URL` in `.env`: `DATABASE_URL=postgresql://coldvault:changeme@localhost:5432/coldvault`
- Or set `POSTGRES_HOST=db` (for Docker)
- Ensure PostgreSQL is running

### Backup Database

**SQLite:**
```bash
cp config/coldvault.db config/coldvault.db.backup
```

**PostgreSQL:**
```bash
docker exec coldvault-db pg_dump -U coldvault coldvault > backup.sql
```

### Restore Database

**SQLite:**
```bash
cp config/coldvault.db.backup config/coldvault.db
```

**PostgreSQL:**
```bash
docker exec -i coldvault-db psql -U coldvault coldvault < backup.sql
```
