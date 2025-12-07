"""
Financial Data Ingester

Fetches and processes financial market data including:
- Market capitalization
- Share price movements
- Cash position estimates
- Trading volume anomalies
- Institutional ownership
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import statistics

import httpx

from src.ingestion.base import DataIngester, IngestionError, RateLimitConfig, RetryConfig


class FinancialDataIngester(DataIngester):
    """
    Ingester for financial market data.

    Supports multiple data sources:
    - yfinance (Yahoo Finance) - free, rate-limited
    - Polygon.io - requires API key
    - Alpha Vantage - requires API key
    """

    YAHOO_BASE_URL = "https://query2.finance.yahoo.com/v8/finance"
    POLYGON_BASE_URL = "https://api.polygon.io"
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

    def __init__(
        self,
        event_bus: Any = None,
        polygon_api_key: Optional[str] = None,
        alpha_vantage_api_key: Optional[str] = None,
        provider: str = "yahoo",  # yahoo, polygon, alpha_vantage
        **kwargs
    ):
        """
        Initialize financial data ingester.

        Args:
            event_bus: Event bus for publishing events
            polygon_api_key: Polygon.io API key
            alpha_vantage_api_key: Alpha Vantage API key
            provider: Data provider to use
        """
        super().__init__(
            source_name="financial_data",
            event_bus=event_bus,
            rate_limit=RateLimitConfig(
                requests_per_second=2.0 if provider == "yahoo" else 5.0
            ),
            retry_config=RetryConfig(max_retries=3),
            **kwargs
        )

        self.polygon_api_key = polygon_api_key
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.provider = provider

        self.client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = asyncio.Semaphore(2 if provider == "yahoo" else 5)
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
                    elif e.response.status_code == 404:
                        self.logger.warning(f"Resource not found: {url}")
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

    async def fetch_yahoo_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current quote data from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Quote data
        """
        try:
            url = f"{self.YAHOO_BASE_URL}/chart/{symbol}"
            params = {
                "range": "1d",
                "interval": "1d",
            }

            response = await self._rate_limited_request("GET", url, params=params)

            if response.status_code == 404:
                return {"error": "Symbol not found", "symbol": symbol}

            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]

            meta = result.get("meta", {})
            timestamp = result.get("timestamp", [])
            quote = result.get("indicators", {}).get("quote", [{}])[0]

            return {
                "symbol": symbol,
                "currency": meta.get("currency"),
                "exchange": meta.get("exchangeName"),
                "current_price": meta.get("regularMarketPrice"),
                "previous_close": meta.get("previousClose"),
                "market_cap": meta.get("marketCap"),
                "volume": meta.get("regularMarketVolume"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error fetching Yahoo quote for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}

    async def fetch_yahoo_historical(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical price data from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of historical price data
        """
        try:
            url = f"{self.YAHOO_BASE_URL}/chart/{symbol}"

            # Convert dates to timestamps
            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            params = {
                "period1": start_ts,
                "period2": end_ts,
                "interval": "1d",
            }

            response = await self._rate_limited_request("GET", url, params=params)

            if response.status_code == 404:
                return []

            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]

            timestamps = result.get("timestamp", [])
            quote = result.get("indicators", {}).get("quote", [{}])[0]

            historical_data = []
            for i, ts in enumerate(timestamps):
                historical_data.append({
                    "symbol": symbol,
                    "date": datetime.fromtimestamp(ts).isoformat(),
                    "open": quote.get("open", [])[i] if i < len(quote.get("open", [])) else None,
                    "high": quote.get("high", [])[i] if i < len(quote.get("high", [])) else None,
                    "low": quote.get("low", [])[i] if i < len(quote.get("low", [])) else None,
                    "close": quote.get("close", [])[i] if i < len(quote.get("close", [])) else None,
                    "volume": quote.get("volume", [])[i] if i < len(quote.get("volume", [])) else None,
                })

            return historical_data

        except Exception as e:
            self.logger.error(f"Error fetching Yahoo historical for {symbol}: {e}")
            return []

    async def fetch_polygon_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch quote data from Polygon.io.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Quote data
        """
        if not self.polygon_api_key:
            raise IngestionError("Polygon API key required")

        try:
            url = f"{self.POLYGON_BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
            params = {"apiKey": self.polygon_api_key}

            response = await self._rate_limited_request("GET", url, params=params)

            if response.status_code == 404:
                return {"error": "Symbol not found", "symbol": symbol}

            data = response.json()
            ticker = data.get("ticker", {})

            return {
                "symbol": symbol,
                "current_price": ticker.get("lastTrade", {}).get("p"),
                "previous_close": ticker.get("prevDay", {}).get("c"),
                "volume": ticker.get("day", {}).get("v"),
                "market_cap": ticker.get("marketCap"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error fetching Polygon quote for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}

    async def fetch_company_overview(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch company overview data.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Company overview data
        """
        # Use Yahoo Finance for company info
        try:
            url = f"{self.YAHOO_BASE_URL}/quoteSummary/{symbol}"
            params = {
                "modules": "assetProfile,financialData,defaultKeyStatistics",
            }

            response = await self._rate_limited_request("GET", url, params=params)

            if response.status_code == 404:
                return {"error": "Symbol not found", "symbol": symbol}

            data = response.json()
            result = data.get("quoteSummary", {}).get("result", [{}])[0]

            profile = result.get("assetProfile", {})
            financial_data = result.get("financialData", {})
            key_stats = result.get("defaultKeyStatistics", {})

            return {
                "symbol": symbol,
                "company_name": profile.get("longBusinessSummary"),
                "industry": profile.get("industry"),
                "sector": profile.get("sector"),
                "employees": profile.get("fullTimeEmployees"),
                "market_cap": key_stats.get("marketCap", {}).get("raw"),
                "enterprise_value": key_stats.get("enterpriseValue", {}).get("raw"),
                "total_cash": financial_data.get("totalCash", {}).get("raw"),
                "total_debt": financial_data.get("totalDebt", {}).get("raw"),
                "revenue": financial_data.get("totalRevenue", {}).get("raw"),
                "cash_per_share": financial_data.get("cashPerShare", {}).get("raw"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error fetching company overview for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}

    def detect_volume_anomaly(
        self,
        recent_volumes: List[float],
        current_volume: float,
        threshold: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Detect trading volume anomalies.

        Args:
            recent_volumes: List of recent volume values
            current_volume: Current volume
            threshold: Standard deviations for anomaly detection

        Returns:
            Anomaly details if detected
        """
        if len(recent_volumes) < 5:
            return None

        mean_volume = statistics.mean(recent_volumes)
        std_volume = statistics.stdev(recent_volumes)

        if std_volume == 0:
            return None

        z_score = (current_volume - mean_volume) / std_volume

        if abs(z_score) > threshold:
            return {
                "current_volume": current_volume,
                "mean_volume": mean_volume,
                "std_volume": std_volume,
                "z_score": z_score,
                "is_anomaly": True,
                "anomaly_type": "high_volume" if z_score > 0 else "low_volume",
            }

        return None

    def calculate_price_change(
        self,
        historical_prices: List[Dict[str, Any]],
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate price change metrics.

        Args:
            historical_prices: List of historical price data
            period_days: Period for calculation

        Returns:
            Price change metrics
        """
        if len(historical_prices) < 2:
            return {}

        # Sort by date
        sorted_prices = sorted(
            historical_prices,
            key=lambda x: x.get("date", ""),
            reverse=True
        )

        current = sorted_prices[0].get("close")
        if not current:
            return {}

        # Find price from period_days ago
        target_date = datetime.utcnow() - timedelta(days=period_days)
        previous = None

        for price_data in sorted_prices:
            price_date = datetime.fromisoformat(price_data.get("date", ""))
            if price_date <= target_date:
                previous = price_data.get("close")
                break

        if not previous:
            previous = sorted_prices[-1].get("close")

        if previous and previous != 0:
            change_pct = ((current - previous) / previous) * 100

            return {
                "current_price": current,
                "previous_price": previous,
                "change": current - previous,
                "change_pct": round(change_pct, 2),
                "period_days": period_days,
            }

        return {}

    async def fetch_latest(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch latest financial data.

        Returns:
            List of raw financial data
        """
        symbols = kwargs.get("symbols", [])
        if not symbols:
            self.logger.warning("No symbols provided for financial data ingestion")
            return []

        all_data = []

        for symbol in symbols:
            try:
                # Fetch current quote
                if self.provider == "yahoo":
                    quote = await self.fetch_yahoo_quote(symbol)
                elif self.provider == "polygon":
                    quote = await self.fetch_polygon_quote(symbol)
                else:
                    self.logger.warning(f"Unknown provider: {self.provider}")
                    continue

                if "error" not in quote:
                    all_data.append({
                        "type": "quote",
                        "symbol": symbol,
                        "data": quote,
                    })

                # Fetch company overview periodically
                overview = await self.fetch_company_overview(symbol)
                if "error" not in overview:
                    all_data.append({
                        "type": "overview",
                        "symbol": symbol,
                        "data": overview,
                    })

                # Small delay between symbols
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error fetching data for {symbol}: {e}")
                continue

        return all_data

    async def fetch_historical(
        self,
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical financial data.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of raw financial data
        """
        symbols = kwargs.get("symbols", [])
        if not symbols:
            self.logger.warning("No symbols provided for historical data ingestion")
            return []

        all_data = []

        for symbol in symbols:
            try:
                # Fetch historical prices
                if self.provider == "yahoo":
                    historical = await self.fetch_yahoo_historical(
                        symbol, start_date, end_date
                    )
                else:
                    self.logger.warning(f"Historical data not implemented for {self.provider}")
                    continue

                for price_data in historical:
                    all_data.append({
                        "type": "historical_price",
                        "symbol": symbol,
                        "data": price_data,
                    })

                # Small delay between symbols
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error fetching historical data for {symbol}: {e}")
                continue

        return all_data

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform financial data to internal schema.

        Args:
            raw_data: Raw financial data

        Returns:
            Normalized financial data
        """
        data_type = raw_data.get("type")
        symbol = raw_data.get("symbol")
        data = raw_data.get("data", {})

        base_record = {
            "source": "financial_data",
            "entity_type": f"financial_{data_type}",
            "symbol": symbol,
            "ingestion_timestamp": datetime.utcnow().isoformat(),
        }

        if data_type == "quote":
            base_record.update({
                "current_price": data.get("current_price"),
                "previous_close": data.get("previous_close"),
                "market_cap": data.get("market_cap"),
                "volume": data.get("volume"),
                "currency": data.get("currency"),
                "exchange": data.get("exchange"),
            })

        elif data_type == "overview":
            base_record.update({
                "company_name": data.get("company_name"),
                "industry": data.get("industry"),
                "sector": data.get("sector"),
                "market_cap": data.get("market_cap"),
                "enterprise_value": data.get("enterprise_value"),
                "total_cash": data.get("total_cash"),
                "total_debt": data.get("total_debt"),
                "revenue": data.get("revenue"),
                "cash_per_share": data.get("cash_per_share"),
            })

        elif data_type == "historical_price":
            base_record.update({
                "date": data.get("date"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close"),
                "volume": data.get("volume"),
            })

        return base_record

    async def health_check(self) -> Dict[str, Any]:
        """Check financial data provider health."""
        try:
            # Test with a common symbol
            if self.provider == "yahoo":
                response = await self.fetch_yahoo_quote("AAPL")
            elif self.provider == "polygon":
                response = await self.fetch_polygon_quote("AAPL")
            else:
                return {
                    "source": self.source_name,
                    "status": "unknown",
                    "error": f"Unknown provider: {self.provider}",
                }

            status = "healthy" if "error" not in response else "degraded"

            return {
                "source": self.source_name,
                "status": status,
                "provider": self.provider,
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
