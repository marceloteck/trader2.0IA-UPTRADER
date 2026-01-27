from __future__ import annotations

import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


def add_moving_averages(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    out = df.copy()
    for p in periods:
        out[f"ma_{p}"] = out["close"].rolling(p).mean()
    return out


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["vwap"] = np.nan
        return out
    pv = out["close"] * out["tick_volume"].fillna(0)
    out["vwap"] = pv.cumsum() / out["tick_volume"].replace(0, np.nan).cumsum()
    return out


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["rsi"] = np.nan
        return out
    out["rsi"] = RSIIndicator(out["close"], window=period).rsi()
    return out


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["atr"] = np.nan
        return out
    atr = AverageTrueRange(
        high=out["high"], low=out["low"], close=out["close"], window=period
    ).average_true_range()
    out["atr"] = atr
    return out


def add_pivots(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["pivot_high"] = out["high"].rolling(lookback).max()
    out["pivot_low"] = out["low"].rolling(lookback).min()
    return out
