"""
Level 3 Tests: Dynamic Risk Adapter

Test risk adjustment system and position sizing.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.execution.risk_adapter import DynamicRiskAdapter, RiskAdjustment
from src.features.regime_transition import RegimeState


class TestDynamicRiskAdapter:
    """Test dynamic risk adaptation."""

    def test_initialization(self):
        """Test adapter initializes with default values."""
        adapter = DynamicRiskAdapter(base_risk=0.02)
        
        assert adapter.base_risk == 0.02
        assert len(adapter.history) == 0
        assert adapter.regime_risk_factors[RegimeState.CHAOTIC] == 0.0
        assert adapter.regime_risk_factors[RegimeState.HIGH_VOL] == 0.7

    def test_custom_config(self):
        """Test adapter with custom configuration."""
        custom_factors = {
            RegimeState.RANGE: 0.95,
            RegimeState.TREND_UP: 1.0,
            RegimeState.TREND_DOWN: 1.0,
            RegimeState.EXHAUSTION: 0.5,
            RegimeState.HIGH_VOL: 0.6,
            RegimeState.CHAOTIC: 0.0
        }
        
        adapter = DynamicRiskAdapter(
            base_risk=0.025,
            regime_risk_factors=custom_factors
        )
        
        assert adapter.regime_risk_factors[RegimeState.TREND_UP] == 1.0

    def test_regime_based_adjustment(self):
        """Test risk adjustment by regime."""
        adapter = DynamicRiskAdapter()
        
        # Normal regime
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        assert adjustment.adjusted_risk > 0
        assert adjustment.original_risk == adapter.base_risk
        assert RegimeState.RANGE in str(adjustment.reason)

    def test_chaotic_regime_blocks_trading(self):
        """Test that chaotic regime blocks trading."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.CHAOTIC,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.05
        )
        
        assert adjustment.adjusted_risk == 0.0
        assert adjustment.risk_factor == 0.0

    def test_transition_reduces_risk(self):
        """Test that in-transition reduces risk."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.8,  # In transition
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        assert adjustment.adjusted_risk < adapter.base_risk
        assert adjustment.risk_factor < 1.0

    def test_high_volatility_reduces_risk(self):
        """Test that high volatility reduces risk."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.1  # High volatility
        )
        
        # Risk should be reduced by volatility
        assert adjustment.adjusted_risk < adapter.base_risk
        assert "volatility" in adjustment.reason.lower()

    def test_drawdown_reduces_risk(self):
        """Test that recent drawdown reduces risk."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.05,  # 5% drawdown
            volatility=0.01
        )
        
        assert adjustment.adjusted_risk <= adapter.base_risk

    def test_ensemble_uncertainty_reduces_risk(self):
        """Test that ensemble uncertainty reduces risk."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.5,  # High uncertainty
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        assert adjustment.adjusted_risk <= adapter.base_risk

    def test_combined_risk_factors(self):
        """Test combination of multiple risk factors."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.HIGH_VOL,
            transition_strength=0.5,
            ensemble_uncertainty=0.3,
            recent_drawdown=0.03,
            volatility=0.08
        )
        
        # All factors should reduce risk
        assert adjustment.adjusted_risk < adapter.base_risk
        assert adjustment.risk_factor < 1.0

    def test_get_current_risk(self):
        """Test retrieving current risk for symbol."""
        adapter = DynamicRiskAdapter()
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        current_risk = adapter.get_current_risk("EURUSD")
        
        assert current_risk is not None
        assert current_risk == adjustment.adjusted_risk

    def test_get_position_size(self):
        """Test position size calculation."""
        adapter = DynamicRiskAdapter(base_risk=0.02)
        
        adjustment = adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        # Simulate position sizing
        balance = 10000.0
        stop_distance = 50.0  # pips
        
        position_size = adapter.get_position_size(
            symbol="EURUSD",
            balance=balance,
            stop_distance=stop_distance
        )
        
        # Should be reasonable (positive)
        assert position_size > 0
        assert isinstance(position_size, float)

    def test_position_size_zero_in_chaotic(self):
        """Test position size is zero in chaotic regime."""
        adapter = DynamicRiskAdapter()
        
        adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.CHAOTIC,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.05
        )
        
        position_size = adapter.get_position_size(
            symbol="EURUSD",
            balance=10000.0,
            stop_distance=50.0
        )
        
        assert position_size == 0.0

    def test_history_tracking(self):
        """Test that adjustments are tracked."""
        adapter = DynamicRiskAdapter()
        
        for i in range(5):
            adapter.adapt_risk(
                symbol="EURUSD",
                regime=RegimeState.RANGE,
                transition_strength=0.0,
                ensemble_uncertainty=0.0,
                recent_drawdown=0.0,
                volatility=0.01
            )
        
        assert len(adapter.history) >= 5

    def test_multiple_symbols(self):
        """Test handling of multiple symbols."""
        adapter = DynamicRiskAdapter()
        
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        
        for symbol in symbols:
            adapter.adapt_risk(
                symbol=symbol,
                regime=RegimeState.RANGE,
                transition_strength=0.0,
                ensemble_uncertainty=0.0,
                recent_drawdown=0.0,
                volatility=0.01
            )
        
        for symbol in symbols:
            assert adapter.get_current_risk(symbol) is not None

    def test_reset_for_symbol(self):
        """Test reset of symbol state."""
        adapter = DynamicRiskAdapter()
        
        # Create state
        adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        # Reset
        adapter.reset_for_symbol("EURUSD")
        
        # Should reset to None
        assert adapter.get_current_risk("EURUSD") is None

    def test_summary_stats(self):
        """Test summary statistics."""
        adapter = DynamicRiskAdapter()
        
        # Create adjustments
        for i in range(10):
            adapter.adapt_risk(
                symbol="EURUSD",
                regime=RegimeState.RANGE if i % 2 == 0 else RegimeState.HIGH_VOL,
                transition_strength=0.0,
                ensemble_uncertainty=0.0,
                recent_drawdown=0.0,
                volatility=0.01 * (i + 1)
            )
        
        stats = adapter.summary_stats()
        
        assert stats is not None
        assert len(stats) > 0

    def test_risk_adjustment_dataclass(self):
        """Test RiskAdjustment dataclass."""
        adjustment = RiskAdjustment(
            time=datetime.utcnow(),
            symbol="EURUSD",
            original_risk=0.02,
            adjusted_risk=0.015,
            risk_factor=0.75,
            reason="Chaotic regime",
            regime=RegimeState.HIGH_VOL,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0
        )
        
        assert adjustment.original_risk == 0.02
        assert adjustment.adjusted_risk == 0.015
        assert adjustment.risk_factor == 0.75
        assert adjustment.regime == RegimeState.HIGH_VOL

    def test_reasonable_risk_bounds(self):
        """Test that adjusted risk stays within reasonable bounds."""
        adapter = DynamicRiskAdapter(base_risk=0.02)
        
        extreme_cases = [
            (RegimeState.CHAOTIC, 1.0, 0.5, 0.1, 0.1),  # Extreme: chaotic, transition, uncertainty, DD, vol
            (RegimeState.RANGE, 0.0, 0.0, 0.0, 0.0),     # Normal: range, no issues
            (RegimeState.HIGH_VOL, 0.8, 0.3, 0.08, 0.06), # Extreme: high vol, transition, uncertainty, DD, vol
        ]
        
        for regime, trans, ens, dd, vol in extreme_cases:
            adjustment = adapter.adapt_risk(
                symbol="EURUSD",
                regime=regime,
                transition_strength=trans,
                ensemble_uncertainty=ens,
                recent_drawdown=dd,
                volatility=vol
            )
            
            # Risk should be between 0 and base_risk
            assert 0 <= adjustment.adjusted_risk <= adapter.base_risk


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
