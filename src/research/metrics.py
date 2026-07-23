"""Rare-event ranking and probability metrics for historical M&A panels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class RankedObservation:
    observation_id: str
    score: float
    label: bool
    probability: float | None = None


def _validate(observations: Sequence[RankedObservation]) -> None:
    if not observations:
        raise ValueError("at least one observation is required")
    identifiers = [item.observation_id for item in observations]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("observation_id values must be unique")
    for item in observations:
        if not math.isfinite(item.score):
            raise ValueError(f"non-finite score for {item.observation_id}")
        if item.probability is not None and not 0.0 <= item.probability <= 1.0:
            raise ValueError(f"probability outside [0, 1] for {item.observation_id}")


def average_precision(observations: Iterable[RankedObservation]) -> float:
    """Return average precision with deterministic observation-ID tie breaking."""
    materialized = list(observations)
    _validate(materialized)
    ranked = sorted(materialized, key=lambda item: (-item.score, item.observation_id))
    positives = sum(item.label for item in ranked)
    if positives == 0:
        return 0.0
    true_positives = 0
    accumulated_precision = 0.0
    for rank, item in enumerate(ranked, 1):
        if item.label:
            true_positives += 1
            accumulated_precision += true_positives / rank
    return accumulated_precision / positives


def evaluate_rare_event_ranking(
    observations: Iterable[RankedObservation],
    *,
    cutoffs: Sequence[int] = (5, 10, 20),
) -> dict[str, object]:
    """Evaluate top-k lift and optional probability quality.

    Probability metrics are emitted only when every row contains an explicit
    probability. An arbitrary research score is never normalized and presented
    as a probability.
    """
    materialized = list(observations)
    _validate(materialized)
    ranked = sorted(materialized, key=lambda item: (-item.score, item.observation_id))
    total = len(ranked)
    positives = sum(item.label for item in ranked)
    base_rate = positives / total
    top_k: dict[str, dict[str, float | int]] = {}
    for requested_k in cutoffs:
        if requested_k < 1:
            raise ValueError("cutoffs must be positive")
        k = min(requested_k, total)
        captured = sum(item.label for item in ranked[:k])
        precision = captured / k
        recall = captured / positives if positives else 0.0
        lift = precision / base_rate if base_rate else 0.0
        top_k[str(requested_k)] = {
            "effective_k": k,
            "captured_positives": captured,
            "precision": precision,
            "recall": recall,
            "lift_over_base_rate": lift,
        }

    result: dict[str, object] = {
        "observations": total,
        "positives": positives,
        "base_rate": base_rate,
        "average_precision": average_precision(ranked),
        "top_k": top_k,
        "probability_metrics": None,
    }
    if all(item.probability is not None for item in ranked):
        epsilon = 1e-15
        brier = (
            sum((float(item.probability) - float(item.label)) ** 2 for item in ranked)
            / total
        )
        log_loss = (
            -sum(
                float(item.label) * math.log(max(epsilon, float(item.probability)))
                + (1.0 - float(item.label))
                * math.log(max(epsilon, 1.0 - float(item.probability)))
                for item in ranked
            )
            / total
        )
        result["probability_metrics"] = {
            "brier_score": brier,
            "log_loss": log_loss,
        }
    return result
