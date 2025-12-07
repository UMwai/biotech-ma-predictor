"""
M&A Scoring Engine

Main orchestrator for calculating composite M&A likelihood scores,
managing watchlists, and coordinating acquirer matching.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from .components import (
    ScoreComponents,
    SignalDecay,
    PipelineAsset,
    PatentInfo,
    TherapeuticArea,
    ClinicalPhase,
)
from .acquirer_matcher import AcquirerMatcher, AcquirerMatch
from .weights import ScoringWeights, ScoreComponent


class ScoreTrend(str, Enum):
    """Score movement direction."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class ComponentScore:
    """
    Individual component score with metadata.

    Attributes:
        component: Component name
        score: Score value (0-100)
        weight: Weight in composite score
        signals_count: Number of signals contributing
        last_updated: When score was last calculated
        trend: Recent trend direction
    """
    component: str
    score: float
    weight: float
    signals_count: int = 0
    last_updated: Optional[datetime] = None
    trend: ScoreTrend = ScoreTrend.STABLE

    def weighted_score(self) -> float:
        """Calculate weighted contribution to composite score."""
        return self.score * self.weight


@dataclass
class MAScore:
    """
    Composite M&A likelihood score.

    Attributes:
        company_id: Target company ID
        company_name: Target company name
        overall_score: Composite score (0-100)
        component_scores: Individual component scores
        top_acquirers: Ranked list of potential acquirers
        calculated_at: When score was calculated
        score_trend: Overall score trend
        trend_change: Points change from previous score
        confidence: Score confidence level (0-1)
        key_signals: Most important contributing signals
    """
    company_id: str
    company_name: str
    overall_score: float
    component_scores: Dict[str, ComponentScore]
    top_acquirers: List[AcquirerMatch] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    score_trend: ScoreTrend = ScoreTrend.STABLE
    trend_change: float = 0.0
    confidence: float = 0.5
    key_signals: List[str] = field(default_factory=list)

    def get_component_score(self, component: str) -> float:
        """Get score for a specific component."""
        if component in self.component_scores:
            return self.component_scores[component].score
        return 0.0

    def get_weighted_component_score(self, component: str) -> float:
        """Get weighted score for a specific component."""
        if component in self.component_scores:
            return self.component_scores[component].weighted_score()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'company_id': self.company_id,
            'company_name': self.company_name,
            'overall_score': self.overall_score,
            'component_scores': {
                name: {
                    'score': cs.score,
                    'weight': cs.weight,
                    'weighted_score': cs.weighted_score(),
                    'signals_count': cs.signals_count,
                    'trend': cs.trend,
                }
                for name, cs in self.component_scores.items()
            },
            'top_acquirers': [acq.to_dict() for acq in self.top_acquirers[:5]],
            'calculated_at': self.calculated_at.isoformat(),
            'score_trend': self.score_trend,
            'trend_change': self.trend_change,
            'confidence': self.confidence,
            'key_signals': self.key_signals,
        }


@dataclass
class WatchlistEntry:
    """
    Watchlist entry for a company.

    Attributes:
        company_id: Company ID
        company_name: Company name
        added_at: When added to watchlist
        current_score: Current M&A score
        add_score: Score when added
        peak_score: Highest score observed
        alerts_enabled: Whether to send alerts
        alert_threshold: Score change to trigger alert
    """
    company_id: str
    company_name: str
    added_at: datetime
    current_score: float
    add_score: float
    peak_score: float
    alerts_enabled: bool = True
    alert_threshold: float = 10.0

    @property
    def score_change_from_add(self) -> float:
        """Score change since added to watchlist."""
        return self.current_score - self.add_score

    @property
    def score_change_from_peak(self) -> float:
        """Score change from peak."""
        return self.current_score - self.peak_score

    def should_alert(self, new_score: float) -> bool:
        """Check if score change warrants an alert."""
        if not self.alerts_enabled:
            return False

        score_change = abs(new_score - self.current_score)
        return score_change >= self.alert_threshold


class ScoringEngine:
    """
    Main M&A scoring engine.

    Orchestrates the calculation of composite M&A likelihood scores by
    combining individual component scores with configurable weights.

    Example:
        >>> engine = ScoringEngine(db_pool)
        >>> score = await engine.calculate_ma_score("BIOTECH-123")
        >>> print(f"M&A Score: {score.overall_score}")
        >>> acquirers = await engine.match_acquirers("BIOTECH-123")
    """

    def __init__(
        self,
        db_pool: Any,
        weights: Optional[ScoringWeights] = None,
        signal_decay: Optional[SignalDecay] = None,
    ):
        """
        Initialize scoring engine.

        Args:
            db_pool: Database connection pool
            weights: Scoring weights configuration
            signal_decay: Signal decay configuration
        """
        self.db_pool = db_pool
        self.weights = weights or ScoringWeights()
        self.signal_decay = signal_decay or SignalDecay()

        # Initialize components
        self.score_components = ScoreComponents(self.signal_decay)
        self.acquirer_matcher = AcquirerMatcher(db_pool)

        # Normalize weights
        self.weights.normalize()

    async def calculate_ma_score(
        self,
        company_id: str,
        include_acquirers: bool = True,
        top_acquirers: int = 5,
    ) -> Optional[MAScore]:
        """
        Calculate comprehensive M&A likelihood score for a company.

        Args:
            company_id: Company ID to score
            include_acquirers: Whether to include acquirer matching
            top_acquirers: Number of top acquirers to include

        Returns:
            MAScore object or None if company not found
        """
        # Fetch company data
        company_data = await self._fetch_company_data(company_id)

        if not company_data:
            return None

        # Calculate all component scores in parallel
        component_tasks = [
            self._calculate_pipeline_component(company_id),
            self._calculate_patent_component(company_id),
            self._calculate_financial_component(company_id),
            self._calculate_insider_component(company_id),
            self._calculate_regulatory_component(company_id),
        ]

        component_results = await asyncio.gather(*component_tasks)

        # Build component scores dict
        component_scores = {
            ScoreComponent.PIPELINE: component_results[0],
            ScoreComponent.PATENT: component_results[1],
            ScoreComponent.FINANCIAL: component_results[2],
            ScoreComponent.INSIDER: component_results[3],
            ScoreComponent.REGULATORY: component_results[4],
        }

        # Calculate strategic fit separately for each potential acquirer
        # For overall score, use an average fit score
        avg_strategic_fit = await self._calculate_average_strategic_fit(company_id)
        component_scores[ScoreComponent.STRATEGIC_FIT] = avg_strategic_fit

        # Calculate composite score
        overall_score = self._calculate_composite_score(component_scores)

        # Determine trend
        previous_score = await self._fetch_previous_score(company_id)
        trend, trend_change = self._calculate_trend(overall_score, previous_score)

        # Calculate confidence
        confidence = self._calculate_confidence(component_scores)

        # Identify key signals
        key_signals = self._identify_key_signals(component_scores)

        # Match acquirers if requested
        acquirers = []
        if include_acquirers:
            acquirers = await self.acquirer_matcher.match_acquirers(
                company_id,
                top_n=top_acquirers,
            )

        # Build MAScore object
        ma_score = MAScore(
            company_id=company_id,
            company_name=company_data['company_name'],
            overall_score=overall_score,
            component_scores=component_scores,
            top_acquirers=acquirers,
            score_trend=trend,
            trend_change=trend_change,
            confidence=confidence,
            key_signals=key_signals,
        )

        # Store score in database
        await self._store_score(ma_score)

        return ma_score

    async def batch_calculate_scores(
        self,
        company_ids: List[str],
        include_acquirers: bool = False,
    ) -> List[MAScore]:
        """
        Calculate M&A scores for multiple companies in parallel.

        Args:
            company_ids: List of company IDs
            include_acquirers: Whether to include acquirer matching

        Returns:
            List of MAScore objects
        """
        tasks = [
            self.calculate_ma_score(company_id, include_acquirers)
            for company_id in company_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and None values
        scores = [
            result for result in results
            if isinstance(result, MAScore)
        ]

        return scores

    async def match_acquirers(
        self,
        company_id: str,
        top_n: int = 10,
        min_score: float = 40.0,
    ) -> List[AcquirerMatch]:
        """
        Find and rank potential acquirers for a company.

        Args:
            company_id: Company ID
            top_n: Number of matches to return
            min_score: Minimum match score

        Returns:
            Ranked list of acquirer matches
        """
        return await self.acquirer_matcher.match_acquirers(
            company_id,
            top_n=top_n,
            min_score=min_score,
        )

    async def find_patent_cliff_opportunities(
        self,
        company_id: str,
        years_ahead: int = 5,
    ) -> List[AcquirerMatch]:
        """
        Find acquirers with patent cliffs that company could address.

        Args:
            company_id: Company ID
            years_ahead: Years to look ahead for cliffs

        Returns:
            Acquirer matches with patent cliff urgency
        """
        return await self.acquirer_matcher.find_patent_cliff_matches(
            company_id,
            years_ahead=years_ahead,
        )

    def _calculate_composite_score(
        self,
        component_scores: Dict[str, ComponentScore],
    ) -> float:
        """
        Calculate weighted composite score from components.

        Args:
            component_scores: Dictionary of component scores

        Returns:
            Composite score 0-100
        """
        total_score = sum(
            cs.weighted_score()
            for cs in component_scores.values()
        )

        return round(min(max(total_score, 0), 100), 2)

    def _calculate_trend(
        self,
        current_score: float,
        previous_score: Optional[float],
    ) -> Tuple[ScoreTrend, float]:
        """
        Calculate score trend and change.

        Args:
            current_score: Current score
            previous_score: Previous score (or None)

        Returns:
            Tuple of (trend, change_amount)
        """
        if previous_score is None:
            return ScoreTrend.STABLE, 0.0

        change = current_score - previous_score

        if abs(change) < 2:
            trend = ScoreTrend.STABLE
        elif change > 0:
            trend = ScoreTrend.UP
        else:
            trend = ScoreTrend.DOWN

        return trend, round(change, 2)

    def _calculate_confidence(
        self,
        component_scores: Dict[str, ComponentScore],
    ) -> float:
        """
        Calculate confidence level in the score.

        Higher confidence when:
        - More signals contributing
        - Recent updates to components
        - Component scores are consistent

        Args:
            component_scores: Component scores

        Returns:
            Confidence level 0-1
        """
        total_signals = sum(cs.signals_count for cs in component_scores.values())
        current_time = datetime.utcnow()

        # Signal count contribution
        signal_confidence = min(total_signals / 50, 0.4)

        # Recency contribution
        recency_scores = []
        for cs in component_scores.values():
            if cs.last_updated:
                days_old = (current_time - cs.last_updated).days
                recency = max(1 - (days_old / 90), 0)  # Decay over 90 days
                recency_scores.append(recency)

        recency_confidence = (sum(recency_scores) / len(recency_scores)) * 0.3 if recency_scores else 0

        # Consistency contribution (low variance = high confidence)
        scores = [cs.score for cs in component_scores.values()]
        if len(scores) > 1:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            consistency = max(1 - (variance / 1000), 0) * 0.3
        else:
            consistency = 0

        total_confidence = signal_confidence + recency_confidence + consistency

        return round(min(max(total_confidence, 0.1), 1.0), 2)

    def _identify_key_signals(
        self,
        component_scores: Dict[str, ComponentScore],
    ) -> List[str]:
        """
        Identify most important signals driving the score.

        Args:
            component_scores: Component scores

        Returns:
            List of key signal descriptions
        """
        signals = []

        # Sort components by weighted contribution
        sorted_components = sorted(
            component_scores.items(),
            key=lambda x: x[1].weighted_score(),
            reverse=True,
        )

        # Top 3 contributors
        for component, cs in sorted_components[:3]:
            if cs.score >= 70:
                signals.append(f"Strong {component} score ({cs.score:.0f})")
            elif cs.score >= 50:
                signals.append(f"Moderate {component} score ({cs.score:.0f})")

        # Trends
        for component, cs in component_scores.items():
            if cs.trend == ScoreTrend.UP and cs.score >= 60:
                signals.append(f"{component.capitalize()} improving")

        return signals[:5]

    async def _calculate_pipeline_component(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate pipeline component score."""
        # Fetch pipeline data
        pipeline_data = await self._fetch_pipeline_data(company_id)

        assets = [
            PipelineAsset(
                name=asset['name'],
                phase=asset['phase'],
                indication=asset['indication'],
                therapeutic_area=asset['therapeutic_area'],
                patient_population=asset.get('patient_population'),
                orphan_designation=asset.get('orphan_designation', False),
                breakthrough_designation=asset.get('breakthrough_designation', False),
                fast_track=asset.get('fast_track', False),
                priority_review=asset.get('priority_review', False),
                last_update=asset.get('last_update'),
            )
            for asset in pipeline_data
        ]

        score = self.score_components.calculate_pipeline_score(assets)
        weight = self.weights.get_weight(ScoreComponent.PIPELINE)

        return ComponentScore(
            component=ScoreComponent.PIPELINE,
            score=score,
            weight=weight,
            signals_count=len(assets),
            last_updated=datetime.utcnow(),
        )

    async def _calculate_patent_component(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate patent component score."""
        patent_data = await self._fetch_patent_data(company_id)

        patents = [
            PatentInfo(
                patent_id=patent['patent_id'],
                title=patent['title'],
                expiry_date=patent['expiry_date'],
                claims_count=patent.get('claims_count', 0),
                citations_count=patent.get('citations_count', 0),
                is_composition=patent.get('is_composition', False),
                is_method=patent.get('is_method', False),
                is_formulation=patent.get('is_formulation', False),
            )
            for patent in patent_data
        ]

        score = self.score_components.calculate_patent_score(patents)
        weight = self.weights.get_weight(ScoreComponent.PATENT)

        return ComponentScore(
            component=ScoreComponent.PATENT,
            score=score,
            weight=weight,
            signals_count=len(patents),
            last_updated=datetime.utcnow(),
        )

    async def _calculate_financial_component(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate financial component score."""
        financial_data = await self._fetch_financial_data(company_id)

        score = self.score_components.calculate_financial_score(
            market_cap=financial_data.get('market_cap', 0),
            cash=financial_data.get('cash', 0),
            burn_rate=financial_data.get('burn_rate', 0),
            revenue=financial_data.get('revenue', 0),
            catalyst_date=financial_data.get('next_catalyst_date'),
        )

        weight = self.weights.get_weight(ScoreComponent.FINANCIAL)

        return ComponentScore(
            component=ScoreComponent.FINANCIAL,
            score=score,
            weight=weight,
            signals_count=1,
            last_updated=datetime.utcnow(),
        )

    async def _calculate_insider_component(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate insider activity component score."""
        insider_data = await self._fetch_insider_data(company_id)

        score = self.score_components.calculate_insider_score(
            insider_purchases=insider_data.get('purchases', []),
            insider_sales=insider_data.get('sales', []),
            institutional_changes=insider_data.get('institutional_changes', []),
        )

        weight = self.weights.get_weight(ScoreComponent.INSIDER)

        total_signals = (
            len(insider_data.get('purchases', [])) +
            len(insider_data.get('sales', [])) +
            len(insider_data.get('institutional_changes', []))
        )

        return ComponentScore(
            component=ScoreComponent.INSIDER,
            score=score,
            weight=weight,
            signals_count=total_signals,
            last_updated=datetime.utcnow(),
        )

    async def _calculate_regulatory_component(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate regulatory component score."""
        regulatory_data = await self._fetch_regulatory_data(company_id)

        score = self.score_components.calculate_regulatory_score(
            regulatory_pathway=regulatory_data.get('pathway', 'unclear'),
            fda_interactions=regulatory_data.get('fda_interactions', []),
            clinical_holds=regulatory_data.get('clinical_holds', 0),
            warning_letters=regulatory_data.get('warning_letters', 0),
        )

        weight = self.weights.get_weight(ScoreComponent.REGULATORY)

        return ComponentScore(
            component=ScoreComponent.REGULATORY,
            score=score,
            weight=weight,
            signals_count=len(regulatory_data.get('fda_interactions', [])),
            last_updated=datetime.utcnow(),
        )

    async def _calculate_average_strategic_fit(
        self,
        company_id: str,
    ) -> ComponentScore:
        """Calculate average strategic fit score across potential acquirers."""
        # For overall score, calculate average fit with top acquirers
        # This gives a general "acquirability" score

        company_data = await self._fetch_company_data(company_id)
        if not company_data:
            return ComponentScore(
                component=ScoreComponent.STRATEGIC_FIT,
                score=50.0,
                weight=self.weights.get_weight(ScoreComponent.STRATEGIC_FIT),
            )

        # Fetch top 5 potential acquirers
        top_acquirers = await self._fetch_top_acquirers(5)

        if not top_acquirers:
            return ComponentScore(
                component=ScoreComponent.STRATEGIC_FIT,
                score=50.0,
                weight=self.weights.get_weight(ScoreComponent.STRATEGIC_FIT),
            )

        fit_scores = []
        for acquirer in top_acquirers:
            fit_score = self.score_components.calculate_strategic_fit_score(
                target_therapeutic_areas=company_data['therapeutic_areas'],
                acquirer_therapeutic_areas=acquirer['therapeutic_areas'],
                acquirer_pipeline_gaps=acquirer.get('pipeline_gaps', []),
                technology_fit=0.5,
            )
            fit_scores.append(fit_score)

        avg_fit = sum(fit_scores) / len(fit_scores) if fit_scores else 50.0

        return ComponentScore(
            component=ScoreComponent.STRATEGIC_FIT,
            score=avg_fit,
            weight=self.weights.get_weight(ScoreComponent.STRATEGIC_FIT),
            signals_count=len(top_acquirers),
            last_updated=datetime.utcnow(),
        )

    # Database query methods

    async def _fetch_company_data(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Fetch basic company data."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id,
                    company_name,
                    therapeutic_areas,
                    market_cap
                FROM companies
                WHERE company_id = $1
            """
            row = await conn.fetchrow(query, company_id)

            if not row:
                return None

            return {
                'company_id': row['company_id'],
                'company_name': row['company_name'],
                'therapeutic_areas': row['therapeutic_areas'] or [],
                'market_cap': row['market_cap'],
            }

    async def _fetch_pipeline_data(self, company_id: str) -> List[Dict[str, Any]]:
        """Fetch pipeline data."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    asset_name as name,
                    clinical_phase as phase,
                    indication,
                    therapeutic_area,
                    patient_population,
                    orphan_designation,
                    breakthrough_designation,
                    fast_track,
                    priority_review,
                    last_update
                FROM pipeline_assets
                WHERE company_id = $1
                  AND is_active = true
            """
            rows = await conn.fetch(query, company_id)
            return [dict(row) for row in rows]

    async def _fetch_patent_data(self, company_id: str) -> List[Dict[str, Any]]:
        """Fetch patent data."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    patent_id,
                    title,
                    expiry_date,
                    claims_count,
                    citations_count,
                    is_composition,
                    is_method,
                    is_formulation
                FROM patents
                WHERE company_id = $1
                  AND expiry_date >= CURRENT_DATE
            """
            rows = await conn.fetch(query, company_id)
            return [dict(row) for row in rows]

    async def _fetch_financial_data(self, company_id: str) -> Dict[str, Any]:
        """Fetch financial data."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    market_cap,
                    cash,
                    burn_rate,
                    revenue,
                    next_catalyst_date
                FROM company_financials
                WHERE company_id = $1
                ORDER BY as_of_date DESC
                LIMIT 1
            """
            row = await conn.fetchrow(query, company_id)
            return dict(row) if row else {}

    async def _fetch_insider_data(self, company_id: str) -> Dict[str, Any]:
        """Fetch insider trading data."""
        async with self.db_pool.acquire() as conn:
            # Purchases
            purchases_query = """
                SELECT
                    transaction_date as date,
                    amount,
                    is_executive
                FROM insider_transactions
                WHERE company_id = $1
                  AND transaction_type = 'purchase'
                  AND transaction_date >= CURRENT_DATE - INTERVAL '1 year'
            """
            purchases = await conn.fetch(purchases_query, company_id)

            # Sales
            sales_query = """
                SELECT
                    transaction_date as date,
                    amount,
                    is_executive,
                    is_planned
                FROM insider_transactions
                WHERE company_id = $1
                  AND transaction_type = 'sale'
                  AND transaction_date >= CURRENT_DATE - INTERVAL '1 year'
            """
            sales = await conn.fetch(sales_query, company_id)

            # Institutional changes
            institutional_query = """
                SELECT
                    filing_date as date,
                    position_change_pct,
                    is_activist
                FROM institutional_holdings
                WHERE company_id = $1
                  AND filing_date >= CURRENT_DATE - INTERVAL '1 year'
            """
            institutional = await conn.fetch(institutional_query, company_id)

            return {
                'purchases': [dict(row) for row in purchases],
                'sales': [dict(row) for row in sales],
                'institutional_changes': [dict(row) for row in institutional],
            }

    async def _fetch_regulatory_data(self, company_id: str) -> Dict[str, Any]:
        """Fetch regulatory data."""
        async with self.db_pool.acquire() as conn:
            # Pathway
            pathway_query = """
                SELECT regulatory_pathway
                FROM companies
                WHERE company_id = $1
            """
            pathway_row = await conn.fetchrow(pathway_query, company_id)
            pathway = pathway_row['regulatory_pathway'] if pathway_row else 'unclear'

            # FDA interactions
            interactions_query = """
                SELECT
                    interaction_type as type,
                    outcome,
                    interaction_date as date
                FROM fda_interactions
                WHERE company_id = $1
                  AND interaction_date >= CURRENT_DATE - INTERVAL '2 years'
            """
            interactions = await conn.fetch(interactions_query, company_id)

            # Issues
            issues_query = """
                SELECT
                    COUNT(*) FILTER (WHERE issue_type = 'clinical_hold') as clinical_holds,
                    COUNT(*) FILTER (WHERE issue_type = 'warning_letter') as warning_letters
                FROM regulatory_issues
                WHERE company_id = $1
                  AND issue_date >= CURRENT_DATE - INTERVAL '2 years'
            """
            issues_row = await conn.fetchrow(issues_query, company_id)

            return {
                'pathway': pathway,
                'fda_interactions': [dict(row) for row in interactions],
                'clinical_holds': issues_row['clinical_holds'] if issues_row else 0,
                'warning_letters': issues_row['warning_letters'] if issues_row else 0,
            }

    async def _fetch_top_acquirers(self, limit: int) -> List[Dict[str, Any]]:
        """Fetch top potential acquirers."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id,
                    company_name,
                    therapeutic_areas,
                    pipeline_gaps
                FROM acquirers
                WHERE is_active = true
                ORDER BY market_cap DESC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)
            return [dict(row) for row in rows]

    async def _fetch_previous_score(self, company_id: str) -> Optional[float]:
        """Fetch most recent previous score."""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT overall_score
                FROM ma_scores
                WHERE company_id = $1
                ORDER BY calculated_at DESC
                OFFSET 1
                LIMIT 1
            """
            row = await conn.fetchrow(query, company_id)
            return row['overall_score'] if row else None

    async def _store_score(self, ma_score: MAScore) -> None:
        """Store calculated score in database."""
        async with self.db_pool.acquire() as conn:
            query = """
                INSERT INTO ma_scores (
                    company_id,
                    overall_score,
                    component_scores,
                    calculated_at,
                    score_trend,
                    trend_change,
                    confidence
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            await conn.execute(
                query,
                ma_score.company_id,
                ma_score.overall_score,
                ma_score.to_dict()['component_scores'],
                ma_score.calculated_at,
                ma_score.score_trend,
                ma_score.trend_change,
                ma_score.confidence,
            )


class WatchlistManager:
    """
    Manages M&A watchlists with automatic add/remove based on scores.

    Tracks score changes and generates alerts for significant movements.
    """

    def __init__(self, db_pool: Any, engine: ScoringEngine):
        """
        Initialize watchlist manager.

        Args:
            db_pool: Database connection pool
            engine: Scoring engine instance
        """
        self.db_pool = db_pool
        self.engine = engine

    async def update_watchlist(
        self,
        score: MAScore,
        auto_add: bool = True,
        auto_remove: bool = True,
    ) -> Optional[str]:
        """
        Update watchlist based on score.

        Args:
            score: MA score for company
            auto_add: Automatically add if score exceeds threshold
            auto_remove: Automatically remove if score falls below threshold

        Returns:
            Action taken ("added", "removed", "updated", or None)
        """
        is_on_watchlist = await self._is_on_watchlist(score.company_id)

        # Auto-add logic
        if not is_on_watchlist and auto_add:
            if score.overall_score >= self.engine.weights.watchlist_add_threshold:
                await self.add_to_watchlist(score)
                return "added"

        # Auto-remove logic
        elif is_on_watchlist and auto_remove:
            if score.overall_score < self.engine.weights.watchlist_remove_threshold:
                await self.remove_from_watchlist(score.company_id)
                return "removed"

            # Update existing entry
            await self._update_watchlist_entry(score)
            return "updated"

        return None

    async def add_to_watchlist(
        self,
        score: MAScore,
        alerts_enabled: bool = True,
    ) -> WatchlistEntry:
        """
        Add company to watchlist.

        Args:
            score: MA score for company
            alerts_enabled: Enable alerts for this company

        Returns:
            Created watchlist entry
        """
        entry = WatchlistEntry(
            company_id=score.company_id,
            company_name=score.company_name,
            added_at=datetime.utcnow(),
            current_score=score.overall_score,
            add_score=score.overall_score,
            peak_score=score.overall_score,
            alerts_enabled=alerts_enabled,
            alert_threshold=self.engine.weights.alert_threshold_change,
        )

        async with self.db_pool.acquire() as conn:
            query = """
                INSERT INTO watchlist (
                    company_id,
                    company_name,
                    added_at,
                    current_score,
                    add_score,
                    peak_score,
                    alerts_enabled,
                    alert_threshold
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            await conn.execute(
                query,
                entry.company_id,
                entry.company_name,
                entry.added_at,
                entry.current_score,
                entry.add_score,
                entry.peak_score,
                entry.alerts_enabled,
                entry.alert_threshold,
            )

        return entry

    async def remove_from_watchlist(self, company_id: str) -> bool:
        """
        Remove company from watchlist.

        Args:
            company_id: Company ID to remove

        Returns:
            True if removed, False if not on watchlist
        """
        async with self.db_pool.acquire() as conn:
            query = "DELETE FROM watchlist WHERE company_id = $1"
            result = await conn.execute(query, company_id)

            # Returns "DELETE N" where N is number of rows deleted
            return result.split()[-1] != '0'

    async def get_watchlist(self) -> List[WatchlistEntry]:
        """
        Get all watchlist entries.

        Returns:
            List of watchlist entries sorted by current score
        """
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    company_id,
                    company_name,
                    added_at,
                    current_score,
                    add_score,
                    peak_score,
                    alerts_enabled,
                    alert_threshold
                FROM watchlist
                ORDER BY current_score DESC
            """
            rows = await conn.fetch(query)

            return [
                WatchlistEntry(
                    company_id=row['company_id'],
                    company_name=row['company_name'],
                    added_at=row['added_at'],
                    current_score=row['current_score'],
                    add_score=row['add_score'],
                    peak_score=row['peak_score'],
                    alerts_enabled=row['alerts_enabled'],
                    alert_threshold=row['alert_threshold'],
                )
                for row in rows
            ]

    async def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for companies needing alerts based on score changes.

        Returns:
            List of alert notifications
        """
        watchlist = await self.get_watchlist()
        alerts = []

        for entry in watchlist:
            if not entry.alerts_enabled:
                continue

            # Recalculate current score
            current_score = await self.engine.calculate_ma_score(
                entry.company_id,
                include_acquirers=False,
            )

            if not current_score:
                continue

            # Check if alert needed
            if entry.should_alert(current_score.overall_score):
                alerts.append({
                    'company_id': entry.company_id,
                    'company_name': entry.company_name,
                    'previous_score': entry.current_score,
                    'new_score': current_score.overall_score,
                    'change': current_score.overall_score - entry.current_score,
                    'trend': current_score.score_trend,
                    'key_signals': current_score.key_signals,
                })

        return alerts

    async def _is_on_watchlist(self, company_id: str) -> bool:
        """Check if company is on watchlist."""
        async with self.db_pool.acquire() as conn:
            query = "SELECT 1 FROM watchlist WHERE company_id = $1"
            row = await conn.fetchrow(query, company_id)
            return row is not None

    async def _update_watchlist_entry(self, score: MAScore) -> None:
        """Update existing watchlist entry with new score."""
        async with self.db_pool.acquire() as conn:
            query = """
                UPDATE watchlist
                SET
                    current_score = $2,
                    peak_score = GREATEST(peak_score, $2),
                    last_updated = CURRENT_TIMESTAMP
                WHERE company_id = $1
            """
            await conn.execute(query, score.company_id, score.overall_score)
