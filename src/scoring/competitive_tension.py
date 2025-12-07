"""
Competitive Tension Scoring Module

Predicts likelihood of bidding wars and competitive dynamics in M&A situations.
Metsera attracted multiple bidders (Novo, Pfizer, others) driving 2x+ premium.

Key Factors:
- Number of potential acquirers with strategic interest
- Asset scarcity in therapeutic area
- Strategic urgency of acquirers (patent cliffs, pipeline gaps)
- Recent competitive M&A behavior
- Target uniqueness/differentiation
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum


class CompetitionLevel(str, Enum):
    """Competition intensity classification."""
    AUCTION = "auction"              # 5+ serious bidders (extreme)
    HIGH_COMPETITION = "high"        # 3-4 bidders (Metsera scenario)
    MODERATE_COMPETITION = "moderate" # 2 bidders
    LOW_COMPETITION = "low"          # 1 obvious acquirer
    NO_COMPETITION = "none"          # 0-1 interested parties


class StrategicUrgency(str, Enum):
    """Acquirer urgency level."""
    CRITICAL = "critical"      # Must-have asset (patent cliff, pipeline crisis)
    HIGH = "high"              # Strategic priority
    MEDIUM = "medium"          # Nice-to-have
    LOW = "low"                # Opportunistic only


@dataclass
class PotentialAcquirer:
    """
    Potential acquirer profile.

    Attributes:
        company: Acquirer name/ticker
        therapeutic_overlap: Strategic fit with target (0-100)
        pipeline_gap_severity: How badly they need this asset (0-100)
        financial_capacity: Can they afford it (0-100)
        recent_ma_activity: Recent M&A deals count
        urgency: Strategic urgency level
        past_bidding_behavior: History of competitive bidding
    """
    company: str
    therapeutic_overlap: float
    pipeline_gap_severity: float
    financial_capacity: float
    recent_ma_activity: int
    urgency: StrategicUrgency
    past_bidding_behavior: str  # aggressive, moderate, conservative
    patent_cliff_risk: bool = False
    revenue_concentration: Optional[float] = None  # % revenue from few drugs


@dataclass
class TargetAsset:
    """
    Target company asset profile for competition assessment.

    Attributes:
        company: Target company
        therapeutic_area: Primary therapeutic area
        lead_asset_phase: Clinical phase of lead asset
        differentiation_score: Clinical differentiation (from other module)
        market_size: Total addressable market ($M)
        competitive_alternatives: Number of similar assets available
        patent_life: Years of patent protection remaining
    """
    company: str
    therapeutic_area: str
    lead_asset_phase: str
    differentiation_score: float
    market_size: float
    competitive_alternatives: int
    patent_life: float
    orphan_designation: bool = False
    breakthrough_designation: bool = False
    regulatory_clarity: float = 50.0


class CompetitiveTension:
    """
    Calculate competitive tension and bidding war likelihood.

    High tension scores indicate multiple strategic buyers competing
    for scarce assets, driving premium valuations (Metsera case).

    Example:
        >>> # Metsera scenario
        >>> target = TargetAsset(
        ...     company="Metsera",
        ...     therapeutic_area="obesity",
        ...     differentiation_score=85,
        ...     competitive_alternatives=2
        ... )
        >>> acquirers = [novo, pfizer, lilly]  # Multiple interested
        >>> scorer = CompetitiveTension()
        >>> score = scorer.calculate_total(target, acquirers)
        >>> # Expected: 85+ (high competition)
    """

    def __init__(self):
        """Initialize competitive tension scorer."""

        # Urgency multipliers
        self.urgency_multipliers = {
            StrategicUrgency.CRITICAL: 2.0,
            StrategicUrgency.HIGH: 1.5,
            StrategicUrgency.MEDIUM: 1.0,
            StrategicUrgency.LOW: 0.6,
        }

        # Bidding behavior multipliers
        self.bidding_multipliers = {
            'aggressive': 1.3,    # Novo Nordisk - willing to pay up
            'moderate': 1.0,
            'conservative': 0.7,
        }

    def count_potential_acquirers(
        self,
        target: TargetAsset,
        acquirer_pool: List[PotentialAcquirer],
        min_fit_threshold: float = 60.0
    ) -> Tuple[int, List[PotentialAcquirer]]:
        """
        Count credible potential acquirers.

        Only count acquirers with:
        - Therapeutic fit > threshold
        - Financial capacity
        - Strategic rationale

        Args:
            target: Target company asset profile
            acquirer_pool: List of potential acquirers
            min_fit_threshold: Minimum strategic fit score

        Returns:
            Tuple of (count, list of qualified acquirers)
        """
        qualified_acquirers = []

        for acquirer in acquirer_pool:
            # Calculate composite fit
            strategic_fit = (
                acquirer.therapeutic_overlap * 0.4 +
                acquirer.pipeline_gap_severity * 0.4 +
                acquirer.financial_capacity * 0.2
            )

            # Must meet minimum threshold
            if strategic_fit < min_fit_threshold:
                continue

            # Must have financial capacity
            if acquirer.financial_capacity < 50:
                continue

            qualified_acquirers.append(acquirer)

        return len(qualified_acquirers), qualified_acquirers

    def assess_asset_scarcity(self, target: TargetAsset) -> float:
        """
        Assess asset scarcity in market (0-100).

        Scarce assets with few alternatives drive competition.
        Metsera: Monthly GLP-1 was scarce (only player).

        Factors:
        - Number of competitive alternatives
        - Differentiation level
        - Market exclusivity (orphan, breakthrough)
        - Patent position

        Args:
            target: Target asset profile

        Returns:
            Scarcity score 0-100
        """
        score = 50.0  # Baseline

        # Alternative availability (fewer = higher scarcity)
        if target.competitive_alternatives == 0:
            alternatives_score = 100  # Only player
        elif target.competitive_alternatives == 1:
            alternatives_score = 85   # One competitor
        elif target.competitive_alternatives == 2:
            alternatives_score = 70   # Two competitors
        elif target.competitive_alternatives <= 5:
            alternatives_score = 50   # Some competition
        else:
            alternatives_score = 30   # Crowded field

        # Differentiation amplifies scarcity
        # High differentiation = fewer true substitutes
        differentiation_multiplier = target.differentiation_score / 100

        # Orphan/breakthrough designations = regulatory scarcity
        exclusivity_bonus = 0
        if target.orphan_designation:
            exclusivity_bonus += 15
        if target.breakthrough_designation:
            exclusivity_bonus += 10

        # Patent life (longer = more valuable scarcity)
        if target.patent_life >= 10:
            patent_bonus = 15
        elif target.patent_life >= 7:
            patent_bonus = 10
        elif target.patent_life >= 5:
            patent_bonus = 5
        else:
            patent_bonus = 0

        # Clinical stage (later = scarcer)
        phase_multiplier = 1.0
        if target.lead_asset_phase in ['Phase 3', 'NDA/BLA']:
            phase_multiplier = 1.3
        elif target.lead_asset_phase == 'Phase 2':
            phase_multiplier = 1.1

        scarcity_score = (
            (alternatives_score * differentiation_multiplier * phase_multiplier) +
            exclusivity_bonus +
            patent_bonus
        )

        return round(min(scarcity_score, 100), 2)

    def calculate_strategic_urgency(
        self,
        acquirers: List[PotentialAcquirer]
    ) -> float:
        """
        Calculate aggregate strategic urgency across acquirers (0-100).

        Higher urgency = more aggressive bidding = higher premiums.

        Urgency drivers:
        - Patent cliffs looming
        - Pipeline gaps
        - Revenue concentration risk
        - Competitive pressure

        Args:
            acquirers: List of potential acquirers

        Returns:
            Strategic urgency score 0-100
        """
        if not acquirers:
            return 0.0

        urgency_scores = []

        for acquirer in acquirers:
            score = 50.0  # Baseline

            # Urgency level
            urgency_mult = self.urgency_multipliers.get(
                acquirer.urgency,
                1.0
            )
            score *= urgency_mult

            # Patent cliff adds urgency
            if acquirer.patent_cliff_risk:
                score += 25

            # Pipeline gap severity
            score += (acquirer.pipeline_gap_severity - 50) * 0.5

            # Revenue concentration (>50% from few drugs = risky)
            if acquirer.revenue_concentration and acquirer.revenue_concentration > 50:
                score += 15

            # Recent M&A activity indicates aggressive strategy
            if acquirer.recent_ma_activity >= 3:  # 3+ recent deals
                score += 10

            urgency_scores.append(min(score, 100))

        # Take weighted average favoring highest urgency
        urgency_scores.sort(reverse=True)

        if len(urgency_scores) == 1:
            return urgency_scores[0]
        elif len(urgency_scores) == 2:
            return urgency_scores[0] * 0.6 + urgency_scores[1] * 0.4
        else:
            return (urgency_scores[0] * 0.5 +
                   urgency_scores[1] * 0.3 +
                   urgency_scores[2] * 0.2)

    def assess_competitive_behavior(
        self,
        acquirers: List[PotentialAcquirer]
    ) -> float:
        """
        Assess likelihood of aggressive competitive bidding (0-100).

        Based on historical bidding behavior of acquirers.

        Args:
            acquirers: List of potential acquirers

        Returns:
            Competitive behavior score 0-100
        """
        if not acquirers:
            return 0.0

        # Count acquirers by behavior type
        aggressive_count = sum(
            1 for a in acquirers
            if a.past_bidding_behavior == 'aggressive'
        )
        moderate_count = sum(
            1 for a in acquirers
            if a.past_bidding_behavior == 'moderate'
        )

        # Base score from acquirer count
        total_count = len(acquirers)
        if total_count >= 5:
            base_score = 100
        elif total_count >= 3:
            base_score = 80
        elif total_count >= 2:
            base_score = 60
        else:
            base_score = 40

        # Aggressive bidder multiplier
        if aggressive_count >= 2:
            base_score *= 1.3  # Multiple aggressive bidders = war
        elif aggressive_count >= 1:
            base_score *= 1.15

        return round(min(base_score, 100), 2)

    def predict_premium_multiplier(
        self,
        competition_score: float
    ) -> Tuple[float, float]:
        """
        Predict acquisition premium multiplier based on competition.

        Based on historical M&A data:
        - No competition: 1.0-1.2x (20% premium)
        - Low competition: 1.2-1.4x (20-40% premium)
        - Moderate: 1.4-1.7x (40-70% premium)
        - High: 1.7-2.5x (70-150% premium) <- Metsera was here
        - Auction: 2.5-4.0x+ (150-300%+ premium)

        Args:
            competition_score: Competitive tension score 0-100

        Returns:
            Tuple of (low_estimate, high_estimate) premium multipliers
        """
        if competition_score >= 90:  # Auction scenario
            return (2.5, 4.0)
        elif competition_score >= 75:  # High competition (Metsera)
            return (1.8, 2.5)
        elif competition_score >= 60:  # Moderate competition
            return (1.4, 1.8)
        elif competition_score >= 40:  # Low competition
            return (1.2, 1.4)
        else:  # No meaningful competition
            return (1.0, 1.2)

    def calculate_total(
        self,
        target: TargetAsset,
        acquirer_pool: List[PotentialAcquirer]
    ) -> float:
        """
        Calculate total competitive tension score (0-100).

        Composite score predicting bidding intensity and premium likelihood.

        Component weights:
        - Number of acquirers: 30%
        - Asset scarcity: 30%
        - Strategic urgency: 25%
        - Competitive behavior: 15%

        Args:
            target: Target company asset profile
            acquirer_pool: Pool of potential acquirers

        Returns:
            Competitive tension score 0-100
        """
        # Count qualified acquirers
        acquirer_count, qualified_acquirers = self.count_potential_acquirers(
            target, acquirer_pool
        )

        # Acquirer count score
        if acquirer_count >= 5:
            acquirer_score = 100
        elif acquirer_count >= 4:
            acquirer_score = 90
        elif acquirer_count >= 3:
            acquirer_score = 80
        elif acquirer_count == 2:
            acquirer_score = 60
        elif acquirer_count == 1:
            acquirer_score = 40
        else:
            acquirer_score = 10

        # Component scores
        scarcity_score = self.assess_asset_scarcity(target)
        urgency_score = self.calculate_strategic_urgency(qualified_acquirers)
        behavior_score = self.assess_competitive_behavior(qualified_acquirers)

        # Weighted composite
        total_score = (
            acquirer_score * 0.30 +
            scarcity_score * 0.30 +
            urgency_score * 0.25 +
            behavior_score * 0.15
        )

        return round(total_score, 2)

    def classify_competition_level(self, score: float) -> CompetitionLevel:
        """
        Classify competition intensity.

        Args:
            score: Competition score 0-100

        Returns:
            CompetitionLevel classification
        """
        if score >= 90:
            return CompetitionLevel.AUCTION
        elif score >= 75:
            return CompetitionLevel.HIGH_COMPETITION
        elif score >= 55:
            return CompetitionLevel.MODERATE_COMPETITION
        elif score >= 35:
            return CompetitionLevel.LOW_COMPETITION
        else:
            return CompetitionLevel.NO_COMPETITION

    def generate_competition_report(
        self,
        target: TargetAsset,
        acquirer_pool: List[PotentialAcquirer]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive competitive tension assessment.

        Args:
            target: Target company
            acquirer_pool: Potential acquirers

        Returns:
            Dictionary with scores, acquirer analysis, and predictions
        """
        # Calculate scores
        total_score = self.calculate_total(target, acquirer_pool)
        acquirer_count, qualified = self.count_potential_acquirers(
            target, acquirer_pool
        )
        scarcity_score = self.assess_asset_scarcity(target)
        urgency_score = self.calculate_strategic_urgency(qualified)
        behavior_score = self.assess_competitive_behavior(qualified)

        competition_level = self.classify_competition_level(total_score)
        premium_range = self.predict_premium_multiplier(total_score)

        # Identify key bidders
        key_bidders = []
        for acq in qualified[:5]:  # Top 5
            fit_score = (
                acq.therapeutic_overlap * 0.4 +
                acq.pipeline_gap_severity * 0.4 +
                acq.financial_capacity * 0.2
            )
            key_bidders.append({
                'company': acq.company,
                'strategic_fit': round(fit_score, 1),
                'urgency': acq.urgency.value,
                'bidding_style': acq.past_bidding_behavior,
                'likelihood': 'high' if fit_score >= 75 else 'medium' if fit_score >= 60 else 'low'
            })

        # Generate insights
        insights = []
        if total_score >= 90:
            insights.append(
                f"Extreme competitive tension with {acquirer_count} potential bidders. "
                f"Auction scenario likely with premium {premium_range[0]:.1f}x-{premium_range[1]:.1f}x."
            )
        elif total_score >= 75:
            insights.append(
                f"High competitive tension ({acquirer_count} bidders) similar to Metsera scenario. "
                f"Expect premium {premium_range[0]:.1f}x-{premium_range[1]:.1f}x."
            )
        elif total_score >= 55:
            insights.append(
                f"Moderate competition expected with {acquirer_count} interested parties. "
                f"Premium {premium_range[0]:.1f}x-{premium_range[1]:.1f}x likely."
            )
        else:
            insights.append(
                f"Limited competitive dynamics. Single bidder scenario most likely. "
                f"Premium {premium_range[0]:.1f}x-{premium_range[1]:.1f}x expected."
            )

        if scarcity_score >= 80:
            insights.append(
                f"High asset scarcity ({target.competitive_alternatives} alternatives) "
                f"will intensify competition."
            )

        if urgency_score >= 75:
            insights.append(
                "Multiple acquirers have critical strategic urgency, "
                "increasing likelihood of aggressive bidding."
            )

        return {
            'target': target.company,
            'total_score': total_score,
            'competition_level': competition_level.value,
            'component_scores': {
                'acquirer_count': acquirer_count,
                'asset_scarcity': scarcity_score,
                'strategic_urgency': urgency_score,
                'competitive_behavior': behavior_score,
            },
            'premium_prediction': {
                'multiplier_low': premium_range[0],
                'multiplier_high': premium_range[1],
                'premium_pct_low': round((premium_range[0] - 1) * 100, 1),
                'premium_pct_high': round((premium_range[1] - 1) * 100, 1),
            },
            'key_bidders': key_bidders,
            'insights': insights,
            'timestamp': datetime.utcnow().isoformat(),
        }
