"""
L7 Integration Test - Dashboard with Market Status Engine
Tests API endpoints, database persistence, and symbol management.
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Test data
TEST_SYMBOL = "WDO$N"
TEST_DB = "test_l7.db"


class TestMarketStatusEngine:
    """Test MarketStatusEngine.generate_status()"""
    
    def test_import(self):
        """Test that MarketStatusEngine can be imported"""
        try:
            from src.ui.market_status import MarketStatusEngine, MarketStatusContext
            engine = MarketStatusEngine()
            assert engine is not None
        except Exception as e:
            pytest.fail(f"Failed to import MarketStatusEngine: {e}")
    
    def test_generate_status_trend_up(self):
        """Test status generation for TREND_UP regime with high confidence"""
        from src.ui.market_status import MarketStatusEngine, MarketStatusContext
        
        context = MarketStatusContext(
            symbol=TEST_SYMBOL,
            timestamp=datetime.now().isoformat(),
            regime="TREND_UP",
            ensemble_confidence=0.85,
            ensemble_signal="BUY",
            model_disagreement=0.1,
            liquidity_strength=0.8,
            zone_proximity="MID",
            cross_market_signals=["CONFIRM_UP"],
            market_broken=False,
            news_block_active=False,
            risk_reduction_active=False,
            macro_h1_signal="BUY",
        )
        
        engine = MarketStatusEngine()
        status = engine.generate_status(context)
        
        assert status.symbol == TEST_SYMBOL
        assert status.risk_state == "OK"
        assert "📈" in status.headline or "ALTA" in status.headline
        assert len(status.reasons) > 0
        assert status.metadata is not None
    
    def test_generate_status_chaotic(self):
        """Test status generation for CHAOTIC regime"""
        from src.ui.market_status import MarketStatusEngine, MarketStatusContext
        
        context = MarketStatusContext(
            symbol=TEST_SYMBOL,
            timestamp=datetime.now().isoformat(),
            regime="CHAOTIC",
            ensemble_confidence=0.45,
            ensemble_signal="NEUTRAL",
            model_disagreement=0.5,
            liquidity_strength=0.3,
            zone_proximity="MID",
            cross_market_signals=[],
            market_broken=False,
            news_block_active=False,
            risk_reduction_active=False,
            macro_h1_signal="NEUTRAL",
        )
        
        engine = MarketStatusEngine()
        status = engine.generate_status(context)
        
        assert status.symbol == TEST_SYMBOL
        assert status.risk_state == "CAUTION"
        assert "🌪️" in status.headline or "caótica" in status.headline.lower()
    
    def test_generate_status_market_broken(self):
        """Test status generation when market is broken"""
        from src.ui.market_status import MarketStatusEngine, MarketStatusContext
        
        context = MarketStatusContext(
            symbol=TEST_SYMBOL,
            timestamp=datetime.now().isoformat(),
            regime="TREND_UP",
            ensemble_confidence=0.8,
            ensemble_signal="BUY",
            model_disagreement=0.1,
            liquidity_strength=0.8,
            zone_proximity="MID",
            cross_market_signals=[],
            market_broken=True,  # Market broken!
            news_block_active=False,
            risk_reduction_active=False,
            macro_h1_signal="BUY",
        )
        
        engine = MarketStatusEngine()
        status = engine.generate_status(context)
        
        assert status.risk_state == "BLOCKED"
        assert "🚨" in status.headline


class TestDatabaseSchema:
    """Test L7 database tables"""
    
    def test_create_tables(self):
        """Test that L7 tables can be created"""
        try:
            from src.db.schema import create_tables
            
            # Create test DB
            conn = sqlite3.connect(f":memory:")
            create_tables(conn)
            
            # Verify tables exist
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                "('market_status_log', 'ui_events', 'runtime_symbol_choice')"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'market_status_log' in tables
            assert 'ui_events' in tables
            assert 'runtime_symbol_choice' in tables
            
            conn.close()
        except Exception as e:
            pytest.fail(f"Failed to create L7 tables: {e}")
    
    def test_repo_insert_market_status(self):
        """Test insert_market_status function"""
        try:
            from src.db.repo import insert_market_status, fetch_latest_market_status
            
            conn = sqlite3.connect(":memory:")
            from src.db.schema import create_tables
            create_tables(conn)
            conn.close()
            
            # Create test file DB
            test_path = "test_repo.db"
            conn = sqlite3.connect(test_path)
            create_tables(conn)
            conn.close()
            
            # Insert status
            status_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": TEST_SYMBOL,
                "headline": "📈 Test headline",
                "phase": "Test phase",
                "risk_state": "OK",
                "reasons": ["Reason 1", "Reason 2"],
                "metadata": {"test": True}
            }
            
            insert_market_status(test_path, status_data)
            
            # Fetch and verify
            result = fetch_latest_market_status(test_path)
            assert result is not None
            assert result["symbol"] == TEST_SYMBOL
            assert result["risk_state"] == "OK"
            
            # Cleanup
            Path(test_path).unlink(missing_ok=True)
        except Exception as e:
            pytest.fail(f"Failed in repo test: {e}")


class TestSymbolManager:
    """Test runtime symbol management"""
    
    def test_symbol_manager_import(self):
        """Test that SymbolManager can be imported"""
        try:
            from src.mt5.symbol_manager import SymbolManager
            mgr = SymbolManager()
            assert mgr is not None
        except Exception as e:
            pytest.fail(f"Failed to import SymbolManager: {e}")
    
    def test_get_set_runtime_symbol(self):
        """Test runtime symbol get/set"""
        try:
            from src.mt5.symbol_manager import SymbolManager
            
            # Set symbol
            result = SymbolManager.set_runtime_symbol("EURUSD")
            assert result is True or result is False  # Should be bool
            
            # Get symbol
            symbol = SymbolManager.get_runtime_symbol()
            if symbol:
                assert isinstance(symbol, str)
            
            # Cleanup
            SymbolManager.clear_runtime_symbol()
        except Exception as e:
            pytest.fail(f"Failed in symbol manager test: {e}")


class TestAPIEndpoints:
    """Test API endpoints (mock testing)"""
    
    def test_api_imports(self):
        """Test that API module can be imported"""
        try:
            from src.dashboard.api import app
            assert app is not None
        except Exception as e:
            pytest.fail(f"Failed to import API app: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
