from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass
class ScoreCalibration:
    threshold: float


def calibrate_threshold(win_rate: float) -> ScoreCalibration:
    threshold = 60.0
    if win_rate > 0.6:
        threshold = 55.0
    if win_rate < 0.4:
        threshold = 70.0
    return ScoreCalibration(threshold=threshold)


def calibrate_by_segments(samples: Iterable[Dict[str, float]]) -> Dict[str, float]:
    thresholds = {}
    for sample in samples:
        regime = sample.get("regime", "unknown")
        hour = sample.get("hour_bucket", "all")
        key = f"{regime}:{hour}"
        win_rate = sample.get("win_rate", 0.5)
        thresholds[key] = calibrate_threshold(win_rate).threshold
    return thresholds
