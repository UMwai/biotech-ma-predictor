"""Archive the saved finite SEC material inventory without assigning outcomes.

At most one request per second, no request retries, original URLs and bytes kept.
The collection is research input, not a completed negative-label review.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
sys.path.insert(0, str(REPO))
from scripts.collect_issuer_archives import Document, clean

LEDGER = REPO / "data/history/panel_seed/negative_reviews/CDXS_STRO_remaining_controls_route_ledger.json"
TICKERS = ["FREQ", "AVDL", "HARP", "FULC", "CNCE", "KALA", "KALV", "KNSA", "KRYS"]


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    def __init__(self):
        self.next_request = 0.0
        self.opener = urllib.request.build_opener(NoRedirect)
        self.cache = {}
        self.journal = ROOT / "controls_b_sec_requests.jsonl"
        if self.journal.exists():
            for line in self.journal.read_text().splitlines():
                item = json.loads(line)
                self.cache[item["source_url"]] = item
        probes = json.loads((ROOT / "controls_b_probes.json").read_text())
        for item in probes:
            if item.get("effective_url") == item["source_url"] and item["source_url"].startswith("https://www.sec.gov/Archives/edgar/data/"):
                self.cache[item["source_url"]] = {**item, "status": "archived", "reused_from": "controls_b_probes.json"}
        initial_index = json.loads((ROOT / "freq_index_probe.json").read_text())
        self.cache[initial_index["url"]] = {"source_url": initial_index["url"], "effective_url": initial_index["effective_url"], "http_status": initial_index["http_status"], "retrieved_at": initial_index["retrieved_at"], "status": "archived", "raw_sha256": initial_index["sha256"], "raw_relative_path": initial_index["raw_relative_path"], "reused_from": "freq_index_probe.json"}

    def fetch(self, url):
        if url in self.cache:
            item = self.cache[url]
            if item.get("status") == "archived":
                assert hashlib.sha256((ROOT / item["raw_relative_path"]).read_bytes()).hexdigest() == item["raw_sha256"]
            return item
        assert re.fullmatch(r"https://www\.sec\.gov/Archives/edgar/data/\d+/\d{18}/[A-Za-z0-9_.-]+", url), url
        time.sleep(max(0.0, self.next_request - time.monotonic()))
        self.next_request = time.monotonic() + 1.05
        item = {"source_url": url, "retrieved_at": stamp(), "status": "not_archived"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BiotechMAResearch/1.0 public historical source verification"})
            with self.opener.open(req, timeout=12) as response:
                item.update(http_status=response.status, effective_url=response.url, content_type=response.headers.get("Content-Type"))
                body = response.read(20_000_001)
            if len(body) > 20_000_000:
                item["status"] = "size_limit_exceeded"
            elif item["effective_url"] != url:
                item["status"] = "identity_redirect_rejected"
            elif len(body) < 50:
                item["status"] = "truncated_body_rejected"
            elif any(s in body[:5000].lower() for s in (b"request rate threshold exceeded", b"your request originates from an undeclared automated tool")):
                item["status"] = "access_denial_body_rejected"
            else:
                digest = hashlib.sha256(body).hexdigest()
                suffix = ".pdf" if body.startswith(b"%PDF") else Path(urllib.parse.urlsplit(url).path).suffix
                path = ROOT / "raw_controls_b_sec" / (digest + suffix)
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(body)
                item.update(status="archived", raw_sha256=digest, byte_count=len(body), raw_relative_path=str(path.relative_to(ROOT)))
        except urllib.error.HTTPError as error:
            item.update(status="http_error", http_status=error.code, effective_url=error.url)
        except (OSError, ValueError) as error:
            item.update(status="transport_error", error_class=type(error).__name__, error=str(error))
        with self.journal.open("a") as journal:
            journal.write(json.dumps(item, sort_keys=True) + "\n")
        self.cache[url] = item
        return item


def index_documents(raw, index_url, accession):
    root = Document(raw).root
    tables = [table for table in root.find("table") if table.attrs.get("summary") == "Document Format Files"]
    if len(tables) != 1:
        raise ValueError("exact SEC document-format table missing")
    if accession not in clean(root):
        raise ValueError("accession absent from SEC index")
    rows = []
    for row in tables[0].find("tr"):
        cells = row.find("td")
        if not cells:
            continue
        if len(cells) != 5 or len(cells[2].find("a")) != 1:
            raise ValueError("SEC index row shape changed")
        link = cells[2].find("a")[0]
        url = urllib.parse.urljoin(index_url, link.attrs["href"])
        parsed = urllib.parse.urlsplit(url)
        if parsed.path in ("/ix", "/ixviewer/doc/action"):
            targets = urllib.parse.parse_qs(parsed.query).get("doc", [])
            if len(targets) != 1:
                raise ValueError("ambiguous inline-XBRL document target")
            url = urllib.parse.urljoin(index_url, targets[0])
        if not url.startswith(index_url.rsplit("/", 1)[0] + "/"):
            raise ValueError("index document leaves accession directory")
        rows.append({"sequence": clean(cells[0]), "description": clean(cells[1]), "document_name": clean(link), "document_type": clean(cells[3]), "index_reported_bytes": clean(cells[4]), "source_url": url})
    if not rows:
        raise ValueError("empty accession inventory")
    dates = re.findall(r'<div class="infoHead">(.*?)</div>\s*<div class="info">(.*?)</div>', raw.decode(errors="replace"), re.S)
    return rows, {re.sub(r"<[^>]+>", "", key).strip(): re.sub(r"<[^>]+>", "", value).strip() for key, value in dates}


def delivery_evidence(row, receipt):
    if receipt["status"] != "archived":
        return {"as_filed_byte_identity_verified": False}
    body = (ROOT / receipt["raw_relative_path"]).read_bytes()
    reported = row.get("index_reported_bytes", "")
    reported = int(reported) if reported.isdigit() else None
    return {"captured_http_response_byte_count": len(body),
            "index_reported_byte_count": reported,
            "index_byte_count_matches_response": len(body) == reported if reported is not None else None,
            "index_byte_count_delta": len(body) - reported if reported is not None else None,
            "sec_delivery_markup_observed": b"sec.gov/akam/" in body,
            "as_filed_byte_identity_verified": False,
            "historical_original_vintage_archived": False}


def collect(ticker, ledger_record, fetcher):
    destination = ROOT / (ticker + "_sec_corpus_discovery.json")
    report = {"schema_version": "sec-original-corpus-discovery-v1", "issuer": ticker, "cik": ledger_record["cik"], "created_at": stamp(), "scope_start_date": "2020-01-01", "scope_end_date": "2022-03-31", "source_ledger_path": str(LEDGER.relative_to(REPO)), "source_ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(), "all_designated_material_parents_and_html_exhibits_archived": False, "negative_label": None, "substantive_outcome_review_complete": False, "historical_inventory_completeness_proven": False, "legacy_inventory_transport_identity_verified": False, "historical_original_vintage_archived": False, "as_filed_byte_identity_verified": False, "delivery_markup_limitation": "Captured bytes are current SEC HTTP responses. SEC delivery markup can change response length from the filing index. Exact response hashes do not establish byte identity with the filing as accepted.", "accessions": []}
    for candidate in ledger_record["required_material_document_candidates"]:
        accession = candidate["accession_number"]
        parent_url = candidate["candidate_SEC_document_uris"][0]
        index_url = parent_url.rsplit("/", 1)[0] + "/" + accession + "-index.html"
        index_receipt = fetcher.fetch(index_url)
        item = {"candidate": candidate, "index_receipt": index_receipt, "documents": [], "all_designated_bodies_archived": False, "subject_and_filer_identity_review_complete": False}
        if index_receipt["status"] == "archived":
            try:
                rows, publication = index_documents((ROOT / index_receipt["raw_relative_path"]).read_bytes(), index_url, accession)
                item.update(index_document_inventory=rows, index_publication_metadata=publication)
                selected = [row for row in rows if urllib.parse.urlsplit(row["source_url"]).path.lower().endswith((".htm", ".html", ".pdf")) or row["source_url"] == parent_url]
                if parent_url not in {row["source_url"] for row in selected}:
                    raise ValueError("saved selected parent absent from accession document inventory")
                for row in selected:
                    receipt = fetcher.fetch(row["source_url"])
                    item["documents"].append({**row, "receipt": receipt, "delivery_evidence": delivery_evidence(row, receipt)})
                item["all_designated_bodies_archived"] = bool(selected) and all(row["receipt"]["status"] == "archived" for row in item["documents"])
                item["omitted_non_html_inventory"] = [row for row in rows if row not in selected]
                item["non_html_or_embedded_exhibit_review_complete"] = False
            except (ValueError, KeyError, AssertionError) as error:
                item["inventory_error"] = str(error)
        report["accessions"].append(item)
        report["updated_at"] = stamp()
        report["completed_accession_count"] = len(report["accessions"])
        report["expected_accession_count"] = len(ledger_record["required_material_document_candidates"])
        report["all_designated_material_parents_and_html_exhibits_archived"] = len(report["accessions"]) == report["expected_accession_count"] and all(entry["all_designated_bodies_archived"] for entry in report["accessions"])
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(destination)
        print(ticker, report["completed_accession_count"], "/", report["expected_accession_count"], accession, len(item["documents"]), item["all_designated_bodies_archived"], flush=True)
        if index_receipt.get("http_status") in (403, 429) or any(entry["receipt"].get("http_status") in (403, 429) for entry in item["documents"]):
            raise SystemExit("SEC access rejection: collection stopped; cached failures will not be retried")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", choices=TICKERS, default=TICKERS)
    args = parser.parse_args()
    records = {row["ticker"]: row for row in json.loads(LEDGER.read_text())["records"]}
    fetcher = Fetcher()
    for ticker in args.tickers:
        collect(ticker, records[ticker], fetcher)
