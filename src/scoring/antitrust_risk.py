"""
Antitrust Risk Scoring Module

Assesses regulatory barriers to M&A deals from antitrust authorities (FTC/DOJ).
In Metsera case: Novo Nordisk had HIGH antitrust risk (dominant GLP-1 player),
while Pfizer had LOW risk, influencing final acquirer selection.

Key Factors:
- Market share concentration (HHI calculation)
- Therapeutic area overlap
- Recent regulatory scrutiny/challenges
- FTC/DOJ historical blocking patterns
- Geographic market definition
- Vertical integration concerns
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class RiskLevel(str, Enum):
    """Antitrust risk level classification."""
    MINIMAL = "minimal"          # 0-20: No meaningful concerns
    LOW = "low"                  # 20-40: Minor concerns, likely approval
    MODERATE = "moderate"        # 40-60: Some concerns, may need remedies
    HIGH = "high"                # 60-80: Significant concerns, lengthy review
    VERY_HIGH = "very_high"      # 80-100: Deal-killer level, likely block


class RegulatoryAction(str, Enum):
    """Types of regulatory actions."""
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"
    SECOND_REQUEST = "second_request"
    UNDER_REVIEW = "under_review"


@dataclass
class MarketShareData:
    """
    Market share data for therapeutic area.

    Attributes:
        therapeutic_area: Market segment
        acquirer_share: Acquirer's current market share (%)
        target_share: Target's current market share (%)
        top_3_total_share: Combined share of top 3 players (%)
        hhi_current: Current Herfindahl-Hirschman Index
        major_competitors: List of other major players
    """
    therapeutic_area: str
    acquirer_share: float
    target_share: float
    top_3_total_share: float
    hhi_current: float
    major_competitors: List[str]


@dataclass
class RegulatoryHistory:
    """
    Acquirer's regulatory history.

    Attributes:
        company: Acquirer name
        deals_reviewed: Total deals reviewed by FTC/DOJ
        deals_blocked: Number of deals blocked
        deals_with_remedies: Number requiring divestitures/remedies
        second_requests: Number of second requests issued
        recent_challenges: Challenges in last 3 years
    """
    company: str
    deals_reviewed: int
    deals_blocked: int
    deals_with_remedies: int
    second_requests: int
    recent_challenges: int
    under_consent_decree: bool = False


@dataclass
class DealContext:
    """
    Specific deal context for antitrust assessment.

    Attributes:
        acquirer: Acquirer company
        target: Target company
        therapeutic_areas: Overlapping therapeutic areas
        deal_value: Deal value (USD millions)
        pipeline_overlap: Whether pipelines overlap significantly
        geographic_markets: Relevant geographic markets
    """
    acquirer: str
    target: str
    therapeutic_areas: List[str]
    deal_value: float
    pipeline_overlap: bool
    geographic_markets: List[str]


class AntitrustRisk:
    """
    Calculate antitrust/regulatory risk for M&A deals.

    Higher scores indicate higher likelihood of FTC/DOJ challenge.

    Metsera example:
    - Novo Nordisk: HIGH risk (dominant GLP-1 position)
    - Pfizer: LOW risk (minimal obesity presence)

    Example:
        >>> # Novo scenario
        >>> market_data = MarketShareData(
        ...     therapeutic_area="obesity",
        ...     acquirer_share=45.0,  # Novo's dominance
        ...     target_share=0.0,
        ...     hhi_current=2800
        ... )
        >>> scorer = AntitrustRisk()
        >>> risk = scorer.calculate_total(market_data, ...)
        >>> # Expected: 75+ (high risk)
        >>>
        >>> # Pfizer scenario
        >>> market_data2 = MarketShareData(
        ...     therapeutic_area="obesity",
        ...     acquirer_share=2.0,  # Minimal presence
        ...     target_share=0.0,
        ...     hhi_current=2800
        ... )
        >>> risk2 = scorer.calculate_total(market_data2, ...)
        >>> # Expected: 25 (low risk)
    """

    def __init__(self):
        """Initialize antitrust risk scorer."""

        # HHI thresholds (DOJ guidelines)
        self.HHI_UNCONCENTRATED = 1500
        self.HHI_MODERATELY_CONCENTRATED = 2500
        # HHI > 2500 = highly concentrated market

        # HHI delta thresholds
        self.HHI_DELTA_SIGNIFICANT = 200
        self.HHI_DELTA_PRESUMPTION = 100

        # Current FTC/DOJ aggressiveness (2024-2025: very aggressive)
        self.regulatory_climate_multiplier = 1.3  # Would update based on administration

    def calculate_market_share(
        self,
        acquirer_share: float,
        target_share: float,
        therapeutic_area: str
    ) -> float:
        """
        Calculate market share concentration risk (0-100).

        FTC guidelines:
        - Combined share > 35% in concentrated market = high risk
        - Combined share > 50% = very high risk
        - Market leader acquiring competitor = high scrutiny

        Args:
            acquirer_share: Acquirer's current market share (%)
            target_share: Target's market share (%)
            therapeutic_area: Market segment

        Returns:
            Market share risk score 0-100
        """
        combined_share = acquirer_share + target_share

        # Base risk from combined share
        if combined_share >= 50:
            share_risk = 100  # Presumptive illegality
        elif combined_share >= 40:
            share_risk = 85
        elif combined_share >= 30:
            share_risk = 70
        elif combined_share >= 20:
            share_risk = 50
        elif combined_share >= 10:
            share_risk = 30
        else:
            share_risk = 10

        # Market leader penalty
        # If acquirer is already #1 and acquiring competitor
        if acquirer_share >= 25 and target_share >= 5:
            share_risk += 20

        # Minimal acquirer share reduces risk
        # (Pfizer's advantage in Metsera deal)
        if acquirer_share < 5:
            share_risk *= 0.5  # Major risk reduction

        return round(min(share_risk, 100), 2)

    def calculate_post_merger_hhi(
        self,
        market_data: MarketShareData
    ) -> Tuple[float, float, float]:
        """
        Calculate post-merger HHI and delta.

        HHI = sum of squared market shares
        Delta HHI = HHI_post - HHI_pre

        DOJ/FTC guidelines:
        - HHI > 2500 and delta > 200: Presumed anticompetitive
        - HHI > 2500 and delta > 100: Likely challenge

        Args:
            market_data: Market share data

        Returns:
            Tuple of (current_hhi, post_merger_hhi, delta_hhi)
        """
        current_hhi = market_data.hhi_current

        # Calculate HHI increase from merger
        # Delta HHI ≈ 2 * acquirer_share * target_share
        delta_hhi = 2 * market_data.acquirer_share * market_data.target_share

        post_merger_hhi = current_hhi + delta_hhi

        return (current_hhi, post_merger_hhi, delta_hhi)

    def calculate_hhi_risk(self, market_data: MarketShareData) -> float:
        """
        Calculate HHI-based risk score (0-100).

        Args:
            market_data: Market share data

        Returns:
            HHI risk score 0-100
        """
        current_hhi, post_hhi, delta_hhi = self.calculate_post_merger_hhi(market_data)

        score = 0.0

        # Post-merger HHI level
        if post_hhi > 2500:  # Highly concentrated
            if delta_hhi > self.HHI_DELTA_PRESUMPTION:
                score = 90  # Presumptive illegality under guidelines
            else:
                score = 60  # Still concerning
        elif post_hhi > 1500:  # Moderately concentrated
            if delta_hhi > self.HHI_DELTA_SIGNIFICANT:
                score = 70
            else:
                score = 40
        else:  # Unconcentrated
            score = 20

        # Delta HHI additional risk
        if delta_hhi > 400:
            score += 10
        elif delta_hhi > 200:
            score += 5

        return round(min(score, 100), 2)

    def check_recent_ftc_actions(
        self,
        regulatory_history: RegulatoryHistory,
        years_back: int = 3
    ) -> float:
        """
        Check acquirer's recent regulatory scrutiny (0-100).

        Companies with recent challenges face heightened scrutiny.

        Args:
            regulatory_history: Acquirer's regulatory history
            years_back: Years to look back

        Returns:
            Historical scrutiny risk score 0-100
        """
        score = 20.0  # Baseline

        # Recent challenges/blocks
        if regulatory_history.recent_challenges > 0:
            score += regulatory_history.recent_challenges * 15

        # Historical block rate
        if regulatory_history.deals_reviewed > 0:
            block_rate = (regulatory_history.deals_blocked /
                         regulatory_history.deals_reviewed)

            if block_rate > 0.3:  # >30% blocked
                score += 30
            elif block_rate > 0.1:
                score += 15

        # Remedy rate (required divestitures)
        if regulatory_history.deals_reviewed > 0:
            remedy_rate = (regulatory_history.deals_with_remedies /
                          regulatory_history.deals_reviewed)

            if remedy_rate > 0.5:
                score += 20
            elif remedy_rate > 0.25:
                score += 10

        # Second request frequency (extensive review)
        if regulatory_history.deals_reviewed > 0:
            second_request_rate = (regulatory_history.second_requests /
                                  regulatory_history.deals_reviewed)

            if second_request_rate > 0.5:
                score += 15

        # Under consent decree (heightened scrutiny)
        if regulatory_history.under_consent_decree:
            score += 25

        return round(min(score, 100), 2)

    def assess_pipeline_overlap_risk(
        self,
        deal_context: DealContext
    ) -> float:
        """
        Assess risk from pipeline overlap (0-100).

        Even if no current market overlap, FTC now considers
        pipeline-to-pipeline competition (nascent competitor doctrine).

        Args:
            deal_context: Deal-specific context

        Returns:
            Pipeline overlap risk score 0-100
        """
        if not deal_context.pipeline_overlap:
            return 10.0

        score = 50.0  # Base score for overlap

        # Multiple therapeutic area overlaps increase risk
        overlap_count = len(deal_context.therapeutic_areas)

        if overlap_count >= 3:
            score += 30
        elif overlap_count >= 2:
            score += 20
        elif overlap_count >= 1:
            score += 10

        return round(min(score, 100), 2)

    def assess_deal_size_scrutiny(self, deal_value: float) -> float:
        """
        Assess scrutiny based on deal size (0-100).

        Larger deals attract more attention.

        Args:
            deal_value: Deal value in USD millions

        Returns:
            Deal size scrutiny score 0-100
        """
        # HSR filing thresholds and mega-deal attention
        if deal_value >= 10000:  # $10B+ mega-deal
            return 80.0
        elif deal_value >= 5000:  # $5B+
            return 60.0
        elif deal_value >= 1000:  # $1B+
            return 40.0
        elif deal_value >= 100:  # $100M+
            return 25.0
        else:
            return 10.0

    def apply_regulatory_climate(self, base_score: float) -> float:
        """
        Adjust score for current regulatory climate.

        2024-2025: Very aggressive enforcement under Biden FTC.
        Would decrease under more permissive administration.

        Args:
            base_score: Base antitrust risk score

        Returns:
            Climate-adjusted score
        """
        adjusted = base_score * self.regulatory_climate_multiplier
        return round(min(adjusted, 100), 2)

    def calculate_total(
        self,
        market_data: MarketShareData,
        regulatory_history: RegulatoryHistory,
        deal_context: DealContext
    ) -> float:
        """
        Calculate total antitrust risk score (0-100).

        Higher score = higher likelihood of FTC/DOJ challenge.

        Component weights:
        - Market share concentration: 35%
        - HHI analysis: 30%
        - Regulatory history: 20%
        - Pipeline overlap: 10%
        - Deal size scrutiny: 5%

        Then adjusted for regulatory climate.

        Args:
            market_data: Market share data
            regulatory_history: Acquirer's regulatory history
            deal_context: Deal-specific context

        Returns:
            Total antitrust risk score 0-100
        """
        # Component scores
        share_risk = self.calculate_market_share(
            market_data.acquirer_share,
            market_data.target_share,
            market_data.therapeutic_area
        )

        hhi_risk = self.calculate_hhi_risk(market_data)

        history_risk = self.check_recent_ftc_actions(regulatory_history)

        pipeline_risk = self.assess_pipeline_overlap_risk(deal_context)

        size_risk = self.assess_deal_size_scrutiny(deal_context.deal_value)

        # Weighted composite
        base_score = (
            share_risk * 0.35 +
            hhi_risk * 0.30 +
            history_risk * 0.20 +
            pipeline_risk * 0.10 +
            size_risk * 0.05
        )

        # Apply regulatory climate adjustment
        final_score = self.apply_regulatory_climate(base_score)

        return round(final_score, 2)

    def classify_risk_level(self, score: float) -> RiskLevel:
        """
        Classify antitrust risk level.

        Args:
            score: Risk score 0-100

        Returns:
            RiskLevel classification
        """
        if score >= 80:
            return RiskLevel.VERY_HIGH
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MODERATE
        elif score >= 20:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL

    def estimate_review_timeline(self, risk_score: float) -> Dict[str, Any]:
        """
        Estimate regulatory review timeline.

        Args:
            risk_score: Antitrust risk score

        Returns:
            Dictionary with timeline estimates
        """
        if risk_score >= 80:
            return {
                'likely_outcome': 'blocked or withdrawn',
                'timeline_months': '18-24+',
                'second_request_probability': 0.95,
                'remedy_probability': 0.8,
            }
        elif risk_score >= 60:
            return {
                'likely_outcome': 'approved with significant remedies',
                'timeline_months': '12-18',
                'second_request_probability': 0.85,
                'remedy_probability': 0.7,
            }
        elif risk_score >= 40:
            return {
                'likely_outcome': 'approved with minor remedies',
                'timeline_months': '8-12',
                'second_request_probability': 0.5,
                'remedy_probability': 0.4,
            }
        elif risk_score >= 20:
            return {
                'likely_outcome': 'approved',
                'timeline_months': '4-6',
                'second_request_probability': 0.2,
                'remedy_probability': 0.1,
            }
        else:
            return {
                'likely_outcome': 'approved',
                'timeline_months': '2-4',
                'second_request_probability': 0.05,
                'remedy_probability': 0.0,
            }

    def generate_risk_report(
        self,
        market_data: MarketShareData,
        regulatory_history: RegulatoryHistory,
        deal_context: DealContext
    ) -> Dict[str, Any]:
        """
        Generate comprehensive antitrust risk assessment.

        Args:
            market_data: Market share data
            regulatory_history: Regulatory history
            deal_context: Deal context

        Returns:
            Dictionary with risk scores, analysis, and recommendations
        """
        # Calculate scores
        total_score = self.calculate_total(
            market_data, regulatory_history, deal_context
        )

        share_risk = self.calculate_market_share(
            market_data.acquirer_share,
            market_data.target_share,
            market_data.therapeutic_area
        )

        hhi_risk = self.calculate_hhi_risk(market_data)
        current_hhi, post_hhi, delta_hhi = self.calculate_post_merger_hhi(market_data)

        history_risk = self.check_recent_ftc_actions(regulatory_history)
        pipeline_risk = self.assess_pipeline_overlap_risk(deal_context)

        risk_level = self.classify_risk_level(total_score)
        timeline = self.estimate_review_timeline(total_score)

        # Generate insights
        insights = []

        if total_score >= 80:
            insights.append(
                f"VERY HIGH antitrust risk. Deal likely to face FTC/DOJ block. "
                f"Recommend reconsidering transaction or extensive divestiture planning."
            )
        elif total_score >= 60:
            insights.append(
                f"HIGH antitrust risk similar to challenged pharma mergers. "
                f"Expect lengthy review and significant remedy requirements."
            )
        elif total_score >= 40:
            insights.append(
                f"MODERATE risk. Deal likely approvable with targeted remedies. "
                f"Plan for extended timeline and possible divestitures."
            )
        else:
            insights.append(
                f"LOW antitrust risk. Deal should clear regulatory review "
                f"without major obstacles."
            )

        # Market concentration insights
        if post_hhi > 2500 and delta_hhi > 200:
            insights.append(
                f"Post-merger HHI ({post_hhi:.0f}) with delta ({delta_hhi:.0f}) "
                f"exceeds DOJ presumption thresholds. Expect challenge."
            )

        # Acquirer positioning insight (Metsera lesson)
        if market_data.acquirer_share < 5:
            insights.append(
                f"Acquirer's minimal market share ({market_data.acquirer_share:.1f}%) "
                f"significantly reduces antitrust risk (Pfizer advantage in Metsera)."
            )
        elif market_data.acquirer_share > 30:
            insights.append(
                f"Acquirer's dominant position ({market_data.acquirer_share:.1f}%) "
                f"creates major regulatory hurdle (Novo challenge in Metsera)."
            )

        # Remedies recommendation
        remedies = []
        if total_score >= 60:
            if market_data.acquirer_share > 25:
                remedies.append("Consider divesting overlapping products")
            if pipeline_risk > 50:
                remedies.append("Offer to license pipeline assets to third parties")
            if delta_hhi > 200:
                remedies.append("Explore joint venture structure instead of acquisition")

        return {
            'deal': f"{deal_context.acquirer} acquiring {deal_context.target}",
            'total_risk_score': total_score,
            'risk_level': risk_level.value,
            'component_scores': {
                'market_share_risk': share_risk,
                'hhi_risk': hhi_risk,
                'regulatory_history_risk': history_risk,
                'pipeline_overlap_risk': pipeline_risk,
            },
            'market_analysis': {
                'current_hhi': round(current_hhi, 0),
                'post_merger_hhi': round(post_hhi, 0),
                'delta_hhi': round(delta_hhi, 0),
                'combined_market_share': round(
                    market_data.acquirer_share + market_data.target_share, 1
                ),
            },
            'timeline_estimate': timeline,
            'insights': insights,
            'recommended_remedies': remedies,
            'timestamp': datetime.utcnow().isoformat(),
        }
