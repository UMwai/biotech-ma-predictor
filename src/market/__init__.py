"""
Market observation module for biotech M&A prediction.

This module provides tools for:
- Tracking comparable M&A transactions
- Analyzing market signals and anomalies
- Scoring market sentiment from multiple sources
"""

from .observation import MarketSignals, MarketObservationEngine
from .comparables import ComparableDeals, Deal, ValuationRange, PremiumStats
from .sentiment import SentimentModel, SentimentScore

__all__ = [
    'MarketSignals',
    'MarketObservationEngine',
    'ComparableDeals',
    'Deal',
    'ValuationRange',
    'PremiumStats',
    'SentimentModel',
    'SentimentScore',
]
