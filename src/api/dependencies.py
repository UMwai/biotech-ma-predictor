"""
Dependency injection for FastAPI routes.

Provides database connections, services, and configuration
to route handlers via dependency injection.
"""

from typing import AsyncGenerator, Optional
from functools import lru_cache

from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from redis.asyncio import Redis
import logging

from src.config import Settings, settings as global_settings

logger = logging.getLogger(__name__)


# Database session management
class Database:
    """Database connection manager."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = create_async_engine(
            settings.postgres_dsn,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


# Global database instance
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Get or create database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(global_settings)
    return _db_instance


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Usage:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    db = get_database()
    async for session in db.get_session():
        yield session


# Redis cache management
class RedisCache:
    """Redis cache manager."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis: Optional[Redis] = None

    async def get_redis(self) -> Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await Redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()


# Global Redis instance
_redis_instance: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get or create Redis cache instance."""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = RedisCache(global_settings)
    return _redis_instance


async def get_redis() -> Redis:
    """
    Dependency to get Redis connection.

    Usage:
        @router.get("/endpoint")
        async def endpoint(redis: Redis = Depends(get_redis)):
            ...
    """
    cache = get_redis_cache()
    return await cache.get_redis()


# Settings dependency
@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings.

    Cached to avoid reloading settings on every request.

    Usage:
        @router.get("/endpoint")
        async def endpoint(settings: Settings = Depends(get_settings)):
            ...
    """
    return global_settings


# API Key authentication
async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Verify API key from request header.

    Raises:
        HTTPException: If API key is missing or invalid.

    Returns:
        The validated API key.

    Usage:
        @router.get("/endpoint")
        async def endpoint(api_key: str = Depends(verify_api_key)):
            ...
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # In production, validate against database or key management system
    # For now, check against configured secret key
    if settings.api_secret_key and x_api_key != settings.api_secret_key:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key


# Optional API Key (for public endpoints with optional auth)
async def optional_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    """
    Optional API key verification.

    Returns None if no key provided, validates if provided.

    Usage:
        @router.get("/endpoint")
        async def endpoint(api_key: Optional[str] = Depends(optional_api_key)):
            # Public endpoint with optional enhanced features for authenticated users
            ...
    """
    if not x_api_key:
        return None

    try:
        return await verify_api_key(x_api_key, settings)
    except HTTPException:
        return None


# Request context
class RequestContext:
    """Request context with user information and rate limiting."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        rate_limit: int = 100,
    ):
        self.api_key = api_key
        self.user_id = user_id or "anonymous"
        self.rate_limit = rate_limit
        self.is_authenticated = api_key is not None


async def get_request_context(
    api_key: Optional[str] = Depends(optional_api_key),
    settings: Settings = Depends(get_settings),
) -> RequestContext:
    """
    Get request context with authentication status.

    Usage:
        @router.get("/endpoint")
        async def endpoint(ctx: RequestContext = Depends(get_request_context)):
            if ctx.is_authenticated:
                # Enhanced features
                ...
    """
    if api_key:
        # In production, look up user from API key
        return RequestContext(
            api_key=api_key,
            user_id="authenticated_user",
            rate_limit=1000,  # Higher limit for authenticated users
        )
    else:
        return RequestContext(
            api_key=None,
            user_id="anonymous",
            rate_limit=100,  # Lower limit for anonymous users
        )


# Pagination helper
class PaginationParams:
    """Pagination parameters."""

    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
        max_page_size: int = 100,
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), max_page_size)

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database query."""
        return self.page_size


def get_pagination(
    page: int = 1,
    page_size: int = 20,
) -> PaginationParams:
    """
    Get pagination parameters from query string.

    Usage:
        @router.get("/endpoint")
        async def endpoint(pagination: PaginationParams = Depends(get_pagination)):
            results = await query.offset(pagination.offset).limit(pagination.limit).all()
            ...
    """
    return PaginationParams(page=page, page_size=page_size)


# Cleanup on shutdown
async def cleanup_resources():
    """Clean up database and Redis connections on shutdown."""
    global _db_instance, _redis_instance

    if _db_instance is not None:
        await _db_instance.close()
        _db_instance = None

    if _redis_instance is not None:
        await _redis_instance.close()
        _redis_instance = None

    logger.info("Cleaned up database and Redis connections")
