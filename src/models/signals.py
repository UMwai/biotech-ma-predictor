"""
Signal event data models.

Defines various types of signals that may indicate M&A potential,
including clinical trial events, patent filings, insider transactions,
and hiring activities.
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any, List
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict


class SignalType(str, Enum):
    """Types of M&A signals."""

    CLINICAL_TRIAL = "clinical_trial"
    PATENT = "patent"
    INSIDER_TRANSACTION = "insider_transaction"
    HIRING = "hiring"
    FINANCIAL = "financial"
    REGULATORY = "regulatory"
    PARTNERSHIP = "partnership"
    MARKET = "market"


class TrialPhase(str, Enum):
    """Clinical trial phases."""

    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"


class TrialStatus(str, Enum):
    """Clinical trial status."""

    NOT_YET_RECRUITING = "not_yet_recruiting"
    RECRUITING = "recruiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"


class TrialOutcome(str, Enum):
    """Clinical trial outcome."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    PENDING = "pending"
    UNKNOWN = "unknown"


class TransactionType(str, Enum):
    """Insider transaction types."""

    PURCHASE = "purchase"
    SALE = "sale"
    OPTION_EXERCISE = "option_exercise"
    GIFT = "gift"
    AWARD = "award"


class InsiderRole(str, Enum):
    """Role of insider in transaction."""

    CEO = "ceo"
    CFO = "cfo"
    COO = "coo"
    CSO = "cso"
    CMO = "cmo"
    BOARD_MEMBER = "board_member"
    DIRECTOR = "director"
    OFFICER = "officer"
    TEN_PERCENT_OWNER = "ten_percent_owner"
    OTHER = "other"


class SeniorityLevel(str, Enum):
    """Seniority level for hiring signals."""

    C_SUITE = "c_suite"
    VP = "vp"
    DIRECTOR = "director"
    SENIOR_MANAGER = "senior_manager"
    MANAGER = "manager"
    INDIVIDUAL_CONTRIBUTOR = "individual_contributor"


class BaseSignal(BaseModel):
    """
    Base signal model with common attributes.

    All specific signal types inherit from this base class.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_20251207_001",
                "signal_type": "clinical_trial",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "ClinicalTrials.gov",
                "company_ticker": "ABCD",
                "relevance_score": 8.5,
            }
        }
    )

    signal_id: str = Field(..., description="Unique signal identifier")
    signal_type: SignalType = Field(..., description="Type of signal")
    timestamp: datetime = Field(..., description="When the signal was detected/occurred")
    source: str = Field(..., description="Data source for the signal")
    company_ticker: str = Field(..., description="Company ticker symbol")

    relevance_score: float = Field(
        5.0,
        ge=0.0,
        le=10.0,
        description="Signal relevance score (0-10)"
    )
    confidence: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in signal accuracy (0-1)"
    )

    tags: List[str] = Field(default_factory=list, description="Additional tags/labels")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    processed: bool = Field(False, description="Whether signal has been processed")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")

    @field_validator("signal_id")
    @classmethod
    def validate_signal_id(cls, v: str) -> str:
        """Validate signal ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Signal ID cannot be empty")
        return v.strip()

    @field_validator("company_ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker symbol."""
        if not v or not v.strip():
            raise ValueError("Company ticker cannot be empty")
        return v.strip().upper()

    @computed_field
    @property
    def weighted_score(self) -> float:
        """Relevance score weighted by confidence."""
        return round(self.relevance_score * self.confidence, 2)

    @computed_field
    @property
    def age_days(self) -> int:
        """Days since signal occurred."""
        delta = datetime.utcnow() - self.timestamp
        return delta.days

    def mark_processed(self) -> None:
        """Mark signal as processed."""
        self.processed = True
        self.processed_at = datetime.utcnow()


class ClinicalTrialSignal(BaseSignal):
    """
    Signal from clinical trial events.

    Captures trial milestones, status changes, and outcome data.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_ct_20251207_001",
                "signal_type": "clinical_trial",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "ClinicalTrials.gov",
                "company_ticker": "ABCD",
                "trial_id": "NCT12345678",
                "phase": "phase_2",
                "status": "completed",
                "outcome": "positive",
                "drug_name": "ABC-123",
                "indication": "Non-small cell lung cancer",
                "enrollment": 150,
                "primary_endpoint_met": True,
            }
        }
    )

    signal_type: SignalType = Field(default=SignalType.CLINICAL_TRIAL, frozen=True)

    trial_id: str = Field(..., description="Clinical trial identifier (e.g., NCT number)")
    phase: TrialPhase = Field(..., description="Trial phase")
    status: TrialStatus = Field(..., description="Current trial status")
    outcome: TrialOutcome = Field(
        TrialOutcome.PENDING,
        description="Trial outcome if available"
    )

    drug_name: str = Field(..., description="Drug being tested")
    indication: str = Field(..., description="Disease/condition being treated")

    enrollment: Optional[int] = Field(None, ge=0, description="Number of patients enrolled")
    sites: Optional[int] = Field(None, ge=0, description="Number of trial sites")

    start_date: Optional[date] = Field(None, description="Trial start date")
    completion_date: Optional[date] = Field(None, description="Trial completion date")

    primary_endpoint_met: Optional[bool] = Field(
        None,
        description="Whether primary endpoint was met"
    )
    secondary_endpoints_met: Optional[List[str]] = Field(
        None,
        description="List of secondary endpoints met"
    )

    adverse_events: Optional[Dict[str, int]] = Field(
        None,
        description="Adverse event counts by type"
    )

    @field_validator("trial_id")
    @classmethod
    def validate_trial_id(cls, v: str) -> str:
        """Validate trial ID format."""
        if not v or not v.strip():
            raise ValueError("Trial ID cannot be empty")
        return v.strip().upper()

    @computed_field
    @property
    def is_positive_outcome(self) -> bool:
        """Whether trial has a positive outcome."""
        return self.outcome == TrialOutcome.POSITIVE and (
            self.primary_endpoint_met is True or self.status == TrialStatus.COMPLETED
        )

    @computed_field
    @property
    def is_late_stage(self) -> bool:
        """Whether trial is in late-stage development."""
        return self.phase in {TrialPhase.PHASE_2_3, TrialPhase.PHASE_3}

    @computed_field
    @property
    def ma_signal_strength(self) -> float:
        """
        M&A signal strength based on trial characteristics (0-10).

        Positive late-stage results are stronger signals.
        """
        base_score = 5.0

        # Phase weighting
        phase_scores = {
            TrialPhase.PHASE_1: 1.0,
            TrialPhase.PHASE_1_2: 1.5,
            TrialPhase.PHASE_2: 2.0,
            TrialPhase.PHASE_2_3: 3.0,
            TrialPhase.PHASE_3: 3.5,
            TrialPhase.PHASE_4: 1.0,
        }
        base_score += phase_scores.get(self.phase, 0.0)

        # Outcome weighting
        if self.outcome == TrialOutcome.POSITIVE:
            base_score += 2.5
        elif self.outcome == TrialOutcome.NEGATIVE:
            base_score -= 3.0
        elif self.outcome == TrialOutcome.MIXED:
            base_score += 0.5

        # Primary endpoint bonus
        if self.primary_endpoint_met is True:
            base_score += 1.5

        return round(min(max(base_score, 0.0), 10.0), 2)


class PatentSignal(BaseSignal):
    """
    Signal from patent activity.

    Tracks new filings, grants, expirations, and litigation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_pat_20251207_001",
                "signal_type": "patent",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "USPTO",
                "company_ticker": "ABCD",
                "patent_id": "US1234567B2",
                "patent_status": "granted",
                "filing_date": "2020-06-15",
                "grant_date": "2022-08-20",
                "expiry_date": "2040-06-15",
                "drug_coverage": ["ABC-123", "ABC-456"],
            }
        }
    )

    signal_type: SignalType = Field(default=SignalType.PATENT, frozen=True)

    patent_id: str = Field(..., description="Patent number/identifier")
    patent_status: str = Field(..., description="Patent status (filed, granted, expired, etc.)")

    filing_date: date = Field(..., description="Date patent was filed")
    grant_date: Optional[date] = Field(None, description="Date patent was granted")
    expiry_date: date = Field(..., description="Patent expiration date")

    title: Optional[str] = Field(None, description="Patent title")
    abstract: Optional[str] = Field(None, description="Patent abstract")

    drug_coverage: List[str] = Field(
        default_factory=list,
        description="Drugs/compounds covered by patent"
    )

    jurisdiction: str = Field(default="US", description="Patent jurisdiction (US, EP, etc.)")

    is_composition_of_matter: bool = Field(
        False,
        description="Whether patent covers composition of matter"
    )
    is_method_of_use: bool = Field(False, description="Whether patent covers method of use")
    is_formulation: bool = Field(False, description="Whether patent covers formulation")

    litigation_active: bool = Field(False, description="Whether patent is in litigation")

    @field_validator("patent_id")
    @classmethod
    def validate_patent_id(cls, v: str) -> str:
        """Validate patent ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Patent ID cannot be empty")
        return v.strip().upper()

    @computed_field
    @property
    def years_until_expiry(self) -> float:
        """Years remaining until patent expires."""
        today = date.today()
        if self.expiry_date < today:
            return 0.0

        delta = self.expiry_date - today
        return round(delta.days / 365.25, 2)

    @computed_field
    @property
    def is_near_expiry(self) -> bool:
        """Whether patent is within 3 years of expiration."""
        return 0 < self.years_until_expiry <= 3.0

    @computed_field
    @property
    def patent_type_score(self) -> float:
        """
        Score based on patent type strength (0-10).

        Composition of matter patents are strongest.
        """
        score = 0.0
        if self.is_composition_of_matter:
            score += 5.0
        if self.is_method_of_use:
            score += 3.0
        if self.is_formulation:
            score += 2.0
        return min(score, 10.0)

    @computed_field
    @property
    def ma_signal_strength(self) -> float:
        """
        M&A signal strength based on patent characteristics (0-10).

        Patents nearing expiry or in litigation indicate vulnerability.
        """
        base_score = 5.0

        # Near expiry increases M&A likelihood
        if self.is_near_expiry:
            base_score += 3.0
        elif self.years_until_expiry < 5.0:
            base_score += 2.0
        elif self.years_until_expiry < 7.0:
            base_score += 1.0

        # Litigation indicates IP challenges
        if self.litigation_active:
            base_score += 2.5

        # Multiple drug coverage
        if len(self.drug_coverage) > 1:
            base_score += 1.0

        return round(min(base_score, 10.0), 2)


class InsiderSignal(BaseSignal):
    """
    Signal from insider trading activity.

    Tracks executive and director stock transactions.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_ins_20251207_001",
                "signal_type": "insider_transaction",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "SEC Form 4",
                "company_ticker": "ABCD",
                "transaction_type": "purchase",
                "insider_name": "John Smith",
                "insider_role": "ceo",
                "shares": 50000,
                "price_per_share": 25.50,
                "transaction_date": "2025-12-05",
            }
        }
    )

    signal_type: SignalType = Field(default=SignalType.INSIDER_TRANSACTION, frozen=True)

    transaction_type: TransactionType = Field(..., description="Type of transaction")
    insider_name: str = Field(..., description="Name of insider")
    insider_role: InsiderRole = Field(..., description="Role/title of insider")

    shares: int = Field(..., description="Number of shares transacted")
    price_per_share: Decimal = Field(..., ge=0, description="Price per share in USD")

    transaction_date: date = Field(..., description="Date of transaction")

    is_10b5_1_plan: bool = Field(
        False,
        description="Whether transaction was part of a 10b5-1 plan"
    )

    shares_owned_after: Optional[int] = Field(
        None,
        description="Total shares owned after transaction"
    )

    @field_validator("insider_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate insider name is not empty."""
        if not v or not v.strip():
            raise ValueError("Insider name cannot be empty")
        return v.strip()

    @computed_field
    @property
    def transaction_value_usd(self) -> Decimal:
        """Total transaction value in USD."""
        return abs(self.shares) * self.price_per_share

    @computed_field
    @property
    def is_significant_transaction(self) -> bool:
        """Whether transaction is significant (>$100k or >10k shares)."""
        return (
            self.transaction_value_usd >= 100000
            or abs(self.shares) >= 10000
        )

    @computed_field
    @property
    def is_c_suite(self) -> bool:
        """Whether insider is C-suite executive."""
        c_suite_roles = {
            InsiderRole.CEO,
            InsiderRole.CFO,
            InsiderRole.COO,
            InsiderRole.CSO,
            InsiderRole.CMO,
        }
        return self.insider_role in c_suite_roles

    @computed_field
    @property
    def ma_signal_strength(self) -> float:
        """
        M&A signal strength based on transaction characteristics (0-10).

        Unusual selling by C-suite may indicate M&A discussions.
        Large purchases by insiders suggest confidence.
        """
        base_score = 5.0

        # C-suite transactions are more significant
        if self.is_c_suite:
            base_score += 1.5

        # Transaction type
        if self.transaction_type == TransactionType.SALE:
            if not self.is_10b5_1_plan:
                # Unplanned sales by insiders may signal M&A
                base_score += 2.5
            else:
                base_score += 0.5
        elif self.transaction_type == TransactionType.PURCHASE:
            # Large insider purchases suggest confidence, lower M&A likelihood
            base_score -= 1.5

        # Transaction size
        if self.is_significant_transaction:
            base_score += 1.5

        # Recent transactions are more relevant
        days_ago = (date.today() - self.transaction_date).days
        if days_ago <= 30:
            base_score += 1.0
        elif days_ago <= 90:
            base_score += 0.5

        return round(min(max(base_score, 0.0), 10.0), 2)


class HiringSignal(BaseSignal):
    """
    Signal from hiring and personnel changes.

    Tracks key executive hires that may indicate strategic shifts.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_hire_20251207_001",
                "signal_type": "hiring",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "LinkedIn",
                "company_ticker": "ABCD",
                "role": "VP of Corporate Development",
                "seniority": "vp",
                "hire_name": "Jane Doe",
                "previous_company": "BigPharma Inc",
                "is_new_position": True,
            }
        }
    )

    signal_type: SignalType = Field(default=SignalType.HIRING, frozen=True)

    role: str = Field(..., description="Job title/role")
    seniority: SeniorityLevel = Field(..., description="Seniority level")

    hire_name: Optional[str] = Field(None, description="Name of new hire")
    previous_company: Optional[str] = Field(None, description="Previous employer")
    previous_role: Optional[str] = Field(None, description="Previous job title")

    department: Optional[str] = Field(None, description="Department/function")
    is_new_position: bool = Field(False, description="Whether this is a newly created role")
    is_replacement: bool = Field(False, description="Whether this replaced someone")

    hire_date: Optional[date] = Field(None, description="Start date")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is not empty."""
        if not v or not v.strip():
            raise ValueError("Role cannot be empty")
        return v.strip()

    @computed_field
    @property
    def is_senior_hire(self) -> bool:
        """Whether hire is senior level (VP or above)."""
        return self.seniority in {SeniorityLevel.C_SUITE, SeniorityLevel.VP}

    @computed_field
    @property
    def is_strategic_role(self) -> bool:
        """
        Whether role is strategically significant.

        Corporate development, M&A, and strategy roles signal transaction activity.
        """
        strategic_keywords = [
            "corporate development",
            "m&a",
            "business development",
            "strategy",
            "corp dev",
            "bd",
        ]
        role_lower = self.role.lower()
        return any(keyword in role_lower for keyword in strategic_keywords)

    @computed_field
    @property
    def ma_signal_strength(self) -> float:
        """
        M&A signal strength based on hiring characteristics (0-10).

        Strategic roles like Corp Dev VP are strong M&A signals.
        """
        base_score = 5.0

        # Strategic roles are key signals
        if self.is_strategic_role:
            base_score += 4.0

        # Seniority
        if self.seniority == SeniorityLevel.C_SUITE:
            base_score += 2.0
        elif self.seniority == SeniorityLevel.VP:
            base_score += 1.5

        # New positions suggest expansion/preparation
        if self.is_new_position:
            base_score += 1.0

        # Previous company context
        if self.previous_company:
            # Coming from big pharma/established companies
            pharma_keywords = ["pharma", "therapeutics", "biogen", "pfizer", "merck"]
            if any(kw in self.previous_company.lower() for kw in pharma_keywords):
                base_score += 0.5

        return round(min(base_score, 10.0), 2)


class FinancialSignal(BaseSignal):
    """
    Signal from financial events and metrics.

    Tracks earnings, cash position changes, and financial stress indicators.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "sig_fin_20251207_001",
                "signal_type": "financial",
                "timestamp": "2025-12-07T10:30:00Z",
                "source": "SEC 10-Q",
                "company_ticker": "ABCD",
                "event_type": "earnings_report",
                "cash_position_usd": 150000000,
                "quarterly_burn_usd": 35000000,
                "revenue_usd": 5000000,
            }
        }
    )

    signal_type: SignalType = Field(default=SignalType.FINANCIAL, frozen=True)

    event_type: str = Field(..., description="Type of financial event")

    cash_position_usd: Optional[Decimal] = Field(None, description="Current cash position")
    quarterly_burn_usd: Optional[Decimal] = Field(None, description="Quarterly cash burn")
    revenue_usd: Optional[Decimal] = Field(None, description="Quarterly revenue")
    net_income_usd: Optional[Decimal] = Field(None, description="Net income/loss")

    guidance_lowered: bool = Field(False, description="Whether guidance was lowered")
    covenant_breach: bool = Field(False, description="Whether debt covenants breached")
    going_concern_warning: bool = Field(
        False,
        description="Whether going concern warning issued"
    )

    @computed_field
    @property
    def runway_quarters(self) -> Optional[float]:
        """Calculate cash runway in quarters."""
        if (
            self.cash_position_usd is None
            or self.quarterly_burn_usd is None
            or self.quarterly_burn_usd <= 0
        ):
            return None

        return round(float(self.cash_position_usd / self.quarterly_burn_usd), 2)

    @computed_field
    @property
    def is_cash_critical(self) -> bool:
        """Whether company is in cash-critical situation (<2 quarters runway)."""
        if self.runway_quarters is None:
            return False
        return self.runway_quarters < 2.0

    @computed_field
    @property
    def ma_signal_strength(self) -> float:
        """
        M&A signal strength based on financial stress (0-10).

        Cash-critical situations are strong M&A signals.
        """
        base_score = 5.0

        # Cash runway
        if self.runway_quarters is not None:
            if self.runway_quarters < 2.0:
                base_score += 4.0
            elif self.runway_quarters < 4.0:
                base_score += 2.5
            elif self.runway_quarters < 6.0:
                base_score += 1.0

        # Financial warnings
        if self.going_concern_warning:
            base_score += 3.0
        if self.covenant_breach:
            base_score += 2.0
        if self.guidance_lowered:
            base_score += 1.0

        return round(min(base_score, 10.0), 2)
