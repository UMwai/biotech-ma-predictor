# Drug DCF Valuation - Quick Start

## Installation

No additional dependencies required. The DCF model uses only Python standard library.

## 1-Minute Quick Start

```python
from src.valuation import DrugDCF, ClinicalPhase, IndicationCategory

# Value a Phase 2 oncology drug
dcf = DrugDCF(
    drug_name="Drug-X",
    peak_sales_estimate=2.5e9,  # $2.5B peak
    clinical_phase=ClinicalPhase.PHASE_2,
    indication_category=IndicationCategory.ONCOLOGY_SOLID,
    years_to_launch=4
)

val = dcf.calculate_valuation()
print(f"NPV: ${val.npv_risk_adjusted/1e9:.2f}B")
# Output: NPV: $0.25B
```

## Run Examples

```bash
# See 6 comprehensive examples
python examples/dcf_valuation_example.py

# Run all tests (28 tests)
python -m pytest tests/test_dcf_model.py -v
```

## Common Use Cases

### 1. M&A Target Screening
```python
from src.valuation import PipelineValuation, DrugCandidate

# Define target's pipeline
drugs = [
    DrugCandidate("Lead", IndicationCategory.ONCOLOGY_SOLID,
                  ClinicalPhase.PHASE_3, peak_sales=4e9, years_to_launch=2),
    DrugCandidate("Backup", IndicationCategory.RARE_DISEASE,
                  ClinicalPhase.PHASE_2, peak_sales=1.2e9, years_to_launch=4)
]

# Value pipeline
pipeline = PipelineValuation(drugs=drugs)
summary = pipeline.value_pipeline()

# Compare to market cap
comparison = pipeline.compare_to_market_cap(market_cap=2.5e9)

if comparison['premium_discount'] > 0.30:
    print(f"ATTRACTIVE TARGET: {comparison['premium_discount']:.1%} undervalued")
    print(f"Suggested bid: ${comparison['implied_acquisition_value']/1e9:.2f}B")
```

### 2. Sensitivity Analysis
```python
sensitivity = dcf.sensitivity_analysis()

# See how NPV changes with peak sales
for result in sensitivity['peak_sales']:
    print(f"Peak ${result['value']/1e9:.1f}B -> NPV ${result['npv_risk_adjusted']/1e9:.2f}B")
```

### 3. Scenario Modeling
```python
scenarios = dcf.scenario_analysis()

print(f"Bear:  ${scenarios['bear'].npv_risk_adjusted/1e9:.2f}B")
print(f"Base:  ${scenarios['base'].npv_risk_adjusted/1e9:.2f}B")
print(f"Bull:  ${scenarios['bull'].npv_risk_adjusted/1e9:.2f}B")
```

## Key Parameters

### Clinical Phases
- `ClinicalPhase.PRECLINICAL` - 7.5% PoS
- `ClinicalPhase.PHASE_1` - 17.5% PoS
- `ClinicalPhase.PHASE_2` - 30% PoS
- `ClinicalPhase.PHASE_3` - 60% PoS
- `ClinicalPhase.NDA_FILED` - 90% PoS
- `ClinicalPhase.APPROVED` - 100% PoS

### Indications (with TAM)
- `IndicationCategory.ONCOLOGY_SOLID` - $5-50B
- `IndicationCategory.RARE_DISEASE` - $500M-2B
- `IndicationCategory.OBESITY_METABOLIC` - $50-100B
- `IndicationCategory.CNS` - $10-30B
- `IndicationCategory.IMMUNOLOGY` - $20-50B

### Revenue Curves
- `RevenueCurveType.STANDARD` - Typical biotech (5yr ramp)
- `RevenueCurveType.BLOCKBUSTER` - Major drug (4yr ramp, extended peak)
- `RevenueCurveType.ORPHAN` - Rare disease (3yr ramp, sustained)
- `RevenueCurveType.GENE_THERAPY` - One-time treatment (durable)

## Estimate Peak Sales from TAM

```python
from src.valuation import estimate_peak_sales, IndicationCategory

peak = estimate_peak_sales(
    indication=IndicationCategory.RARE_DISEASE,
    market_share=0.30  # 30% market share
)
# Returns: ~$300M (30% of $1B typical rare disease TAM)
```

## Export Results

```python
# Save to JSON
valuation.save_to_file('valuation.json')
summary.save_to_file('pipeline.json')

# Or get as dict
data = valuation.to_dict()
```

## Documentation

- **Full Guide**: `/docs/DCF_MODEL_GUIDE.md`
- **API Reference**: `/src/valuation/README.md`
- **Summary**: `/DCF_MODEL_SUMMARY.md`
- **Examples**: `/examples/dcf_valuation_example.py`

## Files Created

```
src/valuation/
├── __init__.py              # Module exports
├── dcf_model.py             # Core DCF engine
├── drug_revenue.py          # Revenue projections
├── assumptions.py           # Industry benchmarks
├── pipeline_valuation.py    # Portfolio valuation
└── README.md                # Quick reference

docs/
└── DCF_MODEL_GUIDE.md       # Comprehensive guide

examples/
└── dcf_valuation_example.py # 6 examples

tests/
└── test_dcf_model.py        # 28 unit tests
```

## Next Steps

1. Run examples: `python examples/dcf_valuation_example.py`
2. Read guide: `docs/DCF_MODEL_GUIDE.md`
3. Start valuing your biotech targets!

## Support

All classes have comprehensive docstrings. Use Python's help:

```python
from src.valuation import DrugDCF
help(DrugDCF)
help(DrugDCF.calculate_valuation)
```
