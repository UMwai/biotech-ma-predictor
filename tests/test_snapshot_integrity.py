"""Regression tests for retrieval lineage and temporal research boundaries."""

from datetime import date, datetime, timezone
import hashlib
import json

import pytest

from scripts.evaluate_market import snapshot_manifest
from src.research.evaluator import evaluate_clinical_assets
from src.research.matching import CompanyMatcher
from src.research.sources import CacheIntegrityError, HttpCache, PublicRefreshCache, StaleSourceError


URL = "https://example.test/source"
RETRIEVED = "2026-07-01T12:00:00+00:00"
NOW = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)


def legacy_cache(root, *, metadata=True):
    payload = b'{"value": "old"}'
    (root / "source.bin").write_bytes(payload)
    if metadata:
        (root / "source.meta.json").write_text(json.dumps({
            "url": URL, "retrieved_at": RETRIEVED,
            "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
        }))
    return payload


def mock_response(monkeypatch, payload):
    class Response:
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return payload

    monkeypatch.setattr("src.research.sources.urllib.request.urlopen", lambda *a, **k: Response())
    monkeypatch.setattr("src.research.sources.utc_now_iso", lambda: NOW.isoformat())


def test_refresh_preserves_legacy_payload_and_retrieval_receipt(tmp_path, monkeypatch):
    original = legacy_cache(tmp_path)
    replacement = b'{"value": "new"}'
    mock_response(monkeypatch, replacement)
    cache = HttpCache(tmp_path, "test", now=NOW, max_age_days=7)
    assert cache.get_bytes(URL, "source", refresh=True) == replacement
    receipts = [json.loads(path.read_text()) for path in (tmp_path / "snapshots").glob("*.json")]
    assert {item["retrieved_at"] for item in receipts} == {RETRIEVED, NOW.isoformat()}
    assert {path.read_bytes() for path in (tmp_path / "blobs").glob("*.bin")} == {original, replacement}
    assert cache.source_snapshots["source"]["freshness"] == "fresh"
    assert HttpCache(tmp_path, "test", offline=True).get_bytes(URL, "source") == replacement


def test_two_refreshes_preserve_both_versioned_payloads(tmp_path, monkeypatch):
    mock_response(monkeypatch, b"first")
    cache = HttpCache(tmp_path, "test", now=NOW)
    cache.get_bytes(URL, "source", refresh=True)
    first_receipt = cache.source_snapshots["source"]["snapshot_path"]
    first_receipt_bytes = (tmp_path / first_receipt).read_bytes()
    mock_response(monkeypatch, b"second")
    cache.get_bytes(URL, "source", refresh=True)
    assert (tmp_path / first_receipt).read_bytes() == first_receipt_bytes
    assert len(list((tmp_path / "snapshots").glob("*.json"))) == 2
    assert {path.read_bytes() for path in (tmp_path / "blobs").glob("*.bin")} == {b"first", b"second"}


@pytest.mark.parametrize("artifact", ["latest", "blob", "receipt"])
def test_tampered_cache_is_rejected(tmp_path, monkeypatch, artifact):
    mock_response(monkeypatch, b'{"value": 1}')
    cache = HttpCache(tmp_path, "test", now=NOW)
    cache.get_bytes(URL, "source")
    item = cache.source_snapshots["source"]
    path = {
        "latest": tmp_path / "source.bin",
        "blob": tmp_path / item["blob_path"],
        "receipt": tmp_path / item["snapshot_path"],
    }[artifact]
    path.write_bytes(b"tampered")
    with pytest.raises(CacheIntegrityError):
        HttpCache(tmp_path, "test", offline=True).get_bytes(URL, "source")


def test_stale_source_requires_opt_in_and_rerun_does_not_freshen_it(tmp_path):
    legacy_cache(tmp_path)
    strict = HttpCache(tmp_path, "test", offline=True, now=NOW, max_age_days=7)
    with pytest.raises(StaleSourceError, match="stale"):
        strict.get_bytes(URL, "source")
    cache = HttpCache(tmp_path, "test", offline=True, now=NOW, max_age_days=7, allow_stale=True)
    cache.get_bytes(URL, "source")
    manifest = snapshot_manifest(cache, NOW.date())
    assert manifest["freshness"]["status"] == "stale_or_unknown"
    assert manifest["freshness"]["oldest_retrieved_at"] == RETRIEVED
    assert manifest["source_snapshots"][0]["age_days"] == 14
    assert manifest["source_snapshots"][0]["retrieved_at"] == RETRIEVED
    assert json.loads((tmp_path / "source.meta.json").read_text())["retrieved_at"] == RETRIEVED


def test_legacy_payload_without_metadata_remains_undated(tmp_path):
    legacy_cache(tmp_path, metadata=False)
    cache = HttpCache(tmp_path, "test", offline=True, now=NOW, max_age_days=7, allow_stale=True)
    cache.get_bytes(URL, "source")
    record = cache.source_snapshots["source"]
    assert record["freshness"] == "unknown"
    assert record["retrieved_at"] is None
    assert record["integrity_status"] == "legacy_unverified"
    strict = HttpCache(tmp_path, "test", offline=True, now=NOW, max_age_days=7)
    with pytest.raises(StaleSourceError, match="unknown"):
        strict.get_bytes(URL, "source")


def test_manifest_identifies_later_sources_without_claiming_historical_replay(tmp_path):
    legacy_cache(tmp_path)
    cache = HttpCache(tmp_path, "test", offline=True, now=NOW)
    cache.get_bytes(URL, "source")
    manifest = snapshot_manifest(cache, date(2026, 6, 30))
    temporal = manifest["temporal_validity"]
    assert temporal["historical_replay_available"] is False
    assert temporal["source_dates_compatible_with_as_of"] is False
    assert temporal["sources_retrieved_after_as_of"] == ["source"]
    record = manifest["source_snapshots"][0]
    assert hashlib.sha256((tmp_path / record["blob_path"]).read_bytes()).hexdigest() == record["sha256"]
    assert hashlib.sha256((tmp_path / record["snapshot_path"]).read_bytes()).hexdigest() == record["snapshot_sha256"]


def test_future_clinical_update_quarantines_whole_asset():
    raw = {
        "name": "EX-101", "sponsor": "Example Bio", "nct_ids": ["NCT00000001"],
        "phases": ["PHASE3"], "statuses": ["RECRUITING"],
        "last_updates": ["2026-07-01", "2026-08-01"], "enrollments": [500],
    }
    rejected = []
    assert evaluate_clinical_assets([raw], CompanyMatcher([]), date(2026, 7, 15), rejected_assets=rejected) == []
    assert rejected[0]["reason"] == "clinical_record_updated_after_as_of"
    assert rejected[0]["latest_update"] == "2026-08-01"
    assert len(evaluate_clinical_assets([raw], CompanyMatcher([]), date(2026, 8, 1))) == 1


def test_different_query_cannot_silently_reuse_payload(tmp_path):
    legacy_cache(tmp_path)
    cache = HttpCache(tmp_path, "test", offline=True)
    with pytest.raises(CacheIntegrityError, match="different URL"):
        cache.get_bytes(URL + "?new=query", "source")


def cached_source(root, url, key, payload, retrieved_at=RETRIEVED):
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{key}.bin").write_bytes(payload)
    (root / f"{key}.meta.json").write_text(json.dumps({
        "url": url, "retrieved_at": retrieved_at,
        "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
    }))


def deny_network(*args, **kwargs):
    raise AssertionError("Unexpected network request")


def test_public_refresh_preserves_old_sec_receipts_and_reports_mixed_freshness(tmp_path, monkeypatch):
    from scripts.evaluate_market import sec_screening_manifest

    sec_url = "https://efts.sec.gov/LATEST/search-index?enddt=2026-07-01"
    cached_source(tmp_path, sec_url, "sec", b"old SEC")
    cached_source(tmp_path, URL, "public", b"today public", NOW.isoformat())
    monkeypatch.setattr("src.research.sources.urllib.request.urlopen", deny_network)
    monkeypatch.setattr("src.research.sources.urllib.request.build_opener", deny_network)
    cache = PublicRefreshCache(tmp_path, "public research", now=NOW)
    assert cache.get_bytes(sec_url, "sec", refresh=True) == b"old SEC"
    assert cache.get_bytes(URL, "public", refresh=True) == b"today public"
    sec = cache.source_snapshots["sec"]
    assert sec["retrieved_at"] == RETRIEVED
    assert sec["sha256"] == hashlib.sha256(b"old SEC").hexdigest()
    assert sec["freshness"] == "stale"
    assert sec["age_days"] == 14
    assert sec["retrieval_policy"] == "cache_only"
    assert cache.source_snapshots["public"]["retrieval_policy"] == "same_day_cache"
    manifest = snapshot_manifest(cache, NOW.date())
    assert manifest["freshness"]["status"] == "stale_or_unknown"
    assert manifest["freshness"]["source_counts"] == {"fresh": 1, "stale": 1}
    assert manifest["freshness"]["allow_stale"] is False
    screening = sec_screening_manifest(cache, NOW.date(), date(2026, 7, 1), public_only=True)
    assert screening["sec_transaction_screening_as_of"] == "2026-07-01"
    assert screening["sec_transaction_screening_status"]["current"] is False
    assert screening["sec_transaction_screening_status"]["lag_days"] == 14
    assert json.loads((tmp_path / "sec.meta.json").read_text())["retrieved_at"] == RETRIEVED


@pytest.mark.parametrize("defect", ["missing", "missing_metadata", "tampered", "unverified", "wrong_url"])
def test_public_refresh_sec_cache_failures_never_fall_back_to_network(tmp_path, monkeypatch, defect):
    url = "https://www.sec.gov/files/company_tickers_exchange.json"
    cached_source(tmp_path, url, "sec", b"SEC")
    if defect == "missing":
        (tmp_path / "sec.bin").unlink()
    elif defect == "missing_metadata":
        (tmp_path / "sec.meta.json").unlink()
    elif defect == "tampered":
        (tmp_path / "sec.bin").write_bytes(b"modified")
    elif defect == "unverified":
        (tmp_path / "sec.meta.json").write_text(json.dumps({"url": url}))
    else:
        url += "?changed"
    monkeypatch.setattr("src.research.sources.urllib.request.urlopen", deny_network)
    monkeypatch.setattr("src.research.sources.urllib.request.build_opener", deny_network)
    with pytest.raises((FileNotFoundError, CacheIntegrityError)):
        PublicRefreshCache(tmp_path, "public research", now=NOW).get_bytes(url, "sec", refresh=True)


def test_public_refresh_fetches_older_public_source_without_relabeling_prior_receipt(tmp_path, monkeypatch):
    cached_source(tmp_path, URL, "public", b"old public")
    calls = []

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"refreshed public"

    def open_response(self, request, timeout):
        calls.append(request.full_url)
        return Response()

    monkeypatch.setattr(PublicRefreshCache, "_open_response", open_response)
    monkeypatch.setattr("src.research.sources.utc_now_iso", lambda: NOW.isoformat())
    cache = PublicRefreshCache(tmp_path, "public research", now=NOW)
    assert cache.get_bytes(URL, "public", refresh=True) == b"refreshed public"
    assert calls == [URL]
    receipts = [json.loads(path.read_text()) for path in (tmp_path / "snapshots").glob("*.json")]
    assert {item["retrieved_at"] for item in receipts} == {RETRIEVED, NOW.isoformat()}
    assert cache.source_snapshots["public"]["freshness"] == "fresh"


@pytest.mark.parametrize("host", ["sec.gov", "www.sec.gov", "efts.sec.gov", "DATA.SEC.GOV."])
def test_public_refresh_blocks_sec_redirects_and_direct_network(tmp_path, host):
    import urllib.request
    from src.research.sources import _NoSECRedirects

    request = urllib.request.Request(URL)
    target = f"https://{host}/source"
    with pytest.raises(PermissionError, match="SEC network"):
        _NoSECRedirects().redirect_request(request, None, 302, "Found", {}, target)
    with pytest.raises(PermissionError, match="SEC network"):
        PublicRefreshCache(tmp_path, "public research")._open_response(urllib.request.Request(target), 1)


def test_partial_evaluator_uses_original_sec_queries_with_new_market_cutoff(tmp_path, monkeypatch):
    from datetime import timedelta
    from urllib.parse import urlencode
    import csv
    import scripts.evaluate_market as evaluator
    from src.research.sources import SEC_FULL_TEXT_SEARCH_URL, SEC_TICKERS_URL

    old = date(2026, 7, 1)
    current = date.today()
    root = tmp_path / "cache"
    cached_source(root, SEC_TICKERS_URL, "sec_company_tickers_exchange",
                  json.dumps({"fields": ["cik", "ticker"], "data": [[1234, "ACME"]]}).encode())
    for form in ("SC 14D9", "DEFM14A"):
        start = old - timedelta(days=365)
        params = urlencode({"forms": form, "startdt": start.isoformat(), "enddt": old.isoformat(), "from": 0, "size": 100})
        key = f"sec_efts_{form.replace(' ', '_')}_{start}_{old}_0000"
        hits = [{"_source": {"ciks": ["1234"], "form": form, "file_date": "2026-06-29"}}]
        cached_source(root, f"{SEC_FULL_TEXT_SEARCH_URL}?{params}", key,
                      json.dumps({"hits": {"total": {"value": 1}, "hits": hits}}).encode())

    def universe(cache, refresh=False):
        from src.research.models import PublicCompany

        assert refresh is True
        cache.get_json(SEC_TICKERS_URL, "sec_company_tickers_exchange", refresh=refresh)
        cached_source(root, URL, "public", b"public", datetime.now(timezone.utc).isoformat())
        cache.get_bytes(URL, "public", refresh=True)
        return [PublicCompany("ACME", "Acme Bio", "NASDAQ", "Biotechnology", 1000000000, cik=1234)]

    monkeypatch.setattr(evaluator, "fetch_public_biotech_universe", universe)
    monkeypatch.setattr(evaluator, "fetch_orange_book_assets", lambda *a, **k: [])
    monkeypatch.setattr(evaluator, "fetch_drugsfda_biologic_assets", lambda *a, **k: [])
    monkeypatch.setattr(evaluator, "fetch_active_clinical_assets", lambda *a, **k: [])
    monkeypatch.setattr("src.research.sources.urllib.request.urlopen", deny_network)
    monkeypatch.setattr("src.research.sources.urllib.request.build_opener", deny_network)
    output = tmp_path / "evaluation"
    monkeypatch.setattr("sys.argv", ["evaluate_market.py", "--refresh-public", "--as-of", str(current),
                                    "--sec-screening-as-of", str(old), "--cache-dir", str(root), "--output-dir", str(output)])
    assert evaluator.main() == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["as_of"] == str(current)
    assert manifest["sec_transaction_screening_as_of"] == str(old)
    assert manifest["sec_transaction_screening_status"]["current"] is False
    assert manifest["freshness"]["status"] == "stale_or_unknown"
    row = next(csv.DictReader((output / "companies.csv").open()))
    assert row["risk_set_eligible"] == "False"
    assert "2026-06-29" in row["risk_set_exclusion_reason"]
    for name, digest in manifest["output_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("flags", [
    ["--refresh-public", "--refresh"], ["--refresh-public", "--offline"],
    ["--refresh-public"], ["--sec-screening-as-of", "2026-07-01"],
    ["--refresh-public", "--sec-screening-as-of", "2026-07-01", "--allow-stale"],
])
def test_evaluator_rejects_ambiguous_partial_refresh_options(monkeypatch, flags):
    from scripts.evaluate_market import parse_args

    monkeypatch.setattr("sys.argv", ["evaluate_market.py", *flags])
    with pytest.raises(SystemExit) as error:
        parse_args()
    assert error.value.code == 2
