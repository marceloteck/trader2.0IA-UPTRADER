"""
Risk Manager V4 - Professional risk controls, circuit breakers, and position sizing.

Features:
- Daily loss limit (hard stop)
- Daily profit target (optional)
- Max trades per day/hour
- Consecutive loss detection
- Volatility circuit breaker
- Brain divergence detection
- Automatic degrade on drawdown
- Cooldown between trades
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    passed: bool
    reason: str = ""
    metrics: Dict = field(default_factory=dict)


@dataclass
class RiskEvent:
    """Risk event for logging."""
    timestamp: datetime
    event_type: str  # DAILY_LOSS_LIMIT, MAX_TRADES_HOUR, etc
    details: Dict
    action: str  # PAUSE, REDUCE, ALLOW, etc


class RiskManager:
    """
    Professional risk management with multiple circuit breakers.
    """
    
    def __init__(self, settings, db_repo=None):
        """
        Initialize risk manager.
        
        Args:
            settings: Configuration settings
            db_repo: Optional DB repo for logging events
        """
        self.settings = settings
        self.db_repo = db_repo
        
        # Daily limits
        self.daily_loss_limit = float(settings.get('DAILY_LOSS_LIMIT', '1000'))
        self.daily_profit_target = float(settings.get('DAILY_PROFIT_TARGET', '0'))
        self.max_trades_per_day = int(settings.get('MAX_TRADES_PER_DAY', '20'))
        self.max_trades_per_hour = int(settings.get('MAX_TRADES_PER_HOUR', '3'))
        
        # Loss protection
        self.max_consecutive_losses = int(settings.get('MAX_CONSECUTIVE_LOSSES', '3'))
        
        # Cooldown between trades
        self.cooldown_seconds = int(settings.get('COOLDOWN_SECONDS', '180'))
        
        # Volatility thresholds
        self.max_atr_pct = float(settings.get('MAX_ATR_PCT', '5.0'))
        
        # Brain divergence
        self.max_brain_divergence = float(settings.get('MAX_BRAIN_DIVERGENCE', '0.3'))
        
        # Degrade on drawdown
        self.degrade_steps = int(settings.get('DEGRADE_STEPS', '3'))
        self.degrade_factor = float(settings.get('DEGRADE_FACTOR', '0.5'))
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.hourly_trade_count = 0
        self.last_hour = datetime.utcnow().hour
        self.last_trade_time: Optional[datetime] = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.max_daily_drawdown = 0.0
        self.degrade_level = 0  # 0-3, reduces position size
        
        # Status
        self.paused = False
        self.pause_reason = ""
        
        logger.info(f"RiskManager initialized: daily_loss_limit={self.daily_loss_limit}, "
                   f"max_trades_hour={self.max_trades_per_hour}")
    
    def check_can_trade(
        self,
        brain_scores: Dict[str, float],
        volatility: Optional[float] = None,
        atr: Optional[float] = None,
        close_price: Optional[float] = None
    ) -> RiskCheckResult:
        """
        Comprehensive risk check before placing a trade.
        
        Returns:
            RiskCheckResult with passed=True/False and reason
        """
        # Check if paused
        if self.paused:
            return RiskCheckResult(
                passed=False,
                reason=f"System paused: {self.pause_reason}"
            )
        
        # Check daily loss limit
        result = self._check_daily_loss()
        if not result.passed:
            return result
        
        # Check daily profit target
        if self.daily_profit_target > 0:
            result = self._check_daily_profit()
            if not result.passed:
                return result
        
        # Check max trades per day
        result = self._check_max_trades_day()
        if not result.passed:
            return result
        
        # Check max trades per hour
        result = self._check_max_trades_hour()
        if not result.passed:
            return result
        
        # Check cooldown
        result = self._check_cooldown()
        if not result.passed:
            return result
        
        # Check consecutive losses
        result = self._check_consecutive_losses()
        if not result.passed:
            return result
        
        # Check volatility
        if atr is not None and close_price is not None:
            result = self._check_volatility(atr, close_price)
            if not result.passed:
                return result
        
        # Check brain divergence
        result = self._check_brain_divergence(brain_scores)
        if not result.passed:
            return result
        
        return RiskCheckResult(passed=True, reason="All checks passed")
    
    def _check_daily_loss(self) -> RiskCheckResult:
        """Check if daily loss limit exceeded."""
        if self.daily_pnl <= -self.daily_loss_limit:
            self.paused = True
            self.pause_reason = f"Daily loss limit exceeded: {self.daily_pnl:.2f}"
            self._log_event(RiskEvent(
                timestamp=datetime.utcnow(),
                event_type='DAILY_LOSS_LIMIT',
                details={'limit': self.daily_loss_limit, 'current': self.daily_pnl},
                action='PAUSE'
            ))
            return RiskCheckResult(passed=False, reason=self.pause_reason)
        return RiskCheckResult(passed=True)
    
    def _check_daily_profit(self) -> RiskCheckResult:
        """Check if daily profit target reached."""
        if self.daily_pnl >= self.daily_profit_target:
            self.paused = True
            self.pause_reason = f"Daily profit target reached: {self.daily_pnl:.2f}"
            self._log_event(RiskEvent(
                timestamp=datetime.utcnow(),
                event_type='DAILY_PROFIT_TARGET',
                details={'target': self.daily_profit_target, 'current': self.daily_pnl},
                action='PAUSE'
            ))
            return RiskCheckResult(passed=False, reason=self.pause_reason)
        return RiskCheckResult(passed=True)
    
    def _check_max_trades_day(self) -> RiskCheckResult:
        """Check max trades per day."""
        if self.daily_trade_count >= self.max_trades_per_day:
            return RiskCheckResult(
                passed=False,
                reason=f"Max trades per day reached: {self.daily_trade_count}/{self.max_trades_per_day}"
            )
        return RiskCheckResult(passed=True)
    
    def _check_max_trades_hour(self) -> RiskCheckResult:
        """Check max trades per hour."""
        # Reset hourly counter if hour changed
        current_hour = datetime.utcnow().hour
        if current_hour != self.last_hour:
            self.hourly_trade_count = 0
            self.last_hour = current_hour
        
        if self.hourly_trade_count >= self.max_trades_per_hour:
            return RiskCheckResult(
                passed=False,
                reason=f"Max trades per hour reached: {self.hourly_trade_count}/{self.max_trades_per_hour}"
            )
        return RiskCheckResult(passed=True)
    
    def _check_cooldown(self) -> RiskCheckResult:
        """Check cooldown between trades."""
        if self.last_trade_time is None:
            return RiskCheckResult(passed=True)
        
        elapsed = (datetime.utcnow() - self.last_trade_time).total_seconds()
        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            return RiskCheckResult(
                passed=False,
                reason=f"Cooldown active: {remaining:.0f}s remaining"
            )
        return RiskCheckResult(passed=True)
    
    def _check_consecutive_losses(self) -> RiskCheckResult:
        """Check for too many consecutive losses."""
        if self.consecutive_losses >= self.max_consecutive_losses:
            action = "REDUCE"
            if self.degrade_level < self.degrade_steps:
                self._apply_degrade()
                msg = f"Degrade applied: level {self.degrade_level}"
            else:
                action = "PAUSE"
                self.paused = True
                self.pause_reason = f"Max consecutive losses: {self.consecutive_losses}"
                msg = f"System paused after {self.consecutive_losses} losses"
            
            return RiskCheckResult(
                passed=False,
                reason=msg
            )
        return RiskCheckResult(passed=True)
    
    def _check_volatility(self, atr: float, close_price: float) -> RiskCheckResult:
        """Check if volatility is too high."""
        if close_price <= 0:
            return RiskCheckResult(passed=True)
        
        atr_pct = (atr / close_price) * 100
        
        if atr_pct > self.max_atr_pct:
            self._log_event(RiskEvent(
                timestamp=datetime.utcnow(),
                event_type='VOLATILITY_HIGH',
                details={'atr_pct': atr_pct, 'threshold': self.max_atr_pct},
                action='REDUCE'
            ))
            return RiskCheckResult(
                passed=False,
                reason=f"Volatility too high: {atr_pct:.1f}% (limit {self.max_atr_pct}%)"
            )
        return RiskCheckResult(passed=True)
    
    def _check_brain_divergence(self, brain_scores: Dict[str, float]) -> RiskCheckResult:
        """Check if brains are too divergent (conflict)."""
        if len(brain_scores) < 2:
            return RiskCheckResult(passed=True)
        
        scores = list(brain_scores.values())
        max_score = max(scores)
        min_score = min(scores)
        
        if max_score <= 0:
            return RiskCheckResult(passed=True)  # All scores negative
        
        divergence = (max_score - min_score) / max_score
        
        if divergence > self.max_brain_divergence:
            self._log_event(RiskEvent(
                timestamp=datetime.utcnow(),
                event_type='BRAIN_DIVERGENCE',
                details={'divergence': divergence, 'threshold': self.max_brain_divergence},
                action='REDUCE'
            ))
            return RiskCheckResult(
                passed=False,
                reason=f"Brains divergent: {divergence:.1%} (limit {self.max_brain_divergence:.1%})"
            )
        return RiskCheckResult(passed=True)
    
    def record_trade(self, side: str, volume: float, entry: float, exit_price: float):
        """Record trade for risk tracking."""
        pnl = (exit_price - entry) * volume
        if side == "SELL":
            pnl = -pnl
        
        self.daily_pnl += pnl
        self.daily_trade_count += 1
        self.hourly_trade_count += 1
        self.last_trade_time = datetime.utcnow()
        
        # Track drawdown
        if self.daily_pnl < self.max_daily_drawdown:
            self.max_daily_drawdown = self.daily_pnl
        
        # Track consecutive wins/losses
        if pnl >= 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
            # Check if should degrade
            if self.consecutive_losses >= self.max_consecutive_losses:
                if self.degrade_level < self.degrade_steps:
                    self._apply_degrade()
        
        logger.info(f"Trade recorded: PnL={pnl:.2f}, daily={self.daily_pnl:.2f}, "
                   f"consecutive_losses={self.consecutive_losses}")
    
    def _apply_degrade(self):
        """Reduce position size by one step."""
        if self.degrade_level < self.degrade_steps:
            self.degrade_level += 1
            logger.warning(f"Degrade applied: level {self.degrade_level}")
            self._log_event(RiskEvent(
                timestamp=datetime.utcnow(),
                event_type='DEGRADE_APPLIED',
                details={'level': self.degrade_level, 'factor': self.degrade_factor},
                action='REDUCE'
            ))
    
    def get_position_size_factor(self) -> float:
        """
        Get position size multiplier based on degrade level.
        
        Returns:
            Multiplier (1.0 = full size, 0.5 = half, 0.25 = quarter, etc)
        """
        if self.degrade_level == 0:
            return 1.0
        return self.degrade_factor ** self.degrade_level
    
    def reset_daily(self):
        """Reset daily counters (call at end of trading day)."""
        logger.info(f"Daily reset: pnl={self.daily_pnl:.2f}, trades={self.daily_trade_count}, "
                   f"max_dd={self.max_daily_drawdown:.2f}")
        
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.hourly_trade_count = 0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.max_daily_drawdown = 0.0
        
        # Gradually recover degrade level
        if self.degrade_level > 0:
            self.degrade_level = max(0, self.degrade_level - 1)
            logger.info(f"Degrade reduced to level {self.degrade_level}")
        
        self.paused = False
        self.pause_reason = ""
    
    def _log_event(self, event: RiskEvent):
        """Log risk event to DB."""
        if self.db_repo and hasattr(self.db_repo, 'insert_risk_event'):
            self.db_repo.insert_risk_event({
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type,
                'details': event.details,
                'action': event.action
            })
