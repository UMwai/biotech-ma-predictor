"""Verify original annual disclosures for either acquired or comparison issuers."""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from src.research.financial_seed import FEATURE_UNITS, REPORTED_FEATURES, _number, _require, _verified_bytes


def _sec_document(url: str) -> tuple[str, str, str] | None:
    """Parse an original EDGAR URL without ambiguous hosts or path traversal."""
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        return None
    if (parsed.scheme != "https" or parsed.netloc not in ("www.sec.gov", "sec.gov")
            or parsed.query or parsed.fragment):
        return None
    match = re.fullmatch(r"/Archives/edgar/data/([0-9]+)/([0-9]{18})/([A-Za-z0-9][A-Za-z0-9_.-]*\.(?:htm|html))",
                         parsed.path)
    return match.groups() if match else None


def read_reviewed_financials(paths: list[Path]) -> list[dict]:
    result, seen = [], set()
    for path in paths:
        dataset = json.loads(path.read_bytes())
        _require(dataset.get("schema_version") == "reviewed-panel-annual-financials-v1", "unsupported panel financial schema")
        for record in dataset["records"]:
            prefix = record["record_id"] + ": "
            _require(type(record["cik"]) is int and record["cik"] > 0, prefix + "positive issuer CIK required")
            _require(record["filing_form"] in ("10-K", "S-1", "S-1/A", "424B4") and record["period_type"] == "annual",
                     prefix + "original annual financial statements required")
            start, end = date.fromisoformat(record["period_start"]), date.fromisoformat(record["period_end"])
            _require(330 <= (end - start).days + 1 <= 400, prefix + "invalid annual duration")
            filed, published = date.fromisoformat(record["filed_date"]), date.fromisoformat(record["publication_date"])
            _require(end <= filed <= published, prefix + "report chronology contradicts fiscal period")
            _require(record.get("publication_date_verified") is True and
                     record.get("publication_timestamp_precision") == "date" and record.get("published_at") is None,
                     prefix + "verified original date-only publication required")
            publication_evidence = record["publication_evidence"]
            _require(publication_evidence.get("url", "").startswith("https://") and bool(publication_evidence.get("evidence_paraphrase")),
                     prefix + "original publication-date source required")
            available = datetime.combine(published, datetime.min.time(), timezone.utc) + timedelta(hours=36)
            _require(datetime.fromisoformat(record["available_at"].replace("Z", "+00:00")) == available,
                     prefix + "availability must preserve publication-date uncertainty")
            retrieved = datetime.fromisoformat(record["retrieved_at"].replace("Z", "+00:00"))
            reviewed = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
            _require(retrieved.tzinfo is not None and reviewed.tzinfo is not None and
                     available <= retrieved <= reviewed <= datetime.now(timezone.utc), prefix + "retrieval/review chronology invalid")
            review = json.loads(_verified_bytes(path.parent, record["evidence_relative_path"], record["evidence_sha256"]))
            _require(review.get("schema_version") == "manual-financial-evidence-v2", prefix + "dated financial receipt required")
            bound = {key: value for key, value in record.items() if key not in ("evidence_relative_path", "evidence_sha256")}
            _require(review == {**bound, "schema_version": "manual-financial-evidence-v2"}, prefix + "financial metadata or values disagree with review")
            _require(record.get("source_url", "").startswith("https://"), prefix + "source URL required")
            if record.get("raw_bytes_archived") is True:
                payload = _verified_bytes(path.parent, record["source_relative_path"], record["source_sha256"])
                _require(len(payload) == record["source_bytes"], prefix + "source byte count mismatch")
                integrity = "archived_original_document"
            else:
                _require(record.get("source_sha256") is None and record.get("source_relative_path") is None,
                         prefix + "unarchived source cannot claim original bytes or their hash")
                _require(record.get("original_sec_url") == record["source_url"] and _sec_document(record["source_url"]) is not None,
                         prefix + "browser-only financial review requires original regulatory document")
                integrity = "review_receipt_original_SEC_document_not_archived"
            identity = (record["cik"], start, end, available)
            _require(identity not in seen, prefix + "duplicate issuer annual financial record")
            seen.add(identity)
            features = {name: None for name in FEATURE_UNITS}
            _require(set(record["facts"]) <= set(REPORTED_FEATURES), prefix + "unsupported reported feature")
            for name, fact in record["facts"].items():
                if fact is None:
                    continue
                _require(fact.get("reported") is True and fact.get("reported_label") and fact.get("statement") and
                         (fact.get("printed_page") is not None or fact.get("pdf_page") is not None or
                          bool(fact.get("table_locator"))), prefix + "statement locator required")
                if fact.get("table_locator"):
                    original = _sec_document(record.get("original_sec_url", ""))
                    statement_source = _sec_document(fact.get("source_url", ""))
                    _require(original is not None and statement_source is not None and
                             original[:2] == statement_source[:2] and
                             re.fullmatch(r"R[0-9]+\.htm", statement_source[2]) is not None,
                             prefix + "statement table must identify the same original SEC accession")
                expected_multiplier = {"USD": 1, "USD thousands": 1000, "USD millions": 1000000}.get(fact.get("source_unit"))
                multiplier = _number(fact.get("unit_multiplier"), "unit_multiplier")
                _require(multiplier == expected_multiplier, prefix + "source unit conversion mismatch")
                reported, value = _number(fact.get("reported_value"), name), _number(fact.get("value_usd"), name)
                _require(math.isclose(value, reported * multiplier, rel_tol=1e-12, abs_tol=0.01), prefix + "reported value conversion mismatch")
                annual = name.startswith("annual_")
                _require(fact.get("unit") == FEATURE_UNITS[name] and fact.get("period_end") == end.isoformat() and
                         fact.get("period_start") == (start.isoformat() if annual else None) and
                         fact.get("period_type") == ("annual" if annual else "instant"), prefix + "flow/instant period or units mismatch")
                _require(name == "annual_operating_cashflow_usd" or value >= 0, prefix + "unexpected negative financial amount")
                features[name] = value
            _require(any(value is not None for value in features.values()), prefix + "no observed financial features")
            ocf = features["annual_operating_cashflow_usd"]
            features["annual_cash_burn_usd"] = None if ocf is None else max(-ocf, 0.0)
            result.append({"record_id": record["record_id"], "cik": record["cik"], "ticker": record["ticker"],
                           "period_start": start.isoformat(), "period_end": end.isoformat(), "features": features,
                           "feature_max_available_at": available.isoformat(), "source_integrity": integrity,
                           "source_url": record["source_url"], "source_sha256": record.get("source_sha256"),
                           "review_receipt_sha256": record["evidence_sha256"], "reviewed_at": reviewed.isoformat()})
    return sorted(result, key=lambda row: (row["cik"], row["period_end"], row["feature_max_available_at"]))


def financials_at_cutoff(records: list[dict], cik: int, cutoff: datetime) -> dict | None:
    """Choose the latest reviewed original annual report actually available then."""
    _require(cutoff.tzinfo is not None, "financial cutoff requires timezone")
    eligible = [row for row in records if row["cik"] == cik and
                datetime.fromisoformat(row["feature_max_available_at"]) <= cutoff]
    return max(eligible, key=lambda row: (row["period_end"], row["feature_max_available_at"])) if eligible else None
