"""
Acquirer Matching Algorithm

Matches biotech targets with potential acquirers based on strategic fit,
patent cliffs, therapeutic area alignment, and historical acquisition patterns.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum

from .components import TherapeuticArea, ClinicalPhase


class AcquirerType(str, Enum):
    """Types of potential acquirers."""
    BIG_PHARMA = "big_pharma"
    MID_PHARMA = "mid_pharma"
    LARGE_BIOTECH = "large_biotech"
    STRATEGIC_BUYER = "strategic_buyer"
    PRIVATE_EQUITY = "private_equity"


@dataclass
class PatentCliff:
    """
    Represents a patent expiry creating revenue gap for acquirer.

    Attributes:
        drug_name: Name of drug losing patent protection
        therapeutic_area: Drug's therapeutic area
        annual_revenue: Current annual revenue (USD)
        expiry_date: Patent expiration date
        generic_erosion_rate: Expected revenue loss rate
    """
    drug_name: str
    therapeutic_area: TherapeuticArea
    annual_revenue: float
    expiry_date: datetime
    generic_erosion_rate: float = 0.8  # 80% revenue loss typical

    @property
    def revenue_gap(self) -> float:
        """Calculate expected revenue gap."""
        return self.annual_revenue * self.generic_erosion_rate

    @property
    def years_until_cliff(self) -> float:
        """Years until patent expiry."""
        return (self.expiry_date - datetime.utcnow()).days / 365.25

    @property
    def urgency_score(self) -> float:
        """
        Calculate urgency score (0-100) based on time to cliff.

        Most urgent acquisitions happen 1-3 years before cliff.
        """
        years = self.years_until_cliff

        if years < 0:
            return 0  # Already expired
        elif years < 1:
            return 100  # Very urgent
        elif years < 2:
            return 90
        elif years < 3:
            return 80
        elif years < 5:
            return 60
        elif years < 7:
            return 40
        else:
            return 20


@dataclass
class TherapeuticAlignment:
    """
    Scores therapeutic area alignment between acquirer and target.

    Attributes:
        overlap_areas: Therapeutic areas in common
        acquirer_focus_areas: Acquirer's primary focus
        target_focus_areas: Target's primary focus
        strategic_priority: How important is this area to acquirer (0-1)
    """
    overlap_areas: List[TherapeuticArea]
    acquirer_focus_areas: List[TherapeuticArea]
    target_focus_areas: List[TherapeuticArea]
    strategic_priority: float = 0.5

    def calculate_alignment_score(self) -> float:
        """
        Calculate therapeutic area alignment score (0-100).

        Perfect score requires:
        - Target focused in acquirer's priority areas
        - Target brings complementary assets
        - No conflicts with existing portfolio
        """
        if not self.target_focus_areas or not self.acquirer_focus_areas:
            return 0.0

        target_set = set(self.target_focus_areas)
        acquirer_set = set(self.acquirer_focus_areas)
        overlap_set = set(self.overlap_areas)

        # Overlap score (target in acquirer's areas)
        overlap_ratio = len(overlap_set) / len(target_set) if target_set else 0
        overlap_score = overlap_ratio * 60

        # Focus score (target matches acquirer priorities)
        focus_score = self.strategic_priority * 30

        # Diversification bonus (target brings new capabilities)
        new_areas = target_set - acquirer_set
        diversification_score = min(len(new_areas) * 5, 10)

        total = overlap_score + focus_score + diversification_score
        return round(min(total, 100), 2)


@dataclass
class HistoricalAcquisition:
    """
    Historical acquisition data for pattern matching.

    Attributes:
        acquirer_id: ID of acquiring company
        target_id: ID of acquired company
        deal_value: Acquisition price (USD)
        deal_date: When acquisition was announced
        target_market_cap: Target's market cap at announcement
        premium: Premium paid over market cap (%)
        therapeutic_areas: Target's therapeutic areas
        clinical_stage: Most advanced asset stage
        deal_rationale: Primary strategic rationale
    """
    acquirer_id: str
    target_id: str
    deal_value: float
    deal_date: datetime
    target_market_cap: float
    premium: float
    therapeutic_areas: List[TherapeuticArea]
    clinical_stage: ClinicalPhase
    deal_rationale: str

    @property
    def years_ago(self) -> float:
        """Years since acquisition."""
        return (datetime.utcnow() - self.deal_date).days / 365.25

    def calculate_similarity(
        self,
        target_therapeutic_areas: List[TherapeuticArea],
        target_phase: ClinicalPhase,
        target_market_cap: float,
    ) -> float:
        """
        Calculate similarity score between this historical deal and a target.

        Args:
            target_therapeutic_areas: Target's therapeutic areas
            target_phase: Target's clinical stage
            target_market_cap: Target's current market cap

        Returns:
            Similarity score 0-100
        """
        score = 0.0

        # Therapeutic area match
        hist_ta_set = set(self.therapeutic_areas)
        target_ta_set = set(target_therapeutic_areas)
        ta_overlap = len(hist_ta_set & target_ta_set)
        ta_score = (ta_overlap / len(target_ta_set)) * 40 if target_ta_set else 0
        score += ta_score

        # Clinical stage match
        phase_order = [
            ClinicalPhase.PRECLINICAL,
            ClinicalPhase.PHASE_1,
            ClinicalPhase.PHASE_2,
            ClinicalPhase.PHASE_3,
            ClinicalPhase.NDA_BLA,
            ClinicalPhase.APPROVED,
        ]

        if self.clinical_stage == target_phase:
            stage_score = 30
        else:
            try:
                hist_idx = phase_order.index(self.clinical_stage)
                target_idx = phase_order.index(target_phase)
                diff = abs(hist_idx - target_idx)
                stage_score = max(30 - (diff * 10), 0)
            except ValueError:
                stage_score = 0

        score += stage_score

        # Market cap similarity
        if self.target_market_cap > 0 and target_market_cap > 0:
            cap_ratio = min(target_market_cap, self.target_market_cap) / max(
                target_market_cap, self.target_market_cap
            )
            cap_score = cap_ratio * 30
            score += cap_score

        return round(min(score, 100), 2)


@dataclass
class AcquirerMatch:
    """
    Represents a matched acquirer for a target company.

    Attributes:
        acquirer_id: ID of potential acquirer
        acquirer_name: Name of acquirer
        acquirer_type: Type of acquirer
        match_score: Overall match score (0-100)
        therapeutic_alignment: Therapeutic area alignment analysis
        patent_cliff_match: Patent cliff driving acquisition need
        financial_capacity: Acquirer's M&A capacity score
        historical_precedent: Similar past acquisitions
        deal_likelihood: Estimated likelihood (0-1)
        estimated_premium: Estimated acquisition premium (%)
        key_drivers: Primary reasons for match
    """
    acquirer_id: str
    acquirer_name: str
    acquirer_type: AcquirerType
    match_score: float
    therapeutic_alignment: TherapeuticAlignment
    patent_cliff_match: Optional[PatentCliff] = None
    financial_capacity: float = 50.0
    historical_precedent: List[HistoricalAcquisition] = field(default_factory=list)
    deal_likelihood: float = 0.0
    estimated_premium: float = 30.0
    key_drivers: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate deal likelihood based on match score."""
        # Convert match score to likelihood probability
        if self.match_score >= 80:
            self.deal_likelihood = 0.7
        elif self.match_score >= 70:
            self.deal_likelihood = 0.5
        elif self.match_score >= 60:
            self.deal_likelihood = 0.3
        elif self.match_score >= 50:
            self.deal_likelihood = 0.15
        else:
            self.deal_likelihood = 0.05

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'acquirer_id': self.acquirer_id,
            'acquirer_name': self.acquirer_name,
            'acquirer_type': self.acquirer_type,
            'match_score': self.match_score,
            'deal_likelihood': self.deal_likelihood,
            'estimated_premium': self.estimated_premium,
            'therapeutic_alignment_score': self.therapeutic_alignment.calculate_alignment_score(),
            'patent_cliff_urgency': self.patent_cliff_match.urgency_score if self.patent_cliff_match else 0,
            'financial_capacity': self.financial_capacity,
            'historical_deals_count': len(self.historical_precedent),
            'key_drivers': self.key_drivers,
        }


class AcquirerMatcher:
    """
    Algorithm for matching biotech targets with potential acquirers.

    Analyzes strategic fit, patent cliffs, therapeutic alignment, and
    historical patterns to identify and rank likely acquirers.
    """

    def __init__(self, db_pool: Any):
        """
        Initialize acquirer matcher.

        Args:
            db_pool: Database connection pool for queries
        """
        self.db_pool = db_pool

        # Acquirer type preferences (general M&A activity levels)
        self.acquirer_type_activity = {
            AcquirerType.BIG_PHARMA: 1.0,
            AcquirerType.MID_PHARMA: 0.8,
            AcquirerType.LARGE_BIOTECH: 0.7,
            AcquirerType.STRATEGIC_BUYER: 0.6,
            AcquirerType.PRIVATE_EQUITY: 0.5,
        }

    async def match_acquirers(
        self,
        target_id: str,
        top_n: int = 10,
        min_score: float = 40.0,
    ) -> List[AcquirerMatch]:
        """
        Find and rank potential acquirers for a target company.

        Args:
            target_id: ID of target company
            top_n: Number of top matches to return
            min_score: Minimum match score threshold

        Returns:
            Ranked list of acquirer matches
        """
        # Fetch target company data
        target_data = await self._fetch_target_data(target_id)

        if not target_data:
            return []

        # Fetch all potential acquirers
        acquirers = await self._fetch_potential_acquirers()

        # Score each acquirer
        matches = []
        for acquirer in acquirers:
            match = await self._score_acquirer_match(target_data, acquirer)

            if match and match.match_score >= min_score:
                matches.append(match)

        # Sort by match score
        matches.sort(key=lambda x: x.match_score, reverse=True)

        return matches[:top_n]

    async def find_patent_cliff_matches(
        self,
        target_id: str,
        years_ahead: int = 5,
    ) -> List[AcquirerMatch]:
        """
        Find acquirers facing patent cliffs that target could address.

        Args:
            target_id: ID of target company
            years_ahead: Look ahead window for patent cliffs

        Returns:
            Acquirers with patent cliff urgency
        """
        target_data = await self._fetch_target_data(target_id)

        if not target_data:
            return []

        # Fetch patent cliffs in target's therapeutic areas
        patent_cliffs = await self._fetch_patent_cliffs(
            target_data['therapeutic_areas'],
            years_ahead,
        )

        # Match targets to acquirers with cliffs
        matches = []
        for cliff in patent_cliffs:
            acquirer_data = await self._fetch_acquirer_by_id(cliff['acquirer_id'])

            if acquirer_data:
                match = await self._score_acquirer_match(
                    target_data,
                    acquirer_data,
                    patent_cliff=cliff,
                )

                if match:
                    matches.append(match)

        # Sort by cliff urgency and match score
        matches.sort(
            key=lambda x: (
                x.patent_cliff_match.urgency_score if x.patent_cliff_match else 0,
                x.match_score,
            ),
            reverse=True,
        )

        return matches

    async def analyze_historical_patterns(
        self,
        acquirer_id: str,
        years_back: int = 10,
    ) -> Dict[str, Any]:
        """
        Analyze an acquirer's historical M&A patterns.

        Args:
            acquirer_id: ID of acquirer
            years_back: Years of history to analyze

        Returns:
            Pattern analysis including preferences and tendencies
        """
        # Fetch historical deals
        deals = await self._fetch_historical_deals(acquirer_id, years_back)

        if not deals:
            return {
                'deal_count': 0,
                'avg_deal_value': 0,
                'preferred_therapeutic_areas': [],
                'preferred_stages': [],
                'avg_premium': 0,
                'deal_frequency': 0,
            }

        # Analyze patterns
        deal_count = len(deals)
        avg_deal_value = sum(d.deal_value for d in deals) / deal_count
        avg_premium = sum(d.premium for d in deals) / deal_count

        # Therapeutic area preferences
        ta_counts = {}
        for deal in deals:
            for ta in deal.therapeutic_areas:
                ta_counts[ta] = ta_counts.get(ta, 0) + 1

        preferred_tas = sorted(
            ta_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:3]

        # Stage preferences
        stage_counts = {}
        for deal in deals:
            stage = deal.clinical_stage
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        preferred_stages = sorted(
            stage_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:3]

        # Deal frequency (deals per year)
        deal_frequency = deal_count / years_back

        return {
            'deal_count': deal_count,
            'avg_deal_value': avg_deal_value,
            'preferred_therapeutic_areas': [ta for ta, _ in preferred_tas],
            'preferred_stages': [stage for stage, _ in preferred_stages],
            'avg_premium': avg_premium,
            'deal_frequency': deal_frequency,
            'recent_deals': deals[:5],  # Most recent 5
        }

    async def _score_acquirer_match(
        self,
        target_data: Dict[str, Any],
        acquirer_data: Dict[str, Any],
        patent_cliff: Optional[Dict[str, Any]] = None,
    ) -> Optional[AcquirerMatch]:
        """
        Score the match between a target and acquirer.

        Args:
            target_data: Target company data
            acquirer_data: Acquirer company data
            patent_cliff: Optional patent cliff data

        Returns:
            AcquirerMatch object or None
        """
        # Calculate therapeutic alignment
        alignment = TherapeuticAlignment(
            overlap_areas=list(
                set(target_data['therapeutic_areas']) &
                set(acquirer_data['therapeutic_areas'])
            ),
            acquirer_focus_areas=acquirer_data['therapeutic_areas'],
            target_focus_areas=target_data['therapeutic_areas'],
            strategic_priority=acquirer_data.get('strategic_priority', 0.5),
        )

        alignment_score = alignment.calculate_alignment_score()

        # Patent cliff urgency
        cliff_score = 0.0
        cliff_obj = None
        if patent_cliff:
            cliff_obj = PatentCliff(
                drug_name=patent_cliff['drug_name'],
                therapeutic_area=patent_cliff['therapeutic_area'],
                annual_revenue=patent_cliff['annual_revenue'],
                expiry_date=patent_cliff['expiry_date'],
            )
            cliff_score = cliff_obj.urgency_score

        # Financial capacity
        financial_capacity = await self._calculate_financial_capacity(
            acquirer_data['acquirer_id']
        )

        # Historical precedent
        historical_deals = await self._fetch_similar_deals(
            acquirer_data['acquirer_id'],
            target_data['therapeutic_areas'],
            target_data['clinical_stage'],
        )

        historical_score = min(len(historical_deals) * 10, 30)

        # Acquirer type activity level
        type_activity = self.acquirer_type_activity.get(
            acquirer_data['acquirer_type'],
            0.5,
        )

        # Calculate composite match score
        match_score = (
            alignment_score * 0.35 +
            cliff_score * 0.25 +
            financial_capacity * 0.20 +
            historical_score * 0.15 +
            (type_activity * 100) * 0.05
        )

        # Identify key drivers
        key_drivers = []
        if alignment_score >= 70:
            key_drivers.append("Strong therapeutic area alignment")
        if cliff_score >= 80:
            key_drivers.append("Urgent patent cliff")
        if historical_score >= 20:
            key_drivers.append("Historical acquisition pattern match")
        if financial_capacity >= 80:
            key_drivers.append("Strong financial capacity")

        # Estimate premium based on urgency and fit
        base_premium = 30.0
        if cliff_score >= 80:
            base_premium += 20
        if alignment_score >= 80:
            base_premium += 15
        estimated_premium = min(base_premium, 80.0)

        return AcquirerMatch(
            acquirer_id=acquirer_data['acquirer_id'],
            acquirer_name=acquirer_data['acquirer_name'],
            acquirer_type=acquirer_data['acquirer_type'],
            match_score=round(match_score, 2),
            therapeutic_alignment=alignment,
            patent_cliff_match=cliff_obj,
            financial_capacity=financial_capacity,
            historical_precedent=historical_deals,
            estimated_premium=estimated_premium,
            key_drivers=key_drivers,
        )

    async def _fetch_target_data(self, target_id: str) -> Optional[Dict[str, Any]]:
        """Fetch target company data from database."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id,
                    company_name,
                    therapeutic_areas,
                    clinical_stage,
                    market_cap,
                    pipeline_assets
                FROM companies
                WHERE company_id = $1
            """
            row = await conn.fetchrow(query, target_id)

            if not row:
                return None

            return {
                'company_id': row['company_id'],
                'company_name': row['company_name'],
                'therapeutic_areas': row['therapeutic_areas'] or [],
                'clinical_stage': row['clinical_stage'],
                'market_cap': row['market_cap'],
                'pipeline_assets': row['pipeline_assets'] or [],
            }

    async def _fetch_potential_acquirers(self) -> List[Dict[str, Any]]:
        """Fetch all potential acquirers from database."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id as acquirer_id,
                    company_name as acquirer_name,
                    acquirer_type,
                    therapeutic_areas,
                    market_cap,
                    cash_position,
                    recent_ma_activity
                FROM acquirers
                WHERE is_active = true
                ORDER BY market_cap DESC
            """
            rows = await conn.fetch(query)

            return [
                {
                    'acquirer_id': row['acquirer_id'],
                    'acquirer_name': row['acquirer_name'],
                    'acquirer_type': row['acquirer_type'],
                    'therapeutic_areas': row['therapeutic_areas'] or [],
                    'market_cap': row['market_cap'],
                    'cash_position': row['cash_position'],
                    'strategic_priority': 0.5,  # Default, could be enhanced
                }
                for row in rows
            ]

    async def _fetch_patent_cliffs(
        self,
        therapeutic_areas: List[TherapeuticArea],
        years_ahead: int,
    ) -> List[Dict[str, Any]]:
        """Fetch patent cliffs in specified therapeutic areas."""
        async with self.db_pool.acquire() as conn:
            cutoff_date = datetime.utcnow() + timedelta(days=years_ahead * 365)

            query = """
                SELECT
                    pc.acquirer_id,
                    pc.drug_name,
                    pc.therapeutic_area,
                    pc.annual_revenue,
                    pc.expiry_date
                FROM patent_cliffs pc
                WHERE pc.therapeutic_area = ANY($1)
                  AND pc.expiry_date <= $2
                  AND pc.expiry_date >= CURRENT_DATE
                ORDER BY pc.expiry_date ASC
            """
            rows = await conn.fetch(query, therapeutic_areas, cutoff_date)

            return [dict(row) for row in rows]

    async def _fetch_acquirer_by_id(self, acquirer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch specific acquirer data."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id as acquirer_id,
                    company_name as acquirer_name,
                    acquirer_type,
                    therapeutic_areas,
                    market_cap
                FROM acquirers
                WHERE company_id = $1
            """
            row = await conn.fetchrow(query, acquirer_id)

            if not row:
                return None

            return {
                'acquirer_id': row['acquirer_id'],
                'acquirer_name': row['acquirer_name'],
                'acquirer_type': row['acquirer_type'],
                'therapeutic_areas': row['therapeutic_areas'] or [],
                'market_cap': row['market_cap'],
                'strategic_priority': 0.5,
            }

    async def _fetch_historical_deals(
        self,
        acquirer_id: str,
        years_back: int,
    ) -> List[HistoricalAcquisition]:
        """Fetch historical M&A deals for an acquirer."""
        async with self.db_pool.acquire() as conn:
            cutoff_date = datetime.utcnow() - timedelta(days=years_back * 365)

            query = """
                SELECT
                    acquirer_id,
                    target_id,
                    deal_value,
                    deal_date,
                    target_market_cap,
                    premium,
                    therapeutic_areas,
                    clinical_stage,
                    deal_rationale
                FROM historical_acquisitions
                WHERE acquirer_id = $1
                  AND deal_date >= $2
                ORDER BY deal_date DESC
            """
            rows = await conn.fetch(query, acquirer_id, cutoff_date)

            return [
                HistoricalAcquisition(
                    acquirer_id=row['acquirer_id'],
                    target_id=row['target_id'],
                    deal_value=row['deal_value'],
                    deal_date=row['deal_date'],
                    target_market_cap=row['target_market_cap'],
                    premium=row['premium'],
                    therapeutic_areas=row['therapeutic_areas'] or [],
                    clinical_stage=row['clinical_stage'],
                    deal_rationale=row['deal_rationale'] or '',
                )
                for row in rows
            ]

    async def _fetch_similar_deals(
        self,
        acquirer_id: str,
        therapeutic_areas: List[TherapeuticArea],
        clinical_stage: ClinicalPhase,
    ) -> List[HistoricalAcquisition]:
        """Fetch historical deals similar to current target."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    acquirer_id,
                    target_id,
                    deal_value,
                    deal_date,
                    target_market_cap,
                    premium,
                    therapeutic_areas,
                    clinical_stage,
                    deal_rationale
                FROM historical_acquisitions
                WHERE acquirer_id = $1
                  AND therapeutic_areas && $2
                ORDER BY deal_date DESC
                LIMIT 10
            """
            rows = await conn.fetch(query, acquirer_id, therapeutic_areas)

            return [
                HistoricalAcquisition(
                    acquirer_id=row['acquirer_id'],
                    target_id=row['target_id'],
                    deal_value=row['deal_value'],
                    deal_date=row['deal_date'],
                    target_market_cap=row['target_market_cap'],
                    premium=row['premium'],
                    therapeutic_areas=row['therapeutic_areas'] or [],
                    clinical_stage=row['clinical_stage'],
                    deal_rationale=row['deal_rationale'] or '',
                )
                for row in rows
            ]

    async def _calculate_financial_capacity(self, acquirer_id: str) -> float:
        """
        Calculate acquirer's M&A financial capacity (0-100).

        Factors:
        - Cash position
        - Debt levels
        - Recent M&A activity
        - Market cap
        """
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    cash_position,
                    total_debt,
                    market_cap,
                    recent_ma_spending
                FROM acquirers
                WHERE company_id = $1
            """
            row = await conn.fetchrow(query, acquirer_id)

            if not row:
                return 50.0

            cash = row['cash_position'] or 0
            debt = row['total_debt'] or 0
            market_cap = row['market_cap'] or 1
            recent_spending = row['recent_ma_spending'] or 0

            # Cash as % of market cap
            cash_ratio = cash / market_cap if market_cap > 0 else 0

            # Debt to market cap
            debt_ratio = debt / market_cap if market_cap > 0 else 0

            # M&A capacity score
            if cash_ratio > 0.5 and debt_ratio < 0.3:
                capacity = 100
            elif cash_ratio > 0.3 and debt_ratio < 0.5:
                capacity = 80
            elif cash_ratio > 0.2:
                capacity = 60
            elif cash_ratio > 0.1:
                capacity = 40
            else:
                capacity = 20

            # Reduce if very recent M&A activity (need time to digest)
            if recent_spending > market_cap * 0.2:  # >20% of market cap
                capacity *= 0.7

            return round(min(capacity, 100), 2)
