#!/usr/bin/env python3
"""Evaluate an externally supplied historical prediction panel; never train on SEC proxies.

Input: JSON schema sealed-company-predictions-v1 (see
docs/PREDICTION_PANEL_FORMAT.md). No bundled eligible historical panel exists.
Missing, censored, unreviewed, or leaking inputs block with exit status 2.
Reports preserve retrospective versus forward evidence modes explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.validation import PanelValidationError, write_evaluation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, help="Externally supplied sealed prediction JSON panel")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "prediction_validation")
    args = parser.parse_args(argv)
    try:
        if args.panel is None:
            raise PanelValidationError("missing eligible historical prediction panel; reviewed labels, historical exchange membership, point-in-time features, and chronological predictions are required")
        report = write_evaluation(args.panel, args.output_dir)
    except (PanelValidationError, OSError) as exc:
        print(json.dumps({"status": "blocked", "training_allowed": False, "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"status": "external_panel_contract_passed", "report": str(report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
