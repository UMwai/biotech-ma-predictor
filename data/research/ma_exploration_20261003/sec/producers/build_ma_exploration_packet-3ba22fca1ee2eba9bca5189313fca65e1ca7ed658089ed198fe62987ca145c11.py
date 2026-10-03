#!/usr/bin/env python3
"""Build the 2026-10-03 M&A exploration packets from archived SEC bytes and review records.

Inputs live under one evidence root: content-addressed SEC collections and their
attempt receipts/raw bytes (``scripts/collect_sec_accessions.py``), the reviewer's
append-only ``reviews/document-review-log.jsonl`` and the authored
``reviews/first-five-observation-judgments.json``. Inherited repository artifacts
(frame ledger, ARQT/CRNX inventories and progress receipts, ABUS v2 packet) are
read-only inputs bound by SHA-256.

Every review must reference a captured document by hash and carry a measured,
timezone-aware clock no earlier than that document's retrieval. Packets record
review depth per document and keep every unread, targeted-only, graphic,
structured or unfetched item open. Nothing here authors a coverage receipt,
assigns an outcome label or admits an observation.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import io
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_sec_accessions import verify_collection, write_addressed  # noqa: E402
from scripts.ma_evidence_io import confined, measured_now, parse_clock, read_once, require, sha256  # noqa: E402

SCHEMA = 'ma-exploration-packet-v1'
REVIEW_DEPTHS = {'full_text_read', 'targeted_sections_only', 'captured_unread',
                 'visual_review_complete', 'structured_format_review_complete'}
CLOSING_DEPTHS = {'full_text_read', 'visual_review_complete', 'structured_format_review_complete'}
INJECTED = re.compile(rb'<script type="text/javascript"  src="/[A-Za-z0-9/_+=-]+"></script>')
FLAGS = {'label_admission_allowed': False, 'outcome_label': None, 'coverage_receipt_authored': False,
         'complete_designated_primary_corpus_attested': False, 'historical_evidence_timing_attested': False,
         'as_accepted_byte_identity_verified': False, 'original_version_verified': False,
         'independent_human_review': False, 'outcome_exposed': True, 'validated_predictive_edge': False}
INHERITED = {
    'frame_ledger': ('data/research/ma_evidence_20261002/ma-evidence-frame-ledger-c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99.json',
                     'c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99'),
    'abus_2021_partial_v2': ('data/research/ma_evidence_20261002/abus_2021/abus-2021-partial-review-v2-9cc529b1dfb06507192f3657bfa2d526858b5ca9ed4c7cea721e8ea15f198f8d.json',
                             '9cc529b1dfb06507192f3657bfa2d526858b5ca9ed4c7cea721e8ea15f198f8d'),
    'ARQT_progress': ('data/history/panel_seed/negative_reviews/ARQT_original_source_progress.json',
                      '1ccaba574f6010ef5b01b9a3ec73d159fda6f8bee3086c391f11e9f485e3655d'),
    'CRNX_progress': ('data/history/panel_seed/negative_reviews/CRNX_original_source_progress.json',
                      'beaf5b8715665ddcca93ce28943c6120dbe6140442e4cc0d816abc34708e06af'),
}
PRIOR_ANNUAL = {  # prior record declarations (financial_records.json) that this pass re-checks against SEC indexes
    'ARQT': {'0001787306-20-000005': '2020-03-19', '0001787306-22-000009': '2022-02-22'},
    'CRNX': {'0001564590-20-009365': '2020-03-09', '0000950170-22-005050': '2022-03-30'},
}
FIRST_FIVE = ['ABUS', 'ADAP', 'AKUS', 'ALT', 'ALVR']
OBSERVATIONS = ['2021-01-01', '2023-01-01', '2024-01-01']


def horizon_end(observation: str) -> str:
    return (date.fromisoformat(observation) + timedelta(days=365)).isoformat()


def inherited(repo: Path, name: str) -> dict:
    relative, digest = INHERITED[name]
    payload, actual = read_once(confined(repo, relative))
    require(actual == digest, f'inherited input changed: {relative} {actual}')
    return {'repo_relative_path': relative, 'sha256': digest, 'bytes': len(payload)}


def load_collections(root: Path, *, now=None) -> tuple[dict, dict, dict]:
    collections, docs, urls = {}, {}, {}
    for path in sorted((root / 'sec' / 'collections').glob('sec-collection-*.json')):
        collection, _, digest = verify_collection(path, root, now_=now)
        name = collection['plan']['name']
        require(name not in collections, f'two bound collections for plan {name}')
        collections[name] = {'relative_path': path.relative_to(root).as_posix(), 'sha256': digest, 'collection': collection}
        for entry in collection['accessions']:
            for kind in ('documents', 'data_files'):
                for doc in entry.get(kind, []):
                    if doc['capture_status'] == 'captured':
                        same = docs.setdefault((entry['accession'], doc['document_name']), {})
                        same[doc['source_sha256']] = {**doc, 'accession': entry['accession']}
        for entry in collection['urls']:
            urls[entry['url']] = entry
    return collections, docs, urls


def load_reviews(root: Path, docs: dict, *, now=None) -> tuple[list[dict], str]:
    current = now or measured_now()
    payload, digest = read_once(confined(root, 'reviews/document-review-log.jsonl'))
    reviews = []
    for number, line in enumerate(payload.decode().splitlines(), 1):
        review = json.loads(line)
        key = (review['accession'], review['document_name'])
        require(key in docs, f'review {number} references an uncaptured document {key}')
        require(review['source_sha256'] in docs[key], f'review {number} hash differs from captured bytes')
        doc = docs[key][review['source_sha256']]
        require(review['review_depth'] in REVIEW_DEPTHS, f'review {number} unknown depth')
        require(review.get('independent_human_review') is False and 'not independent human review' in review['reviewer'],
                f'review {number} must disclose agent review')
        reviewed = parse_clock(review['reviewed_at'], f'review {number}')
        require(parse_clock(doc['retrieved_at'], 'retrieved_at') <= reviewed <= current,
                f'review {number} clock precedes retrieval or is in the future')
        require(isinstance(review.get('paraphrase'), str) and len(review['paraphrase']) >= 20, f'review {number} lacks paraphrase')
        reviews.append(review)
    return reviews, digest


def served_bytes_check(root: Path, doc: dict) -> dict:
    """SEC-served HTML carries one injected script tag; report whether removing exactly it restores the index size."""
    payload, _ = read_once(confined(root, doc['raw_relative_path']), doc['source_sha256'], doc['source_bytes'])
    found = INJECTED.findall(payload)
    stripped = INJECTED.sub(b'', payload)
    return {'served_sha256': doc['source_sha256'], 'served_bytes': doc['source_bytes'], 'index_size_bytes': doc['index_size_bytes'],
            'injected_script_tags': len(found), 'script_stripped_sha256': sha256(stripped) if found else None,
            'script_stripped_length_matches_index_size': len(stripped) == doc['index_size_bytes']}


def review_state(reviews: list[dict]) -> str:
    depths = {r['review_depth'] for r in reviews}
    if depths & CLOSING_DEPTHS:
        return 'closed_by_review'
    if 'targeted_sections_only' in depths:
        return 'targeted_sections_only_open'
    return 'captured_unread_open'


def document_entry(root: Path, doc: dict, reviews: list[dict]) -> dict:
    entry = {k: doc.get(k) for k in ('sequence', 'type', 'description', 'document_name', 'document_url', 'capture_status',
                                     'source_sha256', 'source_bytes', 'raw_relative_path', 'retrieved_at', 'index_size_bytes')}
    if doc['capture_status'] != 'captured':
        entry['state'] = 'open_' + doc['capture_status']
        return entry
    if doc['document_name'].lower().endswith(('.htm', '.html', '.txt')) and doc.get('type') != 'GRAPHIC':
        entry['served_bytes_check'] = served_bytes_check(root, doc)
    else:
        entry['index_size_match'] = doc.get('index_size_match')
    entry['reviews'] = [{k: r[k] for k in ('review_depth', 'sections_read', 'finding', 'paraphrase', 'reviewed_at',
                                           'control_transaction_disclosed')} for r in reviews]
    entry['state'] = review_state(reviews)
    return entry


def accession_entry(root: Path, entry: dict, by_doc: dict, designated: dict | None) -> dict:
    source = designated or entry
    documents, data_files = [], []
    for doc in source['documents']:
        documents.append(document_entry(root, {**doc, 'accession': entry['accession']}, by_doc.get((entry['accession'], doc.get('source_sha256')), [])))
    for doc in source['data_files']:
        data_files.append(document_entry(root, {**doc, 'accession': entry['accession']}, by_doc.get((entry['accession'], doc.get('source_sha256')), [])))
    real = [d for d in documents if d['description'] != 'Complete submission text file']
    parent = real[0]
    open_items = [d['document_name'] for d in documents + data_files if not d['state'].startswith('closed')]
    # The complete submission text file re-packages the listed documents; it is reported, not counted as a separate exhibit.
    aggregate = [d['document_name'] for d in documents if d['description'] == 'Complete submission text file']
    open_listed = [name for name in open_items if name not in aggregate]
    return {'accession': entry['accession'], 'purpose': entry['purpose'], 'inventory_form': entry.get('inventory_form'),
            'inventory_filed_date': entry.get('inventory_filed_date'), 'index': entry['index'],
            'index_capture': {k: entry[k] for k in ('index_url', 'raw_relative_path', 'source_sha256', 'retrieved_at')},
            'filed_date_matches_inventory': entry.get('inventory_filed_date') in (None, entry['index']['filing_date']),
            'collection_plan': 'designated-material-accessions' if designated else None,
            'parent_state': parent['state'], 'documents': documents, 'data_files': data_files,
            'open_items': open_items, 'all_listed_items_closed': not open_items,
            'complete_submission_aggregate_not_fetched': aggregate,
            'all_listed_documents_and_data_files_closed': not open_listed}


def audit_packet(root: Path, repo: Path, ticker: str, collections: dict, by_doc: dict, urls: dict) -> dict:
    plan = collections[f'{ticker.lower()}-2021-audit']['collection']
    designated = {e['accession']: e for e in collections['designated-material-accessions']['collection']['accessions']}
    accessions = [accession_entry(root, e, by_doc, designated.get(e['accession'])) for e in plan['accessions']]
    retained = [a for a in accessions if a['purpose'] == 'retained_material_parent_2021_2022q1']
    require([a['index']['filing_date'] for a in retained] == sorted(a['index']['filing_date'] for a in retained),
            'retained parents not in filing-date order')
    exhibits = [d for a in retained for d in a['documents'][1:] if d['description'] != 'Complete submission text file']
    texts = [d for d in exhibits if d.get('type') != 'GRAPHIC']
    graphics = [d for d in exhibits if d.get('type') == 'GRAPHIC']
    data_files = [d for a in retained for d in a['data_files']]
    annual = []
    for accession, declared in PRIOR_ANNUAL[ticker].items():
        found = next(a for a in accessions if a['accession'] == accession)
        annual.append({'accession': accession, 'form': found['index']['form_heading'], 'period': found['index']['period_of_report'],
                       'sec_index_filing_date': found['index']['filing_date'], 'accepted_edgar_display': found['index']['accepted_edgar_display'],
                       'prior_record_declared_date': declared, 'declared_date_matches_sec_index': declared == found['index']['filing_date'],
                       'primary_document_state': found['parent_state'],
                       'membership_review': found['documents'][0].get('reviews', [])})
    pdfs = [{k: urls[u['url']].get(k) for k in ('id', 'url', 'capture_status', 'source_sha256', 'source_bytes', 'retrieved_at', 'raw_relative_path')}
            | {'prior_capture_sha256': u['prior_capture_sha256'],
               'byte_identical_to_prior_2026_capture': urls[u['url']].get('source_sha256') == u['prior_capture_sha256'],
               'interpretation': 'unchanged bytes since the 2026-09-08 capture only; not original-version evidence'}
            for u in plan['urls']]
    count = lambda items, state: sum(1 for d in items if d['state'] == state)  # noqa: E731
    return {'schema_version': SCHEMA, 'packet': f'{ticker}-2021-negative-timing-audit', 'ticker': ticker, **FLAGS,
            'observation_at': '2021-01-01T00:00:00Z', 'horizon_end_at': '2022-01-01T00:00:00Z',
            'inventory_window': {'start': '2021-01-01', 'end': '2022-03-31',
                                 'excluded_forms_policy': 'src/research/regulatory_corpus.py EXCLUDED_FORMS'},
            'inherited_progress_receipt': inherited(repo, f'{ticker}_progress'),
            'collection': {k: collections[f'{ticker.lower()}-2021-audit'][k] for k in ('relative_path', 'sha256')},
            'admission_status': 'blocked: no SEC-direct timing binder; corpus incomplete; no coverage receipt authored',
            'counts': {'retained_parents': len(retained),
                       'parents_closed_by_full_read': count([{'state': a['parent_state']} for a in retained], 'closed_by_review'),
                       'parents_targeted_only': count([{'state': a['parent_state']} for a in retained], 'targeted_sections_only_open'),
                       'parents_unread': count([{'state': a['parent_state']} for a in retained], 'captured_unread_open'),
                       'text_exhibits': len(texts), 'text_exhibits_closed': count(texts, 'closed_by_review'),
                       'text_exhibits_targeted_only': count(texts, 'targeted_sections_only_open'),
                       'text_exhibits_unread': count(texts, 'captured_unread_open'),
                       'graphics': len(graphics), 'graphics_closed': count(graphics, 'closed_by_review'),
                       'xbrl_data_files': len(data_files), 'xbrl_data_files_closed': count(data_files, 'closed_by_review'),
                       'accessions_with_every_listed_item_closed': sum(a['all_listed_items_closed'] for a in retained),
                       'accessions_with_every_listed_document_and_data_file_closed':
                           sum(a['all_listed_documents_and_data_files_closed'] for a in retained)},
            'annual_membership_evidence': annual, 'annual_pdf_refetch': pdfs, 'accessions': accessions,
            'remaining_gaps': ['targeted-only and unread parents/exhibits listed per accession (open)',
                               'graphics without visual review and XBRL data files not fetched (open)',
                               'complete submission text files not fetched (open)',
                               'issuer-news original-version reconstruction not performed',
                               'SEC-direct negative-coverage/timing binder not implemented',
                               'subject-company filings outside the inherited exact-CIK EFTS inventories not separately searched']}


def resolve(ref: dict, docs: dict, by_doc: dict, label: str) -> dict:
    key = (ref['accession'], ref['document_name'])
    require(key in docs, f'{label}: reference not captured {key}')
    choices = docs[key]
    if 'source_sha256' in ref:
        require(ref['source_sha256'] in choices, f'{label}: referenced hash not captured {key}')
        doc = choices[ref['source_sha256']]
    else:
        require(len(choices) == 1, f'{label}: ambiguous document name {key}; reference must name source_sha256')
        doc = next(iter(choices.values()))
    reviews = by_doc.get((ref['accession'], doc['source_sha256']), [])
    require(bool(reviews), f'{label}: reference has no review record {key}')
    return {**ref, 'source_sha256': doc['source_sha256'], 'raw_relative_path': doc['raw_relative_path'],
            'review_states': sorted({r['review_depth'] for r in reviews}),
            'paraphrases': [r['paraphrase'] for r in reviews]}


def first_five_packet(root: Path, repo: Path, collections: dict, docs: dict, by_doc: dict) -> dict:
    ledger_ref = inherited(repo, 'frame_ledger')
    ledger = json.loads(read_once(confined(repo, ledger_ref['repo_relative_path']))[0])
    planned = [r for r in ledger['rows'] if r['ticker'] in FIRST_FIVE]
    require([(r['ticker'], r['observation_date']) for r in planned] ==
            [(t, o) for t in FIRST_FIVE for o in OBSERVATIONS] and [r['row_index'] for r in planned] == list(range(1, 16)),
            'inherited first-five row order changed')
    judgments_payload, judgments_digest = read_once(confined(root, 'reviews/first-five-observation-judgments.json'))
    judgments = json.loads(judgments_payload)
    require(judgments.get('label_admission_allowed') is False and judgments.get('independent_human_review') is False,
            'judgment authority flags')
    authored = parse_clock(judgments['authored_at'], 'judgments.authored_at')
    batch = collections['first-five-batch']['collection']
    index = {e['accession']: e['index'] for e in batch['accessions'] if e['status'] == 'index_captured'}
    rows = []
    for ledger_row, judged in zip(planned, judgments['rows']):
        t, o = ledger_row['ticker'], ledger_row['observation_date']
        require((judged['ticker'], judged['observation_date']) == (t, o), f'judgment row order differs at {t} {o}')
        require(ledger_row['horizon_end_date'] == horizon_end(o), f'{t} {o}: horizon arithmetic differs from ledger')
        refs = {}
        for name in ('membership_before', 'membership_after'):
            if judged[name]:
                refs[name] = resolve(judged[name], docs, by_doc, f'{t} {o} {name}') | {'index': index[judged[name]['accession']]}
        for ref in judged.get('membership_exclusion_sources', []):
            refs.setdefault('membership_exclusion_sources', []).append(resolve(ref, docs, by_doc, f'{t} {o} exclusion') | {'index': index[ref['accession']]})
        window = judged['window']
        resolved_window = {k: [resolve(r, docs, by_doc, f'{t} {o} {k}') | {'index': index[r['accession']]} for r in window.get(k, [])]
                           for k in ('screened', 'control_candidates', 'engagement', 'engagement_in_window', 'acquirer_side')}
        for kind, items in resolved_window.items():
            for item in items:
                require(parse_clock(max(r['reviewed_at'] for r in by_doc[(item['accession'], item['source_sha256'])]), 'review') <= authored,
                        f'{t} {o}: judgment authored before its cited review')
        before = refs.get('membership_before', {}).get('index', {}).get('filing_date')
        require(before is None or before < o, f'{t} {o}: before-membership evidence not before observation')
        after = refs.get('membership_after', {}).get('index', {}).get('filing_date')
        require(after is None or after > o, f'{t} {o}: after-membership evidence not after observation')
        for item in resolved_window['control_candidates']:
            require(o <= item['index']['filing_date'] <= horizon_end(o), f'{t} {o}: control candidate outside horizon')
        info = judgments['issuers'][t]
        rows.append({'row_index': ledger_row['row_index'], 'ticker': t, 'observation_date': o, 'horizon_end_date': horizon_end(o),
                     'horizon_days': 365, 'cik': info['cik'], 'inherited_ledger_status': ledger_row['ledger_status'],
                     'inherited_identity_status': ledger_row['frame_identity_status'],
                     'identity_evidence': {'sec_cik': info['cik'], 'note': info['identity_note'],
                                           'initial_listing_registration': resolve(info['initial_listing'], docs, by_doc, f'{t} listing') | {'index': index[info['initial_listing']['accession']]},
                                           'identity_join_admitted': False},
                     'listed_instrument': info['instrument'],
                     'ads_mapping_to_common_equity': judged.get('ads_mapping_to_common_equity'),
                     'route': {'collection_route': 'sec_direct_archives_raw_bytes', 'sec_route_compatible_with_existing_timing_binder': False,
                               **info['route']},
                     'membership_status': judged['membership_status'],
                     'membership_evidence': refs, 'membership_exclusion_basis': judged.get('membership_exclusion_basis'),
                     'prior_control_exclusion': judged['prior_control_exclusion'],
                     'window_review': {**resolved_window, 'note': window['note'],
                                       'screen_rule': 'first-five-batch plan purpose (fixed form/item rule); screen, not complete corpus'},
                     'control_subtype': judged.get('control_subtype'),
                     'label_status': judged['label_status'], 'label_admitted': False,
                     'remaining_gaps': judgments['common_remaining_gaps'] + list(ledger_row['remaining_gaps'])})
    statuses = {}
    for row in rows:
        statuses[row['label_status']] = statuses.get(row['label_status'], 0) + 1
    return {'schema_version': SCHEMA, 'packet': 'first-five-fixed-frame-observations', **FLAGS,
            'inherited_frame_ledger': ledger_ref, 'judgments': {'relative_path': 'reviews/first-five-observation-judgments.json',
                                                                'sha256': judgments_digest},
            'collection': {k: collections['first-five-batch'][k] for k in ('relative_path', 'sha256')},
            'abus_2021_inherited_partial_packet': inherited(repo, 'abus_2021_partial_v2') | {
                'status': 'partial; reused by hash, not re-reviewed; graphics/unsupported payloads remain open'},
            'row_count': len(rows), 'label_status_counts': statuses, 'rows': rows,
            'design_questions_for_root': ['ADAP ADS (1 ADS = 6 ordinary shares) vs panel common_equity membership contract',
                                          'ALVR 2024 reverse-merger control candidate: admit to, separately tag from, or exclude from the whole-company acquisition event class']}


def example_packet(docs: dict, by_doc: dict) -> dict:
    cite = lambda a, d: resolve({'accession': a, 'document_name': d}, docs, by_doc, 'example')  # noqa: E731
    return {'schema_version': SCHEMA, 'packet': 'science-buyer-example-akus-lilly', **FLAGS,
            'selection': 'chosen after the AKUS acquisition outcome was known; illustration only',
            'not_a': ['scientific score', 'retrospective prediction', 'sampled new positive', 'evidence of parameter predictiveness',
                      'ordinal rating (full rubric and candidate review not performed)'],
            'declared_buyer_universe': 'unchanged 25 declared buyers; Eli Lilly & Co. already present in the inherited 2020/2022/2023 schedules; no insertion or eventual-buyer filter',
            'frame_note': 'The Oct 17-18, 2022 Lilly agreement falls outside every AKUS observation horizon in the fixed frame (2021 horizon ends 2022-01-01; AKUS not listed on 2023-01-01).',
            'pre_cutoff_evidence_2020_12_31': [cite('0001558370-20-013595', 'tmb-20201112xex99d1.htm'),
                                              cite('0001558370-20-013596', 'akus-20200930x10q.htm'),
                                              cite('0001193125-20-317452', 'd73548dsctoc.htm'),
                                              cite('0001193125-20-317452', 'd73548dex991.htm')],
            'announcement_or_after_outcome_explanation': [cite('0001104659-22-109512', 'tm2228372d1_ex99-1.htm')],
            'excluded_sources': {'akouos_fy2020_10k': 'published 2021-03-29, after the 2021-01-01 observation; cannot supply its features',
                                 'prevail_side_joint_release_0001193125-20-317624': 'same joint release text as the Lilly EX-99.1 held; lead not captured'},
            'observation': ('Before 2021, Akouos publicly described AAV gene-therapy plans for hearing loss (a 2021 IND and planned '
                            'Phase 1/2 trial for AK-OTOF; preclinical, no clinical results), and Lilly publicly announced a '
                            'definitive agreement to acquire Prevail to establish a gene therapy program (announced Dec 15, 2020; '
                            'not closed by the cutoff). The 2022 announcement cites Prevail as Lilly\'s first gene-therapy '
                            'acquisition. Broad platform alignment does not establish target-specific engagement. This is a '
                            'source-backed adjacency illustration chosen with hindsight, not evidence that the adjacency was predictive.')}


def report(packets: dict, summary: dict) -> tuple[str, io.StringIO]:
    lines = ['# M&A exploration 2026-10-03 packets', '',
             'Evidence-only packets; no labels admitted, no coverage receipts, no ratings or fitting. First-fold support remains 4/20.', '',
             f"Newly archived raw files: {summary['raw_files']}; attempt receipts: {summary['attempt_receipts']}; "
             f"review records: {summary['review_records']}.", '',
             '| Audit | Parents | Parents full-read | Parents targeted | Text exhibits closed/targeted/total | Graphics closed/total | XBRL closed/total |',
             '|---|---:|---:|---:|---|---|---|']
    for ticker, c in summary['audit_counts'].items():
        lines.append(f"| {ticker} 2021 | {c['retained_parents']} | {c['parents_closed_by_full_read']} | {c['parents_targeted_only']} | "
                     f"{c['text_exhibits_closed']}/{c['text_exhibits_targeted_only']}/{c['text_exhibits']} | "
                     f"{c['graphics_closed']}/{c['graphics']} | {c['xbrl_data_files_closed']}/{c['xbrl_data_files']} |")
    lines += ['', f"First-five label status counts: {summary['first_five_label_status_counts']}; new label admissions: 0.", '',
              '## Original capture (legacy collections, unchanged bytes)', '']
    for item in summary['original_capture']:
        lines.append(f"- `{item['plan']}`: `{item['relative_path']}` recorded collector `{item['recorded_collector_sha256'][:12]}`, "
                     f"{item['recorded_started_at']} to {item['recorded_completed_at']}; producer snapshot: {item['producer_snapshot_status']}")
    lines += ['', '## Corrected validation (bound v2 collections re-derived from archived plan, receipt and index bytes)', '']
    for item in summary['corrected_validation']:
        lines.append(f"- `{item['plan']['name']}` ({item['mode']}): `{item['relative_path']}`, validator `{item['validated_collector_sha256'][:12]}`, "
                     f"{item['started_at']} to {item['completed_at']}")
    lines.append('')
    for name, (path, digest) in packets.items():
        lines.append(f'- `{name}`: `data/research/ma_exploration_20261003/{path}` (sha256 `{digest}`)')
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['ticker', 'accession', 'filing_date', 'form', 'document_name', 'type', 'state', 'source_sha256'])
    return '\n'.join(lines) + '\n', buffer


def replay_inputs(root: Path) -> list[dict]:
    """Every copied input names its own SHA-256; verify bytes against that name."""
    found = []
    for pattern in ('inputs/*', 'root_web_leads/*', 'finalized-plan-addendum-*.json'):
        for path in sorted(root.glob(pattern)):
            payload, digest = read_once(confined(root, path.relative_to(root)))
            require(path.stem.endswith(digest), f'replay input name does not carry its hash: {path.name}')
            found.append({'relative_path': path.relative_to(root).as_posix(), 'sha256': digest, 'bytes': len(payload)})
    require(any(f['relative_path'].startswith('inputs/exploration-registration-') for f in found), 'registration copy missing')
    return found


def capture_history(collections: dict) -> tuple[list[dict], list[dict]]:
    """Separate the original (legacy) capture record from the corrected bound-collection validation."""
    original, corrected = [], []
    for name, item in sorted(collections.items()):
        collection = item['collection']
        current = sha256((Path(__file__).resolve().parent / 'collect_sec_accessions.py').read_bytes())
        corrected.append({'plan': collection['plan'], 'relative_path': item['relative_path'], 'sha256': item['sha256'],
                          'mode': collection['mode'], 'validated_collector_sha256': collection['collector_sha256'],
                          'recorded_collector_equals_running_source': collection['collector_sha256'] == current,
                          'recorded_hashes_are_provenance_not_validated_by_verify': True,
                          'helper_sha256': collection['helper_sha256'], 'started_at': collection['started_at'],
                          'completed_at': collection['completed_at']})
        lineage = collection['lineage']
        if lineage:
            original.append({'plan': name, **lineage['legacy_collection'], 'producer_snapshot': lineage['producer_snapshot'],
                             'producer_snapshot_status': lineage['producer_snapshot_status']})
        else:
            original.append({'plan': name, 'relative_path': item['relative_path'], 'sha256': item['sha256'],
                             'recorded_collector_sha256': collection['collector_sha256'],
                             'recorded_started_at': collection['started_at'], 'recorded_completed_at': collection['completed_at'],
                             'producer_snapshot_status': 'produced_by_the_corrected_collector'})
    return original, corrected


def build(root: Path, repo: Path, reports: Path) -> dict:
    root, repo = root.resolve(), repo.resolve()
    now = measured_now()
    collections, docs, urls = load_collections(root, now=now)
    reviews, log_digest = load_reviews(root, docs, now=now)
    by_doc: dict = {}
    for review in reviews:
        by_doc.setdefault((review['accession'], review['source_sha256']), []).append(review)
    built = {'ARQT': audit_packet(root, repo, 'ARQT', collections, by_doc, urls),
             'CRNX': audit_packet(root, repo, 'CRNX', collections, by_doc, urls),
             'first_five': first_five_packet(root, repo, collections, docs, by_doc),
             'example': example_packet(docs, by_doc)}
    written = {}
    for name, packet in built.items():
        packet['built_at'] = now.isoformat()
        packet['review_log'] = {'relative_path': 'reviews/document-review-log.jsonl', 'sha256': log_digest, 'records': len(reviews)}
        packet['builder_sha256'] = sha256(Path(__file__).read_bytes())
        path = write_addressed(root / 'packets', name.lower().replace('_', '-'), packet)
        written[name] = (path.relative_to(root).as_posix(), path.stem.rsplit('-', 1)[1])
    summary = {'schema_version': SCHEMA, 'packet': 'exploration-summary', **FLAGS, 'built_at': now.isoformat(),
               'packets': {k: {'relative_path': v[0], 'sha256': v[1]} for k, v in written.items()},
               'collections': {k: {kk: v[kk] for kk in ('relative_path', 'sha256')} for k, v in collections.items()},
               'raw_files': len(list((root / 'sec' / 'raw').glob('*'))),
               'attempt_receipts': len(list((root / 'sec' / 'attempts').glob('attempt-*.json'))),
               'review_records': len(reviews),
               'audit_counts': {t: built[t]['counts'] for t in ('ARQT', 'CRNX')},
               'first_five_label_status_counts': built['first_five']['label_status_counts'],
               'replay_inputs': replay_inputs(root),
               'original_capture': capture_history(collections)[0], 'corrected_validation': capture_history(collections)[1],
               'new_label_admissions': 0, 'first_fold_negative_support': '4/20 unchanged', 'first_fold_positive_support': '5 unchanged',
               'k5_degenerate_heldout_issue': 'open'}
    summary_path = write_addressed(root, 'exploration-summary', summary)
    readme, buffer = report(written | {'summary': (summary_path.relative_to(root).as_posix(), summary_path.stem.rsplit('-', 1)[1])}, summary)
    writer = csv.writer(buffer, lineterminator='\n')
    for t in ('ARQT', 'CRNX'):
        for acc in built[t]['accessions']:
            for doc in acc['documents'] + acc['data_files']:
                writer.writerow([t, acc['accession'], acc['index']['filing_date'], acc['index']['form_heading'],
                                 doc['document_name'], doc.get('type') or '', doc['state'], doc.get('source_sha256') or ''])
    reports.mkdir(parents=True, exist_ok=True)
    csv_bytes = buffer.getvalue().encode()
    csv_path = reports / f'audit-document-census-{sha256(csv_bytes)}.csv'
    csv_path.write_bytes(csv_bytes)
    (reports / 'README.md').write_text(readme + f'- Audit document census CSV: `{csv_path.name}`\n')
    return {'summary': summary_path, 'packets': written, 'csv': csv_path}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, default=Path('data/research/ma_exploration_20261003'))
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    parser.add_argument('--reports-dir', type=Path, default=Path('reports/ma_exploration_20261003'))
    args = parser.parse_args(argv)
    try:
        result = build(args.evidence_root, args.repo_root, args.reports_dir)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({k: str(v) for k, v in result.items()}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
