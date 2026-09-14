"""Build a hash-bound feasibility ledger; no labels or training data are written."""
from __future__ import annotations
import collections, datetime, hashlib, json, pathlib, sys

BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parents[3]
HISTORY = ROOT/'data/history'
sys.path.insert(0,str(ROOT))
from src.research.regulatory_inventory import verify_inventory

TICKERS='ARQT CRNX BEAM ALT APLT APRE CALA ABUS ARCT FREQ AVDL HARP FULC CNCE KALA KALV KNSA KRYS'.split()
EXCLUDED={'3','3/A','4','4/A','5','5/A','144','SC 13G','SC 13G/A','SCHEDULE 13G','SCHEDULE 13G/A','CT ORDER','UPLOAD','CORRESP','EFFECT','S-8','S-8 POS','ARS'}
PERIODS=[('2020-01-01','2020-12-31'),('2021-01-01','2021-12-31'),('2022-01-01','2022-03-31')]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path):return {'source_relative_path':str(path.relative_to(HISTORY)),'source_sha256':digest(path)}
def verify_bound(path,sha):
 assert path.is_file(),str(path)
 assert digest(path)==sha,str(path)

financial_path=HISTORY/'panel_financials/financial_records.json'
financial=json.loads(financial_path.read_bytes())
records=[]
for ticker in TICKERS:
 fin=next(r for r in financial['records'] if r['ticker']==ticker and r['fiscal_year']==2019)
 evidence_path=HISTORY/'panel_financials'/fin['evidence_relative_path']
 verify_bound(evidence_path,fin['evidence_sha256'])
 if fin['raw_bytes_archived']:
  verify_bound(HISTORY/'panel_financials'/fin['source_relative_path'],fin['source_sha256'])
 inventories=[];selected=[];all_rows=[]
 for start,end in PERIODS:
  path=(BASE/f'{ticker}_regulatory_inventory_{start}_{end}.json') if ticker in {'ARQT','CRNX'} else (HISTORY/f'panel_seed/regulatory_inventory/{ticker}/{ticker}_{start}_{end}.json')
  inv=verify_inventory(path)
  assert inv['ticker']==ticker and inv['cik']==int(fin['cik'])
  retained=[r for r in inv['records'] if r['form'] not in EXCLUDED]
  inventories.append(dict(ref(path),start_date=start,end_date=end,indexed_document_count=inv['total'],material_document_count=len(retained),pagination_complete=inv['inventory_complete'],transport_identity_verified=inv['transport_identity_verified'],query_interval_closed=inv['query_interval_closed'],raw_response_hashes_verified=True))
  selected.extend(retained);all_rows.extend(inv['records'])
 probe_paths=sorted(BASE.glob(f'CDXS_STRO_{ticker}*_filing_route_probe_20260908.json'))
 other=BASE/f'{ticker}_filing_route_probe_20260908.json'
 if other.exists():probe_paths.append(other)
 probes=[]
 for path in probe_paths:
  d=json.loads(path.read_bytes());assert d['ticker']==ticker
  if d.get('source_sha256'):
   rawpath=BASE/d['source_relative_path'];verify_bound(rawpath,d['source_sha256'])
  probes.append(dict(ref(path),source_uri=d.get('source_uri',d.get('source_url')),attempted_at=d['attempted_at'],status=d['status'],http_status=d.get('http_status'),effective_url=d.get('effective_url',d.get('resolved_url')),error=d.get('error',d.get('failure')),source_bytes_archived=d.get('source_bytes_archived',bool(d.get('source_sha256'))),complete_material_corpus_archived=False))
 reused=[]
 if ticker=='APRE':
  for name in ['APRE_material_source_gaps.json','APRE_transport/browser_route_capture.json','APRE_transport/original_2020_10k_download_receipt.json']:
   reused.append(ref(BASE/name))
 elif ticker in {'ARQT','CRNX'}:
  reused.extend([ref(BASE/f'{ticker}_filing_index_fetch.json'),ref(BASE/f'{ticker}_original_source_progress.json')])
 elif ticker=='BEAM':reused.append(ref(BASE/'BEAM_sources/fetch_failures.json'))
 if ticker in {'ALT','AVDL','KNSA'}:
  reused.append(dict(ref(HISTORY/f'panel_seed/{ticker}/fetch_failures.json'),scope='Earlier news or corporate-page failures; not filing-route failures.'))
 if ticker=='APRE':
  route_status='original_annual_pdf_browser_access_partial_no_complete_corpus'
  next_action='Use the source-backed original annual filing-details/PDF links in the existing APRE browser receipt to obtain replayable original text and every required material parent/exhibit. Existing one-PDF browser access is not the full 42-parent corpus; linked raw PDF download timed out. A PDF or archived browser-text verifier would need explicit extraction and exhibit reconciliation.'
 elif ticker=='CRNX':
  route_status='corporate_navigation_fetched_linked_filing_archive_previously_denied'
  next_action='The saved corporate investor HTML can be replayed for navigation. Its filing link leads to the previously denied Q4 route, which was not retried. Existing accession-specific SEC browser annual text is partial evidence; archive/review all material originals and exhibits through Q1 2022 using an accessible distinct primary route.'
 elif any('Name or service not known' in (p['error'] or '') for p in probes):
  route_status='historical_official_host_dns_failure_in_bounded_probe'
  next_action='The exact issuer route failed DNS; do not infer the historical issuer had no filings. The saved EFTS inventory provides accession-specific SEC candidates for ordinary public browser review. Discover any successor-host historical filing archive through source-backed navigation, then verify issuer CIK/accession and all attached exhibits before review.'
 else:
  route_status='official_filing_route_timeout_in_bounded_probe'
  next_action='The exact source-discovered filing route timed out in a single bounded raw request. Other document routes are not declared inaccessible. Use the saved primary financial publication evidence and EFTS candidate document URIs to obtain original accession-specific full text and exhibits via a distinct ordinary public route; do not retry the saved failure automatically.'
 source_kind=('third_party_annual_report_pdf' if 'annualreports.com' in fin['source_url'] else 'official_issuer_annual_pdf') if fin['raw_bytes_archived'] else 'original_SEC_document_browser_review_without_original_bytes'
 records.append({'ticker':ticker,'cik':int(fin['cik']),'company_name':fin['company_name'],'observation_at':'2021-01-01T00:00:00Z','horizon_end_at':'2022-01-01T00:00:00Z','inventory_receipts':inventories,'indexed_document_count':len(all_rows),'required_material_document_count':len(selected),'material_forms':dict(sorted(collections.Counter(r['form'] for r in selected).items())),'required_material_document_candidates':[{'accession_number':r['accession'],'form':r['form'],'filing_date':r['filed_date'],'document_name':r['document_name'],'candidate_SEC_document_uris':r['candidate_document_uris']} for r in selected],'source_route_status':route_status,'current_probe_receipts':probes,'prior_evidence_receipts':reused,'equisolve_accession_mirror_compatibility':'not_verified','complete_original_material_corpus_verified':False,'new_reviewed_negative_outcome':None,'additional_training_comparison_eligible':False,'financial_baseline_available':{'record_id':fin['record_id'],'fiscal_year':fin['fiscal_year'],'period_start':fin['period_start'],'period_end':fin['period_end'],'filed_date':fin['filed_date'],'original_SEC_url':fin['original_sec_url'],'actual_source_url':fin['source_url'],'source_kind':source_kind,'raw_bytes_archived':fin['raw_bytes_archived'],'source_sha256':fin['source_sha256'],'review_receipt':ref(evidence_path),'publication_evidence':fin['publication_evidence'],'limits':'Financial columns reviewed in an original annual report are not a complete pending-control baseline or full-year outcome review.'},'next_source_action':next_action,'remaining_review_work':['Review original FY2019 business, material contracts and subsequent events plus complete 2020 material filings for a pending public control transaction at observation; corroborate with FY2020 annual.','Reconcile every selected material parent and attached/embedded exhibit, including active ownership, proxy/tender/deregistration or unusual forms; review transaction and censoring contexts.','Bind original filing identity/version/publication evidence, actual source retrieval and actual current review. Verify historical common-equity listing across the complete observation/horizon interval.','Only a completed source-scoped negative review may derive historical effective availability. Missing or failed source access stays unknown.']})

assert len(records)==18 and len({r['ticker'] for r in records})==18
assert all(r['current_probe_receipts'] or r['ticker']=='APRE' for r in records)
assert all(not r['additional_training_comparison_eligible'] for r in records)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
result={'schema_version':'historical-comparison-source-route-ledger-v1','created_at':now,'reviewer':'Codex-primary-source-review','independent_human_review':False,'scope':'The 18 financially prepared controls other than the separately completed CDXS/STRO 2021 regulatory reviews. Bounded source-route diagnostics and verified inventory metadata, not outcome adjudication.','financial_records_receipt':ref(financial_path),'prior_completed_adjudications_receipt':ref(BASE/'CDXS_STRO_negative_adjudications.json'),'excluded_form_types':sorted(EXCLUDED),'form_scope':'Fixed material selection keeps every unknown form, current/periodic report, active ownership, proxy/tender, registration/prospectus and deregistration form. Passive/insider/routine employee/admin forms and duplicate annual shareholder reports are excluded. Counts identify original document candidates, not verified subject issuers or completed exhibit inventories.','summary':{'remaining_control_issuers':18,'additional_complete_original_corpora_verified':0,'additional_eligible_training_comparisons':0,'indexed_document_count':sum(r['indexed_document_count'] for r in records),'required_material_document_candidates':sum(r['required_material_document_count'] for r in records),'source_route_status_counts':dict(collections.Counter(r['source_route_status'] for r in records))},'transport_limits':'A timeout, DNS error, or denial belongs to its exact URL, transport and recorded time. A current web-search representation can remain readable when raw HTTP fails. A failed news page is never substituted for a filing-route failure. Unattempted document routes remain unprobed. Known failures were preserved and not retried.','historical_index_limits':'Pagination, hashed raw response replay, query interval closure and effective-response URL identity are separate. Legacy inventory receipts without captured effective URLs remain transport_identity_verified=false; this ledger does not invent retrospective transport evidence or assert that removed/corrected filings are recoverable.','original_version_limits':'An issuer-accession HTML mirror must bind actual mirror bytes separately from the SEC original document URI. Current issuer news copies and third-party annual PDFs do not automatically authenticate all original historical release/filing versions.','records':records}
result['parallel_route_assessment_receipt']=ref(BASE/'BEAM_ARQT_CRNX_ALT_APLT_CALA_route_assessment_20260908.json')
assert result['parallel_route_assessment_receipt']['source_sha256']=='9b51d75ea207e366b367b6adee2a426ca97f16c89d9ee314b0650e1b94e6d13e'
path=BASE/'CDXS_STRO_remaining_controls_route_ledger.json'
path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
lines=['# Remaining historical comparison source routes','',f'Created {now}. Codex source review; not independent human review.','',f'All 18 remaining financially prepared controls have a saved prior or new filing-route probe. **No additional complete original filing corpus or eligible negative was established.** The separate CDXS/STRO reviews remain the two admitted comparisons.','',f'The saved inventories replay {result["summary"]["indexed_document_count"]} indexed documents and identify {result["summary"]["required_material_document_candidates"]} selected material-document candidates. Their exhibits still require inventory/review. Legacy effective-URL identity remains unverified.','','| Issuer | Material candidates | Actual bounded source result |','|---|---:|---|']
for r in records:lines.append(f'| {r["ticker"]} | {r["required_material_document_count"]} | {r["source_route_status"].replace("_"," ")} |')
lines+=['','The JSON ledger binds every inventory and probe receipt by SHA-256, includes exact attempted URLs and original SEC document candidates, and separates existing annual financial evidence from the missing baseline, listing and complete outcome review. DNS and timeout results do not assert all public source routes are unavailable.','','The next gate is an accessible, replayable original filing body route, followed by complete material parent/exhibit review and publication/version binding. No additional Equisolve-compatible accession mirror was verified in these 18 issuers.','']
(BASE/'CDXS_STRO_remaining_controls_route_ledger.md').write_text('\n'.join(lines))
print(json.dumps({'path':str(path),'sha256':digest(path),'summary':result['summary']},indent=2))
