"""
Async database connection management.

Handles SQLAlchemy engine creation, session management, connection pooling,
and health checks for the PostgreSQL database.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from src.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages async database connections and sessions.

    Implements singleton pattern to ensure single engine instance.
    Provides session factory for creating async sessions.
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def __new__(cls) -> "DatabaseManager":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(
        cls,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False,
    ) -> "DatabaseManager":
        """
        Initialize database engine and session factory.

        Args:
            pool_size: Number of connections to maintain in the pool
            max_overflow: Max number of connections beyond pool_size
            pool_timeout: Seconds to wait before timing out on connection
            pool_recycle: Seconds before recycling connections
            echo: Whether to log all SQL statements

        Returns:
            DatabaseManager instance
        """
        instance = cls()

        if instance._engine is not None:
            logger.warning("Database already initialized, skipping")
            return instance

        logger.info("Initializing database connection pool")

        # Create async engine with connection pooling
        instance._engine = create_async_engine(
            settings.postgres_dsn,
            echo=echo,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Verify connections before using
            connect_args={
                "server_settings": {
                    "application_name": "biotech_ma_predictor",
                },
            },
        )

        # Create session factory
        instance._session_factory = async_sessionmaker(
            instance._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Database connection pool initialized successfully")
        return instance

    @classmethod
    def get_engine(cls) -> AsyncEngine:
        """
        Get the database engine.

        Returns:
            AsyncEngine instance

        Raises:
            RuntimeError: If database not initialized
        """
        instance = cls()
        if instance._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return instance._engine

    @classmethod
    def get_session_factory(cls) -> async_sessionmaker[AsyncSession]:
        """
        Get the session factory.

        Returns:
            Session factory for creating AsyncSession instances

        Raises:
            RuntimeError: If database not initialized
        """
        instance = cls()
        if instance._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return instance._session_factory

    @classmethod
    async def close(cls) -> None:
        """Close database connections and dispose of engine."""
        instance = cls()
        if instance._engine is not None:
            logger.info("Closing database connection pool")
            await instance._engine.dispose()
            instance._engine = None
            instance._session_factory = None
            logger.info("Database connection pool closed")

    @classmethod
    async def health_check(cls) -> bool:
        """
        Perform database health check.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            engine = cls.get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.

    Provides automatic transaction management:
    - Commits on successful completion
    - Rolls back on exceptions
    - Always closes session

    Usage:
        async with get_db_session() as session:
            # Use session here
            result = await session.execute(...)

    Yields:
        AsyncSession instance
    """
    session_factory = DatabaseManager.get_session_factory()
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def init_db(
    pool_size: int = 20,
    max_overflow: int = 10,
    echo: bool = False,
) -> None:
    """
    Initialize database connection.

    Args:
        pool_size: Number of connections in the pool
        max_overflow: Maximum overflow connections
        echo: Whether to echo SQL statements
    """
    DatabaseManager.initialize(
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
    )
    logger.info("Database initialized")


async def close_db() -> None:
    """Close database connections."""
    await DatabaseManager.close()
    logger.info("Database closed")


async def health_check() -> bool:
    """
    Check database health.

    Returns:
        True if database is healthy
    """
    return await DatabaseManager.health_check()
