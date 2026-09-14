"""Validate reviewed acquisition announcements before freezing a label dataset.

This verifies the review contract, not the truth of a reviewer's assertions.
The SEC candidate ledger and annual reporting proxies alone never enable training.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit


def _timestamp(value: str, field: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be an ISO timestamp with timezone") from exc
    if result.tzinfo is None:
        raise ValueError(f"{field} requires a timezone")
    return result.astimezone(timezone.utc)


def announcement_bounds(row: dict) -> tuple[datetime | None, str, datetime, datetime]:
    """Keep date-only publications uncertain across all civil time zones."""
    supplied = [row[key] for key in ("first_public_announcement_at", "announcement_at", "announced_at") if row.get(key)]
    exact = supplied[0] if supplied else None
    if supplied and any(_timestamp(value, "announcement timestamp") != _timestamp(exact, "announcement timestamp") for value in supplied[1:]):
        raise ValueError("conflicting announcement timestamp aliases")
    precision = row.get("timestamp_precision") or ("timestamp" if exact else "date")
    if precision == "timestamp":
        at = _timestamp(exact, "announcement timestamp")
        day = row.get("announcement_date") or at.date().isoformat()
        try:
            source_day = date.fromisoformat(day)
        except (ValueError, TypeError) as exc:
            raise ValueError("announcement_date must be YYYY-MM-DD") from exc
        midnight = datetime.combine(source_day, datetime.min.time(), timezone.utc)
        if not midnight - timedelta(hours=14) <= at < midnight + timedelta(hours=36):
            raise ValueError("announcement date contradicts timestamp")
        return at, day, at, at
    if precision != "date" or exact:
        raise ValueError("timestamp_precision must agree with available announcement evidence")
    try:
        day = date.fromisoformat(row.get("announcement_date", ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("announcement_date must be YYYY-MM-DD for date-only evidence") from exc
    midnight = datetime.combine(day, datetime.min.time(), timezone.utc)
    return None, day.isoformat(), midnight - timedelta(hours=14), midnight + timedelta(hours=36)


def validate_reviews(candidates: list[dict], reviews: list[dict]) -> dict:
    """Require explicit, traceable decisions; incomplete rows remain pending."""
    by_id = {row["candidate_id"]: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("duplicate candidate IDs")
    seen, events, labels, rejected = set(), set(), [], []
    for row in reviews:
        candidate_id = row.get("candidate_id", "").strip()
        if candidate_id not in by_id:
            raise ValueError(f"unknown candidate: {candidate_id}")
        if candidate_id in seen:
            raise ValueError(f"duplicate review: {candidate_id}")
        seen.add(candidate_id)
        decision = row.get("decision", "").strip().lower()
        if not decision or decision == "pending":
            continue
        if decision not in {"include", "exclude"}:
            raise ValueError(f"{candidate_id}: decision must be include, exclude, or pending")
        for key in ("reviewer", "reviewed_at", "review_notes", "review_primary_source_url"):
            if not row.get(key, "").strip():
                raise ValueError(f"{candidate_id}: {key} is required")
        reviewed_at = _timestamp(row["reviewed_at"], "reviewed_at")
        if reviewed_at > datetime.now(timezone.utc):
            raise ValueError(f"{candidate_id}: review timestamp is in the future")
        source = urlsplit(row["review_primary_source_url"])
        if source.scheme != "https" or not source.hostname or source.username or source.password:
            raise ValueError(f"{candidate_id}: primary source must be a public HTTPS URL")
        if decision == "exclude":
            rejected.append(dict(row))
            continue
        for key in ("reviewed_target_name", "reviewed_target_cik", "acquirer_name",
                    "transaction_structure", "transaction_status"):
            if not row.get(key, "").strip():
                raise ValueError(f"{candidate_id}: {key} is required")
        announced_at, announcement_date, lower, upper = announcement_bounds(row)
        if upper > reviewed_at:
            raise ValueError(f"{candidate_id}: announcement occurs after review")
        if announcement_date > by_id[candidate_id]["sec_signal_date"]:
            raise ValueError(f"{candidate_id}: announcement after candidate filing; review candidate linkage")
        try:
            cik = int(row["reviewed_target_cik"])
            control = float(row.get("change_of_control_percent", ""))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{candidate_id}: CIK and control percent must be numeric") from exc
        if cik <= 0 or not 50 < control <= 100:
            raise ValueError(f"{candidate_id}: target CIK must be positive and control must exceed 50%")
        candidate_cik = by_id[candidate_id].get("target_cik")
        if candidate_cik and str(candidate_cik).isdigit() and cik != int(candidate_cik):
            raise ValueError(f"{candidate_id}: reviewed target CIK differs from candidate target")
        if row["transaction_structure"] not in {"cash", "stock", "mixed", "tender_offer"}:
            raise ValueError(f"{candidate_id}: unsupported change-of-control transaction structure")
        if row["transaction_status"] not in {"pending", "completed", "terminated", "withdrawn"}:
            raise ValueError(f"{candidate_id}: unsupported transaction outcome")
        # Timing disagreements must be reviewed, not counted as additional deals.
        identity = (cik, announcement_date)
        if identity in events:
            raise ValueError(f"duplicate acquisition announcement: {identity}")
        events.add(identity)
        labels.append({
            "candidate_id": candidate_id,
            "target_cik": cik,
            "target_name": row["reviewed_target_name"],
            "target_ticker": row.get("reviewed_target_ticker", ""),
            "acquirer_name": row["acquirer_name"],
            "announced_at": announced_at.isoformat() if announced_at else None,
            "announcement_date": announcement_date,
            "timestamp_precision": "timestamp" if announced_at else "date",
            "announcement_lower_at": lower.isoformat(),
            "announcement_upper_at": upper.isoformat(),
            "event_id": f"{cik}:{announcement_date}",
            "transaction_structure": row["transaction_structure"],
            "change_of_control_percent": control,
            "transaction_status": row["transaction_status"],
            "primary_source_url": row["review_primary_source_url"],
            "reviewer": row["reviewer"],
            "reviewed_at": reviewed_at.isoformat(),
            "review_notes": row["review_notes"],
            "evidence_record_id": row.get("evidence_record_id"),
            "public_listing_source_url": row.get("public_listing_source_url") or row.get("public_listing_evidence_url"),
            "source_title": row.get("source_title"),
            "source_retrieved_at": row.get("retrieved_at") or row.get("source_retrieved_at"),
            "transaction_status_as_of": row.get("transaction_status_as_of"),
            "label": "definitive_change_of_control_announcement",
        })
    labels.sort(key=lambda row: (row["announcement_lower_at"], row["target_cik"]))
    return {
        "labels": labels,
        "excluded_reviews": sorted(rejected, key=lambda row: row["candidate_id"]),
        "candidate_count": len(candidates),
        "reviewed_positive_count": len(labels),
        "reviewed_excluded_count": len(rejected),
        "pending_count": len(candidates) - len(labels) - len(rejected),
        "training_allowed": False,
        "remaining_gates": [
            "independent label-quality audit and complete event ascertainment",
            "historical exchange membership including delisted controls",
            "point-in-time company observations and complete/censored outcome windows",
            "walk-forward evaluation and forward sealed predictions",
        ],
    }


def freeze_reviews(result: dict, output_dir: Path, input_hashes: dict[str, str]) -> Path:
    """Write a content-addressed review snapshot; never revise an existing one."""
    if not result["labels"]:
        raise ValueError("no reviewed positive labels to freeze")
    payload = json.dumps({"schema_version": "reviewed-deals-v2", **result,
                          "input_sha256": input_hashes}, sort_keys=True, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    path = output_dir / f"{digest}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError(f"frozen label snapshot has been modified: {path}")
    return path
