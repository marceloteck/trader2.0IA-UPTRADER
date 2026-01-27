from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


@dataclass
class ElliottCandidate:
    direction: str
    score: float
    invalidation: float
    target_zone: tuple[float, float]


class ElliottProbBrain(Brain):
    id = "elliott_prob"
    name = "Elliott Probabilístico"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 40:
            return None
        pivots = self._extract_pivots(data)
        if len(pivots) < 5:
            return None
        candidates = self._build_candidates(data, pivots)
        if not candidates:
            return None
        best = max(candidates, key=lambda c: c.score)
        action = best.direction if best.direction in {"BUY", "SELL"} else "NEUTRAL"
        return BrainSignal(
            brain_id=self.id,
            action=action,
            entry=float(data.iloc[-1]["close"]),
            sl=float(best.invalidation),
            tp1=float(best.target_zone[0]),
            tp2=float(best.target_zone[1]),
            reasons=["Probabilistic Elliott count"],
            metadata={
                "confidence": best.score,
                "candidates": [c.__dict__ for c in candidates],
                "invalidation_level": best.invalidation,
                "target_zone": best.target_zone,
            },
        )

    def score(self, signal: BrainSignal, context: Context) -> float:
        confidence = float(signal.metadata.get("confidence", 0.0))
        return 50.0 + confidence * 30.0

    def _extract_pivots(self, data: pd.DataFrame) -> List[float]:
        highs = data["high"].rolling(3).max()
        lows = data["low"].rolling(3).min()
        pivots = []
        for i in range(2, len(data) - 2):
            if data["high"].iloc[i] == highs.iloc[i]:
                pivots.append(data["high"].iloc[i])
            if data["low"].iloc[i] == lows.iloc[i]:
                pivots.append(data["low"].iloc[i])
        return pivots[-10:]

    def _build_candidates(self, data: pd.DataFrame, pivots: List[float]) -> List[ElliottCandidate]:
        last = data.iloc[-1]["close"]
        candidates: List[ElliottCandidate] = []
        recent_range = max(pivots) - min(pivots)
        if recent_range == 0:
            return candidates
        retrace = (last - min(pivots)) / recent_range
        confidence = max(0.0, min(1.0, 1 - abs(0.5 - retrace)))
        up_target = last + recent_range * 0.618
        down_target = last - recent_range * 0.618
        candidates.append(
            ElliottCandidate(
                direction="BUY",
                score=confidence,
                invalidation=min(pivots),
                target_zone=(last + recent_range * 0.382, up_target),
            )
        )
        candidates.append(
            ElliottCandidate(
                direction="SELL",
                score=confidence * 0.9,
                invalidation=max(pivots),
                target_zone=(last - recent_range * 0.382, down_target),
            )
        )
        if confidence < 0.4:
            candidates.append(
                ElliottCandidate(
                    direction="NEUTRAL",
                    score=0.4,
                    invalidation=last,
                    target_zone=(last - recent_range * 0.1, last + recent_range * 0.1),
                )
            )
        return candidates
