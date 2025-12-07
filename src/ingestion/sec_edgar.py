"""
SEC EDGAR Data Ingester

Fetches and processes SEC filings for biotech companies including:
- Form 4 (insider transactions)
- 13F (institutional holdings)
- 10-K/10-Q (financial statements and key metrics)
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

import httpx

from src.ingestion.base import DataIngester, IngestionError, RateLimitConfig, RetryConfig


class SECEdgarIngester(DataIngester):
    """
    Ingester for SEC EDGAR filings.

    SEC rate limit: 10 requests per second per IP
    """

    BASE_URL = "https://www.sec.gov"
    COMPANY_SEARCH_URL = f"{BASE_URL}/cgi-bin/browse-edgar"
    FILING_URL = f"{BASE_URL}/cgi-bin/current"

    # SIC codes for biotech/pharma companies
    BIOTECH_SIC_CODES = [
        "2834",  # Pharmaceutical Preparations
        "2835",  # In Vitro & In Vivo Diagnostic Substances
        "2836",  # Biological Products (No Diagnostic Substances)
        "8731",  # Commercial Physical & Biological Research
        "8734",  # Testing Laboratories
    ]

    def __init__(
        self,
        event_bus: Any = None,
        user_agent: str = "Biotech M&A Predictor contact@example.com",
        **kwargs
    ):
        """
        Initialize SEC EDGAR ingester.

        Args:
            event_bus: Event bus for publishing events
            user_agent: User agent string (SEC requires identification)
        """
        super().__init__(
            source_name="sec_edgar",
            event_bus=event_bus,
            rate_limit=RateLimitConfig(requests_per_second=8.0),  # Stay under 10/s limit
            retry_config=RetryConfig(max_retries=3),
            **kwargs
        )

        self.user_agent = user_agent
        self.client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(8)
        self._last_request_time = datetime.utcnow()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                },
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
        """
        Make a rate-limited HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response
        """
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
                    if e.response.status_code == 429:  # Too Many Requests
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

    async def fetch_biotech_companies(self) -> List[Dict[str, Any]]:
        """
        Fetch list of biotech companies from SEC.

        Returns:
            List of company information
        """
        companies = []

        for sic_code in self.BIOTECH_SIC_CODES:
            try:
                params = {
                    "action": "getcompany",
                    "SIC": sic_code,
                    "owner": "exclude",
                    "count": 100,
                    "output": "atom",
                }

                response = await self._rate_limited_request(
                    "GET",
                    self.COMPANY_SEARCH_URL,
                    params=params
                )

                # Parse XML response
                root = ET.fromstring(response.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("atom:entry", ns):
                    company_info = {
                        "cik": entry.find("atom:content/atom:cik", ns).text if entry.find("atom:content/atom:cik", ns) is not None else None,
                        "name": entry.find("atom:title", ns).text if entry.find("atom:title", ns) is not None else None,
                        "sic": sic_code,
                    }
                    companies.append(company_info)

            except Exception as e:
                self.logger.error(f"Error fetching companies for SIC {sic_code}: {e}")
                continue

        self.logger.info(f"Found {len(companies)} biotech companies")
        return companies

    async def fetch_company_filings(
        self,
        cik: str,
        filing_types: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch filings for a specific company.

        Args:
            cik: Central Index Key (CIK) of the company
            filing_types: List of filing types (e.g., ["4", "10-K", "10-Q"])
            start_date: Start date filter
            end_date: End date filter
            count: Maximum number of filings to retrieve

        Returns:
            List of filing information
        """
        filings = []

        # Normalize CIK (10 digits, zero-padded)
        cik_normalized = cik.zfill(10)

        for filing_type in filing_types:
            try:
                params = {
                    "action": "getcompany",
                    "CIK": cik_normalized,
                    "type": filing_type,
                    "dateb": end_date.strftime("%Y%m%d") if end_date else "",
                    "count": count,
                    "output": "atom",
                }

                response = await self._rate_limited_request(
                    "GET",
                    self.COMPANY_SEARCH_URL,
                    params=params
                )

                # Parse XML response
                root = ET.fromstring(response.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("atom:entry", ns):
                    filing_date_str = entry.find("atom:content/atom:filing-date", ns)
                    if filing_date_str is not None:
                        filing_date = datetime.strptime(filing_date_str.text, "%Y-%m-%d")

                        # Filter by date range
                        if start_date and filing_date < start_date:
                            continue
                        if end_date and filing_date > end_date:
                            continue

                    filing_info = {
                        "cik": cik_normalized,
                        "filing_type": filing_type,
                        "filing_date": filing_date_str.text if filing_date_str is not None else None,
                        "accession_number": entry.find("atom:content/atom:accession-number", ns).text if entry.find("atom:content/atom:accession-number", ns) is not None else None,
                        "filing_url": entry.find("atom:content/atom:filing-href", ns).text if entry.find("atom:content/atom:filing-href", ns) is not None else None,
                    }
                    filings.append(filing_info)

            except Exception as e:
                self.logger.error(f"Error fetching {filing_type} filings for CIK {cik}: {e}")
                continue

        return filings

    async def parse_form4(self, filing_url: str) -> Dict[str, Any]:
        """
        Parse Form 4 (insider transaction) filing.

        Args:
            filing_url: URL to the filing

        Returns:
            Parsed transaction data
        """
        try:
            response = await self._rate_limited_request("GET", filing_url)
            content = response.text

            # Extract key information using regex
            # This is a simplified parser - production would use proper XML parsing
            transactions = {
                "filing_url": filing_url,
                "transactions": [],
            }

            # Extract reporter information
            reporter_match = re.search(r"<reportingOwner>(.*?)</reportingOwner>", content, re.DOTALL)
            if reporter_match:
                reporter_section = reporter_match.group(1)
                name_match = re.search(r"<rptOwnerName>(.*?)</rptOwnerName>", reporter_section)
                transactions["reporter_name"] = name_match.group(1) if name_match else None

            # Extract transaction information
            tx_matches = re.finditer(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", content, re.DOTALL)

            for tx_match in tx_matches:
                tx_section = tx_match.group(1)

                # Parse transaction details
                security_title = re.search(r"<securityTitle>(.*?)</securityTitle>", tx_section)
                tx_date = re.search(r"<transactionDate>(.*?)</transactionDate>", tx_section)
                tx_code = re.search(r"<transactionCode>(.*?)</transactionCode>", tx_section)
                shares = re.search(r"<transactionShares>(.*?)</transactionShares>", tx_section)
                price = re.search(r"<transactionPricePerShare>(.*?)</transactionPricePerShare>", tx_section)
                acquired_disposed = re.search(r"<transactionAcquiredDisposedCode>(.*?)</transactionAcquiredDisposedCode>", tx_section)

                transaction = {
                    "security_title": security_title.group(1) if security_title else None,
                    "transaction_date": tx_date.group(1) if tx_date else None,
                    "transaction_code": tx_code.group(1) if tx_code else None,
                    "shares": float(shares.group(1)) if shares else None,
                    "price_per_share": float(price.group(1)) if price else None,
                    "acquired_disposed": acquired_disposed.group(1) if acquired_disposed else None,
                }

                transactions["transactions"].append(transaction)

            return transactions

        except Exception as e:
            self.logger.error(f"Error parsing Form 4: {e}")
            return {"error": str(e), "filing_url": filing_url}

    async def parse_13f(self, filing_url: str) -> Dict[str, Any]:
        """
        Parse 13F (institutional holdings) filing.

        Args:
            filing_url: URL to the filing

        Returns:
            Parsed holdings data
        """
        try:
            response = await self._rate_limited_request("GET", filing_url)
            content = response.text

            holdings = {
                "filing_url": filing_url,
                "positions": [],
            }

            # Extract holdings information
            # Simplified parser - production would use proper XML/SGML parsing
            position_matches = re.finditer(
                r"<infoTable>(.*?)</infoTable>",
                content,
                re.DOTALL
            )

            for pos_match in position_matches:
                pos_section = pos_match.group(1)

                name_match = re.search(r"<nameOfIssuer>(.*?)</nameOfIssuer>", pos_section)
                shares_match = re.search(r"<shrsOrPrnAmt>(.*?)</shrsOrPrnAmt>", pos_section, re.DOTALL)
                value_match = re.search(r"<value>(.*?)</value>", pos_section)

                shares = None
                if shares_match:
                    shares_section = shares_match.group(1)
                    shares_number = re.search(r"<sshPrnamt>(.*?)</sshPrnamt>", shares_section)
                    if shares_number:
                        shares = float(shares_number.group(1))

                position = {
                    "issuer_name": name_match.group(1).strip() if name_match else None,
                    "shares": shares,
                    "value": float(value_match.group(1)) if value_match else None,
                }

                holdings["positions"].append(position)

            return holdings

        except Exception as e:
            self.logger.error(f"Error parsing 13F: {e}")
            return {"error": str(e), "filing_url": filing_url}

    async def extract_10k_metrics(self, filing_url: str) -> Dict[str, Any]:
        """
        Extract key metrics from 10-K/10-Q filings.

        Args:
            filing_url: URL to the filing

        Returns:
            Extracted financial metrics
        """
        try:
            response = await self._rate_limited_request("GET", filing_url)
            content = response.text

            metrics = {
                "filing_url": filing_url,
                "metrics": {},
            }

            # Extract key financial metrics
            # This is simplified - production would use XBRL parsing

            # Cash and cash equivalents
            cash_match = re.search(
                r"Cash[,\s]+[Cc]ash [Ee]quivalents.*?[\$\s]+([\d,]+)",
                content
            )
            if cash_match:
                metrics["metrics"]["cash"] = float(cash_match.group(1).replace(",", ""))

            # Total assets
            assets_match = re.search(
                r"Total [Aa]ssets.*?[\$\s]+([\d,]+)",
                content
            )
            if assets_match:
                metrics["metrics"]["total_assets"] = float(assets_match.group(1).replace(",", ""))

            # Revenue
            revenue_match = re.search(
                r"(?:Revenue|Net [Ss]ales).*?[\$\s]+([\d,]+)",
                content
            )
            if revenue_match:
                metrics["metrics"]["revenue"] = float(revenue_match.group(1).replace(",", ""))

            # R&D expenses
            rd_match = re.search(
                r"Research and [Dd]evelopment.*?[\$\s]+([\d,]+)",
                content
            )
            if rd_match:
                metrics["metrics"]["rd_expenses"] = float(rd_match.group(1).replace(",", ""))

            return metrics

        except Exception as e:
            self.logger.error(f"Error extracting 10-K metrics: {e}")
            return {"error": str(e), "filing_url": filing_url}

    async def fetch_latest(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch latest SEC filings since last fetch.

        Returns:
            List of raw filing data
        """
        start_date = self.last_fetch_time or (datetime.utcnow() - timedelta(days=7))
        end_date = datetime.utcnow()

        return await self.fetch_historical(start_date, end_date, **kwargs)

    async def fetch_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical SEC filings for date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of raw filing data
        """
        filing_types = kwargs.get("filing_types", ["4", "13F-HR", "10-K", "10-Q"])
        companies = kwargs.get("companies", None)

        all_filings = []

        # If no companies specified, fetch biotech companies
        if not companies:
            companies = await self.fetch_biotech_companies()

        self.logger.info(f"Fetching filings for {len(companies)} companies")

        # Fetch filings for each company
        for company in companies[:50]:  # Limit for demo purposes
            try:
                cik = company.get("cik")
                if not cik:
                    continue

                filings = await self.fetch_company_filings(
                    cik=cik,
                    filing_types=filing_types,
                    start_date=start_date,
                    end_date=end_date,
                )

                for filing in filings:
                    filing["company_name"] = company.get("name")
                    all_filings.append(filing)

                # Small delay between companies
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error processing company {company}: {e}")
                continue

        self.logger.info(f"Fetched {len(all_filings)} total filings")
        return all_filings

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform SEC filing data to internal schema.

        Args:
            raw_data: Raw filing data

        Returns:
            Normalized filing data
        """
        return {
            "source": "sec_edgar",
            "entity_type": "sec_filing",
            "cik": raw_data.get("cik"),
            "company_name": raw_data.get("company_name"),
            "filing_type": raw_data.get("filing_type"),
            "filing_date": raw_data.get("filing_date"),
            "accession_number": raw_data.get("accession_number"),
            "filing_url": raw_data.get("filing_url"),
            "ingestion_timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "sic": raw_data.get("sic"),
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check SEC EDGAR API health."""
        try:
            response = await self._rate_limited_request("GET", self.BASE_URL)
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
