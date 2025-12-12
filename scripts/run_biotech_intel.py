#!/usr/bin/env python3
"""Scheduled runner for biotech M&A intelligence pipeline."""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import run_pipeline

# Configuration
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1448144817010774159/0PHoOuttxGKywNS3VGW6vyDVEtKl-XYdc5HbcdOW1KTq4XwtTkbvqpkcJsIUX87gV6bn"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "biotech_intel.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Run the biotech intelligence pipeline."""
    logger.info("=" * 50)
    logger.info(f"Starting biotech M&A intelligence run at {datetime.now()}")

    try:
        result = await run_pipeline(
            discord_webhook=DISCORD_WEBHOOK,
            news_api_key=os.getenv("NEWS_API_KEY")
        )

        logger.info(f"Pipeline completed in {result.total_execution_time_ms:.0f}ms")
        logger.info(f"Total items collected: {result.total_items}")
        logger.info(f"Published to Discord: {result.published}")

        for agent_result in result.agent_results:
            status = "OK" if agent_result.success else f"FAILED: {agent_result.error}"
            logger.info(f"  {agent_result.agent_name}: {status} ({len(agent_result.data)} items)")

        if result.failed_agents:
            logger.warning(f"Failed agents: {', '.join(result.failed_agents)}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
