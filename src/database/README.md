# Database Layer

This directory contains the complete database layer implementation for the biotech M&A predictor system.

## Overview

The database layer provides:
- Async SQLAlchemy ORM models
- Connection pooling and session management
- Repository pattern for data access
- Alembic migrations for schema management
- Optimized indexes and queries

## Structure

```
database/
├── __init__.py              # Package exports
├── connection.py            # Async connection management
├── tables.py                # SQLAlchemy ORM table definitions
├── repositories.py          # Data access layer (repositories)
├── migrations/              # Alembic migration configuration
│   ├── env.py              # Alembic environment setup
│   ├── script.py.mako      # Migration template
│   └── versions/           # Migration scripts
│       └── 001_initial_schema.py
└── README.md               # This file
```

## Tables

### Core Tables

1. **companies** - Core company data
   - Ticker, name, financial metrics
   - Therapeutic areas, operational data
   - Soft delete support
   - Indexes: ticker, market_cap, cash_constrained, therapeutic_areas

2. **drug_candidates** - Pipeline assets
   - Drug name, phase, indication, mechanism
   - Patent and regulatory status
   - Market potential estimates
   - Indexes: company_id + phase, therapeutic_area

3. **signals** - Signal events (polymorphic)
   - Signal type, event date, severity
   - Title, description, source
   - Signal-specific data (JSONB)
   - M&A impact scoring
   - Indexes: company + type, company + date, event_date, severity

4. **ma_scores** - Historical M&A scores
   - Total score and component breakdowns
   - Percentile ranking
   - Score changes (30d, 90d)
   - Key drivers and risk factors
   - Indexes: company + date, total_score, score_date
   - Unique constraint: company_id + score_date

5. **acquirer_matches** - Target-acquirer pairings
   - Strategic fit scoring
   - Synergy rationale
   - Valuation estimates
   - Match ranking
   - Indexes: target, acquirer, fit_score, top_match

### Supporting Tables

6. **reports** - Generated report metadata
   - Report type, date, period
   - S3/local storage references
   - Distribution tracking
   - Soft delete support

7. **alerts** - Alert configurations
   - Alert type and conditions
   - Company/signal filters
   - Notification settings
   - Trigger tracking
   - Soft delete support

8. **webhooks** - Registered webhooks
   - URL, event subscriptions
   - Delivery tracking
   - Retry policies
   - Soft delete support

9. **clients** - API clients
   - Client credentials
   - Access control
   - Rate limiting
   - Watchlists and preferences
   - Soft delete support

## Usage

### Initialize Database

```python
from src.database import init_db, close_db

# Initialize connection pool
await init_db(pool_size=20, max_overflow=10)

# Later, close connections
await close_db()
```

### Using Repositories

```python
from src.database import get_db_session, CompanyRepository

async with get_db_session() as session:
    repo = CompanyRepository(session)

    # Create company
    company = await repo.create(
        ticker="ABCD",
        name="ABC Therapeutics",
        market_cap_usd=1500000000,
        cash_position_usd=250000000,
    )

    # Get company
    company = await repo.get_by_ticker("ABCD")

    # Search companies
    companies = await repo.search(
        therapeutic_areas=["oncology"],
        min_market_cap=1000000000,
    )

    # Update company
    await repo.update(
        company.id,
        cash_position_usd=300000000,
    )
```

### Signal Repository

```python
from src.database import SignalRepository
from datetime import datetime

async with get_db_session() as session:
    repo = SignalRepository(session)

    # Create signal
    signal = await repo.create(
        company_id=company.id,
        signal_type="sec_filing",
        event_date=datetime.utcnow(),
        title="8-K Filing: Material Agreement",
        severity="high",
        signal_data={
            "filing_type": "8-K",
            "url": "https://...",
        },
    )

    # Get signals for company
    signals = await repo.get_by_company(
        company.id,
        signal_types=["sec_filing", "fda_approval"],
        start_date=datetime(2025, 1, 1),
    )

    # Get signal counts
    counts = await repo.get_count_by_type(company_id=company.id)
```

### Score Repository

```python
from src.database import ScoreRepository

async with get_db_session() as session:
    repo = ScoreRepository(session)

    # Create score
    score = await repo.create(
        company_id=company.id,
        total_score=85.5,
        pipeline_score=90.0,
        financial_score=75.0,
        key_drivers=["Late-stage pipeline", "Cash runway < 12mo"],
    )

    # Get latest score
    latest = await repo.get_latest_by_company(company.id)

    # Get score history
    history = await repo.get_history(company.id, days=90)

    # Get top scores
    top_companies = await repo.get_top_scores(limit=50)

    # Update percentile ranks
    await repo.update_percentile_ranks()
```

## Migrations

### Running Migrations

```bash
# Initialize Alembic (already done)
alembic init src/database/migrations

# Create new migration
alembic revision --autogenerate -m "add new column"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

### Migration Best Practices

1. Always review autogenerated migrations
2. Test migrations on development database first
3. Include both upgrade and downgrade paths
4. Use transactions for data migrations
5. Add indexes in separate migrations for large tables

## Connection Pooling

The database manager uses QueuePool with these defaults:
- **pool_size**: 20 connections
- **max_overflow**: 10 additional connections
- **pool_timeout**: 30 seconds
- **pool_recycle**: 3600 seconds (1 hour)
- **pool_pre_ping**: Enabled (verifies connections)

## Performance Optimizations

### Indexes

All tables include strategic indexes for common query patterns:
- Primary lookups (ticker, api_key)
- Foreign key relationships
- Date range queries (event_date, score_date)
- Status filters (is_active, deleted_at)
- JSONB columns (GIN indexes)

### Query Optimization

Repositories include:
- Eager loading with `selectinload()` for relationships
- Pagination support
- Filtered queries with compound indexes
- Aggregate queries for statistics

### Soft Deletes

Tables support soft deletes via `deleted_at` timestamp:
- Preserves historical data
- Allows undelete operations
- Filtered automatically in queries

## Health Checks

```python
from src.database import health_check

# Check database connectivity
is_healthy = await health_check()
```

## Environment Variables

Required configuration in `.env`:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=biotech_ma
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

## Testing

Example test setup:

```python
import pytest
from src.database import init_db, close_db, get_db_session

@pytest.fixture(scope="session")
async def db():
    await init_db(echo=True)
    yield
    await close_db()

@pytest.fixture
async def session():
    async with get_db_session() as session:
        yield session
        await session.rollback()
```

## Data Model Relationships

```
Company
  ├── DrugCandidates (1:N)
  ├── Signals (1:N)
  ├── MAScores (1:N)
  └── AcquirerMatches (1:N as target)

Signal
  └── Company (N:1)

MAScore
  └── Company (N:1)

AcquirerMatch
  └── TargetCompany (N:1)
```

## Common Patterns

### Bulk Insert

```python
async with get_db_session() as session:
    companies = [
        Company(ticker="ABC", name="ABC Inc.", ...),
        Company(ticker="XYZ", name="XYZ Corp.", ...),
    ]
    session.add_all(companies)
    await session.flush()
```

### Transactions

```python
async with get_db_session() as session:
    # All operations in same transaction
    company = await repo.create(...)
    signal = await signal_repo.create(company_id=company.id, ...)
    # Auto-commits if no exception
```

### Error Handling

```python
from sqlalchemy.exc import IntegrityError

try:
    async with get_db_session() as session:
        # Database operations
        pass
except IntegrityError as e:
    # Handle constraint violations
    logger.error(f"Database constraint violation: {e}")
```

## Troubleshooting

### Connection Pool Exhausted

Increase pool size or check for connection leaks:
```python
await init_db(pool_size=50, max_overflow=20)
```

### Slow Queries

Enable SQL echo to debug:
```python
await init_db(echo=True)
```

Check indexes and use EXPLAIN ANALYZE in PostgreSQL.

### Migration Conflicts

Reset Alembic if needed:
```bash
alembic stamp head
alembic revision --autogenerate -m "sync schema"
```
