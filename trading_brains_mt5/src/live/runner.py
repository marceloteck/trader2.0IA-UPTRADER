from __future__ import annotations

from dataclasses import asdict
import logging
import os

from ..brains.brain_hub import BossBrain
from ..brains.brain_interface import Context
from ..brains.cluster_proxy import ClusterProxyBrain
from ..brains.liquidity_levels import LiquidityBrain
from ..db import repo
from ..db.repo_adapter import RepoAdapter
from ..execution.execution_engine import ExecutionEngine, ExecutionMode, Decision as EngineDecision
from ..execution.fill_model import FillModel
from ..execution.order_router import RouterMT5
from ..execution.position_tracker import PositionTracker
from ..execution.risk_manager import RiskManager
from ..execution.settings_adapter import build_execution_settings
from ..execution.sl_tp_manager import SLTPManager
from ..features.feature_store import build_features
from ..infra.safety import assert_live_trading_enabled, stop_file_exists
from ..mt5.data_feed import stream_latest_candles
from ..mt5.mt5_client import MT5Client
from ..mt5.orders import send_order
from .risk import RiskState, check_limits
from ..backtest.engine import _dynamic_spread, _apply_slippage

logger = logging.getLogger(__name__)


def run_live_real(settings) -> None:
    assert_live_trading_enabled(settings.enable_live_trading, settings.live_confirm_key)
    if _use_v4_execution():
        try:
            return _run_live_real_v4(settings)
        except Exception as exc:
            logger.exception("Falha no motor V4 para live real, mantendo legado: %s", exc)
    return _run_live_real_legacy(settings)


def _use_v4_execution() -> bool:
    return os.getenv("USE_V4_EXECUTION", "true").strip().lower() in {"1", "true", "yes", "y"}


def _build_engine(settings, client: MT5Client) -> ExecutionEngine:
    engine_settings = build_execution_settings(settings)
    db_adapter = RepoAdapter(settings.db_path)
    fill_model = FillModel(engine_settings)
    position_tracker = PositionTracker(db_repo=db_adapter)
    risk_manager = RiskManager(engine_settings, db_repo=db_adapter)
    sltp_manager = SLTPManager(engine_settings)
    order_router = RouterMT5(
        mt5_client=client,
        fill_model=fill_model,
        position_tracker=position_tracker,
        db_repo=db_adapter,
    )
    return ExecutionEngine(
        mode=ExecutionMode.LIVE_REAL,
        order_router=order_router,
        risk_manager=risk_manager,
        sltp_manager=sltp_manager,
        position_tracker=position_tracker,
        fill_model=fill_model,
        db_repo=db_adapter,
        settings=engine_settings,
    )


def _build_engine_decision(symbol: str, decision, features) -> EngineDecision:
    brain_scores = {
        item.get("brain_id", ""): float(item.get("score", 0.0))
        for item in decision.metadata.get("signals", [])
        if item.get("brain_id")
    }
    if brain_scores:
        confidence = max(0.0, min(1.0, max(brain_scores.values()) / 100.0))
    else:
        confidence = 0.5

    if decision.action == "HOLD":
        return EngineDecision(
            action="SKIP",
            symbol=symbol,
            confidence=confidence,
            reason=decision.reason,
            brain_scores=brain_scores,
            regime=str(features.get("regime", "")),
        )

    return EngineDecision(
        action="ENTER",
        symbol=symbol,
        side=decision.action,
        volume=decision.size,
        entry_price=decision.entry,
        sl=decision.sl,
        tp=decision.tp1,
        confidence=confidence,
        reason=decision.reason,
        brain_scores=brain_scores,
        regime=str(features.get("regime", "")),
    )


def _run_live_real_v4(settings) -> None:
    client = MT5Client()
    if not client.ensure_connected() or not client.ensure_symbol(settings.symbol):
        return
    boss = BossBrain()
    engine = _build_engine(settings, client)
    for bundle in stream_latest_candles(client, settings.symbol, settings.timeframes):
        if stop_file_exists():
            break
        df = bundle.get(settings.timeframes[0])
        if df is None or df.empty:
            continue
        higher_df = bundle.get("H1") if isinstance(bundle, dict) else None
        features = build_features(df, round_step=settings.round_level_step, higher_df=higher_df)
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
        engine_decision = _build_engine_decision(settings.symbol, decision, features)
        current_price = float(df.iloc[-1]["close"])
        result = engine.execute(
            engine_decision,
            current_prices={settings.symbol: current_price},
            volatility_data={settings.symbol: float(features.get("atr", 0.0))},
        )
        if result.success:
            trade = {
                "symbol": settings.symbol,
                "opened_at": str(df.iloc[-1]["time"]),
                "closed_at": None,
                "side": decision.action,
                "entry": float(result.filled_price or decision.entry),
                "exit": None,
                "pnl": None,
                "mfe": None,
                "mae": None,
                "source": "live_v4",
                "payload": {
                    "order_status": result.order_status,
                    "reason": result.reason,
                    "risk_reason": result.risk_reason,
                },
            }
            repo.insert_trade(settings.db_path, trade)
        elif result.order_status and result.order_status != "SKIPPED":
            repo.insert_ui_event(
                settings.db_path,
                {
                    "timestamp": result.timestamp.isoformat(),
                    "type": "risk_event",
                    "payload": {"reason": result.reason, "risk": result.risk_reason},
                },
            )


def _run_live_real_legacy(settings) -> None:
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
        higher_df = bundle.get("H1") if isinstance(bundle, dict) else None
        features = build_features(df, round_step=settings.round_level_step, higher_df=higher_df)
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
