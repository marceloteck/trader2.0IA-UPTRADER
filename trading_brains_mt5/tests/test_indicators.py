import pandas as pd

from src.features.indicators import add_moving_averages, add_rsi, add_atr, add_vwap


def test_indicators_basic():
    df = pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0.5, 1.5, 2.5, 3.5, 4.5],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "tick_volume": [100, 120, 130, 140, 150],
        }
    )
    df = add_moving_averages(df, [2])
    df = add_rsi(df)
    df = add_atr(df)
    df = add_vwap(df)
    assert "ma_2" in df.columns
    assert "rsi" in df.columns
    assert "atr" in df.columns
    assert "vwap" in df.columns
