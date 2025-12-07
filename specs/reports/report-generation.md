# Report Generation & Client Delivery Specification

## Overview

This specification defines the report generation system for the Biotech M&A Predictor, delivering actionable intelligence to hedge funds, PE firms, and pharma corporate development teams.

## 1. Report Types

### 1.1 Daily Digest
- **Purpose**: Summary of all signal activity in past 24 hours
- **Frequency**: Daily at 6:00 AM ET
- **Audience**: All subscribers
- **Content**: Signal counts, high-impact events, score changes, new watchlist entries

### 1.2 Weekly M&A Watchlist
- **Purpose**: Ranked list of acquisition targets with detailed analysis
- **Frequency**: Weekly on Monday at 8:00 AM ET
- **Audience**: Premium subscribers
- **Content**: Top 20 candidates, score breakdowns, acquirer matches, catalysts

### 1.3 Deep Dive Report
- **Purpose**: Comprehensive analysis of single target company
- **Frequency**: On-demand or triggered by score threshold
- **Audience**: Clients tracking specific companies
- **Content**: Full profile, pipeline analysis, financial metrics, acquirer fit matrix

### 1.4 Alert Report
- **Purpose**: Immediate notification of significant score changes
- **Frequency**: Event-driven (score change > 10 points or new Tier 1 candidate)
- **Audience**: Clients with configured alerts
- **Content**: Score change summary, triggering signals, recommended actions

### 1.5 Acquirer Analysis
- **Purpose**: Analysis from acquirer perspective
- **Frequency**: Monthly or on-demand
- **Audience**: Pharma CorpDev teams
- **Content**: Patent cliff timeline, pipeline gaps, target recommendations

## 2. Report Content Sections

### Standard Sections (All Reports)
1. **Executive Summary** - Key takeaways in 3-5 bullet points
2. **Methodology Note** - Brief explanation of scoring approach
3. **Disclaimer** - Legal disclaimer regarding investment advice

### Daily Digest Sections
1. Executive Summary
2. Signal Activity Summary (by type, by impact level)
3. Top Score Movers (gainers/losers)
4. New Watchlist Entries
5. Upcoming Catalysts (next 30 days)

### Weekly Watchlist Sections
1. Executive Summary
2. Market Overview
3. Ranked Watchlist Table (Top 20)
4. Score Component Breakdown Charts
5. New Additions / Removals
6. Acquirer-Target Heat Map
7. Sector Analysis

### Deep Dive Sections
1. Executive Summary
2. Company Overview
3. M&A Score Analysis (with radar chart)
4. Pipeline Deep Dive (by asset)
5. Financial Analysis
6. Signal History Timeline
7. Potential Acquirers (ranked)
8. Risk Factors
9. Investment Thesis

## 3. Report Generation Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT GENERATION PIPELINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Trigger  │───▶│  Data    │───▶│ Template │───▶│ Renderer │  │
│  │ (Cron/   │    │ Aggreg.  │    │ Engine   │    │ (PDF/    │  │
│  │  Event)  │    │          │    │ (Jinja2) │    │  HTML)   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │         │
│                                                        ▼         │
│                                               ┌──────────────┐  │
│                                               │   Delivery   │  │
│                                               │   Service    │  │
│                                               └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Template Engine
- **Technology**: Jinja2
- **Template Location**: `src/templates/`
- **Supported Formats**: HTML, PDF (via WeasyPrint)

### 3.2 Data Aggregation
```python
# Pseudocode for report data aggregation
async def aggregate_daily_digest_data(date: date) -> DailyDigestData:
    return DailyDigestData(
        signals=await get_signals_for_date(date),
        score_changes=await get_score_changes(date),
        watchlist_additions=await get_new_watchlist_entries(date),
        upcoming_catalysts=await get_catalysts(days=30),
        metrics=await calculate_summary_metrics(date)
    )
```

### 3.3 Chart Generation
- **Library**: Plotly for interactive (HTML), Matplotlib for static (PDF)
- **Chart Types**:
  - Score gauge charts
  - Radar charts for score components
  - Time series for score history
  - Heat maps for acquirer-target fit
  - Bar charts for signal distribution

### 3.4 PDF Rendering
- **Library**: WeasyPrint
- **Page Size**: Letter (8.5" x 11")
- **Branding**: Client logo placement, color schemes

## 4. Client Delivery Mechanisms

### 4.1 Email Distribution
- **Provider**: SendGrid
- **Features**:
  - HTML email with inline summary
  - PDF attachment
  - Tracking (opens, clicks)
  - Unsubscribe management

### 4.2 Secure Portal
- **Access**: Authenticated dashboard
- **Features**:
  - Report archive
  - Download history
  - Favorite reports

### 4.3 API Access
```
GET /reports - List available reports
GET /reports/{id} - Download specific report
GET /reports/{id}/data - Get raw data (JSON)
POST /reports/generate - Generate on-demand report
```

### 4.4 Webhooks
- POST to client endpoint when report ready
- Payload includes report metadata and download URL

### 4.5 Slack/Teams Integration
- Daily digest summary posted to channel
- Alert notifications in real-time

## 5. Scheduling & Triggers

### 5.1 Scheduled Reports
| Report Type | Schedule | Cron Expression |
|-------------|----------|-----------------|
| Daily Digest | Daily 6 AM ET | `0 6 * * *` |
| Weekly Watchlist | Monday 8 AM ET | `0 8 * * 1` |
| Acquirer Analysis | 1st Monday monthly | `0 8 1-7 * 1` |

### 5.2 Event-Driven Triggers
- **Score Alert**: M&A score changes > 10 points
- **New Tier 1**: Company enters Tier 1 (score >= 80)
- **Critical Signal**: FDA approval, trial failure, acquisition announcement

### 5.3 On-Demand
- API endpoint for custom report generation
- Dashboard button for deep dive reports

## 6. White-labeling & Customization

### 6.1 Client Branding
- Logo placement (header)
- Color scheme (primary, secondary)
- Custom footer text
- Contact information

### 6.2 Custom Watchlists
- Clients can define custom universes
- Therapeutic area filters
- Market cap ranges
- Geographic focus

### 6.3 Alert Configuration
- Custom score thresholds
- Signal type filters
- Delivery preferences
- Quiet hours

## 7. Storage & Archival

### 7.1 Report Storage
- **Location**: S3 bucket `biotech-ma-reports`
- **Structure**: `/{client_id}/{year}/{month}/{report_type}/{filename}`
- **Retention**: 2 years hot, then archive to Glacier

### 7.2 Metadata
- Stored in PostgreSQL `reports` table
- Tracks generation time, delivery status, access logs

## 8. Performance Requirements

| Metric | Target |
|--------|--------|
| Daily Digest Generation | < 2 minutes |
| Weekly Watchlist Generation | < 5 minutes |
| Deep Dive Report | < 30 seconds |
| Email Delivery | < 1 minute after generation |
| API Response (report list) | < 200ms |
