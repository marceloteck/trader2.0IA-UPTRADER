"""
Level 3 Tests: Regime Transitions

Test transition detection and performance tracking.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.features.regime_transition import (
    RegimeState, RegimeTransitionDetector, RegimeTransition
)
from src.models.transition_performance import (
    TransitionPerformanceMatrix, TransitionMetrics
)


class TestRegimeState:
    """Test RegimeState enum."""

    def test_regime_states_defined(self):
        """Test all regime states are defined."""
        states = [
            RegimeState.RANGE,
            RegimeState.TREND_UP,
            RegimeState.TREND_DOWN,
            RegimeState.EXHAUSTION,
            RegimeState.HIGH_VOL,
            RegimeState.CHAOTIC,
            RegimeState.UNKNOWN
        ]
        
        assert len(states) == 7
        
        for state in states:
            assert isinstance(state, RegimeState)


class TestRegimeTransitionDetector:
    """Test regime transition detector."""

    def test_initialization(self):
        """Test detector initializes."""
        detector = RegimeTransitionDetector()
        assert detector.window_size == 20
        assert detector.current_regime == RegimeState.UNKNOWN

    def test_valid_transitions_defined(self):
        """Test that valid transitions are properly defined."""
        transitions = RegimeTransitionDetector.VALID_TRANSITIONS
        
        assert RegimeState.CHAOTIC in transitions
        assert RegimeState.RANGE in transitions
        assert RegimeState.TREND_UP in transitions

    def test_detect_range_regime(self):
        """Test detection of RANGE regime."""
        detector = RegimeTransitionDetector(window_size=20)
        
        # Flat prices (range)
        prices = [100.0 + np.random.normal(0, 0.1) for _ in range(30)]
        highs = [max(prices[max(0,i-1):i+2]) for i in range(len(prices))]
        lows = [min(prices[max(0,i-1):i+2]) for i in range(len(prices))]
        volumes = [1000.0] * len(prices)
        
        regime, confidence = detector.detect_regime(
            prices, highs, lows, volumes, datetime.utcnow(), "EURUSD"
        )
        
        assert regime in [RegimeState.RANGE, RegimeState.UNKNOWN]

    def test_detect_trend_up(self):
        """Test detection of TREND_UP regime."""
        detector = RegimeTransitionDetector(window_size=20)
        
        # Uptrend
        prices = [100.0 + i * 0.5 + np.random.normal(0, 0.2) for i in range(30)]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        volumes = [1000.0] * len(prices)
        
        regime, confidence = detector.detect_regime(
            prices, highs, lows, volumes, datetime.utcnow(), "EURUSD"
        )
        
        # Should detect uptrend or high vol
        assert regime in [RegimeState.TREND_UP, RegimeState.HIGH_VOL, RegimeState.UNKNOWN]

    def test_detect_high_volatility(self):
        """Test detection of HIGH_VOL regime."""
        detector = RegimeTransitionDetector(window_size=20)
        
        # High volatility
        prices = [100.0 + np.random.normal(0, 5.0) for _ in range(30)]
        highs = [max(prices[max(0,i-1):i+2]) + 1 for i in range(len(prices))]
        lows = [min(prices[max(0,i-1):i+2]) - 1 for i in range(len(prices))]
        volumes = [2000.0] * len(prices)  # Higher volume
        
        regime, confidence = detector.detect_regime(
            prices, highs, lows, volumes, datetime.utcnow(), "EURUSD"
        )
        
        # Should detect high vol or chaotic
        assert regime in [RegimeState.HIGH_VOL, RegimeState.CHAOTIC]

    def test_update_regime_transitions(self):
        """Test regime transition detection."""
        detector = RegimeTransitionDetector()
        
        # Start with flat prices
        prices = [100.0 + np.random.normal(0, 0.1) for _ in range(30)]
        highs = [p + 0.1 for p in prices]
        lows = [p - 0.1 for p in prices]
        volumes = [1000.0] * len(prices)
        
        # First update
        detector.update_regime(prices, highs, lows, volumes, datetime.utcnow(), "EURUSD")
        first_regime = detector.current_regime
        
        # Change to uptrend
        prices = [100.0 + i * 0.5 + np.random.normal(0, 0.2) for i in range(30)]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        
        transition = detector.update_regime(
            prices, highs, lows, volumes, datetime.utcnow(), "EURUSD"
        )
        
        # Should either transition or update regime
        assert detector.current_regime in RegimeTransitionDetector.VALID_TRANSITIONS.get(first_regime, set())

    def test_is_in_transition(self):
        """Test transition state detection."""
        detector = RegimeTransitionDetector()
        
        assert not detector.is_in_transition()
        
        # Add a recent transition
        detector.transition_history.append(RegimeTransition(
            time=datetime.utcnow(),
            symbol="EURUSD",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.TREND_UP,
            confidence=0.7,
            reasons=["test"]
        ))
        
        assert detector.is_in_transition()

    def test_get_recent_transitions(self):
        """Test retrieval of recent transitions."""
        detector = RegimeTransitionDetector()
        
        # Add transitions
        now = datetime.utcnow()
        detector.transition_history.append(RegimeTransition(
            time=now - timedelta(minutes=5),
            symbol="EURUSD",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.TREND_UP,
            confidence=0.7,
            reasons=["recent"]
        ))
        
        detector.transition_history.append(RegimeTransition(
            time=now - timedelta(minutes=120),
            symbol="EURUSD",
            from_regime=RegimeState.TREND_UP,
            to_regime=RegimeState.EXHAUSTION,
            confidence=0.6,
            reasons=["old"]
        ))
        
        recent = detector.get_recent_transitions(minutes=60)
        assert len(recent) == 1
        assert recent[0].reasons[0] == "recent"


class TestTransitionPerformanceMatrix:
    """Test performance matrix for transitions."""

    def test_initialization(self):
        """Test matrix initializes."""
        matrix = TransitionPerformanceMatrix()
        assert len(matrix.matrix) == 0
        assert len(matrix.recent_trades) == 0

    def test_record_trade(self):
        """Test recording a trade."""
        matrix = TransitionPerformanceMatrix()
        
        matrix.record_trade(
            brain_id="brain_1",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.TREND_UP,
            pnl=100.0,
            win=True,
            trade_id=1
        )
        
        assert len(matrix.recent_trades) == 1
        assert "brain_1" in matrix.matrix

    def test_update_metrics(self):
        """Test metric updates."""
        matrix = TransitionPerformanceMatrix()
        
        # Record winning trades
        for i in range(5):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.TREND_UP,
                pnl=50.0,
                win=True,
                trade_id=i
            )
        
        # Record losing trade
        matrix.record_trade(
            brain_id="brain_1",
            from_regime=RegimeState.RANGE,
            to_regime=RegimeState.TREND_UP,
            pnl=-25.0,
            win=False,
            trade_id=5
        )
        
        metrics = matrix.get_brain_metrics(
            "brain_1",
            RegimeState.RANGE,
            RegimeState.TREND_UP
        )
        
        assert metrics is not None
        assert metrics.trade_count == 6
        assert metrics.win_count == 5
        assert metrics.winrate == 5/6
        assert metrics.quality_score > 0

    def test_get_best_brains_for_transition(self):
        """Test ranking brains by performance."""
        matrix = TransitionPerformanceMatrix()
        
        # Brain 1: good performance
        for i in range(10):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.TREND_UP,
                pnl=100.0,
                win=True,
                trade_id=i
            )
        
        # Brain 2: poor performance
        for i in range(10):
            matrix.record_trade(
                brain_id="brain_2",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.TREND_UP,
                pnl=-50.0,
                win=False,
                trade_id=100+i
            )
        
        best = matrix.get_best_brains_for_transition(
            RegimeState.RANGE,
            RegimeState.TREND_UP,
            min_trades=5
        )
        
        assert len(best) == 2
        assert best[0][0] == "brain_1"  # Brain 1 ranked first
        assert best[0][1] > best[1][1]  # Brain 1 has higher quality

    def test_forbidden_transitions(self):
        """Test identification of forbidden transitions."""
        matrix = TransitionPerformanceMatrix()
        
        # Add losing trades for specific transition
        for i in range(10):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.HIGH_VOL,
                to_regime=RegimeState.CHAOTIC,
                pnl=-100.0,
                win=False,
                trade_id=i
            )
        
        forbidden = matrix.get_brains_forbidden_transitions(
            "brain_1",
            quality_threshold=0.5
        )
        
        assert (RegimeState.HIGH_VOL, RegimeState.CHAOTIC) in forbidden

    def test_get_transition_statistics(self):
        """Test aggregate statistics."""
        matrix = TransitionPerformanceMatrix()
        
        for i in range(5):
            matrix.record_trade(
                brain_id="brain_1",
                from_regime=RegimeState.RANGE,
                to_regime=RegimeState.TREND_UP,
                pnl=100.0,
                win=True,
                trade_id=i
            )
        
        stats = matrix.get_overall_transition_stats(
            RegimeState.RANGE,
            RegimeState.TREND_UP
        )
        
        assert stats['total_trades'] == 5
        assert stats['avg_quality'] > 0
        assert stats['best_quality'] > 0

    def test_matrix_summary(self):
        """Test summary generation."""
        matrix = TransitionPerformanceMatrix()
        
        matrix.record_trade("brain_1", RegimeState.RANGE, RegimeState.TREND_UP, 100, True, 1)
        
        summary = matrix.print_matrix_summary()
        
        assert "brain_1" in summary
        assert "Transition Performance Matrix" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
