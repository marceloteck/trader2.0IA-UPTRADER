from __future__ import annotations

from typing import Iterable


def replay_indices(length: int, times: int) -> Iterable[int]:
    for _ in range(times):
        for idx in range(length):
            yield idx
