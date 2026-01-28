from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException

from ..config.settings import load_settings
from ..db import repo
from ..mt5.mt5_client import MT5Client

app = FastAPI()
settings = load_settings()
logger = logging.getLogger(__name__)

# Runtime symbol tracking
RUNTIME_SYMBOL_PATH = Path("data/config/runtime_symbol.json")
mt5_client = None  # Lazy initialized


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

# ============================================================================
# LEVEL 7: DASHBOARD ENHANCEMENTS
# ============================================================================

@app.get("/symbols/list")
def symbols_list():
    """
    List available trading symbols from MT5.
    
    Returns: {
        "symbols": [
            {"name": "WDO$N", "spread": 2.0, "digits": 0, "trade_mode": "OPEN"},
            ...
        ],
        "current": "WDO$N",
        "mt5_connected": true
    }
    """
    global mt5_client
    
    try:
        if mt5_client is None:
            mt5_client = MT5Client()
        
        # Get available symbols (filtered for common futures)
        symbol_filters = ["WIN", "IND", "IBOV", "BOV", "DOL", "WDO"]
        symbols_info = []
        
        try:
            all_symbols = mt5_client.connection.symbols_get()
            for sym in all_symbols:
                if any(f in sym.name for f in symbol_filters):
                    symbols_info.append({
                        "name": sym.name,
                        "spread": sym.spread,
                        "digits": sym.digits,
                        "trade_mode": str(sym.trade_mode)
                    })
        except Exception as e:
            logger.warning(f"Error fetching symbols from MT5: {e}")
            symbols_info = []
        
        # Get current symbol (from runtime or settings)
        current_symbol = _get_runtime_symbol() or settings.symbol
        
        return {
            "symbols": sorted(symbols_info, key=lambda x: x["name"]),
            "current": current_symbol,
            "mt5_connected": True
        }
    
    except Exception as e:
        logger.error(f"Error in /symbols/list: {e}")
        return {
            "symbols": [],
            "current": settings.symbol,
            "mt5_connected": False,
            "error": str(e)
        }


@app.post("/symbols/set")
def symbols_set(symbol: str):
    """
    Set primary trading symbol (requires ENABLE_DASHBOARD_CONTROL=true).
    
    Args:
        symbol: Symbol name (e.g., "WDO$N")
    
    Returns: {
        "status": "ok",
        "symbol": "WDO$N",
        "saved_to": "data/config/runtime_symbol.json"
    }
    """
    if not settings.enable_dashboard_control:
        raise HTTPException(status_code=403, detail="Dashboard control disabled")
    
    try:
        # Validate symbol exists in MT5
        global mt5_client
        if mt5_client is None:
            mt5_client = MT5Client()
        
        # Save to runtime file
        runtime_data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "changed_by": "dashboard"
        }
        
        os.makedirs("data/config", exist_ok=True)
        with open(RUNTIME_SYMBOL_PATH, "w") as f:
            json.dump(runtime_data, f, indent=2)
        
        # Save to database
        repo.insert_ui_event(
            settings.db_path,
            {
                "timestamp": datetime.now().isoformat(),
                "type": "symbol_changed",
                "payload": {"old_symbol": settings.symbol, "new_symbol": symbol}
            }
        )
        
        logger.info(f"Symbol changed to {symbol} via dashboard")
        
        return {
            "status": "ok",
            "symbol": symbol,
            "saved_to": str(RUNTIME_SYMBOL_PATH)
        }
    
    except Exception as e:
        logger.error(f"Error setting symbol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_runtime_symbol() -> str | None:
    """Get runtime symbol from file if exists."""
    try:
        if RUNTIME_SYMBOL_PATH.exists():
            with open(RUNTIME_SYMBOL_PATH) as f:
                data = json.load(f)
                return data.get("symbol")
    except Exception as e:
        logger.debug(f"Error reading runtime symbol: {e}")
    
    return None


@app.get("/scoreboard/live")
def scoreboard_live():
    """
    Get live scoreboard with market metrics.
    
    Returns: {
        "timestamp": "2024-01-28T10:30:45",
        "counters": {
            "buy_signals": 5,
            "sell_signals": 3,
            "hold_signals": 12,
            "trades_total": 8,
            "trades_win": 5,
            "trades_loss": 3,
            "blocks_news": 2,
            "blocks_correlation": 1
        },
        "metrics": {
            "pnl_today": 250.50,
            "dd_today": -50.00,
            "winrate_today": 0.625,
            "pf_today": 2.1,
            "avg_trade_duration_minutes": 15
        },
        "recent_events": [...]
    }
    """
    try:
        today = datetime.now().date().isoformat()
        
        # Get counters from database
        signals = repo.fetch_latest_signals(settings.db_path, limit=100)
        trades = repo.fetch_latest_trades(settings.db_path, limit=100)
        
        buy_count = sum(1 for s in (signals or []) if s.get("action") == "BUY")
        sell_count = sum(1 for s in (signals or []) if s.get("action") == "SELL")
        hold_count = sum(1 for s in (signals or []) if s.get("action") == "HOLD")
        
        win_count = sum(1 for t in (trades or []) if t.get("pnl", 0) > 0)
        loss_count = sum(1 for t in (trades or []) if t.get("pnl", 0) < 0)
        trade_count = len(trades or [])
        
        # Get UI events for blocks
        ui_events = repo.fetch_ui_events(settings.db_path, limit=50)
        news_blocks = sum(1 for e in (ui_events or []) if e.get("type") == "news_block")
        corr_blocks = sum(1 for e in (ui_events or []) if e.get("type") == "correlation_break")
        
        # Calculate metrics
        total_pnl = sum(t.get("pnl", 0) for t in (trades or []))
        dd = min([t.get("pnl", 0) for t in (trades or [])] or [0])
        winrate = win_count / trade_count if trade_count > 0 else 0.0
        gross_profit = sum(t.get("pnl", 0) for t in (trades or []) if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in (trades or []) if t.get("pnl", 0) < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Recent events
        recent_events = []
        if ui_events:
            for event in sorted(ui_events, key=lambda x: x.get("timestamp", ""), reverse=True)[:20]:
                recent_events.append({
                    "timestamp": event.get("timestamp"),
                    "type": event.get("type"),
                    "payload": event.get("payload", {})
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "counters": {
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "hold_signals": hold_count,
                "trades_total": trade_count,
                "trades_win": win_count,
                "trades_loss": loss_count,
                "blocks_news": news_blocks,
                "blocks_correlation": corr_blocks
            },
            "metrics": {
                "pnl_today": round(total_pnl, 2),
                "dd_today": round(dd, 2),
                "winrate_today": round(winrate, 3),
                "pf_today": round(pf, 2)
            },
            "recent_events": recent_events
        }
    
    except Exception as e:
        logger.error(f"Error in /scoreboard/live: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "counters": {},
            "metrics": {},
            "recent_events": []
        }


@app.get("/market-status/current")
def market_status_current():
    """
    Get current market status (IA trabalhando).
    
    Returns: {
        "timestamp": "2024-01-28T10:30:45",
        "symbol": "WDO$N",
        "headline": "📈 Tendência de ALTA confirmada",
        "phase": "Seguindo tendência com liquidez forte - Pronto para TREND_UP",
        "risk_state": "OK",
        "reasons": [...]
    }
    """
    try:
        # Get latest market status from database
        status = repo.fetch_latest_market_status(settings.db_path)
        
        if status:
            return {
                "timestamp": status.get("timestamp"),
                "symbol": status.get("symbol"),
                "headline": status.get("headline"),
                "phase": status.get("phase"),
                "risk_state": status.get("risk_state"),
                "reasons": status.get("reasons", []),
                "metadata": status.get("metadata", {})
            }
        
        # Fallback if no status saved
        return {
            "timestamp": datetime.now().isoformat(),
            "symbol": settings.symbol,
            "headline": "❓ Aguardando primeira análise",
            "phase": "Iniciando coleta de dados",
            "risk_state": "OK",
            "reasons": ["Sistema inicializando"]
        }
    
    except Exception as e:
        logger.error(f"Error in /market-status/current: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }