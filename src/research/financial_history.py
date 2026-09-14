"""Point-in-time SEC financial facts, preserving accession-level availability."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.research.sources import HttpCache

FEATURE_NAMES = ["cash_usd", "assets_usd", "annual_operating_cashflow_usd", "annual_rd_usd", "annual_cash_burn_usd"]
FEATURE_UNITS = {name: "USD" if name in {"cash_usd", "assets_usd"} else "USD/fiscal_year" for name in FEATURE_NAMES}
CONCEPTS = {
    "cash_usd": [("us-gaap", "CashAndCashEquivalentsAtCarryingValue"), ("ifrs-full", "CashAndCashEquivalents")],
    "assets_usd": [("us-gaap", "Assets"), ("ifrs-full", "Assets")],
    "annual_operating_cashflow_usd": [("us-gaap", "NetCashProvidedByUsedInOperatingActivities"), ("ifrs-full", "CashFlowsFromUsedInOperatingActivities")],
    "annual_rd_usd": [("us-gaap", "ResearchAndDevelopmentExpense"), ("ifrs-full", "ResearchAndDevelopmentExpense")],
}
PERIODIC_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class FinancialSourceBlocked(ValueError):
    """A source request failed; its status receipt is not a financial fact."""

    def __init__(self, receipt: dict[str, Any]):
        self.receipt = receipt
        super().__init__(f"SEC source request blocked: HTTP {receipt['http_status']} at {receipt['url']}")


def parse_cutoff(value: str) -> datetime:
    """Date-only cutoffs mean UTC midnight at the start of the requested date."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("cutoff timestamps require a timezone")
    return parsed.astimezone(timezone.utc)


def require_sec_contact(user_agent: str) -> None:
    if not user_agent or not re.search(r"[^\s<>@]+@[^\s<>@]+\.[A-Za-z]{2,}", user_agent):
        raise ValueError("SEC network access requires explicit SEC_USER_AGENT with your real contact email")
    if any(term in user_agent.lower() for term in ("example.com", "example.org", "example.net", ".invalid", "your-email", "changeme")):
        raise ValueError("SEC_USER_AGENT must contain your actual contact, not a placeholder")


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def filing_availability(documents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Map original accessions to dated primary submissions entries and receipts."""
    result: dict[str, list[dict[str, Any]]] = {}
    for document in documents:
        payload = document["payload"]
        filings = payload.get("filings", {}).get("recent", payload)
        if not isinstance(filings, dict):
            raise ValueError("invalid SEC submissions filing arrays")
        accessions = filings.get("accessionNumber", [])
        for index, accession in enumerate(accessions):
            def item(name: str) -> Any:
                values = filings.get(name, [])
                return values[index] if isinstance(values, list) and index < len(values) else None
            if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                continue
            accepted = item("acceptanceDateTime")
            try:
                accepted_at = datetime.fromisoformat(str(accepted).replace("Z", "+00:00"))
                if accepted_at.tzinfo is None:
                    accepted_at = None
                else:
                    accepted_at = accepted_at.astimezone(timezone.utc)
            except ValueError:
                accepted_at = None
            result.setdefault(accession, []).append({
                "filing_date": _date(item("filingDate")), "accepted_at": accepted_at,
                "accepted_at_raw": accepted, "primary_document": item("primaryDocument"),
                "source": document["source"],
            })
    return result


def _available(fact: dict[str, Any], filing_date: date, mappings: dict[str, list[dict[str, Any]]]) -> tuple[datetime, dict[str, Any]]:
    midnight = datetime.combine(filing_date, datetime.min.time(), timezone.utc)
    public_availability_proxy = midnight + timedelta(hours=36)
    matches = [item for item in mappings.get(fact["accn"], [])
               if item["filing_date"] == filing_date and item["accepted_at"] is not None
               and midnight - timedelta(hours=14) <= item["accepted_at"] < midnight + timedelta(hours=36)]
    if matches:
        selected = max(matches, key=lambda item: item["accepted_at"])
        return max(public_availability_proxy, selected["accepted_at"]), {
            "availability_method": "filed_date_plus_36_hours_public_availability_proxy",
            "public_availability_measured": False,
            "submissions_source": selected["source"],
            "accepted_at": selected["accepted_at"].isoformat(),
            "acceptance_datetime_raw": selected["accepted_at_raw"],
            "primary_document": selected["primary_document"],
        }
    return public_availability_proxy, {
        "availability_method": "filed_date_plus_36_hours_public_availability_proxy",
        "public_availability_measured": False, "accepted_at": None,
        "submissions_source": None, "acceptance_datetime_raw": None,
        "primary_document": None,
    }


def extract_financial_snapshot(companyfacts: dict[str, Any], *, cik: int, cutoff: datetime,
                               companyfacts_source: dict[str, Any], submissions: list[dict[str, Any]]) -> dict[str, Any]:
    """Select facts that were actually filed by cutoff; never backfill later filings."""
    if cutoff.tzinfo is None:
        raise ValueError("cutoff requires timezone")
    cutoff = cutoff.astimezone(timezone.utc)
    if int(companyfacts.get("cik", -1)) != cik:
        raise ValueError("companyfacts CIK does not match requested issuer")
    mappings = filing_availability(submissions)
    features = {name: None for name in FEATURE_NAMES}
    provenance: dict[str, Any] = {}
    missing: dict[str, str] = {}
    used_availability = []
    facts = companyfacts.get("facts", {})
    for feature, concepts in CONCEPTS.items():
        candidates = []
        for priority, (taxonomy, concept) in enumerate(concepts):
            units = facts.get(taxonomy, {}).get(concept, {}).get("units", {})
            for fact in units.get("USD", []):
                accession = fact.get("accn")
                end, filed = _date(fact.get("end")), _date(fact.get("filed"))
                value = fact.get("val")
                if (not isinstance(accession, str) or not ACCESSION.fullmatch(accession)
                        or fact.get("form") not in PERIODIC_FORMS or end is None or filed is None
                        or end > cutoff.date() or filed < end
                        or not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)):
                    continue
                start = _date(fact.get("start"))
                duration = None
                if feature.startswith("annual_"):
                    if start is None:
                        continue
                    duration = (end - start).days + 1
                    if not 330 <= duration <= 400:
                        continue
                elif fact.get("start") not in (None, ""):
                    continue
                available_at, filing_evidence = _available(fact, filed, mappings)
                if available_at > cutoff:
                    continue
                candidates.append({"value": float(value), "concept": f"{taxonomy}:{concept}",
                                   "concept_priority": priority, "period_end": end.isoformat(),
                                   "period_start": start.isoformat() if start else None, "duration_days": duration,
                                   "accession_number": accession, "filed": filed.isoformat(), "form": fact["form"],
                                   "available_at": available_at.isoformat(), "unit": "USD",
                                   "companyfacts_source": companyfacts_source, **filing_evidence})
        if not candidates:
            missing[feature] = "no qualifying original-accession USD fact available by cutoff"
            provenance[feature] = None
            continue
        def rank(item: dict[str, Any]) -> tuple[Any, ...]:
            return item["period_end"], -item["concept_priority"], item["available_at"]
        best_rank = max(rank(item) for item in candidates)
        best = [item for item in candidates if rank(item) == best_rank]
        if len({(item["value"], item["period_start"]) for item in best}) != 1:
            missing[feature] = "conflicting values/periods at the same concept and availability; requires review"
            provenance[feature] = None
            continue
        selected = sorted(best, key=lambda item: item["accession_number"])[0]
        features[feature] = selected["value"]
        provenance[feature] = selected
        used_availability.append(parse_cutoff(selected["available_at"]))
    operating = features["annual_operating_cashflow_usd"]
    if operating is None:
        provenance["annual_cash_burn_usd"] = None
        missing["annual_cash_burn_usd"] = "annual operating cash flow unavailable"
    else:
        features["annual_cash_burn_usd"] = max(-operating, 0.0)
        provenance["annual_cash_burn_usd"] = {"derived_from": "annual_operating_cashflow_usd",
                                              "formula": "max(-annual_operating_cashflow_usd, 0)",
                                              "source_fact": provenance["annual_operating_cashflow_usd"]}
    return {"cik": cik, "information_cutoff_at": cutoff.isoformat(),
            "feature_max_available_at": max(used_availability).isoformat() if used_availability else None,
            "features": features, "fact_provenance": provenance, "missing_feature_reasons": missing}


def _fetch(cache: HttpCache, url: str, key: str, *, refresh: bool) -> dict[str, Any]:
    if not cache.offline:
        require_sec_contact(cache.user_agent)
    try:
        raw = cache.get_bytes(url, key, refresh=refresh)
    except urllib.error.HTTPError as exc:
        raise FinancialSourceBlocked({"url": url, "cache_key": key, "http_status": exc.code,
                                      "reason": str(exc.reason), "observed_at": datetime.now(timezone.utc).isoformat(),
                                      "financial_payload_received": False}) from exc
    digest = hashlib.sha256(raw).hexdigest()
    receipt = cache.source_snapshots.get(key)
    if not receipt or receipt.get("sha256") != digest:
        raise ValueError("SEC payload does not have a matching actual-byte cache receipt")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("SEC response must be a JSON object")
    return {"payload": payload, "source": {**receipt, "actual_bytes_sha256": digest}}


def collect_financial_history(ciks: list[int], cutoffs: list[datetime], cache: HttpCache, *,
                              refresh: bool = False, max_submission_files: int = 10,
                              now: datetime | None = None) -> dict[str, Any]:
    """Collect raw SEC receipts and features only; no risk-set or label invention."""
    if not ciks or any(not isinstance(cik, int) or isinstance(cik, bool) or cik <= 0 for cik in ciks):
        raise ValueError("at least one positive CIK required")
    if not isinstance(max_submission_files, int) or max_submission_files < 0:
        raise ValueError("max_submission_files must be nonnegative")
    current_time = now or datetime.now(timezone.utc)
    if not cutoffs or any(cutoff.tzinfo is None or cutoff > current_time for cutoff in cutoffs):
        raise ValueError("nonfuture timezone-aware financial cutoffs required")
    if not cache.offline:
        require_sec_contact(cache.user_agent)
    snapshots, receipts = [], {}
    for cik in sorted(set(ciks)):
        padded = f"{cik:010d}"
        documents = []
        facts = _fetch(cache, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json", f"sec_companyfacts_{padded}", refresh=refresh)
        receipts[facts["source"]["cache_key"]] = facts["source"]
        if not cache.offline:
            time.sleep(0.2)
        recent = _fetch(cache, f"https://data.sec.gov/submissions/CIK{padded}.json", f"sec_submissions_{padded}", refresh=refresh)
        if int(recent["payload"].get("cik", -1)) != cik:
            raise ValueError("submissions CIK does not match requested issuer")
        documents.append(recent)
        receipts[recent["source"]["cache_key"]] = recent["source"]
        archives = recent["payload"].get("filings", {}).get("files", [])
        if len(archives) > max_submission_files:
            raise ValueError(f"CIK {cik}: historical submissions exceed max_submission_files; explicitly raise limit")
        for archive in archives:
            name = archive.get("name", "")
            if not re.fullmatch(rf"CIK{padded}-submissions-\d+\.json", name):
                raise ValueError("unexpected SEC submissions archive name")
            if not cache.offline:
                time.sleep(0.2)
            document = _fetch(cache, f"https://data.sec.gov/submissions/{name}", name.removesuffix(".json"), refresh=refresh)
            documents.append(document)
            receipts[document["source"]["cache_key"]] = document["source"]
        for cutoff in sorted(set(cutoffs)):
            snapshots.append(extract_financial_snapshot(facts["payload"], cik=cik, cutoff=cutoff,
                                                        companyfacts_source=facts["source"], submissions=documents))
        if not cache.offline:
            time.sleep(0.2)
    return {"schema_version": "sec-financial-feature-snapshots-v1", "collected_at": (now or datetime.now(timezone.utc)).isoformat(),
            "feature_names": FEATURE_NAMES, "feature_units": FEATURE_UNITS, "observations": snapshots,
            "source_receipts": list(receipts.values()), "training_allowed": False,
            "semantics": "PIT feature inputs only; historical membership and reviewed complete outcome labels are not supplied",
            "coverage": {"issuers": len(set(ciks)), "snapshots": len(snapshots),
                         "snapshots_with_any_fact": sum(any(value is not None for value in row["features"].values()) for row in snapshots),
                         "observed_feature_counts": {name: sum(row["features"][name] is not None for row in snapshots) for name in FEATURE_NAMES}}}
