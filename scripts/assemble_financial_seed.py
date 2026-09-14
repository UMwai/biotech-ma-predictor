#!/usr/bin/env python3
"""Validate real pre-acquisition report facts and save immutable financial features."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.financial_seed import assemble_financial_seed  # noqa: E402
from src.research.training import write_immutable_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=ROOT / "data/history/financial_seed/financial_records.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "data/history/frozen_labels.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/historical_financials")
    parser.add_argument("--publish-to-seed", action="store_true", help="Also save a verified feature copy beside the source records for local snapshot assembly")
    args = parser.parse_args()
    try:
        result = assemble_financial_seed(args.records, args.labels)
        output = write_immutable_json(result, args.output_dir, "reviewed-financial-features")
        if args.publish_to_seed:
            with tempfile.NamedTemporaryFile(dir=args.records.parent, prefix=".features-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(output.read_bytes())
            os.replace(temporary, args.records.parent / "feature_snapshot.json")
        print(json.dumps({"status": "financial_evidence_assembled", "records": result["financial_record_count"],
                          "issuers": result["distinct_issuers"], "training_allowed": False, "output": str(output)}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
