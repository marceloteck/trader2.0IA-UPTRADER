"""
Level 3: Transition Performance Matrix

Tracks brain performance across regime transitions.
Builds a matrix: performance[brain_id][from_regime][to_regime]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

from .regime_transition import RegimeState

logger = logging.getLogger("trading_brains.models.transition_performance")


@dataclass
class TransitionMetrics:
    """Performance metrics for a brain in a specific transition."""
    brain_id: str
    from_regime: RegimeState
    to_regime: RegimeState
    trade_count: int = 0
    win_count: int = 0
    winrate: float = 0.0
    profit_factor: float = 1.0  # Wins / Losses
    avg_pnl: float = 0.0
    max_dd: float = 0.0
    quality_score: float = 0.5  # 0..1
    total_pnl: float = 0.0
    last_updated: Optional[datetime] = None


class TransitionPerformanceMatrix:
    """
    Maintains performance matrix across regime transitions.
    Auto-updates based on closed trades.
    """

    def __init__(self):
        """Initialize matrix."""
        # matrix[brain_id][from_regime][to_regime] = TransitionMetrics
        self.matrix: Dict[str, Dict[RegimeState, Dict[RegimeState, TransitionMetrics]]] = {}
        self.recent_trades: List[Dict] = []
        self.max_history = 1000

    def record_trade(
        self,
        brain_id: str,
        from_regime: RegimeState,
        to_regime: RegimeState,
        pnl: float,
        win: bool,
        trade_id: int
    ) -> None:
        """Record a closed trade for transition analysis."""
        trade_record = {
            'brain_id': brain_id,
            'from_regime': from_regime,
            'to_regime': to_regime,
            'pnl': pnl,
            'win': win,
            'trade_id': trade_id,
            'time': datetime.utcnow()
        }
        
        self.recent_trades.append(trade_record)
        if len(self.recent_trades) > self.max_history:
            self.recent_trades.pop(0)
        
        self._update_metrics(brain_id, from_regime, to_regime, pnl, win)

    def _update_metrics(
        self,
        brain_id: str,
        from_regime: RegimeState,
        to_regime: RegimeState,
        pnl: float,
        win: bool
    ) -> None:
        """Update metrics for brain in specific transition."""
        # Initialize structure if needed
        if brain_id not in self.matrix:
            self.matrix[brain_id] = {}
        
        if from_regime not in self.matrix[brain_id]:
            self.matrix[brain_id][from_regime] = {}
        
        if to_regime not in self.matrix[brain_id][from_regime]:
            self.matrix[brain_id][from_regime][to_regime] = TransitionMetrics(
                brain_id=brain_id,
                from_regime=from_regime,
                to_regime=to_regime
            )
        
        metrics = self.matrix[brain_id][from_regime][to_regime]
        
        # Update counts
        metrics.trade_count += 1
        if win:
            metrics.win_count += 1
        
        metrics.winrate = metrics.win_count / metrics.trade_count if metrics.trade_count > 0 else 0
        metrics.avg_pnl = (metrics.avg_pnl * (metrics.trade_count - 1) + pnl) / metrics.trade_count
        metrics.total_pnl += pnl
        
        # Simplified DD tracking (would be cumulative in real system)
        if pnl < 0:
            metrics.max_dd = min(metrics.max_dd, pnl)
        
        # Quality score: balance winrate and avg PnL
        wr_score = metrics.winrate * 100  # 0..100
        pnl_score = min(100, max(-100, metrics.avg_pnl * 100))  # -100..100
        metrics.quality_score = (0.6 * wr_score + 0.4 * pnl_score) / 100.0
        metrics.quality_score = min(1.0, max(0.0, metrics.quality_score))
        
        # Profit factor
        wins = sum(1 for t in self.recent_trades if (
            t['brain_id'] == brain_id and
            t['from_regime'] == from_regime and
            t['to_regime'] == to_regime and
            t['pnl'] > 0
        ))
        losses = sum(1 for t in self.recent_trades if (
            t['brain_id'] == brain_id and
            t['from_regime'] == from_regime and
            t['to_regime'] == to_regime and
            t['pnl'] < 0
        ))
        
        total_wins = sum(t['pnl'] for t in self.recent_trades if (
            t['brain_id'] == brain_id and
            t['from_regime'] == from_regime and
            t['to_regime'] == to_regime and
            t['pnl'] > 0
        ))
        total_losses = abs(sum(t['pnl'] for t in self.recent_trades if (
            t['brain_id'] == brain_id and
            t['from_regime'] == from_regime and
            t['to_regime'] == to_regime and
            t['pnl'] < 0
        )))
        
        if total_losses > 0:
            metrics.profit_factor = total_wins / total_losses
        elif total_wins > 0:
            metrics.profit_factor = total_wins  # All wins
        else:
            metrics.profit_factor = 1.0
        
        metrics.last_updated = datetime.utcnow()

    def get_best_brains_for_transition(
        self,
        from_regime: RegimeState,
        to_regime: RegimeState,
        min_trades: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Get brains ranked by quality for specific transition.
        
        Returns:
            List of (brain_id, quality_score) sorted by quality desc
        """
        candidates = []
        
        for brain_id, regimes in self.matrix.items():
            if from_regime not in regimes:
                continue
            
            if to_regime not in regimes[from_regime]:
                continue
            
            metrics = regimes[from_regime][to_regime]
            
            if metrics.trade_count >= min_trades:
                candidates.append((brain_id, metrics.quality_score))
        
        # Sort by quality score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def get_brains_forbidden_transitions(
        self,
        brain_id: str,
        quality_threshold: float = 0.3
    ) -> List[Tuple[RegimeState, RegimeState]]:
        """
        Get transitions where brain performs poorly.
        These transitions should be avoided.
        
        Returns:
            List of (from_regime, to_regime) tuples to avoid
        """
        forbidden = []
        
        if brain_id not in self.matrix:
            return forbidden
        
        for from_regime, transitions in self.matrix[brain_id].items():
            for to_regime, metrics in transitions.items():
                if metrics.trade_count >= 5 and metrics.quality_score < quality_threshold:
                    forbidden.append((from_regime, to_regime))
        
        return forbidden

    def get_brain_metrics(
        self,
        brain_id: str,
        from_regime: RegimeState,
        to_regime: RegimeState
    ) -> Optional[TransitionMetrics]:
        """Get metrics for specific brain-transition combo."""
        if brain_id not in self.matrix:
            return None
        
        if from_regime not in self.matrix[brain_id]:
            return None
        
        return self.matrix[brain_id][from_regime].get(to_regime)

    def get_overall_transition_stats(
        self,
        from_regime: RegimeState,
        to_regime: RegimeState
    ) -> Dict[str, float]:
        """Get aggregate stats for all brains in specific transition."""
        metrics_list = []
        
        for brain_id, regimes in self.matrix.items():
            if from_regime in regimes and to_regime in regimes[from_regime]:
                metrics = regimes[from_regime][to_regime]
                if metrics.trade_count > 0:
                    metrics_list.append(metrics)
        
        if not metrics_list:
            return {
                'total_trades': 0,
                'avg_winrate': 0.0,
                'avg_quality': 0.0,
                'best_quality': 0.0,
                'avg_pnl': 0.0
            }
        
        return {
            'total_trades': sum(m.trade_count for m in metrics_list),
            'avg_winrate': np.mean([m.winrate for m in metrics_list]),
            'avg_quality': np.mean([m.quality_score for m in metrics_list]),
            'best_quality': max(m.quality_score for m in metrics_list),
            'avg_pnl': np.mean([m.avg_pnl for m in metrics_list])
        }

    def print_matrix_summary(self) -> str:
        """Generate readable summary of performance matrix."""
        lines = ["Transition Performance Matrix:", "=" * 80]
        
        for brain_id in sorted(self.matrix.keys()):
            lines.append(f"\n{brain_id}:")
            regimes = self.matrix[brain_id]
            
            for from_regime in sorted(regimes.keys(), key=lambda x: x.value):
                for to_regime in sorted(regimes[from_regime].keys(), key=lambda x: x.value):
                    metrics = regimes[from_regime][to_regime]
                    
                    if metrics.trade_count > 0:
                        lines.append(
                            f"  {from_regime.value:12} -> {to_regime.value:12} | "
                            f"Trades: {metrics.trade_count:3} | "
                            f"WR: {metrics.winrate:5.1%} | "
                            f"Quality: {metrics.quality_score:5.2f} | "
                            f"PnL: {metrics.avg_pnl:+8.2f}"
                        )
        
        return "\n".join(lines)
