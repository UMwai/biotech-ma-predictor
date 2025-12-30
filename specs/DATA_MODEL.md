# Biotech M&A Predictor - Data Model Specification

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Active

---

## Overview

This document defines the data structures and domain models used in the Biotech M&A Predictor system. The system aggregates signals from multiple upstream sources, calculates M&A probability scores, and matches targets with acquirers.

---

## Data Sources

```
                    UPSTREAM SIGNAL SOURCES
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    │  ┌─────────────────┐  ┌─────────────────┐               │
    │  │ clinical-trial- │  │ patent-ip-      │               │
    │  │ signals         │  │ intelligence    │               │
    │  │                 │  │                 │               │
    │  │ • Trial data    │  │ • Patent data   │               │
    │  │ • Phase changes │  │ • Cliff events  │               │
    │  │ • Outcomes      │  │ • Generic filings│              │
    │  └────────┬────────┘  └────────┬────────┘               │
    │           │                    │                        │
    │  ┌────────┴────────────────────┴────────┐               │
    │  │                                      │               │
    │  │  ┌─────────────────┐  ┌─────────────────┐           │
    │  │  │ insider-hiring- │  │ External APIs   │           │
    │  │  │ signals         │  │ (SEC, FDA)      │           │
    │  │  │                 │  │                 │           │
    │  │  │ • Form 4/13F    │  │ • Company data  │           │
    │  │  │ • Hiring events │  │ • Financial data│           │
    │  │  └─────────────────┘  └─────────────────┘           │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
                              │
                              ▼
    ┌──────────────────────────────────────────────────────────┐
    │              BIOTECH M&A PREDICTOR                        │
    │                                                          │
    │  ┌─────────────────┐  ┌─────────────────┐               │
    │  │   PostgreSQL    │  │   TimescaleDB   │               │
    │  │                 │  │                 │               │
    │  │ • Companies     │  │ • Signals       │               │
    │  │ • Acquirers     │  │ • Score history │               │
    │  │ • Candidates    │  │ • Time-series   │               │
    │  │ • Matches       │  │                 │               │
    │  └─────────────────┘  └─────────────────┘               │
    └──────────────────────────────────────────────────────────┘
```

---

## Core Domain Models

### Company

```python
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List, Dict
from decimal import Decimal
from enum import Enum


class Sector(Enum):
    """Company sector classification"""
    BIOTECHNOLOGY = "biotechnology"
    PHARMACEUTICALS = "pharmaceuticals"
    MEDICAL_DEVICES = "medical_devices"
    DIAGNOSTICS = "diagnostics"
    OTHER = "other"


class TherapeuticArea(Enum):
    """Therapeutic area classifications"""
    ONCOLOGY = "oncology"
    NEUROLOGY = "neurology"
    CARDIOVASCULAR = "cardiovascular"
    IMMUNOLOGY = "immunology"
    RARE_DISEASE = "rare_disease"
    METABOLIC = "metabolic"
    INFECTIOUS_DISEASE = "infectious_disease"
    OTHER = "other"


@dataclass
class Company:
    """
    Represents a biotech company being tracked for M&A potential
    """
    # Identity
    id: str
    ticker: Optional[str]
    name: str
    cik: Optional[str]
    description: Optional[str]

    # Classification
    sector: Sector
    therapeutic_areas: List[TherapeuticArea]
    technology_platforms: List[str]
    headquarters: Optional[str]
    employees: Optional[int]
    founded: Optional[int]

    # Current financials
    market_cap: Optional[Decimal]  # Millions USD
    enterprise_value: Optional[Decimal]
    stock_price: Optional[Decimal]
    cash_position: Optional[Decimal]
    burn_rate: Optional[Decimal]  # Quarterly burn
    runway_months: Optional[int]
    revenue_ttm: Optional[Decimal]
    debt: Optional[Decimal]

    # M&A scoring
    ma_score: Decimal  # 0-100
    ma_tier: int  # 1, 2, or 3
    confidence: Decimal  # 0-1
    recommendation: str  # STRONG_BUY, BUY, HOLD, etc.

    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int

    @property
    def is_watchlist_candidate(self) -> bool:
        """Company is on active watchlist if Tier 1 or 2"""
        return self.ma_tier in (1, 2)

    @property
    def is_high_priority(self) -> bool:
        """High priority if Tier 1"""
        return self.ma_tier == 1

    @property
    def cash_runway_critical(self) -> bool:
        """Cash runway is critical if < 12 months"""
        if self.runway_months is None:
            return False
        return self.runway_months < 12
```

### M&A Candidate

```python
class AcquisitionProbability(Enum):
    """Acquisition probability levels"""
    VERY_HIGH = "very_high"  # > 80%
    HIGH = "high"            # 60-80%
    MEDIUM = "medium"        # 40-60%
    LOW = "low"              # < 40%


class TargetType(Enum):
    """Type of acquisition target"""
    PLATFORM = "platform"        # Full company acquisition
    ASSET = "asset"              # Single asset deal
    PARTNERSHIP = "partnership"  # Strategic partnership
    LICENSE = "license"          # Licensing deal


class PrimaryDriver(Enum):
    """Primary drivers of M&A likelihood"""
    PATENT_CLIFF = "patent_cliff"
    CLINICAL_SUCCESS = "clinical_success"
    CLINICAL_FAILURE = "clinical_failure"
    CASH_BURN = "cash_burn"
    INSIDER_BUYING = "insider_buying"
    LEADERSHIP_CHANGES = "leadership_changes"
    STRATEGIC_HIRING = "strategic_hiring"
    MARKET_CONDITIONS = "market_conditions"
    COMPETITIVE_PRESSURE = "competitive_pressure"
    REGULATORY_PRESSURE = "regulatory_pressure"


@dataclass
class MACandidate:
    """
    M&A candidate assessment for a company
    """
    # Identity
    id: str
    company_id: str
    company: Company  # Reference

    # Current assessment
    ma_score: Decimal  # 0-100
    tier: int  # 1, 2, or 3
    confidence: Decimal  # 0-1
    acquisition_probability: AcquisitionProbability
    target_type: TargetType
    recommendation: str

    # Score components
    clinical_score: Decimal
    patent_score: Decimal
    insider_score: Decimal
    financial_score: Decimal

    # Analysis
    primary_drivers: List[PrimaryDriver]
    risk_factors: List[str]
    key_signals: List[str]

    # Valuation
    valuation_low: Decimal  # Millions USD
    valuation_high: Decimal
    valuation_basis: str

    # Timeline
    earliest_date: Optional[date]
    likely_date: Optional[date]
    latest_date: Optional[date]

    # Contributing signals
    contributing_event_ids: List[str]

    # Metadata
    evaluation_date: date
    created_at: datetime
    updated_at: datetime

    @property
    def signal_summary(self) -> Dict[str, int]:
        """Count of signals by source"""
        return {
            'clinical': len([s for s in self.contributing_event_ids if 'clinical' in s]),
            'patent': len([s for s in self.contributing_event_ids if 'patent' in s]),
            'insider': len([s for s in self.contributing_event_ids if 'insider' in s]),
            'hiring': len([s for s in self.contributing_event_ids if 'hiring' in s])
        }
```

### Acquirer

```python
@dataclass
class Acquirer:
    """
    Potential acquirer company profile
    """
    # Identity
    id: str
    ticker: str
    name: str

    # Financials
    market_cap: Decimal  # Millions USD
    cash_position: Decimal
    debt_capacity: Optional[Decimal]

    # Acquisition profile
    focus_areas: List[TherapeuticArea]
    strategic_priorities: List[str]
    pipeline_gaps: List[str]
    technology_interests: List[str]

    # Historical activity
    deals_5y: int
    avg_deal_size: Decimal
    preferred_stages: List[str]  # phase2, phase3, etc.
    preferred_therapeutics: List[TherapeuticArea]

    # Recent deals
    recent_deals: List['AcquisitionDeal']

    # Status
    active: bool  # Currently acquiring

    # Metadata
    created_at: datetime
    updated_at: datetime


@dataclass
class AcquisitionDeal:
    """
    Historical acquisition deal
    """
    id: str
    acquirer_id: str
    target_name: str
    target_ticker: Optional[str]
    announcement_date: date
    close_date: Optional[date]
    deal_value: Decimal  # Millions USD
    deal_type: str  # acquisition, merger, asset_purchase
    therapeutic_area: TherapeuticArea
    stage: str  # Target's development stage
    premium_pct: Optional[Decimal]  # Premium paid over market
```

### Acquirer-Target Match

```python
class StrategicRationale(Enum):
    """Primary strategic rationale for match"""
    PIPELINE_GAP_FILL = "pipeline_gap_fill"
    THERAPEUTIC_EXPANSION = "therapeutic_area_expansion"
    TECHNOLOGY_ACQUISITION = "technology_acquisition"
    GEOGRAPHIC_EXPANSION = "geographic_expansion"
    DEFENSIVE = "defensive_acquisition"
    TALENT = "talent_acquisition"
    DIVERSIFICATION = "portfolio_diversification"
    MANUFACTURING = "manufacturing_capacity"
    CONSOLIDATION = "market_share_consolidation"


class FinancingFeasibility(Enum):
    """Deal financing feasibility"""
    HIGHLY_FEASIBLE = "highly_feasible"
    FEASIBLE = "feasible"
    CHALLENGING = "challenging"
    UNLIKELY = "unlikely"


@dataclass
class AcquirerMatch:
    """
    Acquirer-target match analysis
    """
    # Identity
    id: str
    target_id: str
    acquirer_id: str
    target: Company  # Reference
    acquirer: Acquirer  # Reference

    # Match scoring
    match_score: Decimal  # 0-100

    # Score components
    therapeutic_fit: Decimal
    technology_fit: Decimal
    financial_fit: Decimal
    historical_pattern: Decimal

    # Strategic analysis
    strategic_rationale: StrategicRationale
    supporting_factors: List[str]

    # Therapeutic alignment detail
    overlapping_areas: List[TherapeuticArea]
    complementary_areas: List[TherapeuticArea]
    gap_fill_potential: List[str]

    # Financial analysis
    target_valuation: Decimal  # Estimated
    deal_size_pct: Decimal  # % of acquirer market cap
    financing_feasibility: FinancingFeasibility

    # Synergies and risks
    synergies: List['Synergy']
    risks: List['DealRisk']

    # Probability and timeline
    probability: Decimal  # 0-100
    confidence: Decimal
    earliest_announcement: Optional[date]
    likely_announcement: Optional[date]
    latest_announcement: Optional[date]

    # Metadata
    evaluation_date: date
    created_at: datetime
    updated_at: datetime


@dataclass
class Synergy:
    """Identified synergy in a potential deal"""
    synergy_type: str  # revenue, cost, rd, commercial, manufacturing
    description: str
    estimated_value: Optional[Decimal]  # Millions USD


@dataclass
class DealRisk:
    """Risk factor for potential deal"""
    risk_type: str  # regulatory, antitrust, integration, clinical, valuation
    description: str
    severity: str  # low, medium, high, critical
```

---

## Signal Models

### Base Signal

```python
class SignalSource(Enum):
    """Source of signal"""
    CLINICAL = "clinical"
    PATENT = "patent"
    INSIDER = "insider"
    HIRING = "hiring"


class SignalDirection(Enum):
    """Signal direction for M&A likelihood"""
    BULLISH = "bullish"    # Increases M&A likelihood
    BEARISH = "bearish"    # Decreases M&A likelihood
    NEUTRAL = "neutral"


@dataclass
class Signal:
    """
    Base signal model
    """
    id: str
    company_id: str
    signal_source: SignalSource
    signal_type: str
    impact_score: Decimal  # 0-100

    direction: SignalDirection
    description: str
    payload: Dict  # Source-specific data

    # Timing
    signal_date: date
    detected_at: datetime

    # Lineage
    event_id: str  # Original event ID from upstream
    correlation_id: Optional[str]
```

### Clinical Trial Signal

```python
class ClinicalSignalType(Enum):
    """Types of clinical trial signals"""
    PHASE_ADVANCEMENT = "phase_advancement"
    PHASE_FAILURE = "phase_failure"
    TRIAL_TERMINATION = "trial_termination"
    POSITIVE_INTERIM = "positive_interim"
    NEGATIVE_INTERIM = "negative_interim"
    ENROLLMENT_COMPLETION = "enrollment_completion"
    PRIMARY_ENDPOINT_MET = "primary_endpoint_met"
    PRIMARY_ENDPOINT_MISSED = "primary_endpoint_missed"
    REGULATORY_BREAKTHROUGH = "regulatory_breakthrough"
    FDA_FAST_TRACK = "fda_fast_track"
    ORPHAN_DESIGNATION = "orphan_designation"


@dataclass
class ClinicalTrialSignal(Signal):
    """
    Clinical trial signal from clinical-trial-signals
    """
    # Trial info
    trial_nct_id: str
    drug_name: str
    indication: str
    therapeutic_area: TherapeuticArea

    # Signal specifics
    clinical_signal_type: ClinicalSignalType
    current_phase: str
    previous_phase: Optional[str]

    # Trial details
    patient_enrollment: Optional[int]
    primary_endpoints: List[str]
    trial_status: str
    estimated_completion: Optional[date]

    # Source
    data_source: str
    url: Optional[str]
```

### Patent Signal

```python
class PatentSignalType(Enum):
    """Types of patent signals"""
    EXPIRATION_IMMINENT = "expiration_imminent"
    EXPIRATION_OCCURRED = "expiration_occurred"
    GENERIC_CHALLENGE = "generic_challenge"
    ANDA_FILING = "anda_filing"
    PARAGRAPH_IV = "paragraph_iv_certification"
    PATENT_INVALIDATION = "patent_invalidation"
    LOSS_OF_EXCLUSIVITY = "loss_of_exclusivity"
    EXTENSION_GRANTED = "extension_granted"
    EXTENSION_DENIED = "extension_denied"


class ThreatLevel(Enum):
    """Patent cliff threat level"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PatentCliffSignal(Signal):
    """
    Patent cliff signal from patent-ip-intelligence
    """
    # Patent info
    patent_number: str
    patent_title: Optional[str]
    patent_type: str  # composition_of_matter, method_of_use, etc.
    drug_name: str

    # Signal specifics
    patent_signal_type: PatentSignalType
    threat_level: ThreatLevel

    # Dates
    expiration_date: date
    days_until_expiration: int

    # Financial impact
    annual_revenue_at_risk: Optional[Decimal]  # Millions USD
    revenue_percentage: Optional[Decimal]

    # Competition
    generic_competitors: List[Dict]
    exclusivity_extensions: List[Dict]
```

### Insider Signal

```python
class InsiderSignalType(Enum):
    """Types of insider signals"""
    INSIDER_BUY = "insider_buy"
    INSIDER_SELL = "insider_sell"
    INSTITUTIONAL_BUY = "institutional_buy"
    INSTITUTIONAL_SELL = "institutional_sell"
    INSTITUTIONAL_NEW = "institutional_new_position"
    INSTITUTIONAL_EXIT = "institutional_exit"
    OPTION_EXERCISE = "option_exercise"
    CLUSTER_BUY = "cluster_buy"
    CLUSTER_SELL = "cluster_sell"


class SignalStrength(Enum):
    """Signal strength classification"""
    STRONG_BUY = "strong_buy_signal"
    MODERATE_BUY = "moderate_buy_signal"
    NEUTRAL = "neutral"
    MODERATE_SELL = "moderate_sell_signal"
    STRONG_SELL = "strong_sell_signal"


@dataclass
class InsiderActivitySignal(Signal):
    """
    Insider activity signal from insider-hiring-signals
    """
    # Activity info
    insider_signal_type: InsiderSignalType
    filing_type: str  # form_4, form_13f, etc.

    # Person/entity
    insider_name: Optional[str]
    insider_title: Optional[str]
    insider_relationship: Optional[str]
    institutional_investor: Optional[str]

    # Transaction
    transaction_date: date
    transaction_code: str
    shares_transacted: int
    price_per_share: Decimal
    total_value: Decimal
    shares_owned_after: Optional[int]
    ownership_percentage: Optional[Decimal]

    # Analysis
    signal_strength: SignalStrength
```

### Hiring Signal

```python
class HiringSignalType(Enum):
    """Types of hiring signals"""
    EXECUTIVE_HIRE = "executive_hire"
    EXECUTIVE_DEPARTURE = "executive_departure"
    SCIENTIST_HIRE = "scientist_hire"
    SCIENTIST_DEPARTURE = "scientist_departure"
    MASS_HIRING = "mass_hiring"
    HIRING_FREEZE = "hiring_freeze"
    LAYOFF = "layoff_announced"
    JOB_POSTING_SURGE = "job_posting_surge"
    C_SUITE_TURNOVER = "c_suite_turnover"


class SignalInterpretation(Enum):
    """Hiring signal interpretation"""
    PREPARING_ACQUISITION = "preparing_for_acquisition"
    GROWTH_MODE = "growth_mode"
    RESTRUCTURING = "restructuring"
    FINANCIAL_DISTRESS = "financial_distress"
    STRATEGIC_PIVOT = "strategic_pivot"
    NORMAL_TURNOVER = "normal_turnover"
    EXPANSION = "expansion"


@dataclass
class HiringSignal(Signal):
    """
    Hiring signal from insider-hiring-signals
    """
    # Signal specifics
    hiring_signal_type: HiringSignalType
    interpretation: SignalInterpretation

    # Role info
    role_title: str
    role_category: str  # c_suite, vp, director, etc.
    department: Optional[str]

    # Person info
    person_name: Optional[str]
    previous_company: Optional[str]
    previous_role: Optional[str]
    destination_company: Optional[str]

    # Details
    effective_date: Optional[date]
    location: Optional[str]
    expertise_areas: List[str]
```

---

## Scoring Models

### M&A Score

```python
@dataclass
class MAScore:
    """
    M&A probability score for a company
    """
    company_id: str
    score_date: date

    # Composite score
    ma_score: Decimal  # 0-100 weighted composite
    tier: int  # 1, 2, or 3
    confidence: Decimal  # 0-1

    # Component scores
    clinical_score: Decimal  # 0-100
    patent_score: Decimal
    insider_score: Decimal
    financial_score: Decimal

    # Component weights used
    clinical_weight: Decimal  # Default 0.30
    patent_weight: Decimal  # Default 0.25
    insider_weight: Decimal  # Default 0.25
    financial_weight: Decimal  # Default 0.20

    # Signals considered
    signal_count: int
    signals_30d: int

    # Change tracking
    score_change_1d: Optional[Decimal]
    score_change_7d: Optional[Decimal]
    score_change_30d: Optional[Decimal]

    @classmethod
    def calculate(
        cls,
        company_id: str,
        clinical: Decimal,
        patent: Decimal,
        insider: Decimal,
        financial: Decimal,
        weights: Optional[Dict[str, Decimal]] = None
    ) -> 'MAScore':
        """
        Calculate weighted M&A score

        Default weights:
        - Clinical: 30% (pipeline value is key M&A driver)
        - Patent: 25% (patent cliff creates urgency)
        - Insider: 25% (insider activity signals intent)
        - Financial: 20% (financial pressure drives deals)
        """
        w = weights or {
            'clinical': Decimal('0.30'),
            'patent': Decimal('0.25'),
            'insider': Decimal('0.25'),
            'financial': Decimal('0.20')
        }

        composite = (
            clinical * w['clinical'] +
            patent * w['patent'] +
            insider * w['insider'] +
            financial * w['financial']
        )

        # Determine tier
        if composite >= 80:
            tier = 1
        elif composite >= 60:
            tier = 2
        else:
            tier = 3

        # Calculate confidence based on signal density
        # Higher signal count = higher confidence
        # This is a placeholder - actual implementation varies
        confidence = min(Decimal('1.0'), Decimal('0.5') + Decimal('0.05') * signal_count)

        return cls(
            company_id=company_id,
            score_date=date.today(),
            ma_score=composite,
            tier=tier,
            confidence=confidence,
            clinical_score=clinical,
            patent_score=patent,
            insider_score=insider,
            financial_score=financial,
            clinical_weight=w['clinical'],
            patent_weight=w['patent'],
            insider_weight=w['insider'],
            financial_weight=w['financial'],
            signal_count=0,  # Set by caller
            signals_30d=0
        )
```

### Match Score

```python
@dataclass
class MatchScore:
    """
    Acquirer-target match score
    """
    target_id: str
    acquirer_id: str
    evaluation_date: date

    # Composite score
    match_score: Decimal  # 0-100

    # Component scores
    therapeutic_fit: Decimal  # 0-100
    technology_fit: Decimal
    financial_fit: Decimal
    historical_pattern: Decimal

    # Component weights
    therapeutic_weight: Decimal  # Default 0.35
    technology_weight: Decimal  # Default 0.20
    financial_weight: Decimal  # Default 0.25
    historical_weight: Decimal  # Default 0.20

    @classmethod
    def calculate(
        cls,
        target_id: str,
        acquirer_id: str,
        therapeutic: Decimal,
        technology: Decimal,
        financial: Decimal,
        historical: Decimal,
        weights: Optional[Dict[str, Decimal]] = None
    ) -> 'MatchScore':
        """
        Calculate weighted match score

        Default weights:
        - Therapeutic: 35% (strategic fit is primary)
        - Financial: 25% (deal must be financeable)
        - Technology: 20% (platform alignment)
        - Historical: 20% (acquirer's track record)
        """
        w = weights or {
            'therapeutic': Decimal('0.35'),
            'technology': Decimal('0.20'),
            'financial': Decimal('0.25'),
            'historical': Decimal('0.20')
        }

        composite = (
            therapeutic * w['therapeutic'] +
            technology * w['technology'] +
            financial * w['financial'] +
            historical * w['historical']
        )

        return cls(
            target_id=target_id,
            acquirer_id=acquirer_id,
            evaluation_date=date.today(),
            match_score=composite,
            therapeutic_fit=therapeutic,
            technology_fit=technology,
            financial_fit=financial,
            historical_pattern=historical,
            therapeutic_weight=w['therapeutic'],
            technology_weight=w['technology'],
            financial_weight=w['financial'],
            historical_weight=w['historical']
        )
```

---

## Database Schema

### PostgreSQL Tables

```sql
-- Companies table
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) UNIQUE,
    name            VARCHAR(500) NOT NULL,
    cik             VARCHAR(20),
    description     TEXT,

    -- Classification
    sector          VARCHAR(100),
    therapeutic_areas TEXT[],
    technology_platforms TEXT[],
    headquarters    VARCHAR(200),
    employees       INTEGER,
    founded         INTEGER,

    -- Financials
    market_cap      DECIMAL(15,2),
    enterprise_value DECIMAL(15,2),
    stock_price     DECIMAL(10,4),
    cash_position   DECIMAL(15,2),
    burn_rate       DECIMAL(15,2),
    runway_months   INTEGER,
    revenue_ttm     DECIMAL(15,2),
    debt            DECIMAL(15,2),

    -- M&A scoring
    ma_score        DECIMAL(5,2),
    ma_tier         INTEGER,
    confidence      DECIMAL(5,4),
    recommendation  VARCHAR(50),

    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version         INTEGER DEFAULT 1
);

CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_ma_score ON companies(ma_score DESC);
CREATE INDEX idx_companies_tier ON companies(ma_tier);

-- Acquirers table
CREATE TABLE acquirers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) UNIQUE,
    name            VARCHAR(500) NOT NULL,

    -- Financials
    market_cap      DECIMAL(15,2),
    cash_position   DECIMAL(15,2),
    debt_capacity   DECIMAL(15,2),

    -- Profile
    focus_areas     TEXT[],
    strategic_priorities TEXT[],
    pipeline_gaps   TEXT[],
    technology_interests TEXT[],

    -- Historical
    deals_5y        INTEGER DEFAULT 0,
    avg_deal_size   DECIMAL(15,2),
    preferred_stages TEXT[],
    preferred_therapeutics TEXT[],

    -- Status
    active          BOOLEAN DEFAULT TRUE,

    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M&A candidates table
CREATE TABLE ma_candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID REFERENCES companies(id),

    -- Assessment
    ma_score        DECIMAL(5,2) NOT NULL,
    tier            INTEGER NOT NULL,
    confidence      DECIMAL(5,4),
    acquisition_probability VARCHAR(20),
    target_type     VARCHAR(50),
    recommendation  VARCHAR(50),

    -- Components
    clinical_score  DECIMAL(5,2),
    patent_score    DECIMAL(5,2),
    insider_score   DECIMAL(5,2),
    financial_score DECIMAL(5,2),

    -- Analysis
    primary_drivers TEXT[],
    risk_factors    TEXT[],
    key_signals     TEXT[],
    valuation_low   DECIMAL(15,2),
    valuation_high  DECIMAL(15,2),
    valuation_basis TEXT,

    -- Timeline
    earliest_date   DATE,
    likely_date     DATE,
    latest_date     DATE,

    -- Signals
    contributing_event_ids TEXT[],

    -- Metadata
    evaluation_date DATE DEFAULT CURRENT_DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id)
);

CREATE INDEX idx_candidates_tier ON ma_candidates(tier);
CREATE INDEX idx_candidates_score ON ma_candidates(ma_score DESC);

-- Acquirer matches table
CREATE TABLE acquirer_matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id       UUID REFERENCES companies(id),
    acquirer_id     UUID REFERENCES acquirers(id),

    -- Scoring
    match_score     DECIMAL(5,2) NOT NULL,
    therapeutic_fit DECIMAL(5,2),
    technology_fit  DECIMAL(5,2),
    financial_fit   DECIMAL(5,2),
    historical_fit  DECIMAL(5,2),

    -- Analysis
    strategic_rationale VARCHAR(100),
    supporting_factors TEXT[],
    overlapping_areas TEXT[],
    gap_fill_potential TEXT[],
    synergies       JSONB,
    risks           JSONB,

    -- Probability
    probability     DECIMAL(5,2),
    confidence      DECIMAL(5,4),
    financing_feasibility VARCHAR(50),

    -- Timeline
    earliest_announcement DATE,
    likely_announcement DATE,
    latest_announcement DATE,

    -- Metadata
    evaluation_date DATE DEFAULT CURRENT_DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(target_id, acquirer_id)
);

CREATE INDEX idx_matches_target ON acquirer_matches(target_id);
CREATE INDEX idx_matches_acquirer ON acquirer_matches(acquirer_id);
CREATE INDEX idx_matches_score ON acquirer_matches(match_score DESC);

-- Reports table
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type     VARCHAR(50) NOT NULL,
    title           VARCHAR(500) NOT NULL,

    -- Period
    period_start    DATE,
    period_end      DATE,

    -- Content
    summary_stats   JSONB,
    featured_candidates JSONB,
    featured_matches JSONB,

    -- Files
    formats         TEXT[],
    file_locations  JSONB,

    -- Distribution
    distribution_list JSONB,
    delivered       BOOLEAN DEFAULT FALSE,
    delivered_at    TIMESTAMP,

    -- Metadata
    generated_at    TIMESTAMP NOT NULL,
    generation_duration_ms INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_date ON reports(generated_at DESC);
```

### TimescaleDB Tables

```sql
-- Signals time-series
CREATE TABLE signals (
    time            TIMESTAMPTZ NOT NULL,
    company_id      UUID NOT NULL,
    signal_id       UUID NOT NULL,
    signal_source   VARCHAR(50) NOT NULL,
    signal_type     VARCHAR(100) NOT NULL,
    impact_score    DECIMAL(5,2),
    direction       VARCHAR(20),
    description     TEXT,
    payload         JSONB,
    event_id        UUID
);

SELECT create_hypertable('signals', 'time');

CREATE INDEX idx_signals_company ON signals (company_id, time DESC);
CREATE INDEX idx_signals_source ON signals (signal_source, time DESC);
CREATE INDEX idx_signals_type ON signals (signal_type, time DESC);

-- Score history time-series
CREATE TABLE score_history (
    time            TIMESTAMPTZ NOT NULL,
    company_id      UUID NOT NULL,
    ma_score        DECIMAL(5,2),
    tier            INTEGER,
    confidence      DECIMAL(5,4),
    clinical_score  DECIMAL(5,2),
    patent_score    DECIMAL(5,2),
    insider_score   DECIMAL(5,2),
    financial_score DECIMAL(5,2),
    signal_count    INTEGER
);

SELECT create_hypertable('score_history', 'time');

CREATE INDEX idx_score_history_company ON score_history (company_id, time DESC);

-- Continuous aggregates for dashboards
CREATE MATERIALIZED VIEW daily_score_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    company_id,
    AVG(ma_score) as avg_score,
    MAX(ma_score) as max_score,
    MIN(ma_score) as min_score,
    SUM(signal_count) as total_signals
FROM score_history
GROUP BY day, company_id;
```

---

## Event Schemas

For detailed event schema definitions, see [specs/events/event-schemas.md](events/event-schemas.md).

---

## Scoring Algorithm Reference

For detailed scoring algorithm specifications, see [specs/scoring-engine/ma-scoring.md](scoring-engine/ma-scoring.md).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-30 | Initial data model specification |

