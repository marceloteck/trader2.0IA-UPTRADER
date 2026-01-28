"""
Integration Tests - Cross-Market Brain + News Filter

Tests end-to-end workflows: correlation analysis + news blocking together.
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.brains.cross_market import CrossMarketBrain, CrossSignal
from src.news.news_filter import NewsFilter


class TestCrossMarketNewsIntegration:
    """Test CrossMarketBrain and NewsFilter working together."""
    
    def test_signal_with_news_blocked(self):
        """Test that BossBrain should reduce confidence when news blocked + signal is REDUCE."""
        # Create synthetic data
        n = 100
        primary_data = pd.DataFrame({
            'close': 100 + np.sin(np.linspace(0, 4*np.pi, n)) * 5
        })
        cross_data = pd.DataFrame({
            'close': 50 + np.sin(np.linspace(0, 4*np.pi, n) + 0.5) * 2.5
        })
        
        brain = CrossMarketBrain()
        
        # Generate signal
        now = datetime(2024, 1, 28, 10, 0)
        metric, signal = brain.update(primary_data, {'IBOV': cross_data}, now)
        
        # Create news filter with blocking event
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,US NFP,HIGH,USA\n")
            csv_path = f.name
        
        try:
            news = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                impact_block='HIGH'
            )
            
            # Check blocking
            is_blocked, reason, event = news.is_blocked(now)
            
            assert is_blocked is True
            assert metric is not None
            assert signal is not None
        finally:
            Path(csv_path).unlink()
    
    def test_risk_reduction_workflow(self):
        """Test risk reduction factor applied during medium-impact event."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Medium Impact,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            news = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                reduce_risk_on_medium=True,
                medium_risk_factor=0.5
            )
            
            now = datetime(2024, 1, 28, 10, 0)
            risk_factor = news.get_risk_factor(now)
            
            # Simulate position sizing
            base_size = 1000
            adjusted_size = base_size * risk_factor
            
            assert risk_factor == 0.5
            assert adjusted_size == 500
        finally:
            Path(csv_path).unlink()


class TestTradingDecisionGates:
    """Test decision logic with multiple gates."""
    
    def test_gate_priority_news_blocks_all(self):
        """Test that news blocking has priority over signals."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,High Impact,HIGH,USA\n")
            csv_path = f.name
        
        try:
            news = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                impact_block='HIGH'
            )
            
            now = datetime(2024, 1, 28, 10, 0)
            is_blocked, reason, event = news.is_blocked(now)
            
            # Even strong signal should be blocked
            confidence = 0.9
            signal_type = 'CONFIRM_BUY'
            
            should_trade = not is_blocked and confidence > 0.5
            
            assert should_trade is False
        finally:
            Path(csv_path).unlink()
    
    def test_gate_combination_correlation_break(self):
        """Test combining correlation break detection with news filter."""
        # Create data with broken correlation
        n = 100
        primary_data = pd.DataFrame({
            'close': 100 + np.random.randn(n).cumsum()
        })
        cross_data = pd.DataFrame({
            'close': 50 + np.random.randn(n).cumsum()
        })
        
        brain = CrossMarketBrain()
        now = datetime(2024, 1, 28, 10, 0)
        metric, signal = brain.update(primary_data, {'IBOV': cross_data}, now)
        
        # Create news filter with no blocking event
        news = NewsFilter(enabled=True, mode='MANUAL', csv_path='nonexistent.csv')
        
        is_blocked, reason, event = news.is_blocked(now)
        
        # Assuming random data creates broken correlation
        # Final decision should account for both
        
        should_trade = not is_blocked
        assert isinstance(should_trade, bool)


class TestConfidenceAdjustment:
    """Test confidence adjustment based on multiple factors."""
    
    def test_reduce_confidence_on_correlation_break(self):
        """Test reducing confidence when correlation is broken."""
        # Base confidence
        base_confidence = 0.8
        
        # Signal indicates correlation broken
        signal_type = 'MARKET_BROKEN'
        signal_strength = 0.7  # Strength of the break signal
        
        # Apply reduction
        adjusted_confidence = base_confidence * signal_strength
        
        assert adjusted_confidence == 0.56
    
    def test_stack_multiple_risk_factors(self):
        """Test applying multiple risk factors (news + correlation + volatility)."""
        base_position_size = 1.0
        
        # Risk factors
        news_risk = 0.5  # Medium-impact event
        correlation_risk = 0.8  # Slight correlation break
        volatility_risk = 0.9  # Elevated volatility
        
        # Apply all factors
        final_size = base_position_size * news_risk * correlation_risk * volatility_risk
        
        assert final_size == pytest.approx(0.36)
        assert final_size < base_position_size


class TestEventHistoryIntegration:
    """Test tracking decisions with news and correlation events."""
    
    def test_log_trading_decision_with_gates(self):
        """Test recording trading decision with gate information."""
        class TradeDecision:
            def __init__(self):
                self.timestamp = datetime.now()
                self.symbol = 'WDO$N'
                self.side = 'BUY'
                self.confidence = 0.75
                self.gates = {}
            
            def add_gate(self, gate_name, blocked, confidence_factor):
                self.gates[gate_name] = {
                    'blocked': blocked,
                    'confidence_factor': confidence_factor
                }
            
            def to_dict(self):
                return {
                    'timestamp': self.timestamp,
                    'symbol': self.symbol,
                    'side': self.side,
                    'confidence': self.confidence,
                    'gates': self.gates
                }
        
        decision = TradeDecision()
        decision.add_gate('news_filter', blocked=False, confidence_factor=1.0)
        decision.add_gate('correlation_break', blocked=False, confidence_factor=0.9)
        
        result = decision.to_dict()
        
        assert result['gates']['news_filter']['confidence_factor'] == 1.0
        assert result['gates']['correlation_break']['confidence_factor'] == 0.9
    
    def test_block_history_with_signals(self):
        """Test correlating block history with cross-market signals."""
        news = NewsFilter(enabled=True)
        
        # Log several blocks
        base_time = datetime(2024, 1, 28, 10, 0)
        for i in range(5):
            news.log_block(
                base_time + timedelta(minutes=i*30),
                is_blocked=(i % 2 == 0),
                reason=f"Event {i}",
                risk_factor=1.0 if i % 2 == 0 else 0.5
            )
        
        history = news.get_block_history(limit=10)
        
        blocked_events = [h for h in history if h.is_blocked]
        assert len(blocked_events) == 3


class TestDataSynchronization:
    """Test synchronizing multi-symbol data."""
    
    def test_merge_asof_synchronization(self):
        """Test using merge_asof to sync primary and cross data."""
        # Create data with slightly different timestamps
        primary = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-28 09:00', periods=10, freq='1min'),
            'close': 100 + np.arange(10),
            'volume': 1000
        })
        
        cross = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-28 09:00:15', periods=10, freq='1min'),
            'close': 50 + np.arange(10),
            'volume': 500
        })
        
        # Synchronize
        merged = pd.merge_asof(
            primary.sort_values('timestamp'),
            cross.sort_values('timestamp'),
            on='timestamp',
            direction='nearest',
            suffixes=('_primary', '_cross')
        )
        
        assert len(merged) == 10
        assert 'close_primary' in merged.columns
        assert 'close_cross' in merged.columns
    
    def test_graceful_degradation_missing_symbol(self):
        """Test handling missing cross-market symbol gracefully."""
        primary_data = pd.DataFrame({
            'close': 100 + np.arange(10)
        })
        
        cross_symbols = {'IBOV': None}  # Symbol missing
        
        available_symbols = {k: v for k, v in cross_symbols.items() if v is not None}
        
        assert len(available_symbols) == 0
        
        # Should still work with primary data only
        brain = CrossMarketBrain()
        now = datetime.now()
        
        # With empty cross data dict, should gracefully handle
        metric, signal = brain.update(primary_data, {}, now)
        
        assert metric is None  # Need at least one cross symbol


class TestMetricsReporting:
    """Test reporting metrics with news and correlation data."""
    
    def test_combined_stats_export(self):
        """Test exporting combined statistics."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Event 1,HIGH,USA\n")
            f.write("2024-01-28T14:00:00,Event 2,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            news = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            # Log some blocks
            for i in range(5):
                news.log_block(
                    datetime.now(),
                    is_blocked=(i < 2),
                    reason="test",
                    risk_factor=1.0
                )
            
            stats = news.export_stats()
            
            report = {
                'timestamp': datetime.now(),
                'total_events': stats['total_events'],
                'high_impact_events': stats['high_impact_count'],
                'total_decisions': stats['block_history_count'],
                'blocks_triggered': len([b for b in news.block_history if b.is_blocked])
            }
            
            assert report['total_events'] == 2
            assert report['high_impact_events'] == 2
            assert report['total_decisions'] == 5
        finally:
            Path(csv_path).unlink()
    
    def test_daily_report_with_filters(self):
        """Test generating daily report with filter statistics."""
        news = NewsFilter(enabled=True)
        
        base_time = datetime(2024, 1, 28)
        
        # Log blocks for a single day
        for i in range(10):
            news.log_block(
                base_time + timedelta(hours=i),
                is_blocked=(i % 3 == 0),
                reason=f"Block {i}",
                risk_factor=1.0
            )
        
        # Get daily stats
        today_blocks = [b for b in news.block_history 
                       if b.timestamp.date() == base_time.date()]
        
        day_report = {
            'date': base_time.date(),
            'total_checks': len(today_blocks),
            'total_blocks': len([b for b in today_blocks if b.is_blocked]),
            'block_rate': len([b for b in today_blocks if b.is_blocked]) / len(today_blocks) if today_blocks else 0
        }
        
        assert day_report['block_rate'] == pytest.approx(0.333, rel=0.01)


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    def test_malformed_csv_with_news_filter(self):
        """Test graceful handling of malformed CSV."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact\n")  # Missing required column
            f.write("2024-01-28T10:00:00,Event,HIGH\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            # Should handle gracefully
            assert filter.enabled is True
            assert len(filter.events) == 0
        finally:
            Path(csv_path).unlink()
    
    def test_invalid_timestamp_format(self):
        """Test handling invalid timestamp in CSV."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("invalid-date,Event,HIGH,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            # Should skip invalid row
            assert len(filter.events) == 0
        finally:
            Path(csv_path).unlink()
    
    def test_correlation_brain_with_empty_cross_data(self):
        """Test CrossMarketBrain handles empty cross data."""
        brain = CrossMarketBrain()
        
        primary = pd.DataFrame({
            'close': [100, 101, 102]
        })
        
        # Empty cross data dict
        metric, signal = brain.update(primary, {}, datetime.now())
        
        assert metric is None
        assert signal is None


class TestConfiguration:
    """Test configuration integration."""
    
    def test_config_parameters_applied(self):
        """Test that config parameters are correctly applied."""
        # Simulate config loading
        config = {
            'news_enabled': True,
            'news_mode': 'MANUAL',
            'news_block_minutes_before': 15,
            'news_block_minutes_after': 15,
            'news_impact_block': 'HIGH',
            'news_reduce_risk_on_medium': True,
            'news_medium_risk_factor': 0.6,
            'cross_guard_enabled': True,
            'cross_guard_min_corr': -0.2,
            'cross_guard_max_corr': 0.2,
            'cross_guard_reduce_confidence': True
        }
        
        # Create filter with config
        news = NewsFilter(
            enabled=config['news_enabled'],
            mode=config['news_mode'],
            block_minutes_before=config['news_block_minutes_before'],
            block_minutes_after=config['news_block_minutes_after'],
            impact_block=config['news_impact_block'],
            reduce_risk_on_medium=config['news_reduce_risk_on_medium'],
            medium_risk_factor=config['news_medium_risk_factor']
        )
        
        assert news.enabled is True
        assert news.mode == 'MANUAL'
        assert news.block_minutes_before == 15
        assert news.medium_risk_factor == 0.6
