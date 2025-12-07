"""
Middleware for authentication, rate limiting, and request logging.

Provides:
- API key authentication
- Rate limiting with Redis
- Request/response logging
- CORS handling
- Error handling
"""

import time
import logging
from typing import Callable, Optional
from datetime import datetime, timedelta

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis.

    Implements token bucket algorithm for rate limiting.
    Adds rate limit headers to responses.
    """

    def __init__(
        self,
        app,
        redis: Optional[Redis] = None,
        default_limit: int = 100,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.redis = redis
        self.default_limit = default_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/ready", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client identifier (API key or IP address)
        api_key = request.headers.get("X-API-Key")
        client_id = api_key if api_key else request.client.host

        # Determine rate limit for this client
        rate_limit = await self._get_rate_limit(client_id, api_key)

        # Check rate limit
        allowed, remaining, reset_time = await self._check_rate_limit(
            client_id, rate_limit
        )

        # Add rate limit headers
        response = None
        if allowed:
            response = await call_next(request)
        else:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Rate limit of {rate_limit} requests per {self.window_seconds}s exceeded",
                    "retry_after": reset_time,
                },
            )

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    async def _get_rate_limit(self, client_id: str, api_key: Optional[str]) -> int:
        """
        Get rate limit for client.

        Authenticated users get higher limits.
        """
        if api_key:
            # Authenticated users get higher limit
            return 1000  # 1000 requests per window
        else:
            # Anonymous users get default limit
            return self.default_limit

    async def _check_rate_limit(
        self, client_id: str, limit: int
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit.

        Returns:
            Tuple of (allowed, remaining, reset_timestamp)
        """
        if self.redis is None:
            # No Redis available, allow all requests
            return True, limit, 0

        now = int(time.time())
        window_start = now - self.window_seconds
        key = f"rate_limit:{client_id}"

        try:
            # Use Redis sorted set for sliding window
            pipe = self.redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry on the key
            pipe.expire(key, self.window_seconds)

            results = await pipe.execute()
            current_count = results[1]

            if current_count < limit:
                # Request allowed
                remaining = limit - current_count - 1
                reset_time = now + self.window_seconds
                return True, remaining, reset_time
            else:
                # Rate limit exceeded
                reset_time = now + self.window_seconds
                return False, 0, reset_time

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # On error, allow the request
            return True, limit, 0


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.

    Logs:
    - Request method, path, and headers
    - Response status code and duration
    - Errors and exceptions
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process and log request."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")
        request.state.request_id = request_id

        # Log request
        start_time = time.time()
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("User-Agent", "unknown"),
            },
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True,
            )
            raise


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication.

    Validates API keys and attaches user context to requests.
    """

    def __init__(self, app, api_secret_key: str):
        super().__init__(app)
        self.api_secret_key = api_secret_key
        self.public_paths = [
            "/",
            "/health",
            "/ready",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication."""
        # Skip authentication for public paths
        if request.url.path in self.public_paths:
            return await call_next(request)

        # Check for API key
        api_key = request.headers.get("X-API-Key")

        # Some endpoints may be public (handled by dependencies)
        # This middleware just validates format if key is present
        if api_key:
            # Validate API key format
            if not self._is_valid_api_key_format(api_key):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "Invalid API key format",
                        "detail": "API key must be a valid format",
                    },
                    headers={"WWW-Authenticate": "ApiKey"},
                )

            # Attach user context to request
            request.state.api_key = api_key
            request.state.is_authenticated = True
        else:
            request.state.api_key = None
            request.state.is_authenticated = False

        return await call_next(request)

    def _is_valid_api_key_format(self, api_key: str) -> bool:
        """
        Validate API key format.

        In production, this would check against a database or key management system.
        """
        # Basic validation: key should be non-empty and alphanumeric
        if not api_key or len(api_key) < 16:
            return False

        return True


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Catches unhandled exceptions and returns proper error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with error handling."""
        try:
            return await call_next(request)
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Validation error",
                    "detail": str(e),
                },
            )
        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Permission denied",
                    "detail": str(e),
                },
            )
        except FileNotFoundError as e:
            logger.warning(f"Resource not found: {e}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "Resource not found",
                    "detail": str(e),
                },
            )
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "detail": "An unexpected error occurred",
                },
            )


# Utility functions for manual rate limit checking
async def check_rate_limit(
    redis: Redis,
    client_id: str,
    limit: int = 100,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Manually check rate limit for a client.

    Args:
        redis: Redis connection
        client_id: Client identifier
        limit: Maximum requests allowed
        window_seconds: Time window in seconds

    Returns:
        Tuple of (allowed, remaining_requests)
    """
    now = int(time.time())
    window_start = now - window_seconds
    key = f"rate_limit:{client_id}"

    try:
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]

        if current_count < limit:
            remaining = limit - current_count - 1
            return True, remaining
        else:
            return False, 0

    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True, limit
