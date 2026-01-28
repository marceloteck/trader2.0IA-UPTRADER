"""
Label generator: Create multi-horizon training labels with quality scores.

Labels:
- tp1_hit, tp2_hit: Did price reach TP1/TP2 before SL?
- mfe, mae: Max favorable/adverse excursion
- quality_score: α*MFE - β*MAE (quality metric)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("trading_brains.training")


@dataclass
class TradeLabel:
    """Label for a single trade across horizons."""
    timestamp: float
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    tp1: float
    tp2: float
    sl: float
    
    # Per-horizon labels
    tp1_hit: Dict[int, bool]  # {5: True, 10: False, 20: False}
    tp2_hit: Dict[int, bool]
    mfe: Dict[int, float]     # Max favorable excursion in pips
    mae: Dict[int, float]     # Max adverse excursion in pips
    quality_score: Dict[int, float]  # α*MFE - β*MAE
    
    def as_dict(self) -> Dict:
        """Convert to dict for persistence."""
        return asdict(self)


class LabelGenerator:
    """
    Generate training labels from trade data and OHLC candles.
    
    Usage:
        gen = LabelGenerator(
            horizons=[5, 10, 20],
            mfe_weight=1.0,
            mae_weight=0.5
        )
        labels = gen.generate_labels(
            trades=trades,  # List of closed trades
            candles=candles,  # OHLC data
            symbol="EURUSD"
        )
    """
    
    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        mfe_weight: float = 1.0,
        mae_weight: float = 0.5,
        db_path: Optional[str] = None
    ):
        """
        Initialize label generator.
        
        Args:
            horizons: Candle horizons to evaluate (default: [5, 10, 20])
            mfe_weight: Weight for MFE in quality score
            mae_weight: Weight for MAE (penalty)
            db_path: Database path (for persistence)
        """
        self.horizons = horizons or [5, 10, 20]
        self.mfe_weight = mfe_weight
        self.mae_weight = mae_weight
        self.db_path = db_path
    
    def generate_labels(
        self,
        trades: List[Dict],
        candles: List[Dict],
        symbol: str
    ) -> List[TradeLabel]:
        """
        Generate labels for trades.
        
        Args:
            trades: List of closed trades with keys:
                - timestamp: entry time
                - side: "BUY" or "SELL"
                - entry_price, tp1, tp2, sl
            candles: OHLC data (list of dicts with timestamp, o, h, l, c)
            symbol: Trading symbol
        
        Returns:
            List of TradeLabel objects
        """
        labels = []
        
        # Build timestamp -> candle map for quick lookup
        candle_map = {c["timestamp"]: c for c in candles}
        
        for trade in trades:
            entry_time = trade["timestamp"]
            
            # Find entry candle
            if entry_time not in candle_map:
                logger.warning(f"No candle for entry at {entry_time}")
                continue
            
            entry_candle_idx = next(
                (i for i, c in enumerate(candles) if c["timestamp"] == entry_time),
                None
            )
            if entry_candle_idx is None:
                continue
            
            # Evaluate each horizon
            tp1_hit = {}
            tp2_hit = {}
            mfe = {}
            mae = {}
            quality = {}
            
            for horizon in self.horizons:
                end_idx = min(entry_candle_idx + horizon, len(candles) - 1)
                horizon_candles = candles[entry_candle_idx:end_idx + 1]
                
                if not horizon_candles:
                    tp1_hit[horizon] = False
                    tp2_hit[horizon] = False
                    mfe[horizon] = 0.0
                    mae[horizon] = 0.0
                    quality[horizon] = 0.0
                    continue
                
                # Extract highs and lows
                highs = [c["h"] for c in horizon_candles]
                lows = [c["l"] for c in horizon_candles]
                
                # Calculate MFE and MAE
                if trade["side"] == "BUY":
                    max_high = max(highs)
                    min_low = min(lows)
                    
                    mfe[horizon] = (max_high - trade["entry_price"]) * 10000
                    mae[horizon] = (trade["entry_price"] - min_low) * 10000
                    
                    tp1_hit[horizon] = max_high >= trade["tp1"]
                    tp2_hit[horizon] = max_high >= trade["tp2"]
                
                else:  # SELL
                    max_high = max(highs)
                    min_low = min(lows)
                    
                    mfe[horizon] = (trade["entry_price"] - min_low) * 10000
                    mae[horizon] = (max_high - trade["entry_price"]) * 10000
                    
                    tp1_hit[horizon] = min_low <= trade["tp1"]
                    tp2_hit[horizon] = min_low <= trade["tp2"]
                
                # Quality score
                quality[horizon] = (
                    self.mfe_weight * mfe[horizon] -
                    self.mae_weight * mae[horizon]
                )
            
            label = TradeLabel(
                timestamp=entry_time,
                symbol=symbol,
                side=trade["side"],
                entry_price=trade["entry_price"],
                tp1=trade["tp1"],
                tp2=trade["tp2"],
                sl=trade["sl"],
                tp1_hit=tp1_hit,
                tp2_hit=tp2_hit,
                mfe=mfe,
                mae=mae,
                quality_score=quality
            )
            
            labels.append(label)
        
        logger.info(f"Generated {len(labels)} labels for {symbol}")
        return labels
    
    def get_best_quality_labels(
        self,
        labels: List[TradeLabel],
        horizon: int,
        percentile: float = 75.0
    ) -> List[TradeLabel]:
        """
        Filter labels by quality score.
        
        Returns only trades with quality above percentile.
        Useful for training on best setups.
        """
        if not labels:
            return []
        
        scores = [l.quality_score.get(horizon, 0) for l in labels]
        threshold = np.percentile(scores, percentile)
        
        filtered = [
            l for l in labels
            if l.quality_score.get(horizon, 0) >= threshold
        ]
        
        logger.info(
            f"Filtered to {len(filtered)} best-quality labels "
            f"(>{threshold:.2f} at {percentile:.0f}th percentile)"
        )
        
        return filtered
    
    def get_stats(self, labels: List[TradeLabel], horizon: int) -> Dict:
        """Get label statistics for a horizon."""
        if not labels:
            return {}
        
        tp1_hit_count = sum(1 for l in labels if l.tp1_hit.get(horizon, False))
        tp2_hit_count = sum(1 for l in labels if l.tp2_hit.get(horizon, False))
        
        mfe_values = [l.mfe.get(horizon, 0) for l in labels]
        mae_values = [l.mae.get(horizon, 0) for l in labels]
        quality_values = [l.quality_score.get(horizon, 0) for l in labels]
        
        return {
            "horizon": horizon,
            "total_labels": len(labels),
            "tp1_hit_rate": tp1_hit_count / len(labels),
            "tp2_hit_rate": tp2_hit_count / len(labels),
            "avg_mfe": np.mean(mfe_values),
            "avg_mae": np.mean(mae_values),
            "avg_quality": np.mean(quality_values),
            "median_quality": np.median(quality_values),
            "quality_std": np.std(quality_values)
        }
    
    def as_dict(self) -> Dict:
        """Export config as dict."""
        return {
            "horizons": self.horizons,
            "mfe_weight": self.mfe_weight,
            "mae_weight": self.mae_weight
        }
