from datetime import date
import json
from pathlib import Path

import pytest

from src.research.execution_markers import (
    HistoricalExecutionMarker,
    score_company_execution,
)


def marker(**overrides):
    row = {
        "marker_id": "marker-1",
        "company_name": "Historical Bio",
        "historical_ticker": "HIST",
        "polarity": "downside",
        "archetype": "regulatory_failure_watch",
        "anchor_date": "2021-01-01",
        "anchor_tags": ["regulatory_failure", "statistical_governance"],
        "anchor_source_url": "https://www.fda.gov/example",
        "anchor_evidence_summary": "Regulatory evidence observable at anchor.",
        "outcome_date": "2022-01-01",
        "outcome_class": "bankruptcy_and_asset_sale",
        "outcome_source_url": "https://www.sec.gov/example",
        "outcome_summary": "A later outcome used only for validation.",
    }
    row.update(overrides)
    return HistoricalExecutionMarker.from_dict(row)


def market(ticker="EXMP", **overrides):
    row = {
        "ticker": ticker,
        "company_name": f"{ticker} Bio",
        "portfolio_score": 80,
        "data_confidence": 60,
        "approved_asset_count": 1,
        "clinical_asset_count": 3,
        "late_stage_asset_count": 2,
    }
    row.update(overrides)
    return row


def test_outcome_labels_cannot_leak_into_anchor_features():
    with pytest.raises(ValueError, match="leaked"):
        marker(anchor_tags=["regulatory_failure", "bankruptcy"])


def test_scorecard_preserves_upside_downside_and_coverage_axes():
    rows = score_company_execution(
        [market("CAPR"), market("GOOD")],
        [
            {
                "ticker": "CAPR",
                "diligence_score": 66,
                "categories": '["statistical_governance"]',
            }
        ],
        [
            {
                "ticker": "CAPR",
                "execution_risk_score": 38,
                "leadership_risk_score": 28,
                "pending_inspection_count": 1,
                "categories": '["regulatory_delivery"]',
            }
        ],
        [marker()],
    )
    by_ticker = {row.ticker: row for row in rows}
    assert by_ticker["CAPR"].execution_downside_score == 66
    assert by_ticker["CAPR"].evidence_coverage == "company_specific_evidence"
    assert by_ticker["CAPR"].closest_marker_id == "marker-1"
    assert by_ticker["CAPR"].marker_similarity > 0
    assert by_ticker["GOOD"].delivery_upside_score > 0
    assert by_ticker["GOOD"].execution_downside_score == 0
    assert by_ticker["GOOD"].execution_outlook == "upside_proxy_risk_unscreened"
    assert "unscreened" in by_ticker["GOOD"].evidence_coverage


def test_later_marker_outcome_does_not_change_similarity():
    current = market(
        approved_asset_count=0,
        late_stage_asset_count=0,
        portfolio_score=0,
    )
    execution = [
        {
            "ticker": "EXMP",
            "execution_risk_score": 40,
            "leadership_risk_score": 20,
            "pending_inspection_count": 0,
            "categories": '["regulatory_delivery"]',
        }
    ]
    first = score_company_execution(
        [current],
        [],
        execution,
        [marker(outcome_class="bankruptcy_and_asset_sale")],
    )[0]
    second = score_company_execution(
        [current],
        [],
        execution,
        [marker(outcome_class="successful_relaunch")],
    )[0]
    assert first.marker_similarity == second.marker_similarity
    assert first.execution_balance_score == second.execution_balance_score


def test_future_marker_anchor_is_excluded_from_point_in_time_match():
    row = score_company_execution(
        [market()],
        [],
        [
            {
                "ticker": "EXMP",
                "execution_risk_score": 40,
                "leadership_risk_score": 20,
                "pending_inspection_count": 0,
                "categories": (
                    '["regulatory_delivery", "statistical_governance"]'
                ),
            }
        ],
        [marker(anchor_date="2030-01-01", outcome_date="2031-01-01")],
        as_of=date(2029, 12, 31),
    )[0]
    assert row.closest_marker_id == ""
    assert row.marker_similarity == 0


def test_exact_company_marker_contributes_evidence_not_later_outcome():
    negative = marker(
        historical_ticker="EXMP",
        anchor_tags=[
            "missed_prespecified_endpoint",
            "confirmatory_failure",
            "product_withdrawal",
        ],
    )
    row = score_company_execution(
        [market(approved_asset_count=0)],
        [],
        [],
        [negative],
    )[0]
    assert row.negative_marker_evidence_score == 65
    assert row.execution_downside_score == 65
    assert row.evidence_coverage == "company_specific_evidence"
    assert row.active_company_marker_ids == ["marker-1"]


def test_seed_marker_library_is_valid_and_balanced():
    path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "execution_markers"
        / "markers.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    markers = [
        HistoricalExecutionMarker.from_dict(row)
        for row in payload["markers"]
    ]
    assert len(markers) == 7
    assert {marker.polarity for marker in markers} == {
        "downside",
        "upside",
    }
    capricor = next(
        marker
        for marker in markers
        if marker.historical_ticker == "CAPR"
    )
    assert capricor.outcome_class == "pending"
    assert capricor.outcome_date == ""
