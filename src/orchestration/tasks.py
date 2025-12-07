"""
Reusable Prefect tasks for biotech M&A predictor workflows.

Tasks are atomic units of work with retry logic, caching, and error handling.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from prefect import task
from prefect.cache_policies import INPUTS, TASK_SOURCE
from prefect.client.schemas.objects import TaskRunResult

logger = logging.getLogger(__name__)


# ============================================================================
# DATA INGESTION TASKS
# ============================================================================

@task(
    name="fetch-sec-filings",
    description="Fetch SEC EDGAR filings (Form 4, 13F, 8-K)",
    retries=3,
    retry_delay_seconds=[60, 300, 900],  # 1min, 5min, 15min exponential backoff
    cache_policy=INPUTS + TASK_SOURCE,
    cache_expiration=timedelta(hours=6),
    tags=["data-ingestion", "sec"],
)
def fetch_sec_filings_task(
    filing_types: List[str],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    cik_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch SEC EDGAR filings for specified types and date range.

    Args:
        filing_types: List of filing types (e.g., ['4', '13F', '8-K'])
        start_date: Start date for filing search
        end_date: End date for filing search
        cik_list: Optional list of CIK numbers to filter

    Returns:
        Dictionary containing filings data and metadata
    """
    logger.info(f"Fetching SEC filings: {filing_types} from {start_date} to {end_date}")

    try:
        # Import here to avoid circular dependencies
        from src.data_sources.sec_edgar import SECEdgarClient

        client = SECEdgarClient()
        filings = []

        for filing_type in filing_types:
            logger.info(f"Processing filing type: {filing_type}")
            results = client.fetch_filings(
                filing_type=filing_type,
                start_date=start_date or datetime.now() - timedelta(days=1),
                end_date=end_date or datetime.now(),
                cik_list=cik_list,
            )
            filings.extend(results)

        logger.info(f"Successfully fetched {len(filings)} SEC filings")

        return {
            "filings": filings,
            "count": len(filings),
            "filing_types": filing_types,
            "fetched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching SEC filings: {str(e)}")
        raise


@task(
    name="fetch-clinical-trials",
    description="Fetch updates from ClinicalTrials.gov",
    retries=3,
    retry_delay_seconds=[60, 300, 900],
    cache_policy=INPUTS + TASK_SOURCE,
    cache_expiration=timedelta(hours=12),
    tags=["data-ingestion", "clinical-trials"],
)
def fetch_clinical_trials_task(
    conditions: Optional[List[str]] = None,
    sponsors: Optional[List[str]] = None,
    updated_since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch clinical trial data from ClinicalTrials.gov.

    Args:
        conditions: List of conditions/diseases to filter
        sponsors: List of sponsor organizations
        updated_since: Fetch trials updated since this date

    Returns:
        Dictionary containing clinical trials data and metadata
    """
    logger.info(f"Fetching clinical trials updated since {updated_since}")

    try:
        from src.data_sources.clinical_trials import ClinicalTrialsClient

        client = ClinicalTrialsClient()
        trials = client.fetch_trials(
            conditions=conditions,
            sponsors=sponsors,
            updated_since=updated_since or datetime.now() - timedelta(days=1),
        )

        logger.info(f"Successfully fetched {len(trials)} clinical trials")

        return {
            "trials": trials,
            "count": len(trials),
            "conditions": conditions,
            "fetched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching clinical trials: {str(e)}")
        raise


@task(
    name="fetch-fda-approvals",
    description="Fetch FDA approvals and regulatory letters",
    retries=3,
    retry_delay_seconds=[60, 300, 900],
    cache_policy=INPUTS + TASK_SOURCE,
    cache_expiration=timedelta(hours=12),
    tags=["data-ingestion", "fda"],
)
def fetch_fda_approvals_task(
    approval_types: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch FDA approval data and regulatory letters.

    Args:
        approval_types: Types of approvals (e.g., ['NDA', 'BLA', 'ANDA'])
        start_date: Start date for approval search
        end_date: End date for approval search

    Returns:
        Dictionary containing FDA approvals data and metadata
    """
    logger.info(f"Fetching FDA approvals from {start_date} to {end_date}")

    try:
        from src.data_sources.fda import FDAClient

        client = FDAClient()
        approvals = client.fetch_approvals(
            approval_types=approval_types or ["NDA", "BLA", "ANDA"],
            start_date=start_date or datetime.now() - timedelta(days=1),
            end_date=end_date or datetime.now(),
        )

        # Fetch regulatory letters
        letters = client.fetch_regulatory_letters(
            start_date=start_date or datetime.now() - timedelta(days=1),
            end_date=end_date or datetime.now(),
        )

        logger.info(f"Successfully fetched {len(approvals)} approvals and {len(letters)} letters")

        return {
            "approvals": approvals,
            "letters": letters,
            "approval_count": len(approvals),
            "letter_count": len(letters),
            "fetched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching FDA data: {str(e)}")
        raise


@task(
    name="fetch-market-data",
    description="Fetch financial market data",
    retries=3,
    retry_delay_seconds=[30, 120, 300],
    cache_policy=INPUTS + TASK_SOURCE,
    cache_expiration=timedelta(hours=1),
    tags=["data-ingestion", "market-data"],
)
def fetch_market_data_task(
    tickers: List[str],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    data_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch market data for specified tickers.

    Args:
        tickers: List of stock tickers
        start_date: Start date for market data
        end_date: End date for market data
        data_types: Types of data to fetch (e.g., ['price', 'volume', 'fundamentals'])

    Returns:
        Dictionary containing market data and metadata
    """
    logger.info(f"Fetching market data for {len(tickers)} tickers")

    try:
        from src.data_sources.market_data import MarketDataClient

        client = MarketDataClient()
        data_types = data_types or ["price", "volume"]
        market_data = {}

        for ticker in tickers:
            ticker_data = client.fetch_ticker_data(
                ticker=ticker,
                start_date=start_date or datetime.now() - timedelta(days=30),
                end_date=end_date or datetime.now(),
                data_types=data_types,
            )
            market_data[ticker] = ticker_data

        logger.info(f"Successfully fetched market data for {len(market_data)} tickers")

        return {
            "market_data": market_data,
            "tickers": tickers,
            "count": len(market_data),
            "fetched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        raise


# ============================================================================
# DATA STORAGE TASKS
# ============================================================================

@task(
    name="store-raw-data",
    description="Store raw data to database or data lake",
    retries=2,
    retry_delay_seconds=[30, 120],
    tags=["storage"],
)
def store_raw_data_task(
    data: Dict[str, Any],
    data_source: str,
    data_type: str,
) -> Dict[str, Any]:
    """
    Store raw ingested data to persistent storage.

    Args:
        data: Raw data to store
        data_source: Source of the data (e.g., 'sec', 'fda', 'clinical_trials')
        data_type: Type of data (e.g., 'filing', 'approval', 'trial')

    Returns:
        Storage metadata
    """
    logger.info(f"Storing {data_type} data from {data_source}")

    try:
        from src.storage.data_lake import DataLakeClient

        client = DataLakeClient()
        result = client.store_raw_data(
            data=data,
            source=data_source,
            data_type=data_type,
            timestamp=datetime.now(),
        )

        logger.info(f"Successfully stored data with ID: {result.get('storage_id')}")
        return result

    except Exception as e:
        logger.error(f"Error storing raw data: {str(e)}")
        raise


# ============================================================================
# SIGNAL PROCESSING TASKS
# ============================================================================

@task(
    name="aggregate-signals",
    description="Aggregate signals from multiple data sources",
    retries=2,
    retry_delay_seconds=[60, 300],
    tags=["processing", "signals"],
)
def aggregate_signals_task(
    company_id: str,
    signal_sources: List[str],
    time_window: timedelta,
) -> Dict[str, Any]:
    """
    Aggregate signals from multiple sources for a company.

    Args:
        company_id: Company identifier
        signal_sources: List of signal sources to aggregate
        time_window: Time window for signal aggregation

    Returns:
        Aggregated signals data
    """
    logger.info(f"Aggregating signals for company {company_id}")

    try:
        from src.signals.aggregator import SignalAggregator

        aggregator = SignalAggregator()
        signals = aggregator.aggregate(
            company_id=company_id,
            sources=signal_sources,
            start_time=datetime.now() - time_window,
            end_time=datetime.now(),
        )

        logger.info(f"Aggregated {len(signals)} signals for company {company_id}")

        return {
            "company_id": company_id,
            "signals": signals,
            "signal_count": len(signals),
            "aggregated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error aggregating signals for {company_id}: {str(e)}")
        raise


@task(
    name="publish-event",
    description="Publish event to event stream",
    retries=3,
    retry_delay_seconds=[10, 30, 60],
    tags=["processing", "events"],
)
def publish_event_task(
    event_type: str,
    event_data: Dict[str, Any],
    priority: str = "normal",
) -> Dict[str, Any]:
    """
    Publish event to event stream for downstream processing.

    Args:
        event_type: Type of event (e.g., 'signal_detected', 'score_changed')
        event_data: Event payload data
        priority: Event priority ('low', 'normal', 'high')

    Returns:
        Event publication metadata
    """
    logger.info(f"Publishing {event_type} event with priority {priority}")

    try:
        from src.events.publisher import EventPublisher

        publisher = EventPublisher()
        result = publisher.publish(
            event_type=event_type,
            data=event_data,
            priority=priority,
            timestamp=datetime.now(),
        )

        logger.info(f"Successfully published event: {result.get('event_id')}")
        return result

    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")
        raise


# ============================================================================
# SCORING TASKS
# ============================================================================

@task(
    name="calculate-company-score",
    description="Calculate M&A attractiveness score for a company",
    retries=2,
    retry_delay_seconds=[30, 120],
    cache_policy=INPUTS + TASK_SOURCE,
    cache_expiration=timedelta(hours=1),
    tags=["processing", "scoring"],
)
def calculate_company_score_task(
    company_id: str,
    signals: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Calculate M&A attractiveness score for a company.

    Args:
        company_id: Company identifier
        signals: Aggregated signals data
        weights: Optional custom weights for scoring components

    Returns:
        Company score data
    """
    logger.info(f"Calculating M&A score for company {company_id}")

    try:
        from src.scoring.calculator import ScoreCalculator

        calculator = ScoreCalculator(weights=weights)
        score_result = calculator.calculate(
            company_id=company_id,
            signals=signals,
        )

        logger.info(
            f"Calculated score {score_result['score']:.2f} for company {company_id}"
        )

        return {
            "company_id": company_id,
            "score": score_result["score"],
            "components": score_result["components"],
            "confidence": score_result["confidence"],
            "calculated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error calculating score for {company_id}: {str(e)}")
        raise


@task(
    name="update-score-history",
    description="Update score history in database",
    retries=2,
    retry_delay_seconds=[30, 120],
    tags=["storage", "scoring"],
)
def update_score_history_task(
    company_id: str,
    score_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Store score in history and detect significant changes.

    Args:
        company_id: Company identifier
        score_data: Score calculation results

    Returns:
        Update metadata including change detection
    """
    logger.info(f"Updating score history for company {company_id}")

    try:
        from src.storage.database import DatabaseClient

        db = DatabaseClient()

        # Store new score
        db.store_score(
            company_id=company_id,
            score=score_data["score"],
            components=score_data["components"],
            timestamp=datetime.now(),
        )

        # Detect significant changes
        previous_score = db.get_latest_score(
            company_id=company_id,
            before=datetime.now() - timedelta(hours=24),
        )

        change_detected = False
        change_magnitude = 0.0

        if previous_score:
            change_magnitude = score_data["score"] - previous_score["score"]
            change_detected = abs(change_magnitude) > 10.0  # Threshold: 10 points

        logger.info(
            f"Score updated for {company_id}. Change: {change_magnitude:.2f}"
        )

        return {
            "company_id": company_id,
            "updated": True,
            "change_detected": change_detected,
            "change_magnitude": change_magnitude,
            "previous_score": previous_score.get("score") if previous_score else None,
            "current_score": score_data["score"],
        }

    except Exception as e:
        logger.error(f"Error updating score history for {company_id}: {str(e)}")
        raise


# ============================================================================
# MATCHING TASKS
# ============================================================================

@task(
    name="run-matching-algorithm",
    description="Run acquirer matching algorithm for a target company",
    retries=2,
    retry_delay_seconds=[60, 300],
    tags=["processing", "matching"],
)
def run_matching_algorithm_task(
    target_company_id: str,
    candidate_acquirers: Optional[List[str]] = None,
    min_score: float = 50.0,
) -> Dict[str, Any]:
    """
    Run matching algorithm to identify potential acquirers.

    Args:
        target_company_id: Target company identifier
        candidate_acquirers: Optional list of candidate acquirer IDs
        min_score: Minimum matching score threshold

    Returns:
        Matching results with ranked acquirers
    """
    logger.info(f"Running matching algorithm for target {target_company_id}")

    try:
        from src.matching.algorithm import MatchingAlgorithm

        matcher = MatchingAlgorithm()
        matches = matcher.find_acquirers(
            target_id=target_company_id,
            candidates=candidate_acquirers,
            min_score=min_score,
        )

        logger.info(f"Found {len(matches)} potential acquirers for {target_company_id}")

        return {
            "target_company_id": target_company_id,
            "matches": matches,
            "match_count": len(matches),
            "matched_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error running matching algorithm: {str(e)}")
        raise


# ============================================================================
# REPORT GENERATION TASKS
# ============================================================================

@task(
    name="generate-report",
    description="Generate report from template and data",
    retries=2,
    retry_delay_seconds=[30, 120],
    tags=["reporting"],
)
def generate_report_task(
    report_type: str,
    data: Dict[str, Any],
    format: str = "html",
) -> Dict[str, Any]:
    """
    Generate report from template and data.

    Args:
        report_type: Type of report (e.g., 'daily_digest', 'watchlist', 'alert')
        data: Data for report generation
        format: Output format ('html', 'pdf', 'json')

    Returns:
        Generated report content and metadata
    """
    logger.info(f"Generating {report_type} report in {format} format")

    try:
        from src.reporting.generator import ReportGenerator

        generator = ReportGenerator()
        report = generator.generate(
            report_type=report_type,
            data=data,
            format=format,
        )

        logger.info(f"Successfully generated {report_type} report")

        return {
            "report_type": report_type,
            "format": format,
            "content": report["content"],
            "metadata": report["metadata"],
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise


@task(
    name="send-notification",
    description="Send notification via configured channels",
    retries=3,
    retry_delay_seconds=[30, 120, 300],
    tags=["notification"],
)
def send_notification_task(
    notification_type: str,
    recipients: List[str],
    content: Dict[str, Any],
    channels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send notification to recipients via configured channels.

    Args:
        notification_type: Type of notification (e.g., 'alert', 'digest', 'report')
        recipients: List of recipient identifiers
        content: Notification content
        channels: Delivery channels (e.g., ['email', 'slack', 'webhook'])

    Returns:
        Notification delivery status
    """
    logger.info(f"Sending {notification_type} notification to {len(recipients)} recipients")

    try:
        from src.notifications.sender import NotificationSender

        sender = NotificationSender()
        channels = channels or ["email"]

        results = sender.send(
            notification_type=notification_type,
            recipients=recipients,
            content=content,
            channels=channels,
        )

        logger.info(f"Successfully sent notification via {channels}")

        return {
            "notification_type": notification_type,
            "recipients": recipients,
            "channels": channels,
            "status": results,
            "sent_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        raise


# ============================================================================
# UTILITY TASKS
# ============================================================================

@task(
    name="get-active-companies",
    description="Get list of active companies to process",
    cache_policy=TASK_SOURCE,
    cache_expiration=timedelta(hours=1),
    tags=["utility"],
)
def get_active_companies_task(
    status: str = "active",
    min_score: Optional[float] = None,
) -> List[str]:
    """
    Retrieve list of active companies for processing.

    Args:
        status: Company status filter
        min_score: Optional minimum M&A score filter

    Returns:
        List of company IDs
    """
    logger.info(f"Retrieving {status} companies")

    try:
        from src.storage.database import DatabaseClient

        db = DatabaseClient()
        companies = db.get_companies(
            status=status,
            min_score=min_score,
        )

        company_ids = [c["id"] for c in companies]
        logger.info(f"Retrieved {len(company_ids)} companies")

        return company_ids

    except Exception as e:
        logger.error(f"Error retrieving companies: {str(e)}")
        raise


@task(
    name="get-top-scored-companies",
    description="Get top-scored companies for watchlist",
    cache_policy=TASK_SOURCE,
    cache_expiration=timedelta(hours=6),
    tags=["utility"],
)
def get_top_scored_companies_task(
    limit: int = 50,
    min_score: float = 60.0,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-scored companies for watchlist generation.

    Args:
        limit: Maximum number of companies to return
        min_score: Minimum M&A score threshold

    Returns:
        List of company data dictionaries
    """
    logger.info(f"Retrieving top {limit} scored companies (min score: {min_score})")

    try:
        from src.storage.database import DatabaseClient

        db = DatabaseClient()
        companies = db.get_top_companies(
            limit=limit,
            min_score=min_score,
            order_by="score",
        )

        logger.info(f"Retrieved {len(companies)} top-scored companies")
        return companies

    except Exception as e:
        logger.error(f"Error retrieving top-scored companies: {str(e)}")
        raise
