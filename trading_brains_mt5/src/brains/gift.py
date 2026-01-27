from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class GiftBrain(Brain):
    id = "gift"
    name = "GIFT"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 5:
            return None
        last = data.iloc[-1]
        prev = data.iloc[-2]
        body = abs(prev["close"] - prev["open"])
        candle_range = prev["high"] - prev["low"]
        if candle_range == 0:
            return None
        strong = body / candle_range > 0.7
        if strong and prev["close"] > prev["open"]:
            limit = prev["close"] - (body * 0.33)
            if last["low"] >= limit and last["close"] > prev["open"]:
                return BrainSignal(
                    brain_id=self.id,
                    action="BUY",
                    entry=float(last["close"]),
                    sl=float(last["low"]),
                    tp1=float(last["close"] + body),
                    tp2=float(last["close"] + body * 1.5),
                    reasons=["Strong impulse candle", "Follow-through respecting 1/3"],
                )
        if strong and prev["close"] < prev["open"]:
            limit = prev["close"] + (body * 0.33)
            if last["high"] <= limit and last["close"] < prev["open"]:
                return BrainSignal(
                    brain_id=self.id,
                    action="SELL",
                    entry=float(last["close"]),
                    sl=float(last["high"]),
                    tp1=float(last["close"] - body),
                    tp2=float(last["close"] - body * 1.5),
                    reasons=["Strong impulse candle", "Follow-through respecting 1/3"],
                )
        return None

    def score(self, signal: BrainSignal, context: Context) -> float:
        regime = context.features.get("regime")
        if regime in {"trend_up", "trend_down"}:
            return 75.0
        return 50.0
