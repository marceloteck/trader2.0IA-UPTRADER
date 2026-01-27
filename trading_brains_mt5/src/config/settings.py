from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

from .constants import DEFAULT_TIMEFRAMES


@dataclass(frozen=True)
class Settings:
    symbol: str
    timeframes: List[str]
    db_path: str
    log_path: str
    spread_max: float
    slippage: float
    risk_per_trade: float
    point_value: float
    min_lot: float
    lot_step: float
    enable_live_trading: bool
    live_confirm_key: str
    daily_loss_limit: float
    max_trades_per_day: int
    max_consec_losses: int
    broker_tz: str
    train_window_days: int
    test_window_days: int
    label_horizon_candles: int
    round_level_step: float
    session_start: str
    session_end: str
    enable_dashboard_control: bool


_DEF = {
    "SYMBOL": "WIN$N",
    "TIMEFRAMES": ",".join(DEFAULT_TIMEFRAMES),
    "DB_PATH": "./data/db/trading.db",
    "LOG_PATH": "./data/logs/app.log",
    "SPREAD_MAX": "2.0",
    "SLIPPAGE": "1.0",
    "RISK_PER_TRADE": "0.005",
    "POINT_VALUE": "1.0",
    "MIN_LOT": "1.0",
    "LOT_STEP": "1.0",
    "ENABLE_LIVE_TRADING": "false",
    "LIVE_CONFIRM_KEY": "CHANGE_ME",
    "DAILY_LOSS_LIMIT": "200.0",
    "MAX_TRADES_PER_DAY": "5",
    "MAX_CONSEC_LOSSES": "3",
    "BROKER_TZ": "America/Sao_Paulo",
    "TRAIN_WINDOW_DAYS": "30",
    "TEST_WINDOW_DAYS": "10",
    "LABEL_HORIZON_CANDLES": "30",
    "ROUND_LEVEL_STEP": "50",
    "SESSION_START": "09:00",
    "SESSION_END": "17:00",
    "ENABLE_DASHBOARD_CONTROL": "false",
}


def _get_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_settings() -> Settings:
    load_dotenv()

    def get_env(key: str) -> str:
        return os.getenv(key, _DEF[key])

    timeframes = [tf.strip() for tf in get_env("TIMEFRAMES").split(",") if tf.strip()]
    if not timeframes:
        timeframes = DEFAULT_TIMEFRAMES

    return Settings(
        symbol=get_env("SYMBOL"),
        timeframes=timeframes,
        db_path=get_env("DB_PATH"),
        log_path=get_env("LOG_PATH"),
        spread_max=float(get_env("SPREAD_MAX")),
        slippage=float(get_env("SLIPPAGE")),
        risk_per_trade=float(get_env("RISK_PER_TRADE")),
        point_value=float(get_env("POINT_VALUE")),
        min_lot=float(get_env("MIN_LOT")),
        lot_step=float(get_env("LOT_STEP")),
        enable_live_trading=_get_bool(get_env("ENABLE_LIVE_TRADING")),
        live_confirm_key=get_env("LIVE_CONFIRM_KEY"),
        daily_loss_limit=float(get_env("DAILY_LOSS_LIMIT")),
        max_trades_per_day=int(get_env("MAX_TRADES_PER_DAY")),
        max_consec_losses=int(get_env("MAX_CONSEC_LOSSES")),
        broker_tz=get_env("BROKER_TZ"),
        train_window_days=int(get_env("TRAIN_WINDOW_DAYS")),
        test_window_days=int(get_env("TEST_WINDOW_DAYS")),
        label_horizon_candles=int(get_env("LABEL_HORIZON_CANDLES")),
        round_level_step=float(get_env("ROUND_LEVEL_STEP")),
        session_start=get_env("SESSION_START"),
        session_end=get_env("SESSION_END"),
        enable_dashboard_control=_get_bool(get_env("ENABLE_DASHBOARD_CONTROL")),
    )
