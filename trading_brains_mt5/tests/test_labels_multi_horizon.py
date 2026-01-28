"""Tests for L1 label generation."""

import pytest
import pandas as pd
from datetime import datetime
from src.training.dataset import LabelGenerator, TradeLabel


def test_label_generator_buy_tp_hit():
    """Test TP hit detection for BUY."""
    gen = LabelGenerator(horizons=[5])
    
    trades = [
        {
            "timestamp": datetime(2024, 1, 1, 10, 0).timestamp(),
            "side": "BUY",
            "entry_price": 1.0500,
            "tp1": 1.0600,
            "tp2": 1.0700,
            "sl": 1.0400
        }
    ]
    
    candles = [
        {"timestamp": datetime(2024, 1, 1, 10, 0).timestamp(), "o": 1.0500, "h": 1.0510, "l": 1.0490, "c": 1.0505},
        {"timestamp": datetime(2024, 1, 1, 10, 1).timestamp(), "o": 1.0505, "h": 1.0610, "l": 1.0500, "c": 1.0600},
        {"timestamp": datetime(2024, 1, 1, 10, 2).timestamp(), "o": 1.0600, "h": 1.0620, "l": 1.0600, "c": 1.0610},
        {"timestamp": datetime(2024, 1, 1, 10, 3).timestamp(), "o": 1.0610, "h": 1.0620, "l": 1.0600, "c": 1.0610},
        {"timestamp": datetime(2024, 1, 1, 10, 4).timestamp(), "o": 1.0610, "h": 1.0620, "l": 1.0600, "c": 1.0610},
    ]
    
    labels = gen.generate_labels(trades, candles, "EURUSD")
    
    assert len(labels) == 1
    assert labels[0].tp1_hit[5] is True
    assert labels[0].mfe[5] > 0


def test_label_generator_sell_mae_calculation():
    """Test MAE calculation for SELL."""
    gen = LabelGenerator(horizons=[5])
    
    trades = [
        {
            "timestamp": datetime(2024, 1, 1, 10, 0).timestamp(),
            "side": "SELL",
            "entry_price": 1.0500,
            "tp1": 1.0400,
            "tp2": 1.0300,
            "sl": 1.0600
        }
    ]
    
    candles = [
        {"timestamp": datetime(2024, 1, 1, 10, 0).timestamp(), "o": 1.0500, "h": 1.0505, "l": 1.0495, "c": 1.0500},
        {"timestamp": datetime(2024, 1, 1, 10, 1).timestamp(), "o": 1.0500, "h": 1.0550, "l": 1.0480, "c": 1.0490},  # High
        {"timestamp": datetime(2024, 1, 1, 10, 2).timestamp(), "o": 1.0490, "h": 1.0495, "l": 1.0480, "c": 1.0485},
        {"timestamp": datetime(2024, 1, 1, 10, 3).timestamp(), "o": 1.0485, "h": 1.0490, "l": 1.0480, "c": 1.0480},
        {"timestamp": datetime(2024, 1, 1, 10, 4).timestamp(), "o": 1.0480, "h": 1.0485, "l": 1.0480, "c": 1.0480},
    ]
    
    labels = gen.generate_labels(trades, candles, "EURUSD")
    
    assert len(labels) == 1
    # MAE should be distance to high (1.0550 - 1.0500) * 10000
    assert labels[0].mae[5] > 0
    assert labels[0].tp1_hit[5] is True


def test_label_generator_quality_score():
    """Test quality score calculation."""
    gen = LabelGenerator(
        horizons=[5],
        mfe_weight=1.0,
        mae_weight=0.5
    )
    
    trades = [
        {
            "timestamp": datetime(2024, 1, 1, 10, 0).timestamp(),
            "side": "BUY",
            "entry_price": 1.0500,
            "tp1": 1.0600,
            "tp2": 1.0700,
            "sl": 1.0400
        }
    ]
    
    candles = [
        {"timestamp": datetime(2024, 1, 1, 10, 0).timestamp(), "o": 1.0500, "h": 1.0510, "l": 1.0490, "c": 1.0505},
        {"timestamp": datetime(2024, 1, 1, 10, 1).timestamp(), "o": 1.0505, "h": 1.0610, "l": 1.0500, "c": 1.0600},
        {"timestamp": datetime(2024, 1, 1, 10, 2).timestamp(), "o": 1.0600, "h": 1.0620, "l": 1.0600, "c": 1.0610},
        {"timestamp": datetime(2024, 1, 1, 10, 3).timestamp(), "o": 1.0610, "h": 1.0620, "l": 1.0600, "c": 1.0610},
        {"timestamp": datetime(2024, 1, 1, 10, 4).timestamp(), "o": 1.0610, "h": 1.0620, "l": 1.0600, "c": 1.0610},
    ]
    
    labels = gen.generate_labels(trades, candles, "EURUSD")
    
    assert len(labels) == 1
    # Quality = 1.0 * MFE - 0.5 * MAE
    quality = labels[0].quality_score[5]
    mfe = labels[0].mfe[5]
    mae = labels[0].mae[5]
    
    assert abs(quality - (1.0 * mfe - 0.5 * mae)) < 0.01


def test_label_generator_get_stats():
    """Test statistics calculation."""
    gen = LabelGenerator(horizons=[5])
    
    trades = [
        {
            "timestamp": datetime(2024, 1, 1, 10, 0).timestamp(),
            "side": "BUY",
            "entry_price": 1.0500,
            "tp1": 1.0600,
            "tp2": 1.0700,
            "sl": 1.0400
        },
        {
            "timestamp": datetime(2024, 1, 1, 10, 10).timestamp(),
            "side": "BUY",
            "entry_price": 1.0600,
            "tp1": 1.0700,
            "tp2": 1.0800,
            "sl": 1.0500
        }
    ]
    
    candles = []
    for i in range(10):
        ts = datetime(2024, 1, 1, 10, i).timestamp()
        candles.append({"timestamp": ts, "o": 1.0500 + i * 0.0001, "h": 1.0510 + i * 0.0001, "l": 1.0490 + i * 0.0001, "c": 1.0505 + i * 0.0001})
    
    labels = gen.generate_labels(trades, candles, "EURUSD")
    stats = gen.get_stats(labels, 5)
    
    assert stats["total_labels"] == 2
    assert "tp1_hit_rate" in stats
    assert "avg_mfe" in stats
