"""Local product contract: real artifacts, exclusions, provenance, and no writes."""

import csv
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from src.local_app import ArtifactStore, create_app


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def manifest(root, layer, **kwargs):
    directory = root / layer
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps({
        "generated_at": "2026-01-02T00:00:00Z", "as_of": "2026-01-01", **kwargs,
    }))


def seal(root, run):
    (run / "snapshot.json").write_text(json.dumps({"artifact_sha256": {
        str(path.relative_to(run)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in run.rglob("*") if path.is_file() and path.name != "snapshot.json"
    }}))
    (root / "local_latest.json").write_text(json.dumps({
        "snapshot_directory": str(run.relative_to(root)),
        "snapshot_sha256": hashlib.sha256((run / "snapshot.json").read_bytes()).hexdigest(),
    }))


@pytest.fixture
def artifacts(tmp_path):
    manifest(tmp_path, "market_evaluation", model_version="test-market-v1")
    write_csv(tmp_path / "market_evaluation/companies.csv", [
        {"ticker": "KEEP", "company_name": "Eligible Biotech", "research_score": 72,
         "risk_set_eligible": "True", "risk_set_exclusion_reason": "", "data_confidence": 50,
         "score_drivers": '["One matched phase 3 asset"]', "top_assets": '["Real asset"]',
         "approved_asset_count": 0, "clinical_asset_count": 1},
        {"ticker": "GONE", "company_name": "Announced Acquisition", "research_score": 99,
         "risk_set_eligible": "False", "risk_set_exclusion_reason": "Announced tender offer",
         "data_confidence": 80, "score_drivers": "[]", "top_assets": "[]",
         "approved_asset_count": 1, "clinical_asset_count": 0},
        {"ticker": "RISK", "company_name": "Evidence Biotech", "research_score": 35,
         "risk_set_eligible": "True", "risk_set_exclusion_reason": "", "data_confidence": 40,
         "score_drivers": "[]", "top_assets": "[]", "approved_asset_count": 0, "clinical_asset_count": 0},
    ])
    manifest(tmp_path, "execution_scorecard")
    write_csv(tmp_path / "execution_scorecard/companies.csv", [
        {"ticker": "KEEP", "company_name": "Eligible Biotech", "evidence_coverage": "market_only_risk_unscreened"},
        {"ticker": "RISK", "company_name": "Evidence Biotech", "evidence_coverage": "company_specific_evidence"},
    ])
    manifest(tmp_path, "execution_risk")
    write_csv(tmp_path / "execution_risk/companies.csv", [
        {"ticker": "RISK", "company_name": "Evidence Biotech", "execution_risk_score": 31},
    ])
    write_csv(tmp_path / "execution_risk/signals.csv", [
        {"ticker": "RISK", "source_url": "https://example.org/primary-document", "summary": "Regulatory review remains pending.",
         "evidence_status": "inspection_pending", "event_date": "2025-12-01", "source_title": "Primary source"},
    ])
    write_csv(tmp_path / "market_evaluation/assets.csv", [
        {"owner_ticker": "KEEP", "asset_name": "Real asset", "source_url": "https://example.org/trial",
         "source_name": "Trial registry", "development_phase": "phase_3", "score": 75,
         "score_drivers": '["Phase 3 study"]', "indications": '["Oncology"]'},
    ])
    return tmp_path


@pytest.fixture
def client(artifacts):
    with TestClient(create_app(artifacts), base_url="http://localhost") as client:
        yield client


def test_watchlist_excludes_announced_transactions_and_preserves_coverage(client):
    response = client.get("/api/v1/predictions/watchlist")
    assert response.status_code == 200
    data = response.json()
    assert [row["ticker"] for row in data["watchlist"]] == ["KEEP", "RISK"]
    assert [row["rank"] for row in data["watchlist"]] == [1, 2]
    assert data["as_of"] == "2026-01-01"
    assert data["coverage"] == {"companies": 3, "eligible": 2, "excluded": 1,
        "with_company_specific_evidence": 1, "unscreened": 2, "with_matched_assets": 2}
    keep = data["watchlist"][0]
    assert not keep["risk_screened"]
    assert keep["combined_diligence_risk"] is None
    assert keep["execution_risk_score"] is None
    assert "not a calibrated" in data["score_semantics"].lower()
    assert "deal_probability" not in response.text


def test_history_progress_is_explicit_and_tampering_cannot_claim_a_model(client, artifacts):
    directory = artifacts / "historical_training"
    directory.mkdir()
    status = {"schema_version": "historical-training-readiness-v1", "status": "data_incomplete",
              "model_trained_on_real_data": False, "training_allowed": False,
              "reviewed_positive_announcements": 49, "reviewed_negative_company_windows": 0,
              "eligible_feature_observations": 0, "pending_candidates": 287,
              "blockers": ["Historical membership is missing"]}
    path = directory / "status.json"
    path.write_text(json.dumps(status))
    history = client.get("/ready").json()["historical_training"]
    assert history["reviewed_positive_announcements"] == 49
    assert history["model_trained_on_real_data"] is False
    status["model_trained_on_real_data"] = True
    path.write_text(json.dumps(status))
    history = client.get("/ready").json()["historical_training"]
    assert history["status"] == "unavailable"
    assert history["model_trained_on_real_data"] is False


def test_partial_refresh_warns_when_transaction_exclusion_screen_is_old(client, artifacts):
    path = artifacts / "market_evaluation/manifest.json"
    value = json.loads(path.read_text())
    value.update(sec_transaction_screening_as_of="2025-12-01",
                 sec_transaction_screening_status={"status": "cache_only_not_current", "current": False})
    path.write_text(json.dumps(value))
    market = client.get("/ready").json()["sources"][0]
    assert any("later announcements have not been screened" in warning for warning in market["warnings"])
    assert market["sec_transaction_screening_as_of"] == "2025-12-01"


def test_excluded_company_remains_available_for_diligence(client):
    excluded = client.get("/api/v1/predictions/watchlist?eligibility=excluded").json()["watchlist"]
    assert len(excluded) == 1
    assert excluded[0]["ticker"] == "GONE"
    assert excluded[0]["rank"] is None
    detail = client.get("/api/v1/companies/gone").json()
    assert detail["risk_set_eligible"] is False
    assert detail["risk_set_exclusion_reason"] == "Announced tender offer"
    assert detail["rank"] is None


def test_filters_and_pagination_apply_to_real_rows(client):
    url = "/api/v1/predictions/watchlist"
    assert client.get(url + "?coverage=screened").json()["watchlist"][0]["ticker"] == "RISK"
    assert client.get(url + "?min_score=70").json()["total"] == 1
    assert client.get(url + "?q=no-such-company").json()["total"] == 0
    assert client.get(url + "?q=eligible").json()["total"] == 1
    assert client.get(url + "?page_size=1&page=2").json()["watchlist"][0]["ticker"] == "RISK"
    assert client.get(url + "?eligibility=invalid").status_code == 422
    assert client.get(url + "?min_score=nan").status_code == 422


def test_company_detail_contains_actual_assets_and_evidence(client):
    keep = client.get("/api/v1/companies/KEEP").json()
    assert keep["assets"]["items"][0]["asset_name"] == "Real asset"
    assert keep["assets"]["items"][0]["source_url"] == "https://example.org/trial"
    assert keep["evidence"][0]["status"] == "unscreened"
    assert keep["evidence"][1]["status"] == "unavailable"
    risk = client.get("/api/v1/companies/RISK").json()
    assert risk["execution_risk_score"] == 31
    assert risk["evidence"][0]["signals"][0]["evidence_status"] == "inspection_pending"
    assert risk["evidence"][0]["signals"][0]["source_url"] == "https://example.org/primary-document"


def test_report_is_real_download_without_modifying_artifacts(client, artifacts):
    before = {p.relative_to(artifacts): p.read_bytes() for p in artifacts.rglob("*") if p.is_file()}
    response = client.get("/api/v1/companies/KEEP/report")
    assert response.status_code == 200
    assert 'attachment; filename="KEEP-research-2026-01-01.md"' == response.headers["content-disposition"]
    assert "text/markdown" in response.headers["content-type"]
    assert "Real asset" in response.text
    assert "https://example.org/trial" in response.text
    assert "2026-01-01" in response.text
    assert "not low risk" in response.text
    assert "deal_probability" not in response.text
    assert before == {p.relative_to(artifacts): p.read_bytes() for p in artifacts.rglob("*") if p.is_file()}


def test_missing_primary_artifacts_fail_readiness_and_api_but_page_loads(tmp_path):
    client = TestClient(create_app(tmp_path), base_url="http://localhost")
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["artifacts"]["status"] == "unavailable"
    for url in ["/ready", "/api/v1/predictions/watchlist", "/api/v1/companies/KEEP", "/api/v1/companies/KEEP/report"]:
        response = client.get(url)
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"


def test_missing_optional_assets_are_unavailable_not_empty_success(client, artifacts):
    (artifacts / "market_evaluation/assets.csv").unlink()
    detail = client.get("/api/v1/companies/KEEP").json()
    assert detail["assets"]["status"] == "unavailable"
    assert detail["assets"]["total"] is None
    assert "Missing artifact" in detail["assets"]["reason"]


@pytest.mark.parametrize("change", ["duplicate", "invalid_score", "invalid_eligibility", "missing_schema"])
def test_invalid_canonical_schema_fails_closed(client, artifacts, change):
    path = artifacts / "market_evaluation/companies.csv"
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    if change == "duplicate":
        rows.append(rows[0])
    elif change == "invalid_score":
        rows[0]["research_score"] = "NaN"
    elif change == "invalid_eligibility":
        rows[0]["risk_set_eligible"] = "maybe"
    else:
        for row in rows:
            del row["risk_set_eligible"]
    write_csv(path, rows)
    assert client.get("/ready").status_code == 503
    assert client.get("/api/v1/predictions/watchlist").status_code == 503


def test_missing_score_remains_visible_as_unknown_without_fabrication(client, artifacts):
    path = artifacts / "market_evaluation/companies.csv"
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["research_score"] = ""
    write_csv(path, rows)
    keep = next(c for c in client.get("/api/v1/predictions/watchlist").json()["watchlist"] if c["ticker"] == "KEEP")
    assert keep["research_score"] is None
    assert keep["rank"] is None


def test_unknown_and_invalid_tickers_are_not_mocked(client):
    assert client.get("/api/v1/companies/UNKNOWN").status_code == 404
    assert client.get("/api/v1/companies/BAD%20TICKER").status_code == 422
    assert client.get("/api/v1/companies/UNKNOWN/report").status_code == 404


def test_source_date_is_not_replaced_by_request_time(client):
    data = client.get("/ready").json()
    assert data["as_of"] == "2026-01-01"
    assert data["freshness"] == "stale_or_unknown"
    assert data["sources"][0]["warnings"]
    assert data["sources"][0]["retrieval_provenance"] == "unverified"
    assert client.get("/health").json()["mode"] == "local_read_only"


def test_dashboard_assets_are_local_and_host_is_restricted(client):
    response = client.get("/")
    assert "https://" not in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/static/desk.js").status_code == 200
    assert client.get("/static/desk.css").status_code == 200
    assert client.get("/", headers={"Host": "attacker.example"}).status_code == 400


def test_unsafe_source_links_are_not_exposed(client, artifacts):
    path = artifacts / "market_evaluation/assets.csv"
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["source_url"] = "javascript:alert(1)"
    write_csv(path, rows)
    assert client.get("/api/v1/companies/KEEP").json()["assets"]["items"][0]["source_url"] is None


def test_artifact_symlink_cannot_escape_output_directory(client, artifacts, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "companies.csv"
    path = artifacts / "market_evaluation/companies.csv"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    assert client.get("/ready").status_code == 503


def test_local_run_pointer_is_confined_and_observed_without_restart(client, artifacts):
    from shutil import copytree
    run = artifacts / "local_runs/test-run"
    run.mkdir(parents=True)
    copytree(artifacts / "market_evaluation", run / "market_evaluation")
    seal(artifacts, run)
    assert client.get("/ready").status_code == 200
    # Main artifacts remain on disk, but a bad active pointer may not fall back to them.
    (artifacts / "local_latest.json").write_text(json.dumps({"snapshot_directory": "../outside"}))
    response = client.get("/ready")
    assert response.status_code == 503
    assert "pointer" in response.text


@pytest.mark.parametrize("target", ["snapshot.json", "market_evaluation/companies.csv"])
def test_sealed_snapshot_tampering_is_rejected(client, artifacts, target):
    from shutil import copytree
    run = artifacts / "local_runs/test-run"
    run.mkdir(parents=True)
    copytree(artifacts / "market_evaluation", run / "market_evaluation")
    seal(artifacts, run)
    assert client.get("/ready").status_code == 200
    path = run / target
    path.write_bytes(path.read_bytes() + b"\n")
    assert client.get("/ready").status_code == 503
    assert client.get("/api/v1/predictions/watchlist").status_code == 503


def test_declared_market_output_hashes_are_checked(client, artifacts):
    path = artifacts / "market_evaluation/manifest.json"
    payload = json.loads(path.read_text())
    payload["output_sha256"] = {
        filename: hashlib.sha256((path.parent / filename).read_bytes()).hexdigest()
        for filename in ("companies.csv", "assets.csv")
    }
    path.write_text(json.dumps(payload))
    assert client.get("/ready").status_code == 200
    companies = path.parent / "companies.csv"
    companies.write_bytes(companies.read_bytes() + b"\n")
    assert client.get("/ready").status_code == 503


def test_recent_cutoff_without_retrieval_metadata_remains_unverified(client, artifacts):
    from datetime import datetime, timezone
    path = artifacts / "market_evaluation/manifest.json"
    payload = json.loads(path.read_text())
    payload["as_of"] = datetime.now(timezone.utc).date().isoformat()
    payload["freshness"] = {"status": "fresh"}
    path.write_text(json.dumps(payload))
    data = client.get("/ready").json()
    assert data["freshness"] == "stale_or_unknown"
    assert data["sources"][0]["retrieval_provenance"] == "unverified"


def test_source_snapshot_identity_mismatch_fails_closed(client, artifacts):
    path = artifacts / "market_evaluation/manifest.json"
    payload = json.loads(path.read_text())
    payload["source_snapshots"] = [{"cache_key": "test", "sha256": "0" * 64, "snapshot_sha256": "1" * 64}]
    payload["source_snapshot_set_sha256"] = "f" * 64
    path.write_text(json.dumps(payload))
    assert client.get("/ready").status_code == 503


@pytest.fixture
def panel_artifacts(artifacts):
    directory = artifacts / 'historical_training/panel_seed'
    directory.mkdir(parents=True)
    summary = {'schema_version':'historical-panel-assembly-v1', 'status':'data_incomplete',
              'frame_companies':1,'planned_observations':1,'reviewed_annual_financial_records':1,
              'financial_issuers':1,'reviewed_negative_corpus_windows':0,'eligible_feature_observations':0,
              'model_training_performed':False,'validated_predictive_edge':False,
              'gap_counts':{'outcome_missing':1}, 'pre_test_training_support': {
                  'company_observations':0, 'structurally_admitted_prior_observations':0,
                  'distinct_positive_events':0, 'distinct_negative_companies':0,
                  'purged_prior_observations':0, 'purged_label_unavailable':0}}
    panel = {'schema_version':'historical-company-features-v1', 'observations':[]}
    report = json.dumps(dict(summary,panel=panel,coverage=[{'ticker':'SYNTH','training_eligible':False}])).encode()
    panel_bytes = json.dumps(panel).encode()
    (directory/'assembly.json').write_bytes(report)
    (directory/'panel.json').write_bytes(panel_bytes)
    status = dict(summary,coverage_report_sha256=hashlib.sha256(report).hexdigest(),panel_sha256=hashlib.sha256(panel_bytes).hexdigest())
    (directory/'status.json').write_text(json.dumps(status))
    return directory,status,report


def test_historical_panel_download_checks_hash_and_never_claims_a_model(client, panel_artifacts):
    directory,status,report = panel_artifacts
    response = client.get('/api/v1/research/historical-coverage')
    assert response.status_code == 200
    assert response.content == report
    assert 'attachment' in response.headers['Content-Disposition']
    (directory/'assembly.json').write_bytes(report+b' ')
    assert client.get('/api/v1/research/historical-coverage').status_code == 503
    (directory/'assembly.json').write_bytes(report)
    status['model_training_performed'] = True
    (directory/'status.json').write_text(json.dumps(status))
    assert client.get('/api/v1/research/historical-coverage').status_code == 503


@pytest.mark.parametrize('name',['assembly.json','panel.json'])
def test_panel_summary_unavailable_when_bound_artifact_missing(client, artifacts, panel_artifacts, name):
    directory,_,_ = panel_artifacts
    (directory/name).unlink()
    assert ArtifactStore(artifacts).panel_status()['status']=='unavailable'
    assert client.get('/api/v1/research/historical-coverage').status_code==503


@pytest.mark.parametrize('field',['eligible_feature_observations','pre_test_training_support','gap_counts'])
def test_panel_display_values_cannot_disagree_with_bound_report(artifacts, panel_artifacts, field):
    directory,status,_ = panel_artifacts
    if field=='eligible_feature_observations': status[field]=1
    elif field=='gap_counts': status[field]={}
    else: status[field]['distinct_positive_events']=999999
    (directory/'status.json').write_text(json.dumps(status))
    result=ArtifactStore(artifacts).panel_status()
    assert result['status']=='unavailable' and 'differs' in result['detail']


def test_panel_counts_are_checked_even_with_consistent_report_hashes(artifacts, panel_artifacts):
    directory,status,report = panel_artifacts
    value=json.loads(report); value['coverage']=[]
    modified=json.dumps(value).encode(); (directory/'assembly.json').write_bytes(modified)
    status['coverage_report_sha256']=hashlib.sha256(modified).hexdigest()
    (directory/'status.json').write_text(json.dumps(status))
    result=ArtifactStore(artifacts).panel_status()
    assert result['status']=='unavailable' and 'counts disagree' in result['detail']


def test_panel_fold_support_cannot_exceed_approved_observations(artifacts, panel_artifacts):
    directory,status,report = panel_artifacts
    value=json.loads(report)
    value['pre_test_training_support']['distinct_negative_companies']=20
    status['pre_test_training_support']=value['pre_test_training_support']
    modified=json.dumps(value).encode();(directory/'assembly.json').write_bytes(modified)
    status['coverage_report_sha256']=hashlib.sha256(modified).hexdigest()
    (directory/'status.json').write_text(json.dumps(status))
    result=ArtifactStore(artifacts).panel_status()
    assert result['status']=='unavailable' and 'fold support disagrees' in result['detail']
