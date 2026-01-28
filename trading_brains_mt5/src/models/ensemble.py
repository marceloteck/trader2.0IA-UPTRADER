"""
Lightweight Ensemble: Combine multiple models with voting strategies.

Models: LogisticRegression, RandomForest, GradientBoosting
Voting: SOFT (average probabilities) or WEIGHTED (weighted by performance)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

logger = logging.getLogger("trading_brains.models.ensemble")


@dataclass
class EnsembleMetrics:
    """Metrics for ensemble decision."""
    prediction: int  # 0 or 1
    proba_mean: float  # Average probability
    proba_std: float  # Disagreement between models
    disagreement_score: float  # 0-1, 1 = max disagreement
    individual_probas: Dict[str, float]  # Per-model probabilities
    votes: Dict[str, int]  # Per-model binary predictions


class LightweightEnsemble:
    """
    Ensemble of 2-3 models with soft or weighted voting.
    
    Usage:
        ensemble = LightweightEnsemble(
            models=["LogisticRegression", "RandomForest"],
            voting="SOFT",
            weights=None  # Auto-calibrate
        )
        ensemble.fit(X_train, y_train)
        metrics = ensemble.predict_with_metrics(X_test)
    """
    
    def __init__(
        self,
        models: List[str] = None,
        voting: str = "SOFT",
        ensemble_mode: str = None,
        weights: Optional[List[float]] = None
    ):
        """
        Initialize ensemble.
        
        Args:
            models: List of model types (LogisticRegression, RandomForest, GradientBoosting)
            voting: "SOFT" (average proba) or "WEIGHTED" (by performance)
            ensemble_mode: Alias for voting parameter (for compatibility)
            weights: Custom weights, or None for auto
        """
        self.models_config = models or [
            "LogisticRegression",
            "RandomForest",
            "GradientBoosting"
        ]
        # Support both voting and ensemble_mode parameters
        voting = ensemble_mode or voting
        self.voting = str(voting).upper()
        self.custom_weights = weights
        self.weights = None
        
        self.models = {}
        self._initialize_models()
    
    def _initialize_models(self) -> None:
        """Create model instances."""
        for model_name in self.models_config:
            if model_name == "LogisticRegression":
                self.models[model_name] = LogisticRegression(
                    max_iter=1000, random_state=42
                )
            elif model_name == "RandomForest":
                self.models[model_name] = RandomForestClassifier(
                    n_estimators=50, max_depth=10, random_state=42
                )
            elif model_name == "GradientBoosting":
                self.models[model_name] = GradientBoostingClassifier(
                    n_estimators=50, max_depth=5, random_state=42
                )
        
        logger.info(f"Initialized models: {list(self.models.keys())}")
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit all models.
        
        Args:
            X: Training features (n_samples, n_features)
            y: Training labels (0/1)
        """
        for name, model in self.models.items():
            model.fit(X, y)
            logger.info(f"Fitted {name} on {len(X)} samples")
        
        # Auto-calibrate weights if WEIGHTED voting
        if self.voting == "WEIGHTED" and self.custom_weights is None:
            self._calibrate_weights(X, y)
    
    def _calibrate_weights(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Calibrate weights based on individual model accuracies.
        
        Args:
            X: Validation features
            y: Validation labels
        """
        accuracies = []
        for name, model in self.models.items():
            acc = model.score(X, y)
            accuracies.append(acc)
            logger.info(f"{name} accuracy: {acc:.3f}")
        
        # Normalize as weights
        total = sum(accuracies)
        self.weights = [acc / total for acc in accuracies]
        logger.info(f"Calibrated weights: {dict(zip(self.models.keys(), self.weights))}")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict binary labels via ensemble.
        
        Returns:
            Binary predictions (0/1)
        """
        metrics_list = [self.predict_with_metrics(x.reshape(1, -1)) for x in X]
        return np.array([m.prediction for m in metrics_list])
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probabilities via ensemble.
        
        Returns:
            Probabilities for class 1 (0-1)
        """
        metrics_list = [self.predict_with_metrics(x.reshape(1, -1)) for x in X]
        return np.array([m.proba_mean for m in metrics_list])
    
    def predict_with_metrics(self, X: np.ndarray) -> EnsembleMetrics:
        """
        Predict with detailed metrics (disagreement, etc).
        
        Args:
            X: Single sample (1, n_features)
        
        Returns:
            EnsembleMetrics with all details
        """
        individual_probas = {}
        votes = {}
        probas = []
        
        for name, model in self.models.items():
            proba = model.predict_proba(X)[0, 1]  # Probability of class 1
            individual_probas[name] = float(proba)
            votes[name] = int(proba >= 0.5)
            probas.append(proba)
        
        probas = np.array(probas)
        
        # SOFT voting: average probabilities
        if self.voting == "SOFT":
            proba_mean = np.mean(probas)
            weights = [1.0 / len(probas)] * len(probas)
        
        # WEIGHTED voting: use calibrated weights
        else:
            if self.weights is None:
                self.weights = [1.0 / len(probas)] * len(probas)
            proba_mean = np.dot(probas, self.weights)
            weights = self.weights
        
        # Disagreement: how much probas vary
        proba_std = float(np.std(probas))
        
        # Disagreement score: 0 = unanimous, 1 = max disagreement
        # Simple proxy: range / max
        proba_range = float(np.max(probas) - np.min(probas))
        disagreement_score = proba_range / max(proba_range, 0.1) if proba_range > 0.1 else 0.0
        
        prediction = 1 if proba_mean >= 0.5 else 0
        
        return EnsembleMetrics(
            prediction=prediction,
            proba_mean=float(proba_mean),
            proba_std=proba_std,
            disagreement_score=disagreement_score,
            individual_probas=individual_probas,
            votes=votes
        )
    
    def get_model_importances(self, feature_names: Optional[List[str]] = None) -> Dict:
        """
        Get feature importances from ensemble models.
        
        Returns:
            Dict with importance per model/feature
        """
        importances = {}
        
        for name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                importances[name] = model.feature_importances_.tolist()
            elif hasattr(model, 'coef_'):
                importances[name] = np.abs(model.coef_[0]).tolist()
        
        return importances
    
    def as_dict(self) -> Dict:
        """Export ensemble config."""
        return {
            'models': self.models_config,
            'voting': self.voting,
            'weights': self.weights,
            'model_types': list(self.models.keys())
        }
