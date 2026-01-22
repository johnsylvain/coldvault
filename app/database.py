"""
Database models and session management
"""
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Text, Float, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Create engine
database_url = settings.get_database_url()
if database_url.startswith("sqlite"):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class JobType(enum.Enum):
    DATASET = "dataset"
    HOST = "host"

class StorageClass(enum.Enum):
    STANDARD = "STANDARD"
    GLACIER_IR = "GLACIER_IR"
    GLACIER_FLEXIBLE = "GLACIER_FLEXIBLE"
    DEEP_ARCHIVE = "DEEP_ARCHIVE"

class BackupStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    job_type = Column(SQLEnum(JobType), nullable=False)
    description = Column(Text)
    
    # Source paths (JSON array)
    source_paths = Column(Text, nullable=False)
    
    # Schedule (cron expression)
    schedule = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    
    # Storage configuration
    s3_bucket = Column(String, nullable=False)
    s3_prefix = Column(String, nullable=False)
    storage_class = Column(SQLEnum(StorageClass), default=StorageClass.DEEP_ARCHIVE)
    
    # Retention
    keep_last_n = Column(Integer, default=30)
    gfs_daily = Column(Integer, default=7)
    gfs_weekly = Column(Integer, default=4)
    gfs_monthly = Column(Integer, default=12)
    
    # Include/exclude patterns (JSON)
    include_patterns = Column(Text)
    exclude_patterns = Column(Text)
    
    # Bandwidth and resource limits
    bandwidth_limit = Column(Integer)  # bytes per second
    cpu_priority = Column(Integer, default=5)  # 0-10
    
    # Encryption
    encryption_enabled = Column(Boolean, default=True)
    
    # Incremental backups
    incremental_enabled = Column(Boolean, default=True)  # Use incremental backups by default
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Last run info
    last_run_at = Column(DateTime)
    last_run_status = Column(SQLEnum(BackupStatus))
    next_run_at = Column(DateTime)

class BackupRun(Base):
    __tablename__ = "backup_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True, nullable=False)
    
    # Run metadata
    status = Column(SQLEnum(BackupStatus), default=BackupStatus.PENDING)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Backup details
    snapshot_id = Column(String, unique=True, index=True)
    size_bytes = Column(BigInteger)  # Changed from Integer to support large backups (>2GB)
    files_count = Column(Integer)
    
    # S3 details
    s3_key = Column(String)
    storage_class = Column(SQLEnum(StorageClass))
    
    # Error info
    error_message = Column(Text)
    log_path = Column(String)
    
    # Manual trigger
    manual_trigger = Column(Boolean, default=False)

class Snapshot(Base):
    __tablename__ = "snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True, nullable=False)
    backup_run_id = Column(Integer, index=True)
    
    snapshot_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Snapshot metadata
    size_bytes = Column(BigInteger)  # Changed from Integer to support large backups (>2GB)
    files_count = Column(Integer)
    
    # S3 location
    s3_key = Column(String, nullable=False)
    manifest_key = Column(String)  # For incremental backups
    storage_class = Column(SQLEnum(StorageClass))
    
    # Incremental backup info
    is_incremental = Column(Boolean, default=False)
    files_unchanged = Column(Integer)  # Number of files that didn't change
    
    # Retention
    retained = Column(Boolean, default=True)
    retention_reason = Column(String)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True)
    backup_run_id = Column(Integer, index=True)
    
    notification_type = Column(String, nullable=False)  # failure, missed_schedule, verification_failure, cost_threshold
    severity = Column(String, default="info")  # info, warning, error
    
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    
    # Delivery channels
    email_sent = Column(Boolean, default=False)
    webhook_sent = Column(Boolean, default=False)

class StorageMetrics(Base):
    """Daily snapshots of storage usage and costs"""
    __tablename__ = "storage_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Total storage by class (bytes)
    total_size_bytes = Column(Integer, default=0)
    size_standard_bytes = Column(Integer, default=0)
    size_glacier_ir_bytes = Column(Integer, default=0)
    size_glacier_flexible_bytes = Column(Integer, default=0)
    size_deep_archive_bytes = Column(Integer, default=0)
    
    # Total files
    total_files = Column(Integer, default=0)
    
    # Calculated costs (monthly, in USD)
    monthly_cost_estimate = Column(Float, default=0.0)
    cost_standard = Column(Float, default=0.0)
    cost_glacier_ir = Column(Float, default=0.0)
    cost_glacier_flexible = Column(Float, default=0.0)
    cost_deep_archive = Column(Float, default=0.0)
    
    # Per-job breakdown (JSON)
    job_breakdown = Column(Text)  # JSON: {job_id: {size_bytes, cost, storage_class}}

def get_db():
    """Dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_database():
    """Run database migrations for schema changes"""
    from sqlalchemy import inspect, text
    
    # Check if we're using SQLite
    if not database_url.startswith("sqlite"):
        # For PostgreSQL, use Alembic or manual migrations
        return
    
    conn = engine.connect()
    try:
        # Check if incremental_enabled column exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('jobs')]
        
        if 'incremental_enabled' not in columns:
            logger.info("Adding incremental_enabled column to jobs table...")
            conn.execute(text("ALTER TABLE jobs ADD COLUMN incremental_enabled BOOLEAN DEFAULT 1"))
            conn.commit()
            logger.info("Migration complete: added incremental_enabled column")
        
        # Check if manifest_key and is_incremental columns exist in snapshots
        snapshot_columns = [col['name'] for col in inspector.get_columns('snapshots')]
        
        if 'manifest_key' not in snapshot_columns:
            logger.info("Adding manifest_key column to snapshots table...")
            conn.execute(text("ALTER TABLE snapshots ADD COLUMN manifest_key VARCHAR"))
            conn.commit()
            logger.info("Migration complete: added manifest_key column")
        
        if 'is_incremental' not in snapshot_columns:
            logger.info("Adding is_incremental column to snapshots table...")
            conn.execute(text("ALTER TABLE snapshots ADD COLUMN is_incremental BOOLEAN DEFAULT 0"))
            conn.commit()
            logger.info("Migration complete: added is_incremental column")
        
        if 'files_unchanged' not in snapshot_columns:
            logger.info("Adding files_unchanged column to snapshots table...")
            conn.execute(text("ALTER TABLE snapshots ADD COLUMN files_unchanged INTEGER"))
            conn.commit()
            logger.info("Migration complete: added files_unchanged column")
        
        # Check if storage_metrics table exists
        tables = inspector.get_table_names()
        if 'storage_metrics' not in tables:
            logger.info("Creating storage_metrics table...")
            conn.execute(text("""
                CREATE TABLE storage_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at DATETIME NOT NULL,
                    total_size_bytes INTEGER DEFAULT 0,
                    size_standard_bytes INTEGER DEFAULT 0,
                    size_glacier_ir_bytes INTEGER DEFAULT 0,
                    size_glacier_flexible_bytes INTEGER DEFAULT 0,
                    size_deep_archive_bytes INTEGER DEFAULT 0,
                    total_files INTEGER DEFAULT 0,
                    monthly_cost_estimate REAL DEFAULT 0.0,
                    cost_standard REAL DEFAULT 0.0,
                    cost_glacier_ir REAL DEFAULT 0.0,
                    cost_glacier_flexible REAL DEFAULT 0.0,
                    cost_deep_archive REAL DEFAULT 0.0,
                    job_breakdown TEXT
                )
            """))
            conn.execute(text("CREATE INDEX idx_storage_metrics_recorded_at ON storage_metrics(recorded_at)"))
            conn.commit()
            logger.info("Migration complete: created storage_metrics table")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
