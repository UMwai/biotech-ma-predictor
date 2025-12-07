"""
Target Ranker - Sophisticated ranking algorithm for M&A targets

Combines 12 factors (6 original + 6 new) to generate composite scores
and rank potential acquisition targets by likelihood and attractiveness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math


class RankingFactor(Enum):
    """All 12 ranking factors"""
    # Original 6 factors
    PIPELINE_QUALITY = "pipeline_quality"
    MARKET_CAP_FIT = "market_cap_fit"
    CASH_RUNWAY = "cash_runway"
    THERAPEUTIC_AREA = "therapeutic_area"
    CLINICAL_STAGE = "clinical_stage"
    FINANCIAL_DISTRESS = "financial_distress"

    # New 6 factors
    SCIENTIFIC_DIFFERENTIATION = "scientific_differentiation"
    ACQUISITION_TENSION = "acquisition_tension"
    STRATEGIC_ACQUIRER_FIT = "strategic_acquirer_fit"
    DATA_CATALYST_TIMING = "data_catalyst_timing"
    COMPETITIVE_LANDSCAPE = "competitive_landscape"
    DEAL_STRUCTURE_FEASIBILITY = "deal_structure_feasibility"


@dataclass
class RankingWeights:
    """Configurable weights for ranking factors (must sum to 1.0)"""

    # Original factors (0.50 total)
    pipeline_quality: float = 0.10
    market_cap_fit: float = 0.08
    cash_runway: float = 0.10
    therapeutic_area: float = 0.09
    clinical_stage: float = 0.08
    financial_distress: float = 0.05

    # New factors (0.50 total)
    scientific_differentiation: float = 0.12
    acquisition_tension: float = 0.10
    strategic_acquirer_fit: float = 0.10
    data_catalyst_timing: float = 0.08
    competitive_landscape: float = 0.06
    deal_structure_feasibility: float = 0.04

    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = sum([
            self.pipeline_quality,
            self.market_cap_fit,
            self.cash_runway,
            self.therapeutic_area,
            self.clinical_stage,
            self.financial_distress,
            self.scientific_differentiation,
            self.acquisition_tension,
            self.strategic_acquirer_fit,
            self.data_catalyst_timing,
            self.competitive_landscape,
            self.deal_structure_feasibility
        ])
        if not math.isclose(total, 1.0, abs_tol=0.001):
            raise ValueError(f"Weights must sum to 1.0, got {total}")


@dataclass
class FactorScores:
    """Individual factor scores for a target (all 0-100)"""

    # Original factors
    pipeline_quality: float = 0.0
    market_cap_fit: float = 0.0
    cash_runway: float = 0.0
    therapeutic_area: float = 0.0
    clinical_stage: float = 0.0
    financial_distress: float = 0.0

    # New factors
    scientific_differentiation: float = 0.0
    acquisition_tension: float = 0.0
    strategic_acquirer_fit: float = 0.0
    data_catalyst_timing: float = 0.0
    competitive_landscape: float = 0.0
    deal_structure_feasibility: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            'pipeline_quality': self.pipeline_quality,
            'market_cap_fit': self.market_cap_fit,
            'cash_runway': self.cash_runway,
            'therapeutic_area': self.therapeutic_area,
            'clinical_stage': self.clinical_stage,
            'financial_distress': self.financial_distress,
            'scientific_differentiation': self.scientific_differentiation,
            'acquisition_tension': self.acquisition_tension,
            'strategic_acquirer_fit': self.strategic_acquirer_fit,
            'data_catalyst_timing': self.data_catalyst_timing,
            'competitive_landscape': self.competitive_landscape,
            'deal_structure_feasibility': self.deal_structure_feasibility
        }


@dataclass
class RankedTarget:
    """Target with ranking information"""
    ticker: str
    name: str
    composite_score: float  # 0-100
    factor_scores: FactorScores
    rank: int
    percentile: float

    # Additional metadata
    key_strengths: List[str] = field(default_factory=list)
    key_weaknesses: List[str] = field(default_factory=list)
    investment_thesis: str = ""


class TargetRanker:
    """
    Sophisticated ranking engine for biotech M&A targets

    Implements a 12-factor scoring model combining quantitative
    and qualitative factors to identify the most attractive targets.
    """

    def __init__(self, weights: Optional[RankingWeights] = None):
        """
        Initialize ranker with optional custom weights

        Args:
            weights: RankingWeights object, uses defaults if None
        """
        self.weights = weights or RankingWeights()

    def calculate_composite_score(
        self,
        company_data: Dict,
        factor_scores: Optional[FactorScores] = None
    ) -> Tuple[float, FactorScores]:
        """
        Calculate composite M&A score for a company

        Args:
            company_data: Dict with company metrics
            factor_scores: Pre-calculated FactorScores, will calculate if None

        Returns:
            Tuple of (composite_score, factor_scores)
        """
        # Calculate individual factor scores if not provided
        if factor_scores is None:
            factor_scores = self._calculate_all_factors(company_data)

        # Weighted average of all factors
        scores_dict = factor_scores.to_dict()
        composite = sum(
            scores_dict[factor.value] * getattr(self.weights, factor.value)
            for factor in RankingFactor
        )

        return composite, factor_scores

    def _calculate_all_factors(self, data: Dict) -> FactorScores:
        """Calculate all 12 factor scores"""
        return FactorScores(
            # Original factors
            pipeline_quality=self._score_pipeline_quality(data),
            market_cap_fit=self._score_market_cap_fit(data),
            cash_runway=self._score_cash_runway(data),
            therapeutic_area=self._score_therapeutic_area(data),
            clinical_stage=self._score_clinical_stage(data),
            financial_distress=self._score_financial_distress(data),

            # New factors
            scientific_differentiation=self._score_scientific_differentiation(data),
            acquisition_tension=self._score_acquisition_tension(data),
            strategic_acquirer_fit=self._score_strategic_acquirer_fit(data),
            data_catalyst_timing=self._score_data_catalyst_timing(data),
            competitive_landscape=self._score_competitive_landscape(data),
            deal_structure_feasibility=self._score_deal_structure_feasibility(data)
        )

    # ========== ORIGINAL FACTORS ==========

    def _score_pipeline_quality(self, data: Dict) -> float:
        """
        Score pipeline quality (0-100)

        Considers:
        - Number of clinical assets
        - Phase distribution
        - Indication quality
        - Data quality
        """
        score = 0.0

        # Base score from number of assets
        num_assets = data.get('total_pipeline_assets', 0)
        score += min(num_assets * 10, 30)  # Max 30 points

        # Lead asset phase
        phase_scores = {
            'Preclinical': 10,
            'Phase 1': 20,
            'Phase 2': 40,
            'Phase 3': 70,
            'NDA/BLA Filed': 85,
            'Approved': 60  # Lower for M&A context
        }
        lead_phase = data.get('lead_asset_phase', 'Preclinical')
        score += phase_scores.get(lead_phase, 0) * 0.4  # Max 34 points

        # Data quality indicators
        has_positive_data = data.get('has_positive_phase2_data', False)
        has_differentiated_moa = data.get('has_differentiated_moa', False)

        if has_positive_data:
            score += 20
        if has_differentiated_moa:
            score += 16

        return min(score, 100)

    def _score_market_cap_fit(self, data: Dict) -> float:
        """
        Score market cap fit for acquisition (0-100)

        Sweet spot: $1B - $15B
        """
        market_cap = data.get('market_cap', 0)

        # Convert to billions
        mc_b = market_cap / 1e9

        # Optimal range scoring
        if 1 <= mc_b <= 5:
            score = 100  # Sweet spot
        elif 5 < mc_b <= 10:
            score = 90
        elif 10 < mc_b <= 15:
            score = 75
        elif 0.5 <= mc_b < 1:
            score = 85
        elif 15 < mc_b <= 25:
            score = 60
        elif 25 < mc_b <= 50:
            score = 40
        else:
            score = 20

        return score

    def _score_cash_runway(self, data: Dict) -> float:
        """
        Score cash runway for acquisition pressure (0-100)

        Sweet spot: 12-24 months (pressure but not distressed)
        """
        runway_months = data.get('cash_runway_months', 999)

        if 12 <= runway_months <= 18:
            score = 100  # Maximum pressure
        elif 18 < runway_months <= 24:
            score = 90
        elif 9 <= runway_months < 12:
            score = 80  # Very distressed
        elif 24 < runway_months <= 36:
            score = 70
        elif 6 <= runway_months < 9:
            score = 60  # Too distressed
        elif 36 < runway_months <= 48:
            score = 50
        else:
            score = 30  # Too comfortable or too desperate

        return score

    def _score_therapeutic_area(self, data: Dict) -> float:
        """
        Score therapeutic area attractiveness (0-100)

        Based on 2024-2025 M&A trends
        """
        area_scores = {
            'obesity_glp1': 100,  # Hottest area
            'radiopharmaceuticals': 95,
            'oncology_adc': 90,
            'autoimmune': 85,
            'cns_neuropsychiatry': 80,
            'rare_disease': 75,
            'gene_therapy': 70,
            'immunology': 65,
            'cardiovascular': 60,
            'infectious_disease': 55
        }

        therapeutic_areas = data.get('therapeutic_areas', [])
        if not therapeutic_areas:
            return 30

        # Take highest scoring area
        max_score = max(
            area_scores.get(area, 40) for area in therapeutic_areas
        )

        return max_score

    def _score_clinical_stage(self, data: Dict) -> float:
        """
        Score clinical development stage (0-100)

        Phase 2/3 most attractive for M&A
        """
        stage_scores = {
            'Preclinical': 20,
            'Phase 1': 40,
            'Phase 2': 90,  # Sweet spot
            'Phase 3': 95,  # Sweet spot
            'NDA/BLA Filed': 75,  # Often too late
            'Approved': 50  # Depends on commercial performance
        }

        stage = data.get('lead_asset_phase', 'Preclinical')
        return stage_scores.get(stage, 30)

    def _score_financial_distress(self, data: Dict) -> float:
        """
        Score financial distress level (0-100)

        Moderate distress is ideal for M&A
        """
        score = 0.0

        # Stock performance (40 points)
        stock_return_52w = data.get('stock_return_52w', 0)
        if -40 <= stock_return_52w <= -20:
            score += 40  # Moderate decline
        elif -60 <= stock_return_52w < -40:
            score += 35
        elif -20 <= stock_return_52w < 0:
            score += 30
        elif stock_return_52w < -60:
            score += 20  # Too distressed
        else:
            score += 10  # No distress

        # Cash position (30 points)
        runway = data.get('cash_runway_months', 999)
        if 12 <= runway <= 18:
            score += 30
        elif 18 < runway <= 24:
            score += 25
        elif runway < 12:
            score += 15
        else:
            score += 10

        # Market sentiment (30 points)
        analyst_sentiment = data.get('analyst_sentiment', 'neutral')
        sentiment_scores = {
            'bearish': 30,
            'neutral': 20,
            'bullish': 10
        }
        score += sentiment_scores.get(analyst_sentiment, 15)

        return min(score, 100)

    # ========== NEW FACTORS ==========

    def _score_scientific_differentiation(self, data: Dict) -> float:
        """
        Score scientific/technical differentiation (0-100)

        Novel MOAs, proprietary tech, unique data
        """
        score = 0.0

        # Novel mechanism of action (30 points)
        if data.get('has_novel_moa', False):
            score += 30
        elif data.get('has_differentiated_moa', False):
            score += 20

        # Proprietary platform/technology (25 points)
        if data.get('has_proprietary_platform', False):
            score += 25

        # Clinical differentiation (25 points)
        if data.get('has_best_in_class_data', False):
            score += 25
        elif data.get('has_positive_phase2_data', False):
            score += 15

        # IP strength (20 points)
        patent_years = data.get('patent_life_years', 0)
        if patent_years >= 15:
            score += 20
        elif patent_years >= 10:
            score += 15
        elif patent_years >= 5:
            score += 10

        return min(score, 100)

    def _score_acquisition_tension(self, data: Dict) -> float:
        """
        Score competitive acquisition tension (0-100)

        Multiple potential acquirers, strategic fit
        """
        score = 0.0

        # Number of likely acquirers (40 points)
        num_acquirers = data.get('num_likely_acquirers', 0)
        score += min(num_acquirers * 10, 40)

        # Recent acquirer interest signals (30 points)
        has_recent_partnership = data.get('has_recent_partnership', False)
        has_activist_investor = data.get('has_activist_investor', False)
        has_takeover_rumors = data.get('has_takeover_rumors', False)

        if has_takeover_rumors:
            score += 15
        if has_activist_investor:
            score += 10
        if has_recent_partnership:
            score += 5

        # Strategic scarcity (30 points)
        is_only_asset_in_space = data.get('is_only_asset_in_space', False)
        has_orphan_designation = data.get('has_orphan_designation', False)

        if is_only_asset_in_space:
            score += 20
        if has_orphan_designation:
            score += 10

        return min(score, 100)

    def _score_strategic_acquirer_fit(self, data: Dict) -> float:
        """
        Score strategic fit with potential acquirers (0-100)

        Portfolio gaps, commercial synergies
        """
        score = 0.0

        # Fills portfolio gap (35 points)
        fills_major_gap = data.get('fills_portfolio_gap', False)
        complements_portfolio = data.get('complements_existing_portfolio', False)

        if fills_major_gap:
            score += 35
        elif complements_portfolio:
            score += 25

        # Commercial infrastructure fit (30 points)
        existing_sales_force_fit = data.get('existing_sales_force_fit', False)
        geographic_fit = data.get('geographic_fit', False)

        if existing_sales_force_fit:
            score += 20
        if geographic_fit:
            score += 10

        # Pipeline synergies (20 points)
        has_combination_potential = data.get('has_combination_potential', False)
        if has_combination_potential:
            score += 20

        # Cultural/strategic fit (15 points)
        similar_therapeutic_focus = data.get('similar_therapeutic_focus', False)
        if similar_therapeutic_focus:
            score += 15

        return min(score, 100)

    def _score_data_catalyst_timing(self, data: Dict) -> float:
        """
        Score upcoming data catalysts (0-100)

        Near-term readouts create acquisition urgency
        """
        score = 0.0

        # Upcoming catalyst in next 6 months (40 points)
        months_to_catalyst = data.get('months_to_next_catalyst', 999)

        if 1 <= months_to_catalyst <= 3:
            score += 40
        elif 3 < months_to_catalyst <= 6:
            score += 35
        elif 6 < months_to_catalyst <= 12:
            score += 25
        elif months_to_catalyst > 12:
            score += 10

        # Catalyst type importance (30 points)
        catalyst_type = data.get('next_catalyst_type', '')
        catalyst_scores = {
            'phase3_topline': 30,
            'phase2_data': 25,
            'nda_filing': 20,
            'partnership': 15,
            'phase1_data': 10
        }
        score += catalyst_scores.get(catalyst_type, 5)

        # Multiple upcoming catalysts (30 points)
        num_catalysts_12mo = data.get('num_catalysts_12mo', 0)
        score += min(num_catalysts_12mo * 10, 30)

        return min(score, 100)

    def _score_competitive_landscape(self, data: Dict) -> float:
        """
        Score competitive positioning (0-100)

        Better to be leading or fast-follower
        """
        score = 0.0

        # Competitive position (50 points)
        position = data.get('competitive_position', 'follower')
        position_scores = {
            'leader': 50,
            'co_leader': 45,
            'fast_follower': 40,
            'follower': 25,
            'laggard': 10
        }
        score += position_scores.get(position, 20)

        # Number of competitors (25 points)
        num_competitors = data.get('num_direct_competitors', 10)
        if num_competitors <= 2:
            score += 25
        elif num_competitors <= 5:
            score += 20
        elif num_competitors <= 10:
            score += 10
        else:
            score += 5

        # Recent competitive developments (25 points)
        competitor_setback = data.get('recent_competitor_setback', False)
        competitor_approval = data.get('recent_competitor_approval', False)

        if competitor_setback:
            score += 20
        if competitor_approval:
            score -= 10  # Negative
        else:
            score += 5

        return max(min(score, 100), 0)

    def _score_deal_structure_feasibility(self, data: Dict) -> float:
        """
        Score deal structure feasibility (0-100)

        Regulatory, antitrust, financing considerations
        """
        score = 70.0  # Base score

        # Antitrust concerns
        has_antitrust_risk = data.get('has_antitrust_risk', False)
        if has_antitrust_risk:
            score -= 30

        # Regulatory complexity
        regulatory_complexity = data.get('regulatory_complexity', 'medium')
        complexity_adjustments = {
            'low': 15,
            'medium': 0,
            'high': -15
        }
        score += complexity_adjustments.get(regulatory_complexity, 0)

        # Shareholder support likelihood
        institutional_ownership = data.get('institutional_ownership', 0.5)
        if institutional_ownership >= 0.7:
            score += 15  # Easier to negotiate
        elif institutional_ownership < 0.3:
            score -= 10

        return max(min(score, 100), 0)

    def rank_targets(
        self,
        companies: List[Dict],
        top_n: Optional[int] = None
    ) -> List[RankedTarget]:
        """
        Rank multiple targets and return sorted list

        Args:
            companies: List of company data dicts
            top_n: Return only top N targets if specified

        Returns:
            List of RankedTarget objects sorted by score
        """
        ranked_targets = []

        for company in companies:
            composite_score, factor_scores = self.calculate_composite_score(company)

            ranked_target = RankedTarget(
                ticker=company['ticker'],
                name=company['name'],
                composite_score=composite_score,
                factor_scores=factor_scores,
                rank=0,  # Will be assigned after sorting
                percentile=0.0  # Will be assigned after sorting
            )

            # Identify strengths and weaknesses
            ranked_target.key_strengths = self._identify_strengths(factor_scores)
            ranked_target.key_weaknesses = self._identify_weaknesses(factor_scores)
            ranked_target.investment_thesis = self._generate_thesis(
                company, factor_scores
            )

            ranked_targets.append(ranked_target)

        # Sort by composite score
        ranked_targets.sort(key=lambda x: x.composite_score, reverse=True)

        # Assign ranks and percentiles
        total = len(ranked_targets)
        for i, target in enumerate(ranked_targets):
            target.rank = i + 1
            target.percentile = ((total - i) / total) * 100

        if top_n:
            return ranked_targets[:top_n]

        return ranked_targets

    def _identify_strengths(self, scores: FactorScores) -> List[str]:
        """Identify top scoring factors as strengths"""
        scores_dict = scores.to_dict()
        sorted_factors = sorted(
            scores_dict.items(),
            key=lambda x: x[1],
            reverse=True
        )

        strengths = []
        for factor, score in sorted_factors[:3]:
            if score >= 70:
                strengths.append(
                    f"{factor.replace('_', ' ').title()} ({score:.0f}/100)"
                )

        return strengths

    def _identify_weaknesses(self, scores: FactorScores) -> List[str]:
        """Identify low scoring factors as weaknesses"""
        scores_dict = scores.to_dict()
        sorted_factors = sorted(scores_dict.items(), key=lambda x: x[1])

        weaknesses = []
        for factor, score in sorted_factors[:3]:
            if score <= 50:
                weaknesses.append(
                    f"{factor.replace('_', ' ').title()} ({score:.0f}/100)"
                )

        return weaknesses

    def _generate_thesis(self, company: Dict, scores: FactorScores) -> str:
        """Generate brief investment thesis"""
        area = company.get('therapeutic_areas', ['Unknown'])[0]
        phase = company.get('lead_asset_phase', 'Unknown')
        market_cap_b = company.get('market_cap', 0) / 1e9

        thesis = (
            f"{company['name']} ({company['ticker']}) is a ${market_cap_b:.1f}B "
            f"{area.replace('_', ' ')} company with a {phase} lead asset. "
        )

        # Add key differentiator
        if scores.scientific_differentiation >= 80:
            thesis += "Strong scientific differentiation and "
        if scores.acquisition_tension >= 80:
            thesis += "high competitive acquisition tension make it "
        else:
            thesis += "Strategic fit and timing make it "

        thesis += "an attractive M&A target."

        return thesis
