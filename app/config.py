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

settings = Settings()
