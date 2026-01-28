"""
Tests for CrossMarketBrain - Correlation, Spread, and Z-Score Detection
"""

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.brains.cross_market import CrossMarketBrain, CrossMetric, CrossSignal


class TestCrossMarketBrainBasics:
    """Test CrossMarketBrain initialization and basic functionality."""
    
    def test_initialization(self):
        """Test brain initialization."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N', 'IBOV'],
            corr_windows=[50, 200],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200
        )
        
        assert brain.primary_symbol == 'WIN$N'
        assert brain.cross_symbols == ['WDO$N', 'IBOV']
        assert brain.corr_windows == [50, 200]
        assert brain.z_threshold == 2.0
    
    def test_insufficient_data_returns_none(self):
        """Test that insufficient data returns None."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 200],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            min_data_points=100
        )
        
        # Create insufficient data
        primary_ohlc = pd.DataFrame({
            'close': [100, 101, 102, 103, 104]  # Only 5 points
        })
        cross_data = {'WDO$N': pd.DataFrame({'close': [50, 50.5, 51, 51.5, 52]})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is None
        assert signal is None


class TestCorrelationCalculation:
    """Test rolling correlation calculations."""
    
    def test_positive_correlation(self):
        """Test correlation when series move together."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            min_data_points=10
        )
        
        # Create perfectly correlated data
        n = 150
        x = np.linspace(0, 4*np.pi, n)
        primary_close = 100 + 10*np.sin(x)
        cross_close = 50 + 5*np.sin(x)  # Same pattern, scaled
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.corr_fast is not None
        assert metric.corr_slow is not None
        assert metric.corr_fast > 0.8  # Should be highly positive
    
    def test_negative_correlation(self):
        """Test correlation when series move opposite."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            min_data_points=10
        )
        
        # Create oppositely correlated data
        n = 150
        x = np.linspace(0, 4*np.pi, n)
        primary_close = 100 + 10*np.sin(x)
        cross_close = 50 - 5*np.sin(x)  # Opposite pattern
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.corr_fast is not None
        assert metric.corr_fast < -0.8  # Should be highly negative


class TestSpreadAndZScore:
    """Test spread calculation and Z-score detection."""
    
    def test_normal_spread(self):
        """Test spread within normal range."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Create data with normal spread
        n = 100
        primary_close = np.array([100 + np.random.normal(0, 0.5) for _ in range(n)])
        cross_close = np.array([50 + np.random.normal(0, 0.25) for _ in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.zscore is not None
        assert abs(metric.zscore) < 2.0  # Should be within normal range
        assert signal.signal_type == 'NEUTRAL'
    
    def test_high_spread_detection(self):
        """Test detection of high (over-extended) spread."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Create data where primary is temporarily overpriced
        n = 100
        primary_close = np.array([100 + i*0.1 for i in range(n)])
        cross_close = np.array([50 + i*0.05 for i in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.zscore is not None
        assert metric.flags.get('spread_high', False)
        assert 'REDUCE_BUY' in signal.signal_type or 'CONFIRM_SELL' in signal.signal_type
    
    def test_low_spread_detection(self):
        """Test detection of low (under-extended) spread."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Create data where primary is temporarily underpriced
        n = 100
        primary_close = np.array([100 - i*0.1 for i in range(n)])
        cross_close = np.array([50 - i*0.05 for i in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.zscore is not None
        assert metric.flags.get('spread_low', False)
        assert 'CONFIRM_BUY' in signal.signal_type or 'REDUCE_SELL' in signal.signal_type


class TestCorrelationBreakDetection:
    """Test correlation break detection."""
    
    def test_correlation_break_flag(self):
        """Test that correlation break is flagged."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            corr_broken_band=(-0.2, 0.2),  # Outside -0.2 to 0.2 is "broken"
            min_data_points=10
        )
        
        # Create uncorrelated (broken) data
        n = 150
        primary_close = np.array([100 + np.random.normal(0, 2) for _ in range(n)])
        cross_close = np.array([50 + np.random.normal(0, 2) for _ in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.corr_fast is not None
        
        # If corr is in broken band, flag should be set
        if -0.2 <= metric.corr_fast <= 0.2:
            assert metric.flags.get('corr_broken', False)
    
    def test_market_broken_signal(self):
        """Test MARKET_BROKEN signal when correlation is broken."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            corr_broken_band=(-0.05, 0.05),  # Very tight band
            min_data_points=10
        )
        
        # Create uncorrelated data
        n = 150
        np.random.seed(42)
        primary_close = np.array([100 + np.random.normal(0, 1) for _ in range(n)])
        cross_close = np.array([50 + np.random.normal(0, 1) for _ in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        # Likely to have low correlation with tight band
        if metric and metric.flags.get('corr_broken', False):
            assert signal.signal_type == 'MARKET_BROKEN'
            assert signal.strength < 0.5  # Should reduce confidence


class TestBetaCalculation:
    """Test beta regression coefficient calculation."""
    
    def test_beta_calculation(self):
        """Test beta is calculated correctly."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=100,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Create data with known beta relationship
        n = 100
        cross_close = np.array(range(100, 100+n), dtype=float)
        primary_close = 50 + 2 * cross_close  # beta = 2
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is not None
        assert metric.beta is not None
        # Beta should be close to 2 (with some estimation error)
        assert 1.8 < metric.beta < 2.2


class TestSignalGeneration:
    """Test signal generation logic."""
    
    def test_signal_types(self):
        """Test that signals are generated with correct types."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        n = 100
        primary_close = np.array([100 + np.random.normal(0, 1) for _ in range(n)])
        cross_close = np.array([50 + np.random.normal(0, 0.5) for _ in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert signal is not None
        assert signal.signal_type in ['CONFIRM_BUY', 'REDUCE_BUY', 'CONFIRM_SELL', 'REDUCE_SELL', 'MARKET_BROKEN', 'NEUTRAL']
        assert 0 <= signal.strength <= 1.0
        assert isinstance(signal.reasons, list)
    
    def test_signal_strength_reflects_zscore(self):
        """Test that signal strength increases with Z-score magnitude."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Create extreme spread (high Z-score)
        n = 100
        primary_close = np.array([100 + i*0.2 for i in range(n)])
        cross_close = np.array([50 + i*0.05 for i in range(n)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        if signal.signal_type in ['REDUCE_BUY', 'CONFIRM_SELL', 'CONFIRM_BUY', 'REDUCE_SELL']:
            # Strong signal should have higher strength
            assert signal.strength > 0.5


class TestHistoryTracking:
    """Test metric and signal history tracking."""
    
    def test_metric_history_tracking(self):
        """Test that metrics are tracked in history."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Generate multiple updates
        for i in range(3):
            primary_close = np.array([100 + np.random.normal(0, 1) for _ in range(100)])
            cross_close = np.array([50 + np.random.normal(0, 0.5) for _ in range(100)])
            
            primary_ohlc = pd.DataFrame({'close': primary_close})
            cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
            
            brain.update(primary_ohlc, cross_data, datetime.now() + timedelta(minutes=i))
        
        history = brain.get_metric_history('WIN$N')
        assert len(history) == 3
        assert all(isinstance(m, CrossMetric) for m in history)
    
    def test_signal_history_tracking(self):
        """Test that signals are tracked in history."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Generate multiple updates
        for i in range(3):
            primary_close = np.array([100 + np.random.normal(0, 1) for _ in range(100)])
            cross_close = np.array([50 + np.random.normal(0, 0.5) for _ in range(100)])
            
            primary_ohlc = pd.DataFrame({'close': primary_close})
            cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
            
            brain.update(primary_ohlc, cross_data, datetime.now() + timedelta(minutes=i))
        
        history = brain.get_signal_history('WIN$N')
        assert len(history) == 3
        assert all(isinstance(s, CrossSignal) for s in history)


class TestDataValidation:
    """Test handling of invalid data."""
    
    def test_missing_close_column(self):
        """Test that missing 'close' column is handled."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            min_data_points=10
        )
        
        # Missing 'close' column
        primary_ohlc = pd.DataFrame({'open': [100, 101, 102]})
        cross_data = {'WDO$N': pd.DataFrame({'close': [50, 50.5, 51]})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is None
        assert signal is None
    
    def test_empty_dataframe(self):
        """Test that empty DataFrames are handled."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=200,
            z_threshold=2.0,
            beta_window=200,
            min_data_points=10
        )
        
        primary_ohlc = pd.DataFrame({'close': []})
        cross_data = {'WDO$N': pd.DataFrame({'close': [50, 50.5, 51]})}
        
        metric, signal = brain.update(primary_ohlc, cross_data, datetime.now())
        
        assert metric is None
        assert signal is None


class TestExportStats:
    """Test statistics export."""
    
    def test_export_stats(self):
        """Test that stats can be exported."""
        brain = CrossMarketBrain(
            primary_symbol='WIN$N',
            cross_symbols=['WDO$N'],
            corr_windows=[50, 100],
            spread_window=50,
            z_threshold=2.0,
            beta_window=50,
            min_data_points=10
        )
        
        # Generate an update
        primary_close = np.array([100 + np.random.normal(0, 1) for _ in range(100)])
        cross_close = np.array([50 + np.random.normal(0, 0.5) for _ in range(100)])
        
        primary_ohlc = pd.DataFrame({'close': primary_close})
        cross_data = {'WDO$N': pd.DataFrame({'close': cross_close})}
        
        brain.update(primary_ohlc, cross_data, datetime.now())
        
        stats = brain.export_stats()
        
        assert isinstance(stats, dict)
        assert 'WIN$N' in stats
        assert stats['WIN$N']['metric_count'] > 0
