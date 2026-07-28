"""Evidence-gated study-integrity screening for biotech diligence.

This module deliberately separates statistical or regulatory concerns from
adjudicated research misconduct.  A model-generated anomaly is never treated
as proof of fraud.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


EVIDENCE_STATUSES = {
    "unverified_anomaly",
    "disputed_allegation",
    "regulatory_concern",
    "inspection_pending",
    "formal_regulatory_finding",
    "confirmed_research_misconduct",
    "publication_retraction",
    "resolved",
}

SOURCE_CLASSES = {
    "regulator_review",
    "regulator_enforcement",
    "court_or_government_enforcement",
    "research_integrity_finding",
    "trial_registry",
    "publication_record",
    "issuer_response",
}

STATUS_MULTIPLIERS = {
    "unverified_anomaly": 0.15,
    "disputed_allegation": 0.20,
    "regulatory_concern": 0.55,
    "inspection_pending": 0.60,
    "formal_regulatory_finding": 0.80,
    "publication_retraction": 0.85,
    "confirmed_research_misconduct": 1.00,
    "resolved": 0.00,
}

CONFIRMED_MISCONDUCT_AUTHORITIES = {
    "regulator_enforcement",
    "court_or_government_enforcement",
    "research_integrity_finding",
}


@dataclass(slots=True)
class StudyIntegritySignal:
    signal_id: str
    company_name: str
    ticker: str
    product_name: str
    study_ids: list[str]
    category: str
    evidence_status: str
    severity: int
    confidence: float
    source_class: str
    source_organization: str
    source_title: str
    source_url: str
    source_date: str
    summary: str
    review_notes: str = ""
    response_url: str = ""
    response_summary: str = ""

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "StudyIntegritySignal":
        signal = cls(
            signal_id=str(row["signal_id"]).strip(),
            company_name=str(row["company_name"]).strip(),
            ticker=str(row.get("ticker", "")).upper().strip(),
            product_name=str(row.get("product_name", "")).strip(),
            study_ids=[
                str(value).strip()
                for value in row.get("study_ids", [])
                if str(value).strip()
            ],
            category=str(row["category"]).strip(),
            evidence_status=str(row["evidence_status"]).strip(),
            severity=int(row["severity"]),
            confidence=float(row["confidence"]),
            source_class=str(row["source_class"]).strip(),
            source_organization=str(row["source_organization"]).strip(),
            source_title=str(row["source_title"]).strip(),
            source_url=str(row["source_url"]).strip(),
            source_date=str(row["source_date"]).strip(),
            summary=str(row["summary"]).strip(),
            review_notes=str(row.get("review_notes", "")).strip(),
            response_url=str(row.get("response_url", "")).strip(),
            response_summary=str(row.get("response_summary", "")).strip(),
        )
        signal.validate()
        return signal

    def validate(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if not self.company_name:
            raise ValueError(f"{self.signal_id}: company_name is required")
        if self.evidence_status not in EVIDENCE_STATUSES:
            raise ValueError(
                f"{self.signal_id}: unsupported evidence_status "
                f"{self.evidence_status!r}"
            )
        if self.source_class not in SOURCE_CLASSES:
            raise ValueError(
                f"{self.signal_id}: unsupported source_class {self.source_class!r}"
            )
        if not 1 <= self.severity <= 5:
            raise ValueError(f"{self.signal_id}: severity must be from 1 to 5")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"{self.signal_id}: confidence must be from 0 to 1")
        if not self.source_url.startswith("https://"):
            raise ValueError(f"{self.signal_id}: source_url must be HTTPS")
        if not self.source_date:
            raise ValueError(f"{self.signal_id}: source_date is required")
        if not self.summary:
            raise ValueError(f"{self.signal_id}: summary is required")

    @property
    def confirmed_misconduct(self) -> bool:
        return (
            self.evidence_status == "confirmed_research_misconduct"
            and self.source_class in CONFIRMED_MISCONDUCT_AUTHORITIES
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

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["weighted_points"] = self.weighted_points
        row["confirmed_misconduct"] = self.confirmed_misconduct
        return row


@dataclass(slots=True)
class CompanyIntegrityEvaluation:
    company_name: str
    ticker: str
    diligence_score: float
    diligence_level: str
    signal_count: int
    open_signal_count: int
    confirmed_misconduct_count: int
    formal_finding_count: int
    pending_inspection_count: int
    disputed_signal_count: int
    categories: list[str]
    study_ids: list[str]
    source_organizations: list[str]
    required_action: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _diligence_level(score: float) -> str:
    if score >= 75:
        return "critical_diligence"
    if score >= 50:
        return "high_diligence"
    if score >= 25:
        return "elevated_diligence"
    if score > 0:
        return "review"
    return "no_detected_signals"


def _required_action(level: str, confirmed_count: int) -> str:
    if confirmed_count:
        return "Escalate to legal, regulatory, and scientific diligence."
    if level == "critical_diligence":
        return "Pause reliance on affected studies pending independent review."
    if level == "high_diligence":
        return "Require source-document and statistical review before reliance."
    if level == "elevated_diligence":
        return "Add targeted clinical, statistical, and regulatory diligence."
    if level == "review":
        return "Review the cited primary evidence before using the study."
    return "Continue monitoring; absence of detected signals is not proof of integrity."


def evaluate_study_integrity(
    signals: Iterable[StudyIntegritySignal],
) -> list[CompanyIntegrityEvaluation]:
    """Aggregate evidence without double-counting repeated descriptions.

    Only the strongest signal for each company/study/category combination
    contributes points. Corroborating records remain visible in signal counts.
    """

    grouped: dict[tuple[str, str], list[StudyIntegritySignal]] = {}
    for signal in signals:
        signal.validate()
        key = (signal.ticker, signal.company_name.casefold())
        grouped.setdefault(key, []).append(signal)

    evaluations: list[CompanyIntegrityEvaluation] = []
    for (_, _), company_signals in grouped.items():
        strongest: dict[tuple[tuple[str, ...], str], float] = {}
        for signal in company_signals:
            study_key = tuple(sorted(signal.study_ids)) or ("company_level",)
            key = (study_key, signal.category)
            strongest[key] = max(strongest.get(key, 0.0), signal.weighted_points)

        score = round(min(100.0, sum(strongest.values())), 2)
        level = _diligence_level(score)
        confirmed_count = sum(s.confirmed_misconduct for s in company_signals)
        evaluations.append(
            CompanyIntegrityEvaluation(
                company_name=company_signals[0].company_name,
                ticker=company_signals[0].ticker,
                diligence_score=score,
                diligence_level=level,
                signal_count=len(company_signals),
                open_signal_count=sum(
                    s.evidence_status != "resolved" for s in company_signals
                ),
                confirmed_misconduct_count=confirmed_count,
                formal_finding_count=sum(
                    s.evidence_status == "formal_regulatory_finding"
                    for s in company_signals
                ),
                pending_inspection_count=sum(
                    s.evidence_status == "inspection_pending" for s in company_signals
                ),
                disputed_signal_count=sum(
                    bool(s.response_url) for s in company_signals
                ),
                categories=sorted({s.category for s in company_signals}),
                study_ids=sorted(
                    {study_id for s in company_signals for study_id in s.study_ids}
                ),
                source_organizations=sorted(
                    {s.source_organization for s in company_signals}
                ),
                required_action=_required_action(level, confirmed_count),
                interpretation=(
                    "Diligence triage score, not a probability and not a finding "
                    "of fraud. Confirmed misconduct requires an adjudicated finding "
                    "from a qualified authority."
                ),
            )
        )

    return sorted(
        evaluations,
        key=lambda item: (-item.diligence_score, item.ticker, item.company_name),
    )


def validate_signal_ledger(
    signals: Iterable[StudyIntegritySignal],
) -> dict[str, int]:
    rows = list(signals)
    ids: set[str] = set()
    confirmed = 0
    for signal in rows:
        signal.validate()
        if signal.signal_id in ids:
            raise ValueError(f"Duplicate signal_id: {signal.signal_id}")
        ids.add(signal.signal_id)
        confirmed += int(signal.confirmed_misconduct)
    return {
        "rows": len(rows),
        "companies": len(
            {(signal.ticker, signal.company_name.casefold()) for signal in rows}
        ),
        "confirmed_misconduct_rows": confirmed,
    }
