# Drug DCF Valuation Model - User Guide

## Overview

This comprehensive DCF (Discounted Cash Flow) valuation model is specifically designed for biotech M&A prediction and drug pipeline analysis. It implements industry-standard valuation methodologies used by investment banks, private equity firms, and corporate development teams.

## Key Features

### 1. Risk-Adjusted NPV Calculations
- Probability of Success (PoS) adjustments by clinical phase
- Phase-specific discount rates (WACC)
- Therapeutic area multipliers for success rates
- Development cost modeling

### 2. Revenue Projection Models
Five distinct revenue curves for different drug types:
- **Standard**: Typical small molecule/biologic (5yr ramp, 3yr peak)
- **Blockbuster**: Major innovation (4yr ramp, 5yr peak, extended plateau)
- **Orphan**: Rare disease (3yr ramp, 7yr peak, sustained post-LOE)
- **Fast Follower**: Me-too drug (3yr ramp, 2yr peak, rapid decline)
- **Gene Therapy**: One-time treatment (2yr ramp, 8yr peak, durable)

### 3. Indication-Specific TAM
Total Addressable Market estimates by therapeutic area:
- **Oncology Solid Tumors**: $5-50B TAM
- **Oncology Hematology**: $3-25B TAM
- **Rare Disease**: $500M-2B TAM
- **Obesity/Metabolic**: $50-100B TAM (hot market)
- **CNS**: $10-30B TAM
- **Immunology**: $20-50B TAM
- **Cardiovascular**: $15-45B TAM
- **Infectious Disease**: $5-25B TAM

### 4. Pipeline Valuation
- Multi-asset portfolio valuation
- Sum-of-parts analysis
- Portfolio correlation adjustments
- Value by phase and indication breakdowns
- Top asset identification

### 5. M&A Analysis
- Market cap comparison
- Premium/discount calculation
- Implied acquisition value with control premium
- Target identification

## Quick Start

### Basic Single Drug Valuation

```python
from src.valuation import DrugDCF, ClinicalPhase, IndicationCategory

# Create DCF model for a Phase 2 oncology drug
dcf = DrugDCF(
    drug_name="ONC-123",
    peak_sales_estimate=2.5e9,  # $2.5B peak sales
    time_to_peak=5,
    patent_life_remaining=12,
    clinical_phase=ClinicalPhase.PHASE_2,
    indication_category=IndicationCategory.ONCOLOGY_SOLID,
    years_to_launch=4
)

# Calculate valuation
valuation = dcf.calculate_valuation()

print(f"Risk-Adjusted NPV: ${valuation.npv_risk_adjusted/1e9:.2f}B")
print(f"Probability of Success: {valuation.probability_of_success:.1%}")
print(f"Peak Sales: ${valuation.peak_sales/1e9:.2f}B")
```

### Pipeline Valuation

```python
from src.valuation import PipelineValuation, DrugCandidate

# Define pipeline
drugs = [
    DrugCandidate(
        name="Lead Asset",
        indication=IndicationCategory.ONCOLOGY_SOLID,
        clinical_phase=ClinicalPhase.PHASE_3,
        peak_sales=4.0e9,
        years_to_launch=2
    ),
    DrugCandidate(
        name="Second Asset",
        indication=IndicationCategory.RARE_DISEASE,
        clinical_phase=ClinicalPhase.PHASE_2,
        peak_sales=1.2e9,
        years_to_launch=4
    )
]

# Value portfolio
pipeline = PipelineValuation(drugs=drugs)
summary = pipeline.value_pipeline()

print(f"Total Pipeline Value: ${summary.risk_adjusted_value/1e9:.2f}B")
print(f"Drug Count: {summary.drug_count}")
```

### Sensitivity Analysis

```python
# Run sensitivity on key variables
sensitivity = dcf.sensitivity_analysis()

# Results show NPV at different peak sales levels
for result in sensitivity['peak_sales']:
    print(f"Peak ${result['value']/1e9:.1f}B -> NPV ${result['npv_risk_adjusted']/1e9:.2f}B")
```

### Scenario Analysis

```python
# Generate bear, base, bull scenarios
scenarios = dcf.scenario_analysis()

print(f"Bear: ${scenarios['bear'].npv_risk_adjusted/1e9:.2f}B")
print(f"Base: ${scenarios['base'].npv_risk_adjusted/1e9:.2f}B")
print(f"Bull: ${scenarios['bull'].npv_risk_adjusted/1e9:.2f}B")
```

## Model Components

### Core DCF Engine (`dcf_model.py`)

**DrugDCF Class**
- Main valuation engine
- Projects revenues using specified curve type
- Calculates operating cash flows with cost structure
- Computes NPV with appropriate discount rate
- Applies probability of success adjustment

**Key Methods:**
- `project_revenues()`: Generate revenue projections
- `calculate_npv()`: Discount cash flows to present value
- `apply_pos_adjustment()`: Risk-adjust for clinical success
- `calculate_valuation()`: Full DCF calculation
- `sensitivity_analysis()`: Test key variable ranges
- `scenario_analysis()`: Bear/base/bull modeling

### Revenue Projections (`drug_revenue.py`)

**RevenueProjector Class**
- Implements multiple revenue curve models
- S-curve ramp to peak
- Plateau at peak sales
- Gradual pre-LOE decline
- Patent cliff at loss of exclusivity
- Post-LOE generic erosion

**Helper Functions:**
- `estimate_peak_sales()`: Calculate peak based on TAM and share
- `project_standard_curve()`: Standard biotech curve
- `project_blockbuster_curve()`: High-value drug curve
- `project_orphan_curve()`: Rare disease curve
- `calculate_revenue_metrics()`: Key revenue statistics

### Industry Assumptions (`assumptions.py`)

**Probability of Success by Phase:**
- Preclinical: 5-10% (typical: 7.5%)
- Phase 1: 15-20% (typical: 17.5%)
- Phase 2: 25-35% (typical: 30%)
- Phase 3: 50-70% (typical: 60%)
- NDA Filed: 85-95% (typical: 90%)
- Approved: 100%

**Discount Rates (WACC):**
- Preclinical Biotech: 15-25% (typical: 18%)
- Clinical Stage: 12-18% (typical: 15%)
- Late Stage: 10-15% (typical: 12%)
- Commercial: 8-12% (typical: 10%)
- Big Pharma: 7-11% (typical: 9%)

**Cost Structure:**
- COGS: 15-40% depending on modality
- R&D: 15-40% depending on stage
- SG&A: 5-35% depending on commercialization
- Tax Rate: 15-20% effective

### Pipeline Valuation (`pipeline_valuation.py`)

**PipelineValuation Class**
- Values multiple drugs simultaneously
- Aggregates to sum-of-parts
- Applies portfolio correlation adjustments
- Breaks down value by phase and indication
- Identifies top value drivers

**Key Methods:**
- `value_single_drug()`: Value one asset
- `value_pipeline()`: Full portfolio valuation
- `calculate_sum_of_parts()`: Simple aggregation
- `compare_to_market_cap()`: M&A premium analysis
- `get_valuation_by_phase()`: Phase breakdown
- `get_top_assets()`: Identify key drivers

## Typical Use Cases

### 1. M&A Target Screening

```python
# Screen biotech for acquisition
pipeline = PipelineValuation(drugs=target_pipeline)
summary = pipeline.value_pipeline()

# Compare to market cap
comparison = pipeline.compare_to_market_cap(market_cap=3.0e9)

if comparison['premium_discount'] > 0.30:  # >30% undervalued
    print(f"Attractive M&A target: {comparison['premium_discount']:.1%} discount")
    print(f"Implied acquisition: ${comparison['implied_acquisition_value']/1e9:.2f}B")
```

### 2. Pipeline Prioritization

```python
# Identify highest-value assets
top_assets = pipeline.get_top_assets(n=3)

for i, asset in enumerate(top_assets, 1):
    print(f"#{i}: {asset.drug_name} - ${asset.npv_risk_adjusted/1e9:.2f}B NPV")
```

### 3. Investment Decision Support

```python
# Evaluate investment at different prices
scenarios = dcf.scenario_analysis()

# If investing at $500M
investment = 500e6
base_return = scenarios['base'].npv_risk_adjusted / investment
bull_return = scenarios['bull'].npv_risk_adjusted / investment

print(f"Base Case MOIC: {base_return:.1f}x")
print(f"Bull Case MOIC: {bull_return:.1f}x")
```

### 4. Deal Valuation

```python
# Value a licensing or acquisition deal
dcf = DrugDCF(
    drug_name="In-License Asset",
    peak_sales_estimate=3.0e9,
    clinical_phase=ClinicalPhase.PHASE_2,
    # ... other params
)

valuation = dcf.calculate_valuation()

# Typical deal: pay 10-20% of risk-adjusted NPV upfront
upfront_payment = valuation.npv_risk_adjusted * 0.15
print(f"Fair upfront: ${upfront_payment/1e6:.1f}M")
```

## Advanced Features

### Custom Revenue Curves

```python
from src.valuation import RevenueProjector, RevenueCurveType

# Use custom parameters
custom_params = {
    'ramp_years': 6,  # Longer ramp
    'peak_years': 4,
    'decline_start_year': 10,
    'patent_cliff_multiplier': 0.40
}

projector = RevenueProjector(
    peak_sales=2.0e9,
    curve_type=RevenueCurveType.STANDARD,
    custom_params=custom_params
)

revenues = projector.project_revenues(years_to_launch=3)
```

### Custom Development Costs

```python
# Specify actual development costs by year
development_costs = [
    30e6,  # Year 1: Phase 2 start
    50e6,  # Year 2: Phase 2 expansion
    80e6,  # Year 3: Phase 3 start
    100e6, # Year 4: Phase 3 completion
]

dcf = DrugDCF(
    # ... standard params
    development_costs=development_costs
)
```

### Portfolio Correlation Adjustment

```python
# Adjust correlation factor based on portfolio diversity
pipeline = PipelineValuation(
    drugs=drugs,
    apply_correlation_adjustment=True,
    correlation_factor=0.70  # Lower correlation = more diverse
)

# Lower correlation -> higher diversification benefit
```

## Export and Integration

### Export to JSON

```python
# Export single drug valuation
valuation.save_to_file('/path/to/valuation.json')

# Export pipeline
summary.save_to_file('/path/to/pipeline.json')
```

### Integration with Other Modules

```python
# Use with M&A predictor
from src.valuation import DrugDCF, estimate_peak_sales
from src.models.ma_predictor import MAPredictionModel

# Value target's pipeline
dcf_value = pipeline.value_pipeline()

# Compare to M&A predictor output
ma_probability = ma_model.predict(company_features)

# Combined analysis
if ma_probability > 0.70 and dcf_value.implied_premium > 0.30:
    print("High probability M&A target with attractive valuation")
```

## Model Validation

The model uses industry-standard assumptions validated against:
- BIO Clinical Development Success Rates Study
- MIT CBER Pharmaceutical Development Statistics
- Investment banking M&A comparable transaction analysis
- Public biotech company valuations and market multiples

## Limitations and Considerations

1. **Simplified Cost Structure**: Uses percentage-of-revenue for costs rather than detailed bottom-up build
2. **Platform Value**: Does not separately value platform technology or follow-on indications
3. **Synergies**: Does not model acquirer-specific synergies in M&A scenarios
4. **Regulatory Risk**: PoS captures average regulatory risk, not drug-specific issues
5. **Commercial Risk**: Assumes successful launch if approved; doesn't model launch failures
6. **Competition**: Revenue curves assume competitive dynamics but don't model specific competitors

## Best Practices

1. **Use Sensitivity Analysis**: Always run sensitivity to understand valuation range
2. **Scenario Modeling**: Bear/base/bull provides probability-weighted expectations
3. **Cross-Check TAM**: Validate TAM estimates against published market research
4. **Adjust PoS**: Override default PoS if drug has specific risk factors
5. **Consider Correlation**: Adjust correlation factor based on pipeline diversity
6. **Compare to Comps**: Validate DCF output against comparable M&A transactions
7. **Export Results**: Save valuations for documentation and audit trail

## Examples

See `/examples/dcf_valuation_example.py` for comprehensive examples including:
1. Single drug valuation
2. Sensitivity analysis
3. Scenario modeling
4. Pipeline valuation
5. M&A premium analysis
6. JSON export

Run examples:
```bash
cd /Users/waiyang/Desktop/repo/biotech-ma-predictor
python examples/dcf_valuation_example.py
```

## Support

For questions or issues with the DCF model, see:
- Model documentation in source code docstrings
- Example implementations in `/examples`
- Industry assumptions reference in `assumptions.py`
