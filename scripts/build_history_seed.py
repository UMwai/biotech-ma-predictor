#!/usr/bin/env python3
"""Assemble source-reviewed announcements; do not invent historical controls."""

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.adjudication import freeze_reviews, validate_reviews  # noqa: E402


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(parsed.tzinfo is not None, "source/review timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def _verified_panel_progress(directory: Path, frozen_labels: Path) -> int:
    """Reject stale summaries and replay their actual source dependencies."""
    status_path, report_path, panel_path = (directory / "panel_seed" / name for name in ("status.json", "assembly.json", "panel.json"))
    status, report, panel = (json.loads(path.read_bytes()) for path in (status_path, report_path, panel_path))
    _require(status.get("schema_version") == "historical-panel-assembly-v1"
             and status.get("model_training_performed") is False, "invalid historical panel progress")
    _require(_sha256(report_path.read_bytes()) == status.get("coverage_report_sha256")
             and _sha256(panel_path.read_bytes()) == status.get("panel_sha256"),
             "historical panel progress differs from saved assembly or feature panel")
    summary = {key: value for key, value in report.items() if key not in ("coverage", "panel", "corpus_reviews")}
    _require(all(key in status and status[key] == value for key, value in summary.items())
             and panel == report.get("panel"), "historical panel summary or feature panel differs from assembly")
    count = status["eligible_feature_observations"]
    _require(type(count) is int and count >= 0 and count == report.get("eligible_feature_observations") == len(panel["observations"]),
             "historical panel observation count differs from assembly")
    # Keys deliberately mirror panel_assembly's producer contract. Newly added or
    # removed optional financial inputs must invalidate a previously saved panel.
    paths = {"sampling_frame": directory / "panel_seed/sampling_frame.json",
             "frame_source_receipt": directory / "panel_seed/nasdaq_source_receipt.json",
             "frozen_labels": frozen_labels,
             "observation_adjudications": directory / "panel_seed/observation_adjudications.json"}
    for name in ("financial_records.json", "positive_financial_records.json"):
        path = directory / "panel_financials" / name
        if path.exists():
            paths[name] = path
    expected = {key: _sha256(path.read_bytes()) if path.exists() else None for key, path in paths.items()}
    _require(report.get("input_sha256") == expected, "historical panel source inputs changed; reassemble before publishing")
    # File-level fingerprints are insufficient when a referenced raw document or
    # review receipt changes without editing its parent manifest. Replay those too.
    from src.research.panel_assembly import assemble_research_panel

    replayed = assemble_research_panel(directory, now=_timestamp(report["generated_at"]))
    _require(replayed == report, "historical panel no longer replays from current source evidence")
    return count


def _verified_review(row: dict, record: dict, candidate: dict, schema: str) -> dict:
    """Cross-check recorded evidence; never claim that matching receipts prove truth."""
    cid = row["candidate_id"]
    prefix = f"{cid}: "
    _require(int(row["reviewed_target_cik"]) == int(record["target_cik"]) == int(candidate["target_cik"]),
             prefix + "review/evidence/candidate CIK mismatch")
    for key in ("sec_signal_date", "filer_name", "filer_tickers", "event_class"):
        _require(row[key] == candidate[key], prefix + f"candidate {key} mismatch")
    for csv_key, evidence_key in (("reviewed_target_name", "target_name"),
                                  ("reviewed_target_ticker", "target_ticker"),
                                  ("acquirer_name", "acquirer_name"),
                                  ("announcement_date", "announcement_date"),
                                  ("timestamp_precision", "timestamp_precision"),
                                  ("transaction_status_as_of", "transaction_status_as_of"),
                                  ("reviewer", "reviewer"), ("reviewed_at", "reviewed_at")):
        _require(row[csv_key] == record[evidence_key], prefix + f"review/evidence {csv_key} mismatch")
    _require((row.get("first_public_announcement_at") or None) == record.get("first_public_announcement_at"),
             prefix + "review/evidence announcement timestamp mismatch")
    if schema == "historical-primary-source-review-v1":
        _require(record["definitive_full_company_acquisition"] is True and row["decision"] == "include",
                 prefix + "unsupported seed decision")
        control = record["proposed_post_transaction_control_percent"]
        status = record["transaction_status"]
        structure = record["transaction_structure"]
        sources = [record["primary_source"], *record["supporting_primary_sources"]]
        listing = record["public_listing"]
        primary = record["primary_source"]
        retrieved = record["retrieved_at"]
        record_id = record["evidence_record_id"]
        _require(row["evidence_record_id"] == record_id, prefix + "evidence record ID mismatch")
        identity = record["target_identity"]
        _require(int(identity["cik"]) == int(candidate["target_cik"]), prefix + "target identity CIK mismatch")
        _require(identity["candidate_filing_url"] in json.loads(candidate["primary_source_urls"]),
                 prefix + "target identity filing is not in candidate ledger")
        _require(record["independent_human_review"] is False, prefix + "unexpected human-audit claim")
    else:
        unsigned = {key: value for key, value in record.items() if key != "review_record_sha256"}
        record_hash = _sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode())
        _require(record["review_record_sha256"] == record_hash, prefix + "review record hash mismatch")
        _require(row["decision"] == record["decision"] == "include", prefix + "unsupported seed decision")
        _require(record["training_allowed"] is False and record["reviewer_is_independent_human"] is False,
                 prefix + "unexpected training or human-audit claim")
        control = record["intended_post_transaction_control_percent"]
        status = record["transaction_status_at_announcement"]
        structure = {"tender_offer_then_merger": "tender_offer"}.get(record["transaction_structure"], record["transaction_structure"])
        sources = record["sources"]
        listing = record["listing_evidence"]
        matches = [source for source in sources if source["url"] == row["review_primary_source_url"]]
        _require(len(matches) == 1, prefix + "primary source identity mismatch")
        primary = matches[0]
        retrieved = primary["retrieved_at"]
        # This is an actual review-receipt hash, not an invented source identifier.
        record_id = "sha256:" + record_hash
        lineage = record["sec_candidate_lineage"]
        for key in ("candidate_id", "filer_name", "sec_signal_date"):
            _require(lineage[key] == candidate[key], prefix + f"SEC lineage {key} mismatch")
        _require(int(lineage["target_cik"]) == int(candidate["target_cik"]), prefix + "SEC lineage CIK mismatch")
        for source_key, candidate_key in (("candidate_source_urls", "primary_source_urls"),
                                          ("accession_numbers", "accession_numbers"), ("filing_forms", "filing_forms")):
            _require(lineage[source_key] == json.loads(candidate[candidate_key]), prefix + f"SEC lineage {source_key} mismatch")
    _require(float(row["change_of_control_percent"]) == float(control), prefix + "control evidence mismatch")
    _require(row["transaction_status"] == status and row["transaction_structure"] == structure,
             prefix + "transaction evidence mismatch")
    source_urls = [source["url"] for source in sources]
    _require(len(set(source_urls)) == len(source_urls), prefix + "duplicate evidence source URL")
    for url in source_urls:
        parsed = urlsplit(url)
        _require(parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password,
                 prefix + "source requires public HTTPS URL")
    _require(primary["url"] == row["review_primary_source_url"] and primary["title"] == row["source_title"],
             prefix + "primary source identity mismatch")
    _require((primary.get("published_date") or primary.get("source_date")) == row["announcement_date"],
             prefix + "primary source date mismatch")
    listing_url = row.get("public_listing_source_url") or row.get("public_listing_evidence_url")
    _require(listing_url == listing["source_url"] and listing_url in source_urls,
             prefix + "listing source identity mismatch")
    _require(listing["ticker"] == row["reviewed_target_ticker"], prefix + "listing ticker mismatch")
    row_retrieved = row.get("source_retrieved_at") or row.get("retrieved_at")
    _require(row_retrieved == retrieved, prefix + "retrieval receipt mismatch")
    _require(_timestamp(retrieved) <= _timestamp(row["reviewed_at"]) <= datetime.now(timezone.utc),
             prefix + "retrieval/review chronology mismatch")
    # Normalize only fields genuinely recorded in the two supported evidence schemas.
    return {**row, "retrieved_at": retrieved, "source_retrieved_at": retrieved,
            "evidence_record_id": record_id, "public_listing_source_url": listing_url}


def freeze_seed_labels(root: Path = ROOT) -> tuple[dict, Path, dict]:
    """Verify reviewed events independently of derived financial/panel snapshots."""
    directory = root / "data/history"
    candidates_path = root / "output/historical_deal_candidates/candidates.csv"
    candidate_payload = candidates_path.read_bytes()
    candidates = list(csv.DictReader(io.StringIO(candidate_payload.decode("utf-8"))))
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    _require(len(by_id) == len(candidates), "duplicate candidate IDs")
    candidate_hash = _sha256(candidate_payload)
    reviews, hashes = [], {str(candidates_path.relative_to(root)): candidate_hash}
    review_paths = sorted(directory.glob("reviews_*.csv"))
    if not review_paths:
        raise ValueError("no source-reviewed history batches")
    for path in review_paths:
        evidence_path = path.with_name(path.name.replace("reviews_", "evidence_")).with_suffix(".json")
        review_payload, evidence_payload = path.read_bytes(), evidence_path.read_bytes()
        evidence = json.loads(evidence_payload)
        schema = evidence.get("schema_version")
        _require(schema in {"historical-primary-source-review-v1", "primary-source-deal-review-evidence-v1"},
                 f"unsupported history evidence schema: {schema}")
        if schema == "historical-primary-source-review-v1":
            review_hash, ledger_hash = evidence["review_csv_sha256"], evidence["candidate_sha256"]
            ledger_path = evidence["candidate_file"]
        else:
            integrity = evidence["integrity"]
            review_hash, ledger_hash = integrity["reviews_csv_sha256"], integrity["candidate_input_sha256"]
            ledger_path = integrity["candidate_input_path"]
            _require(integrity["reviews_csv_path"] == str(path.relative_to(root)), "review receipt path mismatch")
        _require(ledger_path == str(candidates_path.relative_to(root)), "candidate receipt path mismatch")
        if review_hash != _sha256(review_payload):
            raise ValueError(f"review CSV disagrees with its evidence receipt: {path}")
        if ledger_hash != candidate_hash:
            raise ValueError(f"candidate ledger changed since source review: {path}")
        batch = list(csv.DictReader(io.StringIO(review_payload.decode("utf-8"))))
        records = {record["candidate_id"]: record for record in evidence["records"]}
        _require(len(records) == len(evidence["records"]), f"duplicate evidence candidate IDs: {path}")
        record_ids = [record["evidence_record_id"] for record in evidence["records"] if record.get("evidence_record_id")]
        _require(len(record_ids) == len(set(record_ids)), f"duplicate evidence record IDs: {path}")
        if len(records) != len(batch) or {row["candidate_id"] for row in batch} != set(records):
            raise ValueError(f"review/evidence coverage mismatch: {path}")
        for row in batch:
            record = records[row["candidate_id"]]
            _require(row["candidate_id"] in by_id, f"unknown candidate: {row['candidate_id']}")
            reviews.append(_verified_review(row, record, by_id[row["candidate_id"]], schema))
        hashes.update({str(path.relative_to(root)): _sha256(review_payload),
                       str(evidence_path.relative_to(root)): _sha256(evidence_payload)})
    result = validate_reviews(candidates, reviews)
    frozen = freeze_reviews(result, root / "data/reviewed_deals", hashes)
    return result, frozen, hashes


def build_seed(root: Path = ROOT) -> dict:
    directory = root / "data/history"
    result, frozen, hashes = freeze_seed_labels(root)
    financial_features = directory / "financial_seed/feature_snapshot.json"
    financial_count = financial_issuers = 0
    financial_hash = None
    if financial_features.exists():
        from src.research.financial_seed import assemble_financial_seed

        verified = assemble_financial_seed(directory / "financial_seed/financial_records.json", frozen)
        _require(json.loads(financial_features.read_bytes()) == verified, "saved financial features differ from verified source evidence")
        financial_count, financial_issuers = verified["financial_record_count"], verified["distinct_issuers"]
        financial_hash = _sha256(financial_features.read_bytes())
    control_inputs = directory / "control_seed/review_inputs.json"
    control_count = 0
    control_hash = None
    if control_inputs.exists():
        from src.research.control_seed import assemble_control_seed

        controls = assemble_control_seed(control_inputs)
        control_payload = (json.dumps(controls, indent=2, sort_keys=True) + "\n").encode()
        (directory / "control_seed/reviewed_controls.json").write_bytes(control_payload)
        control_count = controls["reviewed_negative_company_windows"]
        control_hash = _sha256(control_payload)
        hashes[str(control_inputs.relative_to(root))] = _sha256(control_inputs.read_bytes())
    panel_status_path = directory / "panel_seed/status.json"
    panel_observations = 0
    if panel_status_path.exists():
        panel_observations = _verified_panel_progress(directory, frozen)
    # This convenience copy is sealed into each published local snapshot.
    (directory / "frozen_labels.json").write_bytes(frozen.read_bytes())
    status = {
        "schema_version": "historical-training-readiness-v1",
        "status": "data_incomplete", "model_trained_on_real_data": False,
        "review_method": "Codex primary-source review; independent audit outstanding",
        "reviewed_positive_announcements": result["reviewed_positive_count"],
        "reviewed_negative_company_windows": control_count,
        "reviewed_control_snapshot_sha256": control_hash,
        "eligible_feature_observations": panel_observations,
        "historical_financial_records": financial_count,
        "historical_financial_issuers": financial_issuers,
        "financial_feature_snapshot_sha256": financial_hash,
        "pending_candidates": result["pending_count"],
        "by_announcement_year": dict(sorted(Counter(row["announcement_date"][:4] for row in result["labels"]).items())),
        "training_allowed": False,
        "blockers": result["remaining_gates"][:3],
        "frozen_labels_sha256": _sha256(frozen.read_bytes()),
        "frozen_labels_path": str(frozen.relative_to(root)),
        "input_sha256": hashes,
        "next_step": "Acquire historical listing membership, reviewed outcome windows, and features published before each observation date.",
    }
    (directory / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-labels-only", action="store_true",
                        help="Update reviewed labels before rebuilding their derived financial and panel artifacts; does not publish readiness")
    args = parser.parse_args()
    try:
        if args.freeze_labels_only:
            result, frozen, _ = freeze_seed_labels()
            (ROOT / "data/history/frozen_labels.json").write_bytes(frozen.read_bytes())
            print(json.dumps({"status": "labels_frozen_derived_artifacts_require_rebuild",
                              "reviewed_positive_announcements": result["reviewed_positive_count"],
                              "frozen_labels_path": str(frozen), "frozen_labels_sha256": _sha256(frozen.read_bytes()),
                              "model_training_performed": False}, indent=2))
        else:
            print(json.dumps(build_seed(), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        print(f"Historical seed build failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
