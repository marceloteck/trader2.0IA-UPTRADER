"""
News Filter - Economic Calendar Integration

Two modes:
1. MANUAL: Load news events from CSV file (data/config/news_events.csv)
2. MT5_CALENDAR: Integrate with MT5 Economic Calendar API (if available)

Blocks trades during high-impact news windows and reduces risk on medium-impact events.

CSV Format (data/config/news_events.csv):
    time,title,impact,country
    2024-01-28T09:30:00,NFPR (USA),HIGH,USA
    2024-01-28T14:00:00,SELIC Decision (BR),HIGH,BR
    2024-01-30T10:00:00,Inflation (BR),MEDIUM,BR
    ...

Usage:
    filter = NewsFilter(
        enabled=True,
        mode='MANUAL',
        csv_path='data/config/news_events.csv',
        block_minutes_before=10,
        block_minutes_after=10,
        impact_block='HIGH',
        reduce_risk_on_medium=True,
        medium_risk_factor=0.5
    )
    
    # Check if blocked
    is_blocked, reason, next_event = filter.is_blocked(now)
    if is_blocked:
        print(f"Trading blocked: {reason}")
    
    # Get risk factor
    risk_factor = filter.get_risk_factor(now)  # 1.0 or 0.5 or other
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class NewsEvent:
    """Economic calendar event."""
    timestamp: datetime
    title: str
    impact: str  # HIGH, MEDIUM, LOW
    country: str = "XX"
    
    def __hash__(self):
        return hash((self.timestamp, self.title, self.impact))
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'title': self.title,
            'impact': self.impact,
            'country': self.country
        }


@dataclass
class NewsBlock:
    """Record of a trade being blocked by news."""
    timestamp: datetime
    is_blocked: bool
    reason: str  # Why blocked or why allowed
    event: Optional[NewsEvent] = None
    risk_factor: float = 1.0  # 1.0 = no reduction, 0.5 = 50% reduction
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'is_blocked': self.is_blocked,
            'reason': self.reason,
            'event': self.event.to_dict() if self.event else None,
            'risk_factor': self.risk_factor,
            'details_json': json.dumps({
                'reason': self.reason,
                'event': self.event.to_dict() if self.event else None,
                'risk_factor': self.risk_factor
            })
        }


class NewsFilter:
    """
    Economic calendar filter for safe trading around news events.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        mode: str = 'MANUAL',
        csv_path: str = 'data/config/news_events.csv',
        block_minutes_before: int = 10,
        block_minutes_after: int = 10,
        impact_block: str = 'HIGH',  # Impact level to block (HIGH, MEDIUM, LOW)
        reduce_risk_on_medium: bool = True,
        medium_risk_factor: float = 0.5
    ):
        """
        Initialize NewsFilter.
        
        Args:
            enabled: Enable/disable filter
            mode: 'MANUAL' or 'MT5_CALENDAR'
            csv_path: Path to CSV file with news events
            block_minutes_before: Minutes to block before event
            block_minutes_after: Minutes to block after event
            impact_block: Impact level to block trades (HIGH, MEDIUM, LOW)
            reduce_risk_on_medium: Reduce risk on MEDIUM-impact events
            medium_risk_factor: Risk reduction factor for medium (0-1)
        """
        self.enabled = enabled
        self.mode = mode
        self.csv_path = csv_path
        self.block_minutes_before = block_minutes_before
        self.block_minutes_after = block_minutes_after
        self.impact_block = impact_block
        self.reduce_risk_on_medium = reduce_risk_on_medium
        self.medium_risk_factor = medium_risk_factor
        
        self.events: List[NewsEvent] = []
        self.block_history: List[NewsBlock] = []
        
        # Load events based on mode
        if self.enabled:
            if self.mode == 'MANUAL':
                self._load_from_csv()
            elif self.mode == 'MT5_CALENDAR':
                self._load_from_mt5_calendar()
    
    def _load_from_csv(self):
        """Load events from CSV file."""
        try:
            path = Path(self.csv_path)
            if not path.exists():
                logger.warning(f"News CSV file not found: {self.csv_path}")
                return
            
            df = pd.read_csv(path)
            
            # Parse columns
            if 'time' not in df.columns or 'title' not in df.columns or 'impact' not in df.columns:
                logger.error(f"CSV must have 'time', 'title', 'impact' columns")
                return
            
            for _, row in df.iterrows():
                try:
                    event_time = pd.to_datetime(row['time'])
                    event = NewsEvent(
                        timestamp=event_time,
                        title=str(row['title']).strip(),
                        impact=str(row['impact']).strip().upper(),
                        country=str(row.get('country', 'XX')).strip().upper()
                    )
                    self.events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse news row: {e}")
                    continue
            
            # Sort by timestamp
            self.events = sorted(self.events, key=lambda e: e.timestamp)
            logger.info(f"Loaded {len(self.events)} news events from {self.csv_path}")
            
        except Exception as e:
            logger.error(f"Error loading news CSV: {e}")
    
    def _load_from_mt5_calendar(self):
        """Load events from MT5 Economic Calendar (stub - requires MT5 API)."""
        try:
            # This would require integration with MT5's economic calendar API
            # For now, it's a stub - falls back to CSV if available
            logger.info("MT5_CALENDAR mode: falling back to CSV")
            self._load_from_csv()
        except Exception as e:
            logger.error(f"Error loading MT5 calendar: {e}")
    
    def is_blocked(self, now: datetime) -> Tuple[bool, str, Optional[NewsEvent]]:
        """
        Check if trading is blocked at this moment.
        
        Args:
            now: Current timestamp
            
        Returns:
            (is_blocked: bool, reason: str, next_event: Optional[NewsEvent])
        """
        if not self.enabled:
            return False, "Filter disabled", None
        
        # Find events in blocking window
        blocking_events = self._get_blocking_events(now)
        
        if blocking_events:
            event = blocking_events[0]
            return True, f"Blocked by {event.title} ({event.impact})", event
        
        # Find next event
        next_event = self._get_next_event(now)
        if next_event:
            minutes_until = (next_event.timestamp - now).total_seconds() / 60
            return False, f"Next event in {minutes_until:.0f} min: {next_event.title}", next_event
        
        return False, "No news events", None
    
    def get_risk_factor(self, now: datetime) -> float:
        """
        Get risk reduction factor for current time.
        Returns 1.0 = no reduction, or 0.5 = 50% position size reduction.
        
        Args:
            now: Current timestamp
            
        Returns:
            Risk factor (1.0 = normal, <1.0 = reduced)
        """
        if not self.enabled:
            return 1.0
        
        # Check for medium-impact events (if enabled)
        if self.reduce_risk_on_medium:
            for event in self.events:
                if event.impact == 'MEDIUM':
                    time_until_event = (event.timestamp - now).total_seconds() / 60
                    time_after_event = (now - event.timestamp).total_seconds() / 60
                    
                    # Within blocking window?
                    if (-self.block_minutes_before <= time_until_event <= 0) or (0 <= time_after_event <= self.block_minutes_after):
                        return self.medium_risk_factor
        
        return 1.0
    
    def _get_blocking_events(self, now: datetime) -> List[NewsEvent]:
        """Get events that would block trading at this moment."""
        blocking = []
        
        # Map impact strings to blocking logic
        impact_levels = {'LOW': 3, 'MEDIUM': 2, 'HIGH': 1}
        block_impact_level = impact_levels.get(self.impact_block, 1)
        
        for event in self.events:
            event_impact_level = impact_levels.get(event.impact, 3)
            
            # Only block if impact >= threshold
            if event_impact_level > block_impact_level:
                continue
            
            # Check timing
            time_until = (event.timestamp - now).total_seconds() / 60
            time_after = (now - event.timestamp).total_seconds() / 60
            
            if (-self.block_minutes_before <= time_until <= 0) or (0 <= time_after <= self.block_minutes_after):
                blocking.append(event)
        
        return blocking
    
    def _get_next_event(self, now: datetime) -> Optional[NewsEvent]:
        """Get next upcoming event."""
        for event in self.events:
            if event.timestamp > now:
                return event
        return None
    
    def log_block(self, now: datetime, is_blocked: bool, reason: str, risk_factor: float = 1.0):
        """Log a block decision for reporting."""
        event = None
        if is_blocked:
            blocking_events = self._get_blocking_events(now)
            if blocking_events:
                event = blocking_events[0]
        
        block = NewsBlock(
            timestamp=now,
            is_blocked=is_blocked,
            reason=reason,
            event=event,
            risk_factor=risk_factor
        )
        self.block_history.append(block)
        
        # Trim history
        if len(self.block_history) > 1000:
            self.block_history = self.block_history[-1000:]
    
    def get_block_history(self, limit: int = 100) -> List[NewsBlock]:
        """Get recent block history."""
        return self.block_history[-limit:]
    
    def get_events_for_date(self, date: datetime) -> List[NewsEvent]:
        """Get all events for a specific date."""
        target_date = date.date()
        return [e for e in self.events if e.timestamp.date() == target_date]
    
    def export_stats(self) -> dict:
        """Export statistics for reporting."""
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'total_events': len(self.events),
            'block_history_count': len(self.block_history),
            'high_impact_count': len([e for e in self.events if e.impact == 'HIGH']),
            'medium_impact_count': len([e for e in self.events if e.impact == 'MEDIUM']),
            'low_impact_count': len([e for e in self.events if e.impact == 'LOW']),
            'recent_blocks': [asdict(b) for b in self.get_block_history(20)]
        }
