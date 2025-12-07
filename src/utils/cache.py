"""
Caching utilities using Redis.
"""

import json
import hashlib
from functools import wraps
from typing import Any, Callable, Optional
import redis.asyncio as redis

from src.config import settings


class Cache:
    """Redis-backed cache for expensive computations."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection."""
        self._client = redis.from_url(self.redis_url, decode_responses=True)

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            await self.connect()

        value = await self._client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
    ) -> None:
        """Set value in cache with TTL."""
        if not self._client:
            await self.connect()

        await self._client.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        if not self._client:
            await self.connect()

        await self._client.delete(key)

    async def clear_pattern(self, pattern: str) -> None:
        """Clear all keys matching pattern."""
        if not self._client:
            await self.connect()

        cursor = 0
        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            if keys:
                await self._client.delete(*keys)
            if cursor == 0:
                break


def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable) -> Callable:
        cache = Cache()

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key from function name and arguments
            key_data = f"{func.__name__}:{args}:{kwargs}"
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            cache_key = f"{key_prefix}:{key_hash}" if key_prefix else key_hash

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator


# Global cache instance
cache = Cache()
