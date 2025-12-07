"""
Configuration management using Pydantic Settings.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database - PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "biotech_ma"
    postgres_user: str = ""
    postgres_password: str = ""

    # Database - TimescaleDB
    timescale_host: str = "localhost"
    timescale_port: int = 5433
    timescale_db: str = "biotech_timeseries"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""

    # Event Bus
    event_bus_type: str = "rabbitmq"

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "biotech"

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    eventbridge_bus_name: str = "biotech-ma-events"

    # SEC EDGAR
    sec_user_agent: str = "BiotechMAPredictor contact@example.com"

    # FDA
    fda_api_key: str = ""

    # Financial APIs
    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""

    # News APIs
    newsapi_key: str = ""
    benzinga_api_key: str = ""

    # AI APIs
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Notifications
    sendgrid_api_key: str = ""
    from_email: str = "reports@example.com"
    slack_bot_token: str = ""
    slack_webhook_url: str = ""

    # Storage
    s3_bucket_name: str = "biotech-ma-reports"
    s3_region: str = "us-east-1"

    # Scoring Thresholds
    ma_score_alert_threshold: int = 75
    ma_score_change_alert: int = 10
    watchlist_min_score: int = 50

    # Scoring Weights (must sum to 1.0)
    weight_pipeline: float = 0.25
    weight_patent: float = 0.15
    weight_financial: float = 0.20
    weight_insider: float = 0.15
    weight_strategic_fit: float = 0.15
    weight_regulatory: float = 0.10

    # Scheduler
    daily_digest_cron: str = "0 6 * * *"
    weekly_report_cron: str = "0 8 * * 1"
    data_refresh_interval_minutes: int = 15

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def postgres_dsn(self) -> str:
        """Get PostgreSQL connection string."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"


# Global settings instance
settings = Settings()
