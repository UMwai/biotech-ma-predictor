"""
Data Ingestion Layer for Biotech M&A Predictor

This module provides a comprehensive data ingestion framework for collecting
data from multiple sources including SEC EDGAR filings, ClinicalTrials.gov,
FDA databases, and financial market data.
"""

from src.ingestion.base import DataIngester, IngestionResult, IngestionError
from src.ingestion.sec_edgar import SECEdgarIngester
from src.ingestion.clinical_trials import ClinicalTrialsIngester
from src.ingestion.fda import FDAIngester
from src.ingestion.financial import FinancialDataIngester
from src.ingestion.orchestrator import IngestionOrchestrator

__all__ = [
    "DataIngester",
    "IngestionResult",
    "IngestionError",
    "SECEdgarIngester",
    "ClinicalTrialsIngester",
    "FDAIngester",
    "FinancialDataIngester",
    "IngestionOrchestrator",
]
