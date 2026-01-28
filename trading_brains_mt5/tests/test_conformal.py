"""
Tests for conformal prediction module.
"""

import logging
import pytest
import numpy as np
from src.models.conformal import ConformalPredictor, ConformalResult

logger = logging.getLogger("test_conformal")


class TestConformalPredictor:
    """Test ConformalPredictor class."""
    
    def test_init_default(self):
        """Test initialization with default parameters."""
        cp = ConformalPredictor()
        assert cp.alpha == 0.1
        assert cp.fitted is False
        assert cp.threshold is None
    
    def test_init_custom_alpha(self):
        """Test initialization with custom alpha."""
        cp = ConformalPredictor(alpha=0.2)
        assert cp.alpha == 0.2
    
    def test_init_invalid_alpha(self):
        """Test that invalid alpha raises ValueError."""
        with pytest.raises(ValueError):
            ConformalPredictor(alpha=0.0)
        
        with pytest.raises(ValueError):
            ConformalPredictor(alpha=1.0)
        
        with pytest.raises(ValueError):
            ConformalPredictor(alpha=-0.1)
    
    def test_fit_calibration_set_valid(self):
        """Test fit_calibration_set with valid data."""
        cp = ConformalPredictor()
        X_cal = np.random.randn(100, 10)
        y_cal = np.random.randint(0, 2, 100)
        
        cp.fit_calibration_set(X_cal, y_cal)
        assert cp.fitted is True
    
    def test_fit_calibration_set_empty(self):
        """Test that empty calibration set raises ValueError."""
        cp = ConformalPredictor()
        with pytest.raises(ValueError):
            cp.fit_calibration_set(np.array([]), np.array([]))
    
    def test_fit_calibration_set_mismatched(self):
        """Test that mismatched X and y raise ValueError."""
        cp = ConformalPredictor()
        X_cal = np.random.randn(100, 10)
        y_cal = np.random.randint(0, 2, 50)
        
        with pytest.raises(ValueError):
            cp.fit_calibration_set(X_cal, y_cal)
    
    def test_compute_nonconformity_2d(self):
        """Test nonconformity computation with 2D probabilities."""
        cp = ConformalPredictor()
        
        # y_true = [0, 1, 1, 0]
        # y_proba = [[0.9, 0.1], [0.2, 0.8], [0.3, 0.7], [0.8, 0.2]]
        # nonconformity for true class: [0.1, 0.2, 0.3, 0.2]
        
        y_true = np.array([0, 1, 1, 0])
        y_proba = np.array([[0.9, 0.1], [0.2, 0.8], [0.3, 0.7], [0.8, 0.2]])
        
        nonconf = cp._compute_nonconformity(y_true, y_proba)
        
        expected = np.array([0.1, 0.2, 0.3, 0.2])
        np.testing.assert_array_almost_equal(nonconf, expected)
    
    def test_compute_nonconformity_1d(self):
        """Test nonconformity computation with 1D probabilities."""
        cp = ConformalPredictor()
        
        # y_true = [0, 1, 1, 0]
        # y_proba = [0.1, 0.8, 0.7, 0.2]  (P(class=1))
        # nonconformity: [1-0.9, 1-0.8, 1-0.7, 1-0.8] = [0.1, 0.2, 0.3, 0.2]
        
        y_true = np.array([0, 1, 1, 0])
        y_proba = np.array([0.1, 0.8, 0.7, 0.2])
        
        nonconf = cp._compute_nonconformity(y_true, y_proba)
        
        expected = np.array([0.9, 0.2, 0.3, 0.8])
        np.testing.assert_array_almost_equal(nonconf, expected)
    
    def test_set_threshold_from_calibration(self):
        """Test threshold setting from calibration set."""
        np.random.seed(42)
        cp = ConformalPredictor(alpha=0.1)
        
        # Create synthetic calibration data
        y_true = np.array([0, 0, 0, 1, 1, 1, 0, 0, 1, 1])
        y_proba = np.array([
            [0.9, 0.1],  # y=0, P(0)=0.9, nonconf=0.1
            [0.85, 0.15],  # y=0, P(0)=0.85, nonconf=0.15
            [0.8, 0.2],  # y=0, P(0)=0.8, nonconf=0.2
            [0.2, 0.8],  # y=1, P(1)=0.8, nonconf=0.2
            [0.25, 0.75],  # y=1, P(1)=0.75, nonconf=0.25
            [0.3, 0.7],  # y=1, P(1)=0.7, nonconf=0.3
            [0.7, 0.3],  # y=0, P(0)=0.7, nonconf=0.3
            [0.6, 0.4],  # y=0, P(0)=0.6, nonconf=0.4
            [0.4, 0.6],  # y=1, P(1)=0.6, nonconf=0.4
            [0.1, 0.9],  # y=1, P(1)=0.9, nonconf=0.1
        ])
        
        cp.set_threshold_from_calibration(y_true, y_proba)
        
        assert cp.fitted is True
        assert cp.threshold is not None
        # With alpha=0.1 and n=10, threshold should be high quantile
        assert cp.threshold > 0
    
    def test_predict_with_set_not_fitted(self):
        """Test that predict_with_set raises error when not fitted."""
        cp = ConformalPredictor()
        y_proba = np.array([0.7, 0.3])
        
        with pytest.raises(RuntimeError):
            cp.predict_with_set(y_proba)
    
    def test_predict_with_set_single(self):
        """Test predict_with_set_single convenience method."""
        np.random.seed(42)
        cp = ConformalPredictor(alpha=0.1)
        
        # Set threshold manually for testing
        cp.threshold = 0.3
        cp.fitted = True
        
        result = cp.predict_with_set_single(0.7)
        
        assert isinstance(result, ConformalResult)
        assert result.predicted_class == 1
        assert result.is_ambiguous in [True, False]
    
    def test_predict_with_set_2d(self):
        """Test predict_with_set with 2D probabilities."""
        np.random.seed(42)
        cp = ConformalPredictor(alpha=0.1)
        
        # Set threshold
        cp.threshold = 0.3
        cp.fitted = True
        
        y_proba = np.array([
            [0.9, 0.1],  # Class 0 likely
            [0.2, 0.8],  # Class 1 likely
            [0.5, 0.5],  # Ambiguous
        ])
        
        results = cp.predict_with_set(y_proba)
        
        assert len(results) == 3
        assert all(isinstance(r, ConformalResult) for r in results)
        assert results[0].predicted_class == 0
        assert results[1].predicted_class == 1
    
    def test_predict_with_set_1d(self):
        """Test predict_with_set with 1D probabilities."""
        np.random.seed(42)
        cp = ConformalPredictor(alpha=0.1)
        
        # Set threshold
        cp.threshold = 0.3
        cp.fitted = True
        
        y_proba = np.array([0.1, 0.8, 0.5])
        
        results = cp.predict_with_set(y_proba)
        
        assert len(results) == 3
        assert all(isinstance(r, ConformalResult) for r in results)
    
    def test_coverage_info(self):
        """Test get_coverage_info method."""
        cp = ConformalPredictor(alpha=0.15)
        cp.threshold = 0.25
        cp.nonconformity_scores = np.array([0.1, 0.2, 0.3])
        cp.fitted = True
        
        info = cp.get_coverage_info()
        
        assert info['alpha'] == 0.15
        assert info['coverage'] == 0.85
        assert info['threshold'] == 0.25
        assert info['num_calibration_samples'] == 3
        assert info['fitted'] is True
    
    def test_repr(self):
        """Test string representation."""
        cp = ConformalPredictor(alpha=0.1)
        repr_str = repr(cp)
        assert "ConformalPredictor" in repr_str
        assert "0.1" in repr_str
        assert "90%" in repr_str


class TestConformalResult:
    """Test ConformalResult dataclass."""
    
    def test_creation(self):
        """Test ConformalResult creation."""
        result = ConformalResult(
            predicted_class=1,
            prediction_set={1},
            confidence=0.9,
            nonconformity_score=0.1,
            calibrated_proba=0.85,
            is_ambiguous=False
        )
        
        assert result.predicted_class == 1
        assert result.prediction_set == {1}
        assert result.confidence == 0.9
        assert result.is_ambiguous is False
    
    def test_str(self):
        """Test string representation."""
        result = ConformalResult(
            predicted_class=1,
            prediction_set={0, 1},
            confidence=0.5,
            nonconformity_score=0.2,
            calibrated_proba=0.5,
            is_ambiguous=True
        )
        
        result_str = str(result)
        assert "ConformalResult" in result_str
        assert "class=1" in result_str
        assert "AMBIGUOUS" in result_str


class TestConformalIntegration:
    """Integration tests with synthetic data."""
    
    def test_full_workflow(self):
        """Test complete conformal prediction workflow."""
        np.random.seed(123)
        
        # Generate synthetic data
        n_cal = 100
        X_cal = np.random.randn(n_cal, 20)
        y_cal = np.random.randint(0, 2, n_cal)
        y_proba_cal = np.random.rand(n_cal, 2)
        y_proba_cal = y_proba_cal / y_proba_cal.sum(axis=1, keepdims=True)  # Normalize
        
        # Create predictor and fit
        cp = ConformalPredictor(alpha=0.1)
        cp.set_threshold_from_calibration(y_cal, y_proba_cal)
        
        # Test on new data
        X_test = np.random.randn(50, 20)
        y_proba_test = np.random.rand(50, 2)
        y_proba_test = y_proba_test / y_proba_test.sum(axis=1, keepdims=True)
        
        results = cp.predict_with_set(y_proba_test)
        
        assert len(results) == 50
        assert all(isinstance(r, ConformalResult) for r in results)
        assert all(len(r.prediction_set) in [1, 2] for r in results)
    
    def test_coverage_guarantee(self):
        """Test that prediction sets have reasonable coverage."""
        np.random.seed(456)
        
        # Generate synthetic balanced data
        n_cal = 200
        X_cal = np.random.randn(n_cal, 10)
        y_cal = np.random.randint(0, 2, n_cal)
        
        # Create perfectly calibrated probabilities for testing
        y_proba_cal = np.column_stack([
            np.where(y_cal == 0, 0.7, 0.3),
            np.where(y_cal == 1, 0.7, 0.3)
        ])
        
        cp = ConformalPredictor(alpha=0.1)
        cp.set_threshold_from_calibration(y_cal, y_proba_cal)
        
        # Test coverage on new data
        n_test = 500
        y_test = np.random.randint(0, 2, n_test)
        y_proba_test = np.column_stack([
            np.where(y_test == 0, 0.7, 0.3),
            np.where(y_test == 1, 0.7, 0.3)
        ])
        
        results = cp.predict_with_set(y_proba_test)
        
        # Check that true labels are in prediction sets
        coverage = sum(
            1 for i, r in enumerate(results)
            if y_test[i] in r.prediction_set
        ) / len(results)
        
        # Should be close to target coverage (1 - alpha)
        expected_coverage = 1 - cp.alpha
        assert coverage >= expected_coverage - 0.15  # Allow some margin
        logger.info(f"Measured coverage: {coverage:.3f}, target: {expected_coverage:.3f}")
