"""
SL/TP Manager V4: Advanced stop loss and take profit management based on liquidity.

Extends the base SLTPManager with:
- Liquidity-aware TP placement
- Level-based trailing (not candle-based)
- Dynamic stop adjustment during transitions
- Runner mode with liquidity confirmation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..liquidity.liquidity_map import LiquidityMap
from ..liquidity.target_selector import TargetSelector, TargetSetup
from ..liquidity.stop_selector import StopSelector, StopSetup

logger = logging.getLogger("trading_brains.execution.sl_tp_manager_v4")


@dataclass
class TrailingState:
    """State of trailing stop."""
    active: bool = False
    last_level_stop: Optional[float] = None
    runner_activated: bool = False
    highest_favorable_price: float = 0.0
    updates_count: int = 0


@dataclass
class LiquidityTPSetup:
    """Complete trade setup with liquidity-based TPs."""
    symbol: str
    side: str
    entry_price: float
    
    # From TargetSelector
    target_setup: TargetSetup
    
    # From StopSelector
    stop_setup: StopSetup
    
    # Trading parameters
    tp1_qty_percent: float = 0.5  # Close 50% at TP1
    tp2_qty_percent: float = 0.3  # Close 30% at TP2
    runner_qty_percent: float = 0.2  # 20% for runner
    
    # Trailing
    trailing_state: TrailingState = None
    
    def __post_init__(self):
        if self.trailing_state is None:
            self.trailing_state = TrailingState()
    
    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'target_setup': self.target_setup.to_dict(),
            'stop_setup': self.stop_setup.to_dict(),
            'tp1_qty_percent': self.tp1_qty_percent,
            'tp2_qty_percent': self.tp2_qty_percent,
            'runner_qty_percent': self.runner_qty_percent,
            'trailing_state': {
                'active': self.trailing_state.active,
                'runner_activated': self.trailing_state.runner_activated,
                'updates_count': self.trailing_state.updates_count,
            },
        }


class SLTPManagerV4:
    """
    Advanced SL/TP management with liquidity awareness.
    
    Usage:
        manager = SLTPManagerV4(liquidity_map)
        
        setup = manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry_price=1.0950,
            market_regime='TREND',
            transition_active=False,
            allow_runner=True,
        )
        
        # Use setup.target_setup.tp1_price, tp2_price
        # Use setup.stop_setup.stop_price
        
        # During trade update
        manager.update_trailing(
            setup=setup,
            current_high=1.0960,
            current_low=1.0945,
            current_close=1.0958,
        )
    """
    
    def __init__(
        self,
        liquidity_map: LiquidityMap,
        min_rr: float = 1.5,
        min_tp_strength: float = 0.55,
        min_runner_confidence: float = 0.65
    ):
        """Initialize with liquidity components."""
        self.lmap = liquidity_map
        self.target_selector = TargetSelector(
            liquidity_map,
            min_rr=min_rr,
            min_tp_strength=min_tp_strength,
            min_runner_confidence=min_runner_confidence
        )
        self.stop_selector = StopSelector(liquidity_map)
    
    def create_setup(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        market_regime: str = 'NORMAL',
        transition_active: bool = False,
        transition_strength: float = 0.0,
        allow_runner: bool = False,
        trend_strength: float = 0.5,
        max_stop_distance: float = 200.0,
        tp1_qty_percent: float = 0.5,
        tp2_qty_percent: float = 0.3,
        runner_qty_percent: float = 0.2,
    ) -> LiquidityTPSetup:
        """
        Create complete trade setup with liquidity-aware TPs and stops.
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            entry_price: Entry price
            market_regime: NORMAL, TRANSITION, CHAOTIC
            transition_active: Is transition active
            transition_strength: Strength of transition (0-1)
            allow_runner: Allow runner setup
            trend_strength: Trend strength (0-1)
            max_stop_distance: Maximum stop distance (pips)
            tp1_qty_percent: Quantity % to close at TP1
            tp2_qty_percent: Quantity % to close at TP2
            runner_qty_percent: Quantity % for runner
        
        Returns:
            LiquidityTPSetup with all parameters
        """
        # Select targets
        target_setup = self.target_selector.select_targets(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss=entry_price - (max_stop_distance / 10000) if side == 'BUY' else entry_price + (max_stop_distance / 10000),
            allow_runner=allow_runner and market_regime != 'CHAOTIC',
            trend_strength=trend_strength,
        )
        
        # Select stop
        stop_setup = self.stop_selector.select_stop(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            market_regime=market_regime,
            transition_active=transition_active,
            max_stop_distance=max_stop_distance,
        )
        
        # Adjust for transition
        if transition_active and transition_strength > 0:
            stop_setup = self.stop_selector.adjust_for_transition(
                stop_setup,
                transition_strength
            )
        
        # Create setup
        setup = LiquidityTPSetup(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            target_setup=target_setup,
            stop_setup=stop_setup,
            tp1_qty_percent=tp1_qty_percent,
            tp2_qty_percent=tp2_qty_percent,
            runner_qty_percent=runner_qty_percent,
        )
        
        logger.info(
            f"Setup created: {symbol} {side} @ {entry_price:.5f}\n"
            f"  TP1: {setup.target_setup.tp1_price} ({setup.target_setup.tp1_reason})\n"
            f"  TP2: {setup.target_setup.tp2_price} ({setup.target_setup.tp2_reason})\n"
            f"  SL: {setup.stop_setup.stop_price} ({setup.stop_setup.stop_reason})\n"
            f"  Runner: {setup.target_setup.runner_enabled}"
        )
        
        return setup
    
    def update_trailing(
        self,
        setup: LiquidityTPSetup,
        current_high: float,
        current_low: float,
        current_close: float,
    ) -> Optional[Dict]:
        """
        Update trailing stop based on liquidity levels.
        
        Only trail between liquidity levels, not candle-by-candle.
        
        Returns:
            Update dict if trailing state changed, else None
        """
        if not setup.target_setup.runner_enabled:
            return None
        
        trailing = setup.trailing_state
        
        if setup.side == 'BUY':
            # Check if TP1 was passed
            if current_low >= setup.target_setup.tp1_price and not trailing.runner_activated:
                trailing.runner_activated = True
                trailing.active = True
                logger.info(f"Runner activated: {setup.symbol} crossed TP1")
            
            if trailing.active:
                # Update highest price
                trailing.highest_favorable_price = max(trailing.highest_favorable_price, current_high)
                
                # Try to trail to next level
                next_level = self.lmap.get_nearest_zone(
                    setup.symbol,
                    trailing.highest_favorable_price,
                    direction='above'
                )
                
                if next_level:
                    new_stop = next_level.price_min - 0.0010
                    if new_stop > (setup.stop_setup.stop_price or setup.entry_price - 0.1):
                        setup.stop_setup.stop_price = new_stop
                        trailing.last_level_stop = new_stop
                        trailing.updates_count += 1
                        
                        return {
                            'action': 'trail_up',
                            'new_stop': new_stop,
                            'zone': next_level.source.value,
                            'highest_price': trailing.highest_favorable_price,
                        }
        
        else:  # SELL
            # Check if TP1 was passed
            if current_high <= setup.target_setup.tp1_price and not trailing.runner_activated:
                trailing.runner_activated = True
                trailing.active = True
                logger.info(f"Runner activated: {setup.symbol} crossed TP1")
            
            if trailing.active:
                # Update lowest price
                trailing.highest_favorable_price = min(
                    trailing.highest_favorable_price or current_low,
                    current_low
                )
                
                # Try to trail to next level
                next_level = self.lmap.get_nearest_zone(
                    setup.symbol,
                    trailing.highest_favorable_price,
                    direction='below'
                )
                
                if next_level:
                    new_stop = next_level.price_max + 0.0010
                    if new_stop < (setup.stop_setup.stop_price or setup.entry_price + 0.1):
                        setup.stop_setup.stop_price = new_stop
                        trailing.last_level_stop = new_stop
                        trailing.updates_count += 1
                        
                        return {
                            'action': 'trail_down',
                            'new_stop': new_stop,
                            'zone': next_level.source.value,
                            'lowest_price': trailing.highest_favorable_price,
                        }
        
        return None
