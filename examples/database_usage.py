"""
Example usage of the database layer.

Demonstrates how to use repositories for common operations.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from src.database import (
    AlertRepository,
    CompanyRepository,
    ReportRepository,
    ScoreRepository,
    SignalRepository,
    close_db,
    get_db_session,
    init_db,
)
from src.models.company import DevelopmentPhase, TherapeuticArea


async def example_company_operations():
    """Example company CRUD operations."""
    print("\n=== Company Operations ===\n")

    async with get_db_session() as session:
        repo = CompanyRepository(session)

        # Create a company
        company = await repo.create(
            ticker="BIOT",
            name="BioTech Innovations Inc.",
            market_cap_usd=Decimal("1500000000"),
            cash_position_usd=Decimal("250000000"),
            quarterly_burn_rate_usd=Decimal("30000000"),
            therapeutic_areas=["oncology", "immunology"],
            founded_year=2015,
            employee_count=120,
            is_public=True,
        )
        print(f"Created company: {company.ticker} - {company.name}")
        print(f"  ID: {company.id}")
        print(f"  Market Cap: ${company.market_cap_usd:,.0f}")

        # Get company by ticker
        found = await repo.get_by_ticker("BIOT")
        print(f"\nFound company by ticker: {found.name}")

        # Update company
        updated = await repo.update(
            company.id,
            cash_position_usd=Decimal("300000000"),
            employee_count=150,
        )
        print(f"\nUpdated company: Cash now ${updated.cash_position_usd:,.0f}")

        # Search companies
        results = await repo.search(
            therapeutic_areas=["oncology"],
            min_market_cap=1000000000,
        )
        print(f"\nFound {len(results)} companies in oncology with >$1B market cap")

        # Get cash constrained companies
        constrained = await repo.get_cash_constrained(min_runway_quarters=4.0)
        print(f"\nFound {len(constrained)} cash-constrained companies")

        return company.id


async def example_signal_operations(company_id):
    """Example signal operations."""
    print("\n=== Signal Operations ===\n")

    async with get_db_session() as session:
        repo = SignalRepository(session)

        # Create various signals
        signals = []

        # SEC filing signal
        signal1 = await repo.create(
            company_id=company_id,
            signal_type="sec_filing",
            event_date=datetime.utcnow(),
            title="8-K Filing: Material Agreement Announced",
            severity="high",
            confidence=0.9,
            description="Company filed 8-K reporting material partnership agreement",
            signal_data={
                "filing_type": "8-K",
                "form_url": "https://sec.gov/...",
                "item": "1.01",
            },
            ma_impact_score=7.5,
        )
        signals.append(signal1)
        print(f"Created SEC filing signal: {signal1.title}")

        # FDA approval signal
        signal2 = await repo.create(
            company_id=company_id,
            signal_type="fda_approval",
            event_date=datetime.utcnow() - timedelta(days=3),
            title="FDA Grants Fast Track Designation",
            severity="high",
            confidence=1.0,
            description="Lead drug candidate receives Fast Track designation",
            signal_data={
                "drug_name": "BIOT-123",
                "indication": "Non-small cell lung cancer",
                "designation_type": "fast_track",
            },
            ma_impact_score=8.0,
        )
        signals.append(signal2)
        print(f"Created FDA signal: {signal2.title}")

        # Insider trading signal
        signal3 = await repo.create(
            company_id=company_id,
            signal_type="insider_trading",
            event_date=datetime.utcnow() - timedelta(days=7),
            title="CEO Purchased 50,000 Shares",
            severity="medium",
            confidence=0.85,
            description="CEO made significant stock purchase",
            signal_data={
                "insider_name": "John Smith",
                "title": "CEO",
                "transaction_type": "purchase",
                "shares": 50000,
                "price_per_share": 15.50,
            },
            ma_impact_score=5.0,
        )
        signals.append(signal3)
        print(f"Created insider trading signal: {signal3.title}")

        # Get signals for company
        company_signals = await repo.get_by_company(
            company_id,
            start_date=datetime.utcnow() - timedelta(days=30),
        )
        print(f"\nTotal signals for company: {len(company_signals)}")

        # Get high severity signals
        high_severity = await repo.get_by_company(
            company_id,
            min_severity="high",
        )
        print(f"High severity signals: {len(high_severity)}")

        # Get signal counts by type
        counts = await repo.get_count_by_type(company_id=company_id)
        print(f"\nSignal counts by type:")
        for signal_type, count in counts.items():
            print(f"  {signal_type}: {count}")


async def example_score_operations(company_id):
    """Example M&A score operations."""
    print("\n=== M&A Score Operations ===\n")

    async with get_db_session() as session:
        repo = ScoreRepository(session)

        # Create initial score
        score1 = await repo.create(
            company_id=company_id,
            total_score=75.5,
            pipeline_score=80.0,
            patent_score=70.0,
            financial_score=65.0,
            insider_score=75.0,
            strategic_fit_score=85.0,
            regulatory_score=78.0,
            key_drivers=[
                "Strong late-stage pipeline",
                "Cash runway < 12 months",
                "Recent insider buying",
            ],
            risk_factors=[
                "Concentrated pipeline risk",
                "Limited commercial infrastructure",
            ],
        )
        print(f"Created M&A score: {score1.total_score}")
        print(f"  Pipeline: {score1.pipeline_score}")
        print(f"  Financial: {score1.financial_score}")

        # Create score from 30 days ago
        await session.execute(
            """
            UPDATE ma_scores
            SET score_date = score_date - interval '30 days'
            WHERE id = :id
            """,
            {"id": score1.id},
        )

        # Create current score (higher)
        score2 = await repo.create(
            company_id=company_id,
            total_score=85.0,
            pipeline_score=90.0,
            patent_score=75.0,
            financial_score=70.0,
            insider_score=85.0,
            strategic_fit_score=90.0,
            regulatory_score=85.0,
            score_change_30d=9.5,
            key_drivers=[
                "Phase 3 data readout positive",
                "Strategic partnership announced",
                "Insider buying accelerated",
            ],
        )
        print(f"\nCreated updated score: {score2.total_score}")
        print(f"  30-day change: +{score2.score_change_30d}")

        # Get latest score
        latest = await repo.get_latest_by_company(company_id)
        print(f"\nLatest score: {latest.total_score}")

        # Get score history
        history = await repo.get_history(company_id, days=90)
        print(f"Score history entries: {len(history)}")

        # Update percentile ranks
        updated = await repo.update_percentile_ranks()
        print(f"\nUpdated percentile ranks for {updated} scores")

        # Get top scores
        top = await repo.get_top_scores(limit=10)
        print(f"\nTop 10 companies by M&A score:")
        for idx, score in enumerate(top, 1):
            print(f"  {idx}. Company {score.company_id}: {score.total_score}")


async def example_report_operations():
    """Example report operations."""
    print("\n=== Report Operations ===\n")

    async with get_db_session() as session:
        repo = ReportRepository(session)

        # Create daily digest report
        report = await repo.create(
            report_type="daily_digest",
            title="Daily M&A Intelligence Digest - 2025-12-07",
            report_date=datetime.utcnow(),
            period_start=datetime.utcnow() - timedelta(days=1),
            period_end=datetime.utcnow(),
            format="pdf",
            s3_bucket="biotech-ma-reports",
            s3_key="reports/daily/2025-12-07-digest.pdf",
            companies_included=["BIOT", "ABCD", "XYZ"],
            key_findings=[
                "3 companies showed significant score increases",
                "New FDA approvals for 2 companies",
                "5 high-severity signals detected",
            ],
            recipients=["analyst@example.com", "pm@example.com"],
        )
        print(f"Created report: {report.title}")
        print(f"  Type: {report.report_type}")
        print(f"  Format: {report.format}")
        print(f"  S3 Key: {report.s3_key}")

        # Update delivery status
        updated = await repo.update_delivery_status(
            report.id,
            status="sent",
            sent_at=datetime.utcnow(),
        )
        print(f"\nReport delivery status: {updated.delivery_status}")

        # Get recent reports
        recent = await repo.get_recent(days=7)
        print(f"\nRecent reports (7 days): {len(recent)}")

        # Get reports by type
        daily_reports = await repo.get_by_type("daily_digest", limit=30)
        print(f"Daily digest reports: {len(daily_reports)}")


async def example_alert_operations(company_id):
    """Example alert and webhook operations."""
    print("\n=== Alert & Webhook Operations ===\n")

    async with get_db_session() as session:
        repo = AlertRepository(session)

        # Create score threshold alert
        alert1 = await repo.create_alert(
            name="High M&A Score Alert",
            alert_type="score_threshold",
            condition={
                "threshold": 80,
                "operator": ">=",
                "metric": "total_score",
            },
            threshold_value=80.0,
            notification_channels=["email", "slack"],
            recipients=["alerts@example.com"],
            is_active=True,
        )
        print(f"Created alert: {alert1.name}")
        print(f"  Type: {alert1.alert_type}")
        print(f"  Threshold: {alert1.threshold_value}")

        # Create score change alert
        alert2 = await repo.create_alert(
            name="Significant Score Change",
            alert_type="score_change",
            condition={
                "change": 10,
                "period": "30d",
                "direction": "increase",
            },
            notification_channels=["email", "webhook"],
            recipients=["pm@example.com"],
            is_active=True,
        )
        print(f"Created alert: {alert2.name}")

        # Get active alerts
        active = await repo.get_active_alerts()
        print(f"\nActive alerts: {len(active)}")

        # Update alert trigger
        triggered = await repo.update_alert_trigger(alert1.id)
        print(f"\nAlert '{triggered.name}' triggered")
        print(f"  Trigger count: {triggered.trigger_count}")
        print(f"  Last triggered: {triggered.last_triggered}")

        # Create webhook
        webhook = await repo.create_webhook(
            name="M&A Intelligence Webhook",
            url="https://api.example.com/webhooks/ma-events",
            event_types=[
                "score_update",
                "new_signal",
                "alert_triggered",
            ],
            company_tickers=["BIOT", "ABCD"],
            min_score=75.0,
            secret="webhook_secret_key_12345",
            is_active=True,
        )
        print(f"\nCreated webhook: {webhook.name}")
        print(f"  URL: {webhook.url}")
        print(f"  Events: {', '.join(webhook.event_types)}")

        # Get active webhooks
        webhooks = await repo.get_active_webhooks(event_type="score_update")
        print(f"\nActive webhooks for 'score_update': {len(webhooks)}")

        # Update webhook status (simulate delivery)
        updated = await repo.update_webhook_status(
            webhook.id,
            success=True,
        )
        print(f"\nWebhook delivery successful")
        print(f"  Success count: {updated.success_count}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Database Layer Usage Examples")
    print("=" * 60)

    # Initialize database
    await init_db(echo=False)

    try:
        # Run examples in sequence
        company_id = await example_company_operations()
        await example_signal_operations(company_id)
        await example_score_operations(company_id)
        await example_report_operations()
        await example_alert_operations(company_id)

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60 + "\n")

    finally:
        # Close database connections
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
