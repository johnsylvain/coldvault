"""
Restic backup engine for host-level backups
"""
import os
import subprocess
import logging
import json
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

class ResticBackupEngine:
    """Handles restic-based host backups"""
    
    def __init__(self):
        self.restic_binary = "/usr/bin/restic"
    
    def backup(self, job, backup_run, db, backup_logger=None, cancellation_flags=None, backup_run_id=None):
        """Execute a restic backup"""
        if backup_logger is None:
            backup_logger = logger
        
        def check_cancellation():
            """Check if backup should be cancelled"""
            if cancellation_flags and backup_run_id:
                if cancellation_flags.get(backup_run_id, False):
                    backup_logger.warning("Cancellation requested, stopping restic backup...")
                    raise InterruptedError("Backup cancelled by user")
        source_paths = json.loads(job.source_paths)
        snapshot_id = f"{job.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        backup_logger.info(f"Creating restic snapshot: {snapshot_id}")
        
        # Setup restic repository
        repo_url = f"s3:s3.amazonaws.com/{job.s3_bucket}/{job.s3_prefix}"
        backup_logger.info(f"Restic repository: {repo_url}")
        
        # Set environment variables for restic
        env = os.environ.copy()
        env["AWS_ACCESS_KEY_ID"] = settings.aws_access_key_id or ""
        env["AWS_SECRET_ACCESS_KEY"] = settings.aws_secret_access_key or ""
        env["RESTIC_PASSWORD"] = settings.encryption_key or ""
        
        # Initialize repository if needed
        backup_logger.info("Checking restic repository...")
        try:
            result = subprocess.run(
                [self.restic_binary, "snapshots", "--repo", repo_url],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            backup_logger.info("Repository exists and is accessible")
        except subprocess.CalledProcessError:
            # Repository doesn't exist, initialize it
            backup_logger.info(f"Initializing new restic repository at {repo_url}")
            result = subprocess.run(
                [self.restic_binary, "init", "--repo", repo_url],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            backup_logger.info("Repository initialized successfully")
        
        # Build restic backup command
        cmd = [self.restic_binary, "backup", "--repo", repo_url, "--verbose"]
        
        # Add source paths
        backup_logger.info(f"Backing up {len(source_paths)} source path(s)...")
        for path in source_paths:
            if os.path.exists(path):
                cmd.append(path)
                backup_logger.info(f"  - {path}")
            else:
                backup_logger.warning(f"  - {path} (does not exist, skipping)")
        
        # Add exclude patterns
        if job.exclude_patterns:
            exclude_list = json.loads(job.exclude_patterns)
            backup_logger.info(f"Exclude patterns: {exclude_list}")
            for pattern in exclude_list:
                cmd.extend(["--exclude", pattern])
        
        # Add tags
        cmd.extend(["--tag", f"job:{job.id}", "--tag", f"snapshot:{snapshot_id}"])
        
        # Execute backup
        check_cancellation()  # Check before starting
        
        backup_logger.info("Starting restic backup...")
        backup_logger.info(f"Command: {' '.join(cmd[:5])}... [paths]")  # Don't log full command with paths
        
        try:
            # Note: restic doesn't support graceful cancellation easily
            # We'll check before starting, but once restic starts, it will complete
            # For true cancellation, we'd need to kill the process (not implemented here)
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            
            # Log restic output
            if result.stdout:
                backup_logger.info("Restic output:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        backup_logger.info(f"  {line}")
            
            if result.stderr:
                backup_logger.warning("Restic warnings:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        backup_logger.warning(f"  {line}")
            
            # Parse output to get snapshot info
            # Restic outputs snapshot ID in the output
            output_lines = result.stdout.split('\n')
            snapshot_hash = None
            for line in output_lines:
                if "snapshot" in line.lower() and "saved" in line.lower():
                    # Extract snapshot hash
                    parts = line.split()
                    for part in parts:
                        if len(part) == 64:  # Restic snapshot IDs are 64 chars
                            snapshot_hash = part
                            break
            
            if not snapshot_hash:
                # Get latest snapshot
                snapshots_result = subprocess.run(
                    [self.restic_binary, "snapshots", "--repo", repo_url, "--json", "--last"],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True
                )
                if snapshots_result.stdout:
                    snapshots = json.loads(snapshots_result.stdout)
                    if snapshots:
                        snapshot_hash = snapshots[0].get("id")
            
            # Get snapshot stats
            stats_result = subprocess.run(
                [self.restic_binary, "stats", "--repo", repo_url, snapshot_hash or "latest"],
                env=env,
                check=True,
                capture_output=True,
                text=True
            )
            
            # Parse stats (rough estimate)
            total_size = 0
            file_count = 0
            for line in stats_result.stdout.split('\n'):
                if "Total Size" in line or "total size" in line.lower():
                    # Try to extract size
                    pass  # Would need to parse restic output
            
            return {
                "snapshot_id": snapshot_hash or snapshot_id,
                "size_bytes": total_size,
                "files_count": file_count,
                "s3_key": f"{job.s3_prefix}/restic/{snapshot_hash or snapshot_id}"
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Restic backup failed: {e.stderr}")
            raise Exception(f"Restic backup failed: {e.stderr}")
