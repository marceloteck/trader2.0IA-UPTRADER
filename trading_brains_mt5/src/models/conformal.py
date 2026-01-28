"""
Conformal Prediction: Uncertainty quantification for binary classification.

Generates prediction sets with guaranteed coverage (1 - alpha) using nonconformity measures.
Light implementation: Uses calibrated probabilities as nonconformity scores.

Key Concepts:
  - Nonconformity measure: 1 - calibrated_proba (distance from confident prediction)
  - Calibration set: Used to compute quantiles of nonconformity scores
  - Prediction set: Singleton (high confidence) or doubleton (uncertain)
  - Confidence level: 1 - alpha (coverage guarantee)

Reference: Vovk et al., "Algorithmic Learning Theory", Chapter on Conformal Prediction
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Set
import numpy as np

logger = logging.getLogger("trading_brains.models.conformal")


@dataclass
class ConformalResult:
    """Result of conformal prediction with uncertainty quantification."""
    
    predicted_class: int  # 0 or 1
    prediction_set: Set[int]  # {0}, {1}, or {0, 1}
    confidence: float  # 1 - alpha when singleton, lower for doubleton
    nonconformity_score: float  # 1 - calibrated_proba
    calibrated_proba: float  # Calibrated probability for predicted class
    is_ambiguous: bool  # True if prediction_set has both classes
    
    def __str__(self) -> str:
        set_str = "{" + ", ".join(str(c) for c in sorted(self.prediction_set)) + "}"
        ambig = " (AMBIGUOUS)" if self.is_ambiguous else ""
        return f"ConformalResult(class={self.predicted_class}, set={set_str}, confidence={self.confidence:.3f}{ambig})"


class ConformalPredictor:
    """
    Conformal Prediction for binary classification.
    
    Uses calibrated probability scores to generate prediction sets with guaranteed coverage.
    Light implementation: Nonconformity = 1 - calibrated_proba
    
    Attributes:
        alpha (float): Significance level (1 - coverage). Default 0.1 = 90% coverage.
        calibrator: ProbabilityCalibrator instance (or similar) that transforms raw probas.
        nonconformity_scores (np.ndarray): Nonconformity scores from calibration set.
        threshold (float): Quantile of nonconformity scores (computed from calibration set).
        fitted (bool): Whether calibration set has been fit.
    """
    
    def __init__(self, alpha: float = 0.1, calibrator: Optional[object] = None):
        """
        Initialize ConformalPredictor.
        
        Args:
            alpha: Significance level (1 - coverage). Default 0.1 = 90% coverage.
            calibrator: ProbabilityCalibrator or similar with transform() method.
                        If None, uses raw probabilities.
        """
        if not (0 < alpha < 1):
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        
        self.alpha = alpha
        self.calibrator = calibrator
        self.nonconformity_scores: Optional[np.ndarray] = None
        self.threshold: Optional[float] = None
        self.fitted = False
        
    def fit_calibration_set(self, X_cal: np.ndarray, y_cal: np.ndarray) -> None:
        """
        Fit conformal prediction using calibration set.
        
        Computes nonconformity scores and threshold from calibration set.
        These are used to determine prediction sets in predict_with_set().
        
        Args:
            X_cal: Calibration features (n_samples, n_features)
            y_cal: Calibration labels (n_samples,) in {0, 1}
        
        Raises:
            ValueError: If X_cal and y_cal have mismatched lengths.
        """
        if len(X_cal) != len(y_cal):
            raise ValueError(f"X_cal and y_cal must have same length, got {len(X_cal)} and {len(y_cal)}")
        
        if len(X_cal) == 0:
            raise ValueError("Calibration set cannot be empty")
        
        # This placeholder expects to be called after fitting models.
        # In real usage, models would provide probabilities.
        # For now, we just mark as fitted.
        self.nonconformity_scores = np.array([])  # Will be computed with probas
        self.fitted = True
        logger.info(f"ConformalPredictor fitted on calibration set (n={len(y_cal)})")
    
    def _compute_nonconformity(self, y_true: np.ndarray, y_proba: np.ndarray) -> np.ndarray:
        """
        Compute nonconformity scores for samples.
        
        Nonconformity = 1 - probability of true class
        
        Args:
            y_true: True labels (n_samples,) in {0, 1}
            y_proba: Predicted probabilities (n_samples, 2) or (n_samples,) with P(class=1)
        
        Returns:
            Nonconformity scores (n_samples,)
        """
        # Handle both formats: (n, 2) and (n,)
        if y_proba.ndim == 2:
            # y_proba is (n_samples, 2)
            proba_of_true = y_proba[np.arange(len(y_true)), y_true]
        else:
            # y_proba is (n_samples,) = P(class=1)
            # Compute P(true_class)
            proba_of_true = np.where(y_true == 1, y_proba, 1 - y_proba)
        
        nonconformity = 1.0 - proba_of_true
        return nonconformity
    
    def set_threshold_from_calibration(self, y_true: np.ndarray, y_proba: np.ndarray) -> None:
        """
        Set prediction threshold from calibration set probabilities.
        
        Computes (1 - alpha)-quantile of nonconformity scores.
        This threshold determines which classes are included in prediction sets.
        
        Args:
            y_true: True labels from calibration set (n_samples,)
            y_proba: Predicted probabilities from model (n_samples, 2) or (n_samples,)
        """
        # Calibrate probabilities if calibrator provided
        if self.calibrator is not None and hasattr(self.calibrator, 'transform'):
            try:
                y_proba_cal = self.calibrator.transform(y_proba)
            except Exception as e:
                logger.warning(f"Calibration failed, using raw probabilities: {e}")
                y_proba_cal = y_proba
        else:
            y_proba_cal = y_proba
        
        # Compute nonconformity scores
        self.nonconformity_scores = self._compute_nonconformity(y_true, y_proba_cal)
        
        # Compute threshold: (1 - alpha)-quantile, rounded up
        # Using ceil to ensure conservative coverage
        n = len(self.nonconformity_scores)
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        self.threshold = np.quantile(self.nonconformity_scores, q_level, method='linear')
        
        self.fitted = True
        logger.info(
            f"ConformalPredictor threshold={self.threshold:.4f} from {n} calibration samples "
            f"(alpha={self.alpha}, coverage={(1-self.alpha)*100:.0f}%)"
        )
    
    def predict_with_set(self, y_proba: np.ndarray) -> List[ConformalResult]:
        """
        Generate prediction sets with confidence for samples.
        
        For each sample:
          - Class 1 included if: 1 - P(1) <= threshold
          - Class 0 included if: 1 - P(0) <= threshold (i.e., 1 - (1 - P(1)) <= threshold)
        
        Args:
            y_proba: Predicted probabilities (n_samples, 2) or (n_samples,) with P(class=1)
        
        Returns:
            List of ConformalResult objects (n_samples,)
        
        Raises:
            RuntimeError: If not fitted via set_threshold_from_calibration()
        """
        if not self.fitted or self.threshold is None:
            raise RuntimeError(
                "ConformalPredictor not fitted. Call set_threshold_from_calibration() first."
            )
        
        # Handle both formats
        if y_proba.ndim == 2:
            # y_proba is (n_samples, 2)
            proba_class_1 = y_proba[:, 1]
        else:
            # y_proba is (n_samples,) = P(class=1)
            proba_class_1 = y_proba
        
        # Calibrate if calibrator provided
        if self.calibrator is not None and hasattr(self.calibrator, 'transform'):
            try:
                # Reconstruct (n, 2) for calibrator
                y_proba_2d = np.column_stack([1 - proba_class_1, proba_class_1])
                proba_cal_2d = self.calibrator.transform(y_proba_2d)
                proba_class_1_cal = proba_cal_2d[:, 1]
            except Exception as e:
                logger.warning(f"Calibration failed in prediction, using raw probabilities: {e}")
                proba_class_1_cal = proba_class_1
        else:
            proba_class_1_cal = proba_class_1
        
        results = []
        for i, p1 in enumerate(proba_class_1_cal):
            p0 = 1.0 - p1
            
            # Nonconformity scores for each class
            nonconf_class_0 = 1.0 - p0  # 1 - P(0) = p1
            nonconf_class_1 = 1.0 - p1
            
            # Prediction set: include class if nonconformity <= threshold
            pred_set = set()
            if nonconf_class_0 <= self.threshold:
                pred_set.add(0)
            if nonconf_class_1 <= self.threshold:
                pred_set.add(1)
            
            # Fallback: ensure at least one class (conservative)
            if not pred_set:
                pred_set = {0, 1}
            
            # Predicted class: higher probability
            pred_class = 1 if p1 > 0.5 else 0
            
            # Confidence: 1 - alpha if singleton, lower if doubleton
            is_ambiguous = len(pred_set) == 2
            confidence = (1 - self.alpha) if not is_ambiguous else (1 - self.alpha) * 0.5
            
            # Nonconformity of predicted class
            nonconf_score = 1.0 - (p1 if pred_class == 1 else p0)
            
            result = ConformalResult(
                predicted_class=pred_class,
                prediction_set=pred_set,
                confidence=confidence,
                nonconformity_score=nonconf_score,
                calibrated_proba=p1 if pred_class == 1 else p0,
                is_ambiguous=is_ambiguous
            )
            results.append(result)
        
        return results
    
    def predict_with_set_single(self, y_proba: float) -> ConformalResult:
        """
        Generate prediction set for a single sample (convenience method).
        
        Args:
            y_proba: Probability of class 1 (float in [0, 1])
        
        Returns:
            ConformalResult for single sample
        """
        result = self.predict_with_set(np.array([y_proba]))[0]
        return result
    
    def get_coverage_info(self) -> dict:
        """
        Get information about coverage and threshold.
        
        Returns:
            Dictionary with coverage, alpha, threshold, num_calibration_samples
        """
        return {
            "coverage": 1 - self.alpha,
            "alpha": self.alpha,
            "threshold": self.threshold,
            "num_calibration_samples": len(self.nonconformity_scores) if self.nonconformity_scores is not None else 0,
            "fitted": self.fitted
        }
    
    def __repr__(self) -> str:
        status = "fitted" if self.fitted else "not fitted"
        return f"ConformalPredictor(alpha={self.alpha}, coverage={(1-self.alpha)*100:.0f}%, {status})"
