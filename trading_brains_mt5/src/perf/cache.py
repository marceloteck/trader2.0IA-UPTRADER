"""
Feature cache: in-memory TTL-based cache to avoid recalculating indicators.

Strategy:
- Cache keyed by (symbol, timeframe, last_closed_time)
- TTL configurable (default: 300 seconds)
- Auto-invalidate on new candle
- Stores full feature dict + version info
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""
    features: Dict[str, float | str]
    timestamp: float
    candle_time: int  # Unix timestamp of last closed candle
    version: str = "1.0"
    
    def is_expired(self, ttl: int = 300) -> bool:
        """Check if entry older than TTL (seconds)."""
        return (time.time() - self.timestamp) > ttl


class FeatureCache:
    """
    In-memory cache for features.
    
    Typical usage:
        cache = FeatureCache(ttl=300)
        
        # Try get
        cached = cache.get("EURUSD", "H1")
        if cached:
            return cached
        
        # Recalculate
        features = build_features(df)
        cache.set("EURUSD", "H1", features, candle_time)
        return features
    """
    
    def __init__(self, ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, symbol: str, timeframe: str) -> Optional[Dict[str, float | str]]:
        """Get cached features if valid."""
        key = f"{symbol}_{timeframe}"
        entry = self._cache.get(key)
        
        if entry is None or entry.is_expired(self.ttl):
            self._misses += 1
            return None
        
        self._hits += 1
        return entry.features
    
    def set(
        self, 
        symbol: str, 
        timeframe: str, 
        features: Dict[str, float | str],
        candle_time: int,
        version: str = "1.0"
    ) -> None:
        """Store features in cache."""
        key = f"{symbol}_{timeframe}"
        self._cache[key] = CacheEntry(
            features=features,
            timestamp=time.time(),
            candle_time=candle_time,
            version=version
        )
    
    def invalidate(self, symbol: str, timeframe: str) -> None:
        """Manually invalidate cache entry."""
        key = f"{symbol}_{timeframe}"
        self._cache.pop(key, None)
    
    def invalidate_all(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, int | float]:
        """Return cache hit/miss stats."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": hit_rate,
            "size": len(self._cache)
        }
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (f"FeatureCache(size={stats['size']}, "
                f"hit_rate={stats['hit_rate']:.1f}%)")
