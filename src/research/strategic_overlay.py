"""Join M&A attractiveness with integrity and execution-risk evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(slots=True)
class StrategicDiligenceRow:
    ticker: str
    company_name: str
    ma_research_score: float
    ma_rank: int
    ma_band: str
    portfolio_score: float
    acquirability_score: float
    market_data_confidence: float
    integrity_diligence_score: float
    execution_risk_score: float
    leadership_risk_score: float
    delivery_upside_score: float
    positive_marker_evidence_score: float
    negative_marker_evidence_score: float
    execution_balance_score: float
    execution_outlook: str
    evidence_coverage_score: float
    closest_marker_id: str
    closest_marker_polarity: str
    marker_similarity: float
    combined_diligence_risk: float
    risk_coverage: str
    confirmed_misconduct_count: int
    confirmed_individual_finding_count: int
    strategic_archetype: str
    suggested_transaction_structure: str
    decision_rule: str
    primary_risk_drivers: list[str]
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(row: dict[str, Any] | None, key: str) -> float:
    if not row:
        return 0.0
    value = row.get(key)
    return float(value) if value not in (None, "") else 0.0


def _integer(row: dict[str, Any] | None, key: str) -> int:
    if not row:
        return 0
    value = row.get(key)
    return int(value) if value not in (None, "") else 0


def _list_value(row: dict[str, Any] | None, key: str) -> list[str]:
    if not row:
        return []
    value = row.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _ma_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 50:
        return "moderate"
    return "low"


def _classify(
    ma_score: float, risk_score: float, leadership_score: float, has_risk_evidence: bool
) -> tuple[str, str, str]:
    high_ma = ma_score >= 70
    moderate_ma = ma_score >= 50
    high_risk = risk_score >= 50
    elevated_risk = risk_score >= 25

    if high_ma and not has_risk_evidence:
        return (
            "ma_candidate_risk_unscreened",
            "No structure recommendation until execution-risk coverage is complete.",
            "High M&A research rank; current risk collectors have no company-specific evidence.",
        )
    if high_ma and high_risk:
        return (
            "distressed_or_structured_target",
            "Prefer asset purchase, option, milestone, or CVR structure over clean whole-company underwriting.",
            "High M&A attractiveness and high diligence risk.",
        )
    if high_ma and elevated_risk:
        return (
            "diligence_sensitive_target",
            "Use staged diligence, contingent value, representations, and regulatory milestones.",
            "High M&A attractiveness with elevated execution or integrity risk.",
        )
    if high_ma:
        return (
            "strategic_target",
            "Whole-company acquisition can advance to full strategic and valuation diligence.",
            "High M&A attractiveness with reviewed risk evidence below escalation thresholds.",
        )
    if moderate_ma and high_risk:
        return (
            "distressed_asset_watch",
            "Monitor for asset sale, licensing, restructuring, or strategic alternatives.",
            "Moderate M&A attractiveness but high diligence risk.",
        )
    if high_risk:
        return (
            "failure_watch",
            "Avoid clean-company assumptions; monitor financing, governance, regulatory, and asset-sale catalysts.",
            "Low M&A attractiveness and high documented diligence risk.",
        )
    if leadership_score >= 25:
        return (
            "leadership_execution_watch",
            "Require leadership track-record and succession diligence before underwriting.",
            "Elevated leadership role-accountability evidence.",
        )
    return (
        "neutral_monitor",
        "No transaction structure recommendation.",
        "Neither axis currently crosses a review threshold.",
    )


def build_strategic_diligence_matrix(
    market_rows: Iterable[dict[str, Any]],
    integrity_rows: Iterable[dict[str, Any]],
    execution_rows: Iterable[dict[str, Any]],
    scorecard_rows: Iterable[dict[str, Any]] = (),
) -> list[StrategicDiligenceRow]:
    market = list(market_rows)
    integrity_by_ticker = {
        str(row.get("ticker", "")).upper(): row for row in integrity_rows
    }
    execution_by_ticker = {
        str(row.get("ticker", "")).upper(): row for row in execution_rows
    }
    scorecard_by_ticker = {
        str(row.get("ticker", "")).upper(): row for row in scorecard_rows
    }
    ranked = sorted(
        market,
        key=lambda row: (
            -_number(row, "research_score"),
            str(row.get("ticker", "")),
        ),
    )

    results: list[StrategicDiligenceRow] = []
    for rank, market_row in enumerate(ranked, 1):
        ticker = str(market_row.get("ticker", "")).upper()
        integrity = integrity_by_ticker.get(ticker)
        execution = execution_by_ticker.get(ticker)
        scorecard = scorecard_by_ticker.get(ticker)
        integrity_score = _number(integrity, "diligence_score")
        execution_score = _number(execution, "execution_risk_score")
        leadership_score = _number(execution, "leadership_risk_score")
        combined_risk = max(
            integrity_score,
            execution_score,
            leadership_score,
            _number(scorecard, "execution_downside_score"),
        )
        has_risk_evidence = bool(
            integrity
            or execution
            or (
                scorecard
                and scorecard.get("evidence_coverage")
                == "company_specific_evidence"
            )
        )
        archetype, structure, rule = _classify(
            _number(market_row, "research_score"),
            combined_risk,
            leadership_score,
            has_risk_evidence,
        )
        drivers = _list_value(execution, "primary_risk_drivers")
        if integrity and not drivers:
            drivers = [
                f"integrity categories: {', '.join(_list_value(integrity, 'categories'))}"
            ]
        if (
            scorecard
            and _number(scorecard, "negative_marker_evidence_score") > 0
            and not drivers
        ):
            drivers = [
                "historical marker evidence: "
                + ", ".join(
                    _list_value(scorecard, "active_company_marker_ids")
                )
            ]
        results.append(
            StrategicDiligenceRow(
                ticker=ticker,
                company_name=str(market_row.get("company_name", "")),
                ma_research_score=_number(market_row, "research_score"),
                ma_rank=rank,
                ma_band=_ma_band(_number(market_row, "research_score")),
                portfolio_score=_number(market_row, "portfolio_score"),
                acquirability_score=_number(market_row, "acquirability_score"),
                market_data_confidence=_number(market_row, "data_confidence"),
                integrity_diligence_score=integrity_score,
                execution_risk_score=execution_score,
                leadership_risk_score=leadership_score,
                delivery_upside_score=_number(
                    scorecard, "delivery_upside_score"
                ),
                positive_marker_evidence_score=_number(
                    scorecard, "positive_marker_evidence_score"
                ),
                negative_marker_evidence_score=_number(
                    scorecard, "negative_marker_evidence_score"
                ),
                execution_balance_score=_number(
                    scorecard, "execution_balance_score"
                ),
                execution_outlook=str(
                    (scorecard or {}).get("execution_outlook", "")
                ),
                evidence_coverage_score=_number(
                    scorecard, "evidence_coverage_score"
                ),
                closest_marker_id=str(
                    (scorecard or {}).get("closest_marker_id", "")
                ),
                closest_marker_polarity=str(
                    (scorecard or {}).get("closest_marker_polarity", "")
                ),
                marker_similarity=_number(scorecard, "marker_similarity"),
                combined_diligence_risk=combined_risk,
                risk_coverage=(
                    str(scorecard.get("evidence_coverage"))
                    if scorecard and scorecard.get("evidence_coverage")
                    else (
                        "company_specific_evidence"
                        if has_risk_evidence
                        else "limited_no_detected_signals"
                    )
                ),
                confirmed_misconduct_count=_integer(
                    integrity, "confirmed_misconduct_count"
                ),
                confirmed_individual_finding_count=_integer(
                    execution, "confirmed_individual_finding_count"
                ),
                strategic_archetype=archetype,
                suggested_transaction_structure=structure,
                decision_rule=rule,
                primary_risk_drivers=drivers,
                interpretation=(
                    "Dual-axis research triage. M&A scores are not calibrated "
                    "probabilities; risk scores are not findings of incompetence "
                    "or fraud."
                ),
            )
        )
    return results
