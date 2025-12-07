"""
Pipeline Gap Analysis Module

Identifies and quantifies strategic pipeline gaps for potential acquirers.
Matches target company assets to acquirer needs for optimal fit scoring.

Key Concepts:
- Patent cliff analysis (revenue at risk)
- Therapeutic area coverage gaps
- Clinical stage distribution (balanced vs concentrated)
- Competitive positioning weaknesses
- Geographic market gaps
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
from collections import defaultdict


class ClinicalPhase(str, Enum):
    """Clinical development phases."""
    DISCOVERY = "discovery"
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    NDA_BLA = "nda_bla"
    APPROVED = "approved"


class GapSeverity(str, Enum):
    """Pipeline gap severity classification."""
    CRITICAL = "critical"      # Immediate crisis (patent cliff, no backfill)
    HIGH = "high"              # Significant gap affecting strategy
    MODERATE = "moderate"      # Notable gap, manageable
    LOW = "low"                # Minor gap, not urgent
    NONE = "none"              # No meaningful gap


@dataclass
class PatentCliff:
    """
    Patent expiration driving revenue loss.

    Attributes:
        product: Product name
        therapeutic_area: Therapeutic area
        annual_revenue: Current annual revenue (USD millions)
        patent_expiry: Patent expiration date
        biosimilar_risk: Percentage revenue expected loss to generics/biosimilars
        replacement_identified: Whether replacement asset exists in pipeline
    """
    product: str
    therapeutic_area: str
    annual_revenue: float
    patent_expiry: datetime
    biosimilar_risk: float  # 0-100 (% expected revenue loss)
    replacement_identified: bool = False


@dataclass
class PipelineAsset:
    """
    Drug pipeline asset.

    Attributes:
        name: Asset name
        therapeutic_area: Primary therapeutic area
        phase: Clinical development phase
        peak_sales_estimate: Estimated peak annual sales (USD millions)
        launch_year_estimate: Expected approval/launch year
        success_probability: Phase-adjusted probability of success
    """
    name: str
    therapeutic_area: str
    phase: ClinicalPhase
    peak_sales_estimate: float
    launch_year_estimate: Optional[int] = None
    success_probability: float = 0.5
    indication: Optional[str] = None
    is_blockbuster_potential: bool = False


@dataclass
class TherapeuticGap:
    """
    Identified gap in therapeutic area coverage.

    Attributes:
        therapeutic_area: Area with gap
        gap_type: Type of gap (no_presence, weak_pipeline, patent_cliff, etc.)
        severity: Gap severity level
        revenue_at_risk: Revenue at risk from gap (USD millions)
        current_assets: Number of current assets in area
        pipeline_assets: Number of pipeline assets in area
        competitive_position: Current competitive position (1-10 scale)
    """
    therapeutic_area: str
    gap_type: str
    severity: GapSeverity
    revenue_at_risk: float
    current_assets: int
    pipeline_assets: int
    competitive_position: float  # 1-10 scale
    description: str = ""


@dataclass
class AcquirerProfile:
    """
    Acquirer company profile for gap analysis.

    Attributes:
        company: Company name
        total_revenue: Total annual revenue (USD millions)
        therapeutic_areas: List of therapeutic areas with presence
        pipeline: List of pipeline assets
        patent_cliffs: List of upcoming patent cliffs
        strategic_priorities: Stated strategic priorities
    """
    company: str
    total_revenue: float
    therapeutic_areas: List[str]
    pipeline: List[PipelineAsset]
    patent_cliffs: List[PatentCliff]
    strategic_priorities: List[str] = field(default_factory=list)
    revenue_concentration: float = 50.0  # % revenue from top products
    target_therapy_areas: List[str] = field(default_factory=list)


class PipelineGapAnalysis:
    """
    Analyze acquirer pipeline gaps and match to target companies.

    Identifies strategic needs that drive M&A activity and high valuations.

    Example:
        >>> # Analyze big pharma with patent cliff
        >>> acquirer = AcquirerProfile(
        ...     company="BigPharma",
        ...     patent_cliffs=[cliff1, cliff2],
        ...     pipeline=[...]
        ... )
        >>> analyzer = PipelineGapAnalysis()
        >>> gaps = analyzer.identify_acquirer_gaps(acquirer)
        >>> fit_score = analyzer.score_target_fit(target, acquirer)
    """

    def __init__(self, forecast_years: int = 10):
        """
        Initialize pipeline gap analyzer.

        Args:
            forecast_years: Years ahead to analyze for gaps
        """
        self.forecast_years = forecast_years

        # Phase success probabilities (industry averages)
        self.phase_success_rates = {
            ClinicalPhase.DISCOVERY: 0.05,
            ClinicalPhase.PRECLINICAL: 0.10,
            ClinicalPhase.PHASE_1: 0.20,
            ClinicalPhase.PHASE_2: 0.30,
            ClinicalPhase.PHASE_3: 0.60,
            ClinicalPhase.NDA_BLA: 0.85,
            ClinicalPhase.APPROVED: 1.0,
        }

        # Phase timing (years to approval)
        self.phase_timing = {
            ClinicalPhase.DISCOVERY: 10,
            ClinicalPhase.PRECLINICAL: 8,
            ClinicalPhase.PHASE_1: 6,
            ClinicalPhase.PHASE_2: 4,
            ClinicalPhase.PHASE_3: 2,
            ClinicalPhase.NDA_BLA: 0.5,
            ClinicalPhase.APPROVED: 0,
        }

    def analyze_patent_cliffs(
        self,
        acquirer: AcquirerProfile,
        years_ahead: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze patent cliff risk and revenue gap.

        Args:
            acquirer: Acquirer profile
            years_ahead: Years to look ahead

        Returns:
            Dictionary with cliff analysis and risk metrics
        """
        cutoff_date = datetime.utcnow() + timedelta(days=365 * years_ahead)

        # Filter cliffs within forecast period
        upcoming_cliffs = [
            cliff for cliff in acquirer.patent_cliffs
            if cliff.patent_expiry <= cutoff_date
        ]

        if not upcoming_cliffs:
            return {
                'total_revenue_at_risk': 0.0,
                'cliffs_count': 0,
                'critical_cliffs': [],
                'gap_severity': GapSeverity.NONE,
            }

        # Calculate revenue at risk
        total_revenue_at_risk = sum(
            cliff.annual_revenue * (cliff.biosimilar_risk / 100)
            for cliff in upcoming_cliffs
        )

        # Identify critical cliffs (>10% of revenue, <3 years)
        critical_cliffs = []
        for cliff in upcoming_cliffs:
            years_to_expiry = (cliff.patent_expiry - datetime.utcnow()).days / 365
            revenue_pct = (cliff.annual_revenue / acquirer.total_revenue) * 100

            if revenue_pct > 10 and years_to_expiry < 3:
                critical_cliffs.append({
                    'product': cliff.product,
                    'therapeutic_area': cliff.therapeutic_area,
                    'revenue_at_risk': cliff.annual_revenue * (cliff.biosimilar_risk / 100),
                    'years_to_expiry': round(years_to_expiry, 1),
                    'revenue_pct': round(revenue_pct, 1),
                    'has_replacement': cliff.replacement_identified,
                })

        # Assess severity
        revenue_at_risk_pct = (total_revenue_at_risk / acquirer.total_revenue) * 100

        if revenue_at_risk_pct > 30:
            severity = GapSeverity.CRITICAL
        elif revenue_at_risk_pct > 20:
            severity = GapSeverity.HIGH
        elif revenue_at_risk_pct > 10:
            severity = GapSeverity.MODERATE
        elif revenue_at_risk_pct > 5:
            severity = GapSeverity.LOW
        else:
            severity = GapSeverity.NONE

        return {
            'total_revenue_at_risk': round(total_revenue_at_risk, 2),
            'revenue_at_risk_pct': round(revenue_at_risk_pct, 2),
            'cliffs_count': len(upcoming_cliffs),
            'critical_cliffs': critical_cliffs,
            'gap_severity': severity.value,
        }

    def assess_pipeline_balance(
        self,
        acquirer: AcquirerProfile
    ) -> Dict[str, Any]:
        """
        Assess pipeline balance across phases.

        Healthy pipeline has assets distributed across phases.
        Gaps in early/mid/late stage create strategic vulnerabilities.

        Args:
            acquirer: Acquirer profile

        Returns:
            Dictionary with balance metrics
        """
        phase_counts = defaultdict(int)
        phase_risk_adjusted_value = defaultdict(float)

        for asset in acquirer.pipeline:
            # Handle both string and enum phases
            phase_key = asset.phase.value if hasattr(asset.phase, 'value') else asset.phase
            phase_counts[phase_key] += 1

            # Risk-adjusted NPV
            phase_enum = asset.phase if hasattr(asset.phase, 'value') else ClinicalPhase(asset.phase)
            prob_success = self.phase_success_rates.get(phase_enum, 0.5)
            risk_adj_value = asset.peak_sales_estimate * prob_success
            phase_risk_adjusted_value[phase_key] += risk_adj_value

        # Identify phase gaps
        gaps = []

        early_stage = (
            phase_counts[ClinicalPhase.DISCOVERY.value] +
            phase_counts[ClinicalPhase.PRECLINICAL.value] +
            phase_counts[ClinicalPhase.PHASE_1.value]
        )
        mid_stage = (
            phase_counts[ClinicalPhase.PHASE_2.value]
        )
        late_stage = (
            phase_counts[ClinicalPhase.PHASE_3.value] +
            phase_counts[ClinicalPhase.NDA_BLA.value]
        )

        if early_stage < 3:
            gaps.append({
                'stage': 'early',
                'severity': 'high' if early_stage == 0 else 'moderate',
                'description': 'Insufficient early-stage pipeline to sustain future growth'
            })

        if mid_stage < 2:
            gaps.append({
                'stage': 'mid',
                'severity': 'high' if mid_stage == 0 else 'moderate',
                'description': 'Weak mid-stage pipeline creates near-term revenue gap'
            })

        if late_stage < 1:
            gaps.append({
                'stage': 'late',
                'severity': 'critical',
                'description': 'No near-term launches to offset patent losses'
            })

        return {
            'phase_distribution': dict(phase_counts),
            'early_stage_count': early_stage,
            'mid_stage_count': mid_stage,
            'late_stage_count': late_stage,
            'balance_gaps': gaps,
            'total_assets': len(acquirer.pipeline),
        }

    def assess_therapeutic_area_gaps(
        self,
        acquirer: AcquirerProfile
    ) -> List[TherapeuticGap]:
        """
        Identify gaps in therapeutic area coverage.

        Args:
            acquirer: Acquirer profile

        Returns:
            List of therapeutic area gaps
        """
        gaps = []

        # Count assets by therapeutic area
        ta_pipeline_counts = defaultdict(int)
        ta_approved_counts = defaultdict(int)

        for asset in acquirer.pipeline:
            if asset.phase == ClinicalPhase.APPROVED:
                ta_approved_counts[asset.therapeutic_area] += 1
            else:
                ta_pipeline_counts[asset.therapeutic_area] += 1

        # Check each therapeutic area
        for ta in acquirer.therapeutic_areas:
            approved = ta_approved_counts.get(ta, 0)
            pipeline = ta_pipeline_counts.get(ta, 0)

            # Determine if gap exists
            if approved == 0 and pipeline == 0:
                # No presence at all
                gap = TherapeuticGap(
                    therapeutic_area=ta,
                    gap_type="no_presence",
                    severity=GapSeverity.HIGH,
                    revenue_at_risk=0.0,
                    current_assets=0,
                    pipeline_assets=0,
                    competitive_position=0.0,
                    description=f"No current or pipeline assets in {ta}"
                )
                gaps.append(gap)

            elif approved > 0 and pipeline < 2:
                # Weak pipeline despite current presence
                gap = TherapeuticGap(
                    therapeutic_area=ta,
                    gap_type="weak_pipeline",
                    severity=GapSeverity.MODERATE,
                    revenue_at_risk=0.0,
                    current_assets=approved,
                    pipeline_assets=pipeline,
                    competitive_position=5.0,
                    description=f"Insufficient pipeline to sustain {ta} franchise"
                )
                gaps.append(gap)

        # Check for patent cliff areas needing replacement
        cliff_areas = set(cliff.therapeutic_area for cliff in acquirer.patent_cliffs)
        for cliff_area in cliff_areas:
            pipeline_in_area = ta_pipeline_counts.get(cliff_area, 0)

            # Calculate revenue at risk in this area
            revenue_at_risk = sum(
                cliff.annual_revenue * (cliff.biosimilar_risk / 100)
                for cliff in acquirer.patent_cliffs
                if cliff.therapeutic_area == cliff_area
            )

            if pipeline_in_area < 2:
                gap = TherapeuticGap(
                    therapeutic_area=cliff_area,
                    gap_type="patent_cliff_backfill",
                    severity=GapSeverity.CRITICAL if revenue_at_risk > 1000 else GapSeverity.HIGH,
                    revenue_at_risk=revenue_at_risk,
                    current_assets=ta_approved_counts.get(cliff_area, 0),
                    pipeline_assets=pipeline_in_area,
                    competitive_position=6.0,
                    description=f"Patent cliff in {cliff_area} with insufficient replacement pipeline"
                )
                gaps.append(gap)

        return gaps

    def identify_acquirer_gaps(
        self,
        acquirer: AcquirerProfile
    ) -> List[TherapeuticGap]:
        """
        Comprehensive gap identification for acquirer.

        Combines patent cliff, pipeline balance, and therapeutic area analysis.

        Args:
            acquirer: Acquirer profile

        Returns:
            Prioritized list of strategic gaps
        """
        all_gaps = []

        # Patent cliff gaps
        cliff_analysis = self.analyze_patent_cliffs(acquirer)
        for critical_cliff in cliff_analysis.get('critical_cliffs', []):
            gap = TherapeuticGap(
                therapeutic_area=critical_cliff.get('therapeutic_area', 'unknown'),
                gap_type="patent_cliff",
                severity=GapSeverity.CRITICAL,
                revenue_at_risk=critical_cliff['revenue_at_risk'],
                current_assets=1,
                pipeline_assets=0 if not critical_cliff['has_replacement'] else 1,
                competitive_position=7.0,
                description=f"Patent cliff: {critical_cliff['product']} "
                           f"({critical_cliff['revenue_at_risk']:.0f}M at risk)"
            )
            all_gaps.append(gap)

        # Therapeutic area gaps
        ta_gaps = self.assess_therapeutic_area_gaps(acquirer)
        all_gaps.extend(ta_gaps)

        # Sort by severity
        severity_order = {
            GapSeverity.CRITICAL: 0,
            GapSeverity.HIGH: 1,
            GapSeverity.MODERATE: 2,
            GapSeverity.LOW: 3,
            GapSeverity.NONE: 4,
        }

        all_gaps.sort(key=lambda g: (severity_order[g.severity], -g.revenue_at_risk))

        return all_gaps

    def score_target_fit(
        self,
        target_therapeutic_areas: List[str],
        target_phase: str,
        target_peak_sales: float,
        acquirer: AcquirerProfile
    ) -> float:
        """
        Score how well target fits acquirer's pipeline gaps (0-100).

        Higher score = better strategic fit = higher likelihood of acquisition.

        Args:
            target_therapeutic_areas: Target's therapeutic areas
            target_phase: Clinical phase of target's lead asset
            target_peak_sales: Estimated peak sales of target asset
            acquirer: Acquirer profile

        Returns:
            Pipeline gap fit score 0-100
        """
        score = 0.0

        # Identify acquirer gaps
        gaps = self.identify_acquirer_gaps(acquirer)

        # Check if target addresses critical gaps
        critical_gap_match = False
        high_gap_match = False

        for gap in gaps:
            for target_ta in target_therapeutic_areas:
                if gap.therapeutic_area.lower() in target_ta.lower():
                    if gap.severity == GapSeverity.CRITICAL:
                        critical_gap_match = True
                        score += 40
                    elif gap.severity == GapSeverity.HIGH:
                        high_gap_match = True
                        score += 25
                    elif gap.severity == GapSeverity.MODERATE:
                        score += 15

        # Phase appropriateness
        # Late-stage assets better for immediate gap filling
        try:
            phase_enum = ClinicalPhase(target_phase.lower().replace(' ', '_').replace('/', '_'))
            if phase_enum in [ClinicalPhase.PHASE_3, ClinicalPhase.NDA_BLA]:
                score += 20
            elif phase_enum == ClinicalPhase.PHASE_2:
                score += 12
            elif phase_enum == ClinicalPhase.PHASE_1:
                score += 5
        except ValueError:
            score += 10  # Default if phase unclear

        # Peak sales potential (blockbuster potential = higher score)
        if target_peak_sales >= 5000:  # $5B+ blockbuster
            score += 20
        elif target_peak_sales >= 2000:  # $2B+
            score += 15
        elif target_peak_sales >= 1000:  # $1B+
            score += 10
        elif target_peak_sales >= 500:
            score += 5

        # Strategic priority match
        for priority in acquirer.strategic_priorities:
            for target_ta in target_therapeutic_areas:
                if priority.lower() in target_ta.lower():
                    score += 10

        return round(min(score, 100), 2)

    def generate_gap_report(
        self,
        acquirer: AcquirerProfile
    ) -> Dict[str, Any]:
        """
        Generate comprehensive pipeline gap report.

        Args:
            acquirer: Acquirer profile

        Returns:
            Dictionary with gap analysis and recommendations
        """
        # Analyze all gap types
        gaps = self.identify_acquirer_gaps(acquirer)
        cliff_analysis = self.analyze_patent_cliffs(acquirer)
        balance = self.assess_pipeline_balance(acquirer)

        # Generate recommendations
        recommendations = []

        # Critical gaps drive acquisition recommendations
        critical_gaps = [g for g in gaps if g.severity == GapSeverity.CRITICAL]
        if critical_gaps:
            for gap in critical_gaps:
                recommendations.append(
                    f"URGENT: Acquire late-stage {gap.therapeutic_area} asset to "
                    f"address ${gap.revenue_at_risk:.0f}M revenue gap"
                )

        # Pipeline balance recommendations
        if balance['late_stage_count'] == 0:
            recommendations.append(
                "Acquire Phase 3/NDA asset for near-term revenue contribution"
            )

        if balance['early_stage_count'] < 3:
            recommendations.append(
                "Build early-stage pipeline through platform/technology acquisitions"
            )

        # Priority therapeutic areas
        priority_areas = []
        for gap in gaps[:3]:  # Top 3 gaps
            priority_areas.append({
                'therapeutic_area': gap.therapeutic_area,
                'severity': gap.severity.value,
                'revenue_at_risk': gap.revenue_at_risk,
                'description': gap.description,
            })

        return {
            'acquirer': acquirer.company,
            'total_gaps': len(gaps),
            'critical_gaps': len(critical_gaps),
            'patent_cliff_analysis': cliff_analysis,
            'pipeline_balance': balance,
            'priority_gaps': priority_areas,
            'recommendations': recommendations,
            'timestamp': datetime.utcnow().isoformat(),
        }
