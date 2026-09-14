"""Join the two reviewed original regulatory corpora; never edits main panel."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO))
from src.research.regulatory_corpus import verify_regulatory_review, bind_historical_timing
from src.research.panel_assembly import _verify_adjudication_contents, verify_archive_review
from src.research.panel_financials import financials_at_cutoff, read_reviewed_financials
from src.research.financial_seed import FEATURE_UNITS
from src.research.training import validate_training_data
from src.research.validation import RETROSPECTIVE_LABEL_TIMING

HERE=Path(__file__).resolve().parent
HISTORY=HERE.parents[1]
def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def provenance(path): return {'source_uri':path.as_uri(),'source_sha256':sha(path.read_bytes())}
def save(path,data):
    raw=(json.dumps(data,sort_keys=True,indent=2)+'\n').encode()
    path.write_bytes(raw)
    frozen=path.with_name(path.stem+'-'+sha(raw)+path.suffix)
    if frozen.exists(): assert frozen.read_bytes()==raw
    else: frozen.write_bytes(raw)
    return sha(raw)

now=datetime.now(timezone.utc)
clock=now.isoformat()
results={t:verify_regulatory_review(HERE/f'{t}_regulatory_outcome_review_2021.json',now=now) for t in ['CDXS','STRO']}
members=[]
for t,r in results.items():
    m=r['review']['membership_review']
    members.append({**m,'kind':'historical_exchange_membership','security_type':'common_equity','biotech_eligible':True,'company_name':{'CDXS':'Codexis, Inc.','STRO':'Sutro Biopharma, Inc.'}[t],'valid_from':'2020-12-21T00:00:00Z','valid_until':'2022-02-24T00:00:00Z','reviewed_at':clock,'reviewer':'Codex-primary-source-review','independent_human_review':False,'pending_transaction_review_complete':True,'pending_transaction_review_receipt':provenance(HERE/f'{t}_regulatory_outcome_review_2021.json'),'source_content_format':'issuer_accession_filing_mirror_html','original_sec_document_bytes_archived':False,'original_source_sha256':None,'interval_basis':'The fixed2020 Nasdaq frame establishes the historical symbol before observation. Original2021 annual Item5 describes a common-stock total-return series spanning the whole2021 outcome period, current Nasdaq common stock and holders/outstanding shares as ofFeb24,2022; complete intervening material filing review finds no control/delisting event. This is a documented reconstruction from trading-history and full material-event evidence, not a generic annual-filer proxy.'})
member_path=HERE/'CDXS_STRO_membership_reviews_2021.json'
save(member_path,{'schema_version':'reviewed-historical-listings-v1','records':members})

financials=read_reviewed_financials([HISTORY/'panel_financials'/'financial_records.json'])
rows=[]
for ticker,result in results.items():
    review=result['review'];review_path=HERE/f'{ticker}_regulatory_outcome_review_2021.json'
    old_path=HERE.parent/ticker/'outcome_review_2021.json'
    issuer_corpus=verify_archive_review(old_path,now=now)
    identity={'cik':result['cik'],'ticker':ticker,'observation_at':review['observation_at'],'horizon_days':365}
    label={**provenance(old_path),'event_class':'no_change_of_control_announcement','reviewed':True,'reviewed_at':clock,'available_at':clock,'review_id':f'{ticker}-2021-original-regulatory-corpus-reviewed-20260908','announcement_at':None,'observed_through':review['horizon_end_at'],'review_scope':'Reviewed issuer news corpus is retained as actual2026 label-source provenance; separately replayed accession-specific original regulatory corpus supplies the explicit retrospective clock under its defined Jan2020–Mar2022 scope.','regulatory_coverage_receipt':provenance(review_path)}
    sources=[]
    for url,body in result['documents'].items():
        a=result['document_reviews'][url];parent=result['inventory_rows'][body['parent_document_url']];page=result['inventory_pages'][parent['index_url']]
        sources.append({'source_id':ticker+'-'+body['accession_number']+'-'+sha(url.encode())[:16],'source_uri':url,'source_sha256':body['source_sha256'],'source_sha256_kind':'original_document_bytes','original_source_sha256':None,'source_content_format':'issuer_accession_filing_mirror_html','original_sec_document_bytes_archived':False,'subject_cik':result['cik'],'source_family':'regulatory_filings','version_status':'verified_original','publication_date':body['publication_date'],'publication_timestamp_precision':'date','published_at':None,'publication_basis':'issuer_publication','retrieved_at':body['retrieved_at'],'source_locator':f'Accession-specific {body["document_type"]}, #document-wrap; full text and contextual review bound to '+a['extracted_text_sha256'],'original_version_evidence':a['original_version_evidence'],'publication_evidence':{'source_uri':parent['index_url'],'source_sha256':page['source_sha256'],'source_locator':f'Issuer archive year{parent["archive_year"]} page{parent["archive_page"]}, filing row{body["accession_number"]}, form{parent["form"]}, issuer-reported publication date{body["publication_date"]}; date precision only.'}})
    inventory=json.loads((HERE/review['inventory_receipt']['source_relative_path']).read_bytes())
    coverage={**provenance(review_path),'kind':'complete_designated_primary_corpus','inventory_complete':True,'full_text_review_complete':True,'censoring_review_complete':True,'known_missing_sources':False,'qualifying_control_event_found':False,'censoring_event_found':False,'window_start_at':'2020-01-01T00:00:00Z','window_end_at':'2022-04-01T00:00:00Z','ascertainment_complete_at':'2022-04-01T12:00:00Z','retrieved_at':inventory['retrieved_at'],'required_source_ids':[s['source_id'] for s in sources],'source_families':['regulatory_filings'],'scope':review['scope'],'removed_page_limitations':review['removed_page_limitations'],'review_method':review['review_method']}
    timing={'schema_version':'retrospective-label-evidence-v1','review_id':label['review_id'],'label_source_sha256':label['source_sha256'],'cik':result['cik'],'event_class':label['event_class'],'observation_at':review['observation_at'],'horizon_end_at':review['horizon_end_at'],'reviewed_at':clock,'reviewer':'Codex-primary-source-review','sources':sources,'sources_sha256':sha(canonical(sources)),'coverage':coverage,'historical_evidence_available_at':'2022-04-01T12:00:00Z'}
    label['historical_evidence_timing']=timing
    bind_historical_timing(label,result)
    membership={**next(m for m in members if m['ticker']==ticker),**provenance(member_path)}
    row={**identity,'label':label,'membership':membership,'risk_set_eligible':True,'risk_set_exclusion_reason':None,'risk_set_review':{**provenance(review_path),'basis':review['baseline_review']['method']+' '+review['baseline_review']['evidence_paraphrase'],'reviewed_at':clock,'reviewer':'Codex-primary-source-review','independent_human_review':False}}
    _verify_adjudication_contents(row,HISTORY,issuer_corpus)
    cutoff=datetime(2020,12,31,23,59,59,tzinfo=timezone.utc)
    financial=financials_at_cutoff(financials,result['cik'],cutoff)
    assert financial is not None and financial['period_end']=='2019-12-31'
    row.update(features=financial['features'],information_cutoff_at=cutoff.isoformat(),feature_max_available_at=financial['feature_max_available_at'],financial_evidence=financial)
    rows.append(row)

frame=json.loads((HERE.parent/'sampling_frame.json').read_bytes())
panel={'schema_version':'historical-company-features-v1','data_as_of':clock,'label_timing_policy':RETROSPECTIVE_LABEL_TIMING,'historical_sampling_frame':frame['historical_sampling_frame'],'feature_names':list(FEATURE_UNITS),'feature_units':FEATURE_UNITS,'synthetic_test_fixture':False,'observations':rows}
_,normalized=validate_training_data(panel,now=now)
assert len(normalized)==2 and all(x['label']==0 and x['label_training_available_at']==datetime(2022,4,1,12,tzinfo=timezone.utc) for x in normalized)
out={'schema_version':'reviewed-historical-observation-adjudications-v1','reviewed_at':clock,'reviewer':'Codex-primary-source-review','scope':'Two evidence-bound2021 comparison observations, ready for root to merge; no model fit or minimum-support claim.','observations':rows}
digest=save(HERE/'CDXS_STRO_negative_adjudications.json',out)
print('Both source, corpus, financial and retrospective timing replays passed:',digest)
