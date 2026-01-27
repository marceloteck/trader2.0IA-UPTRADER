from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


@dataclass
class MacroZones:
    support_zone: tuple[float, float]
    resistance_zone: tuple[float, float]
    macro_trend: str


class GannMacroBrain(Brain):
    id = "gann_macro"
    name = "Gann Macro"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 100:
            return None
        zones = self._compute_zones(data)
        last = float(data.iloc[-1]["close"])
        return BrainSignal(
            brain_id=self.id,
            action="NEUTRAL",
            entry=last,
            sl=zones.support_zone[0],
            tp1=zones.resistance_zone[0],
            tp2=zones.resistance_zone[1],
            reasons=[f"Macro trend {zones.macro_trend}"],
            metadata={
                "macro_trend": zones.macro_trend,
                "support_zone": zones.support_zone,
                "resistance_zone": zones.resistance_zone,
            },
        )

    def score(self, signal: BrainSignal, context: Context) -> float:
        return 40.0

    def _compute_zones(self, data: pd.DataFrame) -> MacroZones:
        ma_fast = data["close"].rolling(50).mean().iloc[-1]
        ma_slow = data["close"].rolling(200).mean().iloc[-1]
        pivot_high = data["high"].rolling(200).max().iloc[-1]
        pivot_low = data["low"].rolling(200).min().iloc[-1]
        last = data["close"].iloc[-1]
        macro_trend = "RANGE"
        if ma_fast > ma_slow:
            macro_trend = "UP"
        elif ma_fast < ma_slow:
            macro_trend = "DOWN"
        support_zone = (float(pivot_low), float(pivot_low + (last - pivot_low) * 0.15))
        resistance_zone = (
            float(pivot_high - (pivot_high - last) * 0.15),
            float(pivot_high),
        )
        return MacroZones(
            support_zone=support_zone,
            resistance_zone=resistance_zone,
            macro_trend=macro_trend,
        )
