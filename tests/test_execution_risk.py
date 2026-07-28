import pytest

from src.research.execution_risk import (
    ExecutionRiskSignal,
    evaluate_execution_risk,
)


def signal(**overrides):
    row = {
        "signal_id": "example-1",
        "company_name": "Example Bio, Inc.",
        "ticker": "EXMP",
        "event_date": "2026-07-28",
        "category": "regulatory_delivery",
        "evidence_status": "formal_failure",
        "severity": 5,
        "confidence": 1.0,
        "scope": "leadership_team",
        "attribution_basis": "role_accountability",
        "responsible_roles": ["executive leadership", "regulatory affairs"],
        "named_people": [],
        "source_organization": "FDA",
        "source_title": "Complete Response Letter",
        "source_url": "https://www.fda.gov/example",
        "summary": "The regulator issued a formal non-approval action.",
    }
    row.update(overrides)
    return ExecutionRiskSignal.from_dict(row)


def test_team_accountability_is_not_individual_finding():
    item = signal()
    assert item.leadership_points < item.weighted_points
    assert item.confirmed_individual_finding is False
    result = evaluate_execution_risk([item])[0]
    assert result.formal_failure_count == 1
    assert result.confirmed_individual_finding_count == 0
    assert "not a finding" in result.interpretation


def test_named_person_requires_official_enforcement_finding():
    with pytest.raises(ValueError, match="named people"):
        signal(named_people=["Person A"])

    item = signal(
        scope="named_executive",
        attribution_basis="official_individual_finding",
        evidence_status="enforcement_finding",
        named_people=["Person A"],
    )
    assert item.confirmed_individual_finding is True
    assert item.leadership_points == item.weighted_points


def test_company_scope_cannot_imply_person_attribution():
    with pytest.raises(ValueError, match="company scope"):
        signal(scope="company", attribution_basis="role_accountability")
