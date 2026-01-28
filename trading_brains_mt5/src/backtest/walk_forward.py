from __future__ import annotations

import logging
from typing import Iterator, Tuple, Optional
import pandas as pd
from datetime import datetime

logger = logging.getLogger("trading_brains.backtest")


def split_walk_forward(
    df: pd.DataFrame,
    train_size: int,
    test_size: int,
    purge_candles: int = 50,
    embargo_candles: int = 50
) -> Iterator[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Walk-forward split with anti-leak purge and embargo.
    
    Anti-leak strategy:
    1. PURGE: Remove data around train/test boundary (leakage window)
    2. EMBARGO: Skip first N candles of test set (forward-looking bias)
    
    Args:
        df: Full OHLC dataframe
        train_size: Candles for training
        test_size: Candles for testing
        purge_candles: Remove this many candles around train/test boundary
        embargo_candles: Skip this many candles at start of test set
    
    Yields:
        (train_df, test_df) tuples with anti-leak adjustments
    """
    start = 0
    split_id = 0
    
    while start + train_size + test_size <= len(df):
        # Original indices
        train_end_idx = start + train_size
        test_start_idx = train_end_idx
        test_end_idx = test_start_idx + test_size
        
        # Apply PURGE: remove purge_candles before boundary
        # This prevents lookahead from training on data too close to test
        purge_train_end = max(start, train_end_idx - purge_candles)
        train = df.iloc[start:purge_train_end]
        
        # Apply EMBARGO: skip first embargo_candles of test
        # This prevents forward-looking bias from training affecting immediate test
        embargo_test_start = test_start_idx + embargo_candles
        embargo_test_start = min(embargo_test_start, test_end_idx)
        test = df.iloc[embargo_test_start:test_end_idx]
        
        if len(train) > 0 and len(test) > 0:
            logger.info(
                f"WF split {split_id}: train={len(train)} "
                f"(purged {purge_candles}), test={len(test)} "
                f"(embargoed {embargo_candles})"
            )
            yield train, test
        
        split_id += 1
        start += test_size

