"""Live public-data sources for the market-wide biotech asset inventory."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import time
import urllib.parse
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from src.research.models import PublicCompany

logger = logging.getLogger(__name__)

NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FDA_ORANGE_BOOK_URL = "https://www.fda.gov/media/76860/download?attachment"
FDA_DRUGSFDA_URL = "https://www.fda.gov/media/89850/download?attachment"
CLINICAL_TRIALS_URL = "https://clinicaltrials.gov/api/v2/studies"
SEC_FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

BIOTECH_INDUSTRY_TERMS = (
    "biotechnology",
    "major pharmaceuticals",
    "pharmaceutical preparations",
    "medicinal chemicals",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_number(value: Any) -> Optional[float]:
    if value in (None, "", "N/A", "--"):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_fda_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%b %d, %Y", "%b %d %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


class HttpCache:
    """Small append-friendly HTTP cache that records raw payload hashes."""

    def __init__(self, root: Path, user_agent: str, offline: bool = False):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.offline = offline

    def _path(self, cache_key: str, suffix: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in cache_key)
        return self.root / f"{safe}.{suffix}"

    def get_bytes(
        self,
        url: str,
        cache_key: str,
        *,
        headers: Optional[dict[str, str]] = None,
        refresh: bool = False,
        timeout: int = 90,
        max_attempts: int = 4,
    ) -> bytes:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        payload_path = self._path(cache_key, "bin")
        if payload_path.exists() and (self.offline or not refresh):
            return payload_path.read_bytes()
        if self.offline:
            raise FileNotFoundError(f"Offline cache miss: {payload_path}")

        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json,*/*",
        }
        request_headers.update(headers or {})
        request = urllib.request.Request(url, headers=request_headers)
        response_headers: dict[str, str] = {}
        for attempt in range(1, max_attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                    response_headers = dict(response.headers.items())
                break
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if not retryable or attempt == max_attempts:
                    raise
                delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning(
                    "HTTP %s for %s; retrying in %.1fs (%d/%d)",
                    exc.code,
                    cache_key,
                    delay,
                    attempt,
                    max_attempts,
                )
                time.sleep(delay)
            except urllib.error.URLError:
                if attempt == max_attempts:
                    raise
                delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning(
                    "Network error for %s; retrying in %.1fs (%d/%d)",
                    cache_key,
                    delay,
                    attempt,
                    max_attempts,
                )
                time.sleep(delay)

        payload_path.write_bytes(payload)
        metadata = {
            "url": url,
            "retrieved_at": utc_now_iso(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "response_headers": response_headers,
        }
        self._path(cache_key, "meta.json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
        return payload

    def get_json(self, url: str, cache_key: str, **kwargs: Any) -> dict[str, Any]:
        return json.loads(self.get_bytes(url, cache_key, **kwargs))


def fetch_public_biotech_universe(
    cache: HttpCache, refresh: bool = False
) -> list[PublicCompany]:
    """Fetch U.S.-listed drug/biotech securities and enrich them with SEC CIKs."""
    params = urllib.parse.urlencode(
        {
            "tableonly": "true",
            "limit": 5000,
            "offset": 0,
            "sector": "Health Care",
            "download": "true",
        }
    )
    nasdaq = cache.get_json(
        f"{NASDAQ_SCREENER_URL}?{params}",
        "nasdaq_healthcare",
        headers={"User-Agent": "Mozilla/5.0 biotech-ma-research"},
        refresh=refresh,
    )
    sec = cache.get_json(
        SEC_TICKERS_URL, "sec_company_tickers_exchange", refresh=refresh
    )

    cik_by_ticker: dict[str, int] = {}
    fields = sec.get("fields", [])
    for record in sec.get("data", []):
        row = dict(zip(fields, record))
        ticker = str(row.get("ticker", "")).upper()
        if ticker:
            cik_by_ticker[ticker] = int(row["cik"])

    rows = (
        (nasdaq.get("data") or {}).get("rows")
        or (nasdaq.get("data") or {}).get("table", {}).get("rows")
        or []
    )
    companies: list[PublicCompany] = []
    for row in rows:
        name = str(row.get("name") or "")
        industry = str(row.get("industry") or "")
        ticker = str(row.get("symbol") or "").upper().strip()
        lower_industry = industry.lower()
        lower_name = name.lower()
        if not ticker or not any(
            term in lower_industry for term in BIOTECH_INDUSTRY_TERMS
        ):
            continue
        if any(term in lower_name for term in (" warrant", " right", " unit")):
            continue
        companies.append(
            PublicCompany(
                ticker=ticker,
                name=name,
                exchange="US-listed",
                industry=industry,
                market_cap_usd=parse_number(row.get("marketCap")),
                country=str(row.get("country") or ""),
                cik=cik_by_ticker.get(ticker.replace("/", "-")),
                source_url=f"https://www.nasdaq.com{row.get('url', '')}",
            )
        )

    companies.sort(key=lambda item: item.ticker)
    logger.info("Built public biotech universe with %d companies", len(companies))
    return companies


def fetch_recent_announced_target_ciks(
    cache: HttpCache,
    as_of: date,
    refresh: bool = False,
    lookback_days: int = 365,
) -> dict[int, list[dict[str, str]]]:
    """Find recent tender-offer and merger-proxy filers for risk-set exclusion.

    Intersecting these filings with the current listed universe catches pending
    transactions without downloading every company's full submission history.
    The records remain candidates for review; the output records why a company
    was conservatively excluded from the prediction risk set.
    """
    start_date = as_of - timedelta(days=lookback_days)
    results: dict[int, list[dict[str, str]]] = defaultdict(list)
    for form in ("SC 14D9", "DEFM14A"):
        offset = 0
        page_size = 100
        while True:
            params = urllib.parse.urlencode(
                {
                    "forms": form,
                    "startdt": start_date.isoformat(),
                    "enddt": as_of.isoformat(),
                    "from": offset,
                    "size": page_size,
                }
            )
            cache_key = (
                f"sec_efts_{form.replace(' ', '_')}_{start_date}_{as_of}_{offset:04d}"
            )
            payload = cache.get_json(
                f"{SEC_FULL_TEXT_SEARCH_URL}?{params}",
                cache_key,
                refresh=refresh,
            )
            hits = (payload.get("hits") or {}).get("hits", [])
            for hit in hits:
                source = hit.get("_source", {})
                record = {
                    "form": source.get("form", form),
                    "file_date": source.get("file_date", ""),
                    "accession_number": source.get("adsh", ""),
                    "display_name": "; ".join(source.get("display_names", [])),
                }
                for cik in source.get("ciks", []):
                    try:
                        results[int(cik)].append(record)
                    except (TypeError, ValueError):
                        continue
            total = int(
                ((payload.get("hits") or {}).get("total") or {}).get("value", 0)
            )
            offset += len(hits)
            if not hits or offset >= total:
                break
            if not cache.offline:
                time.sleep(0.11)

    logger.info("Found %d recent announced-transaction filer CIKs", len(results))
    return dict(results)


def fetch_sec_transaction_filings(
    cache: HttpCache,
    start_date: date,
    end_date: date,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch SEC tender-offer and merger-proxy filing hits.

    Queries are split by calendar year and form to keep every response below
    EDGAR full-text search result limits. The caller is responsible for
    classifying the filer and adjudicating the actual announcement date.
    """
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    results: dict[str, dict[str, Any]] = {}
    for year in range(start_date.year, end_date.year + 1):
        period_start = max(start_date, date(year, 1, 1))
        period_end = min(end_date, date(year, 12, 31))
        for form in ("SC 14D9", "DEFM14A"):
            offset = 0
            page_size = 100
            while True:
                params = urllib.parse.urlencode(
                    {
                        "forms": form,
                        "startdt": period_start.isoformat(),
                        "enddt": period_end.isoformat(),
                        "from": offset,
                        "size": page_size,
                    }
                )
                cache_key = (
                    f"sec_transaction_{form.replace(' ', '_')}_"
                    f"{period_start}_{period_end}_{offset:04d}"
                )
                payload = cache.get_json(
                    f"{SEC_FULL_TEXT_SEARCH_URL}?{params}",
                    cache_key,
                    refresh=refresh,
                )
                hits = (payload.get("hits") or {}).get("hits", [])
                for hit in hits:
                    hit_id = str(hit.get("_id") or "")
                    source = dict(hit.get("_source") or {})
                    if not hit_id or not source:
                        continue
                    source["_id"] = hit_id
                    results[hit_id] = source

                total = int(
                    ((payload.get("hits") or {}).get("total") or {}).get("value", 0)
                )
                offset += len(hits)
                if not hits or offset >= total:
                    break
                if not cache.offline:
                    time.sleep(0.11)

    filings = sorted(
        results.values(),
        key=lambda item: (item.get("file_date", ""), item.get("_id", "")),
    )
    logger.info(
        "Fetched %d SEC transaction filing documents from %s through %s",
        len(filings),
        start_date,
        end_date,
    )
    return filings


def fetch_sec_annual_report_filings(
    cache: HttpCache,
    start_year: int,
    end_year: int,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch annual-report filing hits for historical reporting-company risk sets.

    The filing metadata is later filtered to biotech SIC codes and Exchange Act
    file numbers. Annual reports provide a reproducible historical reporting
    population, but do not by themselves prove exchange listing on every
    observation date.
    """
    if end_year < start_year:
        raise ValueError("end_year must be on or after start_year")

    results: dict[str, dict[str, Any]] = {}
    for year in range(start_year, end_year + 1):
        for form in ("10-K", "20-F", "40-F"):
            offset = 0
            page_size = 100
            while True:
                params = urllib.parse.urlencode(
                    {
                        "forms": form,
                        "startdt": date(year, 1, 1).isoformat(),
                        "enddt": date(year, 12, 31).isoformat(),
                        "from": offset,
                        "size": page_size,
                    }
                )
                cache_key = f"sec_annual_report_{form}_{year}_{offset:04d}"
                payload = cache.get_json(
                    f"{SEC_FULL_TEXT_SEARCH_URL}?{params}",
                    cache_key,
                    refresh=refresh,
                )
                hits = (payload.get("hits") or {}).get("hits", [])
                for hit in hits:
                    hit_id = str(hit.get("_id") or "")
                    source = dict(hit.get("_source") or {})
                    if not hit_id or not source:
                        continue
                    source["_id"] = hit_id
                    results[hit_id] = source

                total = int(
                    ((payload.get("hits") or {}).get("total") or {}).get("value", 0)
                )
                offset += len(hits)
                if not hits or offset >= total:
                    break
                if not cache.offline:
                    time.sleep(0.11)

    filings = sorted(
        results.values(),
        key=lambda item: (item.get("file_date", ""), item.get("_id", "")),
    )
    logger.info(
        "Fetched %d annual-report documents from %d through %d",
        len(filings),
        start_year,
        end_year,
    )
    return filings


def _read_tilde_file(archive: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    with archive.open(filename) as raw:
        wrapper = io.TextIOWrapper(
            raw, encoding="utf-8-sig", errors="replace", newline=""
        )
        return list(csv.DictReader(wrapper, delimiter="~"))


def _read_tab_file(archive: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    with archive.open(filename) as raw:
        wrapper = io.TextIOWrapper(
            raw, encoding="utf-8-sig", errors="replace", newline=""
        )
        return list(csv.DictReader(wrapper, delimiter="\t"))


def fetch_orange_book_assets(
    cache: HttpCache, refresh: bool = False
) -> list[dict[str, Any]]:
    """Return every current Orange Book ingredient/applicant asset with IP dates."""
    payload = cache.get_bytes(FDA_ORANGE_BOOK_URL, "fda_orange_book", refresh=refresh)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        products = _read_tilde_file(archive, "products.txt")
        patents = _read_tilde_file(archive, "patent.txt")
        exclusivities = _read_tilde_file(archive, "exclusivity.txt")

    patent_by_application: dict[tuple[str, str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for patent in patents:
        key = (patent["Appl_Type"], patent["Appl_No"], patent["Product_No"])
        patent_by_application[key].append(patent)

    exclusivity_by_application: dict[tuple[str, str, str], list[dict[str, str]]] = (
        defaultdict(list)
    )
    for exclusivity in exclusivities:
        key = (
            exclusivity["Appl_Type"],
            exclusivity["Appl_No"],
            exclusivity["Product_No"],
        )
        exclusivity_by_application[key].append(exclusivity)

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    ingredient_applicants: dict[str, set[str]] = defaultdict(set)
    for product in products:
        if product.get("Type", "").upper() == "DISCN":
            continue
        ingredient = product.get("Ingredient", "").strip()
        applicant = (
            product.get("Applicant_Full_Name") or product.get("Applicant") or ""
        ).strip()
        if not ingredient or not applicant:
            continue
        ingredient_applicants[ingredient].add(applicant)
        group = grouped.setdefault(
            (ingredient, applicant),
            {
                "ingredient": ingredient,
                "applicant": applicant,
                "trade_names": set(),
                "routes": set(),
                "application_numbers": set(),
                "application_types": set(),
                "approval_dates": [],
                "is_reference_drug": False,
                "patent_expiries": [],
                "exclusivity_expiries": [],
                "patent_numbers": set(),
                "product_rows": 0,
            },
        )
        group["product_rows"] += 1
        group["trade_names"].add(product.get("Trade_Name", "").strip())
        group["routes"].add(product.get("DF;Route", "").strip())
        group["application_numbers"].add(product.get("Appl_No", "").strip())
        group["application_types"].add(product.get("Appl_Type", "").strip())
        group["is_reference_drug"] = (
            group["is_reference_drug"] or product.get("RLD") == "Yes"
        )
        approval_date = parse_fda_date(product.get("Approval_Date", ""))
        if approval_date:
            group["approval_dates"].append(approval_date)

        app_key = (
            product.get("Appl_Type", ""),
            product.get("Appl_No", ""),
            product.get("Product_No", ""),
        )
        for patent in patent_by_application.get(app_key, []):
            expiry = parse_fda_date(patent.get("Patent_Expire_Date_Text", ""))
            if expiry:
                group["patent_expiries"].append(expiry)
            if patent.get("Patent_No"):
                group["patent_numbers"].add(patent["Patent_No"])
        for exclusivity in exclusivity_by_application.get(app_key, []):
            expiry = parse_fda_date(exclusivity.get("Exclusivity_Date", ""))
            if expiry:
                group["exclusivity_expiries"].append(expiry)

    assets: list[dict[str, Any]] = []
    for group in grouped.values():
        ingredient = group["ingredient"]
        assets.append(
            {
                **group,
                "trade_names": sorted(name for name in group["trade_names"] if name),
                "routes": sorted(route for route in group["routes"] if route),
                "application_numbers": sorted(
                    number for number in group["application_numbers"] if number
                ),
                "application_types": sorted(
                    value for value in group["application_types"] if value
                ),
                "approval_dates": sorted(group["approval_dates"]),
                "patent_expiries": sorted(group["patent_expiries"]),
                "exclusivity_expiries": sorted(group["exclusivity_expiries"]),
                "patent_numbers": sorted(group["patent_numbers"]),
                "applicant_count_for_ingredient": len(
                    ingredient_applicants[ingredient]
                ),
            }
        )
    assets.sort(key=lambda item: (item["ingredient"], item["applicant"]))
    logger.info(
        "Parsed %d current Orange Book ingredient/applicant assets", len(assets)
    )
    return assets


def fetch_drugsfda_biologic_assets(
    cache: HttpCache, refresh: bool = False
) -> list[dict[str, Any]]:
    """Return currently marketed BLA ingredient/sponsor assets from Drugs@FDA."""
    payload = cache.get_bytes(FDA_DRUGSFDA_URL, "fda_drugsfda", refresh=refresh)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        applications = _read_tab_file(archive, "Applications.txt")
        products = _read_tab_file(archive, "Products.txt")
        statuses = _read_tab_file(archive, "MarketingStatus.txt")

    sponsor_by_application = {
        row["ApplNo"]: row.get("SponsorName", "").strip()
        for row in applications
        if row.get("ApplType") == "BLA" and row.get("SponsorName", "").strip()
    }
    marketed = {
        (row.get("ApplNo", ""), row.get("ProductNo", ""))
        for row in statuses
        if row.get("MarketingStatusID") in {"1", "2", "5"}
    }

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    sponsors_by_ingredient: dict[str, set[str]] = defaultdict(set)
    for product in products:
        application_number = product.get("ApplNo", "")
        product_number = product.get("ProductNo", "")
        sponsor = sponsor_by_application.get(application_number)
        if not sponsor or (application_number, product_number) not in marketed:
            continue
        ingredient = (
            product.get("ActiveIngredient") or product.get("DrugName") or ""
        ).strip()
        if not ingredient:
            continue
        sponsors_by_ingredient[ingredient].add(sponsor)
        group = grouped.setdefault(
            (ingredient, sponsor),
            {
                "ingredient": ingredient,
                "sponsor": sponsor,
                "trade_names": set(),
                "forms": set(),
                "application_numbers": set(),
                "is_reference_drug": False,
                "product_rows": 0,
            },
        )
        group["product_rows"] += 1
        group["trade_names"].add(product.get("DrugName", "").strip())
        group["forms"].add(product.get("Form", "").strip())
        group["application_numbers"].add(application_number)
        group["is_reference_drug"] = (
            group["is_reference_drug"] or product.get("ReferenceDrug") == "1"
        )

    assets: list[dict[str, Any]] = []
    for group in grouped.values():
        assets.append(
            {
                **group,
                "trade_names": sorted(value for value in group["trade_names"] if value),
                "forms": sorted(value for value in group["forms"] if value),
                "application_numbers": sorted(group["application_numbers"]),
                "sponsor_count_for_ingredient": len(
                    sponsors_by_ingredient[group["ingredient"]]
                ),
            }
        )
    assets.sort(key=lambda item: (item["ingredient"], item["sponsor"]))
    logger.info(
        "Parsed %d currently marketed BLA ingredient/sponsor assets", len(assets)
    )
    return assets


def _iter_clinical_pages(
    cache: HttpCache,
    refresh: bool,
    max_studies: Optional[int],
) -> Iterable[dict[str, Any]]:
    page_token: Optional[str] = None
    fetched = 0
    page_number = 0
    while max_studies is None or fetched < max_studies:
        page_size = min(
            1000, (max_studies - fetched) if max_studies is not None else 1000
        )
        params = {
            "query.term": "AREA[StudyType]INTERVENTIONAL AND AREA[LeadSponsorClass]INDUSTRY",
            "filter.overallStatus": "RECRUITING|NOT_YET_RECRUITING|ACTIVE_NOT_RECRUITING|ENROLLING_BY_INVITATION",
            "fields": (
                "NCTId,BriefTitle,OfficialTitle,OverallStatus,Phase,Condition,Intervention,"
                "LeadSponsorName,LeadSponsorClass,CollaboratorName,EnrollmentCount,"
                "EnrollmentType,StartDate,PrimaryCompletionDate,CompletionDate,LastUpdatePostDate"
            ),
            "format": "json",
            "pageSize": str(page_size),
            "countTotal": "true" if page_number == 0 else "false",
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{CLINICAL_TRIALS_URL}?{urllib.parse.urlencode(params)}"
        cache_key = f"clinical_trials_active_page_{page_number:04d}"
        page = cache.get_json(url, cache_key, refresh=refresh)
        studies = page.get("studies", [])
        if not studies:
            break
        yield from studies
        fetched += len(studies)
        page_token = page.get("nextPageToken")
        page_number += 1
        if not page_token:
            break
        if not cache.offline:
            time.sleep(0.05)


def fetch_active_clinical_assets(
    cache: HttpCache,
    refresh: bool = False,
    max_studies: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Collapse active industry-sponsored trials into sponsor/intervention assets."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_types = {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT", "GENETIC"}
    excluded_terms = {
        "placebo",
        "standard of care",
        "best supportive care",
        "no intervention",
        "chemotherapy regimen",
        "investigator's choice",
        "investigator choice",
        "usual care",
        "radiotherapy",
        "radiation therapy",
        "saline",
    }

    for study in _iter_clinical_pages(cache, refresh, max_studies):
        protocol = study.get("protocolSection", {})
        identity = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        conditions = protocol.get("conditionsModule", {}).get("conditions", [])
        design = protocol.get("designModule", {})
        interventions = protocol.get("armsInterventionsModule", {}).get(
            "interventions", []
        )
        sponsor = sponsor_module.get("leadSponsor", {}).get("name", "").strip()
        nct_id = identity.get("nctId", "")
        if not sponsor or not nct_id:
            continue
        phases = design.get("phases", []) or ["NA"]
        enrollment = (design.get("enrollmentInfo") or {}).get("count")
        last_update = (status.get("lastUpdatePostDateStruct") or {}).get("date")

        for intervention in interventions:
            intervention_type = intervention.get("type", "").upper()
            name = intervention.get("name", "").strip()
            lower_name = name.lower()
            if (
                intervention_type not in allowed_types
                or not name
                or any(term in lower_name for term in excluded_terms)
            ):
                continue
            key = (sponsor.upper(), name.upper())
            asset = grouped.setdefault(
                key,
                {
                    "name": name,
                    "sponsor": sponsor,
                    "intervention_type": intervention_type,
                    "nct_ids": set(),
                    "phases": set(),
                    "conditions": set(),
                    "statuses": set(),
                    "last_updates": [],
                    "enrollments": [],
                    "trial_count": 0,
                },
            )
            asset["trial_count"] += 1
            asset["nct_ids"].add(nct_id)
            asset["phases"].update(phases)
            asset["conditions"].update(conditions)
            asset["statuses"].add(status.get("overallStatus", ""))
            if last_update:
                asset["last_updates"].append(last_update)
            if isinstance(enrollment, int):
                asset["enrollments"].append(enrollment)

    sponsors_by_intervention: dict[str, set[str]] = defaultdict(set)
    for asset in grouped.values():
        normalized_name = " ".join(asset["name"].upper().split())
        sponsors_by_intervention[normalized_name].add(asset["sponsor"])

    assets: list[dict[str, Any]] = []
    for asset in grouped.values():
        normalized_name = " ".join(asset["name"].upper().split())
        assets.append(
            {
                **asset,
                "nct_ids": sorted(asset["nct_ids"]),
                "phases": sorted(asset["phases"]),
                "conditions": sorted(asset["conditions"]),
                "statuses": sorted(value for value in asset["statuses"] if value),
                "last_updates": sorted(asset["last_updates"]),
                "enrollments": sorted(asset["enrollments"]),
                "sponsor_count_for_intervention": len(
                    sponsors_by_intervention[normalized_name]
                ),
            }
        )
    assets.sort(key=lambda item: (item["sponsor"], item["name"]))
    logger.info("Parsed %d active sponsor/intervention clinical assets", len(assets))
    return assets
