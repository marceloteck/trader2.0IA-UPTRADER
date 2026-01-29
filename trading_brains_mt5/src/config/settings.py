from __future__ import annotations

import os
import logging
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
    
    # V4 Execution Engine Settings
    live_mode: str  # SIM, REAL
    require_live_ok_file: bool
    live_ok_filename: str
    fallback_on_mt5_error: str  # PAUSE or SIM
    cooldown_seconds: int
    max_trades_per_hour: int
    daily_profit_target: float
    degrade_steps: int
    degrade_factor: float
    break_even_after_tp1: bool
    trailing_enabled: bool
    trailing_atr_mult: float
    stale_data_minutes: int
    mt5_reconnect_max_seconds: int
    fill_model_spread_base: float
    fill_model_spread_vol_mult: float
    fill_model_slippage_base: float
    fill_model_slippage_max: float
    use_partial_exits: bool
    
    # L1: Walk-Forward Anti-Leak
    wf_purge_candles: int
    wf_embargo_candles: int
    
    # L1: Cost Model
    cost_mode: str  # FIXO, POR_HORARIO, APRENDIDO
    cost_spread_base: float
    cost_slippage_base: float
    cost_slippage_max: float
    cost_commission: float
    
    # L1: Bad Day Filter
    bad_day_enabled: bool
    bad_day_first_n_trades: int
    bad_day_max_loss: float
    bad_day_min_winrate: float
    bad_day_consecutive_max: int
    
    # L1: Time Filter
    time_filter_enabled: bool
    time_filter_blocked_windows: str  # "HH:MM-HH:MM,..."
    time_filter_allow_only: str  # "HH:MM-HH:MM,..." (whitelist)
    
    # L1: Label Generation
    label_horizons: str  # "5,10,20"
    label_mfe_weight: float
    label_mae_weight: float
    
    # L2: Symbol/Asset Configuration
    primary_symbol: str
    symbols: str  # comma-separated list
    symbol_mode: str  # SINGLE or MULTI
    symbol_validate_on_start: bool
    symbol_auto_select: bool
    symbol_auto_select_method: str  # LIQUIDITY, VOLATILITY, SPREAD
    max_active_symbols: int
    
    # L2: Calibration
    calibration_enabled: bool
    calibration_method: str  # PLATT, ISOTONIC, NONE
    calibration_train_size: int
    
    # L2: Ensemble
    ensemble_enabled: bool
    ensemble_models: str  # LogisticRegression,RandomForest,GradientBoosting
    ensemble_voting: str  # SOFT, WEIGHTED
    ensemble_weights: str  # comma-separated or AUTO
    
    # L2: Conformal Prediction
    conformal_enabled: bool
    conformal_alpha: float  # error level (e.g., 0.1 = 90% coverage)
    
    # L2: Uncertainty Gates
    uncertainty_gate_enabled: bool
    max_model_disagreement: float
    max_proba_std: float
    min_global_confidence: float
    
    # L3: Regime Detection & Transitions
    regime_enabled: bool = True
    transition_enabled: bool = True
    
    # L4: LIQUIDITY PROFUNDA
    liquidity_enabled: bool = True
    liquidity_sources: str  # VWAP_DAILY,PIVOT_M5,WYCKOFF,ROUND,etc
    min_liquidity_strength: float  # 0-1, minimum zone strength to consider
    max_level_touches: int  # Max number of tests before level considered "spent"
    round_level_step: float  # Pip step for round number levels
    runner_enabled: bool  # Enable runner mode
    runner_min_confidence: float  # Min trend confidence for runner
    min_rr_ratio: float  # Minimum risk/reward for TP selection
    weak_liquidity_factor: float  # Risk adjustment when zones are weak
    transition_buffer_factor: float  # SL buffer multiplier during transitions
    zone_history_hours: int  # Keep zone data for N hours
    liquidity_learning_enabled: bool  # Learn zone behavior from trades
    liquidity_db_persist: bool  # Persist liquidity data to database
    
    # L5: REINFORCEMENT LEARNING + CAPITAL MANAGEMENT
    operator_capital_brl: float  # Operator's total capital in BRL
    margin_per_contract_brl: float  # Margin required per contract
    max_contracts_cap: int  # Absolute ceiling on contracts
    min_contracts: int  # Minimum contracts to trade (default 1)
    realavancagem_enabled: bool  # Enable controlled re-leveraging
    realavancagem_max_extra_contracts: int  # Max extra contracts beyond base
    realavancagem_mode: str  # SCALP_ONLY | HYBRID
    realavancagem_require_profit_today: bool  # Require daily profit to re-leverage
    realavancagem_min_profit_today_brl: float  # Minimum daily profit in BRL
    realavancagem_min_global_conf: float  # Min global confidence for re-leverage
    realavancagem_allowed_regimes: str  # Comma-separated regime whitelist
    realavancagem_forbidden_modes: str  # Comma-separated forbidden modes
    scalp_tp_points: int  # TP in points for scalp extra contracts
    scalp_sl_points: int  # SL in points for scalp extra contracts
    scalp_max_hold_seconds: int  # Max holding time for scalp
    protect_profit_after_scalp: bool  # Apply risk reduction after scalp win
    protect_profit_cooldown_seconds: int  # Cooldown after scalp
    contract_point_value: float  # Value per point per contract
    rl_policy_enabled: bool  # Enable RL policy gating
    rl_policy_mode: str  # THOMPSON_SAMPLING | QLEARNING
    rl_update_batch_size: int  # Trades to accumulate before policy update
    rl_freeze_threshold: float  # Performance loss before freezing updates
    
    # L6: MULTI-MARKET CORRELATION & NEWS FILTER
    crossmarket_enabled: bool  # Enable cross-market correlation monitoring
    cross_symbols: str  # Comma-separated cross-market symbols (e.g., WDO$N,IBOV)
    ibov_proxy_symbol: str  # IBOV proxy symbol for correlation (e.g., IBOV or mock)
    corr_windows: str  # Comma-separated correlation windows (e.g., 50,200)
    spread_window: int  # Rolling window for spread calculation
    z_threshold: float  # Z-score threshold for over-extension detection
    beta_window: int  # Rolling window for beta calculation (spread model)
    cross_guard_enabled: bool  # Enable correlation-based trade filtering
    cross_guard_min_corr: float  # Min correlation threshold (broken correlation band lower)
    cross_guard_max_corr: float  # Max correlation threshold (broken correlation band upper)
    cross_guard_reduce_confidence: bool  # Reduce confidence when correlation broken
    
    # L6: NEWS FILTER (Economic Calendar)
    news_enabled: bool  # Enable economic calendar filtering
    news_mode: str  # MANUAL | MT5_CALENDAR
    news_block_minutes_before: int  # Minutes to block trades before high-impact news
    news_block_minutes_after: int  # Minutes to block trades after high-impact news
    news_impact_block: str  # Impact level to block (HIGH | MEDIUM | LOW)
    news_reduce_risk_on_medium: bool  # Reduce position size on medium-impact news
    news_medium_risk_factor: float  # Risk reduction factor for medium-impact (0-1)
    
    # L8: OFFLINE TRAINING (Automatic Training When Market Closed)
    auto_offline_training: bool  # Enable automatic offline training
    stale_market_minutes: int  # Minutes without ticks/candles = market stale
    offline_training_mode: str  # REPLAY | WALK_FORWARD | MIXED
    offline_replay_rounds: int  # Number of replay rounds per session
    offline_wf_train_days: int  # Days in walk-forward train window
    offline_wf_test_days: int  # Days in walk-forward test window
    offline_max_minutes: int  # Max minutes per offline session (0 = unlimited)
    offline_cooldown_seconds: int  # Cooldown before checking market again


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
    
    # V4 Execution Engine
    "LIVE_MODE": "SIM",
    "REQUIRE_LIVE_OK_FILE": "true",
    "LIVE_OK_FILENAME": "LIVE_OK.txt",
    "FALLBACK_ON_MT5_ERROR": "PAUSE",
    "COOLDOWN_SECONDS": "180",
    "MAX_TRADES_PER_HOUR": "2",
    "DAILY_PROFIT_TARGET": "0",
    "DEGRADE_STEPS": "3",
    "DEGRADE_FACTOR": "0.5",
    "BREAK_EVEN_AFTER_TP1": "true",
    "TRAILING_ENABLED": "false",
    "TRAILING_ATR_MULT": "1.5",
    "STALE_DATA_MINUTES": "3",
    "MT5_RECONNECT_MAX_SECONDS": "60",
    "FILL_MODEL_SPREAD_BASE": "1.0",
    "FILL_MODEL_SPREAD_VOL_MULT": "0.5",
    "FILL_MODEL_SLIPPAGE_BASE": "0.0",
    "FILL_MODEL_SLIPPAGE_MAX": "2.0",
    "USE_PARTIAL_EXITS": "false",
    
    # L1: Walk-Forward Anti-Leak
    "WF_PURGE_CANDLES": "50",
    "WF_EMBARGO_CANDLES": "50",
    
    # L1: Cost Model
    "COST_MODE": "FIXO",
    "COST_SPREAD_BASE": "1.0",
    "COST_SLIPPAGE_BASE": "0.5",
    "COST_SLIPPAGE_MAX": "2.0",
    "COST_COMMISSION": "0.0",
    
    # L1: Bad Day Filter
    "BAD_DAY_ENABLED": "true",
    "BAD_DAY_FIRST_N_TRADES": "5",
    "BAD_DAY_MAX_LOSS": "-100.0",
    "BAD_DAY_MIN_WINRATE": "0.4",
    "BAD_DAY_CONSECUTIVE_MAX": "3",
    
    # L1: Time Filter
    "TIME_FILTER_ENABLED": "false",
    "TIME_FILTER_BLOCKED_WINDOWS": "",
    "TIME_FILTER_ALLOW_ONLY": "",
    
    # L1: Label Generation
    "LABEL_HORIZONS": "5,10,20",
    "LABEL_MFE_WEIGHT": "1.0",
    "LABEL_MAE_WEIGHT": "0.5",
    
    # L2: Symbol Configuration
    "PRIMARY_SYMBOL": "WIN$N",
    "SYMBOLS": "WIN$N",
    "SYMBOL_MODE": "SINGLE",
    "SYMBOL_VALIDATE_ON_START": "true",
    "SYMBOL_AUTO_SELECT": "false",
    "SYMBOL_AUTO_SELECT_METHOD": "LIQUIDITY",
    "MAX_ACTIVE_SYMBOLS": "1",
    
    # L2: Calibration
    "CALIBRATION_ENABLED": "true",
    "CALIBRATION_METHOD": "PLATT",
    "CALIBRATION_TRAIN_SIZE": "500",
    
    # L2: Ensemble
    "ENSEMBLE_ENABLED": "true",
    "ENSEMBLE_MODELS": "LogisticRegression,RandomForest,GradientBoosting",
    "ENSEMBLE_VOTING": "SOFT",
    "ENSEMBLE_WEIGHTS": "AUTO",
    
    # L2: Conformal Prediction
    "CONFORMAL_ENABLED": "true",
    "CONFORMAL_ALPHA": "0.1",
    
    # L2: Uncertainty Gates
    "UNCERTAINTY_GATE_ENABLED": "true",
    "MAX_MODEL_DISAGREEMENT": "0.25",
    "MAX_PROBA_STD": "0.15",
    "MIN_GLOBAL_CONFIDENCE": "0.55",
    
    # L3: Regime Detection
    "REGIME_ENABLED": "true",
    "TRANSITION_ENABLED": "true",
    
    # L4: LIQUIDITY PROFUNDA
    "LIQUIDITY_ENABLED": "true",
    "LIQUIDITY_SOURCES": "VWAP_DAILY,VWAP_WEEKLY,PIVOT_M5,PIVOT_M15,HIGH_DAILY,LOW_DAILY,WYCKOFF,CLUSTER,ROUND,PREVIOUS_CLOSE",
    "MIN_LIQUIDITY_STRENGTH": "0.60",
    "MAX_LEVEL_TOUCHES": "10",
    "RUNNER_ENABLED": "true",
    "RUNNER_MIN_CONFIDENCE": "0.65",
    "MIN_RR_RATIO": "1.5",
    "WEAK_LIQUIDITY_FACTOR": "0.80",
    "TRANSITION_BUFFER_FACTOR": "1.5",
    "ZONE_HISTORY_HOURS": "24",
    "LIQUIDITY_LEARNING_ENABLED": "true",
    "LIQUIDITY_DB_PERSIST": "true",
    
    # L5: REINFORCEMENT LEARNING + CAPITAL MANAGEMENT
    "OPERATOR_CAPITAL_BRL": "10000",
    "MARGIN_PER_CONTRACT_BRL": "1000",
    "MAX_CONTRACTS_CAP": "10",
    "MIN_CONTRACTS": "1",
    "REALAVANCAGEM_ENABLED": "true",
    "REALAVANCAGEM_MAX_EXTRA_CONTRACTS": "1",
    "REALAVANCAGEM_MODE": "SCALP_ONLY",
    "REALAVANCAGEM_REQUIRE_PROFIT_TODAY": "true",
    "REALAVANCAGEM_MIN_PROFIT_TODAY_BRL": "50",
    "REALAVANCAGEM_MIN_GLOBAL_CONF": "0.70",
    "REALAVANCAGEM_ALLOWED_REGIMES": "TREND_UP,TREND_DOWN",
    "REALAVANCAGEM_FORBIDDEN_MODES": "TRANSITION,CHAOTIC",
    "SCALP_TP_POINTS": "80",
    "SCALP_SL_POINTS": "40",
    "SCALP_MAX_HOLD_SECONDS": "180",
    "PROTECT_PROFIT_AFTER_SCALP": "true",
    "PROTECT_PROFIT_COOLDOWN_SECONDS": "300",
    "CONTRACT_POINT_VALUE": "1.0",
    "RL_POLICY_ENABLED": "true",
    "RL_POLICY_MODE": "THOMPSON_SAMPLING",
    "RL_UPDATE_BATCH_SIZE": "10",
    "RL_FREEZE_THRESHOLD": "0.15",
    
    # L6: MULTI-MARKET CORRELATION & NEWS FILTER
    "CROSSMARKET_ENABLED": "true",
    "CROSS_SYMBOLS": "WDO$N,IBOV",
    "IBOV_PROXY_SYMBOL": "IBOV",
    "CORR_WINDOWS": "50,200",
    "SPREAD_WINDOW": "200",
    "Z_THRESHOLD": "2.0",
    "BETA_WINDOW": "200",
    "CROSS_GUARD_ENABLED": "true",
    "CROSS_GUARD_MIN_CORR": "-0.2",
    "CROSS_GUARD_MAX_CORR": "0.2",
    "CROSS_GUARD_REDUCE_CONFIDENCE": "true",
    
    # L6: NEWS FILTER
    "NEWS_ENABLED": "true",
    "NEWS_MODE": "MANUAL",
    "NEWS_BLOCK_MINUTES_BEFORE": "10",
    "NEWS_BLOCK_MINUTES_AFTER": "10",
    "NEWS_IMPACT_BLOCK": "HIGH",
    "NEWS_REDUCE_RISK_ON_MEDIUM": "true",
    "NEWS_MEDIUM_RISK_FACTOR": "0.5",
    
    # L8: Offline Training
    "AUTO_OFFLINE_TRAINING": "false",
    "STALE_MARKET_MINUTES": "3",
    "OFFLINE_TRAINING_MODE": "REPLAY",
    "OFFLINE_REPLAY_ROUNDS": "5",
    "OFFLINE_WF_TRAIN_DAYS": "60",
    "OFFLINE_WF_TEST_DAYS": "15",
    "OFFLINE_MAX_MINUTES": "480",
    "OFFLINE_COOLDOWN_SECONDS": "30",
}


def _get_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_settings() -> Settings:
    load_dotenv()
    logger = logging.getLogger(__name__)

    def get_env(key: str) -> str:
        return os.getenv(key, _DEF[key])

    timeframes = [tf.strip() for tf in get_env("TIMEFRAMES").split(",") if tf.strip()]
    if not timeframes:
        timeframes = DEFAULT_TIMEFRAMES

    enable_live_trading = _get_bool(get_env("ENABLE_LIVE_TRADING"))
    live_confirm_key = get_env("LIVE_CONFIRM_KEY")
    live_mode = get_env("LIVE_MODE")
    require_live_ok_file = _get_bool(get_env("REQUIRE_LIVE_OK_FILE"))
    live_ok_filename = get_env("LIVE_OK_FILENAME")

    if not enable_live_trading:
        logger.warning("======================================================")
        logger.warning("============== MODO REAL DESABILITADO ================")
        logger.warning("======================================================")
        live_mode = "SIM"

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
        enable_live_trading=enable_live_trading,
        live_confirm_key=live_confirm_key,
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
        
        # V4
        live_mode=live_mode,
        require_live_ok_file=require_live_ok_file,
        live_ok_filename=live_ok_filename,
        fallback_on_mt5_error=get_env("FALLBACK_ON_MT5_ERROR"),
        cooldown_seconds=int(get_env("COOLDOWN_SECONDS")),
        max_trades_per_hour=int(get_env("MAX_TRADES_PER_HOUR")),
        daily_profit_target=float(get_env("DAILY_PROFIT_TARGET")),
        degrade_steps=int(get_env("DEGRADE_STEPS")),
        degrade_factor=float(get_env("DEGRADE_FACTOR")),
        break_even_after_tp1=_get_bool(get_env("BREAK_EVEN_AFTER_TP1")),
        trailing_enabled=_get_bool(get_env("TRAILING_ENABLED")),
        trailing_atr_mult=float(get_env("TRAILING_ATR_MULT")),
        stale_data_minutes=int(get_env("STALE_DATA_MINUTES")),
        mt5_reconnect_max_seconds=int(get_env("MT5_RECONNECT_MAX_SECONDS")),
        fill_model_spread_base=float(get_env("FILL_MODEL_SPREAD_BASE")),
        fill_model_spread_vol_mult=float(get_env("FILL_MODEL_SPREAD_VOL_MULT")),
        fill_model_slippage_base=float(get_env("FILL_MODEL_SLIPPAGE_BASE")),
        fill_model_slippage_max=float(get_env("FILL_MODEL_SLIPPAGE_MAX")),
        use_partial_exits=_get_bool(get_env("USE_PARTIAL_EXITS")),
        
        # L1
        wf_purge_candles=int(get_env("WF_PURGE_CANDLES")),
        wf_embargo_candles=int(get_env("WF_EMBARGO_CANDLES")),
        cost_mode=get_env("COST_MODE"),
        cost_spread_base=float(get_env("COST_SPREAD_BASE")),
        cost_slippage_base=float(get_env("COST_SLIPPAGE_BASE")),
        cost_slippage_max=float(get_env("COST_SLIPPAGE_MAX")),
        cost_commission=float(get_env("COST_COMMISSION")),
        bad_day_enabled=_get_bool(get_env("BAD_DAY_ENABLED")),
        bad_day_first_n_trades=int(get_env("BAD_DAY_FIRST_N_TRADES")),
        bad_day_max_loss=float(get_env("BAD_DAY_MAX_LOSS")),
        bad_day_min_winrate=float(get_env("BAD_DAY_MIN_WINRATE")),
        bad_day_consecutive_max=int(get_env("BAD_DAY_CONSECUTIVE_MAX")),
        time_filter_enabled=_get_bool(get_env("TIME_FILTER_ENABLED")),
        time_filter_blocked_windows=get_env("TIME_FILTER_BLOCKED_WINDOWS"),
        time_filter_allow_only=get_env("TIME_FILTER_ALLOW_ONLY"),
        label_horizons=get_env("LABEL_HORIZONS"),
        label_mfe_weight=float(get_env("LABEL_MFE_WEIGHT")),
        label_mae_weight=float(get_env("LABEL_MAE_WEIGHT")),
        
        # L2
        primary_symbol=get_env("PRIMARY_SYMBOL"),
        symbols=get_env("SYMBOLS"),
        symbol_mode=get_env("SYMBOL_MODE"),
        symbol_validate_on_start=_get_bool(get_env("SYMBOL_VALIDATE_ON_START")),
        symbol_auto_select=_get_bool(get_env("SYMBOL_AUTO_SELECT")),
        symbol_auto_select_method=get_env("SYMBOL_AUTO_SELECT_METHOD"),
        max_active_symbols=int(get_env("MAX_ACTIVE_SYMBOLS")),
        calibration_enabled=_get_bool(get_env("CALIBRATION_ENABLED")),
        calibration_method=get_env("CALIBRATION_METHOD"),
        calibration_train_size=int(get_env("CALIBRATION_TRAIN_SIZE")),
        ensemble_enabled=_get_bool(get_env("ENSEMBLE_ENABLED")),
        ensemble_models=get_env("ENSEMBLE_MODELS"),
        ensemble_voting=get_env("ENSEMBLE_VOTING"),
        ensemble_weights=get_env("ENSEMBLE_WEIGHTS"),
        conformal_enabled=_get_bool(get_env("CONFORMAL_ENABLED")),
        conformal_alpha=float(get_env("CONFORMAL_ALPHA")),
        uncertainty_gate_enabled=_get_bool(get_env("UNCERTAINTY_GATE_ENABLED")),
        max_model_disagreement=float(get_env("MAX_MODEL_DISAGREEMENT")),
        max_proba_std=float(get_env("MAX_PROBA_STD")),
        min_global_confidence=float(get_env("MIN_GLOBAL_CONFIDENCE")),
        
        # L3
        regime_enabled=_get_bool(get_env("REGIME_ENABLED")),
        transition_enabled=_get_bool(get_env("TRANSITION_ENABLED")),
        
        # L4
        liquidity_enabled=_get_bool(get_env("LIQUIDITY_ENABLED")),
        liquidity_sources=get_env("LIQUIDITY_SOURCES"),
        min_liquidity_strength=float(get_env("MIN_LIQUIDITY_STRENGTH")),
        max_level_touches=int(get_env("MAX_LEVEL_TOUCHES")),
        runner_enabled=_get_bool(get_env("RUNNER_ENABLED")),
        runner_min_confidence=float(get_env("RUNNER_MIN_CONFIDENCE")),
        min_rr_ratio=float(get_env("MIN_RR_RATIO")),
        weak_liquidity_factor=float(get_env("WEAK_LIQUIDITY_FACTOR")),
        transition_buffer_factor=float(get_env("TRANSITION_BUFFER_FACTOR")),
        zone_history_hours=int(get_env("ZONE_HISTORY_HOURS")),
        liquidity_learning_enabled=_get_bool(get_env("LIQUIDITY_LEARNING_ENABLED")),
        liquidity_db_persist=_get_bool(get_env("LIQUIDITY_DB_PERSIST")),
        
        # L5
        operator_capital_brl=float(get_env("OPERATOR_CAPITAL_BRL")),
        margin_per_contract_brl=float(get_env("MARGIN_PER_CONTRACT_BRL")),
        max_contracts_cap=int(get_env("MAX_CONTRACTS_CAP")),
        min_contracts=int(get_env("MIN_CONTRACTS")),
        realavancagem_enabled=_get_bool(get_env("REALAVANCAGEM_ENABLED")),
        realavancagem_max_extra_contracts=int(get_env("REALAVANCAGEM_MAX_EXTRA_CONTRACTS")),
        realavancagem_mode=get_env("REALAVANCAGEM_MODE"),
        realavancagem_require_profit_today=_get_bool(get_env("REALAVANCAGEM_REQUIRE_PROFIT_TODAY")),
        realavancagem_min_profit_today_brl=float(get_env("REALAVANCAGEM_MIN_PROFIT_TODAY_BRL")),
        realavancagem_min_global_conf=float(get_env("REALAVANCAGEM_MIN_GLOBAL_CONF")),
        realavancagem_allowed_regimes=get_env("REALAVANCAGEM_ALLOWED_REGIMES"),
        realavancagem_forbidden_modes=get_env("REALAVANCAGEM_FORBIDDEN_MODES"),
        scalp_tp_points=int(get_env("SCALP_TP_POINTS")),
        scalp_sl_points=int(get_env("SCALP_SL_POINTS")),
        scalp_max_hold_seconds=int(get_env("SCALP_MAX_HOLD_SECONDS")),
        protect_profit_after_scalp=_get_bool(get_env("PROTECT_PROFIT_AFTER_SCALP")),
        protect_profit_cooldown_seconds=int(get_env("PROTECT_PROFIT_COOLDOWN_SECONDS")),
        contract_point_value=float(get_env("CONTRACT_POINT_VALUE")),
        rl_policy_enabled=_get_bool(get_env("RL_POLICY_ENABLED")),
        rl_policy_mode=get_env("RL_POLICY_MODE"),
        rl_update_batch_size=int(get_env("RL_UPDATE_BATCH_SIZE")),
        rl_freeze_threshold=float(get_env("RL_FREEZE_THRESHOLD")),
        
        # L6
        crossmarket_enabled=_get_bool(get_env("CROSSMARKET_ENABLED")),
        cross_symbols=get_env("CROSS_SYMBOLS"),
        ibov_proxy_symbol=get_env("IBOV_PROXY_SYMBOL"),
        corr_windows=get_env("CORR_WINDOWS"),
        spread_window=int(get_env("SPREAD_WINDOW")),
        z_threshold=float(get_env("Z_THRESHOLD")),
        beta_window=int(get_env("BETA_WINDOW")),
        cross_guard_enabled=_get_bool(get_env("CROSS_GUARD_ENABLED")),
        cross_guard_min_corr=float(get_env("CROSS_GUARD_MIN_CORR")),
        cross_guard_max_corr=float(get_env("CROSS_GUARD_MAX_CORR")),
        cross_guard_reduce_confidence=_get_bool(get_env("CROSS_GUARD_REDUCE_CONFIDENCE")),
        news_enabled=_get_bool(get_env("NEWS_ENABLED")),
        news_mode=get_env("NEWS_MODE"),
        news_block_minutes_before=int(get_env("NEWS_BLOCK_MINUTES_BEFORE")),
        news_block_minutes_after=int(get_env("NEWS_BLOCK_MINUTES_AFTER")),
        news_impact_block=get_env("NEWS_IMPACT_BLOCK"),
        news_reduce_risk_on_medium=_get_bool(get_env("NEWS_REDUCE_RISK_ON_MEDIUM")),
        news_medium_risk_factor=float(get_env("NEWS_MEDIUM_RISK_FACTOR")),
        
        # L8
        auto_offline_training=_get_bool(get_env("AUTO_OFFLINE_TRAINING")),
        stale_market_minutes=int(get_env("STALE_MARKET_MINUTES")),
        offline_training_mode=get_env("OFFLINE_TRAINING_MODE"),
        offline_replay_rounds=int(get_env("OFFLINE_REPLAY_ROUNDS")),
        offline_wf_train_days=int(get_env("OFFLINE_WF_TRAIN_DAYS")),
        offline_wf_test_days=int(get_env("OFFLINE_WF_TEST_DAYS")),
        offline_max_minutes=int(get_env("OFFLINE_MAX_MINUTES")),
        offline_cooldown_seconds=int(get_env("OFFLINE_COOLDOWN_SECONDS")),
    )
