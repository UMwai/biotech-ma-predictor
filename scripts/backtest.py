#!/usr/bin/env python3
"""
Inspect heuristic scores for 11 hand-entered known acquisition cases.

This is a descriptive diagnostic without contemporaneous controls or verified
point-in-time inputs. It cannot establish predictive accuracy or calibration.

Usage:
    python3 scripts/backtest.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.score_companies import (
    score_pipeline, score_financial, score_strategic_fit,
    score_regulatory, score_patent, score_insider, WEIGHTS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Known completed biotech acquisitions (2023-2025)
# Using PRE-ACQUISITION data (market cap before deal announcement)
COMPLETED_DEALS = [
    {
        "target_ticker": "ITCI",
        "target_name": "Intra-Cellular Therapies",
        "acquirer": "Johnson & Johnson",
        "deal_value": 14_100_000_000,
        "date": "2025-01",
        "ta": ["neurology"],
        "pre_deal_market_cap": 9_500_000_000,
        "lead_asset": "Caplyta",
        "phase": "APPROVED",
        "indication": "Schizophrenia/Bipolar depression",
        "mechanism": "5-HT2A/D receptor modulator",
        "orphan": 0, "breakthrough": 0, "fast_track": 0,
        "cash": 800_000_000, "burn": 50_000_000, "runway_q": 16,
    },
    {
        "target_ticker": "CERE_DEAL",
        "target_name": "Cerevel Therapeutics",
        "acquirer": "AbbVie",
        "deal_value": 8_700_000_000,
        "date": "2024-01",
        "ta": ["neurology"],
        "pre_deal_market_cap": 4_200_000_000,
        "lead_asset": "Emraclidine",
        "phase": "PHASE_2",
        "indication": "Schizophrenia",
        "mechanism": "M4 PAM",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 700_000_000, "burn": 60_000_000, "runway_q": 12,
    },
    {
        "target_ticker": "KRTX_DEAL",
        "target_name": "Karuna Therapeutics",
        "acquirer": "Bristol-Myers Squibb",
        "deal_value": 14_000_000_000,
        "date": "2024-01",
        "ta": ["neurology"],
        "pre_deal_market_cap": 7_500_000_000,
        "lead_asset": "KarXT",
        "phase": "NDA_BLA",
        "indication": "Schizophrenia",
        "mechanism": "Muscarinic agonist",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 900_000_000, "burn": 80_000_000, "runway_q": 11,
    },
    {
        "target_ticker": "MRTX_DEAL",
        "target_name": "Mirati Therapeutics",
        "acquirer": "Bristol-Myers Squibb",
        "deal_value": 5_800_000_000,
        "date": "2024-01",
        "ta": ["oncology"],
        "pre_deal_market_cap": 3_400_000_000,
        "lead_asset": "Krazati (adagrasib)",
        "phase": "APPROVED",
        "indication": "KRAS G12C NSCLC",
        "mechanism": "KRAS G12C inhibitor",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 600_000_000, "burn": 100_000_000, "runway_q": 6,
    },
    {
        "target_ticker": "SGEN_DEAL",
        "target_name": "Seagen",
        "acquirer": "Pfizer",
        "deal_value": 43_000_000_000,
        "date": "2023-12",
        "ta": ["oncology"],
        "pre_deal_market_cap": 28_000_000_000,
        "lead_asset": "Adcetris + Padcev + Tukysa",
        "phase": "APPROVED",
        "indication": "Multiple cancers (ADC platform)",
        "mechanism": "Antibody-drug conjugate",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 2_000_000_000, "burn": 200_000_000, "runway_q": 10,
    },
    {
        "target_ticker": "PROM_DEAL",
        "target_name": "Prometheus Biosciences",
        "acquirer": "Merck",
        "deal_value": 10_800_000_000,
        "date": "2023-06",
        "ta": ["immunology"],
        "pre_deal_market_cap": 5_200_000_000,
        "lead_asset": "PRA023",
        "phase": "PHASE_2",
        "indication": "Ulcerative colitis / Crohn's",
        "mechanism": "Anti-TL1A antibody",
        "orphan": 0, "breakthrough": 0, "fast_track": 1,
        "cash": 400_000_000, "burn": 50_000_000, "runway_q": 8,
    },
    {
        "target_ticker": "HZNP_DEAL",
        "target_name": "Horizon Therapeutics",
        "acquirer": "Amgen",
        "deal_value": 27_800_000_000,
        "date": "2023-10",
        "ta": ["rare_disease", "immunology"],
        "pre_deal_market_cap": 17_000_000_000,
        "lead_asset": "Tepezza + Krystexxa",
        "phase": "APPROVED",
        "indication": "TED / Gout",
        "mechanism": "IGF-1R inhibitor / PEGylated uricase",
        "orphan": 1, "breakthrough": 1, "fast_track": 1,
        "cash": 1_500_000_000, "burn": 100_000_000, "runway_q": 15,
    },
    {
        "target_ticker": "CINC_DEAL",
        "target_name": "CinCor Pharma",
        "acquirer": "AstraZeneca",
        "deal_value": 1_800_000_000,
        "date": "2023-03",
        "ta": ["cardiovascular"],
        "pre_deal_market_cap": 800_000_000,
        "lead_asset": "Baxdrostat",
        "phase": "PHASE_2",
        "indication": "Resistant hypertension",
        "mechanism": "Aldosterone synthase inhibitor",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 200_000_000, "burn": 30_000_000, "runway_q": 7,
    },
    {
        "target_ticker": "IMGO_DEAL",
        "target_name": "Immunomedics (Gilead acq'd)",
        "acquirer": "Gilead",
        "deal_value": 21_000_000_000,
        "date": "2020-09",
        "ta": ["oncology"],
        "pre_deal_market_cap": 12_000_000_000,
        "lead_asset": "Trodelvy",
        "phase": "APPROVED",
        "indication": "Triple-negative breast cancer",
        "mechanism": "Trop-2 ADC",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 800_000_000, "burn": 100_000_000, "runway_q": 8,
    },
    {
        "target_ticker": "METS_DEAL",
        "target_name": "Metsera",
        "acquirer": "Pfizer",
        "deal_value": 10_000_000_000,
        "date": "2025-11",
        "ta": ["metabolic"],
        "pre_deal_market_cap": 5_000_000_000,
        "lead_asset": "MET-001",
        "phase": "PHASE_3",
        "indication": "Obesity (monthly GLP-1)",
        "mechanism": "GLP-1 receptor agonist",
        "orphan": 0, "breakthrough": 0, "fast_track": 1,
        "cash": 500_000_000, "burn": 80_000_000, "runway_q": 6,
    },
    {
        "target_ticker": "89BIO_DEAL",
        "target_name": "89bio",
        "acquirer": "Roche",
        "deal_value": 3_500_000_000,
        "date": "2025-Q1",
        "ta": ["metabolic"],
        "pre_deal_market_cap": 1_800_000_000,
        "lead_asset": "Pegozafermin",
        "phase": "PHASE_3",
        "indication": "MASH",
        "mechanism": "FGF21 analog",
        "orphan": 0, "breakthrough": 1, "fast_track": 1,
        "cash": 300_000_000, "burn": 40_000_000, "runway_q": 8,
    },
]


def score_deal(deal: dict) -> dict:
    """Score a historical deal target using our scoring components."""
    # Build fake company dict
    company = {
        "market_cap_usd": deal["pre_deal_market_cap"],
        "cash_position_usd": deal.get("cash", 100_000_000),
        "quarterly_burn_rate_usd": deal.get("burn", 50_000_000),
        "runway_quarters": deal.get("runway_q"),
        "therapeutic_areas": json.dumps(deal["ta"]),
    }

    # Build fake drug dict
    drugs = [{
        "name": deal["lead_asset"],
        "phase": deal["phase"],
        "therapeutic_area": deal["ta"][0],
        "orphan_designation": deal.get("orphan", 0),
        "breakthrough_therapy": deal.get("breakthrough", 0),
        "fast_track": deal.get("fast_track", 0),
        "priority_review": 0,
    }]

    pipeline, _ = score_pipeline(drugs)
    financial, _ = score_financial(company)
    strategic, _ = score_strategic_fit(company, drugs)
    regulatory, _ = score_regulatory(drugs)
    patent, _ = score_patent(drugs)
    insider, _ = score_insider()

    total = (
        WEIGHTS["pipeline"] * pipeline +
        WEIGHTS["financial"] * financial +
        WEIGHTS["strategic_fit"] * strategic +
        WEIGHTS["regulatory"] * regulatory +
        WEIGHTS["patent"] * patent +
        WEIGHTS["insider"] * insider
    )

    return {
        "ticker": deal["target_ticker"],
        "name": deal["target_name"],
        "acquirer": deal["acquirer"],
        "deal_value": deal["deal_value"],
        "date": deal["date"],
        "total_score": round(total, 1),
        "pipeline": round(pipeline, 1),
        "financial": round(financial, 1),
        "strategic": round(strategic, 1),
        "regulatory": round(regulatory, 1),
    }


def build_known_deal_diagnostic() -> dict:
    """Describe selected known-positive cases without making validation claims."""
    results = sorted(
        (score_deal(deal) for deal in COMPLETED_DEALS),
        key=lambda row: -row["total_score"],
    )
    return {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "schema_version": "known-deal-diagnostic-v1",
        "evaluation_type": "known_positive_case_diagnostic",
        "score_semantics": "heuristic research scores; not calibrated acquisition probabilities",
        "validation_status": "unvalidated",
        "total_deals": len(results),
        "negative_controls": 0,
        "avg_score": round(sum(row["total_score"] for row in results) / len(results), 1),
        "ranking_metrics": None,
        "probability_metrics": None,
        "limitations": [
            "Selected known acquisition cases only; no contemporaneous negative controls.",
            "Hand-entered features have no verified point-in-time availability.",
            "Scores do not establish accuracy, precision, lift, or probability calibration.",
        ],
        "results": results,
    }


async def run_backtest(output_path: Path | None = None) -> dict:
    """Retained command entry point for the descriptive known-deal diagnostic."""
    diagnostic = build_known_deal_diagnostic()
    logger.info("Known-deal heuristic diagnostic: %s selected positive cases", diagnostic["total_deals"])
    logger.info("Validation unavailable: no contemporaneous controls or verified historical inputs")
    if output_path is None:
        output_path = Path(__file__).parent.parent / "output" / "backtest_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(diagnostic, indent=2) + "\n", encoding="utf-8")
    logger.info("Diagnostic saved to %s", output_path)
    return diagnostic


if __name__ == "__main__":
    asyncio.run(run_backtest())
