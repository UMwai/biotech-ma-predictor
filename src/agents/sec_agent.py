"""SEC EDGAR filings subagent for M&A signals."""

import xml.etree.ElementTree as ET
from typing import Any

from .base_agent import BaseAgent

# Keywords indicating M&A activity
MA_KEYWORDS = [
    "acquisition", "merger", "tender offer", "material definitive agreement",
    "change of control", "business combination", "asset purchase",
    "stock purchase agreement", "buyout", "takeover"
]

# Biotech/pharma company keywords
BIOTECH_KEYWORDS = [
    "therapeutics", "pharmaceutical", "biotech", "biosciences", "oncology",
    "biopharma", "medicines", "drug", "clinical", "fda"
]


class SECAgent(BaseAgent):
    """Agent that fetches SEC 8-K filings for M&A signals."""

    # Form types relevant to M&A
    FORM_TYPES = ["8-K", "SC TO-T", "SC 13D", "DEFM14A", "S-4"]

    # SEC requires User-Agent header
    HEADERS = {
        "User-Agent": "BiotechMAPredictor/1.0 (research@example.com)",
        "Accept": "application/atom+xml"
    }

    def __init__(self, form_types: list[str] | None = None, count: int = 100):
        super().__init__("SEC-EDGAR")
        self.form_types = form_types or self.FORM_TYPES
        self.count = count
        self.base_url = "https://www.sec.gov/cgi-bin/browse-edgar"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch recent SEC filings."""
        all_filings = []

        for form_type in self.form_types:
            params = {
                "action": "getcurrent",
                "type": form_type,
                "company": "",
                "dateb": "",
                "owner": "include",
                "count": str(self.count // len(self.form_types)),
                "output": "atom"
            }

            resp = await self.client.get(self.base_url, params=params, headers=self.HEADERS)
            resp.raise_for_status()

            filings = self._parse_atom_feed(resp.text, form_type)
            all_filings.extend(filings)

        return all_filings

    def _parse_atom_feed(self, xml_content: str, form_type: str) -> list[dict[str, Any]]:
        """Parse SEC ATOM feed XML."""
        filings = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                link = entry.find("atom:link", ns)
                summary = entry.find("atom:summary", ns)
                updated = entry.find("atom:updated", ns)

                filings.append({
                    "source": "sec",
                    "form_type": form_type,
                    "title": title.text if title is not None else "",
                    "url": link.get("href") if link is not None else "",
                    "summary": summary.text if summary is not None else "",
                    "date": updated.text if updated is not None else ""
                })
        except ET.ParseError:
            pass

        return filings

    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter filings for biotech M&A relevance."""
        relevant = []

        for filing in data:
            text = f"{filing.get('title', '')} {filing.get('summary', '')}".lower()

            # Check for M&A keywords
            has_ma = any(kw in text for kw in MA_KEYWORDS)
            # Check for biotech keywords
            has_biotech = any(kw in text for kw in BIOTECH_KEYWORDS)

            # Include if it's clearly M&A related (for 8-K) or has both signals
            if filing.get("form_type") in ["SC TO-T", "SC 13D", "DEFM14A", "S-4"]:
                # These forms are inherently M&A related
                if has_biotech:
                    relevant.append(filing)
            elif has_ma and has_biotech:
                relevant.append(filing)
            elif has_ma:
                # Include M&A filings even without explicit biotech mention
                # (company might not have "biotech" in name)
                relevant.append(filing)

        return relevant[:20]  # Limit to top 20
