"""
M&A prediction endpoints.

Provides REST API for accessing M&A predictions, watchlists,
and potential acquirer matches.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_db_session,
    get_pagination,
    PaginationParams,
    optional_api_key,
)

router = APIRouter(prefix="/predictions", tags=["predictions"])


# Response Models
class WatchlistItem(BaseModel):
    """M&A watchlist item with ranking."""

    rank: int = Field(..., description="Rank in watchlist (1 = highest)")
    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    ma_score: float = Field(..., ge=0, le=100, description="M&A likelihood score")
    score_change_7d: Optional[float] = Field(None, description="Score change over 7 days")
    score_change_30d: Optional[float] = Field(None, description="Score change over 30 days")
    market_cap_usd: float = Field(..., description="Market capitalization")
    runway_quarters: Optional[float] = Field(None, description="Cash runway in quarters")
    top_signals: List[str] = Field(..., description="Top M&A signals")
    score_components: dict = Field(..., description="Score breakdown by component")
    last_updated: datetime = Field(..., description="Last score update")

    class Config:
        json_schema_extra = {
            "example": {
                "rank": 1,
                "ticker": "WXYZ",
                "name": "XYZ Biotech",
                "ma_score": 85.0,
                "score_change_7d": 5.2,
                "score_change_30d": 12.5,
                "market_cap_usd": 800000000.0,
                "runway_quarters": 3.5,
                "top_signals": [
                    "Cash runway below 1 year",
                    "Phase 3 trial success",
                    "CFO sold 50% of holdings",
                ],
                "score_components": {
                    "pipeline": 9.0,
                    "patent": 7.5,
                    "financial": 9.5,
                    "insider": 8.0,
                    "strategic_fit": 8.5,
                    "regulatory": 7.5,
                },
                "last_updated": "2025-12-07T10:30:00Z",
            }
        }


class WatchlistResponse(BaseModel):
    """M&A watchlist response."""

    watchlist: List[WatchlistItem]
    total: int = Field(..., description="Total companies in watchlist")
    min_score: float = Field(..., description="Minimum score threshold")
    generated_at: datetime = Field(..., description="When watchlist was generated")


class AcquirerMatch(BaseModel):
    """Potential acquirer match."""

    acquirer_ticker: str = Field(..., description="Acquirer ticker symbol")
    acquirer_name: str = Field(..., description="Acquirer company name")
    match_score: float = Field(..., ge=0, le=100, description="Match score")
    strategic_fit: float = Field(..., ge=0, le=10, description="Strategic fit score")
    financial_capacity: float = Field(..., ge=0, le=10, description="Financial capacity score")
    therapeutic_overlap: List[str] = Field(..., description="Overlapping therapeutic areas")
    rationale: List[str] = Field(..., description="Key reasons for match")
    similar_deals: Optional[List[dict]] = Field(None, description="Similar historical deals")

    class Config:
        json_schema_extra = {
            "example": {
                "acquirer_ticker": "PFE",
                "acquirer_name": "Pfizer Inc.",
                "match_score": 88.5,
                "strategic_fit": 9.0,
                "financial_capacity": 10.0,
                "therapeutic_overlap": ["oncology"],
                "rationale": [
                    "Strong oncology franchise",
                    "Recent acquisitions in similar space",
                    "Portfolio gap in PD-L1 inhibitors",
                ],
                "similar_deals": [
                    {
                        "year": 2023,
                        "target": "Seagen",
                        "value_usd": 43000000000,
                        "therapeutic_area": "oncology",
                    }
                ],
            }
        }


class AcquirersResponse(BaseModel):
    """Potential acquirers response."""

    target_ticker: str
    target_name: str
    acquirers: List[AcquirerMatch]
    total: int


class TargetAcquirerPair(BaseModel):
    """Target-acquirer pairing."""

    target_ticker: str
    target_name: str
    target_ma_score: float
    acquirer_ticker: str
    acquirer_name: str
    match_score: float
    combined_rationale: List[str]
    estimated_value_range_usd: Optional[dict] = Field(
        None, description="Estimated deal value range"
    )
    probability: float = Field(..., ge=0, le=1, description="Deal probability")

    class Config:
        json_schema_extra = {
            "example": {
                "target_ticker": "WXYZ",
                "target_name": "XYZ Biotech",
                "target_ma_score": 85.0,
                "acquirer_ticker": "PFE",
                "acquirer_name": "Pfizer Inc.",
                "match_score": 88.5,
                "combined_rationale": [
                    "Target: Cash-constrained with runway < 1 year",
                    "Target: Phase 3 asset in oncology",
                    "Acquirer: Strong oncology franchise",
                    "Acquirer: Portfolio gap in target's mechanism",
                ],
                "estimated_value_range_usd": {"low": 1200000000, "high": 1800000000},
                "probability": 0.65,
            }
        }


class MatchesResponse(BaseModel):
    """All target-acquirer matches response."""

    matches: List[TargetAcquirerPair]
    total: int
    filters_applied: dict


# Endpoints
@router.get("/watchlist", response_model=WatchlistResponse)
async def get_ma_watchlist(
    min_score: float = Query(70, ge=0, le=100, description="Minimum M&A score"),
    sort_by: str = Query(
        "ma_score", description="Sort by: ma_score, score_change_7d, score_change_30d"
    ),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get current M&A watchlist ranked by acquisition likelihood.

    Returns companies above the score threshold, ranked by M&A score.
    Includes score trends, top signals, and component breakdown.
    """
    from src.database.client import DatabaseClient
    from src.api.routes.companies import company_to_dict  # Helper if needed, or manual mapping

    async with DatabaseClient() as db:
        # Get latest scores
        scores = await db.scores.get_by_score_range(min_score=min_score)
        
        # Filter and sort
        items = []
        for score in scores:
            company = await db.companies.get_by_id(score.company_id)
            if not company:
                continue
                
            # Get specific signals for this company if needed to populate "top_signals"
            # For efficiency in list view, might want to fetch these in bulk or simplify
            signals = await db.signals.get_by_company(score.company_id, limit=3)
            top_signal_titles = [s.title for s in signals]

            # Calculate score changes (mocked for now or fetched if history exists)
            # Logic for changes 7d/30d would go here.
            
            items.append(WatchlistItem(
                rank=0, # Updated later
                ticker=company.ticker,
                name=company.name,
                ma_score=score.total_score,
                score_change_7d=0.0, # Placeholder
                score_change_30d=0.0, # Placeholder
                market_cap_usd=company.market_cap_usd,
                runway_quarters=company.runway_quarters,
                top_signals=top_signal_titles,
                score_components={
                    "pipeline": score.pipeline_score,
                    "patent": score.patent_score,
                    "financial": score.financial_score,
                    "insider": score.insider_score,
                    "strategic_fit": score.strategic_fit_score,
                    "regulatory": score.regulatory_score,
                },
                last_updated=score.score_date,
            ))

    # Sort
    if sort_by == "ma_score":
        items.sort(key=lambda x: x.ma_score, reverse=True)
    elif sort_by == "score_change_7d":
        items.sort(key=lambda x: x.score_change_7d or 0, reverse=True)
    elif sort_by == "score_change_30d":
        items.sort(key=lambda x: x.score_change_30d or 0, reverse=True)
    elif sort_by == "market_cap":
         items.sort(key=lambda x: x.market_cap_usd, reverse=True)

    # Update ranks
    for i, item in enumerate(items, 1):
        item.rank = i

    # Paginate
    total = len(items)
    start = pagination.offset
    end = start + pagination.limit
    page_items = items[start:end]

    return WatchlistResponse(
        watchlist=page_items,
        total=total,
        min_score=min_score,
        generated_at=datetime.utcnow(),
    )


@router.get("/top", response_model=WatchlistResponse)
async def get_top_candidates(
    n: int = Query(10, ge=1, le=100, description="Number of top candidates to return"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get top N acquisition candidates.

    Returns the highest-scoring companies most likely to be acquired.
    Optionally filter by therapeutic area.
    """
    # TODO: Implement actual database query
    # Reuse watchlist logic but limit to top N
    mock_watchlist = [
        WatchlistItem(
            rank=1,
            ticker="WXYZ",
            name="XYZ Biotech",
            ma_score=85.0,
            score_change_7d=5.2,
            score_change_30d=12.5,
            market_cap_usd=800000000.0,
            runway_quarters=3.5,
            top_signals=["Cash runway below 1 year", "Phase 3 trial success"],
            score_components={
                "pipeline": 9.0,
                "patent": 7.5,
                "financial": 9.5,
                "insider": 8.0,
                "strategic_fit": 8.5,
                "regulatory": 7.5,
            },
            last_updated=datetime.utcnow(),
        ),
    ]

    # Limit to top N
    top_items = mock_watchlist[:n]

    return WatchlistResponse(
        watchlist=top_items,
        total=len(top_items),
        min_score=0,
        generated_at=datetime.utcnow(),
    )


@router.get("/{ticker}/acquirers", response_model=AcquirersResponse)
async def get_potential_acquirers(
    ticker: str,
    min_match_score: float = Query(
        60, ge=0, le=100, description="Minimum match score threshold"
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of acquirers"),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get potential acquirers for a target company.

    Returns ranked list of companies that could acquire the target,
    with strategic fit analysis and deal rationale.
    """
    ticker = ticker.upper()

    # TODO: Implement actual database query and matching algorithm
    # Mock response
    mock_acquirers = [
        AcquirerMatch(
            acquirer_ticker="PFE",
            acquirer_name="Pfizer Inc.",
            match_score=88.5,
            strategic_fit=9.0,
            financial_capacity=10.0,
            therapeutic_overlap=["oncology"],
            rationale=[
                "Strong oncology franchise",
                "Recent acquisitions in similar space",
                "Portfolio gap in PD-L1 inhibitors",
            ],
            similar_deals=[
                {
                    "year": 2023,
                    "target": "Seagen",
                    "value_usd": 43000000000,
                    "therapeutic_area": "oncology",
                }
            ],
        ),
        AcquirerMatch(
            acquirer_ticker="BMY",
            acquirer_name="Bristol Myers Squibb",
            match_score=82.0,
            strategic_fit=8.5,
            financial_capacity=9.0,
            therapeutic_overlap=["oncology", "immunology"],
            rationale=[
                "Established oncology portfolio",
                "History of acquiring immunotherapy companies",
                "Complementary pipeline",
            ],
            similar_deals=[],
        ),
    ]

    # Apply filters
    filtered = [acq for acq in mock_acquirers if acq.match_score >= min_match_score]
    filtered = filtered[:limit]

    return AcquirersResponse(
        target_ticker=ticker,
        target_name="Target Company Name",  # Would fetch from DB
        acquirers=filtered,
        total=len(filtered),
    )


@router.get("/matches", response_model=MatchesResponse)
async def get_all_matches(
    min_target_score: float = Query(
        70, ge=0, le=100, description="Minimum target M&A score"
    ),
    min_match_score: float = Query(
        60, ge=0, le=100, description="Minimum match score"
    ),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
    min_probability: Optional[float] = Query(
        None, ge=0, le=1, description="Minimum deal probability"
    ),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get all target-acquirer pairings above threshold.

    Returns comprehensive list of potential M&A matches with probabilities
    and estimated deal values. Useful for market-wide M&A analysis.
    """
    # TODO: Implement actual database query and matching algorithm
    # Mock response
    mock_matches = [
        TargetAcquirerPair(
            target_ticker="WXYZ",
            target_name="XYZ Biotech",
            target_ma_score=85.0,
            acquirer_ticker="PFE",
            acquirer_name="Pfizer Inc.",
            match_score=88.5,
            combined_rationale=[
                "Target: Cash-constrained with runway < 1 year",
                "Target: Phase 3 asset in oncology",
                "Acquirer: Strong oncology franchise",
                "Acquirer: Portfolio gap in target's mechanism",
            ],
            estimated_value_range_usd={"low": 1200000000, "high": 1800000000},
            probability=0.65,
        ),
    ]

    # Apply filters
    filtered = mock_matches
    if min_target_score:
        filtered = [m for m in filtered if m.target_ma_score >= min_target_score]
    if min_match_score:
        filtered = [m for m in filtered if m.match_score >= min_match_score]
    if min_probability:
        filtered = [m for m in filtered if m.probability >= min_probability]

    # Sort by combined score (target_ma_score * match_score)
    filtered.sort(
        key=lambda x: x.target_ma_score * x.match_score, reverse=True
    )

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return MatchesResponse(
        matches=page_items,
        total=total,
        filters_applied={
            "min_target_score": min_target_score,
            "min_match_score": min_match_score,
            "therapeutic_area": therapeutic_area,
            "min_probability": min_probability,
        },
    )
