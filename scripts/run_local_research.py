#!/usr/bin/env python3
"""Build and seal a local research snapshot, then atomically publish its pointer.

By default this uses the existing market artifacts without network access.
--refresh explicitly fetches a new current market snapshot from public sources.
--refresh-public updates Nasdaq/FDA/Clinical inputs while keeping SEC cache-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_script(name: str, *args: object) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / name),
                    *(str(arg) for arg in args)], cwd=ROOT, check=True)


def verify_snapshot(directory: Path) -> dict:
    """Verify every sealed artifact before presenting a snapshot as reproducible."""
    manifest = read_json(directory / "snapshot.json")
    for relative, expected in manifest["artifact_sha256"].items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError(f"missing or invalid snapshot artifact: {relative}")
        if sha256(path) != expected:
            raise ValueError(f"snapshot artifact changed: {relative}")
    return manifest


def saved_market_source(output_root: Path) -> Path:
    """Use the last sealed market inputs without silently rolling back to legacy."""
    pointer_path = output_root / "local_latest.json"
    if not pointer_path.exists():
        return output_root / "market_evaluation"
    pointer = read_json(pointer_path)
    relative = pointer.get("snapshot_directory") if isinstance(pointer, dict) else None
    if not isinstance(relative, str):
        raise ValueError("invalid saved snapshot pointer")
    relative_path = Path(relative)
    directory = (output_root / relative_path).resolve()
    if (relative_path.is_absolute() or ".." in relative_path.parts
            or not relative_path.parts or relative_path.parts[0] != "local_runs"
            or not directory.is_relative_to((output_root / "local_runs").resolve())
            or not directory.is_relative_to(output_root.resolve())):
        raise ValueError("saved snapshot pointer escapes local_runs")
    snapshot_path = directory / "snapshot.json"
    if not snapshot_path.is_file() or sha256(snapshot_path) != pointer.get("snapshot_sha256"):
        raise ValueError("saved snapshot manifest hash mismatch")
    manifest = verify_snapshot(directory)
    sealed = manifest["artifact_sha256"]
    if not all(f"market_evaluation/{name}" in sealed for name in ("manifest.json", "companies.csv")):
        raise ValueError("saved snapshot does not seal required market inputs")
    return directory / "market_evaluation"


def write_coverage_queue(snapshot: Path) -> None:
    with (snapshot / "market_evaluation/companies.csv").open(newline="") as handle:
        market = list(csv.DictReader(handle))
    with (snapshot / "execution_scorecard/companies.csv").open(newline="") as handle:
        risk = {row["ticker"]: row for row in csv.DictReader(handle)}
    queue = []
    for row in market:
        coverage = risk.get(row["ticker"], {}).get("evidence_coverage", "unknown")
        assets = int(row.get("approved_asset_count") or 0) + int(row.get("clinical_asset_count") or 0)
        if assets and coverage == "company_specific_evidence":
            continue
        queue.append({
            "ticker": row["ticker"], "company_name": row["company_name"],
            "risk_set_eligible": row.get("risk_set_eligible", "False"),
            "research_score": row["research_score"], "matched_asset_count": assets,
            "risk_coverage": coverage,
            "next_action": ("Review subsidiary/licensing ownership and unmatched sponsor records; " if not assets else "")
                           + ("Collect primary-source company risk evidence" if coverage != "company_specific_evidence" else ""),
        })
    queue.sort(key=lambda row: (row["risk_set_eligible"].lower() != "true", -float(row["research_score"]), row["ticker"]))
    with (snapshot / "coverage_review.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["ticker", "company_name", "risk_set_eligible", "research_score",
                  "matched_asset_count", "risk_coverage", "next_action"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(queue)


def build_snapshot(output_root: Path, *, refresh: bool = False, user_agent: str = "",
                   rebuild_market: bool = False, refresh_public: bool = False) -> Path:
    output_root = output_root.resolve()
    if sum((refresh, refresh_public, rebuild_market)) > 1:
        raise ValueError("choose only one of --refresh, --refresh-public, or --rebuild-market")
    if refresh and (not user_agent.strip() or "example.com" in user_agent):
        raise ValueError("--refresh requires --user-agent with your real SEC contact information")
    # Source dates stay attached to copied inputs. A new build time never updates them.
    market_source = saved_market_source(output_root) if not refresh else output_root / "market_evaluation"
    if not refresh:
        for name in ("companies.csv", "manifest.json"):
            if not (market_source / name).is_file():
                raise ValueError(f"missing market artifact {market_source / name}; fetch with --refresh")
        source_manifest = read_json(market_source / "manifest.json")
        for relative, expected in source_manifest.get("output_sha256", {}).items():
            path = (market_source / relative).resolve()
            if not path.is_relative_to(market_source.resolve()) or not path.is_file() or sha256(path) != expected:
                raise ValueError(f"market artifact hash mismatch: {relative}")
        if refresh_public or rebuild_market:
            # Keep the exact old query date: changing it changes every SEC URL
            # and would require uncached observations that this mode forbids.
            screening_as_of = date.fromisoformat(source_manifest.get(
                "sec_transaction_screening_as_of", source_manifest["as_of"]))
            if screening_as_of > date.today():
                raise ValueError("SEC screening cutoff is in the future")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    runs = output_root / "local_runs"
    runs.mkdir(parents=True, exist_ok=True)
    staging = runs / f".{run_id}.incomplete"
    final = runs / run_id
    staging.mkdir()
    try:
        evidence = staging / "inputs"
        evidence.mkdir()
        for directory in ("study_integrity", "execution_risk", "execution_markers"):
            shutil.copytree(ROOT / "data" / directory, evidence / directory,
                            ignore=shutil.ignore_patterns("raw"))
        if refresh:
            run_script("evaluate_market.py", "--refresh", "--as-of", date.today(),
                       "--user-agent", user_agent, "--output-dir", staging / "market_evaluation")
        elif refresh_public:
            run_script("evaluate_market.py", "--refresh-public", "--as-of", date.today(),
                       "--sec-screening-as-of", screening_as_of,
                       "--output-dir", staging / "market_evaluation")
        elif rebuild_market:
            run_script("evaluate_market.py", "--offline", "--allow-stale", "--as-of", source_manifest["as_of"],
                       "--sec-screening-as-of", screening_as_of,
                       "--output-dir", staging / "market_evaluation")
        else:
            shutil.copytree(market_source, staging / "market_evaluation")
        # Preserve historical review evidence for the desk without promoting it.
        history = output_root / "historical_deal_candidates"
        if history.is_dir():
            shutil.copytree(history, staging / "historical_deal_candidates")
        history_training = ROOT / "data" / "history"
        if history_training.is_dir():
            shutil.copytree(history_training, staging / "historical_training",
                            ignore=shutil.ignore_patterns("raw*", "external_raw", "sec_financial_raw"))
        market_manifest = read_json(staging / "market_evaluation/manifest.json")
        source_dates = {"market": market_manifest["as_of"]}
        for directory in ("study_integrity", "execution_risk", "execution_markers"):
            name = "markers.json" if directory == "execution_markers" else "evidence.json"
            source_dates[directory] = read_json(evidence / directory / name)["as_of"]
        # This is a current assembly of dated inputs, never a historical replay.
        cutoff = max(date.fromisoformat(value) for value in source_dates.values())
        if cutoff > date.today():
            raise ValueError("input evidence date is in the future")
        run_script("evaluate_study_integrity.py", "--evidence-file", evidence / "study_integrity/evidence.json",
                   "--output-dir", staging / "study_integrity")
        integrity_manifest_path = staging / "study_integrity/manifest.json"
        integrity_manifest = read_json(integrity_manifest_path)
        integrity_manifest["source_file"] = "inputs/study_integrity/evidence.json"
        integrity_manifest_path.write_text(json.dumps(integrity_manifest, indent=2) + "\n")
        run_script("evaluate_execution_risk.py", "--evidence-file", evidence / "execution_risk/evidence.json",
                   "--output-dir", staging / "execution_risk")
        run_script("build_execution_scorecard.py", "--market-companies", staging / "market_evaluation/companies.csv",
                   "--integrity-companies", staging / "study_integrity/companies.csv",
                   "--execution-companies", staging / "execution_risk/companies.csv",
                   "--markers", evidence / "execution_markers/markers.json", "--as-of", cutoff,
                   "--output-dir", staging / "execution_scorecard")
        run_script("build_strategic_matrix.py", "--market-companies", staging / "market_evaluation/companies.csv",
                   "--integrity-companies", staging / "study_integrity/companies.csv",
                   "--execution-companies", staging / "execution_risk/companies.csv",
                   "--execution-scorecard", staging / "execution_scorecard/companies.csv",
                   "--output-dir", staging / "strategic_matrix")
        write_coverage_queue(staging)
        code_files = [ROOT / "scripts" / name for name in (
            "run_local_research.py", "evaluate_market.py", "evaluate_study_integrity.py",
            "evaluate_execution_risk.py", "build_execution_scorecard.py", "build_strategic_matrix.py")]
        code_files += sorted((ROOT / "src/research").glob("*.py"))
        code_files += [ROOT / "requirements.txt", ROOT / "src/__init__.py"]
        for path in code_files:
            destination = staging / "code" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        manifest = {
            "schema_version": "local-research-snapshot-v1", "run_id": run_id,
            "built_at": datetime.now(timezone.utc).isoformat(), "source_as_of": source_dates,
            "source_mode": ("refreshed_market" if refresh else "refreshed_public_sec_cache_only" if refresh_public
                            else "offline_market_rebuild" if rebuild_market else "existing_artifacts"),
            "sec_transaction_screening_as_of": market_manifest.get("sec_transaction_screening_as_of"),
            "sec_transaction_screening_status": market_manifest.get("sec_transaction_screening_status", {
                "status": "legacy_unverified", "current": False,
                "reason": "Legacy market artifacts do not record a separate SEC screening cutoff."}),
            "historical_replay_available": False, "validated_prediction": False,
            "python_version": sys.version,
            "cutoff_age_days": {key: (date.today() - date.fromisoformat(value)).days
                                for key, value in source_dates.items()},
            "market_source_freshness": market_manifest.get("freshness", {
                "status": "unknown", "reason": "Legacy artifacts lack source retrieval lineage; as_of is only a scoring cutoff."}),
            "market_input_provenance": ("recorded_source_hashes" if market_manifest.get("source_snapshots")
                                         and market_manifest.get("output_sha256") else "legacy_unverified"),
            "code_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in code_files},
            "artifact_sha256": {str(path.relative_to(staging)): sha256(path)
                                for path in sorted(staging.rglob("*")) if path.is_file()},
        }
        (staging / "snapshot.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        verify_snapshot(staging)
        staging.rename(final)
        pointer = {"snapshot_directory": str(final.relative_to(output_root)),
                   "snapshot_sha256": sha256(final / "snapshot.json"), "run_id": run_id}
        temporary = output_root / f".local_latest.{run_id}.json"
        temporary.write_text(json.dumps(pointer, indent=2) + "\n")
        os.replace(temporary, output_root / "local_latest.json")
        return final
    except BaseException:
        # A failed build is never published; retain completed prior snapshots.
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--refresh-public", action="store_true",
                      help="Refresh Nasdaq/FDA/Clinical inputs; retain verified SEC cache at its original screening cutoff")
    mode.add_argument("--rebuild-market", action="store_true", help="Re-evaluate cached raw market inputs offline, preserving their original cutoff")
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", ""))
    parser.add_argument("--verify", type=Path, help="Verify an existing snapshot without rebuilding")
    args = parser.parse_args()
    try:
        if args.verify:
            manifest = verify_snapshot(args.verify)
            print(f"Verified snapshot {manifest['run_id']}")
        else:
            path = build_snapshot(args.output_root, refresh=args.refresh, user_agent=args.user_agent,
                                  rebuild_market=args.rebuild_market, refresh_public=args.refresh_public)
            print(f"Published local research snapshot: {path}")
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Local research build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
