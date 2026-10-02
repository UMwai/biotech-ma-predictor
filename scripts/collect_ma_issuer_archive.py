#!/usr/bin/env python3
"""Freeze a Nasdaq-IR (nir-widget) issuer year inventory and capture dated release bodies.

Inventory pages are reused from already-archived captures (hash-verified, never
refetched); year URLs must re-derive from the archived public year form. Each
selected body is requested at most once with the ordinary ``requests`` client and
an honest User-Agent: bounded connect/read timeouts, no redirects followed, no
automatic retries, no authentication or protection workaround. Every success or
failure is persisted (raw bytes first, then its receipt) before the next request,
so an interruption cannot lose completed attempts. A hash-verified success for the
same URL is reused; a recorded failure is never retried automatically.

A current listing cannot prove historical completeness, original content, or the
absence of removed releases. No label is assigned.

Changed hypothesis (2026-10-02): the first version of this collector used urllib
and timed out on every body request; the same honest-agent GET through requests
returned 200, so the transport changed. This is not a retry loop.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_issuer_archives import Document, clean, drupal_page, drupal_year_form  # noqa: E402
from scripts.ma_evidence_io import chronology, confined, measured_now, parse_clock, read_once, require, sha256  # noqa: E402

SCHEMA = 'ma-evidence-issuer-archive-collection-v2'
ATTEMPT_SCHEMA = 'ma-evidence-public-get-attempt-v1'
USER_AGENT = 'biotech-ma-predictor public historical acquisition research'
TIMEOUT = (10, 30)  # connect, read seconds
MAX_BYTES = 10_000_000


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


def store_raw(out_root: Path, payload: bytes) -> str:
    raw_dir = out_root / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f'{sha256(payload)}.html'
    if not target.exists():
        target.write_bytes(payload)
    require(target.read_bytes() == payload, 'raw content address collision')
    return f'raw/{target.name}'


def check_url(url: str, host: str) -> None:
    parts = urlsplit(url)
    require(parts.scheme == 'https' and parts.netloc == host and not parts.fragment, f'URL outside https://{host}: {url}')


def load_probe_capture(probe_root: Path, receipt_name: str, out_root: Path, host: str) -> tuple[bytes, dict]:
    """Verify a pre-existing primary capture (confined to probe_root) and copy its exact bytes."""
    receipt_path = confined(probe_root, receipt_name)
    receipt_bytes, receipt_digest = read_once(receipt_path)
    receipt = json.loads(receipt_bytes)
    check_url(receipt['source_uri'], host)
    require(receipt.get('http_status') == 200 and receipt.get('resolved_uri') == receipt['source_uri'], f'{receipt_name}: status/redirect')
    chronology(receipt_name, receipt['attempted_at'], {'retrieved_at': receipt['retrieved_at']})
    payload, _ = read_once(confined(probe_root, receipt['source_path']), receipt['source_sha256'], receipt['source_bytes'])
    return payload, {'receipt_name': receipt_name, 'receipt_sha256': receipt_digest, 'source_uri': receipt['source_uri'],
                     'source_sha256': receipt['source_sha256'], 'source_bytes': receipt['source_bytes'],
                     'attempted_at': receipt['attempted_at'], 'retrieved_at': receipt['retrieved_at'],
                     'http_client': receipt.get('http_client', 'not_recorded'),
                     'raw_relative_path': store_raw(out_root, payload), 'captured_by': 'primary_issuer_access_probe'}


def freeze_inventory(probe_root: Path, years: list[int], out_root: Path, host: str) -> dict:
    archive_payload, archive = load_probe_capture(probe_root, 'abus-publisher-platform-archive.receipt.json', out_root, host)
    pages, inventory = [], []
    for year in years:
        payload, capture = load_probe_capture(probe_root, f'abus-publisher-platform-{year}.receipt.json', out_root, host)
        url, year_name = drupal_year_form(archive_payload, archive['source_uri'], year)
        require(url == capture['source_uri'], f'{year}: captured URL is not the archived public year-form URL')
        rows, pager = drupal_page(payload, url, year, 1, year_name)
        require(pager['next_url'] is None, f'{year}: unexpected next page; reuse-only inventory would be partial')
        for row in rows:
            check_url(row['url'], host)
        pages.append({**capture, 'archive_year': year, 'year_selector': year_name, 'entry_count': len(rows),
                      'next_url': None, 'selected_year_verified': True})
        inventory.extend({**r, 'archive_year': year} for r in rows)
    require(len({r['url'] for r in inventory}) == len(inventory), 'duplicate release URL across years')
    return {'archive_page': archive, 'host': host, 'pages': pages, 'inventory': inventory}


def attempt_clocks(receipt: dict, label: str) -> dict[str, str]:
    """Validate one attempt receipt's own clocks: attempted <= retrieved/completed/failed <= measured now."""
    ends = {k: receipt[k] for k in ('completed_at', 'retrieved_at', 'failed_at') if receipt.get(k) is not None}
    if receipt.get('outcome') == 'success':
        require('retrieved_at' in ends, f'{label}: success without retrieved_at')
    else:
        require(receipt.get('outcome') == 'failure' and ('completed_at' in ends or 'failed_at' in ends),
                f'{label}: failure without completion/failure clock')
    chronology(label, receipt['attempted_at'], ends)
    return {'attempted_at': receipt['attempted_at'], **ends}


def prior_attempts(out_root: Path) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    attempt_dir = out_root / 'attempts'
    for path in sorted(attempt_dir.glob('attempt-*.json')) if attempt_dir.exists() else []:
        payload, digest = read_once(confined(out_root, path.relative_to(out_root)))
        require(path.stem.endswith(digest), f'attempt receipt not content-addressed: {path.name}')
        receipt = json.loads(payload)
        require(receipt.get('schema_version') == ATTEMPT_SCHEMA, f'unexpected attempt schema: {path.name}')
        attempt_clocks(receipt, path.name)
        found.setdefault(receipt['url'], []).append({**receipt, 'receipt_relative_path': f'attempts/{path.name}'})
    return found


def verified_success(out_root: Path, attempt: dict) -> bool:
    if attempt.get('outcome') != 'success':
        return False
    read_once(confined(out_root, attempt['raw_relative_path']), attempt['source_sha256'], attempt['source_bytes'])
    return True


def fetch_once(session, url: str, host: str, out_root: Path) -> Path:
    """One request; persist raw bytes then the attempt receipt before returning."""
    check_url(url, host)
    import requests  # local import keeps parsing/tests usable without the client
    attempted = now()
    receipt = {'schema_version': ATTEMPT_SCHEMA, 'url': url, 'attempted_at': attempted, 'user_agent': USER_AGENT,
               'http_client': f'requests {requests.__version__}', 'timeout_seconds': list(TIMEOUT),
               'redirects_followed': False, 'automatic_retry_performed': False}
    try:
        response = session.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT, allow_redirects=False, stream=True)
        try:
            payload = response.raw.read(MAX_BYTES + 1, decode_content=True)
        finally:
            response.close()
        receipt.update(completed_at=now(), http_status=response.status_code, final_url=response.url,
                       content_type=response.headers.get('Content-Type', ''),
                       response_date_header=response.headers.get('Date'),
                       last_modified_header=response.headers.get('Last-Modified'))
        problems = []
        if response.status_code != 200:
            problems.append(f'http_status {response.status_code}')
        if response.url != url:
            problems.append('response URL differs from request URL')
        if len(payload) > MAX_BYTES:
            problems.append('response exceeds bounded size')
        if problems:
            receipt.update(outcome='failure', error='; '.join(problems), source_bytes_archived=False)
        else:
            receipt.update(outcome='success', retrieved_at=receipt['completed_at'], source_sha256=sha256(payload),
                           source_bytes=len(payload), raw_relative_path=store_raw(out_root, payload))
    except Exception as exc:  # every failure is retained, never retried
        receipt.update(outcome='failure', failed_at=now(), error=f'{type(exc).__name__}: {exc}', source_bytes_archived=False)
    return write_addressed(out_root / 'attempts', 'attempt', receipt)


def import_primary_body(probe_root: Path, receipt_name: str, out_root: Path, host: str) -> Path:
    payload, capture = load_probe_capture(probe_root, receipt_name, out_root, host)
    receipt = {'schema_version': ATTEMPT_SCHEMA, 'url': capture['source_uri'], 'attempted_at': capture['attempted_at'],
               'completed_at': capture['retrieved_at'], 'retrieved_at': capture['retrieved_at'], 'http_status': 200,
               'final_url': capture['source_uri'], 'outcome': 'success', 'source_sha256': capture['source_sha256'],
               'source_bytes': capture['source_bytes'], 'raw_relative_path': capture['raw_relative_path'],
               'http_client': capture['http_client'], 'user_agent': 'not_recorded_in_primary_receipt',
               'captured_by': 'primary_issuer_access_probe', 'primary_receipt_sha256': capture['receipt_sha256'],
               'redirects_followed': False, 'automatic_retry_performed': False}
    return write_addressed(out_root / 'attempts', 'attempt', receipt)


DATE_FORMATS = ('%b %d, %Y', '%B %d, %Y')


def parse_body(payload: bytes, row: dict) -> dict:
    """Extract one release and check it is the inventory row's page (URL, date, headline)."""
    root = Document(payload).root
    text = payload.decode('utf-8', errors='replace')
    canonical_links = re.findall(r'<link rel="canonical" href="([^"]+)"', text)
    og_urls = re.findall(r'<meta property="og:url" content="([^"]+)"', text)
    titles = {clean(n) for n in root.find(cls='field--name-field-nir-news-title')}
    dates = {clean(n) for n in root.find(cls='field--name-field-nir-news-date')}
    bodies = root.find(cls='node__content')
    problems = []
    if canonical_links != [row['url']] or og_urls != [row['url']]:
        problems.append('canonical/og:url differs from inventory URL')
    if titles != {row['title']}:
        problems.append(f'headline differs from inventory title: {sorted(titles)}')
    parsed_dates = set()
    for value in dates:
        for fmt in DATE_FORMATS:
            try:
                parsed_dates.add(datetime.strptime(value, fmt).date().isoformat())
                break
            except ValueError:
                continue
    if parsed_dates != {row['date']} or len(parsed_dates) != len(dates):
        problems.append(f'displayed date differs from inventory date: {sorted(dates)}')
    if len(bodies) != 1:
        problems.append(f'expected one node__content body, found {len(bodies)}')
    body_text = clean(bodies[0]) if bodies else ''
    if len(body_text) < 200:
        problems.append('release body text unexpectedly short')
    dateline = re.search(r'\(GLOBE NEWSWIRE\)|\(BUSINESS WIRE\)|\(PRNewswire\)', body_text)
    return {'identity_verified': not problems, 'problems': problems, 'headline': sorted(titles),
            'displayed_dates': sorted(dates), 'body_text_sha256': sha256(body_text.encode()),
            'body_characters': len(body_text), 'issuer_ticker_tag_present': '(Nasdaq: ABUS)' in body_text,
            'distribution_dateline': dateline.group(0) if dateline else None,
            'pdf_version_links': sorted(set(re.findall(r'href="(/node/\d+/pdf)"', text)))}


def collect(probe_root: Path, out_root: Path, host: str, years: list[int], body_start: str, body_end: str,
            primary_bodies: list[str], session=None, pause: float = 0.5) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    started = now()
    frozen = freeze_inventory(probe_root, years, out_root, host)
    for name in primary_bodies:
        import_primary_body(probe_root, name, out_root, host)
    selected = sorted((r for r in frozen['inventory'] if body_start <= r['date'] <= body_end), key=lambda r: (r['date'], r['url']))
    if session is None:
        import requests
        from requests.adapters import HTTPAdapter
        session = requests.Session()
        session.mount('https://', HTTPAdapter(max_retries=0))
    bodies = []
    for row in selected:
        attempts = prior_attempts(out_root).get(row['url'], [])
        success = next((a for a in attempts if verified_success(out_root, a)), None)
        if success is None and not attempts:
            fetch_once(session, row['url'], host, out_root)
            time.sleep(pause)
            attempts = prior_attempts(out_root).get(row['url'], [])
            success = next((a for a in attempts if verified_success(out_root, a)), None)
        entry = {**row, 'attempts': [{k: a.get(k) for k in ('receipt_relative_path', 'outcome', 'attempted_at', 'retrieved_at',
                                                             'failed_at', 'http_status', 'error', 'source_sha256', 'http_client')}
                                     for a in attempts]}
        if success:
            payload, _ = read_once(confined(out_root, success['raw_relative_path']), success['source_sha256'])
            entry.update(raw_relative_path=success['raw_relative_path'], source_sha256=success['source_sha256'],
                         retrieved_at=success['retrieved_at'], body=parse_body(payload, row))
            entry['status'] = 'captured_identity_verified' if entry['body']['identity_verified'] else 'captured_identity_mismatch'
        else:
            entry['status'] = 'failed_not_retried' if attempts else 'not_attempted'
        bodies.append(entry)
    counts = {'inventory': len(frozen['inventory']), 'selected': len(selected)}
    for entry in bodies:
        counts[entry['status']] = counts.get(entry['status'], 0) + 1
    collection = {
        'schema_version': SCHEMA, 'issuer': 'ABUS', 'issuer_cik': 1447028, 'collector_sha256': sha256(Path(__file__).read_bytes()),
        'base_parser_sha256': sha256((Path(__file__).resolve().parent / 'collect_issuer_archives.py').read_bytes()),
        'started_at': started, 'completed_at': now(), 'user_agent': USER_AGENT,
        'body_window': {'start_date': body_start, 'end_date': body_end}, **frozen, 'bodies': bodies, 'counts': counts,
        'archive_complete_claimed': False, 'original_version_verified': False,
        'completeness_basis': ('Current public year-selector pages, each with the requested year selected and no next link; '
                               'the publisher displays no count. A current listing cannot prove historical completeness, '
                               'unchanged bodies or the absence of removed releases.'),
        'outcome_label': None, 'label_admission_allowed': False}
    validate_archive(collection, out_root)
    return write_addressed(out_root, 'issuer-archive-collection', collection)


SUMMARY_FIELDS = ('outcome', 'attempted_at', 'retrieved_at', 'failed_at', 'http_status', 'error', 'source_sha256', 'http_client')


def validate_archive(collection: dict, out_root: Path, *, now=None) -> dict[str, str]:
    """Shared producer/consumer check of every represented archive clock, receipt and raw byte.

    Returns every represented source clock (archive page, year pages, recorded attempts). Invalid or
    future receipts are rejected; nothing is repaired or re-timed.
    """
    current = now or measured_now()
    require(collection.get('schema_version') == SCHEMA and collection.get('outcome_label') is None
            and collection.get('archive_complete_claimed') is False, 'unexpected issuer archive schema or flags')
    clocks: dict[str, str] = {}
    for label, capture in [('archive_page', collection['archive_page'])] + [
            (f"year_page_{p['archive_year']}", p) for p in collection['pages']]:
        chronology(label, capture['attempted_at'], {'retrieved_at': capture['retrieved_at']}, now=current)
        read_once(confined(out_root, capture['raw_relative_path']), capture['source_sha256'], capture['source_bytes'])
        clocks[f'{label}.attempted_at'], clocks[f'{label}.retrieved_at'] = capture['attempted_at'], capture['retrieved_at']
    for body in collection['bodies']:
        check_url(body['url'], collection['host'])
        success = None
        for summary in body['attempts']:
            receipt_path = confined(out_root, summary['receipt_relative_path'])
            payload, digest = read_once(receipt_path)
            require(receipt_path.stem.endswith(digest), f'{receipt_path.name}: not content-addressed')
            receipt = json.loads(payload)
            require(receipt.get('schema_version') == ATTEMPT_SCHEMA and receipt['url'] == body['url'], f'{receipt_path.name}: schema/url')
            require(all(summary.get(k) == receipt.get(k) for k in SUMMARY_FIELDS), f'{receipt_path.name}: summary differs from receipt')
            for name, value in attempt_clocks(receipt, receipt_path.name).items():
                clocks[f'{receipt_path.name}.{name}'] = value
            if receipt['outcome'] == 'success':
                read_once(confined(out_root, receipt['raw_relative_path']), receipt['source_sha256'], receipt['source_bytes'])
                success = success or receipt
        if body['status'].startswith('captured_'):
            require(success is not None and body['source_sha256'] == success['source_sha256']
                    and body['retrieved_at'] == success['retrieved_at'] and body['raw_relative_path'] == success['raw_relative_path'],
                    f"{body['url']}: captured body not bound to its success receipt")
            payload, _ = read_once(confined(out_root, body['raw_relative_path']), body['source_sha256'])
            verified = parse_body(payload, body)['identity_verified']
            require(verified == (body['status'] == 'captured_identity_verified'), f"{body['url']}: identity status differs on reparse")
        else:
            require(success is None and body['status'] in ('failed_not_retried', 'not_attempted'), f"{body['url']}: inconsistent status")
    chronology('collection', collection['started_at'], {'completed_at': collection['completed_at']}, now=current)
    completed = parse_clock(collection['completed_at'], 'collection.completed_at')
    for name, value in clocks.items():
        require(parse_clock(value, name) <= completed, f'collection completed before represented source clock {name}={value}')
    return clocks


def verify_archive_collection(path: Path, *, now=None) -> tuple[dict, dict[str, str], str]:
    """Consumer entry point: read the content-addressed collection once, then validate it fully."""
    payload, digest = read_once(path)
    require(path.stem.endswith(digest), 'issuer collection is not content-addressed')
    collection = json.loads(payload)
    return collection, validate_archive(collection, path.parent, now=now), digest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--years', type=int, nargs='+', default=[2020, 2021, 2022])
    parser.add_argument('--body-start', default='2020-01-01')
    parser.add_argument('--body-end', default='2022-03-31')
    parser.add_argument('--primary-body-receipt', action='append', default=[])
    args = parser.parse_args(argv)
    try:
        print(collect(args.probe_dir, args.output_dir, args.host, args.years, args.body_start, args.body_end,
                      args.primary_body_receipt))
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
