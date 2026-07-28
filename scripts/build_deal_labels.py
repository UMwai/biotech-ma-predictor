#!/usr/bin/env python3
"""Build an SEC-derived historical biotech transaction-candidate ledger.

The output is an adjudication queue, not a completed training-label dataset.
Schedule 14D-9 candidates have strong target-company provenance, while
DEFM14A-only candidates require review of the transaction structure and filer
role. No row is marked model-label eligible without verified announcement data.
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

from src.research.deal_labels import (  # noqa: E402
    BIOTECH_SIC_CODES,
    build_annual_risk_set,
    build_deal_candidates,
    validate_candidate_ledger,
)
from src.research.sources import (  # noqa: E402
    HttpCache,
    fetch_sec_annual_report_filings,
    fetch_sec_transaction_filings,
    utc_now_iso,
)

logger = logging.getLogger(__name__)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(materialized[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def write_summary(
    path: Path,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    risk_set: list[dict[str, Any]],
) -> None:
    by_year = Counter(row["sec_signal_date"][:4] for row in rows)
    by_class = Counter(row["event_class"] for row in rows)
    lines = [
        "# Historical Biotech Transaction Candidate Audit",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"SEC filing window: `{manifest['start_date']}` through `{manifest['end_date']}`",
        "",
        "## Coverage",
        "",
        f"- SEC transaction documents fetched: **{manifest['coverage']['sec_documents']}**",
        f"- Biotech transaction candidate clusters: **{manifest['coverage']['candidate_clusters']}**",
        f"- Schedule 14D-9 target candidates: **{by_class.get('tender_offer_target', 0)}**",
        f"- DEFM14A-only review candidates: **{by_class.get('merger_proxy_filer', 0)}**",
        f"- Model-label eligible rows: **{manifest['coverage']['model_label_eligible']}**",
        "",
        "## Candidates by first SEC signal year",
        "",
        "| Year | Candidates |",
        "|---:|---:|",
    ]
    for year, count in sorted(by_year.items()):
        lines.append(f"| {year} | {count} |")

    if risk_set:
        by_observation_year: dict[str, dict[str, int]] = {}
        for row in risk_set:
            year = row["observation_date"][:4]
            bucket = by_observation_year.setdefault(
                year,
                {"companies": 0, "tender": 0, "any": 0, "complete": 0},
            )
            bucket["companies"] += 1
            bucket["tender"] += bool(
                row["provisional_tender_offer_signal_within_horizon"]
            )
            bucket["any"] += bool(
                row["provisional_any_transaction_signal_within_horizon"]
            )
            bucket["complete"] += bool(row["outcome_window_complete"])
        lines.extend(
            [
                "",
                "## Historical annual reporting-company risk sets",
                "",
                "| Observation year | Companies | Complete outcomes | Forward 14D-9 signals | Forward any candidates | 14D-9 incidence |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for year, bucket in sorted(by_observation_year.items()):
            incidence = (
                bucket["tender"] / bucket["companies"] if bucket["companies"] else 0
            )
            incidence_text = (
                f"{incidence:.2%}"
                if bucket["complete"] == bucket["companies"]
                else "censored"
            )
            lines.append(
                f"| {year} | {bucket['companies']} | {bucket['complete']} | "
                f"{bucket['tender']} | {bucket['any']} | {incidence_text} |"
            )

    lines.extend(
        [
            "",
            "## Label status",
            "",
            "This is a primary-source candidate ledger, not a frozen acquisition-label dataset.",
            "No candidate is model-label eligible until a reviewer verifies the target role,",
            "change-of-control structure, and first public announcement timestamp. The SEC filing",
            "date is retained as `sec_signal_date` and must not be silently substituted for the",
            "announcement date in a predictive backtest.",
            "",
            "The annual risk set uses contemporaneous biotech 10-K/20-F/40-F filers with",
            "Exchange Act file numbers beginning `001-`. This removes current-survivor bias",
            "from the denominator, but it is not a complete historical exchange-membership",
            "reconstruction and contains no point-in-time model features.",
            "",
            "Schedule 14D-9 candidates are high-confidence tender-offer target signals. DEFM14A-only",
            "candidates remain an explicit adjudication queue because the filer can be the target,",
            "buyer, SPAC, or another merger participant.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def adjudication_rows(candidates: list[Any]) -> Iterable[dict[str, Any]]:
    """Emit a stable reviewer template without asserting unverified facts."""
    for item in candidates:
        yield {
            "candidate_id": item.candidate_id,
            "sec_signal_date": item.sec_signal_date,
            "filer_name": item.filer_name,
            "filer_tickers": item.filer_tickers,
            "event_class": item.event_class,
            "candidate_confidence": item.confidence,
            "decision": "",
            "reviewed_target_cik": "",
            "reviewed_target_name": "",
            "reviewed_target_ticker": "",
            "acquirer_name": "",
            "first_public_announcement_at": "",
            "transaction_structure": "",
            "change_of_control_percent": "",
            "transaction_status": "",
            "review_primary_source_url": "",
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date", type=date.fromisoformat, default=date(2018, 1, 1)
    )
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "historical_deal_candidates",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data" / "market_evaluation" / "raw",
    )
    parser.add_argument("--cluster-gap-days", type=int, default=240)
    parser.add_argument("--skip-risk-set", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--user-agent",
        default="BiotechMAPredictor/0.1 github.com/UMwai/biotech-ma-predictor",
        help="Identification used for SEC requests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.end_date < args.start_date:
        raise SystemExit("--end-date must be on or after --start-date")

    cache = HttpCache(args.cache_dir, args.user_agent, offline=args.offline)
    filings = fetch_sec_transaction_filings(
        cache,
        args.start_date,
        args.end_date,
        refresh=args.refresh,
    )
    candidates = build_deal_candidates(filings, cluster_gap_days=args.cluster_gap_days)
    ledger_validation = validate_candidate_ledger(candidates)
    rows = [asdict(item) for item in candidates]
    risk_set: list[dict[str, Any]] = []
    risk_set_exclusions: list[dict[str, Any]] = []
    annual_report_filings: list[dict[str, Any]] = []
    if not args.skip_risk_set:
        annual_report_filings = fetch_sec_annual_report_filings(
            cache,
            args.start_date.year,
            args.end_date.year - 1,
            refresh=args.refresh,
        )
        risk_set, risk_set_exclusions = build_annual_risk_set(
            annual_report_filings,
            candidates,
            data_end_date=args.end_date,
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "candidates.csv", rows)
    write_csv(
        args.output_dir / "adjudication_template.csv",
        adjudication_rows(candidates),
    )
    write_csv(args.output_dir / "annual_risk_set.csv", risk_set)
    write_csv(args.output_dir / "annual_risk_set_exclusions.csv", risk_set_exclusions)

    manifest = {
        "generated_at": utc_now_iso(),
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "dataset_version": "sec-biotech-deal-candidates-0.1.0",
        "semantics": "transaction candidate/adjudication queue; not frozen model labels",
        "coverage": {
            "sec_documents": len(filings),
            "candidate_clusters": len(candidates),
            "tender_offer_target_candidates": sum(
                item.event_class == "tender_offer_target" for item in candidates
            ),
            "merger_proxy_review_candidates": sum(
                item.event_class == "merger_proxy_filer" for item in candidates
            ),
            "model_label_eligible": sum(
                item.model_label_eligible for item in candidates
            ),
            "annual_report_documents": len(annual_report_filings),
            "annual_risk_set_rows": len(risk_set),
            "annual_risk_set_exclusions": len(risk_set_exclusions),
            "complete_outcome_rows": sum(
                bool(row["outcome_window_complete"]) for row in risk_set
            ),
            "censored_outcome_rows": sum(
                not bool(row["outcome_window_complete"]) for row in risk_set
            ),
            "provisional_forward_tender_offer_signals": sum(
                bool(row["provisional_tender_offer_signal_within_horizon"])
                for row in risk_set
            ),
            "provisional_forward_any_transaction_signals": sum(
                bool(row["provisional_any_transaction_signal_within_horizon"])
                for row in risk_set
            ),
        },
        "validation": ledger_validation,
        "biotech_sic_codes": sorted(BIOTECH_SIC_CODES),
        "label_gate": {
            "required_fields": [
                "reviewed target identity",
                "first public announcement timestamp",
                "change-of-control classification",
                "transaction outcome class",
            ],
            "training_allowed": False,
            "risk_set_semantics": (
                "contemporaneous annual SEC reporting-company proxy; "
                "not historical exchange membership"
            ),
        },
        "sources": [
            "SEC EDGAR full-text search: SC 14D9 and DEFM14A",
            "SEC EDGAR Archives primary filing documents",
        ],
        "outputs": {
            "candidates": "candidates.csv",
            "adjudication_template": "adjudication_template.csv",
            "annual_risk_set": "annual_risk_set.csv",
            "annual_risk_set_exclusions": "annual_risk_set_exclusions.csv",
            "summary": "summary.md",
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    write_summary(args.output_dir / "summary.md", manifest, rows, risk_set)
    logger.info(
        "Wrote %d biotech candidate clusters to %s",
        len(candidates),
        args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
