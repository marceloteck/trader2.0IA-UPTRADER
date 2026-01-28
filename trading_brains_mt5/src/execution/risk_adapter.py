"""
Level 3 & 4: Dynamic Risk Adaptation

Adjusts risk based on regime transitions, market conditions, and liquidity.

Features:
- Level 3: Regime-based risk adjustment (NORMAL/TRANSITION/CHAOTIC)
- Level 4: Liquidity-aware risk adjustment (zone strength, nearby support/resistance)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Tuple
import numpy as np

from ..features.regime_transition import RegimeState

logger = logging.getLogger("trading_brains.execution.risk_adapter")


@dataclass
class RiskAdjustment:
    """Represents a risk adjustment event."""
    time: datetime
    symbol: str
    original_risk: float
    adjusted_risk: float
    risk_factor: float  # Multiplier: adjusted = original * factor
    reason: str
    regime: Optional[RegimeState] = None
    transition_strength: float = 0.0
    ensemble_uncertainty: float = 0.0
    recent_drawdown: float = 0.0
    # Level 4 additions
    liquidity_strength: float = 0.5  # 0-1, strength of nearby zones
    liquidity_adjustment: float = 1.0  # Adjustment factor from liquidity
    zone_count: int = 0  # Number of nearby zones


class DynamicRiskAdapter:
    """
    Adapts trading risk based on market conditions.
    
    Factors:
    - Regime state
    - Transition strength
    - Ensemble disagreement (Level 2)
    - Recent drawdown
    - Volatility
    """

    def __init__(
        self,
        base_risk: float = 0.02,  # 2% per trade
        transition_risk_factor: float = 0.5,
        chaotic_risk_factor: float = 0.0,
        high_vol_risk_factor: float = 0.7,
        dd_risk_reduction_per_percent: float = 0.01
    ):
        """Initialize risk adapter."""
        self.base_risk = base_risk
        self.transition_risk_factor = transition_risk_factor
        self.chaotic_risk_factor = chaotic_risk_factor
        self.high_vol_risk_factor = high_vol_risk_factor
        self.dd_risk_reduction_per_percent = dd_risk_reduction_per_percent
        
        self.history: Dict[str, list] = {}
        self.current_risk: Dict[str, float] = {}

    def adapt_risk(
        self,
        symbol: str,
        current_regime: RegimeState,
        in_transition: bool = False,
        transition_strength: float = 0.0,
        ensemble_uncertainty: float = 0.0,
        recent_drawdown: float = 0.0,
        volatility: float = 0.0,
        time: datetime = None
    ) -> RiskAdjustment:
        """
        Calculate adjusted risk based on conditions.
        
        Args:
            symbol: Trading symbol
            current_regime: Current regime state
            in_transition: Whether transitioning between regimes
            transition_strength: Strength of transition (0..1)
            ensemble_uncertainty: Uncertainty from ensemble (0..1)
            recent_drawdown: Recent drawdown as percentage (0..1)
            volatility: Current volatility
            time: Timestamp for adjustment
        
        Returns:
            RiskAdjustment with new risk level
        """
        if time is None:
            time = datetime.utcnow()
        
        adjusted_risk = self.base_risk
        reasons = []
        risk_factor = 1.0
        
        # Factor 1: Regime-based adjustment
        if current_regime == RegimeState.CHAOTIC:
            risk_factor *= self.chaotic_risk_factor
            reasons.append("Chaotic regime: risk to 0")
        elif current_regime == RegimeState.HIGH_VOL:
            risk_factor *= self.high_vol_risk_factor
            reasons.append("High volatility: reduced risk")
        elif current_regime in [RegimeState.TREND_UP, RegimeState.TREND_DOWN]:
            risk_factor *= 1.0  # Normal risk in trends
            reasons.append("Trend regime: normal risk")
        elif current_regime == RegimeState.RANGE:
            risk_factor *= 0.9  # Slightly reduced in range
            reasons.append("Range regime: slightly reduced risk")
        elif current_regime == RegimeState.EXHAUSTION:
            risk_factor *= 0.6
            reasons.append("Exhaustion regime: reduced risk")
        
        # Factor 2: Transition-based adjustment
        if in_transition:
            transition_factor = (1 - transition_strength) * self.transition_risk_factor + transition_strength
            risk_factor *= transition_factor
            reasons.append(f"In transition (strength={transition_strength:.2f})")
        
        # Factor 3: Ensemble uncertainty (from Level 2)
        if ensemble_uncertainty > 0.7:
            uncertainty_factor = 1.0 - (ensemble_uncertainty - 0.7) * 0.5
            risk_factor *= uncertainty_factor
            reasons.append(f"High ensemble uncertainty ({ensemble_uncertainty:.2f})")
        
        # Factor 4: Drawdown-based reduction
        if recent_drawdown > 0:
            dd_factor = max(0.1, 1.0 - recent_drawdown * self.dd_risk_reduction_per_percent)
            risk_factor *= dd_factor
            reasons.append(f"Recent drawdown ({recent_drawdown:.1%}): reduced by {(1-dd_factor):.1%}")
        
        # Factor 5: Volatility adjustment
        if volatility > 0.05:  # High volatility
            vol_factor = max(0.5, 1.0 - (volatility - 0.05) / 0.1)
            risk_factor *= vol_factor
            reasons.append(f"High volatility ({volatility:.3f})")
        
        # Apply factor to base risk
        adjusted_risk = self.base_risk * risk_factor
        adjusted_risk = max(0.0, min(self.base_risk, adjusted_risk))  # Clamp
        
        adjustment = RiskAdjustment(
            time=time,
            symbol=symbol,
            original_risk=self.base_risk,
            adjusted_risk=adjusted_risk,
            risk_factor=risk_factor,
            reason=" | ".join(reasons) if reasons else "No adjustment",
            regime=current_regime,
            transition_strength=transition_strength,
            ensemble_uncertainty=ensemble_uncertainty,
            recent_drawdown=recent_drawdown
        )
        
        # Store adjustment
        if symbol not in self.history:
            self.history[symbol] = []
        
        self.history[symbol].append(adjustment)
        self.current_risk[symbol] = adjusted_risk
        
        if risk_factor != 1.0:
            logger.info(
                f"Risk adjustment for {symbol}: "
                f"{self.base_risk:.3f} -> {adjusted_risk:.3f} "
                f"(factor={risk_factor:.2f}, regime={current_regime.value})"
            )
        
        return adjustment

    def get_current_risk(self, symbol: str) -> float:
        """Get current risk for symbol."""
        return self.current_risk.get(symbol, self.base_risk)

    def get_position_size(
        self,
        symbol: str,
        account_balance: float,
        entry_price: float
    ) -> float:
        """
        Calculate position size in units.
        
        Formula: position_size = (account_balance * risk) / (entry_price * stop_distance)
        """
        risk = self.get_current_risk(symbol)
        
        # Simplified: assume stop is 2% from entry
        stop_distance = entry_price * 0.02
        
        position_size = (account_balance * risk) / stop_distance
        return max(0, position_size)

    def get_risk_reduction_reason(self, symbol: str) -> Optional[str]:
        """Get reason for latest risk reduction, if any."""
        if symbol not in self.history or not self.history[symbol]:
            return None
        
        latest = self.history[symbol][-1]
        
        if latest.risk_factor < 1.0:
            return latest.reason
        
        return None

    def reset_for_symbol(self, symbol: str) -> None:
        """Reset risk tracking for symbol."""
        self.current_risk[symbol] = self.base_risk
        if symbol in self.history:
            self.history[symbol] = []

    def get_adjustment_history(self, symbol: str, limit: int = 100) -> list:
        """Get recent risk adjustments for symbol."""
        if symbol not in self.history:
            return []
        
        return self.history[symbol][-limit:]

    def summary_stats(self, symbol: str) -> Dict[str, float]:
        """Get summary statistics of risk adjustments."""
        if symbol not in self.history or not self.history[symbol]:
            return {
                'total_adjustments': 0,
                'avg_risk_factor': 1.0,
                'min_risk': self.base_risk,
                'max_risk': self.base_risk,
                'pct_time_reduced': 0.0
            }
        
        adjustments = self.history[symbol]
        risk_factors = [a.risk_factor for a in adjustments]
        
        return {
            'total_adjustments': len(adjustments),
            'avg_risk_factor': np.mean(risk_factors),
            'min_risk': min(a.adjusted_risk for a in adjustments),
            'max_risk': max(a.adjusted_risk for a in adjustments),
            'pct_time_reduced': sum(1 for f in risk_factors if f < 1.0) / len(risk_factors) if risk_factors else 0
        }

    def adjust_risk_for_liquidity(
        self,
        adjustment: RiskAdjustment,
        liquidity_strength: float,
        zone_count: int,
        weak_liquidity_factor: float = 0.8
    ) -> RiskAdjustment:
        """
        Further adjust risk based on liquidity conditions (Level 4).
        
        Args:
            adjustment: Current risk adjustment
            liquidity_strength: Strength of nearby zones (0-1)
            zone_count: Number of nearby liquidity zones
            weak_liquidity_factor: Risk multiplier when liquidity is weak (< 0.55)
        
        Returns:
            Updated RiskAdjustment with liquidity factors
        """
        # Weak liquidity increases uncertainty
        if liquidity_strength < 0.55:
            liquidity_adjustment = weak_liquidity_factor
        elif liquidity_strength < 0.70:
            liquidity_adjustment = 0.9
        else:
            liquidity_adjustment = 1.0
        
        # Few zones (< 2) also increases uncertainty
        if zone_count < 2:
            liquidity_adjustment *= 0.85
        
        # Update adjustment
        original_adjusted = adjustment.adjusted_risk
        adjustment.adjusted_risk *= liquidity_adjustment
        adjustment.risk_factor *= liquidity_adjustment
        adjustment.liquidity_strength = liquidity_strength
        adjustment.liquidity_adjustment = liquidity_adjustment
        adjustment.zone_count = zone_count
        adjustment.reason += f" | Liquidity: {liquidity_strength:.2f} ({zone_count} zones)"
        
        if liquidity_adjustment != 1.0:
            logger.debug(
                f"Liquidity adjustment for {adjustment.symbol}: "
                f"{original_adjusted:.3f} -> {adjustment.adjusted_risk:.3f} "
                f"(strength={liquidity_strength:.2f}, zones={zone_count})"
            )
        
        return adjustment

