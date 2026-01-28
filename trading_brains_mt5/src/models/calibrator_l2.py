"""
Probability Calibration: Platt scaling and Isotonic regression.

Ensures model probabilities match actual frequencies.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve

logger = logging.getLogger("trading_brains.models.calibration")


class ProbabilityCalibrator:
    """
    Calibrate classifier probabilities using Platt or Isotonic scaling.
    
    Usage:
        calibrator = ProbabilityCalibrator(method="PLATT")
        calibrator.fit(X_cal, y_cal)
        proba_cal = calibrator.transform(proba_raw)
    """
    
    def __init__(
        self,
        method: str = "PLATT",
        n_bins: int = 10
    ):
        """
        Initialize calibrator.
        
        Args:
            method: "PLATT" or "ISOTONIC"
            n_bins: Number of bins for reliability diagram
        """
        self.method = method.upper()
        self.n_bins = n_bins
        self.calibrator = None
        self.fitted = False
        self.reliability_diagram = None
    
    def fit(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray
    ) -> None:
        """
        Fit calibrator on validation set.
        
        Args:
            y_true: True binary labels (0/1)
            y_proba: Raw probabilities from model
        """
        if self.method == "PLATT":
            # Platt scaling: fit sigmoid to probabilities
            self._fit_platt(y_true, y_proba)
        
        elif self.method == "ISOTONIC":
            # Isotonic regression: non-parametric
            self._fit_isotonic(y_true, y_proba)
        
        else:
            logger.warning(f"Unknown method {self.method}, using PLATT")
            self._fit_platt(y_true, y_proba)
        
        self.fitted = True
        self._compute_reliability_diagram(y_true, y_proba)
        logger.info(f"Calibrator fitted: method={self.method}, samples={len(y_true)}")
    
    def _fit_platt(self, y_true: np.ndarray, y_proba: np.ndarray) -> None:
        """Fit Platt scaling (sigmoid function)."""
        from scipy.optimize import minimize
        
        # Fit sigmoid: P(y=1|score) = 1 / (1 + exp(A*score + B))
        def cross_entropy(params):
            A, B = params
            epsilon = 1e-15
            predictions = 1.0 / (1.0 + np.exp(A * y_proba + B))
            predictions = np.clip(predictions, epsilon, 1 - epsilon)
            return -np.mean(
                y_true * np.log(predictions) + (1 - y_true) * np.log(1 - predictions)
            )
        
        result = minimize(cross_entropy, [0, 0], method='BFGS')
        self.calibrator = {
            'type': 'platt',
            'A': result.x[0],
            'B': result.x[1]
        }
        logger.info(f"Platt fitted: A={result.x[0]:.4f}, B={result.x[1]:.4f}")
    
    def _fit_isotonic(self, y_true: np.ndarray, y_proba: np.ndarray) -> None:
        """Fit isotonic regression."""
        from sklearn.isotonic import IsotonicRegression
        
        iso = IsotonicRegression(out_of_bounds='clip')
        iso.fit(y_proba, y_true)
        self.calibrator = {
            'type': 'isotonic',
            'model': iso
        }
        logger.info(f"Isotonic fitted with {len(y_true)} samples")
    
    def _compute_reliability_diagram(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray
    ) -> None:
        """Compute reliability diagram metrics."""
        prob_true, prob_pred = calibration_curve(
            y_true, y_proba, n_bins=self.n_bins, strategy='uniform'
        )
        
        self.reliability_diagram = {
            'prob_true': prob_true,
            'prob_pred': prob_pred,
            'ece': np.mean(np.abs(prob_true - prob_pred)),  # Expected Calibration Error
            'mce': np.max(np.abs(prob_true - prob_pred)),   # Maximum Calibration Error
        }
    
    def transform(self, y_proba: np.ndarray) -> np.ndarray:
        """
        Apply calibration to raw probabilities.
        
        Args:
            y_proba: Raw probabilities (0-1)
        
        Returns:
            Calibrated probabilities
        """
        if not self.fitted:
            logger.warning("Calibrator not fitted, returning raw probabilities")
            return y_proba
        
        if self.calibrator['type'] == 'platt':
            A = self.calibrator['A']
            B = self.calibrator['B']
            return 1.0 / (1.0 + np.exp(A * y_proba + B))
        
        elif self.calibrator['type'] == 'isotonic':
            return self.calibrator['model'].transform(y_proba)
        
        return y_proba
    
    def get_reliability_metrics(self) -> Dict:
        """Get reliability diagram metrics."""
        if self.reliability_diagram is None:
            return {}
        
        return {
            'ece': float(self.reliability_diagram['ece']),
            'mce': float(self.reliability_diagram['mce']),
            'n_bins': self.n_bins
        }
    
    def get_confidence_interval(
        self,
        proba_cal: np.ndarray,
        confidence_level: float = 0.95
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Estimate confidence intervals for calibrated probabilities.
        
        Simple approach: use standard error from binomial distribution.
        """
        n = len(proba_cal) if hasattr(proba_cal, '__len__') else 1
        se = np.sqrt(proba_cal * (1 - proba_cal) / max(n, 1))
        
        z = 1.96 if confidence_level == 0.95 else 2.576  # 99%
        
        lower = np.maximum(proba_cal - z * se, 0)
        upper = np.minimum(proba_cal + z * se, 1)
        
        return lower, upper
    
    def as_dict(self) -> Dict:
        """Export calibrator config."""
        return {
            'method': self.method,
            'fitted': self.fitted,
            'n_bins': self.n_bins,
            'metrics': self.get_reliability_metrics()
        }
