from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class WyckoffAdvancedBrain(Brain):
    id = "wyckoff_adv"
    name = "Wyckoff Advanced"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty or len(data) < 50:
            return None
        recent = data.iloc[-50:]
        high = recent["high"].max()
        low = recent["low"].min()
        last = recent.iloc[-1]
        touch_high = (recent["high"] > high * 0.995).sum()
        touch_low = (recent["low"] < low * 1.005).sum()
        compression = (recent["high"] - recent["low"]).mean()
        range_size = high - low
        confidence = 0.6 if compression < range_size * 0.6 else 0.45
        if last["low"] < low and last["close"] > low:
            return BrainSignal(
                brain_id=self.id,
                action="BUY",
                entry=float(last["close"]),
                sl=float(low - range_size * 0.1),
                tp1=float((high + low) / 2),
                tp2=float(high),
                reasons=["Spring detected"],
                metadata={
                    "setup_type": "SPRING",
                    "touch_count": int(touch_low),
                    "confidence": max(0.2, confidence - max(0, touch_low - 2) * 0.1),
                },
            )
        if last["high"] > high and last["close"] < high:
            return BrainSignal(
                brain_id=self.id,
                action="SELL",
                entry=float(last["close"]),
                sl=float(high + range_size * 0.1),
                tp1=float((high + low) / 2),
                tp2=float(low),
                reasons=["Upthrust detected"],
                metadata={
                    "setup_type": "UPTHRUST",
                    "touch_count": int(touch_high),
                    "confidence": max(0.2, confidence - max(0, touch_high - 2) * 0.1),
                },
            )
        if touch_high >= 2 and touch_low >= 2:
            direction = "BUY" if last["close"] < (high + low) / 2 else "SELL"
            return BrainSignal(
                brain_id=self.id,
                action=direction,
                entry=float(last["close"]),
                sl=float(low if direction == "BUY" else high),
                tp1=float((high + low) / 2),
                tp2=float(high if direction == "BUY" else low),
                reasons=["Range extreme with multiple touches"],
                metadata={
                    "setup_type": "RANGE_EXTREME",
                    "touch_count": int(max(touch_high, touch_low)),
                    "confidence": max(0.3, confidence - max(0, max(touch_high, touch_low) - 2) * 0.1),
                },
            )
        return None

    def score(self, signal: BrainSignal, context: Context) -> float:
        confidence = float(signal.metadata.get("confidence", 0.4))
        if context.features.get("regime") == "range":
            confidence += 0.1
        return 55.0 + confidence * 35.0
