"""Collection orchestration never substitutes a missing market or outcome record."""
import json
from pathlib import Path

import pytest

from scripts import collect_alpaca_market_data as cli
from src.research.alpaca_data import AlpacaAccessError
from test_training import synthetic_dataset


def panel_file(tmp_path):
    panel = synthetic_dataset()
    for row in panel['observations']:
        # Stable fixture symbols; repeated rows can share one query series.
        row['ticker'] = 'TEST' + str(row['cik'])
    path = tmp_path / 'panel.json'
    path.write_text(json.dumps(panel))
    return path


def test_plan_is_read_only_and_uses_each_original_cutoff(tmp_path, monkeypatch, capsys):
    path = panel_file(tmp_path)
    monkeypatch.setattr(cli, 'load_credentials', lambda *args: pytest.fail('plan must not load secrets'))
    monkeypatch.setattr(cli, 'collect_bars', lambda *args, **kwargs: pytest.fail('plan must not connect'))
    assert cli.main(['--panel', str(path), '--plan']) == 0
    value = json.loads(capsys.readouterr().out)
    assert value['network_requests_performed'] is False
    assert value['company_observations'] == len(json.loads(path.read_text())['observations'])
    assert all(r['asof'] == r['information_cutoff_at'][:10] and r['adjustment'] == 'raw' for r in value['requests'])


def test_rejected_authentication_stops_later_windows(tmp_path, monkeypatch, capsys):
    path = panel_file(tmp_path)
    monkeypatch.setattr(cli, 'load_credentials', lambda *args: object())
    calls = []
    def rejected(*args, **kwargs):
        calls.append(1)
        raise AlpacaAccessError('HTTP 401; no automatic retry', 401)
    monkeypatch.setattr(cli, 'collect_bars', rejected)
    assert cli.main(['--panel', str(path), '--output-dir', str(tmp_path / 'market')]) == 2
    result = json.loads(capsys.readouterr().out)
    saved = json.loads(Path(result['manifest']).read_text())
    assert calls == [1] and saved['collections'] == []
    assert len(saved['gaps']) == len(cli.plan_collection(json.loads(path.read_text())))
    assert saved['model_training_performed'] is False and saved['broker_operations_performed'] is False


def test_offline_missing_cache_never_connects(tmp_path, monkeypatch, capsys):
    path = panel_file(tmp_path)
    monkeypatch.setattr(cli, 'load_credentials', lambda *args: pytest.fail('offline must not load secrets'))
    monkeypatch.setattr(cli, 'collect_bars', lambda *args, **kwargs: pytest.fail('offline must not connect'))
    assert cli.main(['--panel', str(path), '--output-dir', str(tmp_path / 'empty'), '--offline']) == 2
    result = json.loads(capsys.readouterr().out)
    saved = json.loads(Path(result['manifest']).read_text())
    assert saved['collection_mode'] == 'offline_replay' and not saved['collections'] and saved['gaps']


def test_missing_credentials_are_explicit_gaps_without_network(tmp_path, monkeypatch, capsys):
    path = panel_file(tmp_path)
    def missing(*args): raise AlpacaAccessError('credentials not configured')
    monkeypatch.setattr(cli, 'load_credentials', missing)
    monkeypatch.setattr(cli, 'collect_bars', lambda *args, **kwargs: pytest.fail('missing credentials must not connect'))
    assert cli.main(['--panel', str(path), '--output-dir', str(tmp_path / 'empty')]) == 2
    result = json.loads(capsys.readouterr().out)
    saved = json.loads(Path(result['manifest']).read_text())
    assert {x['reason'] for x in saved['gaps']} == {'credentials not configured'}
