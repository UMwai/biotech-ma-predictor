#!/usr/bin/env python3
"""Evaluate the U.S.-listed drug/biotech market and all ingested drug assets.

The generated research scores are transparent rankings, not calibrated M&A
probabilities. Raw payloads and retrieval metadata are cached for auditability.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
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
    fetch_active_clinical_assets,
    fetch_drugsfda_biologic_assets,
    fetch_orange_book_assets,
    fetch_public_biotech_universe,
    fetch_recent_announced_target_ciks,
    utc_now_iso,
)

logger = logging.getLogger("market_evaluator")


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
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "output" / "market_evaluation"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=ROOT / "data" / "market_evaluation" / "raw"
    )
    parser.add_argument("--max-clinical-studies", type=int, default=None)
    parser.add_argument("--skip-clinical", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--user-agent",
        default="BiotechMAPredictor/0.1 github.com/UMwai/biotech-ma-predictor",
        help="Identification used for SEC and public API requests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    generated_at = utc_now_iso()
    cache = HttpCache(args.cache_dir, args.user_agent, offline=args.offline)

    logger.info("Fetching public drug/biotech company universe")
    companies = fetch_public_biotech_universe(cache, refresh=args.refresh)
    matcher = CompanyMatcher(companies)

    logger.info("Checking SEC filings for already-announced target transactions")
    announced_target_ciks = fetch_recent_announced_target_ciks(
        cache,
        args.as_of,
        refresh=args.refresh,
    )

    logger.info("Fetching and evaluating FDA Orange Book assets")
    orange_raw = fetch_orange_book_assets(cache, refresh=args.refresh)
    orange_assets = evaluate_orange_book_assets(orange_raw, matcher, args.as_of)

    logger.info("Fetching and evaluating currently marketed Drugs@FDA BLA assets")
    biologic_raw = fetch_drugsfda_biologic_assets(cache, refresh=args.refresh)
    biologic_assets = evaluate_biologic_assets(biologic_raw, matcher)

    clinical_assets = []
    if not args.skip_clinical:
        logger.info("Fetching and evaluating active industry-sponsored clinical assets")
        clinical_raw = fetch_active_clinical_assets(
            cache,
            refresh=args.refresh,
            max_studies=args.max_clinical_studies,
        )
        clinical_assets = evaluate_clinical_assets(clinical_raw, matcher, args.as_of)

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

    manifest = {
        "generated_at": generated_at,
        "as_of": args.as_of.isoformat(),
        "model_version": MODEL_VERSION,
        "score_semantics": "cross-sectional research score; not calibrated M&A probability",
        "coverage": {
            "public_companies": len(companies),
            "orange_book_assets": len(orange_assets),
            "biologic_assets": len(biologic_assets),
            "clinical_assets": len(clinical_assets),
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
        ],
        "outputs": {
            "companies": "companies.csv",
            "assets": "assets.csv",
            "unmatched_owners": "unmatched_owners.csv",
            "announced_transaction_exclusions": "announced_transaction_exclusions.csv",
            "summary": "summary.md",
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    write_summary(args.output_dir / "summary.md", manifest, company_evaluations, assets)

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
