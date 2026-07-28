from src.research.strategic_overlay import build_strategic_diligence_matrix


def market(ticker, score):
    return {
        "ticker": ticker,
        "company_name": f"{ticker} Bio",
        "research_score": score,
        "portfolio_score": 70,
        "acquirability_score": 90,
        "data_confidence": 60,
    }


def integrity(ticker, score):
    return {
        "ticker": ticker,
        "diligence_score": score,
        "confirmed_misconduct_count": 0,
        "categories": '["statistical_governance"]',
    }


def execution(ticker, score, leadership=0):
    return {
        "ticker": ticker,
        "execution_risk_score": score,
        "leadership_risk_score": leadership,
        "confirmed_individual_finding_count": 0,
        "primary_risk_drivers": '["formal regulatory failure"]',
    }


def test_matrix_keeps_ma_and_risk_axes_separate():
    rows = build_strategic_diligence_matrix(
        [
            market("CLEAN", 85),
            market("RISKY", 82),
            market("FAIL", 30),
            market("UNKNOWN", 80),
        ],
        [integrity("CLEAN", 10), integrity("RISKY", 65), integrity("FAIL", 70)],
        [execution("CLEAN", 5), execution("RISKY", 55, 35), execution("FAIL", 60, 40)],
    )
    by_ticker = {row.ticker: row for row in rows}
    assert by_ticker["CLEAN"].strategic_archetype == "strategic_target"
    assert by_ticker["RISKY"].strategic_archetype == "distressed_or_structured_target"
    assert by_ticker["FAIL"].strategic_archetype == "failure_watch"
    assert by_ticker["UNKNOWN"].strategic_archetype == "ma_candidate_risk_unscreened"
    assert by_ticker["RISKY"].ma_research_score == 82
    assert by_ticker["RISKY"].combined_diligence_risk == 65
