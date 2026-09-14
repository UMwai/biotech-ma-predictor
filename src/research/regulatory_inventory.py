"""Replay complete, explicitly scoped SEC full-text search inventories.

Search metadata discovers original filings; it never establishes negative labels.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode

ENDPOINT = 'https://efts.sec.gov/LATEST/search-index'
PAGE_SIZE = 100


def require(condition, message):
    if not condition:
        raise ValueError(message)


def query_url(cik: int, start: str, end: str, offset: int = 0) -> str:
    require(type(cik) is int and 0 < cik < 10**10, 'positive numeric SEC CIK required')
    require(date.fromisoformat(start) <= date.fromisoformat(end), 'invalid inventory date interval')
    require(type(offset) is int and offset >= 0, 'invalid inventory offset')
    # Unpadded CIKs silently return zero results from EFTS.
    return ENDPOINT + '?' + urlencode({'ciks': f'{cik:010d}', 'dateRange': 'custom',
                                      'startdt': start, 'enddt': end, 'from': offset, 'size': PAGE_SIZE})


def parse_page(payload: bytes, cik: int, start: str, end: str) -> tuple[int, list[dict]]:
    value = json.loads(payload)
    require(value.get('timed_out') is False, 'SEC inventory search timed out')
    shards = value['_shards']
    require(shards['failed'] == 0 and shards['successful'] == shards['total'], 'SEC inventory has incomplete shards')
    total, hits = value['hits']['total'], value['hits']['hits']
    require(total.get('relation') == 'eq' and type(total.get('value')) is int and total['value'] >= 0,
            'SEC inventory total is not exact')
    require(isinstance(hits, list) and len(hits) <= PAGE_SIZE, 'invalid SEC inventory page size')
    records = []
    for hit in hits:
        source = hit['_source']
        require(f'{cik:010d}' in source['ciks'], 'SEC inventory contains a different issuer')
        filed = date.fromisoformat(source['file_date'])
        require(date.fromisoformat(start) <= filed <= date.fromisoformat(end), 'SEC inventory filing outside requested dates')
        accession, filename = hit['_id'].split(':', 1)
        require(re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession) is not None and accession == source['adsh'],
                'SEC inventory accession mismatch')
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', filename) is not None,
                'unsafe SEC inventory document filename')
        require(isinstance(source['form'], str) and bool(source['form']), 'SEC inventory form absent')
        records.append({'id': hit['_id'], 'accession': accession, 'document_name': filename,
                        'form': source['form'], 'filed_date': filed.isoformat(), 'ciks': source['ciks'],
                        'display_names': source.get('display_names', []), 'items': source.get('items', []),
                        'candidate_document_uris': [f'https://www.sec.gov/Archives/edgar/data/{int(c)}/'
                                                    f'{accession.replace("-", "")}/{filename}' for c in source['ciks']],
                        'source_hit': hit})
    return total['value'], records


def verify_page_receipt(page: dict, directory: Path, cik: int, start: str, end: str,
                        offset: int, *, require_transport_identity: bool = False) -> tuple[int, list[dict], dict]:
    """Replay a page without upgrading missing transport evidence in old receipts."""
    requested_uri = query_url(cik, start, end, offset)
    require(type(page['offset']) is int and page['offset'] == offset, 'SEC inventory pagination gap or overlap')
    require(page['source_uri'] == requested_uri, 'SEC inventory query identity mismatch')
    transport_verified = 'effective_source_uri' in page
    if transport_verified:
        require(page['effective_source_uri'] == requested_uri, 'SEC inventory effective response query identity mismatch')
    require(not require_transport_identity or transport_verified,
            'cached SEC page transport identity is unverified; original receipt preserved, explicit source review required')
    relative = Path(page['source_relative_path'])
    resolved = (directory / relative).resolve()
    require(not relative.is_absolute() and resolved.is_relative_to(directory.resolve()),
            'SEC inventory path escapes evidence directory')
    raw = resolved.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == page['source_sha256'] and len(raw) == page['source_bytes'],
            'SEC inventory response hash or byte count mismatch')
    retrieved = datetime.fromisoformat(page['retrieved_at'])
    require(retrieved.tzinfo is not None and retrieved <= datetime.now(timezone.utc), 'SEC inventory retrieval clock invalid')
    total, rows = parse_page(raw, cik, start, end)
    # Date-only evidence has no captured timezone. Preserve the same conservative
    # UTC-14h / UTC+36h date bounds used by historical publication receipts.
    for row in rows:
        earliest_publication = datetime.fromisoformat(row['filed_date']).replace(tzinfo=timezone.utc) - timedelta(hours=14)
        require(retrieved >= earliest_publication, 'SEC inventory retrieval predates a returned filing date')
    interval_end = datetime.combine(date.fromisoformat(end), datetime.min.time(), timezone.utc) + timedelta(hours=36)
    return total, rows, dict(page, transport_identity_verified=transport_verified,
                             query_interval_closed=retrieved >= interval_end)


def verify_inventory(path: Path) -> dict:
    """Return derived verification status; never rewrite archived manifests or clocks.

    inventory_complete describes pagination only. Transport identity and whether
    the historical query interval had closed are separate, and none imply a label.
    """
    inventory = json.loads(path.read_bytes())
    require(inventory.get('schema_version') == 'sec-efts-inventory-v1', 'unsupported SEC inventory schema')
    cik, start, end = inventory['cik'], inventory['start_date'], inventory['end_date']
    pages = inventory['pages']
    require(isinstance(pages, list) and bool(pages), 'SEC inventory has no response pages')
    expected_total, records, verified_pages = None, [], []
    for page in pages:
        total, rows, verified_page = verify_page_receipt(page, path.parent, cik, start, end, len(records))
        expected_total = total if expected_total is None else expected_total
        require(total == expected_total == page['total'] and len(rows) == page['returned'], 'SEC inventory total changed between pages')
        require(len(rows) == min(PAGE_SIZE, max(0, total - len(records))), 'SEC inventory response is truncated')
        require(not records or bool(rows), 'SEC inventory has an extra empty page')
        records.extend(rows)
        verified_pages.append(verified_page)
    require(len(records) == expected_total and len({row['id'] for row in records}) == len(records),
            'SEC inventory is incomplete or has duplicate documents')
    require(records == inventory['records'] and expected_total == inventory['total'], 'SEC inventory normalized records disagree with responses')
    require(inventory.get('inventory_complete') is True and inventory.get('outcome_label') is None,
            'SEC search inventory cannot assert an acquisition outcome')
    return dict(inventory, pages=verified_pages,
                transport_identity_verified=all(page['transport_identity_verified'] for page in verified_pages),
                query_interval_closed=all(page['query_interval_closed'] for page in verified_pages))
