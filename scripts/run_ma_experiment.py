#!/usr/bin/env python3
"""Register, prepare ratings, or attempt source-bound retrospective M&A research."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.ma_experiment import DISCLOSURES, rating_template, register, run_experiment  # noqa: E402
from src.research.training import write_immutable_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    registration = commands.add_parser("register")
    registration.add_argument("--parameters", type=Path, required=True)
    for name in ("template", "run"):
        command = commands.add_parser(name)
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--registration", type=Path, required=True)
        if name == "run":
            command.add_argument("--ratings", type=Path)
            command.add_argument("--evidence-root", type=Path)
    for command in (registration, commands.choices["template"], commands.choices["run"]):
        command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "register":
            artifact = register(args.parameters, args.output_dir)
        elif args.command == "template":
            artifact = rating_template(args.dataset, args.registration, args.output_dir)
        else:
            report, artifact = run_experiment(args.dataset, args.registration, args.output_dir,
                ratings_path=args.ratings, evidence_root=args.evidence_root)
            print(json.dumps({"status": report["status"], "artifact": str(artifact), "readiness": report["readiness"], **DISCLOSURES}))
            return 0 if report["weighted_model_evaluated"] else 2
        print(json.dumps({"status": args.command, "artifact": str(artifact), **DISCLOSURES}))
        return 0
    except Exception as exc:  # Persist unexpected failures as well as input-contract errors.
        failure = {"schema_version": "ma-experiment-v1", "status": "blocked", "command": args.command,
            "created_at": datetime.now(timezone.utc).isoformat(), "reason": str(exc), "hashes": None,
            "model_training_performed": False, "weighted_model_evaluated": False, "predictions": None, "metrics": None, **DISCLOSURES}
        try:
            failure["artifact"] = str(write_immutable_json(failure, args.output_dir, "ma-failed-attempt"))
        except (ValueError, OSError) as artifact_error:
            failure["artifact_error"] = str(artifact_error)
        print(json.dumps(failure), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
