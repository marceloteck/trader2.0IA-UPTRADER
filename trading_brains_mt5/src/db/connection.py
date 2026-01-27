from __future__ import annotations

import os
import sqlite3
from typing import Iterator

from .schema import create_tables


def get_conn(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(db_path: str) -> None:
    conn = get_conn(db_path)
    create_tables(conn)
    conn.close()


def conn_scope(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = get_conn(db_path)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()
