from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pandas as pd


try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None


_TIMEFRAME_MAP = {
    "M1": getattr(mt5, "TIMEFRAME_M1", 1),
    "M5": getattr(mt5, "TIMEFRAME_M5", 5),
    "H1": getattr(mt5, "TIMEFRAME_H1", 60),
}


@dataclass
class MT5Client:
    retry_seconds: int = 5

    def connect(self) -> bool:
        if mt5 is None:
            return False
        if mt5.initialize():
            return True
        return False

    def ensure_connected(self) -> bool:
        for _ in range(3):
            if self.connect():
                return True
            time.sleep(self.retry_seconds)
        return False

    def ensure_symbol(self, symbol: str) -> bool:
        if mt5 is None:
            return False
        info = mt5.symbol_info(symbol)
        if info is None:
            return False
        if not info.visible:
            return mt5.symbol_select(symbol, True)
        return True

    def fetch_rates(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        count: Optional[int] = None,
    ) -> pd.DataFrame:
        if mt5 is None:
            return pd.DataFrame()
        tf = _TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M1)
        if count:
            rates = mt5.copy_rates_from(symbol, tf, end, count)
        else:
            rates = mt5.copy_rates_range(symbol, tf, start, end)
        if rates is None:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def fetch_latest_rates(self, symbol: str, timeframe: str, n: int = 300) -> pd.DataFrame:
        if mt5 is None:
            return pd.DataFrame()
        tf = _TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
        if rates is None:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def fetch_ticks(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        if mt5 is None:
            return pd.DataFrame()
        ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
        if ticks is None:
            return pd.DataFrame()
        df = pd.DataFrame(ticks)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def shutdown(self) -> None:
        if mt5 is not None:
            mt5.shutdown()
