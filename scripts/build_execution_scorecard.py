#!/usr/bin/env python3
"""Build the market-wide execution scorecard and marker comparisons."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.execution_markers import (  # noqa: E402
    ExecutionScorecardRow,
    HistoricalExecutionMarker,
    score_company_execution,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market-companies",
        type=Path,
        default=ROOT / "output" / "market_evaluation" / "companies.csv",
    )
    parser.add_argument(
        "--integrity-companies",
        type=Path,
        default=ROOT / "output" / "study_integrity" / "companies.csv",
    )
    parser.add_argument(
        "--execution-companies",
        type=Path,
        default=ROOT / "output" / "execution_risk" / "companies.csv",
    )
    parser.add_argument(
        "--markers",
        type=Path,
        default=ROOT / "data" / "execution_markers" / "markers.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "execution_scorecard",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        help="Exclude marker anchors published after this date.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_markers(path: Path) -> list[HistoricalExecutionMarker]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        HistoricalExecutionMarker.from_dict(row)
        for row in payload.get("markers", [])
    ]


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
            writer.writerow(
                {key: _csv_value(value) for key, value in row.items()}
            )
    return len(rows)


def _company_table(
    lines: list[str],
    title: str,
    rows: list[ExecutionScorecardRow],
) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Ticker | Company | Upside | Downside | Balance | Coverage | Closest marker | Similarity |",
            "|---|---|---:|---:|---:|---|---|---:|",
        ]
    )
    if not rows:
        lines.append("| — | No matching companies | — | — | — | — | — | — |")
    for row in rows:
        marker = row.closest_marker_id or "no reliable match"
        lines.append(
            f"| {row.ticker} | {row.company_name} | "
            f"{row.delivery_upside_score:.2f} | "
            f"{row.execution_downside_score:.2f} | "
            f"{row.execution_balance_score:.2f} | "
            f"{row.evidence_coverage} | {marker} | "
            f"{row.marker_similarity:.2f} |"
        )
    lines.append("")


def _marker_table(
    lines: list[str],
    markers: list[HistoricalExecutionMarker],
) -> None:
    lines.extend(
        [
            "## Historical marker library",
            "",
            "| Marker | Polarity | Anchor | Archetype | Later outcome label |",
            "|---|---|---|---|---|",
        ]
    )
    for marker in markers:
        lines.append(
            f"| {marker.marker_id} | {marker.polarity} | "
            f"{marker.anchor_date} | {marker.archetype} | "
            f"{marker.outcome_class} |"
        )
    lines.append("")


def write_summary(
    path: Path,
    generated_at: str,
    rows: list[ExecutionScorecardRow],
    markers: list[HistoricalExecutionMarker],
) -> None:
    downside = sorted(
        (
            row for row in rows if row.execution_downside_score > 0
        ),
        key=lambda row: (
            -row.execution_downside_score,
            row.ticker,
        ),
    )[:25]
    upside = sorted(
        (
            row
            for row in rows
            if row.execution_outlook == "upside_proxy_risk_unscreened"
        ),
        key=lambda row: (
            -row.delivery_upside_score,
            row.ticker,
        ),
    )[:25]
    lines = [
        "# Biotech Execution Scorecard",
        "",
        f"**Generated:** {generated_at}",
        "",
        "> The scorecard separates sourced downside evidence from a delivery-upside",
        "> proxy. It does not label a company or leader incompetent, fraudulent,",
        "> cleared, or investment-worthy.",
        "",
        "Every market company receives a row. `company_specific_evidence` means the",
        "current evidence ledgers or negative-marker library contain cited company",
        "records. Other coverage",
        "labels mean execution risk is unscreened, even when the upside proxy is high.",
        "",
    ]
    _company_table(lines, "Sourced execution downside", downside)
    _company_table(
        lines,
        "Highest delivery-upside proxies awaiting risk coverage",
        upside,
    )
    _marker_table(lines, markers)
    lines.extend(
        [
            "## Point-in-time controls",
            "",
            "- Marker fingerprints contain only evidence observable on the anchor date.",
            "- Bankruptcy, asset-sale, reverse-merger, and acquisition outcomes are labels, not input features.",
            "- Marker similarity is descriptive precedent matching, not an outcome probability.",
            "- Positive delivery scores use current asset progress and data confidence; they do not prove leadership quality.",
            "- A high downside score changes diligence priority and transaction structure, not factual culpability.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    markers = read_markers(args.markers)
    rows = score_company_execution(
        read_csv(args.market_companies),
        read_csv(args.integrity_companies),
        read_csv(args.execution_companies),
        markers,
        as_of=args.as_of,
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "companies.csv", (row.to_dict() for row in rows))
    write_csv(args.output_dir / "markers.csv", (row.to_dict() for row in markers))
    write_summary(
        args.output_dir / "summary.md",
        generated_at,
        rows,
        markers,
    )
    manifest = {
        "schema_version": "execution-scorecard-v1",
        "generated_at": generated_at,
        "as_of": args.as_of.isoformat(),
        "companies": len(rows),
        "markers": len(markers),
        "coverage_counts": dict(
            sorted(Counter(row.evidence_coverage for row in rows).items())
        ),
        "outlook_counts": dict(
            sorted(Counter(row.execution_outlook for row in rows).items())
        ),
        "outcome_labels_used_as_features": False,
        "interpretation": (
            "Research triage scores, not calibrated probabilities or findings "
            "of incompetence, fraud, or individual culpability."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(rows)} company rows and {len(markers)} markers "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
