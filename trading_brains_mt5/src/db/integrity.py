"""
Database integrity checks and automatic repair.

Strategy:
- Run PRAGMA integrity_check periodically
- If fails, pause trading and alert
- Backup before repair
- Keep log of integrity checks
"""

from __future__ import annotations

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


logger = logging.getLogger("trading_brains.integrity")


class IntegrityChecker:
    """
    Verify database integrity.
    
    Usage:
        checker = IntegrityChecker(db_path)
        if not checker.check():
            # Alert and pause trading
    """
    
    def __init__(self, db_path: str):
        """Initialize checker."""
        self.db_path = db_path
    
    def check(self) -> bool:
        """
        Run PRAGMA integrity_check.
        
        Returns True if OK, False if corrupted.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA integrity_check")
            results = cursor.fetchall()
            
            conn.close()
            
            # integrity_check returns [(ok,)] if OK, else errors
            if results[0][0] == "ok":
                logger.info("Database integrity check: OK")
                return True
            else:
                logger.error(f"Database integrity check FAILED: {results}")
                return False
        
        except Exception as e:
            logger.error(f"Integrity check error: {e}")
            return False
    
    def vacuum(self) -> bool:
        """Compress and optimize database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()
            logger.info("Database VACUUM completed")
            return True
        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database stats."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Page count
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            # Page size
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            # Table count
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            )
            table_count = cursor.fetchone()[0]
            
            conn.close()
            
            size_mb = (page_count * page_size) / (1024 * 1024)
            
            return {
                "page_count": page_count,
                "page_size": page_size,
                "size_mb": size_mb,
                "table_count": table_count
            }
        
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
