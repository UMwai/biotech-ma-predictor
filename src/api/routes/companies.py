"""
Company endpoints.

Provides REST API for accessing company profiles, drug pipelines,
and signal history.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_db_session,
    get_pagination,
    PaginationParams,
    optional_api_key,
)
from src.models.company import (
    TherapeuticArea,
    DevelopmentPhase,
    DrugCandidate,
    Pipeline,
)

router = APIRouter(prefix="/companies", tags=["companies"])


# Response Models
class CompanyListItem(BaseModel):
    """Company summary for list view."""

    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    market_cap_usd: float = Field(..., description="Market capitalization")
    therapeutic_areas: List[str] = Field(..., description="Therapeutic focus areas")
    pipeline_count: int = Field(..., description="Number of drug candidates")
    ma_score: Optional[float] = Field(None, description="M&A likelihood score (0-100)")
    last_updated: datetime = Field(..., description="Last data update")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "ABCD",
                "name": "ABC Therapeutics",
                "market_cap_usd": 1500000000.0,
                "therapeutic_areas": ["oncology", "immunology"],
                "pipeline_count": 5,
                "ma_score": 72.5,
                "last_updated": "2025-12-07T10:30:00Z",
            }
        }


class CompanyListResponse(BaseModel):
    """Paginated company list response."""

    companies: List[CompanyListItem]
    total: int = Field(..., description="Total number of companies")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether more pages available")


class CompanyProfile(BaseModel):
    """Detailed company profile."""

    ticker: str
    name: str
    market_cap_usd: float
    cash_position_usd: float
    quarterly_burn_rate_usd: Optional[float]
    total_debt_usd: float
    runway_quarters: Optional[float]
    is_cash_constrained: bool
    therapeutic_areas: List[str]
    founded_year: Optional[int]
    employee_count: Optional[int]
    headquarters_location: Optional[str]
    pipeline: Optional[Pipeline]
    ma_score: Optional[float] = Field(None, description="M&A likelihood score (0-100)")
    score_components: Optional[dict] = Field(None, description="Score breakdown by component")
    last_updated: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "ABCD",
                "name": "ABC Therapeutics",
                "market_cap_usd": 1500000000.0,
                "cash_position_usd": 250000000.0,
                "quarterly_burn_rate_usd": 30000000.0,
                "total_debt_usd": 0.0,
                "runway_quarters": 8.3,
                "is_cash_constrained": False,
                "therapeutic_areas": ["oncology", "immunology"],
                "founded_year": 2015,
                "employee_count": 120,
                "headquarters_location": "Cambridge, MA",
                "pipeline": None,
                "ma_score": 72.5,
                "score_components": {
                    "pipeline": 8.5,
                    "patent": 7.0,
                    "financial": 6.5,
                    "insider": 7.5,
                    "strategic_fit": 8.0,
                    "regulatory": 7.0,
                },
                "last_updated": "2025-12-07T10:30:00Z",
            }
        }


class SignalHistoryItem(BaseModel):
    """Signal history item."""

    signal_id: str
    signal_type: str
    timestamp: datetime
    relevance_score: float
    confidence: float
    weighted_score: float
    description: str
    metadata: dict

    class Config:
        json_schema_extra = {
            "example": {
                "signal_id": "sig_ct_20251207_001",
                "signal_type": "clinical_trial",
                "timestamp": "2025-12-07T10:30:00Z",
                "relevance_score": 8.5,
                "confidence": 0.9,
                "weighted_score": 7.65,
                "description": "Phase 2 trial completed with positive results",
                "metadata": {
                    "trial_id": "NCT12345678",
                    "drug_name": "ABC-123",
                    "outcome": "positive",
                },
            }
        }


class SignalHistoryResponse(BaseModel):
    """Signal history response."""

    ticker: str
    signals: List[SignalHistoryItem]
    total: int
    date_range: dict


# Endpoints
@router.get("", response_model=CompanyListResponse)
async def list_companies(
    therapeutic_area: Optional[TherapeuticArea] = Query(None, description="Filter by therapeutic area"),
    min_market_cap: Optional[float] = Query(None, description="Minimum market cap in USD"),
    max_market_cap: Optional[float] = Query(None, description="Maximum market cap in USD"),
    min_ma_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum M&A score"),
    cash_constrained_only: bool = Query(False, description="Show only cash-constrained companies"),
    sort_by: str = Query("ma_score", description="Sort by: ma_score, market_cap, name"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    List companies with filtering and pagination.

    Filter by therapeutic area, market cap, M&A score, and cash constraints.
    Returns paginated list with company summaries.
    """
    # TODO: Implement actual database query
    # This is a mock implementation
    mock_companies = [
        CompanyListItem(
            ticker="ABCD",
            name="ABC Therapeutics",
            market_cap_usd=1500000000.0,
            therapeutic_areas=["oncology", "immunology"],
            pipeline_count=5,
            ma_score=72.5,
            last_updated=datetime.utcnow(),
        ),
        CompanyListItem(
            ticker="WXYZ",
            name="XYZ Biotech",
            market_cap_usd=800000000.0,
            therapeutic_areas=["neurology"],
            pipeline_count=3,
            ma_score=85.0,
            last_updated=datetime.utcnow(),
        ),
    ]

    # Apply filters
    filtered = mock_companies
    if min_ma_score is not None:
        filtered = [c for c in filtered if c.ma_score and c.ma_score >= min_ma_score]

    # Sort
    if sort_by == "ma_score":
        filtered.sort(key=lambda x: x.ma_score or 0, reverse=(sort_order == "desc"))
    elif sort_by == "market_cap":
        filtered.sort(key=lambda x: x.market_cap_usd, reverse=(sort_order == "desc"))
    elif sort_by == "name":
        filtered.sort(key=lambda x: x.name, reverse=(sort_order == "desc"))

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return CompanyListResponse(
        companies=page_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        has_more=end < total,
    )


@router.get("/{ticker}", response_model=CompanyProfile)
async def get_company_profile(
    ticker: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get detailed company profile with M&A score.

    Includes:
    - Financial metrics
    - Drug pipeline
    - M&A likelihood score with component breakdown
    - Company metadata
    """
    ticker = ticker.upper()

    # TODO: Implement actual database query
    # Mock response
    if ticker == "ABCD":
        return CompanyProfile(
            ticker="ABCD",
            name="ABC Therapeutics",
            market_cap_usd=1500000000.0,
            cash_position_usd=250000000.0,
            quarterly_burn_rate_usd=30000000.0,
            total_debt_usd=0.0,
            runway_quarters=8.3,
            is_cash_constrained=False,
            therapeutic_areas=["oncology", "immunology"],
            founded_year=2015,
            employee_count=120,
            headquarters_location="Cambridge, MA",
            pipeline=None,  # Would include full pipeline data
            ma_score=72.5,
            score_components={
                "pipeline": 8.5,
                "patent": 7.0,
                "financial": 6.5,
                "insider": 7.5,
                "strategic_fit": 8.0,
                "regulatory": 7.0,
            },
            last_updated=datetime.utcnow(),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Company with ticker {ticker} not found",
    )


@router.get("/{ticker}/signals", response_model=SignalHistoryResponse)
async def get_company_signals(
    ticker: str,
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    start_date: Optional[datetime] = Query(None, description="Start date for signals"),
    end_date: Optional[datetime] = Query(None, description="End date for signals"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum relevance score"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get signal history for a company.

    Returns chronological list of M&A signals with scores and metadata.
    Supports filtering by signal type, date range, and relevance score.
    """
    ticker = ticker.upper()

    # TODO: Implement actual database query
    # Mock response
    mock_signals = [
        SignalHistoryItem(
            signal_id="sig_ct_20251207_001",
            signal_type="clinical_trial",
            timestamp=datetime.utcnow(),
            relevance_score=8.5,
            confidence=0.9,
            weighted_score=7.65,
            description="Phase 2 trial completed with positive results",
            metadata={
                "trial_id": "NCT12345678",
                "drug_name": "ABC-123",
                "outcome": "positive",
            },
        ),
    ]

    # Apply filters
    filtered = mock_signals
    if signal_type:
        filtered = [s for s in filtered if s.signal_type == signal_type]
    if min_score is not None:
        filtered = [s for s in filtered if s.relevance_score >= min_score]

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return SignalHistoryResponse(
        ticker=ticker,
        signals=page_items,
        total=total,
        date_range={
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
        },
    )


@router.get("/{ticker}/pipeline", response_model=Pipeline)
async def get_company_pipeline(
    ticker: str,
    phase: Optional[DevelopmentPhase] = Query(None, description="Filter by development phase"),
    therapeutic_area: Optional[TherapeuticArea] = Query(
        None, description="Filter by therapeutic area"
    ),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get company's drug development pipeline.

    Returns detailed information about all drug candidates with optional filtering
    by development phase and therapeutic area.
    """
    ticker = ticker.upper()

    # TODO: Implement actual database query
    # Mock response
    if ticker == "ABCD":
        mock_pipeline = Pipeline(
            company_ticker=ticker,
            drugs=[
                DrugCandidate(
                    name="ABC-123",
                    phase=DevelopmentPhase.PHASE_2,
                    indication="Non-small cell lung cancer",
                    mechanism="PD-L1 inhibitor",
                    therapeutic_area=TherapeuticArea.ONCOLOGY,
                    orphan_designation=True,
                    competitive_landscape_score=7.5,
                    market_potential_usd=Decimal("2500000000"),
                ),
            ],
            last_updated=datetime.utcnow(),
        )

        # Apply filters
        if phase:
            mock_pipeline.drugs = [d for d in mock_pipeline.drugs if d.phase == phase]
        if therapeutic_area:
            mock_pipeline.drugs = [
                d for d in mock_pipeline.drugs if d.therapeutic_area == therapeutic_area
            ]

        return mock_pipeline

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Company with ticker {ticker} not found",
    )
