from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


@dataclass
class LevelProxy:
    level: float
    touch_count: int
    strength: float


class ClusterProxyBrain(Brain):
    id = "cluster_proxy"
    name = "Cluster Proxy"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 30:
            return None
        recent = data.iloc[-30:]
        tick_spike = recent["tick_volume"] > recent["tick_volume"].rolling(10).mean() * 1.5
        absorption = (recent["high"] - recent["low"]) > (recent["close"] - recent["open"]).abs() * 2
        levels = []
        for idx, row in recent[tick_spike & absorption].iterrows():
            level = float(row["close"])
            touch_count = int(((recent["close"] - level).abs() < (recent["close"].std() * 0.2)).sum())
            strength = min(1.0, (row["tick_volume"] / recent["tick_volume"].mean()) * 0.5)
            levels.append(LevelProxy(level=level, touch_count=touch_count, strength=strength))
        if not levels:
            return None
        bias = "NEUTRAL"
        latest = levels[-1]
        if latest.touch_count <= 2:
            bias = "BUY" if recent.iloc[-1]["close"] > recent.iloc[-2]["close"] else "SELL"
        return BrainSignal(
            brain_id=self.id,
            action=bias,
            entry=float(recent.iloc[-1]["close"]),
            sl=float(recent.iloc[-1]["low"]),
            tp1=float(recent.iloc[-1]["high"]),
            tp2=float(recent.iloc[-1]["high"] + recent["high"].std()),
            reasons=["Cluster proxy detected"],
            metadata={
                "levels_detected": [lvl.__dict__ for lvl in levels],
                "direction_bias": bias,
            },
        )

    def score(self, signal: BrainSignal, context: Context) -> float:
        return 45.0
