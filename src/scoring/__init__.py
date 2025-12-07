"""
M&A Scoring Engine Package

This package provides comprehensive scoring capabilities for predicting
biotech M&A likelihood and matching potential acquirers with targets.

Main Components:
    - ScoringEngine: Main orchestrator for M&A likelihood scoring
    - ScoreComponents: Individual scoring component calculators
    - AcquirerMatcher: Algorithm for matching targets with potential acquirers
    - ScoringWeights: Configurable weights for composite scoring

Example:
    >>> from scoring import ScoringEngine, ScoringWeights
    >>> weights = ScoringWeights()
    >>> engine = ScoringEngine(db_pool, weights)
    >>> score = await engine.calculate_ma_score("BIOTECH-123")
    >>> acquirers = await engine.match_acquirers("BIOTECH-123", top_n=5)
"""

from .engine import ScoringEngine, MAScore, WatchlistManager
from .components import ScoreComponents, SignalDecay
from .acquirer_matcher import AcquirerMatcher, AcquirerMatch, TherapeuticAlignment
from .weights import ScoringWeights, ComponentWeight

__all__ = [
    # Main engine
    'ScoringEngine',
    'MAScore',
    'WatchlistManager',

    # Components
    'ScoreComponents',
    'SignalDecay',

    # Acquirer matching
    'AcquirerMatcher',
    'AcquirerMatch',
    'TherapeuticAlignment',

    # Configuration
    'ScoringWeights',
    'ComponentWeight',
]

__version__ = '1.0.0'
