"""CLI receipts distinguish source assembly, blocked fitting, and synthetic fits."""
import hashlib
import json

import pytest

from scripts import assemble_research_panel as cli
from test_training import requires_model, synthetic_dataset


def setup_assembly(tmp_path, monkeypatch):
    history = tmp_path / 'history'
    panel_dir = history / 'panel_seed'
    panel_dir.mkdir(parents=True)
    (panel_dir / 'sampling_frame.json').write_text(json.dumps({'cohort_plan': {'test_start_year': 2021}}))
    report = {'schema_version': 'historical-panel-assembly-v1', 'status': 'adjudicated_panel_ready_for_training_checks',
              'model_training_performed': False, 'validated_predictive_edge': False,
              'panel': synthetic_dataset(), 'coverage': [], 'corpus_reviews': []}
    monkeypatch.setattr(cli, 'assemble_research_panel', lambda path: report)
    args = ['--history-dir', str(history), '--output-dir', str(tmp_path / 'artifacts'),
            '--publish-to-seed', '--train']
    return panel_dir, args


def test_failed_fit_saves_blocked_receipt_and_keeps_assembly_honest(tmp_path, monkeypatch, capsys):
    panel_dir, args = setup_assembly(tmp_path, monkeypatch)

    def blocked(*args):
        raise cli.TrainingBlocked('comparison outcomes unavailable')

    monkeypatch.setattr(cli, 'train_from_file', blocked)
    assert cli.main(args) == 2
    result = json.loads(capsys.readouterr().err)
    assert result['model_training_performed'] is False
    assert result['reason'] == 'comparison outcomes unavailable'
    from pathlib import Path
    receipt = json.loads(Path(result['training_attempt']).read_text())
    assert receipt['dataset_sha256'] == hashlib.sha256((panel_dir / 'panel.json').read_bytes()).hexdigest()
    assert not list((tmp_path / 'artifacts').rglob('final-model-*.json'))


@requires_model
def test_successful_synthetic_fit_reports_fitting_without_promoting_assembly(tmp_path, monkeypatch, capsys):
    panel_dir, args = setup_assembly(tmp_path, monkeypatch)
    assert cli.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['model_training_performed'] is True
    assert result['validated_predictive_edge'] is False
    assert result['status'] == 'retrospective_baseline_fitted_not_promoted'
    assert result['training_result']['synthetic_test_fixture'] is True
    assert json.loads((panel_dir / 'status.json').read_text())['model_training_performed'] is False
    from pathlib import Path
    receipt = json.loads(Path(result['training_attempt']).read_text())
    for name, path in receipt['artifacts'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == receipt['artifact_sha256'][name]
