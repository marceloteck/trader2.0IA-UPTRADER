"""Test cache module."""

import pytest
import time
from src.perf.cache import FeatureCache


def test_cache_hit():
    """Test cache hit."""
    cache = FeatureCache(ttl=300)
    features = {"close": 1.5, "atr": 0.05, "regime": "trending"}
    
    cache.set("EURUSD", "H1", features, 1000)
    cached = cache.get("EURUSD", "H1")
    
    assert cached == features
    assert cache.get_stats()["hits"] == 1


def test_cache_miss():
    """Test cache miss."""
    cache = FeatureCache(ttl=300)
    cached = cache.get("EURUSD", "H1")
    
    assert cached is None
    assert cache.get_stats()["misses"] == 1


def test_cache_ttl_expiry():
    """Test TTL expiry."""
    cache = FeatureCache(ttl=1)  # 1 second TTL
    features = {"close": 1.5}
    
    cache.set("EURUSD", "H1", features, 1000)
    assert cache.get("EURUSD", "H1") is not None
    
    time.sleep(1.1)  # Wait for expiry
    assert cache.get("EURUSD", "H1") is None


def test_cache_invalidate():
    """Test manual invalidation."""
    cache = FeatureCache()
    features = {"close": 1.5}
    
    cache.set("EURUSD", "H1", features, 1000)
    cache.invalidate("EURUSD", "H1")
    
    assert cache.get("EURUSD", "H1") is None


def test_cache_stats():
    """Test cache statistics."""
    cache = FeatureCache()
    features = {"close": 1.5}
    
    cache.set("EURUSD", "H1", features, 1000)
    cache.get("EURUSD", "H1")  # Hit
    cache.get("GBPUSD", "H1")  # Miss
    
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total"] == 2
    assert stats["hit_rate"] == 50.0
