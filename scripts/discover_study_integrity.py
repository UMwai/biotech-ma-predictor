#!/usr/bin/env python3
"""Match official PubMed integrity records to the market clinical-asset inventory."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.integrity_discovery import (  # noqa: E402
    fetch_pubmed_integrity_records,
    fetch_registry_assets_for_publications,
    load_market_clinical_assets,
    load_market_companies,
    match_publications_to_assets,
)
from src.research.sources import HttpCache  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market-assets",
        type=Path,
        default=ROOT / "output" / "market_evaluation" / "assets.csv",
    )
    parser.add_argument(
        "--market-companies",
        type=Path,
        default=ROOT / "output" / "market_evaluation" / "companies.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "study_integrity" / "discovery",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data" / "study_integrity" / "raw",
    )
    parser.add_argument("--max-records", type=int, default=10_000)
    parser.add_argument(
        "--include-name-matches",
        action="store_true",
        help=(
            "Also emit lower-confidence exact asset-name matches. "
            "The default emits only NCT-linked candidates."
        ),
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--user-agent",
        default="BiotechMAPredictor/0.1 github.com/UMwai/biotech-ma-predictor",
    )
    return parser.parse_args()


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})
    return len(rows)


def main() -> int:
    args = parse_args()
    if args.max_records < 1 or args.max_records > 10_000:
        raise ValueError("--max-records must be from 1 to 10000")
    cache = HttpCache(args.cache_dir, args.user_agent, offline=args.offline)
    assets = load_market_clinical_assets(args.market_assets)
    companies = load_market_companies(args.market_companies)
    total_records, publications = fetch_pubmed_integrity_records(
        cache,
        max_records=args.max_records,
        refresh=args.refresh,
    )
    reported_nct_ids, registry_assets = fetch_registry_assets_for_publications(
        cache,
        publications,
        companies,
        refresh=args.refresh,
    )
    candidates = match_publications_to_assets(
        publications,
        assets + registry_assets,
        include_name_matches=args.include_name_matches,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / "publication_candidates.csv",
        (candidate.to_dict() for candidate in candidates),
    )
    manifest = {
        "schema_version": "study-integrity-discovery-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "NCBI PubMed E-utilities",
        "source_query": (
            '"Retracted Publication"[Publication Type] OR '
            '"Expression of Concern"[Publication Type]'
        ),
        "pubmed_total_records": total_records,
        "pubmed_records_retrieved": len(publications),
        "market_clinical_assets": len(assets),
        "market_companies": len(companies),
        "pubmed_reported_nct_ids": reported_nct_ids,
        "clinicaltrials_records_resolved": len(registry_assets),
        "clinicaltrials_public_sponsor_matches": sum(
            bool(asset.owner_ticker) for asset in registry_assets
        ),
        "matched_review_candidates": len(candidates),
        "included_lower_confidence_name_matches": args.include_name_matches,
        "interpretation": (
            "Discovery candidates only. Matching does not establish that the "
            "asset owner sponsored the publication or committed misconduct."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Reviewed {len(publications)} PubMed integrity records against "
        f"{len(assets)} clinical assets; wrote {len(candidates)} candidates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
