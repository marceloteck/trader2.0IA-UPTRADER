from __future__ import annotations

from pathlib import Path
from typing import Any

from joblib import dump, load


def save_model(model: Any, path: str) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    dump(model, path)
    return path


def load_model(path: str) -> Any:
    return load(path)
