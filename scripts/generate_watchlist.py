#!/usr/bin/env python3
"""
Legacy heuristic watchlist report with acquirer matches.

The optional command reads an existing SQLite database. The supported local
research desk uses its separate artifact pipeline; probabilities remain
unavailable in this compatibility report.

Usage:
    python3 scripts/generate_watchlist.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "biotech_ma.db"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Top pharma acquirers with pipeline gaps
ACQUIRERS = [
    {"name": "Pfizer", "ticker": "PFE", "ta": ["oncology", "metabolic", "immunology", "rare_disease"], "gaps": ["obesity/GLP-1", "ADC platform", "gene therapy"], "recent_deals": ["Seagen ($43B)", "Metsera ($10B)"], "capacity": "high"},
    {"name": "Roche", "ticker": "RHHBY", "ta": ["oncology", "neurology", "immunology"], "gaps": ["obesity", "cell therapy", "ADC expansion"], "recent_deals": ["89bio ($3.5B)"], "capacity": "high"},
    {"name": "Johnson & Johnson", "ticker": "JNJ", "ta": ["immunology", "oncology", "neurology", "cardiovascular"], "gaps": ["CNS expansion", "autoimmune"], "recent_deals": ["Intra-Cellular ($14.1B)"], "capacity": "high"},
    {"name": "AbbVie", "ticker": "ABBV", "ta": ["immunology", "oncology", "neurology"], "gaps": ["neuroscience", "oncology pipeline"], "recent_deals": ["Cerevel ($8.7B)", "ImmunoGen ($10.1B)"], "capacity": "high"},
    {"name": "Merck", "ticker": "MRK", "ta": ["oncology", "immunology", "infectious_disease"], "gaps": ["non-Keytruda pipeline", "autoimmune"], "recent_deals": ["Prometheus ($10.8B)"], "capacity": "high"},
    {"name": "Bristol-Myers Squibb", "ticker": "BMY", "ta": ["oncology", "immunology", "cardiovascular", "neurology"], "gaps": ["growth pipeline post-Opdivo", "neurology"], "recent_deals": ["Karuna ($14B)", "Mirati ($5.8B)"], "capacity": "medium"},
    {"name": "AstraZeneca", "ticker": "AZN", "ta": ["oncology", "cardiovascular", "metabolic", "rare_disease"], "gaps": ["obesity", "cardiometabolic"], "recent_deals": ["CinCor ($1.8B)", "Alexion"], "capacity": "high"},
    {"name": "Eli Lilly", "ticker": "LLY", "ta": ["metabolic", "oncology", "neurology", "immunology"], "gaps": ["oncology expansion", "autoimmune"], "recent_deals": ["DICE Therapeutics ($2.4B)"], "capacity": "high"},
    {"name": "Novartis", "ticker": "NVS", "ta": ["oncology", "immunology", "neurology", "cardiovascular", "rare_disease"], "gaps": ["gene therapy", "obesity"], "recent_deals": ["Chinook ($3.5B)"], "capacity": "high"},
    {"name": "Gilead", "ticker": "GILD", "ta": ["oncology", "infectious_disease", "immunology"], "gaps": ["oncology diversification", "autoimmune"], "recent_deals": ["CymaBay ($4.3B)"], "capacity": "high"},
    {"name": "Amgen", "ticker": "AMGN", "ta": ["oncology", "immunology", "rare_disease", "metabolic"], "gaps": ["obesity", "rare disease"], "recent_deals": ["Horizon ($27.8B)"], "capacity": "medium"},
    {"name": "Sanofi", "ticker": "SNY", "ta": ["immunology", "rare_disease", "oncology"], "gaps": ["oncology", "neurology"], "recent_deals": ["Translate Bio", "Kadmon"], "capacity": "high"},
    {"name": "Daiichi Sankyo", "ticker": "DSNKY", "ta": ["oncology"], "gaps": ["ADC expansion", "solid tumors"], "recent_deals": ["AstraZeneca partnerships"], "capacity": "medium"},
]


def match_acquirers(company: dict, drugs: list[dict]) -> list[dict]:
    """Match a target company with potential acquirers."""
    ta_list = json.loads(company.get("therapeutic_areas", "[]")) if isinstance(company.get("therapeutic_areas"), str) else company.get("therapeutic_areas", [])
    market_cap = company.get("market_cap_usd", 0)
    matches = []

    for acq in ACQUIRERS:
        # Therapeutic overlap
        overlap = set(ta_list) & set(acq["ta"])
        overlap_score = (len(overlap) / max(len(ta_list), 1)) * 40 if ta_list else 0

        # Pipeline gap filling
        gap_score = 0
        drug_mechanisms = " ".join(d.get("mechanism", "").lower() for d in drugs)
        drug_indications = " ".join(d.get("indication", "").lower() for d in drugs)
        for gap in acq.get("gaps", []):
            gap_lower = gap.lower()
            if any(word in drug_mechanisms or word in drug_indications for word in gap_lower.split("/")):
                gap_score += 15
        gap_score = min(gap_score, 40)

        # Financial capacity
        if acq["capacity"] == "high":
            if market_cap < 10_000_000_000:
                capacity_score = 10
            else:
                capacity_score = 5
        elif acq["capacity"] == "medium":
            if market_cap < 5_000_000_000:
                capacity_score = 10
            else:
                capacity_score = 3
        else:
            capacity_score = 2

        total_fit = overlap_score + gap_score + capacity_score

        if total_fit > 20:
            rationale_parts = []
            if overlap:
                rationale_parts.append(f"TA overlap: {', '.join(overlap)}")
            if gap_score > 0:
                rationale_parts.append("Fills pipeline gap")
            rationale = "; ".join(rationale_parts) if rationale_parts else "General strategic interest"

            matches.append({
                "acquirer": acq["name"],
                "acquirer_ticker": acq["ticker"],
                "fit_score": round(total_fit, 1),
                "rationale": rationale,
            })

    matches.sort(key=lambda x: x["fit_score"], reverse=True)
    return matches[:3]


def build_watchlist_entry(company: dict, drugs: list[dict], rank: int) -> dict:
    """Create a heuristic watchlist row with an explicitly unavailable probability."""
    entry = {
        "rank": rank,
        "ticker": company["ticker"],
        "name": company["name"],
        "ma_score": company["total_score"],
        "market_cap_usd": company["market_cap_usd"],
        "cash_position_usd": company["cash_position_usd"],
        "runway_quarters": company["runway_quarters"],
        "therapeutic_areas": json.loads(company["therapeutic_areas"]) if isinstance(company["therapeutic_areas"], str) else company["therapeutic_areas"],
        "scores": {
            "pipeline": company["pipeline_score"],
            "financial": company["financial_score"],
            "strategic_fit": company["strategic_fit_score"],
            "regulatory": company["regulatory_score"],
            "patent": company["patent_score"],
            "insider": company["insider_score"],
        },
        "lead_asset": drugs[0]["name"] if drugs else "N/A",
        "lead_phase": drugs[0]["phase"] if drugs else "N/A",
        "lead_indication": drugs[0]["indication"] if drugs else "N/A",
        "key_drivers": json.loads(company.get("key_drivers", "[]")) if isinstance(company.get("key_drivers"), str) else [],
        "likely_acquirers": match_acquirers(company, drugs),
        "deal_probability_12mo": None,
        "probability_status": "unavailable_unvalidated_model",
        "score_semantics": "heuristic research score; not a calibrated acquisition probability",
    }
    return entry


async def generate_watchlist():
    """Generate the ranked watchlist with acquirer matches."""
    import aiosqlite

    logger.info("=== Generating M&A Watchlist ===\n")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get scored companies
        cursor = await db.execute(
            """SELECT c.*, s.total_score, s.pipeline_score, s.financial_score,
                      s.strategic_fit_score, s.regulatory_score, s.patent_score,
                      s.insider_score, s.key_drivers
               FROM companies c
               JOIN ma_scores s ON c.id = s.company_id
               ORDER BY s.total_score DESC"""
        )
        companies = [dict(row) for row in await cursor.fetchall()]

        watchlist = []
        for rank, company in enumerate(companies[:25], 1):
            company_id = company["id"]

            # Get drugs
            cursor = await db.execute(
                "SELECT * FROM drug_candidates WHERE company_id = ? AND deleted_at IS NULL",
                (company_id,),
            )
            drugs = [dict(d) for d in await cursor.fetchall()]

            entry = build_watchlist_entry(company, drugs, rank)
            watchlist.append(entry)

    # Print report
    logger.info(f"{'='*100}")
    logger.info(f"  BIOTECH M&A WATCHLIST — {datetime.now().strftime('%B %d, %Y')}")
    logger.info(f"  {len(watchlist)} Top Acquisition Candidates")
    logger.info(f"{'='*100}\n")

    for entry in watchlist[:20]:
        acq_str = ", ".join(f"{a['acquirer']} ({a['fit_score']:.0f})" for a in entry["likely_acquirers"][:2])
        logger.info(
            f"  #{entry['rank']:2d}  {entry['ticker']:>6}  {entry['name']:<35}  "
            f"Score: {entry['ma_score']:5.1f}  |  ${entry['market_cap_usd']/1e9:.1f}B  |  "
            f"{entry['lead_asset']:<20} ({entry['lead_phase']})"
        )
        if acq_str:
            logger.info(f"       {'':>6}  Likely acquirers: {acq_str}")
        logger.info("")

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "watchlist_latest.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "methodology": "6-component M&A scoring: pipeline (30%), financial (20%), strategic fit (20%), regulatory (15%), patent (10%), insider (5%)",
            "total_universe": len(companies),
            "watchlist": watchlist,
            "score_semantics": "heuristic research ranking; not calibrated acquisition probabilities",
            "validation_status": "unvalidated; the known-positive diagnostic does not establish predictive accuracy",
        }, f, indent=2)
    logger.info(f"Watchlist saved to {json_path}")

    # Save markdown report
    md_path = OUTPUT_DIR / "watchlist_latest.md"
    with open(md_path, "w") as f:
        f.write(f"# Biotech M&A Watchlist\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y')}\n")
        f.write(f"**Universe:** {len(companies)} companies\n")
        f.write(f"**Methodology:** 6-component scoring (pipeline 30%, financial 20%, strategic fit 20%, regulatory 15%, patent 10%, insider 5%)\n")
        f.write("**Validation:** Heuristic research ranking; acquisition probabilities and predictive accuracy are unavailable.\n\n")
        f.write(f"---\n\n")

        f.write(f"## Top 20 Acquisition Candidates\n\n")
        f.write(f"| Rank | Ticker | Company | Score | Mkt Cap | Lead Asset | Phase | Top Acquirer |\n")
        f.write(f"|------|--------|---------|-------|---------|------------|-------|-------------|\n")

        for entry in watchlist[:20]:
            top_acq = entry["likely_acquirers"][0]["acquirer"] if entry["likely_acquirers"] else "N/A"
            f.write(
                f"| {entry['rank']} | {entry['ticker']} | {entry['name']} | "
                f"{entry['ma_score']:.1f} | ${entry['market_cap_usd']/1e9:.1f}B | "
                f"{entry['lead_asset']} | {entry['lead_phase']} | {top_acq} |\n"
            )

        f.write(f"\n---\n\n")
        f.write(f"## Detailed Profiles\n\n")

        for entry in watchlist[:10]:
            f.write(f"### #{entry['rank']} {entry['ticker']} — {entry['name']}\n\n")
            f.write(f"- **M&A Score:** {entry['ma_score']:.1f}/100\n")
            f.write(f"- **Market Cap:** ${entry['market_cap_usd']/1e9:.1f}B\n")
            f.write(f"- **Cash:** ${entry['cash_position_usd']/1e6:.0f}M\n")
            if entry['runway_quarters']:
                f.write(f"- **Runway:** {entry['runway_quarters']:.1f} quarters\n")
            f.write(f"- **Lead Asset:** {entry['lead_asset']} ({entry['lead_phase']}) — {entry['lead_indication']}\n")
            f.write(f"- **Therapeutic Areas:** {', '.join(entry['therapeutic_areas'])}\n")
            f.write(f"- **Score Breakdown:** Pipeline {entry['scores']['pipeline']:.0f}, Financial {entry['scores']['financial']:.0f}, Strategic {entry['scores']['strategic_fit']:.0f}, Regulatory {entry['scores']['regulatory']:.0f}\n")

            if entry["likely_acquirers"]:
                f.write(f"- **Likely Acquirers:**\n")
                for acq in entry["likely_acquirers"]:
                    f.write(f"  - {acq['acquirer']} (fit: {acq['fit_score']:.0f}) — {acq['rationale']}\n")

            f.write("- **12-Month Deal Probability:** Unavailable; no validated probability model.\n")
            f.write(f"\n")

    logger.info(f"Report saved to {md_path}")


if __name__ == "__main__":
    asyncio.run(generate_watchlist())
