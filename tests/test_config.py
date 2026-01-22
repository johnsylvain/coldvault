"""
Tests for configuration module
"""
import pytest
import os
from app.config import Settings


class TestSettings:
    """Test Settings class"""
    
    def test_default_database_url(self):
        """Test default database URL generation"""
        settings = Settings()
        db_url = settings.get_database_url()
        assert db_url is not None
        assert "sqlite" in db_url or "postgresql" in db_url
    
    def test_custom_database_url(self):
        """Test custom database URL"""
        settings = Settings(database_url="postgresql://user:pass@localhost/db")
        assert settings.get_database_url() == "postgresql://user:pass@localhost/db"
    
    def test_postgres_database_url_from_env(self, monkeypatch):
        """Test PostgreSQL URL generation from environment"""
        monkeypatch.setenv("POSTGRES_HOST", "db")
        settings = Settings(database_password="testpass")
        db_url = settings.get_database_url()
        assert "postgresql" in db_url
        assert "db" in db_url
        assert "testpass" in db_url
    
    def test_default_values(self):
        """Test default configuration values"""
        settings = Settings()
        assert settings.aws_region == "us-east-1"
        assert settings.smtp_port == 587
        assert settings.log_level == "INFO"
        assert settings.backup_scan_threads == 4
        assert settings.backup_upload_threads == 4
    
    def test_optional_fields(self):
        """Test that optional fields can be None"""
        settings = Settings()
        assert settings.aws_access_key_id is None or isinstance(settings.aws_access_key_id, str)
        assert settings.aws_secret_access_key is None or isinstance(settings.aws_secret_access_key, str)
        assert settings.encryption_key is None or isinstance(settings.encryption_key, str)
