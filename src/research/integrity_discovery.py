"""Official-source discovery helpers for study-integrity review candidates."""

from __future__ import annotations

import csv
import re
import time
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.research.sources import HttpCache
from src.research.matching import CompanyMatcher
from src.research.models import PublicCompany


NCBI_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_INTEGRITY_QUERY = (
    '"Retracted Publication"[Publication Type] OR '
    '"Expression of Concern"[Publication Type]'
)

GENERIC_ASSET_TERMS = {
    "active comparator",
    "best supportive care",
    "investigational product",
    "no intervention",
    "placebo",
    "standard of care",
    "treatment",
}

NON_DISTINCTIVE_TOKENS = {
    "chemotherapy",
    "control",
    "experimental",
    "group",
    "injection",
    "placebo",
    "saline",
    "vehicle",
}


def normalize_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def is_distinctive_asset_name(
    original: str, normalized: str, distinct_owner_count: int
) -> bool:
    """Keep terms useful for discovery while rejecting common interventions."""
    if (
        len(normalized) < 6
        or normalized in GENERIC_ASSET_TERMS
        or distinct_owner_count > 2
    ):
        return False
    tokens = normalized.split()
    if set(tokens) & NON_DISTINCTIVE_TOKENS:
        return False

    # Development codes such as EX-101 are usually high-specificity.
    if any(
        re.search(r"[a-z]", token, re.I) and re.search(r"\d", token)
        for token in re.findall(r"[A-Za-z0-9-]+", original)
    ):
        return True

    # Single non-code names must be long and unique in the market inventory.
    if len(tokens) == 1:
        return len(tokens[0]) >= 8 and distinct_owner_count == 1

    # Multiword names are permitted only when uncommon and reasonably specific.
    return len(normalized) >= 12


@dataclass(slots=True)
class MarketClinicalAsset:
    asset_id: str
    asset_name: str
    owner_name: str
    owner_ticker: str
    nct_id: str
    source_url: str
    owner_match_confidence: float = 0.0


@dataclass(slots=True)
class PublicationIntegrityRecord:
    pmid: str
    title: str
    abstract: str
    publication_types: list[str]
    nct_ids: list[str]
    journal: str
    publication_date: str

    @property
    def evidence_status(self) -> str:
        if "Retracted Publication" in self.publication_types:
            return "publication_retraction"
        return "unverified_anomaly"

    @property
    def category(self) -> str:
        if "Retracted Publication" in self.publication_types:
            return "publication_retraction"
        return "publication_expression_of_concern"


@dataclass(slots=True)
class PublicationAssetCandidate:
    pmid: str
    publication_title: str
    publication_types: list[str]
    publication_date: str
    journal: str
    evidence_status: str
    category: str
    matched_asset_id: str
    matched_asset_name: str
    owner_name: str
    owner_ticker: str
    owner_match_confidence: float
    nct_id: str
    match_method: str
    match_confidence: float
    source_url: str
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_market_clinical_assets(path: Path) -> list[MarketClinicalAsset]:
    assets: list[MarketClinicalAsset] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("asset_type") != "clinical_pipeline":
                continue
            assets.append(
                MarketClinicalAsset(
                    asset_id=row["asset_id"],
                    asset_name=row["asset_name"],
                    owner_name=row["owner_name"],
                    owner_ticker=row.get("owner_ticker", ""),
                    nct_id=row["source_id"].upper(),
                    source_url=row["source_url"],
                    owner_match_confidence=float(
                        row.get("owner_match_confidence") or 0.0
                    ),
                )
            )
    return assets


def load_market_companies(path: Path) -> list[PublicCompany]:
    companies: list[PublicCompany] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            market_cap = row.get("market_cap_usd")
            companies.append(
                PublicCompany(
                    ticker=row["ticker"],
                    name=row["company_name"],
                    exchange=row.get("exchange", ""),
                    industry=row.get("industry", ""),
                    market_cap_usd=float(market_cap) if market_cap else None,
                )
            )
    return companies


def _all_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def parse_pubmed_integrity_records(payload: bytes) -> list[PublicationIntegrityRecord]:
    root = ET.fromstring(payload)
    records: list[PublicationIntegrityRecord] = []
    for article in root.findall(".//PubmedArticle"):
        citation = article.find("MedlineCitation")
        if citation is None:
            continue
        article_data = citation.find("Article")
        if article_data is None:
            continue
        pmid = _all_text(citation.find("PMID"))
        title = _all_text(article_data.find("ArticleTitle"))
        abstract = " ".join(
            _all_text(node) for node in article_data.findall(".//AbstractText")
        ).strip()
        publication_types = sorted(
            {
                _all_text(node)
                for node in article_data.findall(".//PublicationType")
                if _all_text(node)
            }
        )
        nct_ids = {
            _all_text(node).upper()
            for node in citation.findall(
                ".//DataBank[DataBankName='ClinicalTrials.gov']"
                "/AccessionNumberList/AccessionNumber"
            )
            if re.fullmatch(r"NCT\d{8}", _all_text(node).upper())
        }
        nct_ids.update(
            value.upper()
            for value in re.findall(r"\bNCT\d{8}\b", f"{title} {abstract}", re.I)
        )
        journal = _all_text(article_data.find(".//Journal/Title"))
        pub_date = article_data.find(".//JournalIssue/PubDate")
        publication_date = " ".join(
            value
            for value in (
                _all_text(pub_date.find("Year")) if pub_date is not None else "",
                _all_text(pub_date.find("Month")) if pub_date is not None else "",
                _all_text(pub_date.find("Day")) if pub_date is not None else "",
            )
            if value
        )
        records.append(
            PublicationIntegrityRecord(
                pmid=pmid,
                title=title,
                abstract=abstract,
                publication_types=publication_types,
                nct_ids=sorted(nct_ids),
                journal=journal,
                publication_date=publication_date,
            )
        )
    return records


def fetch_pubmed_integrity_records(
    cache: HttpCache,
    *,
    max_records: int = 10_000,
    refresh: bool = False,
) -> tuple[int, list[PublicationIntegrityRecord]]:
    search_params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": PUBMED_INTEGRITY_QUERY,
            "retmode": "json",
            "retmax": 0,
            "sort": "pub date",
            "usehistory": "y",
        }
    )
    search = cache.get_json(
        f"{NCBI_ESEARCH_URL}?{search_params}",
        "pubmed_integrity_esearch_v2",
        refresh=refresh,
    )
    result = search.get("esearchresult") or {}
    total = int(result.get("count", 0))
    web_env = result.get("webenv")
    query_key = result.get("querykey")
    if not web_env or not query_key:
        return total, []

    records: list[PublicationIntegrityRecord] = []
    fetch_limit = min(total, max_records)
    batch_size = 500
    for start in range(0, fetch_limit, batch_size):
        fetch_params = urllib.parse.urlencode(
            {
                "db": "pubmed",
                "query_key": query_key,
                "WebEnv": web_env,
                "retstart": start,
                "retmax": min(batch_size, fetch_limit - start),
                "retmode": "xml",
                "rettype": "abstract",
            }
        )
        payload = cache.get_bytes(
            f"{NCBI_EFETCH_URL}?{fetch_params}",
            f"pubmed_integrity_efetch_{start:05d}",
            refresh=refresh,
            timeout=180,
        )
        records.extend(parse_pubmed_integrity_records(payload))
        if not cache.offline and start + batch_size < fetch_limit:
            time.sleep(0.35)
    return total, records


def fetch_registry_assets_for_publications(
    cache: HttpCache,
    publications: list[PublicationIntegrityRecord],
    companies: list[PublicCompany],
    *,
    refresh: bool = False,
) -> tuple[int, list[MarketClinicalAsset]]:
    """Resolve PubMed-reported NCT IDs to official registry sponsors/assets."""
    nct_ids = sorted({nct for row in publications for nct in row.nct_ids})
    matcher = CompanyMatcher(companies)
    assets: list[MarketClinicalAsset] = []
    for index, nct_id in enumerate(nct_ids):
        try:
            payload = cache.get_json(
                f"https://clinicaltrials.gov/api/v2/studies/{nct_id}",
                f"clinicaltrials_{nct_id}",
                refresh=refresh,
            )
        except FileNotFoundError:
            if cache.offline:
                continue
            raise
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        protocol = payload.get("protocolSection") or {}
        sponsor_module = protocol.get("sponsorCollaboratorsModule") or {}
        sponsor = (sponsor_module.get("leadSponsor") or {}).get("name", "")
        match = matcher.match(sponsor)
        interventions = (protocol.get("armsInterventionsModule") or {}).get(
            "interventions"
        ) or []
        intervention_names = list(
            dict.fromkeys(
                str(item.get("name", "")).strip()
                for item in interventions
                if str(item.get("name", "")).strip()
            )
        )
        asset_name = " / ".join(intervention_names[:5]) or nct_id
        assets.append(
            MarketClinicalAsset(
                asset_id=f"clinicaltrials:{nct_id}",
                asset_name=asset_name,
                owner_name=sponsor,
                owner_ticker=match.ticker or "",
                nct_id=nct_id,
                source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                owner_match_confidence=match.confidence,
            )
        )
        if not cache.offline and index + 1 < len(nct_ids):
            time.sleep(0.12)
    return len(nct_ids), assets


def match_publications_to_assets(
    publications: list[PublicationIntegrityRecord],
    assets: list[MarketClinicalAsset],
    *,
    include_name_matches: bool = False,
) -> list[PublicationAssetCandidate]:
    by_nct: dict[str, list[MarketClinicalAsset]] = {}
    by_first_token: dict[str, list[tuple[str, MarketClinicalAsset]]] = {}
    owners_by_term: dict[str, set[str]] = {}
    for asset in assets:
        by_nct.setdefault(asset.nct_id, []).append(asset)
        term = normalize_phrase(asset.asset_name)
        owners_by_term.setdefault(term, set()).add(asset.owner_name.casefold())

    indexed_owner_terms: set[tuple[str, str]] = set()
    for asset in assets:
        term = normalize_phrase(asset.asset_name)
        owner_key = asset.owner_name.casefold()
        if (term, owner_key) in indexed_owner_terms or not is_distinctive_asset_name(
            asset.asset_name, term, len(owners_by_term.get(term, set()))
        ):
            continue
        indexed_owner_terms.add((term, owner_key))
        by_first_token.setdefault(term.split()[0], []).append((term, asset))

    candidates: dict[tuple[str, str], PublicationAssetCandidate] = {}
    for publication in publications:
        for nct_id in publication.nct_ids:
            for asset in by_nct.get(nct_id, []):
                candidates[(publication.pmid, asset.asset_id)] = _candidate(
                    publication, asset, "nct_id", 1.0
                )

        if not include_name_matches:
            continue
        text = normalize_phrase(f"{publication.title} {publication.abstract}")
        padded = f" {text} "
        for token in set(text.split()):
            for term, asset in by_first_token.get(token, []):
                key = (publication.pmid, asset.asset_id)
                if key in candidates or f" {term} " not in padded:
                    continue
                phrase_key = (
                    publication.pmid,
                    f"term:{term}:{asset.owner_name.casefold()}",
                )
                if phrase_key in candidates:
                    continue
                candidate = _candidate(
                    publication, asset, "asset_name_exact_phrase", 0.70
                )
                candidate.matched_asset_id = ""
                candidate.nct_id = ""
                candidates[phrase_key] = candidate

    return sorted(
        candidates.values(),
        key=lambda row: (
            row.evidence_status != "publication_retraction",
            -row.match_confidence,
            row.owner_ticker,
            row.matched_asset_name,
            row.pmid,
        ),
    )


def _candidate(
    publication: PublicationIntegrityRecord,
    asset: MarketClinicalAsset,
    match_method: str,
    confidence: float,
) -> PublicationAssetCandidate:
    return PublicationAssetCandidate(
        pmid=publication.pmid,
        publication_title=publication.title,
        publication_types=publication.publication_types,
        publication_date=publication.publication_date,
        journal=publication.journal,
        evidence_status=publication.evidence_status,
        category=publication.category,
        matched_asset_id=asset.asset_id,
        matched_asset_name=asset.asset_name,
        owner_name=asset.owner_name,
        owner_ticker=asset.owner_ticker,
        owner_match_confidence=asset.owner_match_confidence,
        nct_id=asset.nct_id,
        match_method=match_method,
        match_confidence=confidence,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{publication.pmid}/",
        interpretation=(
            "Discovery candidate for human review. A retraction or expression "
            "of concern does not by itself establish sponsor misconduct or fraud."
        ),
    )
