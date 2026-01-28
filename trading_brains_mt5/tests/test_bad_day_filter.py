"""Tests for L1 bad day filter."""

import pytest
from datetime import datetime, timedelta
from src.live import BadDayFilter


def test_bad_day_filter_consecutive_losses():
    """Test pause on consecutive losses."""
    filter = BadDayFilter(
        enabled=True,
        consecutive_losses_max=2
    )
    
    now = datetime.utcnow()
    
    # First loss
    paused, reason = filter.check(-10.0, now)
    assert not paused
    
    # Second loss (should trigger pause)
    paused, reason = filter.check(-20.0, now + timedelta(minutes=5))
    assert paused
    assert "CONSECUTIVE" in reason


def test_bad_day_filter_loss_limit():
    """Test pause on loss limit."""
    filter = BadDayFilter(
        enabled=True,
        first_n_trades=3,
        max_daily_loss=-100.0
    )
    
    now = datetime.utcnow()
    
    # Trade 1: -40
    filter.check(-40.0, now)
    # Trade 2: -40
    filter.check(-40.0, now + timedelta(minutes=1))
    # Trade 3: -30 (total -110, exceeds limit)
    paused, reason = filter.check(-30.0, now + timedelta(minutes=2))
    
    assert paused
    assert "LOSS_LIMIT" in reason


def test_bad_day_filter_respects_enabled():
    """Test that disabled filter doesn't pause."""
    filter = BadDayFilter(enabled=False)
    
    paused, _ = filter.check(-100.0)
    assert not paused


def test_bad_day_filter_reset():
    """Test reset clears state."""
    filter = BadDayFilter(consecutive_losses_max=2)
    
    filter.check(-10.0)
    filter.check(-20.0)
    
    stats_before = filter.get_stats()
    assert stats_before.trades_count == 2
    
    filter.reset()
    
    stats_after = filter.get_stats()
    assert stats_after.trades_count == 0


def test_bad_day_filter_new_day_resets():
    """Test that new day resets statistics."""
    filter = BadDayFilter(consecutive_losses_max=5)
    
    today = datetime.utcnow()
    tomorrow = today + timedelta(days=1)
    
    filter.check(-10.0, today)
    stats_today = filter.get_stats()
    assert stats_today.trades_count == 1
    
    # Check on tomorrow
    filter.check(+10.0, tomorrow)
    stats_tomorrow = filter.get_stats()
    
    assert stats_tomorrow.trades_count == 1
    assert stats_tomorrow.consecutive_losses == 0


def test_bad_day_filter_as_dict():
    """Test export to dict."""
    filter = BadDayFilter(
        enabled=True,
        first_n_trades=5,
        max_daily_loss=-150.0,
        min_winrate=0.5
    )
    
    config = filter.as_dict()
    
    assert config["enabled"] is True
    assert config["first_n_trades"] == 5
    assert config["max_daily_loss"] == -150.0
