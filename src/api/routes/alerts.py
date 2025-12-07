"""
Alert and webhook endpoints.

Provides REST API for managing M&A alerts, webhooks,
and notification preferences.
"""

from typing import List, Optional
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_db_session,
    get_pagination,
    PaginationParams,
    verify_api_key,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# Enums
class AlertType(str, Enum):
    """Alert type enumeration."""

    SCORE_THRESHOLD = "score_threshold"
    SCORE_CHANGE = "score_change"
    NEW_SIGNAL = "new_signal"
    WATCHLIST_ADD = "watchlist_add"
    WATCHLIST_REMOVE = "watchlist_remove"
    REPORT_READY = "report_ready"


class AlertChannel(str, Enum):
    """Alert delivery channel."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"


class AlertSeverity(str, Enum):
    """Alert severity level."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# Request/Response Models
class AlertRuleCreate(BaseModel):
    """Create alert rule request."""

    name: str = Field(..., min_length=1, max_length=200, description="Alert rule name")
    description: Optional[str] = Field(None, description="Alert rule description")
    alert_type: AlertType = Field(..., description="Type of alert")
    enabled: bool = Field(default=True, description="Whether alert is enabled")
    channels: List[AlertChannel] = Field(..., description="Delivery channels")
    conditions: dict = Field(..., description="Alert trigger conditions")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "High M&A Score Alert",
                "description": "Alert when company M&A score exceeds 80",
                "alert_type": "score_threshold",
                "enabled": True,
                "channels": ["email", "slack"],
                "conditions": {
                    "score_threshold": 80,
                    "companies": ["WXYZ", "ABCD"],
                },
                "metadata": {
                    "email": "analyst@example.com",
                    "slack_channel": "#ma-alerts",
                },
            }
        }

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v):
        """Validate at least one channel is specified."""
        if not v:
            raise ValueError("At least one alert channel must be specified")
        return v


class AlertRuleUpdate(BaseModel):
    """Update alert rule request."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    channels: Optional[List[AlertChannel]] = None
    conditions: Optional[dict] = None
    metadata: Optional[dict] = None


class AlertRule(BaseModel):
    """Alert rule response."""

    rule_id: str = Field(..., description="Unique rule identifier")
    name: str
    description: Optional[str]
    alert_type: AlertType
    enabled: bool
    channels: List[AlertChannel]
    conditions: dict
    metadata: dict
    created_at: datetime
    updated_at: datetime
    created_by: str = Field(..., description="User who created the rule")
    trigger_count: int = Field(..., description="Number of times triggered")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger time")

    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "alert_rule_001",
                "name": "High M&A Score Alert",
                "description": "Alert when company M&A score exceeds 80",
                "alert_type": "score_threshold",
                "enabled": True,
                "channels": ["email", "slack"],
                "conditions": {"score_threshold": 80},
                "metadata": {"email": "analyst@example.com"},
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "created_by": "user_123",
                "trigger_count": 5,
                "last_triggered": "2025-12-07T14:30:00Z",
            }
        }


class AlertRuleListResponse(BaseModel):
    """Alert rules list response."""

    rules: List[AlertRule]
    total: int
    page: int
    page_size: int


class WebhookCreate(BaseModel):
    """Create webhook request."""

    name: str = Field(..., min_length=1, max_length=200, description="Webhook name")
    url: HttpUrl = Field(..., description="Webhook URL")
    secret: Optional[str] = Field(None, description="Webhook secret for HMAC signing")
    enabled: bool = Field(default=True, description="Whether webhook is enabled")
    event_types: List[AlertType] = Field(..., description="Event types to send")
    headers: dict = Field(default_factory=dict, description="Custom HTTP headers")
    retry_config: dict = Field(
        default_factory=lambda: {"max_retries": 3, "retry_delay_seconds": 60},
        description="Retry configuration",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "M&A Alerts Webhook",
                "url": "https://api.example.com/webhooks/ma-alerts",
                "secret": "webhook_secret_key",
                "enabled": True,
                "event_types": ["score_threshold", "watchlist_add"],
                "headers": {"X-Custom-Header": "value"},
                "retry_config": {"max_retries": 3, "retry_delay_seconds": 60},
            }
        }


class WebhookUpdate(BaseModel):
    """Update webhook request."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    event_types: Optional[List[AlertType]] = None
    headers: Optional[dict] = None
    retry_config: Optional[dict] = None


class Webhook(BaseModel):
    """Webhook response."""

    webhook_id: str = Field(..., description="Unique webhook identifier")
    name: str
    url: str
    enabled: bool
    event_types: List[AlertType]
    headers: dict
    retry_config: dict
    created_at: datetime
    updated_at: datetime
    created_by: str
    delivery_count: int = Field(..., description="Number of deliveries attempted")
    success_count: int = Field(..., description="Number of successful deliveries")
    failure_count: int = Field(..., description="Number of failed deliveries")
    last_delivery: Optional[datetime] = Field(None, description="Last delivery attempt")
    last_success: Optional[datetime] = Field(None, description="Last successful delivery")

    class Config:
        json_schema_extra = {
            "example": {
                "webhook_id": "webhook_001",
                "name": "M&A Alerts Webhook",
                "url": "https://api.example.com/webhooks/ma-alerts",
                "enabled": True,
                "event_types": ["score_threshold", "watchlist_add"],
                "headers": {},
                "retry_config": {"max_retries": 3, "retry_delay_seconds": 60},
                "created_at": "2025-12-01T10:00:00Z",
                "updated_at": "2025-12-01T10:00:00Z",
                "created_by": "user_123",
                "delivery_count": 50,
                "success_count": 48,
                "failure_count": 2,
                "last_delivery": "2025-12-07T14:30:00Z",
                "last_success": "2025-12-07T14:30:00Z",
            }
        }


class WebhookListResponse(BaseModel):
    """Webhooks list response."""

    webhooks: List[Webhook]
    total: int
    page: int
    page_size: int


class AlertHistoryItem(BaseModel):
    """Alert history item."""

    alert_id: str = Field(..., description="Unique alert identifier")
    rule_id: str = Field(..., description="Rule that triggered this alert")
    rule_name: str
    alert_type: AlertType
    severity: AlertSeverity
    triggered_at: datetime
    status: AlertStatus
    message: str = Field(..., description="Alert message")
    details: dict = Field(..., description="Alert details")
    channels_delivered: List[AlertChannel] = Field(..., description="Channels where delivered")
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "alert_20251207_001",
                "rule_id": "alert_rule_001",
                "rule_name": "High M&A Score Alert",
                "alert_type": "score_threshold",
                "severity": "high",
                "triggered_at": "2025-12-07T14:30:00Z",
                "status": "triggered",
                "message": "WXYZ M&A score exceeded threshold of 80 (current: 85.0)",
                "details": {
                    "ticker": "WXYZ",
                    "score": 85.0,
                    "threshold": 80,
                    "change_24h": 5.2,
                },
                "channels_delivered": ["email", "slack"],
                "acknowledged_at": None,
                "acknowledged_by": None,
                "resolved_at": None,
            }
        }


class AlertHistoryResponse(BaseModel):
    """Alert history response."""

    alerts: List[AlertHistoryItem]
    total: int
    page: int
    page_size: int


# Endpoints - Alert Rules
@router.get("/rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by alert type"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    List all alert rules.

    Requires authentication. Returns paginated list of alert rules.
    """
    # TODO: Implement actual database query
    # Mock response
    mock_rules = [
        AlertRule(
            rule_id="alert_rule_001",
            name="High M&A Score Alert",
            description="Alert when company M&A score exceeds 80",
            alert_type=AlertType.SCORE_THRESHOLD,
            enabled=True,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            conditions={"score_threshold": 80},
            metadata={"email": "analyst@example.com"},
            created_at=datetime(2025, 12, 1, 10, 0, 0),
            updated_at=datetime(2025, 12, 1, 10, 0, 0),
            created_by="user_123",
            trigger_count=5,
            last_triggered=datetime(2025, 12, 7, 14, 30, 0),
        ),
    ]

    # Apply filters
    filtered = mock_rules
    if enabled is not None:
        filtered = [r for r in filtered if r.enabled == enabled]
    if alert_type:
        filtered = [r for r in filtered if r.alert_type == alert_type]

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return AlertRuleListResponse(
        rules=page_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/rules", response_model=AlertRule, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule: AlertRuleCreate,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Create a new alert rule.

    Requires authentication. Alert will be active if enabled=True.
    """
    # TODO: Implement actual database insertion
    # Mock response
    rule_id = f"alert_rule_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    return AlertRule(
        rule_id=rule_id,
        name=rule.name,
        description=rule.description,
        alert_type=rule.alert_type,
        enabled=rule.enabled,
        channels=rule.channels,
        conditions=rule.conditions,
        metadata=rule.metadata,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by="user_123",
        trigger_count=0,
        last_triggered=None,
    )


@router.get("/rules/{rule_id}", response_model=AlertRule)
async def get_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Get alert rule by ID.

    Requires authentication.
    """
    # TODO: Implement actual database query
    if rule_id == "alert_rule_001":
        return AlertRule(
            rule_id=rule_id,
            name="High M&A Score Alert",
            description="Alert when company M&A score exceeds 80",
            alert_type=AlertType.SCORE_THRESHOLD,
            enabled=True,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            conditions={"score_threshold": 80},
            metadata={"email": "analyst@example.com"},
            created_at=datetime(2025, 12, 1, 10, 0, 0),
            updated_at=datetime(2025, 12, 1, 10, 0, 0),
            created_by="user_123",
            trigger_count=5,
            last_triggered=datetime(2025, 12, 7, 14, 30, 0),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Alert rule {rule_id} not found",
    )


@router.patch("/rules/{rule_id}", response_model=AlertRule)
async def update_alert_rule(
    rule_id: str,
    update: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Update an alert rule.

    Requires authentication. Only provided fields will be updated.
    """
    # TODO: Implement actual database update
    # Mock response - return updated rule
    return AlertRule(
        rule_id=rule_id,
        name=update.name or "High M&A Score Alert",
        description=update.description,
        alert_type=AlertType.SCORE_THRESHOLD,
        enabled=update.enabled if update.enabled is not None else True,
        channels=update.channels or [AlertChannel.EMAIL],
        conditions=update.conditions or {"score_threshold": 80},
        metadata=update.metadata or {},
        created_at=datetime(2025, 12, 1, 10, 0, 0),
        updated_at=datetime.utcnow(),
        created_by="user_123",
        trigger_count=5,
        last_triggered=datetime(2025, 12, 7, 14, 30, 0),
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Delete an alert rule.

    Requires authentication. Rule will be permanently deleted.
    """
    # TODO: Implement actual database deletion
    return None


# Endpoints - Webhooks
@router.get("/webhooks", response_model=WebhookListResponse)
async def list_webhooks(
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    List all webhooks.

    Requires authentication. Returns paginated list of webhooks.
    """
    # TODO: Implement actual database query
    mock_webhooks = [
        Webhook(
            webhook_id="webhook_001",
            name="M&A Alerts Webhook",
            url="https://api.example.com/webhooks/ma-alerts",
            enabled=True,
            event_types=[AlertType.SCORE_THRESHOLD, AlertType.WATCHLIST_ADD],
            headers={},
            retry_config={"max_retries": 3, "retry_delay_seconds": 60},
            created_at=datetime(2025, 12, 1, 10, 0, 0),
            updated_at=datetime(2025, 12, 1, 10, 0, 0),
            created_by="user_123",
            delivery_count=50,
            success_count=48,
            failure_count=2,
            last_delivery=datetime(2025, 12, 7, 14, 30, 0),
            last_success=datetime(2025, 12, 7, 14, 30, 0),
        ),
    ]

    # Apply filters
    filtered = mock_webhooks
    if enabled is not None:
        filtered = [w for w in filtered if w.enabled == enabled]

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return WebhookListResponse(
        webhooks=page_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/webhooks", response_model=Webhook, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    webhook: WebhookCreate,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Register a new webhook.

    Requires authentication. Webhook will be active if enabled=True.
    """
    # TODO: Implement actual database insertion
    webhook_id = f"webhook_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    return Webhook(
        webhook_id=webhook_id,
        name=webhook.name,
        url=str(webhook.url),
        enabled=webhook.enabled,
        event_types=webhook.event_types,
        headers=webhook.headers,
        retry_config=webhook.retry_config,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        created_by="user_123",
        delivery_count=0,
        success_count=0,
        failure_count=0,
        last_delivery=None,
        last_success=None,
    )


@router.get("/webhooks/{webhook_id}", response_model=Webhook)
async def get_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Get webhook by ID.

    Requires authentication.
    """
    # TODO: Implement actual database query
    if webhook_id == "webhook_001":
        return Webhook(
            webhook_id=webhook_id,
            name="M&A Alerts Webhook",
            url="https://api.example.com/webhooks/ma-alerts",
            enabled=True,
            event_types=[AlertType.SCORE_THRESHOLD, AlertType.WATCHLIST_ADD],
            headers={},
            retry_config={"max_retries": 3, "retry_delay_seconds": 60},
            created_at=datetime(2025, 12, 1, 10, 0, 0),
            updated_at=datetime(2025, 12, 1, 10, 0, 0),
            created_by="user_123",
            delivery_count=50,
            success_count=48,
            failure_count=2,
            last_delivery=datetime(2025, 12, 7, 14, 30, 0),
            last_success=datetime(2025, 12, 7, 14, 30, 0),
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Webhook {webhook_id} not found",
    )


@router.patch("/webhooks/{webhook_id}", response_model=Webhook)
async def update_webhook(
    webhook_id: str,
    update: WebhookUpdate,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Update a webhook.

    Requires authentication. Only provided fields will be updated.
    """
    # TODO: Implement actual database update
    return Webhook(
        webhook_id=webhook_id,
        name=update.name or "M&A Alerts Webhook",
        url=str(update.url) if update.url else "https://api.example.com/webhooks/ma-alerts",
        enabled=update.enabled if update.enabled is not None else True,
        event_types=update.event_types or [AlertType.SCORE_THRESHOLD],
        headers=update.headers or {},
        retry_config=update.retry_config or {"max_retries": 3, "retry_delay_seconds": 60},
        created_at=datetime(2025, 12, 1, 10, 0, 0),
        updated_at=datetime.utcnow(),
        created_by="user_123",
        delivery_count=50,
        success_count=48,
        failure_count=2,
        last_delivery=datetime(2025, 12, 7, 14, 30, 0),
        last_success=datetime(2025, 12, 7, 14, 30, 0),
    )


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Delete a webhook.

    Requires authentication. Webhook will be permanently deleted.
    """
    # TODO: Implement actual database deletion
    return None


# Endpoints - Alert History
@router.get("/history", response_model=AlertHistoryResponse)
async def get_alert_history(
    rule_id: Optional[str] = Query(None, description="Filter by rule ID"),
    alert_type: Optional[AlertType] = Query(None, description="Filter by alert type"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    pagination: PaginationParams = Depends(get_pagination),
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Get alert history.

    Requires authentication. Returns paginated list of triggered alerts.
    """
    # TODO: Implement actual database query
    mock_history = [
        AlertHistoryItem(
            alert_id="alert_20251207_001",
            rule_id="alert_rule_001",
            rule_name="High M&A Score Alert",
            alert_type=AlertType.SCORE_THRESHOLD,
            severity=AlertSeverity.HIGH,
            triggered_at=datetime(2025, 12, 7, 14, 30, 0),
            status=AlertStatus.TRIGGERED,
            message="WXYZ M&A score exceeded threshold of 80 (current: 85.0)",
            details={
                "ticker": "WXYZ",
                "score": 85.0,
                "threshold": 80,
                "change_24h": 5.2,
            },
            channels_delivered=[AlertChannel.EMAIL, AlertChannel.SLACK],
        ),
    ]

    # Apply filters
    filtered = mock_history
    if rule_id:
        filtered = [a for a in filtered if a.rule_id == rule_id]
    if alert_type:
        filtered = [a for a in filtered if a.alert_type == alert_type]
    if severity:
        filtered = [a for a in filtered if a.severity == severity]
    if status:
        filtered = [a for a in filtered if a.status == status]

    # Paginate
    total = len(filtered)
    start = pagination.offset
    end = start + pagination.limit
    page_items = filtered[start:end]

    return AlertHistoryResponse(
        alerts=page_items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/history/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Acknowledge an alert.

    Requires authentication. Marks alert as acknowledged.
    """
    # TODO: Implement actual database update
    return {"message": f"Alert {alert_id} acknowledged", "acknowledged_at": datetime.utcnow()}
