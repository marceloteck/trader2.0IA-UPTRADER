"""Tests for L1 time filter."""

import pytest
from datetime import datetime, time
from src.live import TimeFilter


def test_time_filter_blocked_window():
    """Test blocking specific time windows."""
    filter = TimeFilter(
        enabled=True,
        blocked_windows=["09:00-09:15", "17:50-18:10"]
    )
    
    # During blocked window
    blocked_time = datetime(2024, 1, 1, 9, 5)
    assert filter.is_blocked(blocked_time) is True
    
    # Outside blocked window
    allowed_time = datetime(2024, 1, 1, 10, 0)
    assert filter.is_blocked(allowed_time) is False


def test_time_filter_disabled():
    """Test that disabled filter allows all times."""
    filter = TimeFilter(enabled=False, blocked_windows=["09:00-09:15"])
    
    blocked_time = datetime(2024, 1, 1, 9, 5)
    assert filter.is_blocked(blocked_time) is False


def test_time_filter_whitelist_mode():
    """Test allow_only mode (whitelist)."""
    filter = TimeFilter(
        enabled=True,
        allow_only_windows=["10:00-17:00"]
    )
    
    # During allowed window
    allowed_time = datetime(2024, 1, 1, 14, 0)
    assert filter.is_blocked(allowed_time) is False
    
    # Outside allowed window
    blocked_time = datetime(2024, 1, 1, 9, 0)
    assert filter.is_blocked(blocked_time) is True


def test_time_filter_midnight_wrap():
    """Test windows that wrap around midnight."""
    filter = TimeFilter(
        enabled=True,
        blocked_windows=["23:00-02:00"]
    )
    
    # Before midnight
    assert filter.is_blocked(datetime(2024, 1, 1, 23, 30)) is True
    
    # After midnight
    assert filter.is_blocked(datetime(2024, 1, 2, 1, 30)) is True
    
    # During day
    assert filter.is_blocked(datetime(2024, 1, 2, 10, 0)) is False


def test_time_filter_get_blocked_windows():
    """Test retrieving blocked windows."""
    filter = TimeFilter(blocked_windows=["09:00-09:15", "17:50-18:10"])
    
    windows = filter.get_blocked_windows()
    
    assert len(windows) == 2
    assert "09:00:00-09:15:00" in windows


def test_time_filter_as_dict():
    """Test export to dict."""
    filter = TimeFilter(
        enabled=True,
        blocked_windows=["09:00-09:15"]
    )
    
    config = filter.as_dict()
    
    assert config["enabled"] is True
    assert len(config["blocked_windows"]) == 1
