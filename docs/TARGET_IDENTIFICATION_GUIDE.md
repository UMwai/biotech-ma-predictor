# Target Identification Engine - Quick Start Guide

## Overview

The Target Identification Engine is a comprehensive system for finding and ranking potential biotech M&A targets using sophisticated screening and scoring algorithms.

## Quick Start

### Generate Sample Watchlist

```bash
python examples/generate_target_watchlist.py
```

This creates:
- Console report with top 10 detailed targets
- `output/target_watchlist.json` - Full watchlist in JSON
- `output/target_watchlist.csv` - Spreadsheet format
- `output/target_watchlist_report.txt` - Text report

### Basic Python Usage

```python
from targets import TargetIdentifier

# Initialize identifier
identifier = TargetIdentifier()

# Generate sample watchlist with realistic data
watchlist = identifier.generate_sample_watchlist()

# View top 5 targets
for target in watchlist.get_top_n(5):
    print(f"{target.rank}. {target.ticker}: {target.name}")
    print(f"   M&A Score: {target.ma_score:.1f}/100")
    print(f"   Deal Probability: {target.deal_probability_12mo*100:.0f}%")
    print(f"   Top Acquirer: {target.top_acquirer.name}")
```

## Key Features

### 1. Multi-Stage Screening

Filters companies by:
- **Market Cap**: $500M - $50B (configurable)
- **Pipeline Stage**: Phase 2+ preferred
- **Cash Runway**: 12-36 months (sweet spot)
- **Therapeutic Area**: Hot sectors (obesity, ADC, radioligand, etc.)
- **Financial Health**: Distressed but viable

### 2. 12-Factor Ranking

**Original 6 Factors (50% weight):**
1. Pipeline Quality (10%)
2. Market Cap Fit (8%)
3. Cash Runway (10%)
4. Therapeutic Area (9%)
5. Clinical Stage (8%)
6. Financial Distress (5%)

**New 6 Factors (50% weight):**
7. Scientific Differentiation (12%)
8. Acquisition Tension (10%)
9. Strategic Acquirer Fit (10%)
10. Data Catalyst Timing (8%)
11. Competitive Landscape (6%)
12. Deal Structure Feasibility (4%)

### 3. Acquirer Matching

Automatically identifies likely acquirers based on:
- Therapeutic area fit
- Portfolio gaps
- Strategic priorities
- Recent M&A activity

### 4. Deal Predictions

Generates:
- 12-month and 24-month deal probabilities
- Valuation ranges with premiums
- Catalyst timing
- Investment thesis

## Hot Therapeutic Areas (2024-2025)

### 1. Obesity / GLP-1
**Why Hot:** Massive market opportunity, oral formulations valuable
**Sample Targets:**
- Structure Therapeutics (GPCR) - Oral GLP-1
- Viking Therapeutics (VKTX) - Dual agonist
- Altimmune (ALT) - GLP-1/glucagon

**Top Acquirers:** Novo Nordisk, Eli Lilly, Roche, AstraZeneca

### 2. Oncology ADC
**Why Hot:** Multiple recent mega-deals, validated modality
**Sample Targets:**
- Elevation Oncology (ELEV) - NRG1+ cancers
- Compass Therapeutics (CMPX) - Bispecifics
- IGM Biosciences (IGMS) - IgM platform

**Top Acquirers:** Daiichi Sankyo, AbbVie, Merck, Gilead

### 3. Radiopharmaceuticals
**Why Hot:** Novartis Pluvicto success, Eli Lilly entry
**Sample Targets:**
- Fusion Pharmaceuticals (FUSN) - Radioconjugates
- Aura Biosciences (AURA) - VDC platform

**Top Acquirers:** Novartis, Eli Lilly, Bristol Myers Squibb

### 4. Autoimmune
**Why Hot:** Novel mechanisms, post-Humira gaps
**Sample Targets:**
- Annexon Biosciences (ANNX) - Complement
- Xencor (XNCR) - Engineered antibodies

**Top Acquirers:** Johnson & Johnson, AbbVie, Amgen, UCB

### 5. CNS / Neuropsychiatry
**Why Hot:** Recent mega-deals (Cerevel $8.7B, Karuna $14B)
**Sample Targets:**
- Praxis Precision (PRAX) - Essential tremor
- Sage Therapeutics (SAGE) - Depression

**Top Acquirers:** AbbVie, Bristol Myers Squibb, Takeda

### 6. Rare Disease
**Why Hot:** Orphan designations, premium valuations
**Sample Targets:**
- Krystal Biotech (KRYS) - Gene therapy
- Theratechnologies (TBPH) - Metabolic rare disease

**Top Acquirers:** Sanofi, Takeda, BioMarin, Ultragenyx

## Sample Output

### Top Target Example

```
RANK #1 - REPL: Replimune Group
M&A SCORE: 69.2/100 (Top 100%)
Therapeutic Area: Oncology ADC
Lead Asset: RP1 (Phase 3)
Market Cap: $1.15B
Cash Runway: 21 months

DEAL PREDICTIONS:
  12-Month Probability: 50%
  Estimated Deal Value: $1.50B - $2.07B (50% premium)

MOST LIKELY ACQUIRER:
  Daiichi Sankyo (Big Pharma)
  Strategic Fit: 95/100
  Rationale: ADC pioneer and leader

KEY STRENGTHS:
  + Market Cap Fit (100/100)
  + Clinical Stage (95/100)
  + Pipeline Quality (94/100)

INVESTMENT THESIS:
  Replimune Group is a $1.1B oncology ADC company with a
  Phase 3 lead asset. Strategic fit and timing make it an
  attractive M&A target.
```

## Advanced Usage

### Custom Screening Criteria

```python
from targets import TargetScreener, ScreeningCriteria, TherapeuticArea

# Focus on distressed obesity targets
criteria = ScreeningCriteria(
    min_market_cap=500_000_000,
    max_market_cap=5_000_000_000,
    max_cash_runway_months=18,  # Financial pressure
    priority_areas=[TherapeuticArea.OBESITY_GLP1],
    min_stock_decline_52w=-50  # Down 50%+
)

screener = TargetScreener(criteria)
```

### Custom Ranking Weights

```python
from targets import TargetRanker, RankingWeights

# Emphasize science over financials
weights = RankingWeights(
    scientific_differentiation=0.18,
    pipeline_quality=0.14,
    acquisition_tension=0.12,
    strategic_acquirer_fit=0.12,
    therapeutic_area=0.10,
    cash_runway=0.08,
    clinical_stage=0.08,
    data_catalyst_timing=0.08,
    market_cap_fit=0.06,
    competitive_landscape=0.04,
    # ... (must sum to 1.0)
)

ranker = TargetRanker(weights)
```

### Filter Watchlist

```python
# Get obesity targets only
obesity_targets = watchlist.filter_by_area(['obesity_glp1'])

# Get targets for specific acquirer
jnj_targets = watchlist.filter_by_acquirer('Johnson & Johnson')

# Get high-probability targets
high_prob = [t for t in watchlist.targets
             if t.deal_probability_12mo >= 0.5]
```

### Export Options

```python
from targets import WatchlistManager

manager = WatchlistManager()
manager.watchlists['my_list'] = watchlist

# JSON export
manager.export_watchlist('my_list', 'output.json', format='json')

# CSV export
manager.export_watchlist('my_list', 'output.csv', format='csv')

# Text report
report = manager.generate_report('my_list')
print(report)
```

## Understanding the Scores

### M&A Score (0-100)
Composite score combining all 12 factors. Interpretation:
- **80-100**: Exceptional target, high probability
- **70-79**: Strong target, good probability
- **60-69**: Solid target, moderate probability
- **50-59**: Possible target, lower probability
- **<50**: Unlikely target

### Deal Probability (0-1)
Estimated probability of acquisition in next 12 months:
- **>60%**: Very likely
- **40-60%**: Likely
- **20-40%**: Possible
- **<20%**: Unlikely

### Strategic Fit (0-100)
How well target fits acquirer's needs:
- **90-100**: Perfect fit, strategic imperative
- **80-89**: Strong fit, attractive target
- **70-79**: Good fit, makes sense
- **60-69**: Moderate fit, opportunistic
- **<60**: Weak fit

## Acquisition Sweet Spots

The algorithm identifies these ideal profiles for M&A:

| Factor | Sweet Spot | Why |
|--------|-----------|-----|
| Market Cap | $1B - $15B | Digestible, material impact |
| Cash Runway | 12-24 months | Pressure without desperation |
| Stage | Phase 2/3 | De-risked but pre-commercial |
| Stock Performance | -20% to -40% | Distressed but not broken |
| Therapeutic Area | Hot markets | Big Pharma portfolio gaps |
| Pipeline | 2-5 assets | Focused but diversified |
| Data Catalysts | 3-9 months | Acquisition timing window |

## Real-World Context

### Recent Comparable Deals (2023-2024)

**CNS:**
- Cerevel → AbbVie: $8.7B (2023)
- Karuna → Bristol Myers: $14B (2023)

**Radiopharmaceuticals:**
- RayzeBio → BMS: $4.1B (2023)

**Autoimmune:**
- Ventyx → J&J: $1.25B (2024)

**Oncology:**
- Imago → Merck: $1.35B (2023)

### Typical Premiums
- **Phase 2**: 40-60% premium
- **Phase 3**: 50-80% premium
- **Approved (small)**: 30-50% premium
- **Distressed**: 20-40% premium
- **Competitive bidding**: 60-100%+ premium

## Tips for Best Results

1. **Focus on hot therapeutic areas** - Where Big Pharma is actively buying
2. **Look for cash runway pressure** - 12-24 months creates urgency
3. **Phase 2/3 sweet spot** - De-risked enough but not too expensive
4. **Check for catalysts** - Near-term data creates decision points
5. **Multiple acquirer options** - Competitive tension drives premiums
6. **Novel mechanisms** - Scientific differentiation commands premium
7. **Portfolio gap filling** - Strategic fit is critical

## Limitations

- Sample data is illustrative (use real-time data in production)
- Probabilities are estimates, not guarantees
- Market conditions change rapidly
- Regulatory/antitrust considerations not fully modeled
- Management willingness to sell is unknown

## Integration with Other Modules

```python
from predictor import M_A_Predictor
from targets import TargetIdentifier

# Identify targets
identifier = TargetIdentifier()
watchlist = identifier.generate_sample_watchlist()

# Run detailed predictions on top targets
predictor = M_A_Predictor()

for target in watchlist.get_top_n(10):
    company_data = {
        'market_cap': target.market_cap,
        'therapeutic_area': target.therapeutic_area,
        # ... more fields
    }

    prediction = predictor.predict_acquisition(company_data)

    print(f"{target.ticker}: {prediction['acquisition_probability']:.1%}")
```

## Next Steps

1. Run the demo: `python examples/generate_target_watchlist.py`
2. Review the output in `output/` directory
3. Customize screening criteria for your focus
4. Adjust ranking weights based on your strategy
5. Integrate real-time data sources
6. Track targets over time
7. Monitor for catalyst events

## Support Files

- Full documentation: `/src/targets/README.md`
- Source code: `/src/targets/`
- Examples: `/examples/generate_target_watchlist.py`
- Output samples: `/output/`

## Questions?

Review the detailed module READMEs:
- `/src/targets/README.md` - Full technical documentation
- `/src/targets/screener.py` - Screening implementation
- `/src/targets/ranker.py` - Ranking algorithm details
- `/src/targets/watchlist.py` - Data structures
- `/src/targets/identifier.py` - Orchestration engine
