#!/usr/bin/env python3
"""Build an evidence-backed company and leadership execution-risk report."""

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

from src.research.execution_risk import (  # noqa: E402
    ExecutionRiskSignal,
    evaluate_execution_risk,
    validate_execution_ledger,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=ROOT / "data" / "execution_risk" / "evidence.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "execution_risk",
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


def write_summary(path: Path, generated_at: str, evaluations: list[Any]) -> None:
    lines = [
        "# Company and Leadership Execution-Risk Review",
        "",
        f"**Generated:** {generated_at}",
        "",
        "> This report scores documented execution events and role accountability.",
        "> It does not classify any company or person as incompetent.",
        "",
        "| Ticker | Company | Execution risk | Leadership risk | Formal failures | Individual findings | Action |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in evaluations:
        lines.append(
            f"| {item.ticker} | {item.company_name} | "
            f"{item.execution_risk_score:.2f} ({item.execution_risk_level}) | "
            f"{item.leadership_risk_score:.2f} ({item.leadership_risk_level}) | "
            f"{item.formal_failure_count} | "
            f"{item.confirmed_individual_finding_count} | "
            f"{item.required_action} |"
        )
        for driver in item.primary_risk_drivers:
            lines.append(f"|  | **Evidence** | {driver} |  |  |  |  |")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Leadership-team scope records functional accountability during an event window, not culpability.",
            "- Named people are prohibited unless an authority publishes an individual enforcement finding.",
            "- Company statements and rebuttals remain beside the cited primary evidence.",
            "- Missing signals mean limited coverage, not proof of competent execution.",
            "- Scores are diligence priorities, not probabilities of failure.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    payload = json.loads(args.evidence_file.read_text(encoding="utf-8"))
    signals = [ExecutionRiskSignal.from_dict(row) for row in payload.get("signals", [])]
    ledger = validate_execution_ledger(signals)
    evaluations = evaluate_execution_risk(signals)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "signals.csv", (row.to_dict() for row in signals))
    write_csv(
        args.output_dir / "companies.csv",
        (row.to_dict() for row in evaluations),
    )
    write_summary(args.output_dir / "summary.md", generated_at, evaluations)
    manifest = {
        "schema_version": "execution-risk-output-v1",
        "generated_at": generated_at,
        "evidence_as_of": payload.get("as_of"),
        "ledger": ledger,
        "interpretation": (
            "Execution and role-accountability diligence; not an incompetence "
            "or individual misconduct classifier."
        ),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {ledger['rows']} execution signals for "
        f"{ledger['companies']} companies to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
