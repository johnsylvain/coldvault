"""
Configuration settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )
    
    # Database
    database_url: Optional[str] = None
    database_password: str = "changeme"
    
    def get_database_url(self) -> str:
        """Get database URL, defaulting to SQLite or Postgres based on environment"""
        if self.database_url:
            return self.database_url
        # Check if we're in Docker with Postgres
        if os.getenv("POSTGRES_HOST"):
            return f"postgresql://coldvault:{self.database_password}@db:5432/coldvault"
        # Default to SQLite
        return "sqlite:///./config/coldvault.db"
    
    # AWS
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_s3_bucket: Optional[str] = None
    
    # Encryption
    encryption_key: Optional[str] = None
    
    # Paths
    config_path: str = "/config"
    cache_path: str = "/cache"
    
    # Notifications
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    webhook_url: Optional[str] = None
    
    # Logging
    log_level: str = "INFO"
    
    # Performance settings
    backup_scan_threads: int = 4  # Number of threads for file scanning (default: 4)
    backup_upload_threads: int = 4  # Number of threads for S3 uploads (default: 4)
    
    # S3 Upload Retry & Network Resilience
    s3_upload_max_retries: int = 5  # Maximum retry attempts for uploads (default: 5)
    s3_upload_retry_backoff_base: float = 2.0  # Base seconds for exponential backoff (default: 2.0)
    s3_upload_retry_backoff_max: float = 60.0  # Maximum backoff seconds (default: 60.0)
    s3_connect_timeout: int = 30  # Connection timeout in seconds (default: 30)
    s3_read_timeout: int = 300  # Read timeout in seconds (default: 300)
    s3_multipart_threshold: int = 8 * 1024 * 1024  # Size threshold for multipart uploads in bytes (default: 8MB)
    s3_multipart_chunksize: int = 8 * 1024 * 1024  # Chunk size for multipart uploads in bytes (default: 8MB)

settings = Settings()
