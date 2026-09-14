#!/usr/bin/env python3
"""Collect PIT SEC financial inputs only; see docs/HISTORICAL_FINANCIALS.md."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.financial_history import FinancialSourceBlocked, collect_financial_history, parse_cutoff  # noqa: E402
from src.research.sources import HttpCache  # noqa: E402


def load_ciks(path: Path) -> list[int]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        values = [row.get("cik") or row.get("target_cik") for row in rows]
    else:
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("labels"), list):
            values = [row.get("target_cik") for row in data["labels"]]
        elif isinstance(data, dict) and isinstance(data.get("ciks"), list):
            values = data["ciks"]
        else:
            raise ValueError("CIK input must be frozen labels JSON, a ciks array, or a CSV with cik/target_cik")
    if not values or any(isinstance(value, bool) or not str(value).strip().isdigit()
                         or not 0 < int(value) < 10**10 for value in values):
        raise ValueError("CIK input must contain positive SEC issuer identifiers")
    return sorted({int(value) for value in values})


def write_json(value: dict, output_dir: Path, prefix: str) -> Path:
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}-{hashlib.sha256(raw).hexdigest()}.json"
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".financial-", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("immutable financial artifact differs from its content hash")
    finally:
        temporary.unlink(missing_ok=True)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ciks", type=Path, required=True, help="Frozen-label JSON or CIK CSV")
    parser.add_argument("--cutoff", action="append", required=True, help="Repeat for multiple dates/aware timestamps")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data" / "history" / "sec_financial_raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "historical_financials")
    parser.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT", ""))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--max-submission-files", type=int, default=10)
    args = parser.parse_args(argv)
    cache = None
    try:
        ciks = load_ciks(args.ciks)
        cutoffs = [parse_cutoff(value) for value in args.cutoff]
        cache = HttpCache(args.cache_dir, args.user_agent, offline=args.offline)
        result = collect_financial_history(ciks, cutoffs, cache, refresh=args.refresh,
                                          max_submission_files=args.max_submission_files)
        source_hash = hashlib.sha256(args.ciks.read_bytes()).hexdigest()
        result["issuer_input_sha256"] = source_hash
        snapshot_path = write_json(result, args.output_dir, "financial-snapshots")
        manifest = {"schema_version": "sec-financial-collection-manifest-v1", "status": "features_collected",
                    "training_allowed": False, "collected_at": result["collected_at"],
                    "issuer_input_sha256": source_hash, "cutoffs": [cutoff.isoformat() for cutoff in sorted(set(cutoffs))],
                    "coverage": result["coverage"], "source_receipts": result["source_receipts"],
                    "feature_artifact": str(snapshot_path),
                    "feature_artifact_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest()}
        manifest_path = write_json(manifest, args.output_dir, "manifest")
        print(json.dumps({"status": "features_collected", "training_allowed": False,
                          "features": str(snapshot_path), "manifest": str(manifest_path), "coverage": result["coverage"]}))
        return 0
    except (ValueError, OSError) as exc:
        receipt = {"schema_version": "sec-financial-collection-manifest-v1", "status": "blocked",
                   "training_allowed": False, "reason": str(exc),
                   "source_receipts": list(cache.source_snapshots.values()) if cache else []}
        if isinstance(exc, FinancialSourceBlocked):
            receipt["blocked_request"] = exc.receipt
        try:
            receipt_path = write_json(receipt, args.output_dir, "blocked")
            receipt["receipt_path"] = str(receipt_path)
        except (ValueError, OSError):
            pass
        print(json.dumps(receipt), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
