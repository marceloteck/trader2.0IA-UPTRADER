"""
Cross-Market Brain - L6 Multi-Market Correlation & Spread Analysis

Monitors correlation and spread/ratio between primary symbol and cross-market symbols.
Detects over-extension via Z-score and correlation breaks. Provides filtering/confirmation
signals for BossBrain decisions.

Architecture:
    1. Rolling Correlation: Calculate corr(primary, cross) in sliding windows
    2. Spread/Beta Model: Estimate spread = primary - beta*cross using rolling regression
    3. Z-Score Detection: (spread - mean) / std to detect over-extension
    4. Correlation Break: Detect rapid changes or extreme values
    5. Signals: Filter/confirm BossBrain trades based on above metrics

Signals (for BossBrain filtering):
    - CONFIRM_BUY: spread is low (WIN underpriced vs WDO) or corr is healthy
    - REDUCE_BUY: spread is high (WIN overpriced) or corr is broken
    - CONFIRM_SELL: spread is high or corr healthy
    - REDUCE_SELL: spread is low or corr broken
    - MARKET_BROKEN: correlation near 0 or changed rapidly (reduce all agressiveness)

Persistence:
    - cross_metrics: time, symbol, corr_fast, corr_slow, beta, spread, zscore, flags_json
    - cross_signals: time, symbol, signal_json (signal type, strength, reason)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CrossMetric:
    """Cross-market metric record at a point in time."""
    timestamp: datetime
    symbol: str
    corr_fast: Optional[float] = None  # Fast correlation (e.g., 50 candles)
    corr_slow: Optional[float] = None  # Slow correlation (e.g., 200 candles)
    beta: Optional[float] = None  # Regression coefficient
    spread: Optional[float] = None  # primary - beta*cross
    spread_mean: Optional[float] = None  # Rolling mean of spread
    spread_std: Optional[float] = None  # Rolling std of spread
    zscore: Optional[float] = None  # (spread - mean) / std
    corr_fast_prev: Optional[float] = None  # Previous fast corr for change detection
    corr_change_pct: Optional[float] = None  # % change in fast corr bar-to-bar
    flags: Dict[str, bool] = field(default_factory=dict)  # "spread_high", "spread_low", "corr_broken", etc
    
    def to_dict(self) -> dict:
        """Convert to dict for database storage."""
        return {
            'timestamp': self.timestamp,
            'symbol': self.symbol,
            'corr_fast': self.corr_fast,
            'corr_slow': self.corr_slow,
            'beta': self.beta,
            'spread': self.spread,
            'spread_mean': self.spread_mean,
            'spread_std': self.spread_std,
            'zscore': self.zscore,
            'corr_change_pct': self.corr_change_pct,
            'flags_json': json.dumps(self.flags) if self.flags else '{}'
        }


@dataclass
class CrossSignal:
    """Cross-market signal for filtering/confirmation."""
    timestamp: datetime
    symbol: str
    signal_type: str  # CONFIRM_BUY, REDUCE_BUY, CONFIRM_SELL, REDUCE_SELL, MARKET_BROKEN, NEUTRAL
    strength: float  # 0-1, confidence level
    reasons: List[str] = field(default_factory=list)  # Why this signal was generated
    metrics: Dict[str, float] = field(default_factory=dict)  # Supporting metrics
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'strength': self.strength,
            'signal_json': json.dumps({
                'signal_type': self.signal_type,
                'strength': self.strength,
                'reasons': self.reasons,
                'metrics': self.metrics
            })
        }


class CrossMarketBrain:
    """
    Analyzes cross-market correlations and spreads for multi-symbol trading.
    
    Usage:
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N', 'IBOV'],
            corr_windows=[50, 200],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            corr_broken_band=(-0.2, 0.2)
        )
        
        # Feed data each bar
        brain.update(primary_ohlc_df, cross_data_dict, now)
        
        # Get signals
        metric = brain.get_latest_metric('WIN$N')
        signal = brain.get_latest_signal('WIN$N')
        
        # Use signal to filter BossBrain
        if signal.signal_type in ['REDUCE_BUY', 'MARKET_BROKEN']:
            confidence_factor *= signal.strength  # Reduce trade confidence
    """
    
    def __init__(
        self,
        primary_symbol: str,
        cross_symbols: List[str],
        corr_windows: List[int],
        spread_window: int,
        z_threshold: float,
        beta_window: int,
        corr_broken_band: Tuple[float, float] = (-0.2, 0.2),
        min_data_points: int = 10
    ):
        """
        Initialize CrossMarketBrain.
        
        Args:
            primary_symbol: Main trading symbol (e.g., 'WIN$N')
            cross_symbols: Symbols to correlate against (e.g., ['WDO$N', 'IBOV'])
            corr_windows: List of window sizes for rolling correlation
            spread_window: Window for rolling mean/std of spread
            z_threshold: Z-score threshold for over-extension (e.g., 2.0)
            beta_window: Window for rolling beta calculation
            corr_broken_band: (min, max) correlation range; outside = broken correlation
            min_data_points: Minimum bars needed before generating signals
        """
        self.primary_symbol = primary_symbol
        self.cross_symbols = cross_symbols
        self.corr_windows = sorted(corr_windows)
        self.spread_window = spread_window
        self.z_threshold = z_threshold
        self.beta_window = beta_window
        self.corr_broken_band = corr_broken_band
        self.min_data_points = min_data_points
        
        # Historical data storage per symbol
        self.primary_data: pd.DataFrame = pd.DataFrame()  # close prices
        self.cross_data: Dict[str, pd.DataFrame] = {sym: pd.DataFrame() for sym in cross_symbols}
        
        # Latest metrics and signals
        self.latest_metrics: Dict[str, CrossMetric] = {}
        self.latest_signals: Dict[str, CrossSignal] = {}
        
        # History for reporting
        self.metric_history: Dict[str, List[CrossMetric]] = {}
        self.signal_history: Dict[str, List[CrossSignal]] = {}
    
    def update(
        self,
        primary_ohlc: pd.DataFrame,
        cross_data_dict: Dict[str, pd.DataFrame],
        now: datetime
    ) -> Tuple[Optional[CrossMetric], Optional[CrossSignal]]:
        """
        Update with latest OHLC data and generate signals.
        
        Args:
            primary_ohlc: DataFrame with primary symbol OHLC (must have 'close' column)
            cross_data_dict: Dict of symbol -> OHLC DataFrame for cross symbols
            now: Current timestamp
            
        Returns:
            (latest_metric, latest_signal) for primary symbol, or (None, None) if insufficient data
        """
        try:
            # Extract close prices
            if 'close' not in primary_ohlc.columns or primary_ohlc.empty:
                logger.warning(f"Invalid primary OHLC data at {now}")
                return None, None
            
            # Update historical data
            primary_close = primary_ohlc['close'].values
            self.primary_data = pd.DataFrame({
                'close': primary_close,
                'timestamp': primary_ohlc.get('timestamp', range(len(primary_close)))
            })
            
            for sym, ohlc_df in cross_data_dict.items():
                if sym not in self.cross_symbols:
                    continue
                if 'close' not in ohlc_df.columns or ohlc_df.empty:
                    logger.warning(f"Invalid cross symbol {sym} data at {now}")
                    self.cross_data[sym] = pd.DataFrame()
                    continue
                self.cross_data[sym] = pd.DataFrame({
                    'close': ohlc_df['close'].values
                })
            
            # Check minimum data points
            if len(self.primary_data) < self.min_data_points:
                logger.debug(f"Insufficient data for {self.primary_symbol}: {len(self.primary_data)} < {self.min_data_points}")
                return None, None
            
            # Calculate metrics for first cross symbol (main analysis)
            if not self.cross_symbols or self.cross_symbols[0] not in self.cross_data or self.cross_data[self.cross_symbols[0]].empty:
                logger.warning(f"No valid cross-market data for {self.cross_symbols[0]}")
                return None, None
            
            primary_closes = self.primary_data['close'].values
            cross_closes = self.cross_data[self.cross_symbols[0]]['close'].values
            
            # Ensure same length
            min_len = min(len(primary_closes), len(cross_closes))
            primary_closes = primary_closes[-min_len:]
            cross_closes = cross_closes[-min_len:]
            
            if min_len < self.min_data_points:
                return None, None
            
            # Calculate returns
            primary_returns = np.diff(np.log(primary_closes))
            cross_returns = np.diff(np.log(cross_closes))
            
            # Calculate correlations
            metric = self._calculate_metrics(primary_closes, cross_closes, primary_returns, cross_returns, now)
            
            # Generate signal based on metrics
            signal = self._generate_signal(metric, now)
            
            # Store
            self.latest_metrics[self.primary_symbol] = metric
            self.latest_signals[self.primary_symbol] = signal
            
            if self.primary_symbol not in self.metric_history:
                self.metric_history[self.primary_symbol] = []
                self.signal_history[self.primary_symbol] = []
            
            self.metric_history[self.primary_symbol].append(metric)
            self.signal_history[self.primary_symbol].append(signal)
            
            # Trim history to last 500 records
            if len(self.metric_history[self.primary_symbol]) > 500:
                self.metric_history[self.primary_symbol] = self.metric_history[self.primary_symbol][-500:]
            if len(self.signal_history[self.primary_symbol]) > 500:
                self.signal_history[self.primary_symbol] = self.signal_history[self.primary_symbol][-500:]
            
            return metric, signal
            
        except Exception as e:
            logger.error(f"Error updating CrossMarketBrain: {e}", exc_info=True)
            return None, None
    
    def _calculate_metrics(
        self,
        primary_closes: np.ndarray,
        cross_closes: np.ndarray,
        primary_returns: np.ndarray,
        cross_returns: np.ndarray,
        now: datetime
    ) -> CrossMetric:
        """Calculate cross-market metrics."""
        metric = CrossMetric(timestamp=now, symbol=self.primary_symbol)
        
        try:
            # Correlations
            for window in self.corr_windows:
                if len(primary_returns) >= window:
                    corr = np.corrcoef(primary_returns[-window:], cross_returns[-window:])[0, 1]
                    if np.isnan(corr):
                        corr = 0.0
                    if window == self.corr_windows[0]:
                        metric.corr_fast = corr
                    else:
                        metric.corr_slow = corr
            
            # Beta (regression coefficient)
            if len(cross_returns) >= self.beta_window:
                cross_ret_window = cross_returns[-self.beta_window:]
                primary_ret_window = primary_returns[-self.beta_window:]
                if np.std(cross_ret_window) > 1e-6:
                    metric.beta = np.cov(primary_ret_window, cross_ret_window)[0, 1] / np.var(cross_ret_window)
                else:
                    metric.beta = 1.0
            else:
                metric.beta = 1.0
            
            # Spread and Z-score
            if metric.beta is not None and len(cross_closes) >= self.spread_window:
                spread = primary_closes[-1] - metric.beta * cross_closes[-1]
                
                # Calculate rolling mean and std
                spreads = primary_closes[-self.spread_window:] - metric.beta * cross_closes[-self.spread_window:]
                metric.spread_mean = np.mean(spreads)
                metric.spread_std = np.std(spreads)
                metric.spread = spread
                
                if metric.spread_std > 1e-6:
                    metric.zscore = (spread - metric.spread_mean) / metric.spread_std
                else:
                    metric.zscore = 0.0
            
            # Flags
            metric.flags = {}
            
            if metric.zscore is not None:
                if metric.zscore > self.z_threshold:
                    metric.flags['spread_high'] = True  # Primary overpriced
                elif metric.zscore < -self.z_threshold:
                    metric.flags['spread_low'] = True  # Primary underpriced
            
            # Correlation break detection
            if metric.corr_fast is not None:
                if metric.corr_fast < self.corr_broken_band[0] or metric.corr_fast > self.corr_broken_band[1]:
                    metric.flags['corr_broken'] = True
            
            return metric
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return metric
    
    def _generate_signal(self, metric: CrossMetric, now: datetime) -> CrossSignal:
        """Generate trading signal based on metrics."""
        signal = CrossSignal(
            timestamp=now,
            symbol=self.primary_symbol,
            signal_type='NEUTRAL',
            strength=0.5,
            reasons=[],
            metrics={}
        )
        
        try:
            # Check for market broken first (high priority)
            if metric.flags.get('corr_broken', False):
                signal.signal_type = 'MARKET_BROKEN'
                signal.strength = 0.3  # Severely reduce confidence
                signal.reasons.append(f"Correlation broken: {metric.corr_fast:.3f}")
                signal.metrics['corr_fast'] = metric.corr_fast
                return signal
            
            # Check spread-based signals
            has_spread_high = metric.flags.get('spread_high', False)
            has_spread_low = metric.flags.get('spread_low', False)
            
            if has_spread_high:
                # Primary overpriced - favor SELL, reduce BUY
                signal.signal_type = 'REDUCE_BUY' if metric.corr_fast and metric.corr_fast > 0.3 else 'CONFIRM_SELL'
                signal.strength = min(0.8, abs(metric.zscore) / self.z_threshold)
                signal.reasons.append(f"Spread high (zscore={metric.zscore:.2f}): {self.primary_symbol} overpriced")
            
            elif has_spread_low:
                # Primary underpriced - favor BUY, reduce SELL
                signal.signal_type = 'CONFIRM_BUY' if metric.corr_fast and metric.corr_fast > 0.3 else 'REDUCE_SELL'
                signal.strength = min(0.8, abs(metric.zscore) / self.z_threshold)
                signal.reasons.append(f"Spread low (zscore={metric.zscore:.2f}): {self.primary_symbol} underpriced")
            
            else:
                # No extreme spread; default behavior
                signal.signal_type = 'NEUTRAL'
                signal.strength = 0.5
                signal.reasons.append("Spread within normal range")
            
            # Store metrics for reference
            signal.metrics = {
                'corr_fast': metric.corr_fast,
                'corr_slow': metric.corr_slow,
                'zscore': metric.zscore,
                'beta': metric.beta,
                'spread': metric.spread
            }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return signal
    
    def get_latest_metric(self, symbol: str) -> Optional[CrossMetric]:
        """Get latest metric for symbol."""
        return self.latest_metrics.get(symbol)
    
    def get_latest_signal(self, symbol: str) -> Optional[CrossSignal]:
        """Get latest signal for symbol."""
        return self.latest_signals.get(symbol)
    
    def get_metric_history(self, symbol: str, limit: int = 100) -> List[CrossMetric]:
        """Get metric history for symbol (last N records)."""
        if symbol not in self.metric_history:
            return []
        return self.metric_history[symbol][-limit:]
    
    def get_signal_history(self, symbol: str, limit: int = 100) -> List[CrossSignal]:
        """Get signal history for symbol (last N records)."""
        if symbol not in self.signal_history:
            return []
        return self.signal_history[symbol][-limit:]
    
    def export_stats(self) -> dict:
        """Export statistics for reporting."""
        stats = {}
        for symbol in [self.primary_symbol]:
            metric = self.get_latest_metric(symbol)
            signal = self.get_latest_signal(symbol)
            stats[symbol] = {
                'latest_metric': asdict(metric) if metric else None,
                'latest_signal': asdict(signal) if signal else None,
                'metric_count': len(self.metric_history.get(symbol, [])),
                'signal_count': len(self.signal_history.get(symbol, []))
            }
        return stats
