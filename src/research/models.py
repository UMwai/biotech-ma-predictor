"""Canonical records emitted by the biotech M&A research pipeline."""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class PublicCompany:
    ticker: str
    name: str
    exchange: str
    industry: str
    market_cap_usd: Optional[float]
    country: str = ""
    cik: Optional[int] = None
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AssetEvaluation:
    asset_id: str
    asset_name: str
    asset_type: str
    owner_name: str
    owner_ticker: Optional[str]
    owner_match_confidence: float
    development_phase: str
    indications: list[str]
    score: float
    score_drivers: list[str]
    source_name: str
    source_id: str
    source_url: str
    published_at: Optional[str] = None
    patent_expiry: Optional[str] = None
    exclusivity_expiry: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        for key in ("indications", "score_drivers", "metadata"):
            row[key] = row[key]
        return row


@dataclass(slots=True)
class CompanyEvaluation:
    ticker: str
    company_name: str
    exchange: str
    industry: str
    market_cap_usd: Optional[float]
    research_score: float
    portfolio_score: float
    acquirability_score: float
    data_confidence: float
    approved_asset_count: int
    clinical_asset_count: int
    late_stage_asset_count: int
    top_assets: list[str]
    score_drivers: list[str]
    risk_set_eligible: bool
    risk_set_exclusion_reason: Optional[str]
    model_version: str
    evaluated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DealCandidate:
    """Auditable SEC transaction candidate.

    ``sec_signal_date`` is the first qualifying filing date in a filing
    cluster. It is deliberately not named ``announcement_date``: the first
    public deal announcement must be separately reviewed before model use.
    """

    candidate_id: str
    target_cik: int
    filer_name: str
    filer_tickers: list[str]
    sic_codes: list[str]
    sec_signal_date: str
    last_related_filing_date: str
    event_class: str
    confidence: str
    adjudication_status: str
    model_label_eligible: bool
    filing_forms: list[str]
    accession_numbers: list[str]
    primary_source_urls: list[str]
    filing_count: int
    review_notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
