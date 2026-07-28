import pytest

from src.research.study_integrity import (
    StudyIntegritySignal,
    evaluate_study_integrity,
    validate_signal_ledger,
)


def signal(**overrides):
    row = {
        "signal_id": "example-1",
        "company_name": "Example Bio, Inc.",
        "ticker": "EXMP",
        "product_name": "EX-101",
        "study_ids": ["NCT00000001"],
        "category": "endpoint_or_sap_change",
        "evidence_status": "regulatory_concern",
        "severity": 5,
        "confidence": 1.0,
        "source_class": "regulator_review",
        "source_organization": "FDA",
        "source_title": "FDA review",
        "source_url": "https://www.fda.gov/example",
        "source_date": "2026-07-28",
        "summary": "The regulator identified a material concern.",
    }
    row.update(overrides)
    return StudyIntegritySignal.from_dict(row)


def test_regulatory_concern_is_not_confirmed_misconduct():
    item = signal()
    assert item.confirmed_misconduct is False
    result = evaluate_study_integrity([item])[0]
    assert result.confirmed_misconduct_count == 0
    assert result.diligence_score > 0
    assert "not a finding of fraud" in result.interpretation


def test_confirmed_misconduct_requires_qualified_authority():
    item = signal(
        evidence_status="confirmed_research_misconduct",
        source_class="research_integrity_finding",
    )
    assert item.confirmed_misconduct is True

    unqualified = signal(
        signal_id="example-2",
        evidence_status="confirmed_research_misconduct",
        source_class="publication_record",
    )
    assert unqualified.confirmed_misconduct is False


def test_duplicate_category_is_not_double_counted():
    first = signal()
    duplicate = signal(
        signal_id="example-2",
        severity=3,
        source_url="https://www.fda.gov/example-2",
    )
    evaluation = evaluate_study_integrity([first, duplicate])[0]
    assert evaluation.diligence_score == first.weighted_points
    assert evaluation.signal_count == 2


def test_signal_validation_and_duplicate_ids():
    with pytest.raises(ValueError, match="severity"):
        signal(severity=6)
    with pytest.raises(ValueError, match="Duplicate signal_id"):
        validate_signal_ledger([signal(), signal()])
