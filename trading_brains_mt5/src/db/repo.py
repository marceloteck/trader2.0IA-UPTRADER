from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from .connection import get_conn


def insert_features(db_path: str, symbol: str, timeframe: str, time: str, payload: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO features(symbol, timeframe, time, payload) VALUES (?, ?, ?, ?)",
        (symbol, timeframe, time, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def insert_brain_signal(db_path: str, symbol: str, time: str, brain_id: str, signal: Dict[str, Any], score: float) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO brain_signals(symbol, time, brain_id, signal, score) VALUES (?, ?, ?, ?, ?)",
        (symbol, time, brain_id, json.dumps(signal), score),
    )
    conn.commit()
    conn.close()


def insert_decision(db_path: str, symbol: str, time: str, action: str, payload: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO decisions(symbol, time, action, payload) VALUES (?, ?, ?, ?)",
        (symbol, time, action, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def insert_trade(db_path: str, trade: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO trades(symbol, opened_at, closed_at, side, entry, exit, pnl, mfe, mae, source, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade["symbol"],
            trade["opened_at"],
            trade.get("closed_at"),
            trade["side"],
            trade["entry"],
            trade.get("exit"),
            trade.get("pnl"),
            trade.get("mfe"),
            trade.get("mae"),
            trade.get("source", "unknown"),
            json.dumps(trade.get("payload", {})),
        ),
    )
    conn.commit()
    conn.close()


def insert_model(db_path: str, name: str, created_at: str, metrics: Dict[str, Any], path: str) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO models(name, created_at, metrics, path) VALUES (?, ?, ?, ?)",
        (name, created_at, json.dumps(metrics), path),
    )
    conn.commit()
    conn.close()


def upsert_training_state(db_path: str, symbol: str, timeframe: str, last_time: str, state: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "DELETE FROM training_state WHERE id = 1"
    )
    conn.execute(
        "INSERT INTO training_state(id, symbol, timeframe, last_time, state) VALUES (1, ?, ?, ?, ?)",
        (symbol, timeframe, last_time, json.dumps(state)),
    )
    conn.commit()
    conn.close()


def insert_level(db_path: str, symbol: str, time: str, source: str, payload: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO levels(symbol, time, source, payload) VALUES (?, ?, ?, ?)",
        (symbol, time, source, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def insert_metrics_window(db_path: str, run_id: int, window_id: int, metrics: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO metrics_windows(run_id, window_id, metrics_json) VALUES (?, ?, ?)",
        (run_id, window_id, json.dumps(metrics)),
    )
    conn.commit()
    conn.close()


def insert_regime_log(db_path: str, symbol: str, time: str, regime: str, payload: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO regimes_log(symbol, time, regime, payload) VALUES (?, ?, ?, ?)",
        (symbol, time, regime, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def insert_calibration(
    db_path: str, model_name: str, regime: str, hour_bucket: str, threshold: float, payload: Dict[str, Any]
) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO model_calibration(model_name, regime, hour_bucket, threshold, payload) VALUES (?, ?, ?, ?, ?)",
        (model_name, regime, hour_bucket, threshold, json.dumps(payload)),
    )
    conn.commit()
    conn.close()


def insert_order_event(db_path: str, symbol: str, time: str, action: str, retcode: int | None, message: str) -> None:
    conn = get_conn(db_path)
    conn.execute(
        "INSERT INTO order_events(symbol, time, action, retcode, message, payload) VALUES (?, ?, ?, ?, ?, ?)",
        (symbol, time, action, retcode, message, json.dumps({})),
    )
    conn.commit()
    conn.close()


def fetch_latest_signals(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM brain_signals ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_latest_trades(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_latest_decisions(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_latest_levels(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM levels ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_latest_regime(db_path: str) -> Dict[str, Any] | None:
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM regimes_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def fetch_risk_status(db_path: str, today_prefix: str) -> Dict[str, Any]:
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT pnl, opened_at FROM trades WHERE opened_at LIKE ?",
        (f"{today_prefix}%",),
    ).fetchall()
    conn.close()
    pnls = [row["pnl"] for row in rows if row["pnl"] is not None]
    return {
        "trades_today": len(rows),
        "pnl_today": float(sum(pnls)) if pnls else 0.0,
    }


# V3 FUNCTIONS

def insert_brain_performance(db_path: str, metrics: Dict[str, Any]) -> None:
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO brain_performance(
            brain_id, regime, win_rate, profit_factor, avg_rr,
            total_trades, total_pnl, max_drawdown, confidence, last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metrics["brain_id"],
            metrics["regime"],
            metrics["win_rate"],
            metrics["profit_factor"],
            metrics["avg_rr"],
            metrics["total_trades"],
            metrics["total_pnl"],
            metrics["max_drawdown"],
            metrics["confidence"],
            metrics["last_update"],
        ),
    )
    conn.commit()
    conn.close()


def fetch_brain_performance_history(db_path: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Recupera histórico de performance de cérebros"""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM brain_performance ORDER BY last_update DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_meta_decision(
    db_path: str,
    regime: str,
    allow_trading: bool,
    weight_adjustment: str,
    global_confidence: float,
    reasoning: str,
    risk_level: str,
) -> None:
    """Registra decisão do MetaBrain"""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO meta_decisions(
            regime, allow_trading, weight_adjustment, global_confidence,
            reasoning, risk_level, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            regime,
            1 if allow_trading else 0,
            weight_adjustment,
            global_confidence,
            reasoning,
            risk_level,
            __import__("datetime").datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def insert_regime_transition(
    db_path: str,
    from_regime: str,
    to_regime: str,
    from_duration: int,
    from_volatility: float,
    to_volatility: float,
    timestamp: str,
) -> None:
    """Registra transição de regime"""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO regime_transitions(
            from_regime, to_regime, from_duration, from_volatility,
            to_volatility, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (from_regime, to_regime, from_duration, from_volatility, to_volatility, timestamp),
    )
    conn.commit()
    conn.close()


def fetch_regime_history(db_path: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Recupera histórico de transições de regime"""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM regime_transitions ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_replay_priority(
    db_path: str,
    trade_id: int,
    priority_score: float,
    loss_magnitude: float,
    regime: str,
) -> None:
    """Registra prioridade de replay para aprendizado RL"""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO replay_priority(
            trade_id, priority_score, loss_magnitude, regime, last_updated
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (trade_id, priority_score, loss_magnitude, regime, __import__("datetime").datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def fetch_replay_buffer(db_path: str, regime: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Recupera buffer de replay priorizado por regime"""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT rp.*, t.entry, t.exit, t.pnl, t.mfe, t.mae
        FROM replay_priority rp
        JOIN trades t ON rp.trade_id = t.id
        WHERE rp.regime = ? OR rp.regime IS NULL
        ORDER BY rp.priority_score DESC
        LIMIT ?
        """,
        (regime, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_reinforcement_policy(
    db_path: str,
    state_hash: str,
    action: str,
    q_value: float,
    visit_count: int,
) -> None:
    """Registra/atualiza Q-value na tabela de política RL"""
    conn = get_conn(db_path)
    
    # Tenta atualizar, se não existir insere
    conn.execute(
        """
        INSERT OR REPLACE INTO reinforcement_policy(
            state_hash, q_value, visit_count, last_update
        ) VALUES (?, ?, ?, ?)
        """,
        (state_hash, q_value, visit_count, __import__("datetime").datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def fetch_reinforcement_policy(db_path: str) -> List[Dict[str, Any]]:
    """Recupera política RL treinada"""
    conn = get_conn(db_path)
    rows = conn.execute("SELECT * FROM reinforcement_policy").fetchall()
    conn.close()
    return [dict(row) for row in rows]


# V4 Execution Engine Functions

def insert_order_event(db_path: str, event: Dict[str, Any]) -> None:
    """Log order event."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO order_events(
            timestamp, ticket, symbol, side, volume, entry_price, filled_price, 
            filled_volume, status, sl, tp, reason, retcode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.get('timestamp'),
            event.get('ticket'),
            event.get('symbol'),
            event.get('side'),
            event.get('volume'),
            event.get('entry_price'),
            event.get('filled_price'),
            event.get('filled_volume'),
            event.get('status'),
            event.get('sl'),
            event.get('tp'),
            event.get('reason'),
            event.get('retcode'),
        ),
    )
    conn.commit()
    conn.close()


def insert_mt5_event(db_path: str, timestamp: str, event_type: str, message: str, details: Dict = None, severity: str = 'INFO') -> None:
    """Log MT5 event (connection, errors, etc)."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO mt5_events(timestamp, event_type, message, details, severity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            event_type,
            message,
            json.dumps(details) if details else None,
            severity,
        ),
    )
    conn.commit()
    conn.close()


def insert_risk_event(db_path: str, event: Dict[str, Any]) -> None:
    """Log risk event (circuit breaker, degrade, etc)."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO risk_events(timestamp, event_type, details, action)
        VALUES (?, ?, ?, ?)
        """,
        (
            event.get('timestamp'),
            event.get('event_type'),
            json.dumps(event.get('details')) if event.get('details') else None,
            event.get('action'),
        ),
    )
    conn.commit()
    conn.close()


def insert_audit_trail(db_path: str, trace: Dict[str, Any]) -> None:
    """Log decision audit trail."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO audit_trail(run_id, sequence, timestamp, trace_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            trace.get('run_id'),
            trace.get('sequence'),
            trace.get('timestamp'),
            json.dumps(trace),
        ),
    )
    conn.commit()
    conn.close()


def update_audit_trail_execution(db_path: str, run_id: str, sequence: int, execution_data: Dict) -> None:
    """Update audit trail with execution result."""
    conn = get_conn(db_path)
    
    # Fetch existing trace
    row = conn.execute(
        "SELECT trace_json FROM audit_trail WHERE run_id = ? AND sequence = ?",
        (run_id, sequence)
    ).fetchone()
    
    if row:
        trace = json.loads(row[0])
        # Update execution fields
        trace.update(execution_data)
        conn.execute(
            "UPDATE audit_trail SET trace_json = ? WHERE run_id = ? AND sequence = ?",
            (json.dumps(trace), run_id, sequence)
        )
        conn.commit()
    
    conn.close()


def insert_position_state(db_path: str, position: Dict[str, Any]) -> None:
    """Save position state snapshot."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO position_state(
            ticket, symbol, side, volume, entry_price, open_time, sl, tp, status,
            close_price, close_time, current_price, pnl, pnl_percent, comment, magic, last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position.get('ticket'),
            position.get('symbol'),
            position.get('side'),
            position.get('volume'),
            position.get('entry_price'),
            position.get('open_time'),
            position.get('sl'),
            position.get('tp'),
            position.get('status'),
            position.get('close_price'),
            position.get('close_time'),
            position.get('current_price'),
            position.get('pnl'),
            position.get('pnl_percent'),
            position.get('comment'),
            position.get('magic'),
            __import__("datetime").datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def update_position_state(db_path: str, position: Dict[str, Any]) -> None:
    """Update position state."""
    insert_position_state(db_path, position)  # Use INSERT OR REPLACE


def fetch_open_positions(db_path: str) -> List[Dict[str, Any]]:
    """Fetch all open positions."""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM position_state WHERE status = 'OPEN'"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def fetch_position_by_ticket(db_path: str, ticket: int) -> Dict[str, Any]:
    """Fetch position by ticket."""
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM position_state WHERE ticket = ?",
        (ticket,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def insert_execution_result(db_path: str, result: Dict[str, Any]) -> None:
    """Log execution result."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO execution_results(
            timestamp, ticket, symbol, action, success, filled_price, slippage,
            order_status, risk_passed, risk_reason, pnl, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.get('timestamp'),
            result.get('ticket'),
            result.get('decision', {}).get('symbol'),
            result.get('decision', {}).get('action'),
            result.get('success'),
            result.get('filled_price'),
            result.get('slippage'),
            result.get('order_status'),
            result.get('risk_passed'),
            result.get('risk_reason'),
            result.get('pnl'),
            result.get('reason'),
        ),
    )
    conn.commit()
    conn.close()


def fetch_execution_results(db_path: str, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch execution results."""
    conn = get_conn(db_path)
    
    if symbol:
        rows = conn.execute(
            "SELECT * FROM execution_results WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
            (symbol, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM execution_results ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]


# ========================
# LEVEL 5: CAPITAL + RL + SCALP
# ========================

def insert_capital_state(db_path: str, time: str, symbol: str, capital_state: Dict[str, Any]) -> None:
    """Insert capital state record."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO capital_state(time, symbol, operator_capital_brl, margin_per_contract_brl, 
                                   max_contracts_cap, base_contracts, extra_contracts, 
                                   final_contracts, reason, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time,
            symbol,
            capital_state.get("operator_capital_brl"),
            capital_state.get("margin_per_contract_brl"),
            capital_state.get("max_contracts_cap"),
            capital_state.get("base_contracts"),
            capital_state.get("extra_contracts"),
            capital_state.get("final_contracts"),
            capital_state.get("reason"),
            json.dumps(capital_state.get("detail", {}))
        )
    )
    conn.commit()
    conn.close()


def insert_scalp_event(db_path: str, time: str, symbol: str, event: Dict[str, Any]) -> None:
    """Insert scalp event."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO scalp_events(time, symbol, event_type, side, entry_price, exit_price, 
                                  extra_contracts, pnl, hold_time_seconds, reason, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time,
            symbol,
            event.get("event_type"),
            event.get("side"),
            event.get("entry_price"),
            event.get("exit_price"),
            event.get("extra_contracts"),
            event.get("pnl"),
            event.get("hold_time_seconds"),
            event.get("reason"),
            json.dumps(event.get("detail", {}))
        )
    )
    conn.commit()
    conn.close()


def upsert_rl_policy(db_path: str, regime: str, state_hash: str, action: str, policy_values: Dict[str, Any]) -> None:
    """Upsert RL policy value (Thompson Beta)."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO rl_policy(regime, state_hash, action, alpha, beta, count, total_reward, mean_value, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(regime, state_hash, action) DO UPDATE SET
            alpha = excluded.alpha,
            beta = excluded.beta,
            count = excluded.count,
            total_reward = excluded.total_reward,
            mean_value = excluded.mean_value,
            updated_at = excluded.updated_at
        """,
        (
            regime,
            state_hash,
            action,
            policy_values.get("alpha"),
            policy_values.get("beta"),
            policy_values.get("count"),
            policy_values.get("total_reward"),
            policy_values.get("mean_value"),
            policy_values.get("updated_at")
        )
    )
    conn.commit()
    conn.close()


def insert_rl_event(db_path: str, time: str, symbol: str, event: Dict[str, Any]) -> None:
    """Insert RL event."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO rl_events(time, symbol, regime, state_hash, action, reward, reason, frozen, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time,
            symbol,
            event.get("regime"),
            event.get("state_hash"),
            event.get("action"),
            event.get("reward"),
            event.get("reason"),
            1 if event.get("frozen") else 0,
            json.dumps(event.get("detail", {}))
        )
    )
    conn.commit()
    conn.close()


def create_policy_snapshot(db_path: str, snapshot_id: str, regime: str, time: str, policy_data: str, metrics: Dict[str, Any], note: str = None) -> None:
    """Create policy snapshot."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO policy_snapshots(snapshot_id, regime, time, policy_data, metrics_json, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            regime,
            time,
            policy_data,
            json.dumps(metrics),
            note
        )
    )
    conn.commit()
    conn.close()


def fetch_rl_policy_table(db_path: str, regime: str) -> Dict[str, Any]:
    """Fetch entire RL policy table for regime."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT state_hash, action, alpha, beta, count, total_reward, mean_value 
        FROM rl_policy 
        WHERE regime = ?
        """,
        (regime,)
    ).fetchall()
    conn.close()
    
    policy = {}
    for row in rows:
        state_hash = row[0]
        if state_hash not in policy:
            policy[state_hash] = {}
        policy[state_hash][row[1]] = {
            "alpha": row[2],
            "beta": row[3],
            "count": row[4],
            "total_reward": row[5],
            "mean_value": row[6]
        }
    return policy


def insert_rl_report(db_path: str, report_date: str, symbol: str, report_data: Dict[str, Any]) -> None:
    """Insert RL daily report."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO rl_report_log(report_date, symbol, total_rl_events, actions_enter_count, 
                                   actions_hold_count, actions_conservative_count, actions_realavancagem_count,
                                   blocked_by_rl_count, avg_reward, regimes_frozen_count, total_realavancagem_triggered,
                                   realavancagem_success_rate, total_scalps, scalp_winrate, scalp_total_pnl,
                                   performance_trend, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_date,
            symbol,
            report_data.get("total_rl_events"),
            report_data.get("actions_enter_count"),
            report_data.get("actions_hold_count"),
            report_data.get("actions_conservative_count"),
            report_data.get("actions_realavancagem_count"),
            report_data.get("blocked_by_rl_count"),
            report_data.get("avg_reward"),
            report_data.get("regimes_frozen_count"),
            report_data.get("total_realavancagem_triggered"),
            report_data.get("realavancagem_success_rate"),
            report_data.get("total_scalps"),
            report_data.get("scalp_winrate"),
            report_data.get("scalp_total_pnl"),
            report_data.get("performance_trend"),
            json.dumps(report_data.get("detail", {}))
        )
    )
    conn.commit()
    conn.close()

# L6: CROSS-MARKET FUNCTIONS

def insert_cross_metric(db_path: str, metric_data: Dict[str, Any]) -> None:
    """Insert cross-market metric."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO cross_metrics(timestamp, symbol, corr_fast, corr_slow, beta, spread, 
                                   spread_mean, spread_std, zscore, corr_change_pct, flags_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_data.get("timestamp"),
            metric_data.get("symbol"),
            metric_data.get("corr_fast"),
            metric_data.get("corr_slow"),
            metric_data.get("beta"),
            metric_data.get("spread"),
            metric_data.get("spread_mean"),
            metric_data.get("spread_std"),
            metric_data.get("zscore"),
            metric_data.get("corr_change_pct"),
            metric_data.get("flags_json", "{}")
        )
    )
    conn.commit()
    conn.close()


def insert_cross_signal(db_path: str, signal_data: Dict[str, Any]) -> None:
    """Insert cross-market signal."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO cross_signals(timestamp, symbol, signal_type, strength, signal_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            signal_data.get("timestamp"),
            signal_data.get("symbol"),
            signal_data.get("signal_type"),
            signal_data.get("strength"),
            signal_data.get("signal_json", "{}")
        )
    )
    conn.commit()
    conn.close()


def get_latest_cross_signal(db_path: str, symbol: str) -> Dict[str, Any] | None:
    """Get latest cross-market signal for symbol."""
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT timestamp, symbol, signal_type, strength, signal_json FROM cross_signals WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1",
        (symbol,)
    ).fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "timestamp": row[0],
        "symbol": row[1],
        "signal_type": row[2],
        "strength": row[3],
        "signal_json": row[4]
    }


# L6: NEWS FUNCTIONS

def insert_news_event(db_path: str, event_data: Dict[str, Any]) -> None:
    """Insert news event."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO news_events(timestamp, title, impact, country, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event_data.get("timestamp"),
            event_data.get("title"),
            event_data.get("impact"),
            event_data.get("country", "XX"),
            event_data.get("source", "MANUAL")
        )
    )
    conn.commit()
    conn.close()


def insert_news_block(db_path: str, block_data: Dict[str, Any]) -> None:
    """Insert news block record."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO news_blocks(timestamp, is_blocked, reason, event_timestamp, event_title, risk_factor, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            block_data.get("timestamp"),
            1 if block_data.get("is_blocked") else 0,
            block_data.get("reason"),
            block_data.get("event_timestamp"),
            block_data.get("event_title"),
            block_data.get("risk_factor", 1.0),
            block_data.get("details_json", "{}")
        )
    )
    conn.commit()
    conn.close()


def get_news_events_for_date(db_path: str, date_str: str) -> List[Dict[str, Any]]:
    """Get all news events for a specific date."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT timestamp, title, impact, country, source 
        FROM news_events 
        WHERE DATE(timestamp) = ?
        ORDER BY timestamp
        """,
        (date_str,)
    ).fetchall()
    conn.close()
    
    return [
        {
            "timestamp": row[0],
            "title": row[1],
            "impact": row[2],
            "country": row[3],
            "source": row[4]
        }
        for row in rows
    ]


# L7: DASHBOARD UI FUNCTIONS

def insert_market_status(db_path: str, status_data: Dict[str, Any]) -> None:
    """Insert market status log."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO market_status_log(timestamp, symbol, headline, phase, risk_state, reasons_json, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            status_data.get("timestamp"),
            status_data.get("symbol"),
            status_data.get("headline"),
            status_data.get("phase"),
            status_data.get("risk_state"),
            json.dumps(status_data.get("reasons", [])),
            json.dumps(status_data.get("metadata", {}))
        )
    )
    conn.commit()
    conn.close()


def insert_ui_event(db_path: str, event_data: Dict[str, Any]) -> None:
    """Insert UI event (symbol change, market status, etc)."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO ui_events(timestamp, event_type, payload_json)
        VALUES (?, ?, ?)
        """,
        (
            event_data.get("timestamp"),
            event_data.get("type"),
            json.dumps(event_data.get("payload", {}))
        )
    )
    conn.commit()
    conn.close()


def insert_runtime_symbol_choice(db_path: str, choice_data: Dict[str, Any]) -> None:
    """Log symbol choice made via dashboard."""
    conn = get_conn(db_path)
    conn.execute(
        """
        INSERT INTO runtime_symbol_choice(timestamp, symbol, changed_by, metadata_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            choice_data.get("timestamp"),
            choice_data.get("symbol"),
            choice_data.get("changed_by", "dashboard"),
            json.dumps(choice_data.get("metadata", {}))
        )
    )
    conn.commit()
    conn.close()


def fetch_latest_market_status(db_path: str) -> Dict[str, Any] | None:
    """Get latest market status."""
    conn = get_conn(db_path)
    row = conn.execute(
        """
        SELECT timestamp, symbol, headline, phase, risk_state, reasons_json, metadata_json
        FROM market_status_log
        ORDER BY timestamp DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    
    if row:
        return {
            "timestamp": row[0],
            "symbol": row[1],
            "headline": row[2],
            "phase": row[3],
            "risk_state": row[4],
            "reasons": json.loads(row[5]) if row[5] else [],
            "metadata": json.loads(row[6]) if row[6] else {}
        }
    
    return None


def fetch_ui_events(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent UI events."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT timestamp, event_type, payload_json
        FROM ui_events
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()
    
    return [
        {
            "timestamp": row[0],
            "type": row[1],
            "payload": json.loads(row[2]) if row[2] else {}
        }
        for row in rows
    ]


def fetch_runtime_symbol_choices(db_path: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get runtime symbol choices."""
    conn = get_conn(db_path)
    rows = conn.execute(
        """
        SELECT timestamp, symbol, changed_by, metadata_json
        FROM runtime_symbol_choice
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()
    
    return [
        {
            "timestamp": row[0],
            "symbol": row[1],
            "changed_by": row[2],
            "metadata": json.loads(row[3]) if row[3] else {}
        }
        for row in rows
    ]
