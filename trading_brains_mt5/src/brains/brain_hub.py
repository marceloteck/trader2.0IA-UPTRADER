from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

from ..config.constants import DEFAULT_WEIGHTS
from .brain_interface import Brain, BrainSignal, Context, Decision
from .cluster_proxy import ClusterProxyBrain
from .elliott_prob import ElliottProbBrain
from .gann_macro import GannMacroBrain
from .liquidity_levels import LiquidityBrain
from .wyckoff_range import WyckoffRangeBrain
from .wyckoff_adv import WyckoffAdvancedBrain
from .trend_pullback import TrendPullbackBrain
from .gift import GiftBrain
from .momentum import MomentumBrain
from .consolidation_90pts import Consolidation90ptsBrain


class BossBrain:
    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.brains: List[Brain] = [
            WyckoffRangeBrain(),
            WyckoffAdvancedBrain(),
            TrendPullbackBrain(),
            GiftBrain(),
            MomentumBrain(),
            Consolidation90ptsBrain(),
            ElliottProbBrain(),
            ClusterProxyBrain(),
            LiquidityBrain(),
        ]
        self.weights = weights or DEFAULT_WEIGHTS

    def run(self, candles: Union[pd.DataFrame, Dict[str, pd.DataFrame]], context: Context) -> Decision:
        primary = candles if isinstance(candles, pd.DataFrame) else candles.get(context.timeframe)
        if primary is None or primary.empty:
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "No candles", [], {})
        macro_signal = None
        if isinstance(candles, dict):
            h1 = candles.get("H1")
            if h1 is not None and not h1.empty:
                macro_signal = GannMacroBrain().detect(h1)
        regime = context.features.get("regime", "unknown")
        scored: List[tuple[BrainSignal, float]] = []
        contributors: List[str] = []
        for brain in self.brains:
            signal = brain.detect(primary)
            if signal is None:
                continue
            base = brain.score(signal, context)
            weight = self._weight_for_regime(brain.__class__.__name__, regime)
            score = base * weight
            scored.append((signal, score))
            contributors.append(brain.name)

        if not scored:
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "No signals", [], {})

        scored.sort(key=lambda item: item[1], reverse=True)
        signal, score = scored[0]
        if not self._confluence_gate(scored):
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "No confluence", [], {})
        if macro_signal and not self._macro_filter(signal, macro_signal):
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "Macro filter blocked", [], {})
        rr = self._risk_reward(signal)
        if rr < 1.2:
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "Risk reward below minimum", [], {})
        if context.spread > 0 and context.spread >  context.features.get("spread_max", context.spread):
            return Decision("HOLD", 0.0, 0.0, 0.0, 0.0, 0.0, "Spread above limit", [], {})
        size = self._position_size(
            context.features.get("risk_per_trade", 0.005),
            context.features.get("point_value", 1.0),
            context.features.get("min_lot", 1.0),
            context.features.get("lot_step", 1.0),
            signal.entry,
            signal.sl,
        )
        tp1, tp2 = self._target_from_liquidity(signal)
        return Decision(
            action=signal.action,
            entry=signal.entry,
            sl=signal.sl,
            tp1=tp1,
            tp2=tp2,
            size=size,
            reason=f"Top score {score:.1f}",
            contributors=contributors,
            metadata={
                "top_signal": signal.metadata,
                "macro": macro_signal.metadata if macro_signal else {},
                "signals": [
                    {"brain_id": s.brain_id, "action": s.action, "score": sc, "metadata": s.metadata}
                    for s, sc in scored
                ],
            },
        )

    @staticmethod
    def _risk_reward(signal: BrainSignal) -> float:
        risk = abs(signal.entry - signal.sl)
        reward = abs(signal.tp1 - signal.entry)
        if risk == 0:
            return 0.0
        return reward / risk

    def _weight_for_regime(self, brain_name: str, regime: str) -> float:
        base = self.weights.get(brain_name, 1.0)
        if regime == "range" and "Wyckoff" in brain_name:
            return base * 1.2
        if regime.startswith("trend") and "TrendPullback" in brain_name:
            return base * 1.2
        if regime == "high_vol" and "Momentum" in brain_name:
            return base * 1.1
        return base

    @staticmethod
    def _confluence_gate(scored: List[Tuple[BrainSignal, float]]) -> bool:
        if not scored:
            return False
        top_signal, top_score = scored[0]
        same_dir = sum(1 for s, _ in scored if s.action == top_signal.action)
        if same_dir >= 2:
            return True
        return top_score >= 85.0

    @staticmethod
    def _macro_filter(signal: BrainSignal, macro_signal: BrainSignal) -> bool:
        support_zone = macro_signal.metadata.get("support_zone")
        resistance_zone = macro_signal.metadata.get("resistance_zone")
        if not support_zone or not resistance_zone:
            return True
        if signal.action == "BUY" and support_zone[0] <= signal.entry <= support_zone[1]:
            return True
        if signal.action == "SELL" and resistance_zone[0] <= signal.entry <= resistance_zone[1]:
            return True
        if signal.action == "BUY" and signal.entry > resistance_zone[0]:
            return False
        if signal.action == "SELL" and signal.entry < support_zone[1]:
            return False
        return True

    @staticmethod
    def _position_size(
        risk_per_trade: float,
        point_value: float,
        min_lot: float,
        lot_step: float,
        entry: float,
        sl: float,
    ) -> float:
        risk_points = abs(entry - sl)
        if risk_points <= 0 or point_value <= 0:
            return min_lot
        raw = risk_per_trade / (risk_points * point_value)
        steps = max(1, int(raw / lot_step))
        return max(min_lot, steps * lot_step)

    @staticmethod
    def _target_from_liquidity(signal: BrainSignal) -> tuple[float, float]:
        targets = signal.metadata.get("target_candidates")
        if targets:
            targets = sorted(targets)
            if signal.action == "BUY":
                above = [t for t in targets if t > signal.entry]
                if len(above) >= 2:
                    return above[0], above[1]
            if signal.action == "SELL":
                below = [t for t in targets if t < signal.entry]
                if len(below) >= 2:
                    return below[-1], below[-2]
        return signal.tp1, signal.tp2
