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

## Market-Wide Research Evaluation

Build the current U.S.-listed drug/biotech universe and evaluate all ingested
marketed and active clinical assets:

```bash
python3 scripts/evaluate_market.py --as-of YYYY-MM-DD
```

The command uses current Nasdaq/SEC identifiers, FDA Orange Book data,
currently marketed BLA products from Drugs@FDA, and active industry-sponsored
ClinicalTrials.gov records. It writes:

- `output/market_evaluation/companies.csv` — every listed company in scope;
- `output/market_evaluation/assets.csv` — every evaluated marketed or clinical asset;
- `output/market_evaluation/unmatched_owners.csv` — entity-resolution backlog;
- `output/market_evaluation/manifest.json` — coverage, versions, and known gaps; and
- `output/market_evaluation/summary.md` — ranked review tables.

These are transparent cross-sectional research scores, not calibrated M&A
probabilities. Re-run with `--offline` to reproduce results from cached raw
payloads or `--refresh` to fetch a new market snapshot. See the
[market research model card](docs/MARKET_RESEARCH_MODEL_CARD.md) for intended
use, score semantics, evidence status, and promotion gates.

Build the execution scorecard after the market, integrity, and execution-risk
evaluations:

```bash
python3 scripts/evaluate_study_integrity.py
python3 scripts/evaluate_execution_risk.py
python3 scripts/build_execution_scorecard.py
python3 scripts/build_strategic_matrix.py
```

This gives every market company separate delivery-upside, sourced execution
downside, evidence-coverage, and historical-marker similarity fields. Capricor,
past biotech failures, successful remediation, approvals, and later
acquisitions are encoded as point-in-time precedents. Later outcomes remain
validation labels and cannot enter the earlier score. See the
[execution scorecard model card](docs/EXECUTION_SCORECARD_MODEL_CARD.md).

Build the historical SEC transaction-candidate ledger separately:

```bash
python3 scripts/build_deal_labels.py \
  --start-date 2018-01-01 \
  --end-date YYYY-MM-DD
```

This produces an auditable Schedule 14D-9/DEFM14A adjudication queue under
`output/historical_deal_candidates/`, plus annual historical reporting-company
risk sets built from contemporaneous 10-K/20-F/40-F filers. It intentionally
marks every row ineligible for model training until target role, change of
control, and the first public announcement timestamp have been reviewed.

## Configuration

See `config/config.template.env` for required environment variables:
- Database connections
- API keys (SEC, FDA, etc.)
- Event bus configuration
- Alert thresholds

## License

Proprietary - AIvestor Labs LLC
