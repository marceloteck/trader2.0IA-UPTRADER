"""
Time filter: Block trading during low-probability windows.

Supports:
1. Fixed windows (BLOCKED_WINDOWS env)
2. Learned windows (from weekly report suggestions)
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger("trading_brains.filters")


class TimeFilter:
    """
    Block trading during specific hours/windows.
    
    Usage:
        filter = TimeFilter(
            enabled=True,
            blocked_windows=["09:00-09:15", "17:50-18:10"]
        )
        if filter.is_blocked(datetime.utcnow()):
            skip_trading = True
    """
    
    def __init__(
        self,
        enabled: bool = True,
        blocked_windows: Optional[List[str]] = None,
        allow_only_windows: Optional[List[str]] = None,
        db_path: Optional[str] = None
    ):
        """
        Initialize time filter.
        
        Args:
            enabled: Whether filter is active
            blocked_windows: List of "HH:MM-HH:MM" windows to block
            allow_only_windows: If set, only allow these windows (whitelist)
            db_path: Database path (for persistence)
        """
        self.enabled = enabled
        self.db_path = db_path
        self.allow_only_windows = allow_only_windows is not None
        
        self._blocked_ranges: List[Tuple[time, time]] = []
        self._allowed_ranges: List[Tuple[time, time]] = []
        
        if blocked_windows:
            self._parse_windows(blocked_windows, is_blocked=True)
        
        if allow_only_windows:
            self._parse_windows(allow_only_windows, is_blocked=False)
    
    def _parse_windows(
        self,
        windows: List[str],
        is_blocked: bool
    ) -> None:
        """
        Parse window strings "HH:MM-HH:MM".
        
        Args:
            windows: List of window strings
            is_blocked: If True, add to blocked list; if False, to allowed list
        """
        ranges = self._blocked_ranges if is_blocked else self._allowed_ranges
        
        for window_str in windows:
            try:
                start_str, end_str = window_str.strip().split("-")
                start_h, start_m = map(int, start_str.strip().split(":"))
                end_h, end_m = map(int, end_str.strip().split(":"))
                
                start = time(start_h, start_m)
                end = time(end_h, end_m)
                
                ranges.append((start, end))
                logger.info(
                    f"{'Blocked' if is_blocked else 'Allowed'} window: "
                    f"{start.isoformat()}-{end.isoformat()}"
                )
            except Exception as e:
                logger.warning(f"Could not parse window '{window_str}': {e}")
    
    def is_blocked(self, timestamp: Optional[datetime] = None) -> bool:
        """
        Check if trading is blocked at this time.
        
        Args:
            timestamp: Time to check (default: now)
        
        Returns:
            True if blocked, False if allowed
        """
        if not self.enabled:
            return False
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        current_time = timestamp.time()
        
        # Whitelist mode: allow only in specific windows
        if self.allow_only_windows:
            for start, end in self._allowed_ranges:
                if self._time_in_range(current_time, start, end):
                    return False
            return True  # Not in allowed windows → blocked
        
        # Blacklist mode: block specific windows
        for start, end in self._blocked_ranges:
            if self._time_in_range(current_time, start, end):
                return True
        
        return False
    
    @staticmethod
    def _time_in_range(current: time, start: time, end: time) -> bool:
        """Check if current time is between start and end."""
        if start <= end:
            return start <= current <= end
        else:
            # Range wraps around midnight (e.g., 23:00-02:00)
            return current >= start or current <= end
    
    def get_blocked_windows(self) -> List[str]:
        """Get list of blocked windows as strings."""
        return [
            f"{start.isoformat()}-{end.isoformat()}"
            for start, end in self._blocked_ranges
        ]
    
    def get_allowed_windows(self) -> List[str]:
        """Get list of allowed windows as strings."""
        return [
            f"{start.isoformat()}-{end.isoformat()}"
            for start, end in self._allowed_ranges
        ]
    
    def as_dict(self) -> Dict:
        """Export config as dict."""
        return {
            "enabled": self.enabled,
            "blocked_windows": self.get_blocked_windows(),
            "allowed_windows": self.get_allowed_windows(),
            "whitelist_mode": self.allow_only_windows
        }
