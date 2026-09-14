"""Regression coverage for eligibility, heuristic semantics, and ranking metrics."""

import asyncio
import json
import sqlite3

import pytest

from scripts.backtest import build_known_deal_diagnostic, run_backtest
from scripts.generate_watchlist import build_watchlist_entry
from src.research.metrics import RankedObservation, average_precision, evaluate_rare_event_ranking
from src.research.strategic_overlay import build_strategic_diligence_matrix
from src.scoring.acquirer_matcher import AcquirerMatch, AcquirerType, TherapeuticAlignment


@pytest.mark.parametrize("eligibility", [False, "False", "false", 0, "0", None, "", "unknown"])
def test_excluded_companies_keep_diligence_but_never_receive_candidate_rank(eligibility):
    market_rows = [
        {"ticker": "EXCLUDED", "research_score": 99, "risk_set_eligible": eligibility,
         "risk_set_exclusion_reason": "recent transaction filing"},
        {"ticker": "ELIGIBLE", "research_score": 75, "risk_set_eligible": "True"},
        {"ticker": "SECOND", "research_score": 70, "risk_set_eligible": True},
    ]
    rows = build_strategic_diligence_matrix(
        market_rows, [], [{"ticker": "EXCLUDED", "execution_risk_score": 90}],
    )
    assert [row.ticker for row in rows] == ["ELIGIBLE", "SECOND", "EXCLUDED"]
    assert [row.ma_rank for row in rows] == [1, 2, None]
    excluded = rows[-1].to_dict()
    assert excluded["risk_set_eligible"] is False
    assert excluded["risk_set_exclusion_reason"] == "recent transaction filing"
    assert excluded["ma_band"] == "excluded"
    assert excluded["strategic_archetype"] == "excluded_from_prediction_risk_set"
    assert excluded["execution_risk_score"] == 90
    assert "Retained for diligence" in excluded["suggested_transaction_structure"]


def test_missing_or_contradictory_eligibility_fails_closed():
    rows = build_strategic_diligence_matrix([
        {"ticker": "MISSING", "research_score": 99},
        {"ticker": "CONFLICT", "research_score": 99, "risk_set_eligible": True,
         "risk_set_exclusion_reason": "transaction already announced"},
    ], [], [])
    assert all(not row.risk_set_eligible and row.ma_rank is None for row in rows)
    assert all(row.risk_set_exclusion_reason for row in rows)


def test_strategic_csv_roundtrip_retains_exclusions(tmp_path):
    from scripts.build_strategic_matrix import read_csv, write_csv

    rows = build_strategic_diligence_matrix([
        {"ticker": "OGN", "research_score": "77.06", "risk_set_eligible": "False",
         "risk_set_exclusion_reason": "recent DEFM14A filed 2026-06-17"},
    ], [], [])
    output = tmp_path / "matrix.csv"
    write_csv(output, (row.to_dict() for row in rows))
    [persisted] = read_csv(output)
    assert persisted["risk_set_eligible"] == "False"
    assert persisted["ma_rank"] == ""
    assert persisted["risk_set_exclusion_reason"] == "recent DEFM14A filed 2026-06-17"


def test_average_precision_is_invariant_to_ids_inside_equal_score_group():
    for labels in [(True, False), (False, True)]:
        observations = [RankedObservation("a", 50, labels[0]), RankedObservation("b", 50, labels[1])]
        assert average_precision(observations) == 0.5
        assert average_precision(reversed(observations)) == 0.5
    metrics = evaluate_rare_event_ranking(observations, cutoffs=(1,))
    assert metrics["average_precision_tie_policy"] == "group_equal_score_thresholds"
    assert metrics["top_k_tie_policy"] == "observation_id_ascending"


def test_average_precision_weights_recall_changes_at_each_threshold():
    observations = [
        RankedObservation("first", 100, True),
        RankedObservation("second", 50, True),
        RankedObservation("third", 50, False),
        RankedObservation("last", 0, False),
    ]
    assert average_precision(observations) == pytest.approx((1 + 2 / 3) / 2)
    assert average_precision([RankedObservation("negative", 10, False)]) == 0.0


@pytest.mark.parametrize("score", [5, 55, 65, 75, 85, 100])
def test_acquirer_match_never_converts_fit_score_to_probability(score):
    match = AcquirerMatch(
        acquirer_id="example", acquirer_name="Example Pharma",
        acquirer_type=AcquirerType.BIG_PHARMA, match_score=score,
        therapeutic_alignment=TherapeuticAlignment([], [], []),
    )
    serialized = json.loads(json.dumps(match.to_dict()))
    assert match.deal_likelihood is None
    assert serialized["deal_likelihood"] is None
    assert serialized["match_score"] == score
    assert serialized["probability_status"] == "unavailable_unvalidated_model"
    assert "heuristic" in serialized["score_semantics"]


def watchlist_company():
    return {
        "id": "example", "ticker": "EXAMPLE", "name": "Example Bio",
        "total_score": 95, "market_cap_usd": 1_000_000_000,
        "cash_position_usd": 100_000_000, "runway_quarters": 4,
        "therapeutic_areas": '["oncology"]', "pipeline_score": 95,
        "financial_score": 95, "strategic_fit_score": 95,
        "regulatory_score": 95, "patent_score": 95, "insider_score": 50,
        "key_drivers": "[]",
    }


def test_legacy_watchlist_preserves_score_without_probability():
    entry = build_watchlist_entry(watchlist_company(), [], 1)
    assert entry["ma_score"] == 95
    assert entry["deal_probability_12mo"] is None
    assert entry["probability_status"] == "unavailable_unvalidated_model"
    assert "heuristic" in entry["score_semantics"]


def test_known_deal_diagnostic_is_explicitly_not_predictive_validation(tmp_path):
    diagnostic = build_known_deal_diagnostic()
    assert diagnostic["total_deals"] == 11
    assert diagnostic["negative_controls"] == 0
    assert diagnostic["validation_status"] == "unvalidated"
    assert diagnostic["ranking_metrics"] is None
    assert diagnostic["probability_metrics"] is None
    assert "verdict" not in diagnostic
    assert "accuracy" not in diagnostic
    assert "pct_above_50" not in diagnostic
    output_path = tmp_path / "known_deals.json"
    asyncio.run(run_backtest(output_path))
    persisted = json.loads(output_path.read_text())
    assert persisted["evaluation_type"] == "known_positive_case_diagnostic"
    assert persisted["results"] == diagnostic["results"]


def test_legacy_watchlist_json_and_markdown_do_not_publish_fake_accuracy(tmp_path, monkeypatch):
    pytest.importorskip("aiosqlite", reason="optional legacy database integration")
    from scripts import generate_watchlist

    database = tmp_path / "legacy.db"
    company = watchlist_company()
    score_keys = [key for key in company if key.endswith("_score") or key == "key_drivers"]
    company_keys = [key for key in company if key not in score_keys]
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE companies (" + ",".join(company_keys) + ")")
        connection.execute("INSERT INTO companies VALUES (" + ",".join("?" for _ in company_keys) + ")",
                           [company[key] for key in company_keys])
        connection.execute("CREATE TABLE ma_scores (company_id," + ",".join(score_keys) + ")")
        connection.execute("INSERT INTO ma_scores VALUES (" + ",".join("?" for _ in range(len(score_keys) + 1)) + ")",
                           [company["id"], *[company[key] for key in score_keys]])
        connection.execute("CREATE TABLE drug_candidates (company_id, deleted_at)")
    monkeypatch.setattr(generate_watchlist, "DB_PATH", database)
    monkeypatch.setattr(generate_watchlist, "OUTPUT_DIR", tmp_path)
    asyncio.run(generate_watchlist.generate_watchlist())
    report = json.loads((tmp_path / "watchlist_latest.json").read_text())
    markdown = (tmp_path / "watchlist_latest.md").read_text()
    assert report["watchlist"][0]["deal_probability_12mo"] is None
    assert "backtest_accuracy" not in report
    assert "**Backtest:**" not in markdown
    assert "**12-Month Deal Probability:** Unavailable" in markdown
