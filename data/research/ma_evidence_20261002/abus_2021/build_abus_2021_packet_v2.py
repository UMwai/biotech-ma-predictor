#!/usr/bin/env python3
"""Superseding ABUS 2021-01-01 partial source-review packet (not a label).

Re-cites every first-packet finding through verified extracted bytes, adds the
recovered issuer press-release archive (2020, 2021, 2022Q1), an excluded-form
relevance adjudication, and an original filing-price valuation lead. The first
packet and its builder stay unchanged as history. Requires a measured review
timestamp that is not in the future and follows every represented source clock.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from scripts.collect_ma_issuer_archive import parse_body, verify_archive_collection  # noqa: E402
from scripts.collect_issuer_archives import Document, clean  # noqa: E402
from scripts.ma_evidence_io import chronology, confined, read_once, require, review_clock, sha256  # noqa: E402
from scripts.ma_source_packet import CONTROL_OR_EXIT_ITEMS, VerifiedQueue, compare_release  # noqa: E402
from scripts.screen_ma_source_packet import TERMS  # noqa: E402

ORIGINAL = Path('/home/umwai/biotech-ma-predictor')
WORK = Path('/tmp/biotech-ma-evidence-20261002-gxcbzh98')
HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent
COLLECTION = ORIGINAL / 'data/history/web_source_research/20260919/ABUS-submissions/sec-submission-collection.json'
QUEUE = ORIGINAL / 'output/sec_corpus/20260919/ABUS-container-review/sec-outcome-review-queue-0dbebcccab5bcfda363510bb289d52097d7d527e47713b644bcd2be3579c7bdd.json'
FROZEN_PROTOCOL_SHA256 = '8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0'
PROTOCOL_NAME = f'ma-collection-protocol-{FROZEN_PROTOCOL_SHA256}.json'
PROTOCOL_SCHEMA = 'ma-evidence-collection-protocol-v1'
FIRST_PACKET = 'abus-2021-partial-review-a21c52851cd85cdd65750b8a3ffe4cbc7ee74e84caa39c30331d7abd6fa41c11.json'
LEDGER = 'ma-evidence-frame-ledger-c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99.json'
SCREENING = 'sec-screening-ABUS-1fd3ddd7f4bc35276a2572400bcffb4031b0259b72f378d9291b75efb9d57577.json'
ISSUER_COLLECTION = 'issuer_archive/issuer-archive-collection-75e5039c4134cdb01ef8d191fb239f3571aaf52713e7d6060ab401cf3e8c4677.json'
INTERRUPTION = WORK / 'opus-worker-interruption.json'
OBSERVATION, HORIZON_END = '2021-01-01', '2022-01-01'
TOOL_FILES = ['src/research/panel_assembly.py', 'src/research/sec_outcome_review.py', 'src/research/sec_review_queue.py',
              'src/research/regulatory_corpus.py', 'docs/SEC_SUBMISSION_OUTCOME_REVIEW.md', 'docs/REGULATORY_SOURCE_REVIEW.md']
NEW_CODE = ['scripts/ma_evidence_io.py', 'scripts/ma_source_packet.py', 'scripts/collect_ma_issuer_archive.py',
            'scripts/collect_issuer_archives.py', 'scripts/screen_ma_source_packet.py', 'scripts/build_ma_evidence_ledger.py']

# Reviewer's substantive reading of issuer bodies with no same-period SEC exhibit match (by inventory date + title).
UNMATCHED_READING = {
    'results_or_call_scheduling_notice': 'Schedules a results release/call; dial-in logistics only.',
    'investor_conference_participation_notice': 'Announces presentation or fireside-chat participation; webcast logistics only.',
    'clinical_collaboration_announcement': 'Clinical collaboration with another company on a combination trial; no equity, control or asset transfer terms.',
    'scientific_abstract_notice': 'Lists accepted abstracts/presentation schedule and key findings.',
    'personnel_appointment': 'Appointment of a non-board officer.',
    'patent_litigation_filing': 'Arbutus and licensee Genevant sue Moderna for patent infringement damages (lag window, 2022-02-28).',
}


def classify_unmatched(title: str) -> str:
    rules = [(r'to Report .*Financial Results', 'results_or_call_scheduling_notice'),
             (r'to (?:Present|Participate)', 'investor_conference_participation_notice'),
             (r'Clinical Collaboration Agreement', 'clinical_collaboration_announcement'),
             (r'Abstracts? Accepted', 'scientific_abstract_notice'),
             (r'Appoints .* Vice President', 'personnel_appointment'),
             (r'Patent Infringement Lawsuit', 'patent_litigation_filing')]
    for pattern, label in rules:
        if re.search(pattern, title):
            return label
    raise ValueError(f'unclassified unmatched issuer release requires manual reading: {title}')


def excluded_form_adjudication(inventory_paths: list[Path]) -> dict:
    """Relevance of collector-excluded forms to the registered control/exit definitions (contents unreviewed)."""
    rules = {
        '3': ('not_an_announcement_channel', 'Initial insider ownership statement; cannot announce a definitive whole-company control agreement.'),
        '4': ('not_an_announcement_channel', 'Insider transaction report; a >50% acquisition by a holder also requires a Schedule 13D amendment, which was collected (Roivant 13D/A No.11 and its same-day Form 4 agree on the October 2021 conversion).'),
        'SC 13G': ('not_an_announcement_channel_by_eligibility', 'Rule 13d-1(b)/(c) filers certify no purpose of changing or influencing control; control intent requires Schedule 13D.'),
        'SC 13G/A': ('not_an_announcement_channel_by_eligibility', 'Same eligibility rule as SC 13G.'),
        'S-8': ('not_an_announcement_channel', 'Employee-plan share registration.'),
        'EFFECT': ('not_an_announcement_channel', 'SEC notice of registration effectiveness.'),
        'CT ORDER': ('not_an_announcement_channel', 'Confidential-treatment order for exhibit redactions.'),
        'CORRESP': ('relevance_unknown_contents_unreviewed', 'Issuer correspondence with SEC staff; released after review, not a contemporaneous announcement channel, but contents could discuss disclosures.'),
        'UPLOAD': ('relevance_unknown_contents_unreviewed', 'SEC staff letter; same limitation as CORRESP.'),
    }
    counts, seen = {}, {}
    for path in inventory_paths:
        payload, digest = read_once(path)
        seen[path.name] = digest
        for record in json.loads(payload)['records']:
            if record['form'] in rules:
                counts[record['form']] = counts.get(record['form'], 0) + 1
    return {'rule_basis': ('Registered event policy: positive = definitive announcement transferring >50% whole-company control; '
                           'censoring = observed non-acquisition exit. The SEC review contract requires a substantive relevance '
                           'decision for designated forms; it does not make every collector-excluded form mandatory.'),
            'inventory_sha256': seen, 'counts_in_2020_2022Q1_inventory': dict(sorted(counts.items())),
            'per_form': {form: {'relevance': rel, 'rule': text} for form, (rel, text) in rules.items()},
            'contents_reviewed': False,
            'residual': 'CORRESP/UPLOAD relevance remains unknown; no filing-duty completeness assumption is made.'}


def load_frozen_protocol(root: Path, *, first_binding: str, ledger_binding: str) -> tuple[dict, str]:
    """Read the registered protocol once; its bytes, schema and prior bindings must all be the frozen ones."""
    payload, digest = read_once(confined(root, PROTOCOL_NAME))
    require(digest == FROZEN_PROTOCOL_SHA256, f'protocol bytes are not the frozen registration (found {digest})')
    protocol = json.loads(payload)
    require(protocol.get('schema_version') == PROTOCOL_SCHEMA, 'unexpected protocol schema')
    require(first_binding == ledger_binding == digest, 'protocol differs from first-packet or ledger binding')
    return protocol, digest


def first_checkpoint_clocks(receipts: list[dict]) -> dict[str, str]:
    """Re-verify the retained first-checkpoint GET receipts and validate their own clocks."""
    root = WORK / 'collections' / 'ABUS2021'
    clocks = {}
    for entry in receipts:
        path = confined(root, Path(entry['path']).name)
        payload, digest = read_once(path, entry['sha256'])
        receipt = json.loads(payload)
        ends = {'retrieved_at': receipt['retrieved_at']} if receipt.get('retrieved_at') else {}
        chronology(path.name, receipt['attempted_at'], ends)
        clocks.update({f'{path.name}.{k}': v for k, v in {'attempted_at': receipt['attempted_at'], **ends}.items()})
    return clocks


def main(reviewed_at: str) -> Path:
    queue = VerifiedQueue(QUEUE, COLLECTION)
    first_bytes, first_sha = read_once(confined(HERE, FIRST_PACKET))
    require(FIRST_PACKET.endswith(first_sha + '.json'), 'first packet content address')
    first = json.loads(first_bytes)
    ledger_bytes, ledger_sha = read_once(confined(EVIDENCE, LEDGER))
    require(LEDGER.endswith(ledger_sha + '.json'), 'ledger content address')
    ledger = json.loads(ledger_bytes)
    protocol, protocol_sha = load_frozen_protocol(EVIDENCE, first_binding=first['protocol_sha256'],
                                                  ledger_binding=ledger['protocol_sha256'])
    row = ledger['rows'][0]
    require((row['row_index'], row['ticker'], row['observation_date'], row['cik']) == (1, 'ABUS', OBSERVATION, 1447028), 'ledger row 1')
    screening_bytes, screening_sha = read_once(confined(HERE, SCREENING))
    require(SCREENING.endswith(screening_sha + '.json'), 'screening content address')
    screening = json.loads(screening_bytes)
    require(screening['queue']['sha256'] == queue.queue_sha256 and screening['collection']['sha256'] == queue.collection_sha256,
            'screening bound to different SEC inputs')

    # 1. Re-cite every first-packet citation through verified bytes; require identical offsets and excerpts.
    findings = []
    for finding in first['substantive_findings']:
        new = {k: v for k, v in finding.items() if k not in ('source', 'supporting', 'census', 'control_or_exit_items_found')}
        for key in ('source', 'supporting'):
            old = finding.get(key)
            if old is None:
                continue
            olds = old if isinstance(old, list) else [old]
            fresh = [queue.cite(c['accession_number'], c['filename'], c['locator']['pattern']) for c in olds]
            for before, after in zip(olds, fresh):
                require(before['locator'] == after['locator'] and before['extracted_text_sha256'] == after['extracted_text_sha256'],
                        f"{finding['id']}: citation drifted")
            new[key] = fresh if isinstance(old, list) else fresh[0]
        findings.append(new)
    census = queue.eight_k_census()
    flagged = [c for c in census if CONTROL_OR_EXIT_ITEMS & set(c['items'])]
    require(not flagged and len(census) == 45, '8-K census changed; reassess')
    findings[[f['id'] for f in findings].index('F8-8K-item-census')].update(census=census, control_or_exit_items_found=flagged)

    # 2. Issuer archive: re-verify raw bytes, identity, SEC comparison and full-body term screen.
    collection_path = confined(HERE, ISSUER_COLLECTION)
    archive, archive_clocks, archive_sha = verify_archive_collection(collection_path)  # every page/attempt clock, raw byte, identity
    archive_root = collection_path.parent
    patterns = {name: re.compile(expr, re.I) for name, expr in TERMS.items()}
    bodies, clocks = [], {f'issuer_archive.{k}': v for k, v in archive_clocks.items()}
    for body in archive['bodies']:
        require(body['status'] == 'captured_identity_verified', f"{body['url']}: not captured/verified")
        payload, _ = read_once(confined(archive_root, body['raw_relative_path']), body['source_sha256'])
        parsed = parse_body(payload, body)
        require(parsed['identity_verified'] and parsed['body_text_sha256'] == body['body']['body_text_sha256'], f"{body['url']}: reparse differs")
        text = clean(Document(payload).root.find(cls='node__content')[0])
        hits = {name: len(p.findall(text)) for name, p in patterns.items() if p.search(text)}
        comparison = compare_release(text, queue.exhibits_near(body['date']))
        entry = {'date': body['date'], 'title': body['title'], 'url': body['url'], 'source_sha256': body['source_sha256'],
                 'retrieved_at': body['retrieved_at'], 'body_text_sha256': parsed['body_text_sha256'],
                 'body_characters': parsed['body_characters'], 'issuer_ticker_tag_present': parsed['issuer_ticker_tag_present'],
                 'distribution_dateline': parsed['distribution_dateline'], 'term_hits': hits, 'sec_comparison': comparison}
        if comparison['status'] == 'matched_sec_exhibit':
            entry['review'] = 'Matching dated SEC EX-99 exhibit was within the first-packet SEC review; full issuer body term-screened.'
        else:
            label = classify_unmatched(body['title'])
            entry['review'] = {'category': label, 'reading': UNMATCHED_READING[label],
                               'method': 'Full-body term screen plus manual reading of the release text before the boilerplate company description.'}
        if hits:
            entry['hit_disposition'] = ('2020-03-05 business_combination hits describe the historical acquisition accounting '
                                        '(IPR&D/goodwill from the business combination that formed Arbutus); not an event.')
            require(set(hits) == {'business_combination'} and body['date'] == '2020-03-05', 'unexpected term hit requires review')
        clocks[f"issuer_body_{body['date']}_{sha256(body['url'].encode())[:8]}"] = body['retrieved_at']
        bodies.append(entry)
    require(len(bodies) == 60 and sum(b['date'] <= '2020-12-31' for b in bodies) == 23
            and sum('2021' == b['date'][:4] for b in bodies) == 32 and sum(b['date'] >= '2022-01-01' for b in bodies) == 5,
            'issuer body window counts changed')

    # 3. Original filing-price lead (public source facts; not a rating or a cutoff quote).
    price_leads = []
    for accession, filename, pattern, day, price in [
            ('0001104659-20-100169', 'tm2029497-1_s3.htm', r'On August 27, 2020, the last reported sale price', '2020-08-27', 2.92),
            ('0001447028-20-000121', 'a2020-0875mmatm424b5prosupp.htm', r'On August 6, 2020, the last reported sale price', '2020-08-06', 4.37),
            ('0001447028-20-000124', 'a2020-0875mmatm424b5prosupp.htm', r'On August 6, 2020, the last reported sale price', '2020-08-06', 4.37)]:
        cite = queue.cite(accession, filename, pattern, 260)
        require(f'${price:.2f}' in cite['excerpt'], f'{accession}: price text changed')
        price_leads.append({**cite, 'price_date': day, 'last_reported_sale_price_usd': price, 'venue': 'Nasdaq Global Select Market',
                            'days_stale_at_observation': (date.fromisoformat(OBSERVATION) - date.fromisoformat(day)).days})
    require(price_leads[0]['days_stale_at_observation'] == 127 and price_leads[1]['days_stale_at_observation'] == 148, 'staleness arithmetic')

    interruption_bytes, interruption_sha = read_once(INTERRUPTION)
    interruption = json.loads(interruption_bytes)
    clocks.update(protocol_registered_at=protocol['registered_at'], first_packet_reviewed_at=first['reviewed_at'],
                  sec_queue_built_at=queue.queue['built_at'], issuer_collection_completed_at=archive['completed_at'],
                  interruption_at=interruption['interrupted_at'])
    clocks.update(first_checkpoint_clocks(first['sources']['issuer_archive_get_receipts']))
    reviewed = review_clock(reviewed_at, not_before=clocks)

    first_receipts = [{k: r[k] for k in ('path', 'sha256', 'url', 'http_status', 'error')} for r in first['sources']['issuer_archive_get_receipts']]
    packet = {
        'schema_version': 'ma-evidence-abus2021-partial-review-v2',
        'supersedes': {'relative_path': FIRST_PACKET, 'sha256': first_sha, 'builder': 'build_abus_2021_packet.py (unchanged, sha256 74e1c64a...)',
                       'status': 'retained_history_partial_review'},
        'supersedes_v2': {'relative_path': 'abus-2021-partial-review-v2-4bcff2038f19dac3e58ddc6e3b0ed5b8873c2c13057661239f100746ea17325d.json',
                          'status': 'retained_history_built_without_frozen_protocol_or_complete_archive_clock_guards',
                          'issuer_collection': 'issuer-archive-collection-b5de0f89... (retained; same bodies, older collector code basis)'},
        'issuer': first['issuer'], 'observation_at': first['observation_at'], 'information_cutoff_at': first['information_cutoff_at'],
        'horizon_end_at': first['horizon_end_at'], 'horizon_days': 365, 'protocol_sha256': protocol_sha,
        'ledger': {'relative_path': LEDGER, 'sha256': ledger_sha, 'row_index': 1},
        'reviewer': 'Claude Opus 5.5 (claude-opus-5-5), Claude Code session eab10226-e465-4fd6-877d-68427f394405; agent review, not independent human review',
        'reviewed_at': reviewed, 'review_clock_basis': 'measured UTC at packet build; validated not future and not before any represented source clock',
        'represented_source_clocks_checked': len(clocks),
        'sources': {'sec_collection': {'path': str(COLLECTION), 'sha256': queue.collection_sha256},
                    'sec_queue': {'path': str(QUEUE), 'sha256': queue.queue_sha256},
                    'sec_screening_receipt': {'relative_path': SCREENING, 'sha256': screening_sha},
                    'issuer_archive_collection': {'relative_path': ISSUER_COLLECTION, 'sha256': archive_sha}},
        'substantive_findings_sec': findings,
        'issuer_archive': {
            'provider_host': archive['host'], 'host_basis': 'Issuer-operated Nasdaq IR (nir-widget) publisher host; branded Arbutus archive, canonical URL on the same host; normal public URL, no authentication or protection workaround.',
            'inventory_counts': {str(p['archive_year']): p['entry_count'] for p in archive['pages']},
            'year_pages': [{k: p[k] for k in ('archive_year', 'source_uri', 'source_sha256', 'retrieved_at', 'selected_year_verified', 'next_url')} for p in archive['pages']],
            'bodies_selected': len(bodies), 'bodies_captured_identity_verified': len(bodies),
            'sec_matched': sum(b['sec_comparison']['status'] == 'matched_sec_exhibit' for b in bodies),
            'issuer_only': sum(b['sec_comparison']['status'] != 'matched_sec_exhibit' for b in bodies),
            'bodies': bodies,
            'finding': 'No release among 60 dated issuer bodies (23 in 2020, 32 in 2021, 5 in 2022Q1) announces a definitive >50% control agreement, pending transaction, tender/exchange offer, strategic-alternatives process, listing exit or insolvency. 2021 licence/collaboration releases (Qilu, Antios, Vaccitech, X-Chem/Proteros) are asset or collaboration events.',
            'limitations': ['Current publisher listing and current bodies only; archive completeness, removed releases and original body versions are not established.',
                            'PDF versions, embedded images and linked documents (e.g. the Moderna complaint) were not captured.',
                            'No release body publication time beyond the displayed date is established.',
                            'Bodies dated after 2022-03-31 in the 2022 inventory were not fetched and supply no facts.']},
        'collection_attempt_history': {
            'first_checkpoint_failures': first_receipts,
            'interrupted_urllib_collector': {'interruption_receipt_sha256': interruption_sha, 'interrupted_at': interruption['interrupted_at'],
                                             'disclosure': 'The first version of scripts/collect_ma_issuer_archive.py (urllib transport) ran about six minutes and held body-attempt failures in memory until the end; the primary interrupted it. Its individual attempt receipts (about eight body requests per the primary) were never written and are not reconstructed. Only the four copied archive/year pages from that run exist.'},
            'changed_hypothesis': 'Transport changed from urllib to the ordinary requests client with the same honest User-Agent after a primary requests GET of the first body returned 200 (47,520 bytes); one request per URL, no retries.'},
        'excluded_forms': excluded_form_adjudication([confined(ORIGINAL, f'data/history/panel_seed/regulatory_inventory/ABUS/ABUS_{span}.json')
                                                      for span in ('2020-01-01_2020-12-31', '2021-01-01_2021-12-31', '2022-01-01_2022-03-31')]),
        'valuation_source_lead': {
            'status': 'original_filing_price_disclosure_lead_not_a_rating',
            'leads': price_leads,
            'notes': ['Both 424B5 accessions contain the identical prospectus supplement document.',
                      'Filing-disclosed last sale prices dated 127 and 148 days before the observation; not a December 31 quote and not combined with share counts of other dates.',
                      'Current-vendor bars remain feasibility-only with original_vendor_vintage_archived false.',
                      'Shares, cash, debt, rights and a dated comparable framework are still required before any valuation rating.']},
        'pending_baseline_partial': first['pending_baseline_partial'] | {'issuer_2020_releases_reviewed': True},
        'membership_evidence': first['membership_evidence'], 'financial_custody': first['financial_custody'],
        'outcome_summary': {
            'qualifying_control_event_found_in_reviewed_scope': False, 'censoring_event_found_in_reviewed_scope': False,
            'interpretation': 'Within the reviewed SEC text and the recovered issuer release archive, no qualifying event was found. This remains a partial finding, not a negative label.'},
        'gates': {
            'reduced': ['designated_issuer_press_release_archive: 60/60 in-window dated bodies captured and identity-verified from the current publisher archive; completeness/version still unproven',
                        'excluded_forms: relevance adjudicated per form class; CORRESP/UPLOAD relevance unknown and contents unreviewed'],
            'remaining': ['graphic_visual_review_not_performed: 623 SEC graphic payloads (583 unique decoded); issuer-page images not reviewed',
                          'unsupported_format_and_empty_extraction_payloads_unreviewed: 268 + 98',
                          'incorporated_reference_review_not_performed',
                          'accession_original_version_judgments_not_made; as_accepted_byte_identity_verified false',
                          'issuer_release_original_version_and_archive_completeness_unverified',
                          'per_document_subject_identity_review_not_performed (SEC)',
                          'issuer_pre2020_pending_baseline_review_not_performed',
                          'membership_interval_not_adjudicated_or_admitted',
                          'complete_sec_submission_outcome_review_and_historical_timing_receipt_not_produced']},
        'next_missing_original_source': 'Visual review of 583 unique decoded SEC graphics and format-specific review of 366 unsupported/empty payloads; per-accession original-version judgments; pre-2020 pending-transaction baseline.',
        'tool_basis_original_unpublished': {p: sha256((ORIGINAL / p).read_bytes()) for p in TOOL_FILES},
        'tool_basis_new': {p: sha256((REPO / p).read_bytes()) for p in NEW_CODE} | {
            'data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet_v2.py': sha256(Path(__file__).read_bytes())},
        'outcome_label': None, 'label_admission_allowed': False, 'outcome_review_complete': False, 'new_observation_staged': False,
        'independent_human_review': False, 'as_accepted_byte_identity_verified': False, 'historical_original_vintage_archived': False,
        'ordinal_ratings_assigned': False}
    payload = (json.dumps(packet, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
    out = HERE / f'abus-2021-partial-review-v2-{sha256(payload)}.json'
    out.write_bytes(payload)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-at', required=True, help='measured UTC review time (e.g. from `date -u`)')
    print(main(parser.parse_args().reviewed_at))
