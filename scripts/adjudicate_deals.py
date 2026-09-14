#!/usr/bin/env python3
"""Validate the local SEC review CSV, optionally freeze reviewed announcements."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.adjudication import freeze_reviews, validate_reviews  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=ROOT / "output/historical_deal_candidates/candidates.csv")
    parser.add_argument("--reviews", type=Path, default=ROOT / "output/historical_deal_candidates/adjudication_template.csv")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/reviewed_deals")
    args = parser.parse_args()
    try:
        with args.candidates.open(newline="", encoding="utf-8") as handle:
            candidates = list(csv.DictReader(handle))
        with args.reviews.open(newline="", encoding="utf-8") as handle:
            reviews = list(csv.DictReader(handle))
        result = validate_reviews(candidates, reviews)
        if args.freeze:
            path = freeze_reviews(result, args.output_dir, {
                "candidates": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
                "reviews": hashlib.sha256(args.reviews.read_bytes()).hexdigest(),
            })
            result["frozen_snapshot"] = str(path)
        print(json.dumps({key: value for key, value in result.items()
                          if key not in {"labels", "excluded_reviews"}}, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"Review validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
