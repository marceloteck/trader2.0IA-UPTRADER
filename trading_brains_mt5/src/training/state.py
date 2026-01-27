from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..db.connection import get_conn


def load_state(db_path: str) -> Optional[Dict[str, Any]]:
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM training_state WHERE id = 1").fetchone()
    conn.close()
    if row is None:
        return None
    return {"symbol": row["symbol"], "timeframe": row["timeframe"], "last_time": row["last_time"], "state": json.loads(row["state"])}
