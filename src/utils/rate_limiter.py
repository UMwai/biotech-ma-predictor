"""
Rate limiting utilities for API calls.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float
    burst_size: int = 1


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Supports multiple named limits for different endpoints.
    """

    def __init__(self):
        self._configs: Dict[str, RateLimitConfig] = {}
        self._tokens: Dict[str, float] = defaultdict(float)
        self._last_update: Dict[str, float] = defaultdict(float)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def configure(self, name: str, requests_per_second: float, burst_size: int = 1):
        """Configure rate limit for a named endpoint."""
        self._configs[name] = RateLimitConfig(
            requests_per_second=requests_per_second,
            burst_size=burst_size,
        )
        self._tokens[name] = burst_size
        self._last_update[name] = time.monotonic()

    async def acquire(self, name: str) -> None:
        """
        Acquire a token, waiting if necessary.

        Args:
            name: Name of the rate limit to use
        """
        if name not in self._configs:
            return  # No rate limit configured

        config = self._configs[name]

        async with self._locks[name]:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_update[name]

                # Add tokens based on elapsed time
                self._tokens[name] = min(
                    config.burst_size,
                    self._tokens[name] + elapsed * config.requests_per_second,
                )
                self._last_update[name] = now

                if self._tokens[name] >= 1:
                    self._tokens[name] -= 1
                    return

                # Calculate wait time
                wait_time = (1 - self._tokens[name]) / config.requests_per_second
                logger.debug(f"Rate limit {name}: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter that adapts based on response headers.

    Adjusts limits based on X-RateLimit-* headers from APIs.
    """

    def update_from_headers(self, name: str, headers: dict) -> None:
        """Update rate limit based on response headers."""
        remaining = headers.get("X-RateLimit-Remaining")
        reset_time = headers.get("X-RateLimit-Reset")
        limit = headers.get("X-RateLimit-Limit")

        if remaining is not None and reset_time is not None:
            remaining = int(remaining)
            reset_time = int(reset_time)

            if remaining < 5:
                # Slow down if running low
                time_until_reset = max(1, reset_time - time.time())
                new_rate = remaining / time_until_reset

                if name in self._configs:
                    self._configs[name].requests_per_second = max(0.1, new_rate)
                    logger.warning(
                        f"Rate limit {name} adjusted to {new_rate:.2f} req/s "
                        f"({remaining} remaining, resets in {time_until_reset:.0f}s)"
                    )


# Global rate limiter instance
rate_limiter = AdaptiveRateLimiter()

# Configure default limits for common APIs
rate_limiter.configure("sec_edgar", requests_per_second=10, burst_size=10)
rate_limiter.configure("clinical_trials", requests_per_second=3, burst_size=5)
rate_limiter.configure("fda", requests_per_second=5, burst_size=10)
rate_limiter.configure("polygon", requests_per_second=5, burst_size=5)
