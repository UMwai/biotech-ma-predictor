"""
Report endpoints.

Provides REST API for accessing and generating M&A reports,
daily digests, and weekly watchlists.
"""

from typing import List, Optional
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_db_session,
    get_pagination,
    PaginationParams,
    verify_api_key,
    optional_api_key,
)

router = APIRouter(prefix="/reports", tags=["reports"])


# Enums
class ReportType(str, Enum):
    """Report type enumeration."""

    DAILY_DIGEST = "daily_digest"
    WEEKLY_WATCHLIST = "weekly_watchlist"
    COMPANY_DEEP_DIVE = "company_deep_dive"
    SECTOR_ANALYSIS = "sector_analysis"
    CUSTOM = "custom"


class ReportStatus(str, Enum):
    """Report generation status."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFormat(str, Enum):
    """Report output format."""

    JSON = "json"
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"


# Response Models
class ReportMetadata(BaseModel):
    """Report metadata."""

    report_id: str = Field(..., description="Unique report identifier")
    report_type: ReportType = Field(..., description="Type of report")
    title: str = Field(..., description="Report title")
    description: Optional[str] = Field(None, description="Report description")
    status: ReportStatus = Field(..., description="Report generation status")
    format: ReportFormat = Field(..., description="Report format")
    created_at: datetime = Field(..., description="Report creation timestamp")
    generated_at: Optional[datetime] = Field(None, description="Report generation completion time")
    file_size_bytes: Optional[int] = Field(None, description="Report file size")
    download_url: Optional[str] = Field(None, description="URL to download report")
    expires_at: Optional[datetime] = Field(None, description="Report expiration time")

    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "rpt_20251207_daily_001",
                "report_type": "daily_digest",
                "title": "Daily M&A Digest - December 7, 2025",
                "description": "Daily summary of M&A signals and score changes",
                "status": "completed",
                "format": "pdf",
                "created_at": "2025-12-07T06:00:00Z",
                "generated_at": "2025-12-07T06:05:23Z",
                "file_size_bytes": 524288,
                "download_url": "https://s3.amazonaws.com/reports/rpt_20251207_daily_001.pdf",
                "expires_at": "2025-12-14T06:00:00Z",
            }
        }


class ReportListResponse(BaseModel):
    """Report list response."""

    reports: List[ReportMetadata]
    total: int
    page: int
    page_size: int


class DailyDigestContent(BaseModel):
    """Daily digest report content."""

    date: str = Field(..., description="Report date")
    summary: str = Field(..., description="Executive summary")
    top_movers: List[dict] = Field(..., description="Companies with biggest score changes")
    new_signals: List[dict] = Field(..., description="New signals detected")
    watchlist_changes: dict = Field(..., description="Watchlist additions/removals")
    market_overview: dict = Field(..., description="Market-wide statistics")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-12-07",
                "summary": "5 new high-priority signals detected. 2 companies added to watchlist.",
                "top_movers": [
                    {
                        "ticker": "WXYZ",
                        "name": "XYZ Biotech",
                        "score_change": 12.5,
                        "new_score": 85.0,
                        "reason": "Phase 3 trial success + CFO stock sale",
                    }
                ],
                "new_signals": [
                    {
                        "ticker": "ABCD",
                        "signal_type": "clinical_trial",
                        "description": "Positive Phase 2 data announced",
                        "impact_score": 8.5,
                    }
                ],
                "watchlist_changes": {
                    "added": ["WXYZ", "LMNO"],
                    "removed": ["STUV"],
                },
                "market_overview": {
                    "total_companies_tracked": 150,
                    "watchlist_count": 25,
                    "avg_ma_score": 42.3,
                    "signals_today": 18,
                },
            }
        }


class DailyDigestResponse(BaseModel):
    """Daily digest response."""

    metadata: ReportMetadata
    content: DailyDigestContent


class WeeklyWatchlistContent(BaseModel):
    """Weekly watchlist report content."""

    week_start: str = Field(..., description="Week start date")
    week_end: str = Field(..., description="Week end date")
    summary: str = Field(..., description="Executive summary")
    watchlist: List[dict] = Field(..., description="Current watchlist with details")
    week_highlights: List[str] = Field(..., description="Key highlights from the week")
    sector_breakdown: dict = Field(..., description="Watchlist by therapeutic area")
    score_distribution: dict = Field(..., description="Distribution of M&A scores")

    class Config:
        json_schema_extra = {
            "example": {
                "week_start": "2025-12-01",
                "week_end": "2025-12-07",
                "summary": "25 companies on M&A watchlist. Oncology sector showing increased activity.",
                "watchlist": [
                    {
                        "rank": 1,
                        "ticker": "WXYZ",
                        "name": "XYZ Biotech",
                        "ma_score": 85.0,
                        "week_change": 5.2,
                        "key_catalysts": ["Cash runway < 1 year", "Phase 3 success"],
                    }
                ],
                "week_highlights": [
                    "3 new companies exceeded watchlist threshold",
                    "Record number of insider transactions",
                    "2 FDA breakthrough therapy designations",
                ],
                "sector_breakdown": {"oncology": 12, "neurology": 5, "rare_disease": 8},
                "score_distribution": {
                    "70-75": 8,
                    "75-80": 10,
                    "80-85": 5,
                    "85+": 2,
                },
            }
        }


class WeeklyWatchlistResponse(BaseModel):
    """Weekly watchlist response."""

    metadata: ReportMetadata
    content: WeeklyWatchlistContent


class GenerateReportRequest(BaseModel):
    """Request to generate a custom report."""

    report_type: ReportType = Field(..., description="Type of report to generate")
    format: ReportFormat = Field(default=ReportFormat.PDF, description="Output format")
    title: Optional[str] = Field(None, description="Custom report title")
    parameters: dict = Field(
        default_factory=dict, description="Report-specific parameters"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "report_type": "company_deep_dive",
                "format": "pdf",
                "title": "XYZ Biotech - M&A Analysis",
                "parameters": {
                    "ticker": "WXYZ",
                    "include_valuation": True,
                    "include_comparables": True,
                },
            }
        }


class GenerateReportResponse(BaseModel):
    """Response for report generation request."""

    report_id: str = Field(..., description="Report ID for tracking")
    status: ReportStatus = Field(..., description="Initial status")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    message: str = Field(..., description="Status message")


# Endpoints
@router.get("", response_model=ReportListResponse)
async def list_reports(
    report_type: Optional[ReportType] = Query(None, description="Filter by report type"),
    status: Optional[ReportStatus] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Filter by creation date start"),
    end_date: Optional[datetime] = Query(None, description="Filter by creation date end"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    List available reports with filtering and pagination.

    Returns metadata for all reports matching the filter criteria.
    """
    # TODO: Implement actual database query
    # Mock response
    mock_reports = [
        ReportMetadata(
            report_id="rpt_20251207_daily_001",
            report_type=ReportType.DAILY_DIGEST,
            title="Daily M&A Digest - December 7, 2025",
            description="Daily summary of M&A signals and score changes",
            status=ReportStatus.COMPLETED,
            format=ReportFormat.PDF,
            created_at=datetime(2025, 12, 7, 6, 0, 0),
            generated_at=datetime(2025, 12, 7, 6, 5, 23),
            file_size_bytes=524288,
            download_url="https://s3.amazonaws.com/reports/rpt_20251207_daily_001.pdf",
            expires_at=datetime(2025, 12, 14, 6, 0, 0),
        ),
    ]

    # Apply filters
    filtered = mock_reports
    if report_type:
        filtered = [r for r in filtered if r.report_type == report_type]
    if status:
        filtered = [r for r in filtered if r.status == status]

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return ReportListResponse(
        reports=page_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{report_id}", response_model=ReportMetadata)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get report metadata by ID.

    Returns detailed metadata including download URL if report is completed.
    """
    # TODO: Implement actual database query
    # Mock response
    if report_id == "rpt_20251207_daily_001":
        return ReportMetadata(
            report_id=report_id,
            report_type=ReportType.DAILY_DIGEST,
            title="Daily M&A Digest - December 7, 2025",
            description="Daily summary of M&A signals and score changes",
            status=ReportStatus.COMPLETED,
            format=ReportFormat.PDF,
            created_at=datetime(2025, 12, 7, 6, 0, 0),
            generated_at=datetime(2025, 12, 7, 6, 5, 23),
            file_size_bytes=524288,
            download_url="https://s3.amazonaws.com/reports/rpt_20251207_daily_001.pdf",
            expires_at=datetime(2025, 12, 14, 6, 0, 0),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Report {report_id} not found",
    )


@router.post("/generate", response_model=GenerateReportResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Generate a custom report on-demand.

    Requires authentication. Report generation happens asynchronously.
    Returns report ID for tracking progress.
    """
    # Generate report ID
    report_id = f"rpt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{request.report_type.value}"

    # TODO: Implement actual report generation
    # Add to background tasks
    # background_tasks.add_task(generate_report_task, report_id, request)

    return GenerateReportResponse(
        report_id=report_id,
        status=ReportStatus.PENDING,
        estimated_completion=datetime.utcnow(),
        message=f"Report generation queued. Use GET /reports/{report_id} to check status.",
    )


@router.get("/daily-digest/latest", response_model=DailyDigestResponse)
async def get_latest_daily_digest(
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get the latest daily digest report.

    Returns the most recent daily M&A digest with full content.
    """
    # TODO: Implement actual database query
    # Mock response
    metadata = ReportMetadata(
        report_id="rpt_20251207_daily_001",
        report_type=ReportType.DAILY_DIGEST,
        title="Daily M&A Digest - December 7, 2025",
        description="Daily summary of M&A signals and score changes",
        status=ReportStatus.COMPLETED,
        format=ReportFormat.JSON,
        created_at=datetime(2025, 12, 7, 6, 0, 0),
        generated_at=datetime(2025, 12, 7, 6, 5, 23),
    )

    content = DailyDigestContent(
        date="2025-12-07",
        summary="5 new high-priority signals detected. 2 companies added to watchlist.",
        top_movers=[
            {
                "ticker": "WXYZ",
                "name": "XYZ Biotech",
                "score_change": 12.5,
                "new_score": 85.0,
                "reason": "Phase 3 trial success + CFO stock sale",
            }
        ],
        new_signals=[
            {
                "ticker": "ABCD",
                "signal_type": "clinical_trial",
                "description": "Positive Phase 2 data announced",
                "impact_score": 8.5,
            }
        ],
        watchlist_changes={"added": ["WXYZ", "LMNO"], "removed": ["STUV"]},
        market_overview={
            "total_companies_tracked": 150,
            "watchlist_count": 25,
            "avg_ma_score": 42.3,
            "signals_today": 18,
        },
    )

    return DailyDigestResponse(metadata=metadata, content=content)


@router.get("/weekly-watchlist/latest", response_model=WeeklyWatchlistResponse)
async def get_latest_weekly_watchlist(
    db: AsyncSession = Depends(get_db_session),
    api_key: Optional[str] = Depends(optional_api_key),
):
    """
    Get the latest weekly watchlist report.

    Returns the most recent weekly M&A watchlist with full content.
    """
    # TODO: Implement actual database query
    # Mock response
    metadata = ReportMetadata(
        report_id="rpt_20251201_weekly_001",
        report_type=ReportType.WEEKLY_WATCHLIST,
        title="Weekly M&A Watchlist - Week of December 1-7, 2025",
        description="Weekly M&A watchlist and sector analysis",
        status=ReportStatus.COMPLETED,
        format=ReportFormat.JSON,
        created_at=datetime(2025, 12, 1, 8, 0, 0),
        generated_at=datetime(2025, 12, 1, 8, 10, 45),
    )

    content = WeeklyWatchlistContent(
        week_start="2025-12-01",
        week_end="2025-12-07",
        summary="25 companies on M&A watchlist. Oncology sector showing increased activity.",
        watchlist=[
            {
                "rank": 1,
                "ticker": "WXYZ",
                "name": "XYZ Biotech",
                "ma_score": 85.0,
                "week_change": 5.2,
                "key_catalysts": ["Cash runway < 1 year", "Phase 3 success"],
            }
        ],
        week_highlights=[
            "3 new companies exceeded watchlist threshold",
            "Record number of insider transactions",
            "2 FDA breakthrough therapy designations",
        ],
        sector_breakdown={"oncology": 12, "neurology": 5, "rare_disease": 8},
        score_distribution={"70-75": 8, "75-80": 10, "80-85": 5, "85+": 2},
    )

    return WeeklyWatchlistResponse(metadata=metadata, content=content)
