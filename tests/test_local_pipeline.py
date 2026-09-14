import json
from pathlib import Path

import pytest

from scripts.run_local_research import build_snapshot, saved_market_source, sha256, verify_snapshot


def seal_market(output_root, *, as_of="2026-07-22", screening_as_of=None):
    directory = output_root / "local_runs/prior"
    market = directory / "market_evaluation"
    market.mkdir(parents=True)
    (market / "companies.csv").write_text("ticker\nSAVED\n")
    source = {"as_of": as_of}
    if screening_as_of:
        source["sec_transaction_screening_as_of"] = screening_as_of
    (market / "manifest.json").write_text(json.dumps(source))
    manifest = {"run_id": "prior", "artifact_sha256": {
        str(path.relative_to(directory)): sha256(path) for path in market.iterdir()}}
    (directory / "snapshot.json").write_text(json.dumps(manifest))
    (output_root / "local_latest.json").write_text(json.dumps({
        "snapshot_directory": "local_runs/prior", "snapshot_sha256": sha256(directory / "snapshot.json")}))
    return market


def test_snapshot_verification_rejects_tampered_artifact_and_path_escape(tmp_path):
    (tmp_path / "companies.csv").write_text("ticker\nACME\n")
    manifest = {"artifact_sha256": {"companies.csv": sha256(tmp_path / "companies.csv")}}
    (tmp_path / "snapshot.json").write_text(json.dumps(manifest))
    assert verify_snapshot(tmp_path) == manifest
    (tmp_path / "companies.csv").write_text("ticker\nOTHER\n")
    with pytest.raises(ValueError, match="changed"):
        verify_snapshot(tmp_path)
    manifest["artifact_sha256"] = {"../escape.csv": "fake"}
    (tmp_path / "snapshot.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid snapshot artifact"):
        verify_snapshot(tmp_path)


def test_failed_build_leaves_existing_publication_untouched(tmp_path, monkeypatch):
    (tmp_path / "market_evaluation").mkdir()
    (tmp_path / "market_evaluation/companies.csv").write_text("ticker\nACME\n")
    (tmp_path / "market_evaluation/manifest.json").write_text('{"as_of":"2020-01-01"}')
    seal_market(tmp_path)
    pointer = tmp_path / "local_latest.json"
    before = pointer.read_bytes()

    def fail(*args, **kwargs):
        raise ValueError("fixture build failure")

    monkeypatch.setattr("scripts.run_local_research.run_script", fail)
    with pytest.raises(ValueError, match="fixture build failure"):
        build_snapshot(tmp_path)
    assert pointer.read_bytes() == before
    assert [path.name for path in (tmp_path / "local_runs").iterdir()] == ["prior"]


def test_refresh_requires_real_contact_and_missing_artifacts_fail(tmp_path):
    with pytest.raises(ValueError, match="SEC contact"):
        build_snapshot(tmp_path, refresh=True, user_agent="test@example.com")
    with pytest.raises(ValueError, match="missing market artifact"):
        build_snapshot(tmp_path)


def test_launcher_rejects_network_binding(monkeypatch):
    from run_api import main

    monkeypatch.setattr("sys.argv", ["run_api.py", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_saved_market_prefers_verified_latest_snapshot_over_legacy(tmp_path):
    legacy = tmp_path / "market_evaluation"
    legacy.mkdir()
    (legacy / "manifest.json").write_text('{"as_of":"2026-07-22"}')
    latest = seal_market(tmp_path, as_of="2026-09-08", screening_as_of="2026-07-22")
    assert saved_market_source(tmp_path) == latest


@pytest.mark.parametrize("defect", ["pointer_hash", "artifact", "escape", "unsealed_market", "missing_snapshot"])
def test_bad_saved_snapshot_fails_without_falling_back_or_changing_pointer(tmp_path, defect):
    market = seal_market(tmp_path)
    pointer_path = tmp_path / "local_latest.json"
    pointer = json.loads(pointer_path.read_text())
    if defect == "pointer_hash":
        pointer["snapshot_sha256"] = "0" * 64
    elif defect == "artifact":
        (market / "companies.csv").write_text("tampered")
    elif defect == "escape":
        pointer["snapshot_directory"] = "local_runs/../../outside"
    elif defect == "unsealed_market":
        manifest_path = market.parent / "snapshot.json"
        manifest_path.write_text(json.dumps({"artifact_sha256": {}}))
        pointer["snapshot_sha256"] = sha256(manifest_path)
    else:
        (market.parent / "snapshot.json").unlink()
    pointer_path.write_text(json.dumps(pointer))
    before = pointer_path.read_bytes()
    with pytest.raises(ValueError):
        build_snapshot(tmp_path, refresh_public=True)
    assert pointer_path.read_bytes() == before
    assert [path.name for path in (tmp_path / "local_runs").iterdir()] == ["prior"]


@pytest.mark.parametrize("flags", [
    {"refresh": True, "refresh_public": True},
    {"rebuild_market": True, "refresh_public": True},
    {"rebuild_market": True, "refresh": True},
])
def test_build_modes_are_mutually_exclusive(tmp_path, flags):
    with pytest.raises(ValueError, match="choose only one"):
        build_snapshot(tmp_path, **flags)


@pytest.mark.parametrize("mode", ["refresh_public", "rebuild_market"])
def test_partial_build_seals_history_and_retains_sec_cutoff_from_latest_snapshot(tmp_path, monkeypatch, mode):
    from datetime import date
    import scripts.run_local_research as pipeline

    repo = tmp_path / "repo"
    output = tmp_path / "output"
    old_sec = "2026-07-22"
    seal_market(output, as_of=str(date.today()), screening_as_of=old_sec)
    for directory in ("study_integrity", "execution_risk", "execution_markers"):
        destination = repo / "data" / directory
        destination.mkdir(parents=True)
        filename = "markers.json" if directory == "execution_markers" else "evidence.json"
        (destination / filename).write_text(json.dumps({"as_of": old_sec}))
    history = repo / "data/history"
    history.mkdir()
    (history / "status.json").write_text('{"trained":false}')
    (history / "frozen_labels.json").write_text('{"labels":[]}')
    (history / "raw_sources").mkdir()
    (history / "raw_sources/large.bin").write_bytes(b"raw evidence omitted")
    script_names = ("run_local_research.py", "evaluate_market.py", "evaluate_study_integrity.py",
                    "evaluate_execution_risk.py", "build_execution_scorecard.py", "build_strategic_matrix.py")
    (repo / "scripts").mkdir()
    for name in script_names:
        (repo / "scripts" / name).write_text("# fixture code\n")
    (repo / "src/research").mkdir(parents=True)
    (repo / "src/__init__.py").write_text("")
    (repo / "requirements.txt").write_text("")
    monkeypatch.setattr(pipeline, "ROOT", repo)
    calls = []

    def local_fixture_script(name, *args):
        calls.append((name, [str(arg) for arg in args]))
        destination = Path(args[args.index("--output-dir") + 1])
        destination.mkdir()
        (destination / "companies.csv").write_text(
            "ticker,company_name,research_score,risk_set_eligible,approved_asset_count,clinical_asset_count,evidence_coverage\n"
            "ACME,Acme Bio,5,True,0,0,unknown\n")
        if name == "evaluate_market.py":
            manifest = {
                "as_of": str(date.today()), "sec_transaction_screening_as_of": old_sec,
                "sec_transaction_screening_status": {"status": "cache_only_not_current", "current": False},
                "freshness": {"status": "stale_or_unknown"},
            }
        else:
            manifest = {}
        (destination / "manifest.json").write_text(json.dumps(manifest))

    monkeypatch.setattr(pipeline, "run_script", local_fixture_script)
    final = build_snapshot(output, **{mode: True})
    args = calls[0][1]
    assert calls[0][0] == "evaluate_market.py"
    assert ("--refresh-public" if mode == "refresh_public" else "--offline") in args
    assert "--refresh" not in args
    assert "--user-agent" not in args
    assert args[args.index("--sec-screening-as-of") + 1] == old_sec
    assert args[args.index("--as-of") + 1] == str(date.today())
    manifest = verify_snapshot(final)
    assert manifest["source_mode"] == ("refreshed_public_sec_cache_only" if mode == "refresh_public" else "offline_market_rebuild")
    assert manifest["sec_transaction_screening_as_of"] == old_sec
    assert manifest["sec_transaction_screening_status"]["current"] is False
    assert manifest["market_source_freshness"]["status"] == "stale_or_unknown"
    assert "historical_training/status.json" in manifest["artifact_sha256"]
    assert "historical_training/frozen_labels.json" in manifest["artifact_sha256"]
    assert not (final / "historical_training/raw_sources").exists()
    assert saved_market_source(output) == final / "market_evaluation"
