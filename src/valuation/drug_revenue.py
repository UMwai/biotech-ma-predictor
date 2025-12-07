"""
Drug Revenue Projection Models

This module provides sophisticated revenue projection models for different
types of drugs and indications. Includes indication-specific TAM estimates
and multiple revenue curve models (standard, blockbuster, orphan).

Revenue curves model the typical lifecycle of a drug from launch through
patent expiry, with different curves for different drug categories.
"""

from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import math


class RevenueCurveType(Enum):
    """Types of revenue curves for different drug categories."""
    STANDARD = "standard"
    BLOCKBUSTER = "blockbuster"
    ORPHAN = "orphan"
    FAST_FOLLOWER = "fast_follower"
    GENE_THERAPY = "gene_therapy"


class IndicationCategory(Enum):
    """Major indication categories with distinct market characteristics."""
    ONCOLOGY_SOLID = "Oncology Solid Tumors"
    ONCOLOGY_HEMATOLOGY = "Oncology Hematology"
    RARE_DISEASE = "Rare Disease"
    OBESITY_METABOLIC = "Obesity/Metabolic"
    CNS = "CNS"
    IMMUNOLOGY = "Immunology"
    CARDIOVASCULAR = "Cardiovascular"
    INFECTIOUS_DISEASE = "Infectious Disease"


@dataclass
class IndicationTAM:
    """
    Total Addressable Market (TAM) estimates by indication.

    Attributes:
        category: Therapeutic category
        tam_low: Conservative TAM estimate (USD)
        tam_typical: Typical TAM estimate (USD)
        tam_high: Optimistic TAM estimate (USD)
        patient_population: Estimated addressable patients
        description: Market description
    """
    category: IndicationCategory
    tam_low: float
    tam_typical: float
    tam_high: float
    patient_population: int
    description: str


# Indication-Specific TAM Database
INDICATION_TAMS = {
    IndicationCategory.ONCOLOGY_SOLID: IndicationTAM(
        category=IndicationCategory.ONCOLOGY_SOLID,
        tam_low=5e9,
        tam_typical=20e9,
        tam_high=50e9,
        patient_population=500000,
        description="Solid tumor oncology - lung, breast, colorectal, etc."
    ),
    IndicationCategory.ONCOLOGY_HEMATOLOGY: IndicationTAM(
        category=IndicationCategory.ONCOLOGY_HEMATOLOGY,
        tam_low=3e9,
        tam_typical=10e9,
        tam_high=25e9,
        patient_population=200000,
        description="Hematological malignancies - leukemia, lymphoma, myeloma"
    ),
    IndicationCategory.RARE_DISEASE: IndicationTAM(
        category=IndicationCategory.RARE_DISEASE,
        tam_low=500e6,
        tam_typical=1e9,
        tam_high=2e9,
        patient_population=20000,
        description="Orphan diseases - <200k patients in US"
    ),
    IndicationCategory.OBESITY_METABOLIC: IndicationTAM(
        category=IndicationCategory.OBESITY_METABOLIC,
        tam_low=50e9,
        tam_typical=75e9,
        tam_high=100e9,
        patient_population=100000000,
        description="Obesity, diabetes, metabolic syndrome - huge hot market"
    ),
    IndicationCategory.CNS: IndicationTAM(
        category=IndicationCategory.CNS,
        tam_low=10e9,
        tam_typical=20e9,
        tam_high=30e9,
        patient_population=5000000,
        description="CNS disorders - Alzheimer's, Parkinson's, depression, etc."
    ),
    IndicationCategory.IMMUNOLOGY: IndicationTAM(
        category=IndicationCategory.IMMUNOLOGY,
        tam_low=20e9,
        tam_typical=35e9,
        tam_high=50e9,
        patient_population=10000000,
        description="Autoimmune and inflammatory diseases"
    ),
    IndicationCategory.CARDIOVASCULAR: IndicationTAM(
        category=IndicationCategory.CARDIOVASCULAR,
        tam_low=15e9,
        tam_typical=30e9,
        tam_high=45e9,
        patient_population=20000000,
        description="Cardiovascular diseases - established but competitive"
    ),
    IndicationCategory.INFECTIOUS_DISEASE: IndicationTAM(
        category=IndicationCategory.INFECTIOUS_DISEASE,
        tam_low=5e9,
        tam_typical=12e9,
        tam_high=25e9,
        patient_population=3000000,
        description="Infectious diseases - antibiotics, antivirals, vaccines"
    ),
}


class RevenueProjector:
    """
    Projects drug revenues over time using various curve models.

    This class implements multiple revenue trajectory models based on
    drug characteristics, market dynamics, and patent lifecycle.
    """

    def __init__(
        self,
        peak_sales: float,
        curve_type: RevenueCurveType = RevenueCurveType.STANDARD,
        custom_params: Optional[Dict] = None
    ):
        """
        Initialize revenue projector.

        Args:
            peak_sales: Expected peak annual sales (USD)
            curve_type: Type of revenue curve to use
            custom_params: Optional custom parameters to override defaults
        """
        self.peak_sales = peak_sales
        self.curve_type = curve_type
        self.params = self._get_curve_params(curve_type)

        if custom_params:
            self.params.update(custom_params)

    def _get_curve_params(self, curve_type: RevenueCurveType) -> Dict:
        """Get default parameters for a curve type."""
        from .assumptions import REVENUE_CURVES

        curve_name = curve_type.value
        return REVENUE_CURVES.get(curve_name, REVENUE_CURVES['standard']).copy()

    def project_revenues(
        self,
        years_to_launch: int = 0,
        total_years: int = 20,
        patent_life_remaining: int = 12
    ) -> List[float]:
        """
        Project revenue stream over time.

        Args:
            years_to_launch: Years until product launch
            total_years: Total years to project
            patent_life_remaining: Patent life remaining from launch

        Returns:
            List of projected annual revenues

        Examples:
            >>> projector = RevenueProjector(peak_sales=2.5e9)
            >>> revenues = projector.project_revenues(years_to_launch=3)
            >>> len(revenues)
            20
        """
        revenues = []

        for year in range(total_years):
            if year < years_to_launch:
                # Pre-launch, no revenue
                revenues.append(0.0)
            else:
                # Years since launch
                years_post_launch = year - years_to_launch
                revenue = self._calculate_year_revenue(
                    years_post_launch,
                    patent_life_remaining
                )
                revenues.append(revenue)

        return revenues

    def _calculate_year_revenue(
        self,
        years_post_launch: int,
        patent_life: int
    ) -> float:
        """
        Calculate revenue for a specific year post-launch.

        Uses S-curve for ramp, plateau for peak, exponential decay for decline.
        """
        ramp_years = self.params['ramp_years']
        peak_years = self.params['peak_years']
        decline_start = self.params['decline_start_year']
        patent_cliff = self.params['patent_cliff_multiplier']

        if years_post_launch < ramp_years:
            # Ramp phase - S-curve growth
            progress = years_post_launch / ramp_years
            # Smoothed S-curve using tanh
            ramp_factor = (math.tanh(3 * (progress - 0.5)) + 1) / 2
            return self.peak_sales * ramp_factor

        elif years_post_launch < decline_start:
            # Peak plateau phase
            return self.peak_sales

        elif years_post_launch < patent_life:
            # Gradual decline before patent expiry
            years_declining = years_post_launch - decline_start
            decline_years = patent_life - decline_start

            if decline_years > 0:
                decline_factor = 1 - (0.15 * (years_declining / decline_years))
                return self.peak_sales * max(decline_factor, patent_cliff + 0.1)
            else:
                return self.peak_sales

        else:
            # Post patent expiry - generic competition
            years_post_loe = years_post_launch - patent_life

            # Rapid initial decline, then stabilization
            if years_post_loe == 0:
                return self.peak_sales * patent_cliff
            else:
                # Further erosion: 10% per year for 3 years, then flat
                erosion_years = min(years_post_loe, 3)
                erosion_factor = (0.90 ** erosion_years)
                return self.peak_sales * patent_cliff * erosion_factor


def project_standard_curve(
    peak_sales: float,
    years_to_launch: int = 0,
    patent_life: int = 12,
    total_years: int = 20
) -> List[float]:
    """
    Project revenue using standard biotech curve.

    Standard curve: 5-year ramp, 3-year peak, then decline to LOE.

    Args:
        peak_sales: Expected peak annual sales
        years_to_launch: Years until launch
        patent_life: Patent life remaining from launch
        total_years: Total projection period

    Returns:
        List of annual revenues

    Examples:
        >>> revenues = project_standard_curve(peak_sales=1.5e9, years_to_launch=2)
        >>> max(revenues)  # Should be close to 1.5B
        1500000000.0
    """
    projector = RevenueProjector(peak_sales, RevenueCurveType.STANDARD)
    return projector.project_revenues(years_to_launch, total_years, patent_life)


def project_blockbuster_curve(
    peak_sales: float,
    years_to_launch: int = 0,
    patent_life: int = 12,
    total_years: int = 20
) -> List[float]:
    """
    Project revenue using blockbuster curve.

    Blockbuster: Faster 4-year ramp, extended 5-year peak, strong sales.

    Args:
        peak_sales: Expected peak annual sales
        years_to_launch: Years until launch
        patent_life: Patent life remaining from launch
        total_years: Total projection period

    Returns:
        List of annual revenues
    """
    projector = RevenueProjector(peak_sales, RevenueCurveType.BLOCKBUSTER)
    return projector.project_revenues(years_to_launch, total_years, patent_life)


def project_orphan_curve(
    peak_sales: float,
    years_to_launch: int = 0,
    patent_life: int = 12,
    total_years: int = 20
) -> List[float]:
    """
    Project revenue using orphan drug curve.

    Orphan: Quick 3-year ramp, stable 7-year peak, sustained post-LOE (50%).

    Args:
        peak_sales: Expected peak annual sales
        years_to_launch: Years until launch
        patent_life: Patent life remaining from launch
        total_years: Total projection period

    Returns:
        List of annual revenues
    """
    projector = RevenueProjector(peak_sales, RevenueCurveType.ORPHAN)
    return projector.project_revenues(years_to_launch, total_years, patent_life)


def estimate_peak_sales(
    indication: IndicationCategory,
    market_share: float = 0.15,
    use_typical_tam: bool = True,
    pricing_per_patient: Optional[float] = None
) -> float:
    """
    Estimate peak sales based on indication TAM and market dynamics.

    Args:
        indication: Therapeutic indication category
        market_share: Expected peak market share (e.g., 0.15 for 15%)
        use_typical_tam: Use typical TAM vs. optimistic/conservative
        pricing_per_patient: Optional per-patient annual pricing

    Returns:
        Estimated peak annual sales

    Examples:
        >>> peak = estimate_peak_sales(
        ...     IndicationCategory.RARE_DISEASE,
        ...     market_share=0.30
        ... )
        >>> peak  # 30% of $1B typical rare disease TAM
        300000000.0
    """
    tam_data = INDICATION_TAMS.get(indication)

    if not tam_data:
        raise ValueError(f"Unknown indication category: {indication}")

    # Select TAM estimate
    if use_typical_tam:
        tam = tam_data.tam_typical
    else:
        # Conservative approach
        tam = tam_data.tam_low

    # If pricing provided, calculate from patient population
    if pricing_per_patient:
        patients_treated = tam_data.patient_population * market_share
        return patients_treated * pricing_per_patient

    # Otherwise use market share of TAM
    return tam * market_share


def calculate_revenue_metrics(revenues: List[float]) -> Dict[str, float]:
    """
    Calculate key metrics from a revenue projection.

    Args:
        revenues: List of annual revenues

    Returns:
        Dictionary with metrics:
        - total_revenue: Cumulative revenue
        - peak_revenue: Maximum annual revenue
        - years_to_peak: Years to reach peak
        - average_revenue: Average annual revenue

    Examples:
        >>> revenues = [0, 500e6, 1e9, 1.5e9, 1.5e9, 1.2e9]
        >>> metrics = calculate_revenue_metrics(revenues)
        >>> metrics['peak_revenue']
        1500000000.0
    """
    if not revenues:
        return {
            'total_revenue': 0.0,
            'peak_revenue': 0.0,
            'years_to_peak': 0,
            'average_revenue': 0.0
        }

    peak_revenue = max(revenues)
    years_to_peak = revenues.index(peak_revenue)
    total_revenue = sum(revenues)
    average_revenue = total_revenue / len(revenues) if revenues else 0.0

    return {
        'total_revenue': total_revenue,
        'peak_revenue': peak_revenue,
        'years_to_peak': years_to_peak,
        'average_revenue': average_revenue,
    }


def apply_launch_risk(
    revenues: List[float],
    launch_probability: float = 0.90
) -> List[float]:
    """
    Apply launch risk adjustment to revenue projections.

    Even approved drugs can fail to launch or be withdrawn. This applies
    a haircut to account for commercial/launch risk.

    Args:
        revenues: Projected revenues
        launch_probability: Probability of successful launch (0-1)

    Returns:
        Risk-adjusted revenues
    """
    return [r * launch_probability for r in revenues]


def compare_curves(
    peak_sales: float,
    years_to_launch: int = 0
) -> Dict[str, List[float]]:
    """
    Compare all revenue curve types for the same drug.

    Useful for sensitivity analysis and understanding curve differences.

    Args:
        peak_sales: Peak sales estimate
        years_to_launch: Years to launch

    Returns:
        Dictionary mapping curve type to revenue projections

    Examples:
        >>> curves = compare_curves(peak_sales=2e9, years_to_launch=3)
        >>> curves.keys()
        dict_keys(['standard', 'blockbuster', 'orphan', 'fast_follower'])
    """
    results = {}

    for curve_type in RevenueCurveType:
        projector = RevenueProjector(peak_sales, curve_type)
        revenues = projector.project_revenues(years_to_launch=years_to_launch)
        results[curve_type.value] = revenues

    return results
