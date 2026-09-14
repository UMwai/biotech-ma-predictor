"""Synthetic integrity cases; fixtures are never acquisition evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from scripts.collect_issuer_archives import Document, clean
from src.research.regulatory_corpus import (
    EXCLUDED_FORMS, _inventory_page, _navigation, bind_historical_timing, verify_regulatory_review,
)


NOW = datetime(2026, 9, 8, 21, tzinfo=timezone.utc)
REVIEWED = '2026-09-08T20:00:00+00:00'
RETRIEVED = '2026-09-08T19:00:00+00:00'


def save(path, value):
    raw = (json.dumps(value, indent=2) + '\n').encode()
    path.write_bytes(raw)
    return {'source_relative_path': path.name, 'source_sha256': hashlib.sha256(raw).hexdigest()}


def raw_source(root, name, payload, uri):
    raw = payload.encode()
    (root / name).write_bytes(raw)
    return {'source_relative_path': name, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'source_bytes': len(raw), 'url': uri, 'resolved_url': uri, 'retrieved_at': RETRIEVED}


@pytest.fixture
def evidence(tmp_path):
    sources = tmp_path / 'SYNTH_sources'
    sources.mkdir()
    pages, inventory_rows, parent_filings, documents, annotations = [], [], [], [], []
    for year in (2020, 2021, 2022):
        published = f'{year}-02-15'
        accession = f'0000000123-{str(year)[2:]}-000001'
        base = f'https://ir.synthetic.test/filings/content/{accession}/'
        uri = base + 'filing.htm'
        exhibit = base + 'ex991.htm'
        index = f'https://ir.synthetic.test/filings?year={year}'
        html = (f'<select id="year"><option selected>{year}</option></select>'
                '<table class="spr-ir-sec-filings"><tr>'
                f'<td>02/15/{str(year)[2:]}</td><td>8-K</td><td><a class="doc-title" href="{uri}">Form 8-K</a></td>'
                '</tr></table><div class="pagination-wrapper"><a aria-current="page">Page 1</a></div>')
        page = raw_source(sources, f'index{year}.html', html, index)
        rows, pager = _inventory_page(html.encode(), index, year, 1)
        page.update(pager, archive_year=year)
        pages.append(page)
        inventory_rows.extend(rows)
        nav = (f'<div id="sec-filing-header--document-box"><nav aria-label="SEC Filing Documents"><a href="{uri}">8-K »</a>'
               f'<a href="{exhibit}">EX-99.1 »</a></nav></div>')
        parent_raw = nav + '<article id="document-wrap">SYNTH Inc. Form 8-K. This synthetic filing reports ordinary financial results for a unit test.</article>'
        entries = _navigation(parent_raw.encode(), rows[0])
        for entry in entries:
            body = parent_raw if entry['document_url'] == uri else nav + '<article id="document-wrap">Synthetic exhibit99.1 supplies ordinary earnings. This is only a test fixture, never real history.</article>'
            receipt = raw_source(sources, f'{year}-' + entry['document_url'].split('/')[-1], body, entry['document_url'])
            doc = {**entry, **receipt, 'status': 'archived'}
            documents.append(doc)
            text = clean(Document(body.encode()).root.find(ident='document-wrap')[0])
            annotations.append({'document_url': entry['document_url'], 'accession_number': accession,
                'publication_date': published, 'reviewed_at': REVIEWED,
                'extracted_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'qualifying_control_event_found': False, 'censoring_event_found': False,
                'trigger_context_review_complete': True, 'version_status': 'verified_original',
                'evidence_paraphrase': 'Synthetic non-event for integrity testing only.',
                'original_version_evidence': {
                    'source_uri': entry['document_url'],
                    'immutable_document_uri': f'https://www.sec.gov/Archives/edgar/data/123/{accession.replace("-", "")}/{entry["document_url"].split("/")[-1]}',
                    'source_sha256': receipt['source_sha256'], 'source_locator': 'Synthetic accession identity'}})
        parent_filings.append({'parent_document_url': uri, 'accession_number': accession,
            'documents': entries, 'publisher_navigation_source_sha256': documents[-2]['source_sha256']})
    inventory = {'schema_version': 'issuer-regulatory-inventory-v1', 'issuer': 'SYNTH',
        'inventory_complete': True, 'retrieved_at': RETRIEVED, 'pages': pages,
        'all_form_inventory': inventory_rows, 'excluded_form_types': sorted(EXCLUDED_FORMS),
        'required_material_documents': inventory_rows}
    accession_docs = {'issuer': 'SYNTH', 'all_designated_html_documents_archived': True,
                      'parent_filings': parent_filings, 'documents': documents}
    review = {'schema_version': 'issuer-regulatory-outcome-review-v1', 'issuer': {'ticker': 'SYNTH', 'cik': 123},
        'observation_at': '2021-01-01T00:00:00Z', 'horizon_end_at': '2022-01-01T00:00:00Z',
        'inventory_start_date': '2020-01-01', 'inventory_end_date': '2022-03-31',
        'reviewed_at': REVIEWED, 'reviewer': 'synthetic-test-reviewer', 'source_directory': sources.name,
        'full_text_review_complete': True, 'all_trigger_contexts_reviewed': True, 'censoring_review_complete': True,
        'known_missing_sources': False, 'qualifying_control_event_found': False, 'censoring_event_found': False,
        'original_sec_document_bytes_archived': False, 'source_content_format': 'issuer_accession_filing_mirror_html',
        'scope': 'Synthetic current designated issuer accession archive.',
        'removed_page_limitations': 'Current inventory cannot prove historical absence of removal.',
        'source_version_limitations': 'Mirror presentation bytes are not SEC HTML bytes.',
        'inventory_receipt': save(tmp_path / 'inventory.json', inventory),
        'documents_receipt': save(tmp_path / 'documents.json', accession_docs), 'document_reviews': annotations}
    path = tmp_path / 'review.json'
    save(path, review)
    return path


def change(evidence, fn):
    review = json.loads(evidence.read_bytes())
    fn(review)
    save(evidence, review)


def change_receipt(evidence, key, fn):
    review = json.loads(evidence.read_bytes())
    path = evidence.parent / review[key]['source_relative_path']
    obj = json.loads(path.read_bytes())
    fn(obj)
    review[key] = save(path, obj)
    save(evidence, review)


def test_replays_actual_inventory_bytes_exhibits_and_distinct_review_clock(evidence):
    result = verify_regulatory_review(evidence, now=NOW)
    assert result['verified_filing_accessions'] == 3
    assert result['verified_document_bodies'] == 6
    assert result['reviewed_at'].year == 2026


def test_tampered_raw_source_rejected(evidence):
    p = evidence.parent / 'SYNTH_sources/index2021.html'
    p.write_bytes(p.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='source hash'):
        verify_regulatory_review(evidence, now=NOW)


def test_missing_source_never_becomes_empty_negative(evidence):
    (evidence.parent / 'SYNTH_sources/2021-ex991.htm').unlink()
    with pytest.raises(FileNotFoundError):
        verify_regulatory_review(evidence, now=NOW)


def test_material_document_cannot_be_removed_with_rehashed_inventory(evidence):
    change_receipt(evidence, 'inventory_receipt', lambda r: r['required_material_documents'].pop())
    with pytest.raises(ValueError, match='material document selection'):
        verify_regulatory_review(evidence, now=NOW)


def test_rehashed_document_receipt_cannot_omit_exhibit(evidence):
    change_receipt(evidence, 'documents_receipt', lambda r: r['documents'].pop())
    with pytest.raises(ValueError, match='filing or exhibit missing'):
        verify_regulatory_review(evidence, now=NOW)


def test_missing_inventory_year_rejected(evidence):
    change_receipt(evidence, 'inventory_receipt', lambda r: r['pages'].pop(1))
    with pytest.raises(ValueError, match='omits a coverage year'):
        verify_regulatory_review(evidence, now=NOW)


@pytest.mark.parametrize('value', [None, 0, 'false', True])
def test_unknown_or_positive_finding_is_not_negative(evidence, value):
    change(evidence, lambda r: r['document_reviews'][0].update(qualifying_control_event_found=value))
    with pytest.raises(ValueError, match='unknown or contradictory'):
        verify_regulatory_review(evidence, now=NOW)


def test_old_publisher_date_cannot_hide_unknown_original_version(evidence):
    change(evidence, lambda r: r['document_reviews'][0].update(version_status='current_publisher_copy'))
    with pytest.raises(ValueError, match='original-version'):
        verify_regulatory_review(evidence, now=NOW)


def test_forged_historical_review_time_is_rejected(evidence):
    change(evidence, lambda r: r.update(reviewed_at='2022-03-31T00:00:00Z'))
    with pytest.raises(ValueError, match='coverage maturity'):
        verify_regulatory_review(evidence, now=NOW)


def test_copied_wrong_document_text_hash_rejected(evidence):
    change(evidence, lambda r: r['document_reviews'][0].update(extracted_text_sha256='0'*64))
    with pytest.raises(ValueError, match='full-text extraction'):
        verify_regulatory_review(evidence, now=NOW)


def test_original_sec_identity_cannot_silently_switch_cik(evidence):
    change(evidence, lambda r: r['document_reviews'][0]['original_version_evidence'].update(
        immutable_document_uri=r['document_reviews'][0]['original_version_evidence']['immutable_document_uri'].replace('/data/123/', '/data/456/')))
    with pytest.raises(ValueError, match='different regulatory filer CIK'):
        verify_regulatory_review(evidence, now=NOW)


def test_legitimate_other_filer_requires_source_bound_subject_identity(evidence):
    review = json.loads(evidence.read_bytes())
    annotation = review['document_reviews'][0]
    version = annotation['original_version_evidence']
    version['immutable_document_uri'] = version['immutable_document_uri'].replace('/data/123/', '/data/456/')
    annotation.update(document_filer_cik=456, subject_identity_evidence={
        'source_uri': annotation['document_url'], 'source_sha256': version['source_sha256'],
        'source_locator': 'Synthetic other-filer document expressly identifies this target issuer.'})
    save(evidence, review)
    assert verify_regulatory_review(evidence, now=NOW)['cik'] == 123


def add_embedded_exhibit(evidence):
    review = json.loads(evidence.read_bytes())
    path = evidence.parent / review['documents_receipt']['source_relative_path']
    docs = json.loads(path.read_bytes())
    body = next(d for d in docs['documents'] if d['publication_date'] == '2021-02-15' and d['document_type'] == '8-K')
    raw_path = evidence.parent / review['source_directory'] / body['source_relative_path']
    raw = raw_path.read_text().replace('</article>', '<table><tr><td>99.2</td><td>Embedded supplemental release, included below.</td></tr></table>'
        '<p>Exhibit99.2: Synthetic additional ordinary results; this entire statement is part of this test source body.</p></article>')
    raw_path.write_text(raw)
    body.update(source_sha256=hashlib.sha256(raw.encode()).hexdigest(), source_bytes=len(raw.encode()))
    parent = next(p for p in docs['parent_filings'] if p['parent_document_url'] == body['document_url'])
    parent['publisher_navigation_source_sha256'] = body['source_sha256']
    annotation = next(a for a in review['document_reviews'] if a['document_url'] == body['document_url'])
    text = clean(Document(raw.encode()).root.find(ident='document-wrap')[0])
    annotation['extracted_text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    annotation['original_version_evidence']['source_sha256'] = body['source_sha256']
    review['documents_receipt'] = save(path, docs)
    save(evidence, review)
    return {'parent_document_url': body['document_url'], 'exhibit_number': '99.2',
        'containing_document_url': body['document_url'], 'source_sha256': body['source_sha256'],
        'extracted_text_sha256': annotation['extracted_text_sha256'], 'source_locator': 'Embedded supplemental release after the filing body.',
        'evidence_paraphrase': 'Synthetic full supplemental text is embedded in this same reviewed document.'}


def test_listed_unlinked_exhibit_needs_bound_embedded_review(evidence):
    embedded = add_embedded_exhibit(evidence)
    with pytest.raises(ValueError, match='unlinked regulatory exhibit'):
        verify_regulatory_review(evidence, now=NOW)
    change(evidence, lambda r: r.update(embedded_exhibit_coverage=[embedded]))
    assert verify_regulatory_review(evidence, now=NOW)['verified_document_bodies'] == 6
    change(evidence, lambda r: r['embedded_exhibit_coverage'][0].update(source_sha256='0'*64))
    with pytest.raises(ValueError, match='embedded regulatory exhibit evidence'):
        verify_regulatory_review(evidence, now=NOW)


def timing_for(result):
    sources = []
    for uri, body in result['documents'].items():
        parent = result['inventory_rows'][body['parent_document_url']]
        page = result['inventory_pages'][parent['index_url']]
        sources.append({'source_uri': uri, 'source_sha256': body['source_sha256'],
            'source_sha256_kind': 'original_document_bytes', 'source_content_format': 'issuer_accession_filing_mirror_html',
            'original_sec_document_bytes_archived': False, 'original_source_sha256': None,
            'source_family': 'regulatory_filings', 'subject_cik': 123, 'version_status': 'verified_original',
            'publication_date': body['publication_date'], 'published_at': None, 'publication_timestamp_precision': 'date',
            'publication_basis': 'regulator_acceptance', 'retrieved_at': body['retrieved_at'],
            'original_version_evidence': result['document_reviews'][uri]['original_version_evidence'],
            'publication_evidence': {'source_uri': parent['index_url'], 'source_sha256': page['source_sha256'], 'source_locator': 'Filing date row'}})
    return {'historical_evidence_timing': {'cik': 123, 'observation_at': '2021-01-01T00:00:00Z',
        'horizon_end_at': '2022-01-01T00:00:00Z', 'reviewed_at': REVIEWED,
        'coverage': {'source_sha256': result['review_sha256'], 'ascertainment_complete_at': '2022-04-01T12:00:00Z'}, 'sources': sources}}


def test_every_original_source_binds_to_effective_clock(evidence):
    result = verify_regulatory_review(evidence, now=NOW)
    label = timing_for(result)
    bind_historical_timing(label, result)
    label['historical_evidence_timing']['sources'].pop()
    with pytest.raises(ValueError, match='omits a required original'):
        bind_historical_timing(label, result)


@pytest.mark.parametrize('field,value', [('publication_date', '2020-01-01'),
    ('original_sec_document_bytes_archived', True), ('source_sha256', '0'*64),
    ('publication_timestamp_precision', 'timestamp')])
def test_historical_clock_cannot_relabel_source_dates_or_bytes(evidence, field, value):
    result = verify_regulatory_review(evidence, now=NOW)
    label = timing_for(result)
    label['historical_evidence_timing']['sources'][0][field] = value
    with pytest.raises(ValueError):
        bind_historical_timing(label, result)


def test_historical_clock_preserves_full_search_date_uncertainty(evidence):
    result = verify_regulatory_review(evidence, now=NOW)
    label = timing_for(result)
    label['historical_evidence_timing']['coverage']['ascertainment_complete_at'] = '2022-02-16T12:00:00Z'
    with pytest.raises(ValueError, match='inventory-end date uncertainty'):
        bind_historical_timing(label, result)
