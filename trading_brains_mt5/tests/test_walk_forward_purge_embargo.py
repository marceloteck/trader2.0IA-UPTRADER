"""Tests for L1 walk-forward purge and embargo."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.backtest.walk_forward import split_walk_forward


def test_walk_forward_without_purge_embargo():
    """Test basic walk-forward without anti-leak."""
    df = pd.DataFrame({
        "timestamp": [datetime(2024, 1, i) for i in range(1, 31)],
        "close": range(30)
    })
    
    splits = list(split_walk_forward(
        df,
        train_size=10,
        test_size=5,
        purge_candles=0,
        embargo_candles=0
    ))
    
    # Should have 3 splits: indices 0-9, 15-19 / indices 10-14, 20-24 / indices 15-19, 25-29
    assert len(splits) >= 2
    train, test = splits[0]
    assert len(train) == 10
    assert len(test) == 5


def test_walk_forward_purge():
    """Test that purge removes data from train set."""
    df = pd.DataFrame({
        "timestamp": [datetime(2024, 1, i) for i in range(1, 51)],
        "close": range(50)
    })
    
    splits_no_purge = list(split_walk_forward(
        df, train_size=20, test_size=10, purge_candles=0, embargo_candles=0
    ))
    
    splits_with_purge = list(split_walk_forward(
        df, train_size=20, test_size=10, purge_candles=5, embargo_candles=0
    ))
    
    # With purge, train set should be smaller
    train_no_purge, _ = splits_no_purge[0]
    train_with_purge, _ = splits_with_purge[0]
    
    assert len(train_with_purge) < len(train_no_purge)
    assert len(train_with_purge) == len(train_no_purge) - 5


def test_walk_forward_embargo():
    """Test that embargo removes data from test set."""
    df = pd.DataFrame({
        "timestamp": [datetime(2024, 1, i) for i in range(1, 51)],
        "close": range(50)
    })
    
    splits_no_embargo = list(split_walk_forward(
        df, train_size=20, test_size=10, purge_candles=0, embargo_candles=0
    ))
    
    splits_with_embargo = list(split_walk_forward(
        df, train_size=20, test_size=10, purge_candles=0, embargo_candles=3
    ))
    
    # With embargo, test set should be smaller
    _, test_no_embargo = splits_no_embargo[0]
    _, test_with_embargo = splits_with_embargo[0]
    
    assert len(test_with_embargo) < len(test_no_embargo)
    assert len(test_with_embargo) == len(test_no_embargo) - 3


def test_walk_forward_purge_embargo_combined():
    """Test purge and embargo together prevent leakage."""
    df = pd.DataFrame({
        "timestamp": [datetime(2024, 1, i) for i in range(1, 51)],
        "close": range(50)
    })
    
    purge = 5
    embargo = 3
    
    splits = list(split_walk_forward(
        df, train_size=20, test_size=10,
        purge_candles=purge, embargo_candles=embargo
    ))
    
    train, test = splits[0]
    
    # Verify sizes
    assert len(train) == 20 - purge
    assert len(test) == 10 - embargo
    
    # Verify no overlap: train should end before test starts
    # (accounting for embargo offset)
    assert train["close"].max() < test["close"].min()


def test_walk_forward_yields_multiple_splits():
    """Test that walk-forward produces multiple splits."""
    df = pd.DataFrame({
        "timestamp": [datetime(2024, 1, i) for i in range(1, 101)],
        "close": range(100)
    })
    
    splits = list(split_walk_forward(
        df, train_size=30, test_size=10,
        purge_candles=0, embargo_candles=0
    ))
    
    # With 100 candles, 30 train, 10 test, step of 10: should get 7 splits
    # start=0: train 0-29, test 30-39
    # start=10: train 10-39, test 40-49
    # start=20: train 20-49, test 50-59
    # ... up to start=60
    assert len(splits) >= 6
