#!/usr/bin/env python3
"""Archive SEC accession indexes and listed documents as raw bytes, and replay-verify the result.

A plan (``ma-exploration-sec-plan-v1``) names accession targets and explicitly
supported direct-URL targets. ``collect`` archives the exact plan bytes under a
content-addressed path, performs at most one GET per URL (bounded timeouts, no
redirects, no automatic retries), persists raw bytes before each attempt receipt,
and then *derives* every collection entry from the archived plan, receipts and
filing-index bytes. ``verify_collection`` repeats that derivation without network
and requires the stored collection to equal it exactly, so a collection cannot
assert a document type, locator, hash, size, capture status, target or scope that
its archived evidence does not support.

Every URL - requested, cached or parsed from an index - must match one of the
canonical routes below: SEC accession folders (CIK named in that index, the
requested accession, no dot segments, queries, credentials or encodings) or an
explicit public direct route. A filing index must structurally carry the
requested accession in its ``secNum`` block and complete-submission row and must
name the requested archive CIK as a filer or subject company; filer and subject
companies are recorded separately and never inferred from the folder.

Changed hypothesis (2026-10-03): www.sec.gov Archives answered HTTP 403 to the
contact-free agent of ``collect_ma_issuer_archive.py``; this collector uses the
contact-bearing agent the repository owner used in earlier SEC receipts.
data.sec.gov accepted the contact-free agent.

Collections are capture evidence only: served bytes are not as-filed bytes, and
no original-version, completeness, review or label authority is ever asserted.
``rebind`` re-derives a legacy (v1) collection from its archived evidence in
cache-only mode, retaining the legacy file and its recorded producer unchanged.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ma_evidence_io import chronology, confined, measured_now, parse_clock, read_once, require, sha256  # noqa: E402

SCHEMA = 'ma-exploration-sec-collection-v2'
LEGACY_SCHEMA = 'ma-exploration-sec-collection-v1'
PLAN_SCHEMA = 'ma-exploration-sec-plan-v1'
ATTEMPT_SCHEMA = 'ma-exploration-public-get-attempt-v1'
SEC_AGENT = 'BiotechMAPredictor/0.1 waiy392f@gmail.com'
PLAIN_AGENT = 'biotech-ma-predictor public historical acquisition research'
TIMEOUT = (10, 60)
MAX_BYTES = 60_000_000
SCOPES = ('full', 'primary_only', 'full_with_data_files')
ACCESSION = re.compile(r'\d{10}-\d{2}-\d{6}')
PLAN_NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,80}')
SEC_DOCUMENT = re.compile(r'https://www\.sec\.gov/Archives/edgar/data/(?P<cik>[1-9]\d{0,9})/(?P<folder>\d{18})/'
                          r'(?P<name>(?:xsl[A-Za-z0-9]+/)?[A-Za-z0-9][A-Za-z0-9_.-]*)')
DIRECT_ROUTES = {
    'sec_submissions_json': re.compile(r'https://data\.sec\.gov/submissions/CIK\d{10}(?:-submissions-\d{3})?\.json'),
    'arcutis_ir_static_file': re.compile(r'https://investors\.arcutis\.com/static-files/'
                                         r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'),
    'annualreports_archive_pdf': re.compile(r'https://www\.annualreports\.com/HostedData/AnnualReportArchive/[a-z]/NASDAQ_[A-Z]{1,5}_\d{4}\.pdf'),
    'crinetics_q4cdn_financial_pdf': re.compile(r'https://s206\.q4cdn\.com/492797646/files/doc_financials/\d{4}/q\d/[0-9a-f-]{36}\.pdf'),
}
SUFFIXES = {'.htm', '.html', '.txt', '.xml', '.jpg', '.jpeg', '.gif', '.png', '.pdf', '.json', '.xsd'}
AUTHORITY = {'as_accepted_byte_identity_verified': False, 'original_version_verified': False,
             'corpus_completeness_claimed': False, 'label_admission_allowed': False, 'outcome_label': None}
COLLECTION_KEYS = {'schema_version', 'plan', 'collector_sha256', 'helper_sha256', 'mode', 'started_at', 'completed_at',
                   'accessions', 'urls', 'lineage', *AUTHORITY}
HELPER = Path(__file__).resolve().parent / 'ma_evidence_io.py'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def write_addressed(directory: Path, prefix: str, obj) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = canonical(obj)
    path = directory / f'{prefix}-{sha256(payload)}.json'
    if not path.exists():
        path.write_bytes(payload)
    require(path.read_bytes() == payload, f'content address collision: {path}')
    return path


# --- routes -----------------------------------------------------------------------------------------

def sec_document(url: str, accession: str | None = None, ciks: set[int] | None = None) -> re.Match:
    match = SEC_DOCUMENT.fullmatch(url) if isinstance(url, str) else None
    require(match is not None, f'not a canonical SEC accession document URL: {url!r}')
    if accession is not None:
        require(match['folder'] == accession.replace('-', ''), f'document outside accession folder: {url}')
    if ciks is not None:
        require(int(match['cik']) in ciks, f'document folder CIK not named by the filing index: {url}')
    return match


def route(url: str) -> str:
    """Return the supported route name for any URL represented in this evidence; reject everything else."""
    if isinstance(url, str) and url.startswith('https://www.sec.gov/'):
        sec_document(url)
        return 'sec_accession_document'
    for name, pattern in DIRECT_ROUTES.items():
        if isinstance(url, str) and pattern.fullmatch(url):
            return name
    raise ValueError(f'unsupported URL route: {url!r}')


def index_url(accession: str, cik: int) -> str:
    return f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-", "")}/{accession}-index.htm'


def raw_suffix(url: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix in SUFFIXES else '.bin'


def store_raw(root: Path, payload: bytes, suffix: str) -> str:
    target = root / 'sec' / 'raw' / f'{sha256(payload)}{suffix}'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(payload)
    require(target.read_bytes() == payload, 'raw content address collision')
    return target.relative_to(root).as_posix()


# --- attempt receipts ------------------------------------------------------------------------------

def check_receipt(root: Path, receipt: dict, label: str, *, now_=None) -> dict[str, str]:
    """Validate one stored attempt: route, terminal clocks, flags, and success-byte integrity."""
    require(receipt.get('schema_version') == ATTEMPT_SCHEMA, f'{label}: attempt schema')
    route(receipt.get('url'))
    require(receipt.get('redirects_followed') is False and receipt.get('automatic_retry_performed') is False,
            f'{label}: redirects or retries recorded')
    ends = {k: receipt[k] for k in ('completed_at', 'retrieved_at', 'failed_at') if receipt.get(k) is not None}
    if receipt.get('outcome') == 'success':
        require(set(ends) == {'completed_at', 'retrieved_at'} and receipt['retrieved_at'] == receipt['completed_at'],
                f'{label}: success requires completed_at == retrieved_at')
        require(receipt.get('http_status') == 200 and receipt.get('final_url') == receipt['url'], f'{label}: success status/url')
        require(not receipt.get('error'), f'{label}: success with error')
        digest, size = receipt.get('source_sha256'), receipt.get('source_bytes')
        require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest) is not None and type(size) is int,
                f'{label}: success hash/size')
        require(receipt.get('raw_relative_path') == f'sec/raw/{digest}{raw_suffix(receipt["url"])}', f'{label}: raw locator')
        read_once(confined(root, receipt['raw_relative_path']), digest, size)
    else:
        require(receipt.get('outcome') == 'failure' and isinstance(receipt.get('error'), str) and receipt['error'],
                f'{label}: failure without error')
        require(receipt.get('source_bytes_archived') is False and 'raw_relative_path' not in receipt, f'{label}: failure with bytes')
        require(bool(ends) and 'retrieved_at' not in ends, f'{label}: failure clocks')
    chronology(label, receipt['attempted_at'], ends, now=now_)
    return {'attempted_at': receipt['attempted_at'], **ends}


def load_attempts(root: Path, *, now_=None) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    directory = root / 'sec' / 'attempts'
    for path in sorted(directory.glob('attempt-*.json')) if directory.exists() else []:
        payload, digest = read_once(confined(root, path.relative_to(root)))
        require(path.stem == f'attempt-{digest}', f'attempt receipt not content-addressed: {path.name}')
        receipt = json.loads(payload)
        check_receipt(root, receipt, path.name, now_=now_)
        found.setdefault(receipt['url'], []).append({**receipt, 'receipt_relative_path': path.relative_to(root).as_posix()})
    for attempts in found.values():
        attempts.sort(key=lambda a: (parse_clock(a['attempted_at'], 'attempted_at'), a['receipt_relative_path']))
    return found


def fetch_once(session, url: str, root: Path) -> dict:
    """One GET; persist raw bytes, then the attempt receipt. Never raises for transport errors."""
    route(url)
    import requests
    agent = SEC_AGENT if urlsplit(url).netloc == 'www.sec.gov' else PLAIN_AGENT
    receipt = {'schema_version': ATTEMPT_SCHEMA, 'url': url, 'attempted_at': now(), 'user_agent': agent,
               'http_client': f'requests {requests.__version__}', 'timeout_seconds': list(TIMEOUT),
               'redirects_followed': False, 'automatic_retry_performed': False}
    try:
        response = session.get(url, headers={'User-Agent': agent}, timeout=TIMEOUT, allow_redirects=False, stream=True)
        try:
            payload = response.raw.read(MAX_BYTES + 1, decode_content=True)
        finally:
            response.close()
        receipt.update(completed_at=now(), http_status=response.status_code, final_url=response.url,
                       content_type=response.headers.get('Content-Type', ''),
                       response_date_header=response.headers.get('Date'),
                       last_modified_header=response.headers.get('Last-Modified'))
        problems = [p for p, bad in (
            (f'http_status {response.status_code}', response.status_code != 200),
            ('response URL differs from request URL', response.url != url),
            ('response exceeds bounded size', len(payload) > MAX_BYTES)) if bad]
        if problems:
            receipt.update(outcome='failure', error='; '.join(problems), source_bytes_archived=False)
        else:
            receipt.update(outcome='success', retrieved_at=receipt['completed_at'], source_sha256=sha256(payload),
                           source_bytes=len(payload), raw_relative_path=store_raw(root, payload, raw_suffix(url)))
    except Exception as exc:  # retained, never retried
        receipt.pop('completed_at', None)
        receipt.update(outcome='failure', failed_at=now(), error=f'{type(exc).__name__}: {exc}', source_bytes_archived=False)
    path = write_addressed(root / 'sec' / 'attempts', 'attempt', receipt)
    return {**receipt, 'receipt_relative_path': path.relative_to(root).as_posix()}


# --- filing index ----------------------------------------------------------------------------------

def _text(fragment: str) -> str:
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).split())


def _table(page: str, summary: str, accession: str, ciks: set[int]) -> list[dict]:
    tables = re.findall(rf'<table class="tableFile" summary="{summary}">(.*?)</table>', page, flags=re.S)
    require(len(tables) <= 1, f'{summary}: duplicated table')
    rows = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tables[0], flags=re.S) if tables else []:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
        if not cells:
            continue
        require(len(cells) == 5, f'{summary}: index row does not have five cells')
        links = re.findall(r'<a href="([^"]+)">(.*?)</a>', cells[2], flags=re.S)
        require(len(links) == 1, f'{summary}: index row lacks exactly one document link')
        href, label = links[0]
        path = href[len('/ix?doc='):] if href.startswith('/ix?doc=') else href
        require(path.startswith('/Archives/'), f'{summary}: unsupported document reference {href!r}')
        url = 'https://www.sec.gov' + path
        match = sec_document(url, accession, ciks)
        name = match['name'].rsplit('/', 1)[-1]
        rendition = '/' in match['name']
        # EDGAR structured forms list an XSL-rendered view (label <stem>.html, no size) before the raw XML row.
        expected = f'{Path(name).stem}.html' if rendition else name
        require(_text(label) == expected, f'{summary}: link text {label!r} differs from document {name!r}')
        size = _text(cells[4])
        require(not rendition or not size, f'{summary}: XSL rendition row carries a size')
        rows.append({'sequence': _text(cells[0]) or None, 'description': _text(cells[1]), 'document_name': name,
                     'type': _text(cells[3]) or None, 'index_size_bytes': int(size) if size.isdigit() else None,
                     'document_url': url, 'inline_xbrl_viewer_link': href.startswith('/ix?doc='),
                     'edgar_xsl_rendition': rendition,
                     'complete_submission_text_file': _text(cells[1]) == 'Complete submission text file'})
    for position, row in enumerate(rows):
        if row['edgar_xsl_rendition']:
            raw = rows[position + 1] if position + 1 < len(rows) else None
            require(raw is not None and not raw['edgar_xsl_rendition'] and raw['sequence'] == row['sequence']
                    and raw['document_name'] == row['document_name'] and raw['type'] == row['type'],
                    f'{summary}: XSL rendition row is not paired with its raw document row')
    return rows


def _info(page: str, head: str) -> list[str]:
    return [_text(v) for v in re.findall(rf'<div class="infoHead">{head}</div>\s*<div class="info">(.*?)</div>', page, flags=re.S)]


def parse_index(payload: bytes, accession: str, archive_cik: int) -> dict:
    """Parse an EDGAR filing index, binding accession and companies structurally (comments ignored)."""
    require(ACCESSION.fullmatch(accession) is not None, f'bad accession {accession!r}')
    page = re.sub(r'<!--.*?-->', '', payload.decode('utf-8', errors='replace'), flags=re.S)
    numbers = [_text(v) for v in re.findall(r'<div id="secNum">(.*?)</div>', page, flags=re.S)]
    require(numbers == [f'SEC Accession No. {accession}'], f'index secNum does not name {accession}: {numbers}')
    form = re.findall(r'<div id="formName">\s*<strong>(.*?)</strong>', page, flags=re.S)
    require(len(form) == 1, 'index form heading missing or duplicated')
    companies = []
    for block in re.findall(r'<div class="companyInfo">(.*?)</div>', page, flags=re.S):
        match = re.search(r'<span class="companyName">(.*?)\((Filer|Filed by|Subject)\)\s*<acronym[^>]*>CIK</acronym>:?\s*'
                          r'<a href="[^"]*CIK=(\d{10})[^"]*">(\d{10})', block, flags=re.S)
        require(match is not None, 'company block lacks name, role and CIK')
        require(match[3] == match[4], 'company CIK link and text differ')
        companies.append({'name': _text(match[1]), 'role': match[2], 'cik': int(match[3])})
    require(bool(companies), 'index names no company')
    ciks = {c['cik'] for c in companies}
    require(archive_cik in ciks, f'requested archive CIK {archive_cik} is not a named filer or subject company')
    documents = _table(page, 'Document Format Files', accession, ciks)
    data_files = _table(page, 'Data Files', accession, ciks)
    aggregate = [d for d in documents if d['complete_submission_text_file']]
    require(len(aggregate) == 1 and aggregate[0]['document_name'] == f'{accession}.txt',
            'index complete-submission reference does not match the accession')
    require(documents[0]['sequence'] == '1' and not documents[0]['complete_submission_text_file'],
            'index primary document row is not sequence 1')
    return {'accession': accession, 'form_heading': _text(form[0]),
            'filing_date': (_info(page, 'Filing Date') or [None])[0],
            'accepted_edgar_display': (_info(page, 'Accepted') or [None])[0],
            'accepted_timezone_note': 'verbatim EDGAR display value; EDGAR operates on US Eastern time; not converted',
            'period_of_report': (_info(page, 'Period of Report') or [None])[0],
            'items': _info(page, 'Items'), 'companies': companies,
            'filer_ciks': sorted({c['cik'] for c in companies if c['role'] in ('Filer', 'Filed by')}),
            'subject_ciks': sorted({c['cik'] for c in companies if c['role'] == 'Subject'}),
            'documents': documents, 'data_files': data_files}


# --- plans -----------------------------------------------------------------------------------------

def validate_plan(plan: dict) -> dict:
    require(plan.get('schema_version') == PLAN_SCHEMA, 'unexpected plan schema')
    require(isinstance(plan.get('name'), str) and PLAN_NAME.fullmatch(plan['name']) is not None, 'unsafe plan name')
    accessions, urls = plan.get('accessions', []), plan.get('urls', [])
    require(isinstance(accessions, list) and isinstance(urls, list) and bool(accessions or urls), 'plan has no targets')
    for target in accessions:
        require(ACCESSION.fullmatch(str(target.get('accession'))) is not None and type(target.get('archive_cik')) is int
                and target['archive_cik'] > 0 and target.get('scope') in SCOPES, f'bad accession target {target}')
    for target in urls:
        require(route(target.get('url')) != 'sec_accession_document', f'direct target is not a supported direct route: {target}')
    require(len({t['accession'] for t in accessions}) == len(accessions) and len({t['url'] for t in urls}) == len(urls),
            'duplicate plan targets')
    return plan


def archive_plan(root: Path, plan_path: Path) -> tuple[dict, dict]:
    payload, digest = read_once(plan_path)
    plan = validate_plan(json.loads(payload))
    target = root / 'sec' / 'plans' / f'{plan["name"]}-{digest}.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(payload)
    read_once(confined(root, target.relative_to(root)), digest)
    return plan, {'name': plan['name'], 'relative_path': target.relative_to(root).as_posix(), 'sha256': digest}


def load_plan(root: Path, binding: dict) -> dict:
    require(set(binding) == {'name', 'relative_path', 'sha256'}, 'plan binding keys')
    require(binding['relative_path'] == f'sec/plans/{binding["name"]}-{binding["sha256"]}.json', 'plan locator')
    payload, _ = read_once(confined(root, binding['relative_path']), binding['sha256'])
    plan = validate_plan(json.loads(payload))
    require(plan['name'] == binding['name'], 'plan name differs from binding')
    return plan


# --- derivation shared by collect and verify --------------------------------------------------------

SUMMARY = ('receipt_relative_path', 'outcome', 'attempted_at', 'completed_at', 'retrieved_at', 'failed_at', 'http_status',
           'error', 'source_sha256', 'source_bytes', 'raw_relative_path')


def _attempts_before(known: dict, url: str, cutoff) -> list[dict]:
    return [a for a in known.get(url, []) if parse_clock(a['attempted_at'], 'attempted_at') <= cutoff]


def _capture(record: dict, attempts: list[dict]) -> dict:
    record = {**record, 'attempts': [{k: a.get(k) for k in SUMMARY} for a in attempts]}
    hit = next((a for a in attempts if a['outcome'] == 'success'), None)
    if hit is None:
        return {**record, 'capture_status': 'failed_not_retried' if attempts else 'not_attempted'}
    return {**record, 'capture_status': 'captured', 'source_sha256': hit['source_sha256'], 'source_bytes': hit['source_bytes'],
            'raw_relative_path': hit['raw_relative_path'], 'retrieved_at': hit['retrieved_at']}


def _row(row: dict, known: dict, cutoff) -> dict:
    record = _capture(row, _attempts_before(known, row['document_url'], cutoff))
    if record['capture_status'] == 'captured':
        record['index_size_match'] = row['index_size_bytes'] == record['source_bytes']
    return record


def derive_accession(root: Path, target: dict, known: dict, cutoff) -> dict:
    accession, cik, scope = target['accession'], target['archive_cik'], target['scope']
    url = index_url(accession, cik)
    entry = _capture({**target, 'index_url': url}, _attempts_before(known, url, cutoff))
    if entry['capture_status'] != 'captured':
        return {**entry, 'status': 'index_' + entry['capture_status']}
    payload, _ = read_once(confined(root, entry['raw_relative_path']), entry['source_sha256'], entry['source_bytes'])
    index = parse_index(payload, accession, cik)
    entry['index'] = {k: v for k, v in index.items() if k not in ('documents', 'data_files')}
    documents = []
    for position, row in enumerate(index['documents']):
        if row['complete_submission_text_file']:
            documents.append({**row, 'capture_status': 'complete_submission_text_file_not_fetched'})
        elif scope == 'primary_only' and position > 0:
            documents.append({**row, 'capture_status': 'listed_not_fetched_primary_only_scope'})
        else:
            documents.append(_row(row, known, cutoff))
    data_files = [_row(row, known, cutoff) if scope == 'full_with_data_files'
                  else {**row, 'capture_status': 'structured_data_file_listed_not_fetched'} for row in index['data_files']]
    return {**entry, 'status': 'index_captured', 'documents': documents, 'data_files': data_files}


def derive(root: Path, plan: dict, known: dict, cutoff) -> tuple[list[dict], list[dict]]:
    return ([derive_accession(root, t, known, cutoff) for t in plan.get('accessions', [])],
            [_capture(dict(t), _attempts_before(known, t['url'], cutoff)) for t in plan.get('urls', [])])


def referenced_clocks(entries: list[dict]) -> dict[str, str]:
    clocks = {}
    for entry in entries:
        for record in [entry] + entry.get('documents', []) + entry.get('data_files', []):
            for attempt in record.get('attempts', []):
                for key in ('attempted_at', 'completed_at', 'retrieved_at', 'failed_at'):
                    if attempt.get(key):
                        clocks[f"{attempt['receipt_relative_path']}.{key}"] = attempt[key]
    return clocks


# --- collect / verify / rebind ---------------------------------------------------------------------

def _get(session, url: str, root: Path, known: dict, pause: float, offline: bool) -> None:
    if known.get(url):
        return
    require(not offline, f'cache-only replay has no archived attempt for {url}')
    known[url] = [fetch_once(session, url, root)]
    time.sleep(pause)


def _fetch_plan(session, root: Path, plan: dict, known: dict, pause: float, offline: bool) -> None:
    for target in plan.get('accessions', []):
        url = index_url(target['accession'], target['archive_cik'])
        _get(session, url, root, known, pause, offline)
        hit = next((a for a in known[url] if a['outcome'] == 'success'), None)
        if hit is None:
            continue
        payload, _ = read_once(confined(root, hit['raw_relative_path']), hit['source_sha256'], hit['source_bytes'])
        index = parse_index(payload, target['accession'], target['archive_cik'])
        for position, row in enumerate(index['documents']):
            if not row['complete_submission_text_file'] and (target['scope'] != 'primary_only' or position == 0):
                _get(session, row['document_url'], root, known, pause, offline)
        if target['scope'] == 'full_with_data_files':
            for row in index['data_files']:
                _get(session, row['document_url'], root, known, pause, offline)
    for target in plan.get('urls', []):
        _get(session, target['url'], root, known, pause, offline)


def _session():
    import requests
    from requests.adapters import HTTPAdapter
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=0))
    return session


def _write(root: Path, collection: dict) -> Path:
    validate_collection(collection, root)
    directory = root / 'sec' / 'collections'
    path = write_addressed(directory, f'sec-collection-{collection["plan"]["name"]}', collection)
    require(path.resolve().parent == directory.resolve(), 'collection path escapes evidence root')
    return path


def collect(plan_path: Path, root: Path, session=None, pause: float = 0.25) -> Path:
    root = root.resolve()
    plan, binding = archive_plan(root, plan_path)
    started = now()
    known = load_attempts(root)
    _fetch_plan(session or _session(), root, plan, known, pause, offline=False)
    completed = now()
    accessions, urls = derive(root, plan, load_attempts(root), parse_clock(completed, 'completed_at'))
    collection = {'schema_version': SCHEMA, 'plan': binding, 'collector_sha256': sha256(Path(__file__).read_bytes()),
                  'helper_sha256': sha256(HELPER.read_bytes()), 'mode': 'network_collection', 'started_at': started,
                  'completed_at': completed, 'accessions': accessions, 'urls': urls, 'lineage': None, **AUTHORITY}
    return _write(root, collection)


LEGACY_KEEP = ('capture_status', 'source_sha256', 'source_bytes', 'raw_relative_path', 'retrieved_at', 'document_url',
               'document_name', 'type', 'index_size_bytes')


CAPTURE = ('source_sha256', 'source_bytes', 'raw_relative_path', 'retrieved_at')


def _legacy_fields(entry: dict) -> dict:
    """Fields a v1 collection recorded, normalized so a v2 derivation must reproduce them exactly."""
    if 'accession' not in entry:  # direct URL entry: v1 'status' and v2 'capture_status' name the same state
        return {'url': entry['url'], 'state': entry.get('status', entry.get('capture_status')), **{k: entry.get(k) for k in CAPTURE}}
    if 'index_attempts' in entry:  # v1 kept the index capture in its attempt summaries
        hit = next((a for a in entry['index_attempts'] if a.get('outcome') == 'success'), {})
    else:
        hit = entry if entry.get('capture_status') == 'captured' else {}
    index = entry.get('index') or {}
    return {'accession': entry['accession'], 'status': entry.get('status'), 'index_capture': {k: hit.get(k) for k in CAPTURE},
            'index': {k: index.get(k) for k in ('filing_date', 'accepted_edgar_display', 'form_heading')},
            'documents': [{k: d.get(k) for k in LEGACY_KEEP} for d in entry.get('documents', [])],
            'data_files': [{k: d.get(k) for k in LEGACY_KEEP} for d in entry.get('data_files', [])]}


def rebind(root: Path, legacy_relative: Path, plan_source: Path, producer_snapshot: Path | None = None) -> Path:
    """Re-derive a legacy v1 collection from archived evidence only, in cache-only mode, with new clocks."""
    root = root.resolve()
    legacy_payload, legacy_digest = read_once(confined(root, legacy_relative))
    require(Path(legacy_relative).stem.endswith(legacy_digest), 'legacy collection not content-addressed')
    legacy = json.loads(legacy_payload)
    require(legacy.get('schema_version') == LEGACY_SCHEMA, 'not a legacy v1 collection')
    _, plan_digest = read_once(plan_source)
    require(plan_digest == legacy['plan_sha256'], 'plan bytes differ from the legacy recorded plan hash')
    plan, binding = archive_plan(root, plan_source)
    require(plan['name'] == legacy['plan_name'], 'plan name differs from legacy')
    snapshot = None
    if producer_snapshot is not None:
        snap_payload, snap_digest = read_once(producer_snapshot)
        require(snap_digest == legacy['collector_sha256'], 'producer snapshot does not match the recorded collector hash')
        target = root / 'sec' / 'producers' / f'collect_sec_accessions-{snap_digest}.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(snap_payload)
        snapshot = {'relative_path': target.relative_to(root).as_posix(), 'sha256': snap_digest}
    started = now()
    known = load_attempts(root)
    _fetch_plan(None, root, plan, known, 0, offline=True)
    completed = now()
    accessions, urls = derive(root, plan, known, parse_clock(completed, 'completed_at'))
    require(len(legacy['accessions']) == len(accessions) and len(legacy['urls']) == len(urls), 'legacy target count differs')
    for old, new in zip(legacy['accessions'] + legacy['urls'], accessions + urls):
        require(_legacy_fields(old) == _legacy_fields(new),
                f'legacy entry differs from re-derivation: {old.get("accession") or old.get("url")}')
    lineage = {'legacy_collection': {'relative_path': Path(legacy_relative).as_posix(), 'sha256': legacy_digest,
                                     'schema_version': LEGACY_SCHEMA, 'recorded_collector_sha256': legacy['collector_sha256'],
                                     'recorded_started_at': legacy['started_at'], 'recorded_completed_at': legacy['completed_at'],
                                     'recorded_plan_sha256': legacy['plan_sha256']},
               'producer_snapshot': snapshot,
               'producer_snapshot_status': 'archived_matching_recorded_hash' if snapshot else 'unavailable_not_reconstructed',
               'legacy_entries_match_rederivation': True,
               'note': 'legacy file and receipts unchanged; this v2 collection is a new cache-only derivation, not an in-place repair'}
    collection = {'schema_version': SCHEMA, 'plan': binding, 'collector_sha256': sha256(Path(__file__).read_bytes()),
                  'helper_sha256': sha256(HELPER.read_bytes()), 'mode': 'cache_only_rebind_of_legacy', 'started_at': started,
                  'completed_at': completed, 'accessions': accessions, 'urls': urls, 'lineage': lineage, **AUTHORITY}
    return _write(root, collection)


LINEAGE_KEYS = {'legacy_collection', 'producer_snapshot', 'producer_snapshot_status', 'legacy_entries_match_rederivation', 'note'}


def validate_collection(collection: dict, root: Path, *, now_=None) -> dict[str, str]:
    """Re-derive the collection from archived plan, receipts and index bytes; require exact equality."""
    current = now_ or measured_now()
    require(isinstance(collection, dict) and set(collection) == COLLECTION_KEYS, 'unexpected collection keys')
    require(collection['schema_version'] == SCHEMA, 'unexpected collection schema')
    for key, value in AUTHORITY.items():
        require(collection[key] is value, f'unsupported authority claim: {key}={collection[key]!r}')
    require(collection['mode'] in ('network_collection', 'cache_only_rebind_of_legacy'), 'unknown collection mode')
    chronology('collection', collection['started_at'], {'completed_at': collection['completed_at']}, now=current)
    completed = parse_clock(collection['completed_at'], 'completed_at')
    plan = load_plan(root, collection['plan'])
    accessions, urls = derive(root, plan, load_attempts(root, now_=current), completed)
    require(collection['accessions'] == accessions, 'accession entries differ from archived evidence')
    require(collection['urls'] == urls, 'direct-URL entries differ from archived evidence')
    clocks = referenced_clocks(accessions + urls)
    for name, value in clocks.items():
        require(parse_clock(value, name) <= completed, f'collection completed before represented clock {name}={value}')
    lineage = collection['lineage']
    if collection['mode'] == 'network_collection':
        require(lineage is None, 'network collection carries lineage')
        return clocks
    require(isinstance(lineage, dict) and set(lineage) == LINEAGE_KEYS and lineage['legacy_entries_match_rederivation'] is True,
            'rebind lineage keys')
    legacy = lineage['legacy_collection']
    old = json.loads(read_once(confined(root, legacy['relative_path']), legacy['sha256'])[0])
    require(old.get('schema_version') == LEGACY_SCHEMA and old['plan_sha256'] == collection['plan']['sha256']
            and old['plan_name'] == collection['plan']['name'] and old['collector_sha256'] == legacy['recorded_collector_sha256']
            and old['started_at'] == legacy['recorded_started_at'] and old['completed_at'] == legacy['recorded_completed_at'],
            'legacy lineage differs from the legacy file')
    require(len(old['accessions']) == len(accessions) and len(old['urls']) == len(urls), 'legacy target count differs')
    for previous, new in zip(old['accessions'] + old['urls'], accessions + urls):
        require(_legacy_fields(previous) == _legacy_fields(new), 'legacy entry differs from re-derivation')
    snapshot = lineage['producer_snapshot']
    if snapshot is None:
        require(lineage['producer_snapshot_status'] == 'unavailable_not_reconstructed', 'snapshot status')
    else:
        require(lineage['producer_snapshot_status'] == 'archived_matching_recorded_hash'
                and snapshot['relative_path'] == f'sec/producers/collect_sec_accessions-{legacy["recorded_collector_sha256"]}.py',
                'snapshot binding')
        read_once(confined(root, snapshot['relative_path']), legacy['recorded_collector_sha256'])
    return clocks


def verify_collection(path: Path, root: Path, *, now_=None) -> tuple[dict, dict[str, str], str]:
    root = root.resolve()
    path = Path(path).resolve()
    require(path.parent == (root / 'sec' / 'collections').resolve(), 'collection outside sec/collections')
    payload, digest = read_once(confined(root, path.relative_to(root)))
    collection = json.loads(payload)
    name = (collection.get('plan') or {}).get('name') if isinstance(collection, dict) else None
    require(path.name == f'sec-collection-{name}-{digest}.json', 'collection file name does not bind plan name and content hash')
    return collection, validate_collection(collection, root, now_=now_), digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('collect')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--evidence-root', type=Path, required=True)
    again = sub.add_parser('rebind')
    again.add_argument('--evidence-root', type=Path, required=True)
    again.add_argument('--legacy', type=Path, required=True, help='evidence-root-relative legacy collection path')
    again.add_argument('--plan', type=Path, required=True)
    again.add_argument('--producer-snapshot', type=Path)
    check = sub.add_parser('verify')
    check.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'collect':
            print(collect(args.plan, args.evidence_root))
        elif args.command == 'rebind':
            print(rebind(args.evidence_root, args.legacy, args.plan, args.producer_snapshot))
        else:
            root = args.evidence_root.resolve()
            for path in sorted((root / 'sec' / 'collections').glob('sec-collection-*.json')):
                print(verify_collection(path, root)[2], path.name)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
