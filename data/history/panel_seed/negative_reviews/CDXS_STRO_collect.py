"""Bounded public issuer SEC inventories and original filing mirrors; no labels."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import sys,json,re,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from collect_issuer_archives import Store,Document,clean
BASE=Path(__file__).resolve().parent
SITES={'CDXS':'https://ir.codexis.com/sec-filings/all-sec-filings','STRO':'https://ir.sutrobio.com/financials/sec-filings'}
EXCLUDE={'3','3/A','4','4/A','5','5/A','144','SC 13G','SC 13G/A','SCHEDULE 13G','SCHEDULE 13G/A','CT ORDER','UPLOAD','CORRESP','EFFECT','S-8','S-8 POS','ARS'}
def parse(raw,url,year,page):
 root=Document(raw).root
 selected=[clean(o) for s in root.find('select',ident='year') for o in s.find('option') if 'selected' in o.attrs]
 assert selected==[str(year)],selected
 tables=root.find('table','spr-ir-sec-filings');assert len(tables)==1
 rows=[]
 for tr in tables[0].find('tr'):
  td=tr.find('td')
  if not td:continue
  day=datetime.strptime(clean(td[0]),'%m/%d/%y').date();assert day.year==year
  links=tr.find('a','doc-title');assert len(links)==1
  link=urljoin(url,links[0].attrs['href']);match=re.search(r'/content/(\d{10}-\d{2}-\d{6})/',link);assert match,link
  rows.append({'publication_date':day.isoformat(),'form':clean(td[1]),'title':clean(links[0]),'document_url':link,'accession_number':match[1],'index_url':url,'archive_year':year,'archive_page':page})
 links=[a for n in root.find(cls='pagination-wrapper') for a in n.find('a')];current=[clean(a) for a in links if a.attrs.get('aria-current')=='page'];assert current==[f'Page {page}']
 total=max(int(clean(a).split()[1]) for a in links if re.fullmatch(r'Page \d+',clean(a)))
 nxt=[a.attrs['href'] for a in links if clean(a).startswith('Next Page')]
 assert len(rows)>0 and (page==total or len(rows)==10) and bool(nxt)==(page<total)
 return rows,{'page':page,'total_pages':total,'entry_count':len(rows),'next_url':urljoin(url,nxt[0]) if nxt else None}
def collect(ticker):
 D=BASE/(ticker+'_sources');store=Store(D);pages=[];rows=[]
 for year in [2020,2021,2022]:
  url=SITES[ticker]+f'?form_type=&year={year}';page=1
  while url:
   raw,source=store.fetch(url);got,pager=parse(raw,url,year,page);pages.append({**source,**pager,'archive_year':year});rows.extend(got);url=pager['next_url'];page+=1;assert page<50
 assert len({r['accession_number'] for r in rows})==len(rows)
 selected=[r for r in rows if r['publication_date']<='2022-03-31' and r['form'] not in EXCLUDE]
 receipt={'schema_version':'issuer-regulatory-inventory-v1','issuer':ticker,'retrieved_at':datetime.now(timezone.utc).isoformat(),'scope':'Current designated issuer all-form SEC inventory for2020–2022; material sources selected through March31,2022 reporting lag. No outcome label or original-version assertion is assigned automatically.','inventory_complete':True,'all_form_inventory':rows,'pages':pages,'excluded_form_types':sorted(EXCLUDE),'required_material_documents':selected,'training_allowed':False}
 b=(json.dumps(receipt,indent=2,sort_keys=True)+'\n').encode();sha=hashlib.sha256(b).hexdigest();(BASE/(ticker+'_regulatory_inventory.json')).write_bytes(b);(BASE/(ticker+'_regulatory_inventory-'+sha+'.json')).write_bytes(b)
 print(json.dumps({'ticker':ticker,'pages':len(pages),'all_form_rows':len(rows),'forms':{form:sum(r['form']==form for r in selected) for form in sorted({r['form'] for r in selected})},'required_material_documents':len(selected),'inventory_sha256':sha}),flush=True)
 def body(r):
  try:
   raw,s=store.fetch(r['document_url']);return {**r,**s,'body_status':'archived','reviewed':False}
  except Exception as exc:return {**r,'body_status':'blocked','error':str(exc),'reviewed':False}
 with ThreadPoolExecutor(max_workers=3) as pool:bodies=list(pool.map(body,selected))
 value={'issuer':ticker,'body_receipts':bodies,'all_required_bodies_archived':all(r['body_status']=='archived' for r in bodies),'inventory_sha256':sha,'training_allowed':False}
 (BASE/(ticker+'_regulatory_bodies.json')).write_text(json.dumps(value,indent=2)+'\n')
 print(json.dumps({'ticker':ticker,'body_count':len(bodies),'archived':sum(r['body_status']=='archived' for r in bodies)}),flush=True)
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(collect,SITES))
