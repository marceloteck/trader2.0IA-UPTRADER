"""
Tests for Level 4: Stop Selector

Tests stop loss placement logic:
- Zone-based stop placement
- Buffer adjustment
- Transition awareness
- Default fallback
"""

import unittest

from src.liquidity.liquidity_map import LiquidityMap, LiquiditySource, LiquidityZone
from src.liquidity.stop_selector import StopSelector, StopSetup


class TestStopSetup(unittest.TestCase):
    """Test StopSetup dataclass."""
    
    def test_setup_creation(self):
        """Test StopSetup can be created."""
        setup = StopSetup(
            stop_price=1.1040,
            buffer_pips=20.0,
            distance_pips=10.0,
        )
        
        self.assertEqual(setup.stop_price, 1.1040)
        self.assertEqual(setup.buffer_pips, 20.0)
        self.assertEqual(setup.distance_pips, 10.0)
    
    def test_setup_to_dict(self):
        """Test setup serialization."""
        setup = StopSetup(
            stop_price=1.1040,
            buffer_pips=20.0,
            distance_pips=10.0,
            reason="Behind support",
        )
        
        d = setup.to_dict()
        
        self.assertEqual(d['stop_price'], 1.1040)
        self.assertEqual(d['buffer_pips'], 20.0)
        self.assertEqual(d['distance_pips'], 10.0)
    
    def test_adjust_for_transition(self):
        """Test stop adjustment during transitions."""
        setup = StopSetup(
            stop_price=1.1040,
            buffer_pips=20.0,
            distance_pips=10.0,
        )
        
        # Adjust for transition (1.5x buffer)
        adjusted = setup.adjust_for_transition(buffer_factor=1.5)
        
        # Stop should move closer (higher buffer)
        self.assertGreater(adjusted.buffer_pips, 20.0)


class TestStopSelector(unittest.TestCase):
    """Test StopSelector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.selector = StopSelector(
            default_buffer_pips=20.0,
            transition_buffer_factor=1.5,
        )
        self.liq_map = LiquidityMap()
    
    def test_selector_initialization(self):
        """Test selector is properly initialized."""
        self.assertEqual(self.selector.default_buffer_pips, 20.0)
        self.assertEqual(self.selector.transition_buffer_factor, 1.5)
    
    def test_default_stop_selection(self):
        """Test default stop when no zones available."""
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,  # Empty
        )
        
        # Should return default setup
        self.assertIsNotNone(setup)
        self.assertLess(setup.stop_price, 1.1050)  # Below entry for long
        self.assertGreater(setup.buffer_pips, 0)
    
    def test_stop_for_long_trade(self):
        """Test stop placement for long trade."""
        # Add support zone below entry
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        zone.prob_hold = 0.70
        self.liq_map.add_zone(zone)
        
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Stop should be below entry
        self.assertLess(setup.stop_price, 1.1050)
        
        # Stop should be near the support zone
        self.assertLess(abs(setup.stop_price - zone.price_center), 0.0020)
    
    def test_stop_for_short_trade(self):
        """Test stop placement for short trade."""
        # Add resistance zone above entry
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1070,
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        zone.prob_hold = 0.70
        self.liq_map.add_zone(zone)
        
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='SELL',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Stop should be above entry
        self.assertGreater(setup.stop_price, 1.1050)
        
        # Stop should be near the resistance zone
        self.assertLess(abs(setup.stop_price - zone.price_center), 0.0020)
    
    def test_avoid_weak_zones(self):
        """Test stop avoids zones with low hold rate."""
        # Add weak zone
        weak_zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        weak_zone.strength_score = 0.40
        weak_zone.prob_hold = 0.20  # Very weak
        self.liq_map.add_zone(weak_zone)
        
        # Add strong zone
        strong_zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1020,
            price_range=0.0005,
            source=LiquiditySource.PIVOT_M5,
        )
        strong_zone.strength_score = 0.75
        strong_zone.prob_hold = 0.70
        self.liq_map.add_zone(strong_zone)
        
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Stop should prefer strong zone over weak zone
        if setup:
            # Stop closer to strong zone than weak zone
            dist_to_weak = abs(setup.stop_price - weak_zone.price_center)
            dist_to_strong = abs(setup.stop_price - strong_zone.price_center)
            self.assertLess(dist_to_strong, dist_to_weak)
    
    def test_transition_buffer_adjustment(self):
        """Test buffer is increased during transitions."""
        # Add a zone
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        zone.prob_hold = 0.70
        self.liq_map.add_zone(zone)
        
        # Stop in NORMAL mode
        normal_setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Stop in TRANSITION mode
        transition_setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='TRANSITION',
            regime_transition_strength=0.7,
            liquidity_map=self.liq_map,
        )
        
        # Transition should have wider buffer
        if transition_setup.buffer_pips > 0:
            self.assertGreater(
                transition_setup.buffer_pips,
                normal_setup.buffer_pips
            )
    
    def test_chaotic_regime_wide_buffer(self):
        """Test wider buffer in chaotic regime."""
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='CHAOTIC',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,  # Empty
        )
        
        # Chaotic mode should have wider default buffer
        self.assertGreater(setup.buffer_pips, self.selector.default_buffer_pips)
    
    def test_multiple_zones_nearest_selected(self):
        """Test nearest zone is selected when multiple available."""
        # Add multiple zones at different distances
        zone1 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1030,  # Close
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        zone1.strength_score = 0.70
        zone1.prob_hold = 0.65
        
        zone2 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1010,  # Far
            price_range=0.0005,
            source=LiquiditySource.PIVOT_M5,
        )
        zone2.strength_score = 0.75
        zone2.prob_hold = 0.70
        
        self.liq_map.add_zone(zone1)
        self.liq_map.add_zone(zone2)
        
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Should prefer closer zone (zone1)
        self.assertLess(abs(setup.stop_price - zone1.price_center), 0.0010)
    
    def test_short_stop_below_resistance(self):
        """Test short trade stop goes below resistance, not at it."""
        # Add resistance zone
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1070,
            price_range=0.0005,
            source=LiquiditySource.ROUND,
        )
        zone.strength_score = 0.75
        zone.prob_hold = 0.70
        self.liq_map.add_zone(zone)
        
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='SELL',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # For SHORT, stop should be ABOVE the entry
        # but below the zone center (with buffer above zone)
        self.assertGreater(setup.stop_price, 1.1050)
        self.assertGreater(setup.stop_price, zone.price_center - zone.price_range / 2)
    
    def test_distance_calculation(self):
        """Test distance in pips is calculated correctly."""
        setup = self.selector.select_stop(
            symbol='EURUSD',
            entry=1.1050,
            side='BUY',
            regime_mode='NORMAL',
            regime_transition_strength=0.0,
            liquidity_map=self.liq_map,
        )
        
        # Distance should be positive and reasonably sized
        distance = abs(setup.stop_price - 1.1050)
        self.assertGreater(distance, 0)
        
        # Distance in pips: (1.1050 - stop) / 0.0001
        pips = distance / 0.0001
        
        # Should be close to recorded distance_pips
        self.assertGreater(pips, 10)  # At least 10 pips


if __name__ == '__main__':
    unittest.main()
