"""Financial unit/timing checks use synthetic fixtures, never training evidence."""

import hashlib
import json
from copy import deepcopy

import pytest

from src.research.financial_seed import assemble_financial_seed


@pytest.fixture
def source_files(tmp_path):
    payload = b"synthetic annual-report fixture"
    (tmp_path / "report.pdf").write_bytes(payload)
    facts = {}
    for name, value in (("cash_usd", 400), ("assets_usd", 800),
                        ("annual_operating_cashflow_usd", -120), ("annual_rd_usd", 90)):
        facts[name] = {"reported": True, "reported_value": value, "source_unit": "USD thousands",
                       "unit_multiplier": 1000, "value_usd": value * 1000,
                       "period_start": "2019-01-01" if name.startswith("annual_") else None,
                       "period_end": "2019-12-31", "statement": "Synthetic statement", "printed_page": "42",
                       "reported_label": name}
    row = {"candidate_id": "fixture", "cik": "123", "ticker": "SYNTH",
           "announcement_date": "2020-06-01", "filing_form": "10-K", "period_type": "annual",
           "period_start": "2019-01-01", "period_end": "2019-12-31", "filed_date": "2020-02-28",
           "publication_date": "2020-02-28", "publication_timestamp_precision": "date", "published_at": None,
           "publication_evidence": {"url": "https://example.org/synthetic", "evidence_paraphrase": "Synthetic date evidence"},
           "source_relative_path": "report.pdf", "source_sha256": hashlib.sha256(payload).hexdigest(),
           "source_url": "https://example.org/synthetic", "raw_bytes_archived": True, "facts": facts}
    labels = {"labels": [{"candidate_id": "fixture", "target_cik": 123, "announcement_date": "2020-06-01",
                          "announced_at": None, "timestamp_precision": "date"}]}
    review_bytes = json.dumps({"schema_version": "manual-financial-evidence-v2", **row}).encode()
    (tmp_path / "review.json").write_bytes(review_bytes)
    row.update(evidence_relative_path="review.json", evidence_sha256=hashlib.sha256(review_bytes).hexdigest())
    records_path, labels_path = tmp_path / "records.json", tmp_path / "labels.json"
    records_path.write_text(json.dumps({"schema_version": "manual-preannouncement-financials-v1", "records": [row]}))
    labels_path.write_text(json.dumps(labels))
    return records_path, labels_path, row


def write_row(path, row):
    path.write_text(json.dumps({"schema_version": "manual-preannouncement-financials-v1", "records": [row]}))


def update_review(path, row):
    payload = json.dumps({"schema_version": "manual-financial-evidence-v2",
                          **{key: value for key, value in row.items() if key not in ("evidence_relative_path", "evidence_sha256")}}).encode()
    (path.parent / "review.json").write_bytes(payload)
    row["evidence_sha256"] = hashlib.sha256(payload).hexdigest()


def test_real_amount_units_and_conservative_publication_time(source_files):
    records, labels, _ = source_files
    result = assemble_financial_seed(records, labels)
    row = result["records"][0]
    assert row["features"]["cash_usd"] == 400000
    assert row["features"]["annual_cash_burn_usd"] == 120000
    assert row["feature_max_available_at"] == "2020-02-29T12:00:00+00:00"
    assert result["training_allowed"] is False
    assert result["eligible_training_observations"] == 0


def test_missing_operating_cashflow_is_not_zero_burn(source_files):
    records, labels, row = source_files
    row["facts"].pop("annual_operating_cashflow_usd")
    update_review(records, row)
    write_row(records, row)
    assert assemble_financial_seed(records, labels)["records"][0]["features"]["annual_cash_burn_usd"] is None


def test_positive_operating_cashflow_means_observed_zero_burn(source_files):
    records, labels, row = source_files
    row["facts"]["annual_operating_cashflow_usd"].update(reported_value=120, value_usd=120000)
    update_review(records, row)
    write_row(records, row)
    assert assemble_financial_seed(records, labels)["records"][0]["features"]["annual_cash_burn_usd"] == 0


@pytest.mark.parametrize("mutation,error", [
    (lambda row: row.update(cik="124"), "issuer differs"),
    (lambda row: row.update(publication_date="2020-06-01"), "not available before"),
    (lambda row: row["facts"]["cash_usd"].update(unit_multiplier=1), "units and conversion"),
    (lambda row: row["facts"]["cash_usd"].update(value_usd=400), "conversion disagrees"),
    (lambda row: row["facts"]["annual_rd_usd"].update(period_start="2019-04-01"), "annual flow/instant"),
    (lambda row: row.update(source_sha256="a" * 64), "SHA-256 mismatch"),
    (lambda row: row.update(source_relative_path="../escape.pdf"), "missing or outside"),
    (lambda row: row["facts"]["assets_usd"].update(value_usd=float("nan")), "finite number"),
])
def test_invalid_financial_evidence_blocks_the_entire_assembly(source_files, mutation, error):
    records, labels, row = source_files
    altered = deepcopy(row)
    mutation(altered)
    write_row(records, altered)
    with pytest.raises(ValueError, match=error):
        assemble_financial_seed(records, labels)


def test_consistent_unit_math_cannot_overwrite_reviewed_amounts(source_files):
    records, labels, row = source_files
    row["facts"]["cash_usd"].update(reported_value=9000, value_usd=9000000)
    write_row(records, row)
    with pytest.raises(ValueError, match="differs from dated review receipt: facts"):
        assemble_financial_seed(records, labels)


def test_exact_publication_timestamp_cannot_bypass_source_date(source_files):
    records, labels, row = source_files
    row.update(publication_timestamp_precision="timestamp", published_at="2017-01-01T00:00:00Z")
    write_row(records, row)
    with pytest.raises(ValueError, match="date contradicts timestamp"):
        assemble_financial_seed(records, labels)
