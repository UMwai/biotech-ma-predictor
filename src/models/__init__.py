"""
Core data models for the biotech M&A predictor system.

This package contains all Pydantic models used throughout the application:
- Company and pipeline models
- Signal event models
- M&A scoring models
- Report models
"""

from .company import (
    Company,
    DrugCandidate,
    Pipeline,
    TherapeuticArea,
    DevelopmentPhase,
)
from .signals import (
    BaseSignal,
    ClinicalTrialSignal,
    PatentSignal,
    InsiderSignal,
    HiringSignal,
    FinancialSignal,
    SignalType,
    TrialPhase,
    TrialStatus,
    TrialOutcome,
    TransactionType,
    InsiderRole,
    SeniorityLevel,
)
from .scoring import (
    MAScore,
    AcquirerMatch,
    Watchlist,
    WatchlistEntry,
    ScoreComponent,
    ScoreComponentType,
    RiskLevel,
)
from .reports import (
    Report,
    DailyDigest,
    WeeklyWatchlist,
    DeepDiveReport,
    AlertReport,
    ReportType,
    ReportSection,
    SectionType,
)

__all__ = [
    # Company models
    "Company",
    "DrugCandidate",
    "Pipeline",
    "TherapeuticArea",
    "DevelopmentPhase",
    # Signal models
    "BaseSignal",
    "ClinicalTrialSignal",
    "PatentSignal",
    "InsiderSignal",
    "HiringSignal",
    "FinancialSignal",
    "SignalType",
    "TrialPhase",
    "TrialStatus",
    "TrialOutcome",
    "TransactionType",
    "InsiderRole",
    "SeniorityLevel",
    # Scoring models
    "MAScore",
    "AcquirerMatch",
    "Watchlist",
    "WatchlistEntry",
    "ScoreComponent",
    "ScoreComponentType",
    "RiskLevel",
    # Report models
    "Report",
    "DailyDigest",
    "WeeklyWatchlist",
    "DeepDiveReport",
    "AlertReport",
    "ReportType",
    "ReportSection",
    "SectionType",
]
