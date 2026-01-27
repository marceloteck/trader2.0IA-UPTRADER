from __future__ import annotations

import pandas as pd


def classify_regime(df: pd.DataFrame) -> str:
    if df.empty or "ma_20" not in df.columns or "atr" not in df.columns:
        return "unknown"
    recent = df.iloc[-5:]
    slope = recent["ma_20"].diff().mean()
    atr = recent["atr"].mean()
    if atr > recent["close"].mean() * 0.01:
        return "high_vol"
    if slope > 0:
        return "trend_up"
    if slope < 0:
        return "trend_down"
    return "range"
