"""Bounded one-attempt official-route discovery; never assigns outcome labels."""
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parent
DENIED_OR_FAILED = {
    'https://beamtherapeutics.gcs-web.com/financials-filings/sec-filings',
    'https://investors.arcutis.com/financial-information/sec-filings/',
    'https://investors.arcutis.com/financial-information/sec-filings',
    'https://ir.crinetics.com/financials/sec-filings/default.aspx',
    'https://ir.altimmune.com/news-releases',
}
ROUTES = [
    ('BEAM', 'https://investors.beamtx.com/financials-filings/sec-filings', 'Official native-host route found by primary issuer search; gcs host failure preserved.'),
    ('ARQT', 'https://investors.arcutis.com/node/8916/html', 'View HTML link from previously archived original accession 0001787306-22-000009 issuer filing details.'),
    ('CRNX', 'https://crinetics.com/investors/', 'Corporate investor navigation; denied Q4 filing route will not be retried.'),
    ('ALT', 'https://ir.altimmune.com/investors/financials/sec-filings', 'SEC Filings link in previously archived ALT FY2019 original filing details.'),
    ('APLT', 'https://ir.appliedtherapeutics.com/financial-information/sec-filings', 'Native official issuer domain; primary issuer search shows this filing archive under gcs host.'),
    ('CALA', 'https://ir.calithera.com/financial-information/sec-filings', 'Historical issuer filing route named in January 2021 release; annual-report sibling corroborated by original SEC proxy.'),
]

class BoundedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if newurl.rstrip('/') in {u.rstrip('/') for u in DENIED_OR_FAILED} or urllib.parse.urlsplit(newurl).hostname in {'www.sec.gov', 'sec.gov'}:
            raise RuntimeError('redirect_target_previously_failed_or_sec_body_not_requested: ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def probe(item):
    ticker, url, reason = item
    output = BASE / (ticker + '_filing_route_probe_20260908.json')
    if output.exists():
        return {'ticker': ticker, 'reused_receipt': str(output), 'network_attempts': 0}
    record = {'schema_version': 'issuer-filing-route-probe-v1', 'ticker': ticker, 'source_url': url, 'discovery_reason': reason,
              'attempted_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'network_attempts': 1,
              'automatic_retry_allowed': False, 'outcome_label': None, 'complete_material_corpus_verified': False}
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'biotech-ma-predictor public historical acquisition research'})
        with urllib.request.build_opener(BoundedRedirect()).open(request, timeout=20) as response:
            payload = response.read(20_000_001)
            if len(payload) > 20_000_000:
                raise ValueError('response_exceeds_bounded_20MB_capture')
            digest = hashlib.sha256(payload).hexdigest()
            dest = BASE / (ticker + '_route_sources') / (digest + '.bin')
            dest.parent.mkdir(exist_ok=True)
            if not dest.exists(): dest.write_bytes(payload)
            record.update(status='success', http_status=response.status, resolved_url=response.url,
                          content_type=response.headers.get('Content-Type'), source_relative_path=str(dest.relative_to(BASE)),
                          source_sha256=digest, source_bytes=len(payload), source_bytes_archived=True)
    except Exception as exc:
        record.update(status='unavailable', failure_type=type(exc).__name__, failure=str(exc),
                      http_status=getattr(exc, 'code', None), source_bytes_archived=False)
    record['completed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    output.write_text(json.dumps(record, indent=2) + '\n')
    return {k:v for k,v in record.items() if k not in {'source_relative_path','source_sha256','discovery_reason'}}

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(probe, ROUTES):
            print(json.dumps(result), flush=True)
