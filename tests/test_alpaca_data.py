"""Authenticated data access must preserve identity, pagination and unknowns."""
from datetime import datetime, timezone
import json

import pytest

from src.research import alpaca_data as api


def bar(day='2020-10-01', close=10):
    return {'t': day + 'T04:00:00Z', 'o': 10, 'h': 12, 'l': 9, 'c': close, 'v': 100, 'n': 3, 'vw': 10}


def request(symbols=None):
    return api.make_request(symbols or ['CDXS', 'STRO'], '2020-10-01T00:00:00Z',
                            '2020-12-31T23:59:59Z', '2020-12-31')


def collect(tmp_path, monkeypatch, pages=None):
    pages = iter(pages or [{'bars': {'CDXS': [bar()]}, 'next_page_token': 'next'},
                          {'bars': {'STRO': [bar()]}, 'next_page_token': None}])
    seen = []
    def fetch(url, credentials):
        seen.append(url)
        return json.dumps(next(pages)).encode(), {'effective_source_uri': url,
                                                'retrieved_at': datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(api, '_fetch', fetch)
    monkeypatch.setattr(api.time, 'sleep', lambda value: None)
    r = request()
    p = api.collect_bars(r['symbols'], r['start'], r['end'], r['asof'], tmp_path,
                         credentials=api.Credentials('test-key', 'test-secret'))
    return p, seen


def test_page_limit_is_global_and_missing_symbols_are_explicit(tmp_path, monkeypatch):
    path, calls = collect(tmp_path, monkeypatch)
    data = api.verify_bars_manifest(path)
    assert len(calls) == 2 and 'page_token=next' in calls[-1]
    assert set(data['bars_by_symbol']) == {'CDXS', 'STRO'}
    assert data['original_vendor_vintage_archived'] is False and data['outcome_label'] is None
    empty, _ = collect(tmp_path / 'empty', monkeypatch, [{'bars': {'CDXS': [bar()]}, 'next_page_token': None}])
    assert api.verify_bars_manifest(empty)['bars_by_symbol']['STRO'] == []


@pytest.mark.parametrize('change', ['raw_hash', 'source_query', 'redirect', 'normalized_bar', 'missing_page',
                                    'future_adjustment', 'today_mapping', 'vintage', 'outcome', 'path_escape'])
def test_manifest_tampering_fails(tmp_path, monkeypatch, change):
    path, _ = collect(tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    if change == 'raw_hash': (tmp_path / data['pages'][0]['source_relative_path']).write_bytes(b'{}')
    elif change == 'source_query': data['pages'][0]['source_uri'] += '&feed=iex'
    elif change == 'redirect': data['pages'][0]['effective_source_uri'] = 'https://other.invalid/'
    elif change == 'normalized_bar': data['bars_by_symbol']['CDXS'][0]['c'] = 11
    elif change == 'missing_page': data['pages'].pop()
    elif change == 'future_adjustment': data['request']['adjustment'] = 'all'
    elif change == 'today_mapping': data['request']['asof'] = '2026-09-12'
    elif change == 'vintage': data['original_vendor_vintage_archived'] = True
    elif change == 'outcome': data['outcome_label'] = 0
    else: data['pages'][0]['source_relative_path'] = '../outside.json'
    path.write_text(json.dumps(data))
    with pytest.raises((ValueError, OSError)):
        api.verify_bars_manifest(path)


@pytest.mark.parametrize('change', ['duplicate', 'wrong_symbol', 'future_bar', 'nan', 'negative_volume', 'bad_ohlc'])
def test_unusable_bars_fail(change):
    data = {'bars': {'CDXS': [bar()]}, 'next_page_token': None}
    if change == 'duplicate': data['bars']['CDXS'].append(bar())
    elif change == 'wrong_symbol': data['bars']['OTHER'] = data['bars'].pop('CDXS')
    elif change == 'future_bar': data['bars']['CDXS'][0]['t'] = '2021-01-01T04:00:00Z'
    elif change == 'nan': data['bars']['CDXS'][0]['c'] = float('nan')
    elif change == 'negative_volume': data['bars']['CDXS'][0]['v'] = -1
    else: data['bars']['CDXS'][0]['h'] = 5
    with pytest.raises(ValueError): api.parse_page(json.dumps(data).encode(), request())


def test_overlap_and_pagination_cycles_are_not_complete(tmp_path, monkeypatch):
    repeated = [{'bars': {'CDXS': [bar()]}, 'next_page_token': 'repeat'},
                {'bars': {'CDXS': [bar()]}, 'next_page_token': 'repeat'}]
    with pytest.raises(ValueError, match='repeated'):
        collect(tmp_path, monkeypatch, repeated)
    overlap = [{'bars': {'CDXS': [bar()]}, 'next_page_token': 'next'},
               {'bars': {'CDXS': [bar()]}, 'next_page_token': None}]
    with pytest.raises(ValueError, match='overlaps'):
        collect(tmp_path / 'overlap', monkeypatch, overlap)


def test_cached_replay_needs_no_credentials_and_checks_requested_identity(tmp_path, monkeypatch):
    path, _ = collect(tmp_path, monkeypatch)
    monkeypatch.setattr(api, '_fetch', lambda *args: pytest.fail('unexpected network request'))
    monkeypatch.setattr(api, 'load_credentials', lambda *args: pytest.fail('unexpected credential loading'))
    r = request()
    assert api.collect_bars(r['symbols'], r['start'], r['end'], r['asof'], tmp_path) == path


def test_credentials_are_not_represented_or_executed(tmp_path, monkeypatch):
    p = tmp_path / 'private.env'
    p.write_text('export ALPACA_API_KEY="local-key"\nALPACA_SECRET_KEY="local-secret" # comment\nUNRELATED=$(touch never)\n')
    creds = api.load_credentials(p)
    assert creds.key_id == 'local-key' and creds.secret_key == 'local-secret'
    assert 'local-key' not in repr(creds) and 'local-secret' not in repr(creds)
    p.write_text('ALPACA_API_KEY=$(touch secret)\nALPACA_SECRET_KEY=x\n')
    with pytest.raises(ValueError): api.load_credentials(p)
    p.write_text('APCA_API_KEY_ID=one\nAPCA_API_SECRET_KEY=two\nALPACA_API_KEY=three\nALPACA_SECRET_KEY=four\n')
    with pytest.raises(ValueError, match='conflicting'): api.load_credentials(p)


def test_authentication_failure_has_no_retry_or_secret_receipt(tmp_path, monkeypatch):
    calls = []
    def rejected(*args):
        calls.append(1)
        raise api.AlpacaAccessError('authentication failed', 401)
    monkeypatch.setattr(api, '_fetch', rejected)
    r = request()
    for _ in range(2):
        with pytest.raises(api.AlpacaAccessError):
            api.collect_bars(r['symbols'], r['start'], r['end'], r['asof'], tmp_path,
                             credentials=api.Credentials('private-key', 'private-secret'))
    assert calls == [1]
    receipt = next(tmp_path.glob('failure-*.json')).read_text()
    assert 'private-key' not in receipt and 'private-secret' not in receipt
    assert json.loads(receipt)['http_status'] == 401


def test_incomplete_http_body_is_a_durable_sanitized_failure(tmp_path, monkeypatch):
    from http.client import IncompleteRead
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def geturl(self): return api.request_url(request())
        def read(self, size): raise IncompleteRead(b'partial', 500)
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(api, 'build_opener', lambda *args: Opener())
    r = request()
    with pytest.raises(api.AlpacaAccessError, match='IncompleteRead'):
        api.collect_bars(r['symbols'], r['start'], r['end'], r['asof'], tmp_path,
                         credentials=api.Credentials('private-key', 'private-secret'))
    receipt = next(tmp_path.glob('failure-*.json')).read_text()
    assert 'private-secret' not in receipt and json.loads(receipt)['pages_received'] == []


def test_invalid_direct_credentials_and_header_errors_cannot_expose_values(tmp_path, monkeypatch):
    secret = 'synthetic-private-header-value'
    with pytest.raises(ValueError) as error:
        api.Credentials('key', secret + '\r\nInjected: yes')
    assert secret not in str(error.value)
    class Opener:
        def open(self, *args, **kwargs): raise ValueError('invalid header ' + secret)
    monkeypatch.setattr(api, 'build_opener', lambda *args: Opener())
    r = request()
    with pytest.raises(api.AlpacaAccessError) as error:
        api.collect_bars(r['symbols'], r['start'], r['end'], r['asof'], tmp_path,
                         credentials=api.Credentials('key', secret))
    assert secret not in str(error.value)
    assert secret not in next(tmp_path.glob('failure-*.json')).read_text()


@pytest.mark.parametrize('status', [302, 403])
def test_redirect_and_entitlement_errors_do_not_read_or_log_server_bodies(monkeypatch, status):
    from urllib.error import HTTPError
    import io
    class Body(io.BytesIO):
        def read(self, *args): pytest.fail('rejected server response body must not be logged')
    class Opener:
        def open(self, req, **kwargs):
            raise HTTPError(req.full_url, status, 'synthetic-private-value', {}, Body(b'synthetic-private-value'))
    monkeypatch.setattr(api, 'build_opener', lambda *args: Opener())
    assert api._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid/') is None
    with pytest.raises(api.AlpacaAccessError) as error:
        api._fetch(api.request_url(request()), api.Credentials('local-key', 'local-secret'))
    assert error.value.status_code == status and 'synthetic-private-value' not in str(error.value)


def test_cache_pointer_to_a_different_valid_request_is_rejected(tmp_path, monkeypatch):
    path, _ = collect(tmp_path, monkeypatch)
    original_query = request()
    alternate = api.make_request(['CDXS', 'STRO'], original_query['start'], original_query['end'],
                                 original_query['asof'], feed='iex')
    def fetch(url, credentials):
        return json.dumps({'bars': {}, 'next_page_token': None}).encode(), {
            'effective_source_uri': url, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(api, '_fetch', fetch)
    other = api.collect_bars(alternate['symbols'], alternate['start'], alternate['end'], alternate['asof'],
                             tmp_path, feed='iex', credentials=api.Credentials('key', 'secret'))
    pointer = tmp_path / f'query-{api.digest(api.canonical(original_query))}.json'
    pointer.write_bytes(api.canonical({'manifest_relative_path': other.name,
                                      'manifest_sha256': api.digest(other.read_bytes())}))
    monkeypatch.setattr(api, '_fetch', lambda *args: pytest.fail('cache mismatch must not trigger a request'))
    with pytest.raises(ValueError, match='request identity mismatch'):
        api.collect_bars(original_query['symbols'], original_query['start'], original_query['end'],
                         original_query['asof'], tmp_path)
