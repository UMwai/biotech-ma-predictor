"""Invented archived SEC-like bytes test replay mechanics, not original-source admission."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.build_ma_buyer_universe import main
from src.research.ma_buyer_universe import build, replay
from src.research.training import TrainingBlocked


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    protocol = {"schema_version": "ma-evidence-collection-protocol-v1", "registered_at": "2026-10-01T00:00:00+00:00",
                "planned_observation_dates": ["2021-01-01", "2023-01-01", "2024-01-01"],
                "buyer_universe_rule": {"membership_rule": "all_COMMON_STOCKS_legal_corporate_issuers_in_that_funds_schedule"}}
    payload = json.dumps(protocol).encode()
    (root / "protocol.json").write_bytes(payload)
    manifest = {"schema_version": "ma-buyer-source-manifest-v1", "protocol": {"relative_path": "protocol.json", "sha256": digest(payload)}, "captures": []}
    for fiscal in (2020, 2022, 2023):
        heading = "VANECK VECTORS PHARMACEUTICAL ETF" if fiscal == 2020 else "VANECK PHARMACEUTICAL ETF"
        order = "shares_name_value" if fiscal == 2020 else "name_shares_value"
        def stock(name, shares, value):
            parts = [shares, name, value] if fiscal == 2020 else [name, shares, value]
            return "<tr>" + "".join(f"<td>{part}</td>" for part in parts) + "</tr>"
        report = (f"<p>{heading}</p><p>SCHEDULE OF INVESTMENTS</p><p>September 30, {fiscal}</p>"
            "<table><tr><td>Number of Shares</td><td>Value</td></tr><tr><td>COMMON STOCKS: 99.8%</td></tr>"
            "<tr><td>France: 99.8%</td></tr>" + stock("Example Co. (ADR) *", "10", "100") + "</table><table>"
            "<tr><td>Number of Shares</td><td>Value</td></tr><tr><td>France (continued)</td></tr>"
            + stock("Example Co. (USD) †", "5", "100") + stock("Different Co.", "8", "200") +
            "<tr><td>400</td></tr><tr><td>Total Common Stocks (Cost: $350)</td><td>400</td></tr>"
            + stock("EXCLUDED Money Market", "99", "999") + "</table>").encode()
        accession = f"0000930413{str(fiscal)[2:]}001234"
        base = f"https://www.sec.gov/Archives/edgar/data/1137360/{accession}/"
        filename = f"test{fiscal}_ncsr.htm"
        indexfile = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}-index.html"
        index = (f"<p>Filing Date {fiscal}-12-08 Accepted {fiscal}-12-08 12:00:00 Period of Report {fiscal}-09-30</p>"
                 f'<table><tr><td>1</td><td><a href="{base + filename}">{filename}</a></td><td>N-CSR</td><td>{len(report) - 2}</td></tr></table>').encode()
        capture = {"fiscal_year": fiscal, "observation_year": fiscal + 1, "information_cutoff_at": f"{fiscal}-12-31T23:59:59+00:00",
                   "fund_heading": heading, "schedule_table_ordinals": [0, 1], "security_column_order": order}
        for role, raw, url in (("report", report, base + filename), ("index", index, base + indexfile)):
            capture[role] = archive(root, raw, url, f"{fiscal}-{role}")
        manifest["captures"].append(capture)
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return root, path


def archive(root, raw, url, name):
    relative, receipt_relative = name + ".html", name + ".receipt.json"
    retrieval = "2026-10-01T12:00:00+00:00"
    (root / relative).write_bytes(raw)
    receipt = {"source_uri": url, "effective_url": url, "source_sha256": digest(raw), "http_status": 200,
               "source_bytes": len(raw), "retrieved_at": retrieval, "synthetic_test_fixture": True}
    receiptbytes = json.dumps(receipt).encode()
    (root / receipt_relative).write_bytes(receiptbytes)
    return {"source_uri": url, "source_sha256": digest(raw), "source_relative_path": relative,
            "retrieved_at": retrieval, "receipt_relative_path": receipt_relative, "receipt_sha256": digest(receiptbytes)}


def update(root, manifest, role, raw):
    capture = manifest["captures"][0]
    source = capture[role]
    capture[role] = archive(root, raw, source["source_uri"], "mutated-" + role)


def test_replay_complete_integer_totals_identity_and_deterministic_artifacts(tmp_path):
    root, manifest = fixture(tmp_path)
    first = build(manifest, root, tmp_path / "out")
    second = build(manifest, root, tmp_path / "out")
    assert first["manifest"] == second["manifest"] and first["report"] == second["report"]
    assert first["execution"] != second["execution"]
    report = json.loads(Path(first["report"]).read_bytes())
    assert report["human_audit"] is False and report["as_accepted_byte_identity_verified"] is False
    assert report["jan1_eligibility_verified"] is False and report["probability"] is None
    for universe in report["universes"]:
        assert universe["security_count"] == 3 and universe["issuer_count"] == 2
        assert universe["parsed_common_stock_value_usd"] == universe["printed_common_stock_value_usd"] == 400
        assert universe["captured_minus_index_bytes"] == 2
        assert universe["publication"]["source_publication_upper_bound_at"] == f"{universe['fiscal_year']}-12-09T12:00:00+00:00"
        assert universe["publication"]["source_publication_pre_cutoff"]
        company = next(issuer for issuer in universe["issuers"] if issuer["issuer_name"] == "Example Co.")
        assert company["shares"] == 15 and company["value_usd"] == 200
        assert universe["securities"][0]["displayed_name"] == "Example Co. (ADR) *"
        assert not any("EXCLUDED" in security["issuer_name"] for security in universe["securities"])
        assert universe["row_audit"][-1]["row_kind"] == "common_stocks_end"
    execution = json.loads(Path(first["execution"]).read_bytes())
    assert datetime.fromisoformat(execution["executed_at"]) <= datetime.now(timezone.utc)
    assert execution["report_sha256"] == digest(Path(first["report"]).read_bytes())


@pytest.mark.parametrize("mutation,fragment", [
    ("shares", "integer"), ("value", "integer"), ("ambiguous", "security-looking"),
    ("missing_start", "before common-stock start"), ("missing_end", "security-looking"),
    ("total", "total mismatch"), ("subtotal", "subtotal"), ("wrong_fund", "heading mismatch"),
    ("wrong_year", "heading mismatch"), ("wrong_layout", "integer"), ("tables", "consecutive"),
])
def test_malformed_schedule_never_silently_skips_security_or_boundaries(tmp_path, mutation, fragment):
    root, path = fixture(tmp_path)
    manifest = json.loads(path.read_bytes())
    capture = manifest["captures"][0]
    raw = (root / capture["report"]["source_relative_path"]).read_bytes()
    if mutation == "shares": raw = raw.replace(b"<td>10</td>", b"<td>10.5</td>")
    elif mutation == "value": raw = raw.replace(b"<td>100</td>", b"<td>one hundred</td>", 1)
    elif mutation == "ambiguous": raw = raw.replace(b"<td>10</td>", b"<td></td>")
    elif mutation == "missing_start": raw = raw.replace(b"<tr><td>COMMON STOCKS: 99.8%</td></tr>", b"")
    elif mutation == "missing_end": raw = raw.replace(b"<tr><td>Total Common Stocks (Cost: $350)</td><td>400</td></tr>", b"")
    elif mutation == "total": raw = raw.replace(b"(Cost: $350)</td><td>400", b"(Cost: $350)</td><td>401")
    elif mutation == "subtotal": raw = raw.replace(b"<tr><td>400</td></tr>", b"<tr><td>399</td></tr>")
    elif mutation == "wrong_fund": raw = raw.replace(b"VANECK VECTORS PHARMACEUTICAL ETF", b"VANECK OTHER ETF")
    elif mutation == "wrong_year": raw = raw.replace(b"September 30, 2020", b"September 30, 2021")
    elif mutation == "wrong_layout": capture["security_column_order"] = "name_shares_value"
    else: capture["schedule_table_ordinals"] = [1, 0]
    update(root, manifest, "report", raw)
    path.write_text(json.dumps(manifest))
    with pytest.raises(TrainingBlocked, match=fragment): replay(path, root)


@pytest.mark.parametrize("mutation,fragment", [
    ("hash", "hash mismatch"), ("receipt", "receipt.*mismatch"), ("escape", "escapes"),
    ("cutoff", "after target cutoff"), ("period", "fiscal period"), ("type", "N-CSR"),
    ("filename", "exactly once"), ("accession", "accession mismatch"), ("host", "www.sec.gov"),
    ("future_retrieval", "future"), ("future_protocol", "future"), ("years", "capture years"),
])
def test_hash_index_publication_and_clock_contracts(tmp_path, mutation, fragment):
    root, path = fixture(tmp_path)
    manifest = json.loads(path.read_bytes())
    capture = manifest["captures"][0]
    raw = (root / capture["index"]["source_relative_path"]).read_bytes()
    if mutation == "hash": (root / capture["report"]["source_relative_path"]).write_bytes(b"changed")
    elif mutation == "receipt": capture["report"]["retrieved_at"] = "2026-09-30T12:00:00+00:00"
    elif mutation == "escape": capture["report"]["source_relative_path"] = "../outside.html"
    elif mutation == "cutoff": raw = raw.replace(b"2020-12-08", b"2020-12-31")
    elif mutation == "period": raw = raw.replace(b"2020-09-30", b"2020-08-31")
    elif mutation == "type": raw = raw.replace(b">N-CSR<", b">N-CSRS<")
    elif mutation == "filename": raw = raw.replace(b"test2020_ncsr.htm", b"wrong2020_ncsr.htm")
    elif mutation == "accession":
        capture["index"]["source_uri"] = capture["index"]["source_uri"].replace("/000093041320001234/", "/000093041320001235/")
        source = capture["index"]
        capture["index"] = archive(root, raw, source["source_uri"], "other-index")
    elif mutation == "host": capture["report"]["source_uri"] = capture["report"]["source_uri"].replace("www.sec.gov", "sec.gov.evil.example")
    elif mutation == "future_retrieval":
        source = capture["report"]
        source["retrieved_at"] = "2099-01-01T00:00:00+00:00"
        receipt = json.loads((root / source["receipt_relative_path"]).read_bytes())
        receipt["retrieved_at"] = source["retrieved_at"]
        receiptbytes = json.dumps(receipt).encode()
        (root / source["receipt_relative_path"]).write_bytes(receiptbytes)
        source["receipt_sha256"] = digest(receiptbytes)
    elif mutation == "future_protocol":
        protocol = json.loads((root / "protocol.json").read_bytes())
        protocol["registered_at"] = "2099-01-01T00:00:00+00:00"
        protocolbytes = json.dumps(protocol).encode()
        (root / "protocol.json").write_bytes(protocolbytes)
        manifest["protocol"]["sha256"] = digest(protocolbytes)
    else: manifest["captures"][2] = copy.deepcopy(manifest["captures"][1])
    if mutation in ("cutoff", "period", "type", "filename"):
        update(root, manifest, "index", raw)
    path.write_text(json.dumps(manifest))
    with pytest.raises(TrainingBlocked, match=fragment): replay(path, root)


def test_missing_input_cli_is_reviewable_without_traceback(tmp_path, capsys):
    assert main(["--manifest", str(tmp_path / "missing.json"), "--evidence-root", str(tmp_path), "--output-dir", str(tmp_path / "out")]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "blocked"


@pytest.mark.parametrize("mutation", [None, "raw_hash", "comparison_clock", "comparison_before_retrieval", "binding",
    "insertion_bytes", "insertion_hash", "insertion_count", "duplicate_insertion", "missing_member", "duplicate_member", "changed_embedded", "contradictory_assertion"])
def test_archived_version_audit_is_bound_without_promoting_original_vintage(tmp_path, mutation):
    root, path = fixture(tmp_path)
    manifest = json.loads(path.read_bytes())
    complete, comparisons = [], []
    fragments = [b"<script>synthetic-one</script>", b"<script>synthetic-two</script>", b"<script>synthetic-three</script>",
                 b"<noscript>synthetic-unexecuted</noscript>"]
    for capture in manifest["captures"]:
        year = capture["fiscal_year"]
        accession, filename = capture["report"]["source_uri"].split("/")[-2:]
        url = capture["report"]["source_uri"].rsplit("/", 1)[0] + f"/{accession[:10]}-{accession[10:12]}-{accession[12:]}.txt"
        bare = (root / capture["report"]["source_relative_path"]).read_bytes()
        embedded = b"<DOCUMENT>\n<TYPE>N-CSR\n<FILENAME>" + filename.encode() + b"\n<TEXT>\n" + bare + b"\n</TEXT>\n</DOCUMENT>\n"
        direct = b"".join(fragments) + embedded
        capture["report"] = archive(root, direct, capture["report"]["source_uri"], f"{year}-audited-report")
        index = (root / capture["index"]["source_relative_path"]).read_bytes()
        index = index.replace(f"<td>{len(bare)-2}</td>".encode(), f"<td>{len(embedded)}</td>".encode())
        capture["index"] = archive(root, index, capture["index"]["source_uri"], f"{year}-audited-index")
        container = b"<SEC-DOCUMENT>synthetic\n" + embedded + b"</SEC-DOCUMENT>\n"
        if year == 2020:
            if mutation == "missing_member": container = container.replace(filename.encode(), b"different.htm")
            elif mutation == "duplicate_member": container += embedded
            elif mutation == "changed_embedded": container = container.replace(b"<td>100</td>", b"<td>101</td>", 1)
        source = archive(root, container, url, f"{year}-submission")
        complete.append({"fiscal_year": year, "source": source})
        comparisons.append({"fiscal_year": year, "direct_report_sha256": capture["report"]["source_sha256"],
            "complete_submission_sha256": source["source_sha256"], "direct_delivery_extra_bytes": sum(map(len, fragments)),
            "embedded_report_bytes": len(embedded), "embedded_report_sha256": digest(embedded),
            "captured_insertions": [{"bytes_utf8": fragment.decode(), "byte_count": len(fragment), "sha256": digest(fragment)} for fragment in fragments],
            "as_accepted_byte_identity_verified": False, "exact_equality_after_only_recorded_insertions_removed": True})
    comparison = {"schema_version": "ma-buyer-source-delivery-comparison-v1", "human_audit": False,
                  "compared_at": "2099-01-01T00:00:00+00:00" if mutation == "comparison_clock" else "2026-10-01T11:59:00+00:00" if mutation == "comparison_before_retrieval" else "2026-10-01T13:00:00+00:00",
                  "comparisons": comparisons}
    if mutation == "binding": comparisons[0]["complete_submission_sha256"] = "0" * 64
    elif mutation == "insertion_bytes":
        insertion = comparisons[0]["captured_insertions"][0]
        insertion["bytes_utf8"] = "<script>contradictory</script>"
        insertion["byte_count"] = len(insertion["bytes_utf8"].encode())
        insertion["sha256"] = digest(insertion["bytes_utf8"].encode())
    elif mutation == "insertion_hash": comparisons[0]["captured_insertions"][0]["sha256"] = "0" * 64
    elif mutation == "insertion_count": comparisons[0]["captured_insertions"].pop()
    elif mutation == "duplicate_insertion": comparisons[0]["captured_insertions"][1] = dict(comparisons[0]["captured_insertions"][0])
    elif mutation == "contradictory_assertion": comparisons[0]["exact_equality_after_only_recorded_insertions_removed"] = False
    raw = json.dumps(comparison).encode()
    (root / "comparison.json").write_bytes(raw)
    manifest["version_audit"] = {"comparison": {"relative_path": "comparison.json", "sha256": digest(raw)}, "complete_submissions": complete}
    path.write_text(json.dumps(manifest))
    if mutation == "raw_hash": (root / complete[0]["source"]["source_relative_path"]).write_bytes(b"changed")
    if mutation:
        with pytest.raises(TrainingBlocked): replay(path, root)
    else:
        _, report = replay(path, root)
        assert report["as_accepted_byte_identity_verified"] is False
        assert report["human_audit"] is False
        assert report["version_audit_material"] == manifest["version_audit"]
        assert all(row["delivery_discrepancy_status"] == "recorded_delivery_insertions_replayed_exactly" for row in report["universes"])
        assert all(row["delivery_comparison_replay"]["exact_equality_recomputed"] and row["delivery_comparison_replay"]["verified_insertion_count"] == 4 for row in report["universes"])


@pytest.mark.parametrize("displayed", ["Example Co. * (ADR)", "Example Co.*(ADR)", "Example Co.(ADR)*", "Example Co. (USD) †"])
def test_only_terminal_annotations_strip_iteratively_without_name_mapping(tmp_path, displayed):
    root, path = fixture(tmp_path)
    manifest = json.loads(path.read_bytes())
    capture = manifest["captures"][0]
    report = (root / capture["report"]["source_relative_path"]).read_bytes()
    report = report.replace(b"Example Co. (ADR) *", displayed.encode())
    update(root, manifest, "report", report)
    path.write_text(json.dumps(manifest))
    _, result = replay(path, root)
    universe = result["universes"][0]
    assert universe["securities"][0]["displayed_name"] == displayed
    assert universe["securities"][0]["issuer_name"] == "Example Co."
    assert universe["issuer_count"] == 2
    assert next(row for row in universe["issuers"] if row["issuer_name"] == "Example Co.")["shares"] == 15
