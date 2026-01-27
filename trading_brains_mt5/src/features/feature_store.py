from __future__ import annotations

from typing import Dict

import pandas as pd

from .indicators import add_atr, add_moving_averages, add_pivots, add_rsi, add_vwap
from .regimes import classify_regime
from .liquidity import liquidity_levels


def build_features(df: pd.DataFrame, round_step: float = 100) -> Dict[str, float | str]:
    if df.empty:
        return {"regime": "unknown"}
    out = add_moving_averages(df, [20, 34, 89, 200])
    out = add_vwap(out)
    out = add_rsi(out)
    out = add_atr(out)
    out = add_pivots(out)
    last = out.iloc[-1]
    features = {
        "close": float(last["close"]),
        "vwap": float(last["vwap"]) if not pd.isna(last["vwap"]) else 0.0,
        "rsi": float(last["rsi"]) if not pd.isna(last["rsi"]) else 0.0,
        "atr": float(last["atr"]) if not pd.isna(last["atr"]) else 0.0,
        "ma_20": float(last["ma_20"]) if not pd.isna(last["ma_20"]) else 0.0,
        "ma_34": float(last["ma_34"]) if not pd.isna(last["ma_34"]) else 0.0,
        "ma_89": float(last["ma_89"]) if not pd.isna(last["ma_89"]) else 0.0,
        "ma_200": float(last["ma_200"]) if not pd.isna(last["ma_200"]) else 0.0,
        "pivot_high": float(last["pivot_high"]) if not pd.isna(last["pivot_high"]) else 0.0,
        "pivot_low": float(last["pivot_low"]) if not pd.isna(last["pivot_low"]) else 0.0,
    }
    features.update(liquidity_levels(out, round_step=round_step))
    features["regime"] = classify_regime(out)
    return features
