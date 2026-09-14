"""Build a conservative, auditable biotech transaction-candidate ledger."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from src.research.models import DealCandidate

# Drug manufacturing and commercial biological research. SIC 8731 is retained
# as a reviewable expansion because some development-stage issuers file there.
BIOTECH_SIC_CODES = {"2833", "2834", "2835", "2836", "8731"}

_CIK_SUFFIX = re.compile(r"\s*\(CIK\s+\d+\)\s*$", re.IGNORECASE)
_TICKER_GROUP = re.compile(r"\(([^()]*)\)\s*$")
_TICKER_TOKEN = re.compile(r"^[A-Z][A-Z0-9./-]{0,9}$")


def _stable_candidate_id(cik: int, signal_date: date) -> str:
    payload = f"sec-deal-candidate|{cik}|{signal_date.isoformat()}".encode()
    return hashlib.sha256(payload).hexdigest()[:20]


def parse_sec_display_name(display_names: Iterable[str]) -> tuple[str, list[str]]:
    """Extract the issuer name and any current ticker tokens from EFTS text."""
    display_name = next((value.strip() for value in display_names if value.strip()), "")
    without_cik = _CIK_SUFFIX.sub("", display_name).strip()
    ticker_match = _TICKER_GROUP.search(without_cik)
    tickers: list[str] = []
    if ticker_match:
        candidates = [
            token.strip().upper() for token in ticker_match.group(1).split(",")
        ]
        if candidates and all(_TICKER_TOKEN.fullmatch(token) for token in candidates):
            tickers = candidates
            without_cik = without_cik[: ticker_match.start()].strip()
    return without_cik, tickers


def sec_archive_url(cik: int, accession_number: str, hit_id: str) -> str:
    """Build a primary-document EDGAR Archives URL from an EFTS result."""
    accession_path = accession_number.replace("-", "")
    primary_document = hit_id.split(":", 1)[1] if ":" in hit_id else ""
    if not accession_path or not primary_document:
        return ""
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
        f"{accession_path}/{primary_document}"
    )


def _filing_cik(source: dict[str, Any]) -> int | None:
    ciks = source.get("ciks") or []
    if not ciks:
        return None
    try:
        return int(ciks[0])
    except (TypeError, ValueError):
        return None


def _is_biotech_filing(source: dict[str, Any]) -> bool:
    return bool(
        BIOTECH_SIC_CODES.intersection(str(value) for value in source.get("sics", []))
    )


def build_deal_candidates(
    filings: Iterable[dict[str, Any]],
    *,
    cluster_gap_days: int = 240,
) -> list[DealCandidate]:
    """Collapse related SEC filings into reviewable issuer/event candidates.

    A Schedule 14D-9 is filed by the subject company of a tender offer, so it
    receives high provisional target confidence. A DEFM14A alone remains a
    review-required merger-proxy signal and is never model-label eligible.
    Neither class receives an announcement date until a reviewer verifies it.
    """
    if cluster_gap_days < 1:
        raise ValueError("cluster_gap_days must be positive")

    by_cik: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for source in filings:
        cik = _filing_cik(source)
        raw_date = str(source.get("file_date") or "")
        if cik is None or not _is_biotech_filing(source):
            continue
        try:
            filing_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        item = dict(source)
        item["_parsed_date"] = filing_date
        by_cik[cik].append(item)

    clusters: list[tuple[int, list[dict[str, Any]]]] = []
    for cik, issuer_filings in by_cik.items():
        issuer_filings.sort(
            key=lambda item: (item["_parsed_date"], item.get("_id", ""))
        )
        current: list[dict[str, Any]] = []
        for filing in issuer_filings:
            if (
                current
                and (filing["_parsed_date"] - current[-1]["_parsed_date"]).days
                > cluster_gap_days
            ):
                clusters.append((cik, current))
                current = []
            current.append(filing)
        if current:
            clusters.append((cik, current))

    candidates: list[DealCandidate] = []
    for cik, cluster in clusters:
        first_date = cluster[0]["_parsed_date"]
        last_date = cluster[-1]["_parsed_date"]
        forms = sorted(
            {str(item.get("form") or "") for item in cluster if item.get("form")}
        )
        has_14d9 = any(form.upper() == "SC 14D9" for form in forms)
        filer_name, tickers = parse_sec_display_name(
            cluster[0].get("display_names") or []
        )
        accessions = sorted(
            {str(item.get("adsh") or "") for item in cluster if item.get("adsh")}
        )
        urls = sorted(
            {
                url
                for item in cluster
                if (
                    url := sec_archive_url(
                        cik, str(item.get("adsh") or ""), str(item.get("_id") or "")
                    )
                )
            }
        )
        sic_codes = sorted(
            {
                str(sic)
                for item in cluster
                for sic in item.get("sics", [])
                if str(sic) in BIOTECH_SIC_CODES
            }
        )

        if has_14d9:
            event_class = "tender_offer_target"
            confidence = "high"
            adjudication_status = "provisional_primary_source"
            model_label_eligible = False
            notes = (
                "Schedule 14D-9 identifies the tender-offer subject company. "
                "Verify the first public announcement date and exclude non-control offers "
                "before promoting this candidate to a training label."
            )
        else:
            event_class = "merger_proxy_filer"
            confidence = "review_required"
            adjudication_status = "pending_review"
            model_label_eligible = False
            notes = (
                "DEFM14A indicates merger-related proxy material, but the filer may be "
                "a target, buyer, SPAC, or reverse-merger participant. Manual review required."
            )

        candidates.append(
            DealCandidate(
                candidate_id=_stable_candidate_id(cik, first_date),
                target_cik=cik,
                filer_name=filer_name,
                filer_tickers=tickers,
                sic_codes=sic_codes,
                sec_signal_date=first_date.isoformat(),
                last_related_filing_date=last_date.isoformat(),
                event_class=event_class,
                confidence=confidence,
                adjudication_status=adjudication_status,
                model_label_eligible=model_label_eligible,
                filing_forms=forms,
                accession_numbers=accessions,
                primary_source_urls=urls,
                filing_count=len(cluster),
                review_notes=notes,
            )
        )

    return sorted(candidates, key=lambda item: (item.sec_signal_date, item.target_cik))


def build_annual_risk_set(
    annual_report_filings: Iterable[dict[str, Any]],
    deal_candidates: Iterable[DealCandidate],
    *,
    data_end_date: date,
    horizon_days: int = 365,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build annual historical reporting-company rows and exclusions.

    The observation date is December 31 of the annual-report filing year. An
    issuer must have filed a 10-K, 20-F, or 40-F with a biotech SIC and an
    Exchange Act file number beginning ``001-`` during that year. This avoids a
    current-survivor universe, but remains a reporting-company proxy rather than
    a fully reconstructed exchange membership history.

    Outcomes are explicitly provisional SEC signals. They are suitable for
    measuring candidate incidence, not for fitting or evaluating a probability
    model until event dates and roles are adjudicated.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")

    latest_by_year_cik: dict[tuple[int, int], dict[str, Any]] = {}
    for source in annual_report_filings:
        cik = _filing_cik(source)
        raw_date = str(source.get("file_date") or "")
        if cik is None or not _is_biotech_filing(source):
            continue
        file_numbers = [str(value) for value in source.get("file_num", [])]
        if not any(value.startswith("001-") for value in file_numbers):
            continue
        try:
            filing_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        key = (filing_date.year, cik)
        prior = latest_by_year_cik.get(key)
        if prior is None or raw_date > str(prior.get("file_date") or ""):
            latest_by_year_cik[key] = source

    candidates_by_cik: dict[int, list[DealCandidate]] = defaultdict(list)
    for candidate in deal_candidates:
        candidates_by_cik[candidate.target_cik].append(candidate)
    for values in candidates_by_cik.values():
        values.sort(key=lambda item: item.sec_signal_date)

    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for (filing_year, cik), source in sorted(latest_by_year_cik.items()):
        observation_date = date(filing_year, 12, 31)
        horizon_end = observation_date + timedelta(days=horizon_days)
        issuer_candidates = candidates_by_cik.get(cik, [])
        cooldown_start = observation_date - timedelta(days=horizon_days)
        prior_signal = next(
            (
                item
                for item in reversed(issuer_candidates)
                if cooldown_start
                < date.fromisoformat(item.sec_signal_date)
                <= observation_date
            ),
            None,
        )
        filer_name, tickers = parse_sec_display_name(source.get("display_names") or [])
        if prior_signal is not None:
            exclusions.append(
                {
                    "observation_date": observation_date.isoformat(),
                    "cik": cik,
                    "company_name": filer_name,
                    "ticker_candidates": tickers,
                    "reason": (
                        f"transaction candidate signal {prior_signal.candidate_id} "
                        f"on {prior_signal.sec_signal_date}"
                    ),
                }
            )
            continue

        forward_candidates = [
            item
            for item in issuer_candidates
            if observation_date
            < date.fromisoformat(item.sec_signal_date)
            <= horizon_end
        ]
        tender_candidates = [
            item
            for item in forward_candidates
            if item.event_class == "tender_offer_target"
        ]
        rows.append(
            {
                "observation_date": observation_date.isoformat(),
                "horizon_end": horizon_end.isoformat(),
                "outcome_window_complete": horizon_end <= data_end_date,
                "cik": cik,
                "company_name": filer_name,
                "ticker_candidates": tickers,
                "sic_codes": sorted(
                    {
                        str(value)
                        for value in source.get("sics", [])
                        if str(value) in BIOTECH_SIC_CODES
                    }
                ),
                "annual_report_form": source.get("form", ""),
                "annual_report_filed": source.get("file_date", ""),
                "annual_report_accession": source.get("adsh", ""),
                "provisional_tender_offer_signal_within_horizon": bool(
                    tender_candidates
                ),
                "provisional_any_transaction_signal_within_horizon": bool(
                    forward_candidates
                ),
                "forward_candidate_ids": [
                    item.candidate_id for item in forward_candidates
                ],
                "model_label_eligible": False,
            }
        )

    return rows, exclusions


def validate_candidate_ledger(candidates: Iterable[DealCandidate]) -> dict[str, int]:
    """Fail closed on structural defects before publishing candidate artifacts."""
    materialized = list(candidates)
    candidate_ids: set[str] = set()
    cik_dates: set[tuple[int, str]] = set()
    for item in materialized:
        if item.candidate_id in candidate_ids:
            raise ValueError(f"duplicate candidate_id: {item.candidate_id}")
        candidate_ids.add(item.candidate_id)
        cik_date = (item.target_cik, item.sec_signal_date)
        if cik_date in cik_dates:
            raise ValueError(f"duplicate CIK/signal date: {cik_date}")
        cik_dates.add(cik_date)
        if not item.filer_name:
            raise ValueError(f"missing filer name: {item.candidate_id}")
        if not item.primary_source_urls:
            raise ValueError(f"missing primary source URL: {item.candidate_id}")
        if item.model_label_eligible:
            raise ValueError(
                "unadjudicated SEC candidates cannot be model-label eligible: "
                f"{item.candidate_id}"
            )
    return {
        "rows": len(materialized),
        "unique_candidate_ids": len(candidate_ids),
        "unique_cik_signal_dates": len(cik_dates),
    }
