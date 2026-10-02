"""Source-bound ordinal M&A rankings, never deal probabilities or historical seals."""
from __future__ import annotations

import hashlib
import math
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.research.training import TrainingBlocked, _digest, _require, _time

VERSION = "ma-diligence-v1"
POSITIVE_FIELDS = ("clinical_evidence", "clinical_differentiation", "asset_rights",
                   "buyer_fit", "buyer_capacity", "public_engagement", "valuation_attractiveness")
NON_BUYER_FIELDS = tuple(name for name in POSITIVE_FIELDS if not name.startswith("buyer_")) + ("execution_risk",)
SCIENCE_FIELDS = ("clinical_evidence", "clinical_differentiation", "asset_rights")
BUYER_FIELDS = ("buyer_fit", "buyer_capacity")
FINANCIAL_FEATURES = ("cash_usd", "assets_usd", "annual_operating_cashflow_usd", "annual_rd_usd", "annual_cash_burn_usd")
FINANCIAL_UNITS = {name: "USD" if name in ("cash_usd", "assets_usd") else "USD/fiscal_year" for name in FINANCIAL_FEATURES}


def validate_parameters(config: Any) -> dict[str, Any]:
    expected = {"schema_version", "model_version", "rubric_version", "event", "horizon_days",
                "test_start_year", "primary_metric", "k", "regularization_c", "weights", "execution_risk_penalty",
                "buyer_selection_rule", "score_families", "ablation_policy", "top_k_tie_policy", "undefined_metric_policy"}
    _require(isinstance(config, dict) and set(config) == expected, "exact parameter field set required")
    for name, value in (("schema_version", "ma-diligence-parameters-v1"), ("model_version", VERSION),
                        ("rubric_version", VERSION), ("event", "change_of_control_announcement"),
                        ("primary_metric", "mean_cohort_lift_at_5")):
        _require(config[name] == value, f"unsupported {name}")
    for name, value in (("horizon_days", 365), ("test_start_year", 2023), ("k", 5)):
        _require(type(config[name]) is int and config[name] == value, f"{name} must equal {value}")
    weights = config["weights"]
    _require(isinstance(weights, dict) and set(weights) == set(POSITIVE_FIELDS), "exact positive weight field set required")
    for name, value in {**weights, "execution_risk_penalty": config["execution_risk_penalty"],
                        "regularization_c": config["regularization_c"]}.items():
        _require(type(value) in (int, float) and math.isfinite(value), f"{name}: finite numeric value required")
    _require(all(value >= 0 for value in weights.values()) and math.isclose(sum(weights.values()), 1, abs_tol=1e-12, rel_tol=0),
             "weights must be nonnegative and sum to one")
    _require(0 <= config["execution_risk_penalty"] <= 1, "risk penalty must lie in [0,1]")
    _require(config["regularization_c"] == 1, "regularization_c must equal 1 for v1")
    fixed_policies = {
        "buyer_selection_rule": "max_.20_fit_plus_.10_capacity_tie_buyer_id_ascending",
        "score_families": {"full": list(POSITIVE_FIELDS) + ["execution_risk"],
                           "science_only": list(SCIENCE_FIELDS), "buyer_only": list(BUYER_FIELDS)},
        "ablation_policy": "retained_full_weights_without_renormalization_no_execution_penalty",
        "top_k_tie_policy": "observation_id_ascending",
        "undefined_metric_policy": "omit_zero_positive_cohorts_report_support"}
    for name, value in fixed_policies.items():
        _require(config[name] == value, f"unsupported registered policy {name}")
    # Buyer selection remains the fixed predeclared .20/.10 rule even in a new registration.
    return config


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field}: nonempty text required")
    return value


def _source(source: Any, cutoff, reviewed, evidence_root: Path) -> None:
    _require(isinstance(source, dict), "source: object required")
    for name in ("source_uri", "source_relative_path", "source_sha256", "source_locator", "original_version_basis"):
        _text(source.get(name), name)
    parsed = urlparse(source["source_uri"])
    _require(parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None and parsed.password is None,
             "source_uri must be https")
    _require(source.get("version_status") == "verified_original", "historical source requires verified_original version_status")
    available = _time(source.get("available_at"), "source.available_at")
    retrieved = _time(source.get("retrieved_at"), "source.retrieved_at")
    _require(available <= cutoff, "source available after observation information cutoff")
    _require(available <= retrieved <= reviewed, "source retrieval must follow availability and precede actual review")
    relative = Path(source["source_relative_path"])
    _require(not relative.is_absolute() and ".." not in relative.parts, "source path escapes evidence_root")
    root = evidence_root.resolve(strict=True)
    path = (root / relative).resolve(strict=True)
    _require(path.is_relative_to(root) and path.is_file(), "source path escapes evidence_root or is not a file")
    _require(hashlib.sha256(path.read_bytes()).hexdigest() == source["source_sha256"], "archived source hash mismatch")


def _review(review: Any, cutoff, registered, now, evidence_root: Path, *, ordinal: bool = True) -> int | None:
    _require(isinstance(review, dict), "rating review object required")
    if ordinal:
        _require(type(review.get("value")) is int and 0 <= review["value"] <= 4,
                 "rating must be integer 0..4; unknown/null blocks")
    _text(review.get("rationale"), "rationale")
    _text(review.get("reviewer"), "reviewer")
    reviewed = _time(review.get("reviewed_at"), "reviewed_at")
    _require(registered < reviewed <= now, "actual reviewed_at must be after parameter registration and no later than now")
    sources = review.get("sources")
    _require(isinstance(sources, list) and bool(sources), "at least one source required")
    for source in sources:
        _source(source, cutoff, reviewed, evidence_root)
    return review["value"] if ordinal else None


def validate_ratings(sidecar: Any, rows: list[dict[str, Any]], *, dataset_sha256: str,
                     parameter_sha256: str, registration_sha256: str, registered_at,
                     now, evidence_root: Path) -> tuple[dict[str, Any], list[str]]:
    """Accumulate independent observation errors; one invalid record blocks every family."""
    errors: list[str] = []
    scored: dict[str, Any] = {}
    if not isinstance(sidecar, dict):
        return scored, ["missing or malformed ratings sidecar"]
    if sidecar.get("template_status") == "incomplete_inadmissible":
        errors.append("incomplete rating template is inadmissible")
    expected = {"schema_version": "ma-diligence-ratings-v1", "dataset_sha256": dataset_sha256,
                "parameter_sha256": parameter_sha256, "registration_sha256": registration_sha256, "rubric_version": VERSION}
    for key, value in expected.items():
        if sidecar.get(key) != value:
            errors.append(f"ratings {key} binding mismatch")
    records = sidecar.get("records")
    if not isinstance(records, list):
        return scored, errors + ["ratings records list required"]
    identities = {row["observation_id"]: row for row in rows}
    seen: set[str] = set()
    batches: set[str] = set()
    for index, record in enumerate(records):
        try:
            _require(isinstance(record, dict), "record object required")
            _require(set(record) == {"observation_id", "rating_batch_id", "rubric_version", "outcome_knowledge", "ratings", "candidate_buyer_universe", "buyer_reviews"}, "exact rating record fields required; caller-selected/eventual buyer forbidden")
            identity = _text(record.get("observation_id"), "observation_id")
            _require(identity in identities, "extra observation identity")
            _require(identity not in seen, "duplicate observation identity")
            seen.add(identity)
            batches.add(_text(record.get("rating_batch_id"), "rating_batch_id"))
            _require(record.get("rubric_version") == VERSION, "record rubric mismatch")
            _require(record.get("outcome_knowledge") in ("exposed", "masked_packet", "not_known"), "outcome knowledge disclosure required")
            cutoff = identities[identity]["cutoff"]
            ratings = record.get("ratings")
            _require(isinstance(ratings, dict) and set(ratings) == set(NON_BUYER_FIELDS), "exact six non-buyer rating fields required")
            values = {key: _review(value, cutoff, registered_at, now, evidence_root) for key, value in ratings.items()}
            universe = record.get("candidate_buyer_universe")
            _require(isinstance(universe, dict), "source-bound candidate buyer universe required")
            _review(universe, cutoff, registered_at, now, evidence_root, ordinal=False)
            candidates = universe.get("buyer_ids")
            _require(isinstance(candidates, list) and bool(candidates) and all(isinstance(c, str) and c.strip() for c in candidates)
                     and len(set(candidates)) == len(candidates), "nonempty unique candidate buyer_ids required")
            _require(universe.get("completeness_attested") is True, "dated candidate universe completeness must be externally attested")
            reviews = record.get("buyer_reviews")
            _require(isinstance(reviews, dict) and set(reviews) == set(candidates), "every declared buyer must be reviewed; buyer subset forbidden")
            buyer_values = {}
            for buyer, review in reviews.items():
                _require(isinstance(review, dict) and set(review) == {"buyer_fit", "buyer_capacity"}, "exact buyer fit/capacity fields required")
                buyer_values[buyer] = {key: _review(value, cutoff, registered_at, now, evidence_root) for key, value in review.items()}
            selected = min(candidates, key=lambda buyer: (-(2 * buyer_values[buyer]["buyer_fit"] + buyer_values[buyer]["buyer_capacity"]), buyer))
            all_reviews = list(ratings.values()) + [universe] + [review for buyer in reviews.values() for review in buyer.values()]
            source_through = max(_time(source["available_at"], "available_at") for review in all_reviews for source in review["sources"])
            review_through = max(_time(review["reviewed_at"], "reviewed_at") for review in all_reviews)
            scored[identity] = {"values": {**values, **buyer_values[selected]}, "selected_buyer": selected,
                                "selection_reason": "maximum .20*buyer_fit+.10*buyer_capacity; buyer_id ascending breaks ties",
                                "record_sha256": _digest(record), "rating_source_max_available_at": source_through.isoformat(),
                                "actual_rating_reviewed_through": review_through.isoformat()}
        except (ValueError, OSError, TypeError) as exc:
            errors.append(f"ratings record {index}: {exc}")
    missing = sorted(set(identities) - seen)
    if missing:
        errors.append(f"missing rating observations: {', '.join(missing)}")
    if len(batches) != 1:
        errors.append("all records must use one nonempty rating_batch_id")
    return scored, errors


def score(values: dict[str, int], config: dict[str, Any], family: str = "full") -> float:
    """Ablations retain frozen full-model weights without renormalization or tuning."""
    validate_parameters(config)
    _require(family in ("full", "science_only", "buyer_only"), "unknown score family")
    _require(set(values) == set(POSITIVE_FIELDS) | {"execution_risk"}, "exact score field set required")
    _require(all(type(value) is int and 0 <= value <= 4 for value in values.values()), "integer ordinal scores required")
    fields = POSITIVE_FIELDS if family == "full" else SCIENCE_FIELDS if family == "science_only" else BUYER_FIELDS
    # Decimal JSON weights become exact rational values; convert only the final score.
    subtotal = sum((Fraction(str(config["weights"][key])) * values[key] / 4 for key in fields), Fraction(0))
    penalty = Fraction(str(config["execution_risk_penalty"])) * values["execution_risk"] / 4 if family == "full" else Fraction(0)
    return float(100 * min(Fraction(1), max(Fraction(0), subtotal - penalty)))
