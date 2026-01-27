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
