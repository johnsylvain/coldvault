"""
Logging utilities for backup jobs
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from app.config import settings

class BackupLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory and writes to file"""
    
    def __init__(self, log_file_path: str):
        super().__init__()
        self.log_file_path = log_file_path
        self.logs = []
        self.file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        self.file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
    
    def emit(self, record):
        """Emit a log record"""
        # Format the log message
        msg = self.format(record)
        self.logs.append({
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': msg
        })
        
        # Also write to file
        self.file_handler.emit(record)
    
    def get_logs(self, limit: Optional[int] = None):
        """Get stored logs"""
        if limit:
            return self.logs[-limit:]
        return self.logs
    
    def close(self):
        """Close the handler"""
        self.file_handler.close()
        super().close()

def setup_backup_logger(backup_run_id: int, job_name: str) -> Tuple[logging.Logger, str]:
    """
    Set up a logger for a backup run
    
    Returns:
        tuple: (logger, log_file_path)
    """
    # Determine logs directory - check if config_path is writable
    logs_dir = None
    
    # Try settings.config_path first (works in Docker)
    if settings.config_path and os.path.exists(settings.config_path):
        try:
            # Check if we can write to it
            test_file = os.path.join(settings.config_path, ".test_write")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logs_dir = os.path.join(settings.config_path, "logs")
            except (OSError, PermissionError):
                pass
        except Exception:
            pass
    
    # Fall back to local config directory
    if not logs_dir:
        local_config = os.path.join(os.getcwd(), "config")
        if os.path.exists(local_config):
            try:
                test_file = os.path.join(local_config, ".test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logs_dir = os.path.join(local_config, "logs")
            except (OSError, PermissionError):
                pass
    
    # Last resort: use current directory
    if not logs_dir:
        logs_dir = os.path.join(os.getcwd(), "logs")
    
    # Create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create log file path
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    log_filename = f"backup_{backup_run_id}_{timestamp}.log"
    log_file_path = os.path.join(logs_dir, log_filename)
    
    # Create logger
    logger = logging.getLogger(f"backup_{backup_run_id}")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Add custom handler
    handler = BackupLogHandler(log_file_path)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(handler)
    
    # Store handler reference for later retrieval
    logger._backup_handler = handler
    
    return logger, log_file_path

def get_backup_logger(backup_run_id: int) -> Optional[logging.Logger]:
    """Get an existing backup logger"""
    logger_name = f"backup_{backup_run_id}"
    logger = logging.getLogger(logger_name)
    if hasattr(logger, '_backup_handler'):
        return logger
    return None
