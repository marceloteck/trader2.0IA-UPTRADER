from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import uvicorn

from .config.settings import load_settings
from .db.connection import migrate
from .db.integrity import IntegrityChecker
from .db.backup import DatabaseBackup, LogRotator
from .infra.logger import setup_logging
from .mt5.mt5_client import MT5Client
from .backtest.engine import run_backtest
from .backtest.report import save_report
from .training.trainer import run_training
from .training.walk_forward import run_walk_forward
from .live.simulator import run_live_sim
from .live.runner import run_live_real
from .dashboard.api import app as dashboard_app
from .reports.daily_report import DailyReporter
from .reports.weekly_report import WeeklyReporter
from .version import get_build_info, mask_sensitive_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Brains MT5 V5")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")
    sub.add_parser("healthcheck")
    sub.add_parser("integrity-check")
    sub.add_parser("backup-db")
    sub.add_parser("maintenance")
    sub.add_parser("daily-report")
    sub.add_parser("weekly-report")

    backtest = sub.add_parser("backtest")
    backtest.add_argument("--from", dest="start", default=None)
    backtest.add_argument("--to", dest="end", default=None)
    backtest.add_argument("--months", type=int, default=3)

    train = sub.add_parser("train")
    train.add_argument("--replay", type=int, default=1)

    sub.add_parser("walk-forward")

    replay = sub.add_parser("replay-last")
    replay.add_argument("--n", type=int, default=20)

    export = sub.add_parser("export-audit")
    export.add_argument("--from", dest="start", default=None)
    export.add_argument("--to", dest="end", default=None)

    sub.add_parser("live-sim")
    sub.add_parser("live-real")
    sub.add_parser("dashboard")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    logger = setup_logging(settings.log_path)
    
    # Log version and build info
    if args.command in ["live-sim", "live-real", "backtest", "train"]:
        build_info = get_build_info({
            "symbol": settings.symbol,
            "risk_per_trade": settings.risk_per_trade,
            "live_mode": getattr(settings, "live_mode", "SIM")
        })
        logger.info(f"Version: {build_info.version} | Platform: {build_info.platform}")

    if args.command == "init-db":
        migrate(settings.db_path)
        logger.info("Database initialized")
        return

    if args.command == "healthcheck":
        _healthcheck(settings, logger)
        return
    
    if args.command == "integrity-check":
        _integrity_check(settings, logger)
        return
    
    if args.command == "backup-db":
        _backup_db(settings, logger)
        return
    
    if args.command == "maintenance":
        _maintenance(settings, logger)
        return
    
    if args.command == "daily-report":
        _daily_report(settings, logger)
        return
    
    if args.command == "weekly-report":
        _weekly_report(settings, logger)
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


def _healthcheck(settings, logger):
    """Run system health check."""
    logger.info("=== HEALTH CHECK START ===")
    
    # Check database
    try:
        from .db.connection import get_connection
        conn = get_connection(settings.db_path)
        conn.execute("SELECT 1")
        conn.close()
        logger.info("✅ Database: OK")
    except Exception as e:
        logger.error(f"❌ Database: FAIL - {e}")
        return
    
    # Check MT5
    client = MT5Client()
    if not client.ensure_connected():
        logger.error("❌ MT5: FAIL - Not connected")
        return
    logger.info("✅ MT5: Connected")
    
    # Check symbol
    if not client.ensure_symbol(settings.symbol):
        logger.error(f"❌ Symbol: FAIL - {settings.symbol} not available")
        return
    logger.info(f"✅ Symbol: {settings.symbol} available")
    
    logger.info("=== HEALTH CHECK END: OK ===")


def _integrity_check(settings, logger):
    """Check database integrity."""
    logger.info("Running integrity check...")
    checker = IntegrityChecker(settings.db_path)
    
    if checker.check():
        logger.info("✅ Integrity: OK")
        stats = checker.get_stats()
        logger.info(f"Stats: {stats}")
    else:
        logger.error("❌ Integrity: FAILED - recommend restore from backup")


def _backup_db(settings, logger):
    """Create database backup."""
    logger.info("Creating database backup...")
    backup = DatabaseBackup(settings.db_path, "./data/db/backups")
    backup_file = backup.backup()
    logger.info(f"✅ Backup created: {backup_file}")
    
    backups = backup.list_backups()
    logger.info(f"Available backups: {len(backups)}")
    for b in backups[-3:]:
        logger.info(f"  - {b['path']} ({b['size_mb']:.2f} MB)")


def _maintenance(settings, logger):
    """Run full maintenance: backup, vacuum, log rotation."""
    logger.info("=== MAINTENANCE START ===")
    
    # Backup
    backup = DatabaseBackup(settings.db_path, "./data/db/backups")
    backup.backup()
    logger.info("✅ Backup complete")
    
    # Vacuum
    checker = IntegrityChecker(settings.db_path)
    checker.vacuum()
    logger.info("✅ Vacuum complete")
    
    # Rotate logs
    log_dir = Path(settings.log_path).parent
    rotator = LogRotator(str(log_dir), keep_days=30, keep_mb=100)
    rotator.rotate()
    logger.info("✅ Log rotation complete")
    
    logger.info("=== MAINTENANCE END ===")


def _daily_report(settings, logger):
    """Generate daily report."""
    logger.info("Generating daily report...")
    reporter = DailyReporter(settings.db_path, "./data/exports/reports")
    report = reporter.generate()
    logger.info(f"✅ Daily report: {report['statistics']}")


def _weekly_report(settings, logger):
    """Generate weekly report."""
    logger.info("Generating weekly report...")
    reporter = WeeklyReporter(settings.db_path, "./data/exports/reports")
    report = reporter.generate()
    logger.info(f"✅ Weekly report: {report['summary']}")


if __name__ == "__main__":
    main()
