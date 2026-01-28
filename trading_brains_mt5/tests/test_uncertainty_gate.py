"""
Tests for uncertainty gate module.
"""

import pytest
from src.brains.uncertainty_gate import UncertaintyGate, GateDecision, GateReason


class TestGateReason:
    """Test GateReason enum."""
    
    def test_gate_reason_values(self):
        """Test that all GateReason enum values are valid."""
        assert GateReason.ALLOW.value == "allow"
        assert GateReason.DISAGREEMENT_HIGH.value == "disagreement_high"
        assert GateReason.CONFORMAL_AMBIGUOUS.value == "conformal_ambiguous"
        assert GateReason.PROBA_STD_HIGH.value == "proba_std_high"
        assert GateReason.CONFIDENCE_LOW.value == "confidence_low"
        assert GateReason.DISABLED.value == "gate_disabled"


class TestGateDecision:
    """Test GateDecision dataclass."""
    
    def test_creation(self):
        """Test GateDecision creation."""
        decision = GateDecision(
            decision="ALLOW",
            reason="allow",
            details={"disagreement": 0.1}
        )
        
        assert decision.decision == "ALLOW"
        assert decision.reason == "allow"
        assert decision.details["disagreement"] == 0.1
    
    def test_str(self):
        """Test string representation."""
        decision = GateDecision(
            decision="HOLD",
            reason="disagreement_high",
            details={}
        )
        
        decision_str = str(decision)
        assert "GateDecision" in decision_str
        assert "HOLD" in decision_str
        assert "disagreement_high" in decision_str


class TestUncertaintyGate:
    """Test UncertaintyGate class."""
    
    def test_init_default(self):
        """Test initialization with default parameters."""
        gate = UncertaintyGate()
        
        assert gate.enabled is True
        assert gate.thresholds["max_model_disagreement"] == 0.25
        assert gate.thresholds["max_proba_std"] == 0.15
        assert gate.thresholds["min_global_confidence"] == 0.55
    
    def test_init_custom(self):
        """Test initialization with custom parameters."""
        gate = UncertaintyGate(
            enabled=False,
            max_model_disagreement=0.3,
            max_proba_std=0.2,
            min_global_confidence=0.6
        )
        
        assert gate.enabled is False
        assert gate.thresholds["max_model_disagreement"] == 0.3
        assert gate.thresholds["max_proba_std"] == 0.2
        assert gate.thresholds["min_global_confidence"] == 0.6
    
    def test_disabled_gate_always_allows(self):
        """Test that disabled gate always allows."""
        gate = UncertaintyGate(enabled=False)
        
        decision = gate.check()
        
        assert decision.decision == "ALLOW"
        assert decision.reason == GateReason.DISABLED.value
    
    def test_check_disagreement_high(self):
        """Test that high disagreement blocks trade."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.2
        )
        
        decision = gate.check(
            disagreement_score=0.3,  # Above threshold
            proba_mean=0.7,
            proba_std=0.1
        )
        
        assert decision.decision == "HOLD"
        assert decision.reason == GateReason.DISAGREEMENT_HIGH.value
        assert decision.details["disagreement_score"] == 0.3
        assert decision.details["threshold"] == 0.2
    
    def test_check_disagreement_ok(self):
        """Test that low disagreement passes."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.2
        )
        
        decision = gate.check(
            disagreement_score=0.1,  # Below threshold
            proba_mean=0.7,
            proba_std=0.08,
            min_global_confidence=0.55
        )
        
        # Should not be blocked by disagreement
        if decision.decision != "ALLOW":
            assert decision.reason != GateReason.DISAGREEMENT_HIGH.value
    
    def test_check_conformal_ambiguous(self):
        """Test that ambiguous conformal prediction blocks trade."""
        gate = UncertaintyGate(enabled=True)
        
        # Create mock conformal result
        class MockConformal:
            is_ambiguous = True
            prediction_set = {0, 1}
        
        decision = gate.check(
            conformal_result=MockConformal(),
            disagreement_score=0.1,
            proba_mean=0.5,
            proba_std=0.1
        )
        
        assert decision.decision == "HOLD"
        assert decision.reason == GateReason.CONFORMAL_AMBIGUOUS.value
    
    def test_check_conformal_unambiguous(self):
        """Test that unambiguous conformal prediction passes."""
        gate = UncertaintyGate(enabled=True)
        
        class MockConformal:
            is_ambiguous = False
            prediction_set = {1}
        
        decision = gate.check(
            conformal_result=MockConformal(),
            disagreement_score=0.1,
            proba_mean=0.7,
            proba_std=0.08
        )
        
        # Should not be blocked by conformal
        if decision.decision != "ALLOW":
            assert decision.reason != GateReason.CONFORMAL_AMBIGUOUS.value
    
    def test_check_proba_std_high(self):
        """Test that high proba_std blocks trade."""
        gate = UncertaintyGate(
            enabled=True,
            max_proba_std=0.1
        )
        
        decision = gate.check(
            disagreement_score=0.15,
            proba_mean=0.7,
            proba_std=0.2  # Above threshold
        )
        
        assert decision.decision == "HOLD"
        assert decision.reason == GateReason.PROBA_STD_HIGH.value
    
    def test_check_confidence_low(self):
        """Test that low confidence blocks trade."""
        gate = UncertaintyGate(
            enabled=True,
            min_global_confidence=0.6
        )
        
        decision = gate.check(
            disagreement_score=0.15,
            proba_mean=0.52,  # max(0.52, 0.48) = 0.52 < 0.6
            proba_std=0.1
        )
        
        assert decision.decision == "HOLD"
        assert decision.reason == GateReason.CONFIDENCE_LOW.value
    
    def test_check_confidence_ok(self):
        """Test that good confidence passes."""
        gate = UncertaintyGate(
            enabled=True,
            min_global_confidence=0.6
        )
        
        decision = gate.check(
            disagreement_score=0.15,
            proba_mean=0.7,  # max(0.7, 0.3) = 0.7 > 0.6
            proba_std=0.1
        )
        
        # Should not be blocked by confidence
        if decision.decision != "ALLOW":
            assert decision.reason != GateReason.CONFIDENCE_LOW.value
    
    def test_check_all_pass(self):
        """Test that all good metrics allow."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.25,
            max_proba_std=0.15,
            min_global_confidence=0.55
        )
        
        decision = gate.check(
            disagreement_score=0.2,
            proba_mean=0.7,
            proba_std=0.1
        )
        
        assert decision.decision == "ALLOW"
        assert decision.reason == GateReason.ALLOW.value
    
    def test_check_multiple_failures(self):
        """Test that first failure is reported."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.15,
            max_proba_std=0.1,
            min_global_confidence=0.6
        )
        
        # All metrics bad
        decision = gate.check(
            disagreement_score=0.3,
            proba_mean=0.51,
            proba_std=0.2
        )
        
        # Should block on first check (disagreement)
        assert decision.decision == "HOLD"
        assert decision.reason == GateReason.DISAGREEMENT_HIGH.value
    
    def test_update_thresholds(self):
        """Test dynamic threshold updates."""
        gate = UncertaintyGate()
        
        initial_disagreement = gate.thresholds["max_model_disagreement"]
        gate.update_thresholds(max_model_disagreement=0.5)
        
        assert gate.thresholds["max_model_disagreement"] == 0.5
        assert gate.thresholds["max_model_disagreement"] != initial_disagreement
    
    def test_update_unknown_threshold(self):
        """Test that unknown threshold update is logged but ignored."""
        gate = UncertaintyGate()
        
        gate.update_thresholds(unknown_param=0.5)
        
        # Should not add unknown parameter
        assert "unknown_param" not in gate.thresholds
    
    def test_get_config(self):
        """Test get_config method."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.3
        )
        
        config = gate.get_config()
        
        assert config["enabled"] is True
        assert config["thresholds"]["max_model_disagreement"] == 0.3
        assert isinstance(config["thresholds"], dict)
    
    def test_repr(self):
        """Test string representation."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.25,
            max_proba_std=0.15,
            min_global_confidence=0.55
        )
        
        repr_str = repr(gate)
        
        assert "UncertaintyGate" in repr_str
        assert "enabled" in repr_str
        assert "0.25" in repr_str


class TestUncertaintyGateIntegration:
    """Integration tests with ensemble and conformal objects."""
    
    def test_with_ensemble_metrics(self):
        """Test gate with EnsembleMetrics object."""
        gate = UncertaintyGate()
        
        class MockEnsemble:
            disagreement_score = 0.2
            proba_std = 0.1
            proba_mean = 0.7
        
        decision = gate.check(ensemble_metrics=MockEnsemble())
        
        assert decision.decision == "ALLOW"
    
    def test_with_conformal_result(self):
        """Test gate with ConformalResult object."""
        gate = UncertaintyGate()
        
        class MockConformal:
            is_ambiguous = False
            prediction_set = {1}
        
        decision = gate.check(conformal_result=MockConformal())
        
        # Should allow when conformal unambiguous
        if decision.decision != "ALLOW":
            assert decision.reason != GateReason.CONFORMAL_AMBIGUOUS.value
    
    def test_full_workflow(self):
        """Test complete gate workflow with all inputs."""
        gate = UncertaintyGate(
            enabled=True,
            max_model_disagreement=0.25,
            max_proba_std=0.15,
            min_global_confidence=0.55
        )
        
        class MockEnsemble:
            disagreement_score = 0.2
            proba_std = 0.1
            proba_mean = 0.75
        
        class MockConformal:
            is_ambiguous = False
            prediction_set = {1}
        
        decision = gate.check(
            ensemble_metrics=MockEnsemble(),
            conformal_result=MockConformal()
        )
        
        assert decision.decision == "ALLOW"
        assert decision.reason == GateReason.ALLOW.value
        assert decision.details["disagreement_score"] == 0.2
        assert decision.details["proba_std"] == 0.1
