from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskState:
    daily_loss: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0


def check_limits(state: RiskState, daily_loss_limit: float, max_trades: int, max_losses: int) -> bool:
    if state.daily_loss <= -abs(daily_loss_limit):
        return False
    if state.trades_today >= max_trades:
        return False
    if state.consecutive_losses >= max_losses:
        return False
    return True
