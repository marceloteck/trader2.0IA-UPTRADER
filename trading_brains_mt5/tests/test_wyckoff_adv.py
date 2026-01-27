import pandas as pd

from src.brains.wyckoff_adv import WyckoffAdvancedBrain


def test_wyckoff_adv_spring():
    data = {
        "open": [100] * 60,
        "high": [101] * 60,
        "low": [99] * 59 + [95],
        "close": [100] * 59 + [100],
        "tick_volume": [100] * 60,
    }
    df = pd.DataFrame(data)
    signal = WyckoffAdvancedBrain().detect(df)
    assert signal is not None
    assert signal.metadata.get("setup_type") in {"SPRING", "RANGE_EXTREME"}
