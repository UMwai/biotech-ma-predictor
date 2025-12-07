"""
Report data models.

Defines models for various report types including daily digests,
weekly watchlists, and deep-dive analyses.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict


class ReportType(str, Enum):
    """Types of reports."""

    DAILY_DIGEST = "daily_digest"
    WEEKLY_WATCHLIST = "weekly_watchlist"
    DEEP_DIVE = "deep_dive"
    CUSTOM = "custom"
    ALERT = "alert"
    QUARTERLY_REVIEW = "quarterly_review"


class ReportFormat(str, Enum):
    """Report output formats."""

    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"


class SectionType(str, Enum):
    """Types of report sections."""

    EXECUTIVE_SUMMARY = "executive_summary"
    KEY_METRICS = "key_metrics"
    SIGNALS_SUMMARY = "signals_summary"
    COMPANY_ANALYSIS = "company_analysis"
    PIPELINE_REVIEW = "pipeline_review"
    FINANCIAL_ANALYSIS = "financial_analysis"
    ACQUIRER_ANALYSIS = "acquirer_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    RECOMMENDATIONS = "recommendations"
    METHODOLOGY = "methodology"
    DATA_SOURCES = "data_sources"
    APPENDIX = "appendix"


class ReportSection(BaseModel):
    """
    Individual section within a report.

    Contains structured content for one aspect of the analysis.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "section_type": "executive_summary",
                "title": "Executive Summary",
                "content": "This report analyzes...",
                "order": 1,
            }
        }
    )

    section_type: SectionType = Field(..., description="Type of section")
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")

    order: int = Field(default=0, ge=0, description="Display order in report")

    subsections: List["ReportSection"] = Field(
        default_factory=list,
        description="Nested subsections"
    )

    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data for this section"
    )

    charts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chart/visualization specifications"
    )

    @field_validator("title", "content")
    @classmethod
    def validate_text_fields(cls, v: str) -> str:
        """Validate text fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @computed_field
    @property
    def word_count(self) -> int:
        """Approximate word count of content."""
        return len(self.content.split())

    @computed_field
    @property
    def has_data(self) -> bool:
        """Whether section has structured data."""
        return bool(self.data)

    @computed_field
    @property
    def has_visualizations(self) -> bool:
        """Whether section has charts/visualizations."""
        return bool(self.charts)


class Report(BaseModel):
    """
    Base report model.

    Foundation for all report types with common attributes.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "rpt_20251207_001",
                "report_type": "daily_digest",
                "title": "Daily M&A Digest - December 7, 2025",
                "generated_at": "2025-12-07T10:30:00Z",
                "sections": [],
            }
        }
    )

    report_id: str = Field(..., description="Unique report identifier")
    report_type: ReportType = Field(..., description="Type of report")
    title: str = Field(..., description="Report title")

    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp"
    )
    generated_by: Optional[str] = Field(None, description="User/system that generated report")

    period_start: Optional[date] = Field(None, description="Report period start date")
    period_end: Optional[date] = Field(None, description="Report period end date")

    sections: List[ReportSection] = Field(
        default_factory=list,
        description="Report sections"
    )

    summary: Optional[str] = Field(None, description="Brief report summary")
    key_findings: List[str] = Field(
        default_factory=list,
        description="Key findings/takeaways"
    )

    tickers_analyzed: List[str] = Field(
        default_factory=list,
        description="Company tickers included in report"
    )

    format: ReportFormat = Field(
        default=ReportFormat.JSON,
        description="Report output format"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional report metadata"
    )

    version: str = Field(default="1.0.0", description="Report schema version")

    @field_validator("report_id")
    @classmethod
    def validate_report_id(cls, v: str) -> str:
        """Validate report ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Report ID cannot be empty")
        return v.strip()

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("tickers_analyzed")
    @classmethod
    def normalize_tickers(cls, v: List[str]) -> List[str]:
        """Normalize ticker symbols to uppercase."""
        return [ticker.strip().upper() for ticker in v if ticker.strip()]

    @computed_field
    @property
    def total_sections(self) -> int:
        """Total number of sections."""
        return len(self.sections)

    @computed_field
    @property
    def total_word_count(self) -> int:
        """Total word count across all sections."""
        return sum(section.word_count for section in self.sections)

    @computed_field
    @property
    def companies_count(self) -> int:
        """Number of companies analyzed."""
        return len(self.tickers_analyzed)

    @computed_field
    @property
    def period_days(self) -> Optional[int]:
        """Length of reporting period in days."""
        if self.period_start is None or self.period_end is None:
            return None
        delta = self.period_end - self.period_start
        return delta.days + 1  # Inclusive

    def get_section(self, section_type: SectionType) -> Optional[ReportSection]:
        """
        Get section by type.

        Args:
            section_type: Type of section to retrieve

        Returns:
            Section if found, None otherwise
        """
        for section in self.sections:
            if section.section_type == section_type:
                return section
        return None

    def get_sections_sorted(self) -> List[ReportSection]:
        """
        Get sections sorted by order.

        Returns:
            List of sections sorted by order field
        """
        return sorted(self.sections, key=lambda s: s.order)

    def add_section(self, section: ReportSection) -> None:
        """
        Add section to report.

        Args:
            section: Section to add
        """
        # Check for duplicate section types
        if self.get_section(section.section_type) is not None:
            raise ValueError(f"Section of type {section.section_type} already exists")

        self.sections.append(section)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return self.model_dump(mode="json")


class DailyDigest(Report):
    """
    Daily digest report.

    Summarizes key M&A signals and events from the past day.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "dd_20251207",
                "report_type": "daily_digest",
                "title": "Daily M&A Digest - December 7, 2025",
                "digest_date": "2025-12-07",
                "new_signals_count": 12,
                "high_priority_signals": 3,
                "companies_updated": 8,
            }
        }
    )

    report_type: ReportType = Field(default=ReportType.DAILY_DIGEST, frozen=True)

    digest_date: date = Field(..., description="Digest date")

    new_signals_count: int = Field(default=0, ge=0, description="Number of new signals detected")
    high_priority_signals: int = Field(
        default=0,
        ge=0,
        description="Number of high-priority signals"
    )
    companies_updated: int = Field(
        default=0,
        ge=0,
        description="Number of companies with updates"
    )

    top_movers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Companies with largest score changes"
    )

    signal_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Signal count by type"
    )

    notable_events: List[str] = Field(
        default_factory=list,
        description="Notable events summary"
    )

    @computed_field
    @property
    def signals_per_company(self) -> float:
        """Average signals per company updated."""
        if self.companies_updated == 0:
            return 0.0
        return round(self.new_signals_count / self.companies_updated, 2)

    def generate_summary(self) -> str:
        """
        Generate executive summary for the daily digest.

        Returns:
            Summary text
        """
        summary_parts = [
            f"Daily M&A Digest for {self.digest_date.strftime('%B %d, %Y')}",
            f"",
            f"Key Statistics:",
            f"- {self.new_signals_count} new signals detected",
            f"- {self.high_priority_signals} high-priority signals",
            f"- {self.companies_updated} companies updated",
            f"- {self.signals_per_company:.1f} signals per company",
        ]

        if self.notable_events:
            summary_parts.append("")
            summary_parts.append("Notable Events:")
            for event in self.notable_events[:5]:  # Top 5 events
                summary_parts.append(f"- {event}")

        return "\n".join(summary_parts)


class WeeklyWatchlist(Report):
    """
    Weekly watchlist report.

    Comprehensive review of top M&A candidates and score changes.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "ww_2025_49",
                "report_type": "weekly_watchlist",
                "title": "Weekly Watchlist - Week 49, 2025",
                "week_number": 49,
                "year": 2025,
                "top_candidates_count": 10,
            }
        }
    )

    report_type: ReportType = Field(default=ReportType.WEEKLY_WATCHLIST, frozen=True)

    week_number: int = Field(..., ge=1, le=53, description="ISO week number")
    year: int = Field(..., ge=2000, le=2100, description="Year")

    top_candidates_count: int = Field(
        default=10,
        ge=1,
        description="Number of top candidates included"
    )

    top_candidates: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top M&A candidates with scores"
    )

    score_changes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Companies with significant score changes"
    )

    new_to_watchlist: List[str] = Field(
        default_factory=list,
        description="Tickers newly added to watchlist"
    )

    removed_from_watchlist: List[str] = Field(
        default_factory=list,
        description="Tickers removed from watchlist"
    )

    sector_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Candidate count by therapeutic area"
    )

    average_score: Optional[float] = Field(
        None,
        description="Average M&A score across all candidates"
    )

    @computed_field
    @property
    def net_watchlist_change(self) -> int:
        """Net change in watchlist size."""
        return len(self.new_to_watchlist) - len(self.removed_from_watchlist)

    @computed_field
    @property
    def week_description(self) -> str:
        """Human-readable week description."""
        return f"Week {self.week_number}, {self.year}"

    def generate_summary(self) -> str:
        """
        Generate executive summary for the weekly watchlist.

        Returns:
            Summary text
        """
        summary_parts = [
            f"Weekly M&A Watchlist - {self.week_description}",
            f"",
            f"Watchlist Overview:",
            f"- {self.top_candidates_count} top candidates tracked",
            f"- Average M&A score: {self.average_score:.1f}" if self.average_score else "- Average M&A score: N/A",
            f"- {len(self.new_to_watchlist)} new additions",
            f"- {len(self.removed_from_watchlist)} removals",
            f"- Net change: {self.net_watchlist_change:+d}",
        ]

        if self.top_candidates:
            summary_parts.append("")
            summary_parts.append("Top 5 Candidates:")
            for i, candidate in enumerate(self.top_candidates[:5], 1):
                ticker = candidate.get("ticker", "N/A")
                score = candidate.get("score", 0)
                summary_parts.append(f"{i}. {ticker} - Score: {score:.1f}")

        return "\n".join(summary_parts)


class DeepDiveReport(Report):
    """
    Deep-dive analysis report for a specific company.

    Comprehensive analysis including company profile, pipeline,
    financial analysis, signals, scoring, and acquirer matching.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "dd_ABCD_20251207",
                "report_type": "deep_dive",
                "title": "Deep Dive: ABC Therapeutics (ABCD)",
                "target_ticker": "ABCD",
                "target_company_name": "ABC Therapeutics",
            }
        }
    )

    report_type: ReportType = Field(default=ReportType.DEEP_DIVE, frozen=True)

    target_ticker: str = Field(..., description="Target company ticker")
    target_company_name: str = Field(..., description="Target company name")

    # Company profile data
    company_profile: Dict[str, Any] = Field(
        default_factory=dict,
        description="Company profile information"
    )

    # Financial analysis
    financial_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key financial metrics"
    )
    runway_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Cash runway analysis"
    )

    # Pipeline analysis
    pipeline_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline summary statistics"
    )
    key_assets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Key pipeline assets"
    )

    # Signals and events
    recent_signals: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent signals (last 90 days)"
    )
    signal_timeline: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Historical signal timeline"
    )

    # M&A analysis
    ma_score_detail: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed M&A score breakdown"
    )
    potential_acquirers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Potential acquirer analysis"
    )

    # Competitive landscape
    competitors: List[str] = Field(
        default_factory=list,
        description="Key competitors"
    )
    competitive_positioning: Optional[str] = Field(
        None,
        description="Competitive positioning analysis"
    )

    # Investment thesis
    bull_case: List[str] = Field(
        default_factory=list,
        description="Bull case arguments"
    )
    bear_case: List[str] = Field(
        default_factory=list,
        description="Bear case arguments"
    )

    # Catalysts and risks
    upcoming_catalysts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Upcoming catalysts and milestones"
    )
    key_risks: List[str] = Field(
        default_factory=list,
        description="Key risks identified"
    )

    # Valuation
    valuation_metrics: Optional[Dict[str, Any]] = Field(
        None,
        description="Valuation analysis"
    )
    comparable_transactions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Comparable M&A transactions"
    )

    # Analyst notes
    analyst_notes: List[str] = Field(
        default_factory=list,
        description="Additional analyst commentary"
    )

    conclusion: Optional[str] = Field(
        None,
        description="Overall conclusion and recommendation"
    )

    @field_validator("target_ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker."""
        if not v or not v.strip():
            raise ValueError("Target ticker cannot be empty")
        return v.strip().upper()

    @field_validator("target_company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        """Validate company name is not empty."""
        if not v or not v.strip():
            raise ValueError("Target company name cannot be empty")
        return v.strip()

    @computed_field
    @property
    def total_signals_analyzed(self) -> int:
        """Total number of signals analyzed."""
        return len(self.recent_signals)

    @computed_field
    @property
    def ma_score(self) -> Optional[float]:
        """Extract M&A score if available."""
        if self.ma_score_detail:
            return self.ma_score_detail.get("overall_score")
        return None

    @computed_field
    @property
    def recommendation(self) -> str:
        """
        Generate recommendation based on M&A score.

        Returns:
            Recommendation string
        """
        if self.ma_score is None:
            return "INSUFFICIENT_DATA"

        if self.ma_score >= 75:
            return "STRONG_ACQUISITION_CANDIDATE"
        elif self.ma_score >= 60:
            return "LIKELY_ACQUISITION_CANDIDATE"
        elif self.ma_score >= 45:
            return "MODERATE_ACQUISITION_POTENTIAL"
        elif self.ma_score >= 30:
            return "LOW_ACQUISITION_LIKELIHOOD"
        else:
            return "MINIMAL_ACQUISITION_RISK"

    @computed_field
    @property
    def analysis_completeness(self) -> float:
        """
        Calculate completeness of analysis (0-1).

        Based on presence of key analysis sections.
        """
        components = [
            bool(self.company_profile),
            bool(self.financial_metrics),
            bool(self.pipeline_summary),
            bool(self.recent_signals),
            bool(self.ma_score_detail),
            bool(self.potential_acquirers),
            bool(self.upcoming_catalysts),
            bool(self.bull_case),
            bool(self.bear_case),
            bool(self.conclusion),
        ]

        return round(sum(components) / len(components), 2)

    def generate_executive_summary(self) -> str:
        """
        Generate executive summary for the deep dive.

        Returns:
            Executive summary text
        """
        summary_parts = [
            f"Deep Dive Analysis: {self.target_company_name} ({self.target_ticker})",
            f"Generated: {self.generated_at.strftime('%B %d, %Y at %H:%M UTC')}",
            f"",
            f"RECOMMENDATION: {self.recommendation}",
        ]

        if self.ma_score is not None:
            summary_parts.append(f"M&A Score: {self.ma_score:.1f}/100")

        if self.financial_metrics:
            market_cap = self.financial_metrics.get("market_cap_usd")
            if market_cap:
                summary_parts.append(f"Market Cap: ${market_cap:,.0f}")

        if self.pipeline_summary:
            clinical_count = self.pipeline_summary.get("clinical_stage_count", 0)
            summary_parts.append(f"Clinical Stage Assets: {clinical_count}")

        summary_parts.append("")
        summary_parts.append("Key Highlights:")

        # Add top catalysts
        if self.upcoming_catalysts:
            summary_parts.append(f"- {len(self.upcoming_catalysts)} upcoming catalysts identified")

        # Add top risks
        if self.key_risks:
            summary_parts.append(f"- {len(self.key_risks)} key risks identified")

        # Add acquirer count
        if self.potential_acquirers:
            summary_parts.append(
                f"- {len(self.potential_acquirers)} potential acquirers analyzed"
            )

        if self.conclusion:
            summary_parts.append("")
            summary_parts.append("Conclusion:")
            summary_parts.append(self.conclusion)

        return "\n".join(summary_parts)

    def get_priority_actions(self) -> List[str]:
        """
        Generate list of priority actions based on analysis.

        Returns:
            List of recommended actions
        """
        actions = []

        # Check cash runway
        if self.runway_analysis:
            quarters = self.runway_analysis.get("runway_quarters")
            if quarters and quarters < 4:
                actions.append(
                    f"CRITICAL: Monitor cash position - only {quarters:.1f} quarters remaining"
                )

        # Check upcoming catalysts
        if self.upcoming_catalysts:
            near_term = [
                c for c in self.upcoming_catalysts
                if c.get("days_until", 999) < 90
            ]
            if near_term:
                actions.append(
                    f"Track {len(near_term)} upcoming catalysts in next 90 days"
                )

        # Check M&A score
        if self.ma_score and self.ma_score >= 70:
            actions.append(
                "HIGH PRIORITY: Monitor for acquisition rumors and unusual activity"
            )

        # Check potential acquirers
        if self.potential_acquirers:
            top_acquirers = sorted(
                self.potential_acquirers,
                key=lambda a: a.get("fit_score", 0),
                reverse=True
            )[:3]
            if top_acquirers:
                acquirer_names = [a.get("acquirer_name", "Unknown") for a in top_acquirers]
                actions.append(
                    f"Watch for activity from top acquirers: {', '.join(acquirer_names)}"
                )

        return actions


class AlertReport(Report):
    """
    Alert report for time-sensitive M&A signals.

    Generated when specific threshold conditions are met.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "alert_20251207_001",
                "report_type": "alert",
                "title": "M&A Alert: ABCD - Critical Cash Runway",
                "alert_level": "critical",
                "target_ticker": "ABCD",
                "trigger_condition": "Cash runway below 2 quarters",
            }
        }
    )

    report_type: ReportType = Field(default=ReportType.ALERT, frozen=True)

    alert_level: str = Field(..., description="Alert severity (info, warning, critical)")
    target_ticker: str = Field(..., description="Company ticker triggering alert")
    trigger_condition: str = Field(..., description="Condition that triggered alert")

    alert_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed alert information"
    )

    recommended_actions: List[str] = Field(
        default_factory=list,
        description="Recommended actions to take"
    )

    expires_at: Optional[datetime] = Field(
        None,
        description="When alert expires/becomes stale"
    )

    @field_validator("alert_level")
    @classmethod
    def validate_alert_level(cls, v: str) -> str:
        """Validate alert level."""
        valid_levels = {"info", "warning", "critical"}
        v_lower = v.lower()
        if v_lower not in valid_levels:
            raise ValueError(f"Alert level must be one of {valid_levels}")
        return v_lower

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Whether alert has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @computed_field
    @property
    def urgency_score(self) -> int:
        """
        Urgency score (1-10) based on alert level.

        Returns:
            Urgency score
        """
        urgency_map = {
            "info": 3,
            "warning": 6,
            "critical": 10,
        }
        return urgency_map.get(self.alert_level, 5)
