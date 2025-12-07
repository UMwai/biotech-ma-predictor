"""
SQLAlchemy ORM table definitions.

Defines all database tables for the biotech M&A predictor system using
SQLAlchemy's declarative base with async support.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.models.company import DevelopmentPhase, TherapeuticArea


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class TimestampMixin:
    """Mixin for adding timestamp columns to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class Company(Base, TimestampMixin, SoftDeleteMixin):
    """
    Companies table - stores core company data.

    Tracks biotech companies with financial metrics, operational data,
    and metadata for M&A prediction.
    """

    __tablename__ = "companies"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Core identifiers
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Financial data
    market_cap_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cash_position_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    quarterly_burn_rate_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    total_debt_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal(0))
    runway_quarters: Mapped[Optional[float]] = mapped_column(Float)
    enterprise_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))

    # Operational data
    therapeutic_areas: Mapped[list] = mapped_column(JSONB, default=list)
    founded_year: Mapped[Optional[int]] = mapped_column(Integer)
    employee_count: Mapped[Optional[int]] = mapped_column(Integer)
    headquarters_location: Mapped[Optional[str]] = mapped_column(String(255))

    # Status flags
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_cash_constrained: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_data_refresh: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    drug_candidates: Mapped[list["DrugCandidate"]] = relationship(
        "DrugCandidate",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    ma_scores: Mapped[list["MAScore"]] = relationship(
        "MAScore",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    acquirer_matches: Mapped[list["AcquirerMatch"]] = relationship(
        "AcquirerMatch",
        foreign_keys="[AcquirerMatch.target_company_id]",
        back_populates="target_company",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index("idx_companies_market_cap", "market_cap_usd"),
        Index("idx_companies_cash_constrained", "is_cash_constrained"),
        Index("idx_companies_deleted", "deleted_at"),
        Index("idx_companies_therapeutic_areas", "therapeutic_areas", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Company(ticker={self.ticker}, name={self.name})>"


class DrugCandidate(Base, TimestampMixin, SoftDeleteMixin):
    """
    Drug candidates table - stores pipeline assets.

    Tracks individual drug candidates in development with phase,
    indications, and regulatory status.
    """

    __tablename__ = "drug_candidates"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Drug identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[DevelopmentPhase] = mapped_column(
        Enum(DevelopmentPhase, native_enum=False),
        nullable=False,
        index=True,
    )
    indication: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    therapeutic_area: Mapped[TherapeuticArea] = mapped_column(
        Enum(TherapeuticArea, native_enum=False),
        nullable=False,
        index=True,
    )

    # Patent and regulatory
    patent_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    patent_years_remaining: Mapped[Optional[float]] = mapped_column(Float)
    orphan_designation: Mapped[bool] = mapped_column(Boolean, default=False)
    fast_track: Mapped[bool] = mapped_column(Boolean, default=False)
    breakthrough_therapy: Mapped[bool] = mapped_column(Boolean, default=False)

    # Milestones
    next_milestone: Mapped[Optional[str]] = mapped_column(Text)
    next_milestone_date: Mapped[Optional[str]] = mapped_column(String(50))

    # Scoring
    phase_score: Mapped[float] = mapped_column(Float, default=0.0)
    competitive_landscape_score: Mapped[float] = mapped_column(Float, default=5.0)
    market_potential_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))

    # Metadata
    additional_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="drug_candidates")

    # Indexes
    __table_args__ = (
        Index("idx_drug_candidates_company_phase", "company_id", "phase"),
        Index("idx_drug_candidates_therapeutic_area", "therapeutic_area"),
        Index("idx_drug_candidates_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<DrugCandidate(name={self.name}, phase={self.phase})>"


class Signal(Base, TimestampMixin):
    """
    Signals table - stores all signal events (polymorphic).

    Tracks various signal types including SEC filings, FDA events,
    financial changes, insider trading, partnership announcements, etc.
    """

    __tablename__ = "signals"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Signal type (polymorphic discriminator)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Signal metadata
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
    )  # low, medium, high, critical
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0 to 1.0

    # Signal content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    # Signal-specific data (JSONB for flexibility)
    signal_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Impact assessment
    ma_impact_score: Mapped[float] = mapped_column(Float, default=0.0)  # -10 to +10

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="signals")

    # Indexes
    __table_args__ = (
        Index("idx_signals_company_type", "company_id", "signal_type"),
        Index("idx_signals_event_date", "event_date"),
        Index("idx_signals_severity", "severity"),
        Index("idx_signals_company_date", "company_id", "event_date"),
        Index("idx_signals_data", "signal_data", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Signal(type={self.signal_type}, company_id={self.company_id})>"


class MAScore(Base, TimestampMixin):
    """
    M&A Scores table - stores historical prediction scores.

    Tracks M&A likelihood scores over time with component breakdowns
    and rankings.
    """

    __tablename__ = "ma_scores"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Score metadata
    score_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    score_version: Mapped[str] = mapped_column(String(20), default="1.0")

    # Overall score
    total_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # 0-100
    percentile_rank: Mapped[Optional[float]] = mapped_column(Float)  # 0-100

    # Component scores
    pipeline_score: Mapped[float] = mapped_column(Float, default=0.0)
    patent_score: Mapped[float] = mapped_column(Float, default=0.0)
    financial_score: Mapped[float] = mapped_column(Float, default=0.0)
    insider_score: Mapped[float] = mapped_column(Float, default=0.0)
    strategic_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    regulatory_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Score changes
    score_change_30d: Mapped[Optional[float]] = mapped_column(Float)
    score_change_90d: Mapped[Optional[float]] = mapped_column(Float)

    # Additional analysis
    key_drivers: Mapped[list] = mapped_column(JSONB, default=list)
    risk_factors: Mapped[list] = mapped_column(JSONB, default=list)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="ma_scores")

    # Indexes
    __table_args__ = (
        Index("idx_ma_scores_company_date", "company_id", "score_date"),
        Index("idx_ma_scores_total_score", "total_score"),
        Index("idx_ma_scores_date", "score_date"),
        UniqueConstraint("company_id", "score_date", name="uq_company_score_date"),
    )

    def __repr__(self) -> str:
        return f"<MAScore(company_id={self.company_id}, score={self.total_score})>"


class AcquirerMatch(Base, TimestampMixin):
    """
    Acquirer matches table - stores target-acquirer pairings.

    Tracks potential acquirers for each target company with
    strategic fit scoring and rationale.
    """

    __tablename__ = "acquirer_matches"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    target_company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    acquirer_ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    acquirer_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Match metadata
    match_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Fit scoring
    strategic_fit_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-10
    therapeutic_overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
    geographic_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    financial_capacity_score: Mapped[float] = mapped_column(Float, default=0.0)
    historical_ma_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Match analysis
    synergy_rationale: Mapped[Optional[str]] = mapped_column(Text)
    key_assets_of_interest: Mapped[list] = mapped_column(JSONB, default=list)
    estimated_valuation_range_usd: Mapped[Optional[str]] = mapped_column(String(100))

    # Priority
    match_rank: Mapped[Optional[int]] = mapped_column(Integer)  # Rank among all matches
    is_top_match: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    target_company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[target_company_id],
        back_populates="acquirer_matches",
    )

    # Indexes
    __table_args__ = (
        Index("idx_acquirer_matches_target", "target_company_id"),
        Index("idx_acquirer_matches_acquirer", "acquirer_ticker"),
        Index("idx_acquirer_matches_fit_score", "strategic_fit_score"),
        Index("idx_acquirer_matches_top", "is_top_match"),
    )

    def __repr__(self) -> str:
        return f"<AcquirerMatch(target={self.target_company_id}, acquirer={self.acquirer_ticker})>"


class Report(Base, TimestampMixin, SoftDeleteMixin):
    """
    Reports table - stores generated report metadata.

    Tracks all generated reports including daily digests, weekly reports,
    custom analyses, and alert notifications.
    """

    __tablename__ = "reports"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Report metadata
    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # daily_digest, weekly_summary, custom, alert
    report_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Report content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(20), default="pdf")  # pdf, html, json

    # Storage
    s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255))
    local_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    # Distribution
    recipients: Mapped[list] = mapped_column(JSONB, default=list)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(20), default="pending")

    # Report data
    companies_included: Mapped[list] = mapped_column(JSONB, default=list)
    key_findings: Mapped[list] = mapped_column(JSONB, default=list)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_reports_type", "report_type"),
        Index("idx_reports_date", "report_date"),
        Index("idx_reports_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Report(type={self.report_type}, date={self.report_date})>"


class Alert(Base, TimestampMixin, SoftDeleteMixin):
    """
    Alerts table - stores alert configurations.

    Defines alert rules and configurations for monitoring companies,
    scores, and signals.
    """

    __tablename__ = "alerts"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Alert identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # score_threshold, score_change, new_signal, custom

    # Alert conditions
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float)

    # Scope
    company_tickers: Mapped[Optional[list]] = mapped_column(JSONB)  # None = all companies
    signal_types: Mapped[Optional[list]] = mapped_column(JSONB)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    # Notification settings
    notification_channels: Mapped[list] = mapped_column(
        JSONB,
        default=list,
    )  # email, slack, webhook
    recipients: Mapped[list] = mapped_column(JSONB, default=list)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_alerts_type", "alert_type"),
        Index("idx_alerts_active", "is_active"),
        Index("idx_alerts_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Alert(name={self.name}, type={self.alert_type})>"


class Webhook(Base, TimestampMixin, SoftDeleteMixin):
    """
    Webhooks table - stores registered webhooks.

    Tracks webhook endpoints for receiving real-time notifications
    about events, signals, and score changes.
    """

    __tablename__ = "webhooks"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Webhook identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255))

    # Event subscriptions
    event_types: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )  # score_update, new_signal, alert_triggered, etc.

    # Filtering
    company_tickers: Mapped[Optional[list]] = mapped_column(JSONB)
    min_score: Mapped[Optional[float]] = mapped_column(Float)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # Delivery settings
    retry_policy: Mapped[dict] = mapped_column(
        JSONB,
        default={"max_retries": 3, "retry_delay_seconds": 60},
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_webhooks_active", "is_active"),
        Index("idx_webhooks_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Webhook(name={self.name}, url={self.url})>"


class Client(Base, TimestampMixin, SoftDeleteMixin):
    """
    Clients table - stores client configurations.

    Manages API clients with access control, quotas, and preferences.
    """

    __tablename__ = "clients"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Client identification
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    client_type: Mapped[str] = mapped_column(
        String(50),
        default="standard",
    )  # standard, premium, enterprise

    # Access control
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    allowed_endpoints: Mapped[Optional[list]] = mapped_column(JSONB)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=1000)

    # Preferences
    watchlist_tickers: Mapped[list] = mapped_column(JSONB, default=list)
    notification_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    custom_thresholds: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Usage tracking
    last_access: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Indexes
    __table_args__ = (
        Index("idx_clients_active", "is_active"),
        Index("idx_clients_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<Client(name={self.client_name}, type={self.client_type})>"
