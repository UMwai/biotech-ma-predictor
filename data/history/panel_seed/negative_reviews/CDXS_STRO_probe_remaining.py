"""Bounded first probes of source-discovered public issuer filing inventories.
Never retries an existing receipt and does not assign any outcome labels.
"""
import concurrent.futures, datetime, hashlib, json, pathlib, re, urllib.request, urllib.error

BASE = pathlib.Path(__file__).resolve().parent
RAW = BASE / 'CDXS_STRO_route_raw'
RAW.mkdir(exist_ok=True)
ROUTES = {
 'ARCT': ('https://ir.arcturusrx.com/financial-information/sec-filings?items_per_page_toggle=0&page=0', 'CDXS_STRO_route_search_1.json'),
 'ABUS': ('https://investor.arbutusbio.com/index.php/sec-filings?field_nir_sec_date_filed_value=&items_per_page=10&items_per_page_toggle=0&mobile=1&page=25', 'primary issuer filing inventory discovered by web search; archived search/open receipt separately'),
 'FREQ': ('https://frequencytx.gcs-web.com/sec-filings', 'CDXS_STRO_route_search_3.json; original issuer 2023 SEC Form425 specifies this route'),
 'AVDL': ('https://investors.avadel.com/sec-filings?field_nir_sec_date_filed_value=&items_per_page=10&items_per_page_toggle=0&mobile=1&order=field_nir_sec_date_filed&page=3&sort=desc', 'CDXS_STRO_route_search_2.json'),
 'KALA': ('https://investors.kalarx.com/sec-filings', 'CDXS_STRO_route_search_2.json'),
 'KALV': ('https://ir.kalvista.com/sec-filings?items_per_page=10&mobile=1&order=field_nir_sec_date_filed&sort=desc', 'CDXS_STRO_route_search_2.json'),
 'FULC': ('https://ir.fulcrumtx.com/sec-filings/sec-filing/10-k/0001564590-20-008951', 'panel_financials/FULC_2019_review.json; original annual filing-date evidence'),
 'KNSA': ('https://investors.kiniksa.com/sec-filings/sec-filing/10-k/0001558370-20-002081', 'panel_financials/KNSA_2019_review.json; original annual filing-date evidence'),
 'KRYS': ('https://ir.krystalbio.com/sec-filings/sec-filing/10-k/0001564590-20-009550', 'panel_financials/KRYS_2019_review.json; original annual filing-date evidence'),
}

def probe(row):
 ticker,(url,discovery)=row
 path=BASE/f'CDXS_STRO_{ticker}_filing_route_probe_20260908.json'
 if path.exists():
  return ticker, 'existing_receipt_preserved'
 now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
 receipt={'schema_version':'bounded-issuer-filing-route-probe-v1','ticker':ticker.split('_')[0],'route_variant':ticker,'source_uri':url,'discovery_evidence':discovery,'attempted_at':now(),'automatic_retry_allowed':False,'full_text_review_complete':False,'outcome_label':None,'complete_material_corpus_archived':False}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'biotech-ma-predictor public historical acquisition research'}),timeout=15) as response:
   raw=response.read(12_000_000)
   sha=hashlib.sha256(raw).hexdigest(); dest=RAW/f'{sha}.html'
   if not dest.exists():dest.write_bytes(raw)
   text=raw.decode('utf-8',errors='replace')
   receipt.update(status='fetched',http_status=response.status,effective_url=response.geturl(),content_type=response.headers.get('Content-Type'),retrieved_at=now(),source_relative_path=str(dest.relative_to(BASE)),source_sha256=sha,source_bytes=len(raw),equisolve_inventory_marker_found='spr-ir-sec-filings' in text,equisolve_document_marker_found='sec-filing-header--document-box' in text,drupal_marker_found=bool(re.search(r'Drupal|drupalSettings|nir-sec|nir_sec',text)),accession_content_links=re.findall(r'href=[\"\']([^\"\']*/content/[^\"\']+)[\"\']',text)[:20],filing_navigation_links=list(dict.fromkeys(re.findall(r'href=[\"\']([^\"\']*(?:sec-filings|/html|/static-files/)[^\"\']*)[\"\']',text)))[:30])
 except Exception as e:
  receipt.update(status='fetch_failed',http_status=getattr(e,'code',None),error_type=type(e).__name__,error=str(e),effective_url=getattr(e,'url',None),source_bytes_archived=False)
 path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 return ticker,receipt

if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for ticker,r in pool.map(probe,ROUTES.items()):
   print(ticker,json.dumps(r),flush=True)
