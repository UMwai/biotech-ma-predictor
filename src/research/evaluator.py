"""Transparent research scoring for public biotech companies and drug assets.

Scores are cross-sectional research rankings, not calibrated acquisition probabilities.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Optional

from src.research.matching import CompanyMatcher
from src.research.models import AssetEvaluation, CompanyEvaluation, PublicCompany
from src.research.sources import utc_now_iso

MODEL_VERSION = "market-research-0.1.0"

PHASE_VALUE = {
    "EARLY_PHASE1": 10.0,
    "PHASE1": 14.0,
    "PHASE1|PHASE2": 23.0,
    "PHASE2": 27.0,
    "PHASE2|PHASE3": 36.0,
    "PHASE3": 42.0,
    "NA": 6.0,
}


def _stable_id(*parts: str) -> str:
    value = "|".join(parts).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:20]


def _date_from_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _remaining_years(expiry: Optional[date], as_of: date) -> float:
    if not expiry:
        return 0.0
    return max(0.0, (expiry - as_of).days / 365.25)


def evaluate_orange_book_assets(
    raw_assets: Iterable[dict[str, Any]],
    matcher: CompanyMatcher,
    as_of: date,
) -> list[AssetEvaluation]:
    results: list[AssetEvaluation] = []
    for raw in raw_assets:
        match = matcher.match(raw["applicant"])
        patents: list[date] = raw.get("patent_expiries", [])
        exclusivities: list[date] = raw.get("exclusivity_expiries", [])
        patent_expiry = max(patents) if patents else None
        exclusivity_expiry = max(exclusivities) if exclusivities else None
        protection_years = max(
            _remaining_years(patent_expiry, as_of),
            _remaining_years(exclusivity_expiry, as_of),
        )
        competition = int(raw.get("applicant_count_for_ingredient", 1))
        is_innovator = "N" in raw.get("application_types", []) or bool(
            raw.get("is_reference_drug")
        )

        score = 24.0
        drivers = ["FDA-listed marketed product"]
        if is_innovator:
            score += 18.0
            drivers.append("innovator/reference application")
        else:
            drivers.append("generic application")
        if protection_years > 0:
            protection_points = min(24.0, protection_years * 2.4)
            score += protection_points
            drivers.append(f"{protection_years:.1f} years of listed protection")
        else:
            drivers.append("no unexpired listed patent/exclusivity found")
        if competition == 1:
            score += 16.0
            drivers.append("single listed applicant for ingredient")
        elif competition <= 3:
            score += 11.0
            drivers.append(f"limited listed competition ({competition} applicants)")
        elif competition <= 8:
            score += 5.0
            drivers.append(f"moderate listed competition ({competition} applicants)")
        else:
            drivers.append(f"high listed competition ({competition} applicants)")
        score += min(8.0, math.log1p(int(raw.get("product_rows", 1))) * 2.5)

        names = raw.get("trade_names", [])
        source_ids = raw.get("application_numbers", [])
        results.append(
            AssetEvaluation(
                asset_id=_stable_id("orange_book", raw["ingredient"], raw["applicant"]),
                asset_name=raw["ingredient"],
                asset_type="approved_small_molecule",
                owner_name=raw["applicant"],
                owner_ticker=match.ticker,
                owner_match_confidence=match.confidence,
                development_phase="approved",
                indications=[],
                score=round(min(100.0, score), 2),
                score_drivers=drivers,
                source_name="FDA Orange Book",
                source_id=",".join(source_ids),
                source_url="https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files",
                patent_expiry=patent_expiry.isoformat() if patent_expiry else None,
                exclusivity_expiry=(
                    exclusivity_expiry.isoformat() if exclusivity_expiry else None
                ),
                metadata={
                    "trade_names": names,
                    "routes": raw.get("routes", []),
                    "application_types": raw.get("application_types", []),
                    "applicant_count_for_ingredient": competition,
                    "is_reference_drug": bool(raw.get("is_reference_drug")),
                    "patent_count": len(raw.get("patent_numbers", [])),
                },
            )
        )
    return results


def evaluate_biologic_assets(
    raw_assets: Iterable[dict[str, Any]],
    matcher: CompanyMatcher,
) -> list[AssetEvaluation]:
    """Evaluate currently marketed BLA products from Drugs@FDA."""
    results: list[AssetEvaluation] = []
    for raw in raw_assets:
        match = matcher.match(raw["sponsor"])
        competition = int(raw.get("sponsor_count_for_ingredient", 1))
        score = 38.0
        drivers = ["currently marketed BLA product"]
        if raw.get("is_reference_drug"):
            score += 20.0
            drivers.append("reference biological product")
        if competition == 1:
            score += 18.0
            drivers.append("single marketed BLA sponsor for ingredient")
        elif competition <= 3:
            score += 10.0
            drivers.append(f"limited marketed BLA competition ({competition} sponsors)")
        else:
            score += 4.0
            drivers.append(f"multiple marketed BLA sponsors ({competition})")
        score += min(10.0, math.log1p(int(raw.get("product_rows", 1))) * 3.0)

        results.append(
            AssetEvaluation(
                asset_id=_stable_id("drugsfda_bla", raw["ingredient"], raw["sponsor"]),
                asset_name=raw["ingredient"],
                asset_type="approved_biologic",
                owner_name=raw["sponsor"],
                owner_ticker=match.ticker,
                owner_match_confidence=match.confidence,
                development_phase="approved",
                indications=[],
                score=round(min(100.0, score), 2),
                score_drivers=drivers,
                source_name="Drugs@FDA",
                source_id=",".join(raw.get("application_numbers", [])),
                source_url="https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files",
                metadata={
                    "trade_names": raw.get("trade_names", []),
                    "forms": raw.get("forms", []),
                    "sponsor_count_for_ingredient": competition,
                    "is_reference_drug": bool(raw.get("is_reference_drug")),
                },
            )
        )
    return results


def _best_phase(phases: Iterable[str]) -> str:
    normalized = sorted({phase.upper().replace("_", "") for phase in phases if phase})
    if "PHASE3" in normalized:
        return "PHASE3"
    if "PHASE2" in normalized and "PHASE1" in normalized:
        return "PHASE1|PHASE2"
    if "PHASE2" in normalized:
        return "PHASE2"
    if "PHASE1" in normalized:
        return "PHASE1"
    if "EARLYPHASE1" in normalized:
        return "EARLY_PHASE1"
    return "NA"


def evaluate_clinical_assets(
    raw_assets: Iterable[dict[str, Any]],
    matcher: CompanyMatcher,
    as_of: date,
) -> list[AssetEvaluation]:
    results: list[AssetEvaluation] = []
    for raw in raw_assets:
        match = matcher.match(raw["sponsor"])
        sponsor_count = int(raw.get("sponsor_count_for_intervention", 1))
        attributed_ticker = match.ticker if sponsor_count == 1 else None
        attributed_confidence = match.confidence if sponsor_count == 1 else 0.0
        phase = _best_phase(raw.get("phases", []))
        score = PHASE_VALUE[phase]
        drivers = [f"highest active phase: {phase.lower()}"]
        statuses = set(raw.get("statuses", []))
        if "RECRUITING" in statuses:
            score += 10.0
            drivers.append("actively recruiting")
        elif "NOT_YET_RECRUITING" in statuses:
            score += 7.0
            drivers.append("trial not yet recruiting")
        elif "ACTIVE_NOT_RECRUITING" in statuses:
            score += 5.0
            drivers.append("active, no longer recruiting")

        trial_count = int(raw.get("trial_count", 1))
        trial_points = min(16.0, math.log1p(trial_count) * 5.0)
        score += trial_points
        if trial_count > 1:
            drivers.append(f"{trial_count} active registered trials")
        if sponsor_count > 1:
            drivers.append(
                f"intervention appears under {sponsor_count} lead sponsors; ownership not attributed"
            )

        last_updates = [_date_from_iso(value) for value in raw.get("last_updates", [])]
        last_updates = [value for value in last_updates if value]
        latest_update = max(last_updates) if last_updates else None
        if latest_update:
            age_days = max(0, (as_of - latest_update).days)
            if age_days <= 180:
                score += 10.0
                drivers.append("ClinicalTrials.gov record updated within 180 days")
            elif age_days <= 365:
                score += 5.0
                drivers.append("ClinicalTrials.gov record updated within one year")

        max_enrollment = max(raw.get("enrollments", []) or [0])
        if max_enrollment:
            score += min(10.0, math.log10(max_enrollment + 1) * 3.5)
            drivers.append(f"largest active trial enrollment: {max_enrollment}")

        nct_ids = raw.get("nct_ids", [])
        results.append(
            AssetEvaluation(
                asset_id=_stable_id("clinical_trials", raw["sponsor"], raw["name"]),
                asset_name=raw["name"],
                asset_type="clinical_pipeline",
                owner_name=raw["sponsor"],
                owner_ticker=attributed_ticker,
                owner_match_confidence=attributed_confidence,
                development_phase=phase.lower(),
                indications=raw.get("conditions", []),
                score=round(min(100.0, score), 2),
                score_drivers=drivers,
                source_name="ClinicalTrials.gov",
                source_id=",".join(nct_ids),
                source_url=(
                    f"https://clinicaltrials.gov/study/{nct_ids[0]}"
                    if nct_ids
                    else "https://clinicaltrials.gov/"
                ),
                published_at=latest_update.isoformat() if latest_update else None,
                metadata={
                    "intervention_type": raw.get("intervention_type"),
                    "active_trial_count": trial_count,
                    "statuses": sorted(statuses),
                    "max_enrollment": max_enrollment,
                    "relationship_type": "lead_sponsor_association",
                    "sponsor_count_for_intervention": sponsor_count,
                },
            )
        )
    return results


def _acquirability_score(market_cap: Optional[float]) -> tuple[float, str]:
    if market_cap is None or market_cap <= 0:
        return 30.0, "market capitalization unavailable"
    billions = market_cap / 1_000_000_000
    if billions < 0.05:
        return 25.0, f"micro-cap market value (${billions:.2f}B)"
    if billions < 0.25:
        return 65.0, f"small acquisition size (${billions:.2f}B)"
    if billions < 2.0:
        return 100.0, f"highly financeable acquisition size (${billions:.2f}B)"
    if billions < 5.0:
        return 90.0, f"financeable acquisition size (${billions:.2f}B)"
    if billions < 10.0:
        return 72.0, f"large acquisition size (${billions:.1f}B)"
    if billions < 25.0:
        return 50.0, f"very large acquisition size (${billions:.1f}B)"
    if billions < 50.0:
        return 30.0, f"mega-deal-only size (${billions:.1f}B)"
    return 12.0, f"strategic-buyer-scale value (${billions:.1f}B)"


def evaluate_companies(
    companies: Iterable[PublicCompany],
    assets: Iterable[AssetEvaluation],
    evaluated_at: Optional[str] = None,
    announced_target_ciks: Optional[dict[int, list[dict[str, str]]]] = None,
) -> list[CompanyEvaluation]:
    evaluated_at = evaluated_at or utc_now_iso()
    announced_target_ciks = announced_target_ciks or {}
    assets_by_ticker: dict[str, list[AssetEvaluation]] = defaultdict(list)
    for asset in assets:
        if asset.owner_ticker:
            assets_by_ticker[asset.owner_ticker].append(asset)

    evaluations: list[CompanyEvaluation] = []
    for company in companies:
        company_assets = sorted(
            assets_by_ticker.get(company.ticker, []), key=lambda item: -item.score
        )
        top = company_assets[:3]
        if top:
            weights = (0.60, 0.25, 0.15)
            portfolio_score = sum(
                asset.score * weights[index] for index, asset in enumerate(top)
            )
            if len(top) == 1:
                portfolio_score = top[0].score
            elif len(top) == 2:
                portfolio_score = top[0].score * 0.70 + top[1].score * 0.30
        else:
            portfolio_score = 0.0

        approved = sum(
            asset.asset_type.startswith("approved") for asset in company_assets
        )
        clinical = sum(
            asset.asset_type == "clinical_pipeline" for asset in company_assets
        )
        late_stage = sum(
            asset.development_phase in {"phase3", "phase2|phase3", "approved"}
            for asset in company_assets
        )
        acquirability, cap_driver = _acquirability_score(company.market_cap_usd)
        focus_score = (
            70.0 if 1 <= len(company_assets) <= 8 else 50.0 if company_assets else 0.0
        )
        confidence = (
            min(
                100.0,
                20.0
                + sum(min(1.0, asset.owner_match_confidence) * 12 for asset in top),
            )
            if top
            else 10.0
        )
        research_score = (
            0.55 * portfolio_score
            + 0.30 * acquirability
            + 0.10 * focus_score
            + 0.05 * confidence
        )
        drivers = [cap_driver]
        if top:
            drivers.append(f"top asset: {top[0].asset_name} ({top[0].score:.1f})")
            drivers.append(
                f"{approved} approved and {clinical} active clinical assets matched"
            )
        else:
            drivers.append("no FDA Orange Book or active industry-trial asset matched")
        if late_stage:
            drivers.append(f"{late_stage} late-stage/approved matched assets")

        transaction_filings = announced_target_ciks.get(company.cik or -1, [])
        risk_set_eligible = not transaction_filings
        exclusion_reason = None
        if transaction_filings:
            latest = max(
                transaction_filings, key=lambda item: item.get("file_date", "")
            )
            exclusion_reason = (
                f"recent {latest.get('form', 'merger filing')} filed "
                f"{latest.get('file_date', 'date unavailable')}"
            )
            drivers.append(f"excluded from prediction risk set: {exclusion_reason}")

        evaluations.append(
            CompanyEvaluation(
                ticker=company.ticker,
                company_name=company.name,
                exchange=company.exchange,
                industry=company.industry,
                market_cap_usd=company.market_cap_usd,
                research_score=round(min(100.0, research_score), 2),
                portfolio_score=round(portfolio_score, 2),
                acquirability_score=round(acquirability, 2),
                data_confidence=round(confidence, 2),
                approved_asset_count=approved,
                clinical_asset_count=clinical,
                late_stage_asset_count=late_stage,
                top_assets=[asset.asset_name for asset in top],
                score_drivers=drivers,
                risk_set_eligible=risk_set_eligible,
                risk_set_exclusion_reason=exclusion_reason,
                model_version=MODEL_VERSION,
                evaluated_at=evaluated_at,
            )
        )

    evaluations.sort(key=lambda item: (-item.research_score, item.ticker))
    return evaluations
