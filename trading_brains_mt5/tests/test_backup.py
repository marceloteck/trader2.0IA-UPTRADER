"""Test database integrity and backup."""

import tempfile
import sqlite3
from pathlib import Path
from src.db.integrity import IntegrityChecker
from src.db.backup import DatabaseBackup


def test_integrity_check():
    """Test integrity checker."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create valid DB
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.close()
        
        # Check integrity
        checker = IntegrityChecker(db_path)
        assert checker.check()
        
        # Get stats
        stats = checker.get_stats()
        assert "page_count" in stats
        assert "size_mb" in stats
    
    finally:
        Path(db_path).unlink()


def test_database_backup():
    """Test backup creation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        backup_dir = Path(tmp_dir) / "backups"
        
        # Create test DB
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()
        
        # Create backup
        backup = DatabaseBackup(str(db_path), str(backup_dir), keep_n=3)
        backup_file = backup.backup()
        
        assert backup_file.exists()
        
        # List backups
        backups = backup.list_backups()
        assert len(backups) > 0
