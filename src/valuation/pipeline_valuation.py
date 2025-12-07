"""
Pipeline Valuation Module

Implements sum-of-parts valuation for multi-asset biotech portfolios.
This is critical for M&A analysis where buyers acquire entire pipelines.

Key Features:
- Value multiple drugs simultaneously
- Sum-of-parts analysis
- Portfolio risk correlation adjustments
- Comparison to market cap (M&A premium/discount analysis)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
from datetime import datetime

from .dcf_model import DrugDCF, DrugValuation
from .drug_revenue import IndicationCategory, RevenueCurveType
from .assumptions import ClinicalPhase, TherapeuticArea


@dataclass
class DrugCandidate:
    """
    Represents a single drug in a pipeline.

    Attributes:
        name: Drug name/identifier
        indication: Therapeutic indication
        clinical_phase: Development phase
        peak_sales: Expected peak sales
        years_to_launch: Years until launch
        probability_of_success: PoS override (optional)
        therapeutic_area: Therapeutic area (optional)
        revenue_curve_type: Revenue curve to use
    """
    name: str
    indication: IndicationCategory
    clinical_phase: ClinicalPhase
    peak_sales: float
    years_to_launch: int = 3
    probability_of_success: Optional[float] = None
    therapeutic_area: Optional[TherapeuticArea] = None
    revenue_curve_type: RevenueCurveType = RevenueCurveType.STANDARD
    patent_life_remaining: int = 12

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'indication': self.indication.value,
            'clinical_phase': self.clinical_phase.value,
            'peak_sales': self.peak_sales,
            'years_to_launch': self.years_to_launch,
            'probability_of_success': self.probability_of_success,
            'therapeutic_area': self.therapeutic_area.value if self.therapeutic_area else None,
            'revenue_curve_type': self.revenue_curve_type.value,
            'patent_life_remaining': self.patent_life_remaining,
        }


@dataclass
class PortfolioSummary:
    """
    Summary of pipeline valuation results.

    Attributes:
        total_pipeline_value: Sum-of-parts valuation
        risk_adjusted_value: Value with correlation adjustments
        drug_count: Number of drugs in pipeline
        drug_valuations: Individual drug valuations
        market_cap: Company market cap (if applicable)
        implied_premium: Premium/discount vs market cap
        valuation_date: Date of valuation
    """
    total_pipeline_value: float
    risk_adjusted_value: float
    drug_count: int
    drug_valuations: List[DrugValuation]
    market_cap: Optional[float] = None
    implied_premium: Optional[float] = None
    top_asset_concentration: Optional[float] = None
    valuation_date: str = ""

    def __post_init__(self):
        """Calculate derived metrics."""
        if not self.valuation_date:
            self.valuation_date = datetime.now().strftime("%Y-%m-%d")

        if self.market_cap and self.risk_adjusted_value > 0:
            self.implied_premium = (self.market_cap / self.risk_adjusted_value) - 1.0

        # Calculate concentration in top asset
        if self.drug_valuations:
            values = [d.npv_risk_adjusted for d in self.drug_valuations]
            top_value = max(values)
            if self.total_pipeline_value > 0:
                self.top_asset_concentration = top_value / self.total_pipeline_value

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert drug valuations to dicts
        data['drug_valuations'] = [d.to_dict() for d in self.drug_valuations]
        return data

    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, filepath: str):
        """Save portfolio valuation to JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json())


class PipelineValuation:
    """
    Portfolio-level valuation for multi-asset biotech companies.

    Implements sum-of-parts DCF with correlation adjustments for
    portfolio risk diversification.

    Examples:
        >>> drugs = [
        ...     DrugCandidate("Drug A", IndicationCategory.ONCOLOGY_SOLID,
        ...                   ClinicalPhase.PHASE_3, peak_sales=3e9),
        ...     DrugCandidate("Drug B", IndicationCategory.RARE_DISEASE,
        ...                   ClinicalPhase.PHASE_2, peak_sales=800e6)
        ... ]
        >>> pipeline = PipelineValuation(drugs)
        >>> summary = pipeline.value_pipeline()
        >>> print(f"Pipeline value: ${summary.total_pipeline_value/1e9:.2f}B")
    """

    def __init__(
        self,
        drugs: List[DrugCandidate],
        company_name: str = "Portfolio Company",
        discount_rate: Optional[float] = None,
        apply_correlation_adjustment: bool = True,
        correlation_factor: float = 0.90
    ):
        """
        Initialize pipeline valuation.

        Args:
            drugs: List of drug candidates to value
            company_name: Company name for reporting
            discount_rate: Override discount rate for all drugs
            apply_correlation_adjustment: Apply portfolio correlation discount
            correlation_factor: Correlation between assets (0-1, default 0.90)
                Higher correlation = less diversification benefit
        """
        self.drugs = drugs
        self.company_name = company_name
        self.discount_rate = discount_rate
        self.apply_correlation_adjustment = apply_correlation_adjustment
        self.correlation_factor = correlation_factor

        self._drug_valuations: Optional[List[DrugValuation]] = None

    def value_single_drug(self, drug: DrugCandidate) -> DrugValuation:
        """
        Value a single drug candidate.

        Args:
            drug: DrugCandidate to value

        Returns:
            DrugValuation with NPV and metrics
        """
        dcf = DrugDCF(
            drug_name=drug.name,
            peak_sales_estimate=drug.peak_sales,
            time_to_peak=5,  # Default
            patent_life_remaining=drug.patent_life_remaining,
            probability_of_success=drug.probability_of_success,
            clinical_phase=drug.clinical_phase,
            therapeutic_area=drug.therapeutic_area,
            indication_category=drug.indication,
            revenue_curve_type=drug.revenue_curve_type,
            discount_rate=self.discount_rate,
            years_to_launch=drug.years_to_launch,
        )

        return dcf.calculate_valuation()

    def value_pipeline(self) -> PortfolioSummary:
        """
        Value entire pipeline using sum-of-parts.

        Returns:
            PortfolioSummary with total valuation and individual drug values

        Examples:
            >>> drugs = [DrugCandidate("Test", IndicationCategory.ONCOLOGY_SOLID,
            ...                        ClinicalPhase.PHASE_2, 2e9)]
            >>> pipeline = PipelineValuation(drugs)
            >>> summary = pipeline.value_pipeline()
            >>> summary.drug_count
            1
        """
        # Value each drug
        drug_valuations = []
        for drug in self.drugs:
            valuation = self.value_single_drug(drug)
            drug_valuations.append(valuation)

        self._drug_valuations = drug_valuations

        # Calculate sum-of-parts
        total_value = self.calculate_sum_of_parts(drug_valuations)

        # Apply correlation adjustment if enabled
        if self.apply_correlation_adjustment and len(drug_valuations) > 1:
            risk_adjusted = self.apply_portfolio_correlation(
                total_value,
                drug_valuations
            )
        else:
            risk_adjusted = total_value

        return PortfolioSummary(
            total_pipeline_value=total_value,
            risk_adjusted_value=risk_adjusted,
            drug_count=len(drug_valuations),
            drug_valuations=drug_valuations
        )

    def calculate_sum_of_parts(
        self,
        drug_valuations: Optional[List[DrugValuation]] = None
    ) -> float:
        """
        Calculate simple sum-of-parts valuation.

        Args:
            drug_valuations: List of drug valuations (uses cached if None)

        Returns:
            Total pipeline value (sum of individual NPVs)
        """
        if drug_valuations is None:
            if self._drug_valuations is None:
                raise ValueError("Must run value_pipeline() first")
            drug_valuations = self._drug_valuations

        return sum(d.npv_risk_adjusted for d in drug_valuations)

    def apply_portfolio_correlation(
        self,
        total_value: float,
        drug_valuations: List[DrugValuation]
    ) -> float:
        """
        Apply portfolio correlation adjustment.

        Diversified portfolios have less risk than sum-of-parts suggests,
        but in biotech, correlation is high (platform risk, regulatory risk).

        This applies a modest haircut for imperfect diversification.

        Args:
            total_value: Sum-of-parts value
            drug_valuations: Individual drug valuations

        Returns:
            Correlation-adjusted portfolio value
        """
        # Calculate concentration (Herfindahl index)
        values = [d.npv_risk_adjusted for d in drug_valuations]
        total = sum(values)

        if total <= 0:
            return total_value

        # Concentration index: sum of squared market shares
        shares = [v / total for v in values]
        herfindahl = sum(s ** 2 for s in shares)

        # Diversification benefit: lower concentration = higher benefit
        # But limited by correlation factor
        diversification_benefit = (1 - herfindahl) * (1 - self.correlation_factor)

        # Modest uplift for diversification (typically 0-10%)
        adjustment_factor = 1 + (diversification_benefit * 0.10)

        return total_value * adjustment_factor

    def compare_to_market_cap(
        self,
        market_cap: float
    ) -> Dict[str, float]:
        """
        Compare pipeline valuation to company market cap.

        This reveals M&A premium/discount and potential acquisition value.

        Args:
            market_cap: Current market capitalization

        Returns:
            Dictionary with comparison metrics:
            - pipeline_value: Sum-of-parts value
            - market_cap: Current market cap
            - premium_discount: % premium (positive) or discount (negative)
            - implied_acquisition_value: Suggested acquisition price

        Examples:
            >>> drugs = [DrugCandidate("Test", IndicationCategory.ONCOLOGY_SOLID,
            ...                        ClinicalPhase.PHASE_3, 5e9)]
            >>> pipeline = PipelineValuation(drugs)
            >>> pipeline.value_pipeline()
            >>> comparison = pipeline.compare_to_market_cap(2e9)
            >>> 'premium_discount' in comparison
            True
        """
        if self._drug_valuations is None:
            summary = self.value_pipeline()
        else:
            summary = PortfolioSummary(
                total_pipeline_value=self.calculate_sum_of_parts(),
                risk_adjusted_value=self.calculate_sum_of_parts(),
                drug_count=len(self._drug_valuations),
                drug_valuations=self._drug_valuations
            )

        pipeline_value = summary.risk_adjusted_value

        # Premium/discount vs market cap
        if market_cap > 0:
            premium_discount = (pipeline_value / market_cap) - 1.0
        else:
            premium_discount = 0.0

        # Implied acquisition value: typically 30-50% premium over DCF
        # for control premium, synergies, etc.
        control_premium = 0.40  # 40% typical M&A premium
        implied_acquisition_value = pipeline_value * (1 + control_premium)

        return {
            'pipeline_value': pipeline_value,
            'market_cap': market_cap,
            'premium_discount': premium_discount,
            'implied_acquisition_value': implied_acquisition_value,
            'value_per_share': None,  # Would need shares outstanding
        }

    def get_valuation_by_phase(self) -> Dict[str, Dict]:
        """
        Aggregate pipeline value by development phase.

        Returns:
            Dictionary mapping phase to value and drug count

        Examples:
            >>> drugs = [
            ...     DrugCandidate("A", IndicationCategory.ONCOLOGY_SOLID,
            ...                   ClinicalPhase.PHASE_3, 3e9),
            ...     DrugCandidate("B", IndicationCategory.RARE_DISEASE,
            ...                   ClinicalPhase.PHASE_2, 1e9)
            ... ]
            >>> pipeline = PipelineValuation(drugs)
            >>> pipeline.value_pipeline()
            >>> by_phase = pipeline.get_valuation_by_phase()
            >>> 'Phase 3' in by_phase
            True
        """
        if self._drug_valuations is None:
            self.value_pipeline()

        by_phase = {}

        for valuation in self._drug_valuations:
            phase = valuation.clinical_phase

            if phase not in by_phase:
                by_phase[phase] = {
                    'value': 0.0,
                    'count': 0,
                    'drugs': []
                }

            by_phase[phase]['value'] += valuation.npv_risk_adjusted
            by_phase[phase]['count'] += 1
            by_phase[phase]['drugs'].append(valuation.drug_name)

        return by_phase

    def get_valuation_by_indication(self) -> Dict[str, Dict]:
        """
        Aggregate pipeline value by therapeutic indication.

        Returns:
            Dictionary mapping indication to value and drug count
        """
        if self._drug_valuations is None:
            self.value_pipeline()

        by_indication = {}

        for valuation in self._drug_valuations:
            indication = valuation.indication

            if indication not in by_indication:
                by_indication[indication] = {
                    'value': 0.0,
                    'count': 0,
                    'drugs': []
                }

            by_indication[indication]['value'] += valuation.npv_risk_adjusted
            by_indication[indication]['count'] += 1
            by_indication[indication]['drugs'].append(valuation.drug_name)

        return by_indication

    def sensitivity_analysis_portfolio(
        self,
        discount_rate_range: List[float] = None
    ) -> Dict[str, float]:
        """
        Run sensitivity analysis on entire portfolio.

        Args:
            discount_rate_range: Range of discount rates to test

        Returns:
            Dictionary mapping discount rate to portfolio value
        """
        if discount_rate_range is None:
            discount_rate_range = [0.08, 0.10, 0.12, 0.15, 0.18]

        results = {}

        original_rate = self.discount_rate

        for rate in discount_rate_range:
            self.discount_rate = rate
            summary = self.value_pipeline()
            results[f"{rate:.1%}"] = summary.risk_adjusted_value

        # Restore original
        self.discount_rate = original_rate

        return results

    def get_top_assets(self, n: int = 3) -> List[DrugValuation]:
        """
        Get top N most valuable assets in pipeline.

        Args:
            n: Number of top assets to return

        Returns:
            List of top N drug valuations by NPV
        """
        if self._drug_valuations is None:
            self.value_pipeline()

        sorted_drugs = sorted(
            self._drug_valuations,
            key=lambda d: d.npv_risk_adjusted,
            reverse=True
        )

        return sorted_drugs[:n]
