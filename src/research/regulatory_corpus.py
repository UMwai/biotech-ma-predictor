"""Replay explicitly scoped original-filing outcome reviews.

Issuer accession mirrors are archived presentations of a regulatory filing;
their hashes never assert byte identity with an SEC-hosted HTML document.
Current search/issuer inventories retain historical removal limitations.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

from scripts.collect_issuer_archives import Document, clean
from src.research.regulatory_inventory import require


EXCLUDED_FORMS = frozenset({'3', '3/A', '4', '4/A', '5', '5/A', '144',
    'SC 13G', 'SC 13G/A', 'SCHEDULE 13G', 'SCHEDULE 13G/A', 'CT ORDER',
    'UPLOAD', 'CORRESP', 'EFFECT', 'S-8', 'S-8 POS', 'ARS'})


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _time(value, name: str) -> datetime:
    result = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    require(isinstance(result, datetime) and result.tzinfo is not None, name + ': timezone required')
    return result.astimezone(timezone.utc)


def _day(value: str) -> date:
    result = date.fromisoformat(value)
    require(result.isoformat() == value, 'canonical regulatory publication date required')
    return result


def _bytes(root: Path, source: dict) -> bytes:
    relative = Path(source['source_relative_path'])
    path = (root / relative).resolve()
    require(not relative.is_absolute() and path.is_relative_to(root.resolve()), 'regulatory source path escapes evidence directory')
    raw = path.read_bytes()
    require(_sha(raw) == source['source_sha256'], 'regulatory source hash mismatch')
    if 'source_bytes' in source:
        require(type(source['source_bytes']) is int and len(raw) == source['source_bytes'], 'regulatory source byte count mismatch')
    return raw


def _receipt(root: Path, source: dict) -> tuple[dict, Path]:
    result = json.loads(_bytes(root, source))
    require(isinstance(result, dict), 'regulatory receipt must be an object')
    return result, (root / source['source_relative_path']).resolve()


def _mirror_identity(uri: str) -> tuple[str, str]:
    parsed = urlsplit(uri)
    match = re.search(r'/content/(\d{10}-\d{2}-\d{6})/([A-Za-z0-9][A-Za-z0-9_.-]*)$', parsed.path)
    require(parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.query and not parsed.fragment
            and not parsed.username and not parsed.password and match is not None,
            'accession-specific issuer mirror URI required')
    return match.group(1), match.group(2)


def _inventory_page(raw: bytes, url: str, year: int, page: int) -> tuple[list[dict], dict]:
    root = Document(raw).root
    selected = [clean(o) for s in root.find('select', ident='year') for o in s.find('option') if 'selected' in o.attrs]
    require(selected == [str(year)], 'regulatory archive selected-year mismatch')
    tables = root.find('table', 'spr-ir-sec-filings')
    require(len(tables) == 1, 'regulatory archive filing table missing')
    rows = []
    for tr in tables[0].find('tr'):
        cells = tr.find('td')
        if not cells:
            continue
        require(len(cells) >= 2, 'regulatory filing row truncated')
        day = datetime.strptime(clean(cells[0]), '%m/%d/%y').date()
        require(day.year == year, 'regulatory filing outside selected year')
        links = tr.find('a', 'doc-title')
        require(len(links) == 1, 'regulatory filing document link missing')
        uri = urljoin(url, links[0].attrs['href'])
        accession, _ = _mirror_identity(uri)
        rows.append({'publication_date': day.isoformat(), 'form': clean(cells[1]), 'title': clean(links[0]),
            'document_url': uri, 'accession_number': accession, 'index_url': url, 'archive_year': year, 'archive_page': page})
    links = [a for n in root.find(cls='pagination-wrapper') for a in n.find('a')]
    require([clean(a) for a in links if a.attrs.get('aria-current') == 'page'] == [f'Page {page}'],
            'regulatory archive current page mismatch')
    totals = [int(clean(a).split()[1]) for a in links if re.fullmatch(r'Page \d+', clean(a))]
    require(bool(totals), 'regulatory archive page count unavailable')
    total = max(totals)
    following = [urljoin(url, a.attrs['href']) for a in links if clean(a).startswith('Next Page')]
    require(bool(rows) and (page == total or len(rows) == 10) and len(following) == int(page < total),
            'regulatory archive pagination incomplete')
    return rows, {'page': page, 'total_pages': total, 'entry_count': len(rows), 'next_url': following[0] if following else None}


def verify_issuer_inventory(inventory: dict, sources_root: Path, *, reviewed_at: datetime,
                            start: date, end: date) -> list[dict]:
    require(inventory.get('schema_version') == 'issuer-regulatory-inventory-v1' and inventory.get('inventory_complete') is True,
            'complete issuer regulatory inventory required')
    require(inventory.get('excluded_form_types') == sorted(EXCLUDED_FORMS), 'regulatory material form exclusion policy changed')
    require(_time(inventory['retrieved_at'], 'regulatory inventory retrieval') <= reviewed_at, 'inventory follows outcome review')
    pages = inventory['pages']
    require(isinstance(pages, list) and bool(pages), 'regulatory inventory pages missing')
    rows, states = [], {}
    for source in pages:
        year, page = source['archive_year'], source['page']
        require(type(year) is int and type(page) is int, 'invalid regulatory archive page identity')
        require(_time(source['retrieved_at'], 'archive retrieval') <= reviewed_at, 'archive page follows outcome review')
        prior = states.get(year)
        require(page == (prior['page'] + 1 if prior else 1), 'regulatory archive page gap or overlap')
        if prior:
            require(source['url'] == prior['next_url'], 'regulatory archive navigation chain mismatch')
        actual, pager = _inventory_page(_bytes(sources_root, source), source['url'], year, page)
        require(all(source.get(k) == v for k, v in pager.items()), 'regulatory archive pager or count differs from source')
        if prior:
            require(prior['total_pages'] == pager['total_pages'], 'regulatory archive total changed between pages')
        states[year] = pager
        rows.extend(actual)
    require(all(s['page'] == s['total_pages'] and s['next_url'] is None for s in states.values()),
            'regulatory archive last page missing')
    require(set(range(start.year, end.year + 1)) <= set(states), 'regulatory inventory omits a coverage year')
    require(rows == inventory['all_form_inventory'] and len({r['accession_number'] for r in rows}) == len(rows),
            'regulatory normalized inventory differs from source or has duplicate accessions')
    selected = [r for r in rows if start <= _day(r['publication_date']) <= end and r['form'] not in EXCLUDED_FORMS]
    require(selected == inventory['required_material_documents'], 'regulatory material document selection differs from fixed policy')
    require(bool(selected), 'empty material regulatory corpus cannot establish a negative')
    return selected


def _navigation(raw: bytes, parent: dict) -> list[dict]:
    roots = Document(raw).root.find(ident='sec-filing-header--document-box')
    require(len(roots) == 1, 'regulatory accession document inventory missing')
    # Single-document filings legitimately have no exhibit navigation. The
    # complete captured header still binds the parent; listed exhibits are
    # separately reconciled against links or reviewed embedded text below.
    result = [{'document_url': parent['document_url'], 'document_type': parent['form'],
        'parent_form': parent['form'], 'parent_document_url': parent['document_url'],
        'publication_date': parent['publication_date'], 'accession_number': parent['accession_number']}]
    for link in roots[0].find('a'):
        uri = urljoin(parent['document_url'], link.attrs['href'])
        if not urlsplit(uri).path.lower().endswith(('.htm', '.html')):
            require(clean(link).replace('»', '').strip() == 'Complete Filing PDF'
                    and urlsplit(uri).path.endswith('/' + parent['accession_number'] + '.pdf'),
                    'non-HTML regulatory exhibit requires explicit body support')
            continue  # explicitly identified complete-filing presentation duplicate
        accession, filename = _mirror_identity(uri)
        require(accession == parent['accession_number'], 'regulatory exhibit belongs to different accession')
        if uri in {r['document_url'] for r in result}:
            continue
        result.append({'document_url': uri, 'document_type': clean(link).replace('»', '').strip(),
            'parent_form': parent['form'], 'parent_document_url': parent['document_url'],
            'publication_date': parent['publication_date'], 'accession_number': accession})
    require(bool(result) and len({r['document_url'] for r in result}) == len(result), 'empty or duplicate accession document inventory')
    require(any(r['document_url'] == parent['document_url'] and r['document_type'] == parent['form'] for r in result),
            'parent regulatory filing missing from accession document inventory')
    return result


def _listed_exhibits(raw: bytes) -> set[str]:
    """Read exhibit-number cells, including unlinked exhibits in a filing."""
    roots = Document(raw).root.find(ident='document-wrap')
    require(len(roots) == 1, 'regulatory filing content missing')
    result = set()
    for table in roots[0].find('table'):
        for row in table.find('tr'):
            cells = row.find('td')
            if len(cells) < 2:
                continue
            first = clean(cells[0]).strip(' *+†#')
            if re.fullmatch(r'\d{1,3}\.\d+', first) and any(len(clean(c)) > 10 for c in cells[1:]):
                result.add(first)
    return result


def verify_regulatory_review(path: Path, *, now: datetime | None = None) -> dict:
    raw = path.read_bytes()
    review = json.loads(raw)
    require(review.get('schema_version') == 'issuer-regulatory-outcome-review-v1', 'unsupported regulatory outcome review')
    now = _time(now or datetime.now(timezone.utc), 'now')
    reviewed = _time(review['reviewed_at'], 'regulatory review')
    require(reviewed <= now, 'regulatory review is in the future')
    require(isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip()), 'regulatory reviewer required')
    issuer = review['issuer']
    require(type(issuer['cik']) is int and issuer['cik'] > 0 and isinstance(issuer['ticker'], str), 'regulatory issuer identity invalid')
    observation = _time(review['observation_at'], 'regulatory observation')
    horizon = _time(review['horizon_end_at'], 'regulatory horizon')
    start, end = _day(review['inventory_start_date']), _day(review['inventory_end_date'])
    require(observation < horizon and start <= observation.date() and end >= horizon.date(), 'regulatory corpus does not span outcome window')
    require(datetime.combine(end, datetime.min.time(), timezone.utc) + timedelta(hours=36) <= reviewed,
            'regulatory review precedes full coverage maturity')
    for field in ('full_text_review_complete', 'all_trigger_contexts_reviewed', 'censoring_review_complete'):
        require(review.get(field) is True, 'incomplete regulatory outcome review: ' + field)
    for field in ('known_missing_sources', 'qualifying_control_event_found', 'censoring_event_found'):
        require(review.get(field) is False, 'unknown or contradictory regulatory outcome: ' + field)
    require(review.get('original_sec_document_bytes_archived') is False, 'issuer mirror cannot assert archived original SEC bytes')
    require(review.get('source_content_format') == 'issuer_accession_filing_mirror_html', 'explicit accession mirror format required')
    for field in ('scope', 'removed_page_limitations', 'source_version_limitations'):
        require(isinstance(review.get(field), str) and bool(review[field].strip()), 'regulatory source limitations required: ' + field)
    source_directory = Path(review['source_directory'])
    sources_root = (path.parent / source_directory).resolve()
    require(not source_directory.is_absolute() and sources_root.is_relative_to(path.parent.resolve()), 'regulatory source directory escapes evidence root')
    inventory, _ = _receipt(path.parent, review['inventory_receipt'])
    documents, _ = _receipt(path.parent, review['documents_receipt'])
    require(inventory['issuer'] == issuer['ticker'] == documents['issuer'], 'regulatory inventory issuer mismatch')
    selected = verify_issuer_inventory(inventory, sources_root, reviewed_at=reviewed, start=start, end=end)
    require(documents.get('all_designated_html_documents_archived') is True, 'regulatory filing/exhibit archive incomplete')
    bodies = documents['documents']
    require(len({b['document_url'] for b in bodies}) == len(bodies), 'duplicate regulatory filing or exhibit body')
    by_uri = {b['document_url']: b for b in bodies}
    parents = documents['parent_filings']
    require(len(parents) == len(selected) and {p['parent_document_url'] for p in parents} == {r['document_url'] for r in selected},
            'regulatory parent filing inventory mismatch')
    expected, embedded_required = [], set()
    for parent in selected:
        body = by_uri.get(parent['document_url'])
        require(body is not None, 'selected regulatory filing body missing')
        navigation = _navigation(_bytes(sources_root, body), parent)
        saved = next(p for p in parents if p['parent_document_url'] == parent['document_url'])
        require(saved['documents'] == navigation and saved['accession_number'] == parent['accession_number']
                and saved['publisher_navigation_source_sha256'] == body['source_sha256'], 'regulatory exhibit inventory differs from publisher navigation')
        if parent['form'].startswith('8-K'):
            listed = _listed_exhibits(_bytes(sources_root, body))
            linked = {r['document_type'].removeprefix('EX-') for r in navigation}
            embedded_required.update((parent['document_url'], number) for number in listed - linked)
        expected.extend(navigation)
    require(len(expected) == len(bodies) and {d['document_url'] for d in expected} == set(by_uri),
            'regulatory required filing or exhibit missing or extra')
    annotations = review['document_reviews']
    require(len(annotations) == len(bodies) and {r['document_url'] for r in annotations} == set(by_uri),
            'regulatory filing or exhibit review missing or duplicate')
    annotation_by_uri = {r['document_url']: r for r in annotations}
    require(len(annotation_by_uri) == len(annotations), 'duplicate regulatory document review')
    for entry in expected:
        body, annotation = by_uri[entry['document_url']], annotation_by_uri[entry['document_url']]
        require(body.get('status') == 'archived' and all(body.get(k) == v for k, v in entry.items()), 'regulatory document metadata mismatch')
        require(body.get('url') == entry['document_url'] and body.get('resolved_url') == entry['document_url'],
                'regulatory mirror redirected to a different document')
        payload = _bytes(sources_root, body)
        nodes = Document(payload).root.find(ident='document-wrap')
        require(len(nodes) == 1, 'regulatory mirror original filing content missing')
        text = clean(nodes[0])
        require(len(text) >= 50 and _sha(text.encode()) == annotation['extracted_text_sha256'], 'regulatory full-text extraction mismatch')
        for key in ('document_url', 'accession_number', 'publication_date'):
            require(annotation[key] == entry[key], 'regulatory review document identity/date mismatch')
        annotation_at = _time(annotation['reviewed_at'], 'regulatory document review')
        require(datetime.combine(_day(entry['publication_date']), datetime.min.time(), timezone.utc) + timedelta(hours=36)
                <= _time(body['retrieved_at'], 'regulatory body retrieval') <= annotation_at <= reviewed,
                'regulatory document publication/retrieval/review chronology mismatch')
        for field in ('qualifying_control_event_found', 'censoring_event_found'):
            require(annotation.get(field) is False, 'unknown or contradictory regulatory document outcome')
        require(annotation.get('trigger_context_review_complete') is True and annotation.get('version_status') == 'verified_original',
                'regulatory original-version or context review incomplete')
        require(isinstance(annotation.get('evidence_paraphrase'), str) and bool(annotation['evidence_paraphrase'].strip()), 'regulatory document review explanation missing')
        provenance = annotation['original_version_evidence']
        uri = urlsplit(provenance['immutable_document_uri'])
        _, filename = _mirror_identity(entry['document_url'])
        require(uri.scheme == 'https' and uri.hostname in {'www.sec.gov', 'sec.gov'} and not uri.username and not uri.password
                and not uri.query and not uri.fragment
                and re.fullmatch(r'/Archives/edgar/data/\d+/' + entry['accession_number'].replace('-', '') + '/' + re.escape(filename), uri.path),
                'regulatory original accession/document identity mismatch')
        filer_cik = int(uri.path.split('/')[4])
        if filer_cik != issuer['cik']:
            identity = annotation.get('subject_identity_evidence', {})
            require(annotation.get('document_filer_cik') == filer_cik
                    and identity.get('source_uri') == entry['document_url']
                    and identity.get('source_sha256') == body['source_sha256']
                    and isinstance(identity.get('source_locator'), str) and bool(identity['source_locator'].strip()),
                    'different regulatory filer CIK requires explicit bound subject identity evidence')
        require(provenance.get('source_uri') == entry['document_url']
                and provenance.get('source_sha256') == body['source_sha256'] and bool(provenance.get('source_locator')),
                'regulatory version evidence must bind archived accession mirror and locator')
    embedded = review.get('embedded_exhibit_coverage', [])
    require(isinstance(embedded, list) and len(embedded) == len(embedded_required)
            and {(r['parent_document_url'], r['exhibit_number']) for r in embedded} == embedded_required,
            'listed but unlinked regulatory exhibit lacks explicit embedded coverage')
    for item in embedded:
        containing = by_uri.get(item['containing_document_url'])
        require(containing is not None and containing['parent_document_url'] == item['parent_document_url'],
                'embedded regulatory exhibit belongs to different accession')
        annotation = annotation_by_uri[item['containing_document_url']]
        require(item['source_sha256'] == containing['source_sha256']
                and item['extracted_text_sha256'] == annotation['extracted_text_sha256']
                and isinstance(item.get('source_locator'), str) and bool(item['source_locator'].strip())
                and isinstance(item.get('evidence_paraphrase'), str) and bool(item['evidence_paraphrase'].strip()),
                'embedded regulatory exhibit evidence is not bound to reviewed full text')
    return {'review': review, 'review_sha256': _sha(raw), 'review_path': str(path.resolve()),
            'ticker': issuer['ticker'], 'cik': issuer['cik'], 'observation_at': observation,
            'horizon_end_at': horizon, 'reviewed_at': reviewed, 'required_documents': expected,
            'documents': by_uri, 'document_reviews': annotation_by_uri,
            'inventory_rows': {r['document_url']: r for r in selected},
            'inventory_pages': {p['url']: p for p in inventory['pages']},
            'verified_filing_accessions': len(selected), 'verified_document_bodies': len(bodies)}


def bind_historical_timing(label: dict, result: dict) -> None:
    """Bind a retrospective negative clock to every replayed original disclosure."""
    timing = label['historical_evidence_timing']
    coverage = timing['coverage']
    require(coverage['source_sha256'] == result['review_sha256'], 'historical coverage does not bind regulatory review')
    require(_time(timing['reviewed_at'], 'historical timing review') >= result['reviewed_at'], 'historical timing backdates regulatory review')
    required_ascertainment = datetime.combine(_day(result['review']['inventory_end_date']), datetime.min.time(), timezone.utc) + timedelta(hours=36)
    require(_time(coverage.get('ascertainment_complete_at'), 'historical ascertainment completion') == required_ascertainment,
            'historical ascertainment completion must preserve inventory-end date uncertainty')
    require(_time(timing['observation_at'], 'historical observation') == result['observation_at']
            and _time(timing['horizon_end_at'], 'historical horizon') == result['horizon_end_at']
            and timing['cik'] == result['cik'], 'historical regulatory issuer or window mismatch')
    sources = timing['sources']
    require(len(sources) == len(result['documents']) and {s['source_uri'] for s in sources} == set(result['documents']),
            'historical timing omits a required original filing or exhibit')
    for source in sources:
        body = result['documents'][source['source_uri']]
        annotation = result['document_reviews'][source['source_uri']]
        require(source['source_sha256'] == body['source_sha256'] and source.get('source_sha256_kind') == 'original_document_bytes'
                and source.get('source_content_format') == 'issuer_accession_filing_mirror_html'
                and source.get('original_sec_document_bytes_archived') is False
                and source.get('original_source_sha256') is None, 'historical timing misrepresents issuer mirror source bytes')
        require(source['source_family'] == 'regulatory_filings' and source['subject_cik'] == result['cik']
                and source['publication_date'] == body['publication_date'] and source.get('published_at') is None
                and source['publication_timestamp_precision'] == 'date' and source['publication_basis'] in {'regulator_acceptance', 'issuer_publication'},
                'historical original filing identity or publication timing mismatch')
        require(source.get('version_status') == 'verified_original'
                and source['original_version_evidence'] == annotation['original_version_evidence'],
                'historical original-version evidence differs from replayed review')
        parent = result['inventory_rows'][body['parent_document_url']]
        page = result['inventory_pages'][parent['index_url']]
        publication = source['publication_evidence']
        require(publication['source_uri'] == parent['index_url'] and publication['source_sha256'] == page['source_sha256']
                and bool(publication.get('source_locator')), 'historical publication evidence differs from source inventory')
        require(_time(source['retrieved_at'], 'historical source retrieval') == _time(body['retrieved_at'], 'archived source retrieval'),
                'historical filing retrieval mismatch')
