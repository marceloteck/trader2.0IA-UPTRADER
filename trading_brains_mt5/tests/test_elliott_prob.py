import pandas as pd

from src.brains.elliott_prob import ElliottProbBrain


def test_elliott_candidates():
    df = pd.DataFrame(
        {
            "open": [100 + i for i in range(60)],
            "high": [101 + i for i in range(60)],
            "low": [99 + i for i in range(60)],
            "close": [100 + i for i in range(60)],
            "tick_volume": [100] * 60,
        }
    )
    signal = ElliottProbBrain().detect(df)
    assert signal is not None
    assert signal.metadata.get("candidates")
    assert "invalidation_level" in signal.metadata
