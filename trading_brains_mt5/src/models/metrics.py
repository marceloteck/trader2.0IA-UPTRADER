from __future__ import annotations

from typing import Iterable, Dict


def compute_metrics(pnls: Iterable[float]) -> Dict[str, float]:
    pnls_list = list(pnls)
    wins = [p for p in pnls_list if p > 0]
    losses = [p for p in pnls_list if p < 0]
    winrate = len(wins) / len(pnls_list) if pnls_list else 0.0
    payoff = (sum(wins) / len(wins)) / abs(sum(losses) / len(losses)) if wins and losses else 0.0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else 0.0
    return {
        "winrate": winrate,
        "payoff": payoff,
        "profit_factor": profit_factor,
    }
