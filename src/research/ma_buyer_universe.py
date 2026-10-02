"""Local replay of frozen PPH common-stock schedules, without ratings or admission."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from scripts.collect_issuer_archives import Document, clean
from src.research.training import TrainingBlocked, _require, _time, write_immutable_json

SCHEMA = "ma-buyer-source-manifest-v1"
CODE_PATHS = ("src/research/ma_buyer_universe.py", "scripts/build_ma_buyer_universe.py",
              "scripts/collect_issuer_archives.py", "src/research/training.py")
INTEGER = re.compile(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)")
SEC_PATH = re.compile(r"/Archives/edgar/data/1137360/(\d{18})/([^/]+)")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _local(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative, "nonempty relative file path required")
    part = Path(relative)
    _require(not part.is_absolute() and ".." not in part.parts, "local path escapes evidence root")
    resolved_root = root.resolve(strict=True)
    path = (resolved_root / part).resolve(strict=True)
    _require(path.is_relative_to(resolved_root) and path.is_file(), "local path escapes evidence root or is not a file")
    return path


def _bytes(root: Path, relative: str, digest: str) -> bytes:
    raw = _local(root, relative).read_bytes()
    _require(_hash(raw) == digest, f"source hash mismatch: {relative}")
    return raw


def _sec(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    _require(parsed.scheme == "https" and parsed.netloc == "www.sec.gov" and not parsed.query and not parsed.fragment,
             "original SEC https www.sec.gov URL required")
    match = SEC_PATH.fullmatch(parsed.path)
    _require(match is not None, "original SEC URL must use CIK1137360 and an accession-specific filename")
    return match.groups()


def _source(root: Path, source: dict, now: datetime) -> tuple[bytes, dict]:
    _require(isinstance(source, dict) and set(source) == {"source_uri", "source_sha256", "source_relative_path",
        "retrieved_at", "receipt_relative_path", "receipt_sha256"}, "exact typed source fields required")
    _sec(source["source_uri"])
    raw = _bytes(root, source["source_relative_path"], source["source_sha256"])
    receipt = json.loads(_bytes(root, source["receipt_relative_path"], source["receipt_sha256"]))
    _require(isinstance(receipt, dict) and receipt.get("http_status") == 200, "successful original source receipt required")
    for field in ("source_uri", "source_sha256", "retrieved_at"):
        _require(receipt.get(field) == source[field], f"source receipt {field} mismatch")
    _require(receipt.get("effective_url", receipt.get("resolved_uri")) == source["source_uri"], "source redirected from original SEC URL")
    _require(type(receipt.get("source_bytes")) is int and receipt["source_bytes"] == len(raw), "source receipt byte size mismatch")
    retrieved = _time(source["retrieved_at"], "actual retrieved_at")
    _require(retrieved <= now, "source retrieval is in the future")
    if "attempted_at" in receipt:
        _require(_time(receipt["attempted_at"], "source attempt") <= retrieved, "source attempt follows actual retrieval")
    return raw, receipt


def _integer(text: str) -> int:
    _require(INTEGER.fullmatch(text) is not None, f"nonempty integer required: {text}")
    return int(text.replace(",", ""))


def _cells(row) -> list[str]:
    return [clean(node) for node in row.children if getattr(node, "tag", None) in ("td", "th")]


def _compact(row) -> list[str]:
    return [text for text in _cells(row) if text and text != "$"]


def _index(index: bytes, report_url: str, index_url: str, fiscal_year: int, cutoff: datetime) -> dict:
    report_accession, filename = _sec(report_url)
    index_accession, index_filename = _sec(index_url)
    _require(report_accession == index_accession, "report/index accession mismatch")
    _require(index_filename == f"{index_accession[:10]}-{index_accession[10:12]}-{index_accession[12:]}-index.html",
             "original accession index filename required")
    doc = Document(index)
    text = clean(doc.root)
    def unique(pattern: str, name: str) -> str:
        matches = re.findall(pattern, text)
        _require(len(matches) == 1, f"one unambiguous official index {name} required")
        return matches[0]
    filed = unique(r"Filing Date (\d{4}-\d{2}-\d{2})\b", "Filing Date")
    accepted = unique(r"Accepted (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\b", "Accepted")
    period = unique(r"Period of Report (\d{4}-\d{2}-\d{2})\b", "Period of Report")
    _require(period == f"{fiscal_year}-09-30", "official index fiscal period mismatch")
    _require(accepted[:10] == filed, "official index accepted/filing dates inconsistent")
    datetime.strptime(accepted, "%Y-%m-%d %H:%M:%S")  # Preserve timezone-unspecified official display; do not guess.
    upper = datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(hours=36)
    _require(upper <= cutoff, "official publication upper bound is after target cutoff")
    matching = []
    for table_ordinal, table in enumerate(doc.root.find("table")):
        for row_ordinal, row in enumerate(table.find("tr")):
            links = [a for a in row.find("a") if urljoin(index_url, a.attrs.get("href", "")) == report_url and clean(a) == filename]
            if links:
                tokens = _compact(row)
                _require(len(links) == 1 and len(tokens) == 4 and tokens[1] == filename and tokens[2] == "N-CSR",
                         "exact report filename and original N-CSR index row required")
                matching.append({"table_ordinal": table_ordinal, "row_ordinal": row_ordinal,
                                 "document_filename": filename, "document_type": "N-CSR", "index_document_size": _integer(tokens[3])})
    _require(len(matching) == 1, "report must occur exactly once in original index document table")
    return {"filing_date": filed, "accepted_display": accepted, "accepted_display_timezone": "not_supplied_by_index",
            "period_of_report": period, "source_publication_upper_bound_at": upper.isoformat(),
            "publication_bound_policy": "filing_date_UTC_start_plus36hours", "source_publication_pre_cutoff": True,
            "index_document_locator": matching[0]}


def _issuer_name(displayed: str) -> str:
    """Strip only terminal security annotations, regardless of their ordering."""
    issuer = displayed
    while True:
        stripped = re.sub(r"\s*\((?:ADR|USD)\)\s*$", "", issuer)
        stripped = re.sub(r"[\s*†]+$", "", stripped)
        if stripped == issuer:
            return " ".join(issuer.split())
        issuer = stripped


def _delivery_comparison(direct: bytes, complete: bytes, filename: str, entry: dict) -> dict:
    """Recompute exact current-delivery equality; never execute inserted content."""
    named = []
    for match in re.finditer(rb"(?ms)^<DOCUMENT>[ \t]*\r?\n.*?^</DOCUMENT>[ \t]*(?:\r?\n|$)", complete):
        block = match.group()
        header = block.split(b"<TEXT>", 1)[0]
        names = re.findall(rb"(?m)^<FILENAME>([^\r\n]+)", header)
        if filename.encode() in names:
            types = re.findall(rb"(?m)^<TYPE>([^\r\n]+)", header)
            _require(names == [filename.encode()] and types == [b"N-CSR"], "same-named submission member must be an unambiguous N-CSR DOCUMENT")
            named.append(block)
    _require(len(named) == 1, "exactly one same-named N-CSR DOCUMENT required in complete submission")
    embedded = named[0]
    _require(len(embedded) == entry.get("embedded_report_bytes") and _hash(embedded) == entry.get("embedded_report_sha256"),
             "embedded report hash/length mismatch")
    insertions = entry.get("captured_insertions")
    _require(isinstance(insertions, list) and len(insertions) == 4, "exactly four recorded delivery insertions required")
    stripped = direct
    fragments, kinds = [], []
    for insertion in insertions:
        _require(isinstance(insertion, dict) and set(insertion) == {"byte_count", "bytes_utf8", "sha256"}
                 and isinstance(insertion["bytes_utf8"], str) and bool(insertion["bytes_utf8"])
                 and type(insertion["byte_count"]) is int, "typed recorded insertion bytes required")
        fragment = insertion["bytes_utf8"].encode("utf-8")
        _require(len(fragment) == insertion["byte_count"] and _hash(fragment) == insertion["sha256"], "recorded insertion hash/length mismatch")
        _require(fragment not in fragments and direct.count(fragment) == 1 and complete.count(fragment) == 0,
                 "recorded insertion must occur uniquely in direct delivery and not in complete submission")
        if re.fullmatch(rb"<script\b[^>]*>.*?</script>", fragment, flags=re.S | re.I):
            kinds.append("script")
        elif re.fullmatch(rb"<noscript\b[^>]*>.*?</noscript>", fragment, flags=re.S | re.I):
            kinds.append("noscript")
        else:
            _require(False, "recorded insertion must be a complete script or noscript fragment")
        fragments.append(fragment)
        stripped = stripped.replace(fragment, b"", 1)
    _require(sorted(kinds) == ["noscript", "script", "script", "script"], "recorded delivery must contain three scripts and one noscript")
    _require(sum(map(len, fragments)) == entry.get("direct_delivery_extra_bytes"), "recorded insertion total differs from delivery byte discrepancy")
    _require(stripped == embedded and _hash(stripped) == entry["embedded_report_sha256"],
             "direct report does not equal embedded DOCUMENT after only recorded insertions removed")
    return {"exact_equality_recomputed": True, "verified_insertion_count": len(fragments),
            "verified_insertion_bytes": sum(map(len, fragments)), "embedded_report_bytes": len(embedded),
            "embedded_report_sha256": _hash(embedded)}


def parse_schedule(report: bytes, capture: dict) -> dict:
    """Parse only the manifest-selected tables; reject every unexplained pre-total row."""
    doc = Document(report)
    tables = doc.root.find("table")
    ordinals = capture["schedule_table_ordinals"]
    _require(isinstance(ordinals, list) and len(ordinals) == 2 and all(type(n) is int and 0 <= n < len(tables) for n in ordinals)
             and ordinals[1] == ordinals[0] + 1, "two consecutive fixed schedule table ordinals required")
    layout = capture["security_column_order"]
    _require(layout in ("shares_name_value", "name_shares_value"), "supported explicit security column order required")
    # Bind the selected first table to its immediately preceding schedule heading, not an unrelated ETF elsewhere.
    nodes = list(doc.root.walk())
    preceding = nodes[:nodes.index(tables[ordinals[0]])]
    paragraphs = [clean(node) for node in preceding if node.tag == "p" and clean(node)]
    expected_heading = [capture["fund_heading"], "SCHEDULE OF INVESTMENTS", f"September 30, {capture['fiscal_year']}"]
    _require(paragraphs[-3:] == expected_heading, "selected schedule fund/fiscal-year heading mismatch")
    started = False
    ended = False
    securities, audit = [], []
    country, country_value, subtotal_seen = None, 0, False
    printed_total = cost = None
    for ordinal in ordinals:
        for row_ordinal, row in enumerate(tables[ordinal].find("tr")):
            cells, tokens = _cells(row), _compact(row)
            locator = {"table_ordinal": ordinal, "row_ordinal": row_ordinal}
            kind = None
            if not tokens:
                kind = "empty"
            elif tokens == ["Number of Shares", "Value"]:
                kind = "column_header"
            elif len(tokens) == 1 and re.fullmatch(r"COMMON STOCKS: \d+(?:\.\d+)?%", tokens[0]):
                _require(not started and ordinal == ordinals[0], "ambiguous/repeated common-stock start")
                started = True
                kind = "common_stocks_start"
            elif tokens and tokens[0].startswith("Total Common Stocks"):
                _require(started and ordinal == ordinals[-1] and len(tokens) == 2, "missing start or malformed common-stock end")
                match = re.fullmatch(r"Total Common Stocks \(Cost: \$([\d,]+)\)", tokens[0])
                _require(match is not None, "common-stock disclosed cost missing")
                cost, printed_total = _integer(match[1]), _integer(tokens[1])
                kind, ended = "common_stocks_end", True
            else:
                _require(started, "security-looking row before common-stock start")
                if len(tokens) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z .()-]*: \d+(?:\.\d+)?%", tokens[0]):
                    country = tokens[0].split(":")[0]
                    country_value, subtotal_seen = 0, False
                    kind = "country_heading"
                elif len(tokens) == 1 and tokens[0].endswith(" (continued)"):
                    _require(tokens[0] == f"{country} (continued)", "country continuation mismatch")
                    kind = "country_continuation"
                elif len(tokens) == 1 and INTEGER.fullmatch(tokens[0]):
                    _require(country is not None and country_value > 0 and not subtotal_seen and _integer(tokens[0]) == country_value,
                             "ambiguous/mismatched country subtotal row")
                    subtotal_seen, kind = True, "country_subtotal"
                else:
                    _require(len(tokens) == 3 and country is not None and not subtotal_seen, f"malformed/ambiguous security-looking row {locator}: {tokens}")
                    shares_text, displayed, value_text = tokens if layout == "shares_name_value" else (tokens[1], tokens[0], tokens[2])
                    shares, value = _integer(shares_text), _integer(value_text)
                    _require(displayed and not INTEGER.fullmatch(displayed), "nonempty displayed issuer name required")
                    issuer = _issuer_name(displayed)
                    _require(bool(issuer), "stripped issuer name is empty")
                    securities.append({"displayed_name": displayed, "issuer_name": issuer, "shares": shares, "value_usd": value,
                                       "country": country, "source_locator": locator})
                    country_value += value
                    kind = "common_stock_security"
            audit.append({**locator, "cells": cells, "row_kind": kind})
            if ended:
                break
        if ended:
            break
    _require(started and ended and securities, "missing complete common-stock start/end or securities")
    total = sum(security["value_usd"] for security in securities)
    _require(total == printed_total, f"common-stock total mismatch: parsed {total}, printed {printed_total}")
    issuers = {}
    for security in securities:
        issuer = issuers.setdefault(security["issuer_name"], {"issuer_name": security["issuer_name"], "shares": 0, "value_usd": 0,
                                                              "security_locators": []})
        issuer["shares"] += security["shares"]
        issuer["value_usd"] += security["value_usd"]
        issuer["security_locators"].append(security["source_locator"])
    return {"securities": securities, "issuers": [issuers[key] for key in sorted(issuers)], "row_audit": audit,
            "security_count": len(securities), "issuer_count": len(issuers), "printed_common_stock_cost_usd": cost,
            "parsed_common_stock_value_usd": total, "printed_common_stock_value_usd": printed_total,
            "integer_total_reconciled": True, "non_common_stock_assets_excluded_at": audit[-1],
            "issuer_identity_policy": "strip_only_footnote_star_dagger_ADR_USD_then_collapse_exact_displayed_legal_name"}


def replay(manifest_path: Path, evidence_root: Path, *, now: datetime | None = None) -> tuple[dict, dict]:
    current = _time(now or datetime.now(timezone.utc), "actual execution time")
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    _require(isinstance(manifest, dict) and set(manifest) in ({"schema_version", "protocol", "captures"}, {"schema_version", "protocol", "captures", "version_audit"})
             and manifest["schema_version"] == SCHEMA, "exact typed manifest schema required")
    protocol_ref = manifest["protocol"]
    _require(isinstance(protocol_ref, dict) and set(protocol_ref) == {"relative_path", "sha256"}, "typed frozen protocol reference required")
    protocol = json.loads(_bytes(evidence_root, protocol_ref["relative_path"], protocol_ref["sha256"]))
    _require(protocol.get("schema_version") == "ma-evidence-collection-protocol-v1", "frozen collection protocol required")
    _require(_time(protocol.get("registered_at"), "protocol registration") <= current, "protocol registration is in the future")
    _require(protocol.get("buyer_universe_rule", {}).get("membership_rule") == "all_COMMON_STOCKS_legal_corporate_issuers_in_that_funds_schedule",
             "frozen all-common-stock membership rule required")
    captures = manifest["captures"]
    _require(isinstance(captures, list) and len(captures) == 3, "all three dated source captures required")
    version_audit = manifest.get("version_audit")
    comparisons = {}
    submissions = {}
    submission_bytes = {}
    compared_at = None
    if version_audit is not None:
        _require(isinstance(version_audit, dict) and set(version_audit) == {"comparison", "complete_submissions"}, "typed version-audit reference required")
        reference = version_audit["comparison"]
        _require(isinstance(reference, dict) and set(reference) == {"relative_path", "sha256"}, "typed comparison artifact reference required")
        comparison = json.loads(_bytes(evidence_root, reference["relative_path"], reference["sha256"]))
        _require(comparison.get("schema_version") == "ma-buyer-source-delivery-comparison-v1" and comparison.get("human_audit") is False, "mechanical comparison artifact required")
        compared_at = _time(comparison.get("compared_at"), "actual source compared_at")
        _require(compared_at <= current, "source comparison time is in the future")
        for entry in comparison.get("comparisons", []):
            _require(isinstance(entry, dict) and entry.get("fiscal_year") not in comparisons, "unique fiscal-year comparison required")
            comparisons[entry["fiscal_year"]] = entry
        for entry in version_audit["complete_submissions"]:
            _require(isinstance(entry, dict) and set(entry) == {"fiscal_year", "source"} and entry["fiscal_year"] not in submissions, "unique typed complete submission required")
            submission_bytes[entry["fiscal_year"]], _ = _source(evidence_root, entry["source"], current)
            submissions[entry["fiscal_year"]] = entry["source"]
        _require(set(comparisons) == set(submissions) == {2020, 2022, 2023}, "all three version-audit years required")
    observations, universes = [], []
    for capture in captures:
        _require(isinstance(capture, dict) and set(capture) == {"fiscal_year", "observation_year", "information_cutoff_at",
            "fund_heading", "schedule_table_ordinals", "security_column_order", "report", "index"}, "exact typed capture fields required")
        fiscal, target = capture["fiscal_year"], capture["observation_year"]
        _require(type(fiscal) is int and type(target) is int and target == fiscal + 1, "September30 fiscal year must immediately precede observation year")
        expected_fund = "VANECK VECTORS PHARMACEUTICAL ETF" if fiscal == 2020 else "VANECK PHARMACEUTICAL ETF"
        _require(capture["fund_heading"] == expected_fund, "exact PPH fund heading required")
        cutoff = _time(capture["information_cutoff_at"], "information_cutoff_at")
        _require(cutoff == datetime(target, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1), "Jan1 observation's preceding information cutoff required")
        observations.append(f"{target}-01-01")
        report, report_receipt = _source(evidence_root, capture["report"], current)
        index, index_receipt = _source(evidence_root, capture["index"], current)
        publication = _index(index, capture["report"]["source_uri"], capture["index"]["source_uri"], fiscal, cutoff)
        bound = _time(publication["source_publication_upper_bound_at"], "publication bound")
        _require(bound <= _time(report_receipt["retrieved_at"], "report retrieval") and bound <= _time(index_receipt["retrieved_at"], "index retrieval"),
                 "source retrieval predates original publication upper bound")
        schedule = parse_schedule(report, capture)
        index_size = publication["index_document_locator"]["index_document_size"]
        delivery_replay = None
        if version_audit is not None:
            comparison_entry, submission = comparisons[fiscal], submissions[fiscal]
            accession, report_filename = _sec(capture["report"]["source_uri"])
            submission_accession, submission_filename = _sec(submission["source_uri"])
            _require(compared_at >= max(_time(report_receipt["retrieved_at"], "report retrieval"),
                                        _time(submission["retrieved_at"], "complete-submission retrieval")),
                     "comparison time predates an actual direct-report or complete-submission retrieval")
            _require(submission_accession == accession and submission_filename == f"{accession[:10]}-{accession[10:12]}-{accession[12:]}.txt", "complete-submission accession/filename mismatch")
            _require(comparison_entry.get("direct_report_sha256") == capture["report"]["source_sha256"]
                     and comparison_entry.get("complete_submission_sha256") == submission["source_sha256"]
                     and comparison_entry.get("direct_delivery_extra_bytes") == len(report) - index_size
                     and comparison_entry.get("embedded_report_bytes") == index_size
                     and comparison_entry.get("as_accepted_byte_identity_verified") is False
                     and comparison_entry.get("exact_equality_after_only_recorded_insertions_removed") is True, "comparison source/discrepancy binding mismatch")
            delivery_replay = _delivery_comparison(report, submission_bytes[fiscal], report_filename, comparison_entry)
        universes.append({"fiscal_year": fiscal, "observation_year": target, "information_cutoff_at": cutoff.isoformat(),
            "fund_heading": capture["fund_heading"], "sources": {"report": capture["report"], "index": capture["index"]},
            "publication": publication, "captured_report_bytes": len(report), "index_report_bytes": index_size,
            "captured_minus_index_bytes": len(report) - index_size,
            "delivery_discrepancy_status": "recorded_delivery_insertions_replayed_exactly" if version_audit else "capture_index_discrepancy_not_version_verified",
            "delivery_comparison_reference": version_audit["comparison"] if version_audit else None,
            "delivery_comparison_replay": delivery_replay, **schedule})
    _require(sorted(observations) == protocol.get("planned_observation_dates") == ["2021-01-01", "2023-01-01", "2024-01-01"],
             "capture years must match all three frozen protocol observations exactly")
    repo = Path(__file__).resolve().parents[2]
    bindings = {"input_manifest_sha256": _hash(raw_manifest), "protocol_sha256": protocol_ref["sha256"],
                "code_sha256": {name: _hash((repo / name).read_bytes()) for name in CODE_PATHS}}
    disclosures = {"source_publication_pre_cutoff": True, "as_accepted_byte_identity_verified": False,
        "human_audit": False, "original_version_judgement": "pending_primary_and_independent_review",
        "membership_status": "source_backed_parsed_common_stock_membership_not_rating_or_full_model_admission",
        "universe_exhaustive_pharma": False, "jan1_eligibility_verified": False,
        "subsequent_dated_eligibility_review_required": True, "probability": None, "validated_predictive_edge": False,
        "return_backtest_performed": False, "model_training_performed": False}
    output_manifest = {"schema_version": "ma-buyer-replay-manifest-v1", "source_manifest": manifest, **bindings, **disclosures}
    report = {"schema_version": "ma-buyer-universe-replay-v1", **bindings, **disclosures,
              "universes": sorted(universes, key=lambda row: row["observation_year"]), "version_audit_material": version_audit,
              "limits": ["Lagged Sep30 holdings are a finite dated candidate list; not an exhaustive pharmaceutical universe or Jan1 eligibility attestation.",
                         "No eventual-acquirer insertion, current-name mapping, human audit, original-version admission or scientific/buyer ratings.",
                         "Captured/index byte discrepancies are preserved; any bound primary delivery-insertion comparison remains mechanical version-audit material, not as-accepted-byte verification.",
                         "Self-target exclusion and any corporation exits require a subsequent dated identity/eligibility review.",
                         "Index acceptance and filing dates must coincide for these three frozen captures; generalized after-hours SEC calendar handling is outside this replay."]}
    return output_manifest, report


def build(manifest_path: Path, evidence_root: Path, output_dir: Path) -> dict:
    current = datetime.now(timezone.utc)
    manifest, report = replay(manifest_path, evidence_root, now=current)
    manifest_file = write_immutable_json(manifest, output_dir, "ma-buyer-replay-manifest")
    report_file = write_immutable_json(report, output_dir, "ma-buyer-universe")
    execution = {"schema_version": "ma-buyer-replay-execution-v1", "executed_at": current.isoformat(),
                 "manifest_sha256": _hash(manifest_file.read_bytes()), "report_sha256": _hash(report_file.read_bytes()),
                 "source_publication_pre_cutoff": True, "human_audit": False, "model_training_performed": False}
    execution_file = write_immutable_json(execution, output_dir, "ma-buyer-execution")
    return {"status": "mechanical_schedule_replay_not_admitted", "manifest": str(manifest_file),
            "report": str(report_file), "execution": str(execution_file)}
