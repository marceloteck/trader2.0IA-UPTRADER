"""
Tests for symbol manager module.
"""

import pytest
from src.mt5.symbol_manager import SymbolManager, SymbolInfo, SymbolHealth


class TestSymbolInfo:
    """Test SymbolInfo dataclass."""
    
    def test_creation(self):
        """Test SymbolInfo creation."""
        info = SymbolInfo(
            symbol="WIN$N",
            spread=0.5,
            digits=2,
            volume_min=1.0,
            volume_max=100.0,
            volatility=0.015
        )
        
        assert info.symbol == "WIN$N"
        assert info.spread == 0.5
        assert info.digits == 2
    
    def test_str(self):
        """Test string representation."""
        info = SymbolInfo(
            symbol="WIN$N",
            spread=0.5,
            digits=2,
            volume_min=1.0,
            volume_max=100.0,
            volatility=0.015
        )
        
        info_str = str(info)
        assert "WIN$N" in info_str
        assert "0.5" in info_str


class TestSymbolHealth:
    """Test SymbolHealth dataclass."""
    
    def test_creation_healthy(self):
        """Test SymbolHealth creation for healthy symbol."""
        health = SymbolHealth(
            symbol="WIN$N",
            ok=True,
            spread=0.5,
            latency_ms=15.3,
            tick_volume=1000.0,
            volatility=0.015,
            error=None
        )
        
        assert health.symbol == "WIN$N"
        assert health.ok is True
        assert health.error is None
    
    def test_creation_unhealthy(self):
        """Test SymbolHealth creation for unhealthy symbol."""
        health = SymbolHealth(
            symbol="WIN$N",
            ok=False,
            spread=5.0,  # Very high
            latency_ms=150.0,  # Very high
            tick_volume=10.0,  # Very low
            volatility=0.05,
            error="High spread detected"
        )
        
        assert health.ok is False
        assert health.error == "High spread detected"


class TestSymbolManager:
    """Test SymbolManager class."""
    
    def test_init_single_mode(self):
        """Test SymbolManager initialization in SINGLE mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(
            config=config,
            mt5_client=None  # No MT5 in test
        )
        
        assert manager.mode == "SINGLE"
        assert manager.primary_symbol == "WIN$N"
    
    def test_init_multi_round_robin(self):
        """Test SymbolManager initialization in MULTI round-robin mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21,WINN21",
            "symbol_mode": "MULTI",
            "symbol_auto_select": False,
            "max_active_symbols": 3
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        assert manager.mode == "MULTI"
        assert len(manager.symbols_list) == 3
        assert "WIN$N" in manager.symbols_list
        assert "WINM21" in manager.symbols_list
    
    def test_init_multi_auto_select(self):
        """Test SymbolManager initialization in MULTI auto-select mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21,WINN21",
            "symbol_mode": "MULTI",
            "symbol_auto_select": True,
            "symbol_auto_select_method": "LIQUIDITY",
            "max_active_symbols": 2
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        assert manager.mode == "MULTI"
        assert manager.auto_select is True
        assert manager.auto_select_method == "LIQUIDITY"
        assert manager.max_active_symbols == 2
    
    def test_get_active_symbols_single(self):
        """Test get_active_symbols in SINGLE mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        active = manager.get_active_symbols()
        
        assert len(active) == 1
        assert active[0] == "WIN$N"
    
    def test_get_active_symbols_multi_round_robin(self):
        """Test get_active_symbols in MULTI round-robin mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21",
            "symbol_mode": "MULTI",
            "symbol_auto_select": False,
            "max_active_symbols": 2
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        # First call
        active1 = manager.get_active_symbols()
        assert "WIN$N" in active1
        
        # Should rotate (if called again)
        # Note: depends on implementation
    
    def test_get_current_symbol_single(self):
        """Test get_current_symbol in SINGLE mode."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        current = manager.get_current_symbol()
        
        assert current == "WIN$N"
    
    def test_update_symbol_health_single(self):
        """Test updating symbol health."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        manager.update_symbol_health(
            symbol="WIN$N",
            ok=True,
            spread=0.5,
            latency_ms=15.0,
            tick_volume=1000.0,
            volatility=0.015
        )
        
        # Health should be stored
        health = manager.get_symbol_health("WIN$N")
        assert health is not None
        assert health.ok is True
        assert health.spread == 0.5
    
    def test_all_healthy(self):
        """Test all_healthy check."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        # Initially no health data
        # After update
        manager.update_symbol_health(
            symbol="WIN$N",
            ok=True,
            spread=0.5,
            latency_ms=15.0,
            tick_volume=1000.0,
            volatility=0.015
        )
        
        all_ok = manager.all_healthy()
        assert all_ok is True
    
    def test_get_symbol_health(self):
        """Test getting symbol health."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        manager.update_symbol_health(
            symbol="WIN$N",
            ok=True,
            spread=0.5,
            latency_ms=15.0,
            tick_volume=1000.0,
            volatility=0.015
        )
        
        health = manager.get_symbol_health("WIN$N")
        assert health is not None
        assert isinstance(health, SymbolHealth)
    
    def test_get_symbol_health_nonexistent(self):
        """Test getting health for nonexistent symbol."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        health = manager.get_symbol_health("NONEXISTENT")
        assert health is None


class TestSymbolManagerIntegration:
    """Integration tests."""
    
    def test_single_to_multi_workflow(self):
        """Test workflow: start with SINGLE, could switch to MULTI."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        # Start in SINGLE mode
        active = manager.get_active_symbols()
        assert len(active) == 1
        assert active[0] == "WIN$N"
    
    def test_health_tracking_workflow(self):
        """Test health tracking across multiple symbols."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N,WINM21",
            "symbol_mode": "MULTI",
            "symbol_auto_select": False,
            "max_active_symbols": 2
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        
        # Update health for multiple symbols
        manager.update_symbol_health(
            symbol="WIN$N",
            ok=True,
            spread=0.5,
            latency_ms=15.0,
            tick_volume=1000.0,
            volatility=0.015
        )
        
        manager.update_symbol_health(
            symbol="WINM21",
            ok=True,
            spread=0.6,
            latency_ms=16.0,
            tick_volume=800.0,
            volatility=0.016
        )
        
        # Check health
        health_w = manager.get_symbol_health("WIN$N")
        health_m = manager.get_symbol_health("WINM21")
        
        assert health_w.ok is True
        assert health_m.ok is True
        assert health_w.spread == 0.5
        assert health_m.spread == 0.6
    
    def test_repr(self):
        """Test string representation."""
        config = {
            "primary_symbol": "WIN$N",
            "symbols": "WIN$N",
            "symbol_mode": "SINGLE",
            "symbol_auto_select": False,
            "max_active_symbols": 1
        }
        
        manager = SymbolManager(config=config, mt5_client=None)
        repr_str = repr(manager)
        
        assert "SymbolManager" in repr_str
        assert "SINGLE" in repr_str
