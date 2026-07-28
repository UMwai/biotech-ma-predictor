"""Conservative organization-to-public-company entity matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Optional

from src.research.models import PublicCompany

_SECURITY_WORDS = {
    "COMMON",
    "STOCK",
    "SHARES",
    "SHARE",
    "ADS",
    "ADR",
    "DEPOSITARY",
    "ORDINARY",
    "AMERICAN",
    "BENEFICIAL",
    "INTEREST",
    "INTERESTS",
    "CLASS",
    "A",
    "B",
    "C",
    "UNITS",
    "UNIT",
}
_CORPORATE_WORDS = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LTD",
    "LIMITED",
    "LLC",
    "LP",
    "PLC",
    "NV",
    "SA",
    "AG",
    "SE",
    "BV",
    "HOLDING",
    "HOLDINGS",
    "GROUP",
    "THE",
}


def normalize_organization(value: str) -> str:
    """Normalize legal and security names without guessing corporate identity."""
    ascii_value = (
        unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    )
    ascii_value = ascii_value.upper().replace("&", " AND ")
    tokens = re.findall(r"[A-Z0-9]+", ascii_value)
    while tokens and tokens[-1] in _SECURITY_WORDS | _CORPORATE_WORDS:
        tokens.pop()
    tokens = [token for token in tokens if token not in _SECURITY_WORDS]
    while tokens and tokens[-1] in _CORPORATE_WORDS:
        tokens.pop()
    return " ".join(tokens)


@dataclass(frozen=True, slots=True)
class OrganizationMatch:
    ticker: Optional[str]
    confidence: float
    method: str


class CompanyMatcher:
    """Match source sponsor/applicant names to listed companies conservatively."""

    def __init__(self, companies: Iterable[PublicCompany]):
        self.companies = list(companies)
        self._normalized: dict[str, list[PublicCompany]] = {}
        for company in self.companies:
            key = normalize_organization(company.name)
            if key:
                self._normalized.setdefault(key, []).append(company)

    def match(self, organization: str) -> OrganizationMatch:
        key = normalize_organization(organization)
        if not key:
            return OrganizationMatch(None, 0.0, "empty")

        exact = self._normalized.get(key, [])
        if len(exact) == 1:
            return OrganizationMatch(exact[0].ticker, 1.0, "normalized_exact")
        if len(exact) > 1:
            return OrganizationMatch(None, 0.0, "ambiguous_exact")

        key_tokens = set(key.split())
        candidates: list[tuple[float, PublicCompany]] = []
        for company_key, companies in self._normalized.items():
            company_tokens = set(company_key.split())
            if not company_tokens:
                continue
            overlap = key_tokens & company_tokens
            union = key_tokens | company_tokens
            jaccard = len(overlap) / len(union)
            containment = len(overlap) / min(len(key_tokens), len(company_tokens))
            if len(overlap) >= 2 and containment == 1.0 and jaccard >= 0.60:
                for company in companies:
                    candidates.append((0.90, company))
            elif len(overlap) >= 2 and jaccard >= 0.75:
                for company in companies:
                    candidates.append((0.82, company))

        if not candidates:
            return OrganizationMatch(None, 0.0, "unmatched")
        candidates.sort(key=lambda item: (-item[0], item[1].ticker))
        best_score = candidates[0][0]
        best = {item[1].ticker for item in candidates if item[0] == best_score}
        if len(best) != 1:
            return OrganizationMatch(None, 0.0, "ambiguous_fuzzy")
        return OrganizationMatch(candidates[0][1].ticker, best_score, "token_match")
