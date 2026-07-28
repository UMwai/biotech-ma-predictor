#!/usr/bin/env python3
"""Join market M&A research with integrity and execution-risk evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.strategic_overlay import (  # noqa: E402
    StrategicDiligenceRow,
    build_strategic_diligence_matrix,
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
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "strategic_matrix",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def _table(lines: list[str], title: str, rows: list[StrategicDiligenceRow]) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Ticker | Company | M&A score/rank | Integrity | Execution | Leadership | Archetype |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    if not rows:
        lines.append(
            "| — | No companies currently meet this rule | — | — | — | — | — |"
        )
    for row in rows:
        lines.append(
            f"| {row.ticker} | {row.company_name} | "
            f"{row.ma_research_score:.2f} / {row.ma_rank} | "
            f"{row.integrity_diligence_score:.2f} | "
            f"{row.execution_risk_score:.2f} | "
            f"{row.leadership_risk_score:.2f} | "
            f"{row.strategic_archetype} |"
        )
    lines.append("")


def write_summary(
    path: Path, generated_at: str, rows: list[StrategicDiligenceRow]
) -> None:
    unscreened = [
        row for row in rows if row.strategic_archetype == "ma_candidate_risk_unscreened"
    ][:25]
    structured = [
        row
        for row in rows
        if row.strategic_archetype
        in {
            "diligence_sensitive_target",
            "distressed_or_structured_target",
            "distressed_asset_watch",
        }
    ][:25]
    failure = sorted(
        (
            row
            for row in rows
            if row.strategic_archetype
            in {"failure_watch", "leadership_execution_watch"}
        ),
        key=lambda row: (
            -row.combined_diligence_risk,
            -row.leadership_risk_score,
            row.ticker,
        ),
    )[:25]
    lines = [
        "# Biotech Strategic Matrix",
        "",
        f"**Generated:** {generated_at}",
        "",
        "> M&A attractiveness and execution risk are independent axes. A distressed",
        "> company can create an asset opportunity without being a sound whole-company target.",
        "",
    ]
    _table(lines, "High-M&A candidates awaiting risk coverage", unscreened)
    _table(lines, "Diligence-sensitive and structured situations", structured)
    _table(lines, "Execution and leadership failure watch", failure)
    lines.extend(
        [
            "## Current coverage constraint",
            "",
            "The market evaluator covers the broad listed universe, but company-specific",
            "execution evidence is currently populated only for the verified Capricor case.",
            "All other `limited_no_detected_signals` rows are unscreened—not cleared.",
            "",
            "## Decision rules",
            "",
            "- High M&A + low reviewed risk: whole-company strategic diligence.",
            "- High M&A + elevated risk: staged diligence and contingent consideration.",
            "- High M&A + high risk: asset purchase, option, milestone, or CVR structure.",
            "- Low M&A + high risk: failure watch; monitor financing, restructuring, governance, and asset-sale catalysts.",
            "- Named-leader conclusions require official individual findings; team scores indicate functional accountability only.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    matrix = build_strategic_diligence_matrix(
        read_csv(args.market_companies),
        read_csv(args.integrity_companies),
        read_csv(args.execution_companies),
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "companies.csv", (row.to_dict() for row in matrix))
    write_summary(args.output_dir / "summary.md", generated_at, matrix)
    counts = Counter(row.strategic_archetype for row in matrix)
    manifest = {
        "schema_version": "strategic-diligence-matrix-v1",
        "generated_at": generated_at,
        "companies": len(matrix),
        "company_specific_risk_evidence": sum(
            row.risk_coverage == "company_specific_evidence" for row in matrix
        ),
        "archetype_counts": dict(sorted(counts.items())),
        "interpretation": (
            "Dual-axis research triage; neither axis is a calibrated probability."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(matrix)} company rows to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
