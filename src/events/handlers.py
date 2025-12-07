"""
Event handlers for processing events in the biotech M&A predictor system.

Handlers react to events and trigger appropriate actions:
- Signal aggregation
- Score recalculation
- Alert generation
- Report triggering
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from .schemas import (
    BaseEvent,
    ClinicalTrialSignalEvent,
    PatentCliffEvent,
    InsiderActivityEvent,
    HiringSignalEvent,
    MACandidateEvent,
    ReportGeneratedEvent,
)

logger = logging.getLogger(__name__)


class BaseEventHandler(ABC):
    """
    Base class for event handlers.

    Provides common functionality and error handling.
    """

    def __init__(self, name: Optional[str] = None):
        """
        Initialize the event handler.

        Args:
            name: Optional name for the handler (for logging)
        """
        self.name = name or self.__class__.__name__
        self._processed_count = 0
        self._error_count = 0

    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle an event.

        Args:
            event: Event to process

        Raises:
            Exception: If handling fails
        """
        pass

    async def __call__(self, event: BaseEvent) -> None:
        """
        Call the handler (makes it callable).

        Wraps handle() with error tracking.
        """
        try:
            logger.debug(f"{self.name}: Processing event {event.event_type}")
            await self.handle(event)
            self._processed_count += 1
            logger.debug(f"{self.name}: Successfully processed event")
        except Exception as e:
            self._error_count += 1
            logger.error(
                f"{self.name}: Error processing event: {e}",
                exc_info=True
            )
            raise

    def get_stats(self) -> Dict[str, int]:
        """Get handler statistics."""
        return {
            'processed': self._processed_count,
            'errors': self._error_count
        }


class SignalAggregatorHandler(BaseEventHandler):
    """
    Aggregates incoming signals for companies.

    Collects all signal events and stores them for analysis.
    This handler typically writes to a database or cache.
    """

    SIGNAL_EVENT_TYPES = [
        ClinicalTrialSignalEvent,
        PatentCliffEvent,
        InsiderActivityEvent,
        HiringSignalEvent,
    ]

    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        aggregation_window_hours: int = 24
    ):
        """
        Initialize signal aggregator.

        Args:
            storage_backend: Backend for storing signals (e.g., database client)
            aggregation_window_hours: Hours to keep signals in memory
        """
        super().__init__()
        self.storage_backend = storage_backend
        self.aggregation_window = timedelta(hours=aggregation_window_hours)
        self._signal_cache: Dict[str, List[BaseEvent]] = {}

    async def handle(self, event: BaseEvent) -> None:
        """
        Aggregate a signal event.

        Args:
            event: Signal event to aggregate
        """
        # Only process signal events
        if not self._is_signal_event(event):
            logger.debug(f"Ignoring non-signal event: {event.event_type}")
            return

        # Extract company ID
        company_id = self._get_company_id(event)
        if not company_id:
            logger.warning(f"Signal event missing company_id: {event.event_type}")
            return

        logger.info(
            f"Aggregating {event.event_type} signal for company {company_id}"
        )

        # Store in cache
        if company_id not in self._signal_cache:
            self._signal_cache[company_id] = []

        self._signal_cache[company_id].append(event)

        # Clean old signals
        self._clean_old_signals(company_id)

        # Persist to backend if available
        if self.storage_backend:
            await self._persist_signal(company_id, event)

        logger.info(
            f"Company {company_id} now has {len(self._signal_cache[company_id])} "
            f"signals in window"
        )

    def _is_signal_event(self, event: BaseEvent) -> bool:
        """Check if event is a signal event."""
        return any(isinstance(event, cls) for cls in self.SIGNAL_EVENT_TYPES)

    def _get_company_id(self, event: BaseEvent) -> Optional[str]:
        """Extract company ID from event."""
        if hasattr(event, 'company_id'):
            return event.company_id
        return None

    def _clean_old_signals(self, company_id: str) -> None:
        """Remove signals older than the aggregation window."""
        if company_id not in self._signal_cache:
            return

        cutoff_time = datetime.utcnow() - self.aggregation_window
        self._signal_cache[company_id] = [
            signal for signal in self._signal_cache[company_id]
            if signal.timestamp > cutoff_time
        ]

    async def _persist_signal(self, company_id: str, event: BaseEvent) -> None:
        """
        Persist signal to storage backend.

        This is a placeholder - implement based on your storage backend.
        """
        try:
            # Example: await self.storage_backend.store_signal(company_id, event)
            logger.debug(f"Persisted signal for company {company_id}")
        except Exception as e:
            logger.error(f"Failed to persist signal: {e}", exc_info=True)

    def get_company_signals(
        self,
        company_id: str,
        event_type: Optional[str] = None
    ) -> List[BaseEvent]:
        """
        Get aggregated signals for a company.

        Args:
            company_id: Company ID
            event_type: Optional filter by event type

        Returns:
            List of signals
        """
        signals = self._signal_cache.get(company_id, [])

        if event_type:
            signals = [s for s in signals if s.event_type == event_type]

        return signals


class ScoringTriggerHandler(BaseEventHandler):
    """
    Triggers re-scoring when significant signals are received.

    Monitors signal events and triggers the scoring engine
    to recalculate M&A likelihood scores.
    """

    def __init__(
        self,
        scoring_service: Optional[Any] = None,
        min_signals_for_rescore: int = 3,
        rescore_cooldown_hours: int = 1
    ):
        """
        Initialize scoring trigger handler.

        Args:
            scoring_service: Service to trigger for re-scoring
            min_signals_for_rescore: Minimum signals to trigger re-score
            rescore_cooldown_hours: Hours to wait between re-scores
        """
        super().__init__()
        self.scoring_service = scoring_service
        self.min_signals_for_rescore = min_signals_for_rescore
        self.rescore_cooldown = timedelta(hours=rescore_cooldown_hours)
        self._last_rescore: Dict[str, datetime] = {}
        self._signal_counts: Dict[str, int] = {}

    async def handle(self, event: BaseEvent) -> None:
        """
        Process event and trigger re-scoring if needed.

        Args:
            event: Event to process
        """
        # Extract company ID
        company_id = self._get_company_id(event)
        if not company_id:
            return

        # Increment signal count
        self._signal_counts[company_id] = self._signal_counts.get(company_id, 0) + 1

        # Check if we should trigger re-scoring
        if self._should_trigger_rescore(company_id, event):
            logger.info(f"Triggering re-score for company {company_id}")
            await self._trigger_rescore(company_id)

            # Reset counter and update last rescore time
            self._signal_counts[company_id] = 0
            self._last_rescore[company_id] = datetime.utcnow()

    def _get_company_id(self, event: BaseEvent) -> Optional[str]:
        """Extract company ID from event."""
        if hasattr(event, 'company_id'):
            return event.company_id
        return None

    def _should_trigger_rescore(self, company_id: str, event: BaseEvent) -> bool:
        """
        Determine if re-scoring should be triggered.

        Args:
            company_id: Company ID
            event: Event that triggered check

        Returns:
            True if re-scoring should be triggered
        """
        # Check cooldown period
        if company_id in self._last_rescore:
            time_since_last = datetime.utcnow() - self._last_rescore[company_id]
            if time_since_last < self.rescore_cooldown:
                logger.debug(
                    f"Skipping re-score for {company_id} - in cooldown period"
                )
                return False

        # Check signal threshold
        signal_count = self._signal_counts.get(company_id, 0)
        if signal_count < self.min_signals_for_rescore:
            logger.debug(
                f"Signal count {signal_count} below threshold "
                f"{self.min_signals_for_rescore} for {company_id}"
            )
            return False

        # Always trigger for high-impact events
        high_impact_types = [
            'patent_cliff',
            'clinical_trial_signal'  # Phase transitions
        ]
        if event.event_type in high_impact_types:
            logger.info(f"High-impact event detected: {event.event_type}")
            return True

        return True

    async def _trigger_rescore(self, company_id: str) -> None:
        """
        Trigger the scoring service to re-score a company.

        Args:
            company_id: Company to re-score
        """
        try:
            if self.scoring_service:
                # Example: await self.scoring_service.score_company(company_id)
                logger.info(f"Triggered re-score for company {company_id}")
            else:
                logger.warning("No scoring service configured")
        except Exception as e:
            logger.error(f"Failed to trigger re-score: {e}", exc_info=True)


class AlertHandler(BaseEventHandler):
    """
    Monitors M&A candidate events and triggers alerts.

    Sends notifications when:
    - New high-tier candidates are identified
    - Scores cross critical thresholds
    - Significant score changes occur
    """

    def __init__(
        self,
        notification_service: Optional[Any] = None,
        tier_1_threshold: float = 80.0,
        score_change_threshold: float = 15.0
    ):
        """
        Initialize alert handler.

        Args:
            notification_service: Service for sending notifications
            tier_1_threshold: Score threshold for Tier 1 alerts
            score_change_threshold: Minimum score change for alerts
        """
        super().__init__()
        self.notification_service = notification_service
        self.tier_1_threshold = tier_1_threshold
        self.score_change_threshold = score_change_threshold

    async def handle(self, event: BaseEvent) -> None:
        """
        Process M&A candidate events and send alerts.

        Args:
            event: Event to process
        """
        # Only process MA candidate events
        if not isinstance(event, MACandidateEvent):
            return

        alerts = []

        # Check for Tier 1 candidate
        if event.overall_score >= self.tier_1_threshold:
            alerts.append(
                self._create_tier_1_alert(event)
            )

        # Check for significant score change
        if event.score_change and abs(event.score_change) >= self.score_change_threshold:
            alerts.append(
                self._create_score_change_alert(event)
            )

        # Check for new high-tier candidate
        if event.tier == 'tier_1' and (not event.previous_score or event.previous_score < 60):
            alerts.append(
                self._create_new_candidate_alert(event)
            )

        # Send alerts
        for alert in alerts:
            await self._send_alert(alert)

    def _create_tier_1_alert(self, event: MACandidateEvent) -> Dict[str, Any]:
        """Create alert for Tier 1 candidate."""
        return {
            'type': 'tier_1_candidate',
            'severity': 'high',
            'company_id': event.company_id,
            'company_name': event.company_name,
            'score': event.overall_score,
            'message': (
                f"{event.company_name} is a Tier 1 M&A candidate "
                f"with score {event.overall_score:.1f}"
            ),
            'details': {
                'reasoning': event.reasoning,
                'key_signals': event.key_signals,
                'risk_factors': event.risk_factors
            }
        }

    def _create_score_change_alert(self, event: MACandidateEvent) -> Dict[str, Any]:
        """Create alert for significant score change."""
        direction = "increased" if event.score_change > 0 else "decreased"
        return {
            'type': 'score_change',
            'severity': 'medium',
            'company_id': event.company_id,
            'company_name': event.company_name,
            'score': event.overall_score,
            'score_change': event.score_change,
            'message': (
                f"{event.company_name} score {direction} by "
                f"{abs(event.score_change):.1f} points to {event.overall_score:.1f}"
            ),
            'details': {
                'previous_score': event.previous_score,
                'current_score': event.overall_score,
                'key_signals': event.key_signals
            }
        }

    def _create_new_candidate_alert(self, event: MACandidateEvent) -> Dict[str, Any]:
        """Create alert for new high-tier candidate."""
        return {
            'type': 'new_candidate',
            'severity': 'high',
            'company_id': event.company_id,
            'company_name': event.company_name,
            'score': event.overall_score,
            'message': (
                f"New Tier 1 candidate identified: {event.company_name} "
                f"(score: {event.overall_score:.1f})"
            ),
            'details': {
                'reasoning': event.reasoning,
                'key_signals': event.key_signals
            }
        }

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """
        Send an alert notification.

        Args:
            alert: Alert details
        """
        try:
            logger.info(f"Alert: {alert['message']}")

            if self.notification_service:
                # Example: await self.notification_service.send(alert)
                logger.info("Alert sent via notification service")
            else:
                logger.warning("No notification service configured")

        except Exception as e:
            logger.error(f"Failed to send alert: {e}", exc_info=True)


class ReportTriggerHandler(BaseEventHandler):
    """
    Triggers report generation based on events and schedules.

    Monitors events and triggers appropriate report generation.
    """

    def __init__(
        self,
        report_service: Optional[Any] = None,
        auto_generate_on_tier_1: bool = True
    ):
        """
        Initialize report trigger handler.

        Args:
            report_service: Service for generating reports
            auto_generate_on_tier_1: Auto-generate reports for Tier 1 candidates
        """
        super().__init__()
        self.report_service = report_service
        self.auto_generate_on_tier_1 = auto_generate_on_tier_1

    async def handle(self, event: BaseEvent) -> None:
        """
        Process events and trigger reports.

        Args:
            event: Event to process
        """
        # Generate candidate profile for Tier 1 candidates
        if isinstance(event, MACandidateEvent):
            if event.tier == 'tier_1' and self.auto_generate_on_tier_1:
                await self._generate_candidate_profile(event)

        # Log report generation events
        elif isinstance(event, ReportGeneratedEvent):
            logger.info(
                f"Report generated: {event.report_type} - {event.report_title}"
            )

    async def _generate_candidate_profile(self, event: MACandidateEvent) -> None:
        """
        Generate a candidate profile report.

        Args:
            event: M&A candidate event
        """
        try:
            logger.info(
                f"Triggering candidate profile generation for {event.company_name}"
            )

            if self.report_service:
                # Example: await self.report_service.generate_profile(event.company_id)
                logger.info("Candidate profile generation triggered")
            else:
                logger.warning("No report service configured")

        except Exception as e:
            logger.error(
                f"Failed to trigger candidate profile generation: {e}",
                exc_info=True
            )

    async def trigger_scheduled_report(
        self,
        report_type: str,
        **kwargs
    ) -> None:
        """
        Manually trigger a scheduled report.

        Args:
            report_type: Type of report to generate
            **kwargs: Additional parameters for report generation
        """
        try:
            logger.info(f"Triggering scheduled report: {report_type}")

            if self.report_service:
                # Example: await self.report_service.generate(report_type, **kwargs)
                logger.info(f"Scheduled report triggered: {report_type}")
            else:
                logger.warning("No report service configured")

        except Exception as e:
            logger.error(
                f"Failed to trigger scheduled report: {e}",
                exc_info=True
            )
