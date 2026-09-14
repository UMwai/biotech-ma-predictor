"""Materialize Codex's completed, explicitly assisted review; no network or label join.

This is an annotation writer for these two reviewed corpora, not an automatic
negative-label generator. Changing the corpus invalidates its fixed index audit.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
REVIEWER = 'Codex-primary-source-review'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def receipt(path):
    return {'source_relative_path': path.name, 'source_sha256': sha(path.read_bytes())}

def write(name, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path = ROOT / name
    path.write_bytes(raw)
    frozen = path.with_name(path.stem + '-' + sha(raw) + path.suffix)
    if frozen.exists():
        assert frozen.read_bytes() == raw
    else:
        frozen.write_bytes(raw)
    return receipt(frozen)

CDXS = {
0:'Public underwritten offering of 4,285,715 new shares at $17.50, plus an overallotment option; issuance to finance the issuer, not acquisition of its outstanding control.',
5:'Amendment reports Jennifer Aaker committee assignment following her independent director appointment.',
17:'Quarterly earnings and independent director Jennifer Aaker appointment; board expansion and director equity compensation are not a transfer of company control.',
19:'Ordinary annual meeting director elections, auditor ratification and advisory compensation vote.',
20:'Proxy supplement updates Stephen Dilly biography after his appointment at Sierra Oncology; no Codexis merger proposal.',
29:'Annual-meeting notice covers directors, auditor and compensation votes; no company sale vote.',
31:'Takeda/Shire gene-therapy research and product license: Codexis retains protein-sequence IP; $8.5m upfront plus research fees, milestones and royalties. Full embedded EX99.1 is included after signature. No target equity/control purchase.',
50:'Identifies Pfizer as the customer for previously reported enzyme purchase orders; manufacturing product sales, not Codexis equity acquisition.',
51:'Extends the Merck sitagliptin catalyst supply agreement through 2026; commercial enzyme supply, not company control.',
53:'Approximately $15m enzyme purchase orders from a pharmaceutical customer; product purchases, not a whole-company acquisition.',
60:'Approximately $13.9m binding enzyme purchase order; product manufacturing transaction, not a control transaction.',
61:'Ordinary annual meeting election of directors and auditor ratification; Byron Dorgan becomes chair following Bernard Kelley retirement.',
62:'Piper Sandler at-the-market equity distribution facility up to $50m; public financing, not acquisition of outstanding company control.',
77:'Annual-meeting voting notice for directors and auditor; no company sale proposal.',
87:'Amendment reports Esther Martinborough science committee assignment following her director appointment.',
88:'Schedule13D reports CEO John Nicols beneficial ownership of 6.13%, including options and trusts; Item4 describes employment awards, prior purchases and offering lockup, with no current control-transaction proposal. This minority stake does not establish control.',
89:'ARE lease of additional office/laboratory space in San Carlos; landlord remedies are conditional default terms, not an actual bankruptcy or company sale.',
90:'Independent director Esther Martinborough appointment and restricted-stock compensation; no control transfer.',
}
STRO = {
0:'Underwritten issuance of 6m common shares at $21 plus overallotment, financing clinical development and working capital; no purchase of outstanding company control.',
8:'STRO-001 phase1 lymphoma clinical data, safety and enrollment update.',
10:'STRO-002 phase1 ovarian cancer dose-escalation results and clinical presentation; patient response is not corporate control.',
13:'Independent director Jon Marc Wigginton appointment and ordinary option compensation.',
22:'Corporate conference presentation and STRO-002 clinical update.',
25:'Sublease from Five Prime Therapeutics for office/laboratory premises. Five Prime is the landlord counterparty, not buyer or seller of Sutro control.',
33:'Corporate presentation at the Raymond James healthcare conference.',
35:'Ordinary annual meeting director elections and auditor ratification, with no merger proposal.',
36:'Underwritten issuance of 11m new common shares at $7.75 plus overallotment, funding development and working capital.',
48:'10-K/A expressly refiles certifications only; it does not revise the original financial or business disclosures or claim to update subsequent events.',
51:'Preliminary cash position and STRO-002 phase1 clinical response update with presentation.',
67:'Oxford/Silicon Valley Bank $25m secured term loan refinances prior debt; 81,257 warrants are minority financing instruments. Merger/default clauses are contingent contract provisions.',
68:'Independent director James Panek appointment and ordinary option compensation.',
69:'Tasly exclusive Greater China STRO-002 product license; Sutro retains rights elsewhere. Upfront/milestone/royalty economics do not transfer Sutro corporate control.',
70:'Independent director Heidi Hunter appointment and ordinary director option compensation.',
71:'Quarterly financial results and corporate product-development presentation.',
80:'BioNova option to license STRO-001 in Greater China; Sutro retains rights outside that territory. Product license is not an option over Sutro shares or whole-company control.',
81:'Merck cytokine research-program extension, with $2.5m payment and possible development milestones; no company acquisition.',
90:'Five-year extension of San Carlos manufacturing facility lease; property use transaction, not transfer of company control.',
91:'Ordinary annual meeting director elections and auditor ratification.',
92:'STRO-002 dose-escalation data and corporate presentation, not a corporate-control announcement.',
104:'Merck $15m development milestone for IND-enabling toxicology; product collaboration payment, not acquisition.',
121:'POS AM converts a shelf registration to the correct non-automatic form after loss of well-known-seasoned-issuer status. It registers financing capacity; no delisting, insolvency or company sale.',
137:'Post-effective shelf amendment reflects anticipated loss of well-known-seasoned-issuer status and registration of $350m securities/$100m ATM capacity; issuer remains Nasdaq listed.',
141:'Corporate presentation at the January2022 J.P. Morgan conference.',
143:'STRO-002 ovarian cancer dose-expansion efficacy and safety update, including a trial-protocol change; clinical adverse events do not establish corporate censoring.',
}

CONTRACTS = {
'CDXS':{1:'December2020 public offering underwriting',7:'Western Alliance eighth loan amendment',22:'Takeda gene-therapy research/product license, including original press release in ExhibitF',23:'GSK platform technology license amendment',33:'description of common-share voting, liquidation and anti-takeover rights',43:'Merck sitagliptin supply extension',44:'Western Alliance ninth loan amendment',63:'Piper Sandler ATM distribution',67:'form indenture with conditional successor/default clauses',71:'ARE office/laboratory lease',92:'description of common-share voting, liquidation and anti-takeover rights',93:'2015 Merck platform technology-transfer and license agreement, refiled in2022'},
'STRO':{1:'December2020 public offering underwriting',17:'Five Prime premises sublease and master-lease terms',37:'May2020 public offering underwriting',58:'description of capital-stock and conditional anti-takeover/liquidation rights',59:'Oxford/Silicon Valley Bank secured term loan; delisting appears in conditional default definition',60:'minority lender warrant with conditional merger treatment',61:'minority lender warrant with conditional merger treatment',75:'Merck research-program extension and milestone amendment',85:'Alemany premises lease extension',98:'severance and change-in-control compensation plan, not an announced control transaction',106:'Jefferies ATM sales agreement',107:'form debt security',108:'form indenture with conditional default/successor terms',114:'Linda Fitzpatrick employment offer and compensation',115:'severance and change-in-control compensation plan, not an announced control transaction',127:'Edward Albini employment offer and compensation',128:'BioNova Greater China STRO-001 option/product license',129:'Tasly Greater China STRO-002 product license',130:'Jane Chung employment offer and compensation',131:'Arturo Molina employment offer and compensation'}
}

def reason(ticker, record):
    i, form, text = record['index'], record['document_type'], record['full_text']
    specific = (CDXS if ticker == 'CDXS' else STRO).get(i)
    if specific:
        return specific
    if i in CONTRACTS[ticker]:
        return 'Reviewed ' + CONTRACTS[ticker][i] + '. Transaction/control/insolvency wording was assessed in this contract context; no actual target-control or censoring event is disclosed.'
    if form in {'10-K','10-Q'}:
        extra = (' Historical Maxygen IP purchase in2010, liquidation of an Indian subsidiary begun2016, and CO2 Solutions investment bankruptcy in2019 concern assets/other entities, not acquisition or cessation of the Codexis parent.' if ticker == 'CDXS' else ' BMS acquisition of Celgene is a counterparty event in2019; it transfers collaboration obligations, not Sutro ownership. Product licenses and Vaxcyte investment holdings are distinct from parent control.')
        return 'Original periodic report business, material agreements, liquidity, risk and financial-note event language reviewed with the declared assisted screen. Conditional takeover/default and compensation clauses are not event announcements.' + extra
    if form in {'8-K','8-K/A'}:
        assert 'financial results' in text.lower()
        return 'Quarterly or annual operating results disclosure and attached financial release; no target-control or censoring announcement in the reviewed subject or attached text.'
    if form.startswith('EX-99'):
        return ('Financial results, commercial product development or clinical/corporate presentation. All full-text acquisition/censoring triggers were reviewed: property purchases, ordinary share financing, product-license economics, clinical majority counts and conditional securities notices do not announce target control or corporate cessation.' if record['trigger_contexts'] else 'Full extracted financial/clinical/corporate disclosure screened; no acquisition/censoring trigger. Header and parent filing identify a routine operating disclosure; parent subject and event-candidate review found no control or cessation announcement.')
    if form in {'DEF 14A','DEFA14A'}:
        return 'Ordinary annual proxy: director elections, governance, auditor/compensation matters. Biographical acquisitions refer to other employers; conditional equity-plan/control provisions do not announce a target merger.'
    if form in {'424B5','S-3ASR','S-3MEF'}:
        return 'Public offering/shelf financing prospectus. Common-equity sales, potential future uses of proceeds and generic merger/anti-takeover terms are not an announced acquisition of the issuer.'
    if form.startswith(('EX-31','EX-32','EX-23','EX-21')):
        return 'Officer financial-report certification, auditor/legal consent or subsidiary list accompanying the identified parent filing; complete text screening found no separate target-control or censoring announcement.'
    if form.startswith('EX-5') or form == 'EX-FILING FEES':
        return 'Securities-registration legal opinion/consent or filing-fee schedule; bankruptcy/equity terms describe legal enforceability or registered financing, not actual issuer bankruptcy or acquisition.'
    raise ValueError((ticker,i,form))

def main():
    reviewed = datetime.now(timezone.utc).isoformat()
    method = ('Automated full-text broad lexical screening of every extracted accession document, followed by documented document/subject triage; Codex reviewed every 8-K subject section, every financial-release/presentation trigger, every distinct high-signal control/censoring sentence and nonconditional acquisition/insolvency sentence in periodic/proxy reports, plus baseline business/material-agreement/subsequent-event and listing sections. Recurrent legal definitions, prospective risk statements, financing and compensation clauses were assigned contextual dispositions using the reviewed document subject. Full_text_review_complete and all_trigger_contexts_reviewed mean completion of this assisted method, not manual reading of every full legal document or every repeated broad context. No independent human review.')
    for ticker,cik,expected in [('CDXS',1200375,101),('STRO',1382101,146)]:
        pending_path=ROOT/f'{ticker}_pending_regulatory_review.json'
        expected_hash={'CDXS':'5c3713de8d71252e53af971c36afc8a37d94155ec37f2b715e931bde20b20e61','STRO':'b78d15a60e8aab1d37851ab0d5c23819321571c3ec2a85c9b36f14ced914309b'}[ticker]
        assert sha(pending_path.read_bytes())==expected_hash, 'Corpus changed: new substantive review required'
        pending=json.loads(pending_path.read_bytes())
        records=pending['records']; assert len(records)==expected
        inventory=ROOT/f'{ticker}_regulatory_inventory.json'
        documents=ROOT/f'{ticker}_accession_documents.json'
        dispositions=[]; annotations=[]
        for r in records:
            raw=(ROOT/f'{ticker}_sources'/r['source_relative_path']).read_bytes()
            assert sha(raw)==r['source_sha256'] and sha(r['full_text'].encode())==r['full_text_sha256']
            explanation=reason(ticker,r)
            for n,c in enumerate(r['trigger_contexts']):
                assert r['full_text'][c['start']:c['end']]==c['text']
                dispositions.append({'document_url':r['document_url'],'context_index':n,'context_sha256':sha(c['text'].encode()),'start':c['start'],'end':c['end'],'disposition':'nonqualifying_in_reviewed_document_context','method':'assisted document-context triage; see review_method','evidence_paraphrase':explanation})
            sec=f'https://www.sec.gov/Archives/edgar/data/{cik}/{r["accession_number"].replace("-", "")}/{urlsplit(r["document_url"]).path.rsplit("/",1)[-1]}'
            annotations.append({'document_url':r['document_url'],'accession_number':r['accession_number'],'publication_date':r['publication_date'],'extracted_text_sha256':r['full_text_sha256'],'extraction_selector':'#document-wrap','reviewed_at':reviewed,'reviewer':REVIEWER,'qualifying_control_event_found':False,'censoring_event_found':False,'trigger_context_review_complete':True,'trigger_context_count':len(r['trigger_contexts']),'evidence_paraphrase':explanation,'version_status':'verified_original','original_sec_document_bytes_archived':False,'original_source_sha256':None,'source_version_classification':'reviewed original filing text in issuer accession-specific mirror; not SEC-byte identity','original_version_evidence':{'source_uri':r['document_url'],'source_sha256':r['source_sha256'],'immutable_document_uri':sec,'source_locator':f'Issuer filing inventory binds {r["accession_number"]}, {r["parent_form"]}, {r["publication_date"]}; accession document navigation and #document-wrap preserve {r["document_type"]} under the same original filename. Opening original text: '+r['full_text'][:240],'source_content_format':'issuer_accession_filing_mirror_html','original_sec_document_bytes_archived':False,'original_source_sha256':None}})
        context_receipt=write(f'{ticker}_regulatory_context_dispositions.json',{'schema_version':'assisted-regulatory-context-dispositions-v1','reviewed_at':reviewed,'reviewer':REVIEWER,'method':method,'extracted_corpus_receipt':receipt(pending_path),'screen_pattern':pending['screen_pattern'],'full_text_characters_screened':sum(r['full_text_characters'] for r in records),'contexts':dispositions})
        embedded=[]
        for parent,number,containing,locator,description in ([(0,'23.1',2,'Consent paragraph of EX5.1','Counsel consent is explicitly included in the legal opinion.'),(31,'99.1',31,'After SIGNATURE, Exhibit99.1 heading and full Codexis/Takeda release','The entire March23 product-license announcement follows the 8-K signature in the same HTML; also reproduced in May8 EX10.1 ExhibitF.'),(62,'23.1',64,'Consent paragraph of EX5.1','Counsel consent is explicitly included in the legal opinion.')] if ticker=='CDXS' else [(0,'23.1',2,'Consent paragraph of EX5.1','Counsel consent is contained in the legal opinion.'),(36,'23.1',38,'Consent paragraph of EX5.1','Counsel consent is contained in the legal opinion.')]):
            c=records[containing];embedded.append({'parent_document_url':records[parent]['document_url'],'exhibit_number':number,'containing_document_url':c['document_url'],'source_sha256':c['source_sha256'],'extracted_text_sha256':c['full_text_sha256'],'source_locator':locator,'evidence_paraphrase':description})
        annuals=[records[i] for i in ([32,79,91] if ticker=='CDXS' else [57,113,126])]
        listing=annuals[-1]
        baseline={'period_start':'2020-01-01','observation_at':'2021-01-01T00:00:00+00:00','public_pending_control_transaction_found':False,'method':'Original FY2019 annual business/material-contract/financial-note review, complete 2020 selected material filing corpus, corroboration in original FY2020 annual. Known counterparty acquisitions, minority holdings, product licenses and conditional contracts separately adjudicated; no all-since-IPO or all-world coverage claim.','annual_source_urls':[r['document_url'] for r in annuals[:2]],'evidence_paraphrase':('FY2019 subsequent event is Nestle CDX-7108 development agreement; FY2020 subsequent event is ARE premises lease. Commercial agreements and public offerings do not transfer parent control.' if ticker=='CDXS' else 'FY2019 subsequent events describe Oxford/SVB refinancing and warrants. FY2020 business and organization/financing notes describe independent drug development, collaboration contracts and completed public share offerings; no pending Sutro control sale identified.')}
        membership={'security_type':'common_stock','exchange':('Nasdaq Global Select Market' if ticker=='CDXS' else 'Nasdaq Global Market'),'ticker':ticker,'cik':cik,'source_uri':listing['document_url'],'source_sha256':listing['source_sha256'],'extracted_text_sha256':listing['full_text_sha256'],'source_locator':'Item5 Market Information and Stock Price/Stock Performance Graph narrative and dated table','reviewed_interval_start':'2021-01-01','reviewed_interval_end':'2021-12-31','evidence_paraphrase':('Original2021 annual identifies CDXS Nasdaq common stock and reports its common-stock total-return series for Dec31,2016 through Dec31,2021. Intervening complete material filing review has no delisting/control cessation notice; actual underwriting/ATM agreements expressly deny listing-termination actions/notices.' if ticker=='CDXS' else 'Original2021 annual identifies STRO Nasdaq common stock and explicitly describes shareholder returns from Sep27,2018 first trading day through Dec31,2021, with dated quarterly table. Complete intervening material filings contain no listing cessation/control notice. FY2019 annual separately states listing sinceSep27,2018.')}
        result={'schema_version':'issuer-regulatory-outcome-review-v1','issuer':{'ticker':ticker,'cik':cik},'observation_at':'2021-01-01T00:00:00+00:00','horizon_end_at':'2022-01-01T00:00:00+00:00','inventory_start_date':'2020-01-01','inventory_end_date':'2022-03-31','retrospective_ascertainment_available_at':'2022-04-01T12:00:00+00:00','reviewed_at':reviewed,'reviewer':REVIEWER,'source_directory':f'{ticker}_sources','inventory_receipt':receipt(inventory),'documents_receipt':receipt(documents),'context_dispositions_receipt':context_receipt,'document_reviews':annotations,'embedded_exhibit_coverage':embedded,'review_method':method,'full_text_review_complete':True,'all_trigger_contexts_reviewed':True,'censoring_review_complete':True,'known_missing_sources':False,'qualifying_control_event_found':False,'censoring_event_found':False,'source_content_format':'issuer_accession_filing_mirror_html','original_sec_document_bytes_archived':False,'original_source_sha256':None,'source_version_classification':'reviewer-verified accession-specific original filing text represented by current issuer mirror bytes; distinct from mutable current news-release copies','scope':'Complete issuer all-form archive pages for2020/2021/2022, selecting all material forms dated Jan1,2020 through Mar31,2022 under the recorded exclusion list, with every same-accession HTML filing/exhibit and listed embedded8-K exhibits reconciled. Excluded duplicate complete-filing PDFs, XBRL, figure images, mechanical ownership/employee registrations/ARS duplicates. No separately listed material PDF-only exhibit found. Full text means extracted original document text; figures and incorporated historical exhibits are not separately image-read or recursively recollected. Baseline and outcome judgments use the full declared filing corpus, not current survival or absence from positive seeds.','removed_page_limitations':'Current issuer filing archive is the designated inventory. This is a complete surviving source-specific corpus under the declared form scope, not proof that no omitted/corrected filing or undisclosed event exists. No contemporaneous crawl is claimed; original accession-specific presentations were retrieved and reviewed in2026. Errors discovered later must supersede this review rather than rewrite source bytes.','source_version_limitations':'Hashes bind actual current issuer accession-mirror HTML and exact extracted text, not byte equality to SEC-hosted HTML. Original-version status is a review judgment from explicit filing accession/form/filename identity and embedded dated original disclosures, corroborated at selected SEC original sections. SEC browser responses are separate corroboration representations; no original SEC-document byte hash is asserted. Date-only archive publication uses conservative uncertainty bounds, not invented exact acceptance timestamps. News-archive current copies remain current and are not promoted by this review.','baseline_review':baseline,'membership_review':membership,'sec_browser_corroboration_receipt':receipt(ROOT/f'{ticker}_sec_browser_corroboration.json'),'training_allowed':False,'training_note':'This reviewed outcome corpus alone is not a fitted model or complete panel; separate financial feature, fixed-frame membership, temporal lineage and training-support gates remain required.'}
        out=write(f'{ticker}_regulatory_outcome_review_2021.json',result)
        print(ticker,out)

if __name__=='__main__':
    main()
