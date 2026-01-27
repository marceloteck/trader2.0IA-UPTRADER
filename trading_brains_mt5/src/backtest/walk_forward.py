from __future__ import annotations

import pandas as pd


def split_walk_forward(df: pd.DataFrame, train_size: int, test_size: int):
    start = 0
    while start + train_size + test_size <= len(df):
        train = df.iloc[start : start + train_size]
        test = df.iloc[start + train_size : start + train_size + test_size]
        yield train, test
        start += test_size
