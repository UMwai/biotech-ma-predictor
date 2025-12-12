"""Base agent class for all data fetching subagents."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from a subagent execution."""
    agent_name: str
    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    execution_time_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BaseAgent(ABC):
    """Abstract base class for all data-fetching subagents."""

    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Agent must be used as async context manager")
        return self._client

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch data from the source. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter data for biotech M&A relevance. Must be implemented by subclasses."""
        pass

    async def run(self) -> AgentResult:
        """Execute the agent and return results."""
        start = asyncio.get_event_loop().time()
        try:
            raw_data = await self.fetch()
            filtered = self.filter_relevant(raw_data)
            execution_time = (asyncio.get_event_loop().time() - start) * 1000

            logger.info(f"{self.name}: fetched {len(raw_data)} items, {len(filtered)} relevant")

            return AgentResult(
                agent_name=self.name,
                success=True,
                data=filtered,
                execution_time_ms=execution_time
            )
        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start) * 1000
            logger.error(f"{self.name} failed: {e}")
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
