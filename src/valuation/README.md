# Biotech Drug DCF Valuation Model

## Quick Start

```python
from src.valuation import DrugDCF, ClinicalPhase, IndicationCategory

# Value a Phase 2 oncology drug
dcf = DrugDCF(
    drug_name="ONC-123",
    peak_sales_estimate=2.5e9,
    clinical_phase=ClinicalPhase.PHASE_2,
    indication_category=IndicationCategory.ONCOLOGY_SOLID,
    years_to_launch=4
)

valuation = dcf.calculate_valuation()
print(f"NPV: ${valuation.npv_risk_adjusted/1e9:.2f}B")
```

## Files

- **`dcf_model.py`**: Core DCF engine with NPV calculations
- **`drug_revenue.py`**: Revenue projection models and TAM estimates
- **`assumptions.py`**: Industry benchmarks (PoS, WACC, cost structure)
- **`pipeline_valuation.py`**: Multi-drug portfolio valuation

## Key Classes

### DrugDCF
Core DCF valuation for single drugs.

**Key Parameters:**
- `peak_sales_estimate`: Expected peak annual sales
- `clinical_phase`: Development phase (affects PoS and discount rate)
- `indication_category`: Therapeutic area (affects TAM and PoS)
- `years_to_launch`: Time to market
- `patent_life_remaining`: Patent protection from launch

**Key Methods:**
- `calculate_valuation()`: Full DCF with risk adjustment
- `sensitivity_analysis()`: Test key variable ranges
- `scenario_analysis()`: Bear/base/bull cases

### PipelineValuation
Portfolio-level valuation for multi-asset companies.

**Key Parameters:**
- `drugs`: List of DrugCandidate objects
- `apply_correlation_adjustment`: Portfolio diversification benefit

**Key Methods:**
- `value_pipeline()`: Sum-of-parts valuation
- `compare_to_market_cap()`: M&A premium analysis
- `get_top_assets()`: Identify value drivers

## Revenue Curves

### Standard
Typical biotech drug:
- 5 year ramp to peak
- 3 year peak plateau
- Gradual decline to LOE
- 30% retention post-patent

### Blockbuster
Major innovation:
- 4 year ramp (faster adoption)
- 5 year peak (extended plateau)
- 25% retention post-patent

### Orphan
Rare disease:
- 3 year ramp (small patient population)
- 7 year peak (stable market)
- 50% retention (less generic competition)

### Fast Follower
Me-too drug:
- 3 year ramp
- 2 year peak (short window)
- 20% retention (heavy competition)

### Gene Therapy
One-time treatment:
- 2 year ramp (limited patients)
- 8 year peak (durable)
- 60% retention (unique modality)

## Probability of Success

Industry-standard PoS by phase:

| Phase         | PoS (Typical) | Range      |
|---------------|---------------|------------|
| Preclinical   | 7.5%          | 5-10%      |
| Phase 1       | 17.5%         | 15-20%     |
| Phase 2       | 30%           | 25-35%     |
| Phase 3       | 60%           | 50-70%     |
| NDA Filed     | 90%           | 85-95%     |
| Approved      | 100%          | -          |

Therapeutic area multipliers:
- Oncology Solid: 0.85x (harder)
- Rare Disease: 1.15x (easier, smaller trials)
- CNS: 0.75x (challenging endpoints)

## Discount Rates (WACC)

| Company Stage      | Typical | Range     |
|-------------------|---------|-----------|
| Preclinical       | 18%     | 15-25%    |
| Clinical Stage    | 15%     | 12-18%    |
| Late Stage        | 12%     | 10-15%    |
| Commercial        | 10%     | 8-12%     |
| Big Pharma        | 9%      | 7-11%     |

## TAM by Indication

| Indication          | Typical TAM | Range       |
|--------------------|-------------|-------------|
| Oncology Solid     | $20B        | $5-50B      |
| Rare Disease       | $1B         | $500M-2B    |
| Obesity/Metabolic  | $75B        | $50-100B    |
| CNS                | $20B        | $10-30B     |
| Immunology         | $35B        | $20-50B     |

## Common Use Cases

### 1. M&A Target Screening
```python
pipeline = PipelineValuation(drugs=target_drugs)
summary = pipeline.value_pipeline()
comparison = pipeline.compare_to_market_cap(market_cap)

if comparison['premium_discount'] > 0.30:
    print("Undervalued - attractive M&A target")
```

### 2. Deal Valuation
```python
valuation = dcf.calculate_valuation()
upfront = valuation.npv_risk_adjusted * 0.15  # 15% of NPV
print(f"Fair upfront: ${upfront/1e6:.0f}M")
```

### 3. Portfolio Prioritization
```python
top_assets = pipeline.get_top_assets(n=3)
for asset in top_assets:
    print(f"{asset.drug_name}: ${asset.npv_risk_adjusted/1e9:.2f}B")
```

### 4. Sensitivity Testing
```python
scenarios = dcf.scenario_analysis()
print(f"Range: ${scenarios['bear'].npv_risk_adjusted/1e9:.2f}B")
print(f"    to ${scenarios['bull'].npv_risk_adjusted/1e9:.2f}B")
```

## Examples

See `/examples/dcf_valuation_example.py` for comprehensive examples:

```bash
python examples/dcf_valuation_example.py
```

Includes:
1. Single drug valuation
2. Sensitivity analysis
3. Bear/base/bull scenarios
4. Pipeline valuation
5. M&A premium analysis
6. JSON export

## Model Assumptions

Based on:
- BIO Clinical Development Success Rates
- MIT CBER Pharma Statistics
- Investment banking M&A analyses
- Public biotech valuations

## Export Results

```python
# Save to JSON
valuation.save_to_file('valuation.json')
summary.save_to_file('pipeline.json')

# Convert to dict
data = valuation.to_dict()
```

## Documentation

Full documentation: `/docs/DCF_MODEL_GUIDE.md`

## Integration

Works with other biotech-ma-predictor modules:

```python
from src.valuation import PipelineValuation
from src.models.ma_predictor import MAPredictionModel

# Value pipeline
pipeline_value = pipeline.value_pipeline()

# Predict M&A probability
ma_prob = ma_model.predict(features)

# Combined signal
if ma_prob > 0.70 and pipeline_value.implied_premium > 0.30:
    print("High-probability undervalued M&A target")
```
