from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, Iterator, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import pandas as pd

from .mt5_client import MT5Client
from ..config.settings import load_settings

logger = logging.getLogger(__name__)


def stream_latest_candles(
    client: MT5Client,
    symbol: str,
    timeframes: list[str],
    poll_seconds: int = 10,
) -> Iterator[Dict[str, pd.DataFrame]]:
    last_times: Dict[str, datetime] = {}
    while True:
        bundle: Dict[str, pd.DataFrame] = {}
        for tf in timeframes:
            df = client.fetch_latest_rates(symbol, tf, n=500)
            if df.empty:
                bundle[tf] = df
                continue
            latest_time = df.iloc[-1]["time"]
            if last_times.get(tf) != latest_time:
                last_times[tf] = latest_time
                bundle[tf] = df
        if bundle:
            yield bundle
        time.sleep(poll_seconds)


def stream_multi_symbol_candles(
    client: MT5Client,
    primary_symbol: str,
    cross_symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    poll_seconds: int = 10,
) -> Iterator[Dict[str, Dict[str, pd.DataFrame]]]:
    """
    Stream candles for primary symbol and cross-market symbols in parallel.
    
    Args:
        client: MT5Client instance
        primary_symbol: Primary trading symbol (e.g., 'WDO$N')
        cross_symbols: List of cross-market symbols (e.g., ['IBOV', 'DXY'])
        timeframes: List of timeframes (e.g., ['M5', 'M15', 'H1'])
        poll_seconds: Polling interval in seconds
    
    Yields:
        Dictionary with structure:
        {
            'primary': {'M5': df, 'M15': df, ...},
            'cross': {'IBOV': {'M5': df, ...}, 'DXY': {'M5': df, ...}},
            'cross_available': set of available cross symbols
        }
    """
    if not cross_symbols:
        cross_symbols = []
    
    if not timeframes:
        timeframes = ['M5', 'M15', 'H1']
    
    last_times: Dict[str, Dict[str, datetime]] = {
        primary_symbol: {},
    }
    for sym in cross_symbols:
        last_times[sym] = {}
    
    while True:
        bundle = {
            'primary': {},
            'cross': {},
            'cross_available': set()
        }
        
        # Load primary symbol
        try:
            for tf in timeframes:
                df = client.fetch_latest_rates(primary_symbol, tf, n=500)
                if df.empty:
                    bundle['primary'][tf] = df
                    continue
                latest_time = df.iloc[-1]["time"]
                if last_times[primary_symbol].get(tf) != latest_time:
                    last_times[primary_symbol][tf] = latest_time
                    bundle['primary'][tf] = df
        except Exception as e:
            logger.error(f"Error loading {primary_symbol}: {e}")
            bundle['primary'] = {}
        
        # Load cross symbols in parallel
        if cross_symbols:
            with ThreadPoolExecutor(max_workers=len(cross_symbols)) as executor:
                futures = {}
                for sym in cross_symbols:
                    future = executor.submit(_fetch_symbol_candles, client, sym, timeframes)
                    futures[sym] = future
                
                for sym, future in futures.items():
                    try:
                        symbol_data = future.result(timeout=5.0)
                        if symbol_data:
                            bundle['cross'][sym] = symbol_data
                            bundle['cross_available'].add(sym)
                    except Exception as e:
                        logger.warning(f"Failed to load {sym}: {e}")
                        # Graceful degradation: continue without this symbol
        
        # Only yield if we have primary data
        if bundle['primary']:
            yield bundle
        
        time.sleep(poll_seconds)


def _fetch_symbol_candles(
    client: MT5Client,
    symbol: str,
    timeframes: List[str],
) -> Optional[Dict[str, pd.DataFrame]]:
    """Fetch all timeframes for a single symbol."""
    result = {}
    for tf in timeframes:
        try:
            df = client.fetch_latest_rates(symbol, tf, n=500)
            result[tf] = df
        except Exception as e:
            logger.warning(f"Error loading {symbol} {tf}: {e}")
            result[tf] = pd.DataFrame()
    
    return result if result else None


def synchronize_multi_symbol_data(
    primary_df: pd.DataFrame,
    cross_dfs: Dict[str, pd.DataFrame],
    join_method: str = 'nearest',
) -> Dict[str, pd.DataFrame]:
    """
    Synchronize primary and cross-market data by timestamp.
    
    Args:
        primary_df: Primary symbol OHLC data with 'time' column
        cross_dfs: Dict of {symbol: OHLC dataframe}
        join_method: 'nearest' or 'bfill' for missing data
    
    Returns:
        Synchronized dataframe with primary + aligned cross data
    """
    if primary_df.empty or not cross_dfs:
        return primary_df
    
    # Ensure primary has time column
    if 'time' not in primary_df.columns:
        logger.warning("Primary data missing 'time' column")
        return primary_df
    
    result = primary_df.copy()
    
    for symbol, cross_df in cross_dfs.items():
        if cross_df.empty:
            logger.warning(f"Cross symbol {symbol} has empty data")
            continue
        
        if 'time' not in cross_df.columns:
            logger.warning(f"Cross symbol {symbol} missing 'time' column")
            continue
        
        try:
            # Use merge_asof for nearest-timestamp join
            merged = pd.merge_asof(
                result.sort_values('time'),
                cross_df.sort_values('time'),
                on='time',
                direction=join_method,
                suffixes=('', f'_{symbol}')
            )
            result = merged
        except Exception as e:
            logger.error(f"Error synchronizing {symbol}: {e}")
            continue
    
    return result
