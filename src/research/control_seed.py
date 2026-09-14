"""Verify reviewed issuer-news outcome windows without inventing training rows.

Completeness refers to the designated issuer archive as retrieved. It does not
claim a census of regulatory filings, third-party news, or removed web pages.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "control evidence timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def _source(directory: Path, record: dict[str, Any]) -> bytes:
    path = (directory / record["source_relative_path"]).resolve()
    _require(path.is_relative_to(directory.resolve()), "control source escapes evidence directory")
    payload = path.read_bytes()
    _require(hashlib.sha256(payload).hexdigest() == record["source_sha256"], "control source hash mismatch")
    if "source_bytes" in record:
        _require(len(payload) == record["source_bytes"], "control source byte count mismatch")
    return payload


def assemble_control_seed(manifest_path: Path) -> dict[str, Any]:
    directory = manifest_path.parent
    manifest = json.loads(manifest_path.read_bytes())
    _require(manifest.get("schema_version") == "reviewed-control-inputs-v1", "unsupported control input schema")
    output, identities = [], set()
    for item in manifest["records"]:
        archive = json.loads(_source(directory, item["archive"]))
        listing = json.loads(_source(directory, item["listing"]))
        _require(archive.get("schema_version") == "issuer-archive-window-review-v1", "unsupported archive review schema")
        _require(listing.get("schema_version") == "historical-listing-source-review-v1", "unsupported listing review schema")
        cik, ticker = int(archive["issuer"]["cik"]), archive["issuer"]["ticker"]
        _require(cik == int(listing["issuer"]["cik"]) and ticker == listing["issuer"]["ticker"], "control issuer mismatch")
        start, end = date.fromisoformat(archive["proposed_window"]["start_date"]), date.fromisoformat(archive["proposed_window"]["end_date"])
        _require(end - start == timedelta(days=365), "control review requires a complete 365-day window")
        identity = (cik, start, end)
        _require(identity not in identities, "duplicate control window")
        identities.add(identity)
        _require(archive.get("archive_complete") is True, "issuer archive review is incomplete")
        _require(archive.get("body_review_complete") is True, "issuer body review is incomplete")
        archive_reviewed = _time(archive["reviewed_at"])
        _require(archive_reviewed >= _time(end.isoformat() + "T00:00:00Z") + timedelta(hours=36),
                 "control review precedes complete outcome maturity")
        for source in archive.get("navigation_evidence", []):
            _source(directory, source)
            _require(_time(source["retrieved_at"]) <= archive_reviewed, "archive review precedes navigation retrieval")
        inventory = archive["inventory"]
        urls = [row["url"] for row in inventory]
        _require(len(urls) == len(set(urls)), "duplicate archive inventory URL")
        years = archive["archive_years"]
        _require(len(years) == len({row["year"] for row in years}), "duplicate archive year")
        _require({row["year"] for row in years} == set(range(start.year, end.year + 1)), "archive years do not cover outcome window")
        for year in years:
            pages = year["pages"]
            _require({row["page"] for row in pages} == set(range(1, year["total_pages"] + 1)) and len(pages) == year["total_pages"], "archive pagination gap")
            entries = [row for row in inventory if row["archive_year"] == year["year"]]
            _require(len(entries) == year["total_rows"] == sum(row["entry_count"] for row in pages), "archive inventory count mismatch")
            for page in pages:
                _source(directory, page)
                _require(_time(page["retrieved_at"]) <= archive_reviewed, "archive review precedes page retrieval")
                if "reported_pager" in page:
                    pager = page["reported_pager"]
                    _require(pager["page"] == page["page"] and
                             all(pager[key] == year[key] for key in ("total_rows", "total_pages")),
                             "reported archive pagination disagrees with inventory")
                if "selected_year" in page:
                    _require(str(page["selected_year"]) == str(year["year"]), "archive selected year mismatch")
                _require(sum(row["archive_page"] == page["page"] for row in entries) == page["entry_count"], "archive page inventory mismatch")
            _require(all(date.fromisoformat(row["date"]).year == year["year"] for row in entries), "archive entry year mismatch")
        required = {row["url"]: row for row in inventory if start <= date.fromisoformat(row["date"]) <= end}
        _require(bool(required), "empty outcome archive inventory")
        reviews = archive["body_reviews"]
        bodies = {row["url"]: row for row in reviews}
        _require(len(bodies) == len(reviews) and set(required) <= set(bodies), "missing or duplicate full-body review")
        reviewed_at = max(_time(listing["reviewed_at"]), archive_reviewed)
        for url, body in bodies.items():
            _source(directory, body)
            _require(url in urls, "body review outside enumerated archive")
            entry = next(row for row in inventory if row["url"] == url)
            _require(all(body[key] == entry[key] for key in ("date", "title")), "body review inventory identity mismatch")
            _require(bool(body.get("reviewer")) and bool(body.get("review_reason", "").strip()), "substantive body review required")
            body_reviewed = _time(body["reviewed_at"])
            _require(_time(body["retrieved_at"]) <= body_reviewed, "review precedes source retrieval")
            reviewed_at = max(reviewed_at, body_reviewed)
            if url in required:
                _require(body.get("qualified_target_control_event") is False, "positive or unresolved target event in control window")
                _require(body.get("censoring_event") is False, "censored or unresolved control window")
        _require(reviewed_at <= datetime.now(timezone.utc), "future control review")
        membership = listing["membership"]
        _require(membership.get("kind") == "historical_exchange_membership" and membership.get("security_type") == "common_equity" and membership.get("biotech_eligible") is True, "historical biotech common-equity evidence required")
        _require(_time(membership["valid_from"]).date() <= start and _time(membership["valid_until"]).date() > end, "listing evidence does not cover entire outcome window")
        output.append({"cik": cik, "ticker": ticker, "window_start_date": start.isoformat(),
                       "window_end_date": end.isoformat(), "horizon_days": 365,
                       "event_class": "no_change_of_control_announcement", "reviewed": True,
                       "reviewed_at": reviewed_at.isoformat(), "available_at": reviewed_at.isoformat(),
                       "availability_method": "Actual completed review time; no historical availability of this assembled label is asserted.",
                       "coverage_scope": "Complete designated issuer news archive as retrieved, with explicit issuer historical listing assertion; not an independently verified regulatory-event census.",
                       "reviewed_window_release_count": len(required), "archived_body_count": len(bodies),
                       "membership": membership, "archive_evidence": item["archive"], "listing_evidence": item["listing"],
                       "risk_set_eligible": None, "features": None, "training_allowed": False})
    return {"schema_version": "reviewed-control-windows-v1", "records": output,
            "reviewed_negative_company_windows": len(output), "eligible_feature_observations": 0,
            "training_allowed": False, "model_trained_on_real_data": False,
            "limitations": ["Purposive research sample, not a complete historical universe.",
                            "Pre-observation eligibility, contemporaneous features and historical label availability remain unassembled.",
                            "Codex source review; independent human audit outstanding."]}
