#!/usr/bin/env python3
"""Replay historical evidence, report coverage, and optionally fit the strict baseline."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.panel_assembly import assemble_research_panel
from src.research.training import TrainingBlocked, TrainingConfig, train_from_file, write_immutable_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-dir', type=Path, default=ROOT/'data/history')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'output/historical_panels')
    parser.add_argument('--publish-to-seed', action='store_true')
    parser.add_argument('--train', action='store_true', help='Fit only if verified panel passes all fixed evidence floors')
    args = parser.parse_args(argv)
    try:
        result = assemble_research_panel(args.history_dir)
        panel_path = write_immutable_json(result['panel'], args.output_dir, 'historical-company-features')
        report_path = write_immutable_json(result, args.output_dir, 'historical-panel-assembly')
        summary = {key: value for key, value in result.items() if key not in ('coverage','panel','corpus_reviews')}
        summary.update(coverage_report_sha256=report_path.stem.rsplit('-',1)[-1], panel_sha256=panel_path.stem.rsplit('-',1)[-1])
        if args.publish_to_seed:
            target = args.history_dir/'panel_seed'
            for name, payload in [('assembly.json',report_path.read_bytes()),('panel.json',panel_path.read_bytes()),
                                  ('status.json',(json.dumps(summary,indent=2,sort_keys=True)+'\n').encode())]:
                with tempfile.NamedTemporaryFile(dir=target,prefix='.panel-',delete=False) as handle:
                    temporary=Path(handle.name); handle.write(payload)
                os.replace(temporary,target/name)
        artifacts = None
        attempt_path = None
        training_result = None
        if args.train:
            frame=json.loads((args.history_dir/'panel_seed/sampling_frame.json').read_text())
            try:
                artifacts=train_from_file(panel_path,args.output_dir/'model_training',TrainingConfig(frame['cohort_plan']['test_start_year']))
            except TrainingBlocked as exc:
                attempt = {'schema_version': 'historical-training-attempt-v1',
                           'attempted_at': datetime.now(timezone.utc).isoformat(), 'status': 'blocked',
                           'model_training_performed': False, 'validated_predictive_edge': False,
                           'synthetic_test_fixture': result['panel'].get('synthetic_test_fixture', False),
                           'reason': str(exc), 'dataset_sha256': summary['panel_sha256'],
                           'coverage_report_sha256': summary['coverage_report_sha256'],
                           'pre_test_training_support': result.get('pre_test_training_support')}
                attempt_path = write_immutable_json(attempt, args.output_dir, 'training-attempt')
                print(json.dumps(dict(attempt, coverage_report=str(report_path), dataset=str(panel_path),
                                      training_attempt=str(attempt_path))), file=sys.stderr)
                return 2
            # Assembly itself never fits. Record the separate successful training
            # operation without changing the coverage report's authority flags.
            training_result = {
                'schema_version': 'historical-training-attempt-v1',
                'attempted_at': datetime.now(timezone.utc).isoformat(),
                'status': 'retrospective_baseline_fitted_not_promoted',
                'model_training_performed': True, 'validated_predictive_edge': False,
                'synthetic_test_fixture': result['panel'].get('synthetic_test_fixture', False),
                'dataset_sha256': summary['panel_sha256'],
                'coverage_report_sha256': summary['coverage_report_sha256'],
                'pre_test_training_support': result.get('pre_test_training_support'),
                'artifacts': artifacts,
                'artifact_sha256': {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                    for name, path in artifacts.items()},
            }
            attempt_path = write_immutable_json(training_result, args.output_dir, 'training-attempt')
        response = dict(summary, artifacts=artifacts, coverage_report=str(report_path), dataset=str(panel_path))
        if training_result is not None:
            response.update(assembly_status=summary['status'], status=training_result['status'],
                            model_training_performed=True, training_attempt=str(attempt_path),
                            training_result=training_result)
        print(json.dumps(response))
        return 0
    except (TrainingBlocked,ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'blocked','model_training_performed':False,'reason':str(exc)}),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
