"""Source verification attacks using invented SEC packages, never label evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_sec_corpus import main
from src.research.regulatory_corpus import EXCLUDED_FORMS
from src.research.regulatory_inventory import parse_page, query_url
from src.research.sec_corpus import SECCorpusError, verify_sec_corpus

NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)
RETRIEVED = "2026-09-13T12:00:00Z"
ACCESSION = "0000000123-20-000001"
CIK = 123
DAY = "2020-01-15"
BASE = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION.replace('-', '')}/"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return sha(raw)


def source(root, name, raw, url, *, direct=False):
    (root / name).write_bytes(raw)
    return {("source_url" if direct else "source_uri"): url, "effective_url": url,
            ("raw_relative_path" if direct else "source_relative_path"): name,
            ("raw_sha256" if direct else "source_sha256"): sha(raw),
            "byte_count": len(raw), "http_status": 200, "retrieved_at": RETRIEVED}


def inventory(root):
    hit = {"_id": ACCESSION + ":filing.htm", "_source": {
        "adsh": ACCESSION, "ciks": [f"{CIK:010d}"], "file_date": DAY, "form": "8-K"}}
    payload = json.dumps({"timed_out": False, "_shards": {"failed": 0, "successful": 1, "total": 1},
                          "hits": {"total": {"relation": "eq", "value": 1}, "hits": [hit]}}).encode()
    directory = root / "data/history"
    directory.mkdir(parents=True)
    (directory / "query.json").write_bytes(payload)
    url = query_url(CIK, "2020-01-01", "2020-12-31")
    _, records = parse_page(payload, CIK, "2020-01-01", "2020-12-31")
    value = {"schema_version": "sec-efts-inventory-v1", "cik": CIK, "ticker": "SYNTH",
             "start_date": "2020-01-01", "end_date": "2020-12-31", "total": 1,
             "inventory_complete": True, "outcome_label": None, "records": records,
             "pages": [{"offset": 0, "source_uri": url, "effective_source_uri": url,
                        "source_relative_path": "query.json", "source_sha256": sha(payload),
                        "source_bytes": len(payload), "retrieved_at": RETRIEVED, "total": 1, "returned": 1}]}
    digest = save_json(directory / "inventory.json", value)
    return {"source_relative_path": "data/history/inventory.json", "source_sha256": digest}


@pytest.fixture(params=["container", "direct"])
def package(tmp_path, request):
    mode = request.param
    root = tmp_path / "capture"
    root.mkdir()
    inv = inventory(tmp_path)
    specifications = [("8-K", "filing.htm", b"<html><body>Synthetic company current filing.</body></html>"),
                      ("EX-99.1", "ex99.htm", b"<html><body>Synthetic earnings exhibit.</body></html>"),
                      ("GRAPHIC", "chart.jpg", b"begin 644 chart.jpg\nsynthetic encoded graphic\nend")]
    container = (f"<SEC-DOCUMENT>{ACCESSION}.txt : 20200115\n<SEC-HEADER>{ACCESSION}.hdr.sgml\n"
                 f"<ACCEPTANCE-DATETIME>20200115150000\nACCESSION NUMBER:\t{ACCESSION}\n"
                 "CONFORMED SUBMISSION TYPE:\t8-K\nPUBLIC DOCUMENT COUNT:\t3\nFILED AS OF DATE:\t20200115\n"
                 f"FILER:\n CENTRAL INDEX KEY:\t{CIK:010d}\n</SEC-HEADER>\n").encode()
    embedded = []
    rows = []
    direct_documents = []
    for sequence, (kind, name, payload) in enumerate(specifications, 1):
        container += f"<DOCUMENT>\n<TYPE>{kind}\n<SEQUENCE>{sequence}\n<FILENAME>{name}\n<TEXT>".encode()
        start = len(container)
        container += b"\n" + payload + b"\n"
        end = len(container)
        embedded.append({"type": kind, "sequence": str(sequence), "filename": name,
                         "container_text_start": start, "container_text_end": end,
                         "embedded_document_bytes": end - start, "embedded_document_sha256": sha(container[start:end])})
        container += b"</TEXT>\n</DOCUMENT>\n"
        rows.append(f'<tr><td>{sequence}</td><td>{kind}</td><td><a href="{BASE + name}">{name}</a></td><td>{kind}</td><td>{len(payload)}</td></tr>')
        if mode == "direct" and kind != "GRAPHIC":
            response = payload + b'<!-- https://www.sec.gov/akam/test-delivery -->'
            direct_documents.append({"source_url": BASE + name, "sequence": str(sequence), "document_name": name,
                                     "document_type": kind, "receipt": source(root, name, response, BASE + name, direct=True)})
    container += b"</SEC-DOCUMENT>\n"
    rows.append(f'<tr><td></td><td>Complete submission text file</td><td><a href="{BASE + ACCESSION}.txt">{ACCESSION}.txt</a></td><td></td><td>{len(container)}</td></tr>')
    index = (f'<html><body><div>{ACCESSION}</div><div class="infoHead">Filing Date</div><div class="info">{DAY}</div>'
             '<div class="infoHead">Accepted</div><div class="info">2020-01-15 15:00:00</div>'
             '<div class="infoHead">Documents</div><div class="info">3</div>'
             '<table summary="Document Format Files">' + ''.join(rows) + '</table>'
             f'<span class="companyName">Synthetic Company (Filer) CIK: {CIK:010d}</span></body></html>').encode()
    index_receipt = source(root, "index.html", index, BASE + ACCESSION + "-index.html", direct=mode == "direct")
    if mode == "container":
        accession = {"accession_number": ACCESSION, "publication_date": DAY, "form": "8-K",
                     "candidate_parent_uri": BASE + "filing.htm", "index": index_receipt,
                     "submission": source(root, "submission.txt", container, BASE + ACCESSION + ".txt"),
                     "embedded_documents": embedded}
        collection = {"schema_version": "sec-complete-submission-collection-v1", "ticker": "SYNTH", "cik": CIK,
                      "source_inventories": [inv], "excluded_forms": sorted(EXCLUDED_FORMS), "accessions": [accession]}
    else:
        ledger = {"records": [{"ticker": "SYNTH", "cik": CIK,
                               "inventory_receipts": [{**inv, "source_relative_path": "inventory.json"}]}]}
        digest = save_json(tmp_path / "ledger.json", ledger)
        accession = {"candidate": {"accession_number": ACCESSION, "filing_date": DAY, "form": "8-K",
                                   "document_name": "filing.htm", "candidate_SEC_document_uris": [BASE + "filing.htm"]},
                     "index_receipt": index_receipt, "documents": direct_documents}
        collection = {"schema_version": "sec-original-corpus-discovery-v1", "issuer": "SYNTH", "cik": CIK,
                      "source_ledger_path": "ledger.json", "source_ledger_sha256": digest,
                      "scope_start_date": "2020-01-01", "scope_end_date": "2020-12-31", "accessions": [accession]}
    path = root / "collection.json"
    save_json(path, collection)
    return {"path": path, "root": tmp_path, "mode": mode, "collection": collection,
            "index_row_html": rows, "index_receipt": index_receipt}


def verify(package):
    save_json(package["path"], package["collection"])
    return verify_sec_corpus(package["path"], evidence_root=package["root"], now=NOW)


def replace_response(package, receipt, transform):
    root = package["path"].parent
    key = "source_relative_path" if "source_relative_path" in receipt else "raw_relative_path"
    hash_key = "source_sha256" if "source_sha256" in receipt else "raw_sha256"
    path = root / receipt[key]
    raw = transform(path.read_bytes())
    path.write_bytes(raw)
    receipt[hash_key], receipt["byte_count"] = sha(raw), len(raw)


def test_parses_sources_without_promoting_saved_status_or_counts(package):
    package["collection"].update(collection_complete=True, selected_accession_count=999,
                                 embedded_document_count=999, outcome_label=0, label_admission_allowed=True)
    result = verify(package)
    assert result["verified_accessions"] == 1
    assert result["verified_document_payloads"] == (3 if package["mode"] == "container" else 2)
    assert result["missing_document_format_payloads"] == (0 if package["mode"] == "container" else 1)
    assert result["outcome_label"] is None
    assert result["outcome_review_complete"] is result["label_admission_allowed"] is False
    assert result["as_accepted_byte_identity_verified"] is False
    if package["mode"] == "direct":
        assert all(row["index_byte_count_delta"] > 0 for row in result["accessions"][0]["documents"])


def test_response_tamper_is_rejected(package):
    path = package["path"].parent / "index.html"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(SECCorpusError, match="hash mismatch"):
        verify(package)


@pytest.mark.parametrize("field,value", [("effective_url", "https://example.invalid/filing"),
                                           ("retrieved_at", "2099-01-01T00:00:00Z")])
def test_redirect_and_future_clock_are_rejected(package, field, value):
    package["index_receipt"][field] = value
    with pytest.raises(SECCorpusError, match="redirected|chronology"):
        verify(package)


def test_wrong_cik_even_with_rehashed_index_is_rejected(package):
    replace_response(package, package["index_receipt"], lambda b: b.replace(b"CIK: 0000000123", b"CIK: 0000000456"))
    with pytest.raises(SECCorpusError, match="CIK mismatch"):
        verify(package)


def test_wrong_accession_url_is_rejected(package):
    receipt = package["index_receipt"]
    key = "source_uri" if "source_uri" in receipt else "source_url"
    receipt[key] = receipt["effective_url"] = receipt[key].replace(ACCESSION, "0000000123-20-000002")
    with pytest.raises(SECCorpusError, match="URL changed"):
        verify(package)


@pytest.mark.parametrize("row", [0, 1])
def test_rehashed_index_cannot_omit_parent_or_exhibit(package, row):
    omitted = package["index_row_html"][row].encode()
    replace_response(package, package["index_receipt"], lambda b: b.replace(omitted, b""))
    with pytest.raises(SECCorpusError, match="parent absent|omits a document"):
        verify(package)


@pytest.mark.parametrize("symlink", [False, True])
def test_raw_source_path_escape_is_rejected(package, symlink):
    root = package["path"].parent
    outside = package["root"] / "outside.html"
    outside.write_bytes((root / "index.html").read_bytes())
    if symlink:
        (root / "escape.html").symlink_to(outside)
    key = "source_relative_path" if package["mode"] == "container" else "raw_relative_path"
    package["index_receipt"][key] = "escape.html" if symlink else "../outside.html"
    with pytest.raises(SECCorpusError, match="escapes evidence root"):
        verify(package)


def test_captured_accession_cannot_be_dropped(package):
    package["collection"]["accessions"] = []
    with pytest.raises(SECCorpusError, match="nonempty SEC accessions"):
        verify(package)


def test_missing_raw_source_cli_exits_two(package, capsys):
    (package["path"].parent / "index.html").unlink()
    assert main([str(package["path"]), "--evidence-root", str(package["root"])]) == 2
    assert json.loads(capsys.readouterr().err)["label_admission_allowed"] is False


def test_cli_can_write_separate_report(package, tmp_path, capsys):
    destination = tmp_path / "reports"
    assert main([str(package["path"]), "--evidence-root", str(package["root"]), "--output-dir", str(destination)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert Path(result["verification_report"]).is_file()
    assert "accessions" not in result
    assert result["outcome_review_complete"] is False


@pytest.mark.parametrize("attack", ["truncate", "count", "cik", "bounds", "missing_exhibit"])
def test_container_boundary_and_identity_attacks(package, attack):
    if package["mode"] != "container":
        pytest.skip("container-specific attack")
    item = package["collection"]["accessions"][0]
    if attack in {"truncate", "count", "cik"}:
        transforms = {"truncate": lambda b: b[:-25],
                      "count": lambda b: b.replace(b"PUBLIC DOCUMENT COUNT:\t3", b"PUBLIC DOCUMENT COUNT:\t4"),
                      "cik": lambda b: b.replace(b"CENTRAL INDEX KEY:\t0000000123", b"CENTRAL INDEX KEY:\t0000000456")}
        old_size = item["submission"]["byte_count"]
        replace_response(package, item["submission"], transforms[attack])
        new_size = item["submission"]["byte_count"]
        replace_response(package, package["index_receipt"], lambda b: b.replace(f"<td>{old_size}</td>".encode(), f"<td>{new_size}</td>".encode()))
    elif attack == "bounds":
        item["embedded_documents"][0]["container_text_start"] += 1
    else:
        item["embedded_documents"].pop(1)
    with pytest.raises(SECCorpusError, match="truncated|count mismatch|CIK mismatch|byte bounds|receipt omitted"):
        verify(package)


def test_direct_exhibit_cannot_be_dropped_despite_complete_flag(package):
    if package["mode"] != "direct":
        pytest.skip("direct-response-specific attack")
    item = package["collection"]["accessions"][0]
    item["documents"].pop()
    item["all_designated_bodies_archived"] = True
    with pytest.raises(SECCorpusError, match="inventory omitted"):
        verify(package)


@pytest.mark.parametrize("body", [b"", b" \n\t", b"<html><title>Access Denied</title></html>", b"plain error message"])
def test_rehashed_empty_or_error_html_is_rejected(package, body):
    if package["mode"] == "direct":
        receipt = package["collection"]["accessions"][0]["documents"][0]["receipt"]
    else:
        receipt = package["index_receipt"]
    replace_response(package, receipt, lambda _: body)
    with pytest.raises(SECCorpusError, match="empty SEC|denial/error|no document body"):
        verify(package)


@pytest.mark.parametrize("value", [[], None, "collection", 1])
def test_malformed_top_level_cli_exits_two(tmp_path, capsys, value):
    path = tmp_path / "invalid.json"
    save_json(path, value)
    assert main([str(path), "--evidence-root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "Traceback" not in error
    assert json.loads(error)["label_admission_allowed"] is False


def test_malformed_nested_receipt_cli_exits_two(package, capsys):
    key = "index" if package["mode"] == "container" else "index_receipt"
    package["collection"]["accessions"][0][key] = []
    save_json(package["path"], package["collection"])
    assert main([str(package["path"]), "--evidence-root", str(package["root"])]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_declared_collection_clock_order_and_capture_bound(package):
    start, end = ("started_at", "completed_at") if package["mode"] == "container" else ("created_at", "updated_at")
    package["collection"].update({start: "2026-09-13T12:00:00Z", end: "2026-09-13T11:00:00Z"})
    with pytest.raises(SECCorpusError, match="clocks are reversed"):
        verify(package)
    package["collection"][start] = "2026-09-13T10:00:00Z"
    with pytest.raises(SECCorpusError, match="chronology invalid"):
        verify(package)
    # Reused body receipts may predate the collection; supplemental inventories
    # have their own capture clock rather than the original collection window.
    package["collection"].update({start: "2026-09-13T12:01:00Z", end: "2026-09-13T12:02:00Z"})
    assert verify(package)["verified_accessions"] == 1


def test_declared_ticker_cannot_change_company_identity(package):
    key = "ticker" if package["mode"] == "container" else "issuer"
    package["collection"][key] = "OTHER"
    with pytest.raises(SECCorpusError, match="ticker mismatch|company identity"):
        verify(package)


def test_duplicate_index_sequence_is_rejected(package):
    duplicate = (f'<tr><td>2</td><td>Additional exhibit</td><td><a href="{BASE}extra.htm">extra.htm</a></td>'
                 '<td>EX-99.2</td><td>42</td></tr>').encode()
    replace_response(package, package["index_receipt"], lambda b: b.replace(b"</table>", duplicate + b"</table>", 1))
    with pytest.raises(SECCorpusError, match="duplicate SEC index document sequence"):
        verify(package)


def test_direct_unlisted_public_documents_remain_unresolved(package):
    if package["mode"] != "direct":
        pytest.skip("direct-response-specific disclosure gap")
    data_table = (f'<table summary="Data Files"><tr><td>4</td><td>Data</td><td><a href="{BASE}data.xml">data.xml</a></td>'
                  '<td>EX-101.INS</td><td>42</td></tr></table>').encode()
    replace_response(package, package["index_receipt"], lambda b: b.replace(
        b'Documents</div><div class="info">3', b'Documents</div><div class="info">6').replace(b"</body>", data_table + b"</body>"))
    result = verify(package)
    assert result["unresolved_public_document_count"] == 2
    assert result["missing_document_format_payloads"] == 1
    assert len(result["accessions"][0]["data_file_payloads_not_collected"]) == 1
    assert result["label_admission_allowed"] is False


def test_bound_holder_cik_parent_reports_actual_index_location(package):
    if package["mode"] != "container":
        pytest.skip("container ownership filing route")
    holder_base = BASE.replace("/123/", "/456/")
    item = package["collection"]["accessions"][0]
    addition = b"REPORTING OWNER:\n CENTRAL INDEX KEY:\t0000000456\n"
    previous_size = item["submission"]["byte_count"]
    replace_response(package, item["submission"], lambda b: b.replace(b"</SEC-HEADER>", addition + b"</SEC-HEADER>"))
    for embedded in item["embedded_documents"]:
        embedded["container_text_start"] += len(addition)
        embedded["container_text_end"] += len(addition)
    submission_url = holder_base + ACCESSION + ".txt"
    item["submission"].update(source_uri=submission_url, effective_url=submission_url)
    replace_response(package, package["index_receipt"], lambda b: b.replace(BASE.encode(), holder_base.encode()).replace(
        f"<td>{previous_size}</td>".encode(), f'<td>{item["submission"]["byte_count"]}</td>'.encode()).replace(
        b"</body>", b'<span class="companyName">Holder CIK: 0000000456</span></body>'))
    result = verify(package)["accessions"][0]
    assert result["parent_url"] == holder_base + "filing.htm"
    assert result["candidate_parent_uri"] == BASE + "filing.htm"
    assert result["indexed_parent_document_cik"] == 456
    # Merely rewriting link CIKs does not establish a holder relationship.
    replace_response(package, package["index_receipt"], lambda b: b.replace(
        b'<span class="companyName">Holder CIK: 0000000456</span>', b""))
    with pytest.raises(SECCorpusError, match="unbound company CIK"):
        verify(package)
