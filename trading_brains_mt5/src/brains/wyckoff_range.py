from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class WyckoffRangeBrain(Brain):
    id = "wyckoff_range"
    name = "Wyckoff Range"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 30:
            return None
        recent = data.iloc[-30:]
        high = recent["high"].max()
        low = recent["low"].min()
        last = recent.iloc[-1]
        wick = abs(last["close"] - last["open"]) < (last["high"] - last["low"]) * 0.3
        if wick and last["close"] > last["open"] and last["low"] <= low * 1.001:
            return BrainSignal(
                brain_id=self.id,
                action="BUY",
                entry=float(last["close"]),
                sl=float(low),
                tp1=float((high + low) / 2),
                tp2=float(high),
                reasons=["Rejection at range low", "Potential absorption"],
            )
        if wick and last["close"] < last["open"] and last["high"] >= high * 0.999:
            return BrainSignal(
                brain_id=self.id,
                action="SELL",
                entry=float(last["close"]),
                sl=float(high),
                tp1=float((high + low) / 2),
                tp2=float(low),
                reasons=["Rejection at range high", "Potential absorption"],
            )
        return None

    def score(self, signal: BrainSignal, context: Context) -> float:
        if context.features.get("regime") == "range":
            return 80.0
        return 60.0
