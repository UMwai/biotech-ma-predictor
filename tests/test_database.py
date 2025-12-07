"""
Tests for database layer.

Demonstrates testing patterns for repositories and database operations.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.database import (
    CompanyRepository,
    SignalRepository,
    ScoreRepository,
    ReportRepository,
    AlertRepository,
    init_db,
    close_db,
    get_db_session,
)


@pytest.fixture(scope="session")
async def database():
    """Initialize database for testing."""
    await init_db(echo=False)
    yield
    await close_db()


@pytest.fixture
async def db_session(database):
    """Provide a database session for testing."""
    async with get_db_session() as session:
        yield session
        # Rollback after each test to maintain isolation
        await session.rollback()


class TestCompanyRepository:
    """Test suite for CompanyRepository."""

    @pytest.mark.asyncio
    async def test_create_company(self, db_session):
        """Test creating a company."""
        repo = CompanyRepository(db_session)

        company = await repo.create(
            ticker="TEST",
            name="Test Company",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        assert company.ticker == "TEST"
        assert company.name == "Test Company"
        assert company.market_cap_usd == Decimal("1000000000")
        assert company.id is not None

    @pytest.mark.asyncio
    async def test_get_by_ticker(self, db_session):
        """Test retrieving company by ticker."""
        repo = CompanyRepository(db_session)

        # Create company
        await repo.create(
            ticker="FIND",
            name="Find Me Inc.",
            market_cap_usd=Decimal("500000000"),
            cash_position_usd=Decimal("50000000"),
        )

        # Find company
        found = await repo.get_by_ticker("FIND")

        assert found is not None
        assert found.ticker == "FIND"
        assert found.name == "Find Me Inc."

    @pytest.mark.asyncio
    async def test_search_companies(self, db_session):
        """Test searching companies with filters."""
        repo = CompanyRepository(db_session)

        # Create test companies
        await repo.create(
            ticker="ONCO1",
            name="Oncology One",
            market_cap_usd=Decimal("2000000000"),
            cash_position_usd=Decimal("200000000"),
            therapeutic_areas=["oncology"],
        )

        await repo.create(
            ticker="ONCO2",
            name="Oncology Two",
            market_cap_usd=Decimal("500000000"),
            cash_position_usd=Decimal("50000000"),
            therapeutic_areas=["oncology"],
        )

        # Search
        results = await repo.search(
            therapeutic_areas=["oncology"],
            min_market_cap=1000000000,
        )

        assert len(results) >= 1
        assert all("oncology" in c.therapeutic_areas for c in results)
        assert all(c.market_cap_usd >= 1000000000 for c in results)

    @pytest.mark.asyncio
    async def test_update_company(self, db_session):
        """Test updating company attributes."""
        repo = CompanyRepository(db_session)

        # Create company
        company = await repo.create(
            ticker="UPD",
            name="Update Me",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Update
        updated = await repo.update(
            company.id,
            cash_position_usd=Decimal("150000000"),
            employee_count=200,
        )

        assert updated.cash_position_usd == Decimal("150000000")
        assert updated.employee_count == 200

    @pytest.mark.asyncio
    async def test_soft_delete(self, db_session):
        """Test soft deleting a company."""
        repo = CompanyRepository(db_session)

        # Create company
        company = await repo.create(
            ticker="DEL",
            name="Delete Me",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Soft delete
        deleted = await repo.soft_delete(company.id)
        assert deleted is True

        # Should not be findable
        found = await repo.get_by_ticker("DEL")
        assert found is None


class TestSignalRepository:
    """Test suite for SignalRepository."""

    @pytest.mark.asyncio
    async def test_create_signal(self, db_session):
        """Test creating a signal."""
        # Create company first
        company_repo = CompanyRepository(db_session)
        company = await company_repo.create(
            ticker="SIG",
            name="Signal Test",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Create signal
        signal_repo = SignalRepository(db_session)
        signal = await signal_repo.create(
            company_id=company.id,
            signal_type="sec_filing",
            event_date=datetime.utcnow(),
            title="Test Signal",
            severity="high",
        )

        assert signal.company_id == company.id
        assert signal.signal_type == "sec_filing"
        assert signal.severity == "high"

    @pytest.mark.asyncio
    async def test_get_signals_by_company(self, db_session):
        """Test retrieving signals for a company."""
        # Create company
        company_repo = CompanyRepository(db_session)
        company = await company_repo.create(
            ticker="MULTI",
            name="Multi Signal",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Create multiple signals
        signal_repo = SignalRepository(db_session)
        for i in range(3):
            await signal_repo.create(
                company_id=company.id,
                signal_type="test_signal",
                event_date=datetime.utcnow() - timedelta(days=i),
                title=f"Signal {i}",
                severity="medium",
            )

        # Get signals
        signals = await signal_repo.get_by_company(company.id)

        assert len(signals) >= 3

    @pytest.mark.asyncio
    async def test_get_signal_counts(self, db_session):
        """Test getting signal counts by type."""
        # Create company
        company_repo = CompanyRepository(db_session)
        company = await company_repo.create(
            ticker="COUNT",
            name="Count Signals",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Create signals of different types
        signal_repo = SignalRepository(db_session)
        await signal_repo.create(
            company_id=company.id,
            signal_type="sec_filing",
            event_date=datetime.utcnow(),
            title="SEC Signal 1",
            severity="high",
        )
        await signal_repo.create(
            company_id=company.id,
            signal_type="sec_filing",
            event_date=datetime.utcnow(),
            title="SEC Signal 2",
            severity="medium",
        )
        await signal_repo.create(
            company_id=company.id,
            signal_type="fda_approval",
            event_date=datetime.utcnow(),
            title="FDA Signal",
            severity="high",
        )

        # Get counts
        counts = await signal_repo.get_count_by_type(company_id=company.id)

        assert counts.get("sec_filing", 0) >= 2
        assert counts.get("fda_approval", 0) >= 1


class TestScoreRepository:
    """Test suite for ScoreRepository."""

    @pytest.mark.asyncio
    async def test_create_score(self, db_session):
        """Test creating an M&A score."""
        # Create company
        company_repo = CompanyRepository(db_session)
        company = await company_repo.create(
            ticker="SCORE",
            name="Score Test",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Create score
        score_repo = ScoreRepository(db_session)
        score = await score_repo.create(
            company_id=company.id,
            total_score=85.5,
            pipeline_score=90.0,
            financial_score=75.0,
        )

        assert score.company_id == company.id
        assert score.total_score == 85.5
        assert score.pipeline_score == 90.0

    @pytest.mark.asyncio
    async def test_get_latest_score(self, db_session):
        """Test getting the latest score."""
        # Create company
        company_repo = CompanyRepository(db_session)
        company = await company_repo.create(
            ticker="LATEST",
            name="Latest Score",
            market_cap_usd=Decimal("1000000000"),
            cash_position_usd=Decimal("100000000"),
        )

        # Create multiple scores
        score_repo = ScoreRepository(db_session)
        await score_repo.create(
            company_id=company.id,
            total_score=75.0,
        )
        latest = await score_repo.create(
            company_id=company.id,
            total_score=85.0,
        )

        # Get latest
        result = await score_repo.get_latest_by_company(company.id)

        assert result.id == latest.id
        assert result.total_score == 85.0

    @pytest.mark.asyncio
    async def test_get_top_scores(self, db_session):
        """Test getting top scores."""
        score_repo = ScoreRepository(db_session)
        company_repo = CompanyRepository(db_session)

        # Create companies with different scores
        for i, score in enumerate([95.0, 85.0, 75.0]):
            company = await company_repo.create(
                ticker=f"TOP{i}",
                name=f"Top Company {i}",
                market_cap_usd=Decimal("1000000000"),
                cash_position_usd=Decimal("100000000"),
            )
            await score_repo.create(
                company_id=company.id,
                total_score=score,
            )

        # Get top scores
        top = await score_repo.get_top_scores(limit=10)

        assert len(top) >= 3
        # Scores should be in descending order
        assert all(top[i].total_score >= top[i+1].total_score
                   for i in range(len(top)-1))


class TestReportRepository:
    """Test suite for ReportRepository."""

    @pytest.mark.asyncio
    async def test_create_report(self, db_session):
        """Test creating a report."""
        repo = ReportRepository(db_session)

        report = await repo.create(
            report_type="daily_digest",
            title="Test Daily Digest",
            report_date=datetime.utcnow(),
            format="pdf",
        )

        assert report.report_type == "daily_digest"
        assert report.title == "Test Daily Digest"
        assert report.format == "pdf"

    @pytest.mark.asyncio
    async def test_get_reports_by_type(self, db_session):
        """Test retrieving reports by type."""
        repo = ReportRepository(db_session)

        # Create multiple reports
        for i in range(3):
            await repo.create(
                report_type="daily_digest",
                title=f"Daily Digest {i}",
                report_date=datetime.utcnow() - timedelta(days=i),
            )

        # Get reports
        reports = await repo.get_by_type("daily_digest")

        assert len(reports) >= 3

    @pytest.mark.asyncio
    async def test_update_delivery_status(self, db_session):
        """Test updating report delivery status."""
        repo = ReportRepository(db_session)

        # Create report
        report = await repo.create(
            report_type="weekly_summary",
            title="Test Report",
            report_date=datetime.utcnow(),
        )

        # Update status
        updated = await repo.update_delivery_status(
            report.id,
            status="sent",
            sent_at=datetime.utcnow(),
        )

        assert updated.delivery_status == "sent"
        assert updated.sent_at is not None


class TestAlertRepository:
    """Test suite for AlertRepository."""

    @pytest.mark.asyncio
    async def test_create_alert(self, db_session):
        """Test creating an alert."""
        repo = AlertRepository(db_session)

        alert = await repo.create_alert(
            name="Test Alert",
            alert_type="score_threshold",
            condition={"threshold": 80},
        )

        assert alert.name == "Test Alert"
        assert alert.alert_type == "score_threshold"
        assert alert.is_active is True

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, db_session):
        """Test retrieving active alerts."""
        repo = AlertRepository(db_session)

        # Create active alert
        await repo.create_alert(
            name="Active Alert",
            alert_type="score_threshold",
            condition={"threshold": 80},
            is_active=True,
        )

        # Create inactive alert
        await repo.create_alert(
            name="Inactive Alert",
            alert_type="score_change",
            condition={"change": 10},
            is_active=False,
        )

        # Get active alerts
        active = await repo.get_active_alerts()

        assert len(active) >= 1
        assert all(a.is_active for a in active)

    @pytest.mark.asyncio
    async def test_create_webhook(self, db_session):
        """Test creating a webhook."""
        repo = AlertRepository(db_session)

        webhook = await repo.create_webhook(
            name="Test Webhook",
            url="https://api.example.com/webhook",
            event_types=["score_update", "new_signal"],
        )

        assert webhook.name == "Test Webhook"
        assert webhook.url == "https://api.example.com/webhook"
        assert "score_update" in webhook.event_types

    @pytest.mark.asyncio
    async def test_update_webhook_status(self, db_session):
        """Test updating webhook status."""
        repo = AlertRepository(db_session)

        # Create webhook
        webhook = await repo.create_webhook(
            name="Status Test",
            url="https://api.example.com/webhook",
            event_types=["score_update"],
        )

        # Update success
        updated = await repo.update_webhook_status(
            webhook.id,
            success=True,
        )

        assert updated.success_count == 1
        assert updated.failure_count == 0

        # Update failure
        updated = await repo.update_webhook_status(
            webhook.id,
            success=False,
            error="Connection timeout",
        )

        assert updated.success_count == 1
        assert updated.failure_count == 1
        assert updated.last_error == "Connection timeout"
