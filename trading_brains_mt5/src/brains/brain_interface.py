from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BrainSignal:
    brain_id: str
    action: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    reasons: List[str]
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Decision:
    action: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    size: float
    reason: str
    contributors: List[str]
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Context:
    symbol: str
    timeframe: str
    features: Dict[str, float | str]
    spread: float


class Brain:
    id: str
    name: str

    def detect(self, data) -> Optional[BrainSignal]:
        raise NotImplementedError

    def score(self, signal: BrainSignal, context: Context) -> float:
        raise NotImplementedError

    def explain(self, signal: BrainSignal) -> str:
        return "; ".join(signal.reasons)
