#!/usr/bin/env python3
"""Replay explicit archived SEC PPH schedules locally; no fetching or ratings."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.ma_buyer_universe import build  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build(args.manifest, args.evidence_root, args.output_dir)
    except Exception as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "model_training_performed": False}), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
