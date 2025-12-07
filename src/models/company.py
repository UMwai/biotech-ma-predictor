"""
Company and pipeline data models.

Defines the core structure for biotech companies, their drug candidates,
and development pipelines.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, computed_field, ConfigDict


class TherapeuticArea(str, Enum):
    """Therapeutic areas for drug development."""

    ONCOLOGY = "oncology"
    IMMUNOLOGY = "immunology"
    NEUROLOGY = "neurology"
    CARDIOVASCULAR = "cardiovascular"
    RARE_DISEASE = "rare_disease"
    INFECTIOUS_DISEASE = "infectious_disease"
    METABOLIC = "metabolic"
    RESPIRATORY = "respiratory"
    OPHTHALMOLOGY = "ophthalmology"
    DERMATOLOGY = "dermatology"
    OTHER = "other"


class DevelopmentPhase(str, Enum):
    """Clinical development phases."""

    DISCOVERY = "discovery"
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    NDA_BLA = "nda_bla"
    APPROVED = "approved"
    DISCONTINUED = "discontinued"


class DrugCandidate(BaseModel):
    """
    Represents a single drug candidate in development.

    Tracks key attributes including development phase, indication,
    mechanism of action, and patent status.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "ABC-123",
                "phase": "phase_2",
                "indication": "Non-small cell lung cancer",
                "mechanism": "PD-L1 inhibitor",
                "therapeutic_area": "oncology",
                "patent_expiry": "2038-06-15",
                "orphan_designation": True,
                "fast_track": False,
                "breakthrough_therapy": False,
                "next_milestone": "Phase 2 data readout",
                "next_milestone_date": "2025-Q2",
                "competitive_landscape_score": 7.5,
                "market_potential_usd": 2500000000,
            }
        }
    )

    name: str = Field(..., description="Drug candidate name or code")
    phase: DevelopmentPhase = Field(..., description="Current development phase")
    indication: str = Field(..., description="Target disease or condition")
    mechanism: str = Field(..., description="Mechanism of action")
    therapeutic_area: TherapeuticArea = Field(..., description="Primary therapeutic area")

    patent_expiry: Optional[date] = Field(None, description="Primary patent expiration date")
    orphan_designation: bool = Field(False, description="Has orphan drug designation")
    fast_track: bool = Field(False, description="Has FDA fast track designation")
    breakthrough_therapy: bool = Field(False, description="Has breakthrough therapy designation")

    next_milestone: Optional[str] = Field(None, description="Description of next major milestone")
    next_milestone_date: Optional[str] = Field(None, description="Expected date of next milestone (YYYY-MM-DD or YYYY-QN)")

    competitive_landscape_score: float = Field(
        5.0,
        ge=0.0,
        le=10.0,
        description="Competitive advantage score (0-10)"
    )
    market_potential_usd: Optional[Decimal] = Field(
        None,
        description="Estimated peak annual market potential in USD"
    )

    additional_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure drug name is not empty."""
        if not v or not v.strip():
            raise ValueError("Drug candidate name cannot be empty")
        return v.strip()

    @field_validator("next_milestone_date")
    @classmethod
    def validate_milestone_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate milestone date format."""
        if v is None:
            return v

        v = v.strip()

        # Check for quarter format (YYYY-QN)
        if "Q" in v.upper():
            parts = v.upper().split("-Q")
            if len(parts) != 2:
                raise ValueError("Quarter format must be YYYY-QN")
            try:
                year = int(parts[0])
                quarter = int(parts[1])
                if not (1 <= quarter <= 4):
                    raise ValueError("Quarter must be between 1 and 4")
                if year < 2000 or year > 2100:
                    raise ValueError("Year must be between 2000 and 2100")
            except ValueError as e:
                raise ValueError(f"Invalid quarter format: {e}")
            return v.upper()

        # Try parsing as date
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD or YYYY-QN format")

    @computed_field
    @property
    def has_regulatory_designation(self) -> bool:
        """Check if drug has any special regulatory designation."""
        return self.orphan_designation or self.fast_track or self.breakthrough_therapy

    @computed_field
    @property
    def phase_score(self) -> float:
        """
        Numeric score based on development phase (0-10).
        Higher phase = higher score.
        """
        phase_scores = {
            DevelopmentPhase.DISCOVERY: 1.0,
            DevelopmentPhase.PRECLINICAL: 2.0,
            DevelopmentPhase.PHASE_1: 3.5,
            DevelopmentPhase.PHASE_1_2: 4.5,
            DevelopmentPhase.PHASE_2: 6.0,
            DevelopmentPhase.PHASE_2_3: 7.5,
            DevelopmentPhase.PHASE_3: 8.5,
            DevelopmentPhase.NDA_BLA: 9.5,
            DevelopmentPhase.APPROVED: 10.0,
            DevelopmentPhase.DISCONTINUED: 0.0,
        }
        return phase_scores.get(self.phase, 0.0)

    @computed_field
    @property
    def patent_years_remaining(self) -> Optional[float]:
        """Calculate years remaining until patent expiry."""
        if self.patent_expiry is None:
            return None

        today = date.today()
        if self.patent_expiry < today:
            return 0.0

        delta = self.patent_expiry - today
        return round(delta.days / 365.25, 2)

    def to_summary(self) -> str:
        """Generate a brief text summary of the drug candidate."""
        summary = f"{self.name} ({self.phase.value}): {self.indication}"
        if self.has_regulatory_designation:
            designations = []
            if self.orphan_designation:
                designations.append("Orphan")
            if self.fast_track:
                designations.append("Fast Track")
            if self.breakthrough_therapy:
                designations.append("Breakthrough")
            summary += f" [{', '.join(designations)}]"
        return summary


class Pipeline(BaseModel):
    """
    Represents a company's drug development pipeline.

    Aggregates all drug candidates and provides pipeline-level metrics.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_ticker": "ABCD",
                "drugs": [],
                "last_updated": "2025-12-07T10:30:00Z",
            }
        }
    )

    company_ticker: str = Field(..., description="Company ticker symbol")
    drugs: List[DrugCandidate] = Field(default_factory=list, description="List of drug candidates")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last pipeline update timestamp"
    )

    @field_validator("company_ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker symbol."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        return v.strip().upper()

    @computed_field
    @property
    def total_candidates(self) -> int:
        """Total number of drug candidates."""
        return len(self.drugs)

    @computed_field
    @property
    def active_candidates(self) -> int:
        """Number of active (non-discontinued) candidates."""
        return sum(1 for drug in self.drugs if drug.phase != DevelopmentPhase.DISCONTINUED)

    @computed_field
    @property
    def clinical_stage_count(self) -> int:
        """Number of candidates in clinical stages (Phase 1-3)."""
        clinical_phases = {
            DevelopmentPhase.PHASE_1,
            DevelopmentPhase.PHASE_1_2,
            DevelopmentPhase.PHASE_2,
            DevelopmentPhase.PHASE_2_3,
            DevelopmentPhase.PHASE_3,
        }
        return sum(1 for drug in self.drugs if drug.phase in clinical_phases)

    @computed_field
    @property
    def late_stage_count(self) -> int:
        """Number of candidates in late-stage development (Phase 2 and beyond)."""
        late_phases = {
            DevelopmentPhase.PHASE_2,
            DevelopmentPhase.PHASE_2_3,
            DevelopmentPhase.PHASE_3,
            DevelopmentPhase.NDA_BLA,
        }
        return sum(1 for drug in self.drugs if drug.phase in late_phases)

    @computed_field
    @property
    def approved_count(self) -> int:
        """Number of approved drugs."""
        return sum(1 for drug in self.drugs if drug.phase == DevelopmentPhase.APPROVED)

    @computed_field
    @property
    def therapeutic_diversity(self) -> int:
        """Number of unique therapeutic areas in pipeline."""
        return len(set(drug.therapeutic_area for drug in self.drugs))

    @computed_field
    @property
    def average_phase_score(self) -> float:
        """Average development phase score across all active candidates."""
        active = [drug for drug in self.drugs if drug.phase != DevelopmentPhase.DISCONTINUED]
        if not active:
            return 0.0
        return round(sum(drug.phase_score for drug in active) / len(active), 2)

    @computed_field
    @property
    def total_market_potential_usd(self) -> Optional[Decimal]:
        """Total estimated market potential across all candidates."""
        potentials = [
            drug.market_potential_usd
            for drug in self.drugs
            if drug.market_potential_usd is not None
        ]
        if not potentials:
            return None
        return sum(potentials)

    @computed_field
    @property
    def pipeline_strength_score(self) -> float:
        """
        Composite pipeline strength score (0-10).

        Based on:
        - Number of clinical stage assets
        - Late-stage presence
        - Average phase score
        - Therapeutic diversity
        """
        if not self.drugs:
            return 0.0

        # Component scores
        clinical_score = min(self.clinical_stage_count / 5.0, 1.0) * 3.0
        late_stage_score = min(self.late_stage_count / 3.0, 1.0) * 3.0
        phase_score = (self.average_phase_score / 10.0) * 2.5
        diversity_score = min(self.therapeutic_diversity / 3.0, 1.0) * 1.5

        total = clinical_score + late_stage_score + phase_score + diversity_score
        return round(min(total, 10.0), 2)

    def get_drugs_by_phase(self, phase: DevelopmentPhase) -> List[DrugCandidate]:
        """Get all drugs in a specific development phase."""
        return [drug for drug in self.drugs if drug.phase == phase]

    def get_drugs_by_therapeutic_area(self, area: TherapeuticArea) -> List[DrugCandidate]:
        """Get all drugs in a specific therapeutic area."""
        return [drug for drug in self.drugs if drug.therapeutic_area == area]


class Company(BaseModel):
    """
    Represents a biotech company with financial and operational data.

    Core model for tracking companies in the M&A prediction system.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ticker": "ABCD",
                "name": "ABC Therapeutics",
                "market_cap_usd": 1500000000,
                "cash_position_usd": 250000000,
                "quarterly_burn_rate_usd": 30000000,
                "therapeutic_areas": ["oncology", "immunology"],
                "founded_year": 2015,
                "employee_count": 120,
                "headquarters_location": "Cambridge, MA",
                "pipeline": None,
            }
        }
    )

    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")

    market_cap_usd: Decimal = Field(..., ge=0, description="Market capitalization in USD")
    cash_position_usd: Decimal = Field(..., ge=0, description="Cash and equivalents in USD")
    quarterly_burn_rate_usd: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Average quarterly cash burn rate in USD"
    )
    total_debt_usd: Decimal = Field(default=Decimal(0), ge=0, description="Total debt in USD")

    therapeutic_areas: List[TherapeuticArea] = Field(
        default_factory=list,
        description="Primary therapeutic focus areas"
    )

    founded_year: Optional[int] = Field(None, ge=1900, le=2100, description="Year founded")
    employee_count: Optional[int] = Field(None, ge=0, description="Number of employees")
    headquarters_location: Optional[str] = Field(None, description="HQ location")

    pipeline: Optional[Pipeline] = Field(None, description="Drug development pipeline")

    is_public: bool = Field(True, description="Whether company is publicly traded")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last data update timestamp"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional company metadata"
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate and normalize ticker symbol."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        ticker = v.strip().upper()
        if len(ticker) > 10:
            raise ValueError("Ticker symbol too long")
        return ticker

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure company name is not empty."""
        if not v or not v.strip():
            raise ValueError("Company name cannot be empty")
        return v.strip()

    @field_validator("therapeutic_areas")
    @classmethod
    def validate_therapeutic_areas(cls, v: List[TherapeuticArea]) -> List[TherapeuticArea]:
        """Remove duplicates from therapeutic areas."""
        return list(set(v))

    @computed_field
    @property
    def runway_quarters(self) -> Optional[float]:
        """
        Calculate cash runway in quarters.

        Returns None if burn rate is not available or is zero.
        """
        if not self.quarterly_burn_rate_usd or self.quarterly_burn_rate_usd == 0:
            return None

        return round(float(self.cash_position_usd / self.quarterly_burn_rate_usd), 2)

    @computed_field
    @property
    def enterprise_value_usd(self) -> Decimal:
        """Calculate enterprise value (market cap + debt - cash)."""
        return self.market_cap_usd + self.total_debt_usd - self.cash_position_usd

    @computed_field
    @property
    def is_cash_constrained(self) -> bool:
        """
        Determine if company is cash constrained.

        Returns True if runway is less than 4 quarters (1 year).
        """
        if self.runway_quarters is None:
            return False
        return self.runway_quarters < 4.0

    @computed_field
    @property
    def company_age_years(self) -> Optional[int]:
        """Calculate company age in years."""
        if self.founded_year is None:
            return None
        return datetime.now().year - self.founded_year

    @computed_field
    @property
    def pipeline_value_ratio(self) -> Optional[float]:
        """
        Ratio of total pipeline market potential to market cap.

        Higher ratio indicates pipeline may be undervalued.
        """
        if (
            self.pipeline is None
            or self.pipeline.total_market_potential_usd is None
            or self.market_cap_usd == 0
        ):
            return None

        ratio = float(self.pipeline.total_market_potential_usd / self.market_cap_usd)
        return round(ratio, 2)

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary dictionary of key company metrics."""
        return {
            "ticker": self.ticker,
            "name": self.name,
            "market_cap_usd": float(self.market_cap_usd),
            "cash_position_usd": float(self.cash_position_usd),
            "runway_quarters": self.runway_quarters,
            "is_cash_constrained": self.is_cash_constrained,
            "therapeutic_areas": [area.value for area in self.therapeutic_areas],
            "pipeline_drugs": self.pipeline.total_candidates if self.pipeline else 0,
            "pipeline_strength": self.pipeline.pipeline_strength_score if self.pipeline else 0.0,
            "last_updated": self.last_updated.isoformat(),
        }

    def serialize_for_api(self) -> Dict[str, Any]:
        """Serialize company data for API responses."""
        data = self.model_dump(mode="json")

        # Convert Decimal to float for JSON serialization
        data["market_cap_usd"] = float(self.market_cap_usd)
        data["cash_position_usd"] = float(self.cash_position_usd)
        data["total_debt_usd"] = float(self.total_debt_usd)

        if self.quarterly_burn_rate_usd:
            data["quarterly_burn_rate_usd"] = float(self.quarterly_burn_rate_usd)

        return data
