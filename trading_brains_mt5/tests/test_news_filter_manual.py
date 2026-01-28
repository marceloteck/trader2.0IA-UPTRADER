"""
Tests for NewsFilter - Economic Calendar Filtering

Tests MANUAL mode CSV parsing and blocking logic.
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import pytest

from src.news.news_filter import NewsEvent, NewsBlock, NewsFilter


class TestNewsEventCreation:
    """Test NewsEvent dataclass."""
    
    def test_event_creation(self):
        """Test creating a news event."""
        event = NewsEvent(
            timestamp=datetime(2024, 1, 28, 9, 30),
            title="US Non-Farm Payroll",
            impact="HIGH",
            country="USA"
        )
        
        assert event.timestamp == datetime(2024, 1, 28, 9, 30)
        assert event.title == "US Non-Farm Payroll"
        assert event.impact == "HIGH"
        assert event.country == "USA"
    
    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = NewsEvent(
            timestamp=datetime(2024, 1, 28, 9, 30),
            title="US NFP",
            impact="HIGH",
            country="USA"
        )
        
        event_dict = event.to_dict()
        
        assert event_dict['timestamp'] == datetime(2024, 1, 28, 9, 30)
        assert event_dict['title'] == "US NFP"
        assert event_dict['impact'] == "HIGH"


class TestNewsFilterInitialization:
    """Test NewsFilter initialization and mode handling."""
    
    def test_initialization_disabled(self):
        """Test that disabled filter doesn't load events."""
        filter = NewsFilter(enabled=False)
        assert len(filter.events) == 0
    
    def test_initialization_manual_mode(self):
        """Test initialization in MANUAL mode."""
        filter = NewsFilter(
            enabled=True,
            mode='MANUAL',
            csv_path='nonexistent.csv'
        )
        
        assert filter.enabled is True
        assert filter.mode == 'MANUAL'
        assert len(filter.events) == 0  # File doesn't exist


class TestCSVParsing:
    """Test CSV file parsing."""
    
    def test_valid_csv_parsing(self):
        """Test parsing valid CSV file."""
        # Create temporary CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T09:30:00,US Non-Farm Payroll,HIGH,USA\n")
            f.write("2024-01-29T10:00:00,Brazil SELIC Decision,HIGH,BR\n")
            f.write("2024-01-30T14:00:00,ECB Meeting,MEDIUM,EUR\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            assert len(filter.events) == 3
            assert filter.events[0].title == "US Non-Farm Payroll"
            assert filter.events[0].impact == "HIGH"
            assert filter.events[1].country == "BR"
        finally:
            Path(csv_path).unlink()
    
    def test_csv_with_missing_country(self):
        """Test CSV parsing when country column is missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact\n")
            f.write("2024-01-28T09:30:00,US NFP,HIGH\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            assert len(filter.events) == 1
            assert filter.events[0].country == "XX"  # Default
        finally:
            Path(csv_path).unlink()
    
    def test_csv_missing_required_column(self):
        """Test handling of CSV missing required columns."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title\n")  # Missing 'impact'
            f.write("2024-01-28T09:30:00,US NFP\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            assert len(filter.events) == 0  # Should not parse
        finally:
            Path(csv_path).unlink()


class TestBlockingLogic:
    """Test trading blocking logic."""
    
    def test_not_blocked_when_disabled(self):
        """Test that disabled filter doesn't block trades."""
        filter = NewsFilter(enabled=False)
        is_blocked, reason, event = filter.is_blocked(datetime.now())
        
        assert is_blocked is False
        assert reason == "Filter disabled"
    
    def test_blocked_during_event(self):
        """Test that trades are blocked during event window."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,US NFP,HIGH,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                impact_block='HIGH'
            )
            
            # 5 minutes before event
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=5)
            
            is_blocked, reason, event = filter.is_blocked(check_time)
            
            assert is_blocked is True
            assert "Blocked by" in reason
        finally:
            Path(csv_path).unlink()
    
    def test_not_blocked_outside_window(self):
        """Test that trades are allowed outside event window."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,US NFP,HIGH,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                impact_block='HIGH'
            )
            
            # 30 minutes before event (outside window)
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=30)
            
            is_blocked, reason, event = filter.is_blocked(check_time)
            
            assert is_blocked is False
        finally:
            Path(csv_path).unlink()
    
    def test_blocking_respects_impact_level(self):
        """Test that blocking respects impact level threshold."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Medium Event,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            # Only block HIGH impact
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                impact_block='HIGH'  # Only HIGH
            )
            
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=5)
            
            is_blocked, reason, event = filter.is_blocked(check_time)
            
            # Should NOT block MEDIUM when only HIGH is blocked
            assert is_blocked is False
        finally:
            Path(csv_path).unlink()


class TestRiskFactorReduction:
    """Test risk factor reduction for medium-impact events."""
    
    def test_no_reduction_when_disabled(self):
        """Test no reduction when reduce_risk_on_medium is False."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Medium Event,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                reduce_risk_on_medium=False,  # Disabled
                medium_risk_factor=0.5
            )
            
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=5)
            
            risk_factor = filter.get_risk_factor(check_time)
            
            assert risk_factor == 1.0
        finally:
            Path(csv_path).unlink()
    
    def test_medium_impact_reduction(self):
        """Test risk reduction during medium-impact event."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Medium Event,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                reduce_risk_on_medium=True,
                medium_risk_factor=0.5
            )
            
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=5)
            
            risk_factor = filter.get_risk_factor(check_time)
            
            assert risk_factor == 0.5  # 50% reduction
        finally:
            Path(csv_path).unlink()
    
    def test_risk_factor_outside_window(self):
        """Test no reduction outside event window."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T10:00:00,Medium Event,MEDIUM,USA\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path,
                block_minutes_before=10,
                block_minutes_after=10,
                reduce_risk_on_medium=True,
                medium_risk_factor=0.5
            )
            
            event_time = datetime(2024, 1, 28, 10, 0)
            check_time = event_time - timedelta(minutes=30)  # Far before
            
            risk_factor = filter.get_risk_factor(check_time)
            
            assert risk_factor == 1.0
        finally:
            Path(csv_path).unlink()


class TestBlockHistoryTracking:
    """Test logging and tracking of block decisions."""
    
    def test_log_block(self):
        """Test logging a block decision."""
        filter = NewsFilter(enabled=True)
        
        filter.log_block(datetime.now(), is_blocked=True, reason="Test block", risk_factor=1.0)
        
        assert len(filter.block_history) == 1
        assert filter.block_history[0].is_blocked is True
        assert filter.block_history[0].reason == "Test block"
    
    def test_get_block_history(self):
        """Test retrieving block history."""
        filter = NewsFilter(enabled=True)
        
        for i in range(5):
            filter.log_block(
                datetime.now() + timedelta(minutes=i),
                is_blocked=(i % 2 == 0),
                reason=f"Block {i}",
                risk_factor=1.0
            )
        
        history = filter.get_block_history(limit=10)
        assert len(history) == 5
    
    def test_history_trimming(self):
        """Test that history is trimmed to max size."""
        filter = NewsFilter(enabled=True)
        
        # Add 1100 records
        for i in range(1100):
            filter.log_block(datetime.now(), is_blocked=False, reason="test", risk_factor=1.0)
        
        # Should be trimmed to 1000
        assert len(filter.block_history) <= 1000


class TestEventQueries:
    """Test querying news events."""
    
    def test_get_events_for_date(self):
        """Test getting events for a specific date."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T09:30:00,Event 1,HIGH,USA\n")
            f.write("2024-01-28T14:00:00,Event 2,MEDIUM,USA\n")
            f.write("2024-01-29T10:00:00,Event 3,HIGH,BR\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            date_28 = datetime(2024, 1, 28)
            events = filter.get_events_for_date(date_28)
            
            assert len(events) == 2
            assert all(e.timestamp.date() == date_28.date() for e in events)
        finally:
            Path(csv_path).unlink()


class TestExportStats:
    """Test statistics export."""
    
    def test_export_stats_basic(self):
        """Test exporting statistics."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("time,title,impact,country\n")
            f.write("2024-01-28T09:30:00,US NFP,HIGH,USA\n")
            f.write("2024-01-28T14:00:00,Brazil SELIC,HIGH,BR\n")
            csv_path = f.name
        
        try:
            filter = NewsFilter(
                enabled=True,
                mode='MANUAL',
                csv_path=csv_path
            )
            
            filter.log_block(datetime.now(), is_blocked=True, reason="test", risk_factor=1.0)
            
            stats = filter.export_stats()
            
            assert stats['enabled'] is True
            assert stats['mode'] == 'MANUAL'
            assert stats['total_events'] == 2
            assert stats['high_impact_count'] == 2
            assert stats['block_history_count'] == 1
        finally:
            Path(csv_path).unlink()
