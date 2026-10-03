"""Regression tests for the 2026-10-03 SEC accession collector, its bound replay and the packet review checks."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path

import pytest

from scripts import build_ma_exploration_packet as packet
from scripts import collect_sec_accessions as sec

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / 'data/research/ma_exploration_20261003'
ACC = '0001234567-21-000001'
SUBJECT_CIK, FILER_CIK = 1234567, 7654321
FOLDER = f'/Archives/edgar/data/{FILER_CIK}/{ACC.replace("-", "")}'
DIRECT = 'https://data.sec.gov/submissions/CIK0001234567.json'
EARLY = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
LATER = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def company(name: str, role: str, cik: int) -> str:
    return (f'<div class="companyInfo">\n  <span class="companyName">{name} ({role})\n <acronym title="Central Index Key">CIK</acronym>: '
            f'<a href="/cgi-bin/browse-edgar?CIK={cik:010d}&amp;action=getcompany">{cik:010d} (see all company filings)</a></span>\n'
            '<p class="identInfo">Type: <strong>SC 13D/A</strong></p>\n</div>')


def row(seq, desc, href, label, kind, size) -> str:
    return (f'<tr><td scope="row">{seq}</td><td scope="row">{desc}</td><td scope="row"><a href="{href}">{label}</a></td>'
            f'<td scope="row">{kind}</td><td scope="row">{size}</td></tr>')


def index_page(*, accession=ACC, primary=f'{FOLDER}/main.htm', secnum=None, companies=None, extra='') -> bytes:
    """Mirror the real EDGAR index layout surveyed in the saved corpus (secNum block, role-tagged companies)."""
    secnum = accession if secnum is None else secnum
    companies = companies or company('Activist Fund LP', 'Filed by', FILER_CIK) + company('Example Bio Inc.', 'Subject', SUBJECT_CIK)
    rows = (row(1, 'SC 13D/A', primary, Path(primary).name, 'SC 13D/A', 30)
            + row(2, 'EX-99.1', f'{FOLDER}/ex991.htm', 'ex991.htm', 'EX-99.1', 20)
            + row('&nbsp;', 'Complete submission text file', f'{FOLDER}/{accession}.txt', f'{accession}.txt', '&nbsp;', 99))
    return (f'<div id="formName">\n<strong>Form SC 13D/A</strong> - General Statement</div>\n<div id="secNum">\n'
            f'<strong><acronym title="Securities and Exchange Commission">SEC</acronym> Accession <acronym title="Number">No.</acronym>'
            f'</strong> {secnum}\n</div>{extra}<div class="infoHead">Filing Date</div>\n<div class="info">2021-02-08</div>'
            f'<div class="infoHead">Accepted</div>\n<div class="info">2021-02-08 16:05:00</div>{companies}'
            f'<table class="tableFile" summary="Document Format Files"><tr><th>Seq</th></tr>{rows}</table>').encode()


def archive(root: Path, url: str, payload: bytes, **overrides) -> Path:
    relative = sec.store_raw(root, payload, sec.raw_suffix(url))
    receipt = {'schema_version': sec.ATTEMPT_SCHEMA, 'url': url, 'outcome': 'success', 'attempted_at': EARLY,
               'completed_at': LATER, 'retrieved_at': LATER, 'source_sha256': sec.sha256(payload), 'source_bytes': len(payload),
               'raw_relative_path': relative, 'http_status': 200, 'final_url': url, 'redirects_followed': False,
               'automatic_retry_performed': False, **overrides}
    return sec.write_addressed(root / 'sec' / 'attempts', 'attempt', receipt)


class Refuse:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        raise AssertionError('network not allowed')


def evidence(root: Path) -> tuple[Path, dict]:
    """Cached-only third-party filing (filer folder, subject archive CIK) plus one direct route."""
    archive(root, sec.index_url(ACC, SUBJECT_CIK), index_page())
    archive(root, f'https://www.sec.gov{FOLDER}/main.htm', b'<html>filing</html>')
    archive(root, f'https://www.sec.gov{FOLDER}/ex991.htm', b'<html>exhibit</html>')
    archive(root, DIRECT, b'{"cik":"0001234567"}')
    plan = {'schema_version': sec.PLAN_SCHEMA, 'name': 'fixture-plan',
            'accessions': [{'accession': ACC, 'archive_cik': SUBJECT_CIK, 'scope': 'full', 'ticker': 'EXB'}],
            'urls': [{'url': DIRECT, 'role': 'identity'}]}
    plan_path = root / 'plan-source.json'
    plan_path.write_text(json.dumps(plan))
    guard = Refuse()
    path = sec.collect(plan_path, root, session=guard, pause=0)
    assert guard.calls == []  # cache reuse: every source already archived
    return path, json.loads(path.read_bytes())


def test_cached_collection_replays_with_third_party_roles_and_cache_reuse(tmp_path: Path):
    path, collection = evidence(tmp_path)
    _, clocks, digest = sec.verify_collection(path, tmp_path)
    entry = collection['accessions'][0]
    assert entry['index']['filer_ciks'] == [FILER_CIK] and entry['index']['subject_ciks'] == [SUBJECT_CIK]
    assert [d['capture_status'] for d in entry['documents']] == ['captured', 'captured', 'complete_submission_text_file_not_fetched']
    assert collection['plan']['relative_path'] == f'sec/plans/fixture-plan-{collection["plan"]["sha256"]}.json'
    assert all(collection[k] is v for k, v in sec.AUTHORITY.items()) and digest in path.name and clocks
    # A second run with the same plan reuses archived attempts and makes no request.
    guard = Refuse()
    sec.collect(tmp_path / 'plan-source.json', tmp_path, session=guard, pause=0)
    assert guard.calls == []


MUTATIONS = {
    'original_version_authority_true': lambda c: c.update(original_version_verified=True),
    'as_accepted_authority_true': lambda c: c.update(as_accepted_byte_identity_verified=True),
    'label_admission_true': lambda c: c.update(label_admission_allowed=True, outcome_label='negative'),
    'direct_url_locator_hash_length_forged': lambda c: c['urls'][0].update(
        source_sha256='0' * 64, raw_relative_path='../../outside.json', source_bytes=123),
    'document_type_locator_size_forged': lambda c: c['accessions'][0]['documents'][0].update(
        type='SC 14D9', raw_relative_path='../../outside.html', source_bytes=123),
    'unfetched_exhibit_promoted_to_captured': lambda c: c['accessions'][0]['documents'][2].update(capture_status='captured'),
    'plan_digest_forged': lambda c: c['plan'].update(sha256='0' * 64),
    'declared_target_and_scope_forged': lambda c: c['accessions'][0].update(ticker='OTHER', scope='primary_only'),
    'completion_precedes_represented_retrieval': lambda c: c.update(started_at=EARLY, completed_at=EARLY),
    'extra_top_level_claim': lambda c: c.update(review_complete=True),
    'subject_and_filer_swapped': lambda c: c['accessions'][0]['index'].update(filer_ciks=[SUBJECT_CIK], subject_ciks=[FILER_CIK]),
}


@pytest.mark.parametrize('mutation', sorted(MUTATIONS))
def test_collection_contradicting_archived_evidence_is_rejected(tmp_path: Path, mutation: str):
    _, collection = evidence(tmp_path)
    changed = copy.deepcopy(collection)
    MUTATIONS[mutation](changed)
    path = sec.write_addressed(tmp_path / 'sec' / 'collections', f'sec-collection-{changed["plan"]["name"]}', changed)
    with pytest.raises(ValueError):
        sec.verify_collection(path, tmp_path)


@pytest.mark.parametrize('label, page, archive_cik, message', [
    ('accession only in a comment', index_page(secnum='0000000002-20-000002', extra=f'<!-- {ACC} -->'), SUBJECT_CIK, 'secNum'),
    ('requested CIK not a named company', index_page(), 1111111, 'not a named filer or subject'),
    ('dot-segment escape', index_page(primary=f'{FOLDER}/../000000000220000002/other.htm'), SUBJECT_CIK, 'canonical'),
    ('encoded traversal', index_page(primary=f'{FOLDER}/%2e%2e/other.htm'), SUBJECT_CIK, 'canonical'),
    ('query string', index_page(primary=f'{FOLDER}/main.htm?x=1'), SUBJECT_CIK, 'canonical'),
    ('foreign host', index_page(primary='https://evil.example/Archives/edgar/data/1/2/main.htm'), SUBJECT_CIK, 'unsupported'),
    ('folder CIK not named in index', index_page(primary=f'/Archives/edgar/data/999/{ACC.replace("-", "")}/main.htm'), SUBJECT_CIK, 'not named'),
    ('company CIK link and text differ', index_page(companies=company('X', 'Filer', SUBJECT_CIK).replace(
        f'>{SUBJECT_CIK:010d} (see', '>0000000009 (see')), SUBJECT_CIK, 'differ'),
])
def test_index_identity_and_document_urls_are_bound_structurally(label, page, archive_cik, message):
    with pytest.raises(ValueError, match=message):
        sec.parse_index(page, ACC, archive_cik)


@pytest.mark.parametrize('label, overrides, message', [
    ('cached foreign-host receipt', {'url': 'https://outside.example.test/source.json',
                                     'final_url': 'https://outside.example.test/source.json'}, 'unsupported URL'),
    ('success after redirect', {'final_url': 'https://data.sec.gov/submissions/CIK0000000002.json'}, 'status/url'),
    ('success without retrieval clock', {'retrieved_at': None}, 'completed_at == retrieved_at'),
    ('redirect followed', {'redirects_followed': True}, 'redirects or retries'),
    ('future clock', {'completed_at': '2999-01-01T00:00:00+00:00', 'retrieved_at': '2999-01-01T00:00:00+00:00'}, 'future'),
])
def test_cached_receipts_are_validated_without_any_request(tmp_path: Path, label, overrides, message):
    overrides = dict(overrides)
    archive(tmp_path, overrides.pop('url', DIRECT), b'{"cik":"0001234567"}', **overrides)
    with pytest.raises(ValueError, match=message):
        sec.load_attempts(tmp_path)


def test_unsafe_plan_name_cannot_choose_output_path(tmp_path: Path):
    plan = {'schema_version': sec.PLAN_SCHEMA, 'name': 'safe/../../outside', 'urls': [{'url': DIRECT}]}
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='unsafe plan name'):
        sec.collect(tmp_path / 'plan.json', tmp_path, session=Refuse(), pause=0)


class FakeResponse:
    def __init__(self, status: int, url: str, body: bytes):
        self.status_code, self.url, self.headers = status, url, {}
        self.raw = io.BytesIO(body)
        self.raw.read = lambda n, decode_content=True, _r=self.raw: io.BytesIO.read(_r, n)

    def close(self):
        pass


class Counting:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        status, body = self.responses[url]
        return FakeResponse(status, url, body)


def test_network_failure_is_recorded_once_and_never_retried(tmp_path: Path):
    index = sec.index_url(ACC, SUBJECT_CIK)
    responses = {index: (200, index_page()), f'https://www.sec.gov{FOLDER}/main.htm': (200, b'<html>m</html>'),
                 f'https://www.sec.gov{FOLDER}/ex991.htm': (404, b'missing')}
    session = Counting(responses)
    plan = {'schema_version': sec.PLAN_SCHEMA, 'name': 'network', 'accessions': [{'accession': ACC, 'archive_cik': SUBJECT_CIK, 'scope': 'full'}]}
    (tmp_path / 'p.json').write_text(json.dumps(plan))
    collection = json.loads(sec.collect(tmp_path / 'p.json', tmp_path, session=session, pause=0).read_bytes())
    assert [d['capture_status'] for d in collection['accessions'][0]['documents'][:2]] == ['captured', 'failed_not_retried']
    assert all(kw['allow_redirects'] is False for _, kw in session.calls) and len(session.calls) == 3
    sec.collect(tmp_path / 'p.json', tmp_path, session=session, pause=0)
    assert len(session.calls) == 3


def _saved_index(plan: str, accession: str) -> tuple[bytes, dict]:
    path = next((EVIDENCE / 'sec' / 'collections').glob(f'sec-collection-{plan}-*.json'))
    entry = next(e for e in json.loads(path.read_bytes())['accessions'] if e['accession'] == accession)
    return (EVIDENCE / entry['raw_relative_path']).read_bytes(), entry


@pytest.mark.parametrize('plan, accession, filer, subject', [
    ('arqt-2021-audit', '0001193125-21-032458', [1687968], [1787306]),   # Bain filed-by, Arcutis subject
    ('first-five-batch', '0001354457-22-000674', [1354457], [1722271]),  # Nasdaq Form 25 with XSL rendition row
    ('example-lilly-prevail', '0001193125-20-317452', [59478], [1714798]),  # Lilly filer, Prevail subject
])
def test_real_saved_index_layouts_parse_with_separate_roles(plan, accession, filer, subject):
    payload, entry = _saved_index(plan, accession)
    parsed = sec.parse_index(payload, accession, entry['archive_cik'])
    assert parsed['filer_ciks'] == filer and parsed['subject_ciks'] == subject
    assert parsed == {**entry['index'], 'documents': parsed['documents'], 'data_files': parsed['data_files']}


def test_real_rebound_collection_replays_against_unchanged_legacy_and_producer():
    path = next((EVIDENCE / 'sec' / 'collections').glob('sec-collection-designated-material-accessions-*.json'))
    collection, clocks, _ = sec.verify_collection(path, EVIDENCE)
    lineage = collection['lineage']
    assert collection['mode'] == 'cache_only_rebind_of_legacy' and lineage['producer_snapshot_status'] == 'archived_matching_recorded_hash'
    assert max(clocks.values()) <= collection['completed_at'] and lineage['legacy_collection']['recorded_completed_at'] < collection['started_at']


def test_review_records_must_bind_hash_depth_and_clock(tmp_path: Path):
    docs = {(ACC, 'main.htm'): {'a' * 64: {'source_sha256': 'a' * 64, 'retrieved_at': LATER}}}
    good = {'accession': ACC, 'document_name': 'main.htm', 'source_sha256': 'a' * 64, 'review_depth': 'full_text_read',
            'reviewer': 'agent; not independent human review', 'independent_human_review': False,
            'reviewed_at': datetime.now(timezone.utc).isoformat(), 'paraphrase': 'Read the full filing; no control transaction.'}
    log = tmp_path / 'reviews' / 'document-review-log.jsonl'
    log.parent.mkdir()
    for bad, message in [({}, None), ({'reviewed_at': EARLY}, 'precedes retrieval'), ({'source_sha256': 'b' * 64}, 'hash differs'),
                         ({'review_depth': 'skimmed'}, 'unknown depth'), ({'document_name': 'other.htm'}, 'uncaptured')]:
        log.write_text(json.dumps({**good, **bad}) + '\n')
        if message is None:
            assert len(packet.load_reviews(tmp_path, docs)[0]) == 1
        else:
            with pytest.raises(ValueError, match=message):
                packet.load_reviews(tmp_path, docs)


def test_served_bytes_check_and_leap_year_horizon(tmp_path: Path):
    original = b'<html><body>filing</body></html>'
    served = original.replace(b'</body>', b'<script type="text/javascript"  src="/abc/DEF/12-x"></script></body>')
    raw = tmp_path / 'sec' / 'raw' / 'doc.htm'
    raw.parent.mkdir(parents=True)
    raw.write_bytes(served)
    check = packet.served_bytes_check(tmp_path, {'raw_relative_path': 'sec/raw/doc.htm', 'source_sha256': sec.sha256(served),
                                                 'source_bytes': len(served), 'index_size_bytes': len(original)})
    assert check['injected_script_tags'] == 1 and check['script_stripped_sha256'] == sec.sha256(original)
    assert packet.horizon_end('2024-01-01') == '2024-12-31' and packet.horizon_end('2023-01-01') == '2024-01-01'
