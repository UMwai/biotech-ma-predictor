#!/usr/bin/env python3
"""
Legacy heuristic scoring helpers and optional SQLite scoring command.

Implements 6 scoring components adapted from src/scoring/components.py,
reading an existing SQLite database when invoked directly. Hand-set scores do
not establish acquisition probabilities or predictive performance. The supported
local research desk does not use this database command.

Usage:
    python3 scripts/score_companies.py
"""

import asyncio
import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "biotech_ma.db"

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "pipeline": 0.30,
    "financial": 0.20,
    "strategic_fit": 0.20,
    "regulatory": 0.15,
    "patent": 0.10,
    "insider": 0.05,
}

# --- Component Scorers ---

# Phase multipliers (from components.py)
PHASE_MULTIPLIER = {
    "PRECLINICAL": 0.3,
    "PHASE_1": 0.5,
    "PHASE_2": 0.8,
    "PHASE_3": 1.0,
    "NDA_BLA": 0.9,
    "APPROVED": 0.7,
}

# Therapeutic area multipliers
TA_MULTIPLIER = {
    "oncology": 1.0,
    "immunology": 0.9,
    "neurology": 0.85,
    "rare_disease": 0.95,
    "cardiovascular": 0.8,
    "metabolic": 0.95,  # Hot area (obesity)
    "infectious_disease": 0.7,
    "other": 0.5,
}

# Therapeutic area "hotness" for strategic fit
TA_HOTNESS = {
    "metabolic": 100,   # Obesity/GLP-1 is the hottest area
    "oncology": 90,
    "rare_disease": 85,
    "immunology": 80,
    "neurology": 75,
    "cardiovascular": 70,
    "infectious_disease": 60,
    "other": 40,
}


def score_pipeline(drugs: list[dict]) -> tuple[float, list[str]]:
    """
    Score pipeline based on drug candidates.

    Returns (score 0-100, list of key drivers).
    """
    if not drugs:
        return 0.0, ["No pipeline data"]

    drivers = []
    drug_scores = []

    for drug in drugs:
        phase = drug.get("phase", "PRECLINICAL")
        ta = drug.get("therapeutic_area", "other")
        phase_mult = PHASE_MULTIPLIER.get(phase, 0.3)
        ta_mult = TA_MULTIPLIER.get(ta, 0.5)

        # Base score from phase
        base = phase_mult * 60  # Max 60 from phase alone

        # Therapeutic area adjustment
        base *= ta_mult

        # Designation bonuses
        if drug.get("orphan_designation"):
            base += 10
        if drug.get("breakthrough_therapy"):
            base += 15
        if drug.get("fast_track"):
            base += 8
        if drug.get("priority_review"):
            base += 5

        drug_scores.append((drug.get("name", "Unknown"), base, phase))

    # Sort by score descending
    drug_scores.sort(key=lambda x: x[1], reverse=True)

    # Weighted average of top 3 assets
    weights = [0.50, 0.30, 0.20]
    total = 0
    for i, (name, score, phase) in enumerate(drug_scores[:3]):
        w = weights[i] if i < len(weights) else 0
        total += score * w
        if i == 0:
            drivers.append(f"Lead asset: {name} ({phase})")

    # Portfolio diversity bonus
    diversity_bonus = min(len(drug_scores) * 2, 15)
    total += diversity_bonus

    # Cap at 100
    final = min(total, 100)

    if len(drug_scores) > 1:
        drivers.append(f"{len(drug_scores)} pipeline assets (+{diversity_bonus} diversity)")

    return round(final, 2), drivers


def score_financial(company: dict) -> tuple[float, list[str]]:
    """
    Score financial attractiveness for acquisition.

    Small/mid-cap, cash-constrained companies are more acquirable.
    """
    drivers = []
    market_cap = company.get("market_cap_usd", 0)
    cash = company.get("cash_position_usd", 0)
    burn = company.get("quarterly_burn_rate_usd", 0)
    runway = company.get("runway_quarters")

    # Runway score (cash constrained = more likely target)
    if runway is not None and runway > 0:
        if runway < 3:
            runway_score = 100
            drivers.append(f"Critical: {runway:.1f}Q runway")
        elif runway < 6:
            runway_score = 85
            drivers.append(f"Low runway: {runway:.1f}Q")
        elif runway < 8:
            runway_score = 65
        elif runway < 12:
            runway_score = 45
        else:
            runway_score = 20
    else:
        runway_score = 30  # Unknown runway

    # Valuation score - acquirability across market cap spectrum
    # Key insight from backtest: large biotechs DO get acquired ($28B Seagen, $17B Horizon)
    if market_cap < 200_000_000:
        val_score = 40  # Too small, might not be real target
    elif market_cap < 500_000_000:
        val_score = 80
        drivers.append(f"Small cap (${market_cap/1e9:.1f}B) - easy acquisition")
    elif market_cap < 2_000_000_000:
        val_score = 100  # Sweet spot
        drivers.append(f"Sweet spot valuation (${market_cap/1e9:.1f}B)")
    elif market_cap < 5_000_000_000:
        val_score = 90
        drivers.append(f"Mid cap (${market_cap/1e9:.1f}B) - attractive range")
    elif market_cap < 10_000_000_000:
        val_score = 70
    elif market_cap < 20_000_000_000:
        val_score = 55  # Still acquired (Horizon $17B, Karuna $7.5B pre-deal)
    elif market_cap < 40_000_000_000:
        val_score = 40  # Mega deals happen (Seagen $28B)
    else:
        val_score = 20  # Very expensive
        drivers.append(f"Large cap (${market_cap/1e9:.1f}B) - mega-deal only")

    # Final: 45% runway + 55% valuation
    final = 0.45 * runway_score + 0.55 * val_score

    return round(final, 2), drivers


def score_strategic_fit(company: dict, drugs: list[dict]) -> tuple[float, list[str]]:
    """
    Score strategic fit based on therapeutic area hotness and pipeline stage.

    Hot areas (obesity, ADC, radiopharm) score higher.
    Phase 2/3 is the sweet spot (de-risked but not priced in).
    """
    drivers = []
    ta_list = json.loads(company.get("therapeutic_areas", "[]")) if isinstance(company.get("therapeutic_areas"), str) else company.get("therapeutic_areas", [])

    # Therapeutic area hotness (best area wins)
    if ta_list:
        best_ta_score = max(TA_HOTNESS.get(ta, 40) for ta in ta_list)
        best_ta = max(ta_list, key=lambda ta: TA_HOTNESS.get(ta, 40))
        drivers.append(f"Hot area: {best_ta} ({best_ta_score})")
    else:
        best_ta_score = 40

    # Pipeline stage value for M&A
    stage_scores = {
        "PHASE_3": 100,  # Most valuable - de-risked
        "PHASE_2": 85,   # Strong value
        "NDA_BLA": 90,
        "APPROVED": 65,  # Already priced in
        "PHASE_1": 50,
        "PRECLINICAL": 25,
    }

    best_stage_score = 40
    if drugs:
        for drug in drugs:
            phase = drug.get("phase", "PRECLINICAL")
            s = stage_scores.get(phase, 25)
            if s > best_stage_score:
                best_stage_score = s
                if s >= 85:
                    drivers.append(f"De-risked asset ({phase})")

    # Market cap sweetspot for acquirability
    market_cap = company.get("market_cap_usd", 0)
    if 500_000_000 < market_cap < 5_000_000_000:
        sweetspot_bonus = 15
        drivers.append("Acquirable market cap range")
    elif 200_000_000 < market_cap < 10_000_000_000:
        sweetspot_bonus = 5
    else:
        sweetspot_bonus = 0

    # Final: 40% TA hotness + 40% stage + 20% sweetspot
    final = 0.40 * best_ta_score + 0.40 * best_stage_score + sweetspot_bonus

    return round(min(final, 100), 2), drivers


def score_regulatory(drugs: list[dict]) -> tuple[float, list[str]]:
    """
    Score regulatory advantage based on designations.

    Breakthrough, orphan, fast track = faster approval = more attractive.
    """
    drivers = []

    if not drugs:
        return 30.0, ["No regulatory data"]

    # Count designations across pipeline
    total_orphan = sum(1 for d in drugs if d.get("orphan_designation"))
    total_breakthrough = sum(1 for d in drugs if d.get("breakthrough_therapy"))
    total_fast_track = sum(1 for d in drugs if d.get("fast_track"))
    total_priority = sum(1 for d in drugs if d.get("priority_review"))

    # Best designation score
    base = 40  # Default

    if total_breakthrough > 0:
        base = max(base, 90)
        drivers.append(f"Breakthrough therapy ({total_breakthrough})")
    if total_orphan > 0:
        base = max(base, 80)
        drivers.append(f"Orphan designation ({total_orphan})")
    if total_fast_track > 0:
        base = max(base, 70)
        if not total_breakthrough:
            drivers.append(f"Fast track ({total_fast_track})")
    if total_priority > 0:
        base = max(base, 85)

    # Bonus for multiple designations
    total_designations = total_orphan + total_breakthrough + total_fast_track + total_priority
    if total_designations >= 3:
        base = min(base + 10, 100)
        drivers.append(f"Strong regulatory profile ({total_designations} designations)")

    return round(base, 2), drivers


def score_patent(drugs: list[dict]) -> tuple[float, list[str]]:
    """
    Simplified patent score based on pipeline stage and therapeutic area.

    Phase 3 with composition of matter patents = highest value.
    Placeholder until real patent data is available.
    """
    if not drugs:
        return 40.0, ["No patent data (placeholder)"]

    # Heuristic: later stage drugs typically have stronger patent positions
    best_phase = "PRECLINICAL"
    phase_order = ["PRECLINICAL", "PHASE_1", "PHASE_2", "PHASE_3", "NDA_BLA", "APPROVED"]

    for drug in drugs:
        phase = drug.get("phase", "PRECLINICAL")
        if phase_order.index(phase) > phase_order.index(best_phase):
            best_phase = phase

    phase_patent_score = {
        "PRECLINICAL": 30,
        "PHASE_1": 45,
        "PHASE_2": 65,
        "PHASE_3": 80,
        "NDA_BLA": 85,
        "APPROVED": 70,  # May be closer to expiry
    }

    score = phase_patent_score.get(best_phase, 40)
    return score, [f"Patent estimate based on {best_phase} stage"]


def score_insider() -> tuple[float, list[str]]:
    """
    Placeholder insider score.

    Returns baseline 50 until SEC Form 4 data is ingested.
    """
    return 50.0, ["Insider score: baseline (no Form 4 data yet)"]


async def score_all_companies():
    """Score all companies in the database."""
    import aiosqlite

    logger.info("=== M&A Scoring Engine ===")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Get all companies
        cursor = await db.execute("SELECT * FROM companies ORDER BY ticker")
        companies = await cursor.fetchall()
        logger.info(f"Scoring {len(companies)} companies...")

        scores = []

        for company in companies:
            company_dict = dict(company)
            company_id = company_dict["id"]
            ticker = company_dict["ticker"]

            # Get drug candidates
            cursor = await db.execute(
                "SELECT * FROM drug_candidates WHERE company_id = ? AND deleted_at IS NULL",
                (company_id,),
            )
            drugs = [dict(d) for d in await cursor.fetchall()]

            # Calculate all 6 component scores
            pipeline, pipeline_drivers = score_pipeline(drugs)
            financial, financial_drivers = score_financial(company_dict)
            strategic, strategic_drivers = score_strategic_fit(company_dict, drugs)
            regulatory, regulatory_drivers = score_regulatory(drugs)
            patent, patent_drivers = score_patent(drugs)
            insider, insider_drivers = score_insider()

            # Weighted composite score
            total = (
                WEIGHTS["pipeline"] * pipeline +
                WEIGHTS["financial"] * financial +
                WEIGHTS["strategic_fit"] * strategic +
                WEIGHTS["regulatory"] * regulatory +
                WEIGHTS["patent"] * patent +
                WEIGHTS["insider"] * insider
            )
            total = round(total, 2)

            # Collect all drivers
            all_drivers = pipeline_drivers + financial_drivers + strategic_drivers + regulatory_drivers

            # Store score
            score_id = str(uuid4())
            await db.execute(
                """INSERT INTO ma_scores (id, company_id, score_date, total_score,
                   pipeline_score, patent_score, financial_score, insider_score,
                   strategic_fit_score, regulatory_score, key_drivers, extra_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (score_id, company_id, datetime.utcnow().isoformat(), total,
                 pipeline, patent, financial, insider, strategic, regulatory,
                 json.dumps(all_drivers), json.dumps({"score_version": "1.0"})),
            )

            scores.append({
                "ticker": ticker,
                "name": company_dict["name"],
                "total": total,
                "pipeline": pipeline,
                "financial": financial,
                "strategic": strategic,
                "regulatory": regulatory,
                "patent": patent,
                "insider": insider,
                "market_cap": company_dict["market_cap_usd"],
                "drivers": all_drivers,
            })

        await db.commit()

        # Sort by total score
        scores.sort(key=lambda x: x["total"], reverse=True)

        # Display results
        logger.info(f"\n{'='*90}")
        logger.info(f"{'Rank':>4} {'Ticker':>6} {'Name':<35} {'Score':>6} {'Pipe':>5} {'Fin':>5} {'Strat':>5} {'Reg':>5} {'MktCap':>8}")
        logger.info(f"{'='*90}")

        for i, s in enumerate(scores[:30], 1):
            mcap_str = f"${s['market_cap']/1e9:.1f}B"
            logger.info(
                f"{i:4d} {s['ticker']:>6} {s['name']:<35} {s['total']:6.1f} "
                f"{s['pipeline']:5.1f} {s['financial']:5.1f} {s['strategic']:5.1f} "
                f"{s['regulatory']:5.1f} {mcap_str:>8}"
            )

        logger.info(f"\n{'='*90}")
        logger.info(f"Scored {len(scores)} companies. Top 5 key drivers:")
        for s in scores[:5]:
            logger.info(f"\n  {s['ticker']} ({s['total']:.1f}):")
            for d in s['drivers'][:4]:
                logger.info(f"    - {d}")

        # Save to JSON
        output_path = Path(__file__).parent.parent / "output" / "ma_scores.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({
                "generated_at": datetime.utcnow().isoformat(),
                "total_companies": len(scores),
                "scores": scores,
            }, f, indent=2)
        logger.info(f"\nScores saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(score_all_companies())
