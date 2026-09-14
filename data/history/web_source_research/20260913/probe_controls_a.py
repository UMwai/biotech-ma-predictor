"""One ordinary public SEC filing probe per assigned company; no outcome labels."""
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
TICKERS = ['ARQT', 'CRNX', 'BEAM', 'ALT', 'APLT', 'APRE', 'CALA', 'ABUS', 'ARCT']
_last = 0.0

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def inventories(ticker):
    base = REPO / 'data/history/panel_seed'
    if ticker in ('ARQT', 'CRNX'):
        return sorted((base / 'negative_reviews').glob(ticker + '_regulatory_inventory_20*-*_*json'))
    return sorted((base / 'regulatory_inventory' / ticker).glob(ticker + '_20*-*_*json'))

def fetch(url, context, max_bytes=20_000_000):
    global _last
    time.sleep(max(0, 1.05 - (time.monotonic() - _last)))
    _last = time.monotonic()
    result = dict(context, source_uri=url, attempted_at=stamp(), original_bytes_archived=False,
                  source_complete=False, outcome_label=None, network_attempts=1)
    try:
        request = urllib.request.Request(url, headers={
            'User-Agent': 'BiotechMAResearch/1.0 public historical source verification',
            'Accept': 'text/html,application/pdf,application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            result.update(http_status=response.status, effective_url=response.url,
                          content_type=response.headers.get('Content-Type'))
            body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            result['status'] = 'body_size_limit_exceeded'
        else:
            digest = hashlib.sha256(body).hexdigest()
            suffix = '.pdf' if body.startswith(b'%PDF') else ('.txt' if result['content_type'].startswith('text/plain') else '.html')
            path = ROOT / 'raw_controls_a' / (digest + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != body:
                raise ValueError('content address collision')
            path.write_bytes(body)
            result.update(status='downloaded_pending_review', original_bytes_archived=True,
                          source_sha256=digest, source_relative_path=str(path.relative_to(ROOT)),
                          byte_count=len(body), transport_identity_verified=response.url == url)
    except urllib.error.HTTPError as error:
        result.update(status='http_error', http_status=error.code, effective_url=error.url)
    except (OSError, ValueError) as error:
        result.update(status='transport_error', error_class=type(error).__name__, error=str(error))
    result['retrieved_at'] = stamp()
    return result

if __name__ == '__main__':
    destination = ROOT / 'controls_a_sec_probes.json'
    if destination.exists():
        raise SystemExit('Existing receipt retained; no automatic retries')
    results = []
    for ticker in TICKERS:
        candidates = []
        for path in inventories(ticker):
            data = json.loads(path.read_text())
            for row in data['records']:
                if row['form'] == '10-K':
                    candidates.append((row['filed_date'], row, path, data['cik']))
        if not candidates:
            results.append({'ticker': ticker, 'status': 'no_annual_candidate', 'outcome_label': None})
            continue
        _, row, path, cik = max(candidates, key=lambda x:x[0])
        urls = [u for u in row['candidate_document_uris'] if '/data/' + str(int(cik)) + '/' in u]
        if len(urls) != 1:
            raise ValueError('Candidate subject URL ambiguity: ' + ticker)
        result = fetch(urls[0], {'ticker': ticker, 'cik': cik, 'form': row['form'],
                  'accession_number': row['accession'], 'publication_date': row['filed_date'],
                  'inventory_relative_path': str(path.relative_to(REPO)),
                  'inventory_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        results.append(result)
        destination.write_text(json.dumps(results, indent=2) + '\n')
        print(ticker, result['status'], result.get('http_status'), result.get('byte_count'), flush=True)
