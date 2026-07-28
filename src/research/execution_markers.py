"""Point-in-time historical markers and market-wide execution scoring."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable


MARKER_POLARITIES = {"downside", "upside"}

# These are downstream labels. A marker cannot use them as anchor features unless
# the event was already observable on the anchor date.
PROHIBITED_ANCHOR_TAGS = {
    "bankruptcy",
    "asset_sale",
    "strategic_acquisition",
    "reverse_merger",
}

CATEGORY_TAGS = {
    "regulatory_delivery": {"regulatory_failure"},
    "clinical_program_delivery": {"missed_prespecified_endpoint"},
    "statistical_governance": {"statistical_governance"},
    "manufacturing_and_quality": {"manufacturing_quality"},
    "capital_execution": {"capital_distress"},
    "financial_controls": {"financial_control_failure"},
    "guidance_reliability": {"guidance_failure"},
    "partnership_execution": {"partnership_failure"},
}

DOWNSIDE_TAG_POINTS = {
    "regulatory_failure": 20.0,
    "missed_prespecified_endpoint": 15.0,
    "statistical_governance": 15.0,
    "inspection_pending": 8.0,
    "confirmatory_failure": 25.0,
    "product_withdrawal": 25.0,
    "safety_concern": 15.0,
    "endpoint_uncertainty": 12.0,
    "clinical_statistical_deficiency": 15.0,
    "manufacturing_quality": 15.0,
}

UPSIDE_TAG_POINTS = {
    "regulatory_approval": 25.0,
    "first_in_class": 25.0,
    "differentiated_asset": 20.0,
    "successful_remediation": 25.0,
    "accelerated_approval": 10.0,
}


def _number(row: dict[str, Any] | None, key: str) -> float:
    if not row:
        return 0.0
    value = row.get(key)
    return float(value) if value not in (None, "") else 0.0


def _integer(row: dict[str, Any] | None, key: str) -> int:
    return int(_number(row, key))


def _date(value: str, field: str, marker_id: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{marker_id}: {field} must be an ISO date"
        ) from exc


@dataclass(slots=True)
class HistoricalExecutionMarker:
    marker_id: str
    company_name: str
    historical_ticker: str
    polarity: str
    archetype: str
    anchor_date: str
    anchor_tags: list[str]
    anchor_source_url: str
    anchor_evidence_summary: str
    outcome_date: str
    outcome_class: str
    outcome_source_url: str
    outcome_summary: str

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "HistoricalExecutionMarker":
        marker = cls(
            marker_id=str(row["marker_id"]).strip(),
            company_name=str(row["company_name"]).strip(),
            historical_ticker=str(row.get("historical_ticker", "")).upper().strip(),
            polarity=str(row["polarity"]).strip(),
            archetype=str(row["archetype"]).strip(),
            anchor_date=str(row["anchor_date"]).strip(),
            anchor_tags=sorted(
                {
                    str(tag).strip()
                    for tag in row.get("anchor_tags", [])
                    if str(tag).strip()
                }
            ),
            anchor_source_url=str(row["anchor_source_url"]).strip(),
            anchor_evidence_summary=str(row["anchor_evidence_summary"]).strip(),
            outcome_date=str(row.get("outcome_date", "")).strip(),
            outcome_class=str(row["outcome_class"]).strip(),
            outcome_source_url=str(row.get("outcome_source_url", "")).strip(),
            outcome_summary=str(row["outcome_summary"]).strip(),
        )
        marker.validate()
        return marker

    def validate(self) -> None:
        if not self.marker_id or not self.company_name or not self.archetype:
            raise ValueError(
                "marker_id, company_name, and archetype are required"
            )
        if self.polarity not in MARKER_POLARITIES:
            raise ValueError(
                f"{self.marker_id}: unsupported polarity {self.polarity!r}"
            )
        anchor_date = _date(self.anchor_date, "anchor_date", self.marker_id)
        outcome_date = _date(self.outcome_date, "outcome_date", self.marker_id)
        if outcome_date and anchor_date and outcome_date < anchor_date:
            raise ValueError(
                f"{self.marker_id}: outcome_date cannot precede anchor_date"
            )
        if not self.anchor_tags:
            raise ValueError(f"{self.marker_id}: anchor_tags are required")
        leaked = PROHIBITED_ANCHOR_TAGS.intersection(self.anchor_tags)
        if leaked:
            raise ValueError(
                f"{self.marker_id}: downstream outcome tags leaked into "
                f"anchor_tags: {sorted(leaked)}"
            )
        if not self.anchor_source_url.startswith("https://"):
            raise ValueError(
                f"{self.marker_id}: anchor_source_url must be HTTPS"
            )
        if self.outcome_date and not self.outcome_source_url.startswith("https://"):
            raise ValueError(
                f"{self.marker_id}: dated outcomes require an HTTPS source"
            )
        if not self.anchor_evidence_summary or not self.outcome_summary:
            raise ValueError(
                f"{self.marker_id}: evidence and outcome summaries are required"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecutionScorecardRow:
    ticker: str
    company_name: str
    delivery_upside_score: float
    execution_downside_score: float
    leadership_risk_score: float
    positive_marker_evidence_score: float
    negative_marker_evidence_score: float
    execution_balance_score: float
    execution_outlook: str
    evidence_coverage: str
    evidence_coverage_score: float
    approved_asset_count: int
    late_stage_asset_count: int
    active_company_marker_ids: list[str]
    current_feature_tags: list[str]
    closest_marker_id: str
    closest_marker_company: str
    closest_marker_polarity: str
    marker_similarity: float
    marker_outcome_class: str
    marker_outcome_date: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _marker_similarity(company_tags: set[str], marker_tags: set[str]) -> float:
    if not company_tags or not marker_tags:
        return 0.0
    intersection = len(company_tags.intersection(marker_tags))
    # One generic shared tag such as regulatory_approval is too weak to call a
    # company a precedent match.
    if intersection < 2:
        return 0.0
    union = len(company_tags.union(marker_tags))
    return round(100.0 * intersection / union, 2) if union else 0.0


def _delivery_upside(market_row: dict[str, Any]) -> float:
    portfolio = _number(market_row, "portfolio_score")
    confidence = _number(market_row, "data_confidence")
    approved = _integer(market_row, "approved_asset_count")
    late_stage = _integer(market_row, "late_stage_asset_count")
    score = (
        0.35 * portfolio
        + 10.0 * math.log1p(approved)
        + 7.0 * math.log1p(late_stage)
        + 0.15 * confidence
    )
    return round(min(100.0, max(0.0, score)), 2)


def _marker_evidence_score(
    markers: Iterable[HistoricalExecutionMarker],
    point_values: dict[str, float],
) -> float:
    scores = [
        min(
            100.0,
            sum(point_values.get(tag, 0.0) for tag in marker.anchor_tags),
        )
        for marker in markers
    ]
    return round(max(scores, default=0.0), 2)


def _current_tags(
    market_row: dict[str, Any],
    integrity_row: dict[str, Any] | None,
    execution_row: dict[str, Any] | None,
) -> set[str]:
    tags: set[str] = set()
    if _integer(market_row, "approved_asset_count") > 0:
        tags.add("regulatory_approval")
    if _integer(market_row, "late_stage_asset_count") > 0:
        tags.add("late_stage_delivery")
    if _number(market_row, "portfolio_score") >= 75:
        tags.add("strong_asset_portfolio")
    for row in (integrity_row, execution_row):
        if not row:
            continue
        raw = row.get("categories", [])
        if isinstance(raw, str):
            raw = raw.strip("[]").replace('"', "").split(",") if raw else []
        for category in raw:
            normalized = str(category).strip()
            tags.update(CATEGORY_TAGS.get(normalized, {normalized}))
    if execution_row and _integer(execution_row, "pending_inspection_count") > 0:
        tags.add("inspection_pending")
    return tags


def _coverage(
    market_row: dict[str, Any],
    integrity_row: dict[str, Any] | None,
    execution_row: dict[str, Any] | None,
    has_negative_marker: bool,
) -> tuple[str, float]:
    market_confidence = _number(market_row, "data_confidence")
    asset_depth = bool(
        _integer(market_row, "approved_asset_count")
        or _integer(market_row, "clinical_asset_count")
    )
    company_evidence = bool(
        integrity_row or execution_row or has_negative_marker
    )
    if company_evidence:
        return "company_specific_evidence", round(min(100.0, 70 + 0.3 * market_confidence), 2)
    if asset_depth and market_confidence >= 40:
        return "market_only_risk_unscreened", round(min(69.0, 20 + 0.7 * market_confidence), 2)
    return "sparse_risk_unscreened", round(min(39.0, 0.6 * market_confidence), 2)


def _outlook(
    upside: float,
    downside: float,
    coverage: str,
) -> str:
    if downside >= 50:
        return "downside_led"
    if downside >= 25:
        return "elevated_execution_diligence"
    if coverage != "company_specific_evidence":
        if upside >= 50:
            return "upside_proxy_risk_unscreened"
        return "insufficient_risk_evidence"
    if upside - downside >= 25:
        return "upside_led_reviewed"
    return "balanced_reviewed"


def score_company_execution(
    market_rows: Iterable[dict[str, Any]],
    integrity_rows: Iterable[dict[str, Any]],
    execution_rows: Iterable[dict[str, Any]],
    markers: Iterable[HistoricalExecutionMarker],
    as_of: date | None = None,
) -> list[ExecutionScorecardRow]:
    """Score every market row while keeping outcome labels out of features."""

    marker_list = list(markers)
    for marker in marker_list:
        marker.validate()
    if as_of:
        marker_list = [
            marker
            for marker in marker_list
            if date.fromisoformat(marker.anchor_date) <= as_of
        ]
    integrity_by_ticker = {
        str(row.get("ticker", "")).upper(): row for row in integrity_rows
    }
    execution_by_ticker = {
        str(row.get("ticker", "")).upper(): row for row in execution_rows
    }

    results: list[ExecutionScorecardRow] = []
    for market_row in market_rows:
        ticker = str(market_row.get("ticker", "")).upper()
        integrity = integrity_by_ticker.get(ticker)
        execution = execution_by_ticker.get(ticker)
        company_markers = [
            marker
            for marker in marker_list
            if marker.historical_ticker == ticker
        ]
        positive_markers = [
            marker for marker in company_markers if marker.polarity == "upside"
        ]
        negative_markers = [
            marker
            for marker in company_markers
            if marker.polarity == "downside"
        ]
        positive_marker_score = _marker_evidence_score(
            positive_markers, UPSIDE_TAG_POINTS
        )
        negative_marker_score = _marker_evidence_score(
            negative_markers, DOWNSIDE_TAG_POINTS
        )
        integrity_risk = _number(integrity, "diligence_score")
        execution_risk = _number(execution, "execution_risk_score")
        leadership_risk = _number(execution, "leadership_risk_score")
        downside = round(
            max(
                integrity_risk,
                execution_risk,
                leadership_risk,
                negative_marker_score,
            ),
            2,
        )
        upside = max(
            _delivery_upside(market_row),
            positive_marker_score,
        )
        balance = round(upside - downside, 2)
        coverage, coverage_score = _coverage(
            market_row,
            integrity,
            execution,
            bool(negative_markers),
        )
        tags = _current_tags(market_row, integrity, execution)
        for marker in company_markers:
            tags.update(marker.anchor_tags)
        ranked_markers = sorted(
            (
                (
                    _marker_similarity(tags, set(marker.anchor_tags)),
                    marker,
                )
                for marker in marker_list
            ),
            key=lambda pair: (
                -pair[0],
                pair[1].marker_id,
            ),
        )
        similarity, closest = ranked_markers[0] if ranked_markers else (0.0, None)
        if similarity < 15:
            closest = None
            similarity = 0.0

        results.append(
            ExecutionScorecardRow(
                ticker=ticker,
                company_name=str(market_row.get("company_name", "")),
                delivery_upside_score=upside,
                execution_downside_score=downside,
                leadership_risk_score=leadership_risk,
                positive_marker_evidence_score=positive_marker_score,
                negative_marker_evidence_score=negative_marker_score,
                execution_balance_score=balance,
                execution_outlook=_outlook(upside, downside, coverage),
                evidence_coverage=coverage,
                evidence_coverage_score=coverage_score,
                approved_asset_count=_integer(
                    market_row, "approved_asset_count"
                ),
                late_stage_asset_count=_integer(
                    market_row, "late_stage_asset_count"
                ),
                active_company_marker_ids=[
                    marker.marker_id for marker in company_markers
                ],
                current_feature_tags=sorted(tags),
                closest_marker_id=closest.marker_id if closest else "",
                closest_marker_company=closest.company_name if closest else "",
                closest_marker_polarity=closest.polarity if closest else "",
                marker_similarity=similarity,
                marker_outcome_class=closest.outcome_class if closest else "",
                marker_outcome_date=closest.outcome_date if closest else "",
                interpretation=(
                    "Delivery upside is an asset-progress proxy, not proof of "
                    "management quality. Downside uses sourced company evidence. "
                    "A missing risk signal means unscreened, not low risk. Historical "
                    "outcomes are validation labels and are not score features."
                ),
            )
        )

    return sorted(
        results,
        key=lambda row: (
            -row.execution_downside_score,
            -row.delivery_upside_score,
            row.ticker,
        ),
    )
