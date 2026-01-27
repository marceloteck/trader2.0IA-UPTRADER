from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Iterator

import pandas as pd

from .mt5_client import MT5Client


def stream_latest_candles(
    client: MT5Client,
    symbol: str,
    timeframes: list[str],
    poll_seconds: int = 10,
) -> Iterator[Dict[str, pd.DataFrame]]:
    last_times: Dict[str, datetime] = {}
    while True:
        bundle: Dict[str, pd.DataFrame] = {}
        for tf in timeframes:
            df = client.fetch_latest_rates(symbol, tf, n=500)
            if df.empty:
                bundle[tf] = df
                continue
            latest_time = df.iloc[-1]["time"]
            if last_times.get(tf) != latest_time:
                last_times[tf] = latest_time
                bundle[tf] = df
        if bundle:
            yield bundle
        time.sleep(poll_seconds)
