"""Discord webhook publisher for biotech intelligence updates."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .base_agent import AgentResult

# Path to watchlist data
WATCHLIST_PATH = Path(__file__).parent.parent.parent / "data" / "acquisition_targets_2025.json"


class DiscordPublisher:
    """Publishes aggregated biotech intelligence to Discord."""

    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Discord webhook URL required")

    def _load_watchlist(self) -> list[dict[str, Any]]:
        """Load top M&A targets from watchlist."""
        try:
            with open(WATCHLIST_PATH) as f:
                data = json.load(f)
                return data.get("watchlist", [])[:5]
        except Exception:
            return []

    async def publish(self, results: list[AgentResult]) -> bool:
        """Publish aggregated results to Discord."""
        watchlist = self._load_watchlist()
        embeds = self._build_embeds(results, watchlist)

        async with httpx.AsyncClient() as client:
            # Discord allows max 10 embeds per message
            for i in range(0, len(embeds), 10):
                batch = embeds[i:i+10]
                payload = {"embeds": batch}

                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code not in (200, 204):
                    return False

        return True

    def _build_embeds(self, results: list[AgentResult], watchlist: list[dict] = None) -> list[dict[str, Any]]:
        """Build Discord embed objects from agent results."""
        embeds = []

        # Header embed with top targets
        if watchlist:
            target_lines = []
            for t in watchlist[:5]:
                ticker = t.get("ticker", "")
                name = t.get("name", "")
                area = t.get("therapeutic_area", "")
                score = t.get("ma_score", 0)
                prob = t.get("deal_probability_12mo", 0)
                deal_low = t.get("estimated_deal_value", {}).get("low", 0) / 1e9
                deal_high = t.get("estimated_deal_value", {}).get("high", 0) / 1e9
                acquirers = ", ".join([a.get("name", "") for a in t.get("likely_acquirers", [])[:2]])

                target_lines.append(
                    f"**{ticker}** - {name}\n"
                    f"  {area} | Score: {score} | {int(prob*100)}% prob\n"
                    f"  Deal: ${deal_low:.1f}B - ${deal_high:.1f}B | {acquirers}"
                )

            embeds.append({
                "title": "Top Biotech M&A Targets",
                "description": "\n\n".join(target_lines),
                "color": 3066993,  # Green
                "timestamp": datetime.utcnow().isoformat()
            })

        # Status embed
        embeds.append({
            "title": "Live Intelligence Scan",
            "description": f"Completed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "color": 3447003,  # Blue
            "footer": {"text": "Hot Areas: Obesity/GLP-1 | Oncology/ADC | Radiopharmaceuticals | CNS"}
        })

        for result in results:
            if not result.success or not result.data:
                continue

            embed = self._agent_result_to_embed(result)
            if embed:
                embeds.append(embed)

        return embeds

    def _agent_result_to_embed(self, result: AgentResult) -> dict[str, Any] | None:
        """Convert a single agent result to Discord embed."""
        if result.agent_name == "SEC-EDGAR":
            return self._sec_embed(result)
        elif result.agent_name == "FDA-Approvals":
            return self._fda_embed(result)
        elif result.agent_name == "ClinicalTrials":
            return self._trials_embed(result)
        elif result.agent_name == "News-Aggregator":
            return self._news_embed(result)
        return None

    def _sec_embed(self, result: AgentResult) -> dict[str, Any]:
        """Build SEC filings embed."""
        fields = []
        for filing in result.data[:5]:
            title = filing.get("title", "")[:100]
            form = filing.get("form_type", "8-K")
            url = filing.get("url", "")

            fields.append({
                "name": f"{form}",
                "value": f"[{title}]({url})" if url else title,
                "inline": False
            })

        return {
            "title": "SEC M&A Filings",
            "color": 15844367,  # Gold
            "fields": fields,
            "footer": {"text": f"{len(result.data)} filings found | {result.execution_time_ms:.0f}ms"}
        }

    def _fda_embed(self, result: AgentResult) -> dict[str, Any]:
        """Build FDA approvals embed."""
        fields = []
        for drug in result.data[:5]:
            name = drug.get("brand_name") or drug.get("generic_name") or "Unknown"
            sponsor = drug.get("sponsor_name", "")
            date = drug.get("approval_date", "")

            fields.append({
                "name": name,
                "value": f"**Sponsor:** {sponsor}\n**Approved:** {date}",
                "inline": True
            })

        return {
            "title": "FDA Drug Approvals",
            "color": 3066993,  # Green
            "fields": fields,
            "footer": {"text": f"{len(result.data)} approvals | {result.execution_time_ms:.0f}ms"}
        }

    def _trials_embed(self, result: AgentResult) -> dict[str, Any]:
        """Build clinical trials embed."""
        fields = []
        for trial in result.data[:6]:
            sponsor = trial.get("sponsor", "Unknown")[:30]
            phase = trial.get("phase", "")
            completion = trial.get("completion_date", "TBD")
            conditions = ", ".join(trial.get("conditions", [])[:2])[:50]

            fields.append({
                "name": f"{sponsor} ({phase})",
                "value": f"**Conditions:** {conditions}\n**Completion:** {completion}",
                "inline": True
            })

        return {
            "title": "Upcoming Trial Readouts",
            "color": 10181046,  # Purple
            "fields": fields,
            "footer": {"text": f"{len(result.data)} trials tracked | {result.execution_time_ms:.0f}ms"}
        }

    def _news_embed(self, result: AgentResult) -> dict[str, Any]:
        """Build news embed."""
        value_lines = []
        for article in result.data[:8]:
            title = article.get("title", "")[:60]
            url = article.get("url", "")
            provider = article.get("provider", "")

            if url:
                value_lines.append(f"[{title}...]({url}) - *{provider}*")
            else:
                value_lines.append(f"{title}... - *{provider}*")

        return {
            "title": "M&A News",
            "color": 15158332,  # Red
            "description": "\n".join(value_lines) or "No recent M&A news",
            "footer": {"text": f"{len(result.data)} articles | {result.execution_time_ms:.0f}ms"}
        }
