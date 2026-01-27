from __future__ import annotations

from typing import Optional

import pandas as pd

from .brain_interface import Brain, BrainSignal, Context


class MomentumBrain(Brain):
    id = "momentum"
    name = "Momentum"

    def detect(self, data: pd.DataFrame) -> Optional[BrainSignal]:
        if data is None or data.empty:
            return None
        return None

    def score(self, signal: BrainSignal, context: Context) -> float:
        return 40.0
