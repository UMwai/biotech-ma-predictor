#!/usr/bin/env python3
"""Verify captured SEC research evidence offline without assigning outcome labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.sec_corpus import SECCorpusError, verify_sec_corpus
from src.research.training import write_immutable_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection", type=Path, help="Captured APRE submission or FREQ direct-response collection")
    parser.add_argument("--evidence-root", type=Path, default=ROOT, help="Root containing repository-relative source references")
    parser.add_argument("--output-dir", type=Path, help="Optional directory for a separate immutable verification report")
    args = parser.parse_args(argv)
    try:
        result = verify_sec_corpus(args.collection, evidence_root=args.evidence_root)
        summary = {k: v for k, v in result.items() if k not in {"accessions", "source_inventories"}}
        if args.output_dir is not None:
            summary["verification_report"] = str(write_immutable_json(result, args.output_dir, "sec-corpus-verification"))
        print(json.dumps(summary, indent=2))
        return 0
    except (SECCorpusError, OSError, ValueError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "outcome_review_complete": False,
                          "label_admission_allowed": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
