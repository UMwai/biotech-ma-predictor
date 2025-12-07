"""
Scheduler for continuous data ingestion and report generation.

Uses APScheduler to manage:
- Periodic data refresh from all sources
- Daily digest generation
- Weekly watchlist reports
- Event-driven report triggers
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import Settings

logger = logging.getLogger(__name__)


class Scheduler:
    """Manages scheduled tasks for the M&A predictor system."""

    def __init__(
        self,
        ingestion_orchestrator,
        report_generator,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or Settings()
        self.ingestion_orchestrator = ingestion_orchestrator
        self.report_generator = report_generator
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Configure all scheduled jobs."""

        # Data ingestion - runs every N minutes
        self.scheduler.add_job(
            self._run_data_refresh,
            trigger=IntervalTrigger(
                minutes=self.settings.data_refresh_interval_minutes
            ),
            id="data_refresh",
            name="Periodic Data Refresh",
            replace_existing=True,
        )

        # Daily digest - runs at configured time (default 6 AM)
        self.scheduler.add_job(
            self._generate_daily_digest,
            trigger=CronTrigger.from_crontab(self.settings.daily_digest_cron),
            id="daily_digest",
            name="Daily Digest Generation",
            replace_existing=True,
        )

        # Weekly watchlist - runs at configured time (default Monday 8 AM)
        self.scheduler.add_job(
            self._generate_weekly_watchlist,
            trigger=CronTrigger.from_crontab(self.settings.weekly_report_cron),
            id="weekly_watchlist",
            name="Weekly Watchlist Generation",
            replace_existing=True,
        )

        # SEC filings check - runs every hour during market hours
        self.scheduler.add_job(
            self._check_sec_filings,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="9-18",
                minute="0",
                timezone="America/New_York",
            ),
            id="sec_filings",
            name="SEC Filings Check",
            replace_existing=True,
        )

        # Clinical trials check - runs every 4 hours
        self.scheduler.add_job(
            self._check_clinical_trials,
            trigger=IntervalTrigger(hours=4),
            id="clinical_trials",
            name="Clinical Trials Check",
            replace_existing=True,
        )

        # FDA updates check - runs twice daily
        self.scheduler.add_job(
            self._check_fda_updates,
            trigger=CronTrigger(hour="8,16", minute="30"),
            id="fda_updates",
            name="FDA Updates Check",
            replace_existing=True,
        )

        # Score recalculation - runs daily at midnight
        self.scheduler.add_job(
            self._recalculate_all_scores,
            trigger=CronTrigger(hour="0", minute="0"),
            id="score_recalc",
            name="Daily Score Recalculation",
            replace_existing=True,
        )

        logger.info("Scheduled jobs configured")

    async def _run_data_refresh(self):
        """Execute periodic data refresh from all sources."""
        logger.info("Starting periodic data refresh")
        try:
            await self.ingestion_orchestrator.refresh_all()
            logger.info("Data refresh completed successfully")
        except Exception as e:
            logger.exception(f"Data refresh failed: {e}")

    async def _generate_daily_digest(self):
        """Generate and distribute daily digest report."""
        logger.info("Generating daily digest")
        try:
            report = await self.report_generator.generate_daily_digest()
            await self.report_generator.deliver_report(report)
            logger.info(f"Daily digest generated and delivered: {report.id}")
        except Exception as e:
            logger.exception(f"Daily digest generation failed: {e}")

    async def _generate_weekly_watchlist(self):
        """Generate and distribute weekly watchlist report."""
        logger.info("Generating weekly watchlist")
        try:
            report = await self.report_generator.generate_weekly_watchlist()
            await self.report_generator.deliver_report(report)
            logger.info(f"Weekly watchlist generated and delivered: {report.id}")
        except Exception as e:
            logger.exception(f"Weekly watchlist generation failed: {e}")

    async def _check_sec_filings(self):
        """Check for new SEC filings."""
        logger.info("Checking SEC filings")
        try:
            await self.ingestion_orchestrator.ingesters["sec_edgar"].fetch_latest()
        except Exception as e:
            logger.exception(f"SEC filings check failed: {e}")

    async def _check_clinical_trials(self):
        """Check for clinical trial updates."""
        logger.info("Checking clinical trials")
        try:
            await self.ingestion_orchestrator.ingesters["clinical_trials"].fetch_latest()
        except Exception as e:
            logger.exception(f"Clinical trials check failed: {e}")

    async def _check_fda_updates(self):
        """Check for FDA updates."""
        logger.info("Checking FDA updates")
        try:
            await self.ingestion_orchestrator.ingesters["fda"].fetch_latest()
        except Exception as e:
            logger.exception(f"FDA updates check failed: {e}")

    async def _recalculate_all_scores(self):
        """Recalculate M&A scores for all tracked companies."""
        logger.info("Starting daily score recalculation")
        try:
            # This would be implemented in the scoring engine
            # await self.scorer.recalculate_all()
            logger.info("Score recalculation completed")
        except Exception as e:
            logger.exception(f"Score recalculation failed: {e}")

    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    def get_job_status(self) -> dict:
        """Get status of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return {"jobs": jobs, "running": self.scheduler.running}
