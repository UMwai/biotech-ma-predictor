#!/usr/bin/env python3
"""Run the local research desk. No cloud or database services are required."""

import argparse
import ipaddress
import os
from pathlib import Path

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    try:
        local = args.host == "localhost" or ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        local = False
    if not local:
        parser.error("The local research desk must bind to a loopback address.")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    os.environ["BIOTECH_OUTPUT_DIR"] = str(args.output_dir.resolve())
    uvicorn.run("src.local_app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
