from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class LiquidityBrain(Brain):
    id = "liquidity"
    name = "Liquidity Levels"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty:
            return None
        last = float(data.iloc[-1]["close"])
        supports = []
        resistances = []
        if "vwap" in data.columns:
            vwap = float(data["vwap"].iloc[-1])
            if vwap < last:
                supports.append(vwap)
            else:
                resistances.append(vwap)
        pivot_high = float(data["high"].rolling(50).max().iloc[-1])
        pivot_low = float(data["low"].rolling(50).min().iloc[-1])
        round_step = 50.0
        round_level = round(last / round_step) * round_step
        supports.append(round_level if round_level < last else pivot_low)
        resistances.append(round_level if round_level > last else pivot_high)
        supports.append(pivot_low)
        resistances.append(pivot_high)
        action = "NEUTRAL"
        return BrainSignal(
            brain_id=self.id,
            action=action,
            entry=last,
            sl=pivot_low,
            tp1=pivot_high,
            tp2=pivot_high,
            reasons=["Liquidity levels consolidated"],
            metadata={
                "nearest_supports": sorted(supports)[:3],
                "nearest_resistances": sorted(resistances, reverse=True)[:3],
                "target_candidates": sorted(set(supports + resistances)),
            },
        )

    def score(self, signal: BrainSignal, context: Context) -> float:
        return 50.0
