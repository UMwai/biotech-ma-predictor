"""Parallel orchestrator for biotech intelligence subagents."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .base_agent import AgentResult, BaseAgent
from .clinical_trials_agent import ClinicalTrialsAgent
from .discord_publisher import DiscordPublisher
from .fda_agent import FDAAgent, PDUFAAgent
from .news_agent import NewsAgent
from .sec_agent import SECAgent

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Result from parallel orchestration run."""
    success: bool
    total_execution_time_ms: float
    agent_results: list[AgentResult] = field(default_factory=list)
    published: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_items(self) -> int:
        return sum(len(r.data) for r in self.agent_results if r.success)

    @property
    def failed_agents(self) -> list[str]:
        return [r.agent_name for r in self.agent_results if not r.success]


class ParallelOrchestrator:
    """Orchestrates parallel execution of all biotech intelligence subagents."""

    def __init__(
        self,
        discord_webhook_url: str | None = None,
        news_api_key: str | None = None,
        enable_discord: bool = True
    ):
        self.discord_webhook_url = discord_webhook_url
        self.news_api_key = news_api_key
        self.enable_discord = enable_discord

    def _create_agents(self) -> list[BaseAgent]:
        """Create all subagent instances."""
        return [
            SECAgent(),
            FDAAgent(),
            ClinicalTrialsAgent(),
            NewsAgent(api_key=self.news_api_key),
        ]

    async def _run_agent(self, agent: BaseAgent) -> AgentResult:
        """Run a single agent with proper context management."""
        async with agent:
            return await agent.run()

    async def run(self) -> OrchestratorResult:
        """Execute all agents in parallel and optionally publish results."""
        start = asyncio.get_event_loop().time()

        agents = self._create_agents()

        # Run all agents in parallel
        logger.info(f"Starting parallel execution of {len(agents)} agents")
        tasks = [self._run_agent(agent) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to failed AgentResults
        agent_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent_results.append(AgentResult(
                    agent_name=agents[i].name,
                    success=False,
                    error=str(result)
                ))
            else:
                agent_results.append(result)

        total_time = (asyncio.get_event_loop().time() - start) * 1000

        # Publish to Discord if enabled
        published = False
        if self.enable_discord and self.discord_webhook_url:
            try:
                publisher = DiscordPublisher(self.discord_webhook_url)
                published = await publisher.publish(agent_results)
                logger.info(f"Discord publish: {'success' if published else 'failed'}")
            except Exception as e:
                logger.error(f"Discord publish error: {e}")

        result = OrchestratorResult(
            success=all(r.success for r in agent_results),
            total_execution_time_ms=total_time,
            agent_results=agent_results,
            published=published
        )

        logger.info(
            f"Orchestration complete: {result.total_items} items, "
            f"{total_time:.0f}ms, failed: {result.failed_agents}"
        )

        return result


async def run_pipeline(
    discord_webhook: str | None = None,
    news_api_key: str | None = None
) -> OrchestratorResult:
    """Convenience function to run the full pipeline."""
    orchestrator = ParallelOrchestrator(
        discord_webhook_url=discord_webhook,
        news_api_key=news_api_key
    )
    return await orchestrator.run()


# CLI entry point
if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(level=logging.INFO)

    webhook = os.getenv("DISCORD_WEBHOOK_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)

    result = asyncio.run(run_pipeline(discord_webhook=webhook))

    print(f"\n{'='*50}")
    print(f"Pipeline Complete")
    print(f"{'='*50}")
    print(f"Total items: {result.total_items}")
    print(f"Execution time: {result.total_execution_time_ms:.0f}ms")
    print(f"Published to Discord: {result.published}")

    if result.failed_agents:
        print(f"Failed agents: {', '.join(result.failed_agents)}")

    for agent_result in result.agent_results:
        status = "OK" if agent_result.success else "FAILED"
        print(f"  - {agent_result.agent_name}: {status} ({len(agent_result.data)} items, {agent_result.execution_time_ms:.0f}ms)")
