"""
Abstract base class for data ingesters.

This module defines the interface that all data ingesters must implement,
providing a consistent pattern for fetching, transforming, and publishing data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    """Status of an ingestion operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class IngestionError(Exception):
    """Base exception for ingestion errors."""
    pass


@dataclass
class IngestionResult:
    """Result of a data ingestion operation."""

    source: str
    status: IngestionStatus
    records_fetched: int = 0
    records_transformed: int = 0
    events_published: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def mark_complete(self, status: IngestionStatus = IngestionStatus.SUCCESS):
        """Mark the ingestion as complete."""
        self.end_time = datetime.utcnow()
        self.status = status

    @property
    def duration_seconds(self) -> float:
        """Calculate duration of ingestion in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.utcnow() - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source": self.source,
            "status": self.status.value,
            "records_fetched": self.records_fetched,
            "records_transformed": self.records_transformed,
            "events_published": self.events_published,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 1.0
    requests_per_minute: Optional[int] = None
    requests_per_hour: Optional[int] = None
    burst_size: int = 5

    def __post_init__(self):
        """Validate configuration."""
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt."""
        import random

        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


class DataIngester(ABC):
    """
    Abstract base class for data ingesters.

    All data ingesters must implement this interface to ensure consistent
    behavior across different data sources.
    """

    def __init__(
        self,
        source_name: str,
        event_bus: Any = None,
        rate_limit: Optional[RateLimitConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize the data ingester.

        Args:
            source_name: Name of the data source
            event_bus: Event bus for publishing events
            rate_limit: Rate limiting configuration
            retry_config: Retry configuration
        """
        self.source_name = source_name
        self.event_bus = event_bus
        self.rate_limit = rate_limit or RateLimitConfig()
        self.retry_config = retry_config or RetryConfig()
        self.logger = logging.getLogger(f"{__name__}.{source_name}")

        # Track last fetch time for incremental updates
        self.last_fetch_time: Optional[datetime] = None

    @abstractmethod
    async def fetch_latest(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch the latest data since the last successful fetch.

        Returns:
            List of raw data records

        Raises:
            IngestionError: If fetch fails
        """
        pass

    @abstractmethod
    async def fetch_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical data for a specific date range (backfill).

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of raw data records

        Raises:
            IngestionError: If fetch fails
        """
        pass

    @abstractmethod
    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw data to internal schema.

        Args:
            raw_data: Raw data from source

        Returns:
            Normalized data conforming to internal schema

        Raises:
            IngestionError: If transformation fails
        """
        pass

    async def publish_events(self, data: List[Dict[str, Any]]) -> int:
        """
        Publish transformed data as events to the event bus.

        Args:
            data: List of transformed data records

        Returns:
            Number of events published

        Raises:
            IngestionError: If publishing fails
        """
        if not self.event_bus:
            self.logger.warning(f"No event bus configured for {self.source_name}")
            return 0

        published_count = 0
        for record in data:
            try:
                await self.event_bus.publish(
                    topic=f"ingestion.{self.source_name}",
                    event={
                        "source": self.source_name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": record,
                    }
                )
                published_count += 1
            except Exception as e:
                self.logger.error(f"Failed to publish event: {e}")
                raise IngestionError(f"Event publishing failed: {e}")

        return published_count

    async def ingest_latest(self, **kwargs) -> IngestionResult:
        """
        Execute the complete ingestion pipeline for latest data.

        Returns:
            IngestionResult with operation details
        """
        result = IngestionResult(source=self.source_name, status=IngestionStatus.FAILED)

        try:
            # Fetch raw data
            self.logger.info(f"Fetching latest data from {self.source_name}")
            raw_data = await self.fetch_latest(**kwargs)
            result.records_fetched = len(raw_data)

            if not raw_data:
                self.logger.info(f"No new data from {self.source_name}")
                result.mark_complete(IngestionStatus.SKIPPED)
                return result

            # Transform data
            self.logger.info(f"Transforming {len(raw_data)} records from {self.source_name}")
            transformed_data = []
            for record in raw_data:
                try:
                    transformed = self.transform(record)
                    transformed_data.append(transformed)
                except Exception as e:
                    self.logger.error(f"Transformation error: {e}")
                    # Continue processing other records

            result.records_transformed = len(transformed_data)

            # Publish events
            if transformed_data:
                self.logger.info(f"Publishing {len(transformed_data)} events from {self.source_name}")
                result.events_published = await self.publish_events(transformed_data)

            # Update last fetch time
            self.last_fetch_time = datetime.utcnow()

            # Mark success
            if result.records_transformed > 0:
                result.mark_complete(IngestionStatus.SUCCESS)
            else:
                result.mark_complete(IngestionStatus.PARTIAL)

        except Exception as e:
            self.logger.error(f"Ingestion failed for {self.source_name}: {e}")
            result.error = str(e)
            result.mark_complete(IngestionStatus.FAILED)

        return result

    async def ingest_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> IngestionResult:
        """
        Execute the complete ingestion pipeline for historical data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            IngestionResult with operation details
        """
        result = IngestionResult(source=self.source_name, status=IngestionStatus.FAILED)
        result.metadata["start_date"] = start_date.isoformat()
        result.metadata["end_date"] = end_date.isoformat()

        try:
            # Fetch historical data
            self.logger.info(
                f"Fetching historical data from {self.source_name} "
                f"({start_date} to {end_date})"
            )
            raw_data = await self.fetch_historical(start_date, end_date, **kwargs)
            result.records_fetched = len(raw_data)

            if not raw_data:
                self.logger.info(f"No historical data from {self.source_name}")
                result.mark_complete(IngestionStatus.SKIPPED)
                return result

            # Transform data
            self.logger.info(f"Transforming {len(raw_data)} historical records")
            transformed_data = []
            for record in raw_data:
                try:
                    transformed = self.transform(record)
                    transformed_data.append(transformed)
                except Exception as e:
                    self.logger.error(f"Transformation error: {e}")

            result.records_transformed = len(transformed_data)

            # Publish events
            if transformed_data:
                self.logger.info(f"Publishing {len(transformed_data)} historical events")
                result.events_published = await self.publish_events(transformed_data)

            # Mark success
            if result.records_transformed > 0:
                result.mark_complete(IngestionStatus.SUCCESS)
            else:
                result.mark_complete(IngestionStatus.PARTIAL)

        except Exception as e:
            self.logger.error(f"Historical ingestion failed for {self.source_name}: {e}")
            result.error = str(e)
            result.mark_complete(IngestionStatus.FAILED)

        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the data source.

        Returns:
            Dictionary with health check results
        """
        return {
            "source": self.source_name,
            "status": "unknown",
            "last_fetch": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "message": "Health check not implemented",
        }
