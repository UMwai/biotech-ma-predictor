"""Offline verification of captured SEC containers and direct filing responses.

This verifies current captured source bytes and prepares a bounded review queue.
It never adjudicates outcomes, grants label admission, or asserts as-filed byte
identity. Collection declarations are not substitutes for parsing their sources.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from scripts.collect_issuer_archives import Document, clean
from src.research.regulatory_corpus import EXCLUDED_FORMS
from src.research.regulatory_inventory import verify_inventory

MAX_SOURCE_BYTES = 80_000_000
MAX_ACCESSIONS = 1000
MAX_DOCUMENTS = 10000


class SECCorpusError(ValueError):
    """Captured evidence cannot support the declared source inventory."""


def _require(condition, message):
    if not condition:
        raise SECCorpusError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _time(value, name):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise SECCorpusError(name + ": timezone-aware timestamp required") from error
    _require(result.tzinfo is not None, name + ": timezone required")
    return result.astimezone(timezone.utc)


def _day(value):
    _require(isinstance(value, str), "canonical source date required")
    result = date.fromisoformat(value)
    _require(result.isoformat() == value, "canonical source date required")
    return result


def _local(root, relative):
    _require(isinstance(relative, str) and bool(relative), "source relative path required")
    part = Path(relative)
    path = (root / part).resolve()
    _require(not part.is_absolute() and path.is_relative_to(root.resolve()) and path.is_file(),
             "source path missing or escapes evidence root")
    _require(path.stat().st_size <= MAX_SOURCE_BYTES, "source exceeds bounded verification size")
    return path


def _referenced(root, reference):
    path = _local(root, reference["source_relative_path"])
    raw = path.read_bytes()
    _require(_sha(raw) == reference["source_sha256"], "referenced source hash mismatch")
    return path, json.loads(raw)


def _sec_url(url, cik, accession, *, presentation=False):
    _require(isinstance(url, str), "SEC source URL required")
    parsed = urlsplit(url)
    _require(parsed.scheme == "https" and parsed.netloc in {"www.sec.gov", "sec.gov"}
             and not parsed.query and not parsed.fragment, "exact public SEC HTTPS URL required")
    prefix = f"/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    _require(parsed.path.startswith(prefix), "SEC URL CIK or accession mismatch")
    name = parsed.path[len(prefix):]
    if presentation and re.fullmatch(r"xsl[A-Za-z0-9]+/[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        name = name.split("/")[1]
    _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is not None,
             "unsafe SEC document filename or path")
    return name


def _response(root, receipt, expected_url, cik, accession, publication, now):
    _require(isinstance(receipt, dict), "SEC response receipt must be an object")
    _sec_url(expected_url, cik, accession)
    url = receipt.get("source_uri", receipt.get("source_url"))
    _require(url == receipt.get("effective_url") == expected_url,
             "SEC response URL changed or redirected")
    _require(type(receipt.get("http_status")) is int and receipt["http_status"] == 200,
             "successful SEC response required")
    relative = receipt.get("source_relative_path", receipt.get("raw_relative_path"))
    raw = _local(root, relative).read_bytes()
    _require(_sha(raw) == receipt.get("source_sha256", receipt.get("raw_sha256")),
             "SEC response hash mismatch")
    _require(bool(raw.strip()), "empty SEC response body")
    beginning = raw[:8000].lower()
    _require(not any(marker in beginning for marker in (
        b"request rate threshold exceeded", b"your request originates from an undeclared automated tool",
        b"<title>access denied", b"<title>request rejected")), "SEC denial/error response is not a filing")
    suffix = Path(urlsplit(expected_url).path).suffix.lower()
    if suffix in {".htm", ".html"}:
        _require(re.search(rb"<(?:html|body)(?:\s|>)", raw, re.I) is not None,
                 "SEC HTML response has no document body")
    elif suffix == ".pdf":
        _require(raw.startswith(b"%PDF-") and b"%%EOF" in raw[-1024:], "truncated or invalid SEC PDF response")
    recorded_size = receipt.get("byte_count")
    if recorded_size is not None:
        _require(type(recorded_size) is int and len(raw) == recorded_size,
                 "SEC response byte count mismatch")
    retrieved = _time(receipt.get("retrieved_at"), "SEC retrieval")
    lower = datetime.combine(_day(publication), datetime.min.time(), timezone.utc) - timedelta(hours=14)
    _require(lower <= retrieved <= now, "SEC publication/retrieval chronology invalid")
    if "attempted_at" in receipt:
        _require(_time(receipt["attempted_at"], "SEC request") <= retrieved,
                 "SEC request follows retrieval")
    return raw, {"source_url": expected_url, "source_sha256": _sha(raw),
                 "captured_response_bytes": len(raw), "recorded_byte_count_present": recorded_size is not None,
                 "retrieved_at": retrieved.isoformat()}


def _index(raw, index_url, cik, accession, publication, parent, form):
    root = Document(raw).root
    metadata = {}
    for key, value in re.findall(rb'<div class="infoHead">(.*?)</div>\s*<div class="info">(.*?)</div>', raw, re.S):
        name = clean(Document(key).root)
        _require(name not in metadata, "duplicate SEC index metadata")
        metadata[name] = clean(Document(value).root)
    _require(metadata.get("Filing Date") == publication, "SEC index filing date mismatch")
    _require(str(metadata.get("Documents", "")).isdigit(), "SEC index public document count missing")
    count = int(metadata["Documents"])
    _require(0 < count <= MAX_DOCUMENTS, "SEC index document count outside bounded scope")
    _require(accession in clean(root), "SEC index accession absent")
    companies = root.find(cls="companyName")
    company_ciks = {int(c) for node in companies for c in re.findall(r"CIK[=:]\s*(\d+)",
                    clean(node) + " " + " ".join(a.attrs.get("href", "") for a in node.find("a")))}
    _require(cik in company_ciks, "SEC index company CIK mismatch")
    tables = [table for table in root.find("table") if table.attrs.get("summary") == "Document Format Files"]
    _require(len(tables) == 1, "SEC index document-format inventory missing or duplicate")
    rows, data_rows, submission = [], [], None
    for table in tables + [t for t in root.find("table") if t.attrs.get("summary") == "Data Files"]:
        section = table.attrs["summary"]
        for tr in table.find("tr"):
            cells = tr.find("td")
            if not cells:
                continue
            _require(len(cells) == 5 and len(cells[2].find("a")) == 1, "malformed SEC document index row")
            link = cells[2].find("a")[0]
            url = urljoin(index_url, link.attrs["href"])
            parsed = urlsplit(url)
            if parsed.path in {"/ix", "/ixviewer/doc/action"}:
                query = parse_qs(parsed.query)
                _require(parsed.scheme == "https" and parsed.netloc == urlsplit(index_url).netloc
                         and set(query) == {"doc"} and len(query["doc"]) == 1 and not parsed.fragment,
                         "unsafe SEC inline viewer target")
                url = urljoin(index_url, query["doc"][0])
            path_parts = urlsplit(url).path.strip("/").split("/")
            _require(len(path_parts) >= 6 and path_parts[3].isdigit(), "SEC index document CIK absent")
            document_cik = int(path_parts[3])
            _require(document_cik in company_ciks, "SEC index links an unbound company CIK")
            filename = _sec_url(url, document_cik, accession, presentation=True)
            size = clean(cells[4])
            _require(not size or size.isdigit(), "invalid SEC index byte count")
            if clean(cells[1]) == "Complete submission text file":
                _require(submission is None and filename == accession + ".txt" and size.isdigit(),
                         "missing or ambiguous complete submission identity")
                submission = {"source_url": url, "bytes": int(size), "document_cik": document_cik}
                continue
            sequence, document_type = clean(cells[0]), clean(cells[3])
            _require(sequence.isdigit() and 0 < int(sequence) <= MAX_DOCUMENTS and bool(document_type),
                     "SEC index document sequence/type invalid")
            # The XML stylesheet link is a presentation alias, not another payload.
            canonical = f"https://{urlsplit(url).netloc}/Archives/edgar/data/{document_cik}/{accession.replace('-', '')}/{filename}"
            row = {"filename": filename, "sequence": sequence, "type": document_type,
                   "source_url": canonical, "document_cik": document_cik,
                   "index_reported_bytes": int(size) if size else None}
            destination = rows if section == "Document Format Files" else data_rows
            prior = next((r for r in destination if r["source_url"] == canonical), None)
            if prior is not None:
                _require(prior["sequence"] == sequence and prior["type"] == document_type
                         and "/xsl" in (url + " " + prior.get("presentation_url", "")),
                         "duplicate SEC index document identity")
                if size:
                    prior["index_reported_bytes"] = int(size)
            else:
                row["presentation_url"] = url
                destination.append(row)
    _require(submission is not None and bool(rows), "SEC index lacks submission or filing inventory")
    parent_filename = _sec_url(parent, cik, accession)
    parents = [row for row in rows if row["filename"] == parent_filename and row["type"] == form and row["sequence"] == "1"]
    _require(len(parents) == 1,
             "selected parent absent from SEC index or form differs")
    sequences = {int(row["sequence"]) for row in rows + data_rows}
    _require(len(sequences) == len(rows) + len(data_rows), "duplicate SEC index document sequence")
    _require(set(range(1, max(int(row["sequence"]) for row in rows) + 1)) <= sequences,
             "SEC index omits a document sequence")
    if not data_rows:
        _require(sequences == set(range(1, count + 1)), "SEC index document count is incomplete")
    return {"documents": rows, "data_files": data_rows, "submission": submission,
            "public_document_count": count, "acceptance_datetime_local": metadata.get("Accepted"),
            "company_ciks": sorted(company_ciks), "indexed_parent": parents[0],
            "public_count_minus_visible_index_entries": count - len(sequences)}


def _one(pattern, raw, name):
    matches = re.findall(pattern, raw, re.M)
    _require(len(matches) == 1, "missing or duplicate SEC submission " + name)
    return matches[0].decode("utf-8").strip()


def _submission(raw, cik, accession, publication, form):
    _require(raw.startswith(("<SEC-DOCUMENT>" + accession + ".txt").encode())
             and raw.rstrip().endswith(b"</SEC-DOCUMENT>"), "truncated or wrong SEC submission container")
    boundary = re.search(rb"(?m)^</SEC-HEADER>\s*\n", raw)
    _require(boundary is not None, "SEC submission header terminator missing")
    header = raw[:boundary.start()]
    _require(_one(rb"^ACCESSION NUMBER:\s*([^\r\n]+)", header, "accession") == accession,
             "SEC submission accession mismatch")
    _require(_one(rb"^FILED AS OF DATE:\s*(\d{8})", header, "filing date") == publication.replace("-", ""),
             "SEC submission filing date mismatch")
    _require(_one(rb"^CONFORMED SUBMISSION TYPE:\s*([^\r\n]+)", header, "form") == form,
             "SEC submission form mismatch")
    header_ciks = {int(value) for value in re.findall(rb"CENTRAL INDEX KEY:\s*(\d+)", header)}
    _require(cik in header_ciks, "SEC submission company CIK mismatch")
    count = int(_one(rb"^PUBLIC DOCUMENT COUNT:\s*(\d+)", header, "public count"))
    _require(0 < count <= MAX_DOCUMENTS, "SEC submission document count outside bounded scope")
    accepted = _one(rb"^<ACCEPTANCE-DATETIME>(\d{14})", header, "acceptance timestamp")
    datetime.strptime(accepted, "%Y%m%d%H%M%S")
    opens = list(re.finditer(rb"(?m)^<DOCUMENT>[ \t]*\r?\n", raw))
    closes = list(re.finditer(rb"(?m)^</DOCUMENT>[ \t]*(?:\r?\n|$)", raw))
    _require(len(opens) == len(closes) == count, "truncated submission or public document count mismatch")
    records, previous = [], boundary.end()
    for opening, closing in zip(opens, closes):
        _require(previous <= opening.start() < opening.end() <= closing.start()
                 and not raw[previous:opening.start()].strip(), "SEC submission block overlap or unparsed content")
        block = raw[opening.end():closing.start()]
        text_markers = list(re.finditer(rb"(?m)^<TEXT>", block))
        _require(len(text_markers) == 1, "ambiguous SEC document TEXT boundary")
        text = text_markers[0]
        ending = re.search(rb"(?m)^</TEXT>[ \t]*(?:\r?\n)?\s*\Z", block)
        _require(ending is not None and text.end() < ending.start(), "truncated SEC document TEXT payload")
        fields = block[:text.start()]
        record = {name.lower(): _one(rb"^<" + name.encode() + rb">([^\r\n]+)", fields, name)
                  for name in ("TYPE", "SEQUENCE", "FILENAME")}
        _require(record["sequence"].isdigit() and 0 < int(record["sequence"]) <= MAX_DOCUMENTS
                 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", record["filename"]) is not None,
                 "unsafe SEC embedded filename or sequence")
        start, end = opening.end() + text.end(), opening.end() + ending.start()
        record.update(container_text_start=start, container_text_end=end,
                      embedded_document_sha256=_sha(raw[start:end]), embedded_document_bytes=end - start)
        records.append(record)
        previous = closing.end()
    _require(raw[previous:].strip() == b"</SEC-DOCUMENT>", "unparsed content after SEC submission documents")
    _require(len({r["filename"] for r in records}) == count
             and len({r["sequence"] for r in records}) == count, "duplicate SEC embedded document identity")
    return records, accepted, sorted(header_ciks)


def _inventories(collection, collection_root, evidence_root, now):
    cik = collection["cik"]
    container = collection["schema_version"] == "sec-complete-submission-collection-v1"
    ticker = collection.get("ticker") if container else collection.get("issuer")
    _require(isinstance(ticker, str) and re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", ticker) is not None,
             "canonical uppercase SEC corpus ticker required")
    if container:
        references, root = collection["source_inventories"], evidence_root
        _require(set(collection["excluded_forms"]) == EXCLUDED_FORMS, "material form exclusion policy changed")
    else:
        _, ledger = _referenced(evidence_root, {"source_relative_path": collection["source_ledger_path"],
                                               "source_sha256": collection["source_ledger_sha256"]})
        rows = [r for r in ledger["records"] if r["cik"] == cik and r["ticker"] == collection["issuer"]]
        _require(len(rows) == 1, "SEC source ledger company identity ambiguous")
        references, root = rows[0]["inventory_receipts"], evidence_root / "data/history"
    _require(isinstance(references, list) and bool(references), "SEC source inventories missing")
    records, intervals, summaries = [], [], []
    for reference in references:
        path, _ = _referenced(root, reference)
        result = verify_inventory(path)
        _require(result["cik"] == cik, "SEC source inventory CIK mismatch")
        _require(result.get("ticker") == ticker, "SEC source inventory ticker mismatch")
        start, end = _day(result["start_date"]), _day(result["end_date"])
        _require(result["query_interval_closed"], "SEC source inventory interval not mature")
        for page in result["pages"]:
            _require(_time(page["retrieved_at"], "inventory retrieval") <= now, "inventory retrieval follows verification")
        intervals.append((start, end))
        records.extend(result["records"])
        summaries.append({"source_sha256": _sha(path.read_bytes()), "start_date": start.isoformat(),
                          "end_date": end.isoformat(), "all_form_documents": len(result["records"]),
                          "transport_identity_verified": result["transport_identity_verified"]})
    intervals.sort()
    _require(all(left[1] + timedelta(days=1) == right[0] for left, right in zip(intervals, intervals[1:])),
             "SEC inventory date coverage has a gap or overlap")
    if not container:
        _require((intervals[0][0].isoformat(), intervals[-1][1].isoformat()) ==
                 (collection["scope_start_date"], collection["scope_end_date"]), "SEC corpus date scope differs from inventories")
    selected = [r for r in records if r["form"] not in EXCLUDED_FORMS]
    _require(selected and len({r["accession"] for r in selected}) == len(selected),
             "empty or duplicate selected SEC accession inventory")
    fresh_verified = False
    if collection.get("fresh_inventory_receipt"):
        path, _ = _referenced(collection_root, collection["fresh_inventory_receipt"])
        fresh = verify_inventory(path)
        _require(fresh["cik"] == cik and fresh.get("ticker") == ticker and fresh["start_date"] == intervals[0][0].isoformat()
                 and fresh["end_date"] == intervals[-1][1].isoformat() and fresh["query_interval_closed"],
                 "fresh SEC inventory company/date scope mismatch")
        _require(all(_time(p["retrieved_at"], "fresh inventory retrieval") <= now for p in fresh["pages"]),
                 "fresh SEC inventory retrieval follows verification")
        identity = lambda r: (r["accession"], r["document_name"], r["form"], r["filed_date"], tuple(r["ciks"]))
        _require({identity(r) for r in selected} == {identity(r) for r in fresh["records"] if r["form"] not in EXCLUDED_FORMS},
                 "fresh SEC inventory selected accession set differs")
        fresh_verified = fresh["transport_identity_verified"]
    return {r["accession"]: r for r in selected}, summaries, fresh_verified


def verify_sec_corpus(path: Path, *, evidence_root: Path | None = None, now: datetime | None = None) -> dict:
    """Replay either captured SEC format without network access or label changes.

    ``evidence_root`` anchors collection references to the repository evidence
    tree. Source response paths remain confined to the collection's directory.
    """
    try:
        return _verify(Path(path), Path(evidence_root) if evidence_root is not None else Path(path).parent,
                       _time(now or datetime.now(timezone.utc), "verification time"))
    except SECCorpusError:
        raise
    except (KeyError, TypeError, ValueError, OSError, OverflowError, AttributeError) as error:
        raise SECCorpusError("SEC corpus evidence is invalid: " + str(error)) from error


def _verify(path, evidence_root, now):
    _require(path.stat().st_size <= MAX_SOURCE_BYTES, "SEC collection exceeds bounded size")
    raw = path.read_bytes()
    _require(len(raw) <= MAX_SOURCE_BYTES, "SEC collection exceeds bounded size")
    collection = json.loads(raw)
    _require(isinstance(collection, dict), "SEC collection must be an object")
    schema = collection.get("schema_version")
    _require(schema in {"sec-complete-submission-collection-v1", "sec-original-corpus-discovery-v1"},
             "unsupported SEC corpus schema")
    cik = collection.get("cik")
    _require(type(cik) is int and 0 < cik < 10**10, "positive SEC corpus CIK required")
    container = schema == "sec-complete-submission-collection-v1"
    entries = collection["accessions"]
    _require(isinstance(entries, list) and 0 < len(entries) <= MAX_ACCESSIONS, "bounded nonempty SEC accessions required")
    _require(all(isinstance(entry, dict) for entry in entries), "SEC accession entries must be objects")
    for field in ("started_at", "completed_at", "created_at", "updated_at"):
        if field in collection:
            _require(_time(collection[field], field) <= now, "SEC collection clock follows verification")
    for start, end in (("started_at", "completed_at"), ("created_at", "updated_at")):
        if start in collection and end in collection:
            _require(_time(collection[start], start) <= _time(collection[end], end), "SEC collection clocks are reversed")
    completed = collection.get("completed_at", collection.get("updated_at"))
    response_end = _time(completed, "capture completion") if completed is not None else now
    expected, inventories, fresh_verified = _inventories(collection, path.parent, evidence_root, now)
    actual_ids = [a["accession_number"] if container else a["candidate"]["accession_number"] for a in entries]
    _require(len(set(actual_ids)) == len(actual_ids) and set(actual_ids) == set(expected),
             "SEC captured accession set differs from source inventory")
    verified = []
    for item, accession in zip(entries, actual_ids):
        _require(re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) is not None, "invalid SEC accession")
        row = expected[accession]
        base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
        parent = base_url + row["document_name"]
        form, published = row["form"], row["filed_date"]
        if container:
            _require((item["candidate_parent_uri"], item["form"], item["publication_date"]) == (parent, form, published),
                     "SEC selected parent metadata differs from inventory")
        else:
            candidate = item["candidate"]
            _require(candidate["document_name"] == row["document_name"] and candidate["form"] == form
                     and candidate["filing_date"] == published and parent in candidate["candidate_SEC_document_uris"],
                     "SEC selected parent metadata differs from inventory")
        index_url = base_url + accession + "-index.html"
        index_bytes, index_receipt = _response(path.parent, item["index"] if container else item["index_receipt"],
                                             index_url, cik, accession, published, response_end)
        index = _index(index_bytes, index_url, cik, accession, published, parent, form)
        result = {"accession_number": accession, "publication_date": published, "form": form,
                  "candidate_parent_uri": parent, "parent_url": index["indexed_parent"]["source_url"],
                  "indexed_parent_document_cik": index["indexed_parent"]["document_cik"],
                  "index": index_receipt, "index_public_document_count": index["public_document_count"],
                  "public_count_minus_visible_index_entries": index["public_count_minus_visible_index_entries"],
                  "unresolved_public_document_count": 0 if container else max(0, index["public_count_minus_visible_index_entries"]),
                  "index_company_ciks": index["company_ciks"], "documents": [], "missing_document_format_payloads": []}
        if container:
            body, receipt = _response(path.parent, item["submission"], index["submission"]["source_url"],
                                      index["submission"]["document_cik"], accession, published, response_end)
            _require(len(body) == index["submission"]["bytes"], "SEC submission length differs from source index")
            documents, accepted, header_ciks = _submission(body, cik, accession, published, form)
            _require(index["submission"]["document_cik"] in header_ciks,
                     "SEC submission URL company is absent from its header")
            _require(len(documents) == index["public_document_count"], "SEC index/submission public count mismatch")
            _require(re.sub(r"[-: ]", "", index["acceptance_datetime_local"] or "") == accepted,
                     "SEC index/submission acceptance timestamp mismatch")
            saved = item["embedded_documents"]
            _require(isinstance(saved, list) and len(saved) == len(documents), "SEC embedded document receipt omitted or extra")
            for observed, recorded in zip(documents, saved):
                _require(all(recorded.get(k) == v for k, v in observed.items()),
                         "SEC embedded document identity, byte bounds or hash mismatch")
            by_name = {d["filename"]: d for d in documents}
            for entry in index["documents"]:
                observed = by_name.get(entry["filename"])
                _require(observed is not None and observed["type"] == entry["type"]
                         and observed["sequence"] == entry["sequence"], "SEC indexed filing/exhibit missing or changed in submission")
            indexed = {r["filename"] for r in index["documents"]}
            material = {r["filename"] for r in documents if r["type"] not in {"XML", "ZIP", "EXCEL", "JSON"}
                        and not r["type"].startswith("EX-101.")}
            _require(material <= indexed, "SEC index omitted a material submission document")
            result.update(submission=receipt, documents=documents, submission_header_ciks=header_ciks,
                          acceptance_datetime_local_unresolved=accepted,
                          payload_representation="verbatim_TEXT_byte_ranges_in_captured_submission_not_independent_responses",
                          graphic_payloads=sum(r["type"] == "GRAPHIC" for r in documents))
        else:
            selected = {r["source_url"]: r for r in index["documents"]
                        if r["filename"].lower().endswith((".htm", ".html", ".pdf")) or r["source_url"] == parent}
            saved = item["documents"]
            _require(isinstance(saved, list) and len({r["source_url"] for r in saved}) == len(saved)
                     and {r["source_url"] for r in saved} == set(selected), "SEC captured parent/exhibit inventory omitted or extra")
            for entry in saved:
                source = selected[entry["source_url"]]
                _require(entry["document_type"] == source["type"] and entry["sequence"] == source["sequence"]
                         and entry["document_name"] == source["filename"], "SEC direct document metadata differs from index")
                body, receipt = _response(path.parent, entry["receipt"], source["source_url"], cik, accession, published, response_end)
                reported = source["index_reported_bytes"]
                result["documents"].append({**source, "response": receipt,
                    "sec_delivery_markup_observed": b"sec.gov/akam/" in body,
                    "index_byte_count_delta": len(body) - reported if reported is not None else None})
            result["missing_document_format_payloads"] = [r for r in index["documents"] if r["source_url"] not in selected]
            result["data_file_payloads_not_collected"] = index["data_files"]
        verified.append(result)
    missing = sum(len(a["missing_document_format_payloads"]) for a in verified)
    bodies = sum(len(a["documents"]) for a in verified)
    return {"schema_version": "sec-corpus-source-verification-v1", "verified_at": now.isoformat(),
            "input_sha256": _sha(raw), "input_schema": schema, "cik": cik,
            "ticker": collection.get("ticker", collection.get("issuer")),
            "status": "captured_sources_verified_review_required", "verified_accessions": len(verified),
            "verified_document_payloads": bodies, "missing_document_format_payloads": missing,
            "unresolved_public_document_count": sum(a["unresolved_public_document_count"] for a in verified),
            "all_document_format_payloads_present": missing == 0,
            "source_inventories": inventories, "fresh_inventory_transport_identity_verified": fresh_verified,
            "outcome_review_complete": False, "label_admission_allowed": False, "outcome_label": None,
            "historical_original_vintage_archived": False, "as_accepted_byte_identity_verified": False,
            "subject_and_filer_review_complete": False, "graphic_content_review_complete": False,
            "declared_capture_completed_at": completed,
            "source_clock_policy": "Captured responses cannot follow declared capture completion; reused responses may precede collection creation. Supplemental inventory captures retain separate clocks and may follow initial source collection.",
            "accessions": verified,
            "limitations": ["Current SEC response hashes do not prove byte identity at original acceptance or an unchanged historical inventory.",
                            "Container TEXT hashes identify encoded payload ranges, not separately downloaded files or decoded images.",
                            "Direct responses can include SEC delivery markup; index and response byte counts remain separate.",
                            "Missing non-HTML/graphic payloads, substantive outcome and identity review, and historical timing admission remain separate gates."]}
