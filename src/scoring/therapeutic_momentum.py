"""
Therapeutic Momentum Scoring Module

Tracks "market heat" in therapeutic areas to identify hot sectors with high M&A activity.
Obesity/GLP-1 area was extremely hot during Metsera acquisition, driving bidding wars.

Key Metrics:
- M&A deal volume and value in therapeutic area
- VC investment flows
- Clinical trial activity (new trials, enrollment)
- Conference/media attention
- Earnings call mentions by big pharma
- Stock price momentum of sector companies
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from enum import Enum


class TherapeuticArea(str, Enum):
    """Major therapeutic areas tracked for momentum."""
    OBESITY_METABOLIC = "obesity_metabolic"
    ONCOLOGY = "oncology"
    ONCOLOGY_ADC = "oncology_adc"  # Antibody-drug conjugates
    RADIOPHARMACEUTICALS = "radiopharmaceuticals"
    AUTOIMMUNE = "autoimmune"
    RARE_DISEASE = "rare_disease"
    NEUROLOGY = "neurology"
    CARDIOVASCULAR = "cardiovascular"
    INFECTIOUS_DISEASE = "infectious_disease"
    GENE_THERAPY = "gene_therapy"
    CELL_THERAPY = "cell_therapy"
    RNA_THERAPEUTICS = "rna_therapeutics"


class MomentumLevel(str, Enum):
    """Market heat level classification."""
    EXTREME_HOT = "extreme_hot"      # 90-100: White hot (GLP-1 in 2024)
    VERY_HOT = "very_hot"            # 80-90: Major activity
    HOT = "hot"                       # 70-80: Above average activity
    WARM = "warm"                     # 60-70: Moderate interest
    NEUTRAL = "neutral"               # 40-60: Baseline activity
    COOL = "cool"                     # 20-40: Below average
    COLD = "cold"                     # 0-20: Minimal activity


@dataclass
class MADeal:
    """M&A deal data."""
    acquirer: str
    target: str
    deal_value: Optional[float]  # USD millions
    announcement_date: datetime
    therapeutic_area: str
    deal_type: str  # acquisition, merger, licensing
    completion_status: str  # announced, completed, terminated


@dataclass
class VCInvestment:
    """Venture capital investment data."""
    company: str
    amount: float  # USD millions
    investment_date: datetime
    therapeutic_area: str
    round_type: str  # Series A, B, C, etc.
    lead_investor: Optional[str] = None


@dataclass
class ClinicalTrial:
    """Clinical trial activity data."""
    nct_id: str
    title: str
    therapeutic_area: str
    phase: str
    start_date: datetime
    enrollment_target: Optional[int] = None
    sponsor: str
    status: str


class TherapeuticMomentum:
    """
    Calculate therapeutic area momentum score (0-100).

    Identifies "hot" therapeutic areas experiencing high M&A activity,
    investment flows, and innovation. Companies in hot areas command
    premium valuations (e.g., Metsera in obesity/GLP-1 space).

    Example:
        >>> tracker = TherapeuticMomentum()
        >>> score = tracker.calculate_momentum_score("obesity_metabolic")
        >>> print(f"Obesity Momentum: {score:.1f}")
        >>> # Expected: 95+ (extremely hot market in 2024-2025)
    """

    def __init__(self, lookback_months: int = 24):
        """
        Initialize momentum tracker.

        Args:
            lookback_months: How many months to look back for trends
        """
        self.lookback_months = lookback_months

        # Current therapeutic area "heat map" (as of late 2024/early 2025)
        # These would be updated regularly from real data
        self.baseline_scores = {
            TherapeuticArea.OBESITY_METABOLIC: 95,      # Extremely hot (Metsera case)
            TherapeuticArea.ONCOLOGY_ADC: 88,            # Very hot
            TherapeuticArea.RADIOPHARMACEUTICALS: 82,    # Very hot
            TherapeuticArea.AUTOIMMUNE: 78,              # Hot
            TherapeuticArea.RNA_THERAPEUTICS: 75,        # Hot
            TherapeuticArea.GENE_THERAPY: 72,            # Hot
            TherapeuticArea.ONCOLOGY: 70,                # Hot (always hot)
            TherapeuticArea.RARE_DISEASE: 68,            # Warm
            TherapeuticArea.CELL_THERAPY: 65,            # Warm
            TherapeuticArea.NEUROLOGY: 62,               # Warm
            TherapeuticArea.CARDIOVASCULAR: 55,          # Neutral
            TherapeuticArea.INFECTIOUS_DISEASE: 50,      # Neutral
        }

    def calculate_ma_volume(
        self,
        area: str,
        deals: List[MADeal],
        months: int = 24
    ) -> float:
        """
        Calculate M&A volume score for therapeutic area (0-100).

        Higher deal count and values indicate hot market with
        competitive dynamics that drive premiums.

        Args:
            area: Therapeutic area
            deals: List of M&A deals
            months: Lookback period in months

        Returns:
            M&A volume score 0-100
        """
        cutoff_date = datetime.utcnow() - timedelta(days=30 * months)

        # Filter deals in this therapeutic area within lookback period
        relevant_deals = [
            d for d in deals
            if d.therapeutic_area == area and d.announcement_date >= cutoff_date
        ]

        if not relevant_deals:
            return 20.0  # Baseline minimum

        # Count deals
        deal_count = len(relevant_deals)

        # Deal count score
        if deal_count >= 10:
            count_score = 100
        elif deal_count >= 7:
            count_score = 85
        elif deal_count >= 5:
            count_score = 70
        elif deal_count >= 3:
            count_score = 55
        else:
            count_score = 40

        # Total deal value
        total_value = sum(d.deal_value for d in relevant_deals if d.deal_value)

        # Deal value score (in billions)
        value_billions = total_value / 1000 if total_value else 0

        if value_billions >= 20:  # $20B+ (extremely hot)
            value_score = 100
        elif value_billions >= 10:
            value_score = 85
        elif value_billions >= 5:
            value_score = 70
        elif value_billions >= 2:
            value_score = 55
        else:
            value_score = 40

        # Recent acceleration bonus
        recent_deals = [
            d for d in relevant_deals
            if d.announcement_date >= datetime.utcnow() - timedelta(days=180)
        ]
        recent_pct = len(recent_deals) / deal_count if deal_count > 0 else 0

        acceleration_bonus = 0
        if recent_pct > 0.6:  # 60%+ of deals in last 6 months
            acceleration_bonus = 15
        elif recent_pct > 0.4:
            acceleration_bonus = 8

        # Mega-deal bonus (deals > $5B indicate sector importance)
        mega_deals = [d for d in relevant_deals if d.deal_value and d.deal_value > 5000]
        mega_bonus = min(len(mega_deals) * 10, 20)

        final_score = (count_score * 0.4 + value_score * 0.4 +
                      acceleration_bonus + mega_bonus)

        return round(min(final_score, 100), 2)

    def calculate_vc_investment(
        self,
        area: str,
        investments: List[VCInvestment],
        months: int = 24
    ) -> float:
        """
        Calculate VC investment momentum score (0-100).

        High VC investment indicates sector validation and
        future pipeline of acquisition targets.

        Args:
            area: Therapeutic area
            investments: List of VC investments
            months: Lookback period in months

        Returns:
            VC investment score 0-100
        """
        cutoff_date = datetime.utcnow() - timedelta(days=30 * months)

        relevant_investments = [
            inv for inv in investments
            if inv.therapeutic_area == area and inv.investment_date >= cutoff_date
        ]

        if not relevant_investments:
            return 20.0

        # Investment count
        investment_count = len(relevant_investments)

        # Total capital raised
        total_capital = sum(inv.amount for inv in relevant_investments)
        capital_billions = total_capital / 1000

        # Round size score
        round_sizes = [inv.amount for inv in relevant_investments]
        avg_round_size = sum(round_sizes) / len(round_sizes)

        # Score based on total capital
        if capital_billions >= 5:
            capital_score = 100
        elif capital_billions >= 3:
            capital_score = 85
        elif capital_billions >= 1.5:
            capital_score = 70
        elif capital_billions >= 0.75:
            capital_score = 55
        else:
            capital_score = 40

        # Score based on deal count
        if investment_count >= 20:
            count_score = 100
        elif investment_count >= 15:
            count_score = 85
        elif investment_count >= 10:
            count_score = 70
        elif investment_count >= 5:
            count_score = 55
        else:
            count_score = 40

        # Large round bonus (>$100M rounds indicate sector heat)
        large_rounds = [inv for inv in relevant_investments if inv.amount > 100]
        large_round_bonus = min(len(large_rounds) * 8, 20)

        # Recent acceleration
        recent_investments = [
            inv for inv in relevant_investments
            if inv.investment_date >= datetime.utcnow() - timedelta(days=180)
        ]
        recent_pct = len(recent_investments) / investment_count if investment_count > 0 else 0

        acceleration_bonus = 0
        if recent_pct > 0.5:
            acceleration_bonus = 10

        final_score = (capital_score * 0.5 + count_score * 0.3 +
                      large_round_bonus + acceleration_bonus)

        return round(min(final_score, 100), 2)

    def calculate_trial_activity(
        self,
        area: str,
        trials: List[ClinicalTrial],
        months: int = 24
    ) -> float:
        """
        Calculate clinical trial activity score (0-100).

        High trial activity indicates robust pipeline and
        innovation in the therapeutic area.

        Args:
            area: Therapeutic area
            trials: List of clinical trials
            months: Lookback period

        Returns:
            Trial activity score 0-100
        """
        cutoff_date = datetime.utcnow() - timedelta(days=30 * months)

        relevant_trials = [
            t for t in trials
            if t.therapeutic_area == area and t.start_date >= cutoff_date
        ]

        if not relevant_trials:
            return 20.0

        trial_count = len(relevant_trials)

        # Count by phase
        phase_counts = defaultdict(int)
        for trial in relevant_trials:
            phase_counts[trial.phase] += 1

        # Score based on total trial count
        if trial_count >= 100:
            count_score = 100
        elif trial_count >= 75:
            count_score = 85
        elif trial_count >= 50:
            count_score = 70
        elif trial_count >= 25:
            count_score = 55
        else:
            count_score = 40

        # Late-stage trial bonus (Phase 2/3 more significant)
        late_stage = phase_counts.get('Phase 3', 0) + phase_counts.get('Phase 2', 0)
        late_stage_bonus = min(late_stage * 2, 20)

        # Sponsor diversity (more companies = more interest)
        unique_sponsors = len(set(t.sponsor for t in relevant_trials))
        diversity_bonus = min(unique_sponsors * 1.5, 15)

        # Large enrollment trials (major commitment)
        large_trials = [
            t for t in relevant_trials
            if t.enrollment_target and t.enrollment_target > 500
        ]
        enrollment_bonus = min(len(large_trials) * 3, 15)

        final_score = (count_score * 0.6 + late_stage_bonus +
                      diversity_bonus * 0.5 + enrollment_bonus * 0.5)

        return round(min(final_score, 100), 2)

    def calculate_earnings_mentions(
        self,
        area: str,
        mention_data: Optional[Dict[str, int]] = None
    ) -> float:
        """
        Calculate earnings call mention frequency score (0-100).

        When big pharma CEOs frequently mention a therapeutic area
        in earnings calls, it signals strategic priority and M&A intent.

        This would use NLP on earnings transcripts.

        Args:
            area: Therapeutic area
            mention_data: Dictionary mapping therapeutic area to mention count

        Returns:
            Earnings mention score 0-100
        """
        if mention_data is None:
            # Use baseline scores if no real data
            return self.baseline_scores.get(TherapeuticArea(area), 50.0)

        mention_count = mention_data.get(area, 0)

        # Score based on mention frequency across major pharma
        if mention_count >= 50:  # Mentioned 50+ times in recent calls
            score = 100
        elif mention_count >= 30:
            score = 85
        elif mention_count >= 20:
            score = 70
        elif mention_count >= 10:
            score = 55
        elif mention_count >= 5:
            score = 40
        else:
            score = 25

        return round(score, 2)

    def calculate_momentum_score(
        self,
        area: str,
        ma_deals: Optional[List[MADeal]] = None,
        vc_investments: Optional[List[VCInvestment]] = None,
        trials: Optional[List[ClinicalTrial]] = None,
        mention_data: Optional[Dict[str, int]] = None,
        months: int = 24
    ) -> float:
        """
        Calculate composite therapeutic momentum score (0-100).

        Combines all momentum indicators into single score.

        Component weights:
        - M&A volume: 35%
        - VC investment: 25%
        - Trial activity: 20%
        - Earnings mentions: 20%

        Args:
            area: Therapeutic area
            ma_deals: M&A deal data
            vc_investments: VC investment data
            trials: Clinical trial data
            mention_data: Earnings call mention data
            months: Lookback period

        Returns:
            Composite momentum score 0-100
        """
        # Calculate component scores
        if ma_deals:
            ma_score = self.calculate_ma_volume(area, ma_deals, months)
        else:
            ma_score = self.baseline_scores.get(TherapeuticArea(area), 50.0)

        if vc_investments:
            vc_score = self.calculate_vc_investment(area, vc_investments, months)
        else:
            vc_score = self.baseline_scores.get(TherapeuticArea(area), 50.0)

        if trials:
            trial_score = self.calculate_trial_activity(area, trials, months)
        else:
            trial_score = self.baseline_scores.get(TherapeuticArea(area), 50.0)

        mention_score = self.calculate_earnings_mentions(area, mention_data)

        # Weighted composite
        momentum_score = (
            ma_score * 0.35 +
            vc_score * 0.25 +
            trial_score * 0.20 +
            mention_score * 0.20
        )

        return round(momentum_score, 2)

    def classify_momentum_level(self, score: float) -> MomentumLevel:
        """
        Classify momentum score into heat level.

        Args:
            score: Momentum score 0-100

        Returns:
            MomentumLevel classification
        """
        if score >= 90:
            return MomentumLevel.EXTREME_HOT
        elif score >= 80:
            return MomentumLevel.VERY_HOT
        elif score >= 70:
            return MomentumLevel.HOT
        elif score >= 60:
            return MomentumLevel.WARM
        elif score >= 40:
            return MomentumLevel.NEUTRAL
        elif score >= 20:
            return MomentumLevel.COOL
        else:
            return MomentumLevel.COLD

    def generate_momentum_report(
        self,
        area: str,
        ma_deals: Optional[List[MADeal]] = None,
        vc_investments: Optional[List[VCInvestment]] = None,
        trials: Optional[List[ClinicalTrial]] = None,
        mention_data: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive momentum assessment report.

        Args:
            area: Therapeutic area
            ma_deals: M&A deal data
            vc_investments: VC investment data
            trials: Clinical trial data
            mention_data: Earnings call mention data

        Returns:
            Dictionary with momentum scores, classification, and insights
        """
        # Calculate all scores
        momentum_score = self.calculate_momentum_score(
            area, ma_deals, vc_investments, trials, mention_data
        )

        ma_score = self.calculate_ma_volume(area, ma_deals or []) if ma_deals else None
        vc_score = self.calculate_vc_investment(area, vc_investments or []) if vc_investments else None
        trial_score = self.calculate_trial_activity(area, trials or []) if trials else None
        mention_score = self.calculate_earnings_mentions(area, mention_data)

        momentum_level = self.classify_momentum_level(momentum_score)

        # Generate insights
        insights = []
        if momentum_score >= 90:
            insights.append(
                f"{area} is experiencing extreme market heat comparable to obesity/GLP-1 "
                f"sector. Expect premium valuations and competitive bidding."
            )
        elif momentum_score >= 80:
            insights.append(
                f"{area} is a very hot sector with strong M&A activity. "
                f"Favorable environment for acquisitions."
            )
        elif momentum_score >= 70:
            insights.append(
                f"{area} shows robust momentum with above-average activity."
            )
        elif momentum_score < 50:
            insights.append(
                f"{area} shows limited momentum. May face valuation headwinds."
            )

        # Key metrics
        key_metrics = {}
        if ma_deals:
            recent_deals = [
                d for d in ma_deals
                if d.therapeutic_area == area and
                d.announcement_date >= datetime.utcnow() - timedelta(days=180)
            ]
            key_metrics['recent_deals_6mo'] = len(recent_deals)

        if vc_investments:
            recent_vc = [
                inv for inv in vc_investments
                if inv.therapeutic_area == area and
                inv.investment_date >= datetime.utcnow() - timedelta(days=180)
            ]
            key_metrics['recent_vc_rounds_6mo'] = len(recent_vc)
            if recent_vc:
                key_metrics['total_vc_capital_6mo_M'] = sum(inv.amount for inv in recent_vc)

        return {
            'therapeutic_area': area,
            'momentum_score': momentum_score,
            'momentum_level': momentum_level.value,
            'component_scores': {
                'ma_volume': ma_score,
                'vc_investment': vc_score,
                'trial_activity': trial_score,
                'earnings_mentions': mention_score,
            },
            'key_metrics': key_metrics,
            'insights': insights,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def get_hot_sectors(
        self,
        min_score: float = 70.0
    ) -> List[Tuple[str, float]]:
        """
        Get list of hot therapeutic sectors.

        Args:
            min_score: Minimum momentum score to include

        Returns:
            List of (therapeutic_area, score) tuples sorted by score
        """
        hot_sectors = [
            (area.value, score)
            for area, score in self.baseline_scores.items()
            if score >= min_score
        ]

        # Sort by score descending
        hot_sectors.sort(key=lambda x: x[1], reverse=True)

        return hot_sectors
