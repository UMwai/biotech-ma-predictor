"""
Unit Tests for DCF Valuation Model

Tests core functionality of the drug DCF valuation system including:
- Single drug valuations
- Revenue projections
- Sensitivity analysis
- Portfolio valuations
- M&A premium calculations
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.valuation import (
    DrugDCF,
    DrugValuation,
    PipelineValuation,
    DrugCandidate,
    ClinicalPhase,
    IndicationCategory,
    TherapeuticArea,
    RevenueCurveType,
    estimate_peak_sales,
    get_pos_by_phase,
    get_default_discount_rate,
    project_standard_curve,
    project_orphan_curve,
)


class TestDrugDCF(unittest.TestCase):
    """Test core DCF functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.dcf = DrugDCF(
            drug_name="TEST-001",
            peak_sales_estimate=2.0e9,
            time_to_peak=5,
            patent_life_remaining=12,
            clinical_phase=ClinicalPhase.PHASE_2,
            indication_category=IndicationCategory.ONCOLOGY_SOLID,
            years_to_launch=3,
        )

    def test_dcf_initialization(self):
        """Test DCF model initializes correctly."""
        self.assertEqual(self.dcf.drug_name, "TEST-001")
        self.assertEqual(self.dcf.peak_sales_estimate, 2.0e9)
        self.assertGreater(self.dcf.probability_of_success, 0)
        self.assertLess(self.dcf.probability_of_success, 1)

    def test_revenue_projection(self):
        """Test revenue projection generates correct number of years."""
        revenues = self.dcf.project_revenues()
        self.assertEqual(len(revenues), self.dcf.projection_years)

        # Pre-launch years should be zero
        for i in range(self.dcf.years_to_launch):
            self.assertEqual(revenues[i], 0.0)

        # Should have positive revenues post-launch
        self.assertGreater(revenues[self.dcf.years_to_launch + 1], 0)

    def test_revenue_reaches_peak(self):
        """Test revenue projection reaches approximately peak sales."""
        revenues = self.dcf.project_revenues()
        max_revenue = max(revenues)

        # Max revenue should be close to peak sales estimate (within 10%)
        self.assertAlmostEqual(
            max_revenue / self.dcf.peak_sales_estimate,
            1.0,
            delta=0.1
        )

    def test_calculate_valuation(self):
        """Test full valuation calculation."""
        valuation = self.dcf.calculate_valuation()

        self.assertIsInstance(valuation, DrugValuation)
        self.assertEqual(valuation.drug_name, "TEST-001")
        self.assertGreater(valuation.npv_risk_adjusted, 0)
        self.assertGreater(valuation.npv_unadjusted, valuation.npv_risk_adjusted)
        self.assertGreater(valuation.peak_sales, 0)

    def test_pos_adjustment(self):
        """Test probability of success adjustment."""
        valuation = self.dcf.calculate_valuation()

        # Risk-adjusted should be PoS * unadjusted
        expected = valuation.npv_unadjusted * valuation.probability_of_success
        self.assertAlmostEqual(
            valuation.npv_risk_adjusted,
            expected,
            delta=1e6  # Within $1M
        )

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis runs and returns results."""
        sensitivity = self.dcf.sensitivity_analysis()

        self.assertIn('peak_sales', sensitivity)
        self.assertIn('discount_rate', sensitivity)
        self.assertIn('probability_of_success', sensitivity)

        # Each should have multiple data points
        self.assertGreater(len(sensitivity['peak_sales']), 3)

        # Higher peak sales should give higher NPV
        peak_results = sensitivity['peak_sales']
        self.assertLess(
            peak_results[0]['npv_risk_adjusted'],
            peak_results[-1]['npv_risk_adjusted']
        )

    def test_scenario_analysis(self):
        """Test scenario analysis generates bear/base/bull cases."""
        scenarios = self.dcf.scenario_analysis()

        self.assertIn('bear', scenarios)
        self.assertIn('base', scenarios)
        self.assertIn('bull', scenarios)

        # Bull should be higher than base, base higher than bear
        bear_npv = scenarios['bear'].npv_risk_adjusted
        base_npv = scenarios['base'].npv_risk_adjusted
        bull_npv = scenarios['bull'].npv_risk_adjusted

        self.assertLess(bear_npv, base_npv)
        self.assertLess(base_npv, bull_npv)


class TestRevenueProjections(unittest.TestCase):
    """Test revenue projection models."""

    def test_standard_curve(self):
        """Test standard revenue curve."""
        revenues = project_standard_curve(
            peak_sales=1.5e9,
            years_to_launch=2,
            total_years=15
        )

        self.assertEqual(len(revenues), 15)
        self.assertEqual(revenues[0], 0)  # Pre-launch
        self.assertGreater(max(revenues), 1.4e9)  # Close to peak

    def test_orphan_curve(self):
        """Test orphan drug revenue curve."""
        revenues = project_orphan_curve(
            peak_sales=800e6,
            years_to_launch=3,
            total_years=20
        )

        self.assertEqual(len(revenues), 20)
        self.assertGreater(max(revenues), 0.7e9)

    def test_estimate_peak_sales(self):
        """Test peak sales estimation from TAM."""
        peak = estimate_peak_sales(
            indication=IndicationCategory.RARE_DISEASE,
            market_share=0.30,
            use_typical_tam=True
        )

        # Rare disease typical TAM is $1B, 30% share = $300M
        self.assertGreater(peak, 200e6)
        self.assertLess(peak, 400e6)

    def test_revenue_curve_monotonic_growth(self):
        """Test revenue grows during ramp phase."""
        revenues = project_standard_curve(
            peak_sales=2.0e9,
            years_to_launch=2,
            total_years=10
        )

        # During ramp years (2-7), revenue should increase
        for i in range(3, 7):
            self.assertGreaterEqual(revenues[i], revenues[i-1])


class TestAssumptions(unittest.TestCase):
    """Test industry assumptions and lookups."""

    def test_pos_by_phase(self):
        """Test PoS lookup by phase."""
        pos_p1 = get_pos_by_phase(ClinicalPhase.PHASE_1)
        pos_p2 = get_pos_by_phase(ClinicalPhase.PHASE_2)
        pos_p3 = get_pos_by_phase(ClinicalPhase.PHASE_3)

        # PoS should increase with phase advancement
        self.assertLess(pos_p1, pos_p2)
        self.assertLess(pos_p2, pos_p3)

        # All should be between 0 and 1
        self.assertGreater(pos_p1, 0)
        self.assertLess(pos_p3, 1)

    def test_pos_therapeutic_area_adjustment(self):
        """Test therapeutic area PoS adjustments."""
        base_pos = get_pos_by_phase(ClinicalPhase.PHASE_2)
        rare_pos = get_pos_by_phase(
            ClinicalPhase.PHASE_2,
            therapeutic_area=TherapeuticArea.RARE_DISEASE
        )
        cns_pos = get_pos_by_phase(
            ClinicalPhase.PHASE_2,
            therapeutic_area=TherapeuticArea.CNS
        )

        # Rare disease should have higher PoS
        self.assertGreater(rare_pos, base_pos)

        # CNS should have lower PoS
        self.assertLess(cns_pos, base_pos)

    def test_discount_rates(self):
        """Test discount rate lookup."""
        preclinical_rate = get_default_discount_rate('preclinical_biotech')
        clinical_rate = get_default_discount_rate('clinical_stage')
        pharma_rate = get_default_discount_rate('big_pharma')

        # Risk decreases with maturity
        self.assertGreater(preclinical_rate, clinical_rate)
        self.assertGreater(clinical_rate, pharma_rate)


class TestPipelineValuation(unittest.TestCase):
    """Test multi-drug pipeline valuation."""

    def setUp(self):
        """Set up test pipeline."""
        self.drugs = [
            DrugCandidate(
                name="DRUG-A",
                indication=IndicationCategory.ONCOLOGY_SOLID,
                clinical_phase=ClinicalPhase.PHASE_3,
                peak_sales=3.0e9,
                years_to_launch=2
            ),
            DrugCandidate(
                name="DRUG-B",
                indication=IndicationCategory.RARE_DISEASE,
                clinical_phase=ClinicalPhase.PHASE_2,
                peak_sales=1.0e9,
                years_to_launch=4
            ),
        ]

        self.pipeline = PipelineValuation(drugs=self.drugs)

    def test_pipeline_initialization(self):
        """Test pipeline initializes correctly."""
        self.assertEqual(len(self.pipeline.drugs), 2)

    def test_value_single_drug(self):
        """Test valuing individual drug from pipeline."""
        valuation = self.pipeline.value_single_drug(self.drugs[0])

        self.assertIsInstance(valuation, DrugValuation)
        self.assertEqual(valuation.drug_name, "DRUG-A")
        self.assertGreater(valuation.npv_risk_adjusted, 0)

    def test_value_pipeline(self):
        """Test full pipeline valuation."""
        summary = self.pipeline.value_pipeline()

        self.assertEqual(summary.drug_count, 2)
        self.assertGreater(summary.total_pipeline_value, 0)
        self.assertGreater(summary.risk_adjusted_value, 0)
        self.assertEqual(len(summary.drug_valuations), 2)

    def test_sum_of_parts(self):
        """Test sum-of-parts calculation."""
        summary = self.pipeline.value_pipeline()

        # Manual sum
        manual_sum = sum(d.npv_risk_adjusted for d in summary.drug_valuations)

        # Should match total_pipeline_value
        self.assertAlmostEqual(
            summary.total_pipeline_value,
            manual_sum,
            delta=1e6
        )

    def test_compare_to_market_cap(self):
        """Test market cap comparison."""
        summary = self.pipeline.value_pipeline()
        market_cap = 2.0e9

        comparison = self.pipeline.compare_to_market_cap(market_cap)

        self.assertIn('pipeline_value', comparison)
        self.assertIn('market_cap', comparison)
        self.assertIn('premium_discount', comparison)
        self.assertEqual(comparison['market_cap'], market_cap)

    def test_get_top_assets(self):
        """Test identifying top assets."""
        self.pipeline.value_pipeline()
        top_assets = self.pipeline.get_top_assets(n=1)

        self.assertEqual(len(top_assets), 1)
        # Phase 3 drug should be most valuable
        self.assertEqual(top_assets[0].drug_name, "DRUG-A")

    def test_valuation_by_phase(self):
        """Test breakdown by development phase."""
        self.pipeline.value_pipeline()
        by_phase = self.pipeline.get_valuation_by_phase()

        self.assertIn('Phase 3', by_phase)
        self.assertIn('Phase 2', by_phase)
        self.assertEqual(by_phase['Phase 3']['count'], 1)
        self.assertEqual(by_phase['Phase 2']['count'], 1)

    def test_valuation_by_indication(self):
        """Test breakdown by indication."""
        self.pipeline.value_pipeline()
        by_indication = self.pipeline.get_valuation_by_indication()

        self.assertGreater(len(by_indication), 0)

        # Should have oncology and rare disease
        indication_names = list(by_indication.keys())
        self.assertIn('Oncology Solid Tumors', indication_names)
        self.assertIn('Rare Disease', indication_names)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_approved_drug_100_percent_pos(self):
        """Test approved drug has 100% PoS."""
        dcf = DrugDCF(
            drug_name="APPROVED-001",
            peak_sales_estimate=1.0e9,
            clinical_phase=ClinicalPhase.APPROVED,
            years_to_launch=0,  # Already launched
        )

        valuation = dcf.calculate_valuation()
        self.assertEqual(valuation.probability_of_success, 1.0)

    def test_zero_years_to_launch(self):
        """Test drug launching immediately."""
        dcf = DrugDCF(
            drug_name="IMMEDIATE",
            peak_sales_estimate=1.0e9,
            clinical_phase=ClinicalPhase.APPROVED,
            years_to_launch=0,
        )

        revenues = dcf.project_revenues()
        # Should have revenue in year 0
        self.assertGreater(revenues[0], 0)

    def test_very_high_discount_rate(self):
        """Test valuation with high discount rate."""
        dcf = DrugDCF(
            drug_name="HIGH-RISK",
            peak_sales_estimate=2.0e9,
            clinical_phase=ClinicalPhase.PHASE_1,
            discount_rate=0.25,  # 25% WACC
        )

        valuation = dcf.calculate_valuation()
        # Should still produce positive NPV
        self.assertGreater(valuation.npv_unadjusted, 0)

    def test_small_peak_sales(self):
        """Test with small peak sales (e.g., niche orphan drug)."""
        # Small orphan drug that's already approved (no development costs)
        dcf = DrugDCF(
            drug_name="NICHE",
            peak_sales_estimate=500e6,  # $500M peak (realistic for orphan)
            clinical_phase=ClinicalPhase.APPROVED,
            years_to_launch=0,  # Already launched
            revenue_curve_type=RevenueCurveType.ORPHAN,
        )

        valuation = dcf.calculate_valuation()
        # Should have positive NPV since no development costs
        self.assertGreater(valuation.npv_risk_adjusted, 0)
        self.assertLess(valuation.npv_risk_adjusted, 1e9)


class TestExportFunctionality(unittest.TestCase):
    """Test JSON export and data conversion."""

    def test_valuation_to_dict(self):
        """Test converting valuation to dictionary."""
        dcf = DrugDCF(
            drug_name="EXPORT-TEST",
            peak_sales_estimate=1.5e9,
            clinical_phase=ClinicalPhase.PHASE_2,
        )

        valuation = dcf.calculate_valuation()
        data = valuation.to_dict()

        self.assertIsInstance(data, dict)
        self.assertIn('drug_name', data)
        self.assertIn('npv_risk_adjusted', data)
        self.assertEqual(data['drug_name'], "EXPORT-TEST")

    def test_valuation_to_json(self):
        """Test converting valuation to JSON string."""
        dcf = DrugDCF(
            drug_name="JSON-TEST",
            peak_sales_estimate=1.0e9,
            clinical_phase=ClinicalPhase.PHASE_3,
        )

        valuation = dcf.calculate_valuation()
        json_str = valuation.to_json()

        self.assertIsInstance(json_str, str)
        self.assertIn('JSON-TEST', json_str)
        self.assertIn('npv_risk_adjusted', json_str)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()
