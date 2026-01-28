"""
Cost model: realistic spread, slippage, commission by hour and volatility.

Modes:
1. FIXO: Fixed values from .env
2. POR_HORARIO: Hourly table (data/config/spread_by_hour.json)
3. APRENDIDO: Learned from historical spreads
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("trading_brains.costs")


@dataclass
class CostSnapshot:
    """Snapshot of costs at a point in time."""
    timestamp: float
    spread: float
    slippage: float
    commission: float
    spread_basis: str  # "FIXO", "POR_HORARIO", "APRENDIDO"
    details: Dict = None


class CostModel:
    """
    Model trading costs realistically.
    
    Usage:
        model = CostModel(mode="POR_HORARIO", db_path="...")
        spread, slip = model.get_costs("EURUSD", hour=14, atr=0.05, volatility=1.2)
    """
    
    def __init__(
        self,
        mode: str = "FIXO",
        spread_base: float = 1.0,
        slippage_base: float = 0.5,
        slippage_max: float = 2.0,
        commission: float = 0.0,
        config_file: Optional[str] = None,
        db_path: Optional[str] = None
    ):
        """
        Initialize cost model.
        
        Args:
            mode: "FIXO" | "POR_HORARIO" | "APRENDIDO"
            spread_base: Base spread in pips
            slippage_base: Base slippage in pips
            slippage_max: Maximum slippage
            commission: Commission per trade (in currency or %)
            config_file: Path to JSON with hourly costs (if POR_HORARIO)
            db_path: Database path (if APRENDIDO or learning enabled)
        """
        self.mode = mode
        self.spread_base = spread_base
        self.slippage_base = slippage_base
        self.slippage_max = slippage_max
        self.commission = commission
        self.db_path = db_path
        
        self._hourly_costs = {}
        self._load_hourly_costs(config_file)
    
    def _load_hourly_costs(self, config_file: Optional[str]) -> None:
        """Load hourly cost schedule from JSON."""
        if not config_file:
            config_file = "data/config/spread_by_hour.json"
        
        config_path = Path(config_file)
        if config_path.exists():
            try:
                with open(config_path) as f:
                    self._hourly_costs = json.load(f)
                logger.info(f"Loaded hourly costs from {config_file}")
            except Exception as e:
                logger.warning(f"Could not load hourly costs: {e}")
    
    def get_costs(
        self,
        symbol: str,
        hour: int,
        atr: float = 0.0,
        volatility: float = 1.0,
        timestamp: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Get current spread, slippage, and commission.
        
        Args:
            symbol: Trading symbol
            hour: Hour of day (0-23)
            atr: Current ATR (for volatility adjustment)
            volatility: Volatility factor (1.0 = normal)
            timestamp: Current time (for logging)
        
        Returns:
            (spread, slippage, commission)
        """
        if timestamp is None:
            timestamp = datetime.utcnow().timestamp()
        
        if self.mode == "FIXO":
            spread = self.spread_base
            slippage = self.slippage_base * volatility
        
        elif self.mode == "POR_HORARIO":
            hour_key = f"{hour:02d}:00"
            hourly_config = self._hourly_costs.get(hour_key, {})
            
            spread = hourly_config.get("spread", self.spread_base)
            slippage_mult = hourly_config.get("slippage_mult", 1.0)
            slippage = self.slippage_base * slippage_mult * volatility
        
        elif self.mode == "APRENDIDO":
            spread, slippage = self._get_learned_costs(symbol, hour, atr)
            slippage *= volatility
        
        else:
            spread = self.spread_base
            slippage = self.slippage_base
        
        # Clamp slippage
        slippage = min(slippage, self.slippage_max)
        
        return spread, slippage, self.commission
    
    def _get_learned_costs(self, symbol: str, hour: int, atr: float) -> Tuple[float, float]:
        """
        Learn costs from historical data (simplified).
        
        In production, would query cost_events table and compute percentiles.
        For now, returns reasonable defaults based on hour and ATR.
        """
        # Simple heuristic: costs higher during low-liquidity hours
        if hour in [0, 1, 2, 3, 4, 5]:  # Asian hours
            spread_mult = 2.0
            slip_mult = 1.5
        elif hour in [17, 18, 19, 20]:  # US close / European close
            spread_mult = 1.5
            slip_mult = 1.3
        else:
            spread_mult = 1.0
            slip_mult = 1.0
        
        # Volatility adjustment
        slip_mult *= max(1.0, atr / 0.01)  # Assume 0.01 is baseline
        
        return (
            self.spread_base * spread_mult,
            self.slippage_base * slip_mult
        )
    
    def record_cost(
        self,
        timestamp: float,
        spread: float,
        slippage: float,
        commission: float,
        details: Optional[Dict] = None
    ) -> None:
        """Record actual cost observed (for learning)."""
        # Would be persisted to cost_events table
        logger.debug(
            f"Cost snapshot: spread={spread:.2f}, "
            f"slip={slippage:.2f}, comm={commission:.2f}"
        )
    
    def get_total_cost_per_trade(
        self,
        symbol: str,
        volume: float,
        hour: int = 0,
        atr: float = 0.0
    ) -> float:
        """
        Calculate total cost per trade in currency.
        
        Assumes: entry spread + exit spread + slippage + commission.
        """
        spread, slippage, commission = self.get_costs(symbol, hour, atr)
        
        # Total round-trip cost: 2x spread (entry + exit) + 2x slippage
        cost_pips = 2 * (spread + slippage)
        
        # Convert to currency (simplified; real implementation uses pip value)
        # For EURUSD: 1 pip = 0.0001, 1 lot = 100k units
        pip_value = 10.0 if "USD" in symbol else 10.0  # Simplified
        cost_currency = cost_pips * pip_value * volume / 100000
        
        cost_currency += commission * volume
        
        return cost_currency
    
    def as_dict(self) -> Dict:
        """Export config as dict."""
        return {
            "mode": self.mode,
            "spread_base": self.spread_base,
            "slippage_base": self.slippage_base,
            "slippage_max": self.slippage_max,
            "commission": self.commission
        }
