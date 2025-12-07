"""
RabbitMQ implementation of the event bus interface.

Provides a robust, production-ready event bus using RabbitMQ with:
- Automatic reconnection
- Dead letter queue handling
- Message acknowledgment
- Exponential backoff retry logic
"""

import asyncio
import json
import logging
from typing import Callable, Optional, Dict, Set
from datetime import datetime
import aio_pika
from aio_pika import connect_robust, ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractQueue

from .bus import EventBus
from .schemas import BaseEvent, MessageEnvelope

logger = logging.getLogger(__name__)


class RabbitMQEventBus(EventBus):
    """
    RabbitMQ implementation of the EventBus interface.

    Features:
    - Automatic reconnection with exponential backoff
    - Dead letter exchange for failed messages
    - Durable exchanges and queues
    - Message persistence
    - Prefetch limits for fair dispatch
    """

    # Constants
    EXCHANGE_NAME = "biotech_ma_events"
    DLX_EXCHANGE_NAME = "biotech_ma_events_dlx"
    MAX_RETRIES = 5
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    PREFETCH_COUNT = 10

    def __init__(
        self,
        connection_string: str,
        exchange_name: Optional[str] = None,
        prefetch_count: int = PREFETCH_COUNT
    ):
        """
        Initialize RabbitMQ event bus.

        Args:
            connection_string: AMQP connection string (e.g., 'amqp://user:pass@host:port/')
            exchange_name: Custom exchange name (default: biotech_ma_events)
            prefetch_count: Number of messages to prefetch per consumer
        """
        super().__init__(connection_string)
        self.exchange_name = exchange_name or self.EXCHANGE_NAME
        self.prefetch_count = prefetch_count

        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._exchange: Optional[aio_pika.Exchange] = None
        self._dlx_exchange: Optional[aio_pika.Exchange] = None
        self._subscriptions: Dict[str, AbstractQueue] = {}
        self._handlers: Dict[str, Callable] = {}
        self._consumer_tags: Set[str] = set()

    async def start(self) -> None:
        """
        Start the RabbitMQ event bus.

        Establishes connection, creates exchanges and queues,
        and sets up dead letter handling.
        """
        if self._is_running:
            logger.warning("Event bus is already running")
            return

        logger.info(f"Starting RabbitMQ event bus with exchange: {self.exchange_name}")

        try:
            # Establish robust connection with auto-reconnect
            self._connection = await connect_robust(
                self.connection_string,
                reconnect_interval=self.INITIAL_RETRY_DELAY,
                fail_fast=False
            )

            # Create channel
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=self.prefetch_count)

            # Create main topic exchange
            self._exchange = await self._channel.declare_exchange(
                self.exchange_name,
                ExchangeType.TOPIC,
                durable=True
            )

            # Create dead letter exchange
            self._dlx_exchange = await self._channel.declare_exchange(
                self.DLX_EXCHANGE_NAME,
                ExchangeType.TOPIC,
                durable=True
            )

            # Create dead letter queue
            dlq = await self._channel.declare_queue(
                f"{self.exchange_name}_dead_letters",
                durable=True
            )
            await dlq.bind(self._dlx_exchange, routing_key="#")

            self._is_running = True
            logger.info("RabbitMQ event bus started successfully")

        except Exception as e:
            logger.error(f"Failed to start RabbitMQ event bus: {e}", exc_info=True)
            await self._cleanup()
            raise

    async def stop(self) -> None:
        """
        Stop the RabbitMQ event bus and clean up resources.
        """
        if not self._is_running:
            logger.warning("Event bus is not running")
            return

        logger.info("Stopping RabbitMQ event bus")
        await self._cleanup()
        self._is_running = False
        logger.info("RabbitMQ event bus stopped")

    async def _cleanup(self) -> None:
        """Clean up all resources."""
        try:
            # Cancel all consumers
            for tag in self._consumer_tags:
                try:
                    if self._channel:
                        await self._channel.cancel(tag)
                except Exception as e:
                    logger.warning(f"Error canceling consumer {tag}: {e}")

            self._consumer_tags.clear()
            self._handlers.clear()
            self._subscriptions.clear()

            # Close channel and connection
            if self._channel and not self._channel.is_closed:
                await self._channel.close()

            if self._connection and not self._connection.is_closed:
                await self._connection.close()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    async def publish(self, event: BaseEvent, topic: Optional[str] = None) -> None:
        """
        Publish an event to RabbitMQ.

        Args:
            event: Event to publish
            topic: Optional routing key override

        Raises:
            RuntimeError: If event bus is not running
            Exception: If publishing fails after retries
        """
        if not self._is_running:
            raise RuntimeError("Event bus is not running. Call start() first.")

        # Wrap event in envelope
        envelope = MessageEnvelope.from_event(event)
        routing_key = topic or event.event_type

        # Serialize to JSON
        message_body = envelope.model_dump_json().encode('utf-8')

        # Create message with persistence
        message = Message(
            message_body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type='application/json',
            timestamp=datetime.utcnow(),
            message_id=envelope.event_id,
            headers={
                'event_type': envelope.event_type,
                'source': envelope.source,
            }
        )

        # Publish with retry logic
        retry_count = 0
        last_exception = None

        while retry_count <= self.MAX_RETRIES:
            try:
                await self._exchange.publish(
                    message,
                    routing_key=routing_key
                )
                logger.debug(
                    f"Published event {envelope.event_id} to topic {routing_key}"
                )
                return

            except Exception as e:
                last_exception = e
                retry_count += 1

                if retry_count <= self.MAX_RETRIES:
                    delay = min(
                        self.INITIAL_RETRY_DELAY * (2 ** (retry_count - 1)),
                        self.MAX_RETRY_DELAY
                    )
                    logger.warning(
                        f"Failed to publish event (attempt {retry_count}/{self.MAX_RETRIES}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Failed to publish event after {self.MAX_RETRIES} retries: {e}",
                        exc_info=True
                    )

        raise last_exception

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[BaseEvent], None],
        queue_name: Optional[str] = None
    ) -> None:
        """
        Subscribe to events on a topic.

        Args:
            topic: Routing key pattern (supports * and # wildcards)
            handler: Async callback to handle events
            queue_name: Optional queue name (auto-generated if not provided)

        Raises:
            RuntimeError: If event bus is not running
        """
        if not self._is_running:
            raise RuntimeError("Event bus is not running. Call start() first.")

        # Generate queue name if not provided
        if not queue_name:
            queue_name = f"{self.exchange_name}.{topic.replace('#', 'all').replace('*', 'any')}"

        logger.info(f"Subscribing to topic '{topic}' with queue '{queue_name}'")

        try:
            # Declare queue with dead letter exchange
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': self.DLX_EXCHANGE_NAME,
                    'x-dead-letter-routing-key': f"dlx.{topic}"
                }
            )

            # Bind queue to exchange with routing key
            await queue.bind(self._exchange, routing_key=topic)

            # Store subscription
            self._subscriptions[topic] = queue
            self._handlers[topic] = handler

            # Start consuming
            consumer_tag = await queue.consume(
                self._create_message_handler(handler, topic)
            )
            self._consumer_tags.add(consumer_tag)

            logger.info(f"Successfully subscribed to topic '{topic}'")

        except Exception as e:
            logger.error(f"Failed to subscribe to topic '{topic}': {e}", exc_info=True)
            raise

    def _create_message_handler(
        self,
        handler: Callable[[BaseEvent], None],
        topic: str
    ) -> Callable:
        """
        Create a message handler wrapper with error handling and retries.

        Args:
            handler: User-provided event handler
            topic: Topic being handled

        Returns:
            Async callback for consuming messages
        """
        async def message_handler(message: aio_pika.IncomingMessage) -> None:
            async with message.process(
                ignore_processed=True,
                requeue=False
            ):
                try:
                    # Parse message envelope
                    body = message.body.decode('utf-8')
                    envelope = MessageEnvelope.model_validate_json(body)

                    logger.debug(
                        f"Received event {envelope.event_id} on topic {topic}"
                    )

                    # Extract event from envelope
                    event = envelope.to_event()

                    # Call handler
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)

                    # Acknowledge message
                    await message.ack()
                    logger.debug(f"Successfully processed event {envelope.event_id}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in message: {e}", exc_info=True)
                    await message.reject(requeue=False)

                except Exception as e:
                    logger.error(
                        f"Error processing message on topic {topic}: {e}",
                        exc_info=True
                    )

                    # Check retry count
                    retry_count = 0
                    if message.headers and 'x-retry-count' in message.headers:
                        retry_count = int(message.headers['x-retry-count'])

                    if retry_count < self.MAX_RETRIES:
                        # Reject and requeue for retry
                        logger.info(
                            f"Requeuing message (retry {retry_count + 1}/{self.MAX_RETRIES})"
                        )

                        # Update retry count
                        headers = dict(message.headers) if message.headers else {}
                        headers['x-retry-count'] = retry_count + 1

                        # Republish with updated headers
                        retry_message = Message(
                            message.body,
                            headers=headers,
                            delivery_mode=message.delivery_mode,
                            content_type=message.content_type
                        )

                        await self._exchange.publish(
                            retry_message,
                            routing_key=topic
                        )
                        await message.ack()
                    else:
                        # Send to dead letter queue
                        logger.error(
                            f"Message failed after {self.MAX_RETRIES} retries, "
                            "sending to dead letter queue"
                        )
                        await message.reject(requeue=False)

        return message_handler

    async def health_check(self) -> bool:
        """
        Check if the event bus is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if not self._is_running:
                return False

            if not self._connection or self._connection.is_closed:
                return False

            if not self._channel or self._channel.is_closed:
                return False

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return False

    async def get_queue_stats(self, queue_name: str) -> Dict:
        """
        Get statistics for a queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Dictionary with queue statistics
        """
        if not self._is_running:
            raise RuntimeError("Event bus is not running")

        try:
            queue = await self._channel.declare_queue(
                queue_name,
                passive=True  # Don't create, just check
            )

            return {
                'name': queue_name,
                'messages': queue.declaration_result.message_count,
                'consumers': queue.declaration_result.consumer_count,
            }

        except Exception as e:
            logger.error(f"Failed to get queue stats for {queue_name}: {e}")
            return {'name': queue_name, 'error': str(e)}
