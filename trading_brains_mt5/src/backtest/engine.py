from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

import numpy as np
import pandas as pd

from ..brains.brain_hub import BossBrain
from ..brains.brain_interface import Context
from ..features.feature_store import build_features
from ..db import repo


@dataclass
class BacktestResult:
    trades: List[Dict[str, float]]
    pnls: List[float]


def run_backtest(
    symbol: str,
    df: pd.DataFrame,
    db_path: str,
    spread_max: float = 2.0,
    slippage: float = 1.0,
    risk_per_trade: float = 0.005,
    point_value: float = 1.0,
    min_lot: float = 1.0,
    lot_step: float = 1.0,
    round_level_step: float = 100.0,
    fill_model: Optional[object] = None,
) -> BacktestResult:
    boss = BossBrain()
    trades: List[Dict[str, float]] = []
    pnls: List[float] = []
    for idx in range(200, len(df)):
        window = df.iloc[: idx + 1]
        features = build_features(window, round_step=round_level_step)
        spread = _dynamic_spread(window, spread_max)
        features.update(
            {
                "risk_per_trade": risk_per_trade,
                "point_value": point_value,
                "min_lot": min_lot,
                "lot_step": lot_step,
                "spread_max": spread_max,
            }
        )
        context = Context(symbol=symbol, timeframe="M1", features=features, spread=spread)
        decision = boss.run(window, context)
        if decision.action == "HOLD":
            continue
        for signal in decision.metadata.get("signals", []):
            repo.insert_brain_signal(
                db_path,
                symbol,
                str(window.iloc[-1]["time"]),
                signal["brain_id"],
                signal,
                float(signal.get("score", 0.0)),
            )
        if fill_model:
            entry_fill = fill_model.calculate_fill(
                requested_price=decision.entry,
                side=decision.action,
                atr=float(features.get("atr", 0.0)),
                symbol=symbol,
                is_live=False,
            )
            if not entry_fill.success:
                continue
            entry = entry_fill.filled_price
        else:
            entry = decision.entry + (spread / 2 if decision.action == "BUY" else -spread / 2)
            entry = _apply_slippage(entry, decision.action, slippage)
        sl = decision.sl
        tp = decision.tp1
        future = df.iloc[idx + 1 : idx + 30]
        exit_price = None
        for _, row in future.iterrows():
            if decision.action == "BUY":
                if row["low"] <= sl:
                    exit_price = sl
                    break
                if row["high"] >= tp:
                    exit_price = tp
                    break
            else:
                if row["high"] >= sl:
                    exit_price = sl
                    break
                if row["low"] <= tp:
                    exit_price = tp
                    break
        if exit_price is None:
            exit_price = future.iloc[-1]["close"] if not future.empty else entry
        exit_price = exit_price - (spread / 2 if decision.action == "BUY" else -spread / 2)
        if fill_model:
            close_side = "SELL" if decision.action == "BUY" else "BUY"
            exit_fill = fill_model.calculate_fill(
                requested_price=exit_price,
                side=close_side,
                atr=float(features.get("atr", 0.0)),
                symbol=symbol,
                is_live=False,
            )
            if exit_fill.success:
                exit_price = exit_fill.filled_price
        pnl = exit_price - entry if decision.action == "BUY" else entry - exit_price
        trades.append(
            {
                "symbol": symbol,
                "opened_at": str(window.iloc[-1]["time"]),
                "closed_at": str(future.iloc[-1]["time"]) if not future.empty else str(window.iloc[-1]["time"]),
                "side": decision.action,
                "entry": float(entry),
                "exit": float(exit_price),
                "pnl": float(pnl),
                "mfe": float(abs(tp - entry)),
                "mae": float(abs(sl - entry)),
                "source": "backtest",
                "payload": {
                    "reason": decision.reason,
                    "contributors": decision.contributors,
                    "spread": spread,
                    "slippage": slippage,
                    "time_in_trade": len(future),
                },
            }
        )
        pnls.append(float(pnl))
        repo.insert_trade(db_path, trades[-1])
    return BacktestResult(trades=trades, pnls=pnls)


def _dynamic_spread(window: pd.DataFrame, spread_max: float) -> float:
    if window.empty:
        return spread_max
    avg_range = float((window["high"] - window["low"]).rolling(20).mean().iloc[-1])
    if np.isnan(avg_range):
        avg_range = float((window["high"] - window["low"]).mean())
    return min(spread_max, avg_range * 0.1 if avg_range else spread_max)


def _apply_slippage(price: float, action: str, slippage: float) -> float:
    slip = float(np.random.uniform(-slippage, slippage))
    return price + slip if action == "BUY" else price - slip
