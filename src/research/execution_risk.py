"""Evidence-gated company and leadership execution-risk scoring."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


EXECUTION_STATUSES = {
    "unverified_indicator",
    "company_disclosed_event",
    "regulator_concern",
    "inspection_pending",
    "formal_failure",
    "enforcement_finding",
    "resolved",
}

EXECUTION_SCOPES = {"company", "leadership_team", "named_executive"}

ATTRIBUTION_BASES = {
    "none",
    "role_accountability",
    "official_individual_finding",
}

STATUS_MULTIPLIERS = {
    "unverified_indicator": 0.15,
    "company_disclosed_event": 0.35,
    "regulator_concern": 0.55,
    "inspection_pending": 0.60,
    "formal_failure": 0.80,
    "enforcement_finding": 1.00,
    "resolved": 0.00,
}


@dataclass(slots=True)
class ExecutionRiskSignal:
    signal_id: str
    company_name: str
    ticker: str
    event_date: str
    category: str
    evidence_status: str
    severity: int
    confidence: float
    scope: str
    attribution_basis: str
    responsible_roles: list[str]
    named_people: list[str]
    source_organization: str
    source_title: str
    source_url: str
    summary: str
    review_notes: str = ""
    response_url: str = ""
    response_summary: str = ""

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "ExecutionRiskSignal":
        signal = cls(
            signal_id=str(row["signal_id"]).strip(),
            company_name=str(row["company_name"]).strip(),
            ticker=str(row.get("ticker", "")).upper().strip(),
            event_date=str(row["event_date"]).strip(),
            category=str(row["category"]).strip(),
            evidence_status=str(row["evidence_status"]).strip(),
            severity=int(row["severity"]),
            confidence=float(row["confidence"]),
            scope=str(row["scope"]).strip(),
            attribution_basis=str(row["attribution_basis"]).strip(),
            responsible_roles=[
                str(value).strip()
                for value in row.get("responsible_roles", [])
                if str(value).strip()
            ],
            named_people=[
                str(value).strip()
                for value in row.get("named_people", [])
                if str(value).strip()
            ],
            source_organization=str(row["source_organization"]).strip(),
            source_title=str(row["source_title"]).strip(),
            source_url=str(row["source_url"]).strip(),
            summary=str(row["summary"]).strip(),
            review_notes=str(row.get("review_notes", "")).strip(),
            response_url=str(row.get("response_url", "")).strip(),
            response_summary=str(row.get("response_summary", "")).strip(),
        )
        signal.validate()
        return signal

    def validate(self) -> None:
        if not self.signal_id or not self.company_name or not self.event_date:
            raise ValueError("signal_id, company_name, and event_date are required")
        if self.evidence_status not in EXECUTION_STATUSES:
            raise ValueError(
                f"{self.signal_id}: unsupported evidence_status "
                f"{self.evidence_status!r}"
            )
        if self.scope not in EXECUTION_SCOPES:
            raise ValueError(f"{self.signal_id}: unsupported scope {self.scope!r}")
        if self.attribution_basis not in ATTRIBUTION_BASES:
            raise ValueError(
                f"{self.signal_id}: unsupported attribution_basis "
                f"{self.attribution_basis!r}"
            )
        if not 1 <= self.severity <= 5:
            raise ValueError(f"{self.signal_id}: severity must be from 1 to 5")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"{self.signal_id}: confidence must be from 0 to 1")
        if not self.source_url.startswith("https://"):
            raise ValueError(f"{self.signal_id}: source_url must be HTTPS")
        if not self.summary:
            raise ValueError(f"{self.signal_id}: summary is required")
        if self.scope == "company" and self.attribution_basis != "none":
            raise ValueError(
                f"{self.signal_id}: company scope requires attribution_basis none"
            )
        if self.scope != "company" and not self.responsible_roles:
            raise ValueError(
                f"{self.signal_id}: leadership scope requires responsible_roles"
            )
        if self.named_people and (
            self.scope != "named_executive"
            or self.attribution_basis != "official_individual_finding"
            or self.evidence_status != "enforcement_finding"
        ):
            raise ValueError(
                f"{self.signal_id}: named people require an official individual "
                "enforcement finding"
            )
        if self.scope == "named_executive" and not self.named_people:
            raise ValueError(
                f"{self.signal_id}: named_executive scope requires named_people"
            )

    @property
    def weighted_points(self) -> float:
        return round(
            self.severity
            * 4.0
            * STATUS_MULTIPLIERS[self.evidence_status]
            * self.confidence,
            2,
        )

    @property
    def leadership_points(self) -> float:
        if self.scope == "company":
            return 0.0
        attribution_multiplier = (
            1.0 if self.attribution_basis == "official_individual_finding" else 0.75
        )
        return round(self.weighted_points * attribution_multiplier, 2)

    @property
    def confirmed_individual_finding(self) -> bool:
        return bool(
            self.named_people
            and self.attribution_basis == "official_individual_finding"
            and self.evidence_status == "enforcement_finding"
        )

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["weighted_points"] = self.weighted_points
        row["leadership_points"] = self.leadership_points
        row["confirmed_individual_finding"] = self.confirmed_individual_finding
        return row


@dataclass(slots=True)
class ExecutionRiskEvaluation:
    company_name: str
    ticker: str
    execution_risk_score: float
    execution_risk_level: str
    leadership_risk_score: float
    leadership_risk_level: str
    signal_count: int
    open_signal_count: int
    formal_failure_count: int
    pending_inspection_count: int
    confirmed_individual_finding_count: int
    categories: list[str]
    responsible_roles: list[str]
    primary_risk_drivers: list[str]
    required_action: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "elevated"
    if score > 0:
        return "review"
    return "no_detected_signals"


def _required_action(execution_level: str, leadership_level: str) -> str:
    if "critical" in {execution_level, leadership_level}:
        return "Escalate to legal, governance, regulatory, and scientific review."
    if "high" in {execution_level, leadership_level}:
        return "Require independent source-document and leadership-track-record review."
    if "elevated" in {execution_level, leadership_level}:
        return "Add targeted execution, governance, and accountability diligence."
    return "Review cited events and expand source coverage before drawing conclusions."


def evaluate_execution_risk(
    signals: Iterable[ExecutionRiskSignal],
) -> list[ExecutionRiskEvaluation]:
    grouped: dict[tuple[str, str], list[ExecutionRiskSignal]] = {}
    for signal in signals:
        signal.validate()
        key = (signal.ticker, signal.company_name.casefold())
        grouped.setdefault(key, []).append(signal)

    results: list[ExecutionRiskEvaluation] = []
    for company_signals in grouped.values():
        execution_cells: dict[tuple[str, str], float] = {}
        leadership_cells: dict[tuple[str, str], float] = {}
        for signal in company_signals:
            cell = (signal.category, signal.event_date)
            execution_cells[cell] = max(
                execution_cells.get(cell, 0.0), signal.weighted_points
            )
            leadership_cells[cell] = max(
                leadership_cells.get(cell, 0.0), signal.leadership_points
            )

        execution_score = round(min(100.0, sum(execution_cells.values())), 2)
        leadership_score = round(min(100.0, sum(leadership_cells.values())), 2)
        execution_level = _level(execution_score)
        leadership_level = _level(leadership_score)
        strongest = sorted(
            company_signals,
            key=lambda signal: (
                -signal.weighted_points,
                signal.event_date,
                signal.signal_id,
            ),
        )[:3]
        results.append(
            ExecutionRiskEvaluation(
                company_name=company_signals[0].company_name,
                ticker=company_signals[0].ticker,
                execution_risk_score=execution_score,
                execution_risk_level=execution_level,
                leadership_risk_score=leadership_score,
                leadership_risk_level=leadership_level,
                signal_count=len(company_signals),
                open_signal_count=sum(
                    signal.evidence_status != "resolved" for signal in company_signals
                ),
                formal_failure_count=sum(
                    signal.evidence_status == "formal_failure"
                    for signal in company_signals
                ),
                pending_inspection_count=sum(
                    signal.evidence_status == "inspection_pending"
                    for signal in company_signals
                ),
                confirmed_individual_finding_count=sum(
                    signal.confirmed_individual_finding for signal in company_signals
                ),
                categories=sorted({signal.category for signal in company_signals}),
                responsible_roles=sorted(
                    {
                        role
                        for signal in company_signals
                        for role in signal.responsible_roles
                    }
                ),
                primary_risk_drivers=[
                    f"{signal.category}: {signal.summary}" for signal in strongest
                ],
                required_action=_required_action(execution_level, leadership_level),
                interpretation=(
                    "Evidence-backed execution and role-accountability triage. "
                    "It is not a finding that a company or person is incompetent. "
                    "Named-person findings require official adjudication."
                ),
            )
        )

    return sorted(
        results,
        key=lambda item: (
            -max(item.execution_risk_score, item.leadership_risk_score),
            item.ticker,
        ),
    )


def validate_execution_ledger(
    signals: Iterable[ExecutionRiskSignal],
) -> dict[str, int]:
    rows = list(signals)
    signal_ids: set[str] = set()
    for signal in rows:
        signal.validate()
        if signal.signal_id in signal_ids:
            raise ValueError(f"Duplicate signal_id: {signal.signal_id}")
        signal_ids.add(signal.signal_id)
    return {
        "rows": len(rows),
        "companies": len(
            {(signal.ticker, signal.company_name.casefold()) for signal in rows}
        ),
        "named_individual_findings": sum(
            signal.confirmed_individual_finding for signal in rows
        ),
    }
