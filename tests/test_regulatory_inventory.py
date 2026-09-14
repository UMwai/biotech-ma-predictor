"""Search-discovery integrity: no label can be inferred from missing results."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import collect_regulatory_inventory as collector
from src.research.regulatory_inventory import parse_page, query_url, verify_inventory


def response():
    return {'timed_out': False, '_shards': {'failed': 0, 'successful': 2, 'total': 2},
            'hits': {'total': {'value': 1, 'relation': 'eq'}, 'hits': [
                {'_id': '0001234567-21-000001:report.htm', '_source': {
                    'ciks': ['0001745999'], 'file_date': '2021-06-01', 'form': '8-K',
                    'adsh': '0001234567-21-000001', 'items': ['1.01']}}]}}


def write_inventory(tmp_path, value=None):
    raw = json.dumps(value or response()).encode()
    total, records = parse_page(raw, 1745999, '2021-01-01', '2021-12-31')
    (tmp_path / 'raw.json').write_bytes(raw)
    data = {'schema_version': 'sec-efts-inventory-v1', 'cik': 1745999, 'ticker': 'SYNTH',
            'start_date': '2021-01-01', 'end_date': '2021-12-31', 'total': total,
            'records': records, 'inventory_complete': True, 'outcome_label': None,
            'pages': [{'source_uri': query_url(1745999, '2021-01-01', '2021-12-31'),
                       'source_relative_path': 'raw.json', 'source_sha256': hashlib.sha256(raw).hexdigest(),
                       'source_bytes': len(raw), 'retrieved_at': '2026-09-08T00:00:00+00:00',
                       'offset': 0, 'total': total, 'returned': len(records)}]}
    path = tmp_path / 'inventory.json'
    path.write_text(json.dumps(data))
    return path, data


def test_query_pads_cik_and_does_not_filter_out_acquisition_forms():
    query = parse_qs(urlsplit(query_url(1745999, '2021-01-01', '2021-12-31')).query)
    assert query['ciks'] == ['0001745999']
    assert 'q' not in query and 'forms' not in query


@pytest.mark.parametrize('change', ['timeout', 'failed_shard', 'approximate_total', 'wrong_cik', 'wrong_date', 'path_escape'])
def test_unreliable_search_pages_are_rejected(change):
    value = response()
    if change == 'timeout': value['timed_out'] = True
    elif change == 'failed_shard': value['_shards']['failed'] = 1
    elif change == 'approximate_total': value['hits']['total']['relation'] = 'gte'
    elif change == 'wrong_cik': value['hits']['hits'][0]['_source']['ciks'] = ['9999999999']
    elif change == 'wrong_date': value['hits']['hits'][0]['_source']['file_date'] = '2022-01-01'
    else: value['hits']['hits'][0]['_id'] = '0001234567-21-000001:../report.htm'
    with pytest.raises(ValueError): parse_page(json.dumps(value).encode(), 1745999, '2021-01-01', '2021-12-31')


@pytest.mark.parametrize('change', ['raw_tamper', 'query_padding', 'gap', 'invented_label', 'record_tamper', 'duplicate'])
def test_inventory_replays_bytes_pages_and_records(tmp_path, change):
    path, data = write_inventory(tmp_path)
    assert verify_inventory(path)['total'] == 1
    if change == 'raw_tamper': (tmp_path / 'raw.json').write_bytes(b'{}')
    elif change == 'query_padding': data['pages'][0]['source_uri'] = data['pages'][0]['source_uri'].replace('0001745999', '1745999')
    elif change == 'gap': data['pages'][0]['offset'] = 100
    elif change == 'invented_label': data['outcome_label'] = 0
    elif change == 'record_tamper': data['records'][0]['form'] = '10-K'
    else: data['pages'].append(deepcopy(data['pages'][0]))
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError): verify_inventory(path)


def test_truncated_exact_total_is_not_complete(tmp_path):
    value = response(); value['hits']['total']['value'] = 2
    path, _ = write_inventory(tmp_path, value)
    with pytest.raises(ValueError, match='truncated'): verify_inventory(path)


def test_empty_inventory_is_discovery_only(tmp_path):
    value = response(); value['hits'] = {'total': {'value': 0, 'relation': 'eq'}, 'hits': []}
    path, _ = write_inventory(tmp_path, value)
    assert verify_inventory(path)['outcome_label'] is None


def no_network(*args, **kwargs):
    pytest.fail('unexpected network request')


@pytest.mark.parametrize('requested', [
    (9999999, 'SYNTH', '2021-01-01', '2021-12-31'),
    (1745999, 'OTHER', '2021-01-01', '2021-12-31'),
    (1745999, 'SYNTH', '2020-01-01', '2021-12-31'),
    (1745999, 'SYNTH', '2021-01-01', '2022-12-31'),
])
def test_existing_manifest_must_match_requested_identity(tmp_path, monkeypatch, requested):
    path, _ = write_inventory(tmp_path)
    cik, ticker, start, end = requested
    path.rename(tmp_path / f'{ticker}_{start}_{end}.json')
    monkeypatch.setattr(collector, 'urlopen', no_network)
    with pytest.raises(ValueError, match='requested identity mismatch'):
        collector.collect(cik, ticker, start, end, tmp_path)


def test_legacy_manifest_replay_reports_unknown_transport_without_rewriting(tmp_path, monkeypatch):
    path, data = write_inventory(tmp_path)
    # These unsupported claims cannot replace a captured effective response URL.
    data['transport_identity_verified'] = data['pages'][0]['transport_identity_verified'] = True
    path.write_text(json.dumps(data))
    path = path.rename(tmp_path / 'SYNTH_2021-01-01_2021-12-31.json')
    before = path.read_bytes()
    monkeypatch.setattr(collector, 'urlopen', no_network)
    assert collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', tmp_path) == path
    result = verify_inventory(path)
    assert result['transport_identity_verified'] is False
    assert result['pages'][0]['transport_identity_verified'] is False
    assert result['query_interval_closed'] is True
    assert result['inventory_complete'] is True and result['outcome_label'] is None
    assert result['pages'][0]['retrieved_at'] == data['pages'][0]['retrieved_at']
    assert path.read_bytes() == before


def cache_page(directory, receipt):
    digest = hashlib.sha256(receipt['source_uri'].encode()).hexdigest()
    path = directory / f'page-{digest}.json'
    path.write_text(json.dumps(receipt))
    return path


@pytest.mark.parametrize('escape', ['parent', 'absolute', 'symlink'])
def test_cached_raw_path_is_confined_before_reading(tmp_path, monkeypatch, escape):
    directory = tmp_path / 'evidence'
    directory.mkdir()
    path, data = write_inventory(directory)
    path.unlink()
    outside = (directory / 'raw.json').rename(tmp_path / 'outside.json')
    receipt = data['pages'][0]
    receipt['effective_source_uri'] = receipt['source_uri']
    if escape == 'parent':
        receipt['source_relative_path'] = '../outside.json'
    elif escape == 'absolute':
        receipt['source_relative_path'] = str(outside)
    else:
        (directory / 'linked.json').symlink_to(outside)
        receipt['source_relative_path'] = 'linked.json'
    cache_page(directory, receipt)
    reads = []
    read_bytes = Path.read_bytes

    def track_read(path):
        reads.append(path.resolve())
        return read_bytes(path)

    monkeypatch.setattr(Path, 'read_bytes', track_read)
    monkeypatch.setattr(collector, 'urlopen', no_network)
    with pytest.raises(ValueError, match='path escapes evidence directory'):
        collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', directory)
    assert outside.resolve() not in reads


def test_incomplete_legacy_page_cache_cannot_be_upgraded_to_verified_transport(tmp_path, monkeypatch):
    path, data = write_inventory(tmp_path)
    path.unlink()
    receipt = data['pages'][0]
    receipt['transport_identity_verified'] = True
    cached = cache_page(tmp_path, receipt)
    before = cached.read_bytes()
    monkeypatch.setattr(collector, 'urlopen', no_network)
    with pytest.raises(ValueError, match='transport identity is unverified'):
        collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', tmp_path)
    assert cached.read_bytes() == before
    assert not (tmp_path / 'SYNTH_2021-01-01_2021-12-31.json').exists()


class CapturedResponse:
    def __init__(self, uri, payload):
        self.uri, self.payload, self.read_count = uri, payload, 0

    def geturl(self):
        return self.uri

    def read(self, size):
        self.read_count += 1
        return self.payload[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.mark.parametrize('change', ['filter', 'host', 'offset'])
def test_redirected_query_is_rejected_before_body_capture(tmp_path, monkeypatch, change):
    requested = query_url(1745999, '2021-01-01', '2021-12-31')
    effective = {'filter': requested + '&q=acquisition',
                 'host': requested.replace('efts.sec.gov', 'unrelated.example'),
                 'offset': requested.replace('from=0', 'from=100')}[change]
    captured = CapturedResponse(effective, json.dumps(response()).encode())
    monkeypatch.setattr(collector, 'urlopen', lambda *args, **kwargs: captured)
    monkeypatch.setattr(collector.time, 'sleep', lambda _: None)
    with pytest.raises(ValueError, match='effective response query identity mismatch'):
        collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', tmp_path)
    assert captured.read_count == 0
    assert not list((tmp_path / 'raw_sources').iterdir())
    assert not list(tmp_path.glob('page-*.json'))
    failure = json.loads(next(tmp_path.glob('failure-*.json')).read_bytes())
    assert failure['effective_source_uri'] == effective
    assert failure['outcome_label'] is None


def test_verifier_rejects_narrower_effective_query(tmp_path):
    path, data = write_inventory(tmp_path)
    data['pages'][0]['effective_source_uri'] = data['pages'][0]['source_uri'] + '&forms=10-K'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='effective response query identity mismatch'):
        verify_inventory(path)


def test_new_paginated_capture_preserves_effective_urls_and_can_resume_verified_cache(tmp_path, monkeypatch):
    requests = []

    def fetch(request, **kwargs):
        uri = request.full_url
        requests.append(uri)
        offset = int(parse_qs(urlsplit(uri).query)['from'][0])
        value = response()
        value['hits']['total']['value'] = 101
        value['hits']['hits'] = []
        for index in range(offset, min(offset + 100, 101)):
            hit = deepcopy(response()['hits']['hits'][0])
            accession = f'0001234567-21-{index + 1:06d}'
            hit['_id'], hit['_source']['adsh'] = accession + ':report.htm', accession
            value['hits']['hits'].append(hit)
        return CapturedResponse(uri, json.dumps(value).encode())

    monkeypatch.setattr(collector, 'urlopen', fetch)
    monkeypatch.setattr(collector.time, 'sleep', lambda _: None)
    path = collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', tmp_path)
    result = verify_inventory(path)
    assert len(requests) == 2 and result['total'] == 101
    assert result['transport_identity_verified'] is True and result['query_interval_closed'] is True
    assert result['outcome_label'] is None
    assert [page['offset'] for page in result['pages']] == [0, 100]
    assert all(page['effective_source_uri'] == page['source_uri'] for page in result['pages'])
    path.unlink()
    monkeypatch.setattr(collector, 'urlopen', no_network)
    resumed = collector.collect(1745999, 'SYNTH', '2021-01-01', '2021-12-31', tmp_path)
    assert verify_inventory(resumed) == result
    # Later captures cannot turn an earlier open-window page into closed coverage.
    result['pages'][0]['retrieved_at'] = '2021-12-31T00:00:00+00:00'
    resumed.write_text(json.dumps(result))
    replay = verify_inventory(resumed)
    assert replay['inventory_complete'] is True and replay['query_interval_closed'] is False


@pytest.mark.parametrize('retrieved', ['2020-01-01T00:00:00+00:00', '2021-05-31T09:59:59+00:00'])
def test_retrieval_cannot_predate_returned_filing_date(tmp_path, retrieved):
    path, data = write_inventory(tmp_path)
    data['pages'][0]['retrieved_at'] = retrieved
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='retrieval predates a returned filing date'):
        verify_inventory(path)


@pytest.mark.parametrize('retrieved, closed', [
    ('2021-05-31T10:00:00+00:00', False),
    ('2021-12-31T23:59:59+00:00', False),
    ('2022-01-01T11:59:59+00:00', False),
    ('2022-01-01T12:00:00+00:00', True),
])
def test_query_interval_closure_preserves_date_uncertainty(tmp_path, retrieved, closed):
    path, data = write_inventory(tmp_path)
    data['pages'][0]['retrieved_at'] = retrieved
    data['query_interval_closed'] = data['pages'][0]['query_interval_closed'] = not closed
    path.write_text(json.dumps(data))
    result = verify_inventory(path)
    assert result['query_interval_closed'] is closed
    assert result['pages'][0]['query_interval_closed'] is closed
    assert result['inventory_complete'] is True and result['outcome_label'] is None
