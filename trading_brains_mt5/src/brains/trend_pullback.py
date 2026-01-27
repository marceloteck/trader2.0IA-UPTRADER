from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class TrendPullbackBrain(Brain):
    id = "trend_pullback"
    name = "Trend Pullback"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 50:
            return None
        last = data.iloc[-1]
        ma20 = data["close"].rolling(20).mean().iloc[-1]
        ma89 = data["close"].rolling(89).mean().iloc[-1]
        if pd.isna(ma20) or pd.isna(ma89):
            return None
        bullish = ma20 > ma89 and last["close"] > ma20 and last["low"] <= ma20
        bearish = ma20 < ma89 and last["close"] < ma20 and last["high"] >= ma20
        if bullish:
            return BrainSignal(
                brain_id=self.id,
                action="BUY",
                entry=float(last["close"]),
                sl=float(last["low"]),
                tp1=float(last["close"] + (last["close"] - last["low"]) * 1.5),
                tp2=float(last["close"] + (last["close"] - last["low"]) * 2.5),
                reasons=["Trend up with pullback to MA20"],
            )
        if bearish:
            return BrainSignal(
                brain_id=self.id,
                action="SELL",
                entry=float(last["close"]),
                sl=float(last["high"]),
                tp1=float(last["close"] - (last["high"] - last["close"]) * 1.5),
                tp2=float(last["close"] - (last["high"] - last["close"]) * 2.5),
                reasons=["Trend down with pullback to MA20"],
            )
        return None

    def score(self, signal: BrainSignal, context: Context) -> float:
        regime = context.features.get("regime")
        if signal.action == "BUY" and regime == "trend_up":
            return 85.0
        if signal.action == "SELL" and regime == "trend_down":
            return 85.0
        return 55.0
