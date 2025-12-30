# Biotech M&A Predictor - System Architecture

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Active

---

## Overview

The Biotech M&A Predictor is a real-time intelligence platform that aggregates signals from multiple upstream systems, calculates M&A probability scores, matches targets with acquirers, and delivers actionable reports to clients.

---

## System Architecture Diagram

```
                         EXTERNAL DATA SOURCES
    ┌───────────────────────────────────────────────────────────┐
    │  ClinicalTrials.gov  │  USPTO/Orange Book  │  SEC EDGAR  │
    │  FDA APIs            │  PACER              │  LinkedIn   │
    └───────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────┐
    │                    SIGNAL PRODUCERS                        │
    │ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
    │ │ clinical-trial- │ │ patent-ip-      │ │ insider-      │ │
    │ │ signals         │ │ intelligence    │ │ hiring-signals│ │
    │ └────────┬────────┘ └────────┬────────┘ └───────┬───────┘ │
    └──────────┼───────────────────┼──────────────────┼─────────┘
               │                   │                  │
               ▼                   ▼                  ▼
    ┌───────────────────────────────────────────────────────────┐
    │              EVENT BUS (RabbitMQ / EventBridge)            │
    │  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
    │  │ clinical.  │  │ patent.    │  │ insider.   │           │
    │  │ signals    │  │ signals    │  │ signals    │           │
    │  └────────────┘  └────────────┘  └────────────┘           │
    └───────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────┐
    │               BIOTECH M&A PREDICTOR CORE                   │
    │                                                            │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │                 SIGNAL AGGREGATOR                    │  │
    │  │  • Event validation & normalization                  │  │
    │  │  • Company entity resolution                         │  │
    │  │  • Signal deduplication                              │  │
    │  │  • Time-series storage                               │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                          │                                 │
    │                          ▼                                 │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │                 SCORING ENGINE                       │  │
    │  │  • Clinical component scoring                        │  │
    │  │  • Patent risk scoring                               │  │
    │  │  • Insider activity scoring                          │  │
    │  │  • Financial health scoring                          │  │
    │  │  • Composite M&A probability score                   │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                          │                                 │
    │                          ▼                                 │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │                ACQUIRER MATCHER                      │  │
    │  │  • Therapeutic fit analysis                          │  │
    │  │  • Technology platform alignment                     │  │
    │  │  • Financial feasibility                             │  │
    │  │  • Historical pattern matching                       │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                          │                                 │
    │                          ▼                                 │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │                REPORT GENERATOR                      │  │
    │  │  • Daily digest                                      │  │
    │  │  • Weekly watchlist                                  │  │
    │  │  • Deep dive reports                                 │  │
    │  │  • Alert reports                                     │  │
    │  └─────────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │   DATA STORES   │   │   OUTPUT LAYER   │   │   DASHBOARDS   │
    │                 │   │                  │   │                │
    │ • PostgreSQL    │   │ • REST API       │   │ • investment-  │
    │ • TimescaleDB   │   │ • Email          │   │   dashboard    │
    │ • Redis         │   │ • Slack          │   │                │
    │ • S3            │   │ • Webhooks       │   │                │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## Component Architecture

### 1. Signal Aggregator

The Signal Aggregator consumes events from upstream signal producers and normalizes them for downstream processing.

```python
# Signal Aggregator Architecture
class SignalAggregator:
    """
    Consumes signals from event bus, validates, and stores
    """

    def __init__(self):
        self.event_bus = EventBusClient()
        self.company_resolver = CompanyEntityResolver()
        self.signal_store = TimescaleDBClient()
        self.cache = RedisClient()

    async def consume_signals(self):
        """Main event loop for signal consumption"""
        async for event in self.event_bus.subscribe([
            'clinical.signals.*',
            'patent.signals.*',
            'insider.signals.*',
            'hiring.signals.*'
        ]):
            await self.process_event(event)

    async def process_event(self, event: Event):
        """Process a single event"""
        # Validate against schema
        validated = self.validate_event(event)

        # Resolve company entity
        company_id = await self.company_resolver.resolve(
            ticker=validated.ticker_symbol,
            company_name=validated.company_name
        )

        # Store signal
        await self.signal_store.insert_signal(
            company_id=company_id,
            signal_type=validated.signal_type,
            impact_score=validated.impact_score,
            payload=validated.payload,
            timestamp=validated.timestamp
        )

        # Invalidate cache
        await self.cache.invalidate(f"company:{company_id}")

        # Trigger score recalculation
        await self.event_bus.publish(
            'ma.score.recalculate',
            {'company_id': company_id}
        )
```

### 2. Company Entity Resolver

Handles entity resolution to ensure signals are correctly attributed to companies.

```python
class CompanyEntityResolver:
    """
    Resolves company entities across different data sources
    """

    def __init__(self):
        self.db = PostgreSQLClient()
        self.cache = RedisClient()

    async def resolve(
        self,
        ticker: Optional[str] = None,
        company_name: Optional[str] = None,
        cik: Optional[str] = None
    ) -> str:
        """
        Resolve to canonical company ID

        Resolution priority:
        1. Exact ticker match
        2. CIK match
        3. Fuzzy name match
        4. Create new entity
        """
        # Check cache first
        cache_key = self._make_cache_key(ticker, company_name, cik)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Try ticker match
        if ticker:
            company = await self.db.find_by_ticker(ticker)
            if company:
                await self.cache.set(cache_key, company.id)
                return company.id

        # Try CIK match
        if cik:
            company = await self.db.find_by_cik(cik)
            if company:
                await self.cache.set(cache_key, company.id)
                return company.id

        # Fuzzy name match
        if company_name:
            matches = await self.db.fuzzy_match_name(company_name)
            if matches and matches[0].score > 0.9:
                await self.cache.set(cache_key, matches[0].id)
                return matches[0].id

        # Create new entity
        new_company = await self.db.create_company(
            ticker=ticker,
            name=company_name,
            cik=cik
        )
        await self.cache.set(cache_key, new_company.id)
        return new_company.id
```

### 3. M&A Scoring Engine

The core scoring engine that calculates M&A probability scores.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        M&A SCORING ENGINE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐ │
│   │  CLINICAL   │   │   PATENT    │   │   INSIDER   │   │  FINANCIAL  │ │
│   │  COMPONENT  │   │  COMPONENT  │   │  COMPONENT  │   │  COMPONENT  │ │
│   │             │   │             │   │             │   │             │ │
│   │ Weight: 30% │   │ Weight: 25% │   │ Weight: 25% │   │ Weight: 20% │ │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘ │
│          │                 │                 │                 │        │
│          └─────────────────┼─────────────────┼─────────────────┘        │
│                            │                 │                          │
│                            ▼                 │                          │
│                 ┌──────────────────────┐     │                          │
│                 │  WEIGHTED COMBINER   │◄────┘                          │
│                 └──────────┬───────────┘                                │
│                            │                                            │
│                            ▼                                            │
│                 ┌──────────────────────┐                                │
│                 │  CONFIDENCE SCORER   │                                │
│                 └──────────┬───────────┘                                │
│                            │                                            │
│                            ▼                                            │
│                 ┌──────────────────────┐                                │
│                 │   TIER CLASSIFIER    │                                │
│                 │  Tier 1: >= 80       │                                │
│                 │  Tier 2: 60-79       │                                │
│                 │  Tier 3: 40-59       │                                │
│                 └──────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

See [specs/scoring-engine/ma-scoring.md](scoring-engine/ma-scoring.md) for detailed algorithm specification.

### 4. Acquirer Matcher

Matches M&A candidates with potential acquirers.

```python
class AcquirerMatcher:
    """
    Matches target companies with potential acquirers
    """

    MATCH_COMPONENTS = {
        'therapeutic_fit': 0.35,
        'technology_fit': 0.20,
        'financial_fit': 0.25,
        'historical_pattern': 0.20
    }

    async def find_matches(
        self,
        target: Company,
        top_n: int = 10
    ) -> List[AcquirerMatch]:
        """
        Find top N acquirer matches for a target company
        """
        # Get all potential acquirers
        acquirers = await self.db.get_active_acquirers()

        matches = []
        for acquirer in acquirers:
            # Calculate component scores
            therapeutic = self.calculate_therapeutic_fit(target, acquirer)
            technology = self.calculate_technology_fit(target, acquirer)
            financial = self.calculate_financial_fit(target, acquirer)
            historical = self.calculate_historical_pattern(target, acquirer)

            # Weighted combination
            match_score = (
                therapeutic * self.MATCH_COMPONENTS['therapeutic_fit'] +
                technology * self.MATCH_COMPONENTS['technology_fit'] +
                financial * self.MATCH_COMPONENTS['financial_fit'] +
                historical * self.MATCH_COMPONENTS['historical_pattern']
            )

            matches.append(AcquirerMatch(
                target=target,
                acquirer=acquirer,
                match_score=match_score,
                therapeutic_fit=therapeutic,
                technology_fit=technology,
                financial_fit=financial,
                historical_pattern=historical
            ))

        # Sort and return top N
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:top_n]

    def calculate_therapeutic_fit(
        self,
        target: Company,
        acquirer: Company
    ) -> float:
        """
        Calculate therapeutic area alignment score

        Factors:
        - Overlapping therapeutic areas (synergy potential)
        - Complementary areas (portfolio expansion)
        - Acquirer's stated strategic priorities
        - Pipeline gap fill potential
        """
        overlap_score = self._calculate_overlap(
            target.therapeutic_areas,
            acquirer.focus_areas
        )

        gap_fill_score = self._calculate_gap_fill(
            target.pipeline,
            acquirer.pipeline_gaps
        )

        strategic_fit = self._check_strategic_priorities(
            target.therapeutic_areas,
            acquirer.strategic_priorities
        )

        return (overlap_score * 0.3 + gap_fill_score * 0.4 + strategic_fit * 0.3)
```

### 5. Report Generator

Generates and delivers reports to clients.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       REPORT GENERATION PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐                                                      │
│  │   SCHEDULER    │  Cron triggers: daily 6AM, weekly Monday 8AM        │
│  │   (Airflow)    │  Event triggers: score changes, new Tier 1           │
│  └───────┬────────┘                                                      │
│          │                                                               │
│          ▼                                                               │
│  ┌────────────────┐                                                      │
│  │     DATA       │  Aggregate from PostgreSQL, TimescaleDB, S3         │
│  │  AGGREGATOR    │  Apply client filters and preferences               │
│  └───────┬────────┘                                                      │
│          │                                                               │
│          ▼                                                               │
│  ┌────────────────┐                                                      │
│  │    TEMPLATE    │  Jinja2 templates                                   │
│  │    ENGINE      │  Dynamic chart generation (Plotly/Matplotlib)       │
│  └───────┬────────┘                                                      │
│          │                                                               │
│          ▼                                                               │
│  ┌────────────────┐                                                      │
│  │    RENDERER    │  HTML → PDF (WeasyPrint)                            │
│  │                │  JSON data export                                   │
│  └───────┬────────┘                                                      │
│          │                                                               │
│          ▼                                                               │
│  ┌────────────────┐                                                      │
│  │   DELIVERY     │  Email (SendGrid)                                   │
│  │   SERVICE      │  Portal upload                                      │
│  │                │  Webhook callbacks                                  │
│  │                │  Slack notifications                                │
│  └────────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

See [specs/reports/report-generation.md](reports/report-generation.md) for detailed report specifications.

---

## Data Flow Architecture

### Signal Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       SIGNAL PROCESSING PIPELINE                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. INGEST          2. VALIDATE        3. ENRICH         4. STORE        │
│  ┌─────────┐        ┌─────────┐        ┌─────────┐       ┌─────────┐     │
│  │ Event   │───────▶│ Schema  │───────▶│ Entity  │──────▶│Timescale│     │
│  │ Bus     │        │ Valid.  │        │ Resolve │       │ DB      │     │
│  └─────────┘        └─────────┘        └─────────┘       └─────────┘     │
│                          │                  │                 │          │
│                          │ Invalid          │                 │          │
│                          ▼                  │                 │          │
│                     ┌─────────┐             │                 │          │
│                     │  DLQ    │             │                 │          │
│                     └─────────┘             │                 │          │
│                                             │                 │          │
│  5. SCORE           6. MATCH            7. ALERT         8. NOTIFY       │
│  ┌─────────┐        ┌─────────┐        ┌─────────┐       ┌─────────┐     │
│  │ Scoring │◄───────│ Company │◄───────│ Check   │──────▶│  Slack  │     │
│  │ Engine  │        │ Profile │        │ Thresh. │       │  Email  │     │
│  └─────────┘        └─────────┘        └─────────┘       └─────────┘     │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────┐        ┌─────────┐                                          │
│  │ Acquirer│───────▶│ Match   │                                          │
│  │ Matcher │        │ Events  │                                          │
│  └─────────┘        └─────────┘                                          │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Consistency Model

```python
class DataConsistencyManager:
    """
    Ensures data consistency across stores
    """

    async def ensure_consistency(self, company_id: str):
        """
        Ensure all data stores are consistent for a company
        """
        # Get source of truth from PostgreSQL
        company = await self.postgres.get_company(company_id)

        # Verify TimescaleDB signal counts
        signal_count = await self.timescale.count_signals(company_id)
        if company.signal_count != signal_count:
            await self.reconcile_signal_counts(company_id)

        # Verify Redis cache
        cached_score = await self.redis.get(f"score:{company_id}")
        if cached_score != company.ma_score:
            await self.redis.set(f"score:{company_id}", company.ma_score)

        # Verify search index
        indexed = await self.elasticsearch.get(company_id)
        if indexed.version != company.version:
            await self.elasticsearch.index(company)
```

---

## Database Architecture

### PostgreSQL Schema

```sql
-- Core tables in PostgreSQL

-- Companies table (master record)
CREATE TABLE companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) UNIQUE,
    name            VARCHAR(500) NOT NULL,
    cik             VARCHAR(20),

    -- Classification
    sector          VARCHAR(100),
    therapeutic_areas TEXT[],
    technology_platforms TEXT[],

    -- Current metrics
    market_cap      DECIMAL(15,2),
    cash_position   DECIMAL(15,2),
    burn_rate       DECIMAL(15,2),
    runway_months   INTEGER,

    -- M&A scoring
    ma_score        DECIMAL(5,2),
    ma_tier         INTEGER,
    confidence      DECIMAL(5,2),

    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version         INTEGER DEFAULT 1
);

-- Acquirers table
CREATE TABLE acquirers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(10) UNIQUE,
    name            VARCHAR(500) NOT NULL,

    -- Profile
    market_cap      DECIMAL(15,2),
    cash_position   DECIMAL(15,2),

    -- Acquisition strategy
    focus_areas     TEXT[],
    strategic_priorities TEXT[],
    pipeline_gaps   TEXT[],

    -- Historical activity
    deals_5y        INTEGER,
    avg_deal_size   DECIMAL(15,2),
    preferred_stages TEXT[],

    -- Metadata
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- M&A candidates (current watchlist)
CREATE TABLE ma_candidates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID REFERENCES companies(id),

    -- Current assessment
    ma_score        DECIMAL(5,2) NOT NULL,
    confidence      DECIMAL(5,2),
    tier            INTEGER,
    recommendation  VARCHAR(50),

    -- Score components
    clinical_score  DECIMAL(5,2),
    patent_score    DECIMAL(5,2),
    insider_score   DECIMAL(5,2),
    financial_score DECIMAL(5,2),

    -- Analysis
    primary_drivers TEXT[],
    risk_factors    TEXT[],
    valuation_low   DECIMAL(15,2),
    valuation_high  DECIMAL(15,2),

    -- Timeline
    earliest_date   DATE,
    likely_date     DATE,
    latest_date     DATE,

    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(company_id)
);

-- Acquirer-target matches
CREATE TABLE acquirer_matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_id       UUID REFERENCES companies(id),
    acquirer_id     UUID REFERENCES acquirers(id),

    -- Match scoring
    match_score     DECIMAL(5,2) NOT NULL,
    therapeutic_fit DECIMAL(5,2),
    technology_fit  DECIMAL(5,2),
    financial_fit   DECIMAL(5,2),
    historical_fit  DECIMAL(5,2),

    -- Analysis
    strategic_rationale TEXT,
    synergies       JSONB,
    risks           JSONB,

    -- Probability
    probability     DECIMAL(5,2),
    confidence      DECIMAL(5,2),

    -- Metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(target_id, acquirer_id)
);
```

### TimescaleDB Schema (Time-Series)

```sql
-- Signals time-series in TimescaleDB

CREATE TABLE signals (
    time            TIMESTAMPTZ NOT NULL,
    company_id      UUID NOT NULL,
    signal_type     VARCHAR(100) NOT NULL,
    signal_source   VARCHAR(50) NOT NULL,  -- clinical, patent, insider, hiring
    impact_score    DECIMAL(5,2),
    payload         JSONB,
    event_id        UUID
);

SELECT create_hypertable('signals', 'time');

-- Create indexes
CREATE INDEX idx_signals_company ON signals (company_id, time DESC);
CREATE INDEX idx_signals_type ON signals (signal_type, time DESC);
CREATE INDEX idx_signals_source ON signals (signal_source, time DESC);

-- Score history time-series
CREATE TABLE score_history (
    time            TIMESTAMPTZ NOT NULL,
    company_id      UUID NOT NULL,
    ma_score        DECIMAL(5,2),
    clinical_score  DECIMAL(5,2),
    patent_score    DECIMAL(5,2),
    insider_score   DECIMAL(5,2),
    financial_score DECIMAL(5,2),
    tier            INTEGER,
    signal_count    INTEGER
);

SELECT create_hypertable('score_history', 'time');

CREATE INDEX idx_score_history_company ON score_history (company_id, time DESC);
```

See [specs/data-pipeline/architecture.md](data-pipeline/architecture.md) for detailed data pipeline architecture.

---

## Event Architecture

### Event Types

```
Event Hierarchy:
├── Signal Events (from upstream systems)
│   ├── ClinicalTrialSignalEvent
│   ├── PatentCliffEvent
│   ├── InsiderActivityEvent
│   └── HiringSignalEvent
│
├── M&A Events (generated by this system)
│   ├── MACandidateEvent
│   ├── AcquirerMatchEvent
│   └── ScoreChangeEvent
│
└── Report Events
    ├── ReportGeneratedEvent
    └── AlertSentEvent
```

### Event Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EVENT FLOW                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Signal Producers                                                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                           │
│  │ Clinical  │  │  Patent   │  │  Insider  │                           │
│  │ Signals   │  │ Signals   │  │  Signals  │                           │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                           │
│        │              │              │                                   │
│        ▼              ▼              ▼                                   │
│  ┌───────────────────────────────────────────┐                          │
│  │            Signal Aggregator               │                          │
│  │  • Validate & normalize                    │                          │
│  │  • Entity resolution                       │                          │
│  │  • Store in TimescaleDB                    │                          │
│  └─────────────────────┬─────────────────────┘                          │
│                        │                                                 │
│                        ▼ (company_id)                                    │
│  ┌───────────────────────────────────────────┐                          │
│  │             Scoring Engine                 │                          │
│  │  • Recalculate M&A score                  │                          │
│  │  • Update tier classification              │                          │
│  │  • Emit ScoreChangeEvent if significant   │                          │
│  └─────────────────────┬─────────────────────┘                          │
│                        │                                                 │
│          ┌─────────────┼─────────────┐                                   │
│          ▼             │             ▼                                   │
│  ┌──────────────┐      │     ┌──────────────┐                           │
│  │ MACandidateEvent    │     │ Acquirer     │                           │
│  │ (if Tier 1 or 2)    │     │ Matcher      │                           │
│  └──────────────┘      │     └──────┬───────┘                           │
│                        │            │                                    │
│                        │            ▼                                    │
│                        │     ┌──────────────┐                           │
│                        │     │AcquirerMatch │                           │
│                        │     │Event         │                           │
│                        │     └──────────────┘                           │
│                        │                                                 │
│                        ▼                                                 │
│  ┌───────────────────────────────────────────┐                          │
│  │           Report Generator                 │                          │
│  │  • Generate scheduled reports              │                          │
│  │  • Generate alert reports                  │                          │
│  │  • Emit ReportGeneratedEvent              │                          │
│  └───────────────────────────────────────────┘                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

See [specs/events/event-schemas.md](events/event-schemas.md) for detailed event schema specifications.

---

## Infrastructure

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  # Core application
  ma-predictor:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ma_predictor
      - TIMESCALE_URL=postgresql://user:pass@timescale:5432/signals
      - REDIS_URL=redis://redis:6379
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - postgres
      - timescale
      - redis
      - rabbitmq

  # Databases
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ma_predictor
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  timescale:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: signals
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - timescale_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"

  # Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Message queue
  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"

volumes:
  postgres_data:
  timescale_data:
```

### Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION INFRASTRUCTURE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  AWS Region: us-east-1                                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                           VPC                                    │    │
│  │                                                                  │    │
│  │  ┌─────────────────┐        ┌─────────────────┐                 │    │
│  │  │  Public Subnet  │        │  Public Subnet  │                 │    │
│  │  │  (us-east-1a)   │        │  (us-east-1b)   │                 │    │
│  │  │                 │        │                 │                 │    │
│  │  │  ┌───────────┐  │        │  ┌───────────┐  │                 │    │
│  │  │  │    ALB    │◄─┼────────┼──│    ALB    │  │                 │    │
│  │  │  └───────────┘  │        │  └───────────┘  │                 │    │
│  │  └────────┬────────┘        └────────┬────────┘                 │    │
│  │           │                          │                          │    │
│  │  ┌────────┴──────────────────────────┴────────┐                 │    │
│  │  │              Private Subnets                │                 │    │
│  │  │                                             │                 │    │
│  │  │  ┌─────────────┐      ┌─────────────┐      │                 │    │
│  │  │  │    ECS      │      │    ECS      │      │                 │    │
│  │  │  │  Fargate    │      │  Fargate    │      │                 │    │
│  │  │  │ (API/Core)  │      │ (Workers)   │      │                 │    │
│  │  │  └─────────────┘      └─────────────┘      │                 │    │
│  │  │                                             │                 │    │
│  │  │  ┌─────────────┐      ┌─────────────┐      │                 │    │
│  │  │  │    RDS      │      │ Elasticache │      │                 │    │
│  │  │  │ (PostgreSQL)│      │  (Redis)    │      │                 │    │
│  │  │  │ Multi-AZ    │      │             │      │                 │    │
│  │  │  └─────────────┘      └─────────────┘      │                 │    │
│  │  │                                             │                 │    │
│  │  │  ┌─────────────┐      ┌─────────────┐      │                 │    │
│  │  │  │ Timescale   │      │  Amazon MQ  │      │                 │    │
│  │  │  │ Cloud       │      │ (RabbitMQ)  │      │                 │    │
│  │  │  └─────────────┘      └─────────────┘      │                 │    │
│  │  └─────────────────────────────────────────────┘                 │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  External Services:                                                      │
│  • S3 (Report storage)                                                   │
│  • CloudWatch (Logging/Monitoring)                                       │
│  • Secrets Manager                                                       │
│  • EventBridge (Scheduling)                                              │
│  • SES/SendGrid (Email)                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Authentication & Authorization

```python
# API Authentication using API Keys and JWT

class AuthenticationMiddleware:
    """
    Multi-tier authentication:
    1. API Key for service-to-service
    2. JWT for user sessions
    3. OAuth2 for third-party integrations
    """

    async def authenticate(self, request: Request) -> AuthContext:
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            client = await self.validate_api_key(api_key)
            return AuthContext(client=client, method='api_key')

        # Check for JWT
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            user = await self.validate_jwt(token)
            return AuthContext(user=user, method='jwt')

        raise UnauthorizedException()
```

### Data Encryption

- **At Rest**: AES-256 encryption for all databases and S3
- **In Transit**: TLS 1.3 for all connections
- **Field-Level**: PII encrypted at application level

---

## Monitoring & Observability

### Metrics

```python
# Key metrics tracked

METRICS = {
    # Signal processing
    'signals_received_total': Counter,
    'signals_processed_total': Counter,
    'signal_processing_latency': Histogram,
    'signal_validation_errors': Counter,

    # Scoring
    'scores_calculated_total': Counter,
    'score_calculation_latency': Histogram,
    'tier_1_candidates_total': Gauge,

    # Matching
    'matches_generated_total': Counter,
    'match_calculation_latency': Histogram,

    # Reports
    'reports_generated_total': Counter,
    'report_generation_latency': Histogram,
    'reports_delivered_total': Counter,

    # API
    'api_requests_total': Counter,
    'api_request_latency': Histogram,
    'api_errors_total': Counter,
}
```

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Signal processing latency | > 10s | > 30s |
| Score calculation latency | > 5s | > 15s |
| API error rate | > 1% | > 5% |
| Signal backlog | > 1000 | > 5000 |
| Database connection pool | > 80% | > 95% |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-30 | Initial comprehensive architecture specification |

