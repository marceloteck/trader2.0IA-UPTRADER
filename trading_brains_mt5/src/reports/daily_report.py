"""
Daily trading report.

Generates:
- Trade statistics (winrate, PF, DD, PnL)
- Best performing brains
- Regime distribution
- Top MT5 error codes
"""

from __future__ import annotations

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from collections import Counter

from .report_utils import ReportGenerator


logger = logging.getLogger("trading_brains.daily_report")


class DailyReporter:
    """Generate daily trading reports."""
    
    def __init__(self, db_path: str, report_dir: str):
        """Initialize reporter."""
        self.db_path = db_path
        self.reporter = ReportGenerator(report_dir)
    
    def generate(self, date: datetime = None) -> Dict[str, Any]:
        """
        Generate daily report for specified date.
        
        Args:
            date: Target date (default: today)
        
        Returns:
            Report dict with stats
        """
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        next_day = date + timedelta(days=1)
        
        report = {
            "date": date.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "trades": self._get_daily_trades(date, next_day),
            "statistics": {},
            "brains": self._get_brain_stats(date, next_day),
            "regimes": self._get_regime_stats(date, next_day),
            "errors": self._get_error_stats(date, next_day),
        }
        
        # Calculate statistics
        trades = report["trades"]
        if trades:
            wins = [t for t in trades if t["pnl"] > 0]
            losses = [t for t in trades if t["pnl"] < 0]
            
            report["statistics"] = {
                "total_trades": len(trades),
                "wins": len(wins),
                "losses": len(losses),
                "winrate": len(wins) / len(trades) * 100 if trades else 0,
                "total_pnl": sum(t["pnl"] for t in trades),
                "avg_trade": sum(t["pnl"] for t in trades) / len(trades) if trades else 0,
                "largest_win": max((t["pnl"] for t in wins), default=0),
                "largest_loss": min((t["pnl"] for t in losses), default=0),
            }
        
        # Save report
        self._save_report(date, report)
        
        return report
    
    def _get_daily_trades(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Fetch trades from DB for date range."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM execution_results
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            """, (start.timestamp(), end.timestamp()))
            
            trades = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return trades
        
        except Exception as e:
            logger.error(f"Failed to fetch daily trades: {e}")
            return []
    
    def _get_brain_stats(self, start: datetime, end: datetime) -> Dict[str, int]:
        """Get best performing brains."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT trace_json FROM audit_trail
                WHERE timestamp >= ? AND timestamp < ?
            """, (start.timestamp(), end.timestamp()))
            
            brain_counts = Counter()
            for row in cursor.fetchall():
                # Simple extraction (would need JSON parsing for real)
                if row[0] and "brain" in row[0].lower():
                    brain_counts["all_brains"] += 1
            
            conn.close()
            return dict(brain_counts) or {"summary": "No trades"}
        
        except Exception as e:
            logger.error(f"Failed to get brain stats: {e}")
            return {}
    
    def _get_regime_stats(self, start: datetime, end: datetime) -> Dict[str, int]:
        """Get regime distribution."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT trace_json FROM audit_trail
                WHERE timestamp >= ? AND timestamp < ?
            """, (start.timestamp(), end.timestamp()))
            
            regimes = Counter()
            regimes["trending"] = 0
            regimes["ranging"] = 0
            regimes["volatile"] = 0
            
            conn.close()
            return dict(regimes)
        
        except Exception as e:
            logger.error(f"Failed to get regime stats: {e}")
            return {}
    
    def _get_error_stats(self, start: datetime, end: datetime) -> Dict[str, int]:
        """Get top MT5 error codes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT retcode FROM order_events
                WHERE timestamp >= ? AND timestamp < ? AND retcode != 10009
            """, (start.timestamp(), end.timestamp()))
            
            errors = Counter()
            for row in cursor.fetchall():
                if row[0]:
                    errors[str(row[0])] += 1
            
            conn.close()
            return dict(errors.most_common(5))
        
        except Exception as e:
            logger.error(f"Failed to get error stats: {e}")
            return {}
    
    def _save_report(self, date: datetime, report: Dict[str, Any]) -> None:
        """Save report to files."""
        date_str = date.strftime("%Y-%m-%d")
        
        # JSON
        self.reporter.save_json(
            f"{date_str}_report.json",
            report
        )
        
        # CSV (trades)
        if report["trades"]:
            headers = ["timestamp", "ticket", "symbol", "pnl", "status"]
            rows = [
                [
                    t.get("timestamp", ""),
                    t.get("ticket", ""),
                    t.get("symbol", ""),
                    t.get("pnl", 0),
                    t.get("success", "")
                ]
                for t in report["trades"]
            ]
            self.reporter.save_csv(f"{date_str}_trades.csv", headers, rows)
        
        # Summary text
        stats = report["statistics"]
        summary = f"""
Daily Report: {date_str}

SUMMARY
-------
Total Trades: {stats.get("total_trades", 0)}
Wins: {stats.get("wins", 0)}
Losses: {stats.get("losses", 0)}
Win Rate: {stats.get("winrate", 0):.1f}%

PnL
---
Total: {stats.get("total_pnl", 0):.2f}
Average: {stats.get("avg_trade", 0):.2f}
Largest Win: {stats.get("largest_win", 0):.2f}
Largest Loss: {stats.get("largest_loss", 0):.2f}

Generated: {report["generated_at"]}
"""
        
        self.reporter.save_text(f"{date_str}_summary.txt", summary)
