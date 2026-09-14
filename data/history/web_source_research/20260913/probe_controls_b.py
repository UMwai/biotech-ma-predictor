"""Bounded public-source probe for the nine assigned comparison candidates.

This is source discovery only. It does not assign acquisition outcomes.
"""
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
SOURCES = [
    ("FREQ", "sec_annual", "https://www.sec.gov/Archives/edgar/data/1703647/000095017022003655/freq-20211231.htm", "2022-03-15"),
    ("AVDL", "issuer_annual_pdf", "https://investors.avadel.com/static-files/a91627ce-ff5f-4f90-be34-97765118d2fd", "2022-03-16"),
    ("HARP", "sec_annual", "https://www.sec.gov/Archives/edgar/data/1708493/000095017022003375/harp-20211231.htm", "2022-03-10"),
    ("FULC", "issuer_prospectus_pdf", "https://ir.fulcrumtx.com/static-files/33398eb8-bf05-48fd-aef1-3b7c5cc06c2d", "2022 prospectus referencing 2021 filings; exact publication pending"),
    ("CNCE", "sec_annual", "https://www.sec.gov/Archives/edgar/data/1367920/000136792022000018/cnce-20211231.htm", "2022-03-03"),
    ("KALA", "sec_annual", "https://www.sec.gov/Archives/edgar/data/1479419/000155837022004624/kala-20211231x10k.htm", "2022-03-29"),
    ("KNSA", "issuer_annual_pdf", "https://investors.kiniksa.com/static-files/d495a801-dd4a-4996-8886-ca29717c7d40", "2022-02-24"),
    ("KRYS", "issuer_accession_detail", "https://ir.krystalbio.com/sec-filings/sec-filing/8-k/0001193125-21-155718", "2021-05-10"),
    ("KRYS", "issuer_parent_and_exhibit_pdf", "https://ir.krystalbio.com/static-files/5d2f0477-cbe7-4a97-933b-af6f0e796306", "2021-05-10"),
]


def probe(source):
    ticker, kind, url, publication = source
    result = {"ticker": ticker, "kind": kind, "source_url": url,
              "publication_discovery": publication,
              "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "original_bytes_archived": False, "source_complete": False}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BiotechMAResearch/1.0 public historical source verification", "Accept": "text/html,application/pdf"})
        with urllib.request.urlopen(req, timeout=12) as response:
            result.update(http_status=response.status, effective_url=response.url,
                          content_type=response.headers.get("Content-Type"))
            body = response.read(12_000_001)
        if len(body) > 12_000_000:
            result["status"] = "size_limit_exceeded"
            return result
        digest = hashlib.sha256(body).hexdigest()
        suffix = ".pdf" if body.startswith(b"%PDF") else ".html"
        raw = ROOT / "raw_controls_b" / (digest + suffix)
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(body)
        result.update(status="downloaded_pending_review", original_bytes_archived=True,
                      raw_relative_path=str(raw.relative_to(ROOT)), raw_sha256=digest,
                      byte_count=len(body), body_format=suffix.lstrip("."))
    except urllib.error.HTTPError as error:
        result.update(status="http_error", http_status=error.code, effective_url=error.url)
    except (OSError, ValueError) as error:
        result.update(status="transport_error", error_class=type(error).__name__, error=str(error))
    return result


if __name__ == "__main__":
    receipt = ROOT / "controls_b_probes.json"
    if receipt.exists():
        raise SystemExit("Receipt already exists; no automatic retries")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(probe, SOURCES))
    receipt.write_text(json.dumps(results, indent=2) + "\n")
    for result in results:
        print(result["ticker"], result["status"], result.get("byte_count", 0), result.get("http_status"))
