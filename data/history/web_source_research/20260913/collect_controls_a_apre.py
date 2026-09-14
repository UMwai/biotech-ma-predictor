"""Archive APRE's fixed selected SEC accessions; collection is not outcome review.

Every submission is linked from its actual SEC index. Each embedded document
retains byte offsets and a digest within the archived submission container.
No original download or timestamp is invented for the derived document blocks.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse, parse_qs

from probe_controls_a import ROOT, REPO, fetch, inventories, stamp

EXCLUDED = {'3','3/A','4','4/A','5','5/A','144','SC 13G','SC 13G/A',
            'SCHEDULE 13G','SCHEDULE 13G/A','CT ORDER','UPLOAD','CORRESP',
            'EFFECT','S-8','S-8 POS','ARS'}

class FilingIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.section = None
        self.row = None
        self.cell = None
        self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            self.section = attrs.get('summary')
        if tag == 'tr' and self.section:
            self.row = {'section':self.section, 'cells':[], 'links':[]}
        if tag == 'td' and self.row is not None:
            self.cell = []
        if tag == 'a' and self.row is not None and attrs.get('href'):
            self.row['links'].append(attrs['href'])
    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.row['cells'].append(' '.join(''.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            if self.row['cells']:
                self.rows.append(self.row)
            self.row = None
        if tag == 'table':
            self.section = None
    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

def parse_submission(body):
    records = []
    for match in re.finditer(rb'<DOCUMENT>\s*(.*?)</DOCUMENT>', body, re.S):
        block = match.group(1)
        fields = {}
        for name in ('TYPE','SEQUENCE','FILENAME','DESCRIPTION'):
            hit = re.search(rb'(?:^|\n)<' + name.encode() + rb'>([^\r\n]*)', block)
            fields[name.lower()] = hit.group(1).decode('utf-8','replace').strip() if hit else None
        text = re.search(rb'<TEXT>(.*?)</TEXT>\s*$', block, re.S)
        if not text or not fields['filename']:
            raise ValueError('Unrecognized document block')
        payload = text.group(1)
        fields.update(container_text_start=match.start(1)+text.start(1),
                      container_text_end=match.start(1)+text.end(1),
                      embedded_document_sha256=hashlib.sha256(payload).hexdigest(),
                      embedded_document_bytes=len(payload),
                      representation='verbatim_TEXT_payload_in_original_SEC_submission')
        records.append(fields)
    count = re.search(rb'PUBLIC DOCUMENT COUNT:\s*(\d+)', body[:100_000])
    return records, int(count.group(1)) if count else None

def canonical_document(url):
    parsed = urlparse(url)
    if parsed.path in ('/ix', '/ixviewer/doc/action') and parse_qs(parsed.query).get('doc'):
        return urljoin('https://www.sec.gov',parse_qs(parsed.query)['doc'][0])
    return url

def main():
    destination = ROOT / 'controls_a_APRE_complete_submission_collection.json'
    if destination.exists():
        raise SystemExit('Existing collection receipt retained; no automatic retries')
    cached = json.loads((ROOT/'controls_a_sec_probes.json').read_text())
    cached += [json.loads((ROOT/name).read_text()) for name in
               ('controls_a_APRE_index_probe.json','controls_a_APRE_submission_probe.json')]
    cache = {r['source_uri']:r for r in cached if r.get('original_bytes_archived')}
    source_inventories = []
    selected = []
    for path in inventories('APRE'):
        data = json.loads(path.read_text())
        source_inventories.append({'source_relative_path':str(path.relative_to(REPO)),
                                  'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                  'start_date':data['start_date'],'end_date':data['end_date'],
                                  'transport_identity_verified':False,
                                  'limitation':'Legacy inventory did not capture effective response URL.'})
        selected.extend(row for row in data['records'] if row['form'] not in EXCLUDED)
    selected.sort(key=lambda row:(row['filed_date'],row['accession']))
    result = {'schema_version':'sec-complete-submission-collection-v1','ticker':'APRE','cik':1781983,
              'started_at':stamp(),'source_inventories':source_inventories,
              'excluded_forms':sorted(EXCLUDED),'selected_accession_count':len(selected),
              'accessions':[],'collection_complete':False,'outcome_label':None,
              'full_text_outcome_review_complete':False,
              'limitations':['Discovery indexes observed in 2026 can reflect removals or corrections.',
                  'Original SEC submission containers preserve filing text and attachments, but collection alone is not substantive outcome adjudication.',
                  'SEC acceptance datetime is retained as source text; this collector does not invent its timezone or a historical label clock.',
                  'XBRL display files generated outside the complete submission may require separate retrieval if used; document-format parents and exhibits must reconcile.']}
    def save():
        destination.write_text(json.dumps(result,indent=2)+'\n')
    def obtain(url,context):
        if url in cache:
            r=cache[url]
            body=(ROOT/r['source_relative_path']).read_bytes()
            if hashlib.sha256(body).hexdigest()!=r['source_sha256']:
                raise ValueError('Cached bytes changed')
            return r
        r=fetch(url,context,max_bytes=80_000_000)
        cache[url]=r
        return r
    for row in selected:
        uri=next(u for u in row['candidate_document_uris'] if '/data/1781983/' in u)
        index_uri=uri.rsplit('/',1)[0]+'/'+row['accession']+'-index.html'
        item={'accession_number':row['accession'],'publication_date':row['filed_date'],
              'form':row['form'],'candidate_parent_uri':uri,
              'associated_ciks':row['ciks'],'index':None,'submission':None,
              'document_format_inventory':[],'embedded_documents':[],
              'accession_source_complete':False,'outcome_label':None}
        result['accessions'].append(item)
        context={'ticker':'APRE','cik':1781983,'accession_number':row['accession'],
                 'publication_date':row['filed_date'],'form':row['form']}
        idx=obtain(index_uri,dict(context,role='accession_document_inventory'));item['index']=idx
        if not idx.get('original_bytes_archived') or not idx.get('transport_identity_verified'):
            save();print(row['accession'],'index unavailable',flush=True);continue
        index_body=(ROOT/idx['source_relative_path']).read_bytes()
        parser=FilingIndex();parser.feed(index_body.decode('utf-8','replace'))
        item['document_format_inventory']=[r for r in parser.rows if r['section']=='Document Format Files']
        item['data_file_inventory']=[r for r in parser.rows if r['section']=='Data Files']
        links=[link for r in parser.rows if 'Complete submission text file' in r['cells'] for link in r['links']]
        if len(links)!=1:
            item['failure']='Missing or ambiguous complete submission link';save();continue
        submission_uri=urljoin(index_uri,links[0])
        if urlparse(submission_uri).netloc!='www.sec.gov' or '/'+row['accession'].replace('-','')+'/' not in submission_uri:
            item['failure']='Submission link identity mismatch';save();continue
        sub=obtain(submission_uri,dict(context,role='complete_submission_container'));item['submission']=sub
        if not sub.get('original_bytes_archived') or not sub.get('transport_identity_verified'):
            save();print(row['accession'],'submission unavailable',flush=True);continue
        body=(ROOT/sub['source_relative_path']).read_bytes()
        try:
            documents,count=parse_submission(body)
            item['embedded_documents']=documents
            item['declared_public_document_count']=count
            header=body.split(b'</SEC-HEADER>',1)[0]
            accession=re.search(rb'ACCESSION NUMBER:\s*([^\r\n]+)',header)
            filed=re.search(rb'FILED AS OF DATE:\s*(\d{8})',header)
            accepted=re.search(rb'<ACCEPTANCE-DATETIME>(\d{14})',header)
            item['source_acceptance_datetime_local_unresolved']=accepted.group(1).decode() if accepted else None
            item['header_identity_verified']=bool(accession and accession.group(1).decode().strip()==row['accession'] and
                                                   filed and filed.group(1).decode()==row['filed_date'].replace('-',''))
            names={d['filename'] for d in documents}
            expected=[]
            for r in item['document_format_inventory']:
                if 'Complete submission text file' in r['cells']:
                    continue
                if len(r['links'])!=1:
                    raise ValueError('Document row lacks unique link')
                url=canonical_document(urljoin(index_uri,r['links'][0]))
                r['canonical_document_uri']=url
                expected.append(urlparse(url).path.rsplit('/',1)[-1])
            item['missing_document_format_filenames']=sorted(set(expected)-names)
            item['all_embedded_documents_count_verified']=count==len(documents)
            item['parent_present']=row['document_name'] in names
            item['accession_source_complete']=bool(item['header_identity_verified'] and item['parent_present'] and
                item['all_embedded_documents_count_verified'] and not item['missing_document_format_filenames'] and
                body.rstrip().endswith(b'</SEC-DOCUMENT>'))
        except ValueError as error:
            item['failure']=str(error)
        save();print(row['accession'],item['accession_source_complete'],len(item['embedded_documents']),flush=True)
    result['completed_at']=stamp()
    result['source_complete_accession_count']=sum(i['accession_source_complete'] for i in result['accessions'])
    result['collection_complete']=result['source_complete_accession_count']==len(selected)
    result['embedded_document_count']=sum(len(i['embedded_documents']) for i in result['accessions'])
    save()

if __name__=='__main__':
    main()
