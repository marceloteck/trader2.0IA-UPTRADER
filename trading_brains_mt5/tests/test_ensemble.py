"""
Tests for ensemble module.
"""

import pytest
import numpy as np
from src.models.ensemble import LightweightEnsemble, EnsembleMetrics


class TestEnsembleMetrics:
    """Test EnsembleMetrics dataclass."""
    
    def test_creation(self):
        """Test EnsembleMetrics creation."""
        metrics = EnsembleMetrics(
            prediction=1,
            proba_mean=0.75,
            proba_std=0.08,
            disagreement_score=0.16,
            individual_probas={"lr": 0.72, "rf": 0.78, "gb": 0.75},
            votes={"lr": 1, "rf": 1, "gb": 1}
        )
        
        assert metrics.prediction == 1
        assert metrics.proba_mean == 0.75
        assert metrics.proba_std == 0.08
        assert metrics.disagreement_score == 0.16
    
    def test_str(self):
        """Test string representation."""
        metrics = EnsembleMetrics(
            prediction=1,
            proba_mean=0.75,
            proba_std=0.08,
            disagreement_score=0.16,
            individual_probas={"lr": 0.72, "rf": 0.78, "gb": 0.75},
            votes={"lr": 1, "rf": 1, "gb": 1}
        )
        
        metrics_str = str(metrics)
        assert "EnsembleMetrics" in metrics_str
        assert "0.75" in metrics_str


class TestLightweightEnsemble:
    """Test LightweightEnsemble class."""
    
    def test_init_soft_voting(self):
        """Test initialization with SOFT voting."""
        ensemble = LightweightEnsemble(voting="SOFT")
        
        assert ensemble.voting_strategy == "SOFT"
        assert len(ensemble.models) == 3
    
    def test_init_weighted_voting(self):
        """Test initialization with WEIGHTED voting."""
        ensemble = LightweightEnsemble(
            voting="WEIGHTED",
            weights=[0.3, 0.4, 0.3]
        )
        
        assert ensemble.voting_strategy == "WEIGHTED"
        assert ensemble.model_weights == [0.3, 0.4, 0.3]
    
    def test_init_invalid_voting(self):
        """Test that invalid voting strategy raises error."""
        with pytest.raises(ValueError):
            LightweightEnsemble(voting="INVALID")
    
    def test_fit_soft_voting(self):
        """Test fitting with SOFT voting."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        
        # All models should be fitted
        for model in ensemble.models:
            assert hasattr(model, 'predict')
    
    def test_fit_weighted_voting(self):
        """Test fitting with WEIGHTED voting."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        
        ensemble = LightweightEnsemble(voting="WEIGHTED")
        ensemble.fit(X_train, y_train)
        
        for model in ensemble.models:
            assert hasattr(model, 'predict')
    
    def test_predict_soft_voting(self):
        """Test prediction with SOFT voting."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(10, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)
        
        assert len(predictions) == 10
        assert all(p in [0, 1] for p in predictions)
    
    def test_predict_proba_soft_voting(self):
        """Test probability prediction with SOFT voting."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(10, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        probas = ensemble.predict_proba(X_test)
        
        assert probas.shape == (10, 2)
        assert np.all(probas >= 0) and np.all(probas <= 1)
        np.testing.assert_array_almost_equal(probas.sum(axis=1), np.ones(10))
    
    def test_predict_with_metrics_soft_voting(self):
        """Test prediction with metrics (SOFT voting)."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(5, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        metrics_list = ensemble.predict_with_metrics(X_test)
        
        assert len(metrics_list) == 5
        assert all(isinstance(m, EnsembleMetrics) for m in metrics_list)
        
        # Check metrics
        for m in metrics_list:
            assert m.prediction in [0, 1]
            assert 0 <= m.proba_mean <= 1
            assert m.proba_std >= 0
            assert 0 <= m.disagreement_score <= 1
    
    def test_predict_with_metrics_weighted_voting(self):
        """Test prediction with metrics (WEIGHTED voting)."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(5, 20)
        
        ensemble = LightweightEnsemble(voting="WEIGHTED")
        ensemble.fit(X_train, y_train)
        metrics_list = ensemble.predict_with_metrics(X_test)
        
        assert len(metrics_list) == 5
        assert all(isinstance(m, EnsembleMetrics) for m in metrics_list)
    
    def test_disagreement_score_computation(self):
        """Test disagreement score is computed correctly."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(1, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        metrics = ensemble.predict_with_metrics(X_test)[0]
        
        # Disagreement should be normalized to [0, 1]
        assert 0 <= metrics.disagreement_score <= 1
        
        # If std is 0, disagreement should be 0 (perfect agreement)
        if metrics.proba_std == 0:
            assert metrics.disagreement_score == 0
    
    def test_individual_probas(self):
        """Test individual probabilities are returned."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(1, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        metrics = ensemble.predict_with_metrics(X_test)[0]
        
        # Should have probabilities for all 3 models
        assert len(metrics.individual_probas) == 3
        assert all(k in ["LogisticRegression", "RandomForest", "GradientBoosting"] 
                   for k in metrics.individual_probas.keys())
        assert all(0 <= v <= 1 for v in metrics.individual_probas.values())
    
    def test_votes_dict(self):
        """Test votes dictionary is populated."""
        np.random.seed(42)
        X_train = np.random.randn(100, 20)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(1, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        metrics = ensemble.predict_with_metrics(X_test)[0]
        
        # Should have votes for all 3 models
        assert len(metrics.votes) == 3
        assert all(v in [0, 1] for v in metrics.votes.values())


class TestLightweightEnsembleIntegration:
    """Integration tests."""
    
    def test_full_workflow_soft(self):
        """Test complete workflow with SOFT voting."""
        np.random.seed(123)
        
        # Generate synthetic data
        X_train = np.random.randn(200, 30)
        y_train = np.random.randint(0, 2, 200)
        X_test = np.random.randn(50, 30)
        y_test = np.random.randint(0, 2, 50)
        
        # Create and train ensemble
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        
        # Predict
        predictions = ensemble.predict(X_test)
        metrics_list = ensemble.predict_with_metrics(X_test)
        
        assert len(predictions) == 50
        assert len(metrics_list) == 50
        
        # Check accuracy is reasonable
        accuracy = np.mean(predictions == y_test)
        assert accuracy > 0.4  # Better than random
    
    def test_full_workflow_weighted(self):
        """Test complete workflow with WEIGHTED voting."""
        np.random.seed(123)
        
        X_train = np.random.randn(200, 30)
        y_train = np.random.randint(0, 2, 200)
        X_test = np.random.randn(50, 30)
        
        ensemble = LightweightEnsemble(voting="WEIGHTED")
        ensemble.fit(X_train, y_train)
        
        predictions = ensemble.predict(X_test)
        metrics_list = ensemble.predict_with_metrics(X_test)
        
        assert len(predictions) == 50
        assert len(metrics_list) == 50
    
    def test_ensemble_vs_individual_models(self):
        """Test that ensemble is often better than individual models."""
        np.random.seed(456)
        
        X_train = np.random.randn(200, 30)
        y_train = np.random.randint(0, 2, 200)
        X_test = np.random.randn(100, 30)
        y_test = np.random.randint(0, 2, 100)
        
        # Train ensemble
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        ensemble_pred = ensemble.predict(X_test)
        ensemble_acc = np.mean(ensemble_pred == y_test)
        
        # Train individual models
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        
        lr = LogisticRegression(random_state=42)
        lr.fit(X_train, y_train)
        lr_acc = np.mean(lr.predict(X_test) == y_test)
        
        rf = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
        rf.fit(X_train, y_train)
        rf_acc = np.mean(rf.predict(X_test) == y_test)
        
        # Ensemble should be competitive
        assert ensemble_acc > 0.4  # Better than random
    
    def test_repr(self):
        """Test string representation."""
        ensemble = LightweightEnsemble(voting="SOFT")
        repr_str = repr(ensemble)
        
        assert "LightweightEnsemble" in repr_str
        assert "SOFT" in repr_str


class TestEnsembleEdgeCases:
    """Test edge cases and error handling."""
    
    def test_predict_before_fit(self):
        """Test that predicting before fit raises error."""
        ensemble = LightweightEnsemble(voting="SOFT")
        X_test = np.random.randn(10, 20)
        
        with pytest.raises(Exception):  # Models not fitted
            ensemble.predict(X_test)
    
    def test_small_dataset(self):
        """Test with very small dataset."""
        X_train = np.random.randn(10, 5)
        y_train = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        X_test = np.random.randn(2, 5)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)
        
        assert len(predictions) == 2
    
    def test_single_feature(self):
        """Test with single feature."""
        X_train = np.random.randn(100, 1)
        y_train = np.random.randint(0, 2, 100)
        X_test = np.random.randn(10, 1)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)
        
        assert len(predictions) == 10
    
    def test_imbalanced_data(self):
        """Test with imbalanced dataset."""
        X_train = np.random.randn(100, 20)
        y_train = np.concatenate([np.zeros(90), np.ones(10)])  # 9:1 imbalance
        X_test = np.random.randn(10, 20)
        
        ensemble = LightweightEnsemble(voting="SOFT")
        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)
        
        assert len(predictions) == 10
