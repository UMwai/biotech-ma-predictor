"""Turn reviewed, pre-announcement financial reports into dated feature evidence.

This assembles financial evidence only. A known acquired target is not a
historical comparison population, and absent outcomes are never negatives.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.research.adjudication import announcement_bounds

FEATURE_UNITS = {
    "cash_usd": "USD", "assets_usd": "USD",
    "annual_operating_cashflow_usd": "USD/fiscal_year",
    "annual_rd_usd": "USD/fiscal_year", "annual_cash_burn_usd": "USD/fiscal_year",
}
REPORTED_FEATURES = tuple(name for name in FEATURE_UNITS if name != "annual_cash_burn_usd")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any, name: str) -> float:
    _require(type(value) in (int, float) and math.isfinite(value), f"{name}: finite number required")
    return float(value)


def _verified_bytes(root: Path, relative: Any, expected: Any) -> bytes:
    _require(isinstance(relative, str) and bool(relative), "source file path required")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root.resolve()) and path.is_file(), "source file missing or outside evidence directory")
    payload = path.read_bytes()
    _require(hashlib.sha256(payload).hexdigest() == expected, "financial source SHA-256 mismatch")
    return payload


def assemble_financial_seed(records_path: Path, labels_path: Path) -> dict:
    raw_records, raw_labels = records_path.read_bytes(), labels_path.read_bytes()
    dataset, labels = json.loads(raw_records), json.loads(raw_labels)
    _require(dataset.get("schema_version") == "manual-preannouncement-financials-v1", "unsupported financial source schema")
    events = {row["candidate_id"]: row for row in labels["labels"]}
    _require(len(events) == len(labels["labels"]), "duplicate frozen acquisition label")
    rows, seen = [], set()
    for record in dataset.get("records", []):
        cid = record["candidate_id"]
        _require(cid in events, f"unknown acquisition candidate: {cid}")
        event = events[cid]
        _require(int(record["cik"]) == int(event["target_cik"]), "financial issuer differs from reviewed acquisition target")
        _require(record["announcement_date"] == event["announcement_date"], "financial record announcement date differs from reviewed label")
        _require(record.get("filing_form") == "10-K" and record.get("period_type") == "annual", "annual 10-K report required")
        start, end = date.fromisoformat(record["period_start"]), date.fromisoformat(record["period_end"])
        _require(330 <= (end - start).days + 1 <= 400, "annual period must span 330 to 400 days")
        filed = date.fromisoformat(record["filed_date"])
        publication = date.fromisoformat(record["publication_date"])
        _require(end <= filed <= publication, "financial report timing contradicts fiscal period or filing")
        publication_evidence = record.get("publication_evidence", {})
        _require(publication_evidence.get("url", "").startswith("https://") and bool(publication_evidence.get("evidence_paraphrase")),
                 "original publication-date evidence required")
        if record.get("published_at"):
            _require(record.get("publication_timestamp_precision") == "timestamp", "publication timestamp must agree with declared precision")
            available, _, _, _ = announcement_bounds({"announcement_at": record["published_at"],
                                                       "announcement_date": publication.isoformat(),
                                                       "timestamp_precision": "timestamp"})
        else:
            _require(record.get("publication_timestamp_precision") == "date", "explicit publication precision required")
            # Maximum UTC time for an unknown local civil date, not midnight.
            available = datetime.combine(publication, datetime.min.time(), timezone.utc) + timedelta(hours=36)
        _, _, announcement_lower, _ = announcement_bounds(event)
        _require(available < announcement_lower, "financial information was not available before acquisition announcement")
        identity = (int(record["cik"]), start, end)
        _require(identity not in seen, "duplicate company financial period")
        seen.add(identity)
        source_hash = record.get("source_sha256")
        review = json.loads(_verified_bytes(records_path.parent, record.get("evidence_relative_path"), record.get("evidence_sha256")))
        _require(review.get("schema_version") == "manual-financial-evidence-v2", "dated financial review receipt v2 required")
        if record.get("raw_bytes_archived") is True:
            _verified_bytes(records_path.parent, record.get("source_relative_path"), source_hash)
            integrity = "archived_document_hash_verified"
        else:
            _require(source_hash is None and record.get("source_relative_path") is None,
                     "unarchived original source must not claim a document hash")
            integrity = "review_receipt_verified_original_document_not_archived"
        _require(record.get("source_url", "").startswith("https://"), "financial source URL required")
        features = {name: None for name in FEATURE_UNITS}
        provenance = {}
        for name in REPORTED_FEATURES:
            fact = record.get("facts", {}).get(name)
            if fact is None:
                continue
            _require(fact.get("reported") is True and bool(fact.get("reported_label")), f"{name}: reported source fact required")
            _require(bool(fact.get("statement")) and (fact.get("printed_page") is not None or fact.get("pdf_page") is not None),
                     f"{name}: source statement/page locator required")
            multiplier = _number(fact.get("unit_multiplier"), "unit_multiplier")
            expected_multiplier = {"USD": 1, "USD thousands": 1000, "USD millions": 1000000}.get(fact.get("source_unit"))
            _require(multiplier == expected_multiplier, f"{name}: source units and conversion disagree")
            reported, value = _number(fact.get("reported_value"), name), _number(fact.get("value_usd"), name)
            _require(math.isclose(value, reported * multiplier, rel_tol=1e-12, abs_tol=0.01), f"{name}: USD conversion disagrees with reported value")
            _require(fact.get("period_end") == end.isoformat(), f"{name}: period end differs from report")
            expected_start = start.isoformat() if name.startswith("annual_") else None
            _require(fact.get("period_start") == expected_start, f"{name}: annual flow/instant period mismatch")
            _require(name == "annual_operating_cashflow_usd" or value >= 0, f"{name}: unexpected negative amount")
            features[name] = value
            provenance[name] = {**fact, "available_at": available.isoformat(), "source_sha256": source_hash,
                                "source_url": record["source_url"], "source_integrity": integrity}
        _require(any(value is not None for value in features.values()), "financial record has no usable reported features")
        if features["annual_operating_cashflow_usd"] is not None:
            features["annual_cash_burn_usd"] = max(-features["annual_operating_cashflow_usd"], 0.0)
            provenance["annual_cash_burn_usd"] = {"derived_from": "annual_operating_cashflow_usd",
                                                 "formula": "max(-annual_operating_cashflow_usd, 0)",
                                                 "available_at": available.isoformat()}
        for key in ("candidate_id", "cik", "ticker", "period_start", "period_end", "filed_date", "publication_date",
                    "publication_timestamp_precision", "published_at", "filing_form", "period_type", "source_url",
                    "source_sha256", "raw_bytes_archived", "publication_evidence", "facts"):
            _require(review.get(key) == record.get(key), f"financial record differs from dated review receipt: {key}")
        rows.append({"candidate_id": cid, "cik": int(record["cik"]), "ticker": record["ticker"],
                     "period_start": start.isoformat(), "period_end": end.isoformat(),
                     "feature_max_available_at": available.isoformat(), "features": features,
                     "feature_provenance": provenance, "announcement_date": event["announcement_date"],
                     "publication_evidence": publication_evidence, "source_integrity": integrity,
                     "review_receipt_sha256": record["evidence_sha256"],
                     "reviewer": record.get("reviewer"), "independent_human_review": False})
    _require(bool(rows), "no real financial source records supplied")
    rows.sort(key=lambda row: (row["cik"], row["period_end"]))
    return {"schema_version": "reviewed-financial-features-v1", "feature_names": list(FEATURE_UNITS),
            "feature_units": FEATURE_UNITS, "records": rows, "financial_record_count": len(rows),
            "distinct_issuers": len({row["cik"] for row in rows}),
            "source_records_sha256": hashlib.sha256(raw_records).hexdigest(),
            "reviewed_labels_sha256": hashlib.sha256(raw_labels).hexdigest(),
            "training_allowed": False, "eligible_training_observations": 0,
            "scope": "selected acquired-company financial evidence; not a historical prediction panel",
            "remaining_requirements": ["historical observation-date membership", "reviewed comparison-company outcome windows",
                                       "predeclared observation cohorts and complete feature/outcome joins"]}
