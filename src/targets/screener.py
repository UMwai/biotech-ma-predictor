"""
Target Screener - Filters and screening criteria for biotech M&A targets

Implements multi-stage screening to identify companies that fit the
acquisition profile based on market cap, pipeline, financials, and strategic factors.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum
from datetime import datetime


class TherapeuticArea(Enum):
    """Hot therapeutic areas for 2024-2025"""
    OBESITY_GLP1 = "obesity_glp1"
    ONCOLOGY_ADC = "oncology_adc"
    RADIOPHARMACEUTICALS = "radiopharmaceuticals"
    AUTOIMMUNE = "autoimmune"
    CNS_NEUROPSYCHIATRY = "cns_neuropsychiatry"
    RARE_DISEASE = "rare_disease"
    GENE_THERAPY = "gene_therapy"
    IMMUNOLOGY = "immunology"
    CARDIOVASCULAR = "cardiovascular"
    INFECTIOUS_DISEASE = "infectious_disease"


class DevelopmentPhase(Enum):
    """Clinical development phases"""
    PRECLINICAL = "Preclinical"
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    NDA_BLA = "NDA/BLA Filed"
    APPROVED = "Approved"

    @property
    def rank(self) -> int:
        """Numeric rank for comparison"""
        ranks = {
            "Preclinical": 0,
            "Phase 1": 1,
            "Phase 2": 2,
            "Phase 3": 3,
            "NDA/BLA Filed": 4,
            "Approved": 5
        }
        return ranks[self.value]


@dataclass
class ScreeningCriteria:
    """Configurable screening criteria for target identification"""

    # Market cap filters (in USD)
    min_market_cap: float = 500_000_000  # $500M
    max_market_cap: float = 50_000_000_000  # $50B

    # Pipeline requirements
    min_phase: DevelopmentPhase = DevelopmentPhase.PHASE_2
    require_lead_asset: bool = True
    min_pipeline_assets: int = 1

    # Financial health
    min_cash_runway_months: int = 12
    max_cash_runway_months: int = 36  # Sweet spot for acquisition pressure
    max_burn_rate_monthly: Optional[float] = None  # USD per month

    # Strategic filters
    priority_areas: List[TherapeuticArea] = field(default_factory=lambda: [
        TherapeuticArea.OBESITY_GLP1,
        TherapeuticArea.ONCOLOGY_ADC,
        TherapeuticArea.RADIOPHARMACEUTICALS,
        TherapeuticArea.AUTOIMMUNE,
        TherapeuticArea.CNS_NEUROPSYCHIATRY,
        TherapeuticArea.RARE_DISEASE
    ])

    # Recent data catalysts
    require_recent_catalyst: bool = False
    catalyst_lookback_months: int = 6

    # Exclusions
    exclude_preclinical_only: bool = True
    exclude_royalty_companies: bool = True
    exclude_recent_ipos: bool = True  # < 12 months
    ipo_lookback_months: int = 12

    # Geographic focus
    allowed_regions: Set[str] = field(default_factory=lambda: {
        "North America", "Europe", "Asia"
    })

    # Stock performance
    min_stock_decline_52w: Optional[float] = None  # e.g., -30% for distressed
    max_stock_decline_52w: Optional[float] = -80  # Too distressed

    # Institutional ownership
    min_institutional_ownership: float = 0.20  # 20%
    max_institutional_ownership: float = 0.95  # 95%


@dataclass
class CompanyProfile:
    """Company profile for screening"""
    ticker: str
    name: str
    market_cap: float
    cash_position: float
    quarterly_burn_rate: float

    # Pipeline
    lead_asset: Optional[str]
    lead_asset_phase: DevelopmentPhase
    therapeutic_areas: List[TherapeuticArea]
    total_pipeline_assets: int

    # Strategic
    recent_catalysts: List[Dict]
    ipo_date: Optional[datetime]
    region: str

    # Stock metrics
    stock_return_52w: float
    stock_return_ytd: float
    institutional_ownership: float

    # Special flags
    is_royalty_company: bool = False
    has_approved_products: bool = False
    is_platform_company: bool = False

    @property
    def cash_runway_months(self) -> float:
        """Calculate cash runway in months"""
        if self.quarterly_burn_rate <= 0:
            return 999  # No burn or cash positive
        monthly_burn = self.quarterly_burn_rate / 3
        return self.cash_position / monthly_burn

    @property
    def is_distressed(self) -> bool:
        """Check if company is in distressed situation"""
        return (
            self.cash_runway_months < 18 or
            self.stock_return_52w < -50
        )


class TargetScreener:
    """
    Multi-stage screener for identifying biotech acquisition targets

    Uses configurable criteria to filter companies and identify
    those most likely to be acquired based on multiple factors.
    """

    def __init__(self, criteria: Optional[ScreeningCriteria] = None):
        """
        Initialize screener with criteria

        Args:
            criteria: ScreeningCriteria object, uses defaults if None
        """
        self.criteria = criteria or ScreeningCriteria()
        self.screening_stats = {
            'total_reviewed': 0,
            'passed_market_cap': 0,
            'passed_pipeline': 0,
            'passed_financial': 0,
            'passed_strategic': 0,
            'final_targets': 0
        }

    def screen_company(self, company: CompanyProfile) -> tuple[bool, List[str]]:
        """
        Screen a single company against all criteria

        Args:
            company: CompanyProfile to evaluate

        Returns:
            Tuple of (passed: bool, reasons: List[str])
        """
        self.screening_stats['total_reviewed'] += 1
        reasons = []

        # Stage 1: Market cap filter
        if not self._check_market_cap(company):
            reasons.append(f"Market cap ${company.market_cap/1e9:.2f}B outside range")
            return False, reasons
        self.screening_stats['passed_market_cap'] += 1

        # Stage 2: Pipeline requirements
        if not self._check_pipeline(company):
            reasons.append(f"Pipeline does not meet requirements")
            return False, reasons
        self.screening_stats['passed_pipeline'] += 1

        # Stage 3: Financial health
        if not self._check_financial_health(company):
            reasons.append(f"Financial health outside target range")
            return False, reasons
        self.screening_stats['passed_financial'] += 1

        # Stage 4: Strategic fit
        if not self._check_strategic_fit(company):
            reasons.append(f"Does not meet strategic criteria")
            return False, reasons
        self.screening_stats['passed_strategic'] += 1

        # Stage 5: Exclusions
        if not self._check_exclusions(company):
            reasons.append(f"Excluded by specific criteria")
            return False, reasons

        self.screening_stats['final_targets'] += 1
        reasons.append("Passed all screening criteria")
        return True, reasons

    def _check_market_cap(self, company: CompanyProfile) -> bool:
        """Check if market cap is in target range"""
        return (
            self.criteria.min_market_cap <= company.market_cap <=
            self.criteria.max_market_cap
        )

    def _check_pipeline(self, company: CompanyProfile) -> bool:
        """Check pipeline requirements"""
        # Lead asset requirement
        if self.criteria.require_lead_asset and not company.lead_asset:
            return False

        # Minimum phase requirement
        if company.lead_asset_phase.rank < self.criteria.min_phase.rank:
            return False

        # Minimum number of pipeline assets
        if company.total_pipeline_assets < self.criteria.min_pipeline_assets:
            return False

        return True

    def _check_financial_health(self, company: CompanyProfile) -> bool:
        """Check financial health metrics"""
        runway = company.cash_runway_months

        # Cash runway must be in range
        if runway < self.criteria.min_cash_runway_months:
            return False

        if runway > self.criteria.max_cash_runway_months:
            # Allow exceptions for strategic reasons
            if not self._has_strategic_exception(company):
                return False

        # Burn rate check
        if self.criteria.max_burn_rate_monthly:
            monthly_burn = company.quarterly_burn_rate / 3
            if monthly_burn > self.criteria.max_burn_rate_monthly:
                return False

        return True

    def _check_strategic_fit(self, company: CompanyProfile) -> bool:
        """Check strategic fit criteria"""
        # Priority therapeutic areas
        has_priority_area = any(
            area in self.criteria.priority_areas
            for area in company.therapeutic_areas
        )
        if not has_priority_area:
            return False

        # Regional requirements
        if company.region not in self.criteria.allowed_regions:
            return False

        # Recent catalysts
        if self.criteria.require_recent_catalyst:
            if not company.recent_catalysts:
                return False

        # Stock performance
        if self.criteria.min_stock_decline_52w is not None:
            if company.stock_return_52w > self.criteria.min_stock_decline_52w:
                return False

        if company.stock_return_52w < self.criteria.max_stock_decline_52w:
            return False  # Too distressed

        # Institutional ownership
        if not (self.criteria.min_institutional_ownership <=
                company.institutional_ownership <=
                self.criteria.max_institutional_ownership):
            return False

        return True

    def _check_exclusions(self, company: CompanyProfile) -> bool:
        """Check exclusion criteria"""
        # Preclinical only
        if self.criteria.exclude_preclinical_only:
            if (company.lead_asset_phase == DevelopmentPhase.PRECLINICAL and
                company.total_pipeline_assets == 1):
                return False

        # Royalty companies
        if self.criteria.exclude_royalty_companies and company.is_royalty_company:
            return False

        # Recent IPOs
        if self.criteria.exclude_recent_ipos and company.ipo_date:
            months_since_ipo = (
                (datetime.now() - company.ipo_date).days / 30
            )
            if months_since_ipo < self.criteria.ipo_lookback_months:
                return False

        return True

    def _has_strategic_exception(self, company: CompanyProfile) -> bool:
        """Check if company qualifies for strategic exception to runway limits"""
        # Hot therapeutic areas get exception
        hot_areas = [
            TherapeuticArea.OBESITY_GLP1,
            TherapeuticArea.RADIOPHARMACEUTICALS,
            TherapeuticArea.ONCOLOGY_ADC
        ]
        if any(area in hot_areas for area in company.therapeutic_areas):
            return True

        # Platform companies
        if company.is_platform_company:
            return True

        # Phase 3 or later
        if company.lead_asset_phase.rank >= DevelopmentPhase.PHASE_3.rank:
            return True

        return False

    def batch_screen(self, companies: List[CompanyProfile]) -> Dict:
        """
        Screen multiple companies

        Args:
            companies: List of CompanyProfile objects

        Returns:
            Dict with 'passed' and 'failed' companies and stats
        """
        passed = []
        failed = []

        for company in companies:
            result, reasons = self.screen_company(company)
            if result:
                passed.append({
                    'company': company,
                    'reasons': reasons
                })
            else:
                failed.append({
                    'company': company,
                    'reasons': reasons
                })

        return {
            'passed': passed,
            'failed': failed,
            'stats': self.screening_stats,
            'pass_rate': len(passed) / len(companies) if companies else 0
        }

    def get_priority_targets(
        self,
        companies: List[CompanyProfile],
        focus_areas: Optional[List[TherapeuticArea]] = None
    ) -> List[CompanyProfile]:
        """
        Get high-priority targets in specific therapeutic areas

        Args:
            companies: List of companies to filter
            focus_areas: Specific therapeutic areas to focus on

        Returns:
            List of high-priority CompanyProfile objects
        """
        if focus_areas is None:
            focus_areas = self.criteria.priority_areas

        priority_targets = []

        for company in companies:
            # Must pass screening
            passed, _ = self.screen_company(company)
            if not passed:
                continue

            # Must be in focus area
            if not any(area in focus_areas for area in company.therapeutic_areas):
                continue

            # Additional priority criteria
            if (company.cash_runway_months < 24 or  # Acquisition pressure
                company.lead_asset_phase.rank >= DevelopmentPhase.PHASE_3.rank or  # Advanced
                company.is_distressed):  # Distressed
                priority_targets.append(company)

        return priority_targets

    def reset_stats(self):
        """Reset screening statistics"""
        for key in self.screening_stats:
            self.screening_stats[key] = 0
