"""
Market sentiment analysis for biotech M&A prediction.

This module analyzes sentiment from multiple sources including news,
conferences, and social media to gauge market sentiment around biotech companies.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import random
import re


class SentimentPolarity(Enum):
    """Sentiment polarity classifications."""
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class ConferenceType(Enum):
    """Major biotech/healthcare conferences."""
    JPM = "jpm"  # JP Morgan Healthcare Conference
    ASCO = "asco"  # American Society of Clinical Oncology
    ASH = "ash"  # American Society of Hematology
    AACR = "aacr"  # American Association for Cancer Research
    ESMO = "esmo"  # European Society for Medical Oncology
    BIO = "bio"  # BIO International Convention


@dataclass
class NewsArticle:
    """Represents a news article about a biotech company."""
    title: str
    source: str
    published_date: datetime
    sentiment_score: float  # -1 (negative) to 1 (positive)
    relevance_score: float  # 0 to 1
    keywords: List[str]
    mentions_ma: bool = False

    @property
    def weighted_sentiment(self) -> float:
        """Calculate sentiment weighted by relevance."""
        return self.sentiment_score * self.relevance_score


@dataclass
class ConferenceMention:
    """Represents a company mention at a major conference."""
    conference: ConferenceType
    date: datetime
    presentation_type: str  # "oral", "poster", "keynote", "panel"
    topic: str
    buzz_score: float  # 0 to 10 based on attention/discussion
    data_quality: str  # "breakthrough", "positive", "neutral", "disappointing"


@dataclass
class SocialMediaMetrics:
    """Social media sentiment and engagement metrics."""
    platform: str  # "twitter", "stocktwits", "reddit", etc.
    timestamp: datetime
    mention_count: int
    sentiment_score: float  # -1 to 1
    engagement_score: float  # 0 to 10
    trending: bool
    key_topics: List[str]


@dataclass
class SentimentScore:
    """
    Comprehensive sentiment score for a biotech company.

    Aggregates sentiment from multiple sources to provide
    an overall market sentiment assessment.
    """
    ticker: str
    timestamp: datetime

    # Component scores (all -1 to 1 scale)
    news_sentiment: float
    conference_sentiment: float
    social_sentiment: float
    analyst_sentiment: float

    # Confidence levels (0 to 1)
    news_confidence: float
    conference_confidence: float
    social_confidence: float
    analyst_confidence: float

    # Additional metrics
    news_volume: int  # Number of articles
    social_mentions: int
    conference_presentations: int

    def __post_init__(self):
        """Validate sentiment scores."""
        for score in [self.news_sentiment, self.conference_sentiment,
                      self.social_sentiment, self.analyst_sentiment]:
            if not -1 <= score <= 1:
                raise ValueError(f"Sentiment score must be between -1 and 1, got {score}")

        for conf in [self.news_confidence, self.conference_confidence,
                     self.social_confidence, self.analyst_confidence]:
            if not 0 <= conf <= 1:
                raise ValueError(f"Confidence must be between 0 and 1, got {conf}")

    @property
    def aggregate_sentiment(self) -> float:
        """
        Calculate weighted aggregate sentiment score.

        Returns:
            Aggregate sentiment from -1 to 1
        """
        total_weight = 0.0
        weighted_sum = 0.0

        # Weight each component by its confidence
        components = [
            (self.news_sentiment, self.news_confidence, 0.35),  # 35% weight
            (self.conference_sentiment, self.conference_confidence, 0.25),  # 25% weight
            (self.social_sentiment, self.social_confidence, 0.20),  # 20% weight
            (self.analyst_sentiment, self.analyst_confidence, 0.20),  # 20% weight
        ]

        for sentiment, confidence, base_weight in components:
            effective_weight = base_weight * confidence
            weighted_sum += sentiment * effective_weight
            total_weight += effective_weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    @property
    def sentiment_polarity(self) -> SentimentPolarity:
        """Classify overall sentiment polarity."""
        agg = self.aggregate_sentiment

        if agg >= 0.6:
            return SentimentPolarity.VERY_POSITIVE
        elif agg >= 0.2:
            return SentimentPolarity.POSITIVE
        elif agg >= -0.2:
            return SentimentPolarity.NEUTRAL
        elif agg >= -0.6:
            return SentimentPolarity.NEGATIVE
        else:
            return SentimentPolarity.VERY_NEGATIVE

    @property
    def overall_confidence(self) -> float:
        """Calculate overall confidence in sentiment assessment."""
        confidences = [
            self.news_confidence,
            self.conference_confidence,
            self.social_confidence,
            self.analyst_confidence
        ]
        return sum(confidences) / len(confidences)

    def get_sentiment_summary(self) -> str:
        """Get human-readable sentiment summary."""
        polarity = self.sentiment_polarity.value.replace("_", " ").title()
        confidence = self.overall_confidence

        if confidence >= 0.8:
            conf_level = "High"
        elif confidence >= 0.5:
            conf_level = "Moderate"
        else:
            conf_level = "Low"

        return f"{polarity} ({conf_level} Confidence)"


class SentimentModel:
    """
    Model for analyzing and tracking sentiment from multiple sources.
    """

    def __init__(self):
        """Initialize the sentiment model."""
        self.news_cache: Dict[str, List[NewsArticle]] = {}
        self.conference_cache: Dict[str, List[ConferenceMention]] = {}
        self.social_cache: Dict[str, List[SocialMediaMetrics]] = {}

        # Sentiment lexicon for basic NLP
        self.positive_keywords = [
            "breakthrough", "positive", "success", "approval", "advance",
            "promising", "effective", "milestone", "partnership", "acquisition",
            "beat", "exceed", "strong", "growth", "innovative", "FDA approval",
            "clinical success", "expansion", "outperform", "bullish"
        ]

        self.negative_keywords = [
            "failure", "disappointing", "decline", "risk", "concern",
            "miss", "delay", "setback", "warning", "investigation",
            "lawsuit", "rejected", "terminated", "bearish", "downgrade",
            "loss", "weak", "struggle", "challenge", "adverse"
        ]

        self.ma_keywords = [
            "acquisition", "merger", "buyout", "takeover", "deal",
            "offer", "bid", "acquire", "purchase", "M&A"
        ]

    def analyze_news_sentiment(
        self,
        company: str,
        articles: Optional[List[NewsArticle]] = None,
        days: int = 30
    ) -> float:
        """
        Analyze news sentiment for a company.

        Args:
            company: Company name or ticker
            articles: Optional list of articles (if None, uses cache)
            days: Number of days to look back

        Returns:
            Sentiment score from -1 to 1
        """
        if articles is None:
            articles = self._get_recent_news(company, days)

        if not articles:
            return 0.0

        # Calculate weighted average sentiment
        total_weight = 0.0
        weighted_sum = 0.0

        for article in articles:
            # More recent articles get higher weight
            age_days = (datetime.now() - article.published_date).days
            recency_weight = max(0.1, 1.0 - (age_days / days))

            weight = article.relevance_score * recency_weight
            weighted_sum += article.sentiment_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def conference_buzz_score(
        self,
        company: str,
        conferences: Optional[List[ConferenceMention]] = None,
        days: int = 180  # Conferences are less frequent
    ) -> float:
        """
        Calculate conference buzz score for a company.

        Args:
            company: Company name or ticker
            conferences: Optional list of conference mentions
            days: Number of days to look back

        Returns:
            Buzz score from 0 to 10
        """
        if conferences is None:
            conferences = self._get_recent_conferences(company, days)

        if not conferences:
            return 0.0

        # Weight by presentation type
        type_weights = {
            "keynote": 2.0,
            "oral": 1.5,
            "panel": 1.2,
            "poster": 0.8
        }

        # Weight by data quality
        quality_multipliers = {
            "breakthrough": 2.0,
            "positive": 1.5,
            "neutral": 1.0,
            "disappointing": 0.5
        }

        total_score = 0.0
        for conf in conferences:
            base_score = conf.buzz_score
            type_weight = type_weights.get(conf.presentation_type, 1.0)
            quality_mult = quality_multipliers.get(conf.data_quality, 1.0)

            total_score += base_score * type_weight * quality_mult

        # Normalize to 0-10 scale
        if not conferences:
            return 0.0

        return min(10.0, total_score / len(conferences))

    def social_media_momentum(
        self,
        company: str,
        social_data: Optional[List[SocialMediaMetrics]] = None,
        days: int = 7
    ) -> float:
        """
        Calculate social media momentum score.

        Args:
            company: Company name or ticker
            social_data: Optional list of social media metrics
            days: Number of days to look back

        Returns:
            Momentum score from -1 to 1
        """
        if social_data is None:
            social_data = self._get_recent_social(company, days)

        if not social_data:
            return 0.0

        # Weight by engagement and recency
        total_weight = 0.0
        weighted_sentiment = 0.0

        for data in social_data:
            age_hours = (datetime.now() - data.timestamp).total_seconds() / 3600
            recency_weight = max(0.1, 1.0 - (age_hours / (days * 24)))

            weight = data.engagement_score * recency_weight
            if data.trending:
                weight *= 1.5  # Boost trending topics

            weighted_sentiment += data.sentiment_score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sentiment / total_weight

    def analyze_text_sentiment(self, text: str) -> Tuple[float, bool]:
        """
        Perform basic sentiment analysis on text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (sentiment_score, mentions_ma)
        """
        text_lower = text.lower()

        # Count positive and negative keywords
        positive_count = sum(1 for kw in self.positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text_lower)

        # Calculate sentiment score
        total_keywords = positive_count + negative_count
        if total_keywords == 0:
            sentiment = 0.0
        else:
            sentiment = (positive_count - negative_count) / total_keywords

        # Check for M&A mentions
        mentions_ma = any(kw in text_lower for kw in self.ma_keywords)

        return sentiment, mentions_ma

    def aggregate_sentiment(
        self,
        ticker: str,
        lookback_days: int = 30
    ) -> SentimentScore:
        """
        Aggregate sentiment from all sources.

        Args:
            ticker: Stock ticker symbol
            lookback_days: Number of days to analyze

        Returns:
            SentimentScore with comprehensive sentiment analysis
        """
        # Get data from all sources
        news_articles = self._get_recent_news(ticker, lookback_days)
        conferences = self._get_recent_conferences(ticker, 180)
        social_data = self._get_recent_social(ticker, 7)

        # Calculate component sentiments
        news_sentiment = self.analyze_news_sentiment(ticker, news_articles, lookback_days)
        conf_sentiment = (self.conference_buzz_score(ticker, conferences, 180) - 5.0) / 5.0  # Normalize to -1 to 1
        social_sentiment = self.social_media_momentum(ticker, social_data, 7)

        # Analyst sentiment (simplified - would integrate with analyst data in production)
        analyst_sentiment = random.uniform(-0.3, 0.5)  # Placeholder

        # Calculate confidence based on data volume
        news_confidence = min(1.0, len(news_articles) / 20)
        conference_confidence = min(1.0, len(conferences) / 3)
        social_confidence = min(1.0, sum(d.mention_count for d in social_data) / 100)
        analyst_confidence = 0.5  # Placeholder

        return SentimentScore(
            ticker=ticker,
            timestamp=datetime.now(),
            news_sentiment=news_sentiment,
            conference_sentiment=conf_sentiment,
            social_sentiment=social_sentiment,
            analyst_sentiment=analyst_sentiment,
            news_confidence=news_confidence,
            conference_confidence=conference_confidence,
            social_confidence=social_confidence,
            analyst_confidence=analyst_confidence,
            news_volume=len(news_articles),
            social_mentions=sum(d.mention_count for d in social_data),
            conference_presentations=len(conferences)
        )

    def detect_sentiment_shift(
        self,
        ticker: str,
        window_days: int = 7
    ) -> Tuple[float, str]:
        """
        Detect significant sentiment shifts.

        Args:
            ticker: Stock ticker symbol
            window_days: Window for comparison

        Returns:
            Tuple of (change_magnitude, description)
        """
        current = self.aggregate_sentiment(ticker, window_days)

        # Get historical comparison (simplified)
        historical_sentiment = random.uniform(-0.2, 0.2)  # Placeholder

        change = current.aggregate_sentiment - historical_sentiment

        if abs(change) >= 0.5:
            direction = "improved" if change > 0 else "deteriorated"
            return change, f"Sentiment has significantly {direction}"
        elif abs(change) >= 0.3:
            direction = "improved" if change > 0 else "declined"
            return change, f"Sentiment has {direction} moderately"
        else:
            return change, "Sentiment is relatively stable"

    def _get_recent_news(self, company: str, days: int) -> List[NewsArticle]:
        """Get recent news articles from cache or generate mock data."""
        if company in self.news_cache:
            cutoff = datetime.now() - timedelta(days=days)
            return [a for a in self.news_cache[company] if a.published_date >= cutoff]

        # Generate mock data for demonstration
        return self._generate_mock_news(company, days)

    def _get_recent_conferences(self, company: str, days: int) -> List[ConferenceMention]:
        """Get recent conference mentions from cache or generate mock data."""
        if company in self.conference_cache:
            cutoff = datetime.now() - timedelta(days=days)
            return [c for c in self.conference_cache[company] if c.date >= cutoff]

        return self._generate_mock_conferences(company)

    def _get_recent_social(self, company: str, days: int) -> List[SocialMediaMetrics]:
        """Get recent social media data from cache or generate mock data."""
        if company in self.social_cache:
            cutoff = datetime.now() - timedelta(days=days)
            return [s for s in self.social_cache[company] if s.timestamp >= cutoff]

        return self._generate_mock_social(company, days)

    def _generate_mock_news(self, company: str, days: int) -> List[NewsArticle]:
        """Generate realistic mock news articles for testing."""
        articles = []
        num_articles = random.randint(5, 20)

        titles = [
            f"{company} announces positive Phase 3 results",
            f"Analysts upgrade {company} on strong pipeline",
            f"{company} presents breakthrough data at ASCO",
            f"FDA grants priority review to {company}'s lead candidate",
            f"{company} faces setback in clinical trial",
            f"Institutional investors increase stakes in {company}",
            f"{company} expands partnership with major pharma",
            f"Market watch: {company} shows strong momentum",
            f"{company} receives analyst downgrade on valuation concerns",
            f"Breaking: {company} exploring strategic alternatives"
        ]

        sources = ["Bloomberg", "Reuters", "BioPharma Dive", "FierceBiotech",
                   "STAT News", "Wall Street Journal", "Seeking Alpha"]

        for _ in range(num_articles):
            title = random.choice(titles)
            sentiment, mentions_ma = self.analyze_text_sentiment(title)

            articles.append(NewsArticle(
                title=title,
                source=random.choice(sources),
                published_date=datetime.now() - timedelta(days=random.randint(0, days)),
                sentiment_score=sentiment + random.uniform(-0.2, 0.2),
                relevance_score=random.uniform(0.6, 1.0),
                keywords=["biotech", "clinical", "pipeline"],
                mentions_ma=mentions_ma
            ))

        return articles

    def _generate_mock_conferences(self, company: str) -> List[ConferenceMention]:
        """Generate realistic mock conference mentions."""
        conferences = []
        num_mentions = random.randint(1, 4)

        for _ in range(num_mentions):
            conferences.append(ConferenceMention(
                conference=random.choice(list(ConferenceType)),
                date=datetime.now() - timedelta(days=random.randint(0, 180)),
                presentation_type=random.choice(["oral", "poster", "keynote", "panel"]),
                topic="Clinical trial results and pipeline update",
                buzz_score=random.uniform(3.0, 9.0),
                data_quality=random.choice(["breakthrough", "positive", "neutral", "disappointing"])
            ))

        return conferences

    def _generate_mock_social(self, company: str, days: int) -> List[SocialMediaMetrics]:
        """Generate realistic mock social media metrics."""
        social_data = []

        platforms = ["twitter", "stocktwits", "reddit"]

        for platform in platforms:
            for day in range(min(days, 7)):
                social_data.append(SocialMediaMetrics(
                    platform=platform,
                    timestamp=datetime.now() - timedelta(days=day),
                    mention_count=random.randint(10, 500),
                    sentiment_score=random.uniform(-0.5, 0.7),
                    engagement_score=random.uniform(3.0, 9.0),
                    trending=random.random() < 0.2,
                    key_topics=["biotech", "clinical trials", "M&A"]
                ))

        return social_data
