"""
Watchlist Management - Track and manage acquisition target watchlists

Provides data structures and management for maintaining ranked watchlists
of acquisition targets with detailed predictions and valuations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, date
from enum import Enum
import json


class AcquirerType(Enum):
    """Types of potential acquirers"""
    BIG_PHARMA = "Big Pharma"
    LARGE_BIOTECH = "Large Biotech"
    MID_CAP_BIOTECH = "Mid-cap Biotech"
    SPECIALTY_PHARMA = "Specialty Pharma"
    PRIVATE_EQUITY = "Private Equity"


@dataclass
class ValuationRange:
    """Deal valuation range estimates"""
    low: float  # Minimum likely valuation
    base: float  # Base case valuation
    high: float  # Maximum likely valuation
    currency: str = "USD"

    @property
    def midpoint(self) -> float:
        """Calculate midpoint of range"""
        return (self.low + self.high) / 2

    @property
    def range_width(self) -> float:
        """Calculate width of valuation range"""
        return self.high - self.low

    def format_range(self) -> str:
        """Format as human-readable string"""
        return f"${self.low/1e9:.2f}B - ${self.high/1e9:.2f}B (base: ${self.base/1e9:.2f}B)"


@dataclass
class AcquirerMatch:
    """Potential acquirer with strategic fit score"""
    name: str
    acquirer_type: AcquirerType
    strategic_fit_score: float  # 0-100
    rationale: str

    # Strategic factors
    fills_portfolio_gap: bool = False
    therapeutic_area_overlap: bool = False
    geographic_synergies: bool = False
    commercial_synergies: bool = False

    # Deal likelihood
    probability: float = 0.0  # 0-1
    estimated_premium: float = 0.0  # % premium to current market cap

    def __str__(self) -> str:
        return f"{self.name} ({self.strategic_fit_score:.0f}% fit, {self.probability*100:.0f}% probability)"


@dataclass
class DataCatalyst:
    """Upcoming data catalyst"""
    event_type: str  # "Phase 2 data", "Phase 3 topline", etc.
    expected_date: Optional[date]
    asset_name: str
    importance: str  # "Low", "Medium", "High", "Critical"

    def days_until(self) -> Optional[int]:
        """Calculate days until catalyst"""
        if self.expected_date:
            return (self.expected_date - date.today()).days
        return None


@dataclass
class AcquisitionTarget:
    """
    Complete acquisition target profile with predictions

    Represents a single biotech company as an M&A target with
    all relevant metrics, scores, and predictions.
    """
    # Basic info
    ticker: str
    name: str
    therapeutic_area: str
    description: str = ""

    # Therapeutic focus
    therapeutic_areas_list: List[str] = field(default_factory=list)
    lead_asset: str = ""
    lead_asset_indication: str = ""
    development_stage: str = ""

    # Financial metrics
    market_cap: float = 0.0
    enterprise_value: float = 0.0
    cash_position: float = 0.0
    cash_runway_months: float = 0.0
    quarterly_burn_rate: float = 0.0

    # Stock metrics
    stock_price: float = 0.0
    stock_return_52w: float = 0.0
    stock_return_ytd: float = 0.0
    institutional_ownership: float = 0.0

    # M&A Scores
    ma_score: float = 0.0  # 0-100 composite score
    rank: int = 0
    percentile: float = 0.0

    # Factor breakdown
    factor_scores: Dict[str, float] = field(default_factory=dict)
    key_strengths: List[str] = field(default_factory=list)
    key_weaknesses: List[str] = field(default_factory=list)

    # Valuations
    dcf_valuation: float = 0.0
    comparable_valuation: float = 0.0
    analyst_price_target_avg: float = 0.0

    # Deal predictions
    deal_probability_12mo: float = 0.0  # 0-1
    deal_probability_24mo: float = 0.0  # 0-1
    estimated_deal_value: Optional[ValuationRange] = None
    implied_premium: float = 0.0  # % premium to current price

    # Acquirer analysis
    likely_acquirers: List[AcquirerMatch] = field(default_factory=list)
    top_acquirer: Optional[AcquirerMatch] = None

    # Catalysts and timing
    upcoming_catalysts: List[DataCatalyst] = field(default_factory=list)
    next_major_catalyst: Optional[DataCatalyst] = None

    # Additional context
    recent_developments: List[str] = field(default_factory=list)
    investment_thesis: str = ""
    risk_factors: List[str] = field(default_factory=list)

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    data_sources: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Post-initialization processing"""
        # Set top acquirer if not set
        if not self.top_acquirer and self.likely_acquirers:
            self.top_acquirer = max(
                self.likely_acquirers,
                key=lambda x: x.probability
            )

        # Set next major catalyst
        if not self.next_major_catalyst and self.upcoming_catalysts:
            high_importance = [
                c for c in self.upcoming_catalysts
                if c.importance in ["High", "Critical"]
            ]
            if high_importance:
                self.next_major_catalyst = min(
                    high_importance,
                    key=lambda c: c.expected_date or date.max
                )

    def get_summary(self) -> str:
        """Generate one-line summary"""
        return (
            f"{self.ticker}: {self.name} - {self.therapeutic_area} "
            f"(${self.market_cap/1e9:.2f}B, MA Score: {self.ma_score:.0f}, "
            f"Rank: #{self.rank})"
        )

    def get_valuation_summary(self) -> str:
        """Generate valuation summary"""
        if self.estimated_deal_value:
            return (
                f"Deal Value: {self.estimated_deal_value.format_range()} "
                f"({self.implied_premium:.0f}% premium)"
            )
        return "Valuation: Not estimated"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'ticker': self.ticker,
            'name': self.name,
            'therapeutic_area': self.therapeutic_area,
            'lead_asset': self.lead_asset,
            'development_stage': self.development_stage,
            'market_cap': self.market_cap,
            'ma_score': self.ma_score,
            'rank': self.rank,
            'deal_probability_12mo': self.deal_probability_12mo,
            'top_acquirer': str(self.top_acquirer) if self.top_acquirer else None,
            'estimated_deal_value': (
                self.estimated_deal_value.format_range()
                if self.estimated_deal_value else None
            )
        }


@dataclass
class RankedWatchlist:
    """Ranked watchlist of acquisition targets"""
    name: str
    description: str
    targets: List[AcquisitionTarget] = field(default_factory=list)
    created_date: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    # Filters applied
    therapeutic_areas: List[str] = field(default_factory=list)
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    min_ma_score: Optional[float] = None

    def __len__(self) -> int:
        return len(self.targets)

    def get_top_n(self, n: int) -> List[AcquisitionTarget]:
        """Get top N targets by rank"""
        return sorted(self.targets, key=lambda x: x.rank)[:n]

    def filter_by_area(self, areas: List[str]) -> List[AcquisitionTarget]:
        """Filter targets by therapeutic area"""
        return [
            t for t in self.targets
            if t.therapeutic_area in areas or
            any(area in t.therapeutic_areas_list for area in areas)
        ]

    def filter_by_acquirer(self, acquirer_name: str) -> List[AcquisitionTarget]:
        """Filter targets likely to be acquired by specific company"""
        return [
            t for t in self.targets
            if any(a.name == acquirer_name for a in t.likely_acquirers)
        ]

    def get_statistics(self) -> Dict:
        """Get watchlist statistics"""
        if not self.targets:
            return {}

        return {
            'total_targets': len(self.targets),
            'avg_ma_score': sum(t.ma_score for t in self.targets) / len(self.targets),
            'avg_market_cap': sum(t.market_cap for t in self.targets) / len(self.targets),
            'avg_deal_probability': sum(t.deal_probability_12mo for t in self.targets) / len(self.targets),
            'total_estimated_value': sum(
                t.estimated_deal_value.base for t in self.targets
                if t.estimated_deal_value
            ),
            'therapeutic_areas': list(set(t.therapeutic_area for t in self.targets)),
            'high_probability_targets': len([
                t for t in self.targets if t.deal_probability_12mo >= 0.4
            ])
        }


class WatchlistManager:
    """
    Manage multiple watchlists and perform analysis

    Provides functionality to create, update, and analyze
    watchlists of acquisition targets.
    """

    def __init__(self):
        """Initialize watchlist manager"""
        self.watchlists: Dict[str, RankedWatchlist] = {}
        self.active_watchlist: Optional[str] = None

    def create_watchlist(
        self,
        name: str,
        description: str,
        targets: Optional[List[AcquisitionTarget]] = None
    ) -> RankedWatchlist:
        """
        Create a new watchlist

        Args:
            name: Watchlist name
            description: Watchlist description
            targets: Initial targets

        Returns:
            Created RankedWatchlist
        """
        watchlist = RankedWatchlist(
            name=name,
            description=description,
            targets=targets or []
        )

        self.watchlists[name] = watchlist
        if not self.active_watchlist:
            self.active_watchlist = name

        return watchlist

    def add_target(
        self,
        watchlist_name: str,
        target: AcquisitionTarget
    ) -> None:
        """Add target to watchlist"""
        if watchlist_name not in self.watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        self.watchlists[watchlist_name].targets.append(target)
        self.watchlists[watchlist_name].last_updated = datetime.now()

        # Re-rank targets
        self._rerank_watchlist(watchlist_name)

    def remove_target(
        self,
        watchlist_name: str,
        ticker: str
    ) -> None:
        """Remove target from watchlist by ticker"""
        if watchlist_name not in self.watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        watchlist = self.watchlists[watchlist_name]
        watchlist.targets = [t for t in watchlist.targets if t.ticker != ticker]
        watchlist.last_updated = datetime.now()

        self._rerank_watchlist(watchlist_name)

    def update_target(
        self,
        watchlist_name: str,
        ticker: str,
        updates: Dict
    ) -> None:
        """Update target information"""
        if watchlist_name not in self.watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        watchlist = self.watchlists[watchlist_name]
        for target in watchlist.targets:
            if target.ticker == ticker:
                for key, value in updates.items():
                    if hasattr(target, key):
                        setattr(target, key, value)
                target.last_updated = datetime.now()
                break

        watchlist.last_updated = datetime.now()
        self._rerank_watchlist(watchlist_name)

    def _rerank_watchlist(self, watchlist_name: str) -> None:
        """Re-rank targets in watchlist"""
        watchlist = self.watchlists[watchlist_name]

        # Sort by MA score
        sorted_targets = sorted(
            watchlist.targets,
            key=lambda x: x.ma_score,
            reverse=True
        )

        # Update ranks and percentiles
        total = len(sorted_targets)
        for i, target in enumerate(sorted_targets):
            target.rank = i + 1
            target.percentile = ((total - i) / total) * 100 if total > 0 else 0

        watchlist.targets = sorted_targets

    def get_watchlist(self, name: str) -> Optional[RankedWatchlist]:
        """Get watchlist by name"""
        return self.watchlists.get(name)

    def list_watchlists(self) -> List[str]:
        """List all watchlist names"""
        return list(self.watchlists.keys())

    def export_watchlist(
        self,
        watchlist_name: str,
        filepath: str,
        format: str = 'json'
    ) -> None:
        """
        Export watchlist to file

        Args:
            watchlist_name: Name of watchlist to export
            filepath: Output file path
            format: Export format ('json' or 'csv')
        """
        if watchlist_name not in self.watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        watchlist = self.watchlists[watchlist_name]

        if format == 'json':
            data = {
                'name': watchlist.name,
                'description': watchlist.description,
                'created_date': watchlist.created_date.isoformat(),
                'last_updated': watchlist.last_updated.isoformat(),
                'targets': [t.to_dict() for t in watchlist.targets],
                'statistics': watchlist.get_statistics()
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

        elif format == 'csv':
            import csv

            with open(filepath, 'w', newline='') as f:
                if not watchlist.targets:
                    return

                # Get all possible fields from first target
                fieldnames = list(watchlist.targets[0].to_dict().keys())

                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for target in watchlist.targets:
                    writer.writerow(target.to_dict())

        else:
            raise ValueError(f"Unsupported format: {format}")

    def generate_report(self, watchlist_name: str) -> str:
        """Generate text report for watchlist"""
        if watchlist_name not in self.watchlists:
            raise ValueError(f"Watchlist '{watchlist_name}' not found")

        watchlist = self.watchlists[watchlist_name]
        stats = watchlist.get_statistics()

        report = f"""
{'='*80}
ACQUISITION TARGET WATCHLIST REPORT
{'='*80}

Watchlist: {watchlist.name}
Description: {watchlist.description}
Last Updated: {watchlist.last_updated.strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY STATISTICS
{'-'*80}
Total Targets: {stats.get('total_targets', 0)}
Average M&A Score: {stats.get('avg_ma_score', 0):.1f}/100
Average Market Cap: ${stats.get('avg_market_cap', 0)/1e9:.2f}B
Average Deal Probability (12mo): {stats.get('avg_deal_probability', 0)*100:.1f}%
High Probability Targets: {stats.get('high_probability_targets', 0)}
Total Estimated Deal Value: ${stats.get('total_estimated_value', 0)/1e9:.2f}B

TOP 10 TARGETS
{'-'*80}
"""

        for target in watchlist.get_top_n(10):
            report += f"""
#{target.rank} - {target.ticker}: {target.name}
    M&A Score: {target.ma_score:.1f}/100 (Top {target.percentile:.0f}%)
    Therapeutic Area: {target.therapeutic_area}
    Market Cap: ${target.market_cap/1e9:.2f}B
    Deal Probability (12mo): {target.deal_probability_12mo*100:.0f}%
    Top Acquirer: {target.top_acquirer.name if target.top_acquirer else 'N/A'}
    {target.get_valuation_summary()}
"""

        report += f"\n{'='*80}\n"

        return report
