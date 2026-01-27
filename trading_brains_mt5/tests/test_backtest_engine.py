import pandas as pd

from src.backtest.engine import run_backtest


def test_run_backtest_smoke(tmp_path):
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=250, freq="min"),
            "open": [100 + i * 0.1 for i in range(250)],
            "high": [100 + i * 0.1 + 1 for i in range(250)],
            "low": [100 + i * 0.1 - 1 for i in range(250)],
            "close": [100 + i * 0.1 for i in range(250)],
            "tick_volume": [100] * 250,
        }
    )
    db_path = tmp_path / "test.db"
    result = run_backtest("TEST", df, str(db_path), spread_max=2.0, slippage=0.5)
    assert result is not None
