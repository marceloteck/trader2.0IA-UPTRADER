"""
Fill Model V4 - Realistic execution fill simulation for backtest, sim, and live.

Handles:
- Dynamic spread (constant + volatility-based)
- Realistic slippage (random within bounds)
- Latency simulation (optional)
- Rejection logic (spread too high, symbol unavailable)
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class FillResult:
    """Result of a fill attempt."""
    success: bool
    requested_price: float
    filled_price: Optional[float] = None
    slippage: float = 0.0  # How much worse than requested
    spread: float = 0.0    # Bid-ask spread at fill time
    timestamp: Optional[datetime] = None
    reason: str = ""  # If not successful, why
    latency_ms: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        d = asdict(self)
        if self.timestamp:
            d['timestamp'] = self.timestamp.isoformat()
        return d


class FillModel:
    """
    Realistic fill model for all execution types.
    
    Configurable via environment:
    - FILL_MODEL_SPREAD_BASE: Base spread in pips (default 1.0)
    - FILL_MODEL_SPREAD_VOL_MULT: Spread multiplier per ATR unit (default 0.5)
    - FILL_MODEL_SLIPPAGE_BASE: Base slippage in pips (default 0.0)
    - FILL_MODEL_SLIPPAGE_MAX: Max random slippage in pips (default 2.0)
    - FILL_MODEL_REJECTION_PROB: Probability of rejection (default 0.01)
    - FILL_MODEL_LATENCY_MS: Simulated latency in ms (default 0)
    """
    
    def __init__(self, settings):
        """Initialize fill model with settings."""
        self.settings = settings
        
        # Spread and slippage configuration
        self.spread_base = float(settings.get('FILL_MODEL_SPREAD_BASE', '1.0'))
        self.spread_vol_mult = float(settings.get('FILL_MODEL_SPREAD_VOL_MULT', '0.5'))
        self.slippage_base = float(settings.get('FILL_MODEL_SLIPPAGE_BASE', '0.0'))
        self.slippage_max = float(settings.get('FILL_MODEL_SLIPPAGE_MAX', '2.0'))
        self.rejection_prob = float(settings.get('FILL_MODEL_REJECTION_PROB', '0.01'))
        self.latency_ms = float(settings.get('FILL_MODEL_LATENCY_MS', '0'))
        
        logger.info(f"FillModel initialized: spread_base={self.spread_base}, "
                   f"slippage_max={self.slippage_max}, rejection_prob={self.rejection_prob}")
    
    def calculate_fill(
        self,
        requested_price: float,
        side: str,  # "BUY" or "SELL"
        atr: float = 0.0,  # Optional: for vol-adjusted spread
        symbol: str = "",  # Optional: for symbol-specific rules
        is_live: bool = False  # If True, less optimistic slippage
    ) -> FillResult:
        """
        Simulate a fill at given price with realistic slippage and spread.
        
        Args:
            requested_price: Requested entry price
            side: "BUY" or "SELL"
            atr: Average True Range for volatility adjustment
            symbol: Symbol name for logging
            is_live: If True, apply more realistic (worse) slippage
        
        Returns:
            FillResult with filled_price or rejection reason
        """
        
        # Check for rejection (e.g., symbol offline, spread explosion)
        if random.random() < self.rejection_prob:
            return FillResult(
                success=False,
                requested_price=requested_price,
                reason="Random rejection (simulated connectivity issue)",
                timestamp=datetime.utcnow()
            )
        
        # Calculate spread
        spread = self.spread_base + (self.spread_vol_mult * atr)
        
        # Calculate slippage (worse for live, based on side)
        slippage_range = self.slippage_max if is_live else self.slippage_max * 0.5
        random_slippage = random.uniform(self.slippage_base, slippage_range)
        
        # Apply slippage in the negative direction (cost to trader)
        if side.upper() == "BUY":
            filled_price = requested_price + random_slippage + (spread / 2)
        else:  # SELL
            filled_price = requested_price - random_slippage - (spread / 2)
        
        slippage = abs(filled_price - requested_price)
        
        # Simulate latency
        latency = random.uniform(0, self.latency_ms) if self.latency_ms > 0 else 0
        
        result = FillResult(
            success=True,
            requested_price=requested_price,
            filled_price=filled_price,
            slippage=slippage,
            spread=spread,
            timestamp=datetime.utcnow(),
            latency_ms=latency
        )
        
        logger.debug(f"Fill {symbol} {side}: requested={requested_price:.5f}, "
                    f"filled={filled_price:.5f}, slippage={slippage:.2f}pips, "
                    f"spread={spread:.2f}pips, latency={latency:.0f}ms")
        
        return result
    
    def validate_spread(self, spread: float, max_spread_pips: float = 5.0) -> bool:
        """
        Validate if spread is acceptable for trading.
        
        Args:
            spread: Current spread in pips
            max_spread_pips: Maximum acceptable spread
        
        Returns:
            True if spread is OK, False if too high
        """
        return spread <= max_spread_pips
    
    def estimate_worst_case_fill(
        self,
        requested_price: float,
        side: str,
        atr: float = 0.0
    ) -> float:
        """
        Estimate worst-case fill price (for risk calculation).
        Uses max spread + max slippage.
        """
        worst_spread = self.spread_base + (self.spread_vol_mult * atr)
        worst_slippage = self.slippage_max
        
        if side.upper() == "BUY":
            return requested_price + worst_slippage + (worst_spread / 2)
        else:
            return requested_price - worst_slippage - (worst_spread / 2)
