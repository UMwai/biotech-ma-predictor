"""
Abstract event bus interface.

Defines the contract for event bus implementations to support
pluggable messaging backends.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional
import logging

from .schemas import BaseEvent

logger = logging.getLogger(__name__)


class EventBus(ABC):
    """
    Abstract event bus interface for publish/subscribe messaging.

    Implementations must provide methods for publishing events,
    subscribing to topics, and lifecycle management.
    """

    def __init__(self, connection_string: str):
        """
        Initialize event bus.

        Args:
            connection_string: Connection string for the message broker
        """
        self.connection_string = connection_string
        self._is_running = False

    @abstractmethod
    async def publish(self, event: BaseEvent, topic: Optional[str] = None) -> None:
        """
        Publish an event to a topic.

        Args:
            event: The event to publish
            topic: Optional topic override. If not provided, uses event.event_type

        Raises:
            Exception: If publishing fails
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[BaseEvent], None],
        queue_name: Optional[str] = None
    ) -> None:
        """
        Subscribe to events on a topic.

        Args:
            topic: Topic pattern to subscribe to (supports wildcards)
            handler: Async callback function to handle events
            queue_name: Optional queue name for the subscription

        Raises:
            Exception: If subscription fails
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        Start the event bus and establish connections.

        This should:
        - Establish connection to message broker
        - Set up exchanges and queues
        - Start consuming messages

        Raises:
            Exception: If startup fails
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the event bus and clean up resources.

        This should:
        - Stop consuming messages
        - Close connections
        - Clean up resources
        """
        pass

    @property
    def is_running(self) -> bool:
        """Check if the event bus is currently running."""
        return self._is_running

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
