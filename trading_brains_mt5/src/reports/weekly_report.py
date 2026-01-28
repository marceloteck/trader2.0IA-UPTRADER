"""
Weekly trading report.

Aggregates:
- 7-day statistics
- Equity curve
- Stability metrics
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from .report_utils import ReportGenerator
from .daily_report import DailyReporter


logger = logging.getLogger("trading_brains.weekly_report")


class WeeklyReporter:
    """Generate weekly trading reports."""
    
    def __init__(self, db_path: str, report_dir: str):
        """Initialize reporter."""
        self.db_path = db_path
        self.daily = DailyReporter(db_path, report_dir)
        self.reporter = ReportGenerator(report_dir)
    
    def generate(self, end_date: datetime = None) -> Dict[str, Any]:
        """
        Generate weekly report for 7 days ending on end_date.
        
        Args:
            end_date: End of week (default: today)
        
        Returns:
            Report dict with weekly stats
        """
        if end_date is None:
            end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
        
        start_date = end_date - timedelta(days=6)
        start_date = start_date.replace(hour=0, minute=0, second=0)
        
        # Generate daily reports for each day
        daily_reports = []
        current = start_date
        while current <= end_date:
            daily = self.daily.generate(current)
            daily_reports.append(daily)
            current += timedelta(days=1)
        
        # Aggregate
        report = {
            "week_start": start_date.isoformat(),
            "week_end": end_date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "daily_reports": daily_reports,
            "summary": self._aggregate_stats(daily_reports),
        }
        
        # Save
        week_str = start_date.strftime("%Y-W%W")
        self.reporter.save_json(f"{week_str}_weekly_report.json", report)
        
        return report
    
    def _aggregate_stats(self, daily_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate daily stats."""
        stats = {
            "total_trades": 0,
            "total_pnl": 0.0,
            "avg_daily_pnl": 0.0,
            "win_days": 0,
            "loss_days": 0,
            "breakeven_days": 0,
            "best_day": None,
            "worst_day": None,
            "best_day_pnl": 0.0,
            "worst_day_pnl": 0.0,
            "winrate": 0.0,
        }
        
        if not daily_reports:
            return stats
        
        for daily in daily_reports:
            daily_stats = daily.get("statistics", {})
            daily_pnl = daily_stats.get("total_pnl", 0)
            
            stats["total_trades"] += daily_stats.get("total_trades", 0)
            stats["total_pnl"] += daily_pnl
            
            if daily_pnl > 0:
                stats["win_days"] += 1
            elif daily_pnl < 0:
                stats["loss_days"] += 1
            else:
                stats["breakeven_days"] += 1
            
            if daily_pnl > stats["best_day_pnl"]:
                stats["best_day_pnl"] = daily_pnl
                stats["best_day"] = daily["date"]
            
            if daily_pnl < stats["worst_day_pnl"]:
                stats["worst_day_pnl"] = daily_pnl
                stats["worst_day"] = daily["date"]
        
        days = len(daily_reports)
        stats["avg_daily_pnl"] = stats["total_pnl"] / days if days > 0 else 0
        
        if stats["total_trades"] > 0:
            stats["winrate"] = sum(
                d.get("statistics", {}).get("wins", 0) 
                for d in daily_reports
            ) / stats["total_trades"] * 100
        
        return stats
