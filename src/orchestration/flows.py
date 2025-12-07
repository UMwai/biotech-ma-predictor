"""
Main Prefect flows for biotech M&A predictor orchestration.

Flows orchestrate tasks into complete workflows with proper error handling,
logging, and event-driven triggers.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from src.orchestration.tasks import (
    # Data ingestion
    fetch_sec_filings_task,
    fetch_clinical_trials_task,
    fetch_fda_approvals_task,
    fetch_market_data_task,
    store_raw_data_task,
    # Signal processing
    aggregate_signals_task,
    publish_event_task,
    # Scoring
    calculate_company_score_task,
    update_score_history_task,
    # Matching
    run_matching_algorithm_task,
    # Reporting
    generate_report_task,
    send_notification_task,
    # Utilities
    get_active_companies_task,
    get_top_scored_companies_task,
)

logger = logging.getLogger(__name__)


# ============================================================================
# DATA INGESTION FLOWS
# ============================================================================

@flow(
    name="ingest-sec-filings",
    description="Ingest SEC EDGAR filings and store to data lake",
    retries=1,
    retry_delay_seconds=300,
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
def ingest_sec_filings(
    filing_types: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    cik_list: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch SEC EDGAR filings and store to data lake.

    Args:
        filing_types: List of filing types to fetch (default: ['4', '13F', '8-K'])
        start_date: Start date for filing search
        end_date: End date for filing search
        cik_list: Optional list of CIK numbers to filter

    Returns:
        Ingestion summary with counts and status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting SEC filings ingestion flow")

    # Default to common M&A-relevant filing types
    filing_types = filing_types or ["4", "13F", "8-K"]
    start_date = start_date or datetime.now() - timedelta(days=1)
    end_date = end_date or datetime.now()

    try:
        # Fetch SEC filings
        filings_data = fetch_sec_filings_task(
            filing_types=filing_types,
            start_date=start_date,
            end_date=end_date,
            cik_list=cik_list,
        )

        run_logger.info(f"Fetched {filings_data['count']} SEC filings")

        # Store raw data
        storage_result = store_raw_data_task(
            data=filings_data,
            data_source="sec_edgar",
            data_type="filing",
        )

        # Publish event for downstream processing
        event_result = publish_event_task(
            event_type="sec_filings_ingested",
            event_data={
                "filing_count": filings_data["count"],
                "filing_types": filing_types,
                "storage_id": storage_result.get("storage_id"),
            },
            priority="normal",
        )

        run_logger.info("SEC filings ingestion completed successfully")

        return {
            "status": "success",
            "filing_count": filings_data["count"],
            "filing_types": filing_types,
            "storage_id": storage_result.get("storage_id"),
            "event_id": event_result.get("event_id"),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"SEC filings ingestion failed: {str(e)}")

        # Send error notification
        send_notification_task(
            notification_type="error_alert",
            recipients=["data-team@example.com"],
            content={
                "flow": "ingest_sec_filings",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="ingest-clinical-trials",
    description="Ingest clinical trial updates from ClinicalTrials.gov",
    retries=1,
    retry_delay_seconds=300,
    log_prints=True,
)
def ingest_clinical_trials(
    conditions: Optional[List[str]] = None,
    sponsors: Optional[List[str]] = None,
    updated_since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch clinical trial updates and store to data lake.

    Args:
        conditions: List of conditions/diseases to filter
        sponsors: List of sponsor organizations
        updated_since: Fetch trials updated since this date

    Returns:
        Ingestion summary with counts and status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting clinical trials ingestion flow")

    updated_since = updated_since or datetime.now() - timedelta(days=1)

    try:
        # Fetch clinical trials
        trials_data = fetch_clinical_trials_task(
            conditions=conditions,
            sponsors=sponsors,
            updated_since=updated_since,
        )

        run_logger.info(f"Fetched {trials_data['count']} clinical trials")

        # Store raw data
        storage_result = store_raw_data_task(
            data=trials_data,
            data_source="clinical_trials",
            data_type="trial",
        )

        # Publish event
        event_result = publish_event_task(
            event_type="clinical_trials_ingested",
            event_data={
                "trial_count": trials_data["count"],
                "storage_id": storage_result.get("storage_id"),
            },
            priority="normal",
        )

        run_logger.info("Clinical trials ingestion completed successfully")

        return {
            "status": "success",
            "trial_count": trials_data["count"],
            "storage_id": storage_result.get("storage_id"),
            "event_id": event_result.get("event_id"),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Clinical trials ingestion failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["data-team@example.com"],
            content={
                "flow": "ingest_clinical_trials",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="ingest-fda-data",
    description="Ingest FDA approval and regulatory data",
    retries=1,
    retry_delay_seconds=300,
    log_prints=True,
)
def ingest_fda_data(
    approval_types: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch FDA approvals and regulatory letters.

    Args:
        approval_types: Types of approvals to fetch
        start_date: Start date for approval search
        end_date: End date for approval search

    Returns:
        Ingestion summary with counts and status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting FDA data ingestion flow")

    start_date = start_date or datetime.now() - timedelta(days=1)
    end_date = end_date or datetime.now()

    try:
        # Fetch FDA data
        fda_data = fetch_fda_approvals_task(
            approval_types=approval_types,
            start_date=start_date,
            end_date=end_date,
        )

        run_logger.info(
            f"Fetched {fda_data['approval_count']} approvals "
            f"and {fda_data['letter_count']} regulatory letters"
        )

        # Store raw data
        storage_result = store_raw_data_task(
            data=fda_data,
            data_source="fda",
            data_type="approval",
        )

        # Publish event
        event_result = publish_event_task(
            event_type="fda_data_ingested",
            event_data={
                "approval_count": fda_data["approval_count"],
                "letter_count": fda_data["letter_count"],
                "storage_id": storage_result.get("storage_id"),
            },
            priority="normal",
        )

        run_logger.info("FDA data ingestion completed successfully")

        return {
            "status": "success",
            "approval_count": fda_data["approval_count"],
            "letter_count": fda_data["letter_count"],
            "storage_id": storage_result.get("storage_id"),
            "event_id": event_result.get("event_id"),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"FDA data ingestion failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["data-team@example.com"],
            content={
                "flow": "ingest_fda_data",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="ingest-financial-data",
    description="Ingest financial market data for tracked companies",
    retries=1,
    retry_delay_seconds=300,
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
def ingest_financial_data(
    tickers: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Fetch financial market data for companies.

    Args:
        tickers: List of stock tickers (if None, fetches for all active companies)
        start_date: Start date for market data
        end_date: End date for market data

    Returns:
        Ingestion summary with counts and status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting financial data ingestion flow")

    start_date = start_date or datetime.now() - timedelta(days=30)
    end_date = end_date or datetime.now()

    try:
        # If no tickers provided, get all active companies
        if not tickers:
            run_logger.info("Fetching tickers for active companies")
            from src.database.client import DatabaseClient

            db = DatabaseClient()
            companies = db.get_companies(status="active")
            tickers = [c.get("ticker") for c in companies if c.get("ticker")]

        run_logger.info(f"Fetching market data for {len(tickers)} tickers")

        # Fetch market data
        market_data = fetch_market_data_task(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            data_types=["price", "volume", "fundamentals"],
        )

        run_logger.info(f"Fetched market data for {market_data['count']} tickers")

        # Store raw data
        storage_result = store_raw_data_task(
            data=market_data,
            data_source="market_data",
            data_type="price_data",
        )

        # Publish event
        event_result = publish_event_task(
            event_type="market_data_ingested",
            event_data={
                "ticker_count": market_data["count"],
                "storage_id": storage_result.get("storage_id"),
            },
            priority="normal",
        )

        run_logger.info("Financial data ingestion completed successfully")

        return {
            "status": "success",
            "ticker_count": market_data["count"],
            "tickers": tickers,
            "storage_id": storage_result.get("storage_id"),
            "event_id": event_result.get("event_id"),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Financial data ingestion failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["data-team@example.com"],
            content={
                "flow": "ingest_financial_data",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


# ============================================================================
# PROCESSING FLOWS
# ============================================================================

@flow(
    name="process-signals",
    description="Aggregate signals and publish events for company analysis",
    retries=1,
    retry_delay_seconds=180,
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
def process_signals(
    company_ids: Optional[List[str]] = None,
    signal_sources: Optional[List[str]] = None,
    time_window: Optional[timedelta] = None,
) -> Dict[str, Any]:
    """
    Aggregate signals from multiple sources and publish events.

    Args:
        company_ids: List of company IDs to process (if None, processes all active)
        signal_sources: Sources to aggregate (default: all sources)
        time_window: Time window for signal aggregation

    Returns:
        Processing summary with counts and status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting signal processing flow")

    signal_sources = signal_sources or ["sec", "fda", "clinical_trials", "market_data"]
    time_window = time_window or timedelta(days=7)

    try:
        # Get active companies if not specified
        if not company_ids:
            company_ids = get_active_companies_task(status="active")

        run_logger.info(f"Processing signals for {len(company_ids)} companies")

        # Process signals for each company concurrently
        signal_results = []
        event_results = []

        for company_id in company_ids:
            # Aggregate signals
            signals = aggregate_signals_task(
                company_id=company_id,
                signal_sources=signal_sources,
                time_window=time_window,
            )

            signal_results.append(signals)

            # Publish event if significant signals detected
            if signals["signal_count"] > 0:
                event = publish_event_task(
                    event_type="signals_aggregated",
                    event_data={
                        "company_id": company_id,
                        "signal_count": signals["signal_count"],
                        "sources": signal_sources,
                    },
                    priority="normal",
                )
                event_results.append(event)

        total_signals = sum(s["signal_count"] for s in signal_results)
        run_logger.info(
            f"Processed {total_signals} signals for {len(company_ids)} companies"
        )

        return {
            "status": "success",
            "company_count": len(company_ids),
            "total_signals": total_signals,
            "events_published": len(event_results),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Signal processing failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["analytics-team@example.com"],
            content={
                "flow": "process_signals",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="update-company-scores",
    description="Recalculate M&A attractiveness scores for companies",
    retries=1,
    retry_delay_seconds=180,
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
def update_company_scores(
    company_ids: Optional[List[str]] = None,
    min_signal_count: int = 1,
) -> Dict[str, Any]:
    """
    Calculate and update M&A scores for companies.

    Args:
        company_ids: List of company IDs to score (if None, scores all active)
        min_signal_count: Minimum signals required to trigger scoring

    Returns:
        Scoring summary with counts and significant changes
    """
    run_logger = get_run_logger()
    run_logger.info("Starting company scoring flow")

    try:
        # Get active companies if not specified
        if not company_ids:
            company_ids = get_active_companies_task(status="active")

        run_logger.info(f"Calculating scores for {len(company_ids)} companies")

        score_results = []
        significant_changes = []

        for company_id in company_ids:
            # Get signals for scoring
            signals = aggregate_signals_task(
                company_id=company_id,
                signal_sources=["sec", "fda", "clinical_trials", "market_data"],
                time_window=timedelta(days=30),
            )

            # Only score if minimum signals present
            if signals["signal_count"] >= min_signal_count:
                # Calculate score
                score_data = calculate_company_score_task(
                    company_id=company_id,
                    signals=signals,
                )

                # Update score history
                update_result = update_score_history_task(
                    company_id=company_id,
                    score_data=score_data,
                )

                score_results.append(update_result)

                # Track significant changes
                if update_result["change_detected"]:
                    significant_changes.append({
                        "company_id": company_id,
                        "previous_score": update_result["previous_score"],
                        "current_score": update_result["current_score"],
                        "change": update_result["change_magnitude"],
                    })

                    # Publish high-priority event for significant change
                    publish_event_task(
                        event_type="score_changed_significantly",
                        event_data={
                            "company_id": company_id,
                            "previous_score": update_result["previous_score"],
                            "current_score": update_result["current_score"],
                            "change": update_result["change_magnitude"],
                        },
                        priority="high",
                    )

        run_logger.info(
            f"Updated scores for {len(score_results)} companies. "
            f"Detected {len(significant_changes)} significant changes."
        )

        return {
            "status": "success",
            "companies_scored": len(score_results),
            "significant_changes": len(significant_changes),
            "changes": significant_changes,
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Company scoring failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["analytics-team@example.com"],
            content={
                "flow": "update_company_scores",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="match-acquirers",
    description="Run acquirer matching algorithm for high-scoring targets",
    retries=1,
    retry_delay_seconds=180,
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
def match_acquirers(
    target_company_ids: Optional[List[str]] = None,
    min_target_score: float = 60.0,
    min_match_score: float = 50.0,
) -> Dict[str, Any]:
    """
    Match potential acquirers with target companies.

    Args:
        target_company_ids: List of target company IDs (if None, uses high-scoring targets)
        min_target_score: Minimum M&A score for targets
        min_match_score: Minimum matching score threshold

    Returns:
        Matching summary with counts and top matches
    """
    run_logger = get_run_logger()
    run_logger.info("Starting acquirer matching flow")

    try:
        # Get high-scoring targets if not specified
        if not target_company_ids:
            top_companies = get_top_scored_companies_task(
                limit=100,
                min_score=min_target_score,
            )
            target_company_ids = [c["id"] for c in top_companies]

        run_logger.info(f"Matching acquirers for {len(target_company_ids)} targets")

        matching_results = []
        total_matches = 0

        for target_id in target_company_ids:
            # Run matching algorithm
            match_result = run_matching_algorithm_task(
                target_company_id=target_id,
                min_score=min_match_score,
            )

            matching_results.append(match_result)
            total_matches += match_result["match_count"]

            # Publish event with match results
            if match_result["match_count"] > 0:
                publish_event_task(
                    event_type="acquirers_matched",
                    event_data={
                        "target_company_id": target_id,
                        "match_count": match_result["match_count"],
                        "top_matches": match_result["matches"][:5],  # Top 5
                    },
                    priority="normal",
                )

        run_logger.info(
            f"Matched {total_matches} potential acquirers "
            f"for {len(target_company_ids)} targets"
        )

        return {
            "status": "success",
            "target_count": len(target_company_ids),
            "total_matches": total_matches,
            "avg_matches_per_target": total_matches / len(target_company_ids) if target_company_ids else 0,
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Acquirer matching failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["analytics-team@example.com"],
            content={
                "flow": "match_acquirers",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


# ============================================================================
# REPORT FLOWS
# ============================================================================

@flow(
    name="generate-daily-digest",
    description="Generate and send daily M&A digest report",
    retries=1,
    retry_delay_seconds=120,
    log_prints=True,
)
def generate_daily_digest(
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate daily digest report with recent activity and insights.

    Args:
        recipients: List of recipient email addresses

    Returns:
        Report generation and delivery status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting daily digest generation flow")

    recipients = recipients or ["team@example.com"]

    try:
        # Gather data for digest
        run_logger.info("Gathering digest data")

        # Get top-scored companies
        top_companies = get_top_scored_companies_task(
            limit=20,
            min_score=50.0,
        )

        # Get recent significant changes (last 24 hours)
        from src.database.client import DatabaseClient

        db = DatabaseClient()
        recent_changes = db.get_score_changes(
            since=datetime.now() - timedelta(days=1),
            min_change=10.0,
        )

        # Get recent signals
        recent_signals = db.get_recent_signals(
            since=datetime.now() - timedelta(days=1),
        )

        # Generate digest report
        report = generate_report_task(
            report_type="daily_digest",
            data={
                "date": datetime.now().date().isoformat(),
                "top_companies": top_companies,
                "recent_changes": recent_changes,
                "recent_signals": recent_signals,
                "summary_stats": {
                    "total_active_companies": len(get_active_companies_task()),
                    "companies_with_changes": len(recent_changes),
                    "total_signals": len(recent_signals),
                },
            },
            format="html",
        )

        run_logger.info("Daily digest report generated")

        # Send notification
        notification_result = send_notification_task(
            notification_type="daily_digest",
            recipients=recipients,
            content={
                "subject": f"Daily M&A Digest - {datetime.now().strftime('%Y-%m-%d')}",
                "html_body": report["content"],
            },
            channels=["email"],
        )

        run_logger.info(f"Daily digest sent to {len(recipients)} recipients")

        return {
            "status": "success",
            "report_generated": True,
            "recipients": len(recipients),
            "top_companies_count": len(top_companies),
            "recent_changes_count": len(recent_changes),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Daily digest generation failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["ops-team@example.com"],
            content={
                "flow": "generate_daily_digest",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="generate-weekly-watchlist",
    description="Generate weekly ranked watchlist report",
    retries=1,
    retry_delay_seconds=120,
    log_prints=True,
)
def generate_weekly_watchlist(
    recipients: Optional[List[str]] = None,
    top_n: int = 50,
) -> Dict[str, Any]:
    """
    Generate weekly watchlist with top-ranked M&A targets.

    Args:
        recipients: List of recipient email addresses
        top_n: Number of top companies to include

    Returns:
        Report generation and delivery status
    """
    run_logger = get_run_logger()
    run_logger.info("Starting weekly watchlist generation flow")

    recipients = recipients or ["team@example.com"]

    try:
        # Get top-scored companies
        top_companies = get_top_scored_companies_task(
            limit=top_n,
            min_score=60.0,
        )

        run_logger.info(f"Retrieved {len(top_companies)} companies for watchlist")

        # Get matching results for top companies
        matching_data = []
        for company in top_companies[:10]:  # Top 10 with matches
            matches = run_matching_algorithm_task(
                target_company_id=company["id"],
                min_score=50.0,
            )
            matching_data.append({
                "company": company,
                "matches": matches["matches"][:5],  # Top 5 matches
            })

        # Generate watchlist report
        report = generate_report_task(
            report_type="weekly_watchlist",
            data={
                "week_ending": datetime.now().date().isoformat(),
                "top_companies": top_companies,
                "matching_data": matching_data,
                "summary_stats": {
                    "total_companies": len(top_companies),
                    "avg_score": sum(c["score"] for c in top_companies) / len(top_companies),
                    "highest_score": max(c["score"] for c in top_companies),
                },
            },
            format="html",
        )

        run_logger.info("Weekly watchlist report generated")

        # Send notification
        notification_result = send_notification_task(
            notification_type="weekly_watchlist",
            recipients=recipients,
            content={
                "subject": f"Weekly M&A Watchlist - {datetime.now().strftime('%Y-%m-%d')}",
                "html_body": report["content"],
            },
            channels=["email"],
        )

        run_logger.info(f"Weekly watchlist sent to {len(recipients)} recipients")

        return {
            "status": "success",
            "report_generated": True,
            "recipients": len(recipients),
            "companies_included": len(top_companies),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Weekly watchlist generation failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["ops-team@example.com"],
            content={
                "flow": "generate_weekly_watchlist",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise


@flow(
    name="generate-alert-report",
    description="Generate alert report for significant score changes",
    retries=1,
    retry_delay_seconds=60,
    log_prints=True,
)
def generate_alert_report(
    company_id: str,
    change_data: Dict[str, Any],
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate and send alert report for significant score changes.

    This flow is typically triggered by events when significant changes are detected.

    Args:
        company_id: Company that triggered the alert
        change_data: Data about the score change
        recipients: List of recipient email addresses

    Returns:
        Report generation and delivery status
    """
    run_logger = get_run_logger()
    run_logger.info(f"Starting alert report generation for company {company_id}")

    recipients = recipients or ["alerts@example.com"]

    try:
        # Get company details
        from src.storage.database import DatabaseClient

        db = DatabaseClient()
        company = db.get_company(company_id)

        # Get recent signals that may have caused the change
        signals = aggregate_signals_task(
            company_id=company_id,
            signal_sources=["sec", "fda", "clinical_trials", "market_data"],
            time_window=timedelta(days=7),
        )

        # Get potential acquirers
        matches = run_matching_algorithm_task(
            target_company_id=company_id,
            min_score=50.0,
        )

        # Generate alert report
        report = generate_report_task(
            report_type="alert_report",
            data={
                "alert_time": datetime.now().isoformat(),
                "company": company,
                "change_data": change_data,
                "recent_signals": signals,
                "potential_acquirers": matches["matches"][:5],
            },
            format="html",
        )

        run_logger.info("Alert report generated")

        # Send high-priority notification
        notification_result = send_notification_task(
            notification_type="score_alert",
            recipients=recipients,
            content={
                "subject": f"ALERT: Significant Score Change - {company.get('name')}",
                "html_body": report["content"],
            },
            channels=["email", "slack"],
        )

        run_logger.info(f"Alert report sent to {len(recipients)} recipients")

        return {
            "status": "success",
            "company_id": company_id,
            "report_generated": True,
            "recipients": len(recipients),
            "score_change": change_data.get("change_magnitude"),
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        run_logger.error(f"Alert report generation failed: {str(e)}")

        send_notification_task(
            notification_type="error_alert",
            recipients=["ops-team@example.com"],
            content={
                "flow": "generate_alert_report",
                "company_id": company_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            channels=["email", "slack"],
        )

        raise
