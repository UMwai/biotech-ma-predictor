"""
Scoring Weights Configuration

Provides configurable weights for the M&A scoring engine components.
Weights can be adjusted based on market conditions, therapeutic areas,
or specific use cases.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class ScoreComponent(str, Enum):
    """Enumeration of available scoring components."""
    PIPELINE = "pipeline"
    PATENT = "patent"
    FINANCIAL = "financial"
    INSIDER = "insider"
    STRATEGIC_FIT = "strategic_fit"
    REGULATORY = "regulatory"


@dataclass
class ComponentWeight:
    """
    Individual component weight configuration.

    Attributes:
        name: Component name
        weight: Weight value (0.0 to 1.0)
        enabled: Whether this component is active
        min_score: Minimum acceptable score for this component
        decay_factor: Time decay factor for signals (days)
    """
    name: str
    weight: float
    enabled: bool = True
    min_score: Optional[float] = None
    decay_factor: float = 30.0  # days

    def __post_init__(self):
        """Validate weight configuration."""
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {self.weight}")
        if self.decay_factor <= 0:
            raise ValueError(f"Decay factor must be positive, got {self.decay_factor}")


@dataclass
class ScoringWeights:
    """
    Configuration for M&A scoring engine weights.

    The weights determine how much each component contributes to the
    overall M&A likelihood score. Weights are normalized to sum to 1.0.

    Attributes:
        pipeline_weight: Weight for drug pipeline score
        patent_weight: Weight for IP/patent score
        financial_weight: Weight for financial metrics score
        insider_weight: Weight for insider activity score
        strategic_fit_weight: Weight for strategic fit score
        regulatory_weight: Weight for regulatory pathway score
        decay_half_life: Half-life for signal decay in days
        custom_weights: Optional custom component weights

    Example:
        >>> weights = ScoringWeights(
        ...     pipeline_weight=0.30,
        ...     patent_weight=0.25,
        ...     financial_weight=0.20
        ... )
        >>> weights.normalize()
        >>> print(weights.get_weight('pipeline'))
        0.30
    """

    # Component weights (will be normalized)
    pipeline_weight: float = 0.30
    patent_weight: float = 0.20
    financial_weight: float = 0.15
    insider_weight: float = 0.15
    strategic_fit_weight: float = 0.10
    regulatory_weight: float = 0.10

    # Global decay settings
    decay_half_life: float = 30.0  # days
    recent_signal_boost: float = 1.5  # multiplier for signals < 7 days

    # Thresholds
    min_overall_score: float = 40.0  # minimum to be considered
    watchlist_add_threshold: float = 70.0  # auto-add to watchlist
    watchlist_remove_threshold: float = 50.0  # auto-remove from watchlist
    alert_threshold_change: float = 10.0  # points change to trigger alert

    # Component-specific settings
    custom_weights: Dict[str, ComponentWeight] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize and validate weight configuration."""
        self._validate_weights()
        self._initialize_component_weights()

    def _validate_weights(self):
        """Validate that all weights are within valid ranges."""
        weights = [
            self.pipeline_weight,
            self.patent_weight,
            self.financial_weight,
            self.insider_weight,
            self.strategic_fit_weight,
            self.regulatory_weight,
        ]

        for weight in weights:
            if weight < 0:
                raise ValueError(f"Weights must be non-negative, got {weight}")

        if sum(weights) == 0:
            raise ValueError("At least one weight must be positive")

        if self.decay_half_life <= 0:
            raise ValueError("Decay half-life must be positive")

    def _initialize_component_weights(self):
        """Initialize component weight objects if not custom defined."""
        default_components = {
            ScoreComponent.PIPELINE: ComponentWeight(
                name=ScoreComponent.PIPELINE,
                weight=self.pipeline_weight,
                decay_factor=60.0,  # Pipeline news decays slowly
            ),
            ScoreComponent.PATENT: ComponentWeight(
                name=ScoreComponent.PATENT,
                weight=self.patent_weight,
                decay_factor=90.0,  # Patent news decays very slowly
            ),
            ScoreComponent.FINANCIAL: ComponentWeight(
                name=ScoreComponent.FINANCIAL,
                weight=self.financial_weight,
                decay_factor=14.0,  # Financial metrics change quickly
            ),
            ScoreComponent.INSIDER: ComponentWeight(
                name=ScoreComponent.INSIDER,
                weight=self.insider_weight,
                decay_factor=30.0,  # Insider activity moderate decay
            ),
            ScoreComponent.STRATEGIC_FIT: ComponentWeight(
                name=ScoreComponent.STRATEGIC_FIT,
                weight=self.strategic_fit_weight,
                decay_factor=180.0,  # Strategic fit is stable
            ),
            ScoreComponent.REGULATORY: ComponentWeight(
                name=ScoreComponent.REGULATORY,
                weight=self.regulatory_weight,
                decay_factor=45.0,  # Regulatory news moderate decay
            ),
        }

        # Merge with custom weights
        for component, default_weight in default_components.items():
            if component not in self.custom_weights:
                self.custom_weights[component] = default_weight

    def normalize(self) -> 'ScoringWeights':
        """
        Normalize weights to sum to 1.0.

        Returns:
            Self for method chaining
        """
        total_weight = sum(
            w.weight for w in self.custom_weights.values() if w.enabled
        )

        if total_weight == 0:
            raise ValueError("Total weight cannot be zero after filtering enabled components")

        # Normalize each component
        for component_weight in self.custom_weights.values():
            if component_weight.enabled:
                component_weight.weight /= total_weight

        return self

    def get_weight(self, component: str) -> float:
        """
        Get normalized weight for a specific component.

        Args:
            component: Component name

        Returns:
            Normalized weight value
        """
        if component not in self.custom_weights:
            return 0.0

        comp_weight = self.custom_weights[component]
        return comp_weight.weight if comp_weight.enabled else 0.0

    def get_decay_factor(self, component: str) -> float:
        """
        Get decay factor for a specific component.

        Args:
            component: Component name

        Returns:
            Decay factor in days
        """
        if component not in self.custom_weights:
            return self.decay_half_life

        return self.custom_weights[component].decay_factor

    def enable_component(self, component: str) -> None:
        """Enable a scoring component."""
        if component in self.custom_weights:
            self.custom_weights[component].enabled = True

    def disable_component(self, component: str) -> None:
        """Disable a scoring component."""
        if component in self.custom_weights:
            self.custom_weights[component].enabled = False

    def set_weight(self, component: str, weight: float) -> None:
        """
        Set weight for a specific component.

        Args:
            component: Component name
            weight: New weight value (will be normalized)
        """
        if component not in self.custom_weights:
            raise ValueError(f"Unknown component: {component}")

        if weight < 0:
            raise ValueError("Weight must be non-negative")

        self.custom_weights[component].weight = weight

    def get_enabled_components(self) -> Dict[str, ComponentWeight]:
        """Get all enabled components."""
        return {
            name: weight
            for name, weight in self.custom_weights.items()
            if weight.enabled
        }

    def to_dict(self) -> Dict:
        """Convert weights to dictionary representation."""
        return {
            'component_weights': {
                name: {
                    'weight': w.weight,
                    'enabled': w.enabled,
                    'decay_factor': w.decay_factor,
                }
                for name, w in self.custom_weights.items()
            },
            'decay_half_life': self.decay_half_life,
            'recent_signal_boost': self.recent_signal_boost,
            'thresholds': {
                'min_overall_score': self.min_overall_score,
                'watchlist_add': self.watchlist_add_threshold,
                'watchlist_remove': self.watchlist_remove_threshold,
                'alert_change': self.alert_threshold_change,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ScoringWeights':
        """
        Create ScoringWeights from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            ScoringWeights instance
        """
        custom_weights = {}

        for name, weight_data in data.get('component_weights', {}).items():
            custom_weights[name] = ComponentWeight(
                name=name,
                weight=weight_data['weight'],
                enabled=weight_data.get('enabled', True),
                decay_factor=weight_data.get('decay_factor', 30.0),
            )

        thresholds = data.get('thresholds', {})

        return cls(
            custom_weights=custom_weights,
            decay_half_life=data.get('decay_half_life', 30.0),
            recent_signal_boost=data.get('recent_signal_boost', 1.5),
            min_overall_score=thresholds.get('min_overall_score', 40.0),
            watchlist_add_threshold=thresholds.get('watchlist_add', 70.0),
            watchlist_remove_threshold=thresholds.get('watchlist_remove', 50.0),
            alert_threshold_change=thresholds.get('alert_change', 10.0),
        )


# Predefined weight configurations for different scenarios

AGGRESSIVE_WEIGHTS = ScoringWeights(
    pipeline_weight=0.35,
    patent_weight=0.25,
    financial_weight=0.10,
    insider_weight=0.20,
    strategic_fit_weight=0.05,
    regulatory_weight=0.05,
    watchlist_add_threshold=65.0,
)

CONSERVATIVE_WEIGHTS = ScoringWeights(
    pipeline_weight=0.25,
    patent_weight=0.20,
    financial_weight=0.25,
    insider_weight=0.10,
    strategic_fit_weight=0.10,
    regulatory_weight=0.10,
    watchlist_add_threshold=75.0,
)

EARLY_STAGE_WEIGHTS = ScoringWeights(
    pipeline_weight=0.40,
    patent_weight=0.30,
    financial_weight=0.05,
    insider_weight=0.10,
    strategic_fit_weight=0.10,
    regulatory_weight=0.05,
)

LATE_STAGE_WEIGHTS = ScoringWeights(
    pipeline_weight=0.25,
    patent_weight=0.15,
    financial_weight=0.20,
    insider_weight=0.15,
    strategic_fit_weight=0.10,
    regulatory_weight=0.15,
)
