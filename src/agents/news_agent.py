"""Biotech M&A news aggregation subagent."""

import os
from typing import Any

from .base_agent import BaseAgent

MA_TERMS = [
    "acquisition", "acquire", "merger", "buyout", "takeover",
    "tender offer", "deal", "purchase agreement"
]


class NewsAgent(BaseAgent):
    """Agent that fetches biotech M&A news from multiple sources."""

    def __init__(self, api_key: str | None = None):
        super().__init__("News-Aggregator")
        self.api_key = api_key or os.getenv("NEWS_API_KEY")

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch news from multiple sources."""
        news = []

        # Try NewsAPI if key available
        if self.api_key:
            news.extend(await self._fetch_newsapi())

        # Try free RSS feeds
        news.extend(await self._fetch_rss_feeds())

        return news

    async def _fetch_newsapi(self) -> list[dict[str, Any]]:
        """Fetch from NewsAPI."""
        try:
            params = {
                "q": "(biotech OR pharmaceutical OR biopharma) AND (acquisition OR merger OR M&A OR buyout OR takeover)",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": "50"
            }
            headers = {"X-Api-Key": self.api_key}

            resp = await self.client.get(
                "https://newsapi.org/v2/everything",
                params=params,
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                {
                    "source": "news",
                    "provider": article.get("source", {}).get("name"),
                    "title": article.get("title"),
                    "description": article.get("description"),
                    "url": article.get("url"),
                    "published": article.get("publishedAt")
                }
                for article in data.get("articles", [])
            ]
        except Exception:
            return []

    async def _fetch_rss_feeds(self) -> list[dict[str, Any]]:
        """Fetch from free RSS feeds."""
        feeds = [
            "https://www.fiercebiotech.com/rss/xml",
            "https://endpts.com/feed/",
            "https://www.biopharmadive.com/feeds/news/",
        ]

        news = []
        for feed_url in feeds:
            try:
                resp = await self.client.get(feed_url, timeout=10.0)
                if resp.status_code == 200:
                    # Simple XML parsing for RSS
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)

                    for item in root.findall(".//item")[:20]:
                        title = item.find("title")
                        link = item.find("link")
                        desc = item.find("description")
                        pub = item.find("pubDate")

                        news.append({
                            "source": "news",
                            "provider": feed_url.split("/")[2],
                            "title": title.text if title is not None else "",
                            "description": desc.text if desc is not None else "",
                            "url": link.text if link is not None else "",
                            "published": pub.text if pub is not None else ""
                        })
            except Exception:
                continue

        return news

    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter for M&A-specific news."""
        relevant = []

        for article in data:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()

            # Must contain M&A-related terms
            if any(term in text for term in MA_TERMS):
                relevant.append(article)

        # Deduplicate by title similarity
        seen_titles = set()
        unique = []
        for article in relevant:
            title_key = article.get("title", "")[:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique.append(article)

        return unique[:20]
