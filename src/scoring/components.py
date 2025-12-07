"""
Individual Scoring Components

Implements the individual scoring components that make up the composite
M&A likelihood score. Each component calculates a score from 0-100 based
on specific criteria and signals.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum


class ClinicalPhase(str, Enum):
    """Clinical development phases."""
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    NDA_BLA = "nda_bla"
    APPROVED = "approved"


class TherapeuticArea(str, Enum):
    """Major therapeutic areas."""
    ONCOLOGY = "oncology"
    IMMUNOLOGY = "immunology"
    NEUROLOGY = "neurology"
    RARE_DISEASE = "rare_disease"
    CARDIOVASCULAR = "cardiovascular"
    METABOLIC = "metabolic"
    INFECTIOUS_DISEASE = "infectious_disease"
    OTHER = "other"


@dataclass
class SignalDecay:
    """
    Implements time-based signal decay for scoring.

    Signals (news, events, data releases) become less relevant over time.
    This class provides exponential decay functions to weight recent signals
    more heavily than older ones.

    Attributes:
        half_life_days: Number of days for signal to decay to 50% weight
        recent_boost: Multiplier for very recent signals (< 7 days)
        min_weight: Minimum weight floor (never decays to zero)
    """

    half_life_days: float = 30.0
    recent_boost: float = 1.5
    min_weight: float = 0.1

    def calculate_weight(self, signal_date: datetime, current_date: Optional[datetime] = None) -> float:
        """
        Calculate time-based weight for a signal.

        Uses exponential decay: weight = exp(-lambda * t)
        where lambda = ln(2) / half_life

        Args:
            signal_date: Date when signal occurred
            current_date: Current date (defaults to now)

        Returns:
            Weight multiplier between min_weight and recent_boost
        """
        if current_date is None:
            current_date = datetime.utcnow()

        days_ago = (current_date - signal_date).days

        # Very recent signals get a boost
        if days_ago < 7:
            return self.recent_boost

        # Exponential decay
        decay_rate = math.log(2) / self.half_life_days
        weight = math.exp(-decay_rate * days_ago)

        # Apply floor
        return max(weight, self.min_weight)

    def apply_decay(self, score: float, signal_date: datetime, current_date: Optional[datetime] = None) -> float:
        """
        Apply time decay to a score.

        Args:
            score: Original score
            signal_date: When the signal occurred
            current_date: Current date

        Returns:
            Decayed score
        """
        weight = self.calculate_weight(signal_date, current_date)
        return score * weight


@dataclass
class PipelineAsset:
    """Represents a drug pipeline asset."""
    name: str
    phase: ClinicalPhase
    indication: str
    therapeutic_area: TherapeuticArea
    patient_population: Optional[int] = None
    orphan_designation: bool = False
    breakthrough_designation: bool = False
    fast_track: bool = False
    priority_review: bool = False
    last_update: Optional[datetime] = None


@dataclass
class PatentInfo:
    """Patent portfolio information."""
    patent_id: str
    title: str
    expiry_date: datetime
    claims_count: int
    citations_count: int
    is_composition: bool = False
    is_method: bool = False
    is_formulation: bool = False


class ScoreComponents:
    """
    Individual scoring component calculators.

    Each method calculates a 0-100 score for a specific aspect of M&A likelihood.
    Scores are designed to be:
    - Interpretable: 0-100 scale with clear thresholds
    - Comparable: Similar scoring methodology across components
    - Composable: Can be weighted and combined into overall score
    """

    def __init__(self, signal_decay: Optional[SignalDecay] = None):
        """
        Initialize score components.

        Args:
            signal_decay: Signal decay configuration
        """
        self.signal_decay = signal_decay or SignalDecay()

        # Phase value multipliers (relative acquisition attractiveness)
        self.phase_values = {
            ClinicalPhase.PRECLINICAL: 0.3,
            ClinicalPhase.PHASE_1: 0.5,
            ClinicalPhase.PHASE_2: 0.8,
            ClinicalPhase.PHASE_3: 1.0,
            ClinicalPhase.NDA_BLA: 0.9,
            ClinicalPhase.APPROVED: 0.7,
        }

        # Therapeutic area multipliers (M&A activity levels)
        self.therapeutic_area_values = {
            TherapeuticArea.ONCOLOGY: 1.0,
            TherapeuticArea.RARE_DISEASE: 0.95,
            TherapeuticArea.IMMUNOLOGY: 0.9,
            TherapeuticArea.NEUROLOGY: 0.85,
            TherapeuticArea.METABOLIC: 0.8,
            TherapeuticArea.CARDIOVASCULAR: 0.75,
            TherapeuticArea.INFECTIOUS_DISEASE: 0.7,
            TherapeuticArea.OTHER: 0.5,
        }

    def calculate_pipeline_score(self, assets: List[PipelineAsset]) -> float:
        """
        Calculate pipeline value score (0-100).

        Factors:
        - Clinical phase (later = higher)
        - Therapeutic area (oncology, rare disease = higher)
        - Patient population size
        - FDA designations (orphan, breakthrough, fast track)
        - Pipeline diversity (multiple shots on goal)
        - Recent progress (time decay)

        Args:
            assets: List of pipeline assets

        Returns:
            Pipeline score 0-100
        """
        if not assets:
            return 0.0

        asset_scores = []

        for asset in assets:
            # Base score from phase
            phase_score = self.phase_values.get(asset.phase, 0.3) * 100

            # Therapeutic area multiplier
            ta_multiplier = self.therapeutic_area_values.get(
                asset.therapeutic_area, 0.5
            )

            # Market size bonus (larger populations = more valuable)
            market_bonus = 0
            if asset.patient_population:
                if asset.patient_population > 1_000_000:
                    market_bonus = 15
                elif asset.patient_population > 100_000:
                    market_bonus = 10
                elif asset.patient_population < 10_000:
                    # Rare disease - valuable with right designation
                    market_bonus = 5 if asset.orphan_designation else -5

            # FDA designation bonuses
            designation_bonus = 0
            if asset.breakthrough_designation:
                designation_bonus += 15
            if asset.orphan_designation:
                designation_bonus += 10
            if asset.fast_track:
                designation_bonus += 8
            if asset.priority_review:
                designation_bonus += 5

            # Calculate asset score
            asset_score = (phase_score * ta_multiplier) + market_bonus + designation_bonus

            # Apply time decay if last update available
            if asset.last_update:
                asset_score = self.signal_decay.apply_decay(
                    asset_score, asset.last_update
                )

            asset_scores.append(min(asset_score, 100))

        # Pipeline diversity bonus (multiple assets = risk diversification)
        diversity_bonus = min(len(assets) * 2, 15)

        # Take weighted average of top 3 assets plus diversity
        asset_scores.sort(reverse=True)
        top_assets = asset_scores[:3]

        if len(top_assets) == 1:
            base_score = top_assets[0]
        elif len(top_assets) == 2:
            base_score = top_assets[0] * 0.6 + top_assets[1] * 0.4
        else:
            base_score = (top_assets[0] * 0.5 + top_assets[1] * 0.3 + top_assets[2] * 0.2)

        final_score = min(base_score + diversity_bonus, 100)
        return round(final_score, 2)

    def calculate_patent_score(self, patents: List[PatentInfo]) -> float:
        """
        Calculate patent/IP strength score (0-100).

        Factors:
        - Number of patents
        - Patent quality (claims, citations)
        - Patent life remaining
        - Patent type (composition of matter > method > formulation)
        - Portfolio breadth

        Args:
            patents: List of patents

        Returns:
            Patent score 0-100
        """
        if not patents:
            return 0.0

        current_date = datetime.utcnow()
        patent_scores = []

        for patent in patents:
            # Years until expiry
            years_remaining = (patent.expiry_date - current_date).days / 365.25

            # Patent life score (optimal is 5-15 years remaining)
            if years_remaining < 0:
                life_score = 0
            elif years_remaining < 3:
                life_score = 20
            elif years_remaining < 8:
                life_score = 100
            elif years_remaining < 15:
                life_score = 80
            else:
                life_score = 60  # Too far out, less immediate value

            # Patent type multiplier
            type_multiplier = 1.0
            if patent.is_composition:
                type_multiplier = 1.5  # Most valuable
            elif patent.is_method:
                type_multiplier = 1.0
            elif patent.is_formulation:
                type_multiplier = 0.8

            # Quality indicators
            claims_score = min(patent.claims_count * 2, 30)
            citation_score = min(patent.citations_count * 3, 20)

            patent_score = (life_score * type_multiplier) + claims_score + citation_score
            patent_scores.append(min(patent_score, 100))

        # Portfolio size bonus
        portfolio_bonus = min(len(patents) * 3, 20)

        # Calculate weighted score
        patent_scores.sort(reverse=True)
        if len(patent_scores) == 1:
            base_score = patent_scores[0]
        else:
            # Weight top patents more heavily
            weights = [0.4, 0.3, 0.2, 0.1] if len(patent_scores) >= 4 else [0.5, 0.3, 0.2]
            base_score = sum(
                score * weight
                for score, weight in zip(patent_scores[:len(weights)], weights)
            )

        final_score = min(base_score + portfolio_bonus, 100)
        return round(final_score, 2)

    def calculate_financial_score(
        self,
        market_cap: float,
        cash: float,
        burn_rate: float,
        revenue: float = 0.0,
        catalyst_date: Optional[datetime] = None,
    ) -> float:
        """
        Calculate financial attractiveness score (0-100).

        Factors:
        - Cash runway vs upcoming catalysts
        - Valuation (market cap relative to sector)
        - Burn rate sustainability
        - Revenue (if any)
        - Financing pressure

        Args:
            market_cap: Current market capitalization (USD)
            cash: Cash and equivalents (USD)
            burn_rate: Monthly cash burn (USD)
            revenue: Annual revenue (USD)
            catalyst_date: Date of next major catalyst

        Returns:
            Financial score 0-100
        """
        if market_cap <= 0:
            return 0.0

        # Calculate runway in months
        runway_months = cash / burn_rate if burn_rate > 0 else 999

        # Runway score (sweet spot is 6-18 months - financing pressure)
        if runway_months < 3:
            runway_score = 100  # Desperate, likely to sell
        elif runway_months < 6:
            runway_score = 90
        elif runway_months < 12:
            runway_score = 80
        elif runway_months < 18:
            runway_score = 60
        elif runway_months < 24:
            runway_score = 40
        else:
            runway_score = 20  # Well-funded, less pressure

        # Catalyst timing (running out of cash before catalyst = high score)
        catalyst_score = 0
        if catalyst_date:
            months_to_catalyst = (catalyst_date - datetime.utcnow()).days / 30.4
            if 0 < months_to_catalyst < runway_months - 3:
                # Has cash to reach catalyst - moderate score
                catalyst_score = 10
            elif 0 < months_to_catalyst < runway_months + 3:
                # Tight timing - needs funding around catalyst
                catalyst_score = 25
            elif months_to_catalyst > runway_months:
                # Will run out before catalyst - desperate
                catalyst_score = 40

        # Valuation attractiveness (lower = better for acquirer)
        # Typical biotech: $200M - $2B market cap
        if market_cap < 100_000_000:
            valuation_score = 100  # Very cheap
        elif market_cap < 300_000_000:
            valuation_score = 80
        elif market_cap < 500_000_000:
            valuation_score = 60
        elif market_cap < 1_000_000_000:
            valuation_score = 40
        elif market_cap < 2_000_000_000:
            valuation_score = 20
        else:
            valuation_score = 10  # Expensive

        # Revenue component (revenue-generating assets = more valuable)
        revenue_score = 0
        if revenue > 0:
            if revenue > 100_000_000:
                revenue_score = 20
            elif revenue > 50_000_000:
                revenue_score = 15
            elif revenue > 10_000_000:
                revenue_score = 10

        # Combine components
        final_score = (
            runway_score * 0.4 +
            catalyst_score * 0.2 +
            valuation_score * 0.3 +
            revenue_score * 0.1
        )

        return round(min(final_score, 100), 2)

    def calculate_insider_score(
        self,
        insider_purchases: List[Dict[str, Any]],
        insider_sales: List[Dict[str, Any]],
        institutional_changes: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate insider/institutional activity score (0-100).

        Positive signals:
        - Insider purchases (especially executives)
        - Institutional accumulation
        - Activist investor involvement

        Negative signals:
        - Heavy insider selling
        - Institutional distribution
        - Board resignations

        Args:
            insider_purchases: List of insider purchase transactions
            insider_sales: List of insider sale transactions
            institutional_changes: List of institutional position changes

        Returns:
            Insider activity score 0-100
        """
        score = 50.0  # Neutral baseline

        current_date = datetime.utcnow()

        # Process insider purchases (positive signal)
        for purchase in insider_purchases:
            transaction_date = purchase.get('date', current_date)
            amount = purchase.get('amount', 0)
            is_executive = purchase.get('is_executive', False)

            # Base points for purchase
            points = 5 if is_executive else 3

            # Size bonus
            if amount > 1_000_000:
                points += 10
            elif amount > 500_000:
                points += 5
            elif amount > 100_000:
                points += 3

            # Apply decay
            decayed_points = self.signal_decay.apply_decay(
                points, transaction_date, current_date
            )
            score += decayed_points

        # Process insider sales (negative signal, but common for compensation)
        for sale in insider_sales:
            transaction_date = sale.get('date', current_date)
            amount = sale.get('amount', 0)
            is_executive = sale.get('is_executive', False)
            is_10b5_1 = sale.get('is_planned', False)  # Planned sales less concerning

            if is_10b5_1:
                continue  # Ignore planned sales

            # Base penalty
            points = -3 if is_executive else -1

            # Size penalty
            if amount > 5_000_000:
                points -= 15
            elif amount > 1_000_000:
                points -= 8
            elif amount > 500_000:
                points -= 4

            # Apply decay
            decayed_points = self.signal_decay.apply_decay(
                abs(points), transaction_date, current_date
            )
            score += points * (decayed_points / abs(points)) if points != 0 else 0

        # Process institutional changes
        for change in institutional_changes:
            change_date = change.get('date', current_date)
            position_change = change.get('position_change_pct', 0)  # % change
            is_activist = change.get('is_activist', False)

            if position_change > 0:  # Accumulation
                points = 8 if is_activist else 4
                if position_change > 50:  # Major accumulation
                    points += 10
                elif position_change > 20:
                    points += 5

                decayed_points = self.signal_decay.apply_decay(
                    points, change_date, current_date
                )
                score += decayed_points

            elif position_change < 0:  # Distribution
                points = -6 if is_activist else -3
                if position_change < -50:  # Major selling
                    points -= 8

                decayed_points = self.signal_decay.apply_decay(
                    abs(points), change_date, current_date
                )
                score += points * (decayed_points / abs(points)) if points != 0 else 0

        return round(min(max(score, 0), 100), 2)

    def calculate_regulatory_score(
        self,
        regulatory_pathway: str,
        fda_interactions: List[Dict[str, Any]],
        clinical_holds: int = 0,
        warning_letters: int = 0,
    ) -> float:
        """
        Calculate regulatory pathway clarity score (0-100).

        Factors:
        - Clear regulatory pathway
        - Positive FDA interactions
        - No clinical holds or warnings
        - Orphan/breakthrough designations
        - FDA meeting outcomes

        Args:
            regulatory_pathway: Type of pathway (505b2, BLA, NDA, etc)
            fda_interactions: List of FDA meeting/interaction records
            clinical_holds: Number of active clinical holds
            warning_letters: Number of warning letters (last 2 years)

        Returns:
            Regulatory score 0-100
        """
        # Base score by pathway clarity
        pathway_scores = {
            '505b2': 85,  # Clear abbreviated pathway
            'bla': 80,    # Biologics License Application
            'nda': 75,    # New Drug Application
            'orphan': 90, # Orphan drug designation
            'breakthrough': 95,  # Breakthrough therapy
            'fast_track': 85,
            'priority_review': 90,
            'unclear': 40,
            'none': 30,
        }

        base_score = pathway_scores.get(regulatory_pathway.lower(), 50)

        # FDA interaction analysis
        interaction_bonus = 0
        for interaction in fda_interactions:
            interaction_type = interaction.get('type', '')
            outcome = interaction.get('outcome', '')
            interaction_date = interaction.get('date', datetime.utcnow())

            points = 0
            if 'positive' in outcome.lower() or 'agreement' in outcome.lower():
                if 'spa' in interaction_type.lower():  # Special Protocol Assessment
                    points = 15
                elif 'meeting' in interaction_type.lower():
                    points = 10
                else:
                    points = 5

            elif 'complete response' in outcome.lower():
                points = -20

            # Apply decay
            if points != 0:
                decayed_points = self.signal_decay.apply_decay(
                    abs(points), interaction_date
                )
                interaction_bonus += points * (decayed_points / abs(points))

        # Penalties for issues
        hold_penalty = clinical_holds * 25  # Major penalty
        warning_penalty = warning_letters * 15

        final_score = base_score + interaction_bonus - hold_penalty - warning_penalty

        return round(min(max(final_score, 0), 100), 2)

    def calculate_strategic_fit_score(
        self,
        target_therapeutic_areas: List[TherapeuticArea],
        acquirer_therapeutic_areas: List[TherapeuticArea],
        acquirer_pipeline_gaps: List[str],
        technology_fit: float = 0.5,
    ) -> float:
        """
        Calculate strategic fit score between target and acquirer (0-100).

        This is calculated relative to a specific acquirer.

        Factors:
        - Therapeutic area overlap
        - Pipeline gap filling
        - Technology/platform fit
        - Geographic expansion
        - Portfolio diversification

        Args:
            target_therapeutic_areas: Target's therapeutic focus areas
            acquirer_therapeutic_areas: Acquirer's therapeutic focus areas
            acquirer_pipeline_gaps: Known gaps in acquirer pipeline
            technology_fit: Technology/platform fit score (0-1)

        Returns:
            Strategic fit score 0-100
        """
        if not target_therapeutic_areas or not acquirer_therapeutic_areas:
            return 50.0  # Neutral if data missing

        # Therapeutic area overlap
        target_set = set(target_therapeutic_areas)
        acquirer_set = set(acquirer_therapeutic_areas)

        overlap = target_set & acquirer_set
        overlap_score = (len(overlap) / len(target_set)) * 60 if target_set else 0

        # Pipeline gap filling (higher score if fills gaps)
        gap_score = 0
        for gap in acquirer_pipeline_gaps:
            for ta in target_therapeutic_areas:
                if gap.lower() in ta.value.lower():
                    gap_score += 20
                    break

        gap_score = min(gap_score, 40)

        # Technology fit
        tech_score = technology_fit * 30

        # Diversification bonus (new areas = strategic value)
        diversification = target_set - acquirer_set
        diversification_score = min(len(diversification) * 10, 20)

        final_score = (
            overlap_score * 0.4 +
            gap_score * 0.3 +
            tech_score * 0.2 +
            diversification_score * 0.1
        )

        return round(min(final_score, 100), 2)
