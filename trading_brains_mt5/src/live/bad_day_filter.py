"""
Bad day filter: Auto-pause trading if losing pattern detected.

Triggers:
1. Loss limit: First N trades lose more than MAX_LOSS
2. Consecutive losses: K consecutive losing trades
3. Win rate: Win rate below threshold in window
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger("trading_brains.filters")


@dataclass
class DailyStats:
    """Daily trading statistics."""
    date: str
    trades_count: int
    pnl: float
    wins: int
    losses: int
    consecutive_losses: int
    max_loss: float
    paused: bool
    pause_reason: Optional[str] = None


class BadDayFilter:
    """
    Detect and pause trading on bad-luck days.
    
    Usage:
        filter = BadDayFilter(
            first_n=5, max_loss=-100, min_winrate=0.4,
            consecutive_max=3
        )
        paused, reason = filter.check(trade_pnl=pnl)
        if paused:
            skip_trading = True
    """
    
    def __init__(
        self,
        enabled: bool = True,
        first_n_trades: int = 5,
        max_daily_loss: float = -100.0,
        min_winrate: float = 0.4,
        consecutive_losses_max: int = 3,
        db_path: Optional[str] = None
    ):
        """
        Initialize bad day filter.
        
        Args:
            enabled: Whether filter is active
            first_n_trades: Check loss limit on first N trades of day
            max_daily_loss: Max loss allowed in first N trades
            min_winrate: Minimum win rate before pause
            consecutive_losses_max: Max consecutive losses before pause
            db_path: Database path (for persistence)
        """
        self.enabled = enabled
        self.first_n_trades = first_n_trades
        self.max_daily_loss = max_daily_loss
        self.min_winrate = min_winrate
        self.consecutive_losses_max = consecutive_losses_max
        self.db_path = db_path
        
        # Daily state (reset every 24h or day boundary)
        self.daily_trades: List[Tuple[float, str]] = []  # (pnl, timestamp)
        self.consecutive_losses = 0
        self.paused_until: Optional[datetime] = None
        self.last_pause_reason: Optional[str] = None
        self.current_date: Optional[str] = None
    
    def check(
        self,
        trade_pnl: float,
        timestamp: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trading should be paused.
        
        Args:
            trade_pnl: PnL of the just-closed trade
            timestamp: Time of trade close
            symbol: Trading symbol
        
        Returns:
            (should_pause, reason)
        """
        if not self.enabled:
            return False, None
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Reset stats on new day
        date_key = timestamp.strftime("%Y-%m-%d")
        if date_key != self.current_date:
            self.daily_trades = []
            self.consecutive_losses = 0
            self.current_date = date_key
        
        # Check if currently paused
        if self.paused_until and timestamp < self.paused_until:
            return True, f"Paused until {self.paused_until.isoformat()}"
        else:
            self.paused_until = None
        
        # Record trade
        self.daily_trades.append((trade_pnl, timestamp.isoformat()))
        
        # Update consecutive losses
        if trade_pnl < -1e-4:  # Loss (accounting for floating point)
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Check trigger 1: Consecutive losses
        if self.consecutive_losses >= self.consecutive_losses_max:
            return self._pause(
                f"CONSECUTIVE_LOSSES:{self.consecutive_losses}",
                timestamp
            )
        
        # Check trigger 2: Loss limit in first N trades
        if len(self.daily_trades) <= self.first_n_trades:
            daily_pnl = sum(pnl for pnl, _ in self.daily_trades)
            if daily_pnl <= self.max_daily_loss:
                return self._pause(
                    f"LOSS_LIMIT:{daily_pnl:.2f}",
                    timestamp
                )
        
        # Check trigger 3: Win rate in sliding window
        if len(self.daily_trades) >= 5:
            recent_trades = self.daily_trades[-5:]
            wins = sum(1 for pnl, _ in recent_trades if pnl > 1e-4)
            win_rate = wins / len(recent_trades)
            
            if win_rate < self.min_winrate:
                return self._pause(
                    f"WIN_RATE:{win_rate:.2%}",
                    timestamp
                )
        
        return False, None
    
    def _pause(
        self,
        reason: str,
        timestamp: datetime
    ) -> Tuple[bool, str]:
        """
        Pause trading for rest of day.
        
        Args:
            reason: Pause reason code
            timestamp: Time of pause
        
        Returns:
            (True, reason)
        """
        # Pause until 24h later or end of day (e.g., 17:00 UTC)
        self.paused_until = timestamp.replace(
            hour=17, minute=0, second=0, microsecond=0
        )
        if self.paused_until < timestamp:
            self.paused_until += timedelta(days=1)
        
        self.last_pause_reason = reason
        logger.warning(f"BadDayFilter PAUSE: {reason} at {timestamp.isoformat()}")
        
        return True, reason
    
    def reset(self) -> None:
        """Manually reset filter (e.g., on new day)."""
        self.daily_trades = []
        self.consecutive_losses = 0
        self.paused_until = None
        self.last_pause_reason = None
        self.current_date = None
    
    def get_stats(self) -> DailyStats:
        """Get current daily statistics."""
        if not self.current_date:
            return DailyStats(
                date="",
                trades_count=0,
                pnl=0.0,
                wins=0,
                losses=0,
                consecutive_losses=0,
                max_loss=0.0,
                paused=False
            )
        
        pnls = [pnl for pnl, _ in self.daily_trades]
        wins = sum(1 for p in pnls if p > 1e-4)
        losses = sum(1 for p in pnls if p < -1e-4)
        
        return DailyStats(
            date=self.current_date,
            trades_count=len(pnls),
            pnl=sum(pnls),
            wins=wins,
            losses=losses,
            consecutive_losses=self.consecutive_losses,
            max_loss=min(pnls) if pnls else 0.0,
            paused=self.paused_until is not None,
            pause_reason=self.last_pause_reason
        )
    
    def as_dict(self) -> Dict:
        """Export config as dict."""
        return {
            "enabled": self.enabled,
            "first_n_trades": self.first_n_trades,
            "max_daily_loss": self.max_daily_loss,
            "min_winrate": self.min_winrate,
            "consecutive_losses_max": self.consecutive_losses_max
        }
