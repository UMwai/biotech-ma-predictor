"""Replay historical source evidence and retain every frame member in coverage.

A coverage row is not a training observation. Only explicitly adjudicated rows
that pass the shared temporal contract can enter the fitted dataset.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import copy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from scripts.collect_issuer_archives import (
    Document, clean, arcutis_page, crinetics_page, codexis_page, drupal_page,
)

from src.research.financial_seed import FEATURE_UNITS, _require, _verified_bytes
from src.research.panel_financials import financials_at_cutoff, read_reviewed_financials
from src.research.regulatory_corpus import bind_historical_timing, verify_regulatory_review
from src.research.training import validate_training_data
from src.research.validation import RETROSPECTIVE_LABEL_TIMING


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read(path: Path) -> tuple[dict, str]:
    payload = path.read_bytes()
    value = json.loads(payload)
    _require(isinstance(value, dict), 'evidence document must be a JSON object')
    return value, _sha(payload)


def _time(value, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{field}: valid timestamp required') from exc
    _require(parsed.tzinfo is not None, f'{field}: timezone required')
    return parsed.astimezone(timezone.utc)


def _day(value, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{field}: ISO calendar date required') from exc
    _require(parsed.isoformat() == value, f'{field}: canonical ISO calendar date required')
    return parsed


def _ticker(value) -> str:
    _require(isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}', value),
             'invalid historical ticker')
    return value


def _cik(value) -> int:
    _require(not isinstance(value, bool) and str(value).isdigit() and 0 < int(value) < 10**10,
             'positive issuer CIK required')
    return int(value)


def _frame_members_from_source(payload: bytes) -> list[tuple[str, str, str]]:
    tables = []
    count = None
    for table in Document(payload).root.walk():
        if table.tag == 'p':
            match = re.fullmatch(r'The following (\d+) securities will be added to the Index:', clean(table))
            if match:
                count = int(match.group(1))
        if table.tag != 'table' or count is None:
            continue
        rows = [[clean(cell) for cell in row.find('td')] for row in table.find('tr')]
        if rows and rows[0] == ['EXCHANGE', 'SYMBOL', 'COMPANY NAME']:
            _require(len(rows) - 1 == count and all(len(row) == 3 for row in rows[1:]), 'malformed historical exchange table')
            tables.append([tuple(row) for row in rows[1:]])
        count = None
    _require(len(tables) == 1 and bool(tables[0]), 'unambiguous original exchange addition table required')
    return tables[0]


def _replay_inventory(collection: dict, root: Path, reviewed: datetime) -> list[dict]:
    """Reparse archived publisher pages; a rehashed edited inventory is insufficient."""
    pages = collection.get('pages')
    _require(isinstance(pages, list) and bool(pages), 'archive page inventory missing')
    issuer = collection['issuer']
    inventory, groups = [], {}
    for page in pages:
        raw = _verified_bytes(root, page['source_relative_path'], page['source_sha256'])
        _require(len(raw) == page['source_bytes'], 'archive page byte count mismatch')
        _require(_time(page['retrieved_at'], 'page retrieval') <= reviewed,
                 'archive review precedes page retrieval')
        number = page['page']
        _require(type(number) is int and number > 0, 'invalid archive page number')
        if issuer == 'ARQT':
            year = page['archive_year']
            rows, pager = arcutis_page(raw, year, number)
        elif issuer in {'CRNX', 'CDXS', 'STRO'}:
            year = None
            rows, pager = crinetics_page(raw, number) if issuer == 'CRNX' else codexis_page(raw, page['url'], number)
        else:
            year = page['archive_year']
            selectors = [s for s in Document(raw).root.find('select')
                         if any(o.attrs.get('value') == str(year) and 'selected' in o.attrs for o in s.find('option'))]
            _require(len(selectors) == 1, 'unambiguous archive year selector required')
            rows, pager = drupal_page(raw, page['url'], year, number, selectors[0].attrs['name'])
        _require(page['entry_count'] == len(rows), 'archive entry count disagrees with original page')
        for name in ('total_pages', 'total_rows'):
            if pager.get(name) is not None:
                _require(page.get(name) == pager[name], f'archive {name} disagrees with original page')
        groups.setdefault(year, []).append((page, pager))
        inventory.extend({**r, 'archive_year': year or int(r['date'][:4]), 'archive_page': number} for r in rows)
    for group in groups.values():
        ordered = sorted(group, key=lambda pair: pair[0]['page'])
        _require([p['page'] for p, _ in ordered] == list(range(1, len(group) + 1)),
                 'archive pagination has missing or duplicate pages')
        _require(all(p['total_pages'] == len(group) for p, _ in group), 'archive pagination stops before terminal page')
        for index, (page, pager) in enumerate(ordered):
            if 'next_url' in pager:
                next_page = ordered[index + 1][0] if index + 1 < len(ordered) else None
                expected_next = {next_page['url'], next_page.get('resolved_url')} if next_page else {None}
                _require(pager['next_url'] in expected_next, 'archive pagination link chain disagrees with saved pages')
    _require(len({r['url'] for r in inventory}) == len(inventory), 'duplicate original archive release URL')
    saved = collection.get('inventory')
    _require(isinstance(saved, list) and bool(saved), 'designated release inventory missing')
    projection = lambda rows: sorted((r['url'], r['date'], r['title'], r['archive_year'], r['archive_page']) for r in rows)
    _require(projection(saved) == projection(inventory), 'saved inventory differs from archived publisher pages')
    return inventory


def _body_text(payload: bytes, selector: str, body: dict | None = None) -> str:
    if selector.startswith('web-tool-lines:'):
        _require(body is not None and body.get('source_content_format') == 'web_tool_extracted_text_response'
                 and body.get('original_publisher_html_archived') is False,
                 'web representation cannot claim original publisher HTML')
        capture = json.loads(payload)
        _require(capture.get('capture_method') == 'web_tool_open_response' and capture.get('original_publisher_html') is False
                 and capture.get('source_url') == body['source_url'], 'web source representation identity mismatch')
        captured_at = capture['captured_at'].replace(' UTC', '+00:00')
        _require(_time(captured_at, 'web capture') == _time(body['retrieved_at'], 'body retrieval'),
                 'web representation retrieval timestamp mismatch')
        match = re.fullmatch(r'web-tool-lines:(\d+)-(\d+)', selector)
        _require(match is not None, 'invalid web representation selector')
        start, end = map(int, match.groups())
        lines = [(int(m.group(1)), m.group(2)) for line in capture['response'].splitlines()
                 if (m := re.match(r'^L(\d+): (.*)', line)) and start <= int(m.group(1)) <= end]
        _require(start <= end and lines and lines[0][0] == start and lines[-1][0] == end,
                 'web representation selected range is missing')
        return '\n'.join(text for _, text in lines)
    _require(body is None or body.get('source_content_format') != 'web_tool_extracted_text_response',
             'web representation requires its declared extraction format')
    _require(selector in {'#pd-content', '#main-body-container', '.post-content', 'article.full-news-article'},
             'unsupported reviewed full-article selector')
    root = Document(payload).root
    if selector.startswith('#'):
        nodes = root.find(ident=selector[1:])
    elif selector.startswith('.'):
        nodes = root.find(cls=selector[1:])
    elif re.fullmatch(r'[a-z]+\.[\w-]+', selector):
        tag, cls = selector.split('.', 1)
        nodes = root.find(tag, cls)
    else:
        raise ValueError('unsupported recorded issuer body extraction selector')
    _require(len(nodes) == 1, 'recorded issuer body selector is absent or ambiguous')
    return clean(nodes[0])


def _verify_adjudication_source(provenance: dict, history_dir: Path) -> dict:
    """Verify saved review bytes, without representing them as original HTML."""
    uri = provenance.get('source_uri', '')
    relative = provenance.get('source_relative_path')
    if relative is None and urlsplit(uri).scheme == 'file':
        parsed = urlsplit(uri)
        _require(parsed.netloc in ('', 'localhost'), 'adjudication receipt must be a local file')
        path = Path(unquote(parsed.path)).resolve()
        _require(path.is_relative_to(history_dir.resolve()), 'adjudication receipt outside history directory')
        relative = str(path.relative_to(history_dir.resolve()))
    _require(relative is not None, 'adjudication requires a locally archived source receipt')
    value = json.loads(_verified_bytes(history_dir, relative, provenance.get('source_sha256')))
    _require(isinstance(value, dict), 'adjudication review source must be a JSON object')
    return value


def _receipt_path(provenance: dict, history_dir: Path) -> Path:
    if provenance.get('source_relative_path') is not None:
        return history_dir / provenance['source_relative_path']
    return Path(unquote(urlsplit(provenance['source_uri']).path))


def verify_baseline_review(path: Path, *, now: datetime) -> dict:
    """Replay the explicitly bounded public-history baseline and supplements."""
    review, _ = _read(path)
    _require(review.get('schema_version') == 'issuer-pre2020-baseline-review-v1', 'unsupported pending-transaction baseline review')
    _require(review.get('archive_complete') is True and review.get('full_text_review_complete') is True
             and review.get('method', {}).get('all_trigger_contexts_reviewed') is True, 'incomplete pending-transaction baseline review')
    reviewed = _time(review['reviewed_at'], 'baseline review')
    _require(reviewed <= now, 'baseline review is in the future')
    root = path.parent
    collection = json.loads(_verified_bytes(root, review['collection_manifest_relative_path'], review['collection_manifest_sha256']))
    _require(collection.get('issuer') == review['issuer']['ticker'] and collection.get('archive_complete') is True,
             'pending baseline collection issuer or completeness mismatch')
    inventory = _replay_inventory(collection, root, reviewed)
    bounds = review['baseline_review']
    start, end = _day(bounds['start_date'], 'baseline start'), _day(bounds['end_date'], 'baseline end')
    _require(start <= end and datetime.combine(end, datetime.min.time(), timezone.utc) + timedelta(hours=36) <= reviewed,
             'pending baseline dates or review maturity invalid')
    for name in ('pending_qualified_target_control_transaction_found', 'qualified_target_control_event_found', 'censoring_event_found'):
        _require(bounds.get(name) is False, 'pending baseline has unknown or positive event finding')
    expected = {r['url']: r for r in inventory if start.isoformat() <= r['date'] <= end.isoformat()}
    bodies, supplements = review['body_reviews'], review.get('supplemental_body_reviews', [])
    _require(len(bodies) == review['body_count'] and len(supplements) == review.get('supplemental_body_count', 0),
             'pending baseline body count mismatch')
    _require({b['archive_url'] for b in bodies} == set(expected) and len(bodies) == len(expected),
             'pending baseline does not cover its designated inventory')
    _require(len({b['archive_url'] for b in bodies + supplements}) == len(bodies + supplements), 'duplicate pending baseline source body')
    for body in bodies + supplements:
        if body['archive_url'] in expected:
            entry = expected[body['archive_url']]
            _require((body['archive_date'], body['title']) == (entry['date'], entry['title']), 'pending baseline body metadata mismatch')
        published = _day(body['publication_date'], 'baseline body publication')
        _require(start <= published <= end, 'pending baseline body publication outside reviewed dates')
        payload = _verified_bytes(root, body['source_relative_path'], body['source_sha256'])
        _require(len(payload) == body['source_bytes'], 'pending baseline source size mismatch')
        text = _body_text(payload, body['extraction_selector'], body)
        _require(_sha(text.encode()) == body['full_text_sha256'] and len(text) == body['full_text_characters'],
                 'pending baseline full-text extraction mismatch')
        _require(body.get('publication_dateline_verified') is True and body.get('trigger_context_review_complete') is True
                 and body.get('qualified_target_control_event') is False and body.get('censoring_event') is False,
                 'pending baseline body has incomplete or contradictory event review')
        _require(_time(body['retrieved_at'], 'baseline body retrieval') <= reviewed, 'baseline review precedes body retrieval')
        original = body.get('original_archive_source')
        if original and original.get('source_sha256'):
            _verified_bytes(root, original['source_relative_path'], original['source_sha256'])
    for source in review.get('supplemental_discovery_pages', []):
        payload = _verified_bytes(root, source['source_relative_path'], source['source_sha256'])
        _require(len(payload) == source['source_bytes'] and _time(source['retrieved_at'], 'baseline discovery retrieval') <= reviewed,
                 'baseline discovery source size or clock mismatch')
    return review


def _verify_adjudication_contents(row: dict, history_dir: Path, corpus: dict | None) -> None:
    membership, label = row['membership'], row['label']
    source = _verify_adjudication_source(membership, history_dir)
    matches = [r for r in source.get('records', [source])
               if r.get('ticker') == row['ticker'] and _cik(r.get('cik')) == row['cik']]
    _require(len(matches) == 1, 'membership source does not uniquely identify adjudicated issuer')
    member = matches[0]
    for field in ('kind', 'security_type', 'biotech_eligible', 'valid_from', 'valid_until'):
        _require(membership.get(field) == member.get(field), 'adjudicated membership differs from saved review')
    source = _verify_adjudication_source(label, history_dir)
    if label['event_class'] == 'no_change_of_control_announcement':
        _require(corpus is not None and label['source_sha256'] == corpus['review_sha256'],
                 'negative adjudication requires its verified issuer/window corpus')
        _require(source['issuer']['ticker'] == row['ticker'] and _cik(source['issuer']['cik']) == row['cik']
                 and source['outcome_window']['observation_date'] == _time(row['observation_at'], 'observation').date().isoformat()
                 and source['outcome_window']['horizon_days'] == row['horizon_days'], 'negative source issuer or window mismatch')
        source_reviewed = source['reviewed_at']
        if label.get('historical_evidence_timing') is not None:
            provenance = label.get('regulatory_coverage_receipt')
            _require(isinstance(provenance, dict), 'historical negative timing requires a replayable original regulatory corpus')
            _verify_adjudication_source(provenance, history_dir)
            regulatory = verify_regulatory_review(_receipt_path(provenance, history_dir),
                                                  now=_time(label['reviewed_at'], 'label actual review'))
            _require(regulatory['review_sha256'] == provenance['source_sha256']
                     and regulatory['ticker'] == row['ticker'] and regulatory['cik'] == row['cik'],
                     'historical regulatory corpus identity or hash mismatch')
            bind_historical_timing(label, regulatory)
    elif label['event_class'] == 'change_of_control_announcement':
        events = source.get('labels', source.get('records', [source]))
        matches = [event for event in events if event.get('target_ticker') == row['ticker']
                   and _cik(event.get('target_cik')) == row['cik']
                   and event.get('announcement_date') == label.get('announcement_date')]
        _require(len(matches) == 1, 'positive source does not uniquely match issuer and announcement date')
        event = matches[0]
        _require(event.get('label') == 'definitive_change_of_control_announcement'
                 and event.get('timestamp_precision') == label.get('timestamp_precision'), 'positive source event class or precision mismatch')
        if event['timestamp_precision'] == 'timestamp':
            _require(_time(event.get('announcement_at') or event.get('announced_at'), 'source announcement') ==
                     _time(label.get('announcement_at') or label.get('announced_at'), 'adjudicated announcement'),
                     'adjudicated announcement timestamp differs from reviewed event')
        source_reviewed = event['reviewed_at']
    else:
        raise ValueError('adjudicated outcome must be an explicitly reviewed binary event class')
    _require(_time(source_reviewed, 'original actual source review') <=
             _time(label.get('reviewed_at', label['available_at']), 'label actual review') <=
             _time(label['available_at'], 'label availability'), 'adjudicated label backdates its saved actual source review')
    if row.get('risk_set_review'):
        risk_review = row['risk_set_review']
        risk_at = _time(risk_review['reviewed_at'], 'risk adjudication review')
        for provenance in [risk_review, *risk_review.get('supporting_source_receipts', [])]:
            risk = _verify_adjudication_source(provenance, history_dir)
            if risk.get('schema_version') == 'issuer-pre2020-baseline-review-v1':
                verify_baseline_review(_receipt_path(provenance, history_dir), now=risk_at)
            elif risk.get('schema_version') == 'issuer-annual-outcome-review-v1':
                verify_archive_review(_receipt_path(provenance, history_dir), now=risk_at)
            if risk.get('issuer'):
                _require(risk['issuer']['ticker'] == row['ticker'] and _cik(risk['issuer']['cik']) == row['cik'],
                         'risk source issuer differs from adjudication')
            if risk.get('reviewed_at'):
                _require(_time(risk['reviewed_at'], 'risk source review') <= risk_at,
                         'risk adjudication backdates source review')


def verify_archive_review(path: Path, *, now: datetime | None = None) -> dict:
    """Verify a saved full-text corpus review, without promoting it into a label."""
    review, digest = _read(path)
    _require(review.get('schema_version') == 'issuer-annual-outcome-review-v1', 'unsupported issuer outcome review')
    ticker, cik = _ticker(review['issuer']['ticker']), _cik(review['issuer']['cik'])
    root = path.parent
    collection = json.loads(_verified_bytes(root, review['collection_manifest_relative_path'], review['collection_manifest_sha256']))
    _require(collection.get('schema_version') == 'collected-issuer-archive-v1' and collection.get('issuer') == ticker,
             'issuer collection identity or schema mismatch')
    _require(review.get('archive_complete') is True and collection.get('archive_complete') is True,
             'incomplete designated issuer archive')
    _require(review.get('full_text_review_complete') is True and review['method'].get('all_trigger_contexts_reviewed') is True,
             'full-text screening and context review required')
    _require(len(review['body_reviews']) == review['body_count'], 'outcome body review count mismatch')
    reviewed = _time(review['reviewed_at'], 'archive review')
    _require(reviewed <= _time(now or datetime.now(timezone.utc), 'now'), 'invalid actual archive review time')
    inventory = _replay_inventory(collection, root, reviewed)
    inventory_by_url = {entry['url']: entry for entry in inventory}
    baseline, window = review['baseline_review'], review['outcome_window']
    baseline_start, baseline_end = (_day(baseline[k], f'baseline.{k}') for k in ('start_date', 'end_date'))
    observation, window_end = (_day(window[k], f'window.{k}') for k in ('observation_date', 'window_end_date'))
    horizon = window['horizon_days']
    _require(type(horizon) is int and 1 <= horizon <= 3650 and observation + timedelta(days=horizon) == window_end,
             'reviewed outcome horizon disagrees with calendar dates')
    _require(baseline_start <= baseline_end == observation - timedelta(days=1), 'baseline does not meet observation boundary')
    _require(datetime.combine(window_end, datetime.min.time(), timezone.utc) + timedelta(hours=36) <= reviewed,
             'archive review predates outcome date uncertainty and maturity')
    years = {entry['archive_year'] for entry in inventory}
    _require(set(range(baseline_start.year, window_end.year + 1)) <= years,
             'archive inventory does not cover baseline and outcome boundary years')
    urls = set()
    for body in review['body_reviews']:
        payload = _verified_bytes(root, body['source_relative_path'], body['source_sha256'])
        _require(len(payload) == body['source_bytes'], 'issuer source byte count mismatch')
        _require(body['archive_url'] not in urls, 'duplicate issuer body review')
        _require(body['archive_url'] in inventory_by_url, 'body review outside designated source inventory')
        entry = inventory_by_url[body['archive_url']]
        _require((body['archive_date'], body['title']) == (entry['date'], entry['title']),
                 'reviewed body date or title differs from archive inventory')
        urls.add(body['archive_url'])
        _require(body.get('publication_dateline_verified') is True and body.get('trigger_context_review_complete') is True,
                 'unverified dateline or event contexts')
        retrieved = _time(body['retrieved_at'], 'body retrieval')
        published = _day(body['publication_date'], 'body publication date')
        _require(datetime.combine(published, datetime.min.time(), timezone.utc) - timedelta(hours=14) <= retrieved <= reviewed,
                 'invalid publication, retrieval or actual review chronology')
        text = _body_text(payload, body['extraction_selector'], body)
        _require(len(text) == body['full_text_characters'] and _sha(text.encode()) == body['full_text_sha256'],
                 'reviewed full-text extraction differs from archived body')
        original = body.get('original_archive_source')
        if original:
            _require(original['url'] == body['archive_url'], 'replacement source has mismatched original archive URL')
            if original.get('source_sha256') is not None:
                _verified_bytes(root, original['source_relative_path'], original['source_sha256'])
            else:
                _require(original.get('review_status') == 'blocked' and bool(original.get('error')),
                         'replacement original must have archived bytes or explicit retrieval failure')
    expected = {entry['url'] for entry in inventory
                if baseline['start_date'] <= entry['date'] <= window['window_end_date']}
    _require(expected <= urls, 'designated inventory has unreviewed in-window bodies')
    _require(window['qualified_target_control_event_found'] is False and window['censoring_event_found'] is False
             and baseline['pending_qualified_target_control_transaction_found'] is False, 'review is not a negative-window candidate')
    _require(all(b['qualified_target_control_event'] is False and b['censoring_event'] is False for b in review['body_reviews']),
             'negative-window summary contradicts reviewed body')
    return {'ticker': ticker, 'cik': cik,
            'observation_date': window['observation_date'], 'body_count': review['body_count'],
            'reviewed_at': review['reviewed_at'], 'review_sha256': digest,
            'review_path': str(path), 'scope': review['source_scope'],
            'original_source_version_status': review.get('source_version_policy', {}).get('classification', 'unverified'),
            'verified_archive_pages': len(collection['pages']),
            'verified_publisher_body_documents': sum(b.get('source_content_format') != 'web_tool_extracted_text_response' for b in review['body_reviews']),
            'verified_web_response_body_documents': sum(b.get('source_content_format') == 'web_tool_extracted_text_response' for b in review['body_reviews']),
            'negative_training_label_assigned': False,
            'status': 'corpus_reviewed_not_yet_training_eligible'}


def assemble_research_panel(history_dir: Path, *, now: datetime | None = None) -> dict:
    """Construct a complete coverage ledger and strictly admitted feature panel."""
    now = _time(now or datetime.now(timezone.utc), 'now')
    seed = history_dir / 'panel_seed'
    frame, frame_hash = _read(seed / 'sampling_frame.json')
    _require(frame.get('schema_version') == 'historical-sampling-frame-v1', 'unsupported historical sampling frame')
    source, source_receipt_hash = _read(seed / 'nasdaq_source_receipt.json')
    original = _verified_bytes(seed, source['source_relative_path'], source['source_sha256'])
    _require(len(original) == source['bytes'] and source['source_sha256'] == frame['historical_sampling_frame']['source_sha256'],
             'historical frame differs from archived exchange source')
    _require(source['source_uri'] == frame['historical_sampling_frame']['source_uri'], 'historical frame source URI mismatch')
    members = frame['records']
    _require(len(members) == frame['frame_size'] and len({r['historical_ticker'] for r in members}) == len(members),
             'historical frame count or identity mismatch')
    actual_members = sorted(_frame_members_from_source(original))
    recorded_members = sorted((r['exchange'], _ticker(r['historical_ticker']), r['historical_issuer_name']) for r in members)
    _require(recorded_members == actual_members, 'historical frame members differ from original exchange table')
    dates = frame['cohort_plan']['observation_dates']
    _require(isinstance(dates, list) and bool(dates) and dates == sorted(set(dates)),
             'observation plan requires unique ordered dates')
    dates = [_day(day, 'cohort observation date').isoformat() for day in dates]
    sampling = frame['historical_sampling_frame']
    _require(sampling.get('uses_current_listing_status') is False and sampling.get('uses_future_outcomes') is False
             and sampling.get('includes_subsequently_delisted') is True, 'historical frame cannot select on current survival or future outcomes')
    _require(sampling.get('selection_basis') in {'historical_exchange_constituents', 'predeclared_historical_sampling_frame'}
             and bool(sampling.get('selection_rule')) and bool(sampling.get('source_locator')), 'historical frame selection provenance required')
    _require(_time(sampling['population_as_of_at'], 'historical population') <= _time(dates[0]+'T00:00:00Z', 'first observation'),
             'historical sampling frame follows first observation')
    _require(_time(source['retrieved_at'], 'frame source retrieval') == _time(sampling['retrieved_at'], 'sampling source retrieval')
             <= _time(sampling['reviewed_at'], 'sampling review') <= now, 'historical frame retrieval/review clock mismatch')
    horizon_days = frame['cohort_plan']['horizon_days']
    _require(type(horizon_days) is int and 1 <= horizon_days <= 3650, 'invalid cohort horizon')
    financial_paths = [history_dir / 'panel_financials' / name for name in ('financial_records.json', 'positive_financial_records.json')]
    financials = read_reviewed_financials([p for p in financial_paths if p.exists()])
    identities = {}
    for financial in financials:
        ticker, cik = _ticker(financial['ticker']), _cik(financial['cik'])
        _require(ticker not in identities or identities[ticker] == cik, 'conflicting historical financial issuer identities')
        identities[ticker] = cik
    corpus = [verify_archive_review(p, now=now) for p in sorted(seed.glob('*/outcome_review_*.json'))
              if len(p.stem.split('_')[-1]) == 4]  # canonical year pointers, not immutable duplicates
    corpus_by_key = {(r['ticker'], r['observation_date']): r for r in corpus}
    _require(len(corpus_by_key) == len(corpus), 'duplicate issuer/year corpus review')
    labels, labels_hash = _read(history_dir / 'frozen_labels.json')
    events = {}
    for event in labels['labels']:
        _ticker(event['target_ticker'])
        _cik(event['target_cik'])
        _day(event['announcement_date'], 'frozen announcement date')
        events.setdefault(event['target_ticker'], []).append(event)
    adjudication_path = seed / 'observation_adjudications.json'
    adjudications, adjudication_hash = _read(adjudication_path) if adjudication_path.exists() else ({'observations': []}, None)
    approved = {}
    for row in adjudications['observations']:
        at = _time(row['observation_at'], 'adjudicated observation')
        _require(at.time() == datetime.min.time(), 'adjudicated observation must match UTC cohort time')
        _require(type(row['horizon_days']) is int and row['horizon_days'] == horizon_days,
                 'adjudicated horizon differs from historical cohort plan')
        key = (_ticker(row['ticker']), at.date().isoformat())
        _cik(row['cik'])
        _require(key not in approved, 'duplicate observation adjudication')
        approved[key] = row
    frame_keys = {(m['historical_ticker'], day) for m in members for day in dates}
    _require(set(approved) <= frame_keys, 'adjudication outside frozen historical frame')
    coverage, observations = [], []
    for member in members:
        ticker = member['historical_ticker']
        cik = identities.get(ticker)
        for day in dates:
            at = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
            cutoff = at - timedelta(seconds=1)
            horizon = at + timedelta(days=horizon_days)
            financial = financials_at_cutoff(financials, cik, cutoff) if cik else None
            key = (ticker, day)
            corpus_review = corpus_by_key.get(key)
            if corpus_review and cik is not None:
                _require(corpus_review['cik'] == cik, 'corpus issuer differs from historical financial identity')
            positive = [event for event in events.get(ticker, []) if event['target_cik'] == cik and
                        day < event['announcement_date'] < horizon.date().isoformat()]
            prior_events = [event for event in events.get(ticker, []) if event['target_cik'] == cik and event['announcement_date'] <= day]
            _require(not (positive and corpus_review), 'reviewed positive event contradicts negative issuer corpus')
            gaps = []
            if cik is None: gaps.append('historical_identity_unresolved')
            if financial is None: gaps.append('original_annual_financials_unavailable_before_cutoff')
            if not positive and corpus_review is None: gaps.append('outcome_corpus_unreviewed_or_incomplete')
            if prior_events: gaps.append('prior_control_announcement_requires_historical_disposition_review')
            row = approved.get(key)
            if row is None:
                gaps.extend(['historical_membership_and_pending_deal_baseline_not_jointly_adjudicated',
                             'original_outcome_version_and_timing_receipt_not_finalized'])
            else:
                _require(cik == row['cik'], 'adjudicated issuer differs from historical financial identity')
                _require(financial is not None, 'adjudicated observation has no original pre-cutoff annual financials')
                for name, expected in [('information_cutoff_at', cutoff),
                                       ('feature_max_available_at', _time(financial['feature_max_available_at'], 'financial availability'))]:
                    if row.get(name) is not None:
                        _require(_time(row[name], name) == expected, 'adjudicated feature/cutoff chronology differs from original financial join')
                if 'features' in row:
                    _require(row['features'] == financial['features'], 'adjudicated values differ from verified original financials')
                _verify_adjudication_contents(row, history_dir, corpus_review)
                joined = copy.deepcopy(row)
                joined.update(features=financial['features'], information_cutoff_at=cutoff.isoformat(),
                              feature_max_available_at=financial['feature_max_available_at'],
                              financial_evidence=financial)
                observations.append(joined)
                gaps = []
            coverage.append({'ticker': ticker, 'historical_issuer_name': member['historical_issuer_name'], 'cik': cik,
                             'observation_at': at.isoformat(), 'horizon_end_at': horizon.isoformat(),
                             'financial_record_id': financial['record_id'] if financial else None,
                             'financial_period_end': financial['period_end'] if financial else None,
                             'feature_max_available_at': financial['feature_max_available_at'] if financial else None,
                             'reviewed_positive_event_ids': [r['event_id'] for r in positive],
                             'reviewed_negative_corpus_sha256': corpus_review['review_sha256'] if corpus_review else None,
                             'outcome_label': None, 'risk_set_eligible': None,
                             'training_eligible': row is not None, 'remaining_gaps': gaps})
    panel = {'schema_version': 'historical-company-features-v1', 'data_as_of': now.isoformat(),
             'label_timing_policy': RETROSPECTIVE_LABEL_TIMING,
             'historical_sampling_frame': frame['historical_sampling_frame'],
             'feature_names': list(FEATURE_UNITS), 'feature_units': FEATURE_UNITS,
             'synthetic_test_fixture': False, 'observations': observations}
    normalized = validate_training_data(panel, now=now)[1] if observations else []
    by_identity = {(r['cik'], r['observation_at']): r for r in normalized}
    for row in coverage:
        valid = by_identity.get((row['cik'], _time(row['observation_at'], 'coverage observation')))
        if valid:
            row.update(outcome_label=int(valid['label']), risk_set_eligible=True,
                       label_available_at=valid['label_available_at'].isoformat(),
                       label_training_available_at=valid['label_training_available_at'].isoformat(),
                       label_timing_basis=valid['label_timing_basis'])
    test_year = frame['cohort_plan']['test_start_year']
    _require(type(test_year) is int and 1900 <= test_year <= 9998, 'invalid planned test start year')
    first_test_dates = [day for day in dates if _day(day, 'test observation date').year == test_year]
    _require(bool(first_test_dates), 'planned test start year has no cohort observation')
    test_cutoff = _time(first_test_dates[0] + 'T00:00:00Z', 'test cutoff') - timedelta(seconds=1)
    prior = [r for r in normalized if r['observation_at'].year < test_year]
    usable = [r for r in prior if r['horizon_end'] <= test_cutoff and r['label_training_available_at'] <= test_cutoff]
    positives = len({r['event_id'] for r in usable if r['label'] == 1})
    negatives = len({r['cik'] for r in usable if r['label'] == 0})
    support = {'test_start_year': test_year, 'training_cutoff_at': test_cutoff.isoformat(),
               'structurally_admitted_prior_observations': len(prior),
               'company_observations': len(usable), 'distinct_positive_events': positives,
               'distinct_negative_companies': negatives,
               'purged_prior_observations': len(prior) - len(usable),
               'purged_label_unavailable': sum(r['label_training_available_at'] > test_cutoff for r in prior),
               'minimum_distinct_positive_events': 5, 'minimum_distinct_negative_companies': 20,
               'remaining_positive_events': max(0, 5 - positives), 'remaining_negative_companies': max(0, 20 - negatives),
               'meets_training_support_floors': positives >= 5 and negatives >= 20,
               'availability_basis': 'effective label_training_available_at and mature horizon; actual review clock retained separately'}
    return {'schema_version': 'historical-panel-assembly-v1', 'generated_at': now.isoformat(),
            'status': 'adjudicated_panel_ready_for_training_checks' if observations else 'data_incomplete',
            'model_training_performed': False, 'validated_predictive_edge': False,
            'frame_companies': len(members), 'planned_observations': len(coverage),
            'reviewed_annual_financial_records': len(financials), 'financial_issuers': len(identities),
            'financially_joinable_observations': sum(r['financial_record_id'] is not None for r in coverage),
            'reviewed_negative_corpus_windows': len(corpus), 'reviewed_negative_corpus_issuers': len({r['cik'] for r in corpus}),
            'eligible_feature_observations': len(observations),
            'training_eligibility_semantics': 'admitted to the structural input contract; each historical fold separately purges immature or unavailable labels',
            'pre_test_training_support': support,
            'gap_counts': dict(Counter(gap for r in coverage for gap in r['remaining_gaps'])),
            'input_sha256': {'sampling_frame': frame_hash, 'frame_source_receipt': source_receipt_hash,
                              'frozen_labels': labels_hash, 'observation_adjudications': adjudication_hash,
                              **{p.name: _sha(p.read_bytes()) for p in financial_paths if p.exists()}},
            'source_limitations': ['The complete100-member historical entry cohort is preserved, including later acquisitions and source failures.',
                                  'Currently surviving issuer pages are not proof that historical pages were never removed or revised.',
                                  'Agent-reviewed source corpora are distinct from independently audited labels and complete training observations.',
                                  'The latest verified annual report may be old; fiscal period and publication cutoff remain explicit.'],
            'corpus_reviews': corpus, 'coverage': coverage, 'panel': panel}
