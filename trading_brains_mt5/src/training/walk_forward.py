from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

from ..config.settings import Settings
from ..db import repo
from ..features.feature_store import build_features
from ..models.supervised import train_simple_classifier
from ..mt5.mt5_client import MT5Client


def run_walk_forward(settings: Settings) -> List[Dict[str, float]]:
    client = MT5Client()
    if not client.ensure_connected() or not client.ensure_symbol(settings.symbol):
        return []
    end = datetime.utcnow()
    start = end - timedelta(days=settings.train_window_days + settings.test_window_days)
    df = client.fetch_rates(settings.symbol, settings.timeframes[0], start, end)
    if df.empty:
        return []
    windows = _split_windows(df, settings.train_window_days, settings.test_window_days)
    results = []
    for window_id, (train_df, test_df) in enumerate(windows):
        X_train, y_train = _build_dataset(train_df, settings.label_horizon_candles, settings.round_level_step)
        if len(X_train) == 0:
            continue
        model, score = train_simple_classifier(X_train, y_train)
        X_test, y_test = _build_dataset(test_df, settings.label_horizon_candles, settings.round_level_step)
        test_score = float(model.score(X_test, y_test)) if len(X_test) else 0.0
        metrics = {"train_score": score, "test_score": test_score, "train_samples": len(X_train)}
        repo.insert_metrics_window(settings.db_path, 1, window_id, metrics)
        results.append(metrics)
    return results


def _split_windows(df: pd.DataFrame, train_days: int, test_days: int):
    total = train_days + test_days
    start = df["time"].min()
    end = df["time"].max()
    current = start
    while current + timedelta(days=total) <= end:
        train_end = current + timedelta(days=train_days)
        test_end = train_end + timedelta(days=test_days)
        train_df = df[(df["time"] >= current) & (df["time"] < train_end)]
        test_df = df[(df["time"] >= train_end) & (df["time"] < test_end)]
        yield train_df, test_df
        current = test_end


def _build_dataset(df: pd.DataFrame, horizon: int, round_step: float) -> tuple[np.ndarray, np.ndarray]:
    X = []
    y = []
    for idx in range(50, len(df) - horizon):
        window = df.iloc[: idx + 1]
        features = build_features(window, round_step=round_step)
        X.append([
            features.get("close", 0.0),
            features.get("vwap", 0.0),
            features.get("rsi", 0.0),
            features.get("atr", 0.0),
            features.get("ma_20", 0.0),
            features.get("ma_89", 0.0),
        ])
        future = df.iloc[idx : idx + horizon]
        y.append(1 if future["close"].max() > df.iloc[idx]["close"] else 0)
    return np.array(X), np.array(y)
