from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt

from ..models.metrics import compute_metrics


def save_report(trades: List[Dict[str, float]], pnls: List[float], output_dir: str) -> Dict[str, float]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(pnls)
    report_path = Path(output_dir) / "backtest_report.json"
    report_path.write_text(json.dumps({"metrics": metrics, "trades": trades}, indent=2))

    if pnls:
        plt.figure(figsize=(8, 4))
        plt.plot(pnls)
        plt.title("Backtest PnL")
        plt.xlabel("Trade")
        plt.ylabel("PnL")
        plt.tight_layout()
        plt.savefig(Path(output_dir) / "backtest_pnl.png")
        plt.close()
    return metrics
