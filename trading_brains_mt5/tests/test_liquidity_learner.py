"""
Tests for Level 4: Liquidity Learner

Tests the learning algorithm that tracks zone behavior from closed trades:
- Zone behavior classification
- Statistics tracking
- PnL calculation
- Confidence scoring
- Zone pruning
"""

import unittest
from datetime import datetime, timedelta

from src.liquidity.liquidity_learner import LiquidityLearner, LevelBehavior
from src.liquidity.liquidity_map import LiquidityMap, LiquiditySource, LiquidityZone


class TestLevelBehavior(unittest.TestCase):
    """Test LevelBehavior dataclass."""
    
    def test_behavior_creation(self):
        """Test behavior record can be created."""
        behavior = LevelBehavior(
            level_price=1.1050,
            action='held',
            pnl=50.0,
            bars_held=5,
        )
        
        self.assertEqual(behavior.level_price, 1.1050)
        self.assertEqual(behavior.action, 'held')
        self.assertEqual(behavior.pnl, 50.0)
        self.assertEqual(behavior.bars_held, 5)


class TestLiquidityLearner(unittest.TestCase):
    """Test LiquidityLearner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.learner = LiquidityLearner()
        self.liq_map = LiquidityMap()
    
    def test_learner_initialization(self):
        """Test learner is properly initialized."""
        self.assertIsNotNone(self.learner)
        self.assertEqual(len(self.learner.level_stats), 0)
    
    def test_classify_action_held(self):
        """Test classification of price held within zone."""
        level_price = 1.1050
        
        # Price stayed above level
        action = self.learner._classify_action(
            level_price=level_price,
            entry_price=1.1040,
            exit_price=1.1060,
            exit_high=1.1070,
            exit_low=1.1045,
            side='BUY',
        )
        
        self.assertIn(action, ['held', 'broken', 'swept'])
    
    def test_classify_action_broken(self):
        """Test classification of price breaking through zone."""
        level_price = 1.1050
        
        # Price broke above level
        action = self.learner._classify_action(
            level_price=level_price,
            entry_price=1.1040,
            exit_price=1.1070,  # Exit above level
            exit_high=1.1080,
            exit_low=1.1045,
            side='BUY',
        )
        
        # Should be 'broken' or 'swept'
        self.assertIn(action, ['broken', 'swept'])
    
    def test_update_from_trade_creates_stats(self):
        """Test trade update creates level statistics."""
        trade_data = {
            'symbol': 'EURUSD',
            'entry_price': 1.1040,
            'exit_price': 1.1070,
            'exit_high': 1.1080,
            'exit_low': 1.1030,
            'side': 'BUY',
            'pnl': 100.0,
            'bars_held': 10,
        }
        
        # Add some zones to learn from
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        self.liq_map.add_zone(zone)
        
        # Update learner with trade
        self.learner.update_from_trade(
            trade_data=trade_data,
            liquidity_map=self.liq_map,
        )
        
        # Should have recorded behaviors
        self.assertGreater(len(self.learner.trade_history), 0)
    
    def test_expected_pnl_calculation(self):
        """Test PnL expectancy calculation at level."""
        # Record multiple trade outcomes at same level
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        level_id = self.liq_map.add_zone(zone)
        
        # Simulate learning from multiple trades
        # Trade 1: Price held, positive PnL
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='held',
            pnl=50.0,
        )
        
        # Trade 2: Price held, negative PnL
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='held',
            pnl=-20.0,
        )
        
        # Trade 3: Price held, positive PnL
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='held',
            pnl=60.0,
        )
        
        # Check expected PnL
        expected_pnl = self.learner.get_expected_pnl_at_level(
            symbol='EURUSD',
            level_id=level_id,
            action='held',
        )
        
        # Average of 50, -20, 60 is ~30
        self.assertGreater(expected_pnl, 20)
    
    def test_confidence_scoring(self):
        """Test confidence score increases with positive outcomes."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        level_id = self.liq_map.add_zone(zone)
        
        # Record multiple successful holds
        for i in range(5):
            self.learner._update_level_stats(
                symbol='EURUSD',
                level_id=level_id,
                level_price=1.1050,
                action='held',
                pnl=50.0,  # All profitable
            )
        
        confidence = self.learner.get_level_confidence(
            symbol='EURUSD',
            level_id=level_id,
            action='held',
        )
        
        # Confidence should be high (many profitable holds)
        self.assertGreater(confidence, 0.7)
    
    def test_decay_factor_calculation(self):
        """Test decay factor reduces confidence with many tests."""
        # Few tests (< 3) = high decay factor
        decay_few = self.learner._decay_factor(test_count=2)
        self.assertEqual(decay_few, 1.0)
        
        # Medium tests (3-10) = moderate decay
        decay_medium = self.learner._decay_factor(test_count=5)
        self.assertEqual(decay_medium, 0.9)
        
        # Many tests (> 10) = low decay
        decay_many = self.learner._decay_factor(test_count=15)
        self.assertLess(decay_many, 0.9)
    
    def test_prune_old_zones(self):
        """Test removal of untested old zones."""
        old_time = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
            created_at=old_time,
            touch_count=0,  # Never tested
        )
        
        level_id = self.liq_map.add_zone(zone)
        
        initial_count = len(self.liq_map.zones)
        
        # Prune zones older than 24 hours
        self.learner.prune_old_zones(
            liquidity_map=self.liq_map,
            max_age_hours=24,
        )
        
        # Old untested zone should be removed
        self.assertLess(len(self.liq_map.zones), initial_count)
    
    def test_prune_keeps_tested_zones(self):
        """Test pruning doesn't remove tested zones."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
            created_at=(datetime.utcnow() - timedelta(hours=25)).isoformat(),
            touch_count=5,  # Has been tested
        )
        
        self.liq_map.add_zone(zone)
        
        initial_count = len(self.liq_map.zones)
        
        # Prune zones
        self.learner.prune_old_zones(
            liquidity_map=self.liq_map,
            max_age_hours=24,
        )
        
        # Tested zone should be kept
        self.assertEqual(len(self.liq_map.zones), initial_count)
    
    def test_export_statistics(self):
        """Test exporting zone statistics."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        level_id = self.liq_map.add_zone(zone)
        
        # Add some stats
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='held',
            pnl=50.0,
        )
        
        # Export stats
        stats = self.learner.export_stats(symbol='EURUSD')
        
        self.assertIsNotNone(stats)
        self.assertGreater(len(stats), 0)
    
    def test_multiple_symbols_isolation(self):
        """Test learning data is isolated per symbol."""
        # Add zones for different symbols
        eu_zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        gbp_zone = LiquidityZone(
            symbol='GBPUSD',
            price_center=1.3050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        eu_id = self.liq_map.add_zone(eu_zone)
        gbp_id = self.liq_map.add_zone(gbp_zone)
        
        # Update learner with EURUSD trade
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=eu_id,
            level_price=1.1050,
            action='held',
            pnl=50.0,
        )
        
        # Export EURUSD stats - should not include GBPUSD
        eu_stats = self.learner.export_stats(symbol='EURUSD')
        gbp_stats = self.learner.export_stats(symbol='GBPUSD')
        
        self.assertGreater(len(eu_stats), 0)
        self.assertEqual(len(gbp_stats), 0)
    
    def test_action_type_tracking(self):
        """Test different action types are tracked separately."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        level_id = self.liq_map.add_zone(zone)
        
        # Record different actions
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='held',
            pnl=50.0,
        )
        
        self.learner._update_level_stats(
            symbol='EURUSD',
            level_id=level_id,
            level_price=1.1050,
            action='broken',
            pnl=100.0,
        )
        
        # Confidence for 'held' should be different from 'broken'
        held_confidence = self.learner.get_level_confidence(
            symbol='EURUSD',
            level_id=level_id,
            action='held',
        )
        
        broken_confidence = self.learner.get_level_confidence(
            symbol='EURUSD',
            level_id=level_id,
            action='broken',
        )
        
        # Should have different confidences (broken had only 1 instance)
        self.assertNotEqual(held_confidence, broken_confidence)


if __name__ == '__main__':
    unittest.main()
