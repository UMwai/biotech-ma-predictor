"""
Main entry point for the Biotech M&A Predictor system.

This module orchestrates all components:
- Event bus connection
- Data ingestion scheduling
- Scoring engine
- Report generation
- API server
"""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Optional

from src.config import Settings
from src.events.bus import EventBus
from src.events.rabbitmq import RabbitMQEventBus
from src.events.handlers import (
    SignalAggregatorHandler,
    ScoringTriggerHandler,
    AlertHandler,
    ReportTriggerHandler,
)
from src.ingestion.orchestrator import IngestionOrchestrator
from src.scoring.engine import MAScorer
from src.reports.generator import ReportGenerator
from src.scheduler import Scheduler

logger = logging.getLogger(__name__)


class BiotechMAPredictor:
    """Main application orchestrator."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.event_bus: Optional[EventBus] = None
        self.ingestion_orchestrator: Optional[IngestionOrchestrator] = None
        self.scorer: Optional[MAScorer] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.scheduler: Optional[Scheduler] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Biotech M&A Predictor...")

        # Initialize event bus
        self.event_bus = RabbitMQEventBus(
            host=self.settings.rabbitmq_host,
            port=self.settings.rabbitmq_port,
            username=self.settings.rabbitmq_user,
            password=self.settings.rabbitmq_password,
            vhost=self.settings.rabbitmq_vhost,
        )
        await self.event_bus.connect()

        # Initialize scoring engine
        self.scorer = MAScorer(
            weights={
                "pipeline": self.settings.weight_pipeline,
                "patent": self.settings.weight_patent,
                "financial": self.settings.weight_financial,
                "insider": self.settings.weight_insider,
                "strategic_fit": self.settings.weight_strategic_fit,
                "regulatory": self.settings.weight_regulatory,
            }
        )

        # Initialize report generator
        self.report_generator = ReportGenerator(
            settings=self.settings,
            event_bus=self.event_bus,
        )

        # Initialize ingestion orchestrator
        self.ingestion_orchestrator = IngestionOrchestrator(
            settings=self.settings,
            event_bus=self.event_bus,
        )

        # Set up event handlers
        await self._setup_event_handlers()

        # Initialize scheduler
        self.scheduler = Scheduler(
            ingestion_orchestrator=self.ingestion_orchestrator,
            report_generator=self.report_generator,
            settings=self.settings,
        )

        logger.info("Biotech M&A Predictor initialized successfully")

    async def _setup_event_handlers(self):
        """Register event handlers with the event bus."""
        # Signal aggregation
        signal_handler = SignalAggregatorHandler(scorer=self.scorer)
        await self.event_bus.subscribe("signals.*", signal_handler.handle)

        # Scoring triggers
        scoring_handler = ScoringTriggerHandler(scorer=self.scorer)
        await self.event_bus.subscribe("signals.*", scoring_handler.handle)

        # Alert checking
        alert_handler = AlertHandler(
            threshold=self.settings.ma_score_alert_threshold,
            change_threshold=self.settings.ma_score_change_alert,
        )
        await self.event_bus.subscribe("scores.updated", alert_handler.handle)

        # Report generation triggers
        report_handler = ReportTriggerHandler(
            report_generator=self.report_generator
        )
        await self.event_bus.subscribe("alerts.triggered", report_handler.handle)

    async def start(self):
        """Start all services."""
        logger.info("Starting Biotech M&A Predictor services...")

        # Start the scheduler
        self.scheduler.start()

        # Start event bus consumption
        await self.event_bus.start_consuming()

        logger.info("All services started. System is now monitoring for signals.")

    async def stop(self):
        """Gracefully stop all services."""
        logger.info("Shutting down Biotech M&A Predictor...")

        # Stop scheduler
        if self.scheduler:
            self.scheduler.stop()

        # Stop event bus
        if self.event_bus:
            await self.event_bus.stop()

        logger.info("Shutdown complete")

    async def run_forever(self):
        """Run the system until shutdown signal."""
        await self.initialize()
        await self.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        await self.stop()

    def request_shutdown(self):
        """Signal the system to shut down."""
        self._shutdown_event.set()


async def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create application
    app = BiotechMAPredictor()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.request_shutdown)

    # Run the application
    try:
        await app.run_forever()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
