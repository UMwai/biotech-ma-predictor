# Biotech M&A Predictor API

FastAPI-based REST API for the Biotech M&A Predictor system.

## Structure

```
src/api/
├── __init__.py              # Package initialization
├── app.py                   # Main FastAPI application
├── dependencies.py          # Dependency injection (DB, Redis, auth)
├── middleware.py            # Custom middleware (auth, rate limiting, logging)
├── README.md               # This file
└── routes/
    ├── __init__.py         # Routes package
    ├── companies.py        # Company endpoints
    ├── predictions.py      # M&A prediction endpoints
    ├── reports.py          # Report endpoints
    └── alerts.py           # Alert/webhook endpoints
```

## Features

### Main Application (`app.py`)
- FastAPI with lifespan management for startup/shutdown
- CORS configuration for frontend integration
- Custom OpenAPI documentation
- Health and readiness check endpoints
- All routers included with `/api/v1` prefix

### Dependencies (`dependencies.py`)
- **Database**: PostgreSQL with AsyncIO support via SQLAlchemy
- **Cache**: Redis for rate limiting and caching
- **Settings**: Centralized configuration management
- **Authentication**: API key verification
- **Pagination**: Helper classes for paginated responses
- Resource cleanup on shutdown

### Middleware (`middleware.py`)
- **Rate Limiting**: Token bucket algorithm with Redis
  - Anonymous: 100 requests/minute
  - Authenticated: 1000 requests/minute
  - X-RateLimit-* headers in responses
- **Request Logging**: Structured logging with request IDs
- **Authentication**: API key validation
- **Error Handling**: Global exception handlers

### Routes

#### Companies (`/api/v1/companies`)
- `GET /companies` - List companies with filtering/pagination
- `GET /companies/{ticker}` - Get company profile with M&A score
- `GET /companies/{ticker}/signals` - Get signal history
- `GET /companies/{ticker}/pipeline` - Get drug pipeline

#### Predictions (`/api/v1/predictions`)
- `GET /predictions/watchlist` - Current M&A watchlist (ranked)
- `GET /predictions/top` - Top N acquisition candidates
- `GET /predictions/{ticker}/acquirers` - Potential acquirers for target
- `GET /predictions/matches` - All target-acquirer pairings

#### Reports (`/api/v1/reports`)
- `GET /reports` - List reports with filtering
- `GET /reports/{id}` - Get report metadata
- `POST /reports/generate` - Generate on-demand report
- `GET /reports/daily-digest/latest` - Latest daily digest
- `GET /reports/weekly-watchlist/latest` - Latest weekly watchlist

#### Alerts (`/api/v1/alerts`)
- **Alert Rules**:
  - `GET /alerts/rules` - List alert rules
  - `POST /alerts/rules` - Create alert rule
  - `GET /alerts/rules/{id}` - Get alert rule
  - `PATCH /alerts/rules/{id}` - Update alert rule
  - `DELETE /alerts/rules/{id}` - Delete alert rule
- **Webhooks**:
  - `GET /alerts/webhooks` - List webhooks
  - `POST /alerts/webhooks` - Register webhook
  - `GET /alerts/webhooks/{id}` - Get webhook
  - `PATCH /alerts/webhooks/{id}` - Update webhook
  - `DELETE /alerts/webhooks/{id}` - Delete webhook
- **History**:
  - `GET /alerts/history` - Get alert history
  - `POST /alerts/history/{id}/acknowledge` - Acknowledge alert

## Running the API

### Development

```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy asyncpg redis aioredis pydantic-settings

# Run with auto-reload
python -m src.api.app

# Or use uvicorn directly
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Run with Gunicorn + Uvicorn workers
gunicorn src.api.app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

## Configuration

Set environment variables or create `config/.env`:

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=biotech_ma
POSTGRES_USER=biotech
POSTGRES_PASSWORD=secret

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# API
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=your_secret_key_here

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Authentication

Include API key in request header:

```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/v1/companies
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Response Models

All endpoints use Pydantic models for request/response validation:

- Type safety and validation
- Automatic OpenAPI schema generation
- JSON serialization with proper types
- Clear error messages for invalid data

## Error Handling

Standard HTTP status codes:
- `200` - Success
- `201` - Created
- `204` - No Content
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid API key)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

Error response format:
```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

## Rate Limiting

Rate limit headers in all responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1701964800
```

When rate limit exceeded:
```json
{
  "error": "Rate limit exceeded",
  "detail": "Rate limit of 100 requests per 60s exceeded",
  "retry_after": 1701964860
}
```

## Database Integration

Currently uses mock data. To integrate with database:

1. Create SQLAlchemy models in `src/models/db/`
2. Update route handlers to query database via `AsyncSession`
3. Implement proper filtering, sorting, and pagination
4. Add database migrations with Alembic

Example:
```python
@router.get("/companies")
async def list_companies(
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(CompanyModel)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    companies = result.scalars().all()
    return {"companies": companies}
```

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/api/
```

## Next Steps

1. **Database Integration**: Replace mock data with real database queries
2. **Caching**: Add Redis caching for frequently accessed data
3. **Background Tasks**: Implement async report generation
4. **Webhooks**: Add webhook delivery mechanism
5. **Metrics**: Add Prometheus metrics
6. **Monitoring**: Integrate with Sentry or similar
7. **Rate Limiting**: Fine-tune limits per endpoint/user tier
8. **Search**: Add full-text search capabilities
9. **Versioning**: Add API version negotiation
10. **Documentation**: Add usage examples and tutorials
