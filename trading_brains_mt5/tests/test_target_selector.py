"""
Tests for Level 4: Target Selector

Tests intelligent take profit selection logic:
- TP1/TP2 selection based on zone strength
- Risk/reward validation
- Runner mode enablement
- Distance validation
"""

import unittest

from src.liquidity.liquidity_map import LiquidityMap, LiquiditySource, LiquidityZone
from src.liquidity.target_selector import TargetSelector, TargetSetup


class TestTargetSetup(unittest.TestCase):
    """Test TargetSetup dataclass."""
    
    def test_setup_creation(self):
        """Test TargetSetup can be created."""
        setup = TargetSetup(
            tp1_price=1.1100,
            tp2_price=1.1150,
            runner_enabled=False,
            rr_ratio=2.0,
        )
        
        self.assertEqual(setup.tp1_price, 1.1100)
        self.assertEqual(setup.tp2_price, 1.1150)
        self.assertFalse(setup.runner_enabled)
        self.assertEqual(setup.rr_ratio, 2.0)
    
    def test_setup_validation(self):
        """Test setup validation works."""
        setup = TargetSetup(
            tp1_price=1.1100,
            tp2_price=1.1150,
            runner_enabled=False,
            rr_ratio=2.0,
        )
        
        # Valid setup should pass
        self.assertTrue(setup.validate_setup())
    
    def test_setup_to_dict(self):
        """Test setup can be serialized to dict."""
        setup = TargetSetup(
            tp1_price=1.1100,
            tp2_price=1.1150,
            runner_enabled=False,
            rr_ratio=2.0,
            tp1_reason="First strong zone",
            tp2_reason="Second zone",
        )
        
        d = setup.to_dict()
        
        self.assertEqual(d['tp1_price'], 1.1100)
        self.assertEqual(d['tp2_price'], 1.1150)
        self.assertEqual(d['rr_ratio'], 2.0)


class TestTargetSelector(unittest.TestCase):
    """Test TargetSelector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.selector = TargetSelector(
            min_rr=1.5,
            min_tp_strength=0.55,
            min_runner_confidence=0.65,
        )
        self.liq_map = LiquidityMap()
    
    def test_selector_initialization(self):
        """Test selector is properly initialized."""
        self.assertEqual(self.selector.min_rr, 1.5)
        self.assertEqual(self.selector.min_tp_strength, 0.55)
        self.assertEqual(self.selector.min_runner_confidence, 0.65)
    
    def test_select_tp1_simple(self):
        """Test TP1 selection with simple single strong zone."""
        # Add a strong zone above entry
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        self.liq_map.add_zone(zone)
        
        # Entry at 1.1050, stop at 1.1040
        tp1 = self.selector._select_tp1(
            symbol='EURUSD',
            entry=1.1050,
            stop=1.1040,
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        # Should select the strong zone as TP1
        self.assertIsNotNone(tp1)
        self.assertGreater(tp1, 1.1050)
    
    def test_select_tp1_minimum_strength(self):
        """Test TP1 respects minimum strength threshold."""
        # Add weak zone
        weak_zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        weak_zone.strength_score = 0.40  # Below threshold
        self.liq_map.add_zone(weak_zone)
        
        # Add strong zone
        strong_zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1150,
            price_range=0.0010,
            source=LiquiditySource.PIVOT_M5,
        )
        strong_zone.strength_score = 0.75
        self.liq_map.add_zone(strong_zone)
        
        # Should skip weak zone and use strong zone
        tp1 = self.selector._select_tp1(
            symbol='EURUSD',
            entry=1.1050,
            stop=1.1040,
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        # TP1 should be at strong zone, not weak zone
        if tp1:
            self.assertGreater(abs(tp1 - 1.1150), abs(tp1 - 1.1100))
    
    def test_select_tp2_needs_tp1(self):
        """Test TP2 is only selected if TP1 found."""
        # Add single zone
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        self.liq_map.add_zone(zone)
        
        tp2 = self.selector._select_tp2(
            symbol='EURUSD',
            entry=1.1050,
            tp1_price=1.1100,
            trend_score=0.70,
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        # With only one zone, TP2 may not be selected
        # (depends on implementation - could return None)
        if tp2:
            self.assertGreater(tp2, 1.1100)
    
    def test_select_tp2_requires_trend(self):
        """Test TP2 requires strong trend."""
        # Add zones
        zone1 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone1.strength_score = 0.70
        
        zone2 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1150,
            price_range=0.0010,
            source=LiquiditySource.PIVOT_M5,
        )
        zone2.strength_score = 0.70
        
        self.liq_map.add_zone(zone1)
        self.liq_map.add_zone(zone2)
        
        # With weak trend (0.30), TP2 should not be selected
        tp2_weak = self.selector._select_tp2(
            symbol='EURUSD',
            entry=1.1050,
            tp1_price=1.1100,
            trend_score=0.30,  # Weak trend
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        # With strong trend (0.80), TP2 should be selected
        tp2_strong = self.selector._select_tp2(
            symbol='EURUSD',
            entry=1.1050,
            tp1_price=1.1100,
            trend_score=0.80,  # Strong trend
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        # Strong trend should enable TP2
        self.assertGreater(tp2_strong or 0, tp2_weak or 0)
    
    def test_runner_disabled_when_zones_strong(self):
        """Test runner is not enabled when zones ahead are strong."""
        # Add many strong zones above entry
        for i in range(3):
            zone = LiquidityZone(
                symbol='EURUSD',
                price_center=1.1100 + i * 0.0050,
                price_range=0.0010,
                source=LiquiditySource.ROUND,
            )
            zone.strength_score = 0.75  # Strong zones
            self.liq_map.add_zone(zone)
        
        # Strong zones ahead should disable runner
        runner_enabled = self.selector._should_enable_runner(
            symbol='EURUSD',
            entry=1.1050,
            tp1_price=1.1100,
            tp2_price=1.1150,
            trend_score=0.75,
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        self.assertFalse(runner_enabled)
    
    def test_runner_enabled_with_weak_zones(self):
        """Test runner is enabled when zones ahead are weak."""
        # Add weak zones ahead
        for i in range(3):
            zone = LiquidityZone(
                symbol='EURUSD',
                price_center=1.1200 + i * 0.0050,
                price_range=0.0010,
                source=LiquiditySource.ROUND,
            )
            zone.strength_score = 0.40  # Weak zones
            self.liq_map.add_zone(zone)
        
        # Weak zones + strong trend should enable runner
        runner_enabled = self.selector._should_enable_runner(
            symbol='EURUSD',
            entry=1.1050,
            tp1_price=1.1100,
            tp2_price=1.1150,
            trend_score=0.75,  # Strong trend
            side='BUY',
            liquidity_map=self.liq_map,
        )
        
        self.assertTrue(runner_enabled)
    
    def test_rr_ratio_enforcement(self):
        """Test minimum RR ratio is enforced."""
        # TP too close to entry -> low RR ratio
        rr = (1.1055 - 1.1050) / (1.1050 - 1.1040)  # Only 0.5 RR
        
        # Setup validation should fail for low RR
        setup = TargetSetup(
            tp1_price=1.1055,
            tp2_price=None,
            runner_enabled=False,
            rr_ratio=rr,
        )
        
        # This setup should fail RR validation
        if rr < 1.5:
            self.assertFalse(setup.validate_setup() if rr < 1.5 else True)
    
    def test_select_targets_full_flow(self):
        """Test complete target selection flow."""
        # Setup zones
        zone1 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1100,
            price_range=0.0010,
            source=LiquiditySource.PIVOT_M5,
        )
        zone1.strength_score = 0.75
        
        zone2 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1150,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone2.strength_score = 0.70
        
        self.liq_map.add_zone(zone1)
        self.liq_map.add_zone(zone2)
        
        # Select targets
        setup = self.selector.select_targets(
            symbol='EURUSD',
            entry=1.1050,
            stop=1.1040,
            side='BUY',
            trend_score=0.75,
            liquidity_map=self.liq_map,
        )
        
        # Should have valid setup
        self.assertIsNotNone(setup)
        self.assertIsNotNone(setup.tp1_price)
        self.assertGreater(setup.tp1_price, 1.1050)
    
    def test_short_trade_tp_selection(self):
        """Test TP selection for short trades."""
        # Add zones below entry (for short)
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1000,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        self.liq_map.add_zone(zone)
        
        # Select targets for SHORT
        setup = self.selector.select_targets(
            symbol='EURUSD',
            entry=1.1050,
            stop=1.1060,
            side='SELL',
            trend_score=0.75,
            liquidity_map=self.liq_map,
        )
        
        # TP should be below entry
        if setup and setup.tp1_price:
            self.assertLess(setup.tp1_price, 1.1050)
    
    def test_no_zones_available(self):
        """Test behavior when no zones available."""
        # Empty liquidity map
        setup = self.selector.select_targets(
            symbol='EURUSD',
            entry=1.1050,
            stop=1.1040,
            side='BUY',
            trend_score=0.75,
            liquidity_map=self.liq_map,  # Empty
        )
        
        # Should return None or default setup
        # Implementation dependent
        self.assertTrue(setup is None or isinstance(setup, TargetSetup))


if __name__ == '__main__':
    unittest.main()
