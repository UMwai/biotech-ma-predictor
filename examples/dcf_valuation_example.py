"""
DCF Valuation Model - Comprehensive Examples

This script demonstrates how to use the biotech DCF valuation model
for M&A prediction and drug portfolio analysis.

Examples include:
1. Single drug valuation
2. Sensitivity analysis
3. Scenario modeling (bear/base/bull)
4. Pipeline valuation (multi-asset portfolio)
5. M&A premium analysis
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.valuation import (
    DrugDCF,
    PipelineValuation,
    DrugCandidate,
    ClinicalPhase,
    IndicationCategory,
    TherapeuticArea,
    RevenueCurveType,
    estimate_peak_sales,
)


def example_1_single_drug_valuation():
    """
    Example 1: Value a single Phase 2 oncology asset.

    Scenario: Small biotech with a promising Phase 2 solid tumor oncology
    drug targeting a $20B TAM with expected 15% market share.
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Single Drug DCF Valuation")
    print("="*80)

    # Estimate peak sales based on TAM and market share
    peak_sales = estimate_peak_sales(
        indication=IndicationCategory.ONCOLOGY_SOLID,
        market_share=0.15,  # 15% market share
        use_typical_tam=True
    )

    print(f"\nDrug Profile:")
    print(f"  Indication: Solid Tumor Oncology")
    print(f"  Clinical Phase: Phase 2")
    print(f"  Expected Peak Sales: ${peak_sales/1e9:.2f}B")
    print(f"  Years to Launch: 4 years")
    print(f"  Patent Life: 13 years from launch")

    # Create DCF model
    dcf = DrugDCF(
        drug_name="ONC-123",
        peak_sales_estimate=peak_sales,
        time_to_peak=5,
        patent_life_remaining=13,
        clinical_phase=ClinicalPhase.PHASE_2,
        therapeutic_area=TherapeuticArea.ONCOLOGY_SOLID,
        indication_category=IndicationCategory.ONCOLOGY_SOLID,
        revenue_curve_type=RevenueCurveType.STANDARD,
        years_to_launch=4,
    )

    # Calculate valuation
    valuation = dcf.calculate_valuation()

    print(f"\nValuation Results:")
    print(f"  Probability of Success: {valuation.probability_of_success:.1%}")
    print(f"  Discount Rate (WACC): {valuation.discount_rate:.1%}")
    print(f"  Unadjusted NPV: ${valuation.npv_unadjusted/1e9:.2f}B")
    print(f"  Risk-Adjusted NPV: ${valuation.npv_risk_adjusted/1e9:.2f}B")
    print(f"  Peak Sales Multiple: {valuation.peak_multiple:.2f}x")
    print(f"  Years to Peak: {valuation.years_to_peak}")

    # Show first 10 years of revenue projection
    print(f"\nRevenue Projection (first 10 years):")
    for year, revenue in enumerate(valuation.annual_revenues[:10]):
        print(f"  Year {year}: ${revenue/1e9:.2f}B")

    return valuation


def example_2_sensitivity_analysis():
    """
    Example 2: Sensitivity analysis on key variables.

    Tests how valuation changes with different assumptions about:
    - Peak sales estimates
    - Discount rates
    - Probability of success
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Sensitivity Analysis")
    print("="*80)

    # Base case: Phase 3 rare disease drug
    dcf = DrugDCF(
        drug_name="RARE-456",
        peak_sales_estimate=1.2e9,
        time_to_peak=4,
        patent_life_remaining=14,
        clinical_phase=ClinicalPhase.PHASE_3,
        therapeutic_area=TherapeuticArea.RARE_DISEASE,
        indication_category=IndicationCategory.RARE_DISEASE,
        revenue_curve_type=RevenueCurveType.ORPHAN,
        years_to_launch=2,
    )

    print(f"\nBase Case Valuation:")
    base_val = dcf.calculate_valuation()
    print(f"  Risk-Adjusted NPV: ${base_val.npv_risk_adjusted/1e9:.2f}B")

    # Run sensitivity analysis
    print(f"\nSensitivity Analysis:")
    sensitivity = dcf.sensitivity_analysis()

    # Peak Sales Sensitivity
    print(f"\n  Peak Sales Sensitivity:")
    for result in sensitivity['peak_sales']:
        peak = result['value']
        npv = result['npv_risk_adjusted']
        print(f"    Peak Sales ${peak/1e9:.2f}B -> NPV ${npv/1e9:.2f}B")

    # Discount Rate Sensitivity
    print(f"\n  Discount Rate Sensitivity:")
    for result in sensitivity['discount_rate']:
        rate = result['value']
        npv = result['npv_risk_adjusted']
        print(f"    WACC {rate:.1%} -> NPV ${npv/1e9:.2f}B")

    # Probability of Success Sensitivity
    print(f"\n  Probability of Success Sensitivity:")
    for result in sensitivity['probability_of_success']:
        pos = result['value']
        npv = result['npv_risk_adjusted']
        print(f"    PoS {pos:.1%} -> NPV ${npv/1e9:.2f}B")


def example_3_scenario_analysis():
    """
    Example 3: Bear, Base, Bull scenario modeling.

    Models three scenarios for a major obesity drug (hot market).
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Scenario Analysis (Bear/Base/Bull)")
    print("="*80)

    print(f"\nDrug Profile: Obesity/Metabolic Disease")
    print(f"  Phase: Phase 2")
    print(f"  Market: $75B TAM (hot market like GLP-1s)")
    print(f"  Expected Market Share: 10%")

    # Base case: blockbuster obesity drug
    peak_sales = estimate_peak_sales(
        indication=IndicationCategory.OBESITY_METABOLIC,
        market_share=0.10,  # 10% of huge market
        use_typical_tam=True
    )

    dcf = DrugDCF(
        drug_name="OBE-789",
        peak_sales_estimate=peak_sales,
        time_to_peak=4,
        patent_life_remaining=12,
        clinical_phase=ClinicalPhase.PHASE_2,
        therapeutic_area=TherapeuticArea.OBESITY_METABOLIC,
        indication_category=IndicationCategory.OBESITY_METABOLIC,
        revenue_curve_type=RevenueCurveType.BLOCKBUSTER,
        years_to_launch=3,
    )

    # Run scenarios
    scenarios = dcf.scenario_analysis()

    print(f"\nScenario Results:")
    print(f"\n  BEAR CASE (Conservative):")
    bear = scenarios['bear']
    print(f"    Peak Sales: ${bear.peak_sales/1e9:.2f}B")
    print(f"    PoS: {bear.probability_of_success:.1%}")
    print(f"    Discount Rate: {bear.discount_rate:.1%}")
    print(f"    Risk-Adjusted NPV: ${bear.npv_risk_adjusted/1e9:.2f}B")

    print(f"\n  BASE CASE (Expected):")
    base = scenarios['base']
    print(f"    Peak Sales: ${base.peak_sales/1e9:.2f}B")
    print(f"    PoS: {base.probability_of_success:.1%}")
    print(f"    Discount Rate: {base.discount_rate:.1%}")
    print(f"    Risk-Adjusted NPV: ${base.npv_risk_adjusted/1e9:.2f}B")

    print(f"\n  BULL CASE (Optimistic):")
    bull = scenarios['bull']
    print(f"    Peak Sales: ${bull.peak_sales/1e9:.2f}B")
    print(f"    PoS: {bull.probability_of_success:.1%}")
    print(f"    Discount Rate: {bull.discount_rate:.1%}")
    print(f"    Risk-Adjusted NPV: ${bull.npv_risk_adjusted/1e9:.2f}B")

    print(f"\n  Valuation Range: ${bear.npv_risk_adjusted/1e9:.2f}B - ${bull.npv_risk_adjusted/1e9:.2f}B")


def example_4_pipeline_valuation():
    """
    Example 4: Multi-drug pipeline valuation.

    Values a diversified biotech with 4 drugs across different phases
    and indications - typical M&A target.
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Pipeline Valuation (Multi-Asset Portfolio)")
    print("="*80)

    # Define a realistic biotech pipeline
    pipeline_drugs = [
        # Lead asset: Phase 3 oncology drug
        DrugCandidate(
            name="Lead-001 (Oncology)",
            indication=IndicationCategory.ONCOLOGY_SOLID,
            clinical_phase=ClinicalPhase.PHASE_3,
            peak_sales=3.5e9,
            years_to_launch=2,
            therapeutic_area=TherapeuticArea.ONCOLOGY_SOLID,
            revenue_curve_type=RevenueCurveType.STANDARD,
            patent_life_remaining=13,
        ),

        # Second asset: Phase 2 rare disease
        DrugCandidate(
            name="RARE-002 (Rare Disease)",
            indication=IndicationCategory.RARE_DISEASE,
            clinical_phase=ClinicalPhase.PHASE_2,
            peak_sales=1.2e9,
            years_to_launch=4,
            therapeutic_area=TherapeuticArea.RARE_DISEASE,
            revenue_curve_type=RevenueCurveType.ORPHAN,
            patent_life_remaining=14,
        ),

        # Third asset: Phase 2 immunology
        DrugCandidate(
            name="IMM-003 (Immunology)",
            indication=IndicationCategory.IMMUNOLOGY,
            clinical_phase=ClinicalPhase.PHASE_2,
            peak_sales=2.0e9,
            years_to_launch=4,
            therapeutic_area=TherapeuticArea.IMMUNOLOGY,
            revenue_curve_type=RevenueCurveType.STANDARD,
            patent_life_remaining=13,
        ),

        # Early asset: Phase 1 CNS
        DrugCandidate(
            name="CNS-004 (Neurology)",
            indication=IndicationCategory.CNS,
            clinical_phase=ClinicalPhase.PHASE_1,
            peak_sales=1.5e9,
            years_to_launch=6,
            therapeutic_area=TherapeuticArea.CNS,
            revenue_curve_type=RevenueCurveType.STANDARD,
            patent_life_remaining=15,
        ),
    ]

    print(f"\nPipeline Overview:")
    for drug in pipeline_drugs:
        print(f"  {drug.name}")
        print(f"    Phase: {drug.clinical_phase.value}")
        print(f"    Peak Sales: ${drug.peak_sales/1e9:.2f}B")
        print(f"    Launch: {drug.years_to_launch} years")

    # Create pipeline valuation
    pipeline = PipelineValuation(
        drugs=pipeline_drugs,
        company_name="BioTech Innovations Inc.",
        apply_correlation_adjustment=True,
        correlation_factor=0.85  # Moderate correlation
    )

    # Value the pipeline
    summary = pipeline.value_pipeline()

    print(f"\n{'='*60}")
    print(f"PORTFOLIO VALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Number of Assets: {summary.drug_count}")
    print(f"  Sum-of-Parts Value: ${summary.total_pipeline_value/1e9:.2f}B")
    print(f"  Correlation-Adjusted Value: ${summary.risk_adjusted_value/1e9:.2f}B")
    print(f"  Top Asset Concentration: {summary.top_asset_concentration:.1%}")

    # Individual drug values
    print(f"\n{'='*60}")
    print(f"INDIVIDUAL ASSET VALUATIONS")
    print(f"{'='*60}")
    for val in summary.drug_valuations:
        print(f"\n  {val.drug_name}")
        print(f"    Phase: {val.clinical_phase}")
        print(f"    Peak Sales: ${val.peak_sales/1e9:.2f}B")
        print(f"    PoS: {val.probability_of_success:.1%}")
        print(f"    Unadjusted NPV: ${val.npv_unadjusted/1e9:.2f}B")
        print(f"    Risk-Adjusted NPV: ${val.npv_risk_adjusted/1e9:.2f}B")

    # Breakdown by phase
    print(f"\n{'='*60}")
    print(f"VALUE BY DEVELOPMENT PHASE")
    print(f"{'='*60}")
    by_phase = pipeline.get_valuation_by_phase()
    for phase, data in by_phase.items():
        print(f"  {phase}:")
        print(f"    Asset Count: {data['count']}")
        print(f"    Total Value: ${data['value']/1e9:.2f}B")
        print(f"    Assets: {', '.join(data['drugs'])}")

    # Breakdown by indication
    print(f"\n{'='*60}")
    print(f"VALUE BY THERAPEUTIC AREA")
    print(f"{'='*60}")
    by_indication = pipeline.get_valuation_by_indication()
    for indication, data in by_indication.items():
        print(f"  {indication}:")
        print(f"    Asset Count: {data['count']}")
        print(f"    Total Value: ${data['value']/1e9:.2f}B")

    return pipeline, summary


def example_5_ma_premium_analysis():
    """
    Example 5: M&A premium/discount analysis.

    Compares DCF valuation to market cap to determine if company
    is over/undervalued and estimate acquisition premium.
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: M&A Premium Analysis")
    print("="*80)

    # Use the pipeline from Example 4
    pipeline_drugs = [
        DrugCandidate(
            name="Lead Asset",
            indication=IndicationCategory.ONCOLOGY_SOLID,
            clinical_phase=ClinicalPhase.PHASE_3,
            peak_sales=4.0e9,
            years_to_launch=2,
            patent_life_remaining=13,
        ),
        DrugCandidate(
            name="Second Asset",
            indication=IndicationCategory.RARE_DISEASE,
            clinical_phase=ClinicalPhase.PHASE_2,
            peak_sales=1.5e9,
            years_to_launch=4,
            revenue_curve_type=RevenueCurveType.ORPHAN,
            patent_life_remaining=14,
        ),
    ]

    pipeline = PipelineValuation(drugs=pipeline_drugs)
    summary = pipeline.value_pipeline()

    # Current market cap (hypothetical)
    market_cap = 2.5e9  # $2.5B market cap

    print(f"\nCompany Metrics:")
    print(f"  Current Market Cap: ${market_cap/1e9:.2f}B")
    print(f"  DCF Pipeline Value: ${summary.risk_adjusted_value/1e9:.2f}B")

    # Compare to market cap
    comparison = pipeline.compare_to_market_cap(market_cap)

    print(f"\nM&A Analysis:")
    print(f"  Pipeline Value: ${comparison['pipeline_value']/1e9:.2f}B")
    print(f"  Current Market Cap: ${comparison['market_cap']/1e9:.2f}B")
    print(f"  Premium/Discount: {comparison['premium_discount']:+.1%}")

    if comparison['premium_discount'] > 0:
        print(f"    -> Company appears UNDERVALUED by {comparison['premium_discount']:.1%}")
        print(f"    -> Attractive M&A target")
    else:
        print(f"    -> Company appears OVERVALUED by {abs(comparison['premium_discount']):.1%}")
        print(f"    -> Premium valuation, less attractive for M&A")

    print(f"\n  Implied Acquisition Value (with 40% control premium):")
    print(f"    ${comparison['implied_acquisition_value']/1e9:.2f}B")
    print(f"    This represents {comparison['implied_acquisition_value']/market_cap:.1f}x current market cap")

    # Top assets analysis
    print(f"\n{'='*60}")
    print(f"TOP ASSETS (Primary Value Drivers)")
    print(f"{'='*60}")
    top_assets = pipeline.get_top_assets(n=2)
    for i, asset in enumerate(top_assets, 1):
        print(f"\n  #{i}: {asset.drug_name}")
        print(f"    Indication: {asset.indication}")
        print(f"    Phase: {asset.clinical_phase}")
        print(f"    Risk-Adjusted NPV: ${asset.npv_risk_adjusted/1e9:.2f}B")
        print(f"    % of Total Pipeline: {(asset.npv_risk_adjusted/summary.risk_adjusted_value)*100:.1f}%")


def example_6_export_to_json():
    """
    Example 6: Export valuations to JSON for further analysis.
    """
    print("\n" + "="*80)
    print("EXAMPLE 6: Export Valuations to JSON")
    print("="*80)

    # Simple single drug valuation
    dcf = DrugDCF(
        drug_name="EXPORT-001",
        peak_sales_estimate=2.0e9,
        clinical_phase=ClinicalPhase.PHASE_2,
        indication_category=IndicationCategory.ONCOLOGY_SOLID,
        years_to_launch=3,
    )

    valuation = dcf.calculate_valuation()

    # Export to JSON string
    json_output = valuation.to_json(indent=2)

    print(f"\nValuation exported to JSON:")
    print(json_output[:500] + "...")  # Show first 500 chars

    # Could save to file:
    # valuation.save_to_file('/path/to/valuation.json')

    print(f"\nJSON export includes:")
    print(f"  - Drug name and indication")
    print(f"  - Clinical phase")
    print(f"  - All revenue projections")
    print(f"  - NPV calculations (adjusted and unadjusted)")
    print(f"  - Key assumptions used")
    print(f"\nThis can be imported into Excel, BI tools, or other analysis systems")


def main():
    """Run all examples."""
    print("\n")
    print("="*80)
    print(" BIOTECH DCF VALUATION MODEL - COMPREHENSIVE EXAMPLES")
    print(" For M&A Prediction and Drug Portfolio Analysis")
    print("="*80)

    # Run all examples
    example_1_single_drug_valuation()
    example_2_sensitivity_analysis()
    example_3_scenario_analysis()
    pipeline, summary = example_4_pipeline_valuation()
    example_5_ma_premium_analysis()
    example_6_export_to_json()

    print("\n" + "="*80)
    print(" ALL EXAMPLES COMPLETED")
    print("="*80)
    print("\nKey Takeaways:")
    print("  1. Single drug DCF provides risk-adjusted NPV")
    print("  2. Sensitivity analysis shows valuation range under different assumptions")
    print("  3. Scenario modeling (bear/base/bull) provides probability-weighted outcomes")
    print("  4. Pipeline valuation sums individual assets with correlation adjustments")
    print("  5. M&A analysis compares DCF value to market cap for acquisition targets")
    print("  6. All results can be exported to JSON for further analysis")
    print("\nThis model is ready for biotech M&A prediction and target identification!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
