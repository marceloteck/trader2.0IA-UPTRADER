from __future__ import annotations

import pandas as pd


def normalize_rates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    cols = ["time", "open", "high", "low", "close", "tick_volume"]
    return df[cols].copy()
