"""
Tests for Level 4: Liquidity Map

Tests the core zone mapping functionality including:
- Zone creation and deduplication
- Zone statistics tracking
- Probability updates
- Nearest zone queries
- Multi-symbol support
"""

import unittest
from datetime import datetime, timedelta

from src.liquidity.liquidity_map import LiquidityMap, LiquiditySource, LiquidityZone


class TestLiquidityZone(unittest.TestCase):
    """Test LiquidityZone dataclass."""
    
    def test_zone_creation(self):
        """Test zone can be created with required fields."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        self.assertEqual(zone.symbol, 'EURUSD')
        self.assertEqual(zone.price_center, 1.1050)
        self.assertEqual(zone.price_range, 0.0010)
        self.assertEqual(zone.source, LiquiditySource.ROUND)
    
    def test_zone_price_bounds(self):
        """Test zone min/max price calculation."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        self.assertAlmostEqual(zone.price_min, 1.1045)
        self.assertAlmostEqual(zone.price_max, 1.1055)
    
    def test_zone_contains_price(self):
        """Test price containment check."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        self.assertTrue(zone.contains(1.1050))
        self.assertTrue(zone.contains(1.1045))
        self.assertTrue(zone.contains(1.1055))
        self.assertFalse(zone.contains(1.1040))
        self.assertFalse(zone.contains(1.1060))
    
    def test_zone_contains_high_low(self):
        """Test OHLC containment check."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        # Zone is contained within bar
        self.assertTrue(zone.contains_high_low(1.1040, 1.1060))
        
        # Bar touches zone
        self.assertTrue(zone.contains_high_low(1.1050, 1.1070))
        
        # Bar misses zone
        self.assertFalse(zone.contains_high_low(1.1060, 1.1080))


class TestLiquidityMap(unittest.TestCase):
    """Test LiquidityMap class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.map = LiquidityMap()
    
    def test_add_zone(self):
        """Test adding zones to map."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        zone_id = self.map.add_zone(zone)
        
        self.assertIsNotNone(zone_id)
        self.assertIn(zone_id, self.map.zones)
    
    def test_zone_deduplication(self):
        """Test that overlapping zones are deduplicated."""
        zone1 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        zone2 = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,  # Same price
            price_range=0.0008,
            source=LiquiditySource.PIVOT_M5,
        )
        
        id1 = self.map.add_zone(zone1)
        id2 = self.map.add_zone(zone2)
        
        # Should be same zone (deduplicated)
        self.assertEqual(id1, id2)
    
    def test_get_zones_for_symbol(self):
        """Test retrieving zones for a specific symbol."""
        # Add zones for two symbols
        zone_eu = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        zone_gbp = LiquidityZone(
            symbol='GBPUSD',
            price_center=1.3050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        self.map.add_zone(zone_eu)
        self.map.add_zone(zone_gbp)
        
        # Get zones for EURUSD
        eu_zones = self.map.get_zones('EURUSD')
        
        self.assertEqual(len(eu_zones), 1)
        self.assertEqual(eu_zones[0].symbol, 'EURUSD')
    
    def test_get_zones_above_below(self):
        """Test directional zone queries."""
        zones = [
            LiquidityZone('EURUSD', 1.1000, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('EURUSD', 1.1050, 0.0010, LiquiditySource.PIVOT_M5),
            LiquidityZone('EURUSD', 1.1100, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('EURUSD', 1.1150, 0.0010, LiquiditySource.PIVOT_M5),
        ]
        
        for zone in zones:
            self.map.add_zone(zone)
        
        # Get zones above 1.1070
        above = self.map.get_zones_above('EURUSD', 1.1070)
        self.assertEqual(len(above), 2)  # 1.1100, 1.1150
        
        # Get zones below 1.1070
        below = self.map.get_zones_below('EURUSD', 1.1070)
        self.assertEqual(len(below), 2)  # 1.1000, 1.1050
    
    def test_nearest_zone(self):
        """Test finding nearest zone in direction."""
        zones = [
            LiquidityZone('EURUSD', 1.1000, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('EURUSD', 1.1050, 0.0010, LiquiditySource.PIVOT_M5),
            LiquidityZone('EURUSD', 1.1100, 0.0010, LiquiditySource.ROUND),
        ]
        
        for zone in zones:
            self.map.add_zone(zone)
        
        # From 1.1070, nearest above is 1.1100
        nearest_above = self.map.get_nearest_zone('EURUSD', 1.1070, direction='UP')
        self.assertIsNotNone(nearest_above)
        self.assertEqual(nearest_above.price_center, 1.1100)
        
        # From 1.1070, nearest below is 1.1050
        nearest_below = self.map.get_nearest_zone('EURUSD', 1.1070, direction='DOWN')
        self.assertIsNotNone(nearest_below)
        self.assertEqual(nearest_below.price_center, 1.1050)
    
    def test_zone_sorting_by_strength(self):
        """Test zones are sorted by strength score."""
        zones = [
            LiquidityZone('EURUSD', 1.1000, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('EURUSD', 1.1050, 0.0010, LiquiditySource.PIVOT_M5),
            LiquidityZone('EURUSD', 1.1100, 0.0010, LiquiditySource.ROUND),
        ]
        
        # Set different strengths
        zones[0].strength_score = 0.9
        zones[1].strength_score = 0.5
        zones[2].strength_score = 0.7
        
        for zone in zones:
            self.map.add_zone(zone)
        
        # Get sorted zones
        sorted_zones = self.map.get_zones('EURUSD', min_strength=0.0)
        
        # Should be sorted by strength descending
        self.assertEqual(sorted_zones[0].strength_score, 0.9)
        self.assertEqual(sorted_zones[1].strength_score, 0.7)
        self.assertEqual(sorted_zones[2].strength_score, 0.5)
    
    def test_update_from_bar(self):
        """Test zone statistics update from bar."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        zone_id = self.map.add_zone(zone)
        
        # Update from bar that touches zone
        self.map.update_from_bar(
            'EURUSD',
            high=1.1055,
            low=1.1045,
            close=1.1052
        )
        
        # Zone should have been touched
        updated_zone = self.map.zones[zone_id]
        self.assertGreater(updated_zone.touch_count, 0)
    
    def test_min_strength_filter(self):
        """Test filtering zones by minimum strength."""
        zones = [
            LiquidityZone('EURUSD', 1.1000, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('EURUSD', 1.1050, 0.0010, LiquiditySource.PIVOT_M5),
        ]
        
        zones[0].strength_score = 0.3
        zones[1].strength_score = 0.8
        
        for zone in zones:
            self.map.add_zone(zone)
        
        # Get zones with min strength 0.6
        strong_zones = self.map.get_zones('EURUSD', min_strength=0.6)
        
        self.assertEqual(len(strong_zones), 1)
        self.assertEqual(strong_zones[0].strength_score, 0.8)
    
    def test_clear_symbol(self):
        """Test clearing all zones for a symbol."""
        zones = [
            LiquidityZone('EURUSD', 1.1000, 0.0010, LiquiditySource.ROUND),
            LiquidityZone('GBPUSD', 1.3050, 0.0010, LiquiditySource.ROUND),
        ]
        
        for zone in zones:
            self.map.add_zone(zone)
        
        # Clear EURUSD zones
        self.map.clear_symbol('EURUSD')
        
        eu_zones = self.map.get_zones('EURUSD')
        gbp_zones = self.map.get_zones('GBPUSD')
        
        self.assertEqual(len(eu_zones), 0)
        self.assertEqual(len(gbp_zones), 1)
    
    def test_multiple_liquidity_sources(self):
        """Test all liquidity sources can be added."""
        sources = [
            LiquiditySource.VWAP_DAILY,
            LiquiditySource.PIVOT_M5,
            LiquiditySource.WYCKOFF,
            LiquiditySource.CLUSTER,
            LiquiditySource.ROUND,
        ]
        
        for i, source in enumerate(sources):
            zone = LiquidityZone(
                symbol='EURUSD',
                price_center=1.1000 + i * 0.0010,
                price_range=0.0005,
                source=source,
            )
            self.map.add_zone(zone)
        
        # Verify all zones added
        all_zones = self.map.get_zones('EURUSD')
        self.assertEqual(len(all_zones), len(sources))


class TestLiquidityZoneStatistics(unittest.TestCase):
    """Test zone statistics tracking."""
    
    def test_strength_score_calculation(self):
        """Test strength score is calculated from hold probability and test count."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        zone.prob_hold = 0.7
        zone.touch_count = 2  # Few tests
        
        strength = zone.strength_score
        
        # Strength should be high (prob_hold * decay factor)
        self.assertGreater(strength, 0.6)
    
    def test_zone_history(self):
        """Test zone maintains history of updates."""
        zone = LiquidityZone(
            symbol='EURUSD',
            price_center=1.1050,
            price_range=0.0010,
            source=LiquiditySource.ROUND,
        )
        
        # Record multiple tests
        zone.touch_count += 1
        zone.hold_count += 1
        
        zone.touch_count += 1
        zone.break_count += 1
        
        self.assertEqual(zone.touch_count, 2)
        self.assertEqual(zone.hold_count, 1)
        self.assertEqual(zone.break_count, 1)


if __name__ == '__main__':
    unittest.main()
