"""Outcome evidence must fail closed on gaps, censoring and broken lineage."""

import hashlib
import json

import pytest

from src.research.control_seed import assemble_control_seed


def write_source(directory, name, value):
    payload = (json.dumps(value, sort_keys=True) + "\n").encode()
    (directory / name).write_bytes(payload)
    return {"source_relative_path": name, "source_sha256": hashlib.sha256(payload).hexdigest(),
            "source_bytes": len(payload)}


@pytest.fixture
def evidence(tmp_path):
    issuer = {"cik": 123, "ticker": "TEST"}
    membership = {"kind": "historical_exchange_membership", "security_type": "common_equity",
                  "biotech_eligible": True, "valid_from": "2020-02-01T00:00:00Z",
                  "valid_until": "2021-12-31T00:00:00Z"}
    listing = {"schema_version": "historical-listing-source-review-v1", "issuer": issuer,
               "reviewed_at": "2026-01-02T12:00:00Z", "membership": membership}
    archive = {"schema_version": "issuer-archive-window-review-v1", "issuer": issuer,
               "archive_complete": True, "body_review_complete": True, "reviewed_at": "2026-01-02T12:00:00Z",
               "proposed_window": {"start_date": "2020-12-21", "end_date": "2021-12-21"},
               "archive_years": [], "inventory": [], "body_reviews": []}
    for year, release_date in ((2020, "2020-12-21"), (2021, "2021-11-20")):
        entry = {"date": release_date, "title": "Clinical update", "url": f"https://example.test/{year}",
                 "archive_year": year, "archive_page": 1}
        page = {"page": 1, "entry_count": 1, "retrieved_at": "2026-01-01T12:00:00Z",
                **write_source(tmp_path, f"page{year}.json", entry)}
        archive["archive_years"].append({"year": year, "total_rows": 1, "total_pages": 1, "pages": [page]})
        archive["inventory"].append(entry)
        archive["body_reviews"].append({**entry, **write_source(tmp_path, f"body{year}.json", {"clinical": True}),
                                        "qualified_target_control_event": False, "censoring_event": False,
                                        "retrieved_at": "2026-01-01T12:00:00Z", "reviewed_at": "2026-01-02T12:00:00Z",
                                        "reviewer": "Test fixture", "review_reason": "Clinical trial update; no transaction described."})
    return tmp_path, archive, listing


def assemble(evidence):
    directory, archive, listing = evidence
    inputs = {"schema_version": "reviewed-control-inputs-v1", "records": [
        {"archive": write_source(directory, "archive.json", archive),
         "listing": write_source(directory, "listing.json", listing)}]}
    (directory / "inputs.json").write_text(json.dumps(inputs))
    return assemble_control_seed(directory / "inputs.json")


def test_reviewed_outcome_does_not_invent_training_eligibility_or_historical_availability(evidence):
    result = assemble(evidence)
    assert result["reviewed_negative_company_windows"] == 1
    assert result["eligible_feature_observations"] == 0
    assert result["training_allowed"] is False
    row = result["records"][0]
    assert row["available_at"] == row["reviewed_at"] == "2026-01-02T12:00:00+00:00"
    assert row["risk_set_eligible"] is None and row["features"] is None


def test_missing_boundary_body_cannot_be_counted_as_no_event(evidence):
    evidence[1]["body_reviews"].pop(0)
    with pytest.raises(ValueError, match="missing or duplicate full-body"):
        assemble(evidence)


@pytest.mark.parametrize("field", ["qualified_target_control_event", "censoring_event"])
@pytest.mark.parametrize("value", [True, None])
def test_positive_unknown_or_censored_window_is_not_a_negative(evidence, field, value):
    evidence[1]["body_reviews"][1][field] = value
    with pytest.raises(ValueError, match="unresolved"):
        assemble(evidence)


def test_listing_must_cover_the_full_outcome_window(evidence):
    evidence[2]["membership"]["valid_until"] = "2021-12-20T00:00:00Z"
    with pytest.raises(ValueError, match="listing evidence"):
        assemble(evidence)


def test_missing_archive_page_rejected_even_when_review_list_is_complete(evidence):
    evidence[1]["archive_years"][1]["total_pages"] = 2
    with pytest.raises(ValueError, match="pagination gap"):
        assemble(evidence)


def test_raw_source_corruption_is_not_hidden_by_resealed_review(evidence):
    (evidence[0] / "body2021.json").write_text("changed original source")
    with pytest.raises(ValueError, match="source hash mismatch"):
        assemble(evidence)


def test_same_named_different_issuer_cannot_inherit_listing(evidence):
    evidence[2]["issuer"] = {"cik": 456, "ticker": "TEST"}
    with pytest.raises(ValueError, match="issuer mismatch"):
        assemble(evidence)


def test_duplicate_control_is_not_counted_twice(evidence):
    assemble(evidence)
    path = evidence[0] / "inputs.json"
    data = json.loads(path.read_bytes())
    data["records"] *= 2
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="duplicate control window"):
        assemble_control_seed(path)


def test_review_cannot_predate_the_outcome_window(evidence):
    evidence[1]["reviewed_at"] = "2020-01-02T12:00:00Z"
    with pytest.raises(ValueError, match="outcome maturity"):
        assemble(evidence)


def test_future_page_retrieval_cannot_be_ignored(evidence):
    evidence[1]["archive_years"][0]["pages"][0]["retrieved_at"] = "2099-01-01T12:00:00Z"
    with pytest.raises(ValueError, match="page retrieval"):
        assemble(evidence)


def test_declared_inventory_must_match_reported_archive_totals(evidence):
    evidence[1]["archive_years"][0]["pages"][0]["reported_pager"] = {"page": 1, "total_rows": 2, "total_pages": 1}
    with pytest.raises(ValueError, match="pagination disagrees"):
        assemble(evidence)
