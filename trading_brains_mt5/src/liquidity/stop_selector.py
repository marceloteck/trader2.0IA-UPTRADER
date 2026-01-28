"""
Stop Selector: Intelligent stop loss placement based on liquidity structure.

Rules:
- Stop behind strong liquidity zone
- Avoid obvious stops on heavily tested levels
- Reduce stop when level loses strength during transition
- Account for invalidation points
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .liquidity_map import LiquidityMap, LiquidityZone

logger = logging.getLogger("trading_brains.liquidity.stop_selector")


@dataclass
class StopSetup:
    """Stop loss setup with justification."""
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    
    stop_price: Optional[float] = None
    stop_reason: Optional[str] = None
    zone_behind: Optional[LiquidityZone] = None
    
    buffer_pips: float = 0.0  # Safety buffer from zone
    distance_pips: float = 0.0
    
    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'stop_price': self.stop_price,
            'stop_reason': self.stop_reason,
            'buffer_pips': self.buffer_pips,
            'distance_pips': self.distance_pips,
        }


class StopSelector:
    """
    Select intelligent stop losses based on liquidity.
    
    Usage:
        selector = StopSelector(liquidity_map)
        
        setup = selector.select_stop(
            symbol='EURUSD',
            side='BUY',
            entry_price=1.0950,
            market_regime='TREND',
            transition_active=False,
        )
        
        print(f"Stop at: {setup.stop_price}")
        print(f"Reason: {setup.stop_reason}")
    """
    
    def __init__(
        self,
        liquidity_map: LiquidityMap,
        default_buffer_pips: float = 20.0,
        transition_buffer_factor: float = 1.5
    ):
        """
        Initialize stop selector.
        
        Args:
            liquidity_map: LiquidityMap instance
            default_buffer_pips: Default buffer from zone edge
            transition_buffer_factor: Multiply buffer by this during transition
        """
        self.lmap = liquidity_map
        self.default_buffer_pips = default_buffer_pips
        self.transition_buffer_factor = transition_buffer_factor
    
    def select_stop(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        entry_price: float,
        market_regime: str = 'NORMAL',
        transition_active: bool = False,
        max_stop_distance: float = 200.0
    ) -> StopSetup:
        """
        Select stop loss based on liquidity structure.
        
        Args:
            symbol: Symbol
            side: BUY or SELL
            entry_price: Entry price
            market_regime: NORMAL, TRANSITION, CHAOTIC
            transition_active: Is regime transition active
            max_stop_distance: Maximum stop distance from entry
        
        Returns:
            StopSetup with stop price and reason
        """
        setup = StopSetup(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
        )
        
        # Get zones behind entry (opposite direction)
        if side == 'BUY':
            zones_behind = self.lmap.get_zones_below(
                symbol,
                entry_price,
                max_distance=max_stop_distance,
                min_strength=0.0
            )
        else:  # SELL
            zones_behind = self.lmap.get_zones_above(
                symbol,
                entry_price,
                max_distance=max_stop_distance,
                min_strength=0.0
            )
        
        if not zones_behind:
            # Fallback: Use default distance
            setup.stop_price = self._default_stop(entry_price, side, max_stop_distance)
            setup.stop_reason = "No zones behind, using default distance"
            setup.distance_pips = abs(setup.stop_price - entry_price) * 10000
            return setup
        
        # Select best zone
        zone = self._select_zone_for_stop(zones_behind)
        setup.zone_behind = zone
        
        # Calculate buffer
        buffer = self.default_buffer_pips
        if transition_active:
            buffer *= self.transition_buffer_factor
        
        setup.buffer_pips = buffer
        
        # Place stop below/above zone (depending on side)
        if side == 'BUY':
            setup.stop_price = zone.price_min - (buffer / 10000)
            setup.stop_reason = f"Below {zone.source.value} (strength={zone.strength_score:.2f})"
        else:  # SELL
            setup.stop_price = zone.price_max + (buffer / 10000)
            setup.stop_reason = f"Above {zone.source.value} (strength={zone.strength_score:.2f})"
        
        # Validate stop is not too far
        setup.distance_pips = abs(setup.stop_price - entry_price) * 10000
        if setup.distance_pips > max_stop_distance:
            # Use fallback
            setup.stop_price = self._default_stop(entry_price, side, max_stop_distance)
            setup.stop_reason = f"Default distance ({setup.distance_pips:.0f} too far)"
            setup.distance_pips = abs(setup.stop_price - entry_price) * 10000
        
        logger.info(
            f"Stop selected: {setup.stop_price:.5f} "
            f"({setup.distance_pips:.0f} pips) from {setup.stop_reason}"
        )
        
        return setup
    
    def _select_zone_for_stop(self, zones: List[LiquidityZone]) -> LiquidityZone:
        """
        Select best zone for stop.
        
        Prefer:
        1. Strong zones (higher prob_hold)
        2. Recently tested zones
        3. Zones from trusted sources (VWAP, pivots)
        """
        # Filter out heavily tested zones with low hold rates
        candidates = [
            z for z in zones
            if z.prob_hold > 0.3 or z.touch_count < 3
        ]
        
        if not candidates:
            candidates = zones
        
        # Sort by strength (descending)
        candidates.sort(key=lambda z: z.strength_score, reverse=True)
        
        return candidates[0]
    
    def _default_stop(
        self,
        entry_price: float,
        side: str,
        max_distance_pips: float
    ) -> float:
        """Generate default stop loss."""
        distance = max_distance_pips / 10000
        
        if side == 'BUY':
            return entry_price - distance
        else:
            return entry_price + distance
    
    def adjust_for_transition(
        self,
        setup: StopSetup,
        transition_strength: float
    ) -> StopSetup:
        """
        Adjust stop during regime transition.
        
        Args:
            setup: Original setup
            transition_strength: Strength of transition (0-1)
        
        Returns:
            Adjusted setup
        """
        if not setup.stop_price or not setup.zone_behind:
            return setup
        
        # Move stop closer during strong transitions
        adjustment_factor = 1.0 + (transition_strength * 0.5)  # Up to 50% closer
        
        if setup.side == 'BUY':
            # Move stop up (closer to entry)
            new_distance = setup.distance_pips / adjustment_factor
            setup.stop_price = setup.entry_price - (new_distance / 10000)
        else:  # SELL
            # Move stop down (closer to entry)
            new_distance = setup.distance_pips / adjustment_factor
            setup.stop_price = setup.entry_price + (new_distance / 10000)
        
        setup.distance_pips = abs(setup.stop_price - setup.entry_price) * 10000
        setup.stop_reason += f" (adjusted for transition strength={transition_strength:.2f})"
        
        logger.info(
            f"Stop adjusted for transition: {setup.stop_price:.5f} "
            f"({setup.distance_pips:.0f} pips)"
        )
        
        return setup
