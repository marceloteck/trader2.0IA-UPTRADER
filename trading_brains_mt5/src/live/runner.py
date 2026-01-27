from __future__ import annotations

from dataclasses import asdict

from ..brains.brain_hub import BossBrain
from ..brains.brain_interface import Context
from ..brains.cluster_proxy import ClusterProxyBrain
from ..brains.liquidity_levels import LiquidityBrain
from ..db import repo
from ..features.feature_store import build_features
from ..infra.safety import assert_live_trading_enabled, stop_file_exists
from ..mt5.data_feed import stream_latest_candles
from ..mt5.mt5_client import MT5Client
from ..mt5.orders import send_order
from .risk import RiskState, check_limits
from ..backtest.engine import _dynamic_spread, _apply_slippage


def run_live_real(settings) -> None:
    assert_live_trading_enabled(settings.enable_live_trading, settings.live_confirm_key)
    client = MT5Client()
    if not client.ensure_connected() or not client.ensure_symbol(settings.symbol):
        return
    boss = BossBrain()
    risk = RiskState()
    for bundle in stream_latest_candles(client, settings.symbol, settings.timeframes):
        if stop_file_exists():
            break
        df = bundle.get(settings.timeframes[0])
        if df is None or df.empty:
            continue
        features = build_features(df, round_step=settings.round_level_step)
        features.update(
            {
                "spread_max": settings.spread_max,
                "risk_per_trade": settings.risk_per_trade,
                "point_value": settings.point_value,
                "min_lot": settings.min_lot,
                "lot_step": settings.lot_step,
            }
        )
        spread = _dynamic_spread(df, settings.spread_max)
        context = Context(symbol=settings.symbol, timeframe=settings.timeframes[0], features=features, spread=spread)
        decision = boss.run(bundle, context)
        repo.insert_decision(settings.db_path, settings.symbol, str(df.iloc[-1]["time"]), decision.action, asdict(decision))
        for signal in decision.metadata.get("signals", []):
            repo.insert_brain_signal(
                settings.db_path,
                settings.symbol,
                str(df.iloc[-1]["time"]),
                signal["brain_id"],
                signal,
                float(signal.get("score", 0.0)),
            )
        repo.insert_regime_log(settings.db_path, settings.symbol, str(df.iloc[-1]["time"]), features.get("regime", "unknown"), {})
        _store_levels(settings, df)
        if decision.action == "HOLD":
            continue
        if not check_limits(risk, settings.daily_loss_limit, settings.max_trades_per_day, settings.max_consec_losses):
            continue
        price = float(df.iloc[-1]["close"])
        price = price + (spread / 2 if decision.action == "BUY" else -spread / 2)
        price = _apply_slippage(price, decision.action, settings.slippage)
        order = send_order(settings.symbol, decision.action, decision.size, price, decision.sl, decision.tp1)
        repo.insert_order_event(
            settings.db_path,
            settings.symbol,
            str(df.iloc[-1]["time"]),
            decision.action,
            order.retcode,
            order.message,
        )
        trade = {
            "symbol": settings.symbol,
            "opened_at": str(df.iloc[-1]["time"]),
            "closed_at": None,
            "side": decision.action,
            "entry": float(price),
            "exit": None,
            "pnl": None,
            "mfe": None,
            "mae": None,
            "source": "live" if order.success else "live_failed",
            "payload": {"order_result": order.message},
        }
        repo.insert_trade(settings.db_path, trade)
        risk.trades_today += 1


def _store_levels(settings, df):
    cluster = ClusterProxyBrain().detect(df)
    if cluster and cluster.metadata.get("levels_detected"):
        repo.insert_level(
            settings.db_path,
            settings.symbol,
            str(df.iloc[-1]["time"]),
            "cluster_proxy",
            {"levels": cluster.metadata.get("levels_detected")},
        )
    liquidity = LiquidityBrain().detect(df)
    if liquidity:
        repo.insert_level(
            settings.db_path,
            settings.symbol,
            str(df.iloc[-1]["time"]),
            "liquidity",
            {
                "supports": liquidity.metadata.get("nearest_supports"),
                "resistances": liquidity.metadata.get("nearest_resistances"),
            },
        )
