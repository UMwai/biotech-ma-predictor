"""
Premium Model - Acquisition Premium Prediction

Predicts acquisition premium based on all scoring factors.
Integrates clinical differentiation, market momentum, competitive tension,
antitrust risk, and pipeline gap analysis.

Metsera achieved 2.0-2.5x premium due to:
- High clinical differentiation (monthly GLP-1)
- Extreme market momentum (obesity sector)
- Multiple bidders (competitive tension)
- Low antitrust risk (for Pfizer)
- Strong pipeline gap fit

Premium Ranges (historical data):
- No competition: 10-20%
- Low competition: 20-40%
- Moderate competition: 40-70%
- High competition: 70-150% (Metsera range)
- Auction: 150-300%+
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class PremiumTier(str, Enum):
    """Acquisition premium tier classification."""
    DISCOUNT = "discount"           # <0%: Distressed/underwater deal
    MINIMAL = "minimal"             # 0-20%: Standard control premium
    BELOW_AVERAGE = "below_average" # 20-40%: Limited competition
    AVERAGE = "average"             # 40-70%: Typical biotech M&A
    ABOVE_AVERAGE = "above_average" # 70-100%: Competitive situation
    HIGH = "high"                   # 100-150%: Strong competition (Metsera)
    EXTREME = "extreme"             # 150%+: Bidding war/auction


@dataclass
class PremiumEstimate:
    """
    Acquisition premium estimate.

    Attributes:
        base_premium_pct: Base premium estimate (%)
        low_estimate_pct: Low end of range (%)
        high_estimate_pct: High end of range (%)
        premium_tier: Premium tier classification
        confidence_level: Confidence in estimate (0-1)
        key_drivers: Main factors driving premium
        risk_factors: Factors that could reduce premium
    """
    base_premium_pct: float
    low_estimate_pct: float
    high_estimate_pct: float
    premium_tier: PremiumTier
    confidence_level: float
    key_drivers: List[str]
    risk_factors: List[str]

    @property
    def multiplier_low(self) -> float:
        """Low premium multiplier (1.0 = no premium)."""
        return 1.0 + (self.low_estimate_pct / 100)

    @property
    def multiplier_base(self) -> float:
        """Base premium multiplier."""
        return 1.0 + (self.base_premium_pct / 100)

    @property
    def multiplier_high(self) -> float:
        """High premium multiplier."""
        return 1.0 + (self.high_estimate_pct / 100)


@dataclass
class PremiumInputs:
    """
    Inputs for premium calculation.

    All scores should be 0-100 scale.

    Attributes:
        clinical_differentiation_score: Clinical differentiation (0-100)
        therapeutic_momentum_score: Market heat/momentum (0-100)
        competitive_tension_score: Bidding war likelihood (0-100)
        antitrust_risk_score: Regulatory barrier (0-100, higher = more risk)
        pipeline_gap_fit_score: Fit with acquirer needs (0-100)
        target_market_cap: Target's current market cap (USD millions)
        target_development_stage: Clinical stage of lead asset
        target_cash: Target's cash position (USD millions)
    """
    clinical_differentiation_score: float
    therapeutic_momentum_score: float
    competitive_tension_score: float
    antitrust_risk_score: float
    pipeline_gap_fit_score: float

    target_market_cap: float
    target_development_stage: str
    target_cash: float = 0.0


class PremiumModel:
    """
    Calculate expected acquisition premium.

    Integrates all scoring factors to predict likely premium range.

    Example:
        >>> # Metsera scenario
        >>> inputs = PremiumInputs(
        ...     clinical_differentiation_score=85,  # Monthly GLP-1
        ...     therapeutic_momentum_score=95,       # Hot obesity market
        ...     competitive_tension_score=85,        # Multiple bidders
        ...     antitrust_risk_score=25,             # Low for Pfizer
        ...     pipeline_gap_fit_score=90,           # Perfect fit
        ...     target_market_cap=500,
        ...     target_development_stage="Phase 2"
        ... )
        >>> model = PremiumModel()
        >>> premium = model.calculate_expected_premium(inputs)
        >>> # Expected: 100-150% premium (2.0-2.5x multiplier)
    """

    def __init__(self):
        """Initialize premium model."""

        # Component weights for premium calculation
        self.weights = {
            'competitive_tension': 0.35,      # Biggest driver
            'clinical_differentiation': 0.25,  # Quality matters
            'therapeutic_momentum': 0.20,      # Market heat
            'pipeline_gap_fit': 0.15,          # Strategic value
            'antitrust_risk': -0.10,           # Risk reduction (negative)
        }

    def estimate_base_premium(
        self,
        clinical_diff: float,
        momentum: float,
        pipeline_fit: float
    ) -> float:
        """
        Estimate base premium from fundamental value drivers (%).

        This is the premium in absence of competitive dynamics.

        Args:
            clinical_diff: Clinical differentiation score (0-100)
            momentum: Therapeutic momentum score (0-100)
            pipeline_fit: Pipeline gap fit score (0-100)

        Returns:
            Base premium percentage (e.g., 40.0 = 40% premium)
        """
        # Average the fundamental value scores
        avg_value_score = (
            clinical_diff * 0.40 +
            momentum * 0.35 +
            pipeline_fit * 0.25
        )

        # Map to premium range
        # Score 0-20: 0-10% premium
        # Score 20-40: 10-25% premium
        # Score 40-60: 25-45% premium
        # Score 60-80: 45-70% premium
        # Score 80-100: 70-100% premium

        if avg_value_score >= 80:
            base_premium = 70 + ((avg_value_score - 80) * 1.5)
        elif avg_value_score >= 60:
            base_premium = 45 + ((avg_value_score - 60) * 1.25)
        elif avg_value_score >= 40:
            base_premium = 25 + ((avg_value_score - 40) * 1.0)
        elif avg_value_score >= 20:
            base_premium = 10 + ((avg_value_score - 20) * 0.75)
        else:
            base_premium = avg_value_score * 0.5

        return round(base_premium, 1)

    def apply_tension_multiplier(
        self,
        base_premium: float,
        tension_score: float
    ) -> Tuple[float, float]:
        """
        Apply competitive tension multiplier to base premium.

        Competitive dynamics can double or triple premiums.

        Args:
            base_premium: Base premium percentage
            tension_score: Competitive tension score (0-100)

        Returns:
            Tuple of (low_premium, high_premium) with competition factored in
        """
        # Tension multiplier on top of base
        if tension_score >= 90:  # Auction
            tension_mult_low = 2.5
            tension_mult_high = 4.0
        elif tension_score >= 75:  # High competition (Metsera)
            tension_mult_low = 1.8
            tension_mult_high = 2.5
        elif tension_score >= 60:  # Moderate competition
            tension_mult_low = 1.4
            tension_mult_high = 1.8
        elif tension_score >= 40:  # Low competition
            tension_mult_low = 1.1
            tension_mult_high = 1.4
        else:  # Minimal competition
            tension_mult_low = 0.9
            tension_mult_high = 1.1

        # Apply multiplier to base premium
        low_premium = base_premium * tension_mult_low
        high_premium = base_premium * tension_mult_high

        return (round(low_premium, 1), round(high_premium, 1))

    def apply_scarcity_adjustment(
        self,
        premium: float,
        clinical_diff: float,
        momentum: float
    ) -> float:
        """
        Adjust premium for asset scarcity.

        Very scarce assets (high differentiation + hot market) get premium boost.

        Args:
            premium: Current premium estimate
            clinical_diff: Clinical differentiation score
            momentum: Market momentum score

        Returns:
            Scarcity-adjusted premium
        """
        # Scarcity = high differentiation in hot market
        scarcity_score = (clinical_diff * 0.6 + momentum * 0.4)

        adjustment = 0.0

        if scarcity_score >= 90:
            adjustment = premium * 0.25  # +25%
        elif scarcity_score >= 80:
            adjustment = premium * 0.15  # +15%
        elif scarcity_score >= 70:
            adjustment = premium * 0.08  # +8%

        return round(premium + adjustment, 1)

    def apply_antitrust_discount(
        self,
        premium: float,
        antitrust_risk: float
    ) -> float:
        """
        Reduce premium for antitrust risk.

        High regulatory risk reduces valuation/premium:
        - Deal uncertainty
        - Extended timeline
        - Divestiture costs
        - Deal break risk

        Args:
            premium: Current premium estimate
            antitrust_risk: Antitrust risk score (0-100)

        Returns:
            Risk-adjusted premium
        """
        # Discount factor based on risk level
        if antitrust_risk >= 80:  # Deal likely blocked
            discount = 0.50  # -50% premium
        elif antitrust_risk >= 60:  # High risk
            discount = 0.30  # -30%
        elif antitrust_risk >= 40:  # Moderate risk
            discount = 0.15  # -15%
        elif antitrust_risk >= 20:  # Low risk
            discount = 0.05  # -5%
        else:
            discount = 0.0

        adjusted_premium = premium * (1 - discount)

        return round(adjusted_premium, 1)

    def apply_stage_adjustment(
        self,
        premium: float,
        stage: str
    ) -> float:
        """
        Adjust premium based on development stage.

        Later stage = lower risk = higher premium potential.

        Args:
            premium: Current premium estimate
            stage: Clinical development stage

        Returns:
            Stage-adjusted premium
        """
        stage_lower = stage.lower()

        # Stage multipliers
        if 'approved' in stage_lower or 'marketed' in stage_lower:
            multiplier = 1.2
        elif 'nda' in stage_lower or 'bla' in stage_lower or 'phase 3' in stage_lower:
            multiplier = 1.15
        elif 'phase 2' in stage_lower:
            multiplier = 1.0
        elif 'phase 1' in stage_lower:
            multiplier = 0.85
        else:  # Preclinical/discovery
            multiplier = 0.70

        return round(premium * multiplier, 1)

    def calculate_confidence(
        self,
        inputs: PremiumInputs
    ) -> float:
        """
        Calculate confidence level in premium estimate (0-1).

        Higher confidence when:
        - Clear competitive dynamics
        - Extreme values (very high or very low scores)
        - Strong market momentum data
        - Clear antitrust position

        Args:
            inputs: Premium calculation inputs

        Returns:
            Confidence level 0-1
        """
        confidence = 0.5  # Baseline

        # High competitive tension = high confidence
        if inputs.competitive_tension_score >= 80 or inputs.competitive_tension_score <= 30:
            confidence += 0.15

        # Extreme differentiation = high confidence
        if inputs.clinical_differentiation_score >= 85 or inputs.clinical_differentiation_score <= 20:
            confidence += 0.15

        # Clear momentum signal = high confidence
        if inputs.therapeutic_momentum_score >= 85 or inputs.therapeutic_momentum_score <= 25:
            confidence += 0.10

        # Clear antitrust position = high confidence
        if inputs.antitrust_risk_score >= 75 or inputs.antitrust_risk_score <= 25:
            confidence += 0.10

        return round(min(confidence, 1.0), 2)

    def identify_key_drivers(
        self,
        inputs: PremiumInputs
    ) -> List[str]:
        """
        Identify key factors driving premium.

        Args:
            inputs: Premium calculation inputs

        Returns:
            List of key driver descriptions
        """
        drivers = []

        if inputs.competitive_tension_score >= 80:
            drivers.append("High competitive tension with multiple bidders")

        if inputs.clinical_differentiation_score >= 80:
            drivers.append("Strong clinical differentiation commands premium")

        if inputs.therapeutic_momentum_score >= 85:
            drivers.append("Extremely hot therapeutic area driving valuations")

        if inputs.pipeline_gap_fit_score >= 80:
            drivers.append("Excellent fit with acquirer strategic needs")

        if inputs.antitrust_risk_score <= 30:
            drivers.append("Low antitrust risk enables aggressive bidding")

        if 'phase 3' in inputs.target_development_stage.lower() or 'nda' in inputs.target_development_stage.lower():
            drivers.append("Late-stage asset reduces risk and supports premium")

        return drivers

    def identify_risk_factors(
        self,
        inputs: PremiumInputs
    ) -> List[str]:
        """
        Identify factors that could reduce premium.

        Args:
            inputs: Premium calculation inputs

        Returns:
            List of risk factor descriptions
        """
        risks = []

        if inputs.competitive_tension_score <= 40:
            risks.append("Limited competition may constrain premium")

        if inputs.clinical_differentiation_score <= 50:
            risks.append("Weak differentiation limits pricing power")

        if inputs.therapeutic_momentum_score <= 40:
            risks.append("Cool market conditions pressure valuations")

        if inputs.antitrust_risk_score >= 60:
            risks.append("High antitrust risk creates deal uncertainty")

        if inputs.pipeline_gap_fit_score <= 50:
            risks.append("Unclear strategic fit may limit buyer interest")

        if 'preclinical' in inputs.target_development_stage.lower() or 'phase 1' in inputs.target_development_stage.lower():
            risks.append("Early stage increases technical risk")

        # Cash position relative to market cap
        if inputs.target_cash > 0:
            cash_ratio = inputs.target_cash / inputs.target_market_cap
            if cash_ratio > 0.6:
                risks.append("High cash/market cap ratio limits premium justification")

        return risks

    def calculate_expected_premium(
        self,
        inputs: PremiumInputs
    ) -> PremiumEstimate:
        """
        Calculate comprehensive expected premium estimate.

        Integrates all scoring factors into premium range prediction.

        Args:
            inputs: Premium calculation inputs (all component scores)

        Returns:
            PremiumEstimate with range, tier, and analysis
        """
        # Step 1: Base premium from fundamental value
        base_premium = self.estimate_base_premium(
            inputs.clinical_differentiation_score,
            inputs.therapeutic_momentum_score,
            inputs.pipeline_gap_fit_score
        )

        # Step 2: Apply competitive tension multiplier
        low_premium, high_premium = self.apply_tension_multiplier(
            base_premium,
            inputs.competitive_tension_score
        )

        # Step 3: Scarcity adjustment
        low_premium = self.apply_scarcity_adjustment(
            low_premium,
            inputs.clinical_differentiation_score,
            inputs.therapeutic_momentum_score
        )
        high_premium = self.apply_scarcity_adjustment(
            high_premium,
            inputs.clinical_differentiation_score,
            inputs.therapeutic_momentum_score
        )

        # Step 4: Antitrust discount
        low_premium = self.apply_antitrust_discount(
            low_premium,
            inputs.antitrust_risk_score
        )
        high_premium = self.apply_antitrust_discount(
            high_premium,
            inputs.antitrust_risk_score
        )

        # Step 5: Development stage adjustment
        low_premium = self.apply_stage_adjustment(
            low_premium,
            inputs.target_development_stage
        )
        high_premium = self.apply_stage_adjustment(
            high_premium,
            inputs.target_development_stage
        )

        # Calculate base (midpoint)
        base_premium_final = (low_premium + high_premium) / 2

        # Determine premium tier
        if base_premium_final >= 150:
            tier = PremiumTier.EXTREME
        elif base_premium_final >= 100:
            tier = PremiumTier.HIGH
        elif base_premium_final >= 70:
            tier = PremiumTier.ABOVE_AVERAGE
        elif base_premium_final >= 40:
            tier = PremiumTier.AVERAGE
        elif base_premium_final >= 20:
            tier = PremiumTier.BELOW_AVERAGE
        elif base_premium_final >= 0:
            tier = PremiumTier.MINIMAL
        else:
            tier = PremiumTier.DISCOUNT

        # Calculate confidence
        confidence = self.calculate_confidence(inputs)

        # Identify drivers and risks
        drivers = self.identify_key_drivers(inputs)
        risks = self.identify_risk_factors(inputs)

        return PremiumEstimate(
            base_premium_pct=round(base_premium_final, 1),
            low_estimate_pct=round(low_premium, 1),
            high_estimate_pct=round(high_premium, 1),
            premium_tier=tier,
            confidence_level=confidence,
            key_drivers=drivers,
            risk_factors=risks
        )

    def estimate_transaction_value(
        self,
        inputs: PremiumInputs,
        premium_estimate: PremiumEstimate
    ) -> Dict[str, float]:
        """
        Estimate transaction values based on premium.

        Args:
            inputs: Premium inputs (includes target market cap)
            premium_estimate: Premium estimate

        Returns:
            Dictionary with transaction value estimates
        """
        market_cap = inputs.target_market_cap

        # Adjust for cash (enterprise value consideration)
        # Some acquirers value cash, others discount it
        enterprise_value = market_cap - (inputs.target_cash * 0.5)

        low_value = enterprise_value * premium_estimate.multiplier_low
        base_value = enterprise_value * premium_estimate.multiplier_base
        high_value = enterprise_value * premium_estimate.multiplier_high

        return {
            'market_cap': round(market_cap, 1),
            'enterprise_value_estimate': round(enterprise_value, 1),
            'transaction_value_low': round(low_value, 1),
            'transaction_value_base': round(base_value, 1),
            'transaction_value_high': round(high_value, 1),
            'premium_low_pct': premium_estimate.low_estimate_pct,
            'premium_base_pct': premium_estimate.base_premium_pct,
            'premium_high_pct': premium_estimate.high_estimate_pct,
        }

    def generate_premium_report(
        self,
        inputs: PremiumInputs,
        target_name: str = "Target"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive premium analysis report.

        Args:
            inputs: Premium calculation inputs
            target_name: Name of target company

        Returns:
            Dictionary with premium analysis and valuation estimates
        """
        premium_estimate = self.calculate_expected_premium(inputs)
        transaction_values = self.estimate_transaction_value(inputs, premium_estimate)

        # Generate narrative
        if premium_estimate.base_premium_pct >= 100:
            narrative = (
                f"{target_name} expected to command {premium_estimate.base_premium_pct:.0f}% "
                f"premium ({premium_estimate.low_estimate_pct:.0f}%-{premium_estimate.high_estimate_pct:.0f}% range) "
                f"similar to high-profile competitive M&A transactions like Metsera."
            )
        elif premium_estimate.base_premium_pct >= 70:
            narrative = (
                f"{target_name} likely to achieve above-average premium of "
                f"{premium_estimate.base_premium_pct:.0f}% due to competitive dynamics."
            )
        elif premium_estimate.base_premium_pct >= 40:
            narrative = (
                f"{target_name} expected to receive typical biotech acquisition premium "
                f"of {premium_estimate.base_premium_pct:.0f}%."
            )
        else:
            narrative = (
                f"{target_name} premium limited to {premium_estimate.base_premium_pct:.0f}% "
                f"due to competitive and market factors."
            )

        return {
            'target': target_name,
            'premium_estimate': {
                'base_premium_pct': premium_estimate.base_premium_pct,
                'range_low_pct': premium_estimate.low_estimate_pct,
                'range_high_pct': premium_estimate.high_estimate_pct,
                'premium_tier': premium_estimate.premium_tier.value,
                'confidence_level': premium_estimate.confidence_level,
            },
            'valuation_estimates': transaction_values,
            'key_drivers': premium_estimate.key_drivers,
            'risk_factors': premium_estimate.risk_factors,
            'input_scores': {
                'clinical_differentiation': inputs.clinical_differentiation_score,
                'therapeutic_momentum': inputs.therapeutic_momentum_score,
                'competitive_tension': inputs.competitive_tension_score,
                'antitrust_risk': inputs.antitrust_risk_score,
                'pipeline_gap_fit': inputs.pipeline_gap_fit_score,
            },
            'narrative': narrative,
            'timestamp': datetime.utcnow().isoformat(),
        }
