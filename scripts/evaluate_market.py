#!/usr/bin/env python3
"""Evaluate the U.S.-listed drug/biotech market and all ingested drug assets.

The generated research scores are transparent rankings, not calibrated M&A
probabilities. Raw payloads and retrieval metadata are cached for auditability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.evaluator import (  # noqa: E402
    MODEL_VERSION,
    evaluate_biologic_assets,
    evaluate_clinical_assets,
    evaluate_companies,
    evaluate_orange_book_assets,
)
from src.research.matching import CompanyMatcher  # noqa: E402
from src.research.sources import (  # noqa: E402
    HttpCache,
    PublicRefreshCache,
    fetch_active_clinical_assets,
    fetch_drugsfda_biologic_assets,
    fetch_orange_book_assets,
    fetch_public_biotech_universe,
    fetch_recent_announced_target_ciks,
    is_sec_url,
    utc_now_iso,
)

logger = logging.getLogger("market_evaluator")


def snapshot_manifest(cache: HttpCache, as_of: date) -> dict[str, Any]:
    """Describe the exact source observations, independently of run time."""
    fields = (
        "cache_key", "url", "retrieved_at", "sha256", "bytes", "blob_path",
        "snapshot_path", "snapshot_sha256", "integrity_status", "origin",
        "age_days", "freshness", "retrieval_policy", "stale_allowed",
    )
    snapshots = [
        {field: item.get(field) for field in fields}
        for _, item in sorted(cache.source_snapshots.items())
    ]
    dated: list[datetime] = []
    after_cutoff = []
    undated = []
    for item in snapshots:
        try:
            retrieved = datetime.fromisoformat(item["retrieved_at"].replace("Z", "+00:00"))
            if retrieved.tzinfo is None:
                raise ValueError("timezone missing")
            retrieved = retrieved.astimezone(timezone.utc)
            dated.append(retrieved)
            if retrieved.date() > as_of:
                after_cutoff.append(item["cache_key"])
        except (AttributeError, TypeError, ValueError):
            undated.append(item["cache_key"])
    counts = Counter(item["freshness"] for item in snapshots)
    status = "fresh" if snapshots and set(counts) == {"fresh"} else "stale_or_unknown"
    identity = [
        {key: item[key] for key in ("cache_key", "sha256", "snapshot_sha256")}
        for item in snapshots
    ]
    return {
        "snapshot_schema_version": "research-source-snapshots-v1",
        "source_cache_directory": str(cache.root.resolve()),
        "source_snapshots": snapshots,
        "source_snapshot_set_sha256": hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode()
        ).hexdigest(),
        "freshness": {
            "status": status,
            "max_source_age_days": cache.max_age_days,
            "allow_stale": cache.allow_stale,
            "stale_cache_only_hosts": ["sec.gov", "*.sec.gov"] if isinstance(cache, PublicRefreshCache) else [],
            "oldest_retrieved_at": min(dated).isoformat() if dated else None,
            "latest_retrieved_at": max(dated).isoformat() if dated else None,
            "source_counts": dict(counts),
            "generated_at_is_source_freshness": False,
        },
        "temporal_validity": {
            "evaluation_mode": "current_source_cross_section",
            "historical_replay_available": False,
            "as_of_semantics": "scoring cutoff only; does not reconstruct historical source state",
            "source_dates_compatible_with_as_of": bool(snapshots) and not after_cutoff and not undated,
            "sources_retrieved_after_as_of": after_cutoff,
            "sources_without_retrieval_date": undated,
            "clinical_future_update_policy": "quarantine whole aggregated asset",
            "reason": "Current listing, FDA and trial snapshots do not establish a historical point-in-time universe or features.",
        },
    }


def sec_screening_manifest(cache: HttpCache, as_of: date, screening_as_of: date,
                           *, public_only: bool = False) -> dict[str, Any]:
    """Separate transaction-screening coverage from the market scoring cutoff."""
    observations = [item for item in cache.source_snapshots.values()
                    if is_sec_url(item.get("url", ""))]
    verified = bool(observations) and all(item.get("integrity_status") == "verified"
                                         for item in observations)
    fresh = bool(observations) and all(item.get("freshness") == "fresh" for item in observations)
    current = not public_only and screening_as_of == date.today() and verified and fresh
    status = "cache_only_not_current" if public_only else ("current" if current else "not_current_or_unverified")
    return {
        "sec_transaction_screening_as_of": screening_as_of.isoformat(),
        "sec_transaction_screening_status": {
            "status": status, "current": current,
            "source_mode": "cache_only" if public_only or cache.offline else "network_permitted",
            "market_as_of": as_of.isoformat(),
            "lag_days": (as_of - screening_as_of).days,
            "integrity_status": "verified" if verified else "unverified",
            "retrieval_freshness": "fresh" if fresh else "stale_or_unknown",
            "source_count": len(observations),
            "lookback_days": 365,
            "scope": "SEC CIK mapping and recent SC 14D9/DEFM14A candidate exclusions; not a complete transaction census",
            "reason": ("SEC was not refreshed. Later announcements and listing changes are not screened."
                       if public_only else "Screening cutoff and retrieval freshness are recorded independently of build time."),
        },
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_value(value) for key, value in row.items()})
    return len(rows)


def write_summary(
    path: Path, manifest: dict[str, Any], companies: list[Any], assets: list[Any]
) -> None:
    top_companies = [company for company in companies if company.risk_set_eligible][:50]
    lines = [
        "# U.S.-Listed Biotech Market Research Evaluation",
        "",
        f"**Generated:** {manifest['generated_at']}",
        f"**Source freshness:** {manifest['freshness']['status']}; oldest retrieval: {manifest['freshness']['oldest_retrieved_at']}",
        f"**SEC transaction screening through:** {manifest['sec_transaction_screening_as_of']} "
        f"({manifest['sec_transaction_screening_status']['status']})",
        "**Temporal scope:** Current-source cross-section. Historical replay is unavailable; generation time is not source freshness.",
        f"**Model:** `{manifest['model_version']}`",
        "**Interpretation:** Research ranking only; not a calibrated acquisition probability.",
        "",
        "## Coverage",
        "",
        f"- Public drug/biotech companies evaluated: {manifest['coverage']['public_companies']:,}",
        f"- FDA Orange Book ingredient/applicant assets evaluated: {manifest['coverage']['orange_book_assets']:,}",
        f"- Marketed Drugs@FDA BLA ingredient/sponsor assets evaluated: {manifest['coverage']['biologic_assets']:,}",
        f"- Unique marketed active-ingredient names: {manifest['coverage']['unique_marketed_ingredients']:,}",
        f"- Active industry-sponsored clinical assets evaluated: {manifest['coverage']['clinical_assets']:,}",
        f"- Unique active clinical intervention names: {manifest['coverage']['unique_clinical_interventions']:,}",
        f"- Total asset evaluations: {manifest['coverage']['total_assets']:,}",
        f"- Assets matched to listed owners: {manifest['coverage']['assets_matched_to_public_company']:,}",
        f"- Listed companies with at least one matched asset: {manifest['coverage']['companies_with_assets']:,}",
        f"- Current listings excluded for recent transaction filings: {manifest['coverage']['announced_transaction_exclusions']:,}",
        "",
        "The asset file contains every ingested asset, including unmatched private or subsidiary applicants/sponsors. "
        "Public-company matches are conservative and include confidence values. Approved products combine the "
        "Orange Book with currently marketed BLA products in Drugs@FDA.",
        "",
        "## Highest-ranked public-company research candidates",
        "",
        "| Rank | Ticker | Company | Score | Market cap | Approved | Clinical | Confidence |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for rank, company in enumerate(top_companies, 1):
        market_cap = (
            f"${company.market_cap_usd / 1e9:.2f}B" if company.market_cap_usd else "n/a"
        )
        lines.append(
            f"| {rank} | {company.ticker} | {company.company_name.replace('|', '/')} | "
            f"{company.research_score:.2f} | {market_cap} | {company.approved_asset_count} | "
            f"{company.clinical_asset_count} | {company.data_confidence:.0f} |"
        )

    lines.extend(
        [
            "",
            "## Highest-ranked marketed drug assets",
            "",
            "| Rank | Asset | Type | Applicant/sponsor | Associated ticker | Score |",
            "|---:|---|---|---|---|---:|",
        ]
    )
    marketed_assets = sorted(
        (asset for asset in assets if asset.asset_type.startswith("approved")),
        key=lambda item: (-item.score, item.asset_name),
    )[:50]
    for rank, asset in enumerate(marketed_assets, 1):
        lines.append(
            f"| {rank} | {asset.asset_name.replace('|', '/')} | {asset.asset_type} | "
            f"{asset.owner_name.replace('|', '/')} | {asset.owner_ticker or ''} | {asset.score:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Highest-ranked active clinical assets",
            "",
            "| Rank | Intervention | Lead sponsor | Associated ticker | Score |",
            "|---:|---|---|---|---:|",
        ]
    )
    clinical_assets = sorted(
        (asset for asset in assets if asset.asset_type == "clinical_pipeline"),
        key=lambda item: (-item.score, item.asset_name),
    )[:50]
    for rank, asset in enumerate(clinical_assets, 1):
        lines.append(
            f"| {rank} | {asset.asset_name.replace('|', '/')} | "
            f"{asset.owner_name.replace('|', '/')} | {asset.owner_ticker or ''} | {asset.score:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Required cautions",
            "",
            "- Scores rank observable asset strength and acquisition-size feasibility; they are not trained probabilities.",
            "- Entity matching does not yet roll every subsidiary or licensed asset up to its ultimate public parent.",
            "- Drugs@FDA BLA coverage is included, but Purple Book-only CBER products and biologic patent lists may remain incomplete.",
            "- A ClinicalTrials.gov lead-sponsor relationship does not prove ownership; multi-sponsor interventions are not attributed to a ticker.",
            "- Active ClinicalTrials.gov records do not represent every preclinical, paused, completed, or ex-U.S. asset.",
            "- Market data is a current cross-section and is not suitable for historical backtesting.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today(),
                        help="Scoring cutoff only; current sources cannot replay a historical universe")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "output" / "market_evaluation"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=ROOT / "data" / "market_evaluation" / "raw"
    )
    parser.add_argument("--max-clinical-studies", type=int, default=None)
    parser.add_argument("--skip-clinical", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--refresh-public", action="store_true",
                      help="Refresh Nasdaq/FDA/Clinical inputs; SEC remains verified cache-only")
    mode.add_argument("--offline", action="store_true")
    parser.add_argument("--sec-screening-as-of", type=date.fromisoformat,
                        help="Original SEC query cutoff from the prior manifest; required for --refresh-public")
    parser.add_argument("--max-source-age-days", type=float, default=7,
                        help="Maximum retrieval age before a run fails (default: 7 days)")
    parser.add_argument("--allow-stale", action="store_true",
                        help="Permit explicitly flagged stale/undated cached research")
    parser.add_argument(
        "--user-agent",
        default="BiotechMAPredictor/0.1 github.com/UMwai/biotech-ma-predictor",
        help="Identification used for SEC and public API requests",
    )
    args = parser.parse_args()
    if args.refresh_public and args.sec_screening_as_of is None:
        parser.error("--refresh-public requires --sec-screening-as-of from the prior source manifest")
    if args.sec_screening_as_of is not None and not (args.refresh_public or args.offline):
        parser.error("--sec-screening-as-of is only valid with --refresh-public or --offline")
    if args.sec_screening_as_of is not None and args.sec_screening_as_of > args.as_of:
        parser.error("SEC screening cutoff cannot be later than the market cutoff")
    if args.refresh_public and args.allow_stale:
        parser.error("--refresh-public permits stale SEC cache only; --allow-stale cannot be combined")
    return args


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    generated_at = utc_now_iso()
    if args.refresh_public:
        cache = PublicRefreshCache(args.cache_dir, args.user_agent,
                                   max_age_days=args.max_source_age_days)
    else:
        cache = HttpCache(
            args.cache_dir, args.user_agent, offline=args.offline,
            max_age_days=args.max_source_age_days, allow_stale=args.allow_stale,
        )
    refresh_sources = args.refresh or args.refresh_public
    screening_as_of = args.sec_screening_as_of or args.as_of

    logger.info("Fetching public drug/biotech company universe")
    companies = fetch_public_biotech_universe(cache, refresh=refresh_sources)
    matcher = CompanyMatcher(companies)

    logger.info("Checking SEC filings for already-announced target transactions")
    announced_target_ciks = fetch_recent_announced_target_ciks(
        cache,
        screening_as_of,
        refresh=refresh_sources,
    )

    logger.info("Fetching and evaluating FDA Orange Book assets")
    orange_raw = fetch_orange_book_assets(cache, refresh=refresh_sources)
    orange_assets = evaluate_orange_book_assets(orange_raw, matcher, args.as_of)

    logger.info("Fetching and evaluating currently marketed Drugs@FDA BLA assets")
    biologic_raw = fetch_drugsfda_biologic_assets(cache, refresh=refresh_sources)
    biologic_assets = evaluate_biologic_assets(biologic_raw, matcher)

    clinical_assets = []
    rejected_clinical_assets: list[dict[str, Any]] = []
    if not args.skip_clinical:
        logger.info("Fetching and evaluating active industry-sponsored clinical assets")
        clinical_raw = fetch_active_clinical_assets(
            cache,
            refresh=refresh_sources,
            max_studies=args.max_clinical_studies,
        )
        clinical_assets = evaluate_clinical_assets(
            clinical_raw, matcher, args.as_of, rejected_assets=rejected_clinical_assets
        )

    assets = orange_assets + biologic_assets + clinical_assets
    company_evaluations = evaluate_companies(
        companies,
        assets,
        generated_at,
        announced_target_ciks=announced_target_ciks,
    )
    companies_with_assets = {
        asset.owner_ticker for asset in assets if asset.owner_ticker
    }
    unmatched_owners = Counter(
        asset.owner_name for asset in assets if not asset.owner_ticker
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "companies.csv",
        (asdict(item) for item in company_evaluations),
    )
    write_csv(args.output_dir / "assets.csv", (asdict(item) for item in assets))
    write_csv(
        args.output_dir / "unmatched_owners.csv",
        (
            {"owner_name": owner, "asset_count": count}
            for owner, count in unmatched_owners.most_common()
        ),
    )
    write_csv(
        args.output_dir / "announced_transaction_exclusions.csv",
        (
            {
                "ticker": company.ticker,
                "company_name": company.company_name,
                "reason": company.risk_set_exclusion_reason,
            }
            for company in company_evaluations
            if not company.risk_set_eligible
        ),
    )
    write_csv(args.output_dir / "quarantined_clinical_assets.csv", rejected_clinical_assets)

    manifest = {
        "generated_at": generated_at,
        "as_of": args.as_of.isoformat(),
        "model_version": MODEL_VERSION,
        **snapshot_manifest(cache, args.as_of),
        **sec_screening_manifest(cache, args.as_of, screening_as_of, public_only=args.refresh_public),
        "run_parameters": {
            "offline": args.offline, "refresh": args.refresh, "refresh_public": args.refresh_public,
            "sec_screening_as_of": screening_as_of.isoformat(),
            "skip_clinical": args.skip_clinical,
            "max_clinical_studies": args.max_clinical_studies,
            "max_source_age_days": args.max_source_age_days,
            "allow_stale": args.allow_stale,
        },
        "score_semantics": "cross-sectional research score; not calibrated M&A probability",
        "coverage": {
            "public_companies": len(companies),
            "companies_without_sec_cik": sum(company.cik is None for company in companies),
            "orange_book_assets": len(orange_assets),
            "biologic_assets": len(biologic_assets),
            "clinical_assets": len(clinical_assets),
            "quarantined_clinical_assets": len(rejected_clinical_assets),
            "unique_marketed_ingredients": len(
                {
                    asset.asset_name.upper()
                    for asset in assets
                    if asset.asset_type.startswith("approved")
                }
            ),
            "unique_clinical_interventions": len(
                {asset.asset_name.upper() for asset in clinical_assets}
            ),
            "total_assets": len(assets),
            "assets_matched_to_public_company": sum(
                asset.owner_ticker is not None for asset in assets
            ),
            "companies_with_assets": len(companies_with_assets),
            "announced_transaction_exclusions": sum(
                not company.risk_set_eligible for company in company_evaluations
            ),
            "unmatched_owner_names": len(unmatched_owners),
        },
        "sources": [
            "Nasdaq stock screener (current listed healthcare securities)",
            "SEC company_tickers_exchange.json (CIK mapping)",
            "SEC EDGAR full-text search (recent SC 14D9 and DEFM14A risk-set exclusions)",
            "FDA Orange Book current data files",
            "Drugs@FDA current data files (marketed BLA products)",
            "ClinicalTrials.gov API v2 active industry-sponsored interventional studies",
        ],
        "known_gaps": [
            "Purple Book-only CBER products and biologic patent lists may be incomplete",
            "subsidiary and licensing ownership rollups are incomplete",
            "current cross-section is not a historical point-in-time backtest",
            "scores are not calibrated acquisition probabilities",
            *(["SEC transaction screening is cache-only at an older cutoff; later deals and listing changes may be missed"]
              if args.refresh_public else []),
        ],
        "outputs": {
            "companies": "companies.csv",
            "assets": "assets.csv",
            "unmatched_owners": "unmatched_owners.csv",
            "announced_transaction_exclusions": "announced_transaction_exclusions.csv",
            "quarantined_clinical_assets": "quarantined_clinical_assets.csv",
            "summary": "summary.md",
        },
    }
    write_summary(args.output_dir / "summary.md", manifest, company_evaluations, assets)
    manifest["output_sha256"] = {
        name: hashlib.sha256((args.output_dir / name).read_bytes()).hexdigest()
        for name in manifest["outputs"].values()
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    logger.info(
        "Evaluated %d companies and %d assets (%d assets matched to public owners)",
        len(companies),
        len(assets),
        manifest["coverage"]["assets_matched_to_public_company"],
    )
    logger.info("Outputs written to %s", args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
