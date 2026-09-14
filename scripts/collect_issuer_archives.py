#!/usr/bin/env python3
"""Archive public issuer news inventories and bodies; never assign outcome labels.

Uses the ordinary public pagination links on the two supported corporate sites.
Existing response bytes and retrieval timestamps are reused and hash checked.
No SEC requests, authentication workarounds, automatic HTTP retries, or model calls.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urljoin, urlsplit, urlencode
from urllib.request import urlopen


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def find(self, tag=None, cls=None, ident=None):
        return [n for n in self.walk() if (tag is None or n.tag == tag)
                and (cls is None or cls in n.attrs.get("class", "").split())
                and (ident is None or n.attrs.get("id") == ident)]

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def text(self):
        if self.tag in {"script", "style", "nav", "footer", "head"}:
            return ""
        return " ".join(c.text() if isinstance(c, Node) else c for c in self.children)


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, payload):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(payload.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def clean(node):
    return " ".join(html.unescape(node.text()).split())


class Store:
    def __init__(self, directory):
        self.directory = directory
        self.raw = directory / "raw_sources"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.cache_path = directory / "fetch_cache.json"
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}
        self.failures_path = directory / "fetch_failures.json"
        self.failures = json.loads(self.failures_path.read_text()) if self.failures_path.exists() else {}
        self.lock = threading.Lock()

    def fetch(self, url):
        host = urlsplit(url).hostname or ""
        if host == "sec.gov" or host.endswith(".sec.gov") or urlsplit(url).scheme != "https":
            raise ValueError("only public HTTPS issuer sources are permitted")
        if url in self.cache:
            receipt = self.cache[url]
            payload = (self.directory / receipt["source_relative_path"]).read_bytes()
            if hashlib.sha256(payload).hexdigest() != receipt["source_sha256"]:
                raise ValueError("cached issuer source hash mismatch")
            return payload, receipt
        if url in self.failures:
            raise ValueError("previous public source request failed; no automatic retry: " + self.failures[url]["error"])
        time.sleep(.25)
        try:
            with urlopen(url, timeout=50) as response:
                payload = response.read(10_000_001)
                if len(payload) > 10_000_000:
                    raise ValueError("issuer document exceeds bounded response size")
                receipt = {"url": url, "resolved_url": response.url, "http_status": response.status,
                           "retrieved_at": datetime.now(timezone.utc).isoformat(),
                           "content_type": response.headers.get("Content-Type", ""),
                           "source_sha256": hashlib.sha256(payload).hexdigest(), "source_bytes": len(payload)}
        except Exception as exc:
            failure = {"url": url, "attempted_at": datetime.now(timezone.utc).isoformat(),
                       "error": str(exc), "http_status": getattr(exc, "code", None),
                       "source_bytes_archived": False, "automatic_retry_allowed": False}
            with self.lock:
                self.failures[url] = failure
                self.failures_path.write_text(json.dumps(self.failures, indent=2) + "\n")
            raise
        path = self.raw / (receipt["source_sha256"] + (".pdf" if payload.startswith(b"%PDF-") else ".html"))
        if path.exists() and path.read_bytes() != payload:
            raise ValueError("content addressed issuer source collision")
        path.write_bytes(payload)
        receipt["source_relative_path"] = str(path.relative_to(self.directory))
        with self.lock:
            self.cache[url] = receipt
            self.cache_path.write_text(json.dumps(self.cache, indent=2) + "\n")
        return payload, receipt


def arcutis_page(payload, year, page):
    text = payload.decode()
    config = json.loads(re.search(r"window.FWP_JSON = (.*?);", text, re.S).group(1))["preload_data"]
    pager = config["settings"]["pager"]
    options = Document(config["facets"]["publications_year"].encode()).root.find("option")
    selected = [x.attrs["value"] for x in options if "selected" in x.attrs]
    if selected != [str(year)] or pager["page"] != page:
        raise ValueError("issuer archive ignored requested year or page")
    rows = []
    for card in Document(payload).root.find("a", "pd-card-link"):
        dates, titles = card.find("small", "text-muted"), card.find(cls="card-title")
        if dates and titles:
            day = datetime.strptime(clean(dates[0]), "%B %d, %Y").date()
            if day.year == year:  # Current featured cards are outside the filtered archive.
                rows.append({"date": day.isoformat(), "title": clean(titles[0]), "url": card.attrs["href"]})
    expected = min(pager["per_page"], pager["total_rows"] - (page - 1) * pager["per_page"])
    if len(rows) != expected:
        raise ValueError("issuer archive count does not reconcile")
    return rows, pager


def crinetics_page(payload, page):
    section = Document(payload).root.find(cls="tab-content-press-releases")[0]
    info = clean(section.find(cls="pagination-info")[0])
    current, total = map(int, info.split("/"))
    if current != page:
        raise ValueError("issuer archive ignored requested page")
    rows = []
    for entry in section.find(cls="post-entry"):
        day = clean(entry.find(cls="post-eyebrow")[0]).split("|", 1)[1].strip()
        title = entry.find(cls="post-title")[0].find("a")[0]
        rows.append({"date": datetime.strptime(day, "%B %d, %Y").date().isoformat(),
                     "title": clean(title), "url": title.attrs["href"]})
    if page < total and len(rows) != 10:
        raise ValueError("issuer archive has an incomplete intermediate page")
    next_links = section.find("a", "pagination-next")
    if (page < total) != bool(next_links):
        raise ValueError("issuer pagination endpoint inconsistent")
    return rows, {"page": page, "total_pages": total, "per_page": 10,
                  "next_url": next_links[0].attrs["href"] if next_links else None}


DRUPAL_ARCHIVES = {
    "ARCT": "https://ir.arcturusrx.com/press-releases",
    "KALV": "https://ir.kalvista.com/news-releases",
    "KRYS": "https://ir.krystalbio.com/news-releases",
    "ALXO": "https://ir.alxoncology.com/news",
}

EQUISOLVE_ARCHIVES = {
    "CDXS": "https://ir.codexis.com/news-events/press-releases",
    "STRO": "https://ir.sutrobio.com/press-releases",
}


def drupal_year_form(payload, base, year):
    for form in Document(payload).root.find("form"):
        for select in form.find("select"):
            options = select.find("option")
            if any(o.attrs.get("value") == str(year) for o in options):
                # Drupal's public links carry filter values, not transient form_build_id.
                params = {}
                params[select.attrs["name"]] = str(year)
                for other in form.find("select"):
                    if other.attrs.get("name") == "items_per_page":
                        params["items_per_page"] = max(int(o.attrs["value"]) for o in other.find("option"))
                return urljoin(base, form.attrs["action"]) + "?" + urlencode(params), select.attrs["name"]
    raise ValueError(f"archive has no public year selector for {year}")


def drupal_page(payload, url, year, page, year_name):
    root = Document(payload).root
    selectors = [s for s in root.find("select") if s.attrs.get("name") == year_name]
    selected = [o.attrs.get("value") for s in selectors for o in s.find("option") if "selected" in o.attrs]
    if selected != [str(year)]:
        raise ValueError("issuer archive ignored requested year")
    rows = []
    for node in root.walk():
        if node.tag not in {"article", "li", "tr"} and "news-item" not in node.attrs.get("class", "").split():
            continue
        links = [a for a in node.find("a") if "/news-release-details/" in a.attrs.get("href", "")]
        if not links or len({a.attrs["href"].strip() for a in links}) != 1:
            continue
        date_nodes = (node.find(cls="nir-widget--news--date-time") or node.find(cls="field--name-field-nir-news-date")
                      or node.find(cls="news-item-date"))
        if not date_nodes:
            continue
        date_text = clean(date_nodes[0]).split(" at ")[0]
        day = None
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%y", "%m/%d/%Y"):
            try:
                day = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                pass
        if day is None or day.year != year:
            raise ValueError(f"unrecognized or out-of-year archive date {date_text!r}")
        pdfs = [a for a in node.find("a") if re.search(r"/pdf(?:$|\?)", a.attrs.get("href", ""))]
        rows.append({"date": day.isoformat(), "title": clean(links[0]), "url": urljoin(url, links[0].attrs["href"].strip()),
                     **({"pdf_url": urljoin(url, pdfs[0].attrs["href"])} if pdfs else {})})
    if len({r["url"] for r in rows}) != len(rows) or not rows:
        raise ValueError("issuer archive empty or contains duplicate release rows")
    next_links = [a for p in root.find(cls="pager") for a in p.find("a") if a.attrs.get("rel") == "next"]
    counts = re.search(r"Displaying\s+(\d+)\s*-\s*(\d+)\s+of\s+(\d+)", clean(root))
    total_rows = None
    if counts:
        first, last, total_rows = map(int, counts.groups())
        if last - first + 1 != len(rows) or bool(next_links) != (last < total_rows):
            raise ValueError("issuer archive pagination/count mismatch")
    return rows, {"page": page, "total_rows": total_rows,
                  "next_url": urljoin(url, next_links[0].attrs["href"]) if next_links else None,
                  "completeness_basis": "public year selector; all returned rows; followed next links to terminal page"}


def codexis_page(payload, url, page):
    root = Document(payload).root
    rows = []
    for node in root.find("article", "media"):
        day = clean(node.find(cls="date")[0])
        match = re.match(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", day)
        title = node.find("a")[0]
        rows.append({"date": datetime.strptime(match.group(1), "%b %d, %Y").date().isoformat(),
                     "title": clean(title), "url": urljoin(url, title.attrs["href"])})
    links = [a for nav in root.find(cls="pagination-wrapper") for a in nav.find("a")]
    active = [a for a in links if a.attrs.get("aria-current") == "page"]
    if active and clean(active[0]) != f"Page {page}":
        raise ValueError("Codexis archive ignored requested page")
    next_links = [a for a in links if clean(a).startswith("Next Page")]
    total = max(int(clean(a).split()[1]) for a in links if re.fullmatch(r"Page \d+", clean(a)))
    if not rows or (page < total and len(rows) != 10) or bool(next_links) != (page < total):
        raise ValueError("Codexis public pagination does not reconcile")
    return rows, {"page": page, "total_pages": total, "per_page": 10,
                  "next_url": next_links[0].attrs["href"] if next_links else None}


def collect(issuer, years, start, end, directory, bodies=True):
    store = Store(directory)
    inventory, pages, errors = [], [], []
    if issuer == "ARQT":
        for year in years:
            page, total = 1, 1
            while page <= total:
                url = f"https://www.arcutis.com/news-media/?_publications_year={year}" + (f"&_paged={page}" if page > 1 else "")
                payload, receipt = store.fetch(url)
                rows, pager = arcutis_page(payload, year, page)
                total = pager["total_pages"]
                if total > 100:
                    raise ValueError("archive exceeds bounded page count")
                pages.append({**receipt, "archive_year": year, **pager, "entry_count": len(rows)})
                inventory.extend({**r, "archive_year": year, "archive_page": page} for r in rows)
                page += 1
    elif issuer == "CRNX" or issuer in EQUISOLVE_ARCHIVES:
        url, page = ("https://crinetics.com/news-events/?filter=press-releases" if issuer == "CRNX"
                     else EQUISOLVE_ARCHIVES[issuer]), 1
        while url:
            payload, receipt = store.fetch(url)
            rows, pager = crinetics_page(payload, page) if issuer == "CRNX" else codexis_page(payload, url, page)
            pages.append({**receipt, **pager, "entry_count": len(rows)})
            inventory.extend({**r, "archive_year": int(r["date"][:4]), "archive_page": page} for r in rows)
            url, page = pager["next_url"], page + 1
            if page > 100:
                raise ValueError("archive exceeds bounded page count")
    else:
        base = DRUPAL_ARCHIVES[issuer]
        initial, _ = store.fetch(base)
        for year in years:
            url, year_name = drupal_year_form(initial, base, year)
            page, year_rows, year_pages = 1, [], []
            while url:
                payload, receipt = store.fetch(url)
                rows, pager = drupal_page(payload, url, year, page, year_name)
                year_pages.append({**receipt, **pager, "archive_year": year, "entry_count": len(rows)})
                year_rows.extend({**r, "archive_year": year, "archive_page": page} for r in rows)
                url, page = pager["next_url"], page + 1
                if page > 100:
                    raise ValueError("archive exceeds bounded page count")
            reported = {p["total_rows"] for p in year_pages if p["total_rows"] is not None}
            if reported and reported != {len(year_rows)}:
                raise ValueError("year inventory count does not match publisher count")
            pages.extend({**p, "total_pages": len(year_pages), "total_rows": len(year_rows)} for p in year_pages)
            inventory.extend(year_rows)
    if len({r["url"] for r in inventory}) != len(inventory):
        raise ValueError("duplicate release URLs across archive pages")
    selected = [r for r in inventory if start <= r["date"] <= end]
    result = {"schema_version": "collected-issuer-archive-v1", "issuer": issuer,
              "requested_body_range": {"start_date": start, "end_date": end}, "pages": pages,
              "inventory": inventory, "archive_complete": True, "body_receipts": [], "errors": errors,
              "body_review_complete": False, "outcome_labels_assigned": 0, "training_allowed": False,
              "scope": "Current designated issuer archive, not an exhaustive regulatory/event census."}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "collection.json").write_text(json.dumps(result, indent=2) + "\n")
    if bodies:
        def fetch_body(row):
            try:
                payload, receipt = store.fetch(row["url"])
                return {**row, **receipt, "review_status": "pending"}
            except Exception as exc:
                return {**row, "error": str(exc), "review_status": "blocked"}
        with ThreadPoolExecutor(max_workers=3) as executor:
            for receipt in executor.map(fetch_body, selected):
                result["body_receipts"].append(receipt)
                if "error" in receipt:
                    errors.append(receipt)
        result["all_selected_bodies_archived"] = not errors and len(result["body_receipts"]) == len(selected)
    payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    snapshot = directory / ("collection-" + hashlib.sha256(payload).hexdigest() + ".json")
    snapshot.write_bytes(payload)
    (directory / "collection.json").write_bytes(payload)
    return {"issuer": issuer, "inventory_count": len(inventory), "body_count": len(result["body_receipts"]),
            "errors": len(errors), "snapshot": str(snapshot), "outcome_labels_assigned": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", choices=["ARQT", "CRNX", *EQUISOLVE_ARCHIVES, *DRUPAL_ARCHIVES], required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2019, 2026)))
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2025-07-03")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args.issuer, args.years, args.start_date, args.end_date,
                             args.output, not args.inventory_only), indent=2))
