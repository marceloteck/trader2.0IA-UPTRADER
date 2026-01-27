import pandas as pd

from src.brains.gann_macro import GannMacroBrain


def test_gann_macro_zones():
    df = pd.DataFrame(
        {
            "open": [100 + i * 0.5 for i in range(220)],
            "high": [101 + i * 0.5 for i in range(220)],
            "low": [99 + i * 0.5 for i in range(220)],
            "close": [100 + i * 0.5 for i in range(220)],
            "tick_volume": [100] * 220,
        }
    )
    signal = GannMacroBrain().detect(df)
    assert signal is not None
    assert signal.metadata.get("support_zone")
    assert signal.metadata.get("resistance_zone")
