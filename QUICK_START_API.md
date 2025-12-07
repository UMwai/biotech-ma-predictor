# Quick Start Guide - FastAPI Server

## 1. Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy asyncpg redis aioredis pydantic-settings python-multipart
```

## 2. Set Environment Variables

Create `config/.env`:
```env
API_SECRET_KEY=your_secret_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=biotech_ma
POSTGRES_USER=biotech
POSTGRES_PASSWORD=password
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 3. Start the Server

```bash
python run_api.py
```

Server will start at: `http://localhost:8000`

## 4. Access Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 5. Test the API

### Health Check (No Auth Required)
```bash
curl http://localhost:8000/health
```

### List Companies (No Auth Required for Mock Data)
```bash
curl http://localhost:8000/api/v1/companies
```

### Get Company Profile (No Auth Required for Mock Data)
```bash
curl http://localhost:8000/api/v1/companies/ABCD
```

### With Authentication
```bash
curl -H "X-API-Key: your_secret_key_here" \
     http://localhost:8000/api/v1/predictions/watchlist
```

## 6. Example API Calls

### Get M&A Watchlist
```bash
curl -H "X-API-Key: your_key" \
     "http://localhost:8000/api/v1/predictions/watchlist?min_score=70&page=1&page_size=20"
```

### Get Company Signals
```bash
curl "http://localhost:8000/api/v1/companies/ABCD/signals?signal_type=clinical_trial"
```

### Get Top Candidates
```bash
curl "http://localhost:8000/api/v1/predictions/top?n=10"
```

### Get Potential Acquirers
```bash
curl "http://localhost:8000/api/v1/predictions/WXYZ/acquirers?min_match_score=60"
```

### Create Alert Rule
```bash
curl -X POST "http://localhost:8000/api/v1/alerts/rules" \
     -H "X-API-Key: your_key" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "High Score Alert",
       "alert_type": "score_threshold",
       "enabled": true,
       "channels": ["email"],
       "conditions": {"score_threshold": 80}
     }'
```

### Generate Report
```bash
curl -X POST "http://localhost:8000/api/v1/reports/generate" \
     -H "X-API-Key: your_key" \
     -H "Content-Type: application/json" \
     -d '{
       "report_type": "daily_digest",
       "format": "pdf",
       "title": "Custom Daily Digest"
     }'
```

## 7. Response Examples

### Successful Response
```json
{
  "ticker": "ABCD",
  "name": "ABC Therapeutics",
  "ma_score": 72.5,
  "market_cap_usd": 1500000000.0,
  "last_updated": "2025-12-07T10:30:00Z"
}
```

### Error Response
```json
{
  "error": "Validation error",
  "detail": "Invalid ticker symbol format"
}
```

### Rate Limit Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1701964800
```

## 8. Available Endpoints

### Companies
- `GET /api/v1/companies` - List companies
- `GET /api/v1/companies/{ticker}` - Get profile
- `GET /api/v1/companies/{ticker}/signals` - Get signals
- `GET /api/v1/companies/{ticker}/pipeline` - Get pipeline

### Predictions
- `GET /api/v1/predictions/watchlist` - M&A watchlist
- `GET /api/v1/predictions/top` - Top candidates
- `GET /api/v1/predictions/{ticker}/acquirers` - Potential acquirers
- `GET /api/v1/predictions/matches` - All matches

### Reports
- `GET /api/v1/reports` - List reports
- `GET /api/v1/reports/{id}` - Get report
- `POST /api/v1/reports/generate` - Generate report
- `GET /api/v1/reports/daily-digest/latest` - Latest digest
- `GET /api/v1/reports/weekly-watchlist/latest` - Latest watchlist

### Alerts
- `GET /api/v1/alerts/rules` - List alert rules
- `POST /api/v1/alerts/rules` - Create rule
- `GET /api/v1/alerts/webhooks` - List webhooks
- `POST /api/v1/alerts/webhooks` - Register webhook
- `GET /api/v1/alerts/history` - Alert history

## 9. Common Query Parameters

### Pagination
- `page=1` - Page number (default: 1)
- `page_size=20` - Items per page (default: 20, max: 100)

### Filtering
- `min_score=70` - Minimum M&A score
- `therapeutic_area=oncology` - Filter by area
- `enabled=true` - Filter by enabled status
- `start_date=2025-12-01` - Date range start
- `end_date=2025-12-07` - Date range end

### Sorting
- `sort_by=ma_score` - Sort field
- `sort_order=desc` - Sort direction (asc/desc)

## 10. Authentication

Include API key in header:
```bash
-H "X-API-Key: your_api_key_here"
```

Or use curl's `-u` flag for basic auth (if implemented):
```bash
curl -u "api_key:" http://localhost:8000/api/v1/companies
```

## 11. Rate Limits

- **Anonymous**: 100 requests per minute
- **Authenticated**: 1000 requests per minute

Check headers for current usage:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1701964800
```

## 12. Development Tips

### Enable Debug Logging
```python
LOG_LEVEL=DEBUG python run_api.py
```

### Auto-reload on Code Changes
Already enabled in `run_api.py` with `reload=True`

### Test Imports
```bash
python test_api_import.py
```

### Check Syntax
```bash
python -m py_compile src/api/*.py src/api/routes/*.py
```

## 13. Production Deployment

### With Gunicorn
```bash
gunicorn src.api.app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

### With Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "src.api.app:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

## 14. Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Redis Connection Failed
Check Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### Database Connection Failed
Check PostgreSQL is running:
```bash
psql -h localhost -U biotech -d biotech_ma
```

### Import Errors
Ensure you're in the project root:
```bash
cd /Users/waiyang/Desktop/repo/biotech-ma-predictor
python run_api.py
```

## 15. Next Steps

1. **Connect Database**: Replace mock data with real queries
2. **Add Caching**: Implement Redis caching
3. **Background Tasks**: Set up Celery for async jobs
4. **Webhooks**: Implement webhook delivery
5. **Testing**: Add pytest test suite
6. **Monitoring**: Add Prometheus metrics
7. **Security**: Add JWT authentication
8. **Versioning**: Implement API versioning

## Support

For issues or questions:
- Check `/docs` for interactive API documentation
- Review `/src/api/README.md` for detailed documentation
- Check logs for error messages
