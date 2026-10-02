#!/usr/bin/env python3
"""Assemble the ABUS 2021-01-01 partial source-review packet (not a label).

Every cited passage is located by pattern in hash-verified extracted text from
the original read-only SEC review queue and bound to payload, extracted-text and
whole-response hashes. Judgments are the reviewing agent's own statements; they
are not independent human review. Output is content-addressed in this directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ORIGINAL = Path('/home/umwai/biotech-ma-predictor')
WORK = Path('/tmp/biotech-ma-evidence-20261002-gxcbzh98')
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
COLLECTION = ORIGINAL / 'data/history/web_source_research/20260919/ABUS-submissions/sec-submission-collection.json'
QUEUE = ORIGINAL / 'output/sec_corpus/20260919/ABUS-container-review/sec-outcome-review-queue-0dbebcccab5bcfda363510bb289d52097d7d527e47713b644bcd2be3579c7bdd.json'
VERIFICATION = ORIGINAL / 'output/sec_corpus/20260919/ABUS-container-review/sec-corpus-verification-a57bf2ed2778892d3d62f9ecb50053da13edcb23fbd3d4a42c46f0511733d423.json'
PROTOCOL_SHA256 = '8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0'
TOOL_FILES = ['src/research/panel_assembly.py', 'src/research/sec_outcome_review.py', 'src/research/sec_corpus.py',
              'src/research/sec_collection.py', 'src/research/sec_review_queue.py', 'src/research/regulatory_corpus.py',
              'src/research/sec_source_family.py', 'src/research/observation_exclusions.py',
              'scripts/verify_sec_outcome_review.py', 'scripts/build_sec_review_queue.py',
              'scripts/collect_sec_submissions.py', 'scripts/collect_issuer_archives.py',
              'docs/SEC_SUBMISSION_OUTCOME_REVIEW.md', 'docs/REGULATORY_SOURCE_REVIEW.md']


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def one(paths, label):
    paths = sorted(paths)
    require(len(paths) == 1, f'expected exactly one {label}, found {len(paths)}')
    return paths[0]


def main(reviewed_at: str) -> Path:
    collection_bytes, queue_bytes = COLLECTION.read_bytes(), QUEUE.read_bytes()
    collection, queue = json.loads(collection_bytes), json.loads(queue_bytes)
    require(queue['collection_sha256'] == sha(collection_bytes) and QUEUE.stem.endswith(sha(queue_bytes)), 'queue binding')
    screening_path = one(HERE.glob('sec-screening-ABUS-*.json'), 'screening receipt')
    screening_bytes = screening_path.read_bytes()
    require(screening_path.stem.endswith(sha(screening_bytes)), 'screening content address')
    screening = json.loads(screening_bytes)
    require(screening['collection']['sha256'] == sha(collection_bytes) and screening['queue']['sha256'] == sha(queue_bytes),
            'screening bound to other inputs')
    ledger_path = one(EVIDENCE.glob('ma-evidence-frame-ledger-*.json'), 'frame ledger')
    ledger = json.loads(ledger_path.read_bytes())
    row = ledger['rows'][0]
    require((row['row_index'], row['ticker'], row['observation_date'], row['cik']) == (1, 'ABUS', '2021-01-01', 1447028),
            'ledger row 1 is not ABUS 2021')
    accessions = {a['accession_number']: a for a in collection['accessions']}
    docs = {(d['accession_number'], d['filename']): d for d in queue['documents']}
    qroot = QUEUE.parent

    def cite(accession, filename, pattern, width=420):
        doc = docs[(accession, filename)]
        text_bytes = (qroot / doc['extracted_text']['relative_path']).read_bytes()
        require(sha(text_bytes) == doc['extracted_text']['sha256'], f'{filename}: extracted text hash')
        text = text_bytes.decode()
        matches = list(re.finditer(pattern, text))
        require(len(matches) >= 1, f'{filename}: passage not found: {pattern}')
        start = matches[0].start()
        submission = accessions[accession]['submission']
        return {'accession_number': accession, 'filename': filename, 'document_type': doc['document_type'],
                'publication_date': doc['publication_date'], 'payload_sha256': doc['payload_sha256'],
                'extracted_text_sha256': doc['extracted_text']['sha256'],
                'whole_response_sha256': submission['source_sha256'], 'source_uri': submission['source_uri'],
                'locator': {'pattern': pattern, 'extracted_text_char_offset': start, 'match_count': len(matches)},
                'excerpt': ' '.join(text[start:start + width].split())}

    # 8-K item census (2020-01-01 .. 2022-03-31), computed from every 8-K primary document.
    census = []
    for (accession, filename), doc in sorted(docs.items(), key=lambda kv: (kv[1]['publication_date'], kv[0])):
        if doc['document_type'] != '8-K' or not doc.get('extracted_text'):
            continue
        text = (qroot / doc['extracted_text']['relative_path']).read_text()
        items = sorted(set(re.findall(r'Item\s+(\d\.\d\d)', text)))
        census.append({'accession_number': accession, 'publication_date': doc['publication_date'], 'items': items})
    control_items = {'1.02', '2.01', '3.01', '3.03', '5.01', '5.03'}
    flagged = [c for c in census if control_items & set(c['items'])]
    item_101 = [c for c in census if '1.01' in c['items']]

    findings = [
        {'id': 'F1-roivant-13D-amendment-11', 'classification': 'non_qualifying_existing_holder_position',
         'source': cite('0000950103-21-016171', 'dp160071_sc13da-11.htm', r'Roivant beneficially owns 38,847,462, or 29\.1%'),
         'supporting': [cite('0000950103-21-016171', 'dp160071_sc13da-11.htm', r'standstill period whereby'),
                        cite('0000950103-21-016171', 'dp160071_sc13da-11.htm', r'does not currently have any plans or proposals')],
         'judgment': 'Roivant (largest holder) reports 29.1% after the October 18, 2021 mandatory conversion of preferred shares it acquired in 2017-2018. The 49.99% standstill and lock-up expired October 18, 2021; Item 4 states no current plans or proposals under 4(a)-(j). A pre-existing minority position reaching 29.1% is not a definitive announcement transferring more than 50% control; standstill expiry is a disclosed possibility, not an event.'},
        {'id': 'F2-roivant-proxy-2021', 'classification': 'non_qualifying_existing_holder_position',
         'source': cite('0001104659-21-047991', 'tm212510-1_def14a.htm', r'Excluding the Preferred Shares, Roivant'),
         'judgment': 'April 2021 proxy: Roivant 16.6% of common excluding preferred, approximately 32% assuming conversion at then capital structure. Below the >50% control threshold.'},
        {'id': 'F3-roivant-10K-fy2020', 'classification': 'non_qualifying_existing_holder_position',
         'source': cite('0001447028-21-000021', 'abus-20201231.htm', r'executive officers, directors, five percent or greater shareholders'),
         'judgment': 'FY2020 10-K (filed 2021-03-04): insiders/5% holders ~26%; Roivant group ~23% as of March 1, 2021. Concentration risk factor, not a transaction.'},
        {'id': 'F4-roivant-resale-S3', 'classification': 'non_qualifying_secondary_registration',
         'source': cite('0001104659-21-134486', 'tm2131845-1_s3.htm', r'selling shareholder named herein'),
         'judgment': 'November 2021 S-3 registers potential resale by Roivant of its 38,847,462 shares (2015 merger and 2017 subscription origins). A resale registration is not an acquisition of the issuer.'},
        {'id': 'F5-qilu-license', 'classification': 'asset_or_license_event_not_control',
         'source': cite('0001171843-21-008473', 'f8k_121321.htm', r'Item 1\.01'),
         'judgment': 'December 13, 2021 exclusive regional license of AB-729 to Qilu (Greater China). Asset/license event; distinct from corporate control under the registered event policy.'},
        {'id': 'F6-genevant-cross-license-amendment', 'classification': 'asset_or_license_event_not_control',
         'source': cite('0001447028-21-000072', 'abus-20211209.htm', r'Item 1\.01'),
         'judgment': 'December 9, 2021 amendment to the Genevant cross license; Arbutus owns ~16% of Genevant. Not a transfer of Arbutus control.'},
        {'id': 'F7-historical-corporate-history', 'classification': 'pre_period_history_not_window_event',
         'source': cite('0001447028-21-000021', 'abus-20201231.htm', r'statutory plan of arrangement'),
         'judgment': 'All merger/arrangement/business-combination hits that are not equity-plan definitions, indenture boilerplate or XBRL labels describe the 2007 Inex plan of arrangement, the 2008 Protiva acquisition and the 2015 OnCore merger, all before the baseline window.'},
        {'id': 'F8-8K-item-census', 'classification': 'no_control_or_exit_item_in_reviewed_8Ks',
         'judgment': f'{len(census)} 8-K primary documents (2020-01-13..2022-03-03) were inspected. None reports Items 1.02, 2.01, 3.01, 3.03, 5.01 or 5.03. Item 1.01 appears in {len(item_101)} filings: two ATM sales-agreement amendments, the Genevant cross-license amendment and the Qilu license.',
         'census': census, 'control_or_exit_items_found': flagged},
    ]
    require(not flagged, 'an 8-K reports a control/exit item; reassess before packaging')
    require(len(item_101) == 4, 'Item 1.01 count changed; reassess judgment text')

    membership = {
        'status': 'proposed_evidence_not_admitted',
        'contemporaneous_feature': False,
        'frame_entry': {'source': 'Nasdaq Biotechnology Index annual additions notice (frame source)',
                        'source_sha256': '923baca63fe933a5443db8c153837df4f85178d9ff931bc8d01a8d1a240a4955',
                        'population_as_of_at': '2020-12-21T00:00:00Z'},
        'pre_cutoff_listing': [cite('0001447028-20-000038', 'arbutus10k2019.htm', r'Trading Symbol\(s\) Name of Each Exchange'),
                               cite('0001171843-20-008493', 'R1.htm', r'Security Exchange Name NASDAQ', 160)],
        'in_horizon_listing': [cite('0001447028-21-000072', 'R1.htm', r'Security Exchange Name NASDAQ', 160)],
        'post_horizon_continuity': [cite('0001447028-22-000019', 'abus-20211231.htm', r'Trading Symbol\(s\) Name of Each Exchange'),
                                    cite('0001171843-22-000411', 'R1.htm', r'Security Exchange Name NASDAQ', 160)],
        'operating_identity': [cite('0001447028-20-000038', 'arbutus10k2019.htm', r'is a publicly traded \(Nasdaq Global Select Market: ABUS\)'),
                               cite('0001447028-21-000021', 'abus-20201231.htm', r'is a clinical-stage, biopharmaceutical company')],
        'judgment': 'Issuer filings name Nasdaq as the exchange for ABUS common shares before the cutoff (FY2019 10-K cover; 2020-12-10 8-K cover), within the horizon (2021-12-10 8-K cover) and after it (2022-01-24 8-K cover; FY2021 10-K filed 2022-03-03). This is retrospective listing-continuity evidence from cover pages, not a dated exchange membership record. No listing_reviews entry or adjudicated membership interval exists for ABUS.'}

    tenk = accessions['0001447028-20-000038']
    financial = {
        'record_id': 'ABUS-2019-original-annual', 'accession_number': '0001447028-20-000038',
        'whole_response_sha256': tenk['submission']['source_sha256'], 'whole_response_bytes': tenk['submission']['byte_count'],
        'source_uri': tenk['submission']['source_uri'], 'publication_date': tenk['publication_date'],
        'facts': [dict(cite('0001447028-20-000038', 'arbutus10k2019.htm', pattern, 160), fact=name, reported_value=value,
                       source_unit='USD thousands', unit_multiplier=1000, value_usd=value * 1000)
                  for name, pattern, value in [('cash_usd', r'Cash and cash equivalents \$ 31,799', 31799),
                                               ('assets_usd', r'Total assets \$ 105,535', 105535),
                                               ('annual_rd_usd', r'Research and development \$ 57,601', 57601),
                                               ('annual_operating_cashflow_usd', r'Net cash used in operating activities \(71,006', -71006)]],
        'amendment': cite('0001447028-20-000041', 'a201910-ka.htm', r'sole purpose of correcting the Consent'),
        'judgment': 'The four reported FY2019 values in the existing financial record appear verbatim in the original 10-K primary document inside the captured whole SEC response, closing the null raw-hash custody gap for these facts only. The 10-K/A filed 2020-03-06 corrected only the auditor consent date. Values, units and availability in the existing record are unchanged; as-accepted byte identity remains unverified.'}

    receipts = []
    for path in sorted((WORK / 'collections/ABUS2021').glob('get-receipt-*.json')):
        payload = path.read_bytes()
        require(path.stem.endswith(sha(payload)), f'{path.name}: content address')
        value = json.loads(payload)
        if value.get('source_relative_path'):
            raw = (path.parent / value['source_relative_path']).read_bytes()
            require(sha(raw) == value['source_sha256'], f'{path.name}: raw hash')
        receipts.append({'path': str(path), 'sha256': sha(payload), 'url': value['url'],
                         'http_status': value.get('http_status'), 'error': value.get('error'),
                         'source_sha256': value.get('source_sha256')})
    probe_code = WORK / 'collections/ABUS2021/probe_public_get.py'

    kinds = screening['review_kind_counts']
    packet = {
        'schema_version': 'ma-evidence-abus2021-partial-review-v1',
        'issuer': {'ticker': 'ABUS', 'cik': 1447028, 'historical_issuer_name': 'Arbutus Biopharma Corporation',
                   'identity_basis': 'reviewed original FY2019 financial record CIK; SEC submission headers list subject CIK 1447028 for all 67 accessions'},
        'observation_at': '2021-01-01T00:00:00+00:00', 'information_cutoff_at': '2020-12-31T23:59:59+00:00',
        'horizon_end_at': '2022-01-01T00:00:00+00:00', 'horizon_days': 365,
        'protocol_sha256': PROTOCOL_SHA256,
        'ledger': {'relative_path': ledger_path.name, 'sha256': sha(ledger_path.read_bytes()), 'row_index': 1},
        'reviewer': 'Claude Opus 5.5 (claude-opus-5-5) agent source review; not independent human review',
        'reviewed_at': reviewed_at,
        'review_method': ('Byte replay of every captured response and payload slice; automated keyword screening of every saved '
                          'extracted text (text and structured payloads); substantive inspection of all 544 distinct screening '
                          'contexts, every 8-K primary document item list and EX-99 headline, and full reading of the Roivant '
                          'SC 13D/A. Untriggered passages were not all manually read; graphics and unsupported formats were not reviewed.'),
        'sources': {'collection': {'path': str(COLLECTION), 'sha256': sha(collection_bytes)},
                    'queue': {'path': str(QUEUE), 'sha256': sha(queue_bytes)},
                    'verification': {'path': str(VERIFICATION), 'sha256': sha(VERIFICATION.read_bytes())},
                    'screening_receipt': {'relative_path': screening_path.name, 'sha256': sha(screening_bytes)},
                    'issuer_archive_get_receipts': receipts,
                    'probe_code': {'path': str(probe_code), 'sha256': sha(probe_code.read_bytes())}},
        'replay': screening['replay'],
        'coverage': {'accessions': len(accessions), 'payloads': len(docs), 'review_kind_counts': kinds,
                     'window_screen_counts': screening['window_screen_counts'],
                     'distinct_contexts_inspected': screening['distinct_contexts'],
                     'graphic_payloads': sum(v for k, v in kinds.items() if k.startswith('graphic')),
                     'unique_decoded_graphics': screening['unique_decoded_graphics'],
                     'graphics_visually_reviewed': 0,
                     'unsupported_or_empty_extraction_payloads_reviewed': 0,
                     'excluded_forms_not_collected': collection['excluded_forms']},
        'substantive_findings': findings,
        'pending_baseline_partial': {
            'qualified_pending_control_transaction_found_in_reviewed_2020_SEC_text': False,
            'scope': '2020-01-01..2020-12-31 SEC corpus text only (FY2019 10-K, 2020 10-Qs, 8-Ks, DEF 14A, S-3, 424B5). Roivant SC 13D/A No. 11 states no transactions since its July 16, 2019 amendment.',
            'issuer_pre2020_baseline_review_performed': False},
        'membership_evidence': membership,
        'financial_custody': financial,
        'outcome_summary': {
            'qualifying_control_event_found_in_reviewed_scope': False,
            'censoring_event_found_in_reviewed_scope': False,
            'interpretation': 'No qualifying event was found within the reviewed SEC text scope. This is a partial finding, not a negative label: the designated issuer archive, graphics, unsupported formats, excluded ownership forms, incorporated references and source-version review remain open.'},
        'failed_gates': [
            'designated_issuer_press_release_archive_not_collected: issuer homepage GET 200; investor.arbutusbio.com/press-releases, /news-releases and the GlobeNewswire organization page each timed out once (no retry)',
            'graphic_visual_review_not_performed: 623 graphic payloads (609 decoded, 583 unique decoded; 14 undecoded)',
            'unsupported_format_and_empty_extraction_payloads_unreviewed: 268 unsupported_format + 98 structured without extracted text',
            'excluded_forms_not_collected: Forms 3/4/5, SC 13G/13G/A and others listed in coverage',
            'incorporated_reference_review_not_performed',
            'accession_original_version_judgments_not_made: 67 accessions; as_accepted_byte_identity_verified false',
            'per_document_subject_identity_review_not_performed',
            'issuer_pre2020_pending_baseline_review_not_performed',
            'membership_interval_not_adjudicated_or_admitted',
            'complete_sec_submission_outcome_review_and_historical_timing_receipt_not_produced'],
        'next_missing_original_source': 'Arbutus designated press-release inventory and bodies for 2020-01-01..2022-01-01 (investor.arbutusbio.com/news-releases year pages or the GlobeNewswire organization inventory), captured with a supported collector and failure receipts; then visual review of 583 unique decoded graphics.',
        'tool_basis_original_unpublished': {p: sha((ORIGINAL / p).read_bytes()) for p in TOOL_FILES},
        'tool_basis_new': {'scripts/screen_ma_source_packet.py': screening['screener_sha256'],
                           'data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet.py': sha(Path(__file__).read_bytes())},
        'outcome_label': None, 'label_admission_allowed': False, 'outcome_review_complete': False,
        'new_observation_staged': False, 'independent_human_review': False,
        'as_accepted_byte_identity_verified': False, 'historical_original_vintage_archived': False}
    payload = (json.dumps(packet, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
    out = HERE / f'abus-2021-partial-review-{sha(payload)}.json'
    out.write_bytes(payload)
    return out


if __name__ == '__main__':
    print(main(sys.argv[1]))
