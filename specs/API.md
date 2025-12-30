# Biotech M&A Predictor - API Specification

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Active

---

## Overview

The Biotech M&A Predictor API provides programmatic access to M&A candidate data, scoring, acquirer matching, and reports. This document supplements the OpenAPI specification at [specs/api/openapi.yaml](api/openapi.yaml).

---

## Base URL

```
Production: https://api.umwai.com/v1
Staging:    https://api-staging.umwai.com/v1
Local:      http://localhost:8000/v1
```

---

## Authentication

### API Key Authentication

Include your API key in the request header:

```
X-API-Key: your-api-key-here
```

### JWT Authentication (User Sessions)

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Rate Limits

| Plan | Requests/Hour | Requests/Day |
|------|---------------|--------------|
| Free | 100 | 1,000 |
| Professional | 1,000 | 10,000 |
| Enterprise | 10,000 | 100,000 |

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1703980800
```

---

## Companies

### List Companies

```http
GET /companies
```

Query companies in the M&A watchlist.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| min_score | float | Minimum M&A score (0-100) |
| max_score | float | Maximum M&A score (0-100) |
| tier | int | Filter by tier (1, 2, or 3) |
| therapeutic_area | string | Filter by therapeutic area |
| min_market_cap | float | Minimum market cap (millions USD) |
| max_market_cap | float | Maximum market cap (millions USD) |
| sort_by | string | Sort field (score, market_cap, name) |
| order | string | Sort order (asc, desc) |
| limit | int | Results per page (default: 50, max: 100) |
| offset | int | Pagination offset |

**Request:**

```bash
curl -X GET "https://api.umwai.com/v1/companies?min_score=70&tier=1&limit=10" \
  -H "X-API-Key: your-api-key"
```

**Response:**

```json
{
  "data": [
    {
      "id": "comp-12345",
      "ticker": "ACME",
      "name": "Acme Therapeutics Inc.",
      "sector": "biotechnology",
      "therapeutic_areas": ["oncology", "immunology"],
      "ma_score": 87.5,
      "tier": 1,
      "confidence": 0.85,
      "recommendation": "STRONG_BUY",
      "market_cap": 450.5,
      "cash_position": 85.2,
      "runway_months": 15,
      "score_change_7d": 5.2,
      "score_change_30d": 12.8,
      "last_signal_date": "2025-12-28",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-12-28T14:30:00Z"
    }
  ],
  "pagination": {
    "total": 45,
    "limit": 10,
    "offset": 0,
    "has_more": true
  }
}
```

### Get Company

```http
GET /companies/{company_id}
```

Get detailed company profile and M&A analysis.

**Request:**

```bash
curl -X GET "https://api.umwai.com/v1/companies/comp-12345" \
  -H "X-API-Key: your-api-key"
```

**Response:**

```json
{
  "data": {
    "id": "comp-12345",
    "ticker": "ACME",
    "name": "Acme Therapeutics Inc.",
    "description": "Acme Therapeutics is developing next-generation small molecule and antibody-drug conjugate therapies for solid tumors.",
    "sector": "biotechnology",
    "headquarters": "Boston, MA",
    "employees": 150,
    "founded": 2015,

    "financials": {
      "market_cap": 450.5,
      "enterprise_value": 415.3,
      "stock_price": 45.50,
      "stock_change_1d": -1.2,
      "stock_change_30d": 8.5,
      "cash_position": 85.2,
      "burn_rate": 22.5,
      "runway_months": 15,
      "revenue_ttm": 0,
      "debt": 50.0
    },

    "ma_analysis": {
      "ma_score": 87.5,
      "tier": 1,
      "confidence": 0.85,
      "recommendation": "STRONG_BUY",
      "acquisition_probability": "high",
      "target_type": "platform",

      "score_components": {
        "clinical": 85.0,
        "patent": 92.0,
        "insider": 75.0,
        "financial": 88.0
      },

      "primary_drivers": [
        "patent_cliff",
        "strategic_hiring",
        "clinical_success"
      ],

      "risk_factors": [
        "Clinical trial failure risk",
        "High valuation expectations"
      ],

      "valuation_estimate": {
        "low": 800,
        "high": 1500,
        "basis": "Comparable transactions, DCF analysis"
      },

      "timeline_estimate": {
        "earliest": "2026-03-01",
        "most_likely": "2026-06-30",
        "latest": "2026-12-31"
      }
    },

    "pipeline": {
      "total_programs": 5,
      "phase_breakdown": {
        "phase3": 1,
        "phase2": 2,
        "phase1": 2
      },
      "therapeutic_areas": ["oncology", "immunology"],
      "lead_program": {
        "name": "ACM-2001",
        "indication": "Non-Small Cell Lung Cancer",
        "stage": "Phase 3",
        "status": "active_not_recruiting",
        "estimated_completion": "2026-06-30"
      }
    },

    "signals_summary": {
      "total_signals_30d": 7,
      "clinical_signals": 3,
      "patent_signals": 2,
      "insider_signals": 1,
      "hiring_signals": 1,
      "latest_signal": {
        "type": "phase_advancement",
        "description": "ACM-2001 Phase 3 trial enrollment completed",
        "impact_score": 85,
        "date": "2025-12-28"
      }
    },

    "top_acquirer_matches": [
      {
        "acquirer_id": "acq-67890",
        "acquirer_name": "Global Pharma Corporation",
        "ticker": "GPC",
        "match_score": 89.5,
        "strategic_rationale": "pipeline_gap_fill"
      }
    ],

    "updated_at": "2025-12-28T14:30:00Z"
  }
}
```

### Get Company Score History

```http
GET /companies/{company_id}/score-history
```

Get historical M&A scores for a company.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| start_date | date | Start date (YYYY-MM-DD) |
| end_date | date | End date (YYYY-MM-DD) |
| interval | string | Aggregation interval (daily, weekly, monthly) |

**Request:**

```bash
curl -X GET "https://api.umwai.com/v1/companies/comp-12345/score-history?start_date=2025-10-01&interval=daily" \
  -H "X-API-Key: your-api-key"
```

**Response:**

```json
{
  "data": {
    "company_id": "comp-12345",
    "ticker": "ACME",
    "history": [
      {
        "date": "2025-12-28",
        "ma_score": 87.5,
        "clinical_score": 85.0,
        "patent_score": 92.0,
        "insider_score": 75.0,
        "financial_score": 88.0,
        "tier": 1,
        "signal_count": 2
      },
      {
        "date": "2025-12-27",
        "ma_score": 82.3,
        "clinical_score": 80.0,
        "patent_score": 90.0,
        "insider_score": 70.0,
        "financial_score": 85.0,
        "tier": 2,
        "signal_count": 0
      }
    ]
  },
  "pagination": {
    "start_date": "2025-10-01",
    "end_date": "2025-12-28",
    "total_points": 89
  }
}
```

---

## M&A Candidates

### List M&A Candidates

```http
GET /candidates
```

Get ranked list of current M&A candidates.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| tier | int | Filter by tier (1, 2, 3) |
| min_probability | float | Minimum probability score |
| therapeutic_area | string | Filter by therapeutic area |
| limit | int | Results per page (default: 20) |
| offset | int | Pagination offset |

**Response:**

```json
{
  "data": [
    {
      "candidate_id": "cand-2025-001",
      "company_id": "comp-12345",
      "ticker": "ACME",
      "name": "Acme Therapeutics Inc.",
      "ma_score": 87.5,
      "tier": 1,
      "confidence": 0.85,
      "recommendation": "STRONG_BUY",

      "score_components": {
        "clinical": 85.0,
        "patent": 92.0,
        "insider": 75.0,
        "financial": 88.0
      },

      "signal_summary": {
        "clinical_count": 3,
        "patent_count": 2,
        "insider_count": 1,
        "hiring_count": 1,
        "key_events": [
          "Phase 3 advancement",
          "Patent expiring Q1 2026"
        ]
      },

      "primary_drivers": ["patent_cliff", "strategic_hiring"],
      "valuation_range": {
        "low": 800,
        "high": 1500
      },
      "top_match": {
        "acquirer": "Global Pharma Corporation",
        "match_score": 89.5
      },
      "updated_at": "2025-12-28T14:30:00Z"
    }
  ],
  "pagination": {
    "total": 45,
    "limit": 20,
    "offset": 0
  },
  "summary": {
    "tier_1_count": 5,
    "tier_2_count": 18,
    "tier_3_count": 22,
    "avg_score": 62.5
  }
}
```

### Get Candidate Detail

```http
GET /candidates/{candidate_id}
```

Get detailed M&A candidate analysis.

---

## Acquirer Matches

### List Matches for Target

```http
GET /companies/{company_id}/matches
```

Get potential acquirer matches for a target company.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| min_score | float | Minimum match score |
| limit | int | Number of matches to return (default: 10) |

**Response:**

```json
{
  "data": {
    "target": {
      "id": "comp-12345",
      "ticker": "ACME",
      "name": "Acme Therapeutics Inc.",
      "ma_score": 87.5
    },
    "matches": [
      {
        "match_id": "match-2025-001",
        "acquirer": {
          "id": "acq-67890",
          "ticker": "GPC",
          "name": "Global Pharma Corporation",
          "market_cap": 45000
        },
        "match_score": 89.5,
        "score_breakdown": {
          "therapeutic_fit": 95.0,
          "technology_fit": 85.0,
          "financial_fit": 90.0,
          "historical_pattern": 78.0
        },
        "strategic_rationale": {
          "primary": "pipeline_gap_fill",
          "supporting": [
            "Therapeutic area alignment",
            "Phase 3 asset de-risks acquisition"
          ]
        },
        "synergies": [
          {
            "type": "revenue_synergy",
            "description": "Leverage global commercial infrastructure",
            "estimated_value": 500
          }
        ],
        "risks": [
          {
            "type": "clinical_risk",
            "description": "Phase 3 trial completion required",
            "severity": "medium"
          }
        ],
        "probability": 45.0,
        "timeline": {
          "earliest": "2026-01-01",
          "most_likely": "2026-04-15",
          "latest": "2026-09-30"
        }
      }
    ]
  }
}
```

### Get All Matches

```http
GET /matches
```

Get all acquirer-target matches, sorted by match score.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| min_score | float | Minimum match score |
| acquirer_id | string | Filter by acquirer |
| target_tier | int | Filter by target tier |
| limit | int | Results per page (default: 50) |

---

## Signals

### List Signals

```http
GET /signals
```

Query signals across all companies.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| company_id | string | Filter by company |
| signal_type | string | Signal type filter |
| source | string | Signal source (clinical, patent, insider, hiring) |
| min_impact | float | Minimum impact score |
| start_date | date | Start date |
| end_date | date | End date |
| limit | int | Results per page (default: 50) |

**Response:**

```json
{
  "data": [
    {
      "id": "sig-12345",
      "company_id": "comp-12345",
      "ticker": "ACME",
      "company_name": "Acme Therapeutics Inc.",
      "signal_type": "phase_advancement",
      "signal_source": "clinical",
      "impact_score": 85,
      "description": "ACM-2001 advanced to Phase 3 following successful Phase 2 results",
      "details": {
        "trial_nct_id": "NCT04123456",
        "drug_name": "ACM-2001",
        "indication": "Non-Small Cell Lung Cancer",
        "current_phase": "phase3",
        "previous_phase": "phase2"
      },
      "timestamp": "2025-12-28T10:15:00Z"
    }
  ],
  "pagination": {
    "total": 1250,
    "limit": 50,
    "offset": 0
  }
}
```

### Get Company Signals

```http
GET /companies/{company_id}/signals
```

Get all signals for a specific company.

---

## Acquirers

### List Acquirers

```http
GET /acquirers
```

Get list of tracked potential acquirers.

**Response:**

```json
{
  "data": [
    {
      "id": "acq-67890",
      "ticker": "GPC",
      "name": "Global Pharma Corporation",
      "market_cap": 45000,
      "cash_position": 8500,
      "focus_areas": ["oncology", "rare_disease", "immunology"],
      "pipeline_gaps": ["NSCLC late-stage", "ADC platform"],
      "acquisition_profile": {
        "deals_5y": 12,
        "avg_deal_size": 1500,
        "preferred_stages": ["phase2", "phase3"],
        "preferred_therapeutics": ["oncology", "rare_disease"]
      },
      "active": true
    }
  ],
  "pagination": {
    "total": 25,
    "limit": 50,
    "offset": 0
  }
}
```

### Get Acquirer Profile

```http
GET /acquirers/{acquirer_id}
```

Get detailed acquirer profile and acquisition history.

---

## Reports

### List Available Reports

```http
GET /reports
```

List generated reports accessible to the client.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| type | string | Report type (daily_digest, weekly_watchlist, deep_dive) |
| start_date | date | Start date |
| end_date | date | End date |
| limit | int | Results per page |

**Response:**

```json
{
  "data": [
    {
      "id": "rpt-2025-12-001",
      "type": "weekly_watchlist",
      "title": "Weekly M&A Candidate Summary - December 2025 Week 1",
      "reporting_period": {
        "start": "2025-12-01",
        "end": "2025-12-07"
      },
      "generated_at": "2025-12-07T18:30:00Z",
      "formats": ["pdf", "html"],
      "summary": {
        "total_candidates": 12,
        "new_candidates": 3,
        "high_probability": 5
      },
      "download_urls": {
        "pdf": "https://reports.umwai.com/rpt-2025-12-001.pdf",
        "html": "https://reports.umwai.com/rpt-2025-12-001.html"
      }
    }
  ]
}
```

### Get Report

```http
GET /reports/{report_id}
```

Get report metadata and download links.

### Download Report

```http
GET /reports/{report_id}/download
```

Download report file.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| format | string | File format (pdf, html, json) |

### Generate On-Demand Report

```http
POST /reports/generate
```

Generate a custom report.

**Request Body:**

```json
{
  "type": "deep_dive",
  "company_id": "comp-12345",
  "format": ["pdf", "html"],
  "sections": [
    "executive_summary",
    "ma_analysis",
    "pipeline",
    "acquirer_matches"
  ]
}
```

**Response:**

```json
{
  "data": {
    "report_id": "rpt-2025-12-custom-001",
    "status": "generating",
    "estimated_completion": "2025-12-28T15:00:00Z",
    "webhook_url": "https://api.umwai.com/v1/reports/rpt-2025-12-custom-001/status"
  }
}
```

---

## Webhooks

### Configure Webhook

```http
POST /webhooks
```

Register a webhook endpoint to receive events.

**Request Body:**

```json
{
  "url": "https://your-server.com/webhook",
  "events": [
    "candidate.new_tier1",
    "candidate.score_change",
    "match.new_high_score",
    "report.generated"
  ],
  "secret": "your-webhook-secret"
}
```

### Webhook Events

| Event Type | Description |
|------------|-------------|
| `candidate.new_tier1` | New Tier 1 candidate identified |
| `candidate.score_change` | Significant score change (>10 points) |
| `candidate.tier_change` | Company moved between tiers |
| `match.new_high_score` | New high-score acquirer match |
| `signal.high_impact` | High impact signal detected |
| `report.generated` | Scheduled report generated |

### Webhook Payload

```json
{
  "event_id": "evt-12345",
  "event_type": "candidate.new_tier1",
  "timestamp": "2025-12-28T14:30:00Z",
  "data": {
    "company_id": "comp-12345",
    "ticker": "ACME",
    "name": "Acme Therapeutics Inc.",
    "ma_score": 82.5,
    "previous_tier": 2,
    "new_tier": 1,
    "primary_driver": "clinical_success"
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameter",
    "details": {
      "field": "min_score",
      "reason": "Must be between 0 and 100"
    },
    "request_id": "req-12345"
  }
}
```

### Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | VALIDATION_ERROR | Invalid request parameters |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 429 | RATE_LIMITED | Rate limit exceeded |
| 500 | INTERNAL_ERROR | Internal server error |
| 503 | SERVICE_UNAVAILABLE | Service temporarily unavailable |

---

## SDKs

### Python SDK (Coming Soon)

```python
from umwai import MAPredictor

client = MAPredictor(api_key="your-api-key")

# Get top candidates
candidates = client.candidates.list(tier=1, limit=10)

# Get company details
company = client.companies.get("comp-12345")

# Get score history
history = client.companies.score_history("comp-12345", days=90)

# Get acquirer matches
matches = client.matches.for_company("comp-12345", limit=5)
```

---

## OpenAPI Specification

For the complete OpenAPI specification, see [specs/api/openapi.yaml](api/openapi.yaml).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-30 | Initial API specification |

