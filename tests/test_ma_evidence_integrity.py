"""Regressions for evidence integrity: path confinement, single-read hashing, full snapshot
validation, verified census text, review clocks and the incremental issuer collector.

Fixtures are invented or copies of local snapshot bytes; none is historical evidence.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import types

import pytest

from scripts import ma_evidence_io as io
from scripts import screen_ma_source_packet as screener
from scripts.ma_source_packet import VerifiedQueue

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_ma_evidence_ledger', REPO / 'scripts' / 'build_ma_evidence_ledger.py')
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)
EVIDENCE = REPO / 'data' / 'research' / 'ma_evidence_20261002'
SNAPSHOT = EVIDENCE / 'input-snapshot-b87964831a19ef9d16b324d29e2fe3d9d6dc3ff153353ba7110abc55d6c1209c.json'
PROTOCOL = EVIDENCE / 'ma-collection-protocol-8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


# --- path confinement ---------------------------------------------------------

def test_confined_rejects_traversal_absolute_and_symlink_escape(tmp_path):
    root, outside = tmp_path / 'root', tmp_path / 'outside'
    root.mkdir(), outside.mkdir()
    (root / 'ok.txt').write_text('ok')
    (outside / 'secret.txt').write_text('x')
    (root / 'link.txt').symlink_to(outside / 'secret.txt')
    assert io.confined(root, 'ok.txt') == (root / 'ok.txt').resolve()
    assert io.confined(root, str(root / 'ok.txt')) == (root / 'ok.txt').resolve()
    for bad in ('../outside/secret.txt', str(outside / 'secret.txt'), 'link.txt'):
        with pytest.raises(ValueError):
            io.confined(root, bad)
    with pytest.raises(FileNotFoundError):
        io.confined(root, 'missing.txt')


# --- review clocks --------------------------------------------------------------

def test_review_clock_requires_aware_measured_time_after_sources():
    now = datetime(2026, 10, 2, 20, 0, tzinfo=timezone.utc)
    sources = {'retrieved': '2026-10-02T19:58:00+00:00'}
    assert io.review_clock('2026-10-02T19:59:00+00:00', not_before=sources, now=now) == '2026-10-02T19:59:00+00:00'
    for bad in ('2026-10-02T20:01:00+00:00', '2026-10-02T19:57:00+00:00', '2026-10-02T19:59:00'):
        with pytest.raises(ValueError):
            io.review_clock(bad, not_before=sources, now=now)


# --- availability scan reads each artifact once ---------------------------------

def test_availability_scan_hashes_and_parses_the_same_bytes(tmp_path, monkeypatch):
    path = tmp_path / 'data/history/web_source_research/20260919/ABC-submissions/sec-submission-collection.json'
    path.parent.mkdir(parents=True)
    first = json.dumps({'collection_complete': False, 'accessions': []}).encode()
    path.write_bytes(first)
    real = ledger.read_once

    def read_then_replace(target, *args, **kwargs):
        result = real(target, *args, **kwargs)
        Path(target).write_text(json.dumps({'collection_complete': True, 'accessions': [{}] * 99}))
        return result
    monkeypatch.setattr(ledger, 'read_once', read_then_replace)
    item = ledger.scan_source_availability(tmp_path, ['ABC'])['ABC']['sec_submission_collections'][0]
    assert item['sha256'] == sha(first) and item['collection_complete'] is False and item['accessions'] == 0


# --- whole snapshot validation (copies of local bytes) ----------------------------

def copy_snapshot(tmp_path):
    manifest = json.loads(SNAPSHOT.read_bytes())
    target = tmp_path / 'snap'
    (target / 'inputs').mkdir(parents=True)
    shutil.copy(SNAPSHOT, target / SNAPSHOT.name)
    shutil.copy(EVIDENCE / manifest['source_availability']['relative_path'], target)
    for entry in manifest['inputs'].values():
        source = EVIDENCE / entry['snapshot_relative_path']
        if source.exists():
            shutil.copy(source, target / entry['snapshot_relative_path'])
    return target, manifest


def local_inputs_present():
    manifest = json.loads(SNAPSHOT.read_bytes())
    return all((EVIDENCE / e['snapshot_relative_path']).exists() for e in manifest['inputs'].values())


def test_missing_local_only_vendor_inputs_fail_closed_on_public_clone(tmp_path):
    target, manifest = copy_snapshot(tmp_path)
    local = target / manifest['inputs']['valuation_raw_2023_0']['snapshot_relative_path']
    if local.exists():
        local.unlink()
    with pytest.raises(ValueError, match='local-only licensed vendor inputs are not distributed'):
        ledger.build(target / SNAPSHOT.name, PROTOCOL, tmp_path / 'out', tmp_path / 'report')


@pytest.mark.skipif(not local_inputs_present(), reason='local-only licensed vendor inputs absent (public clone)')
@pytest.mark.parametrize('name, action, message', [
    ('valuation_raw_2021_0', 'tamper', 'hash mismatch'),
    ('valuation_raw_2023_0', 'delete', 'local-only licensed vendor inputs'),
    ('status', 'tamper', 'hash mismatch'),
    ('frame_source_html', 'delete', 'missing source'),
])
def test_every_declared_copy_is_validated_even_if_unused(tmp_path, name, action, message):
    target, manifest = copy_snapshot(tmp_path)
    path = target / manifest['inputs'][name]['snapshot_relative_path']
    if action == 'tamper':
        path.write_bytes(path.read_bytes() + b' ')
    else:
        path.unlink()
    with pytest.raises((ValueError, FileNotFoundError), match=message):
        ledger.build(target / SNAPSHOT.name, PROTOCOL, tmp_path / 'out', tmp_path / 'report')


@pytest.mark.skipif(not local_inputs_present(), reason='local-only licensed vendor inputs absent (public clone)')
def test_snapshot_reference_escape_and_authority_mismatch_fail(tmp_path):
    target, manifest = copy_snapshot(tmp_path)
    protocol = json.loads(PROTOCOL.read_bytes())
    escaped = json.loads(json.dumps(manifest))
    escaped['inputs']['status']['snapshot_relative_path'] = '../' + manifest['inputs']['status']['snapshot_relative_path']
    with pytest.raises(ValueError, match='not content-addressed|traversal'):
        ledger.verify_snapshot(escaped, target, protocol)
    wrong = json.loads(json.dumps(manifest))
    wrong['inputs']['panel']['expected_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='authoritative'):
        ledger.verify_snapshot(wrong, target, protocol)
    payloads, availability = ledger.verify_snapshot(manifest, target, protocol)
    assert len(payloads) == 20 and len(availability['tickers']) == 100


# --- screener confinement and single submission read ------------------------------

def screening_fixture(tmp_path):
    root = tmp_path / 'collection'
    root.mkdir()
    payload = b'<html>Agreement and Plan of Merger example</html>'
    submission = b'HEADER' + payload + b'TRAILER'
    index = b'index'
    (root / 'sub.raw').write_bytes(submission)
    (root / 'idx.raw').write_bytes(index)
    doc = {'container_text_start': 6, 'container_text_end': 6 + len(payload), 'embedded_document_sha256': sha(payload),
           'embedded_document_bytes': len(payload), 'filename': 'a.htm'}
    collection = {'schema_version': 'sec-complete-submission-collection-v1', 'collection_complete': True, 'ticker': 'ZZZ',
                  'cik': 1, 'excluded_forms': [],
                  'accessions': [{'accession_number': '0000000001-20-000001', 'embedded_documents': [doc],
                                  'index': {'source_relative_path': 'idx.raw', 'source_sha256': sha(index), 'byte_count': len(index)},
                                  'submission': {'source_relative_path': 'sub.raw', 'source_sha256': sha(submission),
                                                 'byte_count': len(submission)}}]}
    collection_path = root / 'collection.json'
    collection_path.write_text(json.dumps(collection))
    qroot = tmp_path / 'queue'
    qroot.mkdir()
    text = b'Agreement and Plan of Merger example'
    (qroot / 'p.payload').write_bytes(payload)
    (qroot / 't.txt').write_bytes(text)
    queue = {'collection_sha256': sha(collection_path.read_bytes()), 'trigger_context_count': 0, 'extractor_code_sha256': 'x',
             'documents': [{'accession_number': '0000000001-20-000001', 'filename': 'a.htm', 'sequence': '1',
                            'document_type': '8-K', 'parent_form': '8-K', 'publication_date': '2021-02-01',
                            'review_kind': 'text', 'payload_sha256': sha(payload),
                            'payload_artifact': {'relative_path': 'p.payload', 'sha256': sha(payload)},
                            'extracted_text': {'relative_path': 't.txt', 'sha256': sha(text)}}]}
    raw = json.dumps(queue).encode()
    queue_path = qroot / f'sec-outcome-review-queue-{sha(raw)}.json'
    queue_path.write_bytes(raw)
    return collection_path, queue_path, collection


def test_screener_slices_verified_submission_bytes_once(tmp_path, monkeypatch):
    collection_path, queue_path, _ = screening_fixture(tmp_path)
    real = screener.read_once

    def read_then_replace(target, *args, **kwargs):
        result = real(target, *args, **kwargs)
        if Path(target).name == 'sub.raw':
            Path(target).write_bytes(b'REPLACED' * 20)
        return result
    monkeypatch.setattr(screener, 'read_once', read_then_replace)
    receipt = screener.screen(collection_path, queue_path)
    assert receipt['replay'] == {'index_responses': 1, 'submission_responses': 1, 'payload_slices': 1}
    assert receipt['documents'][0]['term_hits'] == {'merger_agreement': 1}


@pytest.mark.parametrize('reference', ['../outside.raw', 'link.raw'])
def test_screener_rejects_manifest_path_escapes(tmp_path, reference):
    collection_path, queue_path, collection = screening_fixture(tmp_path)
    outside = tmp_path / 'outside.raw'
    outside.write_bytes(b'index')
    (collection_path.parent / 'link.raw').symlink_to(outside)
    collection['accessions'][0]['index']['source_relative_path'] = reference
    collection_path.write_text(json.dumps(collection))
    with pytest.raises(ValueError, match='traversal|escapes'):
        screener.screen(collection_path, queue_path)


def test_census_uses_hash_verified_text(tmp_path):
    collection_path, queue_path, _ = screening_fixture(tmp_path)
    queue = json.loads(queue_path.read_bytes())
    queue['collection_sha256'] = sha(collection_path.read_bytes())
    verified = VerifiedQueue(queue_path, collection_path)
    assert verified.eight_k_census()[0]['items'] == []
    (queue_path.parent / 't.txt').write_bytes(b'Item 2.01 Completion of Acquisition')
    with pytest.raises(ValueError, match='hash mismatch'):
        VerifiedQueue(queue_path, collection_path).eight_k_census()


# --- issuer collector: incremental receipts, no retry, identity checks ------------

HOST = 'issuer.example.test'
SELECT = 'abc_year[value]'


def year_form(selected=None):
    marker = ' selected="selected"' if selected else ''
    option = f'<option value="2020"{marker}>2020</option>'
    return f'<form action="/press-releases" method="get"><select name="{SELECT}">{option}</select></form>'


def body_page(url, title='Release A', day='Feb 10, 2020'):
    return (f'<html><head><link rel="canonical" href="{url}" /><meta property="og:url" content="{url}" /></head><body>'
            f'<div class="field--name-field-nir-news-date"><div>{day}</div></div>'
            f'<h1><div class="field--name-field-nir-news-title"><div>{title}</div></div></h1>'
            f'<div class="node__content"><p>WARMINSTER, Pa. (GLOBE NEWSWIRE) -- Example (Nasdaq: ABUS) ' + 'text ' * 80 +
            '</p></div></body></html>').encode()


def probe_fixture(tmp_path, rows=2):
    probe = tmp_path / 'probe'
    probe.mkdir(exist_ok=True)
    base = f'https://{HOST}/press-releases'
    year_url = base + '?abc_year%5Bvalue%5D=2020'
    articles = ''.join(f'<article><div class="nir-widget--news--date-time">Feb {10 + i}, 2020</div>'
                       f'<a href="/news-releases/news-release-details/r{i}">Release {i}</a></article>' for i in range(rows))
    for name, url, html in (('abus-publisher-platform-archive', base, year_form()),
                            ('abus-publisher-platform-2020', year_url, year_form(True) + articles)):
        raw = html.encode()
        (probe / f'{sha(raw)}.html').write_bytes(raw)
        receipt = {'source_uri': url, 'resolved_uri': url, 'http_status': 200, 'attempted_at': '2026-10-02T19:00:00+00:00',
                   'retrieved_at': '2026-10-02T19:00:01+00:00', 'source_sha256': sha(raw), 'source_bytes': len(raw),
                   'source_path': str(probe / f'{sha(raw)}.html')}
        (probe / f'{name}.receipt.json').write_text(json.dumps(receipt))
    return probe


class FakeResponse:
    def __init__(self, url, body, status=200):
        self.url, self.status_code, self.headers = url, status, {'Content-Type': 'text/html'}
        self.raw = self
        self._body = body

    def read(self, limit, decode_content=True):
        return self._body[:limit]

    def close(self):
        pass


class FakeSession:
    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        outcome = self.plan(url)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def collector(monkeypatch):
    # Fake sessions never touch the network; only the version label is read from the client module.
    monkeypatch.setitem(sys.modules, 'requests', types.SimpleNamespace(__version__='test-fake'))
    from scripts import collect_ma_issuer_archive
    return collect_ma_issuer_archive


def run(mod, tmp_path, session):
    return json.loads(mod.collect(probe_fixture(tmp_path), tmp_path / 'out', HOST, [2020], '2020-01-01', '2020-12-31',
                                  [], session=session, pause=0).read_bytes())


def test_collector_verifies_identity_and_persists_before_next_request(tmp_path, collector):
    mod = collector

    def plan(url):
        if url.endswith('r0'):
            return FakeResponse(url, body_page(url, 'Release 0', 'Feb 10, 2020'))
        raise KeyboardInterrupt  # simulated operator interrupt during the second request
    with pytest.raises(KeyboardInterrupt):
        run(mod, tmp_path, FakeSession(plan))
    saved = list((tmp_path / 'out' / 'attempts').glob('attempt-*.json'))
    assert len(saved) == 1 and json.loads(saved[0].read_bytes())['outcome'] == 'success'

    def plan2(url):
        return FakeResponse(url, body_page(url, 'Wrong headline', 'Feb 11, 2020'))
    session = FakeSession(plan2)
    result = run(mod, tmp_path, session)
    assert session.calls == [f'https://{HOST}/news-releases/news-release-details/r1']  # cached success reused
    status = {b['url'].rsplit('/', 1)[1]: b['status'] for b in result['bodies']}
    assert status == {'r0': 'captured_identity_verified', 'r1': 'captured_identity_mismatch'}


def test_collector_records_failures_and_never_retries(tmp_path, collector):
    mod = collector
    first = FakeSession(lambda url: FakeResponse(url, b'', status=302) if url.endswith('r0') else TimeoutError('read timed out'))
    result = run(mod, tmp_path, first)
    assert {b['status'] for b in result['bodies']} == {'failed_not_retried'}
    errors = sorted(a['error'] for b in result['bodies'] for a in b['attempts'])
    assert errors == ['TimeoutError: read timed out', 'http_status 302']
    second = FakeSession(lambda url: FakeResponse(url, body_page(url)))
    run(mod, tmp_path, second)
    assert second.calls == []


def test_collector_rejects_probe_paths_and_hosts_outside_roots(tmp_path, collector):
    mod = collector
    probe = probe_fixture(tmp_path)
    receipt_path = probe / 'abus-publisher-platform-archive.receipt.json'
    receipt = json.loads(receipt_path.read_bytes())
    outside = tmp_path / 'outside.html'
    outside.write_bytes(Path(receipt['source_path']).read_bytes())
    receipt_path.write_text(json.dumps(dict(receipt, source_path=str(outside))))
    with pytest.raises(ValueError, match='outside root'):
        mod.freeze_inventory(probe, [2020], tmp_path / 'out', HOST)
    receipt_path.write_text(json.dumps(dict(receipt, source_uri='https://evil.example/press-releases',
                                            resolved_uri='https://evil.example/press-releases')))
    with pytest.raises(ValueError, match='outside https'):
        mod.freeze_inventory(probe, [2020], tmp_path / 'out', HOST)


# --- archive source clocks: probe, cached attempts and consumer validation --------

def rewrite_receipt(path, **changes):
    receipt = json.loads(path.read_bytes())
    path.write_text(json.dumps(dict(receipt, **changes)))


@pytest.mark.parametrize('clocks', [
    {'attempted_at': '2099-01-01T00:00:00+00:00', 'retrieved_at': '2099-01-01T00:00:01+00:00'},  # future
    {'attempted_at': '2026-10-02T19:00:05+00:00', 'retrieved_at': '2026-10-02T19:00:01+00:00'},  # reversed
    {'attempted_at': '2026-10-02T19:00:00', 'retrieved_at': '2026-10-02T19:00:01'},              # naive
])
def test_inventory_capture_clocks_are_validated(tmp_path, collector, clocks):
    probe = probe_fixture(tmp_path)
    rewrite_receipt(probe / 'abus-publisher-platform-2020.receipt.json', **clocks)
    session = FakeSession(lambda url: FakeResponse(url, body_page(url)))
    with pytest.raises(ValueError):
        collector.collect(probe, tmp_path / 'out', HOST, [2020], '2020-01-01', '2020-12-31', [], session=session, pause=0)
    assert session.calls == []
    assert not list((tmp_path / 'out').glob('issuer-archive-collection-*.json'))


def test_cached_attempt_and_collection_clocks_are_validated_by_producer_and_consumer(tmp_path, collector):
    def plan(url):
        index = url.rsplit('r', 1)[1]
        return FakeResponse(url, body_page(url, f'Release {index}', f'Feb {10 + int(index)}, 2020'))
    result_path = collector.collect(probe_fixture(tmp_path), tmp_path / 'out', HOST, [2020], '2020-01-01', '2020-12-31',
                                    [], session=FakeSession(plan), pause=0)
    collection, clocks, _ = collector.verify_archive_collection(result_path)
    assert {'archive_page.retrieved_at', 'year_page_2020.retrieved_at'} <= set(clocks) and len(clocks) == 4 + 2 * 3
    # Consumer: a future year-page clock in an edited collection is rejected (nothing is re-timed).
    edited = json.loads(json.dumps(collection))
    edited['pages'][0]['retrieved_at'] = '2099-01-01T00:00:01+00:00'
    with pytest.raises(ValueError, match='future'):
        collector.validate_archive(edited, result_path.parent)
    # Producer: a cached attempt receipt with a reversed clock blocks reuse.
    attempt = sorted((tmp_path / 'out' / 'attempts').glob('attempt-*.json'))[0]
    receipt = json.loads(attempt.read_bytes())
    receipt['retrieved_at'] = receipt['completed_at'] = '2020-01-01T00:00:00+00:00'
    payload = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
    attempt.unlink()
    (attempt.parent / f'attempt-{sha(payload)}.json').write_bytes(payload)
    with pytest.raises(ValueError, match='precedes start'):
        collector.prior_attempts(tmp_path / 'out')


# --- frozen protocol enforcement in the active v2 packet builder ------------------

def v2_builder():
    path = EVIDENCE / 'abus_2021' / 'build_abus_2021_packet_v2.py'
    spec = importlib.util.spec_from_file_location('build_abus_2021_packet_v2', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_protocol_bytes_under_frozen_filename_are_rejected(tmp_path):
    builder = v2_builder()
    frozen = builder.FROZEN_PROTOCOL_SHA256
    original = PROTOCOL.read_bytes()
    (tmp_path / builder.PROTOCOL_NAME).write_bytes(original)
    protocol, digest = builder.load_frozen_protocol(tmp_path, first_binding=frozen, ledger_binding=frozen)
    assert digest == frozen and protocol['schema_version'] == 'ma-evidence-collection-protocol-v1'
    with pytest.raises(ValueError, match='first-packet or ledger binding'):
        builder.load_frozen_protocol(tmp_path, first_binding=frozen, ledger_binding='0' * 64)
    changed = json.loads(original)
    changed['event_policy']['positive'] = 'UNREGISTERED_TEST_RULE'
    (tmp_path / builder.PROTOCOL_NAME).write_text(json.dumps(changed))  # filename stays the frozen one
    with pytest.raises(ValueError, match='not the frozen registration'):
        builder.load_frozen_protocol(tmp_path, first_binding=frozen, ledger_binding=frozen)
