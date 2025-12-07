#!/usr/bin/env python3
"""
Example: Find Obesity/GLP-1 Acquisition Targets

Demonstrates how to use the Target Identification Engine to find
targets in a specific therapeutic area with custom criteria.

This example focuses on obesity/GLP-1, the hottest biotech M&A
area in 2024-2025.

Usage:
    python examples/find_obesity_targets.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from targets.identifier import TargetIdentifier
from targets.screener import ScreeningCriteria, TherapeuticArea, DevelopmentPhase
from targets.ranker import RankingWeights


def main():
    """Find and rank obesity/GLP-1 acquisition targets"""

    print("="*80)
    print("OBESITY / GLP-1 M&A TARGET IDENTIFICATION")
    print("="*80)
    print()
    print("Market Context:")
    print("- Obesity market expected to reach $100B+ by 2030")
    print("- Novo Nordisk & Eli Lilly dominate with Wegovy & Zepbound")
    print("- Oral formulations and novel mechanisms highly valuable")
    print("- Recent activity: Novo considering acquisitions to expand pipeline")
    print()

    # Custom screening criteria for obesity targets
    print("Setting up custom screening criteria...")
    criteria = ScreeningCriteria(
        # Focus on smaller targets Big Pharma can acquire
        min_market_cap=300_000_000,  # $300M minimum
        max_market_cap=10_000_000_000,  # $10B maximum

        # Phase 2+ to reduce risk
        min_phase=DevelopmentPhase.PHASE_2,

        # Some financial pressure preferred (motivates deal)
        max_cash_runway_months=30,

        # Focus exclusively on obesity
        priority_areas=[TherapeuticArea.OBESITY_GLP1],

        # Looking for differentiated assets
        exclude_preclinical_only=True
    )

    # Custom ranking weights - emphasize scientific differentiation
    print("Setting up custom ranking weights...")
    weights = RankingWeights(
        # Emphasize science and innovation
        scientific_differentiation=0.16,
        pipeline_quality=0.12,
        therapeutic_area=0.10,

        # Strategic factors
        strategic_acquirer_fit=0.11,
        acquisition_tension=0.10,

        # Clinical and financial
        clinical_stage=0.10,
        cash_runway=0.08,
        data_catalyst_timing=0.08,

        # Other factors
        market_cap_fit=0.05,
        financial_distress=0.03,
        competitive_landscape=0.03,
        deal_structure_feasibility=0.03
    )

    # Initialize identifier with custom settings
    identifier = TargetIdentifier(
        screening_criteria=criteria,
        ranking_weights=weights
    )

    # Generate sample watchlist (in production, use real data)
    print("Screening and ranking obesity targets...")
    print()

    watchlist = identifier.generate_sample_watchlist()

    # Filter for obesity targets
    obesity_targets = watchlist.filter_by_area(['obesity_glp1'])

    print("="*80)
    print(f"OBESITY/GLP-1 TARGETS IDENTIFIED: {len(obesity_targets)}")
    print("="*80)
    print()

    # Display each target
    for i, target in enumerate(obesity_targets, 1):
        print(f"{'='*80}")
        print(f"TARGET #{i} - {target.ticker}: {target.name}")
        print(f"{'='*80}")
        print()

        print(f"M&A SCORE: {target.ma_score:.1f}/100")
        print(f"Overall Rank: #{target.rank} (Top {target.percentile:.0f}%)")
        print()

        print("ASSET PROFILE:")
        print(f"  Lead Asset: {target.lead_asset}")
        print(f"  Development Stage: {target.development_stage}")
        print(f"  Indication: {target.lead_asset_indication}")
        print()

        print("FINANCIAL METRICS:")
        print(f"  Market Cap: ${target.market_cap/1e9:.2f}B")
        print(f"  Cash Position: ${target.cash_position/1e6:.0f}M")
        print(f"  Cash Runway: {target.cash_runway_months:.0f} months")
        print(f"  Quarterly Burn: ${target.quarterly_burn_rate/1e6:.0f}M")
        print()

        print("STOCK PERFORMANCE:")
        print(f"  52-Week Return: {target.stock_return_52w:+.1f}%")
        print(f"  YTD Return: {target.stock_return_ytd:+.1f}%")
        print()

        print("DEAL ANALYSIS:")
        print(f"  12-Month Probability: {target.deal_probability_12mo*100:.0f}%")
        print(f"  24-Month Probability: {target.deal_probability_24mo*100:.0f}%")
        if target.estimated_deal_value:
            print(f"  Deal Value Range: {target.estimated_deal_value.format_range()}")
        print()

        print("TOP 3 LIKELY ACQUIRERS:")
        for acquirer in target.likely_acquirers[:3]:
            print(f"  {acquirer.rank if hasattr(acquirer, 'rank') else ''}"
                  f"  {acquirer.name} ({acquirer.acquirer_type.value})")
            print(f"     Strategic Fit: {acquirer.strategic_fit_score:.0f}/100")
            print(f"     Probability: {acquirer.probability*100:.0f}%")
            print(f"     Rationale: {acquirer.rationale}")
            print()

        print("KEY DIFFERENTIATORS:")
        for strength in target.key_strengths:
            print(f"  + {strength}")
        print()

        print("INVESTMENT THESIS:")
        print(f"  {target.investment_thesis}")
        print()

        if target.upcoming_catalysts:
            print("UPCOMING CATALYSTS:")
            for catalyst in target.upcoming_catalysts:
                print(f"  - {catalyst.event_type}")
                print(f"    Timing: {catalyst.expected_date}")
                print(f"    Importance: {catalyst.importance}")
            print()

        print()

    # Comparative analysis
    print("="*80)
    print("COMPARATIVE ANALYSIS")
    print("="*80)
    print()

    print(f"{'Rank':<6}{'Ticker':<8}{'Company':<30}{'Stage':<12}{'MC($B)':<10}{'Score':<10}{'12mo%':<8}")
    print("-"*90)
    for target in obesity_targets:
        print(f"{target.rank:<6}{target.ticker:<8}{target.name[:28]:<30}"
              f"{target.development_stage:<12}{target.market_cap/1e9:<10.2f}"
              f"{target.ma_score:<10.1f}{target.deal_probability_12mo*100:<8.0f}")

    print()

    # Key insights
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()

    # Find highest probability target
    highest_prob = max(obesity_targets, key=lambda t: t.deal_probability_12mo)
    print(f"HIGHEST PROBABILITY TARGET:")
    print(f"  {highest_prob.ticker}: {highest_prob.name}")
    print(f"  12-Month Probability: {highest_prob.deal_probability_12mo*100:.0f}%")
    print(f"  Primary Driver: {highest_prob.cash_runway_months:.0f} month cash runway")
    print()

    # Find best value
    best_value = min(obesity_targets, key=lambda t: t.market_cap)
    print(f"SMALLEST / BEST VALUE:")
    print(f"  {best_value.ticker}: {best_value.name}")
    print(f"  Market Cap: ${best_value.market_cap/1e9:.2f}B")
    print(f"  M&A Score: {best_value.ma_score:.1f}/100")
    print()

    # Most advanced
    phase_rank = {'Phase 3': 3, 'Phase 2': 2, 'Phase 1': 1, 'Approved': 4}
    most_advanced = max(obesity_targets,
                       key=lambda t: phase_rank.get(t.development_stage, 0))
    print(f"MOST CLINICALLY ADVANCED:")
    print(f"  {most_advanced.ticker}: {most_advanced.name}")
    print(f"  Stage: {most_advanced.development_stage}")
    print(f"  Asset: {most_advanced.lead_asset}")
    print()

    # Acquirer interest analysis
    print("="*80)
    print("ACQUIRER INTEREST ANALYSIS")
    print("="*80)
    print()

    # Count targets by top acquirer
    from collections import Counter
    acquirer_counts = Counter(
        t.top_acquirer.name for t in obesity_targets if t.top_acquirer
    )

    print("Most likely acquirers across obesity targets:")
    for acquirer, count in acquirer_counts.most_common():
        print(f"  {acquirer}: {count} target(s)")
    print()

    # Strategic recommendations
    print("="*80)
    print("STRATEGIC RECOMMENDATIONS")
    print("="*80)
    print()

    print("FOR BIG PHARMA ACQUIRERS:")
    print()
    print("1. NOVO NORDISK - Should acquire:")
    novo_targets = [t for t in obesity_targets
                   if any(a.name == 'Novo Nordisk' for a in t.likely_acquirers)]
    if novo_targets:
        best_novo = max(novo_targets, key=lambda t: t.ma_score)
        print(f"   Top Pick: {best_novo.ticker} ({best_novo.name})")
        print(f"   Rationale: {best_novo.investment_thesis}")
    print()

    print("2. ELI LILLY - Should acquire:")
    lilly_targets = [t for t in obesity_targets
                    if any(a.name == 'Eli Lilly' for a in t.likely_acquirers)]
    if lilly_targets:
        best_lilly = max(lilly_targets, key=lambda t: t.ma_score)
        print(f"   Top Pick: {best_lilly.ticker} ({best_lilly.name})")
        print(f"   Rationale: Diversify beyond tirzepatide")
    print()

    print("3. ROCHE/ASTRAZENECA - Should acquire:")
    print("   Any target with novel oral formulation")
    print("   Rationale: Fast-follower strategy in obesity market")
    print()

    print("="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
