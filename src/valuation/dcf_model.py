"""
Core DCF (Discounted Cash Flow) Model for Drug Valuation

This module implements the fundamental DCF valuation engine for individual
drug candidates, including:
- Risk-adjusted NPV calculations
- Probability of success (PoS) adjustments
- Sensitivity analysis across key variables
- Multiple scenario modeling

The DCF approach is the gold standard for biotech asset valuation in M&A.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import json
from datetime import datetime

from .drug_revenue import (
    RevenueProjector,
    RevenueCurveType,
    IndicationCategory,
    estimate_peak_sales,
    calculate_revenue_metrics
)
from .assumptions import (
    ClinicalPhase,
    TherapeuticArea,
    get_pos_by_phase,
    get_default_discount_rate,
    get_cost_structure,
    TAX_RATES,
    TERMINAL_VALUE
)


@dataclass
class DrugValuation:
    """
    Complete valuation output for a drug candidate.

    Attributes:
        drug_name: Name/identifier of drug
        indication: Therapeutic indication
        clinical_phase: Development phase

        # Revenue projections
        annual_revenues: Projected revenues by year
        peak_sales: Peak annual sales
        years_to_peak: Years to reach peak

        # DCF outputs
        npv_risk_adjusted: Risk-adjusted NPV
        npv_unadjusted: Unadjusted NPV (no PoS)
        probability_of_success: PoS applied
        discount_rate: WACC used

        # Valuation metrics
        value_per_patient: Value per addressable patient
        peak_multiple: NPV as multiple of peak sales

        # Metadata
        valuation_date: When valuation was performed
        assumptions: Key assumptions used
    """
    drug_name: str
    indication: str
    clinical_phase: str

    annual_revenues: List[float]
    peak_sales: float
    years_to_peak: int

    npv_risk_adjusted: float
    npv_unadjusted: float
    probability_of_success: float
    discount_rate: float

    value_per_patient: Optional[float] = None
    peak_multiple: Optional[float] = None

    valuation_date: str = ""
    assumptions: Dict = None

    def __post_init__(self):
        """Calculate derived metrics."""
        if not self.valuation_date:
            self.valuation_date = datetime.now().strftime("%Y-%m-%d")

        if self.peak_sales > 0:
            self.peak_multiple = self.npv_risk_adjusted / self.peak_sales

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, filepath: str):
        """Save valuation to JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())


class DrugDCF:
    """
    Core DCF valuation engine for drug candidates.

    Implements risk-adjusted NPV calculation using projected revenues,
    operating cash flows, and probability of success adjustments.

    Examples:
        >>> dcf = DrugDCF(
        ...     drug_name="ABC-123",
        ...     peak_sales_estimate=2.5e9,
        ...     time_to_peak=5,
        ...     patent_life_remaining=12,
        ...     clinical_phase=ClinicalPhase.PHASE_2,
        ...     probability_of_success=0.30
        ... )
        >>> valuation = dcf.calculate_valuation()
        >>> print(f"Risk-adjusted NPV: ${valuation.npv_risk_adjusted/1e9:.2f}B")
    """

    def __init__(
        self,
        drug_name: str = "Drug Candidate",
        peak_sales_estimate: float = 1.0e9,
        time_to_peak: int = 5,
        patent_life_remaining: int = 12,
        probability_of_success: Optional[float] = None,
        clinical_phase: ClinicalPhase = ClinicalPhase.PHASE_2,
        therapeutic_area: Optional[TherapeuticArea] = None,
        indication_category: Optional[IndicationCategory] = None,
        revenue_curve_type: RevenueCurveType = RevenueCurveType.STANDARD,
        discount_rate: Optional[float] = None,
        years_to_launch: int = 3,
        projection_years: int = 20,
        # Cost structure
        cogs_percent: float = 0.25,
        rd_percent: float = 0.20,
        sga_percent: float = 0.30,
        tax_rate: Optional[float] = None,
        # Development costs
        development_costs: Optional[List[float]] = None,
    ):
        """
        Initialize DCF model.

        Args:
            drug_name: Name/identifier for the drug
            peak_sales_estimate: Expected peak annual sales (USD)
            time_to_peak: Years from launch to peak sales
            patent_life_remaining: Years of patent protection remaining
            probability_of_success: PoS override (calculated if None)
            clinical_phase: Current development phase
            therapeutic_area: Therapeutic area for PoS adjustment
            indication_category: Indication for TAM reference
            revenue_curve_type: Type of revenue curve to use
            discount_rate: WACC (calculated if None)
            years_to_launch: Years until product launch
            projection_years: Total years to project
            cogs_percent: COGS as % of revenue
            rd_percent: R&D as % of revenue
            sga_percent: SG&A as % of revenue
            tax_rate: Effective tax rate (calculated if None)
            development_costs: Annual development costs until launch
        """
        self.drug_name = drug_name
        self.peak_sales_estimate = peak_sales_estimate
        self.time_to_peak = time_to_peak
        self.patent_life_remaining = patent_life_remaining
        self.clinical_phase = clinical_phase
        self.therapeutic_area = therapeutic_area
        self.indication_category = indication_category
        self.revenue_curve_type = revenue_curve_type
        self.years_to_launch = years_to_launch
        self.projection_years = projection_years

        # Calculate or use provided PoS
        if probability_of_success is not None:
            self.probability_of_success = probability_of_success
        else:
            self.probability_of_success = get_pos_by_phase(
                clinical_phase,
                therapeutic_area
            )

        # Calculate or use provided discount rate
        if discount_rate is not None:
            self.discount_rate = discount_rate
        else:
            # Select stage based on clinical phase
            if clinical_phase in [ClinicalPhase.PRECLINICAL]:
                stage = 'preclinical_biotech'
            elif clinical_phase in [ClinicalPhase.PHASE_1, ClinicalPhase.PHASE_2]:
                stage = 'clinical_stage'
            elif clinical_phase in [ClinicalPhase.PHASE_3, ClinicalPhase.NDA_FILED]:
                stage = 'late_stage'
            else:
                stage = 'commercial'

            self.discount_rate = get_default_discount_rate(stage)

        # Cost structure
        self.cogs_percent = cogs_percent
        self.rd_percent = rd_percent
        self.sga_percent = sga_percent
        self.tax_rate = tax_rate if tax_rate is not None else TAX_RATES['effective_biotech']

        # Development costs (burn rate until launch)
        if development_costs:
            self.development_costs = development_costs
        else:
            # Default development cost assumptions
            self.development_costs = self._estimate_development_costs()

        # Initialize revenue projector
        self.revenue_projector = RevenueProjector(
            peak_sales=peak_sales_estimate,
            curve_type=revenue_curve_type
        )

    def _estimate_development_costs(self) -> List[float]:
        """
        Estimate annual development costs until launch.

        Based on clinical phase and time to launch.
        """
        costs = []

        # Annual burn rate by phase (rough estimates)
        burn_rates = {
            ClinicalPhase.PRECLINICAL: 10e6,
            ClinicalPhase.PHASE_1: 25e6,
            ClinicalPhase.PHASE_2: 50e6,
            ClinicalPhase.PHASE_3: 100e6,
            ClinicalPhase.NDA_FILED: 30e6,
            ClinicalPhase.APPROVED: 0,
        }

        base_burn = burn_rates.get(self.clinical_phase, 30e6)

        for year in range(self.years_to_launch):
            # Burn rate increases slightly each year (inflation, trial expansion)
            yearly_burn = base_burn * (1.05 ** year)
            costs.append(yearly_burn)

        return costs

    def project_revenues(self) -> List[float]:
        """
        Project revenues over the projection period.

        Returns:
            List of annual revenues
        """
        return self.revenue_projector.project_revenues(
            years_to_launch=self.years_to_launch,
            total_years=self.projection_years,
            patent_life_remaining=self.patent_life_remaining
        )

    def calculate_operating_cash_flows(
        self,
        revenues: List[float]
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate operating cash flows from revenues.

        Args:
            revenues: Annual revenue projections

        Returns:
            Tuple of (operating_income, free_cash_flows, cumulative_costs)
        """
        operating_income = []
        free_cash_flows = []
        cumulative_costs = []

        for year, revenue in enumerate(revenues):
            # Pre-launch: development costs, no revenue
            if year < self.years_to_launch:
                dev_cost = (self.development_costs[year]
                           if year < len(self.development_costs)
                           else 0)
                operating_income.append(-dev_cost)
                free_cash_flows.append(-dev_cost)
                cumulative_costs.append(dev_cost)
            else:
                # Post-launch: revenue minus costs
                cogs = revenue * self.cogs_percent
                rd = revenue * self.rd_percent
                sga = revenue * self.sga_percent

                ebitda = revenue - cogs - rd - sga

                # Depreciation/amortization (simplified)
                da = revenue * 0.05
                ebit = ebitda - da

                # Taxes
                if ebit > 0:
                    tax = ebit * self.tax_rate
                else:
                    tax = 0  # No tax benefit from losses (conservative)

                net_income = ebit - tax

                # FCF = Net Income + DA - CapEx (simplified: CapEx = 5% revenue)
                capex = revenue * 0.05
                fcf = net_income + da - capex

                operating_income.append(ebit)
                free_cash_flows.append(fcf)
                cumulative_costs.append(0)

        return operating_income, free_cash_flows, cumulative_costs

    def calculate_npv(
        self,
        cash_flows: List[float],
        discount_rate: Optional[float] = None
    ) -> float:
        """
        Calculate Net Present Value of cash flows.

        Args:
            cash_flows: Annual cash flows to discount
            discount_rate: Discount rate (uses default if None)

        Returns:
            NPV of cash flows
        """
        if discount_rate is None:
            discount_rate = self.discount_rate

        npv = 0.0
        for year, cf in enumerate(cash_flows):
            discount_factor = 1 / ((1 + discount_rate) ** year)
            npv += cf * discount_factor

        return npv

    def apply_pos_adjustment(self, npv_unadjusted: float) -> float:
        """
        Apply probability of success adjustment to NPV.

        Risk-adjusted NPV = Unadjusted NPV * PoS

        Args:
            npv_unadjusted: Unadjusted NPV

        Returns:
            Risk-adjusted NPV
        """
        return npv_unadjusted * self.probability_of_success

    def calculate_valuation(self) -> DrugValuation:
        """
        Perform complete DCF valuation.

        Returns:
            DrugValuation object with all results

        Examples:
            >>> dcf = DrugDCF(peak_sales_estimate=3e9, clinical_phase=ClinicalPhase.PHASE_3)
            >>> val = dcf.calculate_valuation()
            >>> val.npv_risk_adjusted > 0
            True
        """
        # Project revenues
        revenues = self.project_revenues()

        # Calculate cash flows
        operating_income, free_cash_flows, _ = self.calculate_operating_cash_flows(revenues)

        # Calculate NPV
        npv_unadjusted = self.calculate_npv(free_cash_flows)
        npv_risk_adjusted = self.apply_pos_adjustment(npv_unadjusted)

        # Revenue metrics
        metrics = calculate_revenue_metrics(revenues)

        # Build assumptions dict
        assumptions = {
            'peak_sales_estimate': self.peak_sales_estimate,
            'time_to_peak': self.time_to_peak,
            'patent_life_remaining': self.patent_life_remaining,
            'years_to_launch': self.years_to_launch,
            'probability_of_success': self.probability_of_success,
            'discount_rate': self.discount_rate,
            'revenue_curve_type': self.revenue_curve_type.value,
            'cogs_percent': self.cogs_percent,
            'rd_percent': self.rd_percent,
            'sga_percent': self.sga_percent,
            'tax_rate': self.tax_rate,
        }

        return DrugValuation(
            drug_name=self.drug_name,
            indication=self.indication_category.value if self.indication_category else "Unknown",
            clinical_phase=self.clinical_phase.value,
            annual_revenues=revenues,
            peak_sales=metrics['peak_revenue'],
            years_to_peak=metrics['years_to_peak'],
            npv_risk_adjusted=npv_risk_adjusted,
            npv_unadjusted=npv_unadjusted,
            probability_of_success=self.probability_of_success,
            discount_rate=self.discount_rate,
            assumptions=assumptions
        )

    def sensitivity_analysis(
        self,
        variables: Optional[List[str]] = None,
        ranges: Optional[Dict[str, List[float]]] = None
    ) -> Dict[str, List[Dict]]:
        """
        Perform sensitivity analysis on key variables.

        Tests how NPV changes with different assumptions for:
        - Peak sales
        - Discount rate
        - Probability of success
        - Time to peak

        Args:
            variables: Variables to test (uses defaults if None)
            ranges: Custom ranges for each variable

        Returns:
            Dictionary mapping variable name to list of results
            Each result is {'value': input_value, 'npv': output_npv}

        Examples:
            >>> dcf = DrugDCF(peak_sales_estimate=2e9)
            >>> sensitivity = dcf.sensitivity_analysis()
            >>> 'peak_sales' in sensitivity
            True
        """
        if variables is None:
            variables = ['peak_sales', 'discount_rate', 'probability_of_success', 'time_to_peak']

        # Default ranges (% variations around base case)
        default_ranges = {
            'peak_sales': [0.5, 0.75, 1.0, 1.25, 1.5],  # 50% to 150%
            'discount_rate': [0.08, 0.10, 0.12, 0.15, 0.18],
            'probability_of_success': [0.5, 0.75, 1.0, 1.25, 1.5],  # Relative
            'time_to_peak': [3, 4, 5, 6, 7],
        }

        if ranges:
            default_ranges.update(ranges)

        results = {}

        for var in variables:
            var_results = []

            if var == 'peak_sales':
                base_value = self.peak_sales_estimate
                test_values = [base_value * m for m in default_ranges['peak_sales']]

                for value in test_values:
                    # Create temporary DCF with modified peak sales
                    temp_dcf = DrugDCF(
                        drug_name=self.drug_name,
                        peak_sales_estimate=value,
                        time_to_peak=self.time_to_peak,
                        patent_life_remaining=self.patent_life_remaining,
                        probability_of_success=self.probability_of_success,
                        clinical_phase=self.clinical_phase,
                        discount_rate=self.discount_rate,
                        years_to_launch=self.years_to_launch,
                        revenue_curve_type=self.revenue_curve_type,
                    )
                    val = temp_dcf.calculate_valuation()
                    var_results.append({
                        'value': value,
                        'npv_risk_adjusted': val.npv_risk_adjusted,
                        'npv_unadjusted': val.npv_unadjusted
                    })

            elif var == 'discount_rate':
                for value in default_ranges['discount_rate']:
                    temp_dcf = DrugDCF(
                        drug_name=self.drug_name,
                        peak_sales_estimate=self.peak_sales_estimate,
                        time_to_peak=self.time_to_peak,
                        patent_life_remaining=self.patent_life_remaining,
                        probability_of_success=self.probability_of_success,
                        clinical_phase=self.clinical_phase,
                        discount_rate=value,
                        years_to_launch=self.years_to_launch,
                        revenue_curve_type=self.revenue_curve_type,
                    )
                    val = temp_dcf.calculate_valuation()
                    var_results.append({
                        'value': value,
                        'npv_risk_adjusted': val.npv_risk_adjusted,
                        'npv_unadjusted': val.npv_unadjusted
                    })

            elif var == 'probability_of_success':
                base_pos = self.probability_of_success
                test_values = [base_pos * m for m in default_ranges['probability_of_success']]
                test_values = [min(v, 1.0) for v in test_values]  # Cap at 100%

                for value in test_values:
                    temp_dcf = DrugDCF(
                        drug_name=self.drug_name,
                        peak_sales_estimate=self.peak_sales_estimate,
                        time_to_peak=self.time_to_peak,
                        patent_life_remaining=self.patent_life_remaining,
                        probability_of_success=value,
                        clinical_phase=self.clinical_phase,
                        discount_rate=self.discount_rate,
                        years_to_launch=self.years_to_launch,
                        revenue_curve_type=self.revenue_curve_type,
                    )
                    val = temp_dcf.calculate_valuation()
                    var_results.append({
                        'value': value,
                        'npv_risk_adjusted': val.npv_risk_adjusted,
                        'npv_unadjusted': val.npv_unadjusted
                    })

            elif var == 'time_to_peak':
                for value in default_ranges['time_to_peak']:
                    temp_dcf = DrugDCF(
                        drug_name=self.drug_name,
                        peak_sales_estimate=self.peak_sales_estimate,
                        time_to_peak=value,
                        patent_life_remaining=self.patent_life_remaining,
                        probability_of_success=self.probability_of_success,
                        clinical_phase=self.clinical_phase,
                        discount_rate=self.discount_rate,
                        years_to_launch=self.years_to_launch,
                        revenue_curve_type=self.revenue_curve_type,
                    )
                    val = temp_dcf.calculate_valuation()
                    var_results.append({
                        'value': value,
                        'npv_risk_adjusted': val.npv_risk_adjusted,
                        'npv_unadjusted': val.npv_unadjusted
                    })

            results[var] = var_results

        return results

    def scenario_analysis(self) -> Dict[str, DrugValuation]:
        """
        Run bear, base, and bull case scenarios.

        Returns:
            Dictionary with 'bear', 'base', 'bull' valuations

        Examples:
            >>> dcf = DrugDCF(peak_sales_estimate=2e9)
            >>> scenarios = dcf.scenario_analysis()
            >>> scenarios['bull'].npv_risk_adjusted > scenarios['base'].npv_risk_adjusted
            True
        """
        # Base case
        base = self.calculate_valuation()

        # Bear case: lower peak sales, higher discount rate, lower PoS
        bear_dcf = DrugDCF(
            drug_name=f"{self.drug_name} (Bear)",
            peak_sales_estimate=self.peak_sales_estimate * 0.60,
            time_to_peak=self.time_to_peak + 1,
            patent_life_remaining=self.patent_life_remaining,
            probability_of_success=self.probability_of_success * 0.70,
            clinical_phase=self.clinical_phase,
            discount_rate=self.discount_rate + 0.03,
            years_to_launch=self.years_to_launch + 1,
            revenue_curve_type=self.revenue_curve_type,
        )
        bear = bear_dcf.calculate_valuation()

        # Bull case: higher peak sales, lower discount rate, higher PoS
        bull_dcf = DrugDCF(
            drug_name=f"{self.drug_name} (Bull)",
            peak_sales_estimate=self.peak_sales_estimate * 1.40,
            time_to_peak=max(self.time_to_peak - 1, 3),
            patent_life_remaining=self.patent_life_remaining,
            probability_of_success=min(self.probability_of_success * 1.30, 1.0),
            clinical_phase=self.clinical_phase,
            discount_rate=max(self.discount_rate - 0.03, 0.08),
            years_to_launch=max(self.years_to_launch - 1, 0),
            revenue_curve_type=self.revenue_curve_type,
        )
        bull = bull_dcf.calculate_valuation()

        return {
            'bear': bear,
            'base': base,
            'bull': bull
        }
