"""
Prefect orchestration module for biotech M&A predictor.

This module provides workflow orchestration for:
- Data ingestion from multiple sources
- Signal processing and aggregation
- Company scoring and acquirer matching
- Report generation and alerting
"""

from src.orchestration.flows import (
    # Data ingestion flows
    ingest_sec_filings,
    ingest_clinical_trials,
    ingest_fda_data,
    ingest_financial_data,
    # Processing flows
    process_signals,
    update_company_scores,
    match_acquirers,
    # Report flows
    generate_daily_digest,
    generate_weekly_watchlist,
    generate_alert_report,
)

from src.orchestration.tasks import (
    # Data ingestion tasks
    fetch_sec_filings_task,
    fetch_clinical_trials_task,
    fetch_fda_approvals_task,
    fetch_market_data_task,
    # Processing tasks
    aggregate_signals_task,
    calculate_company_score_task,
    run_matching_algorithm_task,
    # Report tasks
    generate_report_task,
    send_notification_task,
)

__all__ = [
    # Flows
    "ingest_sec_filings",
    "ingest_clinical_trials",
    "ingest_fda_data",
    "ingest_financial_data",
    "process_signals",
    "update_company_scores",
    "match_acquirers",
    "generate_daily_digest",
    "generate_weekly_watchlist",
    "generate_alert_report",
    # Tasks
    "fetch_sec_filings_task",
    "fetch_clinical_trials_task",
    "fetch_fda_approvals_task",
    "fetch_market_data_task",
    "aggregate_signals_task",
    "calculate_company_score_task",
    "run_matching_algorithm_task",
    "generate_report_task",
    "send_notification_task",
]
