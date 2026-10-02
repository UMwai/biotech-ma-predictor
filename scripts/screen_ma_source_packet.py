#!/usr/bin/env python3
"""Replay one captured SEC submission collection and screen its extracted text.

Automated screening only: hits locate passages for substantive inspection. A
missing hit is never a negative finding, and graphics, unsupported formats and
extraction failures stay pending. Writes one deterministic content-addressed
receipt; it assigns no label and does not mark any document reviewed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ma_evidence_io import confined, read_once  # noqa: E402

SCHEMA = 'ma-evidence-sec-screening-receipt-v1'
# Control, pending-transaction and censoring vocabulary. Broad by design.
TERMS = {
    'merger_agreement': r'agreement and plan of merger|merger agreement|plan of merger',
    'arrangement': r'plan of arrangement|arrangement agreement|scheme of arrangement|amalgamation',
    'tender_or_exchange_offer': r'tender offer|exchange offer|offer to purchase',
    'acquire_company': r'acquire (?:all|the company|arbutus)|acquisition of (?:the company|arbutus|all)|to be acquired|take[- ]private|going[- ]private',
    'change_of_control': r'change (?:of|in) control',
    'business_combination': r'business combination|reverse merger|merger of equals',
    'strategic_review': r'strategic alternatives|strategic review|sale of the company|unsolicited|non-binding proposal|letter of intent',
    'controlling_holder': r'controlling (?:shareholder|stockholder)|majority (?:shareholder|stockholder|of (?:our|the) (?:outstanding )?(?:common )?shares)|schedule 13d|beneficial(?:ly)? own',
    'listing_exit': r'delist|form 25|form 15\b|deregist|suspend(?:ed)? trading|cease(?:d)? to be listed',
    'insolvency': r'bankruptcy|chapter 11|insolven|liquidation|wind(?:ing)?[- ]up|dissolution|receivership|ccaa|creditor protection',
}
WINDOWS = (('baseline', '2020-01-01', '2020-12-31'), ('outcome', '2021-01-01', '2021-12-31'),
           ('lag', '2022-01-01', '2022-03-31'))


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def window(day: str) -> str:
    for name, start, end in WINDOWS:
        if start <= day <= end:
            return name
    return 'outside'


def screen(collection_path: Path, queue_path: Path, context_chars: int = 240) -> dict:
    collection_bytes, collection_digest = read_once(collection_path)
    collection = json.loads(collection_bytes)
    root = collection_path.parent
    require(collection['schema_version'] == 'sec-complete-submission-collection-v1' and collection['collection_complete'] is True,
            'collection must be complete-submission-v1')
    replay = Counter()
    for accession in collection['accessions']:
        verified = {}
        for part in ('index', 'submission'):
            entry = accession[part]
            verified[part], _ = read_once(confined(root, entry['source_relative_path']), entry['source_sha256'], entry['byte_count'])
            replay[f'{part}_responses'] += 1
        submission = verified['submission']  # slice the same verified bytes, never a reread
        for doc in accession['embedded_documents']:
            segment = submission[doc['container_text_start']:doc['container_text_end']]
            require(sha256(segment) == doc['embedded_document_sha256'] and len(segment) == doc['embedded_document_bytes'],
                    f"{accession['accession_number']} {doc['filename']}: payload slice mismatch")
            replay['payload_slices'] += 1
    queue_bytes, queue_digest = read_once(queue_path)
    queue = json.loads(queue_bytes)
    require(queue['collection_sha256'] == collection_digest, 'queue binds a different collection')
    require(queue_path.stem.endswith(queue_digest), 'queue content address mismatch')
    qroot = queue_path.parent
    patterns = {name: re.compile(expr, re.I) for name, expr in TERMS.items()}
    documents, contexts = [], {}
    kinds = Counter()
    for doc in queue['documents']:
        kinds[(doc['review_kind'], 'extracted' if doc.get('extracted_text') else 'decoded' if doc.get('decoded_graphic') else 'none')] += 1
        record = {'accession_number': doc['accession_number'], 'filename': doc['filename'], 'sequence': doc['sequence'],
                  'document_type': doc['document_type'], 'parent_form': doc['parent_form'],
                  'publication_date': doc['publication_date'], 'window': window(doc['publication_date']),
                  'review_kind': doc['review_kind'], 'payload_sha256': doc['payload_sha256'],
                  'screened': False, 'term_hits': {}, 'context_sha256': [],
                  'pending_reason': None}
        artifact = doc['payload_artifact']
        require(artifact['sha256'] == doc['payload_sha256'], f"{doc['filename']}: queue payload hash fields disagree")
        read_once(confined(qroot, artifact['relative_path']), artifact['sha256'])
        if doc.get('extracted_text'):
            text_bytes, _ = read_once(confined(qroot, doc['extracted_text']['relative_path']), doc['extracted_text']['sha256'])
            text = text_bytes.decode('utf-8')
            record.update(screened=True, extracted_text_sha256=doc['extracted_text']['sha256'], extracted_characters=len(text))
            for name, pattern in patterns.items():
                hits = list(pattern.finditer(text))
                if not hits:
                    continue
                record['term_hits'][name] = len(hits)
                for match in hits:
                    start, end = max(0, match.start() - context_chars), min(len(text), match.end() + context_chars)
                    snippet = ' '.join(text[start:end].split())
                    digest = sha256(snippet.encode())
                    entry = contexts.setdefault(digest, {'context_sha256': digest, 'text': snippet, 'terms': [],
                                                         'occurrences': []})
                    if name not in entry['terms']:
                        entry['terms'].append(name)
                    occurrence = [doc['accession_number'], doc['filename'], start]
                    if occurrence not in entry['occurrences']:
                        entry['occurrences'].append(occurrence)
                    if digest not in record['context_sha256']:
                        record['context_sha256'].append(digest)
        elif doc.get('decoded_graphic'):
            record.update(decoded_graphic_sha256=doc['decoded_graphic']['sha256'],
                          pending_reason='graphic_visual_review_not_performed')
        else:
            record['pending_reason'] = 'extraction_error:' + doc.get('extraction_error', 'unknown')
        documents.append(record)
    by_window = Counter((d['window'], d['screened']) for d in documents)
    return {
        'schema_version': SCHEMA, 'ticker': collection['ticker'], 'cik': collection['cik'],
        'collection': {'path': str(collection_path), 'sha256': collection_digest,
                       'excluded_forms': collection['excluded_forms'], 'accessions': len(collection['accessions'])},
        'queue': {'path': str(queue_path), 'sha256': queue_digest, 'documents': len(queue['documents']),
                  'trigger_contexts': queue['trigger_context_count'], 'extractor_code_sha256': queue['extractor_code_sha256']},
        'screener_sha256': sha256(Path(__file__).read_bytes()), 'terms': TERMS, 'context_chars': context_chars,
        'replay': dict(replay), 'review_kind_counts': {f'{k[0]}:{k[1]}': v for k, v in sorted(kinds.items())},
        'window_screen_counts': {f'{k[0]}:{"screened" if k[1] else "unscreened"}': v for k, v in sorted(by_window.items())},
        'unique_decoded_graphics': len({d['decoded_graphic_sha256'] for d in documents if d.get('decoded_graphic_sha256')}),
        'distinct_contexts': len(contexts),
        'documents_with_hits': sum(bool(d['term_hits']) for d in documents),
        'semantics': 'Automated keyword screening of saved extracted text only. Not substantive review, not complete coverage of graphics/unsupported formats, and not a label.',
        'outcome_label': None, 'label_admission_allowed': False, 'outcome_review_complete': False,
        'documents': documents, 'contexts': sorted(contexts.values(), key=lambda c: c['occurrences'][0][:2] + [c['occurrences'][0][2]])}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=Path, required=True)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = screen(args.collection.resolve(), args.queue.resolve())
    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f'blocked: {exc}', file=sys.stderr)
        return 2
    payload = (json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"sec-screening-{receipt['ticker']}-{sha256(payload)}.json"
    if not path.exists():
        path.write_bytes(payload)
    require(path.read_bytes() == payload, 'existing screening receipt differs')
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
