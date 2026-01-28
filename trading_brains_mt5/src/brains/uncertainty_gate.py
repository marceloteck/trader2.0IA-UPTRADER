"""
Uncertainty Gate: Risk management layer to block low-confidence trades.

Prevents trading when:
  1. Ensemble model disagreement > MAX_MODEL_DISAGREEMENT
  2. Conformal prediction set is ambiguous (contains both classes)
  3. Ensemble proba_std > MAX_PROBA_STD
  4. Global confidence (max prob) < MIN_GLOBAL_CONFIDENCE

Returns HOLD signal with reason code when gate blocks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("trading_brains.brains.uncertainty_gate")


class GateReason(str, Enum):
    """Enumeration of reasons gate may block a trade."""
    
    ALLOW = "allow"
    DISAGREEMENT_HIGH = "disagreement_high"
    CONFORMAL_AMBIGUOUS = "conformal_ambiguous"
    PROBA_STD_HIGH = "proba_std_high"
    CONFIDENCE_LOW = "confidence_low"
    DISABLED = "gate_disabled"


@dataclass
class GateDecision:
    """Gate decision and diagnostics."""
    
    decision: str  # "ALLOW" or "HOLD"
    reason: str  # GateReason enum value
    details: Dict[str, Any]  # Diagnostics: disagreement, proba_std, confidence, etc.
    
    def __str__(self) -> str:
        return f"GateDecision({self.decision}, {self.reason})"


class UncertaintyGate:
    """
    Risk management gate to block trades when uncertainty is high.
    
    Configuration:
        enabled (bool): Whether to apply gating. If False, always allows.
        max_model_disagreement (float): Max ensemble disagreement_score (0-1).
        max_proba_std (float): Max ensemble proba_std.
        min_global_confidence (float): Min of max(prob_0, prob_1).
    
    Attributes:
        enabled: Whether gating is active.
        thresholds: Dictionary of threshold values.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        max_model_disagreement: float = 0.25,
        max_proba_std: float = 0.15,
        min_global_confidence: float = 0.55,
    ):
        """
        Initialize UncertaintyGate.
        
        Args:
            enabled: Whether to apply gating logic.
            max_model_disagreement: Max disagreement_score from ensemble (0-1).
            max_proba_std: Max proba_std from ensemble.
            min_global_confidence: Min max(prob_0, prob_1).
        """
        self.enabled = enabled
        self.thresholds = {
            "max_model_disagreement": max_model_disagreement,
            "max_proba_std": max_proba_std,
            "min_global_confidence": min_global_confidence,
        }
        
        logger.info(
            f"UncertaintyGate initialized (enabled={enabled}, "
            f"disagreement<{max_model_disagreement:.3f}, "
            f"proba_std<{max_proba_std:.3f}, "
            f"confidence>{min_global_confidence:.3f})"
        )
    
    def check(
        self,
        signal_strength: float = None,
        ensemble_disagreement: float = None,
        conformal_ambiguous: bool = None,
        ensemble_metrics: Optional[object] = None,
        conformal_result: Optional[object] = None,
        **kwargs
    ) -> GateDecision:
        """
        Check if trade should be allowed based on ensemble and conformal metrics.
        
        Args:
            signal_strength: Model confidence level (0-1) - simplified mode
            ensemble_disagreement: Disagreement score (0-1) - simplified mode
            conformal_ambiguous: Whether conformal prediction is ambiguous - simplified mode
            ensemble_metrics: EnsembleMetrics object with:
                - prediction (0 or 1)
                - proba_mean (float)
                - proba_std (float)
                - disagreement_score (float)
                - individual_probas (dict of model -> proba)
            
            conformal_result: ConformalResult object with:
                - predicted_class (0 or 1)
                - prediction_set (set of classes)
                - confidence (float)
                - is_ambiguous (bool)
            
            **kwargs: Alternative way to pass metrics (e.g., for testing):
                - disagreement_score
                - proba_std
                - proba_mean
                - is_conformal_ambiguous
        
        Returns:
            GateDecision with decision (ALLOW/HOLD), reason, and details
        """
        details = {}
        
        # If gate is disabled, always allow
        if not self.enabled:
            return GateDecision(
                decision="ALLOW",
                reason=GateReason.DISABLED.value,
                details={"reason": "gate_disabled"}
            )
        
        # Extract ensemble metrics - support both object and simplified parameters
        disagreement_score = ensemble_disagreement  # Simplified parameter
        proba_std = None
        proba_mean = None
        
        if ensemble_metrics is not None:
            disagreement_score = getattr(ensemble_metrics, 'disagreement_score', disagreement_score)
            proba_std = getattr(ensemble_metrics, 'proba_std', None)
            proba_mean = getattr(ensemble_metrics, 'proba_mean', None)
        
        # Override with kwargs if provided
        disagreement_score = kwargs.get('disagreement_score', disagreement_score)
        proba_std = kwargs.get('proba_std', proba_std)
        proba_mean = kwargs.get('proba_mean', proba_mean)
        
        details['disagreement_score'] = disagreement_score
        details['proba_std'] = proba_std
        details['proba_mean'] = proba_mean
        
        # Check 1: Model disagreement
        if disagreement_score is not None:
            if disagreement_score > self.thresholds['max_model_disagreement']:
                details['reason'] = "ensemble_disagreement_high"
                details['threshold'] = self.thresholds['max_model_disagreement']
                logger.warning(
                    f"Gate BLOCKED: ensemble disagreement {disagreement_score:.3f} "
                    f"> {self.thresholds['max_model_disagreement']:.3f}"
                )
                return GateDecision(
                    decision="HOLD",
                    reason=GateReason.DISAGREEMENT_HIGH.value,
                    details=details
                )
        
        # Check 2: Conformal ambiguity - support both object and simplified parameter
        is_ambiguous = conformal_ambiguous  # Simplified parameter
        if conformal_result is not None:
            is_ambiguous = getattr(conformal_result, 'is_ambiguous', is_ambiguous)
            pred_set = getattr(conformal_result, 'prediction_set', None)
            
            details['conformal_ambiguous'] = is_ambiguous
            details['prediction_set'] = list(pred_set) if pred_set else None
            
            if is_ambiguous:
                logger.warning(
                    f"Gate BLOCKED: conformal prediction ambiguous "
                    f"(prediction_set={pred_set})"
                )
                return GateDecision(
                    decision="HOLD",
                    reason=GateReason.CONFORMAL_AMBIGUOUS.value,
                    details=details
                )
        
        # Check 3: Probability std dev
        if proba_std is not None:
            if proba_std > self.thresholds['max_proba_std']:
                details['reason'] = "proba_std_high"
                details['threshold'] = self.thresholds['max_proba_std']
                logger.warning(
                    f"Gate BLOCKED: proba_std {proba_std:.3f} "
                    f"> {self.thresholds['max_proba_std']:.3f}"
                )
                return GateDecision(
                    decision="HOLD",
                    reason=GateReason.PROBA_STD_HIGH.value,
                    details=details
                )
        
        # Check 4: Global confidence
        if proba_mean is not None:
            global_confidence = max(proba_mean, 1 - proba_mean)
            details['global_confidence'] = global_confidence
            
            if global_confidence < self.thresholds['min_global_confidence']:
                details['reason'] = "confidence_low"
                details['threshold'] = self.thresholds['min_global_confidence']
                logger.warning(
                    f"Gate BLOCKED: global confidence {global_confidence:.3f} "
                    f"< {self.thresholds['min_global_confidence']:.3f}"
                )
                return GateDecision(
                    decision="HOLD",
                    reason=GateReason.CONFIDENCE_LOW.value,
                    details=details
                )
        
        # All checks passed
        logger.debug(f"Gate ALLOWED (disagreement={disagreement_score}, "
                    f"proba_std={proba_std}, confidence={proba_mean})")
        return GateDecision(
            decision="ALLOW",
            reason=GateReason.ALLOW.value,
            details=details
        )
    
    def update_thresholds(self, **kwargs) -> None:
        """
        Update gate thresholds dynamically.
        
        Args:
            max_model_disagreement: New disagreement threshold
            max_proba_std: New std dev threshold
            min_global_confidence: New confidence threshold
        """
        for key, value in kwargs.items():
            if key in self.thresholds:
                self.thresholds[key] = value
                logger.info(f"Updated gate threshold: {key} = {value}")
            else:
                logger.warning(f"Unknown threshold: {key}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current gate configuration."""
        return {
            "enabled": self.enabled,
            "thresholds": self.thresholds.copy(),
        }
    
    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return (
            f"UncertaintyGate({status}, "
            f"disagreement<{self.thresholds['max_model_disagreement']:.3f}, "
            f"proba_std<{self.thresholds['max_proba_std']:.3f}, "
            f"confidence>{self.thresholds['min_global_confidence']:.3f})"
        )
