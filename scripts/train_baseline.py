#!/usr/bin/env python3
"""Fit or apply the strict historical research baseline; see docs/BASELINE_TRAINING.md."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.training import (  # noqa: E402
    TrainingBlocked, TrainingConfig, apply_baseline, train_from_file, write_immutable_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="historical-company-features-v1 JSON")
    parser.add_argument("--test-start-year", type=int)
    parser.add_argument("--min-train-positive-events", type=int, default=5)
    parser.add_argument("--min-train-negative-companies", type=int, default=20)
    parser.add_argument("--min-test-years", type=int, default=2)
    parser.add_argument("--regularization-c", type=float, default=1.0)
    parser.add_argument("--apply-model", type=Path, help="Portable fitted final-model JSON")
    parser.add_argument("--current-features", type=Path, help="current-company-features-v1 JSON")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "baseline_training")
    args = parser.parse_args(argv)
    try:
        if args.apply_model or args.current_features:
            if not args.apply_model or not args.current_features or args.dataset:
                raise TrainingBlocked("application requires --apply-model and --current-features without --dataset")
            result = apply_baseline(json.loads(args.apply_model.read_text()), json.loads(args.current_features.read_text()))
            output = write_immutable_json(result, args.output_dir, "current-research-scores")
            print(json.dumps({"status": "research_scores_only", "probability": None, "output": str(output)}))
        else:
            if args.dataset is None or args.test_start_year is None:
                raise TrainingBlocked("missing eligible historical dataset or explicit --test-start-year; reviewed labels, verified historical membership, and point-in-time features are required")
            artifacts = train_from_file(args.dataset, args.output_dir, TrainingConfig(
                test_start_year=args.test_start_year, min_train_positive_events=args.min_train_positive_events,
                min_train_negative_companies=args.min_train_negative_companies, min_test_years=args.min_test_years,
                regularization_c=args.regularization_c,
            ))
            print(json.dumps({"status": "retrospective_baseline_fitted_not_promoted", "validated_predictive_edge": False,
                              "artifacts": artifacts}))
    except (TrainingBlocked, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "active_model_promoted": False, "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
