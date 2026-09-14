#!/usr/bin/env python3
"""Collect historical market bars for an existing reviewed company panel locally."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.alpaca_data import (AlpacaAccessError, collect_bars, digest, immutable_json,
                                     load_credentials, make_request, timestamp, verify_bars_manifest)
from src.research.training import validate_training_data


def plan_collection(panel: dict, feed: str = 'sip', lookback_days: int = 400) -> list[dict]:
    validate_training_data(panel)
    if type(lookback_days) is not int or not 120 <= lookback_days <= 730:
        raise ValueError('historical market lookback must be 120 to 730 calendar days')
    groups = {}
    for row in panel['observations']:
        cutoff = timestamp(row['information_cutoff_at']).isoformat()
        groups.setdefault(cutoff, set()).add(row['ticker'])
    return [dict(make_request(sorted(symbols), (timestamp(cutoff) - timedelta(days=lookback_days)).isoformat(),
                              cutoff, timestamp(cutoff).date().isoformat(), feed), information_cutoff_at=cutoff)
            for cutoff, symbols in sorted(groups.items())]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', type=Path, default=ROOT / 'data/history/panel_seed/panel.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/alpaca_market_data')
    parser.add_argument('--env-file', type=Path,
                        help='Explicit dotenv source; otherwise use process keys, ALPACA_CREDENTIALS_FILE, or ~/.config/alpaca_creds.env')
    parser.add_argument('--feed', choices=('sip', 'iex'), default='sip')
    parser.add_argument('--lookback-days', type=int, default=400)
    parser.add_argument('--plan', action='store_true', help='Show exact historical queries without loading credentials or connecting')
    parser.add_argument('--offline', action='store_true', help='Replay cached manifests only; never load credentials or connect')
    parser.add_argument('--refresh', action='store_true', help='Explicitly collect a new vendor snapshot; preserve old raw bytes')
    args = parser.parse_args(argv)
    if args.offline and args.refresh:
        parser.error('--offline and --refresh cannot be combined')
    try:
        raw_panel = args.panel.read_bytes()
        panel = json.loads(raw_panel)
        plan = plan_collection(panel, args.feed, args.lookback_days)
        if args.plan:
            print(json.dumps({'schema_version': 'alpaca-panel-market-plan-v1', 'base_panel_sha256': digest(raw_panel),
                              'company_observations': len(panel['observations']), 'requests': plan,
                              'network_requests_performed': False, 'model_training_performed': False}, indent=2))
            return 0
        credentials = None
        credential_error = None
        if not args.offline:
            try:
                credentials = load_credentials(args.env_file)
            except (AlpacaAccessError, ValueError, OSError) as exc:
                credential_error = str(exc)
        successful, gaps = [], []
        stopped = credential_error
        for request in plan:
            identity = {k: request[k] for k in ('information_cutoff_at', 'asof', 'symbols')}
            directory = args.output_dir / request['asof']
            if stopped:
                gaps.append(dict(identity, reason=stopped))
                continue
            try:
                if args.offline:
                    # Derive exactly the collector's query identity, without any network fallback.
                    query = {k: v for k, v in request.items() if k != 'information_cutoff_at'}
                    from src.research.alpaca_data import canonical, confined_bytes
                    cache = directory / f'query-{digest(canonical(query))}.json'
                    reference = json.loads(cache.read_bytes())
                    payload = confined_bytes(directory, reference['manifest_relative_path'])
                    if digest(payload) != reference['manifest_sha256']:
                        raise ValueError('cached Alpaca manifest hash mismatch')
                    path = directory / reference['manifest_relative_path']
                    if verify_bars_manifest(path)['request'] != query:
                        raise ValueError('cached Alpaca query identity mismatch')
                else:
                    path = collect_bars(request['symbols'], request['start'], request['end'], request['asof'],
                                        directory, feed=args.feed, credentials=credentials, refresh=args.refresh)
                successful.append(dict(identity, bars_manifest_relative_path=str(path.relative_to(args.output_dir)),
                                       bars_manifest_sha256=digest(path.read_bytes())))
            except (ValueError, OSError, KeyError, TypeError) as exc:
                reason = str(exc)
                gaps.append(dict(identity, reason=reason))
                if isinstance(exc, AlpacaAccessError):
                    # An authentication/entitlement/transport failure is not retried
                    # once per company window. No automatic alternate feed/key.
                    stopped = reason
        manifest = {'schema_version': 'alpaca-panel-market-collection-v1', 'base_panel_sha256': digest(raw_panel),
                    'collected_at': datetime.now(timezone.utc).isoformat(), 'feed': args.feed,
                    'collections': successful, 'gaps': gaps, 'company_observations': len(panel['observations']),
                    'status': 'complete_market_queries' if not gaps else 'market_queries_incomplete',
                    'model_training_performed': False, 'original_vendor_vintage_archived': False,
                    'collection_mode': 'offline_replay' if args.offline else 'authenticated_read_only',
                    'request_headers_recorded': False, 'broker_operations_performed': False}
        path = immutable_json(manifest, args.output_dir, 'alpaca-panel-market-collection')
        print(json.dumps({'status': manifest['status'], 'manifest': str(path), 'successful_windows': len(successful),
                          'failed_windows': len(gaps), 'model_training_performed': False}))
        return 2 if gaps else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'model_training_performed': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
