"""
Prefect deployment configurations for biotech M&A predictor workflows.

This module defines deployment configurations with schedules, work pools,
and infrastructure settings for all orchestrated flows.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule as ServerCronSchedule

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

logger = logging.getLogger(__name__)


# ============================================================================
# DEPLOYMENT CONFIGURATIONS
# ============================================================================

# Default work pool and queue
DEFAULT_WORK_POOL = "biotech-ma-pool"
DEFAULT_WORK_QUEUE = "default"

# Common tags for organization
TAGS_DATA_INGESTION = ["data-ingestion", "etl"]
TAGS_PROCESSING = ["processing", "analytics"]
TAGS_REPORTING = ["reporting", "notifications"]


# ============================================================================
# DATA INGESTION DEPLOYMENTS
# ============================================================================

def create_sec_filings_deployment() -> Deployment:
    """
    Create deployment for SEC filings ingestion.

    Schedule: Every day at 7:00 AM ET (after market open)
    """
    deployment = Deployment.build_from_flow(
        flow=ingest_sec_filings,
        name="sec-filings-daily",
        version="1.0.0",
        description="Daily ingestion of SEC EDGAR filings (Form 4, 13F, 8-K)",
        tags=TAGS_DATA_INGESTION + ["sec", "edgar"],
        schedule=CronSchedule(
            cron="0 12 * * 1-5",  # 12:00 UTC = 7:00 AM ET (weekdays only)
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="data-ingestion",
        parameters={
            "filing_types": ["4", "13F", "8-K"],
            "start_date": None,  # Will use default (last 24 hours)
            "end_date": None,
            "cik_list": None,
        },
        is_schedule_active=True,
    )

    logger.info("SEC filings deployment created")
    return deployment


def create_clinical_trials_deployment() -> Deployment:
    """
    Create deployment for clinical trials ingestion.

    Schedule: Every day at 8:00 AM ET
    """
    deployment = Deployment.build_from_flow(
        flow=ingest_clinical_trials,
        name="clinical-trials-daily",
        version="1.0.0",
        description="Daily ingestion of ClinicalTrials.gov updates",
        tags=TAGS_DATA_INGESTION + ["clinical-trials"],
        schedule=CronSchedule(
            cron="0 13 * * *",  # 13:00 UTC = 8:00 AM ET (daily)
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="data-ingestion",
        parameters={
            "conditions": None,  # All conditions
            "sponsors": None,  # All sponsors
            "updated_since": None,  # Will use default (last 24 hours)
        },
        is_schedule_active=True,
    )

    logger.info("Clinical trials deployment created")
    return deployment


def create_fda_data_deployment() -> Deployment:
    """
    Create deployment for FDA data ingestion.

    Schedule: Every day at 9:00 AM ET
    """
    deployment = Deployment.build_from_flow(
        flow=ingest_fda_data,
        name="fda-data-daily",
        version="1.0.0",
        description="Daily ingestion of FDA approvals and regulatory letters",
        tags=TAGS_DATA_INGESTION + ["fda", "regulatory"],
        schedule=CronSchedule(
            cron="0 14 * * *",  # 14:00 UTC = 9:00 AM ET (daily)
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="data-ingestion",
        parameters={
            "approval_types": ["NDA", "BLA", "ANDA"],
            "start_date": None,  # Will use default (last 24 hours)
            "end_date": None,
        },
        is_schedule_active=True,
    )

    logger.info("FDA data deployment created")
    return deployment


def create_financial_data_deployment() -> Deployment:
    """
    Create deployment for financial market data ingestion.

    Schedule: Every day at 5:00 PM ET (after market close)
    """
    deployment = Deployment.build_from_flow(
        flow=ingest_financial_data,
        name="financial-data-daily",
        version="1.0.0",
        description="Daily ingestion of financial market data",
        tags=TAGS_DATA_INGESTION + ["market-data", "financial"],
        schedule=CronSchedule(
            cron="0 22 * * 1-5",  # 22:00 UTC = 5:00 PM ET (weekdays only)
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="data-ingestion",
        parameters={
            "tickers": None,  # Will fetch for all active companies
            "start_date": None,  # Will use default (last 30 days)
            "end_date": None,
        },
        is_schedule_active=True,
    )

    logger.info("Financial data deployment created")
    return deployment


# ============================================================================
# PROCESSING DEPLOYMENTS
# ============================================================================

def create_process_signals_deployment() -> Deployment:
    """
    Create deployment for signal processing.

    Schedule: Every 4 hours
    """
    deployment = Deployment.build_from_flow(
        flow=process_signals,
        name="process-signals-periodic",
        version="1.0.0",
        description="Periodic signal aggregation and event publishing",
        tags=TAGS_PROCESSING + ["signals", "events"],
        schedule=CronSchedule(
            cron="0 */4 * * *",  # Every 4 hours
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="processing",
        parameters={
            "company_ids": None,  # Process all active companies
            "signal_sources": ["sec", "fda", "clinical_trials", "market_data"],
            "time_window": None,  # Will use default (7 days)
        },
        is_schedule_active=True,
    )

    logger.info("Signal processing deployment created")
    return deployment


def create_update_scores_deployment() -> Deployment:
    """
    Create deployment for company score updates.

    Schedule: Twice daily (morning and evening)
    """
    deployment = Deployment.build_from_flow(
        flow=update_company_scores,
        name="update-scores-twice-daily",
        version="1.0.0",
        description="Calculate and update M&A attractiveness scores",
        tags=TAGS_PROCESSING + ["scoring", "analytics"],
        schedule=CronSchedule(
            cron="0 9,17 * * *",  # 09:00 and 17:00 UTC
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="processing",
        parameters={
            "company_ids": None,  # Score all active companies
            "min_signal_count": 1,
        },
        is_schedule_active=True,
    )

    logger.info("Score update deployment created")
    return deployment


def create_match_acquirers_deployment() -> Deployment:
    """
    Create deployment for acquirer matching.

    Schedule: Daily at 6:00 PM ET
    """
    deployment = Deployment.build_from_flow(
        flow=match_acquirers,
        name="match-acquirers-daily",
        version="1.0.0",
        description="Match potential acquirers with high-scoring targets",
        tags=TAGS_PROCESSING + ["matching", "recommendations"],
        schedule=CronSchedule(
            cron="0 23 * * *",  # 23:00 UTC = 6:00 PM ET
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="processing",
        parameters={
            "target_company_ids": None,  # Use high-scoring targets
            "min_target_score": 60.0,
            "min_match_score": 50.0,
        },
        is_schedule_active=True,
    )

    logger.info("Acquirer matching deployment created")
    return deployment


# ============================================================================
# REPORTING DEPLOYMENTS
# ============================================================================

def create_daily_digest_deployment() -> Deployment:
    """
    Create deployment for daily digest report.

    Schedule: Every weekday at 6:00 AM ET
    """
    deployment = Deployment.build_from_flow(
        flow=generate_daily_digest,
        name="daily-digest-morning",
        version="1.0.0",
        description="Generate and send daily M&A digest report",
        tags=TAGS_REPORTING + ["digest", "daily"],
        schedule=CronSchedule(
            cron="0 11 * * 1-5",  # 11:00 UTC = 6:00 AM ET (weekdays only)
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="reporting",
        parameters={
            "recipients": ["team@example.com"],  # Configure recipients
        },
        is_schedule_active=True,
    )

    logger.info("Daily digest deployment created")
    return deployment


def create_weekly_watchlist_deployment() -> Deployment:
    """
    Create deployment for weekly watchlist report.

    Schedule: Every Monday at 7:00 AM ET
    """
    deployment = Deployment.build_from_flow(
        flow=generate_weekly_watchlist,
        name="weekly-watchlist-monday",
        version="1.0.0",
        description="Generate and send weekly ranked watchlist",
        tags=TAGS_REPORTING + ["watchlist", "weekly"],
        schedule=CronSchedule(
            cron="0 12 * * 1",  # 12:00 UTC on Mondays = 7:00 AM ET
            timezone="UTC",
        ),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="reporting",
        parameters={
            "recipients": ["team@example.com"],  # Configure recipients
            "top_n": 50,
        },
        is_schedule_active=True,
    )

    logger.info("Weekly watchlist deployment created")
    return deployment


def create_alert_report_deployment() -> Deployment:
    """
    Create deployment for alert reports (event-driven, no schedule).

    This deployment is triggered by events when significant score changes are detected.
    """
    deployment = Deployment.build_from_flow(
        flow=generate_alert_report,
        name="alert-report-event-driven",
        version="1.0.0",
        description="Generate alert reports for significant score changes (event-driven)",
        tags=TAGS_REPORTING + ["alert", "event-driven"],
        schedule=None,  # Event-driven, no schedule
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="alerts",
        parameters={
            # Parameters will be provided by triggering event
            "recipients": ["alerts@example.com"],
        },
        is_schedule_active=False,  # Activated by events
    )

    logger.info("Alert report deployment created (event-driven)")
    return deployment


# ============================================================================
# DEPLOYMENT MANAGEMENT FUNCTIONS
# ============================================================================

def create_all_deployments() -> List[Deployment]:
    """
    Create all deployment configurations.

    Returns:
        List of all deployment objects
    """
    logger.info("Creating all deployment configurations")

    deployments = [
        # Data ingestion
        create_sec_filings_deployment(),
        create_clinical_trials_deployment(),
        create_fda_data_deployment(),
        create_financial_data_deployment(),
        # Processing
        create_process_signals_deployment(),
        create_update_scores_deployment(),
        create_match_acquirers_deployment(),
        # Reporting
        create_daily_digest_deployment(),
        create_weekly_watchlist_deployment(),
        create_alert_report_deployment(),
    ]

    logger.info(f"Created {len(deployments)} deployment configurations")
    return deployments


def apply_all_deployments() -> None:
    """
    Apply all deployments to Prefect server.

    This function creates and applies all deployment configurations.
    Run this to register deployments with your Prefect instance.
    """
    logger.info("Applying all deployments to Prefect server")

    deployments = create_all_deployments()

    for deployment in deployments:
        try:
            deployment.apply()
            logger.info(f"Applied deployment: {deployment.name}")
        except Exception as e:
            logger.error(f"Failed to apply deployment {deployment.name}: {str(e)}")
            raise

    logger.info("All deployments applied successfully")


def get_deployment_info() -> Dict[str, Dict]:
    """
    Get information about all deployment configurations.

    Returns:
        Dictionary mapping deployment names to their configurations
    """
    deployments = create_all_deployments()

    info = {}
    for deployment in deployments:
        info[deployment.name] = {
            "flow_name": deployment.flow_name,
            "version": deployment.version,
            "description": deployment.description,
            "tags": deployment.tags,
            "schedule": str(deployment.schedule) if deployment.schedule else "Event-driven",
            "work_pool": deployment.work_pool_name,
            "work_queue": deployment.work_queue_name,
            "is_schedule_active": deployment.is_schedule_active,
        }

    return info


# ============================================================================
# CUSTOM DEPLOYMENT BUILDERS
# ============================================================================

def create_custom_sec_deployment(
    name: str,
    cron: str,
    filing_types: List[str],
    cik_list: Optional[List[str]] = None,
) -> Deployment:
    """
    Create a custom SEC filings deployment with specific parameters.

    Args:
        name: Deployment name
        cron: Cron schedule expression
        filing_types: List of filing types to fetch
        cik_list: Optional list of specific CIK numbers

    Returns:
        Custom deployment configuration
    """
    deployment = Deployment.build_from_flow(
        flow=ingest_sec_filings,
        name=name,
        version="1.0.0",
        description=f"Custom SEC filings ingestion: {', '.join(filing_types)}",
        tags=TAGS_DATA_INGESTION + ["sec", "custom"],
        schedule=CronSchedule(cron=cron, timezone="UTC"),
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="data-ingestion",
        parameters={
            "filing_types": filing_types,
            "cik_list": cik_list,
        },
        is_schedule_active=True,
    )

    logger.info(f"Custom SEC deployment '{name}' created")
    return deployment


def create_ad_hoc_score_update(
    company_ids: List[str],
    name: str = "ad-hoc-score-update",
) -> Deployment:
    """
    Create an ad-hoc deployment for scoring specific companies.

    Args:
        company_ids: List of company IDs to score
        name: Deployment name

    Returns:
        Ad-hoc deployment configuration
    """
    deployment = Deployment.build_from_flow(
        flow=update_company_scores,
        name=name,
        version="1.0.0",
        description=f"Ad-hoc score update for {len(company_ids)} companies",
        tags=TAGS_PROCESSING + ["scoring", "ad-hoc"],
        schedule=None,  # No schedule, run on-demand
        work_pool_name=DEFAULT_WORK_POOL,
        work_queue_name="processing",
        parameters={
            "company_ids": company_ids,
            "min_signal_count": 0,  # Score regardless of signals
        },
        is_schedule_active=False,
    )

    logger.info(f"Ad-hoc score update deployment '{name}' created")
    return deployment


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Apply all deployments when run as a script.

    Usage:
        python -m src.orchestration.deployments
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "info":
                # Display deployment information
                info = get_deployment_info()
                print("\nDeployment Configurations:")
                print("=" * 80)
                for name, details in info.items():
                    print(f"\n{name}:")
                    for key, value in details.items():
                        print(f"  {key}: {value}")
            elif sys.argv[1] == "apply":
                # Apply all deployments
                apply_all_deployments()
                print("\nAll deployments applied successfully!")
            else:
                print(f"Unknown command: {sys.argv[1]}")
                print("Usage: python -m src.orchestration.deployments [info|apply]")
                sys.exit(1)
        else:
            # Default: display info
            info = get_deployment_info()
            print("\nDeployment Configurations:")
            print("=" * 80)
            for name, details in info.items():
                print(f"\n{name}:")
                for key, value in details.items():
                    print(f"  {key}: {value}")

            print("\n" + "=" * 80)
            print("To apply deployments, run: python -m src.orchestration.deployments apply")

    except Exception as e:
        logger.error(f"Deployment operation failed: {str(e)}")
        sys.exit(1)
