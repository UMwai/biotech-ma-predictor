"""
Industry Assumptions and Benchmarks for Biotech Valuation

This module contains industry-standard assumptions, benchmarks, and parameters
used in biotech drug valuation, including probability of success by development
phase, discount rates, and revenue curve parameters.

All assumptions are based on historical industry data and academic research
from sources like BIO, MIT CBER, and investment banking M&A reports.
"""

from typing import Dict, Optional, Tuple
from enum import Enum


class ClinicalPhase(Enum):
    """Development phase of a drug candidate."""
    PRECLINICAL = "Preclinical"
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    NDA_FILED = "NDA Filed"
    APPROVED = "Approved"


class TherapeuticArea(Enum):
    """Major therapeutic areas with different success profiles."""
    ONCOLOGY_SOLID = "Oncology Solid Tumors"
    ONCOLOGY_HEMATOLOGY = "Oncology Hematology"
    RARE_DISEASE = "Rare Disease"
    OBESITY_METABOLIC = "Obesity/Metabolic"
    CNS = "CNS"
    IMMUNOLOGY = "Immunology"
    CARDIOVASCULAR = "Cardiovascular"
    INFECTIOUS_DISEASE = "Infectious Disease"
    RESPIRATORY = "Respiratory"


# Probability of Success (PoS) by Clinical Phase
# Source: BIO/Informa Pharma Intelligence Clinical Development Success Rates
PROBABILITY_OF_SUCCESS = {
    ClinicalPhase.PRECLINICAL: {
        'min': 0.05,
        'typical': 0.075,
        'max': 0.10,
        'description': 'Very early stage, high attrition'
    },
    ClinicalPhase.PHASE_1: {
        'min': 0.15,
        'typical': 0.175,
        'max': 0.20,
        'description': 'Safety established, efficacy unproven'
    },
    ClinicalPhase.PHASE_2: {
        'min': 0.25,
        'typical': 0.30,
        'max': 0.35,
        'description': 'Proof of concept critical phase'
    },
    ClinicalPhase.PHASE_3: {
        'min': 0.50,
        'typical': 0.60,
        'max': 0.70,
        'description': 'Pivotal trials, lower risk'
    },
    ClinicalPhase.NDA_FILED: {
        'min': 0.85,
        'typical': 0.90,
        'max': 0.95,
        'description': 'Regulatory review, high probability'
    },
    ClinicalPhase.APPROVED: {
        'min': 1.00,
        'typical': 1.00,
        'max': 1.00,
        'description': 'Already approved, commercial risk only'
    }
}

# Therapeutic area-specific PoS multipliers
# Some indications have systematically higher/lower success rates
TA_POS_MULTIPLIERS = {
    TherapeuticArea.ONCOLOGY_SOLID: 0.85,  # More challenging
    TherapeuticArea.ONCOLOGY_HEMATOLOGY: 1.10,  # Better success rate
    TherapeuticArea.RARE_DISEASE: 1.15,  # Higher success, smaller trials
    TherapeuticArea.OBESITY_METABOLIC: 0.90,  # Competitive, challenging endpoints
    TherapeuticArea.CNS: 0.75,  # Historically difficult
    TherapeuticArea.IMMUNOLOGY: 1.05,  # Moderate success
    TherapeuticArea.CARDIOVASCULAR: 0.95,  # Established but competitive
    TherapeuticArea.INFECTIOUS_DISEASE: 1.00,  # Baseline
    TherapeuticArea.RESPIRATORY: 0.95,  # Moderate
}

# Discount Rates (WACC) by Company Profile
# Higher risk companies require higher discount rates
DISCOUNT_RATES = {
    'preclinical_biotech': {
        'min': 0.15,
        'typical': 0.18,
        'max': 0.25,
        'description': 'Early stage, single asset, high risk'
    },
    'clinical_stage': {
        'min': 0.12,
        'typical': 0.15,
        'max': 0.18,
        'description': 'Clinical assets, moderate risk'
    },
    'late_stage': {
        'min': 0.10,
        'typical': 0.12,
        'max': 0.15,
        'description': 'Phase 3 or NDA, lower risk'
    },
    'commercial': {
        'min': 0.08,
        'typical': 0.10,
        'max': 0.12,
        'description': 'Revenue generating, established'
    },
    'big_pharma': {
        'min': 0.07,
        'typical': 0.09,
        'max': 0.11,
        'description': 'Large cap, diversified, lowest risk'
    }
}

# Revenue Curve Parameters by Drug Type
# Different drugs have different revenue trajectories
REVENUE_CURVES = {
    'standard': {
        'ramp_years': 5,
        'peak_years': 3,
        'decline_start_year': 8,
        'patent_cliff_multiplier': 0.30,  # 70% revenue loss at LOE
        'description': 'Typical small molecule or biologic'
    },
    'blockbuster': {
        'ramp_years': 4,
        'peak_years': 5,
        'decline_start_year': 9,
        'patent_cliff_multiplier': 0.25,  # Steeper decline
        'description': 'Major innovation, large market'
    },
    'orphan': {
        'ramp_years': 3,
        'peak_years': 7,
        'decline_start_year': 10,
        'patent_cliff_multiplier': 0.50,  # More sustained, less generic competition
        'description': 'Rare disease, limited competition'
    },
    'fast_follower': {
        'ramp_years': 3,
        'peak_years': 2,
        'decline_start_year': 5,
        'patent_cliff_multiplier': 0.20,  # Heavy competition
        'description': 'Me-too drug in competitive market'
    },
    'gene_therapy': {
        'ramp_years': 2,
        'peak_years': 8,
        'decline_start_year': 10,
        'patent_cliff_multiplier': 0.60,  # Durable with limited competition
        'description': 'One-time treatment, curative'
    }
}

# Operating Margin Assumptions
# Varies significantly by company stage
OPERATING_MARGINS = {
    'preclinical': -1.00,  # Pure cash burn
    'clinical_stage': -0.80,  # High R&D spend
    'commercial_early': 0.10,  # Just launched, high SG&A
    'commercial_mature': 0.30,  # Established product
    'blockbuster': 0.45,  # Economies of scale
    'big_pharma': 0.25,  # Diversified portfolio average
}

# Cost of Goods Sold (COGS) as % of Revenue
COGS_ASSUMPTIONS = {
    'small_molecule': 0.15,  # Low manufacturing cost
    'biologic': 0.25,  # Higher manufacturing cost
    'cell_therapy': 0.40,  # Very high, personalized
    'gene_therapy': 0.35,  # High complexity
}

# SG&A as % of Revenue (Sales, General, Administrative)
SGA_ASSUMPTIONS = {
    'partner_commercialized': 0.05,  # Partner handles sales
    'self_commercialized_orphan': 0.25,  # Focused sales force
    'self_commercialized_primary': 0.35,  # Large sales force needed
    'big_pharma': 0.30,  # Established infrastructure
}

# R&D as % of Revenue
RD_ASSUMPTIONS = {
    'single_asset_commercial': 0.20,  # Maintaining approved drug
    'pipeline_active': 0.40,  # Building pipeline
    'big_pharma': 0.15,  # Diversified spending
}

# Tax Rates
TAX_RATES = {
    'us_federal': 0.21,
    'effective_biotech': 0.15,  # Often lower due to credits, losses
    'effective_pharma': 0.20,
}

# Terminal Value Assumptions
TERMINAL_VALUE = {
    'growth_rate_perpetuity': 0.02,  # Conservative long-term growth
    'exit_multiple_ebitda': 12.0,  # Typical M&A multiple
    'patent_expiry_residual': 0.15,  # % of peak sales post-LOE
}


def get_pos_by_phase(
    phase: ClinicalPhase,
    therapeutic_area: Optional[TherapeuticArea] = None,
    use_typical: bool = True
) -> float:
    """
    Get probability of success for a given clinical phase.

    Args:
        phase: Development phase of the drug
        therapeutic_area: Optional therapeutic area for adjustment
        use_typical: If True, return typical value; else return conservative (min)

    Returns:
        Probability of success as a float between 0 and 1

    Examples:
        >>> get_pos_by_phase(ClinicalPhase.PHASE_2)
        0.30
        >>> get_pos_by_phase(ClinicalPhase.PHASE_2, TherapeuticArea.CNS)
        0.225  # 0.30 * 0.75 multiplier for CNS
    """
    base_pos = PROBABILITY_OF_SUCCESS[phase]
    pos_value = base_pos['typical'] if use_typical else base_pos['min']

    if therapeutic_area:
        multiplier = TA_POS_MULTIPLIERS.get(therapeutic_area, 1.0)
        pos_value *= multiplier

    # Cap at 1.0
    return min(pos_value, 1.0)


def get_default_discount_rate(
    company_stage: str = 'clinical_stage',
    use_typical: bool = True
) -> float:
    """
    Get appropriate discount rate based on company stage.

    Args:
        company_stage: Stage of company (preclinical_biotech, clinical_stage, etc.)
        use_typical: If True, return typical value; else return conservative (max)

    Returns:
        Discount rate as a float (e.g., 0.15 for 15%)

    Examples:
        >>> get_default_discount_rate('clinical_stage')
        0.15
        >>> get_default_discount_rate('big_pharma', use_typical=False)
        0.11
    """
    rates = DISCOUNT_RATES.get(company_stage, DISCOUNT_RATES['clinical_stage'])
    return rates['typical'] if use_typical else rates['max']


def get_revenue_curve_params(curve_type: str = 'standard') -> Dict:
    """
    Get revenue curve parameters for a specific drug type.

    Args:
        curve_type: Type of revenue curve (standard, blockbuster, orphan, etc.)

    Returns:
        Dictionary of curve parameters

    Examples:
        >>> params = get_revenue_curve_params('blockbuster')
        >>> params['ramp_years']
        4
    """
    return REVENUE_CURVES.get(curve_type, REVENUE_CURVES['standard']).copy()


def calculate_effective_tax_rate(
    has_revenue: bool = False,
    has_nols: bool = True,
    jurisdiction: str = 'us'
) -> float:
    """
    Calculate effective tax rate based on company situation.

    Args:
        has_revenue: Whether company is generating revenue
        has_nols: Whether company has Net Operating Losses to offset
        jurisdiction: Tax jurisdiction

    Returns:
        Effective tax rate as float

    Examples:
        >>> calculate_effective_tax_rate(has_revenue=False)
        0.0  # No tax on losses
        >>> calculate_effective_tax_rate(has_revenue=True, has_nols=False)
        0.20
    """
    if not has_revenue:
        return 0.0

    if has_nols:
        return 0.05  # Minimal tax due to NOL carryforwards

    return TAX_RATES.get('effective_pharma', 0.20)


def get_cost_structure(
    drug_type: str = 'biologic',
    commercialization: str = 'partner_commercialized',
    development_stage: str = 'commercial_early'
) -> Dict[str, float]:
    """
    Get expected cost structure for a drug program.

    Args:
        drug_type: Type of drug (small_molecule, biologic, cell_therapy, gene_therapy)
        commercialization: Commercialization strategy
        development_stage: Current development stage

    Returns:
        Dictionary with cogs, sga, rd, and margin assumptions

    Examples:
        >>> costs = get_cost_structure('biologic', 'self_commercialized_orphan')
        >>> costs['cogs']
        0.25
    """
    return {
        'cogs': COGS_ASSUMPTIONS.get(drug_type, 0.25),
        'sga': SGA_ASSUMPTIONS.get(commercialization, 0.30),
        'rd': RD_ASSUMPTIONS.get(development_stage, 0.20),
        'operating_margin': OPERATING_MARGINS.get(development_stage, 0.20),
    }


# Peak penetration assumptions by market type
PEAK_PENETRATION_RATES = {
    'first_in_class': 0.30,  # 30% of addressable patients
    'best_in_class': 0.25,
    'competitive': 0.15,
    'me_too': 0.08,
    'orphan_dominant': 0.50,  # Higher capture in rare disease
}


def estimate_market_share(
    competitive_position: str = 'competitive',
    time_to_market: int = 0
) -> float:
    """
    Estimate peak market penetration based on competitive dynamics.

    Args:
        competitive_position: Position in market (first_in_class, best_in_class, etc.)
        time_to_market: Years since first competitor launched (penalizes late entry)

    Returns:
        Estimated peak penetration rate

    Examples:
        >>> estimate_market_share('first_in_class')
        0.30
        >>> estimate_market_share('competitive', time_to_market=3)
        0.1125  # 15% * 0.75 penalty for being 3 years late
    """
    base_share = PEAK_PENETRATION_RATES.get(competitive_position, 0.15)

    # Penalty for late entry: 25% reduction per year late
    if time_to_market > 0:
        penalty = 0.75 ** time_to_market
        base_share *= penalty

    return base_share
