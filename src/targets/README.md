# Target Identification Engine

Comprehensive system for identifying, screening, and ranking potential biotech acquisition targets.

## Overview

The Target Identification Engine implements a sophisticated multi-stage process to identify the most attractive biotech M&A targets:

1. **Screening** - Filter companies by market cap, pipeline stage, financial health, and therapeutic area
2. **Ranking** - Score targets using 12 weighted factors (6 original + 6 new)
3. **Analysis** - Generate detailed profiles with valuations and acquirer matches
4. **Watchlist** - Create ranked watchlists with deal probabilities and predictions

## Components

### TargetScreener (`screener.py`)

Filters companies using configurable criteria:

```python
from targets import TargetScreener, ScreeningCriteria

criteria = ScreeningCriteria(
    min_market_cap=500_000_000,  # $500M
    max_market_cap=50_000_000_000,  # $50B
    min_phase=DevelopmentPhase.PHASE_2,
    max_cash_runway_months=36,  # Pressure sweet spot
    priority_areas=[
        TherapeuticArea.OBESITY_GLP1,
        TherapeuticArea.ONCOLOGY_ADC,
        TherapeuticArea.RADIOPHARMACEUTICALS
    ]
)

screener = TargetScreener(criteria)
results = screener.batch_screen(companies)
```

### TargetRanker (`ranker.py`)

Ranks targets using 12-factor composite scoring model:

**Original 6 Factors:**
1. Pipeline Quality (10%)
2. Market Cap Fit (8%)
3. Cash Runway (10%)
4. Therapeutic Area (9%)
5. Clinical Stage (8%)
6. Financial Distress (5%)

**New 6 Factors:**
7. Scientific Differentiation (12%)
8. Acquisition Tension (10%)
9. Strategic Acquirer Fit (10%)
10. Data Catalyst Timing (8%)
11. Competitive Landscape (6%)
12. Deal Structure Feasibility (4%)

```python
from targets import TargetRanker, RankingWeights

ranker = TargetRanker()
ranked_targets = ranker.rank_targets(companies, top_n=20)

for target in ranked_targets:
    print(f"{target.rank}. {target.name}: {target.composite_score:.1f}/100")
```

### WatchlistManager (`watchlist.py`)

Manages acquisition target watchlists:

```python
from targets import WatchlistManager, AcquisitionTarget

manager = WatchlistManager()
watchlist = manager.create_watchlist(
    name="Q1 2025 Hot Targets",
    description="Top acquisition candidates",
    targets=targets
)

# Filter by therapeutic area
obesity_targets = watchlist.filter_by_area(['obesity_glp1'])

# Filter by acquirer
jnj_targets = watchlist.filter_by_acquirer('Johnson & Johnson')

# Export
manager.export_watchlist('Q1 2025 Hot Targets', 'output.json', format='json')
```

### TargetIdentifier (`identifier.py`)

Main orchestration engine:

```python
from targets import TargetIdentifier

identifier = TargetIdentifier()

# Generate watchlist from company universe
watchlist = identifier.identify_targets(company_data, top_n=20)

# Or generate sample watchlist with realistic data
sample_watchlist = identifier.generate_sample_watchlist()

# Access top targets
top_10 = watchlist.get_top_n(10)
```

## Data Structures

### AcquisitionTarget

Complete target profile with predictions:

```python
@dataclass
class AcquisitionTarget:
    # Identity
    ticker: str
    name: str
    therapeutic_area: str
    lead_asset: str
    development_stage: str

    # Financials
    market_cap: float
    cash_position: float
    cash_runway_months: float

    # M&A Metrics
    ma_score: float  # 0-100 composite
    rank: int
    percentile: float

    # Predictions
    deal_probability_12mo: float
    estimated_deal_value: ValuationRange
    implied_premium: float

    # Acquirers
    likely_acquirers: List[AcquirerMatch]
    top_acquirer: AcquirerMatch

    # Context
    upcoming_catalysts: List[DataCatalyst]
    investment_thesis: str
```

### AcquirerMatch

Potential acquirer with strategic fit:

```python
@dataclass
class AcquirerMatch:
    name: str
    acquirer_type: AcquirerType
    strategic_fit_score: float  # 0-100
    rationale: str
    probability: float  # 0-1
    estimated_premium: float
```

## Hot Therapeutic Areas (2024-2025)

The engine prioritizes these high-activity areas:

1. **Obesity/GLP-1** - Hottest area; oral formulations, dual/triple agonists
2. **Oncology ADC** - Antibody-drug conjugates, bispecifics
3. **Radiopharmaceuticals** - Radioligand therapies for cancer
4. **Autoimmune** - Novel mechanisms, complement inhibitors
5. **CNS/Neuropsychiatry** - Recent mega-deals (Cerevel, Karuna)
6. **Rare Disease** - Orphan drugs, gene therapies

## Example Targets (From Sample Data)

**Top Obesity/GLP-1 Targets:**
- Structure Therapeutics (GPCR) - Oral GLP-1
- Viking Therapeutics (VKTX) - GLP-1/GIP dual agonist
- Altimmune (ALT) - GLP-1/glucagon dual agonist

**Top Oncology ADC Targets:**
- Elevation Oncology (ELEV) - NRG1+ cancers
- Compass Therapeutics (CMPX) - Bispecifics

**Top Radioligand Targets:**
- Fusion Pharmaceuticals (FUSN) - Radioconjugates
- Aura Biosciences (AURA) - Virus-like drug conjugates

**Top CNS Targets:**
- Praxis Precision (PRAX) - Essential tremor (Phase 3)
- Sage Therapeutics (SAGE) - Depression (approved)

## Screening Sweet Spots

The algorithm identifies these ideal profiles:

1. **Market Cap**: $1B - $15B (digestible for Big Pharma)
2. **Cash Runway**: 12-24 months (pressure but not desperate)
3. **Stage**: Phase 2/3 (de-risked but pre-approval)
4. **Stock**: -20% to -40% decline (distressed but not broken)
5. **Therapeutic Area**: Hot markets with Big Pharma gaps

## Usage Example

```python
from targets import TargetIdentifier

# Initialize engine
identifier = TargetIdentifier()

# Generate sample watchlist
watchlist = identifier.generate_sample_watchlist()

# View statistics
stats = watchlist.get_statistics()
print(f"Total targets: {stats['total_targets']}")
print(f"Average M&A score: {stats['avg_ma_score']:.1f}")
print(f"High probability deals: {stats['high_probability_targets']}")

# Get top targets
for target in watchlist.get_top_n(5):
    print(f"\n{target.rank}. {target.name} ({target.ticker})")
    print(f"   M&A Score: {target.ma_score:.1f}/100")
    print(f"   Deal Probability: {target.deal_probability_12mo*100:.0f}%")
    print(f"   Top Acquirer: {target.top_acquirer.name}")
    print(f"   {target.investment_thesis}")

# Export results
identifier.watchlist_manager.watchlists['current'] = watchlist
identifier.watchlist_manager.export_watchlist(
    'current',
    'target_watchlist.json',
    format='json'
)
```

## Running the Demo

```bash
python examples/generate_target_watchlist.py
```

This generates:
- Console report with top 10 targets
- JSON export (`output/target_watchlist.json`)
- CSV export (`output/target_watchlist.csv`)
- Text report (`output/target_watchlist_report.txt`)

## Customization

### Custom Screening Criteria

```python
criteria = ScreeningCriteria(
    min_market_cap=2_000_000_000,  # $2B minimum
    max_market_cap=20_000_000_000,  # $20B maximum
    min_phase=DevelopmentPhase.PHASE_3,  # Phase 3+ only
    max_cash_runway_months=18,  # High pressure
    priority_areas=[TherapeuticArea.OBESITY_GLP1]  # Focus area
)

screener = TargetScreener(criteria)
```

### Custom Ranking Weights

```python
weights = RankingWeights(
    # Emphasize scientific differentiation
    scientific_differentiation=0.20,
    pipeline_quality=0.15,
    acquisition_tension=0.15,
    # ... other weights (must sum to 1.0)
)

ranker = TargetRanker(weights)
```

## Output Formats

### JSON Export
```json
{
  "name": "Top 20 Targets",
  "targets": [
    {
      "ticker": "GPCR",
      "name": "Structure Therapeutics",
      "therapeutic_area": "obesity_glp1",
      "ma_score": 87.5,
      "rank": 1,
      "deal_probability_12mo": 0.65,
      "top_acquirer": "Novo Nordisk (95% fit)"
    }
  ]
}
```

### CSV Export
Columns: Ticker, Name, Therapeutic Area, Market Cap, M&A Score, Rank, Deal Probability, Top Acquirer

## Integration

Integrate with other modules:

```python
from predictor import M_A_Predictor
from targets import TargetIdentifier

# Identify targets
identifier = TargetIdentifier()
watchlist = identifier.generate_sample_watchlist()

# Run detailed predictions on top targets
predictor = M_A_Predictor()

for target in watchlist.get_top_n(10):
    company_data = {...}  # Get company data
    prediction = predictor.predict_acquisition(company_data)
    print(f"{target.name}: {prediction['acquisition_probability']:.1%}")
```

## Performance Notes

- Screening: O(n) - linear with number of companies
- Ranking: O(n log n) - dominated by sorting
- Typical performance: ~1000 companies/second on modern hardware

## Future Enhancements

1. **Real-time data integration** - SEC filings, clinical trials, news
2. **Machine learning** - Train on historical M&A outcomes
3. **Event monitoring** - Automated catalyst tracking
4. **Competitive intelligence** - Track acquirer portfolios
5. **Deal prediction models** - Regression for deal value estimation
