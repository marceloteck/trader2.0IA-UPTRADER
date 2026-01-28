"""
Symbol Manager: Handle single/multi-asset trading configuration and validation.

Features:
- SINGLE mode: Trade one fixed symbol
- MULTI mode: Trade multiple symbols (round-robin or by liquidity)
- Auto-select: Choose symbols based on spread, liquidity, volatility
- Health tracking: Monitor symbol availability and conditions
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("trading_brains.mt5.symbol_manager")


@dataclass
class SymbolInfo:
    """Information about a trading symbol."""
    symbol: str
    available: bool
    spread: float
    digits: int
    trade_modes: List[str]
    volume_min: float
    volume_step: float
    volume_max: float
    tick_volume: Optional[float] = None
    volatility: Optional[float] = None
    last_checked: Optional[float] = None


@dataclass
class SymbolHealth:
    """Health status of a symbol."""
    symbol: str
    timestamp: float
    ok: bool
    spread: float
    latency_ms: float
    tick_volume: float
    volatility: float
    error: Optional[str] = None


class SymbolManager:
    """
    Manage trading symbols: validate, select, and track health.
    
    Usage:
        manager = SymbolManager(
            mode="MULTI",
            symbols=["WIN$N", "WDOV"],
            auto_select=True,
            auto_select_method="LIQUIDITY"
        )
        active_symbols = manager.get_active_symbols()
        health = manager.get_symbol_health()
    """
    
    def __init__(
        self,
        mode: str = "SINGLE",
        primary_symbol: str = "WIN$N",
        symbols: Optional[List[str]] = None,
        max_active: int = 1,
        auto_select: bool = False,
        auto_select_method: str = "LIQUIDITY",
        validate_on_start: bool = True,
        mt5_client = None
    ):
        """
        Initialize symbol manager.
        
        Args:
            settings: Settings object with symbol configuration
            mode: "SINGLE" or "MULTI" (default from settings)
            primary_symbol: Primary symbol (default from settings.primary_symbol)
            symbols: List of symbols if MULTI mode
            max_active: Maximum simultaneous active symbols
            auto_select: Automatically select best symbols
            auto_select_method: "LIQUIDITY", "VOLATILITY", "SPREAD"
            validate_on_start: Validate symbols on initialization
            mt5_client: MT5 client instance
        """
        # Get defaults from settings if available
        if mode is None:
            mode = getattr(settings, 'symbol_mode', 'SINGLE')
        if primary_symbol is None:
            primary_symbol = getattr(settings, 'primary_symbol', 'EURUSD')
        
        self.mode = str(mode).upper()
        self.primary_symbol = primary_symbol
        self.symbols = symbols or [primary_symbol]
        self.max_active = max_active
        self.auto_select = auto_select
        self.auto_select_method = str(auto_select_method).upper()
        self.mt5_client = mt5_client
        
        self.active_symbols: List[str] = []
        self.symbol_info: Dict[str, SymbolInfo] = {}
        self.symbol_health: Dict[str, SymbolHealth] = {}
        self.current_index = 0  # For round-robin
        
        # Initialize
        if validate_on_start:
            self._initialize()
    
    def _initialize(self) -> None:
        """Initialize and validate symbols."""
        logger.info(
            f"SymbolManager init: mode={self.mode}, "
            f"symbols={self.symbols}, max_active={self.max_active}"
        )
        
        if self.mode == "SINGLE":
            self._validate_symbol(self.primary_symbol)
            if self.primary_symbol in self.symbol_info and self.symbol_info[self.primary_symbol].available:
                self.active_symbols = [self.primary_symbol]
            else:
                logger.error(f"Primary symbol {self.primary_symbol} validation failed")
                self.active_symbols = []
        
        elif self.mode == "MULTI":
            for symbol in self.symbols:
                self._validate_symbol(symbol)
            
            if self.auto_select:
                self.active_symbols = self._select_best_symbols()
            else:
                self.active_symbols = [
                    s for s in self.symbols
                    if s in self.symbol_info and self.symbol_info[s].available
                ][:self.max_active]
        
        logger.info(f"Active symbols: {self.active_symbols}")
    
    def _validate_symbol(self, symbol: str) -> bool:
        """
        Validate symbol with MT5.
        
        Returns:
            True if valid, False otherwise
        """
        if not self.mt5_client:
            logger.warning("No MT5 client - skipping validation")
            return False
        
        try:
            info = self.mt5_client.fetch_symbol_info(symbol)
            if info:
                self.symbol_info[symbol] = SymbolInfo(
                    symbol=symbol,
                    available=True,
                    spread=info.get("spread", 1.0),
                    digits=info.get("digits", 5),
                    trade_modes=info.get("trade_modes", ["BUY", "SELL"]),
                    volume_min=info.get("volume_min", 0.1),
                    volume_step=info.get("volume_step", 0.01),
                    volume_max=info.get("volume_max", 100.0),
                    last_checked=datetime.utcnow().timestamp()
                )
                logger.info(f"Validated symbol {symbol}: spread={info.get('spread', 1.0)}")
                return True
            else:
                logger.warning(f"Symbol {symbol} not found")
                return False
        except Exception as e:
            logger.warning(f"Failed to validate {symbol}: {e}")
            return False
    
    def _select_best_symbols(self) -> List[str]:
        """
        Select best symbols based on auto_select_method.
        
        Returns:
            List of selected symbols (up to max_active)
        """
        valid_symbols = [
            s for s in self.symbols
            if s in self.symbol_info and self.symbol_info[s].available
        ]
        
        if not valid_symbols:
            logger.warning("No valid symbols to select from")
            return []
        
        if self.auto_select_method == "LIQUIDITY":
            # Higher tick volume = more liquid
            # Requires tick_volume to be set
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: -(self.symbol_info[s].tick_volume or 0)
            )
        
        elif self.auto_select_method == "SPREAD":
            # Lower spread = better
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: self.symbol_info[s].spread
            )
        
        elif self.auto_select_method == "VOLATILITY":
            # Moderate volatility (not too high)
            sorted_symbols = sorted(
                valid_symbols,
                key=lambda s: abs(0.01 - (self.symbol_info[s].volatility or 0.01))
            )
        
        else:
            sorted_symbols = valid_symbols
        
        selected = sorted_symbols[:self.max_active]
        logger.info(f"Auto-selected {self.auto_select_method}: {selected}")
        return selected
    
    def get_active_symbols(self) -> List[str]:
        """Get list of active symbols to trade."""
        return self.active_symbols
    
    def get_current_symbol(self) -> Optional[str]:
        """
        Get current symbol (round-robin in MULTI mode).
        
        Returns:
            Symbol to trade now, or None if no active symbols
        """
        if not self.active_symbols:
            return None
        
        if self.mode == "SINGLE":
            return self.active_symbols[0]
        
        # MULTI: round-robin
        symbol = self.active_symbols[self.current_index % len(self.active_symbols)]
        self.current_index += 1
        return symbol
    
    def get_symbol_info(self, symbol: Optional[str] = None) -> Optional[SymbolInfo]:
        """Get info for symbol (current if None)."""
        if symbol is None:
            symbol = self.get_current_symbol()
        
        if symbol is None:
            return None
        
        return self.symbol_info.get(symbol)
    
    def get_health_status(self) -> Dict[str, SymbolHealth]:
        """Get health status for all symbols."""
        return self.symbol_health
    
    def update_symbol_health(
        self,
        symbol: str,
        ok: bool,
        spread: float,
        latency_ms: float,
        tick_volume: float,
        volatility: float,
        error: Optional[str] = None
    ) -> None:
        """Record symbol health check."""
        self.symbol_health[symbol] = SymbolHealth(
            symbol=symbol,
            timestamp=datetime.utcnow().timestamp(),
            ok=ok,
            spread=spread,
            latency_ms=latency_ms,
            tick_volume=tick_volume,
            volatility=volatility,
            error=error
        )
    
    def all_healthy(self) -> bool:
        """Check if all active symbols are healthy."""
        if not self.active_symbols:
            return False
        
        return all(
            self.symbol_health.get(s, SymbolHealth(
                symbol=s, timestamp=0, ok=False, spread=0, latency_ms=0, tick_volume=0, volatility=0
            )).ok
            for s in self.active_symbols
        )
    
    def as_dict(self) -> Dict:
        """Export state as dict."""
        return {
            "mode": self.mode,
            "primary_symbol": self.primary_symbol,
            "symbols": self.symbols,
            "max_active": self.max_active,
            "auto_select": self.auto_select,
            "auto_select_method": self.auto_select_method,
            "active_symbols": self.active_symbols,
            "symbol_info": {
                k: asdict(v) for k, v in self.symbol_info.items()
            },
            "symbol_health": {
                k: asdict(v) for k, v in self.symbol_health.items()
            }
        }    
    # L7: Runtime symbol override support
    @staticmethod
    def get_runtime_symbol() -> Optional[str]:
        """
        Get runtime symbol choice from dashboard (L7).
        
        Returns:
            Symbol if runtime_symbol.json exists, None otherwise
        """
        from pathlib import Path
        
        runtime_path = Path("data/config/runtime_symbol.json")
        try:
            if runtime_path.exists():
                with open(runtime_path, "r") as f:
                    data = json.load(f)
                    symbol = data.get("symbol")
                    if symbol:
                        logger.debug(f"Runtime symbol found: {symbol}")
                        return symbol
        except Exception as e:
            logger.debug(f"Error reading runtime symbol: {e}")
        
        return None
    
    @staticmethod
    def set_runtime_symbol(symbol: str) -> bool:
        """
        Set runtime symbol choice (L7 dashboard).
        
        Args:
            symbol: New symbol to set
        
        Returns:
            True if successful
        """
        from pathlib import Path
        
        try:
            runtime_path = Path("data/config/runtime_symbol.json")
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            
            runtime_data = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "changed_by": "dashboard"
            }
            
            with open(runtime_path, "w") as f:
                json.dump(runtime_data, f, indent=2)
            
            logger.info(f"Runtime symbol set to {symbol}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting runtime symbol: {e}")
            return False
    
    @staticmethod
    def clear_runtime_symbol() -> bool:
        """
        Clear runtime symbol choice (revert to default).
        
        Returns:
            True if successful
        """
        from pathlib import Path
        
        try:
            runtime_path = Path("data/config/runtime_symbol.json")
            if runtime_path.exists():
                runtime_path.unlink()
                logger.info("Runtime symbol choice cleared")
            return True
        
        except Exception as e:
            logger.error(f"Error clearing runtime symbol: {e}")
            return False