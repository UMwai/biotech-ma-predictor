#!/usr/bin/env python3
"""Archive SEC accession filing indexes and their listed documents as raw bytes.

Each target accession is captured as its EDGAR ``<accession>-index.htm`` page
plus every row of the index's "Document Format Files" table (``full`` scope) or
only the primary row (``primary_only``). "Data Files" (XBRL) rows are listed
from the index and fetched only under ``full_with_data_files``. Direct URL targets (data.sec.gov submissions
JSON, issuer PDFs) are fetched once on an explicit host allowlist.

Every GET is made at most once: bounded timeouts, no redirects followed, no
automatic retries. Raw bytes are persisted before the content-addressed attempt
receipt, so an interruption cannot lose a completed attempt. A hash-verified
success for the same URL is reused; a recorded failure is never retried.

Changed hypothesis (2026-10-03): www.sec.gov Archives answered HTTP 403 to the
contact-free agent used by ``collect_ma_issuer_archive.py``; this collector uses
the contact-bearing agent the repository owner already used in earlier SEC
receipts. data.sec.gov accepted the contact-free agent. This is not a retry loop.

Captured bytes are SEC-hosted dissemination copies. An index ``Size`` match is
recorded, but no as-accepted byte identity, original-version judgment, corpus
completeness or outcome label is asserted.
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
from scripts.ma_evidence_io import chronology, confined, measured_now, read_once, require, sha256  # noqa: E402

SCHEMA = 'ma-exploration-sec-collection-v1'
ATTEMPT_SCHEMA = 'ma-exploration-public-get-attempt-v1'
SEC_AGENT = 'BiotechMAPredictor/0.1 waiy392f@gmail.com'
PLAIN_AGENT = 'biotech-ma-predictor public historical acquisition research'
AGENTS = {'www.sec.gov': SEC_AGENT, 'data.sec.gov': PLAIN_AGENT}
ALLOWED_HOSTS = frozenset({'www.sec.gov', 'data.sec.gov', 'investors.arcutis.com',
                           'www.annualreports.com', 's206.q4cdn.com'})
TIMEOUT = (10, 60)
MAX_BYTES = 60_000_000
SCOPES = ('full', 'primary_only', 'full_with_data_files')
ACCESSION = re.compile(r'\d{10}-\d{2}-\d{6}')
SUFFIXES = {'.htm', '.html', '.txt', '.xml', '.jpg', '.jpeg', '.gif', '.png', '.pdf', '.json', '.xsd'}


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


def check_url(url: str) -> str:
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.netloc in ALLOWED_HOSTS and not parts.fragment
            and not parts.username and not parts.password, f'URL outside allowlist: {url}')
    return parts.netloc


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


def attempt_clocks(receipt: dict, label: str, *, now_=None) -> dict[str, str]:
    ends = {k: receipt[k] for k in ('completed_at', 'retrieved_at', 'failed_at') if receipt.get(k) is not None}
    if receipt.get('outcome') == 'success':
        require('retrieved_at' in ends, f'{label}: success without retrieved_at')
    else:
        require(receipt.get('outcome') == 'failure' and bool(ends), f'{label}: failure without clock')
    chronology(label, receipt['attempted_at'], ends, now=now_)
    return {'attempted_at': receipt['attempted_at'], **ends}


def load_attempts(root: Path, *, now_=None) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    directory = root / 'sec' / 'attempts'
    for path in sorted(directory.glob('attempt-*.json')) if directory.exists() else []:
        payload, digest = read_once(confined(root, path.relative_to(root)))
        require(path.stem.endswith(digest), f'attempt receipt not content-addressed: {path.name}')
        receipt = json.loads(payload)
        require(receipt.get('schema_version') == ATTEMPT_SCHEMA, f'unexpected attempt schema: {path.name}')
        attempt_clocks(receipt, path.name, now_=now_)
        if receipt['outcome'] == 'success':
            read_once(confined(root, receipt['raw_relative_path']), receipt['source_sha256'], receipt['source_bytes'])
        found.setdefault(receipt['url'], []).append({**receipt, 'receipt_relative_path': path.relative_to(root).as_posix()})
    for attempts in found.values():
        attempts.sort(key=lambda a: a['attempted_at'])
    return found


def fetch_once(session, url: str, root: Path) -> dict:
    """One GET; persist raw bytes, then the attempt receipt. Never raises for transport errors."""
    host = check_url(url)
    import requests
    agent = AGENTS.get(host, PLAIN_AGENT)
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
        receipt.update(outcome='failure', failed_at=now(), error=f'{type(exc).__name__}: {exc}', source_bytes_archived=False)
    path = write_addressed(root / 'sec' / 'attempts', 'attempt', receipt)
    return {**receipt, 'receipt_relative_path': path.relative_to(root).as_posix()}


def _cells(row: str) -> list[str]:
    return re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)


def _text(fragment: str) -> str:
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).split())


def _table(page: str, summary: str) -> list[dict]:
    match = re.search(rf'<table class="tableFile" summary="{summary}">(.*?)</table>', page, flags=re.S)
    if match is None:
        return []
    rows = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', match.group(1), flags=re.S):
        cells = _cells(row)
        if not cells:
            continue
        require(len(cells) == 5, f'{summary}: index row does not have five cells')
        hrefs = re.findall(r'href="([^"]+)"', cells[2])
        require(len(hrefs) == 1, f'{summary}: index row lacks one document link')
        href = hrefs[0]
        normalized = href[len('/ix?doc='):] if href.startswith('/ix?doc=') else href
        size = _text(cells[4])
        rows.append({'sequence': _text(cells[0]) or None, 'description': _text(cells[1]),
                     'document_name': Path(normalized).name, 'type': _text(cells[3]) or None,
                     'index_size_bytes': int(size) if size.isdigit() else None,
                     'href': href, 'document_url': 'https://www.sec.gov' + normalized,
                     'inline_xbrl_viewer_link': href.startswith('/ix?doc='),
                     'complete_submission_text_file': _text(cells[1]) == 'Complete submission text file'})
    return rows


def _info(page: str, head: str) -> list[str]:
    return [_text(v) for v in re.findall(rf'<div class="infoHead">{head}</div>\s*<div class="info">(.*?)</div>', page, flags=re.S)]


def parse_index(payload: bytes, accession: str, archive_cik: int) -> dict:
    """Extract identity, dates, companies and document tables from an EDGAR filing index page."""
    page = payload.decode('utf-8', errors='replace')
    require(f'{accession}' in page, 'filing index does not name the requested accession')
    form = re.findall(r'<div id="formName">\s*<strong>(.*?)</strong>', page, flags=re.S)
    companies = []
    for block in re.findall(r'<div class="companyInfo">(.*?)</div>\s*</div>', page, flags=re.S):
        name = re.search(r'<span class="companyName">(.*?)<acronym', block, flags=re.S)
        cik = re.search(r'CIK=(\d{10})', block)
        role = re.search(r'\((Filer|Subject|Filed by|Reporting|Issuer|Filed for)\)', block)
        companies.append({'name_and_role': _text(name.group(1)) if name else None,
                          'role': role.group(1) if role else None, 'cik': int(cik.group(1)) if cik else None})
    documents = _table(page, 'Document Format Files')
    data_files = _table(page, 'Data Files')
    require(bool(documents), 'filing index has no document table')
    # Third-party filings link documents under the filer's CIK folder; only CIKs the index itself names count.
    folder_ciks = {archive_cik} | {c['cik'] for c in companies if c['cik'] is not None}
    prefixes = tuple(f'https://www.sec.gov/Archives/edgar/data/{c}/{accession.replace("-", "")}/' for c in folder_ciks)
    for row in documents + data_files:
        require(row['document_url'].startswith(prefixes), f'index document outside accession folder: {row["href"]}')
    return {'accession': accession, 'form_heading': _text(form[0]) if form else None,
            'filing_date': (_info(page, 'Filing Date') or [None])[0],
            'accepted_edgar_display': (_info(page, 'Accepted') or [None])[0],
            'accepted_timezone_note': 'verbatim EDGAR display value; EDGAR operates on US Eastern time; not converted',
            'period_of_report': (_info(page, 'Period of Report') or [None])[0],
            'items': _info(page, 'Items'), 'companies': companies,
            'documents': documents, 'data_files': data_files}


def _success(attempts: list[dict]) -> dict | None:
    return next((a for a in attempts if a['outcome'] == 'success'), None)


def _get(session, url: str, root: Path, known: dict, pause: float) -> list[dict]:
    attempts = known.get(url, [])
    if not attempts:
        attempts = [fetch_once(session, url, root)]
        known[url] = attempts
        time.sleep(pause)
    return attempts


def _summary(attempts: list[dict]) -> list[dict]:
    keys = ('receipt_relative_path', 'outcome', 'attempted_at', 'retrieved_at', 'failed_at', 'http_status', 'error',
            'source_sha256', 'source_bytes', 'raw_relative_path')
    return [{k: a.get(k) for k in keys} for a in attempts]


def _fetch_row(session, row: dict, root: Path, known: dict, pause: float) -> dict:
    record = {k: v for k, v in row.items() if k != 'href'}
    attempts = _get(session, row['document_url'], root, known, pause)
    record['attempts'] = _summary(attempts)
    hit = _success(attempts)
    if hit is None:
        return {**record, 'capture_status': 'failed_not_retried'}
    return {**record, 'capture_status': 'captured', 'source_sha256': hit['source_sha256'],
            'source_bytes': hit['source_bytes'], 'raw_relative_path': hit['raw_relative_path'],
            'retrieved_at': hit['retrieved_at'], 'index_size_match': row['index_size_bytes'] == hit['source_bytes']}


def collect_accession(session, target: dict, root: Path, known: dict, pause: float) -> dict:
    accession, cik, scope = target['accession'], int(target['archive_cik']), target['scope']
    require(ACCESSION.fullmatch(accession) is not None and scope in SCOPES, f'bad target {target}')
    index_url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-", "")}/{accession}-index.htm'
    attempts = _get(session, index_url, root, known, pause)
    entry = {**target, 'index_url': index_url, 'index_attempts': _summary(attempts)}
    success = _success(attempts)
    if success is None:
        return {**entry, 'status': 'index_failed_not_retried'}
    payload, _ = read_once(confined(root, success['raw_relative_path']), success['source_sha256'])
    index = parse_index(payload, accession, cik)
    entry['index'] = {k: v for k, v in index.items() if k not in ('documents', 'data_files')}
    documents = []
    for position, row in enumerate(index['documents']):
        if row['complete_submission_text_file']:
            documents.append({k: v for k, v in row.items() if k != 'href'} | {'capture_status': 'complete_submission_text_file_not_fetched'})
        elif scope != 'primary_only' or position == 0:
            documents.append(_fetch_row(session, row, root, known, pause))
        else:
            documents.append({k: v for k, v in row.items() if k != 'href'} | {'capture_status': 'listed_not_fetched_primary_only_scope'})
    if scope == 'full_with_data_files':
        data_files = [_fetch_row(session, row, root, known, pause) for row in index['data_files']]
    else:
        data_files = [{k: v for k, v in row.items() if k != 'href'} | {'capture_status': 'structured_data_file_listed_not_fetched'}
                      for row in index['data_files']]
    return {**entry, 'status': 'index_captured', 'documents': documents, 'data_files': data_files}


def collect_url(session, target: dict, root: Path, known: dict, pause: float) -> dict:
    attempts = _get(session, target['url'], root, known, pause)
    hit = _success(attempts)
    entry = {**target, 'attempts': _summary(attempts)}
    if hit is None:
        return {**entry, 'status': 'failed_not_retried'}
    return {**entry, 'status': 'captured', 'source_sha256': hit['source_sha256'], 'source_bytes': hit['source_bytes'],
            'raw_relative_path': hit['raw_relative_path'], 'retrieved_at': hit['retrieved_at']}


def collect(plan_path: Path, root: Path, session=None, pause: float = 0.25) -> Path:
    plan_bytes, plan_digest = read_once(plan_path)
    plan = json.loads(plan_bytes)
    require(plan.get('schema_version') == 'ma-exploration-sec-plan-v1', 'unexpected plan schema')
    started = now()
    if session is None:
        import requests
        from requests.adapters import HTTPAdapter
        session = requests.Session()
        session.mount('https://', HTTPAdapter(max_retries=0))
    known = load_attempts(root)
    accessions = [collect_accession(session, t, root, known, pause) for t in plan.get('accessions', [])]
    urls = [collect_url(session, t, root, known, pause) for t in plan.get('urls', [])]
    collection = {'schema_version': SCHEMA, 'plan_name': plan['name'], 'plan_sha256': plan_digest,
                  'collector_sha256': sha256(Path(__file__).read_bytes()), 'started_at': started, 'completed_at': now(),
                  'accessions': accessions, 'urls': urls, 'as_accepted_byte_identity_verified': False,
                  'original_version_verified': False, 'corpus_completeness_claimed': False, 'outcome_label': None,
                  'label_admission_allowed': False}
    validate_collection(collection, root)
    return write_addressed(root / 'sec', f'sec-collection-{plan["name"]}', collection)


def validate_collection(collection: dict, root: Path, *, now_=None) -> dict[str, str]:
    """Re-verify every receipt, raw byte, summary and clock the collection represents."""
    current = now_ or measured_now()
    require(collection.get('schema_version') == SCHEMA and collection.get('outcome_label') is None
            and collection.get('label_admission_allowed') is False and collection.get('corpus_completeness_claimed') is False,
            'unexpected collection schema or authority flags')
    clocks: dict[str, str] = {}

    def check(summaries: list[dict], url: str) -> dict | None:
        hit = None
        for summary in summaries:
            path = confined(root, summary['receipt_relative_path'])
            payload, digest = read_once(path)
            require(path.stem.endswith(digest), f'{path.name}: not content-addressed')
            receipt = json.loads(payload)
            require(receipt['url'] == url and receipt['schema_version'] == ATTEMPT_SCHEMA, f'{path.name}: url/schema')
            require(all(summary.get(k) == receipt.get(k) for k in summary if k != 'receipt_relative_path'),
                    f'{path.name}: summary differs from receipt')
            for name, value in attempt_clocks(receipt, path.name, now_=current).items():
                clocks[f'{path.name}.{name}'] = value
            if receipt['outcome'] == 'success':
                read_once(confined(root, receipt['raw_relative_path']), receipt['source_sha256'], receipt['source_bytes'])
                hit = hit or receipt
        return hit

    for entry in collection['accessions']:
        hit = check(entry['index_attempts'], entry['index_url'])
        require((hit is not None) == (entry['status'] == 'index_captured'), f"{entry['accession']}: index status")
        if hit is None:
            continue
        payload, _ = read_once(confined(root, hit['raw_relative_path']), hit['source_sha256'])
        index = parse_index(payload, entry['accession'], int(entry['archive_cik']))
        require(entry['index'] == {k: v for k, v in index.items() if k not in ('documents', 'data_files')},
                f"{entry['accession']}: index fields differ on reparse")
        require([d['document_url'] for d in entry['documents']] == [d['document_url'] for d in index['documents']],
                f"{entry['accession']}: document census differs on reparse")
        require([d['document_url'] for d in entry['data_files']] == [d['document_url'] for d in index['data_files']],
                f"{entry['accession']}: data file census differs on reparse")
        for doc in entry['documents'] + entry['data_files']:
            if 'attempts' in doc:
                got = check(doc['attempts'], doc['document_url'])
                require((got is not None) == (doc['capture_status'] == 'captured'), f"{doc['document_url']}: status")
                if got is not None:
                    require(doc['source_sha256'] == got['source_sha256'] and doc['retrieved_at'] == got['retrieved_at'],
                            f"{doc['document_url']}: not bound to its success receipt")
    for entry in collection['urls']:
        got = check(entry['attempts'], entry['url'])
        require((got is not None) == (entry['status'] == 'captured'), f"{entry['url']}: status")
    chronology('collection', collection['started_at'], {'completed_at': collection['completed_at']}, now=current)
    return clocks


def verify_collection(path: Path, root: Path, *, now_=None) -> tuple[dict, dict[str, str], str]:
    payload, digest = read_once(path)
    require(path.stem.endswith(digest), 'collection is not content-addressed')
    collection = json.loads(payload)
    return collection, validate_collection(collection, root, now_=now_), digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(collect(args.plan, args.evidence_root.resolve()))
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
