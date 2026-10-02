"""Verified-byte citation helpers for source-review packets.

Every passage, census and comparison is computed from extracted text whose bytes
were read once, confined to the queue root and checked against the queue hash.
Helpers locate evidence; judgments stay with the named reviewer.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.ma_evidence_io import confined, read_once, require  # noqa: E402

CONTROL_OR_EXIT_ITEMS = {'1.02', '2.01', '3.01', '3.03', '5.01', '5.03'}


class VerifiedQueue:
    """Read-once view of a content-addressed SEC review queue and its collection."""

    def __init__(self, queue_path: Path, collection_path: Path):
        queue_bytes, self.queue_sha256 = read_once(queue_path)
        require(queue_path.stem.endswith(self.queue_sha256), 'queue is not content-addressed')
        collection_bytes, self.collection_sha256 = read_once(collection_path)
        self.queue, self.collection = json.loads(queue_bytes), json.loads(collection_bytes)
        require(self.queue['collection_sha256'] == self.collection_sha256, 'queue binds a different collection')
        self.root = queue_path.parent
        self.docs = {(d['accession_number'], d['filename']): d for d in self.queue['documents']}
        self.accessions = {a['accession_number']: a for a in self.collection['accessions']}

    def text(self, accession: str, filename: str) -> tuple[str, dict]:
        doc = self.docs[(accession, filename)]
        require(bool(doc.get('extracted_text')), f'{filename}: no saved extracted text')
        payload, _ = read_once(confined(self.root, doc['extracted_text']['relative_path']), doc['extracted_text']['sha256'])
        return payload.decode('utf-8'), doc

    def cite(self, accession: str, filename: str, pattern: str, width: int = 420) -> dict:
        text, doc = self.text(accession, filename)
        matches = list(re.finditer(pattern, text))
        require(bool(matches), f'{filename}: passage not found: {pattern}')
        start = matches[0].start()
        submission = self.accessions[accession]['submission']
        return {'accession_number': accession, 'filename': filename, 'document_type': doc['document_type'],
                'publication_date': doc['publication_date'], 'payload_sha256': doc['payload_sha256'],
                'extracted_text_sha256': doc['extracted_text']['sha256'],
                'whole_response_sha256': submission['source_sha256'], 'source_uri': submission['source_uri'],
                'locator': {'pattern': pattern, 'extracted_text_char_offset': start, 'match_count': len(matches)},
                'excerpt': ' '.join(text[start:start + width].split())}

    def eight_k_census(self) -> list[dict]:
        census = []
        for (accession, filename), doc in sorted(self.docs.items(), key=lambda kv: (kv[1]['publication_date'], kv[0])):
            if doc['document_type'] != '8-K' or not doc.get('extracted_text'):
                continue
            text, _ = self.text(accession, filename)
            census.append({'accession_number': accession, 'publication_date': doc['publication_date'],
                           'extracted_text_sha256': doc['extracted_text']['sha256'],
                           'items': sorted(set(re.findall(r'Item\s+(\d\.\d\d)', text)))})
        return census

    def exhibits_near(self, day: str, max_days: int = 3) -> list[tuple[dict, str]]:
        from datetime import date
        target = date.fromisoformat(day)
        found = []
        for (accession, filename), doc in self.docs.items():
            if doc['document_type'].startswith('EX-99') and doc.get('extracted_text') and \
                    abs((date.fromisoformat(doc['publication_date']) - target).days) <= max_days:
                found.append((doc, self.text(accession, filename)[0]))
        return found


def words(text: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', text.lower())


def compare_release(body_text: str, exhibits: list[tuple[dict, str]], threshold: float = 0.9) -> dict:
    """Best same-period SEC exhibit by full word-sequence similarity (mechanical, not a version judgment)."""
    body = words(body_text)
    best = None
    for doc, text in exhibits:
        other = words(text)
        matcher = difflib.SequenceMatcher(None, body, other, autojunk=False)
        covered = sum(block.size for block in matcher.get_matching_blocks())
        score = {'accession_number': doc['accession_number'], 'filename': doc['filename'],
                 'publication_date': doc['publication_date'], 'payload_sha256': doc['payload_sha256'],
                 'extracted_text_sha256': doc['extracted_text']['sha256'], 'similarity_ratio': round(matcher.ratio(), 4),
                 'issuer_words_covered': round(covered / max(1, len(body)), 4), 'issuer_words': len(body),
                 'exhibit_words': len(other)}
        if best is None or score['issuer_words_covered'] > best['issuer_words_covered']:
            best = score
    if best is None or best['issuer_words_covered'] < threshold:
        return {'status': 'no_same_period_sec_exhibit_match', 'best_candidate': best, 'threshold': threshold}
    return {'status': 'matched_sec_exhibit', **best, 'threshold': threshold}
