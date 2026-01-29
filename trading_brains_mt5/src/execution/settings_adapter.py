from __future__ import annotations

from typing import Dict

from ..config.settings import Settings


def build_execution_settings(settings: Settings) -> Dict[str, object]:
    """Converte Settings para o formato esperado pelo motor V4."""
    return {
        "DB_PATH": settings.db_path,
        "DAILY_LOSS_LIMIT": settings.daily_loss_limit,
        "DAILY_PROFIT_TARGET": settings.daily_profit_target,
        "MAX_TRADES_PER_DAY": settings.max_trades_per_day,
        "MAX_TRADES_PER_HOUR": settings.max_trades_per_hour,
        "MAX_CONSECUTIVE_LOSSES": settings.max_consec_losses,
        "COOLDOWN_SECONDS": settings.cooldown_seconds,
        "DEGRADE_STEPS": settings.degrade_steps,
        "DEGRADE_FACTOR": settings.degrade_factor,
        "USE_PARTIAL_EXITS": settings.use_partial_exits,
        "BREAK_EVEN_AFTER_TP1": settings.break_even_after_tp1,
        "TRAILING_ENABLED": settings.trailing_enabled,
        "TRAILING_ATR_MULT": settings.trailing_atr_mult,
        "FILL_MODEL_SPREAD_BASE": settings.fill_model_spread_base,
        "FILL_MODEL_SPREAD_VOL_MULT": settings.fill_model_spread_vol_mult,
        "FILL_MODEL_SLIPPAGE_BASE": settings.fill_model_slippage_base,
        "FILL_MODEL_SLIPPAGE_MAX": settings.fill_model_slippage_max,
        "LIVE_MODE": settings.live_mode,
        "ENABLE_LIVE_TRADING": settings.enable_live_trading,
        "LIVE_CONFIRM_KEY": settings.live_confirm_key,
        "REQUIRE_LIVE_OK_FILE": settings.require_live_ok_file,
        "LIVE_OK_FILENAME": settings.live_ok_filename,
    }
