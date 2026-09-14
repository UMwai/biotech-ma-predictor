"""Synthetic market fixtures test integrity; they are not acquisition evidence."""
import copy
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from scripts.assemble_alpaca_panel import main
from src.research.alpaca_data import make_request, request_url
from src.research.market_features import FEATURE_UNITS, MARKET_TIMEZONE, _expected_sessions
from src.research.market_panel import enrich_market_panel

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def market_case(tmp_path):
    observations = []
    for year in (2021, 2023, 2024):
        at = datetime(year, 1, 1, tzinfo=timezone.utc)
        horizon = at + timedelta(days=365)
        for cik, ticker in ((1, 'POSI'), (2, 'NEGA')):
            positive = cik == 1
            observations.append({'cik': cik, 'ticker': ticker, 'observation_at': at.isoformat(), 'horizon_days': 365,
                'information_cutoff_at': (at - timedelta(seconds=1)).isoformat(),
                'feature_max_available_at': (at - timedelta(days=45)).isoformat(),
                'features': {'cash_usd': 1000.0 * cik, 'assets_usd': None},
                'financial_evidence': {'synthetic_test_fixture': True, 'cash_source': f'synthetic://financial/{cik}/{year}'},
                'risk_set_eligible': True, 'risk_set_exclusion_reason': None,
                'membership': {'kind': 'historical_exchange_membership', 'source_uri': 'synthetic://membership',
                    'source_sha256': 'a' * 64, 'security_type': 'common_equity', 'biotech_eligible': True,
                    'cik': cik, 'ticker': ticker, 'valid_from': '2017-01-01T00:00:00Z', 'valid_until': '2026-01-01T00:00:00Z'},
                'label': {'reviewed': True, 'review_id': f'synthetic-{cik}-{year}',
                    'source_uri': 'synthetic://outcome', 'source_sha256': 'b' * 64,
                    'event_class': 'change_of_control_announcement' if positive else 'no_change_of_control_announcement',
                    'announcement_at': (at + timedelta(days=100)).isoformat() if positive else None,
                    'observed_through': (horizon + timedelta(days=5)).isoformat(),
                    'available_at': (horizon + timedelta(days=10)).isoformat()}})
    panel = {'schema_version': 'historical-company-features-v1', 'data_as_of': NOW.isoformat(),
             'feature_names': ['cash_usd', 'assets_usd'], 'feature_units': {'cash_usd': 'USD', 'assets_usd': 'USD'},
             'synthetic_test_fixture': True, 'observations': observations}
    base_path = tmp_path / 'base.json'
    collection_path = tmp_path / 'market' / 'collection.json'
    collection = {'schema_version': 'alpaca-panel-market-collection-v1', 'base_panel_sha256': save(base_path, panel),
                  'feed': 'sip', 'collected_at': NOW.isoformat(), 'collections': [], 'gaps': [], 'model_training_performed': False}
    manifests, raw_responses = [], []
    for year in (2021, 2023, 2024):
        cutoff = datetime(year, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        request = make_request(['POSI', 'NEGA'], (cutoff - timedelta(days=150)).isoformat(),
                               cutoff.isoformat(), cutoff.date().isoformat())
        days = _expected_sessions(cutoff.astimezone(MARKET_TIMEZONE).date() - timedelta(days=1), 64)
        bars = [{'t': datetime.combine(day, time.min, MARKET_TIMEZONE).isoformat(),
                 'o': 10 + index / 100, 'h': 11 + index / 100,
                 'l': 9 + index / 100, 'c': 10 + index / 100, 'v': 1000, 'n': 20, 'vw': 10 + index / 100}
                for index, day in enumerate(days)]
        response = {'bars': {ticker: copy.deepcopy(bars) for ticker in request['symbols']}, 'next_page_token': None}
        directory = collection_path.parent / str(year)
        raw_hash = save(directory / 'response.json', response)
        receipt = {'source_uri': request_url(request), 'effective_source_uri': request_url(request),
                   'source_relative_path': 'response.json', 'source_sha256': raw_hash,
                   'source_bytes': (directory / 'response.json').stat().st_size, 'retrieved_at': NOW.isoformat()}
        manifest = {'schema_version': 'alpaca-stock-bars-v1', 'request': request, 'pages': [receipt],
                    'bars_by_symbol': copy.deepcopy(response['bars']), 'retrieved_at': NOW.isoformat(),
                    'query_complete': True, 'original_vendor_vintage_archived': False, 'outcome_label': None}
        path = directory / 'manifest.json'
        collection['collections'].append({'information_cutoff_at': cutoff.isoformat(), 'asof': cutoff.date().isoformat(),
                    'symbols': request['symbols'], 'bars_manifest_relative_path': str(path.relative_to(collection_path.parent)),
                    'bars_manifest_sha256': save(path, manifest)})
        manifests.append(manifest)
        raw_responses.append(response)
    save(collection_path, collection)

    def persist(index=None, *, update_response=False, update_base=False):
        if update_base:
            collection['base_panel_sha256'] = save(base_path, panel)
        if index is not None:
            entry = collection['collections'][index]
            path = collection_path.parent / entry['bars_manifest_relative_path']
            manifest = manifests[index]
            if update_response:
                response = raw_responses[index]
                raw_hash = save(path.parent / 'response.json', response)
                manifest['pages'][0].update(source_sha256=raw_hash, source_bytes=(path.parent / 'response.json').stat().st_size)
                manifest['bars_by_symbol'] = {symbol: response['bars'].get(symbol, []) for symbol in manifest['request']['symbols']}
            entry['bars_manifest_sha256'] = save(path, manifest)
        save(collection_path, collection)

    return {'panel': panel, 'collection': collection, 'base_path': base_path, 'collection_path': collection_path,
            'manifests': manifests, 'responses': raw_responses, 'persist': persist}


def run(case, **kwargs):
    return enrich_market_panel(case['base_path'], case['collection_path'], now=NOW, **kwargs)


def test_enrichment_preserves_every_label_membership_and_financial_value(market_case):
    original_bytes = market_case['base_path'].read_bytes()
    result = run(market_case, test_start_year=2023)
    assert result['base_observations'] == result['enriched_observations'] == 6
    assert result['observations_with_market_features'] == 6
    assert result['model_training_performed'] is False
    assert result['pre_test_training_support']['distinct_positive_events'] == 1
    assert result['pre_test_training_support']['distinct_negative_companies'] == 1
    for old, new in zip(market_case['panel']['observations'], result['panel']['observations']):
        for field in ('label', 'membership', 'financial_evidence', 'risk_set_eligible', 'risk_set_exclusion_reason', 'cik', 'ticker'):
            assert new[field] == old[field]
        assert all(new['features'][name] == value for name, value in old['features'].items())
        assert all(new['features'][name] is not None for name in FEATURE_UNITS)
        assert new['market_evidence']['original_vendor_vintage_archived'] is False
        assert new['market_evidence']['calculation']['provenance']['historical_publication_proof'] is False
        assert datetime.fromisoformat(new['feature_max_available_at']) <= datetime.fromisoformat(new['information_cutoff_at'])
    assert market_case['base_path'].read_bytes() == original_bytes


def test_new_assembly_advances_information_freeze_without_backdating_vendor_history(market_case):
    case = market_case
    case['panel']['data_as_of'] = '2026-09-08T00:00:00+00:00'
    case['persist'](update_base=True)
    result = run(case, test_start_year=2023)
    assert result['panel']['data_as_of'] == NOW.isoformat()
    assert result['panel']['market_enrichment']['base_data_as_of'] == case['panel']['data_as_of']
    assert result['panel']['market_enrichment']['original_vendor_vintage_archived'] is False
    assert result['pre_test_training_support']['distinct_negative_companies'] == 1
    for old, new in zip(case['panel']['observations'], result['panel']['observations']):
        assert new['label'] == old['label'] and new['information_cutoff_at'] == old['information_cutoff_at']


def test_later_assembly_does_not_legalize_an_invalid_base_freeze(market_case):
    case = market_case
    case['panel']['data_as_of'] = '2026-09-08T00:00:00+00:00'
    case['panel']['observations'][0]['label']['available_at'] = '2026-09-10T00:00:00+00:00'
    case['persist'](update_base=True)
    with pytest.raises(ValueError): run(case)


def test_future_assembly_timestamp_is_rejected(market_case):
    with pytest.raises(ValueError, match='assembly freeze is in the future'):
        enrich_market_panel(market_case['base_path'], market_case['collection_path'],
                            now=datetime.now(timezone.utc) + timedelta(days=1))


@pytest.mark.parametrize('change, expected', [
    ('base_hash', 'base panel SHA-256'), ('manifest_hash', 'manifest SHA-256'),
    ('raw_bytes', 'hash/size'), ('missing_cutoff', 'omits an expected'),
    ('extra_cutoff', 'extra or duplicate'), ('missing_symbol', 'symbols differ'),
    ('extra_symbol', 'symbols differ'), ('identity', 'membership must bind'),
    ('future_financial', 'features/cutoff'), ('unreviewed_label', 'not reviewed'),
    ('unsupported_label', 'unsupported event class'), ('vintage', 'vintage'),
    ('feed', 'SIP'), ('missing_classes', 'base panel SHA-256'),
])
def test_tampering_and_silent_inventory_changes_fail_closed(market_case, change, expected):
    case = market_case
    collection = case['collection']
    if change == 'base_hash':
        case['base_path'].write_bytes(case['base_path'].read_bytes() + b' ')
    elif change == 'manifest_hash':
        collection['collections'][0]['bars_manifest_sha256'] = '0' * 64
        case['persist']()
    elif change == 'raw_bytes':
        (case['collection_path'].parent / '2021/response.json').write_bytes(b'{}')
    elif change == 'missing_cutoff':
        collection['collections'].pop(); case['persist']()
    elif change == 'extra_cutoff':
        collection['collections'].append(copy.deepcopy(collection['collections'][0])); case['persist']()
    elif change in ('missing_symbol', 'extra_symbol'):
        collection['collections'][0]['symbols'] = ['POSI'] if change == 'missing_symbol' else ['POSI', 'NEGA', 'EXTRA']
        case['persist']()
    elif change == 'identity':
        case['panel']['observations'][0]['membership']['cik'] = 999; case['persist'](update_base=True)
    elif change == 'future_financial':
        case['panel']['observations'][0]['feature_max_available_at'] = '2026-01-01T00:00:00Z'; case['persist'](update_base=True)
    elif change == 'unreviewed_label':
        case['panel']['observations'][0]['label']['reviewed'] = False; case['persist'](update_base=True)
    elif change == 'unsupported_label':
        case['panel']['observations'][0]['label']['event_class'] = 'unreviewed_candidate'; case['persist'](update_base=True)
    elif change == 'vintage':
        case['manifests'][0]['original_vendor_vintage_archived'] = True; case['persist'](0)
    elif change == 'feed':
        collection['feed'] = 'blended'; case['persist']()
    else:
        case['panel']['observations'] = [row for row in case['panel']['observations'] if row['cik'] == 1]
        save(case['base_path'], case['panel'])
    with pytest.raises(ValueError, match=expected):
        run(case)


@pytest.mark.parametrize('field,value', [('end', '2021-01-01T00:00:00Z'), ('asof', '2021-01-01'),
                                        ('start', '2020-12-01T00:00:00Z'), ('feed', 'iex')])
def test_request_identity_cannot_change_even_when_manifest_is_rehashed(market_case, field, value):
    manifest = market_case['manifests'][0]
    manifest['request'][field] = value
    market_case['persist'](0)
    with pytest.raises(ValueError):
        run(market_case)


@pytest.mark.parametrize('change,expected', [('end', 'end differs'), ('lookback', 'lookback'), ('feed', 'same declared feed')])
def test_self_consistent_source_query_still_must_match_panel_contract(market_case, change, expected):
    manifest = market_case['manifests'][0]
    request = manifest['request']
    if change == 'end':
        request['end'] = '2020-12-31T22:59:59+00:00'
    elif change == 'lookback':
        request['start'] = '2020-12-01T00:00:00+00:00'
        for symbol in request['symbols']:
            market_case['responses'][0]['bars'][symbol] = [bar for bar in market_case['responses'][0]['bars'][symbol]
                                                           if bar['t'] >= request['start']]
    else:
        request['feed'] = 'iex'
    manifest['pages'][0].update(source_uri=request_url(request), effective_source_uri=request_url(request))
    market_case['persist'](0, update_response=True)
    with pytest.raises(ValueError, match=expected):
        run(market_case)


def test_explicit_iex_is_supported_without_consolidated_volume_claim(market_case):
    market_case['collection']['feed'] = 'iex'
    for index, manifest in enumerate(market_case['manifests']):
        manifest['request']['feed'] = 'iex'
        manifest['pages'][0].update(source_uri=request_url(manifest['request']),
                                     effective_source_uri=request_url(manifest['request']))
        market_case['persist'](index)
    result = run(market_case)
    assert result['feed'] == result['panel']['market_enrichment']['feed'] == 'iex'
    assert result['market_coverage_scope'] == 'iex_venue_only'
    assert all(row['market_coverage_scope'] == 'iex_venue_only' for row in result['coverage'])


def test_missing_bars_remain_null_without_changing_either_outcome(market_case):
    response = market_case['responses'][0]
    response['bars'].pop('NEGA')
    market_case['persist'](0, update_response=True)
    result = run(market_case)
    rows = result['panel']['observations']
    negative = next(row for row in rows if row['ticker'] == 'NEGA' and row['observation_at'].startswith('2021'))
    assert all(negative['features'][name] is None for name in FEATURE_UNITS)
    assert negative['label'] == market_case['panel']['observations'][1]['label']
    assert negative['feature_max_available_at'] == market_case['panel']['observations'][1]['feature_max_available_at']
    assert len(rows) == 6


def test_explicit_failed_windows_are_preserved_but_unexplained_omissions_fail(market_case):
    entry = market_case['collection']['collections'].pop(0)
    market_case['collection']['gaps'].append({key: entry[key] for key in ('information_cutoff_at', 'asof', 'symbols')} | {'reason': 'Synthetic provider unavailable'})
    market_case['persist']()
    result = run(market_case)
    assert result['failed_collection_windows'] == 1 and result['observations_without_market_features'] == 2
    assert result['base_observations'] == result['enriched_observations'] == 6
    assert all(result['panel']['observations'][i]['label'] == market_case['panel']['observations'][i]['label'] for i in range(6))


def test_all_windows_unavailable_keeps_all_rows_without_model_or_vintage_claims(market_case):
    collection = market_case['collection']
    collection['gaps'] = [{key: entry[key] for key in ('information_cutoff_at', 'asof', 'symbols')} |
                          {'reason': 'Synthetic authentication probe failed; no bars requested'}
                          for entry in collection['collections']]
    collection['collections'] = []
    market_case['persist']()
    result = run(market_case, test_start_year=2023)
    assert result['failed_collection_windows'] == 3
    assert result['status'] == 'market_data_unavailable'
    assert result['observations_without_market_features'] == result['enriched_observations'] == 6
    assert result['original_vendor_vintage_archived'] is False
    assert result['model_training_performed'] is False
    for original, row in zip(market_case['panel']['observations'], result['panel']['observations']):
        assert row['label'] == original['label'] and row['financial_evidence'] == original['financial_evidence']
        assert row['feature_max_available_at'] == original['feature_max_available_at']
        assert all(row['features'][name] is None for name in FEATURE_UNITS)


def test_bars_before_reviewed_membership_are_masked(market_case):
    first = market_case['panel']['observations'][0]
    first['membership']['valid_from'] = '2020-12-20T00:00:00Z'
    market_case['persist'](update_base=True)
    row = run(market_case)['panel']['observations'][0]
    assert row['market_evidence']['bars_before_membership_excluded'] > 0
    assert all(row['features'][name] is None for name in FEATURE_UNITS)


def test_bar_whose_day_is_not_completed_cannot_enter_features(market_case):
    before = run(market_case)['panel']['observations'][0]['features']
    for ticker in ('NEGA', 'POSI'):
        market_case['responses'][0]['bars'][ticker].append(
            {'t': '2020-12-31T05:00:00Z', 'o': 1000, 'h': 1001, 'l': 999, 'c': 1000, 'v': 1000})
    market_case['persist'](0, update_response=True)
    row = run(market_case)['panel']['observations'][0]
    assert row['features'] == before
    assert row['market_evidence']['calculation']['provenance']['excluded_incomplete_or_future_bar_count'] == 1


def test_manifest_paths_cannot_escape_collection_directory(market_case, tmp_path):
    entry = market_case['collection']['collections'][0]
    original = market_case['collection_path'].parent / entry['bars_manifest_relative_path']
    outside = tmp_path / 'outside.json'; outside.write_bytes(original.read_bytes())
    entry['bars_manifest_relative_path'] = '../outside.json'
    market_case['persist']()
    with pytest.raises(ValueError, match='outside collection'):
        run(market_case)


def test_cli_saves_separate_artifacts_and_truthful_blocked_training(market_case, tmp_path, capsys):
    args = ['--dataset', str(market_case['base_path']), '--market-collection', str(market_case['collection_path']),
            '--output-dir', str(tmp_path / 'out'), '--test-start-year', '2023']
    assert main(args) == 0
    response = json.loads(capsys.readouterr().out)
    assert response['model_training_performed'] is False
    assert Path(response['dataset']).is_file()
    assert main(args + ['--train']) == 2
    blocked = json.loads(capsys.readouterr().err)
    attempt = json.loads(Path(blocked['training_attempt']).read_bytes())
    assert blocked['model_training_performed'] is attempt['model_training_performed'] is False
    assert attempt['status'] == 'blocked' and attempt['synthetic_test_fixture'] is True
    assert attempt['dataset_sha256'] == hashlib.sha256(Path(blocked['dataset']).read_bytes()).hexdigest()


def test_cli_success_receipt_is_separate_from_unfitted_assembly(market_case, tmp_path, capsys, monkeypatch):
    import scripts.assemble_alpaca_panel as cli
    def fake_train(dataset, output, config):
        config.validate()
        artifact = output / 'synthetic-model.json'
        save(artifact, {'synthetic_test_fixture': True, 'test_stub': True})
        return {'final_model': str(artifact)}
    monkeypatch.setattr(cli, 'train_from_file', fake_train)
    args = ['--dataset', str(market_case['base_path']), '--market-collection', str(market_case['collection_path']),
            '--output-dir', str(tmp_path / 'out'), '--train', '--test-start-year', '2023']
    assert cli.main(args) == 0
    response = json.loads(capsys.readouterr().out)
    assert response['model_training_performed'] is True and response['validated_predictive_edge'] is False
    assert json.loads(Path(response['coverage_report']).read_bytes())['model_training_performed'] is False
    receipt = json.loads(Path(response['training_attempt']).read_bytes())
    assert receipt['synthetic_test_fixture'] is True
    assert receipt['artifact_sha256']['final_model'] == hashlib.sha256(Path(receipt['artifacts']['final_model']).read_bytes()).hexdigest()
