"""
ClinicalTrials.gov Data Ingester

Fetches and processes clinical trial data including:
- Trial status changes
- Enrollment numbers
- Endpoint modifications
- Results when posted
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import json

import httpx

from src.ingestion.base import DataIngester, IngestionError, RateLimitConfig, RetryConfig


class ClinicalTrialsIngester(DataIngester):
    """
    Ingester for ClinicalTrials.gov data.

    Uses the ClinicalTrials.gov API v2
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2"
    STUDY_FIELDS_URL = f"{BASE_URL}/studies"

    # Fields to retrieve from API
    STUDY_FIELDS = [
        "NCTId",
        "BriefTitle",
        "OfficialTitle",
        "OverallStatus",
        "StudyType",
        "Phase",
        "Condition",
        "Intervention",
        "LeadSponsorName",
        "StartDate",
        "PrimaryCompletionDate",
        "CompletionDate",
        "EnrollmentCount",
        "EnrollmentType",
        "PrimaryOutcomeDescription",
        "SecondaryOutcomeDescription",
        "HasResults",
        "LastUpdatePostDate",
    ]

    # Status values that indicate important changes
    IMPORTANT_STATUSES = [
        "RECRUITING",
        "ACTIVE_NOT_RECRUITING",
        "COMPLETED",
        "TERMINATED",
        "SUSPENDED",
        "WITHDRAWN",
    ]

    def __init__(
        self,
        event_bus: Any = None,
        **kwargs
    ):
        """
        Initialize ClinicalTrials.gov ingester.

        Args:
            event_bus: Event bus for publishing events
        """
        super().__init__(
            source_name="clinical_trials",
            event_bus=event_bus,
            rate_limit=RateLimitConfig(requests_per_second=2.0),  # Conservative rate
            retry_config=RetryConfig(max_retries=3),
            **kwargs
        )

        self.client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(2)
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
                    raise IngestionError(f"HTTP error: {e}")

                except httpx.RequestError as e:
                    if attempt < self.retry_config.max_retries - 1:
                        delay = self.retry_config.get_delay(attempt)
                        self.logger.warning(f"Request failed, retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                        continue
                    raise IngestionError(f"Request failed: {e}")

            raise IngestionError("Max retries exceeded")

    async def search_trials(
        self,
        query: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        sponsors: Optional[List[str]] = None,
        updated_after: Optional[datetime] = None,
        page_size: int = 100,
        max_studies: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Search for clinical trials.

        Args:
            query: General search query
            conditions: List of conditions to filter
            sponsors: List of sponsor names to filter
            updated_after: Only return studies updated after this date
            page_size: Number of results per page
            max_studies: Maximum total studies to retrieve

        Returns:
            List of trial data
        """
        all_studies = []
        page_token = None

        while len(all_studies) < max_studies:
            try:
                # Build query parameters
                params = {
                    "format": "json",
                    "pageSize": min(page_size, max_studies - len(all_studies)),
                }

                # Build filter expression
                filters = []

                if query:
                    filters.append(f"SEARCH[BasicSearch]{query}")

                if conditions:
                    condition_filters = " OR ".join([f"AREA[Condition]{c}" for c in conditions])
                    filters.append(f"({condition_filters})")

                if sponsors:
                    sponsor_filters = " OR ".join([f"AREA[LeadSponsorName]{s}" for s in sponsors])
                    filters.append(f"({sponsor_filters})")

                if updated_after:
                    date_str = updated_after.strftime("%Y-%m-%d")
                    filters.append(f"AREA[LastUpdatePostDate]RANGE[{date_str},MAX]")

                if filters:
                    params["query.cond"] = " AND ".join(filters)

                if page_token:
                    params["pageToken"] = page_token

                # Make request
                response = await self._rate_limited_request(
                    "GET",
                    self.STUDY_FIELDS_URL,
                    params=params
                )

                data = response.json()

                # Extract studies
                studies = data.get("studies", [])
                if not studies:
                    break

                all_studies.extend(studies)

                # Check for next page
                page_token = data.get("nextPageToken")
                if not page_token:
                    break

                self.logger.info(f"Retrieved {len(all_studies)} studies so far...")

            except Exception as e:
                self.logger.error(f"Error searching trials: {e}")
                break

        self.logger.info(f"Retrieved total of {len(all_studies)} studies")
        return all_studies

    async def get_study_details(self, nct_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific study.

        Args:
            nct_id: NCT identifier (e.g., "NCT12345678")

        Returns:
            Study details
        """
        try:
            url = f"{self.STUDY_FIELDS_URL}/{nct_id}"
            response = await self._rate_limited_request("GET", url, params={"format": "json"})
            data = response.json()

            return data.get("protocolSection", {})

        except Exception as e:
            self.logger.error(f"Error fetching study {nct_id}: {e}")
            return {"error": str(e), "nct_id": nct_id}

    async def get_study_results(self, nct_id: str) -> Optional[Dict[str, Any]]:
        """
        Get results for a study if available.

        Args:
            nct_id: NCT identifier

        Returns:
            Study results or None if not available
        """
        try:
            details = await self.get_study_details(nct_id)

            # Check if results are available
            has_results = details.get("statusModule", {}).get("hasResults", False)

            if not has_results:
                return None

            # Extract results section
            results = details.get("resultsSection", {})

            return {
                "nct_id": nct_id,
                "participant_flow": results.get("participantFlowModule"),
                "baseline_characteristics": results.get("baselineCharacteristicsModule"),
                "outcome_measures": results.get("outcomeMeasuresModule"),
                "adverse_events": results.get("adverseEventsModule"),
            }

        except Exception as e:
            self.logger.error(f"Error fetching results for {nct_id}: {e}")
            return None

    def detect_status_change(
        self,
        current_status: str,
        previous_status: Optional[str]
    ) -> Optional[str]:
        """
        Detect important status changes.

        Args:
            current_status: Current trial status
            previous_status: Previous trial status

        Returns:
            Change type if important, None otherwise
        """
        if not previous_status or current_status == previous_status:
            return None

        # Define important transitions
        important_transitions = {
            ("RECRUITING", "COMPLETED"): "trial_completed",
            ("ACTIVE_NOT_RECRUITING", "COMPLETED"): "trial_completed",
            ("RECRUITING", "TERMINATED"): "trial_terminated",
            ("ACTIVE_NOT_RECRUITING", "TERMINATED"): "trial_terminated",
            ("RECRUITING", "SUSPENDED"): "trial_suspended",
            ("NOT_YET_RECRUITING", "RECRUITING"): "trial_started",
            ("RECRUITING", "WITHDRAWN"): "trial_withdrawn",
        }

        return important_transitions.get((previous_status, current_status))

    def calculate_enrollment_change(
        self,
        current_enrollment: Optional[int],
        previous_enrollment: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate enrollment changes.

        Args:
            current_enrollment: Current enrollment count
            previous_enrollment: Previous enrollment count

        Returns:
            Change information if significant
        """
        if current_enrollment is None or previous_enrollment is None:
            return None

        if current_enrollment == previous_enrollment:
            return None

        change_pct = ((current_enrollment - previous_enrollment) / previous_enrollment) * 100

        # Flag significant changes (>10%)
        if abs(change_pct) > 10:
            return {
                "previous": previous_enrollment,
                "current": current_enrollment,
                "change": current_enrollment - previous_enrollment,
                "change_pct": round(change_pct, 2),
                "is_significant": True,
            }

        return None

    async def fetch_latest(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch latest clinical trial updates.

        Returns:
            List of raw trial data
        """
        start_date = self.last_fetch_time or (datetime.utcnow() - timedelta(days=7))

        # Search for recently updated trials
        trials = await self.search_trials(
            conditions=kwargs.get("conditions", ["cancer", "oncology"]),
            updated_after=start_date,
            max_studies=kwargs.get("max_studies", 500),
        )

        return trials

    async def fetch_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical clinical trial data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of raw trial data
        """
        trials = await self.search_trials(
            conditions=kwargs.get("conditions", ["cancer", "oncology"]),
            updated_after=start_date,
            max_studies=kwargs.get("max_studies", 1000),
        )

        # Filter by end_date (API doesn't support end date filter)
        filtered_trials = []
        for trial in trials:
            try:
                # Extract last update date
                status_module = trial.get("protocolSection", {}).get("statusModule", {})
                last_update = status_module.get("lastUpdatePostDateStruct", {}).get("date")

                if last_update:
                    update_date = datetime.strptime(last_update, "%Y-%m-%d")
                    if update_date <= end_date:
                        filtered_trials.append(trial)
                else:
                    # Include if no date available
                    filtered_trials.append(trial)

            except Exception as e:
                self.logger.error(f"Error filtering trial by date: {e}")
                continue

        return filtered_trials

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform clinical trial data to internal schema.

        Args:
            raw_data: Raw trial data from API

        Returns:
            Normalized trial data
        """
        protocol = raw_data.get("protocolSection", {})

        # Extract identification
        id_module = protocol.get("identificationModule", {})
        nct_id = id_module.get("nctId")
        brief_title = id_module.get("briefTitle")
        official_title = id_module.get("officialTitle")

        # Extract status
        status_module = protocol.get("statusModule", {})
        overall_status = status_module.get("overallStatus")
        last_update = status_module.get("lastUpdatePostDateStruct", {}).get("date")

        # Extract sponsor
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name")

        # Extract design
        design_module = protocol.get("designModule", {})
        study_type = design_module.get("studyType")
        phases = design_module.get("phases", [])

        # Extract enrollment
        enrollment_info = design_module.get("enrollmentInfo", {})
        enrollment_count = enrollment_info.get("count")

        # Extract conditions
        conditions_module = protocol.get("conditionsModule", {})
        conditions = conditions_module.get("conditions", [])

        # Extract interventions
        interventions_module = protocol.get("armsInterventionsModule", {})
        interventions = interventions_module.get("interventions", [])

        # Extract outcomes
        outcomes_module = protocol.get("outcomesModule", {})
        primary_outcomes = outcomes_module.get("primaryOutcomes", [])

        return {
            "source": "clinical_trials",
            "entity_type": "clinical_trial",
            "nct_id": nct_id,
            "brief_title": brief_title,
            "official_title": official_title,
            "overall_status": overall_status,
            "study_type": study_type,
            "phases": phases,
            "lead_sponsor": lead_sponsor,
            "conditions": conditions,
            "interventions": [i.get("name") for i in interventions],
            "enrollment_count": enrollment_count,
            "primary_outcomes": [
                {
                    "measure": o.get("measure"),
                    "description": o.get("description"),
                }
                for o in primary_outcomes
            ],
            "last_update_date": last_update,
            "ingestion_timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "has_results": status_module.get("hasResults", False),
                "start_date": status_module.get("startDateStruct", {}).get("date"),
                "completion_date": status_module.get("completionDateStruct", {}).get("date"),
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check ClinicalTrials.gov API health."""
        try:
            response = await self._rate_limited_request(
                "GET",
                self.STUDY_FIELDS_URL,
                params={"pageSize": 1, "format": "json"}
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
