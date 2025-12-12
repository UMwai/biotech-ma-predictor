"""FDA drug approvals and PDUFA dates subagent."""

from datetime import datetime, timedelta
from typing import Any

from .base_agent import BaseAgent


class FDAAgent(BaseAgent):
    """Agent that fetches FDA drug approval data and upcoming PDUFA dates."""

    def __init__(self, days_back: int = 30, limit: int = 50):
        super().__init__("FDA-Approvals")
        self.days_back = days_back
        self.limit = limit
        self.api_url = "https://api.fda.gov/drug/drugsfda.json"

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch recent FDA drug approvals."""
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.days_back)

        params = {
            "search": f"submissions.submission_type:ORIG+AND+submissions.submission_status_date:[{start_date.strftime('%Y%m%d')}+TO+{end_date.strftime('%Y%m%d')}]",
            "limit": str(self.limit),
            "sort": "submissions.submission_status_date:desc"
        }

        try:
            resp = await self.client.get(self.api_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for drug in data.get("results", []):
                submissions = drug.get("submissions", [])
                products = drug.get("products", [])
                openfda = drug.get("openfda", {})

                # Get the most recent approval submission
                approval_sub = None
                for sub in submissions:
                    if sub.get("submission_type") == "ORIG" and sub.get("submission_status") == "AP":
                        approval_sub = sub
                        break

                results.append({
                    "source": "fda",
                    "application_number": drug.get("application_number"),
                    "sponsor_name": drug.get("sponsor_name"),
                    "brand_name": products[0].get("brand_name") if products else None,
                    "generic_name": openfda.get("generic_name", [None])[0],
                    "approval_date": approval_sub.get("submission_status_date") if approval_sub else None,
                    "submission_class": approval_sub.get("submission_class_code_description") if approval_sub else None,
                    "route": openfda.get("route", []),
                    "substance_name": openfda.get("substance_name", [])
                })

            return results

        except Exception as e:
            # Return empty if API fails (common with FDA API)
            return []

    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter for relevant approvals (all FDA approvals are relevant for biotech tracking)."""
        # Filter out entries without essential data
        return [
            d for d in data
            if d.get("brand_name") or d.get("generic_name")
        ][:20]


class PDUFAAgent(BaseAgent):
    """Agent that tracks upcoming PDUFA dates (FDA decision deadlines)."""

    def __init__(self):
        super().__init__("PDUFA-Calendar")
        # Note: This would need a proper data source - biopharmcatalyst requires scraping
        self.known_pdufa_dates = []

    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch upcoming PDUFA dates."""
        # Static list of known major PDUFA dates - in production, scrape biopharmcatalyst
        # or use a paid API like Evaluate Pharma
        return [
            {
                "source": "pdufa",
                "company": "Viking Therapeutics",
                "ticker": "VKTX",
                "drug": "VK2735",
                "indication": "Obesity",
                "pdufa_date": "2026-Q2",
                "catalyst_type": "Phase 3 Readout Expected"
            },
            {
                "source": "pdufa",
                "company": "Structure Therapeutics",
                "ticker": "GPCR",
                "drug": "GSBR-1290",
                "indication": "Obesity",
                "pdufa_date": "2025-Q4",
                "catalyst_type": "Phase 2b Data"
            },
        ]

    def filter_relevant(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """All PDUFA dates are relevant."""
        return data
