# Biotech M&A Predictor

A continuous monitoring system that identifies biotech companies likely to be acquisition targets and matches them with potential acquirers.

## Overview

This system aggregates signals from multiple data sources to score biotech companies on their acquisition likelihood, generating actionable intelligence for hedge funds, PE firms, and pharmaceutical corporate development teams.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SIGNAL PRODUCERS                                   │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────┤
│ clinical-trial- │ patent-ip-      │ insider-hiring- │ External APIs           │
│ signals         │ intelligence    │ signals         │ (SEC, FDA, USPTO)       │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬─────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT BUS (RabbitMQ/EventBridge)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         M&A PREDICTOR CORE                                   │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────┤
│ Signal          │ Company         │ M&A Scoring     │ Acquirer                │
│ Aggregator      │ Profiler        │ Engine          │ Matcher                 │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬─────────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA STORES                                          │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────┤
│ PostgreSQL      │ TimescaleDB     │ S3/Document     │ Redis                   │
│ (Profiles)      │ (Time-series)   │ Store           │ (Cache)                 │
└─────────────────┴─────────────────┴─────────────────┴─────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                         │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────────┤
│ Report          │ API             │ Dashboard       │ Alerts                  │
│ Generator       │ Server          │ (Streamlit)     │ (Email/Slack)           │
└─────────────────┴─────────────────┴─────────────────┴─────────────────────────┘
```

## Key Features

- **Continuous Monitoring**: Not a one-time analysis - runs 24/7 watching for signals
- **Multi-Signal Integration**: Combines clinical, patent, insider, and financial signals
- **M&A Scoring**: Proprietary algorithm scores companies 0-100 on acquisition likelihood
- **Acquirer Matching**: Identifies which big pharma/biotech would most likely acquire each target
- **Automated Reporting**: Daily digests, weekly watchlists, deep-dive reports
- **Client Delivery**: Email, API, dashboard, and webhook delivery options

## Specs-First Development

This project follows specs engineering principles. All specifications are defined before implementation:

```
specs/
├── events/           # Event schema definitions
├── data-pipeline/    # Data flow architecture
├── scoring-engine/   # M&A scoring algorithm spec
├── reports/          # Report templates and delivery
└── api/              # API contracts
```

## Related Repositories

This system integrates with:
- [clinical-trial-signals](https://github.com/UMwai/clinical-trial-signals) - Trial outcome detection
- [patent-ip-intelligence](https://github.com/UMwai/patent-ip-intelligence) - Patent cliff analysis
- [insider-hiring-signals](https://github.com/UMwai/insider-hiring-signals) - Insider activity tracking
- [investment-dashboard](https://github.com/UMwai/investment-dashboard) - Visualization layer

## Quick Start

```bash
# Clone the repo
git clone https://github.com/UMwai/biotech-ma-predictor.git
cd biotech-ma-predictor

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp config/config.template.env config/.env
# Edit .env with your API keys

# Run the system
python -m src.main
```

## Configuration

See `config/config.template.env` for required environment variables:
- Database connections
- API keys (SEC, FDA, etc.)
- Event bus configuration
- Alert thresholds

## License

Proprietary - AIvestor Labs LLC
