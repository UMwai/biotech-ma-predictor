#!/usr/bin/env python3
"""Create a separate verified market-enriched panel; optionally run strict training."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.market_panel import enrich_market_panel
from src.research.training import TrainingBlocked, TrainingConfig, train_from_file, write_immutable_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True, help='Exact reviewed base historical feature panel')
    parser.add_argument('--market-collection', type=Path, required=True, help='Immutable Alpaca window collection manifest')
    parser.add_argument('--output-dir', type=Path, required=True, help='Separate directory for enriched research artifacts')
    parser.add_argument('--train', action='store_true', help='Attempt the existing baseline only with all fixed evidence floors')
    parser.add_argument('--test-start-year', type=int, help='First held-out year; required with --train')
    args = parser.parse_args(argv)
    try:
        if args.train and args.test_start_year is None:
            raise ValueError('--test-start-year is required with --train')
        result = enrich_market_panel(args.dataset, args.market_collection, test_start_year=args.test_start_year)
        dataset_path = write_immutable_json(result['panel'], args.output_dir, 'market-enriched-company-features')
        report_path = write_immutable_json(result, args.output_dir, 'market-panel-assembly')
        dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
        summary = {key: value for key, value in result.items() if key not in ('coverage', 'panel')}
        summary.update(dataset=str(dataset_path), dataset_sha256=dataset_hash,
                       coverage_report=str(report_path), coverage_report_sha256=report_hash)
        if args.train:
            config = TrainingConfig(args.test_start_year)
            attempt = {'schema_version': 'historical-training-attempt-v1',
                       'attempted_at': datetime.now(timezone.utc).isoformat(),
                       'model_training_performed': False, 'validated_predictive_edge': False,
                       'synthetic_test_fixture': result['panel'].get('synthetic_test_fixture', False),
                       'dataset_sha256': dataset_hash, 'coverage_report_sha256': report_hash,
                       'base_panel_sha256': result['base_panel_sha256'],
                       'market_collection_sha256': result['market_collection_sha256'],
                       'pre_test_training_support': result['pre_test_training_support']}
            try:
                artifacts = train_from_file(dataset_path, args.output_dir / 'model_training', config)
            except TrainingBlocked as exc:
                attempt.update(status='blocked', reason=str(exc))
                attempt_path = write_immutable_json(attempt, args.output_dir, 'training-attempt')
                print(json.dumps(dict(summary, status='blocked', model_training_performed=False,
                                      reason=str(exc), training_attempt=str(attempt_path))), file=sys.stderr)
                return 2
            attempt.update(status='retrospective_baseline_fitted_not_promoted', model_training_performed=True,
                           artifacts=artifacts, artifact_sha256={
                               name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                               for name, path in artifacts.items()})
            attempt_path = write_immutable_json(attempt, args.output_dir, 'training-attempt')
            summary.update(assembly_status=summary['status'], status=attempt['status'], model_training_performed=True,
                           training_attempt=str(attempt_path), training_result=attempt)
        print(json.dumps(summary))
        return 0
    except (TrainingBlocked, ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'model_training_performed': False,
                          'validated_predictive_edge': False, 'reason': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
