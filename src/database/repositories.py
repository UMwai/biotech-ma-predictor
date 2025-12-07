"""
Data access layer - Repository pattern implementations.

Provides async repositories for all database operations with optimized
queries, filtering, and transaction management.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.database.tables import (
    Alert,
    AcquirerMatch,
    Company,
    DrugCandidate,
    MAScore,
    Report,
    Signal,
    Webhook,
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async database session
        """
        self.session = session


class CompanyRepository(BaseRepository):
    """
    Repository for company data operations.

    Provides CRUD operations, search, filtering, and aggregations
    for company records.
    """

    async def create(
        self,
        ticker: str,
        name: str,
        market_cap_usd: float,
        cash_position_usd: float,
        **kwargs,
    ) -> Company:
        """
        Create a new company record.

        Args:
            ticker: Stock ticker symbol
            name: Company name
            market_cap_usd: Market capitalization
            cash_position_usd: Cash position
            **kwargs: Additional company attributes

        Returns:
            Created Company instance
        """
        company = Company(
            ticker=ticker.upper(),
            name=name,
            market_cap_usd=market_cap_usd,
            cash_position_usd=cash_position_usd,
            **kwargs,
        )
        self.session.add(company)
        await self.session.flush()
        await self.session.refresh(company)
        logger.info(f"Created company: {ticker}")
        return company

    async def get_by_id(
        self,
        company_id: UUID,
        include_pipeline: bool = False,
    ) -> Optional[Company]:
        """
        Get company by ID.

        Args:
            company_id: Company UUID
            include_pipeline: Whether to load drug candidates

        Returns:
            Company instance or None
        """
        query = select(Company).where(
            and_(
                Company.id == company_id,
                Company.deleted_at.is_(None),
            )
        )

        if include_pipeline:
            query = query.options(selectinload(Company.drug_candidates))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_ticker(
        self,
        ticker: str,
        include_pipeline: bool = False,
    ) -> Optional[Company]:
        """
        Get company by ticker symbol.

        Args:
            ticker: Stock ticker
            include_pipeline: Whether to load drug candidates

        Returns:
            Company instance or None
        """
        query = select(Company).where(
            and_(
                Company.ticker == ticker.upper(),
                Company.deleted_at.is_(None),
            )
        )

        if include_pipeline:
            query = query.options(selectinload(Company.drug_candidates))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        include_pipeline: bool = False,
    ) -> List[Company]:
        """
        Get all companies with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_pipeline: Whether to load drug candidates

        Returns:
            List of Company instances
        """
        query = (
            select(Company)
            .where(Company.deleted_at.is_(None))
            .order_by(Company.ticker)
            .offset(skip)
            .limit(limit)
        )

        if include_pipeline:
            query = query.options(selectinload(Company.drug_candidates))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def search(
        self,
        name_pattern: Optional[str] = None,
        therapeutic_areas: Optional[List[str]] = None,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        is_cash_constrained: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Company]:
        """
        Search companies with filters.

        Args:
            name_pattern: Pattern to match in company name
            therapeutic_areas: Filter by therapeutic areas
            min_market_cap: Minimum market cap
            max_market_cap: Maximum market cap
            is_cash_constrained: Filter by cash constraint status
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of matching companies
        """
        filters = [Company.deleted_at.is_(None)]

        if name_pattern:
            filters.append(Company.name.ilike(f"%{name_pattern}%"))

        if therapeutic_areas:
            filters.append(Company.therapeutic_areas.contains(therapeutic_areas))

        if min_market_cap is not None:
            filters.append(Company.market_cap_usd >= min_market_cap)

        if max_market_cap is not None:
            filters.append(Company.market_cap_usd <= max_market_cap)

        if is_cash_constrained is not None:
            filters.append(Company.is_cash_constrained == is_cash_constrained)

        query = (
            select(Company)
            .where(and_(*filters))
            .order_by(Company.market_cap_usd.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        company_id: UUID,
        **kwargs,
    ) -> Optional[Company]:
        """
        Update company attributes.

        Args:
            company_id: Company UUID
            **kwargs: Attributes to update

        Returns:
            Updated Company instance or None
        """
        stmt = (
            update(Company)
            .where(
                and_(
                    Company.id == company_id,
                    Company.deleted_at.is_(None),
                )
            )
            .values(**kwargs, updated_at=datetime.utcnow())
            .returning(Company)
        )

        result = await self.session.execute(stmt)
        company = result.scalar_one_or_none()

        if company:
            logger.info(f"Updated company: {company.ticker}")

        return company

    async def soft_delete(self, company_id: UUID) -> bool:
        """
        Soft delete a company.

        Args:
            company_id: Company UUID

        Returns:
            True if deleted, False if not found
        """
        stmt = (
            update(Company)
            .where(
                and_(
                    Company.id == company_id,
                    Company.deleted_at.is_(None),
                )
            )
            .values(deleted_at=datetime.utcnow())
        )

        result = await self.session.execute(stmt)
        deleted = result.rowcount > 0

        if deleted:
            logger.info(f"Soft deleted company: {company_id}")

        return deleted

    async def get_cash_constrained(
        self,
        min_runway_quarters: float = 4.0,
    ) -> List[Company]:
        """
        Get companies with limited cash runway.

        Args:
            min_runway_quarters: Maximum runway to consider constrained

        Returns:
            List of cash-constrained companies
        """
        query = (
            select(Company)
            .where(
                and_(
                    Company.deleted_at.is_(None),
                    Company.runway_quarters < min_runway_quarters,
                    Company.runway_quarters.is_not(None),
                )
            )
            .order_by(Company.runway_quarters)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics for all companies.

        Returns:
            Dictionary with company statistics
        """
        query = select(
            func.count(Company.id).label("total_companies"),
            func.avg(Company.market_cap_usd).label("avg_market_cap"),
            func.sum(Company.market_cap_usd).label("total_market_cap"),
            func.count(
                func.nullif(Company.is_cash_constrained, False)
            ).label("cash_constrained_count"),
        ).where(Company.deleted_at.is_(None))

        result = await self.session.execute(query)
        row = result.one()

        return {
            "total_companies": row.total_companies or 0,
            "avg_market_cap": float(row.avg_market_cap or 0),
            "total_market_cap": float(row.total_market_cap or 0),
            "cash_constrained_count": row.cash_constrained_count or 0,
        }


class SignalRepository(BaseRepository):
    """
    Repository for signal data operations.

    Manages signal events including creation, querying, and aggregation.
    """

    async def create(
        self,
        company_id: UUID,
        signal_type: str,
        event_date: datetime,
        title: str,
        severity: str = "medium",
        **kwargs,
    ) -> Signal:
        """
        Create a new signal.

        Args:
            company_id: Company UUID
            signal_type: Type of signal
            event_date: When the signal occurred
            title: Signal title
            severity: Signal severity (low, medium, high, critical)
            **kwargs: Additional signal attributes

        Returns:
            Created Signal instance
        """
        signal = Signal(
            company_id=company_id,
            signal_type=signal_type,
            event_date=event_date,
            title=title,
            severity=severity,
            **kwargs,
        )
        self.session.add(signal)
        await self.session.flush()
        await self.session.refresh(signal)
        logger.info(f"Created signal: {signal_type} for company {company_id}")
        return signal

    async def get_by_company(
        self,
        company_id: UUID,
        signal_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Signal]:
        """
        Get signals for a specific company.

        Args:
            company_id: Company UUID
            signal_types: Filter by signal types
            start_date: Filter by start date
            end_date: Filter by end date
            min_severity: Minimum severity level
            limit: Maximum number of signals

        Returns:
            List of Signal instances
        """
        filters = [Signal.company_id == company_id]

        if signal_types:
            filters.append(Signal.signal_type.in_(signal_types))

        if start_date:
            filters.append(Signal.event_date >= start_date)

        if end_date:
            filters.append(Signal.event_date <= end_date)

        if min_severity:
            severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            min_level = severity_order.get(min_severity, 1)
            valid_severities = [
                k for k, v in severity_order.items() if v >= min_level
            ]
            filters.append(Signal.severity.in_(valid_severities))

        query = (
            select(Signal)
            .where(and_(*filters))
            .order_by(Signal.event_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_type(
        self,
        signal_type: str,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Signal]:
        """
        Get signals of a specific type.

        Args:
            signal_type: Type of signal
            start_date: Filter by start date
            limit: Maximum number of signals

        Returns:
            List of Signal instances
        """
        filters = [Signal.signal_type == signal_type]

        if start_date:
            filters.append(Signal.event_date >= start_date)

        query = (
            select(Signal)
            .where(and_(*filters))
            .order_by(Signal.event_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(
        self,
        days: int = 7,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Signal]:
        """
        Get recent signals across all companies.

        Args:
            days: Number of days to look back
            severity: Filter by severity
            limit: Maximum number of signals

        Returns:
            List of recent Signal instances
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        filters = [Signal.event_date >= start_date]

        if severity:
            filters.append(Signal.severity == severity)

        query = (
            select(Signal)
            .where(and_(*filters))
            .order_by(Signal.event_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_count_by_type(
        self,
        company_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get signal counts grouped by type.

        Args:
            company_id: Optional company filter
            start_date: Optional start date filter

        Returns:
            Dictionary mapping signal types to counts
        """
        filters = []

        if company_id:
            filters.append(Signal.company_id == company_id)

        if start_date:
            filters.append(Signal.event_date >= start_date)

        query = select(
            Signal.signal_type,
            func.count(Signal.id).label("count"),
        )

        if filters:
            query = query.where(and_(*filters))

        query = query.group_by(Signal.signal_type)

        result = await self.session.execute(query)
        return {row.signal_type: row.count for row in result.all()}


class ScoreRepository(BaseRepository):
    """
    Repository for M&A score operations.

    Manages score storage, retrieval, and historical tracking.
    """

    async def create(
        self,
        company_id: UUID,
        total_score: float,
        pipeline_score: float = 0.0,
        patent_score: float = 0.0,
        financial_score: float = 0.0,
        insider_score: float = 0.0,
        strategic_fit_score: float = 0.0,
        regulatory_score: float = 0.0,
        **kwargs,
    ) -> MAScore:
        """
        Create a new M&A score.

        Args:
            company_id: Company UUID
            total_score: Overall M&A score
            pipeline_score: Pipeline component score
            patent_score: Patent component score
            financial_score: Financial component score
            insider_score: Insider trading component score
            strategic_fit_score: Strategic fit component score
            regulatory_score: Regulatory component score
            **kwargs: Additional score attributes

        Returns:
            Created MAScore instance
        """
        score = MAScore(
            company_id=company_id,
            total_score=total_score,
            pipeline_score=pipeline_score,
            patent_score=patent_score,
            financial_score=financial_score,
            insider_score=insider_score,
            strategic_fit_score=strategic_fit_score,
            regulatory_score=regulatory_score,
            **kwargs,
        )
        self.session.add(score)
        await self.session.flush()
        await self.session.refresh(score)
        logger.info(f"Created M&A score for company {company_id}: {total_score}")
        return score

    async def get_latest_by_company(
        self,
        company_id: UUID,
    ) -> Optional[MAScore]:
        """
        Get the most recent score for a company.

        Args:
            company_id: Company UUID

        Returns:
            Latest MAScore instance or None
        """
        query = (
            select(MAScore)
            .where(MAScore.company_id == company_id)
            .order_by(MAScore.score_date.desc())
            .limit(1)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_history(
        self,
        company_id: UUID,
        days: int = 90,
        limit: int = 100,
    ) -> List[MAScore]:
        """
        Get score history for a company.

        Args:
            company_id: Company UUID
            days: Number of days to look back
            limit: Maximum number of scores

        Returns:
            List of historical MAScore instances
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(MAScore)
            .where(
                and_(
                    MAScore.company_id == company_id,
                    MAScore.score_date >= start_date,
                )
            )
            .order_by(MAScore.score_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_top_scores(
        self,
        limit: int = 50,
        score_date: Optional[datetime] = None,
    ) -> List[MAScore]:
        """
        Get companies with highest M&A scores.

        Args:
            limit: Maximum number of scores
            score_date: Optional specific date (defaults to latest)

        Returns:
            List of top MAScore instances
        """
        # If no date specified, get latest scores by using a subquery
        if score_date is None:
            # Subquery to get latest score_date for each company
            latest_subq = (
                select(
                    MAScore.company_id,
                    func.max(MAScore.score_date).label("max_date"),
                )
                .group_by(MAScore.company_id)
                .subquery()
            )

            # Join to get full score records
            query = (
                select(MAScore)
                .join(
                    latest_subq,
                    and_(
                        MAScore.company_id == latest_subq.c.company_id,
                        MAScore.score_date == latest_subq.c.max_date,
                    ),
                )
                .order_by(MAScore.total_score.desc())
                .limit(limit)
            )
        else:
            query = (
                select(MAScore)
                .where(MAScore.score_date == score_date)
                .order_by(MAScore.total_score.desc())
                .limit(limit)
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_score_range(
        self,
        min_score: float,
        max_score: float = 100.0,
        limit: int = 100,
    ) -> List[MAScore]:
        """
        Get latest scores within a score range.

        Args:
            min_score: Minimum score threshold
            max_score: Maximum score threshold
            limit: Maximum number of results

        Returns:
            List of MAScore instances
        """
        # Subquery for latest scores
        latest_subq = (
            select(
                MAScore.company_id,
                func.max(MAScore.score_date).label("max_date"),
            )
            .group_by(MAScore.company_id)
            .subquery()
        )

        query = (
            select(MAScore)
            .join(
                latest_subq,
                and_(
                    MAScore.company_id == latest_subq.c.company_id,
                    MAScore.score_date == latest_subq.c.max_date,
                ),
            )
            .where(
                and_(
                    MAScore.total_score >= min_score,
                    MAScore.total_score <= max_score,
                )
            )
            .order_by(MAScore.total_score.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_percentile_ranks(
        self,
        score_date: Optional[datetime] = None,
    ) -> int:
        """
        Calculate and update percentile ranks for scores.

        Args:
            score_date: Date to update ranks for (defaults to today)

        Returns:
            Number of scores updated
        """
        if score_date is None:
            score_date = datetime.utcnow().date()

        # Get all scores for the date
        query = select(MAScore).where(
            func.date(MAScore.score_date) == score_date
        )
        result = await self.session.execute(query)
        scores = list(result.scalars().all())

        if not scores:
            return 0

        # Sort by total score
        scores.sort(key=lambda x: x.total_score)

        # Calculate percentiles
        total = len(scores)
        for idx, score in enumerate(scores):
            percentile = (idx / (total - 1)) * 100 if total > 1 else 50
            score.percentile_rank = round(percentile, 2)

        await self.session.flush()
        logger.info(f"Updated {total} percentile ranks for date {score_date}")
        return total


class ReportRepository(BaseRepository):
    """
    Repository for report operations.

    Manages report metadata, storage references, and retrieval.
    """

    async def create(
        self,
        report_type: str,
        title: str,
        report_date: datetime,
        format: str = "pdf",
        **kwargs,
    ) -> Report:
        """
        Create a new report.

        Args:
            report_type: Type of report
            title: Report title
            report_date: Report generation date
            format: Report format (pdf, html, json)
            **kwargs: Additional report attributes

        Returns:
            Created Report instance
        """
        report = Report(
            report_type=report_type,
            title=title,
            report_date=report_date,
            format=format,
            **kwargs,
        )
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        logger.info(f"Created report: {title} ({report_type})")
        return report

    async def get_by_id(self, report_id: UUID) -> Optional[Report]:
        """
        Get report by ID.

        Args:
            report_id: Report UUID

        Returns:
            Report instance or None
        """
        query = select(Report).where(
            and_(
                Report.id == report_id,
                Report.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_type(
        self,
        report_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Report]:
        """
        Get reports by type.

        Args:
            report_type: Type of report
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of reports

        Returns:
            List of Report instances
        """
        filters = [
            Report.report_type == report_type,
            Report.deleted_at.is_(None),
        ]

        if start_date:
            filters.append(Report.report_date >= start_date)

        if end_date:
            filters.append(Report.report_date <= end_date)

        query = (
            select(Report)
            .where(and_(*filters))
            .order_by(Report.report_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> List[Report]:
        """
        Get recent reports.

        Args:
            days: Number of days to look back
            limit: Maximum number of reports

        Returns:
            List of recent Report instances
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        query = (
            select(Report)
            .where(
                and_(
                    Report.report_date >= start_date,
                    Report.deleted_at.is_(None),
                )
            )
            .order_by(Report.report_date.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_delivery_status(
        self,
        report_id: UUID,
        status: str,
        sent_at: Optional[datetime] = None,
    ) -> Optional[Report]:
        """
        Update report delivery status.

        Args:
            report_id: Report UUID
            status: New delivery status
            sent_at: When the report was sent

        Returns:
            Updated Report instance or None
        """
        values = {"delivery_status": status}
        if sent_at:
            values["sent_at"] = sent_at

        stmt = (
            update(Report)
            .where(
                and_(
                    Report.id == report_id,
                    Report.deleted_at.is_(None),
                )
            )
            .values(**values)
            .returning(Report)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AlertRepository(BaseRepository):
    """
    Repository for alert and webhook operations.

    Manages alert configurations, webhooks, and notification tracking.
    """

    async def create_alert(
        self,
        name: str,
        alert_type: str,
        condition: Dict[str, Any],
        **kwargs,
    ) -> Alert:
        """
        Create a new alert.

        Args:
            name: Alert name
            alert_type: Type of alert
            condition: Alert condition configuration
            **kwargs: Additional alert attributes

        Returns:
            Created Alert instance
        """
        alert = Alert(
            name=name,
            alert_type=alert_type,
            condition=condition,
            **kwargs,
        )
        self.session.add(alert)
        await self.session.flush()
        await self.session.refresh(alert)
        logger.info(f"Created alert: {name} ({alert_type})")
        return alert

    async def get_active_alerts(
        self,
        alert_type: Optional[str] = None,
    ) -> List[Alert]:
        """
        Get all active alerts.

        Args:
            alert_type: Optional filter by alert type

        Returns:
            List of active Alert instances
        """
        filters = [
            Alert.is_active == True,
            Alert.deleted_at.is_(None),
        ]

        if alert_type:
            filters.append(Alert.alert_type == alert_type)

        query = select(Alert).where(and_(*filters))

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_alert_trigger(
        self,
        alert_id: UUID,
    ) -> Optional[Alert]:
        """
        Update alert trigger timestamp and count.

        Args:
            alert_id: Alert UUID

        Returns:
            Updated Alert instance or None
        """
        stmt = (
            update(Alert)
            .where(
                and_(
                    Alert.id == alert_id,
                    Alert.deleted_at.is_(None),
                )
            )
            .values(
                last_triggered=datetime.utcnow(),
                trigger_count=Alert.trigger_count + 1,
            )
            .returning(Alert)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_webhook(
        self,
        name: str,
        url: str,
        event_types: List[str],
        **kwargs,
    ) -> Webhook:
        """
        Create a new webhook.

        Args:
            name: Webhook name
            url: Webhook endpoint URL
            event_types: List of event types to subscribe to
            **kwargs: Additional webhook attributes

        Returns:
            Created Webhook instance
        """
        webhook = Webhook(
            name=name,
            url=url,
            event_types=event_types,
            **kwargs,
        )
        self.session.add(webhook)
        await self.session.flush()
        await self.session.refresh(webhook)
        logger.info(f"Created webhook: {name}")
        return webhook

    async def get_active_webhooks(
        self,
        event_type: Optional[str] = None,
    ) -> List[Webhook]:
        """
        Get all active webhooks.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of active Webhook instances
        """
        filters = [
            Webhook.is_active == True,
            Webhook.deleted_at.is_(None),
        ]

        query = select(Webhook).where(and_(*filters))

        result = await self.session.execute(query)
        webhooks = list(result.scalars().all())

        # Filter by event type if specified
        if event_type:
            webhooks = [
                w for w in webhooks
                if event_type in w.event_types
            ]

        return webhooks

    async def update_webhook_status(
        self,
        webhook_id: UUID,
        success: bool,
        error: Optional[str] = None,
    ) -> Optional[Webhook]:
        """
        Update webhook delivery status.

        Args:
            webhook_id: Webhook UUID
            success: Whether delivery was successful
            error: Optional error message

        Returns:
            Updated Webhook instance or None
        """
        values = {
            "last_triggered": datetime.utcnow(),
        }

        if success:
            values["success_count"] = Webhook.success_count + 1
        else:
            values["failure_count"] = Webhook.failure_count + 1
            if error:
                values["last_error"] = error

        stmt = (
            update(Webhook)
            .where(
                and_(
                    Webhook.id == webhook_id,
                    Webhook.deleted_at.is_(None),
                )
            )
            .values(**values)
            .returning(Webhook)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
