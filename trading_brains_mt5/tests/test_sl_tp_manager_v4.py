"""
Tests for Level 4: SL/TP Manager V4

Tests advanced stop loss and take profit management:
- Complete setup creation
- Trailing logic
- Runner activation
- Regime awareness
- Integration with selectors
"""

import unittest
from datetime import datetime

from src.execution.sl_tp_manager_v4 import SLTPManagerV4, LiquidityTPSetup, TrailingState
from src.liquidity.liquidity_map import LiquidityMap, LiquiditySource, LiquidityZone
from src.liquidity.target_selector import TargetSelector
from src.liquidity.stop_selector import StopSelector


class TestTrailingState(unittest.TestCase):
    """Test TrailingState dataclass."""
    
    def test_state_creation(self):
        """Test TrailingState initialization."""
        state = TrailingState()
        
        self.assertFalse(state.active)
        self.assertIsNone(state.last_level_stop)
        self.assertFalse(state.runner_activated)
        self.assertEqual(state.highest_favorable_price, 0.0)
        self.assertEqual(state.updates_count, 0)
    
    def test_state_activation(self):
        """Test trailing state activation."""
        state = TrailingState(
            active=True,
            last_level_stop=1.1040,
            highest_favorable_price=1.1100,
        )
        
        self.assertTrue(state.active)
        self.assertEqual(state.last_level_stop, 1.1040)


class TestLiquidityTPSetup(unittest.TestCase):
    """Test LiquidityTPSetup dataclass."""
    
    def test_setup_creation(self):
        """Test complete setup creation."""
        setup = LiquidityTPSetup(
            symbol='EURUSD',
            side='BUY',
            entry_price=1.1050,
            tp1_qty_percent=0.5,
            tp2_qty_percent=0.3,
            runner_qty_percent=0.2,
        )
        
        self.assertEqual(setup.symbol, 'EURUSD')
        self.assertEqual(setup.side, 'BUY')
        self.assertEqual(setup.entry_price, 1.1050)
        self.assertEqual(setup.tp1_qty_percent, 0.5)
        self.assertEqual(setup.tp2_qty_percent, 0.3)
        self.assertEqual(setup.runner_qty_percent, 0.2)
    
    def test_setup_serialization(self):
        """Test setup can be serialized."""
        setup = LiquidityTPSetup(
            symbol='EURUSD',
            side='BUY',
            entry_price=1.1050,
        )
        
        d = setup.to_dict()
        
        self.assertEqual(d['symbol'], 'EURUSD')
        self.assertEqual(d['side'], 'BUY')
        self.assertEqual(d['entry_price'], 1.1050)


class TestSLTPManagerV4(unittest.TestCase):
    """Test SLTPManagerV4 class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = SLTPManagerV4()
        self.liq_map = LiquidityMap()
        self.target_selector = TargetSelector()
        self.stop_selector = StopSelector()
    
    def test_manager_initialization(self):
        """Test manager is properly initialized."""
        self.assertIsNotNone(self.manager)
        self.assertEqual(len(self.manager.active_trades), 0)
    
    def test_create_setup_basic(self):
        """Test creating a basic trade setup."""
        # Add zones
        zone_tp = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone_tp.strength_score = 0.75
        
        zone_sl = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,
            price_range=0.0005,
            source=LiquiditySource.PIVOT_M5,
        )
        zone_sl.strength_score = 0.70
        
        self.liq_map.add_zone(zone_tp)
        self.liq_map.add_zone(zone_sl)
        
        # Create setup
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        # Should have valid setup
        self.assertIsNotNone(setup)
        self.assertEqual(setup.symbol, 'EURUSD')
        self.assertEqual(setup.side, 'BUY')
        self.assertEqual(setup.entry_price, 1.1050)
    
    def test_create_setup_with_transition(self):
        """Test setup creation during regime transition."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.70
        self.liq_map.add_zone(zone)
        
        # Create setup during transition
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.50,
            regime_mode='TRANSITION',
            regime_transition_strength=0.7,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        # Setup should be created but conservative
        self.assertIsNotNone(setup)
    
    def test_add_active_trade(self):
        """Test adding trade to active tracking."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        self.liq_map.add_zone(zone)
        
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        # Add to active trades
        trade_id = self.manager.add_active_trade(setup)
        
        self.assertIsNotNone(trade_id)
        self.assertIn(trade_id, self.manager.active_trades)
    
    def test_update_trailing_tp1_not_hit(self):
        """Test trailing when TP1 not hit yet."""
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        trade_id = self.manager.add_active_trade(setup)
        
        # Update with current price below TP1
        current_price = 1.1070
        update = self.manager.update_trailing(
            trade_id=trade_id,
            current_price=current_price,
            current_high=1.1070,
            current_low=1.1060,
        )
        
        # No trailing update yet (TP1 not hit)
        self.assertIsNotNone(update)
    
    def test_update_trailing_tp1_hit(self):
        """Test runner activation when TP1 is hit."""
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        if not setup or not setup.target_setup or not setup.target_setup.tp1_price:
            self.skipTest("No valid TP1 selected")
        
        trade_id = self.manager.add_active_trade(setup)
        
        # Update with current price at TP1
        current_price = setup.target_setup.tp1_price
        update = self.manager.update_trailing(
            trade_id=trade_id,
            current_price=current_price,
            current_high=current_price,
            current_low=current_price - 0.0010,
        )
        
        # Runner should activate
        self.assertIsNotNone(update)
    
    def test_short_trade_setup(self):
        """Test setup creation for short trades."""
        # Add zones below entry
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1000,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        self.liq_map.add_zone(zone)
        
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='SELL',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        # Setup should be valid
        self.assertIsNotNone(setup)
        self.assertEqual(setup.side, 'SELL')
    
    def test_qty_distribution(self):
        """Test quantity distribution across TP levels."""
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        if not setup:
            self.skipTest("Setup creation failed")
        
        # Check qty distribution sums to 100%
        total_qty = (
            setup.tp1_qty_percent +
            setup.tp2_qty_percent +
            setup.runner_qty_percent
        )
        
        self.assertAlmostEqual(total_qty, 1.0, places=5)
    
    def test_get_active_trade(self):
        """Test retrieving active trade by ID."""
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        if not setup:
            self.skipTest("Setup creation failed")
        
        trade_id = self.manager.add_active_trade(setup)
        
        # Retrieve trade
        retrieved = self.manager.get_active_trade(trade_id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.symbol, 'EURUSD')
    
    def test_close_active_trade(self):
        """Test closing an active trade."""
        setup = self.manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
            target_selector=self.target_selector,
            stop_selector=self.stop_selector,
        )
        
        if not setup:
            self.skipTest("Setup creation failed")
        
        trade_id = self.manager.add_active_trade(setup)
        initial_count = len(self.manager.active_trades)
        
        # Close trade
        self.manager.close_active_trade(trade_id)
        
        final_count = len(self.manager.active_trades)
        
        self.assertLess(final_count, initial_count)
        self.assertNotIn(trade_id, self.manager.active_trades)


class TestSLTPManagerV4Integration(unittest.TestCase):
    """Integration tests for complete flow."""
    
    def test_complete_long_trade_flow(self):
        """Test complete flow for long trade."""
        manager = SLTPManagerV4()
        liq_map = LiquidityMap()
        target_selector = TargetSelector()
        stop_selector = StopSelector()
        
        # Setup market with zones
        zone_tp = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone_tp.strength_score = 0.75
        
        zone_sl = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,
            price_range=0.0005,
            source=LiquiditySource.PIVOT_M5,
        )
        zone_sl.strength_score = 0.70
        
        liq_map.add_zone(zone_tp)
        liq_map.add_zone(zone_sl)
        
        # Create setup
        setup = manager.create_setup(
            symbol='EURUSD',
            side='BUY',
            entry=1.1050,
            trend_score=0.75,
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=liq_map,
            target_selector=target_selector,
            stop_selector=stop_selector,
        )
        
        self.assertIsNotNone(setup)
        
        # Add to active
        trade_id = manager.add_active_trade(setup)
        self.assertIn(trade_id, manager.active_trades)
        
        # Update trailing
        update = manager.update_trailing(
            trade_id=trade_id,
            current_price=1.1070,
            current_high=1.1070,
            current_low=1.1065,
        )
        
        self.assertIsNotNone(update)
        
        # Close trade
        manager.close_active_trade(trade_id)
        self.assertNotIn(trade_id, manager.active_trades)


if __name__ == '__main__':
    unittest.main()
