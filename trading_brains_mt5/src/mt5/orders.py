from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    mt5 = None


@dataclass
class OrderResult:
    success: bool
    message: str
    order_id: Optional[int] = None
    retcode: Optional[int] = None


def send_order(symbol: str, action: str, lot: float, price: float, sl: float, tp: float) -> OrderResult:
    if mt5 is None:
        return OrderResult(False, "MetaTrader5 package not available", retcode=None)
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 202405,
        "comment": "TradingBrains",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    if result is None:
        return OrderResult(False, "Order send failed", retcode=None)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return OrderResult(False, f"Order failed retcode={result.retcode}", retcode=result.retcode)
    return OrderResult(True, "Order placed", result.order, retcode=result.retcode)
