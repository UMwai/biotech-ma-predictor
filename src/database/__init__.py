"""
Database layer for biotech M&A predictor.

Provides async database access, ORM models, and repository pattern implementations.
"""

from src.database.connection import (
    DatabaseManager,
    get_db_session,
    init_db,
    close_db,
    health_check,
)
from src.database.tables import (
    Base,
    Company,
    DrugCandidate,
    Signal,
    MAScore,
    AcquirerMatch,
    Report,
    Alert,
    Webhook,
    Client,
)
from src.database.repositories import (
    CompanyRepository,
    SignalRepository,
    ScoreRepository,
    ReportRepository,
    AlertRepository,
)
from src.database.client import DatabaseClient

__all__ = [
    # Connection management
    "DatabaseManager",
    "get_db_session",
    "init_db",
    "close_db",
    "health_check",
    # Tables
    "Base",
    "Company",
    "DrugCandidate",
    "Signal",
    "MAScore",
    "AcquirerMatch",
    "Report",
    "Alert",
    "Webhook",
    "Client",
    # Repositories
    "CompanyRepository",
    "SignalRepository",
    "ScoreRepository",
    "ReportRepository",
    "AlertRepository",
    # Client
    "DatabaseClient",
]
