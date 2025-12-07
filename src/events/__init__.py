"""
Event bus integration for biotech M&A predictor system.

This module provides event-driven communication between system components
using RabbitMQ as the message broker.
"""

from .bus import EventBus
from .rabbitmq import RabbitMQEventBus
from .schemas import (
    BaseEvent,
    MessageEnvelope,
    ClinicalTrialSignalEvent,
    PatentCliffEvent,
    InsiderActivityEvent,
    HiringSignalEvent,
    MACandidateEvent,
    ReportGeneratedEvent,
)
from .handlers import (
    SignalAggregatorHandler,
    ScoringTriggerHandler,
    AlertHandler,
    ReportTriggerHandler,
)

__all__ = [
    # Core interfaces
    "EventBus",
    "RabbitMQEventBus",
    # Event schemas
    "BaseEvent",
    "MessageEnvelope",
    "ClinicalTrialSignalEvent",
    "PatentCliffEvent",
    "InsiderActivityEvent",
    "HiringSignalEvent",
    "MACandidateEvent",
    "ReportGeneratedEvent",
    # Event handlers
    "SignalAggregatorHandler",
    "ScoringTriggerHandler",
    "AlertHandler",
    "ReportTriggerHandler",
]
