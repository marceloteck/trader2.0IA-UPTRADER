"""
Liquidity Map: Real-time mapping of liquidity zones across multiple timeframes.

Maps liquidity sources:
- VWAP (daily, weekly)
- High/Low (daily, session)
- Pivots (M1, M5, M15)
- Round levels
- Wyckoff, Cluster, Gann zones

Each level tracks:
- Price zone (range, not point)
- Source
- Touch/hold/break counts
- Strength score
- Probability of holding/breaking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json

import numpy as np

logger = logging.getLogger("trading_brains.liquidity.liquidity_map")


class LiquiditySource(str, Enum):
    """Source of a liquidity level."""
    VWAP_DAILY = "vwap_daily"
    VWAP_WEEKLY = "vwap_weekly"
    HIGH_DAILY = "high_daily"
    LOW_DAILY = "low_daily"
    HIGH_SESSION = "high_session"
    LOW_SESSION = "low_session"
    PIVOT_M1 = "pivot_m1"
    PIVOT_M5 = "pivot_m5"
    PIVOT_M15 = "pivot_m15"
    WYCKOFF = "wyckoff"
    CLUSTER = "cluster"
    GANN = "gann"
    ROUND_LEVEL = "round"
    PREVIOUS_CLOSE = "prev_close"
    SUPPORT_RESISTANCE = "support_resistance"


@dataclass
class LiquidityZone:
    """A liquidity zone with statistics."""
    symbol: str
    source: LiquiditySource
    price_center: float
    price_range: float  # e.g., 50 pips - zone is [center - range/2, center + range/2]
    timeframe: str  # M1, M5, H1, D1, etc
    created_at: str  # ISO timestamp
    last_tested: Optional[str] = None
    
    # Statistics
    touch_count: int = 0
    hold_count: int = 0  # Price bounced
    break_count: int = 0  # Price broke through
    sweep_count: int = 0  # Broke then returned
    
    # Strength metrics
    strength_score: float = 0.5  # 0-1
    prob_hold: float = 0.5  # Probability of bouncing
    prob_break: float = 0.5  # Probability of breaking
    
    # Metadata
    last_update: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    @property
    def price_min(self) -> float:
        """Lower bound of zone."""
        return self.price_center - self.price_range / 2
    
    @property
    def price_max(self) -> float:
        """Upper bound of zone."""
        return self.price_center + self.price_range / 2
    
    def contains(self, price: float) -> bool:
        """Check if price is in this zone."""
        return self.price_min <= price <= self.price_max
    
    def contains_high_low(self, high: float, low: float) -> bool:
        """Check if H/L touched this zone."""
        return (low <= self.price_max) and (high >= self.price_min)
    
    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            'symbol': self.symbol,
            'source': self.source.value,
            'price_center': self.price_center,
            'price_range': self.price_range,
            'price_min': self.price_min,
            'price_max': self.price_max,
            'timeframe': self.timeframe,
            'touch_count': self.touch_count,
            'hold_count': self.hold_count,
            'break_count': self.break_count,
            'sweep_count': self.sweep_count,
            'strength_score': self.strength_score,
            'prob_hold': self.prob_hold,
            'prob_break': self.prob_break,
            'last_tested': self.last_tested,
            'last_update': self.last_update,
        }


class LiquidityMap:
    """
    Real-time mapping of liquidity zones.
    
    Usage:
        lmap = LiquidityMap()
        
        # Add liquidity zones from various sources
        lmap.add_zone(LiquidityZone(symbol='EURUSD', ...))
        
        # Get zones for a symbol
        zones = lmap.get_zones('EURUSD')
        
        # Update on bar close
        lmap.update_from_bar('EURUSD', high, low, close)
        
        # Get sorted zones above/below current price
        above = lmap.get_zones_above('EURUSD', current_price, max_distance=200)
        below = lmap.get_zones_below('EURUSD', current_price, max_distance=200)
    """
    
    def __init__(self):
        """Initialize empty liquidity map."""
        self.zones: Dict[str, List[LiquidityZone]] = {}
        self.history: List[Dict] = []
    
    def add_zone(self, zone: LiquidityZone) -> None:
        """Add a liquidity zone."""
        symbol = zone.symbol
        if symbol not in self.zones:
            self.zones[symbol] = []
        
        # Check if similar zone exists
        for existing in self.zones[symbol]:
            if (abs(existing.price_center - zone.price_center) < zone.price_range and
                existing.source == zone.source and
                existing.timeframe == zone.timeframe):
                # Update existing instead
                existing.last_update = datetime.utcnow().isoformat()
                existing.metadata.update(zone.metadata)
                return
        
        self.zones[symbol].append(zone)
        logger.info(
            f"Added liquidity zone: {symbol} {zone.source.value} "
            f"@ {zone.price_center:.5f} (strength={zone.strength_score:.2f})"
        )
    
    def remove_zone(self, symbol: str, source: LiquiditySource, price_center: float) -> bool:
        """Remove a zone."""
        if symbol not in self.zones:
            return False
        
        self.zones[symbol] = [
            z for z in self.zones[symbol]
            if not (z.source == source and abs(z.price_center - price_center) < z.price_range)
        ]
        return True
    
    def get_zones(self, symbol: str, min_strength: float = 0.0) -> List[LiquidityZone]:
        """Get all zones for symbol above minimum strength."""
        if symbol not in self.zones:
            return []
        
        zones = [z for z in self.zones[symbol] if z.strength_score >= min_strength]
        return sorted(zones, key=lambda z: z.strength_score, reverse=True)
    
    def get_zones_above(
        self, 
        symbol: str, 
        current_price: float, 
        max_distance: float = 200.0,
        min_strength: float = 0.0
    ) -> List[LiquidityZone]:
        """Get zones above current price, sorted by distance."""
        zones = self.get_zones(symbol, min_strength)
        above = [
            z for z in zones
            if z.price_center > current_price and
            z.price_center - current_price <= max_distance
        ]
        return sorted(above, key=lambda z: z.price_center)
    
    def get_zones_below(
        self, 
        symbol: str, 
        current_price: float, 
        max_distance: float = 200.0,
        min_strength: float = 0.0
    ) -> List[LiquidityZone]:
        """Get zones below current price, sorted by distance (reversed)."""
        zones = self.get_zones(symbol, min_strength)
        below = [
            z for z in zones
            if z.price_center < current_price and
            current_price - z.price_center <= max_distance
        ]
        return sorted(below, key=lambda z: z.price_center, reverse=True)
    
    def update_from_bar(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float,
        time: Optional[str] = None
    ) -> List[Dict]:
        """
        Update zones after bar close.
        
        Returns:
            List of updated zones with their new statistics
        """
        if symbol not in self.zones:
            return []
        
        time = time or datetime.utcnow().isoformat()
        updates = []
        
        for zone in self.zones[symbol]:
            if not zone.contains_high_low(high, low):
                continue
            
            # Zone was tested
            zone.touch_count += 1
            zone.last_tested = time
            
            # Determine behavior
            if zone.contains(close):
                # Price is still in zone = held
                zone.hold_count += 1
            elif close > zone.price_center:
                # Price broke above
                zone.break_count += 1
                if high > zone.price_max:
                    zone.sweep_count += 0.5  # Partial break
            else:
                # Price broke below
                zone.break_count += 1
                if low < zone.price_min:
                    zone.sweep_count += 0.5  # Partial break
            
            # Update probabilities
            if zone.touch_count > 0:
                zone.prob_hold = zone.hold_count / zone.touch_count
                zone.prob_break = zone.break_count / zone.touch_count
            
            # Update strength score
            # Strength = prob_hold * decay_by_tests
            # Decay if too many tests with low hold rate
            decay = max(0.3, 1.0 - (zone.touch_count - zone.hold_count) * 0.1)
            zone.strength_score = max(0.0, min(1.0, zone.prob_hold * decay))
            
            zone.last_update = time
            
            updates.append({
                'zone_id': f"{symbol}_{zone.source.value}_{zone.price_center:.5f}",
                'source': zone.source.value,
                'price': zone.price_center,
                'touch_count': zone.touch_count,
                'hold_count': zone.hold_count,
                'break_count': zone.break_count,
                'strength_score': zone.strength_score,
                'prob_hold': zone.prob_hold,
                'prob_break': zone.prob_break,
            })
        
        if updates:
            self.history.append({
                'time': time,
                'symbol': symbol,
                'high': high,
                'low': low,
                'close': close,
                'updates': updates,
            })
        
        return updates
    
    def get_nearest_zone(
        self,
        symbol: str,
        price: float,
        direction: str = 'both'  # 'above', 'below', 'both'
    ) -> Optional[LiquidityZone]:
        """Get nearest zone in specified direction."""
        zones = self.get_zones(symbol, min_strength=0.0)
        
        if direction == 'above':
            candidates = [z for z in zones if z.price_center > price]
            if not candidates:
                return None
            return min(candidates, key=lambda z: z.price_center - price)
        
        elif direction == 'below':
            candidates = [z for z in zones if z.price_center < price]
            if not candidates:
                return None
            return max(candidates, key=lambda z: price - z.price_center)
        
        else:  # both
            above = min(
                (z for z in zones if z.price_center > price),
                key=lambda z: z.price_center - price,
                default=None
            )
            below = max(
                (z for z in zones if z.price_center < price),
                key=lambda z: price - z.price_center,
                default=None
            )
            
            if above and below:
                dist_above = above.price_center - price
                dist_below = price - below.price_center
                return above if dist_above < dist_below else below
            return above or below
    
    def clear_symbol(self, symbol: str) -> None:
        """Clear all zones for symbol."""
        if symbol in self.zones:
            del self.zones[symbol]
            logger.info(f"Cleared liquidity map for {symbol}")
