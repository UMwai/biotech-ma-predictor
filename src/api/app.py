"""
Main FastAPI application.

Creates and configures the FastAPI app with all routes, middleware,
and lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

from src.config import Settings, settings as global_settings
from src.api.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    AuthenticationMiddleware,
    ErrorHandlingMiddleware,
)
from src.api.dependencies import (
    get_redis_cache,
    cleanup_resources,
)
from src.api.routes import companies, predictions, reports, alerts

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Biotech M&A Predictor API...")

    # Initialize Redis connection
    try:
        redis_cache = get_redis_cache()
        redis = await redis_cache.get_redis()
        await redis.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Rate limiting will be disabled.")

    logger.info("API server ready")

    yield

    # Shutdown
    logger.info("Shutting down Biotech M&A Predictor API...")
    await cleanup_resources()
    logger.info("Shutdown complete")


def create_app(settings: Settings = global_settings) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        settings: Application settings

    Returns:
        Configured FastAPI application
    """
    # Create FastAPI app
    app = FastAPI(
        title="Biotech M&A Predictor API",
        description="""
# Biotech M&A Predictor API

REST API for accessing biotech M&A predictions, company data, and signals.

## Features

- **Company Data**: Access detailed company profiles, pipelines, and signals
- **M&A Predictions**: Get ranked watchlists and potential acquirer matches
- **Reports**: Generate and access M&A analysis reports
- **Alerts**: Configure webhooks and notifications for M&A signals

## Authentication

Most endpoints require an API key provided via the `X-API-Key` header.

```
X-API-Key: your_api_key_here
```

## Rate Limiting

- **Anonymous users**: 100 requests per minute
- **Authenticated users**: 1000 requests per minute

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Time when rate limit resets (Unix timestamp)

## Data Freshness

All data is updated continuously throughout the trading day. The `last_updated`
timestamp on each resource indicates when it was last refreshed.

## Support

For API support, contact: api-support@example.com
        """,
        version="1.0.0",
        contact={
            "name": "API Support",
            "email": "api-support@example.com",
        },
        license_info={
            "name": "Proprietary",
        },
        lifespan=lifespan,
        docs_url=None,  # We'll customize docs
        redoc_url=None,  # We'll customize redoc
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # React dev server
            "http://localhost:8000",  # API dev server
            "https://biotech-ma.example.com",  # Production frontend
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
    )

    # Add custom middleware (order matters - first added = outermost)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthenticationMiddleware, api_secret_key=settings.api_secret_key)

    # Add rate limiting middleware with Redis
    try:
        redis_cache = get_redis_cache()
        # We'll get Redis connection lazily in the middleware
        app.add_middleware(
            RateLimitMiddleware,
            redis=None,  # Will be set up in middleware
            default_limit=100,
            window_seconds=60,
        )
    except Exception as e:
        logger.warning(f"Rate limiting middleware disabled: {e}")

    # Include routers
    app.include_router(companies.router, prefix="/api/v1")
    app.include_router(predictions.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")

    # Health check endpoints
    @app.get("/health", tags=["health"], include_in_schema=False)
    async def health_check():
        """Health check endpoint for load balancers."""
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/ready", tags=["health"], include_in_schema=False)
    async def readiness_check():
        """Readiness check endpoint."""
        # Check if critical services are available
        try:
            redis_cache = get_redis_cache()
            redis = await redis_cache.get_redis()
            await redis.ping()
            return {"status": "ready", "redis": "connected"}
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "error": str(e)},
            )

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """API root endpoint with information."""
        return {
            "name": "Biotech M&A Predictor API",
            "version": "1.0.0",
            "status": "operational",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        }

    # Custom OpenAPI docs
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Custom Swagger UI with branding."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Biotech M&A Predictor API - Swagger UI",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """Custom ReDoc with branding."""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="Biotech M&A Predictor API - ReDoc",
            redoc_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )

    # Custom OpenAPI schema
    def custom_openapi():
        """Generate custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="Biotech M&A Predictor API",
            version="1.0.0",
            description=app.description,
            routes=app.routes,
        )

        # Add security scheme
        openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for authentication",
            }
        }

        # Add global security requirement for protected endpoints
        # (Individual endpoints can override this)
        openapi_schema["security"] = [{"ApiKeyAuth": []}]

        # Add custom tags
        openapi_schema["tags"] = [
            {
                "name": "companies",
                "description": "Company data and profiles",
            },
            {
                "name": "predictions",
                "description": "M&A predictions and watchlists",
            },
            {
                "name": "reports",
                "description": "Report generation and access",
            },
            {
                "name": "alerts",
                "description": "Alert rules and webhooks",
            },
            {
                "name": "health",
                "description": "Health and readiness checks",
            },
        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


# Create default app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run server
    uvicorn.run(
        "src.api.app:app",
        host=global_settings.api_host,
        port=global_settings.api_port,
        reload=True,  # Enable auto-reload in development
        log_level=global_settings.log_level.lower(),
    )
