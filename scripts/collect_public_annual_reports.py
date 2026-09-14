#!/usr/bin/env python3
"""Archive original annual-report PDFs; extraction candidates are never reviewed facts.

This collector only accesses public AnnualReports mirrors and explicit issuer URLs.
It makes no SEC requests. Downloading a PDF does not establish its filing date,
historical membership, a negative label, or eligibility for model training.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import requests
import time


def collect(ticker: str, year: int, root: Path) -> dict:
    path = root / "raw" / f"{ticker}_{year}.pdf"
    if path.exists():
        return {"ticker": ticker, "fiscal_year": year, "cached_existing": True,
                "source_relative_path": str(path.relative_to(root)),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    url = ("https://www.annualreports.com/HostedData/AnnualReportArchive/"
           f"{ticker[0].lower()}/NASDAQ_{ticker}_{year}.pdf")
    receipt = {"ticker": ticker, "fiscal_year": year, "source_url": url,
               "retrieved_at": datetime.now(timezone.utc).isoformat(),
               "raw_bytes_archived": False, "financial_facts_reviewed": False}
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        receipt.update(http_status=response.status_code, resolved_url=response.url)
        if response.ok and response.content.startswith(b"%PDF"):
            path.write_bytes(response.content)
            receipt.update(source_relative_path=str(path.relative_to(root)),
                           source_sha256=hashlib.sha256(response.content).hexdigest(),
                           source_bytes=len(response.content), raw_bytes_archived=True)
        elif response.ok:
            receipt["rejection_reason"] = "not PDF bytes"
    except requests.RequestException as exc:
        receipt["error"] = str(exc)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--cohort", choices=["controls", "positives"])
    parser.add_argument("--output", type=Path, default=Path("data/history/panel_financials"))
    parser.add_argument("--request-interval", type=float, default=2.0)
    args = parser.parse_args()
    pairs = []
    if args.cohort == "controls":
        payload = json.loads(Path("data/history/control_seed/window_review_receipts.json").read_text())
        tickers = [item["historical_ticker"] for item in payload["records"]]
        pairs = [(ticker, year) for ticker in tickers for year in (args.years or [2020, 2022, 2023])]
    elif args.cohort == "positives":
        payload = json.loads(Path("data/history/frozen_labels.json").read_text())
        for item in payload["labels"]:
            announced = datetime.fromisoformat(item["announcement_date"])
            # A request target only: actual filing availability must be verified.
            year = min(2023, announced.year - (2 if announced.month < 4 else 1))
            pairs.append((item["target_ticker"], year))
    elif args.tickers and args.years:
        pairs = [(ticker, year) for ticker in args.tickers for year in args.years]
    else:
        parser.error("provide --cohort or both --tickers and --years")
    if args.request_interval < 1 or any(year < 2016 or year > 2023 for _, year in pairs):
        parser.error("request interval must be at least 1 second and historical report years 2016..2023")
    (args.output / "raw").mkdir(parents=True, exist_ok=True)
    receipts_path = args.output / "download_receipts.json"
    receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else []
    for pair in sorted(set(pairs)):
        result = collect(*pair, args.output)
        if not result.get("cached_existing"):
            receipts.append(result)
            receipts_path.write_text(json.dumps(receipts, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        if result.get("http_status") == 429 or result.get("error"):
            print("Rate limit or connection error; collection stopped without retries.", flush=True)
            break
        if not result.get("cached_existing"):
            time.sleep(args.request_interval)


if __name__ == "__main__":
    main()
