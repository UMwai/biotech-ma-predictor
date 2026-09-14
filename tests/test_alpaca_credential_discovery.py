"""Credential discovery selects one source; all credentials here are synthetic."""
from pathlib import Path

import pytest

from src.research.alpaca_data import CREDENTIAL_PAIRS, credential_source, load_credentials, AlpacaAccessError


@pytest.fixture
def home(tmp_path, monkeypatch):
    for pair in CREDENTIAL_PAIRS:
        for key in pair:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv('ALPACA_CREDENTIALS_FILE', raising=False)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    return tmp_path


def write_pair(path, name):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'APCA_API_KEY_ID={name}-key\nAPCA_API_SECRET_KEY={name}-secret\n')
    return path


def test_shared_config_is_found_without_copying_or_exposing_credentials(home):
    path = write_pair(home / '.config/alpaca_creds.env', 'shared')
    before = path.read_bytes()
    assert credential_source() == path
    pair = load_credentials()
    assert pair.key_id == 'shared-key' and pair.secret_key == 'shared-secret'
    assert 'shared-key' not in repr(pair) and path.read_bytes() == before


def test_explicit_file_wins_over_process_and_shared_settings(home, monkeypatch):
    write_pair(home / '.config/alpaca_creds.env', 'shared')
    chosen = write_pair(home / 'chosen.env', 'explicit')
    monkeypatch.setenv('APCA_API_KEY_ID', 'environment-key')
    monkeypatch.setenv('APCA_API_SECRET_KEY', 'environment-secret')
    monkeypatch.setenv('ALPACA_CREDENTIALS_FILE', str(home / 'missing.env'))
    assert load_credentials(chosen).key_id == 'explicit-key'


def test_process_credentials_win_over_file_reference_and_shared_default(home, monkeypatch):
    write_pair(home / '.config/alpaca_creds.env', 'shared')
    monkeypatch.setenv('ALPACA_CREDENTIALS_FILE', str(home / 'missing.env'))
    monkeypatch.setenv('APCA_API_KEY_ID', 'environment-key')
    monkeypatch.setenv('APCA_API_SECRET_KEY', 'environment-secret')
    assert credential_source() is None and load_credentials().key_id == 'environment-key'


def test_reference_overrides_shared_default(home, monkeypatch):
    write_pair(home / '.config/alpaca_creds.env', 'shared')
    chosen = write_pair(home / 'referenced.env', 'reference')
    monkeypatch.setenv('ALPACA_CREDENTIALS_FILE', str(chosen))
    assert credential_source() == chosen and load_credentials().key_id == 'reference-key'


def test_missing_config_is_reported_without_network(home):
    with pytest.raises(AlpacaAccessError, match='not configured'):
        load_credentials()


@pytest.mark.parametrize('source', ['process', 'explicit', 'reference'])
def test_incomplete_selected_source_cannot_silently_fall_back(home, monkeypatch, source):
    write_pair(home / '.config/alpaca_creds.env', 'shared')
    partial = home / 'partial.env'
    partial.write_text('APCA_API_KEY_ID=incomplete-key\n')
    if source == 'process': monkeypatch.setenv('APCA_API_KEY_ID', 'incomplete-key')
    elif source == 'reference': monkeypatch.setenv('ALPACA_CREDENTIALS_FILE', str(partial))
    with pytest.raises(ValueError, match='incomplete'):
        load_credentials(partial if source == 'explicit' else None)


def test_missing_explicit_reference_does_not_use_shared_credentials(home, monkeypatch):
    write_pair(home / '.config/alpaca_creds.env', 'shared')
    monkeypatch.setenv('ALPACA_CREDENTIALS_FILE', str(home / 'missing.env'))
    with pytest.raises(FileNotFoundError): load_credentials()
