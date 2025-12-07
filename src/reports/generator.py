"""
Report Generator - Main orchestrator for generating all report types.

This module coordinates the entire report generation process, from data fetching
to rendering and delivery.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
import asyncpg

from .templates import TemplateManager, ChartGenerator
from .renderers import HTMLRenderer, PDFRenderer
from .delivery import DeliveryManager, DeliveryResult


logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Types of reports that can be generated."""
    DAILY_DIGEST = "daily_digest"
    WEEKLY_WATCHLIST = "weekly_watchlist"
    DEEP_DIVE = "deep_dive"
    ALERT = "alert"


class ReportFormat(str, Enum):
    """Output formats for reports."""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


@dataclass
class ReportContext:
    """Context data for report generation."""
    report_type: ReportType
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    client_config: Optional[Dict[str, Any]] = None


class ReportConfig(BaseModel):
    """Configuration for report generation."""
    client_id: Optional[str] = None
    formats: List[ReportFormat] = Field(default=[ReportFormat.HTML, ReportFormat.PDF])
    delivery_methods: List[str] = Field(default=["email"])
    recipients: List[str] = Field(default=[])
    include_charts: bool = True
    include_raw_data: bool = False
    custom_branding: Optional[Dict[str, str]] = None
    filters: Optional[Dict[str, Any]] = None


class ReportGenerator:
    """
    Main report generator orchestrator.

    Coordinates data fetching, template rendering, format conversion,
    and delivery of all report types.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        template_manager: TemplateManager,
        chart_generator: ChartGenerator,
        html_renderer: HTMLRenderer,
        pdf_renderer: PDFRenderer,
        delivery_manager: DeliveryManager,
    ):
        """
        Initialize the report generator.

        Args:
            db_pool: Database connection pool
            template_manager: Template management system
            chart_generator: Chart and visualization generator
            html_renderer: HTML rendering engine
            pdf_renderer: PDF rendering engine
            delivery_manager: Delivery orchestration manager
        """
        self.db_pool = db_pool
        self.template_manager = template_manager
        self.chart_generator = chart_generator
        self.html_renderer = html_renderer
        self.pdf_renderer = pdf_renderer
        self.delivery_manager = delivery_manager

        logger.info("ReportGenerator initialized")

    async def generate_daily_digest(
        self,
        config: Optional[ReportConfig] = None,
    ) -> Dict[str, Any]:
        """
        Generate daily digest report summarizing past 24h signals.

        Args:
            config: Optional report configuration

        Returns:
            Generated report data with rendered content
        """
        logger.info("Generating daily digest report")

        config = config or ReportConfig()
        now = datetime.utcnow()
        period_start = now - timedelta(hours=24)

        context = ReportContext(
            report_type=ReportType.DAILY_DIGEST,
            generated_at=now,
            period_start=period_start,
            period_end=now,
            client_config=config.custom_branding,
        )

        try:
            # Fetch data for the digest
            context.data = await self._fetch_daily_digest_data(
                period_start,
                now,
                config.filters
            )

            # Generate charts if requested
            if config.include_charts:
                context.data['charts'] = await self._generate_daily_charts(context.data)

            # Add metadata
            context.metadata = {
                'total_signals': len(context.data.get('signals', [])),
                'companies_mentioned': len(context.data.get('companies', [])),
                'high_priority_alerts': len(context.data.get('alerts', [])),
            }

            # Render in requested formats
            rendered = await self._render_report(context, config.formats)

            # Deliver if needed
            if config.delivery_methods:
                delivery_results = await self.delivery_manager.deliver_report(
                    rendered,
                    config.delivery_methods,
                    config.recipients,
                    metadata={
                        'report_type': ReportType.DAILY_DIGEST.value,
                        'period': f"{period_start.date()} to {now.date()}",
                    }
                )
                rendered['delivery_results'] = [r.dict() for r in delivery_results]

            logger.info(
                f"Daily digest generated successfully: "
                f"{context.metadata['total_signals']} signals"
            )

            return rendered

        except Exception as e:
            logger.error(f"Error generating daily digest: {e}", exc_info=True)
            raise

    async def generate_weekly_watchlist(
        self,
        config: Optional[ReportConfig] = None,
    ) -> Dict[str, Any]:
        """
        Generate weekly watchlist of ranked M&A candidates.

        Args:
            config: Optional report configuration

        Returns:
            Generated report data with rendered content
        """
        logger.info("Generating weekly watchlist report")

        config = config or ReportConfig()
        now = datetime.utcnow()
        period_start = now - timedelta(days=7)

        context = ReportContext(
            report_type=ReportType.WEEKLY_WATCHLIST,
            generated_at=now,
            period_start=period_start,
            period_end=now,
            client_config=config.custom_branding,
        )

        try:
            # Fetch watchlist data
            context.data = await self._fetch_watchlist_data(
                period_start,
                now,
                config.filters
            )

            # Generate charts
            if config.include_charts:
                context.data['charts'] = await self._generate_watchlist_charts(
                    context.data
                )

            # Add metadata
            context.metadata = {
                'total_candidates': len(context.data.get('candidates', [])),
                'new_entrants': len(context.data.get('new_candidates', [])),
                'score_improvements': len(context.data.get('improved_scores', [])),
                'average_score': context.data.get('average_score', 0),
            }

            # Render report
            rendered = await self._render_report(context, config.formats)

            # Deliver
            if config.delivery_methods:
                delivery_results = await self.delivery_manager.deliver_report(
                    rendered,
                    config.delivery_methods,
                    config.recipients,
                    metadata={
                        'report_type': ReportType.WEEKLY_WATCHLIST.value,
                        'week_ending': now.date().isoformat(),
                    }
                )
                rendered['delivery_results'] = [r.dict() for r in delivery_results]

            logger.info(
                f"Weekly watchlist generated: "
                f"{context.metadata['total_candidates']} candidates"
            )

            return rendered

        except Exception as e:
            logger.error(f"Error generating weekly watchlist: {e}", exc_info=True)
            raise

    async def generate_deep_dive(
        self,
        company_id: str,
        config: Optional[ReportConfig] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive deep-dive analysis for a single company.

        Args:
            company_id: Company identifier
            config: Optional report configuration

        Returns:
            Generated report data with rendered content
        """
        logger.info(f"Generating deep dive report for company {company_id}")

        config = config or ReportConfig()
        now = datetime.utcnow()

        context = ReportContext(
            report_type=ReportType.DEEP_DIVE,
            generated_at=now,
            period_start=now - timedelta(days=365),  # 1 year lookback
            period_end=now,
            client_config=config.custom_branding,
        )

        try:
            # Fetch comprehensive company data
            context.data = await self._fetch_deep_dive_data(company_id)

            # Generate comprehensive charts
            if config.include_charts:
                context.data['charts'] = await self._generate_deep_dive_charts(
                    context.data
                )

            # Add metadata
            context.metadata = {
                'company_id': company_id,
                'company_name': context.data.get('company', {}).get('name', 'Unknown'),
                'ma_score': context.data.get('current_score', 0),
                'risk_level': context.data.get('risk_level', 'Unknown'),
                'pipeline_drugs': len(context.data.get('pipeline', [])),
            }

            # Render report
            rendered = await self._render_report(context, config.formats)

            # Deliver
            if config.delivery_methods:
                delivery_results = await self.delivery_manager.deliver_report(
                    rendered,
                    config.delivery_methods,
                    config.recipients,
                    metadata={
                        'report_type': ReportType.DEEP_DIVE.value,
                        'company_id': company_id,
                        'company_name': context.metadata['company_name'],
                    }
                )
                rendered['delivery_results'] = [r.dict() for r in delivery_results]

            logger.info(f"Deep dive report generated for {company_id}")

            return rendered

        except Exception as e:
            logger.error(
                f"Error generating deep dive for {company_id}: {e}",
                exc_info=True
            )
            raise

    async def generate_alert_report(
        self,
        company_id: str,
        alert_type: str,
        alert_data: Dict[str, Any],
        config: Optional[ReportConfig] = None,
    ) -> Dict[str, Any]:
        """
        Generate alert report when significant score changes occur.

        Args:
            company_id: Company identifier
            alert_type: Type of alert (score_change, new_signal, etc.)
            alert_data: Alert-specific data
            config: Optional report configuration

        Returns:
            Generated report data with rendered content
        """
        logger.info(
            f"Generating alert report for {company_id}, type: {alert_type}"
        )

        config = config or ReportConfig()
        now = datetime.utcnow()

        context = ReportContext(
            report_type=ReportType.ALERT,
            generated_at=now,
            period_start=now - timedelta(hours=1),
            period_end=now,
            client_config=config.custom_branding,
        )

        try:
            # Fetch alert context
            context.data = await self._fetch_alert_data(
                company_id,
                alert_type,
                alert_data
            )

            # Generate focused charts
            if config.include_charts:
                context.data['charts'] = await self._generate_alert_charts(
                    context.data,
                    alert_type
                )

            # Add metadata
            context.metadata = {
                'company_id': company_id,
                'company_name': context.data.get('company', {}).get('name', 'Unknown'),
                'alert_type': alert_type,
                'severity': alert_data.get('severity', 'medium'),
                'score_change': alert_data.get('score_change', 0),
            }

            # Render report
            rendered = await self._render_report(context, config.formats)

            # Deliver alerts immediately
            if config.delivery_methods:
                delivery_results = await self.delivery_manager.deliver_report(
                    rendered,
                    config.delivery_methods,
                    config.recipients,
                    metadata={
                        'report_type': ReportType.ALERT.value,
                        'alert_type': alert_type,
                        'company_id': company_id,
                        'priority': 'high',
                    }
                )
                rendered['delivery_results'] = [r.dict() for r in delivery_results]

            logger.info(f"Alert report generated for {company_id}")

            return rendered

        except Exception as e:
            logger.error(
                f"Error generating alert report for {company_id}: {e}",
                exc_info=True
            )
            raise

    async def _render_report(
        self,
        context: ReportContext,
        formats: List[ReportFormat],
    ) -> Dict[str, Any]:
        """
        Render report in requested formats.

        Args:
            context: Report context with data
            formats: List of output formats

        Returns:
            Dict with rendered content in each format
        """
        rendered = {
            'report_type': context.report_type.value,
            'generated_at': context.generated_at.isoformat(),
            'metadata': context.metadata,
            'formats': {},
        }

        for fmt in formats:
            try:
                if fmt == ReportFormat.HTML:
                    rendered['formats']['html'] = await self.html_renderer.render(
                        context
                    )
                elif fmt == ReportFormat.PDF:
                    # First render HTML, then convert to PDF
                    html_content = await self.html_renderer.render(context)
                    rendered['formats']['pdf'] = await self.pdf_renderer.render(
                        html_content,
                        context
                    )
                elif fmt == ReportFormat.JSON:
                    rendered['formats']['json'] = context.data

                logger.debug(f"Rendered report in {fmt.value} format")

            except Exception as e:
                logger.error(f"Error rendering {fmt.value} format: {e}")
                rendered['formats'][fmt.value] = None

        return rendered

    async def _fetch_daily_digest_data(
        self,
        period_start: datetime,
        period_end: datetime,
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fetch data for daily digest report."""
        async with self.db_pool.acquire() as conn:
            # Fetch signals from past 24h
            signals = await conn.fetch("""
                SELECT
                    s.signal_id,
                    s.company_id,
                    s.signal_type,
                    s.detected_at,
                    s.significance_score,
                    s.metadata,
                    c.name as company_name,
                    c.ticker
                FROM signals s
                JOIN companies c ON s.company_id = c.company_id
                WHERE s.detected_at >= $1
                  AND s.detected_at < $2
                  AND s.significance_score >= 0.5
                ORDER BY s.significance_score DESC, s.detected_at DESC
                LIMIT 100
            """, period_start, period_end)

            # Fetch companies with score changes
            companies = await conn.fetch("""
                SELECT
                    c.company_id,
                    c.name,
                    c.ticker,
                    s.ma_score,
                    s.score_change_24h,
                    s.risk_level
                FROM companies c
                JOIN ma_scores s ON c.company_id = s.company_id
                WHERE s.score_change_24h != 0
                ORDER BY ABS(s.score_change_24h) DESC
                LIMIT 20
            """)

            # Fetch high-priority alerts
            alerts = await conn.fetch("""
                SELECT
                    a.alert_id,
                    a.company_id,
                    a.alert_type,
                    a.created_at,
                    a.severity,
                    c.name as company_name
                FROM alerts a
                JOIN companies c ON a.company_id = c.company_id
                WHERE a.created_at >= $1
                  AND a.created_at < $2
                  AND a.severity IN ('high', 'critical')
                ORDER BY a.created_at DESC
            """, period_start, period_end)

            return {
                'signals': [dict(s) for s in signals],
                'companies': [dict(c) for c in companies],
                'alerts': [dict(a) for a in alerts],
                'period_start': period_start,
                'period_end': period_end,
            }

    async def _fetch_watchlist_data(
        self,
        period_start: datetime,
        period_end: datetime,
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fetch data for weekly watchlist report."""
        async with self.db_pool.acquire() as conn:
            # Fetch top M&A candidates
            candidates = await conn.fetch("""
                SELECT
                    c.company_id,
                    c.name,
                    c.ticker,
                    c.market_cap,
                    c.therapeutic_areas,
                    s.ma_score,
                    s.score_change_7d,
                    s.pipeline_score,
                    s.financial_score,
                    s.strategic_fit_score,
                    s.risk_level,
                    s.updated_at
                FROM companies c
                JOIN ma_scores s ON c.company_id = s.company_id
                WHERE s.ma_score >= 50
                ORDER BY s.ma_score DESC
                LIMIT 50
            """)

            # Identify new entrants
            new_candidates = await conn.fetch("""
                SELECT company_id, name, ticker, ma_score
                FROM companies c
                JOIN ma_scores s USING (company_id)
                WHERE s.first_qualified_at >= $1
                  AND s.first_qualified_at < $2
                  AND s.ma_score >= 50
                ORDER BY s.ma_score DESC
            """, period_start, period_end)

            # Get score improvements
            improved = await conn.fetch("""
                SELECT
                    company_id,
                    name,
                    ticker,
                    ma_score,
                    score_change_7d
                FROM companies c
                JOIN ma_scores s USING (company_id)
                WHERE s.score_change_7d >= 10
                ORDER BY s.score_change_7d DESC
                LIMIT 10
            """)

            # Calculate average score
            avg_score = await conn.fetchval("""
                SELECT AVG(ma_score)
                FROM ma_scores
                WHERE ma_score >= 50
            """)

            return {
                'candidates': [dict(c) for c in candidates],
                'new_candidates': [dict(c) for c in new_candidates],
                'improved_scores': [dict(c) for c in improved],
                'average_score': float(avg_score) if avg_score else 0,
                'period_start': period_start,
                'period_end': period_end,
            }

    async def _fetch_deep_dive_data(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Fetch comprehensive data for deep-dive report."""
        async with self.db_pool.acquire() as conn:
            # Company overview
            company = await conn.fetchrow("""
                SELECT * FROM companies WHERE company_id = $1
            """, company_id)

            if not company:
                raise ValueError(f"Company {company_id} not found")

            # Current score and components
            score = await conn.fetchrow("""
                SELECT * FROM ma_scores WHERE company_id = $1
            """, company_id)

            # Pipeline
            pipeline = await conn.fetch("""
                SELECT * FROM drug_candidates
                WHERE company_id = $1
                ORDER BY phase DESC, development_stage
            """, company_id)

            # Recent signals
            signals = await conn.fetch("""
                SELECT * FROM signals
                WHERE company_id = $1
                ORDER BY detected_at DESC
                LIMIT 50
            """, company_id)

            # Patent activity
            patents = await conn.fetch("""
                SELECT * FROM patents
                WHERE company_id = $1
                ORDER BY filed_date DESC
                LIMIT 20
            """, company_id)

            # Financial history
            financials = await conn.fetch("""
                SELECT * FROM financial_data
                WHERE company_id = $1
                ORDER BY period_end DESC
                LIMIT 8
            """, company_id)

            # Potential acquirers
            acquirers = await conn.fetch("""
                SELECT * FROM acquirer_matches
                WHERE target_company_id = $1
                ORDER BY match_score DESC
                LIMIT 10
            """, company_id)

            # Score history
            score_history = await conn.fetch("""
                SELECT
                    date,
                    ma_score,
                    pipeline_score,
                    financial_score,
                    strategic_fit_score
                FROM ma_score_history
                WHERE company_id = $1
                  AND date >= CURRENT_DATE - INTERVAL '90 days'
                ORDER BY date ASC
            """, company_id)

            return {
                'company': dict(company),
                'current_score': dict(score) if score else {},
                'pipeline': [dict(p) for p in pipeline],
                'signals': [dict(s) for s in signals],
                'patents': [dict(p) for p in patents],
                'financials': [dict(f) for f in financials],
                'potential_acquirers': [dict(a) for a in acquirers],
                'score_history': [dict(h) for h in score_history],
                'risk_level': score['risk_level'] if score else 'unknown',
            }

    async def _fetch_alert_data(
        self,
        company_id: str,
        alert_type: str,
        alert_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data for alert report."""
        async with self.db_pool.acquire() as conn:
            # Company info
            company = await conn.fetchrow("""
                SELECT * FROM companies WHERE company_id = $1
            """, company_id)

            # Current score
            score = await conn.fetchrow("""
                SELECT * FROM ma_scores WHERE company_id = $1
            """, company_id)

            # Recent score changes
            score_history = await conn.fetch("""
                SELECT date, ma_score
                FROM ma_score_history
                WHERE company_id = $1
                  AND date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY date ASC
            """, company_id)

            # Triggering signal(s)
            trigger_signals = []
            if 'signal_ids' in alert_data:
                trigger_signals = await conn.fetch("""
                    SELECT * FROM signals
                    WHERE signal_id = ANY($1)
                    ORDER BY detected_at DESC
                """, alert_data['signal_ids'])

            return {
                'company': dict(company),
                'current_score': dict(score) if score else {},
                'score_history': [dict(h) for h in score_history],
                'trigger_signals': [dict(s) for s in trigger_signals],
                'alert_data': alert_data,
            }

    async def _generate_daily_charts(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate charts for daily digest."""
        charts = {}

        # Signal distribution by type
        charts['signals_by_type'] = await self.chart_generator.create_bar_chart(
            data=data.get('signals', []),
            x_field='signal_type',
            title='Signals by Type (24h)',
        )

        # Top movers
        charts['top_movers'] = await self.chart_generator.create_bar_chart(
            data=data.get('companies', [])[:10],
            x_field='name',
            y_field='score_change_24h',
            title='Top Score Changes (24h)',
        )

        return charts

    async def _generate_watchlist_charts(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate charts for watchlist report."""
        charts = {}

        # Score distribution
        charts['score_distribution'] = await self.chart_generator.create_histogram(
            data=[c['ma_score'] for c in data.get('candidates', [])],
            title='M&A Score Distribution',
            xlabel='Score',
        )

        # Top candidates
        charts['top_candidates'] = await self.chart_generator.create_bar_chart(
            data=data.get('candidates', [])[:15],
            x_field='ticker',
            y_field='ma_score',
            title='Top 15 M&A Candidates',
        )

        return charts

    async def _generate_deep_dive_charts(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate comprehensive charts for deep-dive report."""
        charts = {}

        # Score history timeline
        charts['score_timeline'] = await self.chart_generator.create_line_chart(
            data=data.get('score_history', []),
            x_field='date',
            y_fields=['ma_score', 'pipeline_score', 'financial_score'],
            title='M&A Score History (90 days)',
        )

        # Score components breakdown
        if data.get('current_score'):
            charts['score_breakdown'] = await self.chart_generator.create_pie_chart(
                data={
                    'Pipeline': data['current_score'].get('pipeline_score', 0),
                    'Financial': data['current_score'].get('financial_score', 0),
                    'Strategic Fit': data['current_score'].get('strategic_fit_score', 0),
                },
                title='Score Components',
            )

        # Pipeline by phase
        charts['pipeline_phases'] = await self.chart_generator.create_bar_chart(
            data=data.get('pipeline', []),
            x_field='phase',
            title='Pipeline by Development Phase',
        )

        return charts

    async def _generate_alert_charts(
        self,
        data: Dict[str, Any],
        alert_type: str,
    ) -> Dict[str, str]:
        """Generate focused charts for alert report."""
        charts = {}

        # Score trend
        if data.get('score_history'):
            charts['score_trend'] = await self.chart_generator.create_line_chart(
                data=data['score_history'],
                x_field='date',
                y_fields=['ma_score'],
                title='Recent Score Trend',
            )

        return charts
