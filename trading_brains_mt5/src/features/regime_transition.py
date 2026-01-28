"""
Level 3: Regime Transition Detection and Management

Defines explicit regime states and valid transitions.
Detects when the market is transitioning between states.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

logger = logging.getLogger("trading_brains.features.regime_transition")


class RegimeState(str, Enum):
    """Possible regime states."""
    RANGE = "RANGE"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    EXHAUSTION = "EXHAUSTION"
    HIGH_VOL = "HIGH_VOL"
    CHAOTIC = "CHAOTIC"
    UNKNOWN = "UNKNOWN"


@dataclass
class RegimeTransition:
    """Represents a regime transition."""
    time: datetime
    symbol: str
    from_regime: RegimeState
    to_regime: RegimeState
    confidence: float  # 0..1
    reasons: List[str]  # Why transition detected
    duration_minutes: int = 0


class RegimeTransitionDetector:
    """
    Detects transitions between regime states.
    Uses explicit rules and heuristics (no ML).
    """

    # Define valid transitions
    VALID_TRANSITIONS: Dict[RegimeState, Set[RegimeState]] = {
        RegimeState.RANGE: {RegimeState.TREND_UP, RegimeState.TREND_DOWN, RegimeState.CHAOTIC},
        RegimeState.TREND_UP: {RegimeState.EXHAUSTION, RegimeState.RANGE, RegimeState.CHAOTIC},
        RegimeState.TREND_DOWN: {RegimeState.EXHAUSTION, RegimeState.RANGE, RegimeState.CHAOTIC},
        RegimeState.EXHAUSTION: {RegimeState.RANGE, RegimeState.HIGH_VOL, RegimeState.CHAOTIC},
        RegimeState.HIGH_VOL: {RegimeState.RANGE, RegimeState.TREND_UP, RegimeState.TREND_DOWN, RegimeState.CHAOTIC},
        RegimeState.CHAOTIC: {RegimeState.RANGE},  # Only exit chaos via stabilization
        RegimeState.UNKNOWN: {RegimeState.RANGE, RegimeState.TREND_UP, RegimeState.TREND_DOWN},
    }

    def __init__(self, window_size: int = 20):
        """Initialize detector."""
        self.window_size = window_size
        self.current_regime = RegimeState.UNKNOWN
        self.regime_start_time = None
        self.transition_history: List[RegimeTransition] = []
        self.metrics_history: Dict[str, List[float]] = {
            'returns': [],
            'volatility': [],
            'upper_band': [],
            'lower_band': [],
            'slope': [],
            'atr': []
        }

    def detect_regime(
        self,
        close_prices: List[float],
        high_prices: List[float],
        low_prices: List[float],
        volume: List[float],
        time: datetime,
        symbol: str
    ) -> Tuple[RegimeState, float]:
        """
        Detect current regime from price/volume data.
        
        Returns:
            (regime_state, confidence)
        """
        if len(close_prices) < self.window_size:
            return RegimeState.UNKNOWN, 0.0

        prices = np.array(close_prices[-self.window_size:])
        highs = np.array(high_prices[-self.window_size:])
        lows = np.array(low_prices[-self.window_size:])
        vols = np.array(volume[-self.window_size:]) if volume else np.ones(len(prices))

        # Compute metrics
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        mean_return = np.mean(returns)
        
        # ATR (Average True Range)
        true_range = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs[1:] - prices[:-1]),
                np.abs(lows[1:] - prices[:-1])
            )
        )
        atr = np.mean(true_range)
        
        # Slope
        slope = (prices[-1] - prices[0]) / len(prices)
        slope_normalized = slope / (prices[0] + 1e-9)
        
        # Bollinger Band squeeze
        bb_middle = np.mean(prices)
        bb_std = np.std(prices)
        bb_width = 2 * bb_std / bb_middle if bb_middle > 0 else 0
        
        # Volume change
        recent_vol = np.mean(vols[-5:]) if len(vols) >= 5 else np.mean(vols)
        older_vol = np.mean(vols[-self.window_size:-5]) if len(vols) > 10 else np.mean(vols)
        vol_ratio = recent_vol / (older_vol + 1e-9)
        
        # Store metrics
        self.metrics_history['returns'].append(mean_return)
        self.metrics_history['volatility'].append(volatility)
        self.metrics_history['slope'].append(slope_normalized)
        self.metrics_history['atr'].append(atr)

        # Decision logic
        regime, confidence = self._classify_regime(
            mean_return=mean_return,
            volatility=volatility,
            slope=slope_normalized,
            atr=atr,
            bb_width=bb_width,
            vol_ratio=vol_ratio,
            prices=prices
        )

        return regime, confidence

    def _classify_regime(
        self,
        mean_return: float,
        volatility: float,
        slope: float,
        atr: float,
        bb_width: float,
        vol_ratio: float,
        prices: np.ndarray
    ) -> Tuple[RegimeState, float]:
        """Classify current regime based on metrics."""
        
        scores = {}
        
        # CHAOTIC: High volatility + high volume ratio
        if volatility > np.percentile([self.metrics_history['volatility'][-10:]], 90) if self.metrics_history['volatility'] else False:
            if vol_ratio > 1.5:
                scores[RegimeState.CHAOTIC] = 0.9
        
        # HIGH_VOL: High volatility but not chaotic
        if volatility > 0.03:
            scores[RegimeState.HIGH_VOL] = 0.75
        
        # TREND_UP or TREND_DOWN: Strong slope + moderate volatility
        abs_slope = abs(slope)
        if abs_slope > 0.01 and volatility < 0.03:
            if slope > 0:
                scores[RegimeState.TREND_UP] = 0.7
            else:
                scores[RegimeState.TREND_DOWN] = 0.7
        
        # EXHAUSTION: Weak slope + low volatility after strong trend
        if abs_slope < 0.005 and volatility < 0.015:
            if len(self.metrics_history['slope']) >= 5:
                recent_slopes = self.metrics_history['slope'][-5:]
                if any(abs(s) > 0.01 for s in recent_slopes):
                    scores[RegimeState.EXHAUSTION] = 0.65
        
        # RANGE: Low slope + low volatility + tight BB
        if abs_slope < 0.002 and volatility < 0.01 and bb_width < 0.02:
            scores[RegimeState.RANGE] = 0.8
        
        # Default
        if not scores:
            scores[RegimeState.RANGE] = 0.4
        
        # Pick highest confidence
        best_regime = max(scores, key=scores.get)
        confidence = scores[best_regime]
        
        return best_regime, confidence

    def update_regime(
        self,
        close_prices: List[float],
        high_prices: List[float],
        low_prices: List[float],
        volume: List[float],
        time: datetime,
        symbol: str
    ) -> Optional[RegimeTransition]:
        """
        Update regime and detect transitions.
        
        Returns:
            RegimeTransition if regime changed
        """
        new_regime, confidence = self.detect_regime(
            close_prices, high_prices, low_prices, volume, time, symbol
        )
        
        # Check for transition
        if new_regime != self.current_regime and new_regime != RegimeState.UNKNOWN:
            # Validate transition
            if new_regime in self.VALID_TRANSITIONS.get(self.current_regime, set()):
                transition = RegimeTransition(
                    time=time,
                    symbol=symbol,
                    from_regime=self.current_regime,
                    to_regime=new_regime,
                    confidence=confidence,
                    reasons=self._get_transition_reasons(
                        self.current_regime, new_regime, confidence
                    ),
                    duration_minutes=self._get_duration()
                )
                
                self.transition_history.append(transition)
                self.current_regime = new_regime
                self.regime_start_time = time
                
                logger.info(
                    f"Regime transition detected: {self.current_regime} "
                    f"-> {new_regime} (confidence={confidence:.2f})"
                )
                
                return transition
        
        return None

    def _get_transition_reasons(
        self,
        from_regime: RegimeState,
        to_regime: RegimeState,
        confidence: float
    ) -> List[str]:
        """Generate readable reasons for transition."""
        reasons = []
        
        if to_regime == RegimeState.CHAOTIC:
            reasons.append("High volatility detected")
            reasons.append("Market instability increasing")
        elif to_regime == RegimeState.TREND_UP:
            reasons.append("Uptrend emerging from range")
            reasons.append("Positive slope confirmed")
        elif to_regime == RegimeState.TREND_DOWN:
            reasons.append("Downtrend emerging from range")
            reasons.append("Negative slope confirmed")
        elif to_regime == RegimeState.EXHAUSTION:
            reasons.append("Trend losing strength")
            reasons.append("Volatility declining")
        elif to_regime == RegimeState.RANGE:
            reasons.append("Market stabilizing")
            reasons.append("Bounded movement detected")
        
        reasons.append(f"Confidence: {confidence:.1%}")
        return reasons

    def _get_duration(self) -> int:
        """Get duration of current regime in minutes."""
        if self.regime_start_time is None:
            return 0
        return int((datetime.utcnow() - self.regime_start_time).total_seconds() / 60)

    def get_current_regime(self) -> RegimeState:
        """Get current regime state."""
        return self.current_regime

    def is_in_transition(self) -> bool:
        """Check if system is currently transitioning."""
        if len(self.transition_history) < 2:
            return False
        
        last_transition = self.transition_history[-1]
        time_since = (datetime.utcnow() - last_transition.time).total_seconds() / 60
        
        # Consider in transition for 10 minutes after detected change
        return time_since < 10

    def get_recent_transitions(self, minutes: int = 60) -> List[RegimeTransition]:
        """Get transitions from last N minutes."""
        cutoff = (datetime.utcnow().timestamp() - minutes * 60)
        return [
            t for t in self.transition_history
            if t.time.timestamp() > cutoff
        ]
