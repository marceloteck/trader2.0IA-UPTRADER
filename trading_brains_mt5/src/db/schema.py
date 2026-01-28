from __future__ import annotations

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            notes TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            time TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            tick_volume REAL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            time TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            brain_id TEXT NOT NULL,
            signal TEXT NOT NULL,
            score REAL NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            side TEXT NOT NULL,
            entry REAL NOT NULL,
            exit REAL,
            pnl REAL,
            mfe REAL,
            mae REAL,
            source TEXT NOT NULL,
            payload TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metrics TEXT NOT NULL,
            path TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS training_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            last_time TEXT NOT NULL,
            state TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            source TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_windows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            window_id INTEGER NOT NULL,
            metrics_json TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS regimes_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            regime TEXT NOT NULL,
            payload TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            regime TEXT NOT NULL,
            hour_bucket TEXT NOT NULL,
            threshold REAL NOT NULL,
            payload TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            action TEXT NOT NULL,
            retcode INTEGER,
            message TEXT,
            payload TEXT
        )
        """
    )
    
    # V3 Tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS brain_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brain_id TEXT NOT NULL,
            regime TEXT NOT NULL,
            win_rate REAL,
            profit_factor REAL,
            avg_rr REAL,
            total_trades INTEGER,
            total_pnl REAL,
            max_drawdown REAL,
            confidence REAL,
            last_update TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regime TEXT NOT NULL,
            allow_trading INTEGER,
            weight_adjustment TEXT,
            global_confidence REAL,
            reasoning TEXT,
            risk_level TEXT,
            timestamp TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS regime_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_regime TEXT NOT NULL,
            to_regime TEXT NOT NULL,
            from_duration INTEGER,
            from_volatility REAL,
            to_volatility REAL,
            timestamp TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reinforcement_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regime TEXT NOT NULL,
            hour_bucket INTEGER,
            state_hash TEXT,
            q_value REAL,
            visit_count INTEGER,
            last_update TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS replay_priority (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            priority_score REAL,
            loss_magnitude REAL,
            regime TEXT,
            last_updated TEXT
        )
        """
    )
    
    # V4 Execution Engine Tables
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticket INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            volume REAL,
            entry_price REAL,
            filled_price REAL,
            filled_volume REAL,
            status TEXT,
            sl REAL,
            tp REAL,
            reason TEXT,
            retcode INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mt5_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT,
            message TEXT,
            details TEXT,
            severity TEXT DEFAULT 'INFO'
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            action TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            trace_json TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS position_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket INTEGER UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            volume REAL,
            entry_price REAL,
            open_time TEXT,
            sl REAL,
            tp REAL,
            status TEXT,
            close_price REAL,
            close_time TEXT,
            current_price REAL,
            pnl REAL,
            pnl_percent REAL,
            comment TEXT,
            magic INTEGER,
            last_update TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticket INTEGER,
            symbol TEXT,
            action TEXT,
            success BOOLEAN,
            filled_price REAL,
            slippage REAL,
            order_status TEXT,
            risk_passed BOOLEAN,
            risk_reason TEXT,
            pnl REAL,
            reason TEXT
        )
        """
    )
    
    # L1: Walk-Forward tracking (purge+embargo)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS wf_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            split_id INTEGER NOT NULL,
            train_from TEXT NOT NULL,
            train_to TEXT NOT NULL,
            test_from TEXT NOT NULL,
            test_to TEXT NOT NULL,
            purge_candles INTEGER DEFAULT 50,
            embargo_candles INTEGER DEFAULT 50,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, split_id)
        )
        """
    )
    
    # L1: Cost tracking (spread, slippage, commission by mode)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_events (
            timestamp TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            mode TEXT NOT NULL,
            spread REAL NOT NULL,
            slippage REAL NOT NULL,
            commission REAL NOT NULL,
            volatility REAL DEFAULT 1.0,
            details TEXT
        )
        """
    )
    
    # L1: Bad day filter events
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bad_day_events (
            timestamp TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            daily_pnl REAL,
            trades_count INTEGER,
            consecutive_losses INTEGER,
            paused_until TEXT,
            details TEXT
        )
        """
    )
    
    # L1: Time filter hits
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS time_filter_hits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            window TEXT,
            UNIQUE(timestamp, action)
        )
        """
    )
    
    # L1: Multi-horizon training labels
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            tp1 REAL,
            tp2 REAL,
            sl REAL,
            horizon INTEGER NOT NULL,
            tp1_hit BOOLEAN,
            tp2_hit BOOLEAN,
            mfe REAL,
            mae REAL,
            quality_score REAL,
            details TEXT,
            UNIQUE(timestamp, symbol, horizon)
        )
        """
    )
    
    # L1: Report insights (regime, hour, brain performance)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS report_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            insight_type TEXT NOT NULL,
            subject TEXT,
            metric_name TEXT,
            metric_value REAL,
            details TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    
    # L2: Symbol configuration and management
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS symbols_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            mode TEXT NOT NULL,
            symbols_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    
    # L2: Symbol health tracking (spread, latency, volatility)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            ok BOOLEAN NOT NULL,
            spread REAL,
            latency_ms REAL,
            tick_volume REAL,
            volatility REAL,
            details_json TEXT
        )
        """
    )
    
    # L2: Symbol selection log (which symbols were selected and when)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_selection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            method TEXT NOT NULL,
            selected_symbols_json TEXT NOT NULL
        )
        """
    )
    
    # L2: Probability calibration configuration and metrics
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS model_calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            brain_id TEXT NOT NULL,
            method TEXT NOT NULL,
            calibration_sample_size INTEGER,
            metrics_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(model_id, brain_id, method)
        )
        """
    )
    
    # L2: Ensemble voting metrics (per-prediction analysis)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ensemble_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            time TEXT NOT NULL,
            brain_id TEXT NOT NULL,
            regime TEXT,
            prediction INTEGER,
            proba_mean REAL,
            proba_std REAL,
            disagreement_score REAL,
            individual_probas_json TEXT,
            metrics_json TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    
    # L2: Uncertainty gate events (when gate blocks a trade)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            gate_type TEXT NOT NULL,
            decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            values_json TEXT NOT NULL
        )
        """
    )
    
    # L2: Calibration report logs (daily/weekly calibration metrics)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            brain_id TEXT,
            method TEXT,
            expected_calibration_error REAL,
            max_calibration_error REAL,
            brier_score REAL,
            num_predictions INTEGER,
            reliability_diagram_json TEXT,
            metrics_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    
    # L3: Regime change detection events
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS regime_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            detector TEXT NOT NULL,
            change_detected BOOLEAN,
            strength REAL,
            metric_changed TEXT,
            cusum_details_json TEXT,
            bocpd_details_json TEXT,
            combined_strength REAL,
            confidence REAL,
            details_json TEXT NOT NULL
        )
        """
    )
    
    # L3: Regime transition events
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS regime_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            from_regime TEXT NOT NULL,
            to_regime TEXT NOT NULL,
            confidence REAL,
            reasons_json TEXT,
            duration_minutes INTEGER,
            is_valid_transition BOOLEAN
        )
        """
    )
    
    # L3: Brain performance per transition
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transition_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brain_id TEXT NOT NULL,
            from_regime TEXT NOT NULL,
            to_regime TEXT NOT NULL,
            trade_count INTEGER,
            win_count INTEGER,
            winrate REAL,
            profit_factor REAL,
            avg_pnl REAL,
            max_dd REAL,
            quality_score REAL,
            total_pnl REAL,
            last_updated TEXT
        )
        """
    )
    
    # L3: Meta brain mode tracking
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_mode_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            mode TEXT NOT NULL,
            reason TEXT,
            details_json TEXT
        )
        """
    )
    
    # L3: Risk adjustments
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            original_risk REAL,
            adjusted_risk REAL,
            risk_factor REAL,
            reason TEXT,
            regime TEXT,
            transition_strength REAL,
            ensemble_uncertainty REAL,
            recent_drawdown REAL
        )
        """
    )
    
    # L3: Blocked signals (when brain signal is incompatible with regime)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS blocked_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            brain_id TEXT NOT NULL,
            signal TEXT,
            current_regime TEXT,
            block_reason TEXT,
            detail_json TEXT
        )
        """
    )
    
    # ========================
    # L4: LIQUIDITY MAPPING & LEARNING
    # ========================
    
    # L4: Liquidity levels (zones from various sources)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidity_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price_center REAL NOT NULL,
            price_min REAL NOT NULL,
            price_max REAL NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_tested TEXT,
            touch_count INTEGER DEFAULT 0,
            hold_count INTEGER DEFAULT 0,
            break_count INTEGER DEFAULT 0,
            sweep_count INTEGER DEFAULT 0,
            strength_score REAL DEFAULT 0.5,
            prob_hold REAL DEFAULT 0.5,
            prob_break REAL DEFAULT 0.5,
            last_updated TEXT
        )
        """
    )
    
    # L4: Level behavior statistics (aggregate statistics per level)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidity_level_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            level_id INTEGER NOT NULL,
            price_level REAL NOT NULL,
            action TEXT NOT NULL,  -- 'held', 'broken', 'swept', 'touched'
            count INTEGER DEFAULT 0,
            pnl_sum REAL DEFAULT 0,
            pnl_avg REAL DEFAULT 0,
            pnl_max REAL DEFAULT 0,
            pnl_min REAL DEFAULT 0,
            confidence REAL DEFAULT 0.5,
            last_updated TEXT,
            FOREIGN KEY (level_id) REFERENCES liquidity_levels(id)
        )
        """
    )
    
    # L4: Target selections (take profit levels selected)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS target_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            tp1_price REAL,
            tp2_price REAL,
            runner_enabled INTEGER DEFAULT 0,
            tp1_strength REAL,
            tp2_strength REAL,
            rr_ratio REAL,
            tp1_qty_percent REAL DEFAULT 0.5,
            tp2_qty_percent REAL DEFAULT 0.3,
            runner_qty_percent REAL DEFAULT 0.2,
            selection_reason TEXT,
            detail_json TEXT
        )
        """
    )
    
    # L4: Stop loss decisions (stop placement logic)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stop_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_price REAL NOT NULL,
            zone_id INTEGER,
            zone_strength REAL,
            buffer_pips REAL,
            distance_pips REAL,
            adjusted_for_transition INTEGER DEFAULT 0,
            selection_reason TEXT,
            detail_json TEXT,
            FOREIGN KEY (zone_id) REFERENCES liquidity_levels(id)
        )
        """
    )
    
    # L4: Liquidity-aware trade tracking
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidity_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            side TEXT NOT NULL,
            tp1_price REAL,
            tp2_price REAL,
            runner_enabled INTEGER DEFAULT 0,
            tp1_hit INTEGER DEFAULT 0,
            tp2_hit INTEGER DEFAULT 0,
            runner_hit INTEGER DEFAULT 0,
            stop_price REAL,
            stop_hit INTEGER DEFAULT 0,
            pnl REAL,
            pnl_percent REAL,
            mfe REAL,
            mae REAL,
            zones_involved_json TEXT,  -- JSON list of zone IDs that were relevant
            last_updated TEXT
        )
        """
    )
    
    # L4: Runner events (when runner mode is activated)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runner_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            trade_id INTEGER NOT NULL,
            tp1_hit_price REAL NOT NULL,
            runner_activated INTEGER DEFAULT 1,
            runner_zones_ahead INTEGER DEFAULT 0,
            runner_trend_score REAL,
            avg_zone_strength REAL,
            pnl_from_runner REAL,
            runner_closed_at_price REAL,
            detail_json TEXT
        )
        """
    )
    
    # L4: Liquidity reports (daily/weekly summaries)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS liquidity_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            total_zones INTEGER,
            strong_zones INTEGER,
            medium_zones INTEGER,
            weak_zones INTEGER,
            zones_tested INTEGER,
            zones_held_count INTEGER,
            zones_broken_count INTEGER,
            zones_swept_count INTEGER,
            avg_zone_strength REAL,
            total_trades INTEGER,
            trades_with_tp1_hit INTEGER,
            trades_with_tp2_hit INTEGER,
            trades_with_runner INTEGER,
            runner_success_rate REAL,
            pnl_from_tp1 REAL,
            pnl_from_tp2 REAL,
            pnl_from_runner REAL,
            total_pnl REAL,
            liquidity_quality_score REAL,
            detail_json TEXT
        )
        """
    )
    
    # ========================
    # L5: REINFORCEMENT LEARNING + CAPITAL MANAGEMENT
    # ========================
    
    # L5: Capital state tracking
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS capital_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            operator_capital_brl REAL NOT NULL,
            margin_per_contract_brl REAL NOT NULL,
            max_contracts_cap INTEGER NOT NULL,
            base_contracts INTEGER NOT NULL,
            extra_contracts INTEGER NOT NULL,
            final_contracts INTEGER NOT NULL,
            reason TEXT,
            detail_json TEXT
        )
        """
    )
    
    # L5: Scalp events (fast exits for extra contracts)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scalp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,  -- OPENED, TP_HIT, SL_HIT, TIMEOUT
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            extra_contracts INTEGER,
            pnl REAL,
            hold_time_seconds INTEGER,
            reason TEXT,
            detail_json TEXT
        )
        """
    )
    
    # L5: RL Policy table (Thompson Sampling per regime)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_policy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regime TEXT NOT NULL,
            state_hash TEXT NOT NULL,
            action TEXT NOT NULL,
            alpha REAL,
            beta REAL,
            count INTEGER DEFAULT 0,
            total_reward REAL DEFAULT 0,
            mean_value REAL,
            updated_at TEXT,
            UNIQUE(regime, state_hash, action)
        )
        """
    )
    
    # L5: RL Events (policy decisions and learning)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            regime TEXT NOT NULL,
            state_hash TEXT NOT NULL,
            action TEXT NOT NULL,
            reward REAL,
            reason TEXT,
            frozen INTEGER DEFAULT 0,
            detail_json TEXT
        )
        """
    )
    
    # L5: Policy snapshots (for rollback)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS policy_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT UNIQUE NOT NULL,
            regime TEXT NOT NULL,
            time TEXT NOT NULL,
            policy_data TEXT NOT NULL,  -- JSON export of policy table
            metrics_json TEXT,  -- Performance metrics at snapshot time
            note TEXT
        )
        """
    )
    
    # L5: RL Report log (daily/weekly summaries)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_report_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            total_rl_events INTEGER,
            actions_enter_count INTEGER,
            actions_hold_count INTEGER,
            actions_conservative_count INTEGER,
            actions_realavancagem_count INTEGER,
            blocked_by_rl_count INTEGER,
            avg_reward REAL,
            regimes_frozen_count INTEGER,
            total_realavancagem_triggered INTEGER,
            realavancagem_success_rate REAL,
            total_scalps INTEGER,
            scalp_winrate REAL,
            scalp_total_pnl REAL,
            performance_trend REAL,
            detail_json TEXT
        )
        """
    )
    
    # L6: Cross-Market Metrics
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            corr_fast REAL,  -- Fast rolling correlation (e.g., 50 candles)
            corr_slow REAL,  -- Slow rolling correlation (e.g., 200 candles)
            beta REAL,  -- Regression coefficient
            spread REAL,  -- primary - beta*cross
            spread_mean REAL,  -- Rolling mean
            spread_std REAL,  -- Rolling std
            zscore REAL,  -- (spread - mean) / std
            corr_change_pct REAL,  -- % change in fast corr
            flags_json TEXT  -- JSON: {spread_high, spread_low, corr_broken, ...}
        )
        """
    )
    
    # L6: Cross-Market Signals (for filtering/confirmation)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,  -- CONFIRM_BUY, REDUCE_BUY, CONFIRM_SELL, REDUCE_SELL, MARKET_BROKEN, NEUTRAL
            strength REAL,  -- 0-1 confidence
            signal_json TEXT  -- JSON: {signal_type, strength, reasons, metrics}
        )
        """
    )
    
    # L6: News Events (economic calendar)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            title TEXT NOT NULL,
            impact TEXT NOT NULL,  -- HIGH, MEDIUM, LOW
            country TEXT,  -- Country code (USA, BR, EUR, etc)
            source TEXT  -- Source (e.g., MANUAL, MT5_CALENDAR)
        )
        """
    )
    
    # L6: News Blocks (record of trades blocked by news)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            is_blocked INTEGER NOT NULL,  -- 0=allowed, 1=blocked
            reason TEXT,  -- Why blocked or allowed
            event_timestamp TEXT,  -- Timestamp of triggering event
            event_title TEXT,  -- Title of triggering event
            risk_factor REAL,  -- 1.0 = no reduction, 0.5 = 50% reduction
            details_json TEXT  -- JSON: {reason, event, risk_factor, ...}
        )
        """
    )
    
    # L7: Market Status Log (IA trabalhando - status do mercado)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS market_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            headline TEXT NOT NULL,  -- Main status (ex: "Tendência de alta confirmada")
            phase TEXT NOT NULL,  -- Current phase (ex: "Aguardando pullback para compra")
            risk_state TEXT NOT NULL,  -- OK, CAUTION, BLOCKED
            reasons_json TEXT,  -- JSON list of reasons
            metadata_json TEXT  -- JSON with all supporting data
        )
        """
    )
    
    # L7: UI Events (symbol changes, blocks, state changes)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ui_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,  -- symbol_changed, news_block, correlation_break, etc
            payload_json TEXT  -- JSON with event details
        )
        """
    )
    
    # L7: Runtime Symbol Choices (track symbol changes via dashboard)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_symbol_choice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            changed_by TEXT NOT NULL,  -- dashboard, auto, config
            metadata_json TEXT  -- JSON with change details
        )
        """
    )
