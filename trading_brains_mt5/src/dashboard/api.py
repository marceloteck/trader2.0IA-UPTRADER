from __future__ import annotations

import os
from datetime import datetime

from fastapi import FastAPI

from ..config.settings import load_settings
from ..db import repo

app = FastAPI()
settings = load_settings()


@app.get("/status")
def status():
    return {
        "symbol": settings.symbol,
        "timeframes": settings.timeframes,
        "live_enabled": settings.enable_live_trading,
    }


@app.get("/signals")
def signals(limit: int = 50):
    return repo.fetch_latest_signals(settings.db_path, limit=limit)


@app.get("/trades")
def trades(limit: int = 50):
    return repo.fetch_latest_trades(settings.db_path, limit=limit)


@app.get("/metrics/latest")
def metrics_latest():
    decisions = repo.fetch_latest_decisions(settings.db_path, limit=1)
    return {"latest_decision": decisions[0] if decisions else None}


@app.get("/brains/scoreboard")
def brains_scoreboard(limit: int = 10):
    signals = repo.fetch_latest_signals(settings.db_path, limit=limit)
    return {"signals": signals}


@app.get("/regime/current")
def regime_current():
    return repo.fetch_latest_regime(settings.db_path)


@app.get("/levels/current")
def levels_current():
    return repo.fetch_latest_levels(settings.db_path, limit=10)


@app.get("/risk/status")
def risk_status():
    today = datetime.utcnow().date().isoformat()
    return repo.fetch_risk_status(settings.db_path, today)


@app.post("/control/kill")
def control_kill():
    if not settings.enable_dashboard_control:
        return {"status": "disabled"}
    os.makedirs("./data", exist_ok=True)
    stop_path = os.path.join("./data", "STOP.txt")
    with open(stop_path, "w", encoding="utf-8") as handle:
        handle.write("STOP")
    return {"status": "ok", "path": stop_path}
