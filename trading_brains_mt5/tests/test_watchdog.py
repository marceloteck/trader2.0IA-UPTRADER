"""Test watchdog module."""

import pytest
import time
from src.monitoring.watchdog import Watchdog


def test_watchdog_healthy():
    """Test healthy heartbeat."""
    wd = Watchdog(timeout=5)
    
    assert wd.is_healthy()
    
    wd.heartbeat()
    assert wd.is_healthy()


def test_watchdog_timeout_callback():
    """Test timeout callback."""
    called = []
    
    def on_timeout():
        called.append(True)
    
    wd = Watchdog(timeout=1, on_timeout=on_timeout)
    wd.start()
    
    time.sleep(1.5)
    # Callback should have been called
    
    wd.stop()


def test_watchdog_start_stop():
    """Test start/stop."""
    wd = Watchdog()
    
    wd.start()
    assert wd._running
    
    wd.stop()
    assert not wd._running
