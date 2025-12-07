# Database Layer - Quick Reference

## Overview

The database layer provides async PostgreSQL access using SQLAlchemy with a repository pattern for clean data access.

## File Structure

```
src/database/
├── __init__.py                 # Package exports
├── connection.py               # Async connection management
├── tables.py                   # SQLAlchemy ORM models
├── repositories.py             # Data access repositories
├── migrations/
│   ├── env.py                 # Alembic async config
│   ├── script.py.mako         # Migration template
│   └── versions/
│       └── 001_initial_schema.py
└── README.md

scripts/
└── db_utils.py                # Database CLI utilities

examples/
└── database_usage.py          # Usage examples

tests/
└── test_database.py           # Test suite
```

## Database Tables

### Core Tables

| Table | Purpose | Key Features |
|-------|---------|--------------|
| **companies** | Core company data | Soft delete, therapeutic areas JSONB index |
| **drug_candidates** | Pipeline assets | Phase tracking, regulatory designations |
| **signals** | Signal events | Polymorphic, JSONB data, severity levels |
| **ma_scores** | M&A prediction scores | Historical tracking, percentile ranks |
| **acquirer_matches** | Target-acquirer pairs | Strategic fit scoring |
| **reports** | Report metadata | S3 storage references |
| **alerts** | Alert configurations | Condition-based triggers |
| **webhooks** | Webhook endpoints | Event subscriptions, delivery tracking |
| **clients** | API clients | Access control, rate limiting |

## Quick Start

### Initialize Database

```python
from src.database import init_db, close_db

# Initialize
await init_db(pool_size=20)

# Later...
await close_db()
```

### Basic Usage

```python
from src.database import get_db_session, CompanyRepository

async with get_db_session() as session:
    repo = CompanyRepository(session)

    # Create
    company = await repo.create(
        ticker="BIOT",
        name="BioTech Inc.",
        market_cap_usd=1500000000,
        cash_position_usd=250000000,
    )

    # Read
    company = await repo.get_by_ticker("BIOT")

    # Update
    await repo.update(company.id, employee_count=150)

    # Search
    results = await repo.search(
        therapeutic_areas=["oncology"],
        min_market_cap=1000000000,
    )
```

## Repository API

### CompanyRepository

```python
# CRUD operations
company = await repo.create(ticker, name, market_cap_usd, cash_position_usd, **kwargs)
company = await repo.get_by_id(company_id, include_pipeline=False)
company = await repo.get_by_ticker(ticker, include_pipeline=False)
companies = await repo.get_all(skip=0, limit=100, include_pipeline=False)
company = await repo.update(company_id, **kwargs)
deleted = await repo.soft_delete(company_id)

# Search & filter
companies = await repo.search(
    name_pattern=None,
    therapeutic_areas=None,
    min_market_cap=None,
    max_market_cap=None,
    is_cash_constrained=None,
    skip=0,
    limit=100,
)

# Special queries
companies = await repo.get_cash_constrained(min_runway_quarters=4.0)
stats = await repo.get_statistics()
```

### SignalRepository

```python
# Create signal
signal = await repo.create(
    company_id,
    signal_type,
    event_date,
    title,
    severity="medium",
    **kwargs,
)

# Query signals
signals = await repo.get_by_company(
    company_id,
    signal_types=None,
    start_date=None,
    end_date=None,
    min_severity=None,
    limit=100,
)

signals = await repo.get_by_type(signal_type, start_date=None, limit=100)
signals = await repo.get_recent(days=7, severity=None, limit=100)

# Aggregations
counts = await repo.get_count_by_type(company_id=None, start_date=None)
```

### ScoreRepository

```python
# Create score
score = await repo.create(
    company_id,
    total_score,
    pipeline_score=0.0,
    patent_score=0.0,
    financial_score=0.0,
    insider_score=0.0,
    strategic_fit_score=0.0,
    regulatory_score=0.0,
    **kwargs,
)

# Query scores
score = await repo.get_latest_by_company(company_id)
history = await repo.get_history(company_id, days=90, limit=100)
top_scores = await repo.get_top_scores(limit=50, score_date=None)
scores = await repo.get_by_score_range(min_score, max_score=100.0, limit=100)

# Utilities
count = await repo.update_percentile_ranks(score_date=None)
```

### ReportRepository

```python
# Create report
report = await repo.create(
    report_type,
    title,
    report_date,
    format="pdf",
    **kwargs,
)

# Query reports
report = await repo.get_by_id(report_id)
reports = await repo.get_by_type(report_type, start_date=None, end_date=None, limit=50)
reports = await repo.get_recent(days=30, limit=50)

# Update status
report = await repo.update_delivery_status(report_id, status, sent_at=None)
```

### AlertRepository

```python
# Alerts
alert = await repo.create_alert(name, alert_type, condition, **kwargs)
alerts = await repo.get_active_alerts(alert_type=None)
alert = await repo.update_alert_trigger(alert_id)

# Webhooks
webhook = await repo.create_webhook(name, url, event_types, **kwargs)
webhooks = await repo.get_active_webhooks(event_type=None)
webhook = await repo.update_webhook_status(webhook_id, success, error=None)
```

## Database CLI Utilities

```bash
# Check database health
python scripts/db_utils.py check

# Create all tables
python scripts/db_utils.py create-all

# Drop all tables (with confirmation)
python scripts/db_utils.py drop-all

# Reset database
python scripts/db_utils.py reset

# Show database info and table counts
python scripts/db_utils.py info

# Execute SQL query
python scripts/db_utils.py query "SELECT COUNT(*) FROM companies"

# Vacuum analyze all tables
python scripts/db_utils.py vacuum

# Show all indexes
python scripts/db_utils.py indexes

# Show table statistics
python scripts/db_utils.py stats
python scripts/db_utils.py stats --table companies

# Show active connections
python scripts/db_utils.py connections
```

## Alembic Migrations

```bash
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

# Show SQL for migration (without executing)
alembic upgrade head --sql
```

## Common Patterns

### Transaction Management

```python
# Automatic transaction management
async with get_db_session() as session:
    # All operations in same transaction
    company = await company_repo.create(...)
    signal = await signal_repo.create(company_id=company.id, ...)
    # Auto-commits on success, rolls back on exception
```

### Bulk Operations

```python
async with get_db_session() as session:
    companies = [
        Company(ticker="ABC", name="ABC Inc.", ...),
        Company(ticker="XYZ", name="XYZ Corp.", ...),
    ]
    session.add_all(companies)
    await session.flush()
```

### Error Handling

```python
from sqlalchemy.exc import IntegrityError

try:
    async with get_db_session() as session:
        repo = CompanyRepository(session)
        company = await repo.create(...)
except IntegrityError as e:
    logger.error(f"Constraint violation: {e}")
    # Handle duplicate ticker, etc.
```

### Eager Loading

```python
# Load company with all drug candidates
company = await repo.get_by_ticker("BIOT", include_pipeline=True)

# Access related data without additional queries
for drug in company.drug_candidates:
    print(drug.name, drug.phase)
```

## Index Optimization

All tables include strategic indexes:

- **companies**: ticker (unique), market_cap, cash_constrained, therapeutic_areas (GIN)
- **drug_candidates**: company_id + phase, therapeutic_area
- **signals**: company_id + signal_type, company_id + event_date, severity, signal_data (GIN)
- **ma_scores**: company_id + score_date (unique), total_score
- **acquirer_matches**: target_company_id, acquirer_ticker, strategic_fit_score
- **reports**: report_type, report_date
- **alerts**: alert_type, is_active
- **webhooks**: is_active
- **clients**: api_key (unique), is_active

## Configuration

Environment variables in `config/.env`:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=biotech_ma
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

Connection pool settings:
- Pool size: 20 connections
- Max overflow: 10 connections
- Pool timeout: 30 seconds
- Pool recycle: 3600 seconds
- Pre-ping: Enabled

## Testing

See `/Users/waiyang/Desktop/repo/biotech-ma-predictor/tests/test_database.py` for comprehensive test examples.

```bash
# Run database tests
pytest tests/test_database.py -v

# Run with coverage
pytest tests/test_database.py --cov=src.database
```

## Examples

See `/Users/waiyang/Desktop/repo/biotech-ma-predictor/examples/database_usage.py` for complete working examples of all repository operations.

```bash
# Run examples
python examples/database_usage.py
```

## Performance Tips

1. **Use indexes** - All common query patterns are indexed
2. **Batch operations** - Use bulk inserts for multiple records
3. **Eager loading** - Use `include_pipeline=True` to avoid N+1 queries
4. **Connection pooling** - Reuse connections from the pool
5. **Soft deletes** - Preserve data while excluding from queries
6. **JSONB indexes** - GIN indexes on therapeutic_areas and signal_data

## Troubleshooting

### Connection pool exhausted
```python
await init_db(pool_size=50, max_overflow=20)
```

### Slow queries
```python
# Enable SQL logging
await init_db(echo=True)

# Then check PostgreSQL query plan
# EXPLAIN ANALYZE SELECT ...
```

### Migration conflicts
```bash
# Reset to current schema
alembic stamp head

# Create sync migration
alembic revision --autogenerate -m "sync schema"
```

## Additional Resources

- Full documentation: `/Users/waiyang/Desktop/repo/biotech-ma-predictor/src/database/README.md`
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- Alembic docs: https://alembic.sqlalchemy.org/
- asyncpg docs: https://magicstack.github.io/asyncpg/
