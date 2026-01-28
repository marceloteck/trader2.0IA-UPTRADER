"""
News Filter Module - Economic Calendar Integration

Provides economic calendar filtering to prevent trading during high-impact news events.
"""

from .news_filter import NewsEvent, NewsBlock, NewsFilter

__all__ = ['NewsEvent', 'NewsBlock', 'NewsFilter']
