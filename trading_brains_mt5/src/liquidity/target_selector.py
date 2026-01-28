"""
Target Selector: Intelligent TP1, TP2, and Runner selection based on liquidity.

Rules:
- TP1 = first level with high prob_hold
- TP2 = next relevant level (if safe)
- RUNNER = only if trend confirmed and next levels are weak
- RR ratio must be respected (min 1.5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .liquidity_map import LiquidityMap, LiquidityZone

logger = logging.getLogger("trading_brains.liquidity.target_selector")


@dataclass
class TargetSetup:
    """Complete TP1/TP2/Runner setup."""
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    
    tp1_price: Optional[float] = None
    tp1_reason: Optional[str] = None
    tp1_strength: float = 0.0
    
    tp2_price: Optional[float] = None
    tp2_reason: Optional[str] = None
    tp2_strength: float = 0.0
    
    runner_enabled: bool = False
    runner_reason: Optional[str] = None
    
    rr_ratio: float = 0.0  # TP1 / SL distance
    
    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'tp1_price': self.tp1_price,
            'tp1_reason': self.tp1_reason,
            'tp1_strength': self.tp1_strength,
            'tp2_price': self.tp2_price,
            'tp2_reason': self.tp2_reason,
            'tp2_strength': self.tp2_strength,
            'runner_enabled': self.runner_enabled,
            'runner_reason': self.runner_reason,
            'rr_ratio': self.rr_ratio,
        }


class TargetSelector:
    """
    Select intelligent targets based on liquidity zones.
    
    Usage:
        selector = TargetSelector(liquidity_map, min_rr=1.5)
        
        setup = selector.select_targets(
            symbol='EURUSD',
            side='BUY',
            entry_price=1.0950,
            stop_loss=1.0920,
            allow_runner=True,
            trend_strength=0.8,
        )
        
        print(f"TP1: {setup.tp1_price}")
        print(f"TP2: {setup.tp2_price}")
    """
    
    def __init__(
        self,
        liquidity_map: LiquidityMap,
        min_rr: float = 1.5,
        min_tp_strength: float = 0.55,
        min_runner_confidence: float = 0.65
    ):
        """
        Initialize target selector.
        
        Args:
            liquidity_map: LiquidityMap instance
            min_rr: Minimum risk/reward ratio
            min_tp_strength: Minimum zone strength for valid TP
            min_runner_confidence: Minimum confidence to enable runner
        """
        self.lmap = liquidity_map
        self.min_rr = min_rr
        self.min_tp_strength = min_tp_strength
        self.min_runner_confidence = min_runner_confidence
    
    def select_targets(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        entry_price: float,
        stop_loss: float,
        allow_runner: bool = False,
        trend_strength: float = 0.5,
        max_tp2_distance: Optional[float] = None
    ) -> TargetSetup:
        """
        Select TP1, TP2, and Runner based on liquidity.
        
        Args:
            symbol: Symbol
            side: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss price
            allow_runner: Allow runner setup
            trend_strength: Current trend strength (0-1)
            max_tp2_distance: Maximum distance for TP2 from entry
        
        Returns:
            TargetSetup with TP prices and reasons
        """
        setup = TargetSetup(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
        )
        
        # Get zones in direction of trade
        if side == 'BUY':
            zones_ahead = self.lmap.get_zones_above(
                symbol, 
                entry_price, 
                max_distance=500.0,
                min_strength=0.0
            )
        else:  # SELL
            zones_ahead = self.lmap.get_zones_below(
                symbol, 
                entry_price, 
                max_distance=500.0,
                min_strength=0.0
            )
        
        if not zones_ahead:
            logger.warning(f"No liquidity zones found for {symbol} {side}")
            return setup
        
        # Select TP1: First strong zone
        tp1_zone = self._select_tp1(zones_ahead)
        if tp1_zone:
            setup.tp1_price = tp1_zone.price_center
            setup.tp1_reason = f"{tp1_zone.source.value} (strength={tp1_zone.strength_score:.2f})"
            setup.tp1_strength = tp1_zone.strength_score
            
            # Calculate RR for TP1
            sl_distance = abs(entry_price - stop_loss)
            tp1_distance = abs(setup.tp1_price - entry_price)
            setup.rr_ratio = tp1_distance / sl_distance if sl_distance > 0 else 0
            
            logger.info(
                f"TP1 selected: {setup.tp1_price:.5f} (RR={setup.rr_ratio:.2f}) "
                f"from {tp1_zone.source.value}"
            )
        
        # Select TP2: Next relevant zone (if trend is strong)
        if trend_strength > 0.55 and len(zones_ahead) > 1:
            tp2_zone = self._select_tp2(zones_ahead, tp1_zone, max_tp2_distance)
            if tp2_zone and setup.tp1_price:
                setup.tp2_price = tp2_zone.price_center
                setup.tp2_reason = f"{tp2_zone.source.value} (strength={tp2_zone.strength_score:.2f})"
                setup.tp2_strength = tp2_zone.strength_score
                
                logger.info(
                    f"TP2 selected: {setup.tp2_price:.5f} "
                    f"from {tp2_zone.source.value}"
                )
        
        # Enable runner if conditions met
        if allow_runner and trend_strength > self.min_runner_confidence and setup.tp1_price:
            runner_ok = self._should_enable_runner(
                zones_ahead,
                setup.tp1_price,
                side
            )
            if runner_ok:
                setup.runner_enabled = True
                setup.runner_reason = f"Trend={trend_strength:.2f}, weak zones ahead"
                logger.info(f"Runner enabled: {setup.runner_reason}")
        
        return setup
    
    def _select_tp1(self, zones: List[LiquidityZone]) -> Optional[LiquidityZone]:
        """Select TP1: first strong zone."""
        for zone in zones:
            if zone.strength_score >= self.min_tp_strength:
                return zone
        
        # Fallback: first zone if no strong one
        if zones:
            return zones[0]
        
        return None
    
    def _select_tp2(
        self,
        zones: List[LiquidityZone],
        tp1_zone: Optional[LiquidityZone],
        max_distance: Optional[float] = None
    ) -> Optional[LiquidityZone]:
        """Select TP2: next relevant zone after TP1."""
        if not tp1_zone:
            return None
        
        # Find zones after TP1
        candidates = [
            z for z in zones
            if z.price_center != tp1_zone.price_center
        ]
        
        if not candidates:
            return None
        
        # If max_distance specified, filter
        if max_distance:
            candidates = [
                z for z in candidates
                if abs(z.price_center - tp1_zone.price_center) <= max_distance
            ]
        
        # Prefer zones with good strength
        candidates_strong = [z for z in candidates if z.strength_score >= 0.55]
        if candidates_strong:
            return candidates_strong[0]
        
        return candidates[0] if candidates else None
    
    def _should_enable_runner(
        self,
        zones: List[LiquidityZone],
        tp1_price: float,
        side: str
    ) -> bool:
        """Check if runner should be enabled."""
        # Runner only if zones after TP1 are weak
        if side == 'BUY':
            zones_after = [z for z in zones if z.price_center > tp1_price]
        else:
            zones_after = [z for z in zones if z.price_center < tp1_price]
        
        if not zones_after:
            return True  # No zones ahead = enable runner
        
        # Check average strength of zones ahead
        avg_strength = sum(z.strength_score for z in zones_after) / len(zones_after)
        
        # Enable runner if zones ahead are weak
        return avg_strength < 0.60
    
    def validate_setup(self, setup: TargetSetup) -> Tuple[bool, str]:
        """
        Validate setup.
        
        Returns:
            (is_valid, reason)
        """
        if not setup.tp1_price:
            return False, "No TP1 selected"
        
        if setup.rr_ratio < self.min_rr:
            return False, f"RR ratio {setup.rr_ratio:.2f} < {self.min_rr}"
        
        # Check that TP1 and TP2 don't overlap
        if setup.tp2_price and setup.tp1_price:
            if abs(setup.tp2_price - setup.tp1_price) < 10:  # Min distance
                return False, "TP2 too close to TP1"
        
        return True, "Valid"
