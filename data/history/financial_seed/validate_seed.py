"""Validate the hand-reviewed financial seed without network or model fitting."""

from datetime import date
import csv
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def checked_file(relative: str, expected: str) -> Path:
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT), f"path escapes seed: {relative}"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"hash mismatch: {relative}"
    return path


def validate_review_receipt(record: dict) -> None:
    receipt = json.loads(checked_file(record["evidence_relative_path"], record["evidence_sha256"]).read_text())
    assert receipt["schema_version"] == "manual-financial-evidence-v2"
    bound_fields = (
        "record_id", "candidate_id", "cik", "ticker", "period_start", "period_end",
        "filed_date", "publication_date", "publication_timestamp_precision", "published_at",
        "filing_form", "fiscal_year", "period_type", "publication_date_lower", "publication_date_upper",
        "source_url", "original_sec_url", "source_relative_path", "source_sha256",
        "raw_bytes_archived", "retrieved_at", "publication_evidence", "facts",
    )
    for field in bound_fields:
        assert field in receipt and receipt[field] == record[field], f"receipt mismatch: {record['record_id']} {field}"
    previous = json.loads(checked_file(receipt["previous_receipt_relative_path"], receipt["previous_receipt_sha256"]).read_text())
    assert previous["schema_version"] == "manual-financial-evidence-v1"
    for field, value in previous.items():
        if field != "schema_version":
            assert receipt[field] == value, f"v1 evidence changed: {record['record_id']} {field}"


def main() -> None:
    manifest = json.loads((ROOT / "financial_records.json").read_text())
    reviews = {row["candidate_id"]: row for row in csv.DictReader(
        (ROOT.parent / "reviews_2018_2021.csv").open())}
    identifiers = set()
    pdf_fact_count = 0
    for record in manifest["records"]:
        assert record["record_id"] not in identifiers
        identifiers.add(record["record_id"])
        review = reviews[record["candidate_id"]]
        assert record["cik"] == review["reviewed_target_cik"]
        assert record["ticker"] == review["reviewed_target_ticker"]
        assert record["announcement_date"] == review["announcement_date"]
        assert date.fromisoformat(record["period_start"]) < date.fromisoformat(record["period_end"])
        assert record["period_end"] < record["filed_date"] < record["announcement_date"]
        assert record["publication_date"] == record["filed_date"]
        assert record["publication_timestamp_precision"] == "date"
        assert record["published_at"] is None
        assert record["publication_evidence"]["url"].startswith("https://")
        assert record["publication_evidence"]["evidence_paraphrase"]
        validate_review_receipt(record)
        page_map = {}
        if record["raw_bytes_archived"]:
            checked_file(record["source_relative_path"], record["source_sha256"])
            suffix = "financial_pages" if record["ticker"] == "MNTA" else "selected_pages"
            pages = json.loads((ROOT / f"{record['ticker']}_{record['fiscal_year']}_{suffix}.json").read_text())
            page_map = {item["pdf_page"]: item["text"].replace("\xa0", " ") for item in pages}
        else:
            assert record["source_relative_path"] is None
            assert record["source_sha256"] is None
        for name, fact in record["facts"].items():
            assert fact["reported"] is True
            assert fact["source_unit"] == "USD thousands" and fact["unit_multiplier"] == 1000
            assert fact["reported_value"] * 1000 == fact["value_usd"]
            assert fact["period_end"] == record["period_end"]
            assert fact["printed_page"] is not None or fact["pdf_page"] is not None
            if name in ("cash_usd", "assets_usd"):
                assert fact["period_start"] is None and fact["period_type"] == "instant"
            else:
                assert fact["period_start"] == record["period_start"] and fact["period_type"] == "annual"
            if page_map:
                text = page_map[fact["pdf_page"]]
                label = fact["reported_label"].lower()
                lines = [line for line in text.splitlines() if label in line.lower()]
                assert lines, f"reported label absent: {record['ticker']} {name}"
                number = f"{abs(fact['reported_value']):,}"
                assert any(number in line for line in lines), f"table value absent: {record['ticker']} {name}"
                if fact["reported_value"] < 0:
                    assert any(re.search(r"\(\s*" + re.escape(number) + r"\s*\)", line) for line in lines)
                assert "thousands" in text.lower()
                pdf_fact_count += 1
    assert manifest["model_training_eligible"] is False
    assert manifest["negative_control_count"] == 0
    print(json.dumps({"companies": len(identifiers), "reported_facts": sum(len(r["facts"]) for r in manifest["records"]),
                      "pdf_table_facts_checked": pdf_fact_count, "source_and_evidence_hashes": "passed",
                      "v2_record_bindings_and_preserved_v1_receipts": "passed",
                      "identity_period_unit_publication_checks": "passed", "model_fitted": False}))


if __name__ == "__main__":
    main()
