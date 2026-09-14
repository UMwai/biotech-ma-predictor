#!/usr/bin/env python3
"""Collect exact paginated SEC search metadata, without assigning outcome labels."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.regulatory_inventory import PAGE_SIZE, query_url, require, verify_inventory, verify_page_receipt

USER_AGENT = 'biotech-ma-predictor public historical acquisition research'


def collect(cik: int, ticker: str, start: str, end: str, directory: Path) -> Path:
    query_url(cik, start, end)  # Validate the requested identity even when reusing a manifest.
    require(isinstance(ticker, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', ticker) is not None,
            'safe SEC inventory ticker required')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'raw_sources').mkdir(exist_ok=True)
    manifest_path = directory / f'{ticker}_{start}_{end}.json'
    if manifest_path.exists():
        inventory = verify_inventory(manifest_path)
        require((inventory['cik'], inventory.get('ticker'), inventory['start_date'], inventory['end_date'])
                == (cik, ticker, start, end), 'existing SEC inventory requested identity mismatch')
        # A legacy manifest remains replayable, with transport status explicitly
        # false in verify_inventory's result. It is not rewritten as a new capture.
        return manifest_path
    records, pages, total = [], [], None
    while total is None or len(records) < total:
        offset = len(records)
        url = query_url(cik, start, end, offset)
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        receipt_path = directory / f'page-{cache_key}.json'
        failure_path = directory / f'failure-{cache_key}.json'
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
        elif failure_path.exists():
            raise ValueError('prior request failed; explicit source review required before retry')
        else:
            time.sleep(1.0)
            effective_uri = None
            try:
                with urlopen(Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'}), timeout=30) as response:
                    effective_uri = response.geturl()
                    require(effective_uri == url, 'SEC inventory effective response query identity mismatch')
                    raw = response.read(5_000_001)
                    if len(raw) > 5_000_000:
                        raise ValueError('SEC page exceeds bounded response size')
                digest = hashlib.sha256(raw).hexdigest()
                relative = f'raw_sources/{digest}.json'
                (directory / relative).write_bytes(raw)
                receipt = {'source_uri': url, 'effective_source_uri': effective_uri,
                           'source_relative_path': relative, 'source_sha256': digest,
                           'source_bytes': len(raw), 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'offset': offset}
                receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            except Exception as exc:
                failure_path.write_text(json.dumps({'source_uri': url, 'effective_source_uri': effective_uri,
                                                   'attempted_at': datetime.now(timezone.utc).isoformat(),
                                                   'error': str(exc), 'status_code': getattr(exc, 'code', None),
                                                   'outcome_label': None, 'automatic_retry_allowed': False}, indent=2) + '\n')
                raise
        actual_total, rows, receipt = verify_page_receipt(receipt, directory, cik, start, end, offset,
                                                        require_transport_identity=True)
        if total is not None and actual_total != total:
            raise ValueError('SEC inventory changed while paging')
        total = actual_total
        if len(rows) != min(PAGE_SIZE, total - offset):
            raise ValueError('SEC inventory returned a truncated page')
        if total > 10000:
            raise ValueError('SEC result limit exceeded; explicitly partition date interval')
        pages.append(dict(receipt, total=total, returned=len(rows)))
        records.extend(rows)
    value = {'schema_version': 'sec-efts-inventory-v1', 'cik': cik, 'ticker': ticker,
             'start_date': start, 'end_date': end, 'total': total, 'pages': pages, 'records': records,
             'inventory_complete': True, 'outcome_label': None,
             'transport_identity_verified': all(page['transport_identity_verified'] for page in pages),
             'query_interval_closed': all(page['query_interval_closed'] for page in pages),
             'scope': 'Every result in the exact unfiltered padded-CIK and filing-date EFTS query; no search-term exclusion.',
             'limitations': ['Search metadata is not a full-text outcome review or proof of historical listing.',
                             'Current SEC indexes may reflect post-acceptance corrections or removals.',
                             'Candidate document URIs require original-document subject identity verification; associated CIKs are not automatically filers.']}
    temporary = manifest_path.with_suffix('.incomplete')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    verify_inventory(temporary)
    temporary.replace(manifest_path)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cik', type=int, required=True)
    parser.add_argument('--ticker', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/history/panel_seed/regulatory_inventory')
    args = parser.parse_args()
    try:
        date.fromisoformat(args.start); date.fromisoformat(args.end)
        path = collect(args.cik, args.ticker, args.start, args.end, args.output_dir)
        inventory = verify_inventory(path)
        print(json.dumps({'path': str(path), 'inventory_complete': inventory['inventory_complete'],
                          'transport_identity_verified': inventory['transport_identity_verified'],
                          'query_interval_closed': inventory['query_interval_closed'], 'outcome_label': None}))
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc), 'outcome_label': None}), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
