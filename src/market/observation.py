"""
Market signal observation and tracking for biotech M&A prediction.

This module monitors real-time market signals that may indicate
potential M&A activity.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import random


class SignalStrength(Enum):
    """Signal strength classifications."""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class OptionsActivity(Enum):
    """Types of unusual options activity."""
    HEAVY_CALL_BUYING = "heavy_call_buying"
    CALL_SPREAD = "call_spread"
    PROTECTIVE_PUTS = "protective_puts"
    NORMAL = "normal"
    UNUSUAL_ACTIVITY = "unusual_activity"


@dataclass
class MarketSignals:
    """
    Real-time market signals for M&A prediction.

    These signals can indicate potential M&A activity or market interest
    in a particular biotech company.
    """
    ticker: str
    timestamp: datetime

    # Volume and trading signals
    trading_volume_anomaly: float  # vs 30-day average (e.g., 2.5 = 250% of average)
    relative_volume: float  # Current vs average

    # Short interest signals
    short_interest_change: float  # Percentage change in short interest
    short_interest_ratio: float  # Days to cover

    # Options activity
    options_activity: OptionsActivity
    call_put_ratio: float  # Higher ratio = more bullish sentiment
    unusual_options_volume: float  # vs 30-day average

    # Analyst activity
    analyst_upgrades: int  # Number of upgrades in last 30 days
    analyst_downgrades: int  # Number of downgrades in last 30 days
    price_target_change: float  # Percentage change in consensus target

    # Institutional activity
    institutional_accumulation: float  # Net change in institutional ownership
    insider_buying_intensity: float  # Score 0-10 based on insider purchases
    institutional_ownership_pct: float  # Percentage owned by institutions

    # Price action
    price_momentum_20d: float  # 20-day price change percentage
    price_momentum_60d: float  # 60-day price change percentage
    distance_from_52w_high: float  # Percentage from 52-week high
    distance_from_52w_low: float  # Percentage from 52-week low

    def __post_init__(self):
        """Validate signal values."""
        if self.call_put_ratio < 0:
            raise ValueError("Call/put ratio must be positive")
        if not 0 <= self.institutional_ownership_pct <= 100:
            raise ValueError("Institutional ownership must be 0-100%")
        if not 0 <= self.insider_buying_intensity <= 10:
            raise ValueError("Insider buying intensity must be 0-10")

    @property
    def volume_signal_strength(self) -> SignalStrength:
        """Classify volume signal strength."""
        if self.trading_volume_anomaly >= 3.0:
            return SignalStrength.STRONG_BULLISH
        elif self.trading_volume_anomaly >= 2.0:
            return SignalStrength.BULLISH
        elif self.trading_volume_anomaly <= 0.5:
            return SignalStrength.BEARISH
        else:
            return SignalStrength.NEUTRAL

    @property
    def options_signal_strength(self) -> SignalStrength:
        """Classify options activity signal strength."""
        if self.options_activity == OptionsActivity.HEAVY_CALL_BUYING:
            if self.call_put_ratio >= 2.0:
                return SignalStrength.STRONG_BULLISH
            return SignalStrength.BULLISH
        elif self.options_activity == OptionsActivity.UNUSUAL_ACTIVITY:
            return SignalStrength.BULLISH
        elif self.options_activity == OptionsActivity.PROTECTIVE_PUTS:
            return SignalStrength.BEARISH
        return SignalStrength.NEUTRAL

    @property
    def institutional_signal_strength(self) -> SignalStrength:
        """Classify institutional activity signal strength."""
        if self.institutional_accumulation >= 5.0 and self.insider_buying_intensity >= 7:
            return SignalStrength.STRONG_BULLISH
        elif self.institutional_accumulation >= 3.0 or self.insider_buying_intensity >= 5:
            return SignalStrength.BULLISH
        elif self.institutional_accumulation <= -3.0:
            return SignalStrength.BEARISH
        return SignalStrength.NEUTRAL

    @property
    def analyst_signal_strength(self) -> SignalStrength:
        """Classify analyst activity signal strength."""
        net_upgrades = self.analyst_upgrades - self.analyst_downgrades

        if net_upgrades >= 3 and self.price_target_change >= 20:
            return SignalStrength.STRONG_BULLISH
        elif net_upgrades >= 2 or self.price_target_change >= 10:
            return SignalStrength.BULLISH
        elif net_upgrades <= -2:
            return SignalStrength.BEARISH
        return SignalStrength.NEUTRAL

    def calculate_composite_score(self) -> float:
        """
        Calculate composite M&A signal score (0-100).

        Higher scores indicate stronger M&A potential signals.

        Returns:
            Composite score from 0-100
        """
        score = 50.0  # Start neutral

        # Volume signals (0-20 points)
        if self.trading_volume_anomaly >= 3.0:
            score += 20
        elif self.trading_volume_anomaly >= 2.0:
            score += 15
        elif self.trading_volume_anomaly >= 1.5:
            score += 10

        # Options signals (0-20 points)
        if self.options_activity == OptionsActivity.HEAVY_CALL_BUYING:
            score += 15
        if self.call_put_ratio >= 2.0:
            score += 5
        elif self.call_put_ratio >= 1.5:
            score += 3

        # Institutional signals (0-25 points)
        score += min(self.institutional_accumulation * 2, 15)
        score += min(self.insider_buying_intensity * 1.5, 10)

        # Analyst signals (0-15 points)
        net_upgrades = self.analyst_upgrades - self.analyst_downgrades
        score += min(net_upgrades * 3, 10)
        score += min(self.price_target_change / 5, 5)

        # Short interest (0-10 points)
        # Decreasing short interest can indicate squeeze or buyout speculation
        if self.short_interest_change <= -20:
            score += 10
        elif self.short_interest_change <= -10:
            score += 5

        # Price momentum (0-10 points)
        if self.price_momentum_20d >= 20:
            score += 5
        if self.price_momentum_60d >= 30:
            score += 5

        return max(0, min(100, score))

    def get_ma_likelihood_indicator(self) -> Tuple[str, float]:
        """
        Get M&A likelihood indicator based on composite signals.

        Returns:
            Tuple of (likelihood_label, confidence_score)
        """
        composite = self.calculate_composite_score()

        if composite >= 80:
            return ("Very High", 0.85)
        elif composite >= 70:
            return ("High", 0.70)
        elif composite >= 60:
            return ("Moderate-High", 0.55)
        elif composite >= 50:
            return ("Moderate", 0.40)
        elif composite >= 40:
            return ("Low-Moderate", 0.30)
        else:
            return ("Low", 0.20)


class MarketObservationEngine:
    """
    Engine for tracking and analyzing market signals across multiple companies.
    """

    def __init__(self):
        """Initialize the market observation engine."""
        self.signals_cache: Dict[str, List[MarketSignals]] = {}
        self.watchlist: List[str] = []

    def add_to_watchlist(self, ticker: str) -> None:
        """Add a ticker to the watchlist."""
        if ticker not in self.watchlist:
            self.watchlist.append(ticker)

    def remove_from_watchlist(self, ticker: str) -> None:
        """Remove a ticker from the watchlist."""
        if ticker in self.watchlist:
            self.watchlist.remove(ticker)

    def record_signals(self, signals: MarketSignals) -> None:
        """
        Record market signals for a ticker.

        Args:
            signals: MarketSignals instance to record
        """
        if signals.ticker not in self.signals_cache:
            self.signals_cache[signals.ticker] = []

        self.signals_cache[signals.ticker].append(signals)

        # Keep only last 90 days of signals
        cutoff = datetime.now() - timedelta(days=90)
        self.signals_cache[signals.ticker] = [
            s for s in self.signals_cache[signals.ticker]
            if s.timestamp >= cutoff
        ]

    def get_latest_signals(self, ticker: str) -> Optional[MarketSignals]:
        """
        Get most recent signals for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Latest MarketSignals or None if not available
        """
        if ticker not in self.signals_cache or not self.signals_cache[ticker]:
            return None

        return sorted(self.signals_cache[ticker], key=lambda x: x.timestamp)[-1]

    def get_signal_history(
        self,
        ticker: str,
        days: int = 30
    ) -> List[MarketSignals]:
        """
        Get historical signals for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back

        Returns:
            List of MarketSignals sorted by timestamp
        """
        if ticker not in self.signals_cache:
            return []

        cutoff = datetime.now() - timedelta(days=days)
        return sorted(
            [s for s in self.signals_cache[ticker] if s.timestamp >= cutoff],
            key=lambda x: x.timestamp
        )

    def scan_for_anomalies(
        self,
        min_volume_anomaly: float = 2.0,
        min_insider_buying: float = 5.0
    ) -> List[Tuple[str, MarketSignals, str]]:
        """
        Scan watchlist for unusual market activity.

        Args:
            min_volume_anomaly: Minimum volume anomaly threshold
            min_insider_buying: Minimum insider buying intensity

        Returns:
            List of (ticker, signals, reason) tuples for anomalies
        """
        anomalies = []

        for ticker in self.watchlist:
            latest = self.get_latest_signals(ticker)
            if not latest:
                continue

            reasons = []

            # Check volume anomalies
            if latest.trading_volume_anomaly >= min_volume_anomaly:
                reasons.append(
                    f"Volume spike: {latest.trading_volume_anomaly:.1f}x average"
                )

            # Check insider buying
            if latest.insider_buying_intensity >= min_insider_buying:
                reasons.append(
                    f"Heavy insider buying: {latest.insider_buying_intensity:.1f}/10"
                )

            # Check unusual options activity
            if latest.options_activity in [
                OptionsActivity.HEAVY_CALL_BUYING,
                OptionsActivity.UNUSUAL_ACTIVITY
            ]:
                reasons.append(f"Unusual options: {latest.options_activity.value}")

            # Check institutional accumulation
            if latest.institutional_accumulation >= 5.0:
                reasons.append(
                    f"Institutional accumulation: +{latest.institutional_accumulation:.1f}%"
                )

            # Check analyst upgrades
            if latest.analyst_upgrades >= 3:
                reasons.append(f"Multiple analyst upgrades: {latest.analyst_upgrades}")

            if reasons:
                anomalies.append((ticker, latest, "; ".join(reasons)))

        return sorted(anomalies, key=lambda x: x[1].calculate_composite_score(), reverse=True)

    def get_top_ma_candidates(self, top_n: int = 10) -> List[Tuple[str, float, str]]:
        """
        Get top M&A candidates based on signal analysis.

        Args:
            top_n: Number of top candidates to return

        Returns:
            List of (ticker, score, likelihood) tuples
        """
        candidates = []

        for ticker in self.watchlist:
            latest = self.get_latest_signals(ticker)
            if not latest:
                continue

            score = latest.calculate_composite_score()
            likelihood, _ = latest.get_ma_likelihood_indicator()

            candidates.append((ticker, score, likelihood))

        return sorted(candidates, key=lambda x: x[1], reverse=True)[:top_n]

    def generate_mock_signals(
        self,
        ticker: str,
        ma_likely: bool = False
    ) -> MarketSignals:
        """
        Generate realistic mock market signals for testing.

        Args:
            ticker: Stock ticker symbol
            ma_likely: If True, generate signals suggesting M&A activity

        Returns:
            MarketSignals instance with simulated data
        """
        if ma_likely:
            # Generate signals suggesting potential M&A
            return MarketSignals(
                ticker=ticker,
                timestamp=datetime.now(),
                trading_volume_anomaly=random.uniform(2.5, 4.0),
                relative_volume=random.uniform(2.0, 3.5),
                short_interest_change=random.uniform(-25, -10),
                short_interest_ratio=random.uniform(2, 5),
                options_activity=OptionsActivity.HEAVY_CALL_BUYING,
                call_put_ratio=random.uniform(2.0, 3.5),
                unusual_options_volume=random.uniform(3.0, 5.0),
                analyst_upgrades=random.randint(3, 6),
                analyst_downgrades=random.randint(0, 1),
                price_target_change=random.uniform(20, 40),
                institutional_accumulation=random.uniform(5.0, 10.0),
                insider_buying_intensity=random.uniform(7.0, 10.0),
                institutional_ownership_pct=random.uniform(60, 85),
                price_momentum_20d=random.uniform(15, 35),
                price_momentum_60d=random.uniform(25, 50),
                distance_from_52w_high=random.uniform(-10, 0),
                distance_from_52w_low=random.uniform(40, 80)
            )
        else:
            # Generate normal market signals
            return MarketSignals(
                ticker=ticker,
                timestamp=datetime.now(),
                trading_volume_anomaly=random.uniform(0.8, 1.3),
                relative_volume=random.uniform(0.9, 1.2),
                short_interest_change=random.uniform(-5, 5),
                short_interest_ratio=random.uniform(3, 7),
                options_activity=OptionsActivity.NORMAL,
                call_put_ratio=random.uniform(0.8, 1.2),
                unusual_options_volume=random.uniform(0.9, 1.1),
                analyst_upgrades=random.randint(0, 2),
                analyst_downgrades=random.randint(0, 2),
                price_target_change=random.uniform(-5, 10),
                institutional_accumulation=random.uniform(-2.0, 2.0),
                insider_buying_intensity=random.uniform(2.0, 5.0),
                institutional_ownership_pct=random.uniform(40, 70),
                price_momentum_20d=random.uniform(-10, 15),
                price_momentum_60d=random.uniform(-15, 20),
                distance_from_52w_high=random.uniform(-30, -5),
                distance_from_52w_low=random.uniform(20, 60)
            )
