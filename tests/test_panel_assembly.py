"""Synthetic receipts test replay mechanics, never historical investment evidence."""
import hashlib
import json
from datetime import datetime, timezone

import pytest

from src.research.panel_assembly import assemble_research_panel, verify_archive_review, verify_baseline_review


NOW = datetime(2026, 9, 8, 23, tzinfo=timezone.utc)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture
def evidence(tmp_path):
    seed = tmp_path / 'panel_seed'
    seed.mkdir()
    members = [('Nasdaq', 'ARQT', 'Synthetic issuer'), ('Nasdaq', 'UNKN', 'Unknown synthetic issuer')]
    html = ('<p>The following 2 securities will be added to the Index:</p><table><tr>'
            '<td>EXCHANGE</td><td>SYMBOL</td><td>COMPANY NAME</td></tr>' +
            ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in member) + '</tr>' for member in members) + '</table>').encode()
    source_hash = save(seed / 'original.html', html)
    source = dict(source_uri='https://example.org/exchange', source_relative_path='original.html',
                  source_sha256=source_hash, bytes=len(html), retrieved_at='2026-01-01T00:00:00Z')
    save(seed / 'nasdaq_source_receipt.json', source)
    frame = dict(schema_version='historical-sampling-frame-v1', frame_size=2,
                 records=[dict(exchange=e, historical_ticker=t, historical_issuer_name=n) for e, t, n in members],
                 cohort_plan=dict(observation_dates=['2021-01-01', '2023-01-01', '2024-01-01'], horizon_days=365, test_start_year=2023),
                 historical_sampling_frame=dict(source_uri=source['source_uri'], source_sha256=source_hash,
                    selection_basis='predeclared_historical_sampling_frame', selection_rule='All named synthetic table members',
                    source_locator='Synthetic exchange additions table', uses_current_listing_status=False,
                    uses_future_outcomes=False, includes_subsequently_delisted=True,
                    population_as_of_at='2020-12-21T00:00:00Z', retrieved_at='2026-01-01T00:00:00Z', reviewed_at='2026-01-02T00:00:00Z'))
    save(seed / 'sampling_frame.json', frame)
    save(tmp_path / 'frozen_labels.json', dict(labels=[]))

    financial_dir = tmp_path / 'panel_financials'
    report = b'Synthetic annual financial statement'
    report_hash = save(financial_dir / 'report.pdf', report)
    record = dict(record_id='synthetic-arqt-2019', cik=123, ticker='ARQT', filing_form='10-K', period_type='annual',
                  period_start='2019-01-01', period_end='2019-12-31', filed_date='2020-03-01', publication_date='2020-03-01',
                  publication_date_verified=True, publication_timestamp_precision='date', published_at=None,
                  publication_evidence=dict(url='https://example.org/report', evidence_paraphrase='Synthetic date'),
                  available_at='2020-03-02T12:00:00Z', retrieved_at='2026-01-01T00:00:00Z', reviewed_at='2026-01-02T00:00:00Z',
                  source_url='https://example.org/report', raw_bytes_archived=True, source_relative_path='report.pdf',
                  source_sha256=report_hash, source_bytes=len(report), facts={'cash_usd':dict(reported=True,
                      reported_label='Cash', statement='Balance sheet', printed_page='F1', source_unit='USD', unit_multiplier=1,
                      reported_value=100, value_usd=100, unit='USD', period_type='instant', period_start=None, period_end='2019-12-31')})
    def save_financial():
        annotation = {k:v for k,v in record.items() if k not in ('evidence_relative_path', 'evidence_sha256')}
        h = save(financial_dir / 'review.json', dict(annotation, schema_version='manual-financial-evidence-v2'))
        record.update(evidence_relative_path='review.json', evidence_sha256=h)
        save(financial_dir / 'financial_records.json', dict(schema_version='reviewed-panel-annual-financials-v1', records=[record]))
    save_financial()

    root = seed / 'ARQT'
    pages, inventory, bodies = [], [], []
    for year, day in [(2020, '2020-06-01'), (2021, '2021-06-01'), (2022, '2022-01-05')]:
        url, title = f'https://example.org/{year}-release', f'Synthetic release {year}'
        entry = dict(date=day, title=title, url=url, archive_year=year, archive_page=1)
        inventory.append(entry)
        config = {'preload_data': {'settings': {'pager':dict(page=1,total_pages=1,per_page=12,total_rows=1)},
                                   'facets': {'publications_year': f'<option value="{year}" selected>{year}</option>'}}}
        page = (f'<script>window.FWP_JSON = {json.dumps(config)};</script>' +
                f'<a class="pd-card-link" href="{url}"><small class="text-muted">{datetime.fromisoformat(day).strftime("%B %d, %Y")}</small>' +
                f'<h3 class="card-title">{title}</h3></a>').encode()
        path = f'page-{year}.html'
        page_hash = save(root / path, page)
        pages.append(dict(url=f'https://example.org/archive?year={year}', page=1, archive_year=year,
                          total_pages=1,per_page=12,total_rows=1,entry_count=1,source_relative_path=path,
                          source_sha256=page_hash,source_bytes=len(page),retrieved_at='2026-01-01T00:00:00Z'))
        if year == 2022:
            continue
        text = f'Synthetic issuer {title} published {day}; ordinary clinical research.'
        payload = f'<div id="pd-content">{text}</div>'.encode()
        body_hash = save(root / f'body-{year}.html', payload)
        bodies.append(dict(archive_url=url,archive_date=day,title=title,source_url=url,
                           source_relative_path=f'body-{year}.html',source_sha256=body_hash,source_bytes=len(payload),
                           retrieved_at='2026-01-01T00:00:00Z',publication_date=day,publication_dateline_verified=True,
                           trigger_context_review_complete=True,extraction_selector='#pd-content',
                           full_text_characters=len(text),full_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                           qualified_target_control_event=False,censoring_event=False))
    collection = dict(schema_version='collected-issuer-archive-v1',issuer='ARQT',archive_complete=True,pages=pages,inventory=inventory)
    review = dict(schema_version='issuer-annual-outcome-review-v1',issuer=dict(ticker='ARQT',cik=123),
                  collection_manifest_relative_path='collection.json',archive_complete=True,full_text_review_complete=True,
                  method=dict(all_trigger_contexts_reviewed=True),body_reviews=bodies,body_count=2,reviewed_at='2026-01-02T00:00:00Z',
                  baseline_review=dict(start_date='2020-01-01',end_date='2020-12-31',pending_qualified_target_control_transaction_found=False),
                  outcome_window=dict(observation_date='2021-01-01',window_end_date='2022-01-01',horizon_days=365,
                                      qualified_target_control_event_found=False,censoring_event_found=False),
                  source_scope='Synthetic complete designated corpus',source_version_policy=dict(classification='unverified_original_version'))
    def save_corpus():
        review['collection_manifest_sha256'] = save(root/'collection.json',collection)
        save(root/'outcome_review_2021.json',review)
    save_corpus()
    membership = dict(cik=123,ticker='ARQT',kind='historical_exchange_membership',security_type='common_equity',
                      biotech_eligible=True,valid_from='2020-02-01T00:00:00Z',valid_until='2025-01-01T00:00:00Z')
    member_hash = save(seed/'listing.json',dict(records=[membership]))
    row = dict(ticker='ARQT',cik=123,observation_at='2021-01-01T00:00:00Z',horizon_days=365,risk_set_eligible=True,
               membership=dict(membership,source_uri=(seed/'listing.json').as_uri(),source_sha256=member_hash),
               label=dict(reviewed=True,review_id='synthetic-negative',source_uri=(root/'outcome_review_2021.json').as_uri(),
                          source_sha256=hashlib.sha256((root/'outcome_review_2021.json').read_bytes()).hexdigest(),
                          event_class='no_change_of_control_announcement',announcement_at=None,
                          observed_through='2022-01-01T00:00:00Z',available_at='2026-01-03T00:00:00Z',reviewed_at='2026-01-03T00:00:00Z'))
    def approve():
        save(seed/'observation_adjudications.json',dict(observations=[row]))
    return dict(history=tmp_path,seed=seed,root=root,frame=frame,collection=collection,review=review,
                save_corpus=save_corpus,record=record,save_financial=save_financial,row=row,approve=approve)


def test_unknown_is_not_zero_and_complete_frame_is_preserved(evidence):
    result = assemble_research_panel(evidence['history'],now=NOW)
    assert result['frame_companies']==2 and result['planned_observations']==6
    assert result['eligible_feature_observations']==0
    assert all(row['outcome_label'] is None and row['risk_set_eligible'] is None for row in result['coverage'])
    assert result['reviewed_negative_corpus_windows']==1
    assert result['corpus_reviews'][0]['negative_training_label_assigned'] is False


def test_valid_legacy_review_is_admitted_but_purged_from_2023(evidence):
    evidence['approve']()
    result=assemble_research_panel(evidence['history'],now=NOW)
    assert result['eligible_feature_observations']==1
    row=result['panel']['observations'][0]
    assert row['features']['cash_usd']==100 and row['features']['assets_usd'] is None
    support=result['pre_test_training_support']
    assert support['structurally_admitted_prior_observations']==1
    assert support['company_observations']==0 and support['purged_label_unavailable']==1
    assert support['remaining_positive_events']==5 and support['remaining_negative_companies']==20
    assert next(r for r in result['coverage'] if r['training_eligible'])['label_timing_basis']=='recorded_availability'


def test_negative_historical_clock_requires_replayed_original_corpus(evidence):
    evidence['row']['label']['historical_evidence_timing'] = {'claimed_original': True}
    evidence['approve']()
    with pytest.raises(ValueError, match='replayable original regulatory corpus'):
        assemble_research_panel(evidence['history'], now=NOW)


@pytest.mark.parametrize('artifact',['original.html','ARQT/page-2021.html','ARQT/body-2021.html'])
def test_tampered_archived_source_blocks_replay(evidence,artifact):
    (evidence['seed']/artifact).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_rehashed_frame_cannot_replace_an_exchange_member(evidence):
    evidence['frame']['records'][1]['historical_ticker']='FAKE'
    save(evidence['seed']/'sampling_frame.json',evidence['frame'])
    with pytest.raises(ValueError,match='members differ'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_empty_panel_still_checks_historical_sampling_provenance(evidence):
    evidence['frame']['historical_sampling_frame']['uses_current_listing_status']=True
    save(evidence['seed']/'sampling_frame.json',evidence['frame'])
    with pytest.raises(ValueError,match='current survival'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_rehashed_inventory_cannot_remove_an_unreviewed_release(evidence):
    evidence['collection']['inventory'].pop(1)
    evidence['review']['body_reviews'].pop()
    evidence['review']['body_count']=1
    evidence['save_corpus']()
    with pytest.raises(ValueError,match='saved inventory differs'):
        verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)


def test_missing_archive_inventory_is_not_empty_negative(evidence):
    evidence['collection']['pages']=[]
    evidence['collection']['inventory']=[]
    evidence['save_corpus']()
    with pytest.raises(ValueError,match='page inventory missing'):
        assemble_research_panel(evidence['history'],now=NOW)


@pytest.mark.parametrize('change,error',[
    ('ticker','outside frozen'),('time','UTC cohort time'),('horizon','horizon differs'),
    ('identity','financial identity'),('member_interval','membership differs'),('backdated_review','backdates'),
])
def test_adjudication_identity_dates_and_saved_review_binding(evidence,change,error):
    row=evidence['row']
    if change=='ticker':row['ticker']='OTHER'
    elif change=='time':row['observation_at']='2021-01-01T12:00:00Z'
    elif change=='horizon':row['horizon_days']=364
    elif change=='identity':row['cik']=999
    elif change=='member_interval':row['membership']['valid_until']='2027-01-01T00:00:00Z'
    else:row['label'].update(reviewed_at='2022-01-03T00:00:00Z',available_at='2022-01-03T00:00:00Z')
    evidence['approve']()
    with pytest.raises(ValueError,match=error):
        assemble_research_panel(evidence['history'],now=NOW)


def test_future_financial_statement_cannot_supply_observation(evidence):
    row=evidence['record'];row.update(filed_date='2022-03-01',publication_date='2022-03-01',available_at='2022-03-02T12:00:00Z')
    evidence['save_financial']();evidence['approve']()
    with pytest.raises(ValueError,match='no original pre-cutoff'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_adjudication_cannot_override_canonical_feature_timestamp(evidence):
    evidence['row']['feature_max_available_at']='2021-03-01T00:00:00Z'
    evidence['approve']()
    with pytest.raises(ValueError,match='feature/cutoff chronology differs'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_review_file_tamper_is_checked_before_admission(evidence):
    evidence['approve']()
    save(evidence['seed']/'listing.json',{'records':[]})
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_missing_page_cannot_be_hidden_by_resealing_inventory(evidence):
    evidence['collection']['pages'].pop(1)
    evidence['save_corpus']()
    with pytest.raises(ValueError,match='saved inventory differs'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_prior_acquisition_remains_unknown_without_disposition_review(evidence):
    save(evidence['history']/'frozen_labels.json',{'labels':[dict(target_cik=123,target_ticker='ARQT',
         announcement_date='2020-06-01',event_id='123:2020-06-01')]})
    result=assemble_research_panel(evidence['history'],now=NOW)
    rows=[r for r in result['coverage'] if r['ticker']=='ARQT']
    assert all(r['outcome_label'] is None and not r['training_eligible'] for r in rows)
    assert all('prior_control_announcement_requires_historical_disposition_review' in r['remaining_gaps'] for r in rows)


def test_forged_extracted_text_hash_is_rejected(evidence):
    evidence['review']['body_reviews'][0]['full_text_sha256']='0'*64;evidence['save_corpus']()
    with pytest.raises(ValueError,match='full-text extraction differs'):
        verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)


def test_adjudicated_positive_is_bound_to_saved_event(evidence):
    (evidence['root']/'outcome_review_2021.json').unlink()
    event=dict(target_cik=123,target_ticker='ARQT',announcement_date='2021-06-01',event_id='123:2021-06-01',
               label='definitive_change_of_control_announcement',timestamp_precision='date',reviewed_at='2026-01-02T00:00:00Z')
    path=evidence['history']/'frozen_labels.json'
    digest=save(path,{'labels':[event]})
    label=evidence['row']['label']
    label.update(source_uri=path.as_uri(),source_sha256=digest,event_class='change_of_control_announcement',
                 timestamp_precision='date',announcement_date='2021-06-01')
    evidence['approve']()
    result=assemble_research_panel(evidence['history'],now=NOW)
    assert result['eligible_feature_observations']==1
    assert result['pre_test_training_support']['distinct_positive_events']==0
    label['announcement_date']='2021-07-01';evidence['approve']()
    with pytest.raises(ValueError,match='uniquely match issuer and announcement date'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_conflicting_positive_and_negative_corpora_fail_closed(evidence):
    save(evidence['history']/'frozen_labels.json',{'labels':[dict(target_cik=123,target_ticker='ARQT',
         announcement_date='2021-06-01',event_id='123:2021-06-01')]})
    with pytest.raises(ValueError,match='contradicts negative issuer corpus'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_supporting_risk_receipt_hash_is_verified(evidence):
    row=evidence['row']
    row['risk_set_review']=dict(source_uri=row['label']['source_uri'],source_sha256=row['label']['source_sha256'],
                               reviewed_at='2026-01-03T00:00:00Z',supporting_source_receipts=[
                                   dict(source_uri=row['membership']['source_uri'],source_sha256='0'*64)])
    evidence['approve']()
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        assemble_research_panel(evidence['history'],now=NOW)


def test_pending_baseline_transitively_replays_body_bytes(evidence):
    review=dict(evidence['review'],schema_version='issuer-pre2020-baseline-review-v1',supplemental_body_count=0)
    review['baseline_review']=dict(start_date='2020-01-01',end_date='2021-12-31',
        pending_qualified_target_control_transaction_found=False,qualified_target_control_event_found=False,censoring_event_found=False)
    path=evidence['root']/'synthetic-baseline.json';save(path,review)
    assert verify_baseline_review(path,now=NOW)['body_count']==2
    (evidence['root']/'body-2020.html').write_bytes(b'changed source')
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        verify_baseline_review(path,now=NOW)


def test_unreviewed_page_fragment_cannot_replace_article_selector(evidence):
    evidence['review']['body_reviews'][0]['extraction_selector']='#footer';evidence['save_corpus']()
    with pytest.raises(ValueError,match='full-article selector'):
        verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)


@pytest.mark.parametrize('flag',[None,0,'false',True])
def test_unknown_or_positive_event_flag_cannot_be_negative(evidence,flag):
    evidence['review']['body_reviews'][0]['qualified_target_control_event']=flag;evidence['save_corpus']()
    with pytest.raises(ValueError,match='negative-window summary contradicts'):
        verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)


def test_web_capture_keeps_transport_distinction_and_replays_text(evidence):
    body=evidence['review']['body_reviews'][0]
    text='Synthetic issuer release\nNo event announced.'
    capture=dict(capture_method='web_tool_open_response',original_publisher_html=False,source_url=body['source_url'],
                 captured_at='2026-01-01 00:00:00 UTC',response='L10: Synthetic issuer release\nL11: No event announced.\nL12: Navigation')
    h=save(evidence['root']/'web.json',capture)
    body.update(source_relative_path='web.json',source_sha256=h,source_bytes=(evidence['root']/'web.json').stat().st_size,
                extraction_selector='web-tool-lines:10-11',source_content_format='web_tool_extracted_text_response',
                original_publisher_html_archived=False,full_text_characters=len(text),full_text_sha256=hashlib.sha256(text.encode()).hexdigest())
    evidence['save_corpus']()
    result=verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)
    assert result['verified_web_response_body_documents']==1 and result['verified_publisher_body_documents']==1
    body['original_publisher_html_archived']=True;evidence['save_corpus']()
    with pytest.raises(ValueError,match='cannot claim original'):
        verify_archive_review(evidence['root']/'outcome_review_2021.json',now=NOW)
