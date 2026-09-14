from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin,urlsplit
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from collect_issuer_archives import Store,Document,clean
BASE=Path(__file__).resolve().parent

def collect(ticker):
 D=BASE/(ticker+'_sources');store=Store(D);m=json.loads((BASE/(ticker+'_regulatory_bodies.json')).read_text());required=[];seen=set();parents=[]
 for p in m['body_receipts']:
  raw=(D/p['source_relative_path']).read_bytes();root=Document(raw).root;box=root.find(ident='sec-filing-header--document-box');assert len(box)==1
  links=[{'document_url':p['document_url'],'document_type':p['form'],'parent_document_url':p['document_url'],'parent_form':p['form'],'publication_date':p['publication_date'],'accession_number':p['accession_number']}]
  if p['document_url'] not in seen:seen.add(p['document_url']);required.append(links[0])
  for a in box[0].find('a'):
   u=urljoin(p['document_url'],a.attrs.get('href',''));ext=urlsplit(u).path.rsplit('.',1)[-1].lower()
   if ext in ['htm','html'] and '/content/'+p['accession_number']+'/' in u:
    item={'document_url':u,'document_type':clean(a).replace(' »',''),'parent_document_url':p['document_url'],'parent_form':p['form'],'publication_date':p['publication_date'],'accession_number':p['accession_number']}
    if u not in {r['document_url'] for r in links}:links.append(item)
    if u not in seen:seen.add(u);required.append(item)
  assert p['document_url'] in {r['document_url'] for r in links}
  parents.append({'parent_document_url':p['document_url'],'accession_number':p['accession_number'],'documents':links,'publisher_navigation_source_sha256':p['source_sha256']})
 def fetch(row):
  try:raw,s=store.fetch(row['document_url']);return {**row,**s,'status':'archived'}
  except Exception as e:return {**row,'status':'blocked','error':str(e)}
 with ThreadPoolExecutor(max_workers=3) as ex:docs=list(ex.map(fetch,required))
 data={'schema_version':'issuer-accession-document-inventory-v1','issuer':ticker,'parent_filings':parents,'documents':docs,'all_designated_html_documents_archived':all(r['status']=='archived' for r in docs),'scope':'Every HTML document actually linked by the original accession mirror navigation, including exhibits; XBRL/XML/images and full-submission PDF duplicates excluded. Incorporated historical references are not represented as newly published current documents.','training_allowed':False}
 b=(json.dumps(data,indent=2,sort_keys=True)+'\n').encode();sha=hashlib.sha256(b).hexdigest();(BASE/(ticker+'_accession_documents.json')).write_bytes(b);(BASE/(ticker+'_accession_documents-'+sha+'.json')).write_bytes(b)
 print(json.dumps({'ticker':ticker,'parent_filings':len(parents),'documents':len(docs),'archived':sum(r['status']=='archived' for r in docs),'sha256':sha}),flush=True)
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(collect,['CDXS','STRO']))
