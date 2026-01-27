from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ..config.settings import Settings
from ..db import repo
from ..features.feature_store import build_features
from ..infra.time_utils import utc_now
from ..models.model_store import save_model
from ..models.supervised import train_simple_classifier
from ..models.calibrator import calibrate_by_segments
from ..mt5.mt5_client import MT5Client
from .state import load_state


def _build_dataset(df: pd.DataFrame, horizon: int, round_step: float) -> Tuple[np.ndarray, np.ndarray]:
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


def run_training(settings: Settings, replay: int = 1) -> Dict[str, float]:
    client = MT5Client()
    if not client.ensure_connected() or not client.ensure_symbol(settings.symbol):
        return {"status": "mt5_not_connected"}

    state = load_state(settings.db_path)
    end = datetime.utcnow()
    start = end - timedelta(days=60)
    if state:
        start = datetime.fromisoformat(state["last_time"]) if state["last_time"] else start

    df = client.fetch_rates(settings.symbol, settings.timeframes[0], start, end)
    if df.empty:
        return {"status": "no_data"}

    X, y = _build_dataset(df, settings.label_horizon_candles, settings.round_level_step)
    if len(X) == 0:
        return {"status": "not_enough_data"}

    model, score = train_simple_classifier(X, y)
    model_path = str(Path("./data/exports/models") / f"model_{utc_now().strftime('%Y%m%d_%H%M%S')}.joblib")
    save_model(model, model_path)
    metrics = {"train_score": score, "samples": len(X)}
    repo.insert_model(settings.db_path, "log_reg", utc_now().isoformat(), metrics, model_path)
    _save_calibration(settings, df, y)
    repo.upsert_training_state(
        settings.db_path,
        settings.symbol,
        settings.timeframes[0],
        str(df.iloc[-1]["time"]),
        {
            "last_score": score,
            "last_dataset_rows": len(X),
            "label_horizon": settings.label_horizon_candles,
            "model_version": "log_reg_v2",
            "seed": 42,
        },
    )
    return metrics


def _save_calibration(settings: Settings, df: pd.DataFrame, y: np.ndarray) -> None:
    samples = []
    for idx in range(50, min(len(df) - 1, len(y) + 50)):
        window = df.iloc[: idx + 1]
        features = build_features(window, round_step=settings.round_level_step)
        hour_bucket = window.iloc[-1]["time"].strftime("%H")
        samples.append(
            {
                "regime": features.get("regime", "unknown"),
                "hour_bucket": hour_bucket,
                "win_rate": 1.0 if y[idx - 50] == 1 else 0.0,
            }
        )
    thresholds = calibrate_by_segments(samples)
    for key, threshold in thresholds.items():
        regime, hour_bucket = key.split(":")
        repo.insert_calibration(settings.db_path, "log_reg", regime, hour_bucket, threshold, {})
