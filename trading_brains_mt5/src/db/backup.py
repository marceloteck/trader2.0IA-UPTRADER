"""
Automatic database backup and log rotation.

Strategy:
- Backup before each major operation
- Keep last N backups
- VACUUM database weekly
- Rotate logs: keep last N MB or N days
"""

from __future__ import annotations

import shutil
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


logger = logging.getLogger("trading_brains.backup")


class DatabaseBackup:
    """
    Manage SQLite backups.
    
    Usage:
        backup = DatabaseBackup(db_path, backup_dir, keep_n=7)
        backup.backup()  # Create timestamped backup
        backup.cleanup()  # Remove old backups
    """
    
    def __init__(self, db_path: str, backup_dir: str, keep_n: int = 7):
        """
        Initialize backup manager.
        
        Args:
            db_path: Path to SQLite database
            backup_dir: Directory to store backups
            keep_n: Number of backups to keep
        """
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.keep_n = keep_n
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def backup(self) -> Path:
        """Create timestamped backup."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"trading_{timestamp}.db"
            
            shutil.copy2(self.db_path, str(backup_file))
            logger.info(f"Backup created: {backup_file}")
            
            self.cleanup()
            return backup_file
        
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise
    
    def cleanup(self) -> None:
        """Remove old backups, keeping last N."""
        try:
            backups = sorted(self.backup_dir.glob("trading_*.db"))
            
            if len(backups) > self.keep_n:
                to_remove = backups[:-self.keep_n]
                for f in to_remove:
                    f.unlink()
                    logger.info(f"Removed old backup: {f}")
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []
        for f in sorted(self.backup_dir.glob("trading_*.db")):
            stat = f.stat()
            backups.append({
                "path": str(f),
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        return backups
    
    def restore(self, backup_path: str) -> None:
        """Restore from backup."""
        try:
            src = Path(backup_path)
            if not src.exists():
                raise FileNotFoundError(f"Backup not found: {backup_path}")
            
            shutil.copy2(str(src), self.db_path)
            logger.info(f"Database restored from: {backup_path}")
        
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise


class LogRotator:
    """
    Rotate log files.
    
    Strategy:
    - Keep logs for last N days
    - Or keep last N MB total
    """
    
    def __init__(self, log_dir: str, keep_days: int = 30, keep_mb: int = 100):
        """
        Initialize log rotator.
        
        Args:
            log_dir: Directory with logs
            keep_days: Keep logs from last N days
            keep_mb: Keep total size under N MB
        """
        self.log_dir = Path(log_dir)
        self.keep_days = keep_days
        self.keep_mb = keep_mb
    
    def rotate(self) -> None:
        """Remove old logs."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.keep_days)
            
            logs = list(self.log_dir.glob("*.log"))
            total_size = 0
            
            # Remove by age
            for log_file in logs:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff:
                    log_file.unlink()
                    logger.info(f"Removed old log: {log_file}")
                else:
                    total_size += log_file.stat().st_size
            
            # Remove by total size
            size_mb = total_size / (1024 * 1024)
            if size_mb > self.keep_mb:
                logs = sorted(
                    self.log_dir.glob("*.log"),
                    key=lambda x: x.stat().st_mtime
                )
                for log_file in logs:
                    if size_mb <= self.keep_mb:
                        break
                    size = log_file.stat().st_size
                    log_file.unlink()
                    size_mb -= size / (1024 * 1024)
                    logger.info(f"Removed log (size limit): {log_file}")
        
        except Exception as e:
            logger.error(f"Log rotation failed: {e}")
