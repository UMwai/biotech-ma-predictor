"""
Comparable transaction analysis for biotech M&A valuation.

This module tracks historical M&A deals and provides valuation benchmarks
based on comparable transactions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
import statistics


class TherapeuticArea(Enum):
    """Major therapeutic areas in biotech."""
    ONCOLOGY = "oncology"
    IMMUNOLOGY = "immunology"
    CNS = "cns"
    METABOLIC = "metabolic"
    RARE_DISEASE = "rare_disease"
    CARDIOVASCULAR = "cardiovascular"
    INFECTIOUS_DISEASE = "infectious_disease"
    OTHER = "other"


class DevelopmentStage(Enum):
    """Drug development stages."""
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    APPROVED = "approved"
    MARKETED = "marketed"


class DealStructure(Enum):
    """Types of deal structures."""
    ALL_CASH = "all_cash"
    CASH_AND_STOCK = "cash_and_stock"
    STOCK_ONLY = "stock_only"
    WITH_CVR = "with_cvr"  # Contingent Value Rights


@dataclass
class Deal:
    """Represents a completed M&A transaction."""
    acquirer: str
    target: str
    announcement_date: datetime
    total_value_bn: float  # Total deal value in billions
    upfront_value_bn: float  # Upfront payment in billions
    milestone_value_bn: float  # Potential milestones in billions
    therapeutic_area: TherapeuticArea
    development_stage: DevelopmentStage
    deal_structure: DealStructure
    key_assets: List[str]
    premium_to_undisturbed: Optional[float] = None  # Percentage
    ev_to_peak_sales: Optional[float] = None
    strategic_rationale: Optional[str] = None

    @property
    def has_milestones(self) -> bool:
        """Check if deal includes milestone payments."""
        return self.milestone_value_bn > 0

    @property
    def upfront_ratio(self) -> float:
        """Calculate upfront payment as percentage of total value."""
        if self.total_value_bn == 0:
            return 0.0
        return (self.upfront_value_bn / self.total_value_bn) * 100


@dataclass
class ValuationRange:
    """Valuation range based on comparable analysis."""
    low: float  # In billions
    median: float
    high: float
    methodology: str
    comparable_count: int
    confidence_level: str  # "high", "medium", "low"

    def __repr__(self) -> str:
        return f"${self.low:.1f}B - ${self.median:.1f}B - ${self.high:.1f}B ({self.confidence_level} confidence)"


@dataclass
class PremiumStats:
    """Premium statistics by sector."""
    sector: str
    median_premium: float
    min_premium: float
    max_premium: float
    sample_size: int
    percentile_25: float
    percentile_75: float

    def __repr__(self) -> str:
        return f"{self.sector}: {self.median_premium:.1f}% median premium (n={self.sample_size})"


class ComparableDeals:
    """
    Track and analyze comparable M&A transactions.

    This class maintains a database of historical biotech M&A deals
    and provides valuation benchmarks based on comparable analysis.
    """

    def __init__(self):
        """Initialize with recent biotech M&A benchmark data (2023-2025)."""
        self.deals: List[Deal] = self._initialize_benchmark_deals()

    def _initialize_benchmark_deals(self) -> List[Deal]:
        """Initialize database with recent major biotech M&A transactions."""
        return [
            Deal(
                acquirer="Pfizer",
                target="Seagen",
                announcement_date=datetime(2023, 3, 13),
                total_value_bn=43.0,
                upfront_value_bn=43.0,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.ONCOLOGY,
                development_stage=DevelopmentStage.MARKETED,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["Adcetris", "Padcev", "Tukysa", "Tivdak"],
                premium_to_undisturbed=32.8,
                ev_to_peak_sales=2.1,
                strategic_rationale="ADC platform and marketed oncology portfolio"
            ),
            Deal(
                acquirer="Pfizer",
                target="Metsera",
                announcement_date=datetime(2025, 1, 15),
                total_value_bn=10.0,
                upfront_value_bn=1.0,
                milestone_value_bn=9.0,
                therapeutic_area=TherapeuticArea.METABOLIC,
                development_stage=DevelopmentStage.PHASE_3,
                deal_structure=DealStructure.WITH_CVR,
                key_assets=["MET-097 (obesity)"],
                premium_to_undisturbed=85.0,
                ev_to_peak_sales=0.8,
                strategic_rationale="Entry into obesity market"
            ),
            Deal(
                acquirer="Merck",
                target="Prometheus Biosciences",
                announcement_date=datetime(2023, 4, 16),
                total_value_bn=10.8,
                upfront_value_bn=10.8,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.IMMUNOLOGY,
                development_stage=DevelopmentStage.PHASE_2,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["PRA023 (IBD)"],
                premium_to_undisturbed=75.0,
                ev_to_peak_sales=1.2,
                strategic_rationale="Immunology pipeline expansion"
            ),
            Deal(
                acquirer="Bristol Myers Squibb",
                target="Karuna Therapeutics",
                announcement_date=datetime(2023, 12, 22),
                total_value_bn=14.0,
                upfront_value_bn=14.0,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.CNS,
                development_stage=DevelopmentStage.PHASE_3,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["KarXT (schizophrenia)"],
                premium_to_undisturbed=53.0,
                ev_to_peak_sales=2.8,
                strategic_rationale="CNS portfolio expansion"
            ),
            Deal(
                acquirer="AbbVie",
                target="ImmunoGen",
                announcement_date=datetime(2023, 11, 30),
                total_value_bn=10.1,
                upfront_value_bn=10.1,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.ONCOLOGY,
                development_stage=DevelopmentStage.APPROVED,
                key_assets=["Elahere (ovarian cancer)", "ADC platform"],
                deal_structure=DealStructure.ALL_CASH,
                premium_to_undisturbed=94.5,
                ev_to_peak_sales=3.2,
                strategic_rationale="ADC technology and oncology expansion"
            ),
            Deal(
                acquirer="Roche",
                target="Telavant",
                announcement_date=datetime(2023, 10, 23),
                total_value_bn=7.1,
                upfront_value_bn=7.1,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.IMMUNOLOGY,
                development_stage=DevelopmentStage.PHASE_2,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["TL1A inhibitor (IBD)"],
                premium_to_undisturbed=None,  # Private company
                ev_to_peak_sales=1.5,
                strategic_rationale="IBD pipeline strengthening"
            ),
            Deal(
                acquirer="Johnson & Johnson",
                target="Ambrx",
                announcement_date=datetime(2024, 1, 8),
                total_value_bn=2.0,
                upfront_value_bn=2.0,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.ONCOLOGY,
                development_stage=DevelopmentStage.PHASE_2,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["ARX517 (prostate cancer)", "ADC platform"],
                premium_to_undisturbed=102.0,
                ev_to_peak_sales=0.9,
                strategic_rationale="ADC platform expansion"
            ),
            Deal(
                acquirer="Novartis",
                target="Chinook Therapeutics",
                announcement_date=datetime(2023, 4, 3),
                total_value_bn=3.5,
                upfront_value_bn=3.5,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.RARE_DISEASE,
                development_stage=DevelopmentStage.PHASE_3,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["Atrasentan (kidney disease)"],
                premium_to_undisturbed=68.0,
                ev_to_peak_sales=2.3,
                strategic_rationale="Rare disease portfolio expansion"
            ),
            Deal(
                acquirer="Eli Lilly",
                target="Dice Therapeutics",
                announcement_date=datetime(2023, 2, 1),
                total_value_bn=2.4,
                upfront_value_bn=2.4,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.IMMUNOLOGY,
                development_stage=DevelopmentStage.PHASE_2,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["S1P receptor modulator"],
                premium_to_undisturbed=56.0,
                ev_to_peak_sales=1.1,
                strategic_rationale="Immunology pipeline strengthening"
            ),
            Deal(
                acquirer="Sanofi",
                target="Provention Bio",
                announcement_date=datetime(2023, 4, 27),
                total_value_bn=2.9,
                upfront_value_bn=2.9,
                milestone_value_bn=0.0,
                therapeutic_area=TherapeuticArea.METABOLIC,
                development_stage=DevelopmentStage.APPROVED,
                deal_structure=DealStructure.ALL_CASH,
                key_assets=["Tzield (Type 1 diabetes)"],
                premium_to_undisturbed=102.8,
                ev_to_peak_sales=3.5,
                strategic_rationale="Immunology and diabetes expansion"
            ),
        ]

    def add_deal(self, deal: Deal) -> None:
        """Add a new deal to the database."""
        self.deals.append(deal)

    def find_comparables(
        self,
        therapeutic_area: Optional[TherapeuticArea] = None,
        development_stage: Optional[DevelopmentStage] = None,
        min_value_bn: Optional[float] = None,
        max_value_bn: Optional[float] = None,
        lookback_years: int = 3
    ) -> List[Deal]:
        """
        Find comparable deals based on filtering criteria.

        Args:
            therapeutic_area: Filter by therapeutic area
            development_stage: Filter by development stage
            min_value_bn: Minimum deal value in billions
            max_value_bn: Maximum deal value in billions
            lookback_years: Only include deals from last N years

        Returns:
            List of comparable deals
        """
        cutoff_date = datetime.now().replace(year=datetime.now().year - lookback_years)

        comparables = [d for d in self.deals if d.announcement_date >= cutoff_date]

        if therapeutic_area:
            comparables = [d for d in comparables if d.therapeutic_area == therapeutic_area]

        if development_stage:
            comparables = [d for d in comparables if d.development_stage == development_stage]

        if min_value_bn is not None:
            comparables = [d for d in comparables if d.total_value_bn >= min_value_bn]

        if max_value_bn is not None:
            comparables = [d for d in comparables if d.total_value_bn <= max_value_bn]

        return sorted(comparables, key=lambda x: x.announcement_date, reverse=True)

    def calculate_implied_valuation(
        self,
        therapeutic_area: TherapeuticArea,
        development_stage: DevelopmentStage,
        peak_sales_estimate: Optional[float] = None
    ) -> ValuationRange:
        """
        Calculate implied valuation range based on comparable transactions.

        Args:
            therapeutic_area: Target company's therapeutic area
            development_stage: Target company's development stage
            peak_sales_estimate: Estimated peak sales in billions (optional)

        Returns:
            ValuationRange with low, median, high estimates
        """
        # Find comparable deals
        comparables = self.find_comparables(
            therapeutic_area=therapeutic_area,
            development_stage=development_stage
        )

        # If no exact matches, broaden search
        if len(comparables) < 3:
            comparables = self.find_comparables(therapeutic_area=therapeutic_area)

        if len(comparables) < 3:
            comparables = self.find_comparables(development_stage=development_stage)

        if len(comparables) == 0:
            return ValuationRange(
                low=0.5,
                median=2.0,
                high=5.0,
                methodology="insufficient_comparables",
                comparable_count=0,
                confidence_level="low"
            )

        # Calculate valuation based on deal values
        values = [d.total_value_bn for d in comparables]

        low = min(values)
        high = max(values)
        median = statistics.median(values)

        # If peak sales estimate provided, use EV/Peak Sales multiples
        if peak_sales_estimate and peak_sales_estimate > 0:
            multiples = [d.ev_to_peak_sales for d in comparables if d.ev_to_peak_sales]

            if multiples:
                low_multiple = min(multiples)
                high_multiple = max(multiples)
                median_multiple = statistics.median(multiples)

                low = peak_sales_estimate * low_multiple
                median = peak_sales_estimate * median_multiple
                high = peak_sales_estimate * high_multiple
                methodology = f"ev_peak_sales_multiple (n={len(multiples)})"
            else:
                methodology = f"comparable_deal_values (n={len(comparables)})"
        else:
            methodology = f"comparable_deal_values (n={len(comparables)})"

        # Determine confidence level
        if len(comparables) >= 5 and peak_sales_estimate:
            confidence = "high"
        elif len(comparables) >= 3:
            confidence = "medium"
        else:
            confidence = "low"

        return ValuationRange(
            low=low,
            median=median,
            high=high,
            methodology=methodology,
            comparable_count=len(comparables),
            confidence_level=confidence
        )

    def premium_analysis(
        self,
        therapeutic_area: Optional[TherapeuticArea] = None
    ) -> PremiumStats:
        """
        Calculate premium statistics from comparable deals.

        Args:
            therapeutic_area: Optional filter by therapeutic area

        Returns:
            PremiumStats with median, range, and percentiles
        """
        if therapeutic_area:
            relevant_deals = [
                d for d in self.deals
                if d.therapeutic_area == therapeutic_area and d.premium_to_undisturbed
            ]
            sector = therapeutic_area.value
        else:
            relevant_deals = [d for d in self.deals if d.premium_to_undisturbed]
            sector = "all_biotech"

        if not relevant_deals:
            return PremiumStats(
                sector=sector,
                median_premium=50.0,
                min_premium=30.0,
                max_premium=80.0,
                sample_size=0,
                percentile_25=40.0,
                percentile_75=70.0
            )

        premiums = [d.premium_to_undisturbed for d in relevant_deals]

        return PremiumStats(
            sector=sector,
            median_premium=statistics.median(premiums),
            min_premium=min(premiums),
            max_premium=max(premiums),
            sample_size=len(premiums),
            percentile_25=statistics.quantiles(premiums, n=4)[0],
            percentile_75=statistics.quantiles(premiums, n=4)[2]
        )

    def get_deal_structure_trends(self) -> Dict[str, float]:
        """
        Analyze trends in deal structures.

        Returns:
            Dictionary with percentages for each deal structure type
        """
        total = len(self.deals)
        if total == 0:
            return {}

        structure_counts = {}
        for deal in self.deals:
            structure = deal.deal_structure.value
            structure_counts[structure] = structure_counts.get(structure, 0) + 1

        return {
            structure: (count / total) * 100
            for structure, count in structure_counts.items()
        }

    def get_average_upfront_ratio(
        self,
        development_stage: Optional[DevelopmentStage] = None
    ) -> float:
        """
        Calculate average upfront payment ratio.

        Args:
            development_stage: Optional filter by development stage

        Returns:
            Average upfront ratio as percentage
        """
        if development_stage:
            relevant_deals = [
                d for d in self.deals if d.development_stage == development_stage
            ]
        else:
            relevant_deals = self.deals

        if not relevant_deals:
            return 80.0  # Default assumption

        ratios = [d.upfront_ratio for d in relevant_deals]
        return statistics.mean(ratios)

    def get_hot_therapeutic_areas(self, lookback_months: int = 12) -> List[tuple]:
        """
        Identify therapeutic areas with most M&A activity.

        Args:
            lookback_months: Period to analyze

        Returns:
            List of (therapeutic_area, deal_count, total_value_bn) tuples
        """
        cutoff_date = datetime.now().replace(month=max(1, datetime.now().month - lookback_months))
        recent_deals = [d for d in self.deals if d.announcement_date >= cutoff_date]

        area_stats = {}
        for deal in recent_deals:
            area = deal.therapeutic_area.value
            if area not in area_stats:
                area_stats[area] = {"count": 0, "total_value": 0.0}
            area_stats[area]["count"] += 1
            area_stats[area]["total_value"] += deal.total_value_bn

        result = [
            (area, stats["count"], stats["total_value"])
            for area, stats in area_stats.items()
        ]

        return sorted(result, key=lambda x: x[2], reverse=True)  # Sort by total value
