"""
FDA Data Ingester

Fetches and processes FDA data including:
- Drug approval decisions
- Complete Response Letters (CRLs)
- Breakthrough therapy designations
- Fast track designations
- Orphan drug designations
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json

import httpx

from src.ingestion.base import DataIngester, IngestionError, RateLimitConfig, RetryConfig


class FDAIngester(DataIngester):
    """
    Ingester for FDA databases.

    Uses openFDA API for drug approvals and designations.
    """

    BASE_URL = "https://api.fda.gov"
    DRUG_EVENT_URL = f"{BASE_URL}/drug/event.json"
    DRUG_LABEL_URL = f"{BASE_URL}/drug/label.json"
    DRUG_APPROVAL_URL = f"{BASE_URL}/drug/drugsfda.json"

    # Approval types
    APPROVAL_TYPES = [
        "NDA",  # New Drug Application
        "ANDA",  # Abbreviated NDA (generic)
        "BLA",  # Biologics License Application
    ]

    # Action types
    ACTION_TYPES = [
        "AP",  # Approval
        "TA",  # Tentative Approval
        "CR",  # Complete Response Letter (rejection)
    ]

    def __init__(
        self,
        event_bus: Any = None,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize FDA data ingester.

        Args:
            event_bus: Event bus for publishing events
            api_key: FDA API key (optional, increases rate limits)
        """
        super().__init__(
            source_name="fda",
            event_bus=event_bus,
            # Without API key: 240 requests per minute, 1000 per day
            # With API key: 240 requests per minute, 120,000 per day
            rate_limit=RateLimitConfig(
                requests_per_second=3.0,
                requests_per_minute=240 if api_key else 240,
            ),
            retry_config=RetryConfig(max_retries=3),
            **kwargs
        )

        self.api_key = api_key
        self.client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(3)
        self._last_request_time = datetime.utcnow()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
        return self.client

    async def _rate_limited_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make a rate-limited HTTP request."""
        async with self._rate_limiter:
            # Ensure minimum delay between requests
            now = datetime.utcnow()
            elapsed = (now - self._last_request_time).total_seconds()
            min_delay = 1.0 / self.rate_limit.requests_per_second

            if elapsed < min_delay:
                await asyncio.sleep(min_delay - elapsed)

            client = await self._get_client()

            # Add API key if available
            params = kwargs.get("params", {})
            if self.api_key:
                params["api_key"] = self.api_key
                kwargs["params"] = params

            # Retry logic
            for attempt in range(self.retry_config.max_retries):
                try:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    self._last_request_time = datetime.utcnow()
                    return response

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        delay = self.retry_config.get_delay(attempt)
                        self.logger.warning(f"Rate limited, retrying in {delay}s")
                        await asyncio.sleep(delay)
                        continue
                    elif e.response.status_code == 404:
                        # No results found
                        self.logger.info("No results found for query")
                        return e.response
                    raise IngestionError(f"HTTP error: {e}")

                except httpx.RequestError as e:
                    if attempt < self.retry_config.max_retries - 1:
                        delay = self.retry_config.get_delay(attempt)
                        self.logger.warning(f"Request failed, retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                        continue
                    raise IngestionError(f"Request failed: {e}")

            raise IngestionError("Max retries exceeded")

    async def fetch_drug_approvals(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch drug approvals from FDA.

        Args:
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records

        Returns:
            List of approval records
        """
        all_approvals = []
        skip = 0

        while len(all_approvals) < limit:
            try:
                # Build search query
                search_parts = []

                if start_date:
                    start_str = start_date.strftime("%Y%m%d")
                    if end_date:
                        end_str = end_date.strftime("%Y%m%d")
                        search_parts.append(f"submissions.submission_status_date:[{start_str}+TO+{end_str}]")
                    else:
                        search_parts.append(f"submissions.submission_status_date:[{start_str}+TO+99991231]")

                search_query = "+AND+".join(search_parts) if search_parts else "*:*"

                params = {
                    "search": search_query,
                    "limit": min(100, limit - len(all_approvals)),
                    "skip": skip,
                }

                response = await self._rate_limited_request(
                    "GET",
                    self.DRUG_APPROVAL_URL,
                    params=params
                )

                if response.status_code == 404:
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                all_approvals.extend(results)
                skip += len(results)

                self.logger.info(f"Fetched {len(all_approvals)} approvals so far...")

                # Check if we've reached the end
                meta = data.get("meta", {})
                total = meta.get("results", {}).get("total", 0)
                if len(all_approvals) >= total:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching drug approvals: {e}")
                break

        return all_approvals

    async def fetch_breakthrough_designations(
        self,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch breakthrough therapy designations.

        Note: This data is not directly available via openFDA API.
        In production, this would scrape FDA's breakthrough therapy page
        or use a commercial data provider.

        Args:
            start_date: Start date filter
            limit: Maximum number of records

        Returns:
            List of breakthrough designations
        """
        # Placeholder - would need to implement web scraping or use commercial API
        self.logger.warning(
            "Breakthrough designation data not available via openFDA. "
            "Would require web scraping or commercial data source."
        )
        return []

    async def fetch_fast_track_designations(
        self,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch fast track designations.

        Note: Similar to breakthrough designations, not directly available.

        Args:
            start_date: Start date filter
            limit: Maximum number of records

        Returns:
            List of fast track designations
        """
        self.logger.warning(
            "Fast track designation data not available via openFDA. "
            "Would require web scraping or commercial data source."
        )
        return []

    async def fetch_orphan_drug_designations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch orphan drug designations.

        Note: Would require scraping FDA's orphan drug database.

        Args:
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records

        Returns:
            List of orphan drug designations
        """
        self.logger.warning(
            "Orphan drug designation data not available via openFDA. "
            "Would require web scraping or commercial data source."
        )
        return []

    async def fetch_complete_response_letters(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch Complete Response Letters (CRLs).

        CRLs are indicated by action_type='CR' in submissions.

        Args:
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum number of records

        Returns:
            List of CRL records
        """
        all_crls = []
        skip = 0

        while len(all_crls) < limit:
            try:
                # Build search query for CRLs
                search_parts = ["submissions.submission_status:CR"]

                if start_date:
                    start_str = start_date.strftime("%Y%m%d")
                    if end_date:
                        end_str = end_date.strftime("%Y%m%d")
                        search_parts.append(f"submissions.submission_status_date:[{start_str}+TO+{end_str}]")
                    else:
                        search_parts.append(f"submissions.submission_status_date:[{start_str}+TO+99991231]")

                search_query = "+AND+".join(search_parts)

                params = {
                    "search": search_query,
                    "limit": min(100, limit - len(all_crls)),
                    "skip": skip,
                }

                response = await self._rate_limited_request(
                    "GET",
                    self.DRUG_APPROVAL_URL,
                    params=params
                )

                if response.status_code == 404:
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                all_crls.extend(results)
                skip += len(results)

                self.logger.info(f"Fetched {len(all_crls)} CRLs so far...")

                # Check if we've reached the end
                meta = data.get("meta", {})
                total = meta.get("results", {}).get("total", 0)
                if len(all_crls) >= total:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching CRLs: {e}")
                break

        return all_crls

    async def fetch_drug_labels(
        self,
        search_term: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch drug labels.

        Args:
            search_term: Search term for drug labels
            limit: Maximum number of records

        Returns:
            List of label records
        """
        all_labels = []
        skip = 0

        while len(all_labels) < limit:
            try:
                params = {
                    "search": search_term if search_term else "*:*",
                    "limit": min(100, limit - len(all_labels)),
                    "skip": skip,
                }

                response = await self._rate_limited_request(
                    "GET",
                    self.DRUG_LABEL_URL,
                    params=params
                )

                if response.status_code == 404:
                    break

                data = response.json()
                results = data.get("results", [])

                if not results:
                    break

                all_labels.extend(results)
                skip += len(results)

                # Limit to avoid excessive data
                if len(all_labels) >= limit:
                    break

            except Exception as e:
                self.logger.error(f"Error fetching drug labels: {e}")
                break

        return all_labels

    def extract_approval_info(self, approval_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key information from approval data.

        Args:
            approval_data: Raw approval data

        Returns:
            Extracted approval information
        """
        submissions = approval_data.get("submissions", [])

        # Find most recent approval or action
        latest_submission = None
        latest_date = None

        for submission in submissions:
            sub_status_date = submission.get("submission_status_date")
            if sub_status_date:
                try:
                    sub_date = datetime.strptime(sub_status_date, "%Y%m%d")
                    if latest_date is None or sub_date > latest_date:
                        latest_date = sub_date
                        latest_submission = submission
                except ValueError:
                    continue

        approval_info = {
            "application_number": approval_data.get("application_number"),
            "sponsor_name": approval_data.get("sponsor_name"),
            "openfda": approval_data.get("openfda", {}),
        }

        if latest_submission:
            approval_info.update({
                "submission_type": latest_submission.get("submission_type"),
                "submission_status": latest_submission.get("submission_status"),
                "submission_status_date": latest_submission.get("submission_status_date"),
                "submission_class_code": latest_submission.get("submission_class_code"),
            })

        # Extract product information
        products = approval_data.get("products", [])
        if products:
            approval_info["products"] = [
                {
                    "product_number": p.get("product_number"),
                    "brand_name": p.get("brand_name"),
                    "active_ingredients": p.get("active_ingredients", []),
                    "dosage_form": p.get("dosage_form"),
                    "route": p.get("route"),
                }
                for p in products
            ]

        return approval_info

    async def fetch_latest(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch latest FDA data.

        Returns:
            List of raw FDA records
        """
        start_date = self.last_fetch_time or (datetime.utcnow() - timedelta(days=30))

        all_data = []

        # Fetch approvals
        approvals = await self.fetch_drug_approvals(
            start_date=start_date,
            limit=kwargs.get("limit", 100)
        )
        all_data.extend([{"type": "approval", "data": a} for a in approvals])

        # Fetch CRLs
        crls = await self.fetch_complete_response_letters(
            start_date=start_date,
            limit=kwargs.get("limit", 100)
        )
        all_data.extend([{"type": "crl", "data": c} for c in crls])

        return all_data

    async def fetch_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical FDA data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of raw FDA records
        """
        all_data = []

        # Fetch approvals
        approvals = await self.fetch_drug_approvals(
            start_date=start_date,
            end_date=end_date,
            limit=kwargs.get("limit", 500)
        )
        all_data.extend([{"type": "approval", "data": a} for a in approvals])

        # Fetch CRLs
        crls = await self.fetch_complete_response_letters(
            start_date=start_date,
            end_date=end_date,
            limit=kwargs.get("limit", 500)
        )
        all_data.extend([{"type": "crl", "data": c} for c in crls])

        return all_data

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform FDA data to internal schema.

        Args:
            raw_data: Raw FDA data

        Returns:
            Normalized FDA data
        """
        data_type = raw_data.get("type")
        data = raw_data.get("data", {})

        # Extract common fields
        openfda = data.get("openfda", {})

        base_record = {
            "source": "fda",
            "entity_type": f"fda_{data_type}",
            "application_number": data.get("application_number"),
            "sponsor_name": data.get("sponsor_name"),
            "brand_names": openfda.get("brand_name", []),
            "generic_names": openfda.get("generic_name", []),
            "manufacturer_names": openfda.get("manufacturer_name", []),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        # Extract submissions
        submissions = data.get("submissions", [])
        if submissions:
            # Get latest submission
            latest_submission = max(
                submissions,
                key=lambda s: s.get("submission_status_date", "0"),
                default={}
            )

            base_record.update({
                "submission_type": latest_submission.get("submission_type"),
                "submission_status": latest_submission.get("submission_status"),
                "submission_status_date": latest_submission.get("submission_status_date"),
                "submission_class_code": latest_submission.get("submission_class_code"),
            })

        # Extract products
        products = data.get("products", [])
        if products:
            base_record["products"] = [
                {
                    "brand_name": p.get("brand_name"),
                    "active_ingredients": p.get("active_ingredients", []),
                    "dosage_form": p.get("dosage_form"),
                    "route": p.get("route"),
                }
                for p in products
            ]

        # Add type-specific metadata
        base_record["metadata"] = {
            "data_type": data_type,
            "product_type": data.get("product_type"),
        }

        return base_record

    async def health_check(self) -> Dict[str, Any]:
        """Check FDA API health."""
        try:
            response = await self._rate_limited_request(
                "GET",
                self.DRUG_APPROVAL_URL,
                params={"search": "*:*", "limit": 1}
            )
            return {
                "source": self.source_name,
                "status": "healthy" if response.status_code == 200 else "degraded",
                "last_fetch": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            }
        except Exception as e:
            return {
                "source": self.source_name,
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
