# Biotech M&A Predictor - Product Roadmap

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Active Development

---

## Executive Summary

The Biotech M&A Predictor is a continuous monitoring system that identifies biotech companies likely to be acquisition targets and matches them with potential acquirers. It aggregates signals from clinical trials, patent intelligence, insider activity, and hiring patterns to generate M&A probability scores and actionable investment intelligence.

---

## Vision

Build the definitive biotech M&A prediction platform that continuously monitors the biotech landscape, identifies acquisition candidates before the market, and delivers actionable intelligence to hedge funds, PE firms, and pharmaceutical corporate development teams.

---

## Phase 1: Foundation (Weeks 1-4)

### Milestone 1.1: Core Infrastructure
**Target:** Week 2

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Event Bus Setup | P0 | RabbitMQ/EventBridge configuration | Complete |
| PostgreSQL Schema | P0 | Company and signal data models | Complete |
| TimescaleDB Setup | P0 | Time-series data storage | Complete |
| Redis Cache | P0 | Caching layer for hot data | Complete |
| Docker Compose | P0 | Local development environment | Complete |

### Milestone 1.2: Signal Integration
**Target:** Week 4

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Clinical Trial Events | P0 | Consume clinical-trial-signals | Complete |
| Patent Cliff Events | P0 | Consume patent-ip-intelligence | Complete |
| Insider Activity Events | P0 | Consume insider-hiring-signals | Complete |
| Signal Aggregation | P0 | Aggregate signals by company | Complete |
| Event Validation | P0 | Schema validation for all events | Complete |

### Deliverables
- Working event bus with all signal producers connected
- Company profile database populated
- Real-time signal aggregation

---

## Phase 2: Scoring Engine (Weeks 5-8)

### Milestone 2.1: M&A Scoring Algorithm
**Target:** Week 6

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Base Score Calculation | P0 | Core M&A probability score | Complete |
| Clinical Component | P0 | Trial outcome impact scoring | Complete |
| Patent Component | P0 | Patent cliff risk scoring | Complete |
| Insider Component | P0 | Insider activity impact scoring | Complete |
| Financial Component | P0 | Cash runway and valuation scoring | Complete |

### Milestone 2.2: Score Calibration
**Target:** Week 8

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Historical Backtesting | P0 | Validate against past M&A events | Complete |
| Weight Optimization | P0 | Optimize component weights | Complete |
| Confidence Intervals | P1 | Add confidence scoring | Complete |
| Tier Classification | P1 | Tier 1/2/3 categorization | Complete |

### Deliverables
- Calibrated M&A scoring algorithm
- Historical validation metrics
- Tiered candidate classification

### Scoring Algorithm Reference
See [specs/scoring-engine/ma-scoring.md](scoring-engine/ma-scoring.md) for detailed algorithm specification.

---

## Phase 3: Acquirer Matching (Weeks 9-12)

### Milestone 3.1: Acquirer Profiles
**Target:** Week 10

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Big Pharma Profiles | P0 | Top 20 pharma acquirer profiles | Complete |
| Acquisition History | P0 | Historical deal data | Complete |
| Pipeline Gap Analysis | P0 | Therapeutic area gaps | Complete |
| Patent Cliff Calendar | P0 | Acquirer patent expirations | Complete |

### Milestone 3.2: Matching Algorithm
**Target:** Week 12

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Therapeutic Fit | P0 | Therapeutic area alignment | Complete |
| Technology Fit | P1 | Platform compatibility | Complete |
| Financial Fit | P1 | Deal size feasibility | Complete |
| Historical Pattern Match | P1 | Match to historical deals | Complete |
| Match Scoring | P0 | Combined match score | Complete |

### Deliverables
- Acquirer profile database
- Acquirer-target matching algorithm
- Match quality scoring

---

## Phase 4: Reporting System (Weeks 13-16)

### Milestone 4.1: Report Generation
**Target:** Week 14

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Daily Digest | P0 | Daily signal summary | Complete |
| Weekly Watchlist | P0 | Ranked M&A candidates | Complete |
| Deep Dive Reports | P1 | Single company analysis | Complete |
| Alert Reports | P1 | Score change alerts | Planned |
| Acquirer Analysis | P2 | Acquirer perspective reports | Planned |

### Milestone 4.2: Report Delivery
**Target:** Week 16

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Email Distribution | P0 | SendGrid integration | Complete |
| PDF Generation | P0 | WeasyPrint rendering | Complete |
| Secure Portal | P1 | Web-based report access | Planned |
| Slack Integration | P1 | Slack notifications | Planned |
| Webhook Delivery | P2 | Client webhook callbacks | Planned |

### Deliverables
- Automated daily and weekly reports
- Multi-channel delivery system
- Report archive

### Report Specification Reference
See [specs/reports/report-generation.md](reports/report-generation.md) for detailed report specifications.

---

## Phase 5: API Platform (Weeks 17-20)

### Milestone 5.1: REST API
**Target:** Week 18

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Companies Endpoint | P0 | List and query companies | Complete |
| Scores Endpoint | P0 | M&A scores and history | Complete |
| Signals Endpoint | P1 | Signal data access | Complete |
| Matches Endpoint | P1 | Acquirer-target matches | Complete |
| Reports Endpoint | P1 | Report generation API | Planned |

### Milestone 5.2: API Management
**Target:** Week 20

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| API Authentication | P0 | API key authentication | Complete |
| Rate Limiting | P0 | Per-client rate limits | Complete |
| Usage Tracking | P1 | API call analytics | Planned |
| API Documentation | P1 | Swagger/OpenAPI docs | Complete |
| SDK Generation | P2 | Python SDK | Planned |

### Deliverables
- Production-ready REST API
- API authentication and rate limiting
- Developer documentation

### API Reference
See [specs/api/openapi.yaml](api/openapi.yaml) for OpenAPI specification.

---

## Phase 6: Advanced Analytics (Weeks 21-24)

### Milestone 6.1: ML Enhancement
**Target:** Week 22

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Feature Engineering | P1 | ML feature pipeline | Planned |
| Model Training | P1 | M&A prediction model | Planned |
| Ensemble Scoring | P1 | Combine rule + ML scoring | Planned |
| Model Monitoring | P2 | Model drift detection | Planned |

### Milestone 6.2: Market Intelligence
**Target:** Week 24

| Feature | Priority | Description | Status |
|---------|----------|-------------|--------|
| Sector Analysis | P1 | Therapeutic area trends | Planned |
| Deal Flow Prediction | P2 | Market-level forecasting | Planned |
| Valuation Modeling | P2 | Acquisition price estimation | Planned |
| Competitive Intelligence | P2 | Big pharma strategy tracking | Planned |

### Deliverables
- ML-enhanced scoring
- Market-level analytics
- Valuation estimates

---

## Future Roadmap (Beyond Week 24)

### Enterprise Features (v2.0)
- White-label platform for clients
- Custom scoring models per client
- Multi-user team accounts
- Audit logging and compliance

### Global Expansion (v2.1)
- European biotech coverage (EMA)
- Asian biotech coverage (PMDA, NMPA)
- Multi-currency valuation
- International patent coverage

### Advanced ML (v3.0)
- NLP-based signal detection
- News sentiment analysis
- Conference call analysis
- Social media monitoring

---

## Signal Types Reference

### Clinical Trial Signals

| Signal Type | Weight | Description |
|-------------|--------|-------------|
| Phase Advancement | +20-30 | Trial progresses to next phase |
| Phase Failure | +15-25 | Failed trial creates vulnerability |
| Trial Termination | +10-15 | Terminated trials signal distress |
| Positive Interim | +15-20 | Positive interim data |
| Regulatory Breakthrough | +25-35 | Fast track, breakthrough therapy |

### Patent Signals

| Signal Type | Weight | Description |
|-------------|--------|-------------|
| Expiration Imminent | +20-30 | Key patent expiring < 2 years |
| Generic Challenge | +15-25 | ANDA/Paragraph IV filing |
| Patent Invalidation | +25-35 | Patent struck down |
| No Pipeline Replacement | +10-15 | No late-stage pipeline |

### Insider Signals

| Signal Type | Weight | Description |
|-------------|--------|-------------|
| C-Suite Buy Cluster | +25-35 | Multiple executives buying |
| CEO Large Purchase | +20-30 | CEO significant purchase |
| Director Buying | +15-20 | Board members buying |
| Institutional Accumulation | +10-15 | 13F position increase |

### Hiring Signals

| Signal Type | Weight | Description |
|-------------|--------|-------------|
| BD/CorpDev Hire | +20-30 | New business development executive |
| Regulatory Specialist | +15-20 | Regulatory affairs senior hire |
| C-Suite Turnover | +15-25 | CEO/CFO departure |
| Mass Layoffs | +10-20 | Significant workforce reduction |

---

## Success Metrics

### Phase 1-2 Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Signal Processing Latency | < 5 sec | Time from signal to score update |
| Score Accuracy | > 70% | Historical validation accuracy |
| Daily Signal Volume | > 100 | Average signals processed per day |

### Phase 3-4 Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Match Accuracy | > 60% | Acquirer prediction accuracy |
| Report Generation Time | < 5 min | Weekly report generation |
| Client Satisfaction | > 90% | Report satisfaction surveys |

### Phase 5-6 Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| API Uptime | > 99.9% | API availability |
| API Response Time | < 200ms | Average API latency |
| ML Model Lift | > 20% | Improvement over baseline |

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Data Source Outage | High | Medium | Multiple data source redundancy |
| Scoring Model Drift | High | Medium | Continuous backtesting |
| Regulatory Changes | Medium | Low | Monitor SEC/FDA changes |
| Competitive Intelligence | Medium | Medium | Proprietary signal combinations |
| Client Churn | High | Low | Regular feedback loops |

---

## Resource Requirements

### Infrastructure

| Component | Development | Production |
|-----------|-------------|------------|
| Application Servers | 2 vCPU, 4GB | 4 vCPU, 16GB (x2) |
| PostgreSQL | 2 vCPU, 4GB | 4 vCPU, 32GB |
| TimescaleDB | 2 vCPU, 4GB | 4 vCPU, 32GB |
| Redis | 512MB | 2GB |
| RabbitMQ | 1 vCPU, 1GB | 2 vCPU, 4GB |

### Estimated Monthly Costs

| Resource | Development | Production |
|----------|-------------|------------|
| Compute | $150-250 | $800-1200 |
| Database | $100-150 | $400-600 |
| Storage | $50-100 | $200-300 |
| Data Feeds | $500-1000 | $2000-5000 |
| **Total** | **$800-1500** | **$3400-7100** |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-30 | Initial roadmap with enhanced structure |

