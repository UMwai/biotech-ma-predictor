#!/usr/bin/env python3
"""Freeze the historical M&A frame inputs and build the 300-row evidence ledger.

``snapshot`` copies exact input bytes from a read-only original checkout and the
valuation probe into content-addressed files and asserts every expected hash.
``build`` reads only that snapshot plus the registered collection protocol.

The ledger enumerates availability and dispositions. It never assigns a label:
missing positive evidence, missing candidates and keyword absence are not
negatives. Vendor quote presence is not original-vintage valuation evidence.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ma_evidence_io import confined, read_once  # noqa: E402

LEDGER_SCHEMA = 'ma-evidence-frame-ledger-v1'
SNAPSHOT_SCHEMA = 'ma-evidence-input-snapshot-v1'
AVAILABILITY_SCHEMA = 'ma-evidence-source-availability-v1'
PROTOCOL_SHA256 = '8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0'

# Exact original bytes required by the reconciled plan (2026-10-02).
ORIGINAL_INPUTS = {
    'sampling_frame': ('data/history/panel_seed/sampling_frame.json',
                       'e69a4a6babeddc0e2334551a0125b2d60b0d2223652b5e60f40d9bdb95185a76'),
    'panel': ('data/history/panel_seed/panel.json',
              '147059f3a23c43c23a54df3151d3cb87e5d0fed85c9c30202ed03dc8ffdd7954'),
    'assembly': ('data/history/panel_seed/assembly.json',
                 '9d04186c997347065fbf9f2419ed147aa51d6b3f61eed2d84324260eec8ec28d'),
    'status': ('data/history/panel_seed/status.json',
               '176be801ac691d64bdba3a4254b36ec634ef109f56f182e782523196a9ed6319'),
    'observation_adjudications': ('data/history/panel_seed/observation_adjudications.json',
                                  '5da40c2e1cae5a9b5646869f853dff2a8ba0726d07fcfbd6c7b1f9655e726c3e'),
    'observation_exclusions': ('data/history/panel_seed/observation_exclusions.json',
                               '8bc3fa72168215b7561a64757773d5d08aa854434759b8e048264a62c1c3548d'),
    'frame_source_receipt': ('data/history/panel_seed/nasdaq_source_receipt.json',
                             'cb464fda9e112acc22f8fd6902c2dc5a5314d542ff6b5ee2328fc07dde63d498'),
    'frame_source_html': ('data/history/panel_seed/raw/923baca63fe933a5443db8c153837df4f85178d9ff931bc8d01a8d1a240a4955.html',
                          '923baca63fe933a5443db8c153837df4f85178d9ff931bc8d01a8d1a240a4955'),
    'listing_reviews': ('data/history/panel_seed/listing_reviews.json',
                        '70ea7ef7491578ef11ecf4a147ecc37b9ae2d0e1fcdff17205f73eb6cfa4ce9d'),
    'frozen_labels': ('data/history/frozen_labels.json',
                      '8e28d32782f9d8079d9e2c1e2c9594d794c4e57f9e280cc485d077c9466d6bd2'),
    'financial_records.json': ('data/history/panel_financials/financial_records.json',
                               '0377939ec2410c46cc5ff3e60d01a51e04edb582edd35870e9c97cada5f38a73'),
    'positive_financial_records.json': ('data/history/panel_financials/positive_financial_records.json',
                                        '104231af59aef70f16d4cf5b6a4ca226ed9ead71a6cc0e09bdee9b398ca371ea'),
    'deal_candidates': ('output/historical_deal_candidates/candidates.csv',
                        '8637f8ba3613970d630e6839d75c48a308be54ca9d745f5f447e589d19fd6c7a'),
}
VALUATION_PROBE = ('valuation-source-probe-7c892cff4ec0c67a957bb1287e7b2518ab220984c2bb04e03e0800c190969774.json',
                   '7c892cff4ec0c67a957bb1287e7b2518ab220984c2bb04e03e0800c190969774')
# Assembly input_sha256 keys bound to snapshot logical names.
# Licensed vendor quote payloads stay local (not redistributed); replay needs them.
LOCAL_ONLY_INPUTS = ({f'valuation_manifest_{year}' for year in (2021, 2023, 2024)}
                     | {f'valuation_raw_{year}_0' for year in (2021, 2023, 2024)})
# Expected schema of each parsed original artifact.
INPUT_SCHEMAS = {'sampling_frame': 'historical-sampling-frame-v1', 'panel': 'historical-company-features-v1',
                 'assembly': 'historical-panel-assembly-v1', 'status': 'historical-panel-assembly-v1',
                 'observation_adjudications': 'reviewed-company-observation-adjudications-v1',
                 'observation_exclusions': 'historical-observation-exclusions-v1',
                 'listing_reviews': 'reviewed-historical-membership-v1', 'frozen_labels': 'reviewed-deals-v2',
                 'financial_records.json': 'reviewed-panel-annual-financials-v1',
                 'positive_financial_records.json': 'reviewed-panel-annual-financials-v1',
                 'valuation_probe': 'ma-valuation-source-probe-v1'}
ASSEMBLY_INPUT_KEYS = {'sampling_frame': 'sampling_frame', 'frame_source_receipt': 'frame_source_receipt',
                       'frozen_labels': 'frozen_labels', 'observation_adjudications': 'observation_adjudications',
                       'observation_exclusions': 'observation_exclusions',
                       'financial_records.json': 'financial_records.json',
                       'positive_financial_records.json': 'positive_financial_records.json'}
NAME_SUFFIXES = {'inc', 'incorporated', 'corp', 'corporation', 'co', 'company', 'ltd', 'limited', 'plc',
                 'sa', 'nv', 'ag', 'se', 'holdings', 'holding', 'the', 'llc', 'lp', 'group'}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_addressed(directory: Path, prefix: str, obj) -> Path:
    payload = canonical(obj)
    path = directory / f'{prefix}-{sha256(payload)}.json'
    if path.exists():
        require(path.read_bytes() == payload, f'existing content-addressed file differs: {path}')
    else:
        path.write_bytes(payload)
    return path


def norm_name(name: str) -> str:
    words = re.sub(r'[^a-z0-9 ]', ' ', name.lower().replace('&', ' and ')).split()
    while words and words[-1] in NAME_SUFFIXES:
        words.pop()
    return ' '.join(words)


def _scanned(path: Path, root: Path) -> tuple[dict, bytes]:
    """Read one globbed artifact once (confined to root) and describe those exact bytes."""
    resolved = confined(root, path.relative_to(root))
    payload, digest = read_once(resolved)
    return {'path': str(path.relative_to(root)), 'sha256': digest, 'bytes': len(payload)}, payload


def scan_source_availability(original: Path, tickers: list[str]) -> dict:
    """Record which existing source artifacts exist per ticker; no completion is inferred."""
    out = {}
    for ticker in tickers:
        entry = {'sec_submission_collections': [], 'sec_review_queues': [], 'issuer_outcome_review_pointers': [],
                 'issuer_archive_collections': [], 'regulatory_inventories': []}
        for path in sorted(original.glob(f'data/history/web_source_research/*/{ticker}-submissions/sec-submission-collection.json')):
            item, payload = _scanned(path, original)
            value = json.loads(payload)
            dates = [inv.get('source_relative_path', '') for inv in value.get('source_inventories', [])]
            item.update(schema_version=value.get('schema_version'), cik=value.get('cik'),
                        collection_complete=value.get('collection_complete'),
                        full_text_outcome_review_complete=value.get('full_text_outcome_review_complete'),
                        accessions=len(value.get('accessions', [])), inventory_paths=dates)
            entry['sec_submission_collections'].append(item)
        for path in sorted(original.glob(f'output/sec_corpus/*/{ticker}-*/sec-outcome-review-queue-*.json')):
            item, payload = _scanned(path, original)
            value = json.loads(payload)
            item.update(schema_version=value.get('schema_version'), cik=value.get('cik'), status=value.get('status'),
                        document_count=value.get('document_count'), trigger_context_count=value.get('trigger_context_count'),
                        outcome_review_complete=value.get('outcome_review_complete'),
                        label_admission_allowed=value.get('label_admission_allowed'))
            entry['sec_review_queues'].append(item)
        for path in sorted(original.glob(f'data/history/panel_seed/{ticker}/outcome_review_*.json')):
            if len(path.stem.split('_')[-1]) == 4:
                entry['issuer_outcome_review_pointers'].append(_scanned(path, original)[0])
        for path in sorted(original.glob(f'data/history/panel_seed/{ticker}/collection*.json')):
            entry['issuer_archive_collections'].append(_scanned(path, original)[0])
        for path in sorted(original.glob(f'data/history/panel_seed/regulatory_inventory/{ticker}/*.json')):
            entry['regulatory_inventories'].append(_scanned(path, original)[0])
        out[ticker] = entry
    return out


def snapshot(original: Path, valuation_root: Path, protocol_path: Path, output_dir: Path) -> Path:
    protocol_bytes = protocol_path.read_bytes()
    require(sha256(protocol_bytes) == PROTOCOL_SHA256, 'collection protocol hash mismatch')
    protocol = json.loads(protocol_bytes)
    require(protocol.get('schema_version') == 'ma-evidence-collection-protocol-v1', 'unsupported protocol schema')
    inputs_dir = output_dir / 'inputs'
    inputs_dir.mkdir(parents=True, exist_ok=True)
    entries, payloads = {}, {}

    def capture(name: str, source: Path, expected: str | None, origin: str) -> bytes:
        payload, digest = read_once(source)
        require(expected is None or digest == expected, f'{name}: expected {expected}, found {digest}')
        target = inputs_dir / f'{digest}{source.suffix}'
        if target.exists():
            require(target.read_bytes() == payload, f'{name}: existing snapshot bytes differ')
        else:
            target.write_bytes(payload)
        entries[name] = {'origin': origin, 'source_path': str(source), 'sha256': digest, 'bytes': len(payload),
                         'expected_sha256': expected, 'snapshot_relative_path': f'inputs/{target.name}'}
        payloads[name] = payload
        return payload

    for name, (relative, expected) in ORIGINAL_INPUTS.items():
        capture(name, confined(original, relative), expected, 'original_checkout_read_only')
    probe = json.loads(capture('valuation_probe', confined(valuation_root, VALUATION_PROBE[0]), VALUATION_PROBE[1],
                               'primary_owned_valuation_probe_read_only'))
    require(probe['frame_sha256'] == protocol['sampling_frame_sha256'], 'valuation probe frame mismatch')
    for result in probe['results']:
        year = result['observation_year']
        manifest_path = confined(valuation_root, result['manifest_path'])
        manifest = json.loads(capture(f'valuation_manifest_{year}', manifest_path, result['manifest_sha256'],
                                      'primary_owned_valuation_probe_read_only'))
        for index, page in enumerate(manifest['pages']):
            capture(f'valuation_raw_{year}_{index}',
                    confined(valuation_root, manifest_path.parent.relative_to(valuation_root.resolve()) / page['source_relative_path']),
                    page['source_sha256'], 'primary_owned_valuation_probe_read_only')

    # Cross-bindings recorded inside the original artifacts.
    verify_authority(entries, {name: json.loads(payloads[name]) for name in set(INPUT_SCHEMAS) | {'frame_source_receipt'}},
                     protocol)

    availability = {'schema_version': AVAILABILITY_SCHEMA, 'original_root': str(original),
                    'scanned_at': datetime.now(timezone.utc).isoformat(),
                    'semantics': 'Existence and hashes of existing artifacts only; presence never implies review completion, admission or a label.',
                    'tickers': scan_source_availability(original, protocol['collection_order'])}
    availability_path = write_addressed(output_dir, 'source-availability', availability)
    manifest = {'schema_version': SNAPSHOT_SCHEMA, 'captured_at': datetime.now(timezone.utc).isoformat(),
                'original_root': str(original), 'original_root_policy': 'read_only_dirty_concurrent_source_basis',
                'valuation_root': str(valuation_root), 'protocol_sha256': PROTOCOL_SHA256,
                'builder_sha256': sha256(Path(__file__).read_bytes()),
                'cross_bindings_verified': ['assembly.input_sha256', 'status.coverage_report_sha256',
                                            'status.panel_sha256', 'protocol.sampling_frame_sha256',
                                            'valuation_probe.frame_sha256', 'valuation manifests and raw pages'],
                'inputs': entries,
                'source_availability': {'relative_path': availability_path.name,
                                        'sha256': sha256(availability_path.read_bytes())}}
    return write_addressed(output_dir, 'input-snapshot', manifest)


def verify_authority(entries: dict, parsed: dict, protocol: dict) -> None:
    """Check authoritative hashes, schemas and recorded cross-bindings of the original inputs."""
    for name, (_, expected) in ORIGINAL_INPUTS.items():
        require(entries[name]['expected_sha256'] == expected == entries[name]['sha256'], f'{name}: not the authoritative original bytes')
    require(entries['valuation_probe']['expected_sha256'] == VALUATION_PROBE[1] == entries['valuation_probe']['sha256'],
            'valuation probe is not the authoritative probe')
    for name, schema in INPUT_SCHEMAS.items():
        require(parsed[name].get('schema_version') == schema, f'{name}: unexpected schema {parsed[name].get("schema_version")}')
    assembly, status, frame, probe = parsed['assembly'], parsed['status'], parsed['sampling_frame'], parsed['valuation_probe']
    for key, name in ASSEMBLY_INPUT_KEYS.items():
        require(assembly['input_sha256'][key] == entries[name]['sha256'], f'assembly input binding mismatch: {key}')
    require(status['coverage_report_sha256'] == entries['assembly']['sha256'], 'status coverage hash mismatch')
    require(status['panel_sha256'] == entries['panel']['sha256'], 'status panel hash mismatch')
    require(entries['sampling_frame']['sha256'] == protocol['sampling_frame_sha256'] == probe['frame_sha256'], 'frame hash binding mismatch')
    receipt = parsed['frame_source_receipt']
    require(receipt['source_sha256'] == entries['frame_source_html']['sha256'] == frame['historical_sampling_frame']['source_sha256']
            and receipt['bytes'] == entries['frame_source_html']['bytes'], 'frame source receipt/html/frame binding mismatch')
    years = sorted(r['observation_year'] for r in probe['results'])
    require(years == [2021, 2023, 2024], 'valuation probe years differ from protocol dates')
    for result in probe['results']:
        name = f"valuation_manifest_{result['observation_year']}"
        require(result['manifest_sha256'] == entries[name]['expected_sha256'] == entries[name]['sha256'], f'{name}: probe binding mismatch')


def verify_snapshot(manifest: dict, root: Path, protocol: dict) -> tuple[dict, dict]:
    """Validate every declared byte copy once; return payloads and the parsed availability index."""
    require(manifest.get('schema_version') == SNAPSHOT_SCHEMA and manifest.get('protocol_sha256') == PROTOCOL_SHA256,
            'unsupported snapshot schema or protocol binding')
    expected_names = set(ORIGINAL_INPUTS) | {'valuation_probe'} | LOCAL_ONLY_INPUTS
    require(set(manifest['inputs']) == expected_names, 'snapshot declares unexpected or missing inputs')
    payloads, missing_local = {}, []
    for name, entry in sorted(manifest['inputs'].items()):
        relative = entry['snapshot_relative_path']
        require(Path(relative).name.split('.')[0] == entry['sha256'], f'{name}: snapshot file is not content-addressed')
        try:
            path = confined(root, relative)
        except FileNotFoundError:
            if name in LOCAL_ONLY_INPUTS:
                missing_local.append(f'{name} ({relative})')
                continue
            raise
        payloads[name], _ = read_once(path, entry['sha256'], entry['bytes'])
    require(not missing_local, 'local-only licensed vendor inputs are not distributed and are missing here: '
            + ', '.join(missing_local) + '; full ledger replay requires the locally retained files')
    parsed = {name: json.loads(payloads[name]) for name in set(INPUT_SCHEMAS) | {'frame_source_receipt'}}
    verify_authority(manifest['inputs'], parsed, protocol)
    for year in (2021, 2023, 2024):
        vendor = json.loads(payloads[f'valuation_manifest_{year}'])
        raw = json.loads(payloads[f'valuation_raw_{year}_0'])
        require(vendor.get('schema_version') == 'alpaca-stock-bars-v1' and len(vendor['pages']) == 1, f'{year}: vendor manifest schema/pages')
        page = vendor['pages'][0]
        require(page['source_sha256'] == manifest['inputs'][f'valuation_raw_{year}_0']['sha256'] == manifest['inputs'][f'valuation_raw_{year}_0']['expected_sha256']
                and page['source_bytes'] == len(payloads[f'valuation_raw_{year}_0']), f'{year}: raw vendor page binding mismatch')
        require(raw.get('next_page_token') is None and raw['bars'] == {k: v for k, v in vendor['bars_by_symbol'].items() if v},
                f'{year}: parsed vendor bars differ from raw vendor page')
    reference = manifest['source_availability']
    availability_path = confined(root, reference['relative_path'])
    availability_bytes, digest = read_once(availability_path, reference['sha256'])
    require(availability_path.stem.endswith(digest), 'availability index is not content-addressed')
    availability = json.loads(availability_bytes)
    require(availability.get('schema_version') == AVAILABILITY_SCHEMA
            and set(availability['tickers']) == set(protocol['collection_order']), 'availability index schema or tickers mismatch')
    return payloads, availability


def _bars(manifest: dict, ticker: str, observation: str) -> dict:
    bars = manifest['bars_by_symbol'].get(ticker) or []
    dates = sorted(bar['t'][:10] for bar in bars)
    require(all(day < observation for day in dates), f'{ticker}: vendor bar on/after observation date')
    return {'vendor_bars_present': bool(bars), 'vendor_bar_count': len(bars),
            'vendor_first_bar_date': dates[0] if dates else None, 'vendor_last_bar_date': dates[-1] if dates else None}


def build_rows(protocol: dict, frame: dict, assembly: dict, panel: dict, frozen: dict, candidates: list[dict],
               financial_records: list[dict], availability: dict, valuation: dict, valuation_hashes: dict,
               exclusion_refs: dict) -> list[dict]:
    """Join snapshot artifacts into one ordered row per frame member and planned date."""
    dates = protocol['planned_observation_dates']
    horizon_days = frame['cohort_plan']['horizon_days']
    require(frame['cohort_plan']['observation_dates'] == dates and horizon_days == 365, 'frame plan differs from protocol')
    members = {m['historical_ticker']: m for m in frame['records']}
    require(list(protocol['collection_order']) == [m['historical_ticker'] for m in frame['records']],
            'protocol order differs from frame table order')
    coverage = {}
    for row in assembly['coverage']:
        key = (row['ticker'], row['observation_at'][:10])
        require(key not in coverage, f'duplicate coverage row {key}')
        coverage[key] = row
    expected_keys = {(t, d) for t in protocol['collection_order'] for d in dates}
    require(set(coverage) == expected_keys, 'assembly coverage keys differ from protocol frame x dates')
    admitted = {}
    for obs in panel['observations']:
        key = (obs['cik'], obs['observation_at'][:10])
        require(key not in admitted, f'duplicate admitted observation {key}')
        admitted[key] = obs
    financial_by_id = {r['record_id']: r for r in financial_records}
    labels = frozen['labels']
    rows = []
    for ticker in protocol['collection_order']:
        member = members[ticker]
        for day in dates:
            cov = coverage[(ticker, day)]
            cik = cov['cik']
            horizon_end = (date.fromisoformat(day) + timedelta(days=horizon_days)).isoformat()
            require(cov['horizon_end_at'][:10] == horizon_end, f'{ticker} {day}: horizon mismatch')
            if cik is not None:
                event_matches = [(e, 'reviewed_financial_cik') for e in labels if e['target_cik'] == cik]
                cand_matches = [(c, 'target_cik') for c in candidates if c['target_cik'] and int(c['target_cik']) == cik]
            else:
                event_matches = [(e, 'ticker_only_identity_unverified') for e in labels if e['target_ticker'] == ticker]
                name = norm_name(member['historical_issuer_name'])
                cand_matches = [(c, 'filer_name_only_identity_unverified') for c in candidates
                                if norm_name(c['filer_name']) == name]
            in_events = [{'event_id': e['event_id'], 'announcement_date': e['announcement_date'], 'match_basis': b,
                          'acquirer_name': e['acquirer_name'], 'label': e['label']}
                         for e, b in event_matches if day < e['announcement_date'] < horizon_end]
            prior_events = [{'event_id': e['event_id'], 'announcement_date': e['announcement_date'], 'match_basis': b}
                            for e, b in event_matches if e['announcement_date'] <= day]
            in_cands = [{'candidate_id': c['candidate_id'], 'sec_signal_date': c['sec_signal_date'],
                         'event_class': c['event_class'], 'adjudication_status': c['adjudication_status'],
                         'target_cik': int(c['target_cik']) if c['target_cik'] else None, 'match_basis': b}
                        for c, b in cand_matches if day < c['sec_signal_date'] <= horizon_end]
            prior_cands = [{'candidate_id': c['candidate_id'], 'sec_signal_date': c['sec_signal_date'], 'match_basis': b}
                           for c, b in cand_matches if c['sec_signal_date'] <= day]
            obs = admitted.get((cik, day)) if cik is not None else None
            require(bool(obs) == bool(cov['training_eligible']), f'{ticker} {day}: panel/coverage admission disagree')
            label = obs['label'] if obs else None
            financial = financial_by_id.get(cov['financial_record_id']) if cov['financial_record_id'] else None
            require(cov['financial_record_id'] is None or financial is not None, f'{ticker} {day}: unknown financial record')
            if financial:
                require(financial['cik'] == cik, f'{ticker} {day}: financial identity mismatch')
            censoring = cov['censoring_evidence']
            gaps = list(cov['remaining_gaps'])
            if obs:
                status = 'admitted_positive' if cov['outcome_label'] == 1 else 'admitted_negative'
                require(cov['outcome_label'] in (0, 1), f'{ticker} {day}: admitted row lacks a binary label')
            elif cov['observation_disposition'] == 'censored_no_binary_label':
                status = 'censored_no_binary_label'
            elif 'prior_control_announcement_requires_historical_disposition_review' in gaps:
                status = 'prior_control_announcement_post_event_disposition_unreviewed'
            elif cov['reviewed_positive_event_ids']:
                status = 'reviewed_control_event_in_horizon_not_admitted'
            elif in_events:
                status = 'reviewed_event_ticker_match_identity_unverified'
            elif prior_events:
                status = 'prior_control_event_ticker_match_identity_unverified'
            elif in_cands:
                status = 'sec_candidate_signal_in_horizon_unadjudicated'
            else:
                status = 'outcome_unknown_unreviewed'
            avail = availability['tickers'][ticker]
            year = day[:4]
            bars = _bars(valuation[year], ticker, day)
            rows.append({
                'row_index': len(rows) + 1, 'ticker': ticker, 'historical_issuer_name': member['historical_issuer_name'],
                'frame_identity_status': member['identity_status'], 'observation_date': day,
                'horizon_end_date': horizon_end, 'cik': cik,
                'identity_basis': 'reviewed_original_financial_record_cik' if cik is not None else None,
                'identity_unresolved': cik is None,
                'ledger_status': status, 'training_eligible': bool(cov['training_eligible']),
                'admitted_outcome_label': cov['outcome_label'],
                'admitted_event_class': label['event_class'] if label else None,
                'admitted_review_id': label.get('review_id') if label else None,
                'admitted_label_source_sha256': label.get('source_sha256') if label else None,
                'admitted_announcement_date': label.get('announcement_date') if label else None,
                'label_available_at': cov.get('label_available_at'),
                'label_training_available_at': cov.get('label_training_available_at'),
                'label_timing_basis': cov.get('label_timing_basis'),
                'observation_disposition': cov['observation_disposition'],
                'censoring_review': exclusion_refs.get((ticker, day)) if censoring else None,
                'reviewed_positive_event_ids': cov['reviewed_positive_event_ids'],
                'frozen_events_in_horizon': in_events, 'frozen_events_prior': prior_events,
                'candidate_signals_in_horizon': in_cands, 'candidate_signals_prior': prior_cands,
                'reviewed_negative_corpus_sha256': cov['reviewed_negative_corpus_sha256'],
                'financial_record_id': cov['financial_record_id'], 'financial_period_end': cov['financial_period_end'],
                'financial_feature_max_available_at': cov['feature_max_available_at'],
                'financial_filing_form': financial.get('filing_form') if financial else None,
                'financial_source_sha256': financial.get('source_sha256') if financial else None,
                'financial_raw_bytes_archived': financial.get('raw_bytes_archived') if financial else None,
                'sec_submission_collections': [{k: c[k] for k in ('path', 'sha256', 'cik', 'collection_complete', 'accessions')}
                                               for c in avail['sec_submission_collections']],
                'sec_review_queues': [{k: q[k] for k in ('path', 'sha256', 'status', 'document_count',
                                                         'trigger_context_count', 'outcome_review_complete')}
                                      for q in avail['sec_review_queues']],
                'issuer_outcome_review_pointer': next((p for p in avail['issuer_outcome_review_pointers']
                                                       if p['path'].endswith(f'outcome_review_{year}.json')), None),
                'issuer_archive_collection_count': len(avail['issuer_archive_collections']),
                'regulatory_inventory_count': len(avail['regulatory_inventories']),
                **bars, 'vendor_manifest_sha256': valuation_hashes[year],
                'original_vendor_vintage_archived': False, 'valuation_rating_supported': False,
                'negative_label_assigned_by_ledger': False,
                'remaining_gaps': gaps})
    require(len(rows) == len(expected_keys), 'ledger rows differ from frame x dates')
    return rows


def summarize(rows: list[dict], assembly: dict) -> dict:
    def count(field):
        out = {}
        for row in rows:
            out[str(row[field])] = out.get(str(row[field]), 0) + 1
        return dict(sorted(out.items()))
    gap_counts = {}
    for row in rows:
        for gap in row['remaining_gaps']:
            gap_counts[gap] = gap_counts.get(gap, 0) + 1
    require(gap_counts == assembly['gap_counts'], 'ledger gaps differ from assembly gap counts')
    support = assembly['pre_test_training_support']
    return {
        'rows': len(rows), 'companies': len({r['ticker'] for r in rows}),
        'ledger_status': count('ledger_status'),
        'structurally_admitted_observations': sum(r['training_eligible'] for r in rows),
        'admitted_positive': sum(r['admitted_outcome_label'] == 1 for r in rows),
        'admitted_negative': sum(r['admitted_outcome_label'] == 0 for r in rows),
        'pre_2023_training_support_from_assembly': {k: support[k] for k in (
            'structurally_admitted_prior_observations', 'company_observations', 'distinct_positive_events',
            'distinct_negative_companies', 'minimum_distinct_negative_companies', 'remaining_negative_companies',
            'purged_label_unavailable', 'meets_training_support_floors')},
        'identity_unresolved_rows': sum(r['identity_unresolved'] for r in rows),
        'identity_unresolved_companies': len({r['ticker'] for r in rows if r['identity_unresolved']}),
        'financially_joinable_rows': sum(r['financial_record_id'] is not None for r in rows),
        'financial_rows_with_null_raw_source_hash': sum(r['financial_record_id'] is not None and not r['financial_source_sha256'] for r in rows),
        'rows_with_reviewed_positive_event_by_cik': sum(bool(r['reviewed_positive_event_ids']) for r in rows),
        'rows_with_frozen_event_in_horizon_any_basis': sum(bool(r['frozen_events_in_horizon']) for r in rows),
        'rows_with_ticker_only_frozen_event': sum(any(e['match_basis'].startswith('ticker_only') for e in r['frozen_events_in_horizon']) for r in rows),
        'rows_with_candidate_signal_in_horizon': sum(bool(r['candidate_signals_in_horizon']) for r in rows),
        'rows_with_name_only_candidate_signal': sum(any(c['match_basis'].startswith('filer_name_only') for c in r['candidate_signals_in_horizon']) for r in rows),
        'rows_with_prior_control_event': sum(bool(r['frozen_events_prior']) for r in rows),
        'censored_rows': sum(r['observation_disposition'] == 'censored_no_binary_label' for r in rows),
        'rows_with_verified_negative_corpus_review': sum(r['reviewed_negative_corpus_sha256'] is not None for r in rows),
        'companies_with_sec_submission_collection': len({r['ticker'] for r in rows if r['sec_submission_collections']}),
        'companies_with_sec_review_queue': len({r['ticker'] for r in rows if r['sec_review_queues']}),
        'rows_with_vendor_bars': sum(r['vendor_bars_present'] for r in rows),
        'rows_without_vendor_bars': sum(not r['vendor_bars_present'] for r in rows),
        'valuation_rating_supported_rows': 0, 'negative_labels_assigned_by_ledger': 0,
        'gap_counts': dict(sorted(gap_counts.items()))}


CSV_FIELDS = ['row_index', 'ticker', 'historical_issuer_name', 'observation_date', 'horizon_end_date', 'cik',
              'identity_unresolved', 'ledger_status', 'training_eligible', 'admitted_outcome_label',
              'admitted_event_class', 'admitted_review_id', 'admitted_announcement_date', 'label_training_available_at',
              'observation_disposition', 'reviewed_positive_event_ids', 'frozen_events_in_horizon',
              'frozen_events_prior', 'candidate_signals_in_horizon', 'reviewed_negative_corpus_sha256',
              'financial_record_id', 'financial_period_end', 'financial_feature_max_available_at',
              'financial_source_sha256', 'sec_submission_collections', 'sec_review_queues',
              'issuer_outcome_review_pointer', 'vendor_bars_present', 'vendor_bar_count', 'vendor_last_bar_date',
              'original_vendor_vintage_archived', 'valuation_rating_supported', 'negative_label_assigned_by_ledger',
              'remaining_gaps']


def to_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(row[k], sort_keys=True, separators=(',', ':'))
                         if isinstance(row[k], (list, dict)) else ('' if row[k] is None else row[k]) for k in CSV_FIELDS})
    return buffer.getvalue().encode()


def build(snapshot_path: Path, protocol_path: Path, output_dir: Path, report_dir: Path) -> tuple[Path, Path]:
    protocol_bytes = protocol_path.read_bytes()
    require(sha256(protocol_bytes) == PROTOCOL_SHA256, 'collection protocol hash mismatch')
    protocol = json.loads(protocol_bytes)
    require(protocol.get('schema_version') == 'ma-evidence-collection-protocol-v1', 'unsupported protocol schema')
    snapshot_bytes, snapshot_digest = read_once(snapshot_path)
    require(snapshot_path.stem.endswith(snapshot_digest), f'content address mismatch: {snapshot_path}')
    manifest = json.loads(snapshot_bytes)
    root = snapshot_path.parent
    payloads, availability = verify_snapshot(manifest, root, protocol)

    def load(name):
        return payloads[name]
    frame = json.loads(load('sampling_frame'))
    assembly = json.loads(load('assembly'))
    panel = json.loads(load('panel'))
    frozen = json.loads(load('frozen_labels'))
    candidates = list(csv.DictReader(io.StringIO(load('deal_candidates').decode())))
    financial_records = (json.loads(load('financial_records.json'))['records']
                         + json.loads(load('positive_financial_records.json'))['records'])
    exclusions = json.loads(load('observation_exclusions'))
    valuation, valuation_hashes = {}, {}
    for year in ('2021', '2023', '2024'):
        value = json.loads(load(f'valuation_manifest_{year}'))
        require(len(value['request']['symbols']) == 100 and value['request']['symbols'] == protocol['collection_order'],
                f'{year}: vendor request does not cover the ordered frame')
        require(value['original_vendor_vintage_archived'] is False and value['query_complete'] is True, f'{year}: probe flags')
        require(value['request']['end'][:10] < f'{year}-01-01', f'{year}: vendor window reaches observation date')
        valuation[year], valuation_hashes[year] = value, manifest['inputs'][f'valuation_manifest_{year}']['sha256']
    exclusion_refs = {}
    for ref in exclusions['reviews']:
        match = re.search(r'/([A-Z]+)-(\d{4})-censoring-review-', ref['source_relative_path'])
        require(match is not None, 'unparseable censoring review reference')
        exclusion_refs[(match.group(1), f'{match.group(2)}-01-01')] = ref
    rows = build_rows(protocol, frame, assembly, panel, frozen, candidates, financial_records, availability,
                      valuation, valuation_hashes, exclusion_refs)
    require(len(rows) == 300 and len({(r['ticker'], r['observation_date']) for r in rows}) == 300,
            'ledger must hold 300 unique frame rows')
    summary = summarize(rows, assembly)
    csv_bytes = to_csv(rows)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / f'ma-evidence-frame-ledger-{sha256(csv_bytes)}.csv'
    if not csv_path.exists():
        csv_path.write_bytes(csv_bytes)
    require(csv_path.read_bytes() == csv_bytes, 'csv content address mismatch')
    ledger = {
        'schema_version': LEDGER_SCHEMA, 'protocol_sha256': PROTOCOL_SHA256,
        'input_snapshot': {'relative_path': snapshot_path.name, 'sha256': snapshot_digest},
        'local_only_inputs': sorted(LOCAL_ONLY_INPUTS),
        'input_sha256': {k: v['sha256'] for k, v in sorted(manifest['inputs'].items())},
        'builder_sha256': sha256(Path(__file__).read_bytes()),
        'csv': {'relative_path': f'reports/ma_evidence_20261002/{csv_path.name}', 'sha256': sha256(csv_bytes),
                'rows': len(rows)},
        'collection_order_rule': protocol['collection_order_rule'],
        'row_order': 'protocol collection_order x planned_observation_dates ascending',
        'semantics': {
            'ledger_status_precedence': ['admitted_positive|admitted_negative', 'censored_no_binary_label',
                                         'prior_control_announcement_post_event_disposition_unreviewed',
                                         'reviewed_control_event_in_horizon_not_admitted',
                                         'reviewed_event_ticker_match_identity_unverified',
                                         'prior_control_event_ticker_match_identity_unverified',
                                         'sec_candidate_signal_in_horizon_unadjudicated', 'outcome_unknown_unreviewed'],
            'identity': 'CIK only from the assembly join to reviewed original financial records; ticker or name matches are flagged unverified and never resolve identity.',
            'candidates': 'Unadjudicated SEC form signals (tender-offer target / merger-proxy filer) from the 336-row candidate ledger; not labels. Absence of a candidate is not evidence of no event.',
            'negatives': 'This ledger assigns no labels. Only the 20 existing structurally admitted rows carry binary outcomes.',
            'valuation': 'Vendor SIP raw daily bars for the 15 days before cutoff show quote availability under a current-vendor reconstruction only; original_vendor_vintage_archived false; no valuation rating is supported.',
            'source_availability': 'Existing artifact presence only; queues and collections remain pending substantive review unless an assembly-verified corpus hash is present.'},
        'summary': summary, 'rows': rows,
        'limitations': ['Assembly coverage and all admitted labels are reused as originally verified; this build does not re-run the original verifiers.',
                        'Ticker/name-only matches can be wrong for reused tickers or renamed issuers.',
                        'The candidate ledger was generated from SEC form signals through its own date range and is not an exhaustive event census.',
                        'Vendor symbol mapping (asof) is not CIK identity or historical membership.',
                        'Outcome-exposed retrospective collection; no predictive or independent confirmation.']}
    output_dir.mkdir(parents=True, exist_ok=True)
    return write_addressed(output_dir, 'ma-evidence-frame-ledger', ledger), csv_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--original-root', type=Path, required=True)
    snap.add_argument('--valuation-root', type=Path, required=True)
    snap.add_argument('--protocol', type=Path, required=True)
    snap.add_argument('--output-dir', type=Path, required=True)
    bld = sub.add_parser('build')
    bld.add_argument('--snapshot', type=Path, required=True)
    bld.add_argument('--protocol', type=Path, required=True)
    bld.add_argument('--output-dir', type=Path, required=True)
    bld.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            print(snapshot(args.original_root.resolve(), args.valuation_root.resolve(), args.protocol, args.output_dir))
        else:
            for path in build(args.snapshot, args.protocol, args.output_dir, args.report_dir):
                print(path)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
