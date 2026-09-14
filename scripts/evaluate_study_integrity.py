#!/usr/bin/env python3
"""Build an auditable biotech study-integrity diligence report."""

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

from src.research.study_integrity import (  # noqa: E402
    CompanyIntegrityEvaluation,
    StudyIntegritySignal,
    evaluate_study_integrity,
    validate_signal_ledger,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=ROOT / "data" / "study_integrity" / "evidence.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "study_integrity",
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


def write_summary(
    path: Path,
    generated_at: str,
    evaluations: list[CompanyIntegrityEvaluation],
    signals: list[StudyIntegritySignal],
) -> None:
    lines = [
        "# Biotech Study-Integrity Diligence",
        "",
        f"**Generated:** {generated_at}",
        "",
        "> This is evidence triage, not an accusation engine. Statistical anomalies,",
        "> regulatory concerns, inspections, and retractions do not by themselves prove fraud.",
        "",
        "## Company review queue",
        "",
        "| Ticker | Company | Diligence score | Level | Open signals | Confirmed misconduct | Action |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for item in evaluations:
        lines.append(
            f"| {item.ticker} | {item.company_name} | {item.diligence_score:.2f} | "
            f"{item.diligence_level} | {item.open_signal_count} | "
            f"{item.confirmed_misconduct_count} | {item.required_action} |"
        )

    lines.extend(
        [
            "",
            "## Evidence ledger",
            "",
            "| Company / study | Category | Status | Severity | Points | Primary source |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    ordered = sorted(
        signals,
        key=lambda signal: (
            signal.company_name,
            signal.study_ids,
            -signal.weighted_points,
            signal.signal_id,
        ),
    )
    for signal in ordered:
        studies = ", ".join(signal.study_ids) or "company-level"
        lines.append(
            f"| {signal.ticker} / {studies} | {signal.category} | "
            f"{signal.evidence_status} | {signal.severity} | "
            f"{signal.weighted_points:.2f} | "
            f"[{signal.source_organization}]({signal.source_url}) |"
        )
        lines.append(f"|  |  | **Evidence:** {signal.summary} |  |  |  |")
        if signal.response_url:
            lines.append(
                f"|  |  | **Company response:** "
                f"[Response]({signal.response_url}) — {signal.response_summary} |  |  |  |"
            )

    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "- `confirmed_research_misconduct` requires an adjudicated finding from a regulator, court/government enforcement authority, or research-integrity authority.",
            "- A failed endpoint or FDA effectiveness determination is not itself misconduct.",
            "- An open inspection remains `inspection_pending`; it cannot be promoted to a finding before the authority publishes an outcome.",
            "- Sponsor rebuttals are retained next to disputed signals and do not erase the primary-source concern.",
            "- The score prioritizes diligence and must not be used as a calibrated probability of fraud or acquisition.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    payload = json.loads(args.evidence_file.read_text(encoding="utf-8"))
    signals = [
        StudyIntegritySignal.from_dict(row) for row in payload.get("signals", [])
    ]
    ledger = validate_signal_ledger(signals)
    evaluations = evaluate_study_integrity(signals)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "signals.csv", (s.to_dict() for s in signals))
    write_csv(args.output_dir / "companies.csv", (e.to_dict() for e in evaluations))
    write_summary(
        args.output_dir / "summary.md",
        generated_at,
        evaluations,
        signals,
    )
    manifest = {
        "schema_version": "study-integrity-output-v1",
        "generated_at": generated_at,
        "evidence_as_of": payload.get("as_of"),
        "source_file": str(args.evidence_file),
        "ledger": ledger,
        "interpretation": (
            "Diligence triage only; not a probability or finding of fraud."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {ledger['rows']} signals for {ledger['companies']} companies "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
