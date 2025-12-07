"""
M&A Scoring Engine Package

This package provides comprehensive scoring capabilities for predicting
biotech M&A likelihood and matching potential acquirers with targets.

Main Components:
    - ScoringEngine: Main orchestrator for M&A likelihood scoring
    - ScoreComponents: Individual scoring component calculators
    - AcquirerMatcher: Algorithm for matching targets with potential acquirers
    - ScoringWeights: Configurable weights for composite scoring

NEW Metsera Case Study Modules (Advanced Scoring Factors):
    - ClinicalDifferentiation: Asset quality within drug class
    - TherapeuticMomentum: Market heat tracking
    - CompetitiveTension: Bidding war likelihood prediction
    - AntitrustRisk: Regulatory barrier assessment
    - PipelineGapAnalysis: Acquirer strategic need analysis
    - PremiumModel: Acquisition premium prediction

Example:
    >>> from scoring import ScoringEngine, ScoringWeights
    >>> weights = ScoringWeights()
    >>> engine = ScoringEngine(db_pool, weights)
    >>> score = await engine.calculate_ma_score("BIOTECH-123")
    >>> acquirers = await engine.match_acquirers("BIOTECH-123", top_n=5)

    >>> # NEW: Advanced scoring
    >>> from scoring import (
    ...     ClinicalDifferentiation,
    ...     TherapeuticMomentum,
    ...     CompetitiveTension,
    ...     AntitrustRisk,
    ...     PipelineGapAnalysis,
    ...     PremiumModel
    ... )
    >>> momentum = TherapeuticMomentum()
    >>> score = momentum.calculate_momentum_score("obesity_metabolic")
    >>> # Returns: 95+ (extremely hot market)
"""

from .engine import ScoringEngine, MAScore, WatchlistManager
from .components import ScoreComponents, SignalDecay
from .acquirer_matcher import AcquirerMatcher, AcquirerMatch, TherapeuticAlignment
from .weights import ScoringWeights, ComponentWeight

# NEW: Metsera case study modules
from .clinical_differentiation import (
    ClinicalDifferentiation,
    DrugAsset,
    DosingFrequency,
    RouteOfAdministration,
    MOANovelty,
)
from .therapeutic_momentum import (
    TherapeuticMomentum,
    TherapeuticArea,
    MomentumLevel,
    MADeal,
    VCInvestment,
    ClinicalTrial,
)
from .competitive_tension import (
    CompetitiveTension,
    CompetitionLevel,
    StrategicUrgency,
    PotentialAcquirer,
    TargetAsset,
)
from .antitrust_risk import (
    AntitrustRisk,
    RiskLevel,
    RegulatoryAction,
    MarketShareData,
    RegulatoryHistory,
    DealContext,
)
from .pipeline_gaps import (
    PipelineGapAnalysis,
    TherapeuticGap,
    PatentCliff,
    PipelineAsset,
    AcquirerProfile,
    GapSeverity,
)
from .premium_model import (
    PremiumModel,
    PremiumEstimate,
    PremiumInputs,
    PremiumTier,
)

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

    # NEW: Metsera case study modules
    'ClinicalDifferentiation',
    'DrugAsset',
    'DosingFrequency',
    'RouteOfAdministration',
    'MOANovelty',

    'TherapeuticMomentum',
    'TherapeuticArea',
    'MomentumLevel',
    'MADeal',
    'VCInvestment',
    'ClinicalTrial',

    'CompetitiveTension',
    'CompetitionLevel',
    'StrategicUrgency',
    'PotentialAcquirer',
    'TargetAsset',

    'AntitrustRisk',
    'RiskLevel',
    'RegulatoryAction',
    'MarketShareData',
    'RegulatoryHistory',
    'DealContext',

    'PipelineGapAnalysis',
    'TherapeuticGap',
    'PatentCliff',
    'PipelineAsset',
    'AcquirerProfile',
    'GapSeverity',

    'PremiumModel',
    'PremiumEstimate',
    'PremiumInputs',
    'PremiumTier',
]

__version__ = '1.1.0'
