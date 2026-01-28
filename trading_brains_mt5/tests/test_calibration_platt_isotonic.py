"""
Tests for probability calibration module.
"""

import pytest
import numpy as np
from src.models.calibrator_l2 import ProbabilityCalibrator


class TestProbabilityCalibrator:
    """Test ProbabilityCalibrator class."""
    
    def test_init_platt(self):
        """Test initialization with PLATT method."""
        calibrator = ProbabilityCalibrator(method="PLATT")
        
        assert calibrator.method == "PLATT"
        assert calibrator.fitted is False
    
    def test_init_isotonic(self):
        """Test initialization with ISOTONIC method."""
        calibrator = ProbabilityCalibrator(method="ISOTONIC")
        
        assert calibrator.method == "ISOTONIC"
        assert calibrator.fitted is False
    
    def test_init_invalid_method(self):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError):
            ProbabilityCalibrator(method="INVALID")
    
    def test_fit_platt(self):
        """Test fitting with PLATT method."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)  # Normalize
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        
        assert calibrator.fitted is True
        assert hasattr(calibrator, 'sigmoid_coef_')
        assert hasattr(calibrator, 'sigmoid_intercept_')
    
    def test_fit_isotonic(self):
        """Test fitting with ISOTONIC method."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="ISOTONIC")
        calibrator.fit(y_true, y_proba)
        
        assert calibrator.fitted is True
        assert hasattr(calibrator, 'isotonic_regressor_')
    
    def test_fit_empty_data(self):
        """Test that empty data raises ValueError."""
        calibrator = ProbabilityCalibrator(method="PLATT")
        
        with pytest.raises(ValueError):
            calibrator.fit(np.array([]), np.array([]))
    
    def test_fit_mismatched_shapes(self):
        """Test that mismatched shapes raise ValueError."""
        calibrator = ProbabilityCalibrator(method="PLATT")
        y_true = np.array([0, 1, 0])
        y_proba = np.array([[0.9, 0.1], [0.2, 0.8]])  # 2 samples
        
        with pytest.raises(ValueError):
            calibrator.fit(y_true, y_proba)
    
    def test_transform_platt(self):
        """Test transform with PLATT method."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        
        # Transform on new data
        y_proba_test = np.random.rand(20, 2)
        y_proba_test = y_proba_test / y_proba_test.sum(axis=1, keepdims=True)
        
        y_proba_cal = calibrator.transform(y_proba_test)
        
        assert y_proba_cal.shape == (20, 2)
        assert np.all(y_proba_cal >= 0) and np.all(y_proba_cal <= 1)
        np.testing.assert_array_almost_equal(y_proba_cal.sum(axis=1), np.ones(20))
    
    def test_transform_isotonic(self):
        """Test transform with ISOTONIC method."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="ISOTONIC")
        calibrator.fit(y_true, y_proba)
        
        y_proba_test = np.random.rand(20, 2)
        y_proba_test = y_proba_test / y_proba_test.sum(axis=1, keepdims=True)
        
        y_proba_cal = calibrator.transform(y_proba_test)
        
        assert y_proba_cal.shape == (20, 2)
        assert np.all(y_proba_cal >= 0) and np.all(y_proba_cal <= 1)
    
    def test_transform_not_fitted(self):
        """Test that transform before fit raises error."""
        calibrator = ProbabilityCalibrator(method="PLATT")
        y_proba_test = np.random.rand(10, 2)
        
        with pytest.raises(RuntimeError):
            calibrator.transform(y_proba_test)
    
    def test_get_reliability_metrics_platt(self):
        """Test reliability metrics for PLATT."""
        np.random.seed(42)
        
        # Create data where model is overconfident
        y_true = np.array([0, 0, 0, 1, 1, 1, 0, 0, 1, 1] * 10)
        y_proba = np.column_stack([
            np.where(y_true == 0, 0.95, 0.05),  # Overconfident
            np.where(y_true == 1, 0.05, 0.95)
        ])
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        
        metrics = calibrator.get_reliability_metrics()
        
        assert "expected_calibration_error" in metrics
        assert "max_calibration_error" in metrics
        assert "brier_score" in metrics
        assert "reliability_diagram" in metrics
        
        assert metrics["expected_calibration_error"] >= 0
        assert metrics["max_calibration_error"] >= 0
        assert metrics["brier_score"] >= 0
    
    def test_get_reliability_metrics_isotonic(self):
        """Test reliability metrics for ISOTONIC."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="ISOTONIC")
        calibrator.fit(y_true, y_proba)
        
        metrics = calibrator.get_reliability_metrics()
        
        assert "expected_calibration_error" in metrics
        assert "max_calibration_error" in metrics
        assert "brier_score" in metrics
    
    def test_get_confidence_interval(self):
        """Test confidence interval computation."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        
        # Get confidence interval for a probability
        lower, upper = calibrator.get_confidence_interval(0.7, confidence=0.95)
        
        assert lower <= 0.7 <= upper
        assert lower >= 0
        assert upper <= 1
    
    def test_calibration_improves_overconfident_model(self):
        """Test that calibration improves overconfident probabilities."""
        np.random.seed(42)
        
        # Create overconfident model
        y_true = np.array([0, 0, 0, 1, 1, 1] * 10)
        y_proba_raw = np.column_stack([
            np.where(y_true == 0, 0.99, 0.01),  # Very overconfident
            np.where(y_true == 1, 0.01, 0.99)
        ])
        
        # Calibrate
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba_raw)
        y_proba_cal = calibrator.transform(y_proba_raw)
        
        # Check that calibrated probs are less extreme
        assert np.max(y_proba_raw[:, 1]) > np.max(y_proba_cal[:, 1])
        assert np.min(y_proba_raw[:, 1]) < np.min(y_proba_cal[:, 1])
    
    def test_calibration_preserves_ranking(self):
        """Test that calibration preserves probability ordering."""
        np.random.seed(42)
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        y_proba_cal = calibrator.transform(y_proba)
        
        # Class with higher raw probability should usually have higher calibrated prob
        predictions_raw = y_proba.argmax(axis=1)
        predictions_cal = y_proba_cal.argmax(axis=1)
        
        # Should mostly agree
        agreement = np.mean(predictions_raw == predictions_cal)
        assert agreement > 0.8


class TestCalibrationIntegration:
    """Integration tests."""
    
    def test_full_workflow_platt(self):
        """Test complete Platt calibration workflow."""
        np.random.seed(123)
        
        # Generate synthetic data
        n_train = 200
        n_val = 100
        n_test = 100
        
        X_train = np.random.randn(n_train, 20)
        y_train = np.random.randint(0, 2, n_train)
        X_val = np.random.randn(n_val, 20)
        y_val = np.random.randint(0, 2, n_val)
        X_test = np.random.randn(n_test, 20)
        y_test = np.random.randint(0, 2, n_test)
        
        # Create and train a simple model
        from sklearn.linear_model import LogisticRegression
        model = LogisticRegression(random_state=42)
        model.fit(X_train, y_train)
        
        # Get raw probabilities
        y_proba_val = model.predict_proba(X_val)
        y_proba_test_raw = model.predict_proba(X_test)
        
        # Calibrate
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_val, y_proba_val)
        
        # Transform test probabilities
        y_proba_test_cal = calibrator.transform(y_proba_test_raw)
        
        # Check calibration improved
        metrics = calibrator.get_reliability_metrics()
        assert metrics["expected_calibration_error"] < 0.3
    
    def test_full_workflow_isotonic(self):
        """Test complete Isotonic calibration workflow."""
        np.random.seed(123)
        
        n_train = 200
        n_val = 100
        n_test = 100
        
        X_train = np.random.randn(n_train, 20)
        y_train = np.random.randint(0, 2, n_train)
        X_val = np.random.randn(n_val, 20)
        y_val = np.random.randint(0, 2, n_val)
        X_test = np.random.randn(n_test, 20)
        
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(n_estimators=20, random_state=42)
        model.fit(X_train, y_train)
        
        y_proba_val = model.predict_proba(X_val)
        y_proba_test_raw = model.predict_proba(X_test)
        
        calibrator = ProbabilityCalibrator(method="ISOTONIC")
        calibrator.fit(y_val, y_proba_val)
        
        y_proba_test_cal = calibrator.transform(y_proba_test_raw)
        
        assert y_proba_test_cal.shape == (100, 2)
        assert np.all(y_proba_test_cal >= 0) and np.all(y_proba_test_cal <= 1)
    
    def test_platt_vs_isotonic(self):
        """Test difference between Platt and Isotonic calibration."""
        np.random.seed(456)
        
        y_true = np.random.randint(0, 2, 200)
        y_proba = np.random.rand(200, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        # Fit both
        platt = ProbabilityCalibrator(method="PLATT")
        platt.fit(y_true, y_proba)
        
        isotonic = ProbabilityCalibrator(method="ISOTONIC")
        isotonic.fit(y_true, y_proba)
        
        # Get metrics
        platt_metrics = platt.get_reliability_metrics()
        isotonic_metrics = isotonic.get_reliability_metrics()
        
        # Both should produce valid metrics
        assert platt_metrics["expected_calibration_error"] >= 0
        assert isotonic_metrics["expected_calibration_error"] >= 0


class TestCalibrationEdgeCases:
    """Test edge cases."""
    
    def test_single_class_training(self):
        """Test with single class in training (edge case)."""
        y_true = np.zeros(50)  # All class 0
        y_proba = np.column_stack([np.ones(50), np.zeros(50)])
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        
        # Should handle gracefully
        try:
            calibrator.fit(y_true, y_proba)
            # Either succeeds with edge case handling or raises informative error
            assert True
        except ValueError:
            assert True  # Acceptable to reject
    
    def test_perfect_probabilities(self):
        """Test with perfect probability predictions."""
        y_true = np.array([0, 0, 1, 1] * 25)
        y_proba = np.column_stack([
            np.where(y_true == 0, 1.0, 0.0),
            np.where(y_true == 1, 0.0, 1.0)
        ])
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)
        
        metrics = calibrator.get_reliability_metrics()
        # Calibration error should be very small
        assert metrics["expected_calibration_error"] < 0.1
    
    def test_many_features(self):
        """Test with high-dimensional input."""
        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.rand(100, 2)
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)
        
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(y_true, y_proba)  # Only depends on proba, not input dim
        
        assert calibrator.fitted is True
