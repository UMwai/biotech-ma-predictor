"""Offline source integrity audit and discovery summary; no label admission."""
from pathlib import Path
import collections
import datetime as dt
import hashlib
import json
import re
import sys

from collect_controls_a_apre import EXCLUDED, parse_submission
from probe_controls_a import ROOT, REPO

sys.path.insert(0,str(REPO))
from src.research.regulatory_inventory import verify_inventory

now=dt.datetime.now(dt.timezone.utc).isoformat()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path):return {'source_relative_path':str(path.relative_to(ROOT)),'source_sha256':sha(path)}
collection_path=ROOT/'controls_a_APRE_complete_submission_collection.json'
collection=json.loads(collection_path.read_text())
fresh_path=ROOT/'APRE_fresh_inventory/APRE_2020-01-01_2022-03-31.json'
fresh=verify_inventory(fresh_path)
rows=[r for r in fresh['records'] if r['form'] not in EXCLUDED]
expected={(r['accession'],r['form'],r['filed_date'],r['document_name']) for r in rows}
actual={(a['accession_number'],a['form'],a['publication_date'],a['candidate_parent_uri'].rsplit('/',1)[-1]) for a in collection['accessions']}
assert expected==actual and len(actual)==42
checks=[]
for accession in collection['accessions']:
    idx,sub=accession['index'],accession['submission']
    for receipt in (idx,sub):
        path=ROOT/receipt['source_relative_path']
        assert sha(path)==receipt['source_sha256']
        assert path.stat().st_size==receipt['byte_count']
        assert receipt['effective_url']==receipt['source_uri']
    body=(ROOT/sub['source_relative_path']).read_bytes()
    records,count=parse_submission(body)
    assert records==accession['embedded_documents'] and count==len(records)
    assert len({r['filename'] for r in records})==len(records)
    assert all(hashlib.sha256(body[r['container_text_start']:r['container_text_end']]).hexdigest()==r['embedded_document_sha256'] for r in records)
    row=next(r for r in accession['document_format_inventory'] if 'Complete submission text file' in r['cells'])
    index_size=int(row['cells'][4]); assert index_size==len(body)
    header=body.split(b'</SEC-HEADER>',1)[0]
    assert re.search(rb'CENTRAL INDEX KEY:\s*0*1781983(?:\s|$)',header)
    assert accession['header_identity_verified'] and accession['accession_source_complete']
    checks.append({'accession_number':accession['accession_number'],'all_source_hashes_verified':True,
                   'effective_source_identity_verified':True,'source_header_subject_cik_present':1781983,
                   'source_header_filing_identity_verified':True,'index_submission_byte_count':index_size,
                   'submission_byte_count_matches_index':True,'embedded_document_count':count,
                   'all_text_payload_hashes_and_byte_bounds_verified':True,
                   'all_document_format_entries_present':True,'outcome_label':None})
collection['fresh_inventory_receipt']=ref(fresh_path)
collection['fresh_inventory_all_form_total']=fresh['total']
collection['fresh_inventory_selection_matches_exactly']=True
collection['fresh_inventory_transport_identity_verified']=True
collection['source_content_format']='currently_served_SEC_complete_submission_SGML_with_verbatim_embedded_TEXT_payloads'
collection['source_bytes_archived']=True
collection['as_accepted_byte_identity_verified']=False
collection['source_version_limitations']=[
 'The exact current SEC HTTP response bytes are archived. Hashes do not independently establish byte-for-byte identity to the submission at its original acceptance time.',
 'Every submission length matches its current accession index size and its document count and filename inventory reconcile. These are current-source consistency checks, not evidence that no source correction or removal occurred.',
 'Embedded document hashes identify verbatim TEXT payload ranges in the source container, including wrappers and encoded graphics; they are not hashes of separately downloaded HTML or decoded images.',
 'The original_bytes_archived field in transport probe receipts refers to exact source-response bytes, not verified as-accepted bytes.']
collection['offline_integrity_verified_at']=now
collection_path.write_text(json.dumps(collection,indent=2)+'\n')
audit={'schema_version':'sec-submission-collection-offline-audit-v1','verified_at':now,'reviewer':'Codex-source-integrity-audit',
       'independent_human_review':False,'collection_receipt':ref(collection_path),'fresh_inventory_receipt':ref(fresh_path),
       'fresh_inventory_total':fresh['total'],'fresh_inventory_pages':len(fresh['pages']),
       'fresh_inventory_transport_identity_verified':fresh['transport_identity_verified'],
       'fresh_inventory_selection_matches_exactly':True,'selected_accession_count':42,'accession_checks':checks,
       'all_checks_passed':True,'substantive_outcome_review_complete':False,'outcome_label':None}
(ROOT/'controls_a_APRE_offline_integrity_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
probes=json.loads((ROOT/'controls_a_sec_probes.json').read_text())
annual=json.loads((ROOT/'controls_a_annual_identity_audit.json').read_text())
issuer_results=[]
counts={'ARQT':63,'CRNX':58,'BEAM':51,'ALT':45,'APLT':51,'APRE':42,'CALA':46,'ABUS':67,'ARCT':70}
for source, identity in zip(probes,annual):
    ticker=source['ticker']; complete=ticker=='APRE'
    issuer_results.append({'ticker':ticker,'cik':source['cik'],'selected_material_accession_candidates':counts[ticker],
       'fresh_original_SEC_route_status':'downloaded_accession_specific_primary_source',
       'annual_report':dict(source,identity_audit=identity),
       'complete_designated_source_collection':complete,
       'collected_selected_accessions':42 if complete else 1,
       'source_scope':'All selected accessions from 2020-01-01 through 2022-03-31, including their indexed document-format attachments.' if complete else 'One fiscal2021 annual-report HTML parent only; other selected accessions and its attachments remain uncollected in this bounded task.',
       'complete_outcome_window_review':False,'outcome_label':None,
       'ready_to_use':'Source corpus can be replayed and substantively reviewed; direct SEC submission-container verifier support is still needed.' if complete else 'Annual source with verified CIK, ticker, fiscal year, exact source bytes and source-file date is ready for source review.',
       'remaining_work':['Substantive pending-deal/outcome/censoring review of parents and exhibits including graphics.','Historical listing interval and publication/version evidence review.','Explicit SEC-container verifier/receipt adapter and independent replay before existing label/panel admission.'] if complete else ['Collect remaining selected accession indexes, complete submissions and exhibits through March31,2022.','Reconcile against a fresh identity-verified all-form inventory.','Review listing, baseline, outcome, source version and censoring evidence.']})
failures=[]
for filename in ['controls_a_ARQT_2021_08_05_8K_fetch.json','controls_a_ALT_2021_02_25_8K_fetch.json','controls_a_CRNX_2021_report_fetch.json']:
    path=ROOT/filename
    failures.append({'receipt':ref(path),'result':json.loads(path.read_text())})
result={'schema_version':'historical-control-source-research-v1','researched_at':now,'researcher':'Codex-primary-source-research',
        'independent_human_review':False,'assigned_tickers':[r['ticker'] for r in issuer_results],
        'observation_at':'2021-01-01T00:00:00Z','baseline_start_date':'2020-01-01','outcome_year':2021,
        'reporting_lag_end_date':'2022-03-31','new_negative_labels':0,'label_or_panel_files_modified':False,
        'summary':{'successful_primary_annual_sources':9,'complete_selected_accession_source_corpora':1,
                   'complete_substantively_reviewed_negative_windows':0,'APRE_selected_accessions':42,
                   'APRE_embedded_documents':707,'APRE_document_format_entries':257,
                   'APRE_document_format_non_graphic_entries':117,'APRE_document_format_graphics':140,
                   'APRE_submission_bytes':57198252,'APRE_all_form_inventory_total':124,
                   'APRE_all_form_inventory_pages':2},
        'method':'Primary web search and actual issuer link navigation, then bounded normal public SEC HTTP GET. One worker at no more than one request per second; no credentials, paid access, bypass, or retries of failed identical URLs.',
        'issuer_results':issuer_results,
        'APRE_collection_receipt':ref(collection_path),
        'APRE_integrity_audit_receipt':ref(ROOT/'controls_a_APRE_offline_integrity_audit.json'),
        'annual_probe_receipt':ref(ROOT/'controls_a_sec_probes.json'),
        'annual_identity_audit_receipt':ref(ROOT/'controls_a_annual_identity_audit.json'),
        'alternate_issuer_route_evidence':{'web_capture_receipt':ref(ROOT/'controls_a_html_routes.json'),
            'working_representations':[{'ticker':'ARQT','source_uri':'https://investors.arcutis.com/node/8361/html','filing_date':'2021-06-14','format':'web_tool_text_representation','publisher_response_bytes_archived':False},
               {'ticker':'BEAM','source_uri':'https://investors.beamtx.com/node/6916/html','filing_date':'2021-01-12','format':'web_tool_text_representation','publisher_response_bytes_archived':False,'notes':'Parent8-K and Exhibit99.1 slides appear inline; graphical content would require separate review.'}],
            'failed_representation':{'ticker':'ALT','source_uri':'https://ir.altimmune.com/node/13801/html','status':'web_tool_fetch_error','filing_date':'2021-06-16'}},
        'preserved_alternative_source_failures':failures,
        'limitations':collection['source_version_limitations']+[
            'Search absence and transport failure are not negative outcomes.',
            'An annual report alone does not establish complete baseline/outcome coverage.',
            'APRE graphics are retained as source-container payloads; their substantive information has not yet been reviewed.',
            'No model, labels, panel admission or historical label clock changed.']}
(ROOT/'controls_a.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Primary source research: comparison issuers A','',f'Reviewed {now}. Codex primary-source research; no independent human review.','',
 '**Nine original SEC annual-report routes work. APRE now has a complete collected source corpus for the selected filing scope, but no new negative outcome is approved.**','',
 'The search covers the 2020 pending-deal baseline, the 2021 outcome window and reporting lag through March31,2022. Each failed alternate request remains recorded; no failure or search absence was converted into a negative.','',
 '| Issuer | Source-backed result | Remaining source work |','|---|---|---|']
for r in issuer_results:
 a=r['annual_report']; lines.append(f"| {r['ticker']} | [FY2021 SEC10-K]({a['source_uri']}) filed {a['publication_date']}; CIK/ticker/FY identity and SHA verified | "+('All42 selected accession indexes and complete submissions archived; substantive review pending' if r['ticker']=='APRE' else f"{r['selected_material_accession_candidates']} selected accession candidates in the prior inventory; complete corpus and exhibits remain uncollected")+' |')
lines += ['', 'APRE has a fresh, effective-URL-verified SEC search inventory of124 all-form results across2 pages. Applying the unchanged material-form selection gives exactly the42 archived accessions. Their707 embedded documents include257 indexed document-format entries:117 parents/exhibits and140 graphics. All42 submission byte lengths match their SEC accession index sizes, totaling57,198,252 bytes. Source hashes, subject CIK, filing identity, embedded byte ranges, document counts and indexed filenames replay successfully.','',
 'The exact currently served SEC bytes are retained. This does not independently prove byte-for-byte identity at original acceptance; current SEC indexes or sources may contain corrections or removals. Embedded hashes bind verbatim TEXT payloads inside complete submission containers, including encoded graphics, and are not individual HTTP-download or decoded-image hashes.','',
 'The next gate is substantive review of the original filing text and exhibit graphics for pending control deals, outcome events and censoring, plus listing/version evidence and an explicit verifier for this SEC-container format. The existing issuer-mirror verifier must not silently mislabel these bytes as issuer mirrors. No labels, panel rows or model eligibility changed.','',
 'Bound receipts: [discovery ledger](controls_a.json), [APRE collection](controls_a_APRE_complete_submission_collection.json), [offline integrity audit](controls_a_APRE_offline_integrity_audit.json), [annual identity audit](controls_a_annual_identity_audit.json), and [fresh APRE inventory](APRE_fresh_inventory/APRE_2020-01-01_2022-03-31.json). Original response bodies are local in raw_controls_a/.','']
(ROOT/'controls_a.md').write_text('\n'.join(lines))
print(json.dumps({'ledger':str(ROOT/'controls_a.json'),'sha256':sha(ROOT/'controls_a.json'),'APRE_collection_sha256':sha(collection_path),'audit_passed':True,'new_negative_labels':0},indent=2))
