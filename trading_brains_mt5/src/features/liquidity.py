from __future__ import annotations

import pandas as pd


def liquidity_levels(df: pd.DataFrame, round_step: float = 100) -> dict:
    if df.empty:
        return {}
    recent = df.iloc[-100:]
    high = recent["high"].max()
    low = recent["low"].min()
    return {
        "day_high": high,
        "day_low": low,
        "round_level": round(recent["close"].iloc[-1] / round_step) * round_step,
    }
