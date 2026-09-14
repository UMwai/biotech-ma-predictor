"""Synthetic SEC payloads test PIT selection; no live requests are made."""

import hashlib
import io
import json
import urllib.error
from datetime import datetime, timezone

import pytest

from scripts.collect_historical_financials import load_ciks, main
from src.research.financial_history import collect_financial_history, extract_financial_snapshot, parse_cutoff
from src.research.sources import HttpCache

CIK = 1234
ORIGINAL = "0000001234-21-000001"
RESTATED = "0000001234-22-000001"


def fact(value, *, accession=ORIGINAL, filed="2021-02-01", start=None, end="2020-12-31"):
    result = {"val": value, "accn": accession, "filed": filed, "end": end, "form": "10-K"}
    if start:
        result["start"] = start
    return result


def payload():
    return {"cik": CIK, "facts": {"us-gaap": {
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [fact(100), fact(999, accession=RESTATED, filed="2022-03-01")]}},
        "Assets": {"units": {"USD": [fact(1000)]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [fact(-40, start="2020-01-01"), fact(-5, start="2020-10-01")]}},
        "ResearchAndDevelopmentExpense": {"units": {"USD": [fact(0, start="2020-01-01")]}},
    }}}


def submissions(accepted="2021-02-01T15:00:00Z"):
    return [{"payload": {"accessionNumber": [ORIGINAL], "filingDate": ["2021-02-01"],
                          "acceptanceDateTime": [accepted], "primaryDocument": ["annual.htm"]},
             "source": {"sha256": "b" * 64, "url": "synthetic://submissions"}}]


def extract(data=None, cutoff="2021-02-02T12:00:00Z", docs=None):
    return extract_financial_snapshot(data or payload(), cik=CIK, cutoff=parse_cutoff(cutoff),
                                      companyfacts_source={"sha256": "a" * 64, "url": "synthetic://companyfacts"},
                                      submissions=submissions() if docs is None else docs)


def test_acceptance_is_retained_but_public_availability_uses_conservative_proxy():
    before = extract(cutoff="2021-02-01T14:59:59Z")
    assert before["features"]["cash_usd"] is None
    after_acceptance = extract(cutoff="2021-02-01T16:00:00Z")
    assert after_acceptance["features"]["cash_usd"] is None
    assert extract(cutoff="2021-02-02T11:59:59Z")["features"]["cash_usd"] is None
    known = extract()
    assert known["features"]["cash_usd"] == 100
    assert known["fact_provenance"]["cash_usd"]["accession_number"] == ORIGINAL
    assert known["fact_provenance"]["cash_usd"]["submissions_source"]["sha256"] == "b" * 64
    assert known["feature_max_available_at"] == "2021-02-02T12:00:00+00:00"
    provenance = known["fact_provenance"]["cash_usd"]
    assert provenance["accepted_at"] == "2021-02-01T15:00:00+00:00"
    assert provenance["acceptance_datetime_raw"] == "2021-02-01T15:00:00Z"
    assert provenance["public_availability_measured"] is False
    later = extract(cutoff="2022-03-03T00:00:00Z")
    assert later["features"]["cash_usd"] == 999
    assert later["fact_provenance"]["cash_usd"]["accession_number"] == RESTATED


def test_no_backfilled_value_when_only_later_restated_fact_survives():
    data = payload()
    values = data["facts"]["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"]
    values.pop(0)
    assert extract(data)["features"]["cash_usd"] is None


@pytest.mark.parametrize("docs", [[], submissions("2021-02-01T15:00:00")])
def test_date_only_or_naive_acceptance_uses_conservative_next_day_noon(docs):
    assert extract(cutoff="2021-02-02T11:59:59Z", docs=docs)["features"]["cash_usd"] is None
    after = extract(cutoff="2021-02-02T12:00:00Z", docs=docs)
    assert after["features"]["cash_usd"] == 100
    assert after["fact_provenance"]["cash_usd"]["availability_method"] == "filed_date_plus_36_hours_public_availability_proxy"
    assert after["fact_provenance"]["cash_usd"]["accepted_at"] is None


def test_only_usd_instant_and_annual_duration_facts_qualify():
    data = payload()
    cash = data["facts"]["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"]["units"]
    cash["EUR"] = [fact(50000)]
    cash["USD"].append(fact(5000, start="2020-01-01"))
    result = extract(data)
    assert result["features"]["cash_usd"] == 100
    assert result["features"]["annual_operating_cashflow_usd"] == -40
    assert result["fact_provenance"]["annual_operating_cashflow_usd"]["duration_days"] == 366
    assert result["features"]["annual_cash_burn_usd"] == 40
    assert result["features"]["annual_rd_usd"] == 0
    data["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"] = [fact(-5, start="2020-10-01")]
    result = extract(data)
    assert result["features"]["annual_operating_cashflow_usd"] is None
    assert result["features"]["annual_cash_burn_usd"] is None


def test_positive_cashflow_produces_observed_zero_burn():
    data = payload()
    data["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"] = [fact(25, start="2020-01-01")]
    result = extract(data)
    assert result["features"]["annual_cash_burn_usd"] == 0
    assert result["fact_provenance"]["annual_cash_burn_usd"]["source_fact"]["value"] == 25


def test_conflicting_same_available_original_facts_remain_missing():
    data = payload()
    data["facts"]["us-gaap"]["Assets"]["units"]["USD"].append(fact(2000))
    result = extract(data)
    assert result["features"]["assets_usd"] is None
    assert "conflicting" in result["missing_feature_reasons"]["assets_usd"]


def test_original_accession_and_period_end_are_required():
    data = payload()
    data["facts"]["us-gaap"]["Assets"]["units"]["USD"] = [fact(100, accession="", end="2020-12-31"), fact(200, end="2025-12-31")]
    assert extract(data)["features"]["assets_usd"] is None


def cache_payload(directory, key, url, data):
    raw = (json.dumps(data, indent=4) + "\n").encode()
    (directory / f"{key}.bin").write_bytes(raw)
    (directory / f"{key}.meta.json").write_text(json.dumps({"url": url, "retrieved_at": "2026-09-08T00:00:00+00:00",
                                                          "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))
    return hashlib.sha256(raw).hexdigest()


def test_offline_collection_reads_archived_acceptance_and_actual_byte_hashes(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("offline collection attempted network access")
    monkeypatch.setattr(HttpCache, "_open_response", no_network)
    facts_hash = cache_payload(tmp_path, "sec_companyfacts_0000001234", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000001234.json", payload())
    cache_payload(tmp_path, "sec_submissions_0000001234", "https://data.sec.gov/submissions/CIK0000001234.json",
                  {"cik": str(CIK), "filings": {"recent": {"accessionNumber": []},
                                                "files": [{"name": "CIK0000001234-submissions-001.json"}]}})
    cache_payload(tmp_path, "CIK0000001234-submissions-001", "https://data.sec.gov/submissions/CIK0000001234-submissions-001.json", submissions()[0]["payload"])
    result = collect_financial_history([CIK], [parse_cutoff("2021-02-02T12:00:00Z")], HttpCache(tmp_path, "", offline=True),
                                      now=datetime(2026, 9, 8, 1, tzinfo=timezone.utc))
    assert result["training_allowed"] is False
    assert len(result["source_receipts"]) == 3
    row = result["observations"][0]
    assert row["features"]["cash_usd"] == 100
    assert row["fact_provenance"]["cash_usd"]["accepted_at"] == "2021-02-01T15:00:00+00:00"
    assert row["fact_provenance"]["cash_usd"]["companyfacts_source"]["actual_bytes_sha256"] == facts_hash
    assert "membership" not in row and "label" not in row and "observation_at" not in row


def test_cik_inputs_and_date_cutoffs(tmp_path):
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"labels": [{"target_cik": "00001234"}, {"target_cik": CIK}]}))
    assert load_ciks(frozen) == [CIK]
    csv_path = tmp_path / "issuers.csv"
    csv_path.write_text("cik,name\n1234,Synthetic\n5678,Fixture\n")
    assert load_ciks(csv_path) == [1234, 5678]
    assert parse_cutoff("2021-02-01").isoformat() == "2021-02-01T00:00:00+00:00"


def test_live_access_without_contact_blocks_before_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError("network access without user contact")
    monkeypatch.setattr(HttpCache, "_open_response", no_network)
    ciks = tmp_path / "ciks.json"
    ciks.write_text(json.dumps({"ciks": [CIK]}))
    assert main(["--ciks", str(ciks), "--cutoff", "2021-03-01", "--cache-dir", str(tmp_path / "cache"),
                 "--output-dir", str(tmp_path / "out")]) == 2
    receipt = json.loads(capsys.readouterr().err)
    assert "SEC_USER_AGENT" in receipt["reason"] and receipt["training_allowed"] is False


def test_403_stops_without_retry_or_alternate_identity_and_writes_blocked_receipt(tmp_path, monkeypatch, capsys):
    attempts = []
    def forbidden(self, request, timeout):
        attempts.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b"blocked"))
    monkeypatch.setattr(HttpCache, "_open_response", forbidden)
    # A transport-isolated test string; no contact header is sent to any service.
    monkeypatch.setenv("SEC_USER_AGENT", "Synthetic fixture offline-test@research.test")
    ciks = tmp_path / "ciks.json"
    ciks.write_text(json.dumps({"ciks": [CIK]}))
    assert main(["--ciks", str(ciks), "--cutoff", "2021-03-01", "--cache-dir", str(tmp_path / "cache"),
                 "--output-dir", str(tmp_path / "out")]) == 2
    receipt = json.loads(capsys.readouterr().err)
    assert len(attempts) == 1
    assert receipt["blocked_request"]["http_status"] == 403
    assert receipt["blocked_request"]["financial_payload_received"] is False
