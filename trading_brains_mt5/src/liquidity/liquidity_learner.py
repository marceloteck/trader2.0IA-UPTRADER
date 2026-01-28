"""
Liquidity Learner: Learn behavior of liquidity levels after each trade.

Updates zone statistics based on:
- Did level hold?
- Was it broken?
- Was it swept?
- Decay old tests

Maintains probability models for each zone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from .liquidity_map import LiquidityMap, LiquidityZone, LiquiditySource

logger = logging.getLogger("trading_brains.liquidity.liquidity_learner")


@dataclass
class LevelBehavior:
    """Record of how a level behaved during a trade."""
    level_id: str
    symbol: str
    source: LiquiditySource
    price: float
    action: str  # 'touched', 'held', 'broken', 'swept'
    time: str
    side: str  # BUY or SELL
    trade_pnl: Optional[float] = None  # PnL if available


class LiquidityLearner:
    """
    Learn liquidity zone behavior from trades.
    
    Usage:
        learner = LiquidityLearner(liquidity_map)
        
        # After trade closes
        learner.update_from_trade(
            symbol='EURUSD',
            entry_price=1.0950,
            exit_price=1.0970,
            high=1.0975,
            low=1.0945,
            side='BUY',
            pnl=200,
        )
    """
    
    def __init__(self, liquidity_map: LiquidityMap):
        """Initialize learner with a liquidity map."""
        self.lmap = liquidity_map
        self.behaviors: List[LevelBehavior] = []
        self.level_stats: Dict[str, Dict] = {}
    
    def update_from_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        high: float,
        low: float,
        side: str,  # BUY or SELL
        pnl: Optional[float] = None,
        time: Optional[str] = None
    ) -> List[LevelBehavior]:
        """
        Update zone statistics based on trade.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            exit_price: Exit price
            high: Trade high
            low: Trade low
            side: BUY or SELL
            pnl: Profit/loss
            time: Trade close time
        
        Returns:
            List of level behaviors updated
        """
        time = time or datetime.utcnow().isoformat()
        zones = self.lmap.get_zones(symbol, min_strength=0.0)
        
        if not zones:
            return []
        
        behaviors = []
        
        for zone in zones:
            if not zone.contains_high_low(high, low):
                continue
            
            level_id = f"{symbol}_{zone.source.value}_{zone.price_center:.5f}"
            behavior = LevelBehavior(
                level_id=level_id,
                symbol=symbol,
                source=zone.source,
                price=zone.price_center,
                action=self._classify_action(zone, entry_price, exit_price, high, low, side),
                time=time,
                side=side,
                trade_pnl=pnl,
            )
            
            behaviors.append(behavior)
            self.behaviors.append(behavior)
            
            # Update zone stats
            self._update_level_stats(level_id, behavior, zone)
            
            logger.debug(
                f"Level {zone.source.value} @ {zone.price_center:.5f}: "
                f"{behavior.action} (touch_count={zone.touch_count})"
            )
        
        return behaviors
    
    def _classify_action(
        self,
        zone: LiquidityZone,
        entry: float,
        exit: float,
        high: float,
        low: float,
        side: str
    ) -> str:
        """Classify how the level behaved."""
        # Check if price ended in zone
        if zone.contains(exit):
            return 'held'
        
        # Check if swept (broken then returned)
        if side == 'BUY':
            if high > zone.price_max and low < zone.price_max:
                return 'swept'
            elif high > zone.price_max:
                return 'broken'
        else:  # SELL
            if low < zone.price_min and high > zone.price_min:
                return 'swept'
            elif low < zone.price_min:
                return 'broken'
        
        return 'touched'
    
    def _update_level_stats(
        self,
        level_id: str,
        behavior: LevelBehavior,
        zone: LiquidityZone
    ) -> None:
        """Update statistics for a level."""
        if level_id not in self.level_stats:
            self.level_stats[level_id] = {
                'held_count': 0,
                'broken_count': 0,
                'swept_count': 0,
                'pnl_when_held': [],
                'pnl_when_broken': [],
                'last_update': datetime.utcnow().isoformat(),
            }
        
        stats = self.level_stats[level_id]
        
        if behavior.action == 'held':
            stats['held_count'] += 1
            if behavior.trade_pnl is not None:
                stats['pnl_when_held'].append(behavior.trade_pnl)
        elif behavior.action == 'broken':
            stats['broken_count'] += 1
            if behavior.trade_pnl is not None:
                stats['pnl_when_broken'].append(behavior.trade_pnl)
        elif behavior.action == 'swept':
            stats['swept_count'] += 1
        
        stats['last_update'] = datetime.utcnow().isoformat()
        
        # Update zone probabilities
        total = stats['held_count'] + stats['broken_count'] + stats['swept_count']
        if total > 0:
            zone.prob_hold = stats['held_count'] / total
            zone.prob_break = (stats['broken_count'] + stats['swept_count']) / total
            zone.strength_score = zone.prob_hold * self._decay_factor(total)
    
    @staticmethod
    def _decay_factor(test_count: int) -> float:
        """
        Decay factor based on number of tests.
        
        More tests = more confidence (up to a point).
        Too many failed tests = reduced strength.
        """
        if test_count < 3:
            return 1.0  # < 3 tests: full strength
        elif test_count < 10:
            return 0.9  # 3-10: slight decay
        else:
            return max(0.5, 1.0 - (test_count - 10) * 0.05)  # Decay over 10
    
    def get_expected_pnl_at_level(
        self,
        level_id: str,
        action: str = 'held'
    ) -> Optional[float]:
        """Get average PnL when level acted as specified."""
        if level_id not in self.level_stats:
            return None
        
        stats = self.level_stats[level_id]
        
        if action == 'held' and stats['pnl_when_held']:
            return np.mean(stats['pnl_when_held'])
        elif action == 'broken' and stats['pnl_when_broken']:
            return np.mean(stats['pnl_when_broken'])
        
        return None
    
    def get_level_confidence(
        self,
        level_id: str,
        action: str = 'held'
    ) -> float:
        """Get confidence (0-1) that level will act as specified."""
        if level_id not in self.level_stats:
            return 0.0
        
        stats = self.level_stats[level_id]
        total = stats['held_count'] + stats['broken_count'] + stats['swept_count']
        
        if total == 0:
            return 0.0
        
        if action == 'held':
            return stats['held_count'] / total
        elif action == 'broken':
            return (stats['broken_count'] + stats['swept_count']) / total
        
        return 0.0
    
    def prune_old_zones(self, hours: int = 24) -> int:
        """Remove zones untested for N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        count = 0
        
        for symbol, zones in list(self.lmap.zones.items()):
            for zone in zones[:]:
                if zone.last_tested is None:
                    continue
                
                last_test = datetime.fromisoformat(zone.last_tested)
                if last_test < cutoff:
                    zones.remove(zone)
                    count += 1
                    logger.info(f"Pruned untested zone: {symbol} {zone.source.value}")
        
        return count
    
    def export_stats(self) -> Dict:
        """Export all learner statistics."""
        return {
            'level_stats': self.level_stats,
            'behavior_count': len(self.behaviors),
            'timestamp': datetime.utcnow().isoformat(),
        }
