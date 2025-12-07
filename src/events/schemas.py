"""
Event schema definitions using Pydantic.

Defines all event types and the message envelope format for the
biotech M&A predictor system.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Enumeration of all event types in the system."""
    CLINICAL_TRIAL_SIGNAL = "clinical_trial_signal"
    PATENT_CLIFF = "patent_cliff"
    INSIDER_ACTIVITY = "insider_activity"
    HIRING_SIGNAL = "hiring_signal"
    MA_CANDIDATE = "ma_candidate"
    REPORT_GENERATED = "report_generated"


class BaseEvent(BaseModel):
    """
    Base class for all events.

    All events must have a type and timestamp.
    """
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MessageEnvelope(BaseModel):
    """
    Message envelope wrapping all events.

    Provides metadata and routing information for events.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(description="Source service/component that generated the event")
    event_type: str = Field(description="Type of event being transmitted")
    payload: Dict[str, Any] = Field(description="Event payload data")
    version: str = Field(default="1.0", description="Message schema version")
    correlation_id: Optional[str] = Field(
        default=None,
        description="ID to correlate related events"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @classmethod
    def from_event(cls, event: BaseEvent, source: str = "biotech-ma-predictor") -> "MessageEnvelope":
        """
        Create an envelope from an event.

        Args:
            event: Event to wrap
            source: Source identifier

        Returns:
            MessageEnvelope containing the event
        """
        return cls(
            source=source,
            event_type=event.event_type,
            payload=event.model_dump(),
            timestamp=event.timestamp
        )

    def to_event(self) -> BaseEvent:
        """
        Extract the event from the envelope.

        Returns:
            The unwrapped event
        """
        # Map event types to classes
        event_classes = {
            EventType.CLINICAL_TRIAL_SIGNAL: ClinicalTrialSignalEvent,
            EventType.PATENT_CLIFF: PatentCliffEvent,
            EventType.INSIDER_ACTIVITY: InsiderActivityEvent,
            EventType.HIRING_SIGNAL: HiringSignalEvent,
            EventType.MA_CANDIDATE: MACandidateEvent,
            EventType.REPORT_GENERATED: ReportGeneratedEvent,
        }

        event_class = event_classes.get(self.event_type)
        if event_class:
            return event_class(**self.payload)
        else:
            # Return generic BaseEvent if type unknown
            return BaseEvent(**self.payload)


class ClinicalTrialSignalEvent(BaseEvent):
    """
    Event emitted when a significant clinical trial signal is detected.

    Examples: Phase transition, enrollment milestone, FDA designation
    """
    event_type: str = Field(default=EventType.CLINICAL_TRIAL_SIGNAL)

    company_id: str = Field(description="ID of the company")
    company_name: str = Field(description="Name of the company")
    trial_id: str = Field(description="Clinical trial identifier (e.g., NCT number)")
    trial_phase: str = Field(description="Trial phase (I, II, III, IV)")
    indication: str = Field(description="Disease/condition being treated")
    signal_type: str = Field(
        description="Type of signal: phase_transition, enrollment_complete, fda_designation, results_posted"
    )
    signal_strength: float = Field(
        ge=0.0,
        le=1.0,
        description="Strength/confidence of the signal (0-1)"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional signal details"
    )


class PatentCliffEvent(BaseEvent):
    """
    Event emitted when a patent cliff is approaching or detected.

    Patent cliffs represent significant revenue risk for pharma companies.
    """
    event_type: str = Field(default=EventType.PATENT_CLIFF)

    company_id: str = Field(description="ID of the company")
    company_name: str = Field(description="Name of the company")
    drug_name: str = Field(description="Name of the drug/product")
    patent_number: str = Field(description="Patent number")
    expiration_date: datetime = Field(description="Patent expiration date")
    years_until_expiration: float = Field(description="Years until expiration")
    estimated_revenue_impact: Optional[float] = Field(
        default=None,
        description="Estimated annual revenue at risk (USD)"
    )
    market_share: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Drug's market share in its category"
    )
    severity: str = Field(
        description="Severity level: critical, high, medium, low"
    )

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v):
        allowed = ['critical', 'high', 'medium', 'low']
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v


class InsiderActivityEvent(BaseEvent):
    """
    Event emitted when significant insider trading activity is detected.

    Tracks executive/director stock transactions.
    """
    event_type: str = Field(default=EventType.INSIDER_ACTIVITY)

    company_id: str = Field(description="ID of the company")
    company_name: str = Field(description="Name of the company")
    insider_name: str = Field(description="Name of the insider")
    insider_title: str = Field(description="Title/position of the insider")
    transaction_type: str = Field(
        description="Transaction type: buy, sell, option_exercise, gift"
    )
    shares: int = Field(description="Number of shares in transaction")
    price_per_share: Optional[float] = Field(
        default=None,
        description="Price per share (USD)"
    )
    transaction_value: float = Field(description="Total transaction value (USD)")
    transaction_date: datetime = Field(description="Date of transaction")
    filing_date: datetime = Field(description="SEC filing date")
    form_type: str = Field(description="SEC form type (e.g., Form 4)")

    @field_validator('transaction_type')
    @classmethod
    def validate_transaction_type(cls, v):
        allowed = ['buy', 'sell', 'option_exercise', 'gift']
        if v not in allowed:
            raise ValueError(f"Transaction type must be one of {allowed}")
        return v


class HiringSignalEvent(BaseEvent):
    """
    Event emitted when significant hiring patterns are detected.

    Tracks job postings and hiring trends that may signal M&A activity.
    """
    event_type: str = Field(default=EventType.HIRING_SIGNAL)

    company_id: str = Field(description="ID of the company")
    company_name: str = Field(description="Name of the company")
    signal_type: str = Field(
        description="Type of hiring signal: expansion, specialized_roles, reduction, integration_roles"
    )
    job_category: str = Field(
        description="Category of jobs: clinical, regulatory, commercial, integration, finance"
    )
    job_count: int = Field(description="Number of relevant job postings")
    growth_rate: Optional[float] = Field(
        default=None,
        description="Percentage change in hiring rate"
    )
    key_roles: List[str] = Field(
        default_factory=list,
        description="Notable job titles posted"
    )
    locations: List[str] = Field(
        default_factory=list,
        description="Geographic locations for roles"
    )
    analysis_period_days: int = Field(
        default=30,
        description="Period over which signal was detected"
    )

    @field_validator('signal_type')
    @classmethod
    def validate_signal_type(cls, v):
        allowed = ['expansion', 'specialized_roles', 'reduction', 'integration_roles']
        if v not in allowed:
            raise ValueError(f"Signal type must be one of {allowed}")
        return v


class MACandidateEvent(BaseEvent):
    """
    Event emitted when a company is identified or updated as an M&A candidate.

    This is the primary output of the scoring system.
    """
    event_type: str = Field(default=EventType.MA_CANDIDATE)

    company_id: str = Field(description="ID of the company")
    company_name: str = Field(description="Name of the company")
    ticker: Optional[str] = Field(default=None, description="Stock ticker symbol")
    overall_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Overall M&A likelihood score (0-100)"
    )
    score_components: Dict[str, float] = Field(
        description="Breakdown of score components"
    )
    tier: str = Field(
        description="Candidate tier: tier_1, tier_2, tier_3"
    )
    reasoning: str = Field(description="Human-readable explanation of the score")
    key_signals: List[str] = Field(
        default_factory=list,
        description="List of key signals contributing to score"
    )
    risk_factors: List[str] = Field(
        default_factory=list,
        description="Identified risk factors"
    )
    market_cap: Optional[float] = Field(
        default=None,
        description="Market capitalization (USD)"
    )
    previous_score: Optional[float] = Field(
        default=None,
        description="Previous score for comparison"
    )
    score_change: Optional[float] = Field(
        default=None,
        description="Change in score since last evaluation"
    )
    last_evaluated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the score was calculated"
    )

    @field_validator('tier')
    @classmethod
    def validate_tier(cls, v):
        allowed = ['tier_1', 'tier_2', 'tier_3']
        if v not in allowed:
            raise ValueError(f"Tier must be one of {allowed}")
        return v


class ReportGeneratedEvent(BaseEvent):
    """
    Event emitted when a report is successfully generated.

    Used to notify downstream systems and trigger notifications.
    """
    event_type: str = Field(default=EventType.REPORT_GENERATED)

    report_id: str = Field(description="Unique report identifier")
    report_type: str = Field(
        description="Type of report: daily_summary, weekly_deep_dive, candidate_profile, alert"
    )
    report_title: str = Field(description="Title of the report")
    generated_by: str = Field(description="Service/user that generated the report")
    file_path: Optional[str] = Field(
        default=None,
        description="Path to generated report file"
    )
    file_format: str = Field(
        default="pdf",
        description="Report format: pdf, html, json"
    )
    entities_covered: List[str] = Field(
        default_factory=list,
        description="Company IDs covered in the report"
    )
    time_period: Optional[Dict[str, str]] = Field(
        default=None,
        description="Time period covered by report"
    )
    recipient_emails: List[str] = Field(
        default_factory=list,
        description="Email addresses to notify"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional report metadata"
    )

    @field_validator('report_type')
    @classmethod
    def validate_report_type(cls, v):
        allowed = ['daily_summary', 'weekly_deep_dive', 'candidate_profile', 'alert']
        if v not in allowed:
            raise ValueError(f"Report type must be one of {allowed}")
        return v

    @field_validator('file_format')
    @classmethod
    def validate_file_format(cls, v):
        allowed = ['pdf', 'html', 'json']
        if v not in allowed:
            raise ValueError(f"File format must be one of {allowed}")
        return v
