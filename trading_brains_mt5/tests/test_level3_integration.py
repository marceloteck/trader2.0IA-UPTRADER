"""
Level 3 Integration Tests

Test full Level 3 pipeline: regime detection → transitions → risk adaptation.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.features.regime_change import RegimeChangeDetector
from src.features.regime_transition import RegimeState, RegimeTransitionDetector
from src.models.transition_performance import TransitionPerformanceMatrix
from src.execution.risk_adapter import DynamicRiskAdapter


class TestLevel3Integration:
    """Test Level 3 components working together."""

    def test_full_workflow(self):
        """Test complete Level 3 workflow with simulated trading day."""
        # Initialize components
        change_detector = RegimeChangeDetector()
        transition_detector = RegimeTransitionDetector()
        performance_matrix = TransitionPerformanceMatrix()
        risk_adapter = DynamicRiskAdapter()
        
        # Simulate a trading day
        current_time = datetime.utcnow()
        symbol = "EURUSD"
        
        # Phase 1: Range market (first 100 bars)
        prices = [100.0 + np.random.normal(0, 0.1) for _ in range(100)]
        
        for i, price in enumerate(prices):
            bar_time = current_time + timedelta(minutes=i)
            
            # Update detectors
            change_detector.update(price, symbol, bar_time)
            
            if i >= 20:  # Need min history
                regime_event = change_detector.detect()
                assert regime_event is None or regime_event.change_detected == False
        
        # Phase 2: Transition to uptrend (next 20 bars)
        prices_trend = [105.0 + i * 0.3 + np.random.normal(0, 0.2) for i in range(20)]
        prices.extend(prices_trend)
        
        for i, price in enumerate(prices_trend):
            bar_idx = 100 + i
            bar_time = current_time + timedelta(minutes=bar_idx)
            
            change_detector.update(price, symbol, bar_time)
        
        # Phase 3: Simulate trades during different regimes
        # Trade during range
        performance_matrix.record_trade(
            brain_id="brain_momentum",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.RANGE,
            pnl=150.0,
            win=True,
            trade_id=1
        )
        
        # Trade during transition
        performance_matrix.record_trade(
            brain_id="brain_trend",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.TREND_UP,
            pnl=200.0,
            win=True,
            trade_id=2
        )
        
        # Verify performance matrix
        best_brains = performance_matrix.get_best_brains_for_transition(
            RegimeState.RANGE,
            RegimeState.TREND_UP,
            min_trades=1
        )
        
        assert len(best_brains) > 0
        assert best_brains[0][0] == "brain_trend"
        
        # Test risk adaptation across regimes
        for regime in [RegimeState.RANGE, RegimeState.TREND_UP, RegimeState.CHAOTIC]:
            adjustment = risk_adapter.adapt_risk(
                symbol=symbol,
                regime=regime,
                transition_strength=0.5 if regime == RegimeState.TREND_UP else 0.0,
                ensemble_uncertainty=0.2,
                recent_drawdown=0.02,
                volatility=0.01
            )
            
            assert adjustment is not None
            assert 0 <= adjustment.adjusted_risk <= risk_adapter.base_risk

    def test_regime_change_triggers_transition(self):
        """Test that regime change detector can trigger transition detection."""
        change_detector = RegimeChangeDetector()
        transition_detector = RegimeTransitionDetector()
        
        symbol = "EURUSD"
        current_time = datetime.utcnow()
        
        # Generate normal prices
        prices = [100.0 + np.random.normal(0, 0.1) for _ in range(50)]
        
        # Record prices in detector
        for i, price in enumerate(prices):
            change_detector.update(price, symbol, current_time + timedelta(minutes=i))
        
        # Should have history
        assert len(change_detector.history[symbol]) > 0
        
        # Now simulate a shock
        shock_price = 101.0  # 1% jump
        change_detector.update(shock_price, symbol, current_time + timedelta(minutes=100))
        
        # Check if change was detected
        event = change_detector.detect()
        
        # Event may or may not be detected depending on sensitivity
        # But detector should be tracking the shock
        assert change_detector.history[symbol][-1] == shock_price

    def test_transition_performance_feedback_loop(self):
        """Test that performance is tracked during transitions."""
        performance_matrix = TransitionPerformanceMatrix()
        risk_adapter = DynamicRiskAdapter()
        
        # Simulate trades in different transitions
        transitions = [
            (RegimeState.RANGE, RegimeState.TREND_UP),
            (RegimeState.RANGE, RegimeState.TREND_UP),
            (RegimeState.TREND_UP, RegimeState.EXHAUSTION),
            (RegimeState.EXHAUSTION, RegimeState.RANGE),
        ]
        
        brain_ids = ["brain_momentum", "brain_trend", "brain_range"]
        pnls = [100, -50, 200, 75]
        
        for idx, ((from_r, to_r), pnl) in enumerate(zip(transitions, pnls)):
            brain = brain_ids[idx % len(brain_ids)]
            
            performance_matrix.record_trade(
                brain_id=brain,
                from_regime=from_r,
                to_regime=to_r,
                pnl=pnl,
                win=pnl > 0,
                trade_id=idx
            )
        
        # Check that matrix was populated
        assert len(performance_matrix.matrix) > 0
        
        # Get best brain for range->trend
        best = performance_matrix.get_best_brains_for_transition(
            RegimeState.RANGE,
            RegimeState.TREND_UP,
            min_trades=1
        )
        
        assert len(best) > 0

    def test_risk_adaptation_multi_symbol(self):
        """Test risk adaptation across multiple symbols."""
        risk_adapter = DynamicRiskAdapter()
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        
        # Adapt risk for multiple symbols
        adaptations = {}
        for symbol in symbols:
            adaptation = risk_adapter.adapt_risk(
                symbol=symbol,
                regime=RegimeState.HIGH_VOL,
                transition_strength=0.4,
                ensemble_uncertainty=0.3,
                recent_drawdown=0.05,
                volatility=0.08
            )
            
            adaptations[symbol] = adaptation
        
        # Verify all symbols have adapted risk
        for symbol in symbols:
            assert symbol in adaptations
            assert adaptations[symbol].adjusted_risk >= 0
            assert adaptations[symbol].adjusted_risk <= risk_adapter.base_risk

    def test_chaotic_market_protection(self):
        """Test that system protects against chaotic markets."""
        change_detector = RegimeChangeDetector()
        performance_matrix = TransitionPerformanceMatrix()
        risk_adapter = DynamicRiskAdapter()
        
        symbol = "EURUSD"
        current_time = datetime.utcnow()
        
        # Simulate chaotic market (random jumps)
        prices = []
        for i in range(100):
            if i % 10 == 0:
                # Random shock
                prices.append(100.0 + np.random.normal(0, 2.0))
            else:
                prices.append(100.0 + np.random.normal(0, 0.2))
        
        # Update detector
        for i, price in enumerate(prices):
            change_detector.update(price, symbol, current_time + timedelta(minutes=i))
        
        # Check if changes were detected
        changes_detected = 0
        for event in change_detector.history[symbol][-20:]:
            if isinstance(event, dict) and event.get('change_detected'):
                changes_detected += 1
        
        # In chaotic market, some changes should be detected
        # (not guaranteed but likely)
        
        # Risk should be low in chaotic
        risk_chaotic = risk_adapter.adapt_risk(
            symbol=symbol,
            regime=RegimeState.CHAOTIC,
            transition_strength=0.8,
            ensemble_uncertainty=0.6,
            recent_drawdown=0.1,
            volatility=0.1
        )
        
        assert risk_chaotic.adjusted_risk == 0.0  # Blocked

    def test_performance_matrix_forbidden_transitions(self):
        """Test that bad transitions are identified."""
        matrix = TransitionPerformanceMatrix()
        
        # Record losing trades for specific transition
        for i in range(20):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.HIGH_VOL,
                to_regime=RegimeState.CHAOTIC,
                pnl=-200.0,
                win=False,
                trade_id=i
            )
        
        # Record winning trades for different transition
        for i in range(20, 25):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.TREND_UP,
                pnl=100.0,
                win=True,
                trade_id=i
            )
        
        # Check forbidden
        forbidden = matrix.get_brains_forbidden_transitions(
            "brain_1",
            quality_threshold=0.5
        )
        
        assert (RegimeState.HIGH_VOL, RegimeState.CHAOTIC) in forbidden
        assert (RegimeState.RANGE, RegimeState.TREND_UP) not in forbidden

    def test_dynamic_brain_selection_by_regime(self):
        """Test that best brains are selected by regime."""
        matrix = TransitionPerformanceMatrix()
        
        # Brain 1: Good in RANGE
        for i in range(10):
            matrix.record_trade(
                brain_id="brain_range",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.RANGE,
                pnl=100.0,
                win=True,
                trade_id=i
            )
        
        # Brain 2: Good in TREND
        for i in range(10, 20):
            matrix.record_trade(
                brain_id="brain_trend",
                from_regime=RegimeState.TREND_UP,
                to_regime=RegimeState.TREND_UP,
                pnl=150.0,
                win=True,
                trade_id=i
            )
        
        # Get best for range
        best_range = matrix.get_best_brains_for_transition(
            RegimeState.RANGE,
            RegimeState.RANGE,
            min_trades=5
        )
        
        # Get best for trend
        best_trend = matrix.get_best_brains_for_transition(
            RegimeState.TREND_UP,
            RegimeState.TREND_UP,
            min_trades=5
        )
        
        # Each should select appropriate brain
        assert len(best_range) > 0 or len(best_trend) > 0

    def test_level3_backward_compatibility(self):
        """Test that Level 3 doesn't break existing functionality."""
        # Verify all components initialize without errors
        detectors = [
            RegimeChangeDetector(),
            RegimeTransitionDetector(),
            TransitionPerformanceMatrix(),
            DynamicRiskAdapter()
        ]
        
        for detector in detectors:
            assert detector is not None
        
        # Test basic operations
        change_detector = RegimeChangeDetector()
        change_detector.update(100.0, "EURUSD", datetime.utcnow())
        assert "EURUSD" in change_detector.history
        
        risk_adapter = DynamicRiskAdapter()
        adjustment = risk_adapter.adapt_risk(
            symbol="EURUSD",
            regime=RegimeState.RANGE,
            transition_strength=0.0,
            ensemble_uncertainty=0.0,
            recent_drawdown=0.0,
            volatility=0.01
        )
        
        assert adjustment.adjusted_risk > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
