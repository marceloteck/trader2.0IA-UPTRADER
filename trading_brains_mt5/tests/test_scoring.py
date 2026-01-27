from src.brains.brain_interface import BrainSignal, Context
from src.brains.trend_pullback import TrendPullbackBrain


def test_trend_pullback_score():
    brain = TrendPullbackBrain()
    signal = BrainSignal("trend_pullback", "BUY", 100.0, 95.0, 110.0, 120.0, ["test"])
    context = Context(symbol="TEST", timeframe="M1", features={"regime": "trend_up"}, spread=0.0)
    score = brain.score(signal, context)
    assert score >= 80.0
