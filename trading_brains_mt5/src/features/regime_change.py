"""
Level 3: Regime Change Detection

Two parallel detectors:
1. CUSUM (fast, lightweight) - detects abrupt changes
2. BOCPD Simplified (Bayesian Online Change Point Detection)

Outputs:
- change_detected: bool
- strength: 0..1
- metric: what changed (return/vol/slope)
- probability_of_change: 0..1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("trading_brains.features.regime_change")


@dataclass
class RegimeChangeEvent:
    """Regime change detection result."""
    time: datetime
    symbol: str
    change_detected: bool
    cusum_strength: float  # 0..1
    bocpd_probability: float  # 0..1
    metric_changed: str  # 'return' / 'volatility' / 'slope'
    cusum_details: Dict = field(default_factory=dict)
    bocpd_details: Dict = field(default_factory=dict)
    combined_strength: float = 0.0
    confidence: float = 0.0  # High confidence of actual change


class CUSUMDetector:
    """
    Cumulative Sum Control Chart - fast change point detector.
    Detects shifts in mean or variance.
    """

    def __init__(self, threshold: float = 5.0, drift: float = 0.5):
        """
        Initialize CUSUM detector.
        
        Args:
            threshold: Control limit (higher = less sensitive)
            drift: Drift factor for mean shift detection
        """
        self.threshold = threshold
        self.drift = drift
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.reference_mean = None
        self.reference_std = None
        self.history: List[float] = []
        self.change_points: List[int] = []

    def fit(self, data: np.ndarray) -> None:
        """Fit baseline statistics."""
        if len(data) >= 10:
            self.reference_mean = np.mean(data[-20:]) if len(data) >= 20 else np.mean(data)
            self.reference_std = np.std(data[-20:]) if len(data) >= 20 else np.std(data)
        else:
            self.reference_mean = np.mean(data)
            self.reference_std = np.std(data) if np.std(data) > 0 else 1.0

    def update(self, value: float) -> Tuple[bool, float]:
        """
        Update CUSUM and detect change.
        
        Returns:
            (change_detected, strength)
        """
        if self.reference_mean is None:
            self.fit(np.array([value]))
            return False, 0.0

        normalized = (value - self.reference_mean) / (self.reference_std + 1e-9)
        self.cusum_pos = max(0, self.cusum_pos + normalized - self.drift)
        self.cusum_neg = max(0, self.cusum_neg - normalized - self.drift)

        self.history.append(value)
        change_detected = self.cusum_pos > self.threshold or self.cusum_neg > self.threshold

        if change_detected:
            self.change_points.append(len(self.history) - 1)
            # Reset CUSUM
            strength = min(1.0, max(self.cusum_pos, self.cusum_neg) / (self.threshold * 2))
            return True, strength

        return False, 0.0

    def reset(self) -> None:
        """Reset for new regime."""
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0


class BOCPDSimplified:
    """
    Simplified Bayesian Online Change Point Detection.
    Lightweight version without heavy dependencies.
    """

    def __init__(self, hazard_rate: float = 1.0 / 100):
        """
        Initialize BOCPD.
        
        Args:
            hazard_rate: Prior probability of change at each step
        """
        self.hazard_rate = hazard_rate
        self.growth_probs = [1.0]  # P(r_t | x_{1:t})
        self.eval_points = []
        self.data = []
        self.change_prob = 0.0
        self.run_length = 0

    def update(self, value: float) -> Tuple[float, float]:
        """
        Update BOCPD with new observation.
        
        Returns:
            (probability_of_change, expected_run_length)
        """
        self.data.append(value)

        # Compute predictive probability under each run length
        n = len(self.data)
        
        # Simple likelihood: assume Normal distribution
        if len(self.data) < 2:
            self.change_prob = 0.0
            self.run_length = 0
            return 0.0, 0.0

        # Compute mean and std under each run
        likelihoods = []
        for r in range(len(self.growth_probs)):
            window_start = max(0, n - 1 - r) if r > 0 else n - 1
            window = self.data[window_start:n]
            
            if len(window) >= 1:
                mean = np.mean(window)
                std = np.std(window) if len(window) > 1 else 1.0
                std = max(std, 0.01)
                
                # Likelihood of current value under this run
                z = (value - mean) / std
                likelihood = np.exp(-0.5 * z * z) / (std * np.sqrt(2 * np.pi))
                likelihoods.append(likelihood)
            else:
                likelihoods.append(1.0)

        # Update growth probabilities
        new_growth_probs = []
        changepoint_prob = 0.0

        for r, prob in enumerate(self.growth_probs):
            new_prob = prob * likelihoods[r] * (1 - self.hazard_rate)
            new_growth_probs.append(new_prob)
            changepoint_prob += prob * likelihoods[r] * self.hazard_rate

        # Add new run length starting with changepoint
        if len(likelihoods) > 0:
            new_growth_probs.insert(0, changepoint_prob * likelihoods[0])

        # Normalize
        total_prob = sum(new_growth_probs)
        if total_prob > 0:
            self.growth_probs = [p / total_prob for p in new_growth_probs]
        else:
            self.growth_probs = [1.0 / len(new_growth_probs)] * len(new_growth_probs)

        # Compute probability of change and expected run length
        self.change_prob = changepoint_prob / (total_prob + 1e-9)
        self.run_length = np.argmax(self.growth_probs)

        return self.change_prob, float(self.run_length)


class RegimeChangeDetector:
    """
    Master detector combining CUSUM and BOCPD.
    """

    def __init__(
        self,
        cusum_threshold: float = 5.0,
        bocpd_hazard: float = 1.0 / 100,
        min_history: int = 20,
        change_confidence_threshold: float = 0.6
    ):
        """Initialize detector."""
        self.cusum = CUSUMDetector(threshold=cusum_threshold)
        self.bocpd = BOCPDSimplified(hazard_rate=bocpd_hazard)
        self.min_history = min_history
        self.change_confidence_threshold = change_confidence_threshold
        
        # Separate detectors for different metrics
        self.returns_detector = CUSUMDetector(threshold=cusum_threshold)
        self.volatility_detector = CUSUMDetector(threshold=cusum_threshold * 0.8)
        self.slope_detector = CUSUMDetector(threshold=cusum_threshold * 1.2)
        
        self.history: Dict[str, List[float]] = {
            'returns': [],
            'volatility': [],
            'slope': []
        }

    def update(
        self,
        close_prices: List[float],
        time: datetime,
        symbol: str
    ) -> Optional[RegimeChangeEvent]:
        """
        Detect regime changes from price data.
        
        Args:
            close_prices: Last N close prices (at least min_history)
            time: Current timestamp
            symbol: Symbol name
        
        Returns:
            RegimeChangeEvent or None
        """
        if len(close_prices) < self.min_history:
            return None

        # Compute metrics
        prices = np.array(close_prices[-self.min_history:])
        returns = np.diff(prices) / prices[:-1]
        
        # Volatility (rolling)
        volatility = np.std(returns) if len(returns) > 2 else 0.0
        
        # Slope of prices
        slope = (prices[-1] - prices[0]) / (len(prices) - 1)
        
        # Update detectors
        change_returns, strength_returns = self.returns_detector.update(returns[-1] if len(returns) > 0 else 0)
        change_vol, strength_vol = self.volatility_detector.update(volatility)
        change_slope, strength_slope = self.slope_detector.update(slope)
        
        # Store history
        self.history['returns'].append(returns[-1] if len(returns) > 0 else 0)
        self.history['volatility'].append(volatility)
        self.history['slope'].append(slope)
        
        # BOCPD update
        bocpd_prob, run_length = self.bocpd.update(volatility)
        
        # Combine signals
        any_change = change_returns or change_vol or change_slope or bocpd_prob > 0.5
        
        if not any_change:
            return None

        # Determine which metric changed
        strengths = {
            'return': strength_returns,
            'volatility': strength_vol,
            'slope': strength_slope
        }
        metric_changed = max(strengths, key=strengths.get)
        
        # Combined strength
        combined_strength = (strength_returns + strength_vol + strength_slope) / 3.0
        confidence = (combined_strength + bocpd_prob) / 2.0
        
        if confidence < self.change_confidence_threshold:
            return None

        return RegimeChangeEvent(
            time=time,
            symbol=symbol,
            change_detected=True,
            cusum_strength=combined_strength,
            bocpd_probability=bocpd_prob,
            metric_changed=metric_changed,
            cusum_details={
                'return_strength': strength_returns,
                'volatility_strength': strength_vol,
                'slope_strength': strength_slope,
            },
            bocpd_details={
                'run_length': int(run_length),
                'probability': bocpd_prob
            },
            combined_strength=combined_strength,
            confidence=confidence
        )

    def reset(self) -> None:
        """Reset all detectors."""
        self.cusum.reset()
        self.returns_detector.reset()
        self.volatility_detector.reset()
        self.slope_detector.reset()
        self.history = {k: [] for k in self.history}
