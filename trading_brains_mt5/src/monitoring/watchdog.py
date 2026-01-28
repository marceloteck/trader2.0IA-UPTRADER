"""
Watchdog: monitor loop health, detect stalls, trigger restart.

Strategy:
- Heartbeat: each main loop iteration updates timestamp
- Check every N seconds: if no heartbeat, log and signal restart
- Safe exit: flush DB, close connections, exit cleanly
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Callable, Optional, Dict, Any
from datetime import datetime


logger = logging.getLogger("trading_brains.watchdog")


class Watchdog:
    """
    Monitor loop execution.
    
    Usage:
        wd = Watchdog(timeout=30, on_timeout=restart_callback)
        wd.start()
        
        while trading:
            wd.heartbeat()
            # ... do work
            time.sleep(1)
        
        wd.stop()
    """
    
    def __init__(
        self,
        timeout: int = 30,
        on_timeout: Optional[Callable] = None
    ):
        """
        Initialize watchdog.
        
        Args:
            timeout: Seconds without heartbeat before triggering timeout
            on_timeout: Callback to invoke on timeout
        """
        self.timeout = timeout
        self.on_timeout = on_timeout
        self._last_heartbeat = time.time()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def heartbeat(self) -> None:
        """Signal that loop is alive."""
        with self._lock:
            self._last_heartbeat = time.time()
    
    def start(self) -> None:
        """Start watchdog monitor thread."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Watchdog started (timeout={self.timeout}s)")
    
    def stop(self) -> None:
        """Stop watchdog."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Watchdog stopped")
    
    def _monitor_loop(self) -> None:
        """Monitor thread: check heartbeat periodically."""
        while self._running:
            time.sleep(5)  # Check every 5 seconds
            
            with self._lock:
                elapsed = time.time() - self._last_heartbeat
            
            if elapsed > self.timeout:
                logger.error(
                    f"Watchdog: No heartbeat for {elapsed:.1f}s (timeout={self.timeout}s)"
                )
                if self.on_timeout:
                    self.on_timeout()
                self._running = False
                return
    
    def is_healthy(self) -> bool:
        """Check if heartbeat is still fresh."""
        with self._lock:
            elapsed = time.time() - self._last_heartbeat
        return elapsed < self.timeout
    
    def get_status(self) -> Dict[str, Any]:
        """Get watchdog status."""
        with self._lock:
            elapsed = time.time() - self._last_heartbeat
        
        return {
            "running": self._running,
            "last_heartbeat": datetime.fromtimestamp(self._last_heartbeat).isoformat(),
            "seconds_since_heartbeat": elapsed,
            "is_healthy": self.is_healthy()
        }
