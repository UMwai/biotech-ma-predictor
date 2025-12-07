"""
M&A scoring and prediction models.

Defines models for M&A likelihood scores, acquirer matching,
and watchlist management.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict


class RiskLevel(str, Enum):
    """Risk levels for M&A predictions."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ScoreComponentType(str, Enum):
    """Types of score components."""

    FINANCIAL_STRESS = "financial_stress"
    PIPELINE_QUALITY = "pipeline_quality"
    MARKET_CONDITIONS = "market_conditions"
    STRATEGIC_SIGNALS = "strategic_signals"
    COMPETITIVE_PRESSURE = "competitive_pressure"
    REGULATORY_ENVIRONMENT = "regulatory_environment"


class ScoreComponent(BaseModel):
    """
    Individual component of an M&A score.

    Represents a single factor contributing to the overall prediction.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "component_type": "financial_stress",
                "name": "Cash Runway",
                "score": 8.5,
                "weight": 0.25,
                "description": "Company has 3.2 quarters of runway remaining",
            }
        }
    )

    component_type: ScoreComponentType = Field(..., description="Type of component")
    name: str = Field(..., description="Component name")
    score: float = Field(..., ge=0.0, le=10.0, description="Component score (0-10)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight in final score (0-1)")

    description: Optional[str] = Field(None, description="Description of the component")
    supporting_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Supporting data for this component"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate component name is not empty."""
        if not v or not v.strip():
            raise ValueError("Component name cannot be empty")
        return v.strip()

    @computed_field
    @property
    def weighted_score(self) -> float:
        """Score multiplied by weight."""
        return round(self.score * self.weight, 2)


class MAScore(BaseModel):
    """
    M&A likelihood score for a company.

    Composite score with breakdown of contributing factors.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_ticker": "ABCD",
                "overall_score": 75.5,
                "components": [],
                "calculated_at": "2025-12-07T10:30:00Z",
                "timeframe_months": 12,
                "confidence_level": 0.82,
            }
        }
    )

    company_ticker: str = Field(..., description="Company ticker symbol")
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall M&A score (0-100)")

    components: List[ScoreComponent] = Field(
        default_factory=list,
        description="Individual score components"
    )

    calculated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When score was calculated"
    )

    timeframe_months: int = Field(
        12,
        ge=1,
        le=60,
        description="Prediction timeframe in months"
    )

    confidence_level: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in prediction (0-1)"
    )

    risk_factors: List[str] = Field(
        default_factory=list,
        description="Key risk factors identified"
    )
    opportunities: List[str] = Field(
        default_factory=list,
        description="Key opportunities identified"
    )

    model_version: str = Field(default="1.0.0", description="Scoring model version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("company_ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker symbol."""
        if not v or not v.strip():
            raise ValueError("Company ticker cannot be empty")
        return v.strip().upper()

    @field_validator("components")
    @classmethod
    def validate_components_weights(cls, v: List[ScoreComponent]) -> List[ScoreComponent]:
        """Validate that component weights sum to approximately 1.0."""
        if not v:
            return v

        total_weight = sum(comp.weight for comp in v)
        if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
            raise ValueError(f"Component weights must sum to 1.0, got {total_weight}")

        return v

    @computed_field
    @property
    def risk_level(self) -> RiskLevel:
        """
        Risk level based on overall score.

        Higher score = higher M&A likelihood = higher risk for independence.
        """
        if self.overall_score >= 80:
            return RiskLevel.VERY_HIGH
        elif self.overall_score >= 65:
            return RiskLevel.HIGH
        elif self.overall_score >= 45:
            return RiskLevel.MEDIUM
        elif self.overall_score >= 25:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW

    @computed_field
    @property
    def adjusted_score(self) -> float:
        """Score adjusted by confidence level."""
        return round(self.overall_score * self.confidence_level, 2)

    @computed_field
    @property
    def score_age_days(self) -> int:
        """Days since score was calculated."""
        delta = datetime.utcnow() - self.calculated_at
        return delta.days

    @computed_field
    @property
    def is_stale(self) -> bool:
        """Whether score is stale (>7 days old)."""
        return self.score_age_days > 7

    def get_top_components(self, n: int = 3) -> List[ScoreComponent]:
        """
        Get top N components by weighted score.

        Args:
            n: Number of top components to return

        Returns:
            List of top components sorted by weighted score
        """
        sorted_components = sorted(
            self.components,
            key=lambda c: c.weighted_score,
            reverse=True
        )
        return sorted_components[:n]

    def get_component_by_type(self, component_type: ScoreComponentType) -> Optional[ScoreComponent]:
        """
        Get component by type.

        Args:
            component_type: Type of component to retrieve

        Returns:
            Component if found, None otherwise
        """
        for component in self.components:
            if component.component_type == component_type:
                return component
        return None

    def to_summary(self) -> Dict[str, Any]:
        """Generate summary dictionary of score."""
        top_components = self.get_top_components(3)

        return {
            "ticker": self.company_ticker,
            "overall_score": self.overall_score,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence_level,
            "adjusted_score": self.adjusted_score,
            "timeframe_months": self.timeframe_months,
            "top_factors": [
                {
                    "name": comp.name,
                    "score": comp.score,
                    "weighted_score": comp.weighted_score,
                }
                for comp in top_components
            ],
            "calculated_at": self.calculated_at.isoformat(),
            "is_stale": self.is_stale,
        }


class AcquirerMatch(BaseModel):
    """
    Represents a potential acquirer and fit score for a target company.

    Analyzes strategic, financial, and therapeutic area alignment.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_ticker": "ABCD",
                "acquirer_ticker": "BIGPHARMA",
                "acquirer_name": "BigPharma Inc.",
                "fit_score": 82.5,
                "strategic_fit": 8.5,
                "therapeutic_fit": 9.0,
                "financial_fit": 7.8,
                "rationale": "Strong therapeutic area alignment in oncology",
            }
        }
    )

    target_ticker: str = Field(..., description="Target company ticker")
    acquirer_ticker: str = Field(..., description="Potential acquirer ticker")
    acquirer_name: str = Field(..., description="Potential acquirer name")

    fit_score: float = Field(..., ge=0.0, le=100.0, description="Overall fit score (0-100)")

    strategic_fit: float = Field(..., ge=0.0, le=10.0, description="Strategic fit score (0-10)")
    therapeutic_fit: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Therapeutic area alignment (0-10)"
    )
    financial_fit: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        description="Financial capacity fit (0-10)"
    )
    cultural_fit: float = Field(
        5.0,
        ge=0.0,
        le=10.0,
        description="Cultural/organizational fit (0-10)"
    )

    rationale: str = Field(..., description="Explanation for the match")

    synergies: List[str] = Field(
        default_factory=list,
        description="Identified synergy opportunities"
    )
    concerns: List[str] = Field(
        default_factory=list,
        description="Potential concerns or obstacles"
    )

    historical_precedent: Optional[str] = Field(
        None,
        description="Similar past acquisitions by this acquirer"
    )

    estimated_premium_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=200.0,
        description="Estimated acquisition premium percentage"
    )

    probability: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Probability of this match occurring (0-1)"
    )

    calculated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When match was calculated"
    )

    @field_validator("target_ticker", "acquirer_ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker symbols."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        return v.strip().upper()

    @field_validator("acquirer_name", "rationale")
    @classmethod
    def validate_text_fields(cls, v: str) -> str:
        """Validate text fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @computed_field
    @property
    def composite_fit_score(self) -> float:
        """
        Calculate composite fit from individual components.

        Weighted average of strategic, therapeutic, financial, and cultural fit.
        """
        weights = {
            "strategic": 0.30,
            "therapeutic": 0.30,
            "financial": 0.25,
            "cultural": 0.15,
        }

        composite = (
            self.strategic_fit * weights["strategic"]
            + self.therapeutic_fit * weights["therapeutic"]
            + self.financial_fit * weights["financial"]
            + self.cultural_fit * weights["cultural"]
        )

        # Scale to 0-100
        return round(composite * 10, 2)

    @computed_field
    @property
    def is_strong_match(self) -> bool:
        """Whether this is a strong match (fit score >= 70)."""
        return self.fit_score >= 70.0

    @computed_field
    @property
    def expected_value_score(self) -> float:
        """Expected value: fit_score * probability."""
        return round(self.fit_score * self.probability, 2)

    def to_summary(self) -> Dict[str, Any]:
        """Generate summary of acquirer match."""
        return {
            "acquirer": f"{self.acquirer_name} ({self.acquirer_ticker})",
            "fit_score": self.fit_score,
            "is_strong_match": self.is_strong_match,
            "probability": self.probability,
            "rationale": self.rationale,
            "key_synergies": self.synergies[:3] if self.synergies else [],
            "top_concerns": self.concerns[:2] if self.concerns else [],
        }


class WatchlistEntry(BaseModel):
    """
    Single entry in a watchlist.

    Combines company info with M&A score and acquirer matches.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "ABCD",
                "company_name": "ABC Therapeutics",
                "ma_score": None,
                "potential_acquirers": [],
                "added_at": "2025-12-07T10:30:00Z",
                "priority": "high",
            }
        }
    )

    ticker: str = Field(..., description="Company ticker")
    company_name: str = Field(..., description="Company name")

    ma_score: Optional[MAScore] = Field(None, description="M&A likelihood score")
    potential_acquirers: List[AcquirerMatch] = Field(
        default_factory=list,
        description="Potential acquirer matches"
    )

    added_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When added to watchlist"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    priority: str = Field(
        default="medium",
        description="Priority level (low, medium, high, critical)"
    )

    notes: List[str] = Field(default_factory=list, description="Analyst notes")
    tags: List[str] = Field(default_factory=list, description="Custom tags")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        return v.strip().upper()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority is valid value."""
        valid_priorities = {"low", "medium", "high", "critical"}
        v_lower = v.lower()
        if v_lower not in valid_priorities:
            raise ValueError(f"Priority must be one of {valid_priorities}")
        return v_lower

    @computed_field
    @property
    def score(self) -> Optional[float]:
        """Get overall M&A score if available."""
        return self.ma_score.overall_score if self.ma_score else None

    @computed_field
    @property
    def risk_level(self) -> Optional[RiskLevel]:
        """Get risk level if score available."""
        return self.ma_score.risk_level if self.ma_score else None

    @computed_field
    @property
    def top_acquirer(self) -> Optional[AcquirerMatch]:
        """Get top potential acquirer by fit score."""
        if not self.potential_acquirers:
            return None
        return max(self.potential_acquirers, key=lambda a: a.fit_score)

    @computed_field
    @property
    def days_on_watchlist(self) -> int:
        """Days since added to watchlist."""
        delta = datetime.utcnow() - self.added_at
        return delta.days


class Watchlist(BaseModel):
    """
    Collection of companies being monitored for M&A activity.

    Provides filtering, sorting, and aggregation capabilities.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Q4 2025 High Priority",
                "description": "Companies with high M&A likelihood",
                "entries": [],
                "created_at": "2025-12-07T10:30:00Z",
            }
        }
    )

    name: str = Field(..., description="Watchlist name")
    description: Optional[str] = Field(None, description="Watchlist description")

    entries: List[WatchlistEntry] = Field(
        default_factory=list,
        description="Watchlist entries"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    owner: Optional[str] = Field(None, description="Watchlist owner/creator")
    is_public: bool = Field(False, description="Whether watchlist is public")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate watchlist name is not empty."""
        if not v or not v.strip():
            raise ValueError("Watchlist name cannot be empty")
        return v.strip()

    @computed_field
    @property
    def total_companies(self) -> int:
        """Total number of companies on watchlist."""
        return len(self.entries)

    @computed_field
    @property
    def average_score(self) -> Optional[float]:
        """Average M&A score across all entries with scores."""
        scores = [entry.score for entry in self.entries if entry.score is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)

    @computed_field
    @property
    def high_risk_count(self) -> int:
        """Number of high or very high risk entries."""
        high_risk = {RiskLevel.HIGH, RiskLevel.VERY_HIGH}
        return sum(
            1 for entry in self.entries
            if entry.risk_level in high_risk
        )

    def get_by_ticker(self, ticker: str) -> Optional[WatchlistEntry]:
        """
        Get entry by ticker symbol.

        Args:
            ticker: Company ticker to find

        Returns:
            Entry if found, None otherwise
        """
        ticker = ticker.upper()
        for entry in self.entries:
            if entry.ticker == ticker:
                return entry
        return None

    def get_by_priority(self, priority: str) -> List[WatchlistEntry]:
        """
        Get entries by priority level.

        Args:
            priority: Priority level to filter by

        Returns:
            List of entries with matching priority
        """
        priority = priority.lower()
        return [entry for entry in self.entries if entry.priority == priority]

    def get_by_risk_level(self, risk_level: RiskLevel) -> List[WatchlistEntry]:
        """
        Get entries by risk level.

        Args:
            risk_level: Risk level to filter by

        Returns:
            List of entries with matching risk level
        """
        return [entry for entry in self.entries if entry.risk_level == risk_level]

    def get_sorted_by_score(self, descending: bool = True) -> List[WatchlistEntry]:
        """
        Get entries sorted by M&A score.

        Args:
            descending: Sort in descending order (highest scores first)

        Returns:
            Sorted list of entries
        """
        # Separate entries with and without scores
        with_scores = [e for e in self.entries if e.score is not None]
        without_scores = [e for e in self.entries if e.score is None]

        # Sort entries with scores
        sorted_with_scores = sorted(
            with_scores,
            key=lambda e: e.score,
            reverse=descending
        )

        # Return sorted entries followed by entries without scores
        return sorted_with_scores + without_scores

    def add_entry(self, entry: WatchlistEntry) -> None:
        """
        Add entry to watchlist.

        Args:
            entry: Entry to add
        """
        # Check for duplicates
        if self.get_by_ticker(entry.ticker) is not None:
            raise ValueError(f"Entry with ticker {entry.ticker} already exists")

        self.entries.append(entry)
        self.updated_at = datetime.utcnow()

    def remove_entry(self, ticker: str) -> bool:
        """
        Remove entry by ticker.

        Args:
            ticker: Ticker of entry to remove

        Returns:
            True if entry was removed, False if not found
        """
        ticker = ticker.upper()
        original_length = len(self.entries)
        self.entries = [e for e in self.entries if e.ticker != ticker]

        if len(self.entries) < original_length:
            self.updated_at = datetime.utcnow()
            return True
        return False

    def to_summary(self) -> Dict[str, Any]:
        """Generate summary of watchlist."""
        return {
            "name": self.name,
            "total_companies": self.total_companies,
            "average_score": self.average_score,
            "high_risk_count": self.high_risk_count,
            "priority_breakdown": {
                "critical": len(self.get_by_priority("critical")),
                "high": len(self.get_by_priority("high")),
                "medium": len(self.get_by_priority("medium")),
                "low": len(self.get_by_priority("low")),
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
