from copy import deepcopy

import pytest

from src.research.adjudication import freeze_reviews, validate_reviews


@pytest.fixture
def reviewed_deal():
    candidate = {"candidate_id": "fixture", "sec_signal_date": "2020-02-02"}
    review = {
        "candidate_id": "fixture", "decision": "include", "reviewer": "test reviewer",
        "reviewed_at": "2021-01-01T12:00:00+00:00", "review_notes": "Synthetic test fixture",
        "review_primary_source_url": "https://www.sec.gov/Archives/test-fixture",
        "reviewed_target_name": "Fixture", "reviewed_target_cik": "123",
        "acquirer_name": "Buyer", "first_public_announcement_at": "2020-02-01T08:00:00-05:00",
        "transaction_structure": "cash", "transaction_status": "terminated",
        "change_of_control_percent": "100",
    }
    return candidate, review


def test_failed_deal_is_positive_announcement_but_training_stays_gated(reviewed_deal):
    candidate, review = reviewed_deal
    result = validate_reviews([candidate], [review])
    assert result["reviewed_positive_count"] == 1
    assert result["labels"][0]["announced_at"] == "2020-02-01T13:00:00+00:00"
    assert result["training_allowed"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("change_of_control_percent", "50"), ("change_of_control_percent", "NaN"),
    ("transaction_structure", "license"), ("reviewer", ""),
    ("first_public_announcement_at", "2020-02-01"),
    ("first_public_announcement_at", "2020-03-01T08:00:00Z"),
    ("review_primary_source_url", "file:///tmp/test"),
])
def test_incomplete_or_non_control_reviews_rejected(reviewed_deal, field, value):
    candidate, review = reviewed_deal
    review[field] = value
    with pytest.raises(ValueError):
        validate_reviews([candidate], [review])


def test_duplicate_deals_and_unknown_candidates_rejected(reviewed_deal):
    candidate, review = reviewed_deal
    other = deepcopy(review)
    other["candidate_id"] = "second"
    with pytest.raises(ValueError, match="unknown candidate"):
        validate_reviews([candidate], [other])
    with pytest.raises(ValueError, match="duplicate acquisition"):
        validate_reviews([candidate, {**candidate, "candidate_id": "second"}], [review, other])
    other["first_public_announcement_at"] = "2020-02-01T14:00:00Z"
    with pytest.raises(ValueError, match="duplicate acquisition"):
        validate_reviews([candidate, {**candidate, "candidate_id": "second"}], [review, other])


def test_pending_is_not_negative_and_empty_freeze_rejected(tmp_path, reviewed_deal):
    candidate, _ = reviewed_deal
    result = validate_reviews([candidate], [{"candidate_id": "fixture", "decision": ""}])
    assert result["pending_count"] == 1
    assert result["labels"] == []
    with pytest.raises(ValueError, match="no reviewed positive"):
        freeze_reviews(result, tmp_path, {})


def test_frozen_reviews_are_idempotent_and_detect_tampering(tmp_path, reviewed_deal):
    candidate, review = reviewed_deal
    result = validate_reviews([candidate], [review])
    path = freeze_reviews(result, tmp_path, {"candidates": "test"})
    assert freeze_reviews(result, tmp_path, {"candidates": "test"}) == path
    path.write_text("tampered")
    with pytest.raises(ValueError, match="modified"):
        freeze_reviews(result, tmp_path, {"candidates": "test"})


def test_date_only_source_never_fabricates_precise_announcement(reviewed_deal):
    candidate, review = reviewed_deal
    review.update(first_public_announcement_at="", announcement_date="2020-02-01", timestamp_precision="date")
    label = validate_reviews([candidate], [review])["labels"][0]
    assert label["announced_at"] is None
    assert label["announcement_lower_at"] == "2020-01-31T10:00:00+00:00"
    assert label["announcement_upper_at"] == "2020-02-02T12:00:00+00:00"
    assert label["event_id"] == "123:2020-02-01"
    review["reviewed_at"] = "2020-02-02T01:00:00+00:00"
    with pytest.raises(ValueError, match="after review"):
        validate_reviews([candidate], [review])


def test_source_date_cannot_contradict_exact_timestamp(reviewed_deal):
    candidate, review = reviewed_deal
    review.update(announcement_date="2020-01-01", timestamp_precision="timestamp")
    with pytest.raises(ValueError, match="contradicts timestamp"):
        validate_reviews([candidate], [review])
