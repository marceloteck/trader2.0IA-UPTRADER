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
    conn.commit()
