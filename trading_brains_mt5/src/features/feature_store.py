from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from .indicators import add_atr, add_moving_averages, add_pivots, add_rsi, add_vwap
from .regimes import classify_regime
from .liquidity import liquidity_levels


def build_features(
    df: pd.DataFrame,
    round_step: float = 100,
    higher_df: Optional[pd.DataFrame] = None,
) -> Dict[str, float | str]:
    if df.empty:
        return {"regime": "unknown"}
    out = add_moving_averages(df, [20, 34, 89, 200])
    out = add_vwap(out)
    out = add_rsi(out)
    out = add_atr(out)
    out = add_pivots(out)
    last = out.iloc[-1]
    candle_range = float(last["high"] - last["low"])
    candle_body = float(abs(last["close"] - last["open"]))
    upper_wick = float(last["high"] - max(last["open"], last["close"]))
    lower_wick = float(min(last["open"], last["close"]) - last["low"])
    candle_range = candle_range if candle_range > 0 else 1e-9
    body_ratio = candle_body / candle_range
    wick_ratio = (upper_wick + lower_wick) / candle_range
    volume_zscore = 0.0
    if "tick_volume" in out.columns:
        volume_roll = out["tick_volume"].rolling(20)
        vol_mean = volume_roll.mean().iloc[-1]
        vol_std = volume_roll.std().iloc[-1]
        if vol_std and not pd.isna(vol_std) and vol_std > 0:
            volume_zscore = float((last["tick_volume"] - vol_mean) / vol_std)
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
        "candle_body_ratio": float(body_ratio),
        "candle_wick_ratio": float(wick_ratio),
        "volume_zscore": float(volume_zscore),
    }
    features.update(liquidity_levels(out, round_step=round_step))
    features["regime"] = classify_regime(out)
    if higher_df is not None and not higher_df.empty:
        higher = add_moving_averages(higher_df, [20, 50])
        higher = add_atr(higher)
        higher_last = higher.iloc[-1]
        features["regime_h1"] = classify_regime(higher)
        features["ma_20_h1"] = float(higher_last["ma_20"]) if not pd.isna(higher_last["ma_20"]) else 0.0
        features["ma_50_h1"] = float(higher_last["ma_50"]) if not pd.isna(higher_last["ma_50"]) else 0.0
        features["atr_h1"] = float(higher_last["atr"]) if not pd.isna(higher_last["atr"]) else 0.0
    return features
