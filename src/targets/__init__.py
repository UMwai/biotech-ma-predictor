"""
Target Identification Engine for Biotech M&A

This module provides sophisticated tools for identifying, screening, and ranking
potential biotech acquisition targets based on multiple factors including:
- Market cap and financial health
- Pipeline quality and therapeutic area
- Strategic fit with likely acquirers
- Market timing and deal probability
"""

from .identifier import TargetIdentifier
from .screener import TargetScreener, ScreeningCriteria
from .ranker import TargetRanker, RankingWeights
from .watchlist import (
    AcquisitionTarget,
    AcquirerMatch,
    ValuationRange,
    WatchlistManager,
    RankedWatchlist
)

__all__ = [
    'TargetIdentifier',
    'TargetScreener',
    'ScreeningCriteria',
    'TargetRanker',
    'RankingWeights',
    'AcquisitionTarget',
    'AcquirerMatch',
    'ValuationRange',
    'WatchlistManager',
    'RankedWatchlist'
]

__version__ = '1.0.0'
