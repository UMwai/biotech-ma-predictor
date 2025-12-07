#!/usr/bin/env python3
"""
Demonstration script for Target Identification Engine

Generates a comprehensive watchlist of biotech M&A targets
with detailed scoring, ranking, and predictions.

Usage:
    python examples/generate_target_watchlist.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from targets.identifier import TargetIdentifier
from targets.screener import ScreeningCriteria, TherapeuticArea
from targets.ranker import RankingWeights


def main():
    """Generate and display acquisition target watchlist"""

    print("="*80)
    print("BIOTECH M&A TARGET IDENTIFICATION ENGINE")
    print("="*80)
    print()

    # Initialize identifier with default criteria
    print("Initializing Target Identification Engine...")
    identifier = TargetIdentifier()

    # Generate sample watchlist
    print("Screening and ranking potential acquisition targets...")
    print()

    watchlist = identifier.generate_sample_watchlist()

    # Display summary statistics
    stats = watchlist.get_statistics()

    print("="*80)
    print("WATCHLIST SUMMARY")
    print("="*80)
    print(f"Total Targets Identified: {stats['total_targets']}")
    print(f"Average M&A Score: {stats['avg_ma_score']:.1f}/100")
    print(f"Average Market Cap: ${stats['avg_market_cap']/1e9:.2f}B")
    print(f"Average Deal Probability (12mo): {stats['avg_deal_probability']*100:.1f}%")
    print(f"High Probability Targets (>40%): {stats['high_probability_targets']}")
    print(f"Total Estimated Deal Value: ${stats['total_estimated_value']/1e9:.1f}B")
    print()
    print(f"Therapeutic Areas: {', '.join(stats['therapeutic_areas'])}")
    print()

    # Display top 10 targets in detail
    print("="*80)
    print("TOP 10 ACQUISITION TARGETS")
    print("="*80)
    print()

    for target in watchlist.get_top_n(10):
        print(f"{'='*80}")
        print(f"RANK #{target.rank} - {target.ticker}: {target.name}")
        print(f"{'='*80}")
        print()

        # Basic info
        print(f"M&A SCORE: {target.ma_score:.1f}/100 (Top {target.percentile:.0f}%)")
        print(f"Therapeutic Area: {target.therapeutic_area.replace('_', ' ').title()}")
        print(f"Lead Asset: {target.lead_asset} ({target.development_stage})")
        print(f"Indication: {target.lead_asset_indication}")
        print()

        # Financial metrics
        print("FINANCIAL PROFILE:")
        print(f"  Market Cap: ${target.market_cap/1e9:.2f}B")
        print(f"  Cash Position: ${target.cash_position/1e6:.0f}M")
        print(f"  Cash Runway: {target.cash_runway_months:.0f} months")
        print(f"  Stock Performance (52w): {target.stock_return_52w:+.1f}%")
        print()

        # Deal predictions
        print("DEAL PREDICTIONS:")
        print(f"  12-Month Probability: {target.deal_probability_12mo*100:.0f}%")
        print(f"  24-Month Probability: {target.deal_probability_24mo*100:.0f}%")
        if target.estimated_deal_value:
            print(f"  Estimated Deal Value: {target.estimated_deal_value.format_range()}")
            print(f"  Implied Premium: {target.implied_premium:.0f}%")
        print()

        # Top acquirer
        if target.top_acquirer:
            print("MOST LIKELY ACQUIRER:")
            print(f"  {target.top_acquirer.name} ({target.top_acquirer.acquirer_type.value})")
            print(f"  Strategic Fit: {target.top_acquirer.strategic_fit_score:.0f}/100")
            print(f"  Acquisition Probability: {target.top_acquirer.probability*100:.0f}%")
            print(f"  Rationale: {target.top_acquirer.rationale}")
            print()

        # All likely acquirers
        if len(target.likely_acquirers) > 1:
            print("OTHER LIKELY ACQUIRERS:")
            for acquirer in target.likely_acquirers[1:4]:  # Top 3 others
                print(f"  - {acquirer.name} (Fit: {acquirer.strategic_fit_score:.0f}%, "
                      f"Prob: {acquirer.probability*100:.0f}%)")
            print()

        # Key strengths
        if target.key_strengths:
            print("KEY STRENGTHS:")
            for strength in target.key_strengths:
                print(f"  + {strength}")
            print()

        # Investment thesis
        if target.investment_thesis:
            print("INVESTMENT THESIS:")
            print(f"  {target.investment_thesis}")
            print()

        # Upcoming catalysts
        if target.upcoming_catalysts:
            print("UPCOMING CATALYSTS:")
            for catalyst in target.upcoming_catalysts:
                days = catalyst.days_until()
                days_str = f"({days} days)" if days else "(TBD)"
                print(f"  - {catalyst.event_type} {days_str} - {catalyst.importance} importance")
            print()

        print()

    # Display all targets in summary table
    print("="*80)
    print("COMPLETE WATCHLIST - ALL TARGETS")
    print("="*80)
    print()
    print(f"{'Rank':<6}{'Ticker':<8}{'Company':<30}{'Area':<20}{'MC($B)':<10}{'Score':<8}{'Prob%':<8}")
    print("-"*90)

    for target in watchlist.targets:
        area_short = target.therapeutic_area.replace('_', ' ')[:18]
        name_short = target.name[:28]
        print(f"{target.rank:<6}{target.ticker:<8}{name_short:<30}{area_short:<20}"
              f"{target.market_cap/1e9:<10.2f}{target.ma_score:<8.1f}"
              f"{target.deal_probability_12mo*100:<8.0f}")

    print()

    # Therapeutic area breakdown
    print("="*80)
    print("TARGETS BY THERAPEUTIC AREA")
    print("="*80)
    print()

    for area in [TherapeuticArea.OBESITY_GLP1, TherapeuticArea.ONCOLOGY_ADC,
                 TherapeuticArea.RADIOPHARMACEUTICALS, TherapeuticArea.AUTOIMMUNE,
                 TherapeuticArea.CNS_NEUROPSYCHIATRY, TherapeuticArea.RARE_DISEASE]:

        area_targets = watchlist.filter_by_area([area.value])
        if area_targets:
            print(f"\n{area.value.replace('_', ' ').upper()}:")
            print("-" * 60)
            for target in sorted(area_targets, key=lambda x: x.ma_score, reverse=True):
                print(f"  {target.ticker:6} - {target.name:35} "
                      f"(Score: {target.ma_score:.0f}, Prob: {target.deal_probability_12mo*100:.0f}%)")

    # Export watchlist
    print()
    print("="*80)
    print("EXPORTING WATCHLIST")
    print("="*80)

    output_dir = Path(__file__).parent.parent / 'output'
    output_dir.mkdir(exist_ok=True)

    json_path = output_dir / 'target_watchlist.json'
    csv_path = output_dir / 'target_watchlist.csv'

    identifier.watchlist_manager.watchlists['current'] = watchlist
    identifier.watchlist_manager.export_watchlist('current', str(json_path), format='json')
    identifier.watchlist_manager.export_watchlist('current', str(csv_path), format='csv')

    print(f"\nWatchlist exported to:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")

    # Generate full report
    report = identifier.watchlist_manager.generate_report('current')
    report_path = output_dir / 'target_watchlist_report.txt'

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"  Report: {report_path}")
    print()

    print("="*80)
    print("TARGET IDENTIFICATION COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
