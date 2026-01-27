from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn

from .config.settings import load_settings
from .db.connection import migrate
from .infra.logger import setup_logging
from .mt5.mt5_client import MT5Client
from .backtest.engine import run_backtest
from .backtest.report import save_report
from .training.trainer import run_training
from .training.walk_forward import run_walk_forward
from .live.simulator import run_live_sim
from .live.runner import run_live_real
from .dashboard.api import app as dashboard_app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Brains MT5")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")

    backtest = sub.add_parser("backtest")
    backtest.add_argument("--from", dest="start", default=None)
    backtest.add_argument("--to", dest="end", default=None)
    backtest.add_argument("--months", type=int, default=3)

    train = sub.add_parser("train")
    train.add_argument("--replay", type=int, default=1)

    sub.add_parser("walk-forward")

    sub.add_parser("live-sim")
    sub.add_parser("live-real")
    sub.add_parser("dashboard")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    logger = setup_logging(settings.log_path)

    if args.command == "init-db":
        migrate(settings.db_path)
        logger.info("Database initialized")
        return

    if args.command == "backtest":
        client = MT5Client()
        if not client.ensure_connected() or not client.ensure_symbol(settings.symbol):
            logger.error("MT5 not connected or symbol not available")
            return
        end = datetime.utcnow() if args.end is None else datetime.fromisoformat(args.end)
        if args.start:
            start = datetime.fromisoformat(args.start)
        else:
            start = end - timedelta(days=30 * args.months)
        df = client.fetch_rates(settings.symbol, settings.timeframes[0], start, end)
        if df.empty:
            logger.error("No data for backtest")
            return
        result = run_backtest(
            settings.symbol,
            df,
            settings.db_path,
            settings.spread_max,
            settings.slippage,
            settings.risk_per_trade,
            settings.point_value,
            settings.min_lot,
            settings.lot_step,
            settings.round_level_step,
        )
        metrics = save_report(result.trades, result.pnls, "./data/exports/reports")
        logger.info("Backtest finished: %s", metrics)
        return

    if args.command == "train":
        metrics = run_training(settings, replay=args.replay)
        logger.info("Training finished: %s", metrics)
        return

    if args.command == "walk-forward":
        metrics = run_walk_forward(settings)
        logger.info("Walk-forward finished: %s", metrics)
        return

    if args.command == "live-sim":
        logger.info("Starting live simulation")
        run_live_sim(settings)
        return

    if args.command == "live-real":
        logger.info("Starting live trading")
        run_live_real(settings)
        return

    if args.command == "dashboard":
        web_dir = Path(__file__).parent / "dashboard" / "web"
        if web_dir.exists():
            from fastapi.staticfiles import StaticFiles

            dashboard_app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
        uvicorn.run(dashboard_app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
