# Target Identification Engine - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    TARGET IDENTIFICATION ENGINE                  │
└─────────────────────────────────────────────────────────────────┘

Input: Company Universe (Real-time data or samples)
    │
    ├─> Market data (price, market cap)
    ├─> Financial data (cash, burn rate)
    ├─> Pipeline data (assets, phases)
    └─> Strategic data (partnerships, events)
    
    ↓
    
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1: SCREENING                        (screener.py)         │
├──────────────────────────────────────────────────────────────────┤
│  • Market Cap Filter: $500M - $50B                              │
│  • Pipeline Requirements: Phase 2+, lead asset                   │
│  • Financial Health: 12-36 month cash runway                     │
│  • Therapeutic Area: Hot markets (obesity, ADC, etc.)            │
│  • Geographic: North America, Europe, Asia                       │
│  • Exclusions: Royalty cos, recent IPOs, preclinical only        │
└──────────────────────────────────────────────────────────────────┘
    
    ↓ Passed Companies
    
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2: RANKING                          (ranker.py)           │
├──────────────────────────────────────────────────────────────────┤
│  12-Factor Composite Scoring:                                    │
│                                                                   │
│  ORIGINAL 6 FACTORS (50%):                                       │
│  ├─ Pipeline Quality (10%)                                       │
│  ├─ Market Cap Fit (8%)                                          │
│  ├─ Cash Runway (10%)                                            │
│  ├─ Therapeutic Area (9%)                                        │
│  ├─ Clinical Stage (8%)                                          │
│  └─ Financial Distress (5%)                                      │
│                                                                   │
│  NEW 6 FACTORS (50%):                                            │
│  ├─ Scientific Differentiation (12%)                             │
│  ├─ Acquisition Tension (10%)                                    │
│  ├─ Strategic Acquirer Fit (10%)                                 │
│  ├─ Data Catalyst Timing (8%)                                    │
│  ├─ Competitive Landscape (6%)                                   │
│  └─ Deal Structure Feasibility (4%)                              │
│                                                                   │
│  Output: Composite M&A Score (0-100)                             │
└──────────────────────────────────────────────────────────────────┘
    
    ↓ Ranked Targets
    
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 3: ANALYSIS                         (identifier.py)       │
├──────────────────────────────────────────────────────────────────┤
│  For each target:                                                 │
│  • Match likely acquirers by therapeutic area                    │
│  • Calculate strategic fit scores                                │
│  • Estimate deal probabilities (12mo, 24mo)                      │
│  • Generate valuation ranges with premiums                       │
│  • Identify upcoming data catalysts                              │
│  • Create investment thesis                                      │
│  • Highlight key strengths/weaknesses                            │
└──────────────────────────────────────────────────────────────────┘
    
    ↓ Analyzed Targets
    
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 4: WATCHLIST GENERATION             (watchlist.py)        │
├──────────────────────────────────────────────────────────────────┤
│  • Create ranked watchlist                                        │
│  • Calculate statistics and insights                             │
│  • Generate reports (text, JSON, CSV)                            │
│  • Support filtering and export                                  │
└──────────────────────────────────────────────────────────────────┘
    
    ↓
    
Output: Ranked Watchlist with Predictions
    │
    ├─> JSON export (structured data)
    ├─> CSV export (spreadsheet)
    ├─> Text report (human-readable)
    └─> API objects (programmatic access)
```

## Module Structure

```
biotech-ma-predictor/
│
├── src/targets/
│   ├── __init__.py              # Public API exports
│   ├── screener.py              # Screening engine
│   ├── ranker.py                # Ranking engine
│   ├── watchlist.py             # Data structures
│   └── identifier.py            # Orchestration + sample data
│
├── examples/
│   ├── generate_target_watchlist.py   # Main demo
│   └── find_obesity_targets.py        # Area-specific demo
│
├── docs/
│   ├── TARGET_IDENTIFICATION_GUIDE.md  # Quick start
│   └── SYSTEM_ARCHITECTURE.md          # This file
│
├── output/
│   ├── target_watchlist.json          # Generated output
│   ├── target_watchlist.csv           # Generated output
│   └── target_watchlist_report.txt    # Generated output
│
└── TARGET_IDENTIFICATION_SUMMARY.md   # Overview
```

## Data Flow Diagram

```
┌─────────────┐
│   Company   │
│   Universe  │
└──────┬──────┘
       │
       ├──────> [CompanyProfile]
       │         - ticker, name
       │         - market_cap
       │         - pipeline
       │         - financials
       │
       ↓
┌──────────────────┐
│ TargetScreener   │
│ .screen_company()│
└──────┬───────────┘
       │
       ├──> Market Cap Check
       ├──> Pipeline Check
       ├──> Financial Check
       ├──> Strategic Check
       └──> Exclusions Check
       │
       ↓ (if passed)
┌──────────────────┐
│  TargetRanker    │
│  .rank_targets() │
└──────┬───────────┘
       │
       ├──> Calculate 12 factor scores
       ├──> Weight factors
       ├──> Generate composite score
       └──> Sort by score
       │
       ↓
┌────────────────────┐
│ TargetIdentifier   │
│ .identify_targets()│
└──────┬─────────────┘
       │
       ├──> Match acquirers
       ├──> Predict probabilities
       ├──> Estimate valuations
       └──> Generate thesis
       │
       ↓
┌──────────────────┐
│ RankedWatchlist  │
└──────┬───────────┘
       │
       ├──> [AcquisitionTarget] objects
       │     - Full profile
       │     - Predictions
       │     - Acquirer matches
       │
       ↓
┌──────────────────┐
│WatchlistManager  │
│ .export()        │
└──────┬───────────┘
       │
       ├──> JSON file
       ├──> CSV file
       └──> Text report
```

## Class Hierarchy

```
Data Classes (watchlist.py):
├── ValuationRange
│   ├── low: float
│   ├── base: float
│   ├── high: float
│   └── format_range() → str
│
├── AcquirerMatch
│   ├── name: str
│   ├── strategic_fit_score: float
│   ├── probability: float
│   └── rationale: str
│
├── DataCatalyst
│   ├── event_type: str
│   ├── expected_date: date
│   └── days_until() → int
│
└── AcquisitionTarget
    ├── ticker, name, description
    ├── market_cap, cash_position
    ├── ma_score, rank, percentile
    ├── factor_scores: Dict
    ├── likely_acquirers: List[AcquirerMatch]
    └── estimated_deal_value: ValuationRange

Engine Classes:
├── TargetScreener (screener.py)
│   ├── __init__(criteria: ScreeningCriteria)
│   ├── screen_company(company) → (bool, List[str])
│   └── batch_screen(companies) → Dict
│
├── TargetRanker (ranker.py)
│   ├── __init__(weights: RankingWeights)
│   ├── calculate_composite_score(company) → float
│   └── rank_targets(companies) → List[RankedTarget]
│
├── TargetIdentifier (identifier.py)
│   ├── __init__(criteria, weights)
│   ├── identify_targets(universe) → RankedWatchlist
│   └── generate_sample_watchlist() → RankedWatchlist
│
└── WatchlistManager (watchlist.py)
    ├── create_watchlist(name, targets)
    ├── export_watchlist(name, filepath, format)
    └── generate_report(name) → str
```

## Scoring Algorithm Detail

```
For each company:

1. Calculate individual factor scores (0-100):
   
   Pipeline Quality:
   ├─ Number of assets × 10 (max 30 pts)
   ├─ Lead asset phase (10-85 pts)
   └─ Data quality (0-36 pts)
   
   Market Cap Fit:
   ├─ $1B-$5B: 100 pts (sweet spot)
   ├─ $5B-$10B: 90 pts
   └─ Other ranges scaled
   
   Cash Runway:
   ├─ 12-18 months: 100 pts (max pressure)
   ├─ 18-24 months: 90 pts
   └─ Other ranges scaled
   
   ... (all 12 factors)

2. Apply weights:
   
   composite_score = Σ(factor_score[i] × weight[i])
   
   where weights sum to 1.0

3. Rank by composite score:
   
   Sort descending by composite_score
   Assign rank = position (1, 2, 3, ...)
   Calculate percentile = (n - rank + 1) / n × 100

4. Generate insights:
   
   key_strengths = top 3 factors (score ≥ 70)
   key_weaknesses = bottom 3 factors (score ≤ 50)
   investment_thesis = template based on scores
```

## Acquirer Matching Logic

```
Therapeutic Area → Likely Acquirers:

obesity_glp1:
├─ Novo Nordisk (95% fit) - "Leader in metabolic disease"
├─ Eli Lilly (90% fit) - "Strong GLP-1 portfolio"
├─ Roche (75% fit) - "Expanding metabolic franchise"
└─ AstraZeneca (70% fit) - "Cardiometabolic focus"

oncology_adc:
├─ Daiichi Sankyo (95% fit) - "ADC pioneer and leader"
├─ AbbVie (85% fit) - "Building ADC portfolio"
├─ Merck (80% fit) - "Expanding beyond Keytruda"
└─ Gilead (75% fit) - "Oncology growth strategy"

radiopharmaceuticals:
├─ Novartis (90% fit) - "Radioligand leader (Pluvicto)"
├─ Eli Lilly (85% fit) - "Recent radioligand entry"
└─ BMS (75% fit) - "Diversifying oncology"

... (all 10 therapeutic areas)
```

## Deal Probability Calculation

```
Base Probability = (MA_Score / 100) × 0.5

Adjustments:
├─ Cash runway < 15 months: +20%
├─ Cash runway < 24 months: +15%
├─ Stock return < -40%: +10%
├─ Has activist investor: +15%
└─ Has takeover rumors: +10%

Final Probability = min(base + adjustments, 0.85)

24-Month Probability = min(12-month × 1.6, 0.95)
```

## Export Formats

### JSON Structure
```json
{
  "name": "Watchlist Name",
  "targets": [
    {
      "ticker": "ABCD",
      "name": "Company Name",
      "ma_score": 85.5,
      "rank": 1,
      "deal_probability_12mo": 0.65,
      "top_acquirer": "Big Pharma (95% fit)",
      "estimated_deal_value": "$2.0B - $3.0B"
    }
  ],
  "statistics": {
    "total_targets": 20,
    "avg_ma_score": 70.5,
    "high_probability_targets": 12
  }
}
```

### CSV Structure
```
Ticker,Name,Therapeutic Area,Market Cap,M&A Score,Rank,Deal Probability,...
ABCD,Company Name,obesity_glp1,2000000000,85.5,1,0.65,...
```

## Performance Characteristics

```
Screening:
├─ Time Complexity: O(n)
├─ Space Complexity: O(n)
└─ Throughput: ~1000 companies/sec

Ranking:
├─ Time Complexity: O(n log n) [sorting]
├─ Space Complexity: O(n)
└─ Throughput: ~500 companies/sec

Full Pipeline:
├─ Time Complexity: O(n log n)
├─ Bottleneck: Sorting in ranking
└─ Typical: <1 sec for 1000 companies
```

## Extension Points

```
1. Data Sources:
   ├─ SEC EDGAR API → Financial data
   ├─ ClinicalTrials.gov → Pipeline data
   ├─ Yahoo Finance → Stock data
   └─ News APIs → Event detection

2. Machine Learning:
   ├─ Historical deals → Train probability models
   ├─ Feature engineering → Better factors
   └─ Ensemble methods → Combine predictions

3. Real-time Monitoring:
   ├─ Price alerts → Track targets
   ├─ News monitoring → Event detection
   └─ Insider trading → Signal detection

4. Advanced Analytics:
   ├─ Monte Carlo → Deal simulations
   ├─ Network analysis → Acquirer mapping
   └─ Scenario planning → "What if" analysis
```

## Integration Architecture

```
┌─────────────────────────────────────────────────┐
│         External Systems                         │
├─────────────────────────────────────────────────┤
│  • SEC EDGAR (financial filings)                │
│  • ClinicalTrials.gov (pipeline data)            │
│  • Yahoo Finance / Bloomberg (stock data)        │
│  • PubMed / BioRxiv (scientific data)            │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────┐
│         Data Ingestion Layer                     │
├─────────────────────────────────────────────────┤
│  • API clients                                   │
│  • Data parsers                                  │
│  • Data validation                               │
│  • Update scheduling                             │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────┐
│         Target Identification Engine             │
├─────────────────────────────────────────────────┤
│  • Screener                                      │
│  • Ranker                                        │
│  • Identifier                                    │
│  • Watchlist Manager                             │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────┐
│         Output & Integration                     │
├─────────────────────────────────────────────────┤
│  • JSON/CSV export                               │
│  • Database storage                              │
│  • REST API                                      │
│  • Dashboard/UI                                  │
│  • Alert system                                  │
└─────────────────────────────────────────────────┘
```

## Conclusion

The Target Identification Engine provides a sophisticated, modular architecture for biotech M&A target identification. The four-stage pipeline (Screen → Rank → Analyze → Export) efficiently processes company data through configurable filters and scoring algorithms to produce actionable watchlists with detailed predictions and strategic insights.
