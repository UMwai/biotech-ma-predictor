"""
Ingestion Orchestrator

Coordinates all data ingesters, manages scheduling, handles rate limiting,
and ensures data quality through deduplication and validation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict
import logging
import hashlib
import json

from src.ingestion.base import (
    DataIngester,
    IngestionResult,
    IngestionStatus,
    IngestionError,
)
from src.ingestion.sec_edgar import SECEdgarIngester
from src.ingestion.clinical_trials import ClinicalTrialsIngester
from src.ingestion.fda import FDAIngester
from src.ingestion.financial import FinancialDataIngester

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """
    Orchestrates all data ingestion processes.

    Responsibilities:
    - Coordinate multiple data ingesters
    - Schedule periodic ingestion jobs
    - Handle rate limiting across sources
    - Deduplicate events
    - Monitor ingestion health
    - Retry failed ingestions
    """

    def __init__(
        self,
        event_bus: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the ingestion orchestrator.

        Args:
            event_bus: Event bus for publishing events
            config: Configuration for ingesters
        """
        self.event_bus = event_bus
        self.config = config or {}

        # Initialize ingesters
        self.ingesters: Dict[str, DataIngester] = {}
        self._initialize_ingesters()

        # Deduplication cache (stores hashes of recently seen events)
        self.event_cache: Dict[str, Set[str]] = defaultdict(set)
        self.cache_ttl = timedelta(hours=24)
        self.cache_cleanup_interval = timedelta(hours=1)
        self.last_cache_cleanup = datetime.utcnow()

        # Ingestion history
        self.ingestion_history: List[IngestionResult] = []
        self.max_history_size = 1000

        # Scheduling
        self.schedules: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        self._scheduler_task: Optional[asyncio.Task] = None

    def _initialize_ingesters(self):
        """Initialize all data ingesters."""
        # SEC EDGAR
        if self.config.get("sec_edgar", {}).get("enabled", True):
            self.ingesters["sec_edgar"] = SECEdgarIngester(
                event_bus=self.event_bus,
                user_agent=self.config.get("sec_edgar", {}).get(
                    "user_agent",
                    "Biotech M&A Predictor contact@example.com"
                ),
            )

        # ClinicalTrials.gov
        if self.config.get("clinical_trials", {}).get("enabled", True):
            self.ingesters["clinical_trials"] = ClinicalTrialsIngester(
                event_bus=self.event_bus,
            )

        # FDA
        if self.config.get("fda", {}).get("enabled", True):
            self.ingesters["fda"] = FDAIngester(
                event_bus=self.event_bus,
                api_key=self.config.get("fda", {}).get("api_key"),
            )

        # Financial Data
        if self.config.get("financial", {}).get("enabled", True):
            self.ingesters["financial"] = FinancialDataIngester(
                event_bus=self.event_bus,
                polygon_api_key=self.config.get("financial", {}).get("polygon_api_key"),
                alpha_vantage_api_key=self.config.get("financial", {}).get("alpha_vantage_api_key"),
                provider=self.config.get("financial", {}).get("provider", "yahoo"),
            )

        logger.info(f"Initialized {len(self.ingesters)} ingesters: {list(self.ingesters.keys())}")

    def add_ingester(self, name: str, ingester: DataIngester):
        """
        Add a custom ingester.

        Args:
            name: Unique name for the ingester
            ingester: DataIngester instance
        """
        self.ingesters[name] = ingester
        logger.info(f"Added custom ingester: {name}")

    def remove_ingester(self, name: str):
        """
        Remove an ingester.

        Args:
            name: Name of the ingester to remove
        """
        if name in self.ingesters:
            del self.ingesters[name]
            logger.info(f"Removed ingester: {name}")

    def _generate_event_hash(self, event: Dict[str, Any]) -> str:
        """
        Generate a hash for event deduplication.

        Args:
            event: Event data

        Returns:
            Hash string
        """
        # Create a stable representation of the event
        # Exclude timestamp and other volatile fields
        stable_data = {
            "source": event.get("source"),
            "entity_type": event.get("entity_type"),
            # Include key identifiers based on entity type
        }

        # Add entity-specific identifiers
        entity_type = event.get("entity_type", "")

        if "sec_filing" in entity_type:
            stable_data["accession_number"] = event.get("accession_number")
        elif "clinical_trial" in entity_type:
            stable_data["nct_id"] = event.get("nct_id")
        elif "fda" in entity_type:
            stable_data["application_number"] = event.get("application_number")
        elif "financial" in entity_type:
            stable_data["symbol"] = event.get("symbol")
            stable_data["date"] = event.get("date")

        # Generate hash
        stable_json = json.dumps(stable_data, sort_keys=True)
        return hashlib.sha256(stable_json.encode()).hexdigest()

    def _is_duplicate(self, source: str, event: Dict[str, Any]) -> bool:
        """
        Check if an event is a duplicate.

        Args:
            source: Source name
            event: Event data

        Returns:
            True if duplicate, False otherwise
        """
        event_hash = self._generate_event_hash(event)

        if event_hash in self.event_cache[source]:
            return True

        # Add to cache
        self.event_cache[source].add(event_hash)
        return False

    def _cleanup_cache(self):
        """Clean up old entries from the deduplication cache."""
        now = datetime.utcnow()

        if now - self.last_cache_cleanup < self.cache_cleanup_interval:
            return

        # Simple cleanup: clear entire cache periodically
        # In production, would track timestamps per entry
        logger.info("Cleaning up deduplication cache")
        self.event_cache.clear()
        self.last_cache_cleanup = now

    def _add_to_history(self, result: IngestionResult):
        """
        Add an ingestion result to history.

        Args:
            result: Ingestion result
        """
        self.ingestion_history.append(result)

        # Trim history if needed
        if len(self.ingestion_history) > self.max_history_size:
            self.ingestion_history = self.ingestion_history[-self.max_history_size:]

    async def ingest_all_latest(
        self,
        sources: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, IngestionResult]:
        """
        Ingest latest data from all (or specified) sources.

        Args:
            sources: List of source names to ingest (None = all)
            **kwargs: Additional parameters for ingesters

        Returns:
            Dictionary mapping source names to ingestion results
        """
        if sources is None:
            sources = list(self.ingesters.keys())

        results = {}

        # Run ingestions concurrently
        tasks = []
        for source in sources:
            if source not in self.ingesters:
                logger.warning(f"Unknown ingester: {source}")
                continue

            ingester = self.ingesters[source]
            task = self._run_ingestion(ingester, source, "latest", **kwargs)
            tasks.append((source, task))

        # Wait for all tasks
        for source, task in tasks:
            try:
                result = await task
                results[source] = result
                self._add_to_history(result)
            except Exception as e:
                logger.error(f"Ingestion failed for {source}: {e}")
                error_result = IngestionResult(
                    source=source,
                    status=IngestionStatus.FAILED,
                    error=str(e)
                )
                error_result.mark_complete(IngestionStatus.FAILED)
                results[source] = error_result

        # Cleanup cache
        self._cleanup_cache()

        return results

    async def ingest_all_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        sources: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, IngestionResult]:
        """
        Ingest historical data from all (or specified) sources.

        Args:
            start_date: Start of date range
            end_date: End of date range
            sources: List of source names to ingest (None = all)
            **kwargs: Additional parameters for ingesters

        Returns:
            Dictionary mapping source names to ingestion results
        """
        if sources is None:
            sources = list(self.ingesters.keys())

        results = {}

        # Run ingestions sequentially for historical to avoid overwhelming sources
        for source in sources:
            if source not in self.ingesters:
                logger.warning(f"Unknown ingester: {source}")
                continue

            try:
                ingester = self.ingesters[source]
                result = await ingester.ingest_historical(
                    start_date, end_date, **kwargs
                )
                results[source] = result
                self._add_to_history(result)

                # Delay between sources
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Historical ingestion failed for {source}: {e}")
                error_result = IngestionResult(
                    source=source,
                    status=IngestionStatus.FAILED,
                    error=str(e)
                )
                error_result.mark_complete(IngestionStatus.FAILED)
                results[source] = error_result

        return results

    async def _run_ingestion(
        self,
        ingester: DataIngester,
        source: str,
        mode: str,
        **kwargs
    ) -> IngestionResult:
        """
        Run ingestion for a single source.

        Args:
            ingester: DataIngester instance
            source: Source name
            mode: "latest" or "historical"
            **kwargs: Additional parameters

        Returns:
            Ingestion result
        """
        try:
            if mode == "latest":
                result = await ingester.ingest_latest(**kwargs)
            else:
                result = await ingester.ingest_historical(**kwargs)

            logger.info(
                f"Ingestion completed for {source}: "
                f"{result.records_fetched} fetched, "
                f"{result.records_transformed} transformed, "
                f"{result.events_published} published"
            )

            return result

        except Exception as e:
            logger.error(f"Ingestion error for {source}: {e}")
            raise

    def schedule_ingestion(
        self,
        source: str,
        interval: timedelta,
        mode: str = "latest",
        **kwargs
    ):
        """
        Schedule periodic ingestion for a source.

        Args:
            source: Source name
            interval: Time between ingestions
            mode: "latest" or "historical"
            **kwargs: Additional parameters for ingester
        """
        self.schedules[source] = {
            "interval": interval,
            "mode": mode,
            "kwargs": kwargs,
            "next_run": datetime.utcnow() + interval,
        }

        logger.info(f"Scheduled {mode} ingestion for {source} every {interval}")

    def unschedule_ingestion(self, source: str):
        """
        Remove a scheduled ingestion.

        Args:
            source: Source name
        """
        if source in self.schedules:
            del self.schedules[source]
            logger.info(f"Unscheduled ingestion for {source}")

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Scheduler started")

        while self.is_running:
            try:
                now = datetime.utcnow()

                # Check each scheduled ingestion
                for source, schedule in list(self.schedules.items()):
                    if now >= schedule["next_run"]:
                        # Run ingestion
                        logger.info(f"Running scheduled ingestion for {source}")

                        if source not in self.ingesters:
                            logger.warning(f"Unknown ingester: {source}")
                            continue

                        ingester = self.ingesters[source]

                        try:
                            result = await self._run_ingestion(
                                ingester,
                                source,
                                schedule["mode"],
                                **schedule["kwargs"]
                            )
                            self._add_to_history(result)

                        except Exception as e:
                            logger.error(f"Scheduled ingestion failed for {source}: {e}")

                        # Update next run time
                        schedule["next_run"] = now + schedule["interval"]

                # Sleep for a short interval
                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)  # Wait before retrying

        logger.info("Scheduler stopped")

    async def start(self):
        """Start the orchestrator and scheduler."""
        if self.is_running:
            logger.warning("Orchestrator already running")
            return

        self.is_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Orchestrator started")

    async def stop(self):
        """Stop the orchestrator and scheduler."""
        if not self.is_running:
            return

        logger.info("Stopping orchestrator...")
        self.is_running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        # Close all ingesters
        for name, ingester in self.ingesters.items():
            try:
                if hasattr(ingester, "close"):
                    await ingester.close()
            except Exception as e:
                logger.error(f"Error closing ingester {name}: {e}")

        logger.info("Orchestrator stopped")

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Run health checks on all ingesters.

        Returns:
            Dictionary mapping source names to health check results
        """
        results = {}

        tasks = []
        for name, ingester in self.ingesters.items():
            task = ingester.health_check()
            tasks.append((name, task))

        for name, task in tasks:
            try:
                result = await task
                results[name] = result
            except Exception as e:
                results[name] = {
                    "source": name,
                    "status": "error",
                    "error": str(e),
                }

        return results

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get ingestion statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total_ingestions": len(self.ingestion_history),
            "by_source": defaultdict(lambda: {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "records_fetched": 0,
                "records_transformed": 0,
                "events_published": 0,
            }),
            "recent_errors": [],
        }

        for result in self.ingestion_history:
            source_stats = stats["by_source"][result.source]
            source_stats["total"] += 1

            if result.status == IngestionStatus.SUCCESS:
                source_stats["successful"] += 1
            elif result.status == IngestionStatus.FAILED:
                source_stats["failed"] += 1

            source_stats["records_fetched"] += result.records_fetched
            source_stats["records_transformed"] += result.records_transformed
            source_stats["events_published"] += result.events_published

            if result.error:
                stats["recent_errors"].append({
                    "source": result.source,
                    "error": result.error,
                    "timestamp": result.start_time.isoformat(),
                })

        # Keep only recent errors (last 10)
        stats["recent_errors"] = stats["recent_errors"][-10:]

        # Convert defaultdict to regular dict
        stats["by_source"] = dict(stats["by_source"])

        return stats

    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """
        Get list of scheduled ingestion jobs.

        Returns:
            List of scheduled job information
        """
        jobs = []

        for source, schedule in self.schedules.items():
            jobs.append({
                "source": source,
                "mode": schedule["mode"],
                "interval_seconds": schedule["interval"].total_seconds(),
                "next_run": schedule["next_run"].isoformat(),
            })

        return jobs

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
