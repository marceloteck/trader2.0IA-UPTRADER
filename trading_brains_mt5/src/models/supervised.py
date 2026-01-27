from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression


def train_simple_classifier(X: np.ndarray, y: np.ndarray) -> Tuple[LogisticRegression, float]:
    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
    score = float(model.score(X, y))
    return model, score


def train_brain_classifiers(datasets: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> Dict[str, LogisticRegression]:
    models = {}
    for brain_id, (X, y) in datasets.items():
        if len(X) == 0:
            continue
        model = LogisticRegression(max_iter=200)
        model.fit(X, y)
        models[brain_id] = model
    return models


def prob_to_score(prob: float) -> float:
    return max(0.0, min(100.0, prob * 100))
