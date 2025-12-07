"""
Biotech Drug Valuation Module

This module provides comprehensive DCF (Discounted Cash Flow) valuation
models specifically designed for biotech M&A prediction and drug pipeline analysis.

Main Components:
- DrugDCF: Core DCF valuation engine for individual drug candidates
- PipelineValuation: Multi-drug portfolio valuation with sum-of-parts analysis
- Revenue projection models tailored to different drug categories
- Industry-standard probability of success (PoS) adjustments
- Sensitivity analysis and scenario modeling

Typical Usage:
    >>> from src.valuation import DrugDCF, PipelineValuation
    >>> drug_dcf = DrugDCF(
    ...     peak_sales_estimate=2.5e9,
    ...     time_to_peak=5,
    ...     patent_life_remaining=12,
    ...     probability_of_success=0.30,
    ...     clinical_phase='Phase 2'
    ... )
    >>> npv = drug_dcf.calculate_npv(discount_rate=0.12)
    >>> sensitivity = drug_dcf.sensitivity_analysis()
"""

from .dcf_model import DrugDCF, DrugValuation
from .assumptions import (
    ClinicalPhase,
    TherapeuticArea,
    PROBABILITY_OF_SUCCESS,
    DISCOUNT_RATES,
    REVENUE_CURVES,
    get_default_discount_rate,
    get_pos_by_phase,
    get_revenue_curve_params
)
from .drug_revenue import (
    RevenueProjector,
    RevenueCurveType,
    IndicationCategory,
    IndicationTAM,
    project_standard_curve,
    project_blockbuster_curve,
    project_orphan_curve,
    estimate_peak_sales
)
from .pipeline_valuation import (
    PipelineValuation,
    DrugCandidate,
    PortfolioSummary
)

__all__ = [
    # Core DCF classes
    'DrugDCF',
    'DrugValuation',
    'PipelineValuation',
    'DrugCandidate',
    'PortfolioSummary',

    # Enums
    'ClinicalPhase',
    'TherapeuticArea',
    'RevenueCurveType',
    'IndicationCategory',

    # Revenue projection
    'RevenueProjector',
    'IndicationTAM',
    'project_standard_curve',
    'project_blockbuster_curve',
    'project_orphan_curve',
    'estimate_peak_sales',

    # Assumptions and constants
    'PROBABILITY_OF_SUCCESS',
    'DISCOUNT_RATES',
    'REVENUE_CURVES',
    'get_default_discount_rate',
    'get_pos_by_phase',
    'get_revenue_curve_params',
]

__version__ = '1.0.0'
