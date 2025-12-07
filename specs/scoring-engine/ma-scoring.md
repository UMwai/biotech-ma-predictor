# M&A Scoring Engine Specification

**Version:** 1.0
**Last Updated:** 2025-12-07
**Status:** Draft

## Overview

The M&A Scoring Engine is the core intelligence component of the Biotech M&A Predictor system. It analyzes multiple signals across clinical, financial, strategic, and market dimensions to predict which biotech companies are likely acquisition targets and match them with potential acquirers.

---

## 1. Acquisition Likelihood Scoring Model

### 1.1 Composite Score Formula

The composite M&A likelihood score (0-100) is calculated as a weighted sum of component scores:

```
M&A_Score = Σ(w_i × S_i × D_i)

where:
- w_i = weight for factor i
- S_i = normalized score for factor i (0-100)
- D_i = confidence/data quality factor (0-1)
```

### 1.2 Scoring Factors & Weights

#### Factor 1: Clinical Pipeline Value (30% weight)

**Subfactors:**
- **Phase Advancement Score (40%)**
  ```
  Phase_Score = Σ(asset_phase_value × indication_multiplier)

  Phase Values:
  - Preclinical: 10
  - Phase 1: 25
  - Phase 2: 50
  - Phase 3: 75
  - NDA/BLA Filed: 90
  - Approved: 100

  Indication Multipliers:
  - Orphan designation: 1.3x
  - Fast track: 1.2x
  - Breakthrough therapy: 1.4x
  - Priority review: 1.3x
  - Rare disease (non-orphan): 1.15x
  ```

- **Mechanism Novelty Score (25%)**
  ```
  Novelty_Score = 100 - (competitive_programs × 5)

  Adjustments:
  - First-in-class: +30 points
  - Best-in-class potential: +20 points
  - Me-too (>10 competitors): -40 points
  - Novel target (validated <2 years): +25 points
  ```

- **Indication Attractiveness (20%)**
  ```
  Indication_Score = (market_size_B × 10) + unmet_need_score

  Market Size Bands:
  - >$10B: 50 points
  - $5-10B: 40 points
  - $1-5B: 30 points
  - $500M-1B: 20 points
  - <$500M: 10 points

  Unmet Need Score (0-50):
  - No approved therapies: 50
  - Limited options (<3 approved): 35
  - Standard of care inadequate: 25
  - Crowded market: 10
  ```

- **Clinical Data Quality (15%)**
  ```
  Data_Quality = (endpoint_strength × 0.4) + (p_value_score × 0.3) +
                 (effect_size_score × 0.3)

  Endpoint Strength:
  - Primary endpoint met: 100
  - Secondary met, primary trending: 70
  - Biomarker/surrogate positive: 50
  - Preclinical only: 20

  P-value Score:
  - p < 0.001: 100
  - p < 0.01: 85
  - p < 0.05: 70
  - p < 0.1: 40
  - p > 0.1: 10

  Effect Size Score:
  - Hazard ratio < 0.5 or >2.0: 100
  - HR 0.5-0.7 or 1.5-2.0: 75
  - HR 0.7-0.9 or 1.1-1.5: 50
  - Minimal effect: 25
  ```

#### Factor 2: Patent Position Strength (12% weight)

```
Patent_Score = (coverage_breadth × 0.35) + (remaining_life × 0.30) +
               (litigation_strength × 0.20) + (freedom_to_operate × 0.15)

Coverage Breadth (0-100):
- Composition of matter: 100
- Formulation + method of use: 75
- Method of use only: 50
- Limited claims: 25

Remaining Life (0-100):
- >15 years: 100
- 10-15 years: 80
- 5-10 years: 50
- 2-5 years: 25
- <2 years: 10

Litigation Strength (0-100):
- No challenges, strong prosecution: 100
- Successfully defended: 90
- Minor challenges pending: 70
- Major IPR/litigation ongoing: 40
- Invalidated patents: 10

Freedom to Operate (0-100):
- Clear FTO: 100
- Minor blocking patents (workarounds exist): 75
- Licensing agreements in place: 60
- Significant blocking patents: 30
- Multiple FTO issues: 10
```

#### Factor 3: Cash Runway vs Catalyst Timing (18% weight)

```
Runway_Score = catalyst_pressure × urgency_multiplier

Catalyst Pressure (0-100):
months_to_catalyst = min(time_to_next_major_catalyst)
runway_months = cash / monthly_burn

pressure_ratio = runway_months / months_to_catalyst

Pressure Score:
- ratio < 0.5 (running out before catalyst): 100
- ratio 0.5-0.8 (tight timing): 85
- ratio 0.8-1.2 (balanced): 60
- ratio 1.2-2.0 (comfortable): 35
- ratio > 2.0 (plenty of runway): 15

Urgency Multiplier:
- Positive Phase 3 readout in <6mo: 1.5x
- NDA filing imminent: 1.4x
- Phase 2 readout in <6mo: 1.3x
- Major partnership decision point: 1.2x
- No near-term catalysts: 0.8x
```

**Major Catalysts Include:**
- Clinical trial readouts (Phase 2+)
- Regulatory submissions/decisions
- Partnership milestones
- Patent expirations (competitors)
- Market authorizations

#### Factor 4: Management/Board Signals (10% weight)

```
Management_Score = Σ(signal_type_value × recency_weight × magnitude)

Signal Types & Base Values:
- CEO/CFO departure: 70
- Board additions (ex-Big Pharma): 80
- Activist investor involvement: 75
- Hiring of M&A advisors: 90
- Strategic review announced: 95
- Insider buying (C-suite/board): 65
- Key scientific hire from acquirer: 60
- Reduction in R&D headcount: 55
- Sale of non-core assets: 70
- Termination of early programs: 50

Recency Weight:
- <30 days: 1.0x
- 30-90 days: 0.8x
- 90-180 days: 0.6x
- 180-365 days: 0.4x
- >365 days: 0.2x

Magnitude:
- Multiple signals in <90 days: 1.3x
- Single major signal: 1.0x
- Weak signal: 0.7x
```

#### Factor 5: Strategic Fit with Potential Acquirers (15% weight)

```
Strategic_Fit = (therapeutic_alignment × 0.30) + (technology_fit × 0.25) +
                (geographic_fit × 0.15) + (size_fit × 0.20) + (gap_filling × 0.10)

Therapeutic Alignment (0-100):
- Core therapeutic area for 3+ acquirers: 100
- Core for 1-2 acquirers: 75
- Adjacent area for multiple acquirers: 50
- Niche area: 30
- No clear alignment: 10

Technology Fit (0-100):
- Platform matches acquirer strategy: 100
- Complementary technology: 80
- Orthogonal but valuable: 60
- Standard approach: 40
- Outdated/commodity: 20

Geographic Fit (0-100):
- Global rights, major markets: 100
- US + EU rights: 90
- US or EU only: 70
- Single country/region: 40
- Limited geography: 20

Size Fit (0-100):
market_cap = target market cap
typical_deal = acquirer's avg deal size (last 5 years)

fit_ratio = market_cap / typical_deal

Size Score:
- ratio 0.5-1.5 (sweet spot): 100
- ratio 0.3-0.5 or 1.5-2.5: 75
- ratio 0.1-0.3 or 2.5-4.0: 50
- ratio <0.1 (too small): 30
- ratio >4.0 (too large): 25

Gap Filling (0-100):
- Fills patent cliff gap: 100
- Addresses therapeutic gap: 80
- Adds new capability: 70
- Incremental addition: 40
- Redundant with existing pipeline: 10
```

#### Factor 6: Competitive Landscape (8% weight)

```
Competitive_Score = 100 - (competitor_penalty + market_saturation_penalty)

Competitor Penalty:
direct_competitors = count of programs in same indication, same MoA
- 0-1 competitors: 0 penalty
- 2-3 competitors: 15 penalty
- 4-6 competitors: 35 penalty
- 7-10 competitors: 50 penalty
- >10 competitors: 70 penalty

Market Saturation Penalty:
approved_therapies = count in indication
- 0 approved (pure unmet need): 0 penalty
- 1-2 approved: 5 penalty
- 3-5 approved: 15 penalty
- 6-10 approved: 30 penalty
- >10 approved: 50 penalty

Adjustments:
- Best-in-class profile: -20 penalty (better score)
- Differentiated mechanism: -15 penalty
- Superior efficacy shown: -25 penalty
- Differentiated safety profile: -20 penalty
- Me-too profile: +30 penalty (worse score)
```

#### Factor 7: Regulatory Pathway Clarity (5% weight)

```
Regulatory_Score = pathway_score - risk_penalty

Pathway Score:
- Approved comparator, clear endpoints: 100
- Orphan pathway, precedented: 90
- Accelerated approval eligible: 85
- Standard pathway, well-defined: 75
- Novel pathway, precedented in class: 60
- First-in-class, FDA guidance exists: 50
- Unclear endpoints/requirements: 30

Risk Penalty:
- FDA clinical hold (current): 60
- FDA clinical hold (resolved): 20
- CRL received: 40
- Complete response letter addressed: 15
- Orphan designation revoked: 25
- Regulatory guidance negative: 30
- Manufacturing/CMC issues: 20
```

#### Factor 8: Historical M&A Patterns in Therapeutic Area (2% weight)

```
Historical_Pattern_Score = (deal_frequency × 0.4) + (premium_trend × 0.3) +
                          (stage_preference × 0.3)

Deal Frequency (0-100):
deals_last_3y = count of M&A in therapeutic area (last 36 months)
- >10 deals: 100
- 6-10 deals: 80
- 3-5 deals: 60
- 1-2 deals: 40
- 0 deals: 20

Premium Trend (0-100):
avg_premium = average premium paid in area (last 3y)
- >100% premium: 100
- 75-100%: 85
- 50-75%: 70
- 25-50%: 50
- <25%: 30

Stage Preference (0-100):
Match between target's stage and acquirer preferences:
- Perfect match (e.g., Phase 3 in area with Phase 3 deals): 100
- Close match: 75
- Stage typically acquired: 50
- Stage rarely acquired: 25
- No precedent: 10
```

### 1.3 Weight Summary Table

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Clinical Pipeline Value | 30% | Primary driver of acquisition value |
| Cash Runway vs Catalyst | 18% | Creates urgency and negotiating leverage |
| Strategic Fit | 15% | Determines acquirer interest pool |
| Patent Position | 12% | Protects value and competitive position |
| Management Signals | 10% | Leading indicator of company intentions |
| Competitive Landscape | 8% | Affects valuation and urgency |
| Regulatory Pathway | 5% | De-risks timeline and approval |
| Historical Patterns | 2% | Validates market conditions |
| **TOTAL** | **100%** | |

---

## 2. Target Company Profile Schema

### 2.1 Company Identifiers

```json
{
  "company_id": "uuid",
  "ticker": "NASDAQ:ABCD",
  "cik": "0001234567",
  "lei": "549300ABCDEFGHIJK123",
  "company_name": "BioTech Corp",
  "company_name_variations": ["BTC", "BioTech Corporation"],
  "founded_date": "2015-03-15",
  "headquarters": {
    "city": "Cambridge",
    "state": "MA",
    "country": "US"
  },
  "website": "https://biotechcorp.com",
  "employee_count": 150,
  "last_updated": "2025-12-07T10:30:00Z"
}
```

### 2.2 Pipeline Assets Schema

```json
{
  "pipeline": [
    {
      "asset_id": "uuid",
      "asset_name": "BTC-101",
      "asset_type": "small_molecule | biologic | cell_therapy | gene_therapy | other",
      "therapeutic_area": "oncology",
      "indication": "non-small cell lung cancer",
      "indication_icd10": ["C34.90", "C34.91"],
      "target": "EGFR",
      "mechanism": "tyrosine kinase inhibitor",
      "modality": "oral small molecule",

      "development_stage": {
        "current_phase": "phase_2",
        "phase_status": "enrolling | completed | readout_expected | on_hold",
        "next_milestone": "Phase 2 topline data",
        "next_milestone_date": "2026-Q2",
        "geography": ["US", "EU"]
      },

      "regulatory_status": {
        "orphan_designation": ["FDA", "EMA"],
        "fast_track": true,
        "breakthrough_therapy": false,
        "priority_review": false,
        "accelerated_approval_eligible": true,
        "regulatory_holds": []
      },

      "clinical_data": {
        "last_update_date": "2025-09-15",
        "primary_endpoint": "objective response rate",
        "primary_endpoint_met": true,
        "efficacy_summary": "45% ORR vs 20% SOC (p=0.003)",
        "safety_summary": "Well-tolerated, no DLTs",
        "competitive_advantage": "Superior efficacy in EGFR+ population"
      },

      "market_opportunity": {
        "addressable_market_usd": 8500000000,
        "patient_population": 125000,
        "competitive_landscape": "crowded | moderate | limited | first-in-class",
        "approved_therapies_count": 4,
        "peak_sales_estimate_usd": 1200000000
      },

      "patent_status": {
        "composition_of_matter_expiry": "2038-06-30",
        "formulation_expiry": "2040-12-15",
        "method_of_use_expiry": "2037-03-20",
        "patent_families": 3,
        "granted_patents": 12,
        "pending_applications": 5,
        "litigation_status": "none | pending | resolved",
        "freedom_to_operate": "clear | licensing_required | blocked"
      },

      "asset_scores": {
        "clinical_value": 78,
        "commercial_potential": 82,
        "technical_risk": 35,
        "regulatory_risk": 25,
        "composite_asset_score": 75
      }
    }
  ]
}
```

### 2.3 Financial Metrics Schema

```json
{
  "financials": {
    "as_of_date": "2025-09-30",
    "market_cap_usd": 450000000,
    "enterprise_value_usd": 380000000,

    "balance_sheet": {
      "cash_and_equivalents": 125000000,
      "marketable_securities": 45000000,
      "total_current_assets": 180000000,
      "total_assets": 220000000,
      "total_current_liabilities": 35000000,
      "total_liabilities": 50000000,
      "stockholders_equity": 170000000
    },

    "income_statement_ttm": {
      "revenue": 5000000,
      "research_development": 85000000,
      "general_administrative": 25000000,
      "operating_expenses": 110000000,
      "net_loss": -105000000
    },

    "cash_flow_ttm": {
      "operating_cash_flow": -95000000,
      "investing_cash_flow": -15000000,
      "financing_cash_flow": 120000000,
      "free_cash_flow": -110000000
    },

    "burn_metrics": {
      "monthly_burn_rate": 8750000,
      "runway_months": 19.4,
      "next_financing_needed": "2027-Q2",
      "runway_to_catalyst_ratio": 0.85
    },

    "valuation_metrics": {
      "price_to_book": 2.65,
      "ev_to_cash": 3.04,
      "market_cap_per_asset": 225000000
    }
  }
}
```

### 2.4 Signal History Schema

```json
{
  "signal_history": [
    {
      "signal_id": "uuid",
      "timestamp": "2025-11-15T14:30:00Z",
      "signal_type": "management_change | clinical_update | financial_event | regulatory | partnership | market",
      "signal_category": "insider_buying",
      "description": "CEO purchased 50,000 shares at $9.50",
      "source": "SEC Form 4",
      "source_url": "https://sec.gov/...",
      "impact_score": 65,
      "sentiment": "positive | negative | neutral",
      "confidence": 0.92,
      "included_in_score": true
    }
  ],

  "signal_summary": {
    "total_signals_90d": 12,
    "positive_signals_90d": 8,
    "negative_signals_90d": 2,
    "neutral_signals_90d": 2,
    "signal_momentum": "increasing | stable | decreasing"
  }
}
```

### 2.5 M&A Score Schema

```json
{
  "ma_score": {
    "composite_score": 73.5,
    "score_percentile": 87,
    "score_history": [
      {
        "date": "2025-12-01",
        "score": 73.5
      },
      {
        "date": "2025-11-01",
        "score": 68.2
      }
    ],

    "component_scores": {
      "clinical_pipeline_value": 78.0,
      "patent_position_strength": 82.0,
      "cash_runway_catalyst": 85.0,
      "management_signals": 65.0,
      "strategic_fit": 70.0,
      "competitive_landscape": 68.0,
      "regulatory_pathway": 75.0,
      "historical_patterns": 80.0
    },

    "confidence_factors": {
      "data_completeness": 0.95,
      "data_recency": 0.88,
      "signal_quality": 0.90,
      "overall_confidence": 0.91
    },

    "score_drivers": [
      "Tight cash runway with Phase 2 readout in 6 months",
      "Strong strategic fit with 3 potential acquirers",
      "Recent insider buying by CEO and board members"
    ],

    "risk_factors": [
      "Crowded competitive landscape",
      "No breakthrough therapy designation yet"
    ],

    "last_updated": "2025-12-07T10:30:00Z",
    "next_update": "2025-12-14T10:30:00Z"
  }
}
```

---

## 3. Acquirer Matching Algorithm

### 3.1 Acquirer Profile Schema

```json
{
  "acquirer_id": "uuid",
  "company_name": "MegaPharma Inc",
  "ticker": "NYSE:MEGA",

  "strategic_priorities": {
    "therapeutic_areas": [
      {
        "area": "oncology",
        "priority": "high | medium | low",
        "sub_areas": ["lung cancer", "breast cancer"],
        "stage_preference": ["phase_2", "phase_3"]
      }
    ],
    "technology_interests": ["small_molecule", "ADC", "immuno-oncology"],
    "geographic_focus": ["global", "US", "EU"]
  },

  "patent_cliffs": [
    {
      "product_name": "Blockbuster-X",
      "patent_expiry": "2028-06-30",
      "current_sales_usd": 5000000000,
      "therapeutic_area": "oncology",
      "time_to_cliff_months": 30,
      "replacement_urgency": "critical | high | medium | low"
    }
  ],

  "deal_capacity": {
    "cash_on_hand": 25000000000,
    "debt_capacity": 15000000000,
    "typical_deal_size": {
      "min": 500000000,
      "max": 10000000000,
      "average": 3500000000
    }
  },

  "historical_deals": [
    {
      "target_name": "BioAcq Corp",
      "deal_date": "2024-03-15",
      "deal_value_usd": 2800000000,
      "therapeutic_area": "oncology",
      "asset_stage": "phase_3",
      "premium_percent": 85,
      "deal_rationale": "Fill patent cliff for Product-Y"
    }
  ],

  "acquisition_patterns": {
    "avg_deals_per_year": 2.3,
    "preferred_stages": ["phase_2", "phase_3"],
    "avg_premium": 78,
    "time_to_close_avg_days": 145,
    "success_rate": 0.82
  }
}
```

### 3.2 Matching Score Formula

```
Acquirer_Match_Score = (therapeutic_alignment × 0.25) +
                       (patent_cliff_fit × 0.25) +
                       (valuation_fit × 0.20) +
                       (stage_fit × 0.15) +
                       (historical_pattern_match × 0.10) +
                       (strategic_urgency × 0.05)

All components scored 0-100, final score 0-100
```

### 3.3 Component Calculations

#### Therapeutic Alignment
```
Therapeutic_Alignment = Σ(asset_match × priority_weight)

For each target asset:
- Matches acquirer's high-priority area: 100 × 1.0
- Matches medium-priority area: 75 × 0.7
- Matches low-priority area: 50 × 0.4
- Adjacent to priority area: 30 × 0.3
- No alignment: 0

Technology bonus:
- Matches technology interest: +15 points
- Complementary technology: +10 points
```

#### Patent Cliff Fit
```
Patent_Cliff_Fit = max(cliff_urgency_score for all cliffs)

For each patent cliff:
time_to_cliff = months until patent expiry
target_approval_time = estimated months to approval

timing_fit = 1 - |time_to_cliff - target_approval_time| / 60

cliff_urgency_score = (timing_fit × 0.6) +
                     (therapeutic_match × 0.3) +
                     (sales_replacement_potential × 0.1)

Timing Fit (0-100):
- Perfect timing (±6 months): 100
- Good timing (±12 months): 80
- Acceptable (±24 months): 60
- Suboptimal (±36 months): 40
- Poor timing: 20

Therapeutic Match (0-100):
- Same indication: 100
- Same therapeutic area: 75
- Related area: 50
- Unrelated: 25

Sales Replacement Potential (0-100):
target_peak_sales / cliff_product_sales × 100 (capped at 100)
```

#### Valuation Fit
```
Valuation_Fit = deal_size_fit × premium_affordability

Deal Size Fit (0-100):
target_ev = target enterprise value
acquirer_typical = acquirer's average deal size

size_ratio = target_ev / acquirer_typical

- ratio 0.5-1.5: 100
- ratio 0.3-0.5 or 1.5-2.5: 80
- ratio 0.2-0.3 or 2.5-4.0: 60
- ratio 0.1-0.2 or 4.0-6.0: 40
- ratio <0.1 or >6.0: 20

Premium Affordability (0-1):
estimated_deal = target_ev × (1 + historical_avg_premium)
available_capacity = acquirer_cash + acquirer_debt_capacity

affordability = min(1, available_capacity / estimated_deal)
```

#### Stage Fit
```
Stage_Fit = stage_preference_match + data_quality_bonus

Stage Preference Match (0-90):
For each asset:
- Matches preferred stage: 90
- Adjacent stage (±1): 70
- Acceptable stage: 50
- Non-preferred stage: 30

Data Quality Bonus (0-10):
- Phase 3 with positive data: +10
- Phase 2 with strong efficacy: +8
- Phase 2 with early data: +5
- Earlier stages: +3
```

#### Historical Pattern Match
```
Pattern_Match = (therapeutic_match × 0.4) +
                (stage_match × 0.3) +
                (size_match × 0.3)

Therapeutic Match (0-100):
historical_deals_in_area = count of acquirer deals in target's TA
- >5 deals: 100
- 3-5 deals: 80
- 1-2 deals: 60
- 0 deals but adjacent: 40
- No precedent: 20

Stage Match (0-100):
historical_deals_at_stage = count at target's development stage
- >3 deals: 100
- 2-3 deals: 75
- 1 deal: 50
- 0 deals: 25

Size Match (0-100):
Similar to valuation_fit size_ratio calculation
```

#### Strategic Urgency
```
Urgency = (pipeline_gap × 0.5) + (market_pressure × 0.3) +
          (competitive_threat × 0.2)

Pipeline Gap (0-100):
approved_products_expiring_5y = count
late_stage_replacements = count of Phase 3+ assets

gap = approved_products_expiring_5y - late_stage_replacements
- gap ≥ 3: 100
- gap = 2: 75
- gap = 1: 50
- gap = 0: 25
- gap < 0 (surplus): 10

Market Pressure (0-100):
- Revenue decline >10% YoY: 100
- Revenue flat or declining <10%: 70
- Revenue growth <5%: 50
- Revenue growth 5-10%: 30
- Revenue growth >10%: 10

Competitive Threat (0-100):
- Major competitor launched competing product: 100
- Competitor Phase 3 positive in core area: 80
- Market share erosion >5%: 70
- Stable competitive position: 30
```

### 3.4 Top Acquirer Ranking

For each target company, generate ranked list of potential acquirers:

```json
{
  "target_company_id": "uuid",
  "potential_acquirers": [
    {
      "rank": 1,
      "acquirer_id": "uuid",
      "acquirer_name": "MegaPharma Inc",
      "match_score": 87.5,
      "estimated_probability": 0.42,
      "component_scores": {
        "therapeutic_alignment": 95,
        "patent_cliff_fit": 88,
        "valuation_fit": 82,
        "stage_fit": 90,
        "historical_pattern_match": 85,
        "strategic_urgency": 78
      },
      "deal_rationale": [
        "Fills $5B patent cliff for Blockbuster-X expiring 2028",
        "Perfect therapeutic alignment with oncology focus",
        "Historical pattern: 5 similar deals in past 3 years"
      ],
      "estimated_valuation_range": {
        "low": 1800000000,
        "base": 2400000000,
        "high": 3200000000
      },
      "estimated_timeline": "Q1-Q2 2026"
    }
  ]
}
```

### 3.5 Probability Estimation

```
Acquisition_Probability = base_prob × score_multiplier × timing_multiplier

Base Probability by Score:
- Score 90-100: 0.35
- Score 80-89: 0.25
- Score 70-79: 0.18
- Score 60-69: 0.12
- Score 50-59: 0.07
- Score <50: 0.03

Score Multiplier:
- Multiple acquirers with score >80: 1.5x
- 2-3 acquirers with score >70: 1.3x
- 1 acquirer with score >70: 1.0x
- No acquirer with score >70: 0.7x

Timing Multiplier:
- Catalyst in <6 months + low runway: 1.4x
- Catalyst in 6-12 months: 1.2x
- Catalyst in 12-18 months: 1.0x
- Catalyst >18 months: 0.8x
- No clear catalyst: 0.6x
```

---

## 4. Signal Weighting & Decay

### 4.1 Signal Combination Rules

When multiple signals contribute to a scoring factor:

```
Combined_Signal_Score = weighted_average(signals) × correlation_adjustment

Weighted Average:
Σ(signal_value × recency_weight × confidence) / Σ(recency_weight × confidence)
```

### 4.2 Recency Weighting Function

```
Recency_Weight(t) = e^(-λt)

where:
- t = time since signal (in days)
- λ = decay constant (varies by signal type)

Signal Type Decay Constants:
- Clinical data: λ = 0.003 (half-life ~230 days)
- Management changes: λ = 0.006 (half-life ~115 days)
- Financial data: λ = 0.008 (half-life ~87 days)
- Market signals: λ = 0.012 (half-life ~58 days)
- Regulatory events: λ = 0.004 (half-life ~173 days)
- Insider trading: λ = 0.010 (half-life ~69 days)

Recency Weight Calculation:
days_old = today - signal_date
weight = exp(-λ × days_old)

Example: Insider buying 60 days ago
weight = e^(-0.010 × 60) = e^(-0.6) = 0.549
```

### 4.3 Signal Correlation Handling

Some signals are correlated and should not be double-counted:

```
Correlation_Adjustment = 1 - (overlap_factor × correlation_coefficient)

Correlated Signal Pairs:
- CEO departure + Strategic review: r = 0.7
- Insider buying + Board additions: r = 0.5
- Cash runway + Asset sale: r = 0.6
- Phase 3 start + Partnership talks: r = 0.4
- Clinical hold + Regulatory guidance: r = 0.8

When both signals present:
adjusted_score = signal_A + (signal_B × (1 - r))

Example:
- CEO departure score: 70
- Strategic review announced: 95
- Correlation: 0.7

Without adjustment: 70 + 95 = 165 (overstated)
With adjustment: 70 + (95 × 0.3) = 98.5 (more accurate)
```

### 4.4 Signal Momentum

Track rate of change in signal frequency:

```
Signal_Momentum = (signals_recent / signals_baseline) - 1

signals_recent = count in last 30 days
signals_baseline = average count per 30 days (trailing 180 days)

Momentum Categories:
- >0.5 (50% increase): "Accelerating"
- 0.2 to 0.5: "Increasing"
- -0.2 to 0.2: "Stable"
- -0.5 to -0.2: "Decreasing"
- <-0.5: "Decelerating"

Momentum Impact on Score:
- Accelerating: +5 points
- Increasing: +2 points
- Stable: 0 points
- Decreasing: -2 points
- Decelerating: -5 points
```

### 4.5 Confidence Decay

Signal confidence degrades over time:

```
Confidence(t) = initial_confidence × recency_weight(t) × verification_factor

Verification Factor:
- Confirmed by multiple sources: 1.0
- Single source, verified: 0.95
- Single source, unverified: 0.85
- Rumor/speculation: 0.60

Example:
Initial confidence: 0.90
Days old: 45
Signal type: Management change (λ = 0.006)
Verification: Single source, verified (0.95)

Recency weight: e^(-0.006 × 45) = 0.763
Current confidence: 0.90 × 0.763 × 0.95 = 0.652
```

### 4.6 Data Quality Factors

Each component score includes a data quality multiplier:

```
D_i = completeness × recency × reliability

Completeness (0-1):
- All data points available: 1.0
- >80% data points: 0.9
- 60-80% data points: 0.8
- 40-60% data points: 0.6
- <40% data points: 0.4

Recency (0-1):
- Updated within 30 days: 1.0
- 30-90 days: 0.9
- 90-180 days: 0.8
- 180-365 days: 0.6
- >365 days: 0.4

Reliability (0-1):
- Primary source (SEC, clinicaltrials.gov): 1.0
- Company disclosure: 0.95
- Reputable secondary source: 0.90
- News/media: 0.80
- Social media/rumor: 0.60
```

---

## 5. Alert Thresholds

### 5.1 Score Change Alerts

Trigger alerts when M&A score changes significantly:

```
Score_Change_Alert_Level = f(Δscore, timeframe, absolute_score)

Alert Levels:
CRITICAL: Immediate action recommended
HIGH: Review within 24 hours
MEDIUM: Review within week
LOW: FYI only

Thresholds:
CRITICAL:
- Score increase ≥15 points in ≤7 days
- Score reaches ≥85 (top 5%)
- Score increase ≥10 points AND score ≥75

HIGH:
- Score increase 10-14 points in ≤14 days
- Score reaches 75-84 (top 15%)
- Score increase ≥8 points AND multiple positive signals

MEDIUM:
- Score increase 5-9 points in ≤30 days
- Score reaches 65-74 (top 30%)
- New acquirer match with score ≥80

LOW:
- Score increase 3-4 points in ≤30 days
- Score reaches 55-64
- Routine updates
```

### 5.2 Watchlist Entry Criteria

Companies enter the watchlist when meeting minimum thresholds:

```
Watchlist_Entry = (score ≥ threshold) OR (special_conditions)

Standard Entry:
- M&A Score ≥ 60
- At least one Phase 2+ asset
- Market cap $100M - $10B
- Confidence factor ≥ 0.70

Special Entry Conditions:
- Score ≥ 55 AND cash runway < 12 months AND Phase 3 readout in <6 months
- Score ≥ 50 AND strategic review announced
- Score ≥ 55 AND activist investor involved
- Score ≥ 50 AND 3+ strong acquirer matches (match score ≥75)
- Any score AND hiring of M&A advisor confirmed

Priority Tiers:
TIER 1 (Highest Priority):
- Score ≥ 80 OR
- Score ≥ 70 AND strategic review announced OR
- Score ≥ 65 AND M&A advisor hired

TIER 2 (High Priority):
- Score 70-79 OR
- Score 60-69 AND cash runway < 9 months OR
- Score 60-69 AND 2+ acquirer matches ≥80

TIER 3 (Medium Priority):
- Score 60-69 (standard)
- Score 55-59 AND special conditions met

TIER 4 (Monitoring):
- Score 50-59 AND special conditions met
- Score ≥60 but low confidence (<0.70)
```

### 5.3 Watchlist Removal Criteria

Remove companies when conditions change:

```
Remove from watchlist when:

Permanent Removal:
- Acquisition completed
- Company bankrupt/delisted
- Pipeline assets terminated (all material programs)
- Pivot to non-biotech business

Temporary Removal (move to "Inactive" list):
- Score drops below 50 for 90+ consecutive days
- Successful financing + no near-term catalysts (score <55)
- Major clinical failure (Phase 3) if only asset
- Lost strategic fit (e.g., therapeutic area deprioritized)

Re-evaluation Required:
- Score 45-49 for 60 days (review for special conditions)
- Confidence factor drops below 0.60
- Data freshness >180 days on key metrics
```

### 5.4 Signal-Based Alerts

Specific signals trigger immediate alerts:

```
Instant Alert Signals:
CRITICAL:
- Strategic review/sale process announced
- M&A advisor hired (confirmed)
- Activist investor takes >5% stake
- CEO/CFO sudden departure
- Clinical hold lifted + cash runway <6 months

HIGH:
- Positive Phase 3 data + cash runway <12 months
- Board adds 2+ big pharma executives
- Insider buying by 3+ executives/directors in 30 days
- Partnership termination (acquirer may buy)
- Major investor increases stake >50%

MEDIUM:
- Phase 2 positive data (material program)
- Orphan/Breakthrough designation granted
- Key scientific hire from potential acquirer
- Analyst upgrades citing M&A potential
- Patent granted (composition of matter)
```

### 5.5 Alert Delivery Rules

```
Alert Delivery Priority:
CRITICAL:
- Immediate push notification
- Email within 5 minutes
- Dashboard highlight
- Daily summary (top section)

HIGH:
- Push notification (batched hourly)
- Email within 1 hour
- Dashboard highlight
- Daily summary

MEDIUM:
- Email digest (every 6 hours)
- Dashboard notification
- Daily summary

LOW:
- Daily summary only
- Dashboard update

Alert Deduplication:
- Same alert within 24 hours: suppress
- Similar alerts (same company): combine
- Score update alerts: max 1 per company per day
```

---

## 6. Model Validation Approach

### 6.1 Backtesting Methodology

**Objective:** Validate the scoring model against historical M&A transactions

#### Data Requirements
```
Historical Dataset:
- Biotech M&A deals (2015-2024)
- Minimum deal size: $100M
- Target criteria: Public biotech with clinical assets
- Required data points:
  * Target financials (at announcement)
  * Pipeline status (at announcement)
  * Deal terms (value, premium, timeline)
  * Historical signals (6-12 months pre-announcement)

Test Set Size:
- Training set: 2015-2021 (calibration)
- Validation set: 2022-2023 (tuning)
- Test set: 2024 (final validation)
- Target: 100+ deals for statistical significance
```

#### Backtesting Process
```
For each historical deal:
1. Reconstruct company profile at T-12, T-6, T-3, T-1 months
2. Calculate M&A score using available data
3. Identify potential acquirers and match scores
4. Record score trajectory and signals
5. Compare predictions vs actual outcomes

Sliding Window Analysis:
- Calculate scores monthly for 24 months pre-acquisition
- Measure score evolution and signal timing
- Identify optimal "early warning" timeframe
```

### 6.2 Performance Metrics

#### Classification Metrics

```
Confusion Matrix (at score threshold = 60):

                  Predicted Acquired    Predicted Not Acquired
Actually Acquired        TP                      FN
Not Acquired            FP                      TN

Precision = TP / (TP + FP)
- "Of companies we flagged, what % were actually acquired?"
- Target: ≥30% (biotech M&A is noisy)

Recall = TP / (TP + FN)
- "Of all acquired companies, what % did we identify?"
- Target: ≥70%

F1 Score = 2 × (Precision × Recall) / (Precision + Recall)
- Target: ≥0.40

Specificity = TN / (TN + FP)
- "Of companies not acquired, what % did we correctly exclude?"
- Target: ≥60%
```

#### Ranking Metrics

```
Precision@K:
- Precision in top K scored companies
- Calculate for K = 10, 20, 50
- Target: P@10 ≥ 40%, P@20 ≥ 35%, P@50 ≥ 25%

Average Precision (AP):
AP = Σ(Precision@k × rel(k)) / total_relevant
where rel(k) = 1 if item k was acquired, 0 otherwise

Mean Average Precision (MAP):
- Average AP across all time periods
- Target: ≥0.35

Normalized Discounted Cumulative Gain (NDCG):
NDCG@K = DCG@K / IDCG@K

DCG@K = Σ(rel_i / log2(i+1)) for i=1 to K
where rel_i = relevance score (1 if acquired, 0 if not)

Target: NDCG@20 ≥ 0.45
```

#### Lead Time Analysis

```
Lead Time = announcement_date - first_alert_date

Calculate:
- Mean lead time (target: ≥3 months)
- Median lead time
- Distribution (25th, 50th, 75th percentiles)

Lead Time by Score Level:
- Score ≥80: Expected lead time 1-3 months
- Score 70-79: Expected lead time 3-6 months
- Score 60-69: Expected lead time 6-12 months

Lead Time Accuracy:
accuracy = |predicted_timeframe - actual_time| / actual_time
Target: 70% of deals within ±50% of predicted timeframe
```

### 6.3 Calibration Testing

Assess whether predicted probabilities match actual acquisition rates:

```
Calibration Plot:
- Bin companies by predicted probability (e.g., 0-10%, 10-20%, ...)
- Calculate actual acquisition rate in each bin
- Plot predicted vs actual

Perfect calibration: predicted = actual

Brier Score:
BS = (1/N) × Σ(predicted_prob - actual_outcome)²
where actual_outcome = 1 if acquired, 0 if not

Lower is better, target: <0.20

Expected Calibration Error (ECE):
ECE = Σ(|bin_confidence - bin_accuracy| × bin_weight)

Target: <0.10
```

### 6.4 Acquirer Matching Validation

```
Matching Accuracy Metrics:

Exact Match Rate:
- Actual acquirer in top 1 predicted: target ≥25%
- Actual acquirer in top 3 predicted: target ≥50%
- Actual acquirer in top 5 predicted: target ≥65%

Match Score Distribution:
For deals where acquirer was predicted:
- Mean match score: track trend
- Median match score: target ≥70
- Min match score in top 5: target ≥55

Therapeutic Area Accuracy:
- % deals where TA prediction matched actual: target ≥75%

Valuation Correlation:
correlation(predicted_valuation, actual_deal_value)
Target: r ≥ 0.60

Mean Absolute Percentage Error (MAPE):
MAPE = (1/N) × Σ|predicted - actual| / actual × 100%
Target: ≤40%
```

### 6.5 Component Score Analysis

Evaluate individual scoring factors:

```
Feature Importance:
- Calculate correlation of each factor with acquisition outcome
- Use logistic regression coefficients
- Compare to assigned weights

Factor Correlation with Outcome:
Calculate for each component score:
- Pearson correlation with binary outcome (acquired/not)
- Point-biserial correlation
- Target: all factors r ≥ 0.15

Component Predictive Power:
For each factor independently:
- AUC (Area Under ROC Curve)
- Target: all components AUC ≥ 0.60
- Combined model AUC target: ≥0.75

Weight Optimization:
Use backtesting to optimize weights:
- Grid search over weight combinations
- Constraint: weights sum to 100%
- Objective: maximize F1 score or MAP
- Validate on holdout set
```

### 6.6 Robustness Testing

```
Sensitivity Analysis:
Vary input parameters ±20% and measure score change:
- Cash runway: How sensitive is score?
- Clinical data: Impact of efficacy changes?
- Market cap: Effect of valuation shifts?

Target: No single parameter change >20% → score change >10 points

Missing Data Analysis:
Test performance with incomplete data:
- 10% missing: expected score accuracy ≥95%
- 25% missing: expected score accuracy ≥85%
- 50% missing: expected score accuracy ≥70%

Temporal Stability:
- Score volatility: Standard deviation of month-to-month changes
- Target: σ < 8 points for stable situations
- Flag if σ > 15 points (data quality issue)

Bias Testing:
Check for systematic biases:
- Therapeutic area bias (oncology vs others)
- Market cap bias (small vs mid vs large)
- Geography bias (US vs EU vs Asia)
- Time period bias (bull vs bear market)

Target: Performance variance across segments <15%
```

### 6.7 Continuous Monitoring

```
Model Performance Dashboard:

Daily Metrics:
- Scores calculated today
- Alerts generated
- Data freshness by source

Weekly Metrics:
- Score distribution (histogram)
- Top 20 companies tracked
- Alert accuracy (false positive rate)

Monthly Metrics:
- Precision/Recall on test set
- Score calibration check
- Component score distributions
- Data quality scores

Quarterly Metrics:
- Full backtest on new data
- Model drift detection
- Weight reoptimization
- Feature engineering review

Annual Metrics:
- Complete validation study
- Comparison to market benchmarks
- External audit of methodology
- Model version update decision

Model Drift Detection:
Compare current performance to baseline:
- AUC decline >5%: Warning
- AUC decline >10%: Retraining required
- Precision decline >10%: Investigation needed
- Mean score shift >5 points: Recalibration needed
```

### 6.8 Validation Success Criteria

```
Minimum Performance Requirements:

MUST MEET (System Launch):
- Recall ≥ 60%
- Precision ≥ 25%
- Mean lead time ≥ 2 months
- Top acquirer in top 5: ≥55%
- AUC ≥ 0.70
- Brier score ≤ 0.25

TARGET GOALS (6 months post-launch):
- Recall ≥ 70%
- Precision ≥ 30%
- Mean lead time ≥ 3 months
- Top acquirer in top 3: ≥50%
- AUC ≥ 0.75
- Brier score ≤ 0.20

STRETCH GOALS (12 months post-launch):
- Recall ≥ 75%
- Precision ≥ 35%
- Mean lead time ≥ 4 months
- Top acquirer in top 3: ≥60%
- AUC ≥ 0.80
- Brier score ≤ 0.18

Validation Gate for Production:
System proceeds to production only if:
✓ All MUST MEET criteria satisfied on test set
✓ No single metric <80% of MUST MEET threshold
✓ Data quality score ≥ 0.75
✓ Manual review of top 20 scored companies confirms reasonableness
✓ At least 3 recent deals (last 6 months) were flagged in advance
```

---

## 7. Implementation Notes

### 7.1 Score Calculation Frequency

```
Calculation Schedule:
- Real-time: When new signal detected (critical signals)
- Hourly: Market data updates
- Daily: Standard score recalculation (all companies)
- Weekly: Deep recalculation with data refresh
- Monthly: Full backfill with historical data

Optimization:
- Cache intermediate calculations
- Update only changed components when possible
- Full recalculation weekly or on manual trigger
```

### 7.2 Data Sources

```
Required Data Feeds:
- SEC EDGAR (10-K, 10-Q, 8-K, Form 4)
- ClinicalTrials.gov
- FDA databases (approvals, designations)
- Patent databases (USPTO, EPO)
- Market data (prices, volume)
- News feeds (Bloomberg, Reuters)
- Conference presentations
- Company investor relations

Data Quality Checks:
- Completeness validation
- Freshness monitoring
- Anomaly detection
- Cross-source verification
```

### 7.3 Scalability Considerations

```
Performance Targets:
- Score calculation: <5 seconds per company
- Full universe refresh (500 companies): <30 minutes
- Alert generation: <1 minute from signal detection
- Dashboard load: <2 seconds

Database Design:
- Time-series optimized for score history
- Indexed for fast acquirer matching
- Materialized views for dashboards
- Audit trail for all score changes
```

### 7.4 Governance & Auditability

```
Version Control:
- All scoring formulas versioned
- Weight changes logged
- Model updates documented
- Backtest results archived

Audit Trail:
- Every score calculation logged
- Data inputs recorded
- Alert decisions traceable
- Manual overrides documented

Review Process:
- Weekly: Data quality review
- Monthly: Performance metrics review
- Quarterly: Model validation
- Annual: Independent audit
```

---

## 8. Appendix

### 8.1 Glossary of Terms

| Term | Definition |
|------|------------|
| Asset | A drug candidate or development program |
| Catalyst | A major event that changes company valuation (clinical data, regulatory decision, etc.) |
| CIK | Central Index Key (SEC identifier) |
| Composite Score | Weighted combination of all scoring factors |
| DLT | Dose-limiting toxicity |
| FTO | Freedom to operate (patent perspective) |
| LEI | Legal Entity Identifier |
| MoA | Mechanism of action |
| ORR | Objective response rate |
| Patent Cliff | Expiration of patent protection on blockbuster drug |
| Signal | An event or data point indicating M&A likelihood |
| SOC | Standard of care |

### 8.2 Therapeutic Area Classifications

```
Primary Categories:
- Oncology
- Immunology
- Neurology
- Cardiology
- Rare/Orphan Diseases
- Infectious Diseases
- Metabolic Disorders
- Respiratory
- Dermatology
- Ophthalmology
- Other

Sub-categories (Oncology example):
- Solid tumors
  * Lung cancer
  * Breast cancer
  * Colorectal cancer
  * Prostate cancer
- Hematologic malignancies
  * Leukemia
  * Lymphoma
  * Multiple myeloma
```

### 8.3 Development Stage Definitions

| Stage | Description | Typical Duration | Success Rate |
|-------|-------------|------------------|--------------|
| Preclinical | Lab and animal studies | 3-6 years | ~10% |
| Phase 1 | First-in-human safety | 1-2 years | ~63% |
| Phase 2 | Efficacy in small patient group | 2-3 years | ~31% |
| Phase 3 | Large-scale efficacy/safety | 2-4 years | ~58% |
| NDA/BLA | Regulatory review | 0.5-2 years | ~85% |
| Approved | Market authorization granted | - | - |

### 8.4 Example Score Calculation

**Company:** BioTech Example Corp
**Ticker:** BTEC
**Market Cap:** $500M

**Component Scores:**
1. Clinical Pipeline Value: 75
   - Phase 2 oncology asset, positive data
   - First-in-class mechanism

2. Patent Position: 80
   - Composition of matter until 2040
   - No litigation

3. Cash Runway vs Catalyst: 90
   - 8 months runway
   - Phase 2 readout in 6 months

4. Management Signals: 70
   - Recent insider buying
   - Board added ex-Pfizer exec

5. Strategic Fit: 85
   - Matches 3 acquirers' focus areas
   - Fills pipeline gap for oncology

6. Competitive Landscape: 65
   - 4 competitors in indication
   - Best-in-class profile

7. Regulatory Pathway: 75
   - Orphan designation
   - Clear precedent

8. Historical Patterns: 70
   - Active M&A in therapeutic area

**Calculation:**
```
M&A_Score = (75 × 0.30) + (80 × 0.12) + (90 × 0.18) + (70 × 0.10) +
            (85 × 0.15) + (65 × 0.08) + (75 × 0.05) + (70 × 0.02)

= 22.5 + 9.6 + 16.2 + 7.0 + 12.75 + 5.2 + 3.75 + 1.4
= 78.4

Rounded: 78
Percentile: 89th
Tier: 2 (High Priority)
```

**Top Acquirer Matches:**
1. Pfizer (match score: 88) - Oncology focus, $4B patent cliff 2028
2. Merck (match score: 82) - Adjacent area, historical pattern
3. AstraZeneca (match score: 75) - Therapeutic alignment

**Estimated Probability:** 28%
**Alert Level:** HIGH
**Recommended Action:** Add to watchlist, monitor catalysts

---

## Document Control

**Revision History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-07 | System Architect | Initial specification |

**Review Schedule:**
- Next Review: 2026-01-07
- Review Frequency: Monthly (first 6 months), then quarterly

**Approval:**
- Technical Review: [ Pending ]
- Business Review: [ Pending ]
- Compliance Review: [ Pending ]

---

END OF SPECIFICATION
