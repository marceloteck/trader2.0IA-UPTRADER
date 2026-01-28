"""
Level 3 Tests: Regime Change Detection

Test CUSUM and BOCPD detectors for change point detection.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.features.regime_change import (
    CUSUMDetector, BOCPDSimplified, RegimeChangeDetector, RegimeChangeEvent
)


class TestCUSUMDetector:
    """Test CUSUM change point detector."""

    def test_initialization(self):
        """Test CUSUM initializes properly."""
        cusum = CUSUMDetector(threshold=5.0)
        assert cusum.threshold == 5.0
        assert cusum.cusum_pos == 0.0
        assert cusum.cusum_neg == 0.0

    def test_fit_baseline(self):
        """Test baseline fitting."""
        data = np.array([1.0, 1.05, 1.02, 0.98, 1.01, 0.99])
        cusum = CUSUMDetector()
        cusum.fit(data)
        
        assert cusum.reference_mean is not None
        assert cusum.reference_std is not None
        assert cusum.reference_std > 0

    def test_detects_mean_shift(self):
        """Test detection of mean shift."""
        cusum = CUSUMDetector(threshold=3.0)
        
        # Normal data
        for val in [1.0, 1.05, 0.98, 1.02]:
            cusum.fit(np.array([val]))
            cusum.update(val)
        
        # Shift up (sudden change)
        detected = False
        for val in [2.0, 2.1, 2.05, 2.08]:
            change, strength = cusum.update(val)
            if change:
                detected = True
                assert strength > 0
                break
        
        assert detected, "CUSUM should detect mean shift"

    def test_reset_cusum(self):
        """Test CUSUM reset functionality."""
        cusum = CUSUMDetector()
        cusum.cusum_pos = 10.0
        cusum.cusum_neg = 5.0
        
        cusum.reset()
        
        assert cusum.cusum_pos == 0.0
        assert cusum.cusum_neg == 0.0


class TestBOCPDSimplified:
    """Test Bayesian Online Change Point Detection."""

    def test_initialization(self):
        """Test BOCPD initializes properly."""
        bocpd = BOCPDSimplified(hazard_rate=0.01)
        assert bocpd.hazard_rate == 0.01
        assert len(bocpd.growth_probs) > 0

    def test_update_returns_probabilities(self):
        """Test BOCPD returns valid probabilities."""
        bocpd = BOCPDSimplified()
        
        # Feed some data
        for val in [1.0, 1.02, 0.98, 1.01]:
            prob, run_length = bocpd.update(val)
            
            assert 0 <= prob <= 1, f"Probability should be 0..1, got {prob}"
            assert run_length >= 0

    def test_detects_distribution_change(self):
        """Test BOCPD detects distribution change."""
        bocpd = BOCPDSimplified(hazard_rate=0.05)
        
        # Normal regime
        for val in np.random.normal(0, 1, 20):
            prob, _ = bocpd.update(val)
        
        # Changed regime
        max_prob = 0
        for val in np.random.normal(2, 1, 10):  # Shifted mean
            prob, _ = bocpd.update(val)
            max_prob = max(max_prob, prob)
        
        # Should detect change
        assert max_prob > 0.1, f"Should detect change, max_prob={max_prob}"

    def test_growth_probs_sum_to_one(self):
        """Test that growth probabilities sum to 1."""
        bocpd = BOCPDSimplified()
        
        for _ in range(10):
            bocpd.update(np.random.randn())
        
        total = sum(bocpd.growth_probs)
        assert abs(total - 1.0) < 0.01, f"Probs should sum to 1, got {total}"


class TestRegimeChangeDetector:
    """Test master regime change detector."""

    def test_initialization(self):
        """Test detector initializes."""
        detector = RegimeChangeDetector()
        assert detector.cusum is not None
        assert detector.bocpd is not None
        assert detector.min_history == 20

    def test_update_requires_min_history(self):
        """Test that update returns None with insufficient data."""
        detector = RegimeChangeDetector(min_history=20)
        
        prices = [100.0, 100.5, 99.8, 100.2]
        result = detector.update(prices, datetime.utcnow(), "EURUSD")
        
        assert result is None, "Should return None with insufficient history"

    def test_detect_normal_prices(self):
        """Test detection with normal price movement."""
        detector = RegimeChangeDetector(min_history=20)
        
        # Normal prices
        prices = [100.0 + np.sin(i * 0.1) * 2 for i in range(30)]
        result = detector.update(prices, datetime.utcnow(), "EURUSD")
        
        # Should not detect change in normal movement
        if result is not None:
            assert result.confidence < 0.7

    def test_detect_price_shock(self):
        """Test detection of price shock."""
        detector = RegimeChangeDetector(
            cusum_threshold=2.0,
            change_confidence_threshold=0.3
        )
        
        # Normal prices
        prices = list(np.random.normal(100, 1, 25))
        
        # Price shock
        prices.extend([110.0, 110.5, 110.2, 110.8])
        
        result = detector.update(prices, datetime.utcnow(), "EURUSD")
        
        # May detect shock
        if result is not None:
            assert result.change_detected

    def test_metric_changed_tracking(self):
        """Test that detector identifies which metric changed."""
        detector = RegimeChangeDetector(change_confidence_threshold=0.2)
        
        # Prices with high volatility shift
        prices = []
        for i in range(15):
            prices.append(100.0 + np.random.normal(0, 0.5))
        for i in range(15):
            prices.append(100.0 + np.random.normal(0, 3.0))  # Increased volatility
        
        result = detector.update(prices, datetime.utcnow(), "EURUSD")
        
        if result is not None:
            assert result.metric_changed in ['return', 'volatility', 'slope']

    def test_event_has_required_fields(self):
        """Test that RegimeChangeEvent has all required fields."""
        event = RegimeChangeEvent(
            time=datetime.utcnow(),
            symbol="EURUSD",
            change_detected=True,
            cusum_strength=0.8,
            bocpd_probability=0.6,
            metric_changed='volatility'
        )
        
        assert event.time is not None
        assert event.symbol == "EURUSD"
        assert event.change_detected
        assert 0 <= event.cusum_strength <= 1
        assert 0 <= event.bocpd_probability <= 1
        assert event.metric_changed in ['return', 'volatility', 'slope']
        assert event.combined_strength >= 0
        assert 0 <= event.confidence <= 1


class TestRegimeChangeIntegration:
    """Integration tests for regime change detection."""

    def test_full_workflow(self):
        """Test complete detection workflow."""
        detector = RegimeChangeDetector()
        time = datetime.utcnow()
        
        # Simulate trading day
        prices = [100.0]
        for i in range(50):
            if i < 25:
                # Normal movement
                prices.append(prices[-1] * (1 + np.random.normal(0, 0.001)))
            else:
                # Volatile movement (regime change)
                prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))
        
        # Try detection every bar
        for i in range(20, len(prices)):
            event = detector.update(
                prices[i-19:i+1],
                time + timedelta(minutes=i),
                "EURUSD"
            )
            
            if event is not None:
                assert event.change_detected
                assert event.confidence > 0

    def test_multiple_symbols(self):
        """Test detector with multiple symbols."""
        detector = RegimeChangeDetector()
        
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        
        for symbol in symbols:
            prices = [100.0 + i * 0.1 + np.random.randn() * 0.5 for i in range(30)]
            result = detector.update(prices, datetime.utcnow(), symbol)
            
            # Should handle all symbols without error
            assert result is None or isinstance(result, RegimeChangeEvent)

    def test_detector_memory(self):
        """Test that detector maintains history."""
        detector = RegimeChangeDetector()
        
        # First update
        prices1 = [100.0 + i * 0.1 for i in range(30)]
        detector.update(prices1, datetime.utcnow(), "EURUSD")
        
        # Second update with shift
        prices2 = [101.0 + i * 0.1 for i in range(30)]
        result = detector.update(prices2, datetime.utcnow(), "EURUSD")
        
        # Detector should have history
        assert len(detector.history['returns']) > 0 or result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
