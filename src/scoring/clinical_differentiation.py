"""
Clinical Differentiation Scoring Module

Assesses the quality and competitive positioning of drug assets within their class.
Based on the Metsera case study where monthly GLP-1 formulation drove high acquisition value.

Key Factors:
- Dosing convenience (monthly > weekly > daily)
- Mechanism of action novelty (first-in-class > best-in-class > me-too)
- Clinical efficacy data quality
- Head-to-head trial data
- Safety/tolerability profile
- Formulation innovation
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class DosingFrequency(str, Enum):
    """Drug dosing frequency categories."""
    ONCE_MONTHLY = "once_monthly"
    TWICE_MONTHLY = "twice_monthly"
    ONCE_WEEKLY = "once_weekly"
    TWICE_WEEKLY = "twice_weekly"
    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    AS_NEEDED = "as_needed"


class RouteOfAdministration(str, Enum):
    """Route of drug administration."""
    SUBCUTANEOUS = "subcutaneous"
    INTRAMUSCULAR = "intramuscular"
    INTRAVENOUS = "intravenous"
    ORAL = "oral"
    TRANSDERMAL = "transdermal"
    INHALED = "inhaled"
    OTHER = "other"


class MOANovelty(str, Enum):
    """Mechanism of action novelty classification."""
    FIRST_IN_CLASS = "first_in_class"  # Novel MOA, no competitors
    BEST_IN_CLASS = "best_in_class"    # Improved efficacy/safety in existing class
    FAST_FOLLOWER = "fast_follower"    # Close behind leader, some differentiation
    ME_TOO = "me_too"                   # Similar to existing drugs, minimal differentiation


@dataclass
class DrugAsset:
    """
    Drug asset with clinical differentiation attributes.

    Attributes:
        name: Drug name
        indication: Primary indication
        dosing_frequency: How often drug is dosed
        route: Route of administration
        moa_novelty: Mechanism of action novelty level
        efficacy_data: Efficacy metrics from trials
        safety_data: Safety/tolerability metrics
        head_to_head_trials: Whether has head-to-head comparison data
        formulation_innovation: Novel formulation technology
    """
    name: str
    indication: str
    dosing_frequency: DosingFrequency
    route: RouteOfAdministration
    moa_novelty: MOANovelty

    # Efficacy data
    primary_endpoint_met: bool = False
    primary_endpoint_value: Optional[float] = None  # e.g., % weight loss, response rate
    statistical_significance: Optional[float] = None  # p-value
    effect_size: Optional[float] = None  # Cohen's d or similar

    # Safety data
    adverse_event_rate: Optional[float] = None  # % patients with AEs
    serious_ae_rate: Optional[float] = None
    discontinuation_rate: Optional[float] = None

    # Competitive positioning
    head_to_head_trials: bool = False
    head_to_head_superiority: bool = False
    competitor_efficacy_delta: Optional[float] = None  # % improvement vs competitor

    # Innovation
    formulation_innovation: bool = False
    delivery_innovation: bool = False  # e.g., needle-free, oral bioavailability
    patent_protected_formulation: bool = False

    # Market factors
    patient_preference_score: Optional[float] = None  # Survey data, 0-10
    physician_preference_score: Optional[float] = None

    last_update: Optional[datetime] = None


class ClinicalDifferentiation:
    """
    Calculate clinical differentiation score for drug assets.

    Higher scores indicate stronger competitive positioning and higher
    likelihood of premium acquisition valuation (like Metsera's GLP-1).

    Example:
        >>> drug = DrugAsset(
        ...     name="GLP-1 Monthly",
        ...     indication="Obesity",
        ...     dosing_frequency=DosingFrequency.ONCE_MONTHLY,
        ...     route=RouteOfAdministration.SUBCUTANEOUS,
        ...     moa_novelty=MOANovelty.BEST_IN_CLASS,
        ...     head_to_head_superiority=True
        ... )
        >>> scorer = ClinicalDifferentiation()
        >>> score = scorer.calculate_total(drug)
        >>> print(f"Clinical Differentiation: {score:.1f}")
    """

    def __init__(self):
        """Initialize clinical differentiation scorer."""

        # Dosing convenience scores (0-100 scale)
        # Monthly dosing is premium (Metsera example)
        self.dosing_scores = {
            DosingFrequency.ONCE_MONTHLY: 100,
            DosingFrequency.TWICE_MONTHLY: 85,
            DosingFrequency.ONCE_WEEKLY: 75,
            DosingFrequency.TWICE_WEEKLY: 65,
            DosingFrequency.ONCE_DAILY: 50,
            DosingFrequency.TWICE_DAILY: 35,
            DosingFrequency.THREE_TIMES_DAILY: 25,
            DosingFrequency.AS_NEEDED: 40,
        }

        # Route preference (some routes allow better convenience)
        self.route_multipliers = {
            RouteOfAdministration.ORAL: 1.2,  # Most convenient
            RouteOfAdministration.SUBCUTANEOUS: 1.0,
            RouteOfAdministration.TRANSDERMAL: 1.1,
            RouteOfAdministration.INHALED: 0.95,
            RouteOfAdministration.INTRAMUSCULAR: 0.85,
            RouteOfAdministration.INTRAVENOUS: 0.7,  # Least convenient
            RouteOfAdministration.OTHER: 0.8,
        }

        # MOA novelty scores
        self.moa_scores = {
            MOANovelty.FIRST_IN_CLASS: 100,
            MOANovelty.BEST_IN_CLASS: 85,
            MOANovelty.FAST_FOLLOWER: 60,
            MOANovelty.ME_TOO: 30,
        }

    def score_dosing_convenience(self, drug: DrugAsset) -> float:
        """
        Score dosing convenience (0-100).

        Metsera's monthly GLP-1 scored highly here vs weekly competitors.

        Factors:
        - Dosing frequency (monthly > weekly > daily)
        - Route of administration
        - Formulation innovation
        - Delivery innovation

        Args:
            drug: Drug asset to score

        Returns:
            Dosing convenience score 0-100
        """
        # Base score from frequency
        base_score = self.dosing_scores.get(drug.dosing_frequency, 50)

        # Route multiplier
        route_mult = self.route_multipliers.get(drug.route, 1.0)

        # Apply route adjustment
        score = base_score * route_mult

        # Formulation innovation bonus
        if drug.formulation_innovation:
            score += 10

        # Delivery innovation bonus (e.g., needle-free injection)
        if drug.delivery_innovation:
            score += 15

        # Patent protection adds value
        if drug.patent_protected_formulation:
            score += 10

        # Patient preference data
        if drug.patient_preference_score:
            # Scale 0-10 patient score to 0-15 bonus
            preference_bonus = (drug.patient_preference_score / 10) * 15
            score += preference_bonus

        return round(min(score, 100), 2)

    def score_moa_novelty(self, drug: DrugAsset) -> float:
        """
        Score mechanism of action novelty (0-100).

        First-in-class commands highest premiums, but best-in-class
        (like Metsera) can also achieve high scores with strong data.

        Args:
            drug: Drug asset to score

        Returns:
            MOA novelty score 0-100
        """
        # Base score from MOA classification
        base_score = self.moa_scores.get(drug.moa_novelty, 50)

        # Best-in-class gets bonus if has superiority data
        if drug.moa_novelty == MOANovelty.BEST_IN_CLASS:
            if drug.head_to_head_superiority:
                base_score += 15

            # Quantified improvement over competitor
            if drug.competitor_efficacy_delta:
                if drug.competitor_efficacy_delta > 30:  # >30% better
                    base_score += 20
                elif drug.competitor_efficacy_delta > 15:
                    base_score += 12
                elif drug.competitor_efficacy_delta > 5:
                    base_score += 6

        # Fast follower can score higher with strong differentiation
        elif drug.moa_novelty == MOANovelty.FAST_FOLLOWER:
            if drug.formulation_innovation or drug.delivery_innovation:
                base_score += 15
            if drug.head_to_head_superiority:
                base_score += 10

        return round(min(base_score, 100), 2)

    def score_efficacy_data(self, drug: DrugAsset) -> float:
        """
        Score clinical efficacy data quality (0-100).

        Strong efficacy data is critical for premium valuations.

        Factors:
        - Primary endpoint achievement
        - Statistical significance
        - Effect size magnitude
        - Head-to-head superiority

        Args:
            drug: Drug asset to score

        Returns:
            Efficacy data score 0-100
        """
        score = 0.0

        # Primary endpoint met (critical)
        if drug.primary_endpoint_met:
            score += 40
        else:
            return 0.0  # Failed primary endpoint = minimal value

        # Statistical significance
        if drug.statistical_significance:
            if drug.statistical_significance < 0.001:  # p < 0.001
                score += 20
            elif drug.statistical_significance < 0.01:
                score += 15
            elif drug.statistical_significance < 0.05:
                score += 10

        # Effect size magnitude
        if drug.effect_size:
            # Cohen's d interpretation: small=0.2, medium=0.5, large=0.8
            if drug.effect_size >= 1.0:  # Very large effect
                score += 25
            elif drug.effect_size >= 0.8:  # Large effect
                score += 20
            elif drug.effect_size >= 0.5:  # Medium effect
                score += 12
            elif drug.effect_size >= 0.2:  # Small effect
                score += 6

        # Head-to-head trial data (highly valuable)
        if drug.head_to_head_trials:
            score += 10

            if drug.head_to_head_superiority:
                score += 20  # Demonstrated superiority is huge

        # Primary endpoint value (indication-specific thresholds)
        if drug.primary_endpoint_value:
            # These are examples - would need indication-specific logic
            if drug.indication.lower() in ['obesity', 'weight loss']:
                # % weight loss
                if drug.primary_endpoint_value >= 20:  # 20%+ weight loss
                    score += 15
                elif drug.primary_endpoint_value >= 15:
                    score += 10
                elif drug.primary_endpoint_value >= 10:
                    score += 5

        return round(min(score, 100), 2)

    def score_safety_profile(self, drug: DrugAsset) -> float:
        """
        Score safety and tolerability profile (0-100).

        Good safety is necessary but not sufficient. Poor safety
        can torpedo value regardless of efficacy.

        Args:
            drug: Drug asset to score

        Returns:
            Safety profile score 0-100
        """
        score = 70.0  # Assume decent safety as baseline

        # Adverse event rate
        if drug.adverse_event_rate is not None:
            if drug.adverse_event_rate < 20:  # Very low AE rate
                score += 15
            elif drug.adverse_event_rate < 40:
                score += 8
            elif drug.adverse_event_rate < 60:
                score += 0  # Neutral
            elif drug.adverse_event_rate < 80:
                score -= 15
            else:
                score -= 30  # Very high AE rate

        # Serious adverse events (critical)
        if drug.serious_ae_rate is not None:
            if drug.serious_ae_rate < 2:
                score += 10
            elif drug.serious_ae_rate < 5:
                score += 5
            elif drug.serious_ae_rate > 10:
                score -= 20
            elif drug.serious_ae_rate > 20:
                score -= 40  # Unacceptable safety

        # Discontinuation rate (proxy for tolerability)
        if drug.discontinuation_rate is not None:
            if drug.discontinuation_rate < 5:
                score += 10
            elif drug.discontinuation_rate < 10:
                score += 5
            elif drug.discontinuation_rate > 20:
                score -= 15
            elif drug.discontinuation_rate > 30:
                score -= 30

        # Physician preference (safety influences prescribing)
        if drug.physician_preference_score:
            # Scale 0-10 to -10 to +10 adjustment
            physician_adj = (drug.physician_preference_score - 5) * 2
            score += physician_adj

        return round(min(max(score, 0), 100), 2)

    def calculate_total(self, drug: DrugAsset) -> float:
        """
        Calculate total clinical differentiation score (0-100).

        Weighted composite of all differentiation factors.

        Component weights:
        - Dosing convenience: 30%
        - MOA novelty: 25%
        - Efficacy data: 30%
        - Safety profile: 15%

        Args:
            drug: Drug asset to score

        Returns:
            Total clinical differentiation score 0-100
        """
        dosing_score = self.score_dosing_convenience(drug)
        moa_score = self.score_moa_novelty(drug)
        efficacy_score = self.score_efficacy_data(drug)
        safety_score = self.score_safety_profile(drug)

        # Weighted composite
        total_score = (
            dosing_score * 0.30 +
            moa_score * 0.25 +
            efficacy_score * 0.30 +
            safety_score * 0.15
        )

        return round(total_score, 2)

    def generate_narrative(self, drug: DrugAsset) -> Dict[str, Any]:
        """
        Generate narrative assessment of clinical differentiation.

        Args:
            drug: Drug asset to assess

        Returns:
            Dictionary with scores, strengths, weaknesses, and narrative
        """
        dosing_score = self.score_dosing_convenience(drug)
        moa_score = self.score_moa_novelty(drug)
        efficacy_score = self.score_efficacy_data(drug)
        safety_score = self.score_safety_profile(drug)
        total_score = self.calculate_total(drug)

        strengths = []
        weaknesses = []

        # Dosing convenience assessment
        if dosing_score >= 80:
            strengths.append(
                f"Excellent dosing convenience ({drug.dosing_frequency.value} via "
                f"{drug.route.value})"
            )
        elif dosing_score < 50:
            weaknesses.append("Suboptimal dosing regimen limits patient compliance")

        # MOA novelty assessment
        if moa_score >= 85:
            strengths.append(f"Strong competitive positioning ({drug.moa_novelty.value})")
        elif moa_score < 50:
            weaknesses.append("Limited differentiation from existing therapies")

        # Efficacy assessment
        if efficacy_score >= 80:
            strengths.append("Compelling efficacy data with strong statistical support")
            if drug.head_to_head_superiority:
                strengths.append("Demonstrated superiority in head-to-head trials")
        elif efficacy_score < 50:
            weaknesses.append("Efficacy data lacks competitive differentiation")

        # Safety assessment
        if safety_score >= 80:
            strengths.append("Favorable safety and tolerability profile")
        elif safety_score < 60:
            weaknesses.append("Safety concerns may limit market uptake")

        # Overall narrative
        if total_score >= 80:
            narrative = (
                f"{drug.name} demonstrates strong clinical differentiation with "
                f"multiple competitive advantages. Premium acquisition candidate."
            )
        elif total_score >= 65:
            narrative = (
                f"{drug.name} shows meaningful differentiation in {drug.indication}, "
                f"though some gaps exist vs. best-in-class."
            )
        elif total_score >= 50:
            narrative = (
                f"{drug.name} has moderate differentiation but faces competitive "
                f"challenges that may limit premium valuation."
            )
        else:
            narrative = (
                f"{drug.name} lacks sufficient clinical differentiation to command "
                f"premium M&A valuation in current market."
            )

        return {
            'total_score': total_score,
            'component_scores': {
                'dosing_convenience': dosing_score,
                'moa_novelty': moa_score,
                'efficacy_data': efficacy_score,
                'safety_profile': safety_score,
            },
            'strengths': strengths,
            'weaknesses': weaknesses,
            'narrative': narrative,
            'timestamp': datetime.utcnow().isoformat(),
        }
