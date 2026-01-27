import pandas as pd

from src.features.indicators import add_vwap
from src.brains.liquidity_levels import LiquidityBrain


def test_liquidity_levels():
    df = pd.DataFrame(
        {
            "open": [100 + i for i in range(60)],
            "high": [101 + i for i in range(60)],
            "low": [99 + i for i in range(60)],
            "close": [100 + i for i in range(60)],
            "tick_volume": [100] * 60,
        }
    )
    df = add_vwap(df)
    signal = LiquidityBrain().detect(df)
    assert signal is not None
    assert signal.metadata.get("nearest_supports")
