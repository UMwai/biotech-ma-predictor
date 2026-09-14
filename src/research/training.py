"""Strict historical logistic baseline fitting; no heuristic/proxy label promotion."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import tempfile
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.research.metrics import RankedObservation, evaluate_rare_event_ranking
from src.research.validation import (
    RECORDED_LABEL_TIMING, PanelValidationError, calibration_bins, evaluate_panel, validate_panel,
)

DATA_SCHEMA = "historical-company-features-v1"
MODEL_SCHEMA = "historical-logistic-baseline-v1"


class TrainingBlocked(ValueError):
    """The supplied evidence cannot support the requested fit or application."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrainingBlocked(message)


def _time(value: Any, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrainingBlocked(f"{name}: timezone-aware ISO timestamp required") from exc
    _require(parsed.tzinfo is not None, f"{name}: timezone required")
    return parsed.astimezone(timezone.utc)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _feature_contract(data: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    names = data.get("feature_names")
    _require(isinstance(names, list) and bool(names)
             and all(isinstance(name, str) and name.strip() for name in names),
             "feature_names must be a nonempty list of names")
    _require(len(set(names)) == len(names), "duplicate feature names")
    units = data.get("feature_units")
    _require(isinstance(units, dict) and set(units) == set(names)
             and all(isinstance(unit, str) and unit.strip() for unit in units.values()),
             "feature_units must specify a nonempty unit for every feature")
    from src.research.market_contract import validate_market_feature_contract
    try:
        validate_market_feature_contract(data, names)
    except ValueError as exc:
        raise TrainingBlocked(str(exc)) from exc
    return names, units


def _features(row: dict[str, Any], names: list[str]) -> list[float | None]:
    features = row.get("features")
    _require(isinstance(features, dict) and set(features) == set(names),
             "every row must explicitly supply each feature; use null for missing values")
    values = []
    for name in names:
        value = features[name]
        _require(value is None or (isinstance(value, (int, float)) and not isinstance(value, bool)
                                  and math.isfinite(value)), f"feature {name}: finite number or null required")
        values.append(None if value is None else float(value))
    return values


@dataclass(frozen=True)
class TrainingConfig:
    test_start_year: int
    min_train_positive_events: int = 5
    min_train_negative_companies: int = 20
    min_test_years: int = 2
    regularization_c: float = 1.0
    max_iter: int = 2000

    def validate(self) -> None:
        _require(isinstance(self.test_start_year, int) and not isinstance(self.test_start_year, bool)
                 and 1900 <= self.test_start_year <= 9998, "valid test_start_year is required")
        for field, floor in (("min_train_positive_events", 5), ("min_train_negative_companies", 20), ("min_test_years", 2)):
            value = getattr(self, field)
            _require(isinstance(value, int) and not isinstance(value, bool) and value >= floor,
                     f"{field} must be at least {floor}; evidence floors cannot be relaxed")
        _require(isinstance(self.regularization_c, (int, float)) and not isinstance(self.regularization_c, bool)
                 and math.isfinite(self.regularization_c) and self.regularization_c > 0,
                 "regularization_c must be finite and positive")
        _require(isinstance(self.max_iter, int) and self.max_iter > 0, "max_iter must be positive")


def validate_training_data(data: Any, *, now: datetime | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reuse reviewed-label/membership/feature chronology checks without publishing predictions."""
    _require(isinstance(data, dict) and data.get("schema_version") == DATA_SCHEMA,
             f"schema_version must be {DATA_SCHEMA}; candidate ledgers and annual proxies cannot be fitted")
    names, _ = _feature_contract(data)
    raw_rows = data.get("observations")
    _require(isinstance(raw_rows, list) and bool(raw_rows), "no eligible historical observations supplied")
    current_time = _time(now or datetime.now(timezone.utc), "now")
    adapters = []
    for index, row in enumerate(raw_rows):
        _require(isinstance(row, dict), f"observations[{index}]: object required")
        _features(row, names)
        # This private adapter only reuses the shared structural evidence checks.
        # It is never saved or represented as a trained prediction record.
        adapted = copy.deepcopy(row)
        adapted.update({"training_cutoff_at": row.get("information_cutoff_at"),
                        "training_outcomes_available_through": row.get("information_cutoff_at"),
                        "split_method": "expanding_window", "fold_id": f"input-check-{index}",
                        "model_version": "pre_fit_input_contract_check",
                        "training_dataset_sha256": "0" * 64,
                        "feature_snapshot_sha256": _digest(row["features"]),
                        "prediction_generated_at": current_time.isoformat(),
                        "prediction_sealed_at": current_time.isoformat(), "score": 0, "probability": None})
        adapters.append(adapted)
    try:
        normalized = validate_panel({"schema_version": "sealed-company-predictions-v1",
                                     "evaluation_mode": "retrospective_out_of_time", "data_as_of": data.get("data_as_of"),
                                     "label_timing_policy": data.get("label_timing_policy", RECORDED_LABEL_TIMING),
                                     "historical_sampling_frame": data.get("historical_sampling_frame"),
                                     "observations": adapters}, now=current_time)
    except PanelValidationError as exc:
        raise TrainingBlocked(str(exc)) from exc
    keyed = {(int(row["cik"]), _time(row["observation_at"], "observation_at").date()): row for row in raw_rows}
    ordered = [keyed[(row["cik"], row["observation_at"].date())] for row in normalized]
    return ordered, normalized


def _support(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {"company_observations": len(rows),
            "positive_observations": sum(row["label"] for row in rows),
            "distinct_positive_events": len({row["event_id"] for row in rows if row["label"]}),
            "distinct_negative_companies": len({row["cik"] for row in rows if not row["label"]})}


def _support_gate(rows: list[dict[str, Any]], config: TrainingConfig, fold: str) -> None:
    support = _support(rows)
    _require(support["distinct_positive_events"] >= config.min_train_positive_events,
             f"{fold}: insufficient distinct positive events ({support['distinct_positive_events']}/{config.min_train_positive_events})")
    _require(support["distinct_negative_companies"] >= config.min_train_negative_companies,
             f"{fold}: insufficient distinct negative companies ({support['distinct_negative_companies']}/{config.min_train_negative_companies})")


def _fit(raw_rows: list[dict[str, Any]], normalized: list[dict[str, Any]], names: list[str], config: TrainingConfig) -> dict[str, Any]:
    try:
        import numpy as np
        import sklearn
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise TrainingBlocked("optional modeling dependencies unavailable; install requirements-model.txt to fit this baseline") from exc
    matrix = np.array([[np.nan if value is None else value for value in _features(row, names)] for row in raw_rows], dtype=float)
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    imputed = imputer.fit_transform(matrix)
    design = np.column_stack([imputed, np.isnan(matrix).astype(float)])
    scaler = StandardScaler()
    scaled = scaler.fit_transform(design)
    model = LogisticRegression(C=config.regularization_c, solver="lbfgs", max_iter=config.max_iter,
                               tol=1e-8, random_state=0)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(scaled, np.array([int(row["label"]) for row in normalized]))
    except ConvergenceWarning as exc:
        raise TrainingBlocked("logistic optimization did not converge; no model published") from exc
    return {"model_type": "L2_regularized_logistic_regression", "sklearn_version": sklearn.__version__,
            "numpy_version": np.__version__, "feature_medians": imputer.statistics_.tolist(),
            "transform_order": "median_imputed_features_then_missing_indicator_for_every_feature",
            "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
            "coefficients": model.coef_[0].tolist(), "intercept": float(model.intercept_[0]),
            "iterations": int(model.n_iter_[0]), "all_missing_train_feature_fill": 0.0,
            "training_feature_observed_counts": np.sum(~np.isnan(matrix), axis=0).tolist(),
            "regularization_c": config.regularization_c, "class_weight": None}


def decision_score(model: dict[str, Any], features: dict[str, Any]) -> float:
    """Apply portable JSON transformations without importing sklearn or numpy."""
    names = model["feature_names"]
    values = _features({"features": features}, names)
    design = [model["feature_medians"][index] if value is None else value for index, value in enumerate(values)]
    design += [float(value is None) for value in values]
    return model["intercept"] + sum(coefficient * (value - mean) / scale
                                     for coefficient, value, mean, scale in zip(model["coefficients"], design, model["scaler_mean"], model["scaler_scale"], strict=True))


def _sigmoid(score: float) -> float:
    return 1 / (1 + math.exp(-score)) if score >= 0 else math.exp(score) / (1 + math.exp(score))


def _training_base_rate_comparator(fit_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]],
                                   cutoff: datetime, training_hash: str) -> dict[str, Any]:
    """Estimate a constant from the actual purged training partition only."""
    probability = sum(row["label"] for row in fit_rows) / len(fit_rows)
    observations = [RankedObservation(row["observation_id"], probability, row["label"], probability)
                    for row in test_rows]
    metrics = evaluate_rare_event_ranking(observations, cutoffs=())
    metrics.update({"top_k": None, "ranking_status": "constant_probability_has_no_ranking_discrimination",
                    "sample_unit": "company_observation", "metric_semantics": "same_holdout_row_diagnostics",
                    "calibration_bins": calibration_bins(observations)})
    return {"training_source": "actual_purged_fold_training_partition", "probability": probability,
            "probability_semantics": "mature_training_company_observation_event_rate; not a unique-deal rate",
            "training_cutoff_at": cutoff.isoformat(), "training_dataset_sha256": training_hash,
            "training_observations": len(fit_rows), "training_support": _support(fit_rows),
            "training_outcomes_available_through": max(row["label_training_available_at"] for row in fit_rows).isoformat(),
            "actual_label_assembly_available_through": max(row["label_available_at"] for row in fit_rows).isoformat(),
            "training_observation_ids": [row["observation_id"] for row in fit_rows],
            "evaluated_observation_ids": [row["observation_id"] for row in test_rows], "metrics": metrics}


def train_baseline(data: Any, config: TrainingConfig, *, now: datetime | None = None) -> dict[str, Any]:
    """Fit every declared annual holdout plus a final present-use research model."""
    config.validate()
    current_time = _time(now or datetime.now(timezone.utc), "now")
    raw, rows = validate_training_data(data, now=current_time)
    names, units = _feature_contract(data)
    test_years = sorted({row["observation_at"].year for row in rows if row["observation_at"].year >= config.test_start_year})
    _require(len(test_years) >= config.min_test_years,
             f"insufficient chronological test years ({len(test_years)}/{config.min_test_years})")
    _require(test_years[0] == config.test_start_year, "test_start_year has no observations")
    _require(test_years == list(range(test_years[0], test_years[-1] + 1)), "missing year within declared annual test period")
    plans = []
    for year in test_years:
        test_indices = [index for index, row in enumerate(rows) if row["observation_at"].year == year]
        cutoff = min(rows[index]["cutoff"] for index in test_indices)
        prior = [index for index, row in enumerate(rows) if row["observation_at"].year < year]
        train_indices = [index for index in prior if rows[index]["horizon_end"] <= cutoff
                         and rows[index]["label_training_available_at"] <= cutoff]
        train_rows = [rows[index] for index in train_indices]
        _support_gate(train_rows, config, f"fold-{year}")
        plans.append((year, test_indices, train_indices, cutoff, len(prior) - len(train_indices)))
    predictions, folds = [], []
    for year, test_indices, train_indices, cutoff, purged in plans:
        fit_raw, fit_rows = [raw[index] for index in train_indices], [rows[index] for index in train_indices]
        model = {"feature_names": names, **_fit(fit_raw, fit_rows, names, config)}
        if "market_data_contract" in data:
            model["market_data_contract"] = copy.deepcopy(data["market_data_contract"])
        training_hash = _digest(fit_raw)
        model_hash = _digest(model)
        latest_training_label = max(row["label_training_available_at"] for row in fit_rows)
        produced_at = _time(now or datetime.now(timezone.utc), "now")
        comparator = _training_base_rate_comparator(fit_rows, [rows[index] for index in test_indices], cutoff, training_hash)
        folds.append({"fold_id": f"annual-{year}", "test_year": year, "training_cutoff_at": cutoff.isoformat(),
                      "label_timing_policy": data.get("label_timing_policy", RECORDED_LABEL_TIMING),
                      "training_outcomes_available_through": latest_training_label.isoformat(),
                      "actual_label_assembly_available_through": max(row["label_available_at"] for row in fit_rows).isoformat(),
                      "training_support": _support(fit_rows), "training_dataset_sha256": training_hash,
                      "purged_prior_observations": purged, "test_observations": len(test_indices),
                      "training_observation_ids": [row["observation_id"] for row in fit_rows],
                      "model_sha256": model_hash, "model": model, "training_base_rate_comparator": comparator})
        for index in test_indices:
            score = decision_score(model, raw[index]["features"])
            predicted = copy.deepcopy(raw[index])
            predicted.pop("features", None)
            predicted.update({"training_cutoff_at": cutoff.isoformat(),
                              "training_outcomes_available_through": latest_training_label.isoformat(),
                              "split_method": "expanding_window", "fold_id": f"annual-{year}",
                              "model_version": f"{MODEL_SCHEMA}:{model_hash}", "training_dataset_sha256": training_hash,
                              "feature_snapshot_sha256": _digest(raw[index]["features"]),
                              "prediction_generated_at": produced_at.isoformat(), "prediction_sealed_at": produced_at.isoformat(),
                              "score": score, "probability": _sigmoid(score),
                              "probability_semantics": "raw_logistic_estimate_for_retrospective_calibration_evaluation_only"})
            predictions.append(predicted)
    prediction_panel = {"schema_version": "sealed-company-predictions-v1", "evaluation_mode": "retrospective_out_of_time",
                        "label_timing_policy": data.get("label_timing_policy", RECORDED_LABEL_TIMING),
                        "historical_sampling_frame": copy.deepcopy(data.get("historical_sampling_frame")),
                        "data_as_of": data["data_as_of"], "observations": predictions}
    evaluation = evaluate_panel(prediction_panel, input_sha256=_digest(prediction_panel),
                                now=_time(now or datetime.now(timezone.utc), "now"))
    for fold in folds:
        annual = evaluation["by_year"][str(fold["test_year"])]
        annual["heldout_history_base_rate_comparator"] = annual.pop("past_only_base_rate_comparator")
        annual["past_only_base_rate_comparator"] = fold["training_base_rate_comparator"]
    evaluation["training_comparator_semantics"] = "Actual purged training rows estimate each annual constant; heldout-history-only estimates are retained separately."
    final_fit = _fit(raw, rows, names, config)
    produced_at = _time(now or datetime.now(timezone.utc), "now")
    final_model = {"schema_version": MODEL_SCHEMA, "feature_names": names, "feature_units": units,
                   "generated_at": produced_at.isoformat(), "training_cutoff_at": data["data_as_of"],
                   "training_dataset_sha256": _digest(raw), "training_support": _support(rows),
                   "config": asdict(config), "calibration_status": "unvalidated", "user_facing_probability": None,
                   "validated_predictive_edge": False, **final_fit}
    if "market_data_contract" in data:
        final_model["market_data_contract"] = copy.deepcopy(data["market_data_contract"])
    return {"schema_version": "baseline-training-run-v2", "dataset_sha256": _digest(data),
            "label_timing_policy": data.get("label_timing_policy", RECORDED_LABEL_TIMING),
            "config": asdict(config), "status": "retrospective_baseline_fitted_not_promoted",
            "validated_predictive_edge": False, "calibration_status": "unvalidated", "model_training_performed": True,
            "synthetic_test_fixture": data.get("synthetic_test_fixture") is True,
            "final_model": final_model, "folds": folds, "prediction_panel": prediction_panel, "evaluation": evaluation}


def _validate_portable_model(model: Any) -> None:
    _require(isinstance(model, dict) and model.get("schema_version") == MODEL_SCHEMA, "unsupported portable model schema")
    names, _ = _feature_contract(model)
    for field, size in (("feature_medians", len(names)), ("scaler_mean", 2 * len(names)),
                        ("scaler_scale", 2 * len(names)), ("coefficients", 2 * len(names))):
        values = model.get(field)
        _require(isinstance(values, list) and len(values) == size
                 and all(isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) for value in values),
                 f"model {field}: invalid transformation parameters")
    _require(all(value > 0 for value in model["scaler_scale"]), "model scales must be positive")
    _require(isinstance(model.get("intercept"), (int, float)) and math.isfinite(model["intercept"]), "invalid model intercept")
    _require(model.get("transform_order") == "median_imputed_features_then_missing_indicator_for_every_feature", "unsupported model transform")


def apply_baseline(model: Any, data: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Score explicit current features for research; all acquisition probabilities stay null."""
    _validate_portable_model(model)
    _require(isinstance(data, dict) and data.get("schema_version") == "current-company-features-v1", "current-company-features-v1 input required")
    names, units = _feature_contract(data)
    _require(names == model["feature_names"] and units == model["feature_units"], "feature names/order or units differ from fitted model")
    _require(data.get("market_data_contract") == model.get("market_data_contract"),
             "market source/feed/derivation contract differs from fitted model")
    current_time = _time(now or datetime.now(timezone.utc), "now")
    model_created = _time(model.get("generated_at"), "model.generated_at")
    training_cutoff = _time(model.get("training_cutoff_at"), "model.training_cutoff_at")
    observations = data.get("observations")
    _require(isinstance(observations, list) and bool(observations), "no current feature observations supplied")
    results, identities = [], set()
    for row in observations:
        _require(isinstance(row, dict), "current observation must be an object")
        raw_cik = row.get("cik")
        _require(not isinstance(raw_cik, bool) and str(raw_cik).isdigit() and int(raw_cik) > 0, "positive CIK required")
        cik = int(raw_cik)
        observation = _time(row.get("observation_at"), "observation_at")
        cutoff = _time(row.get("information_cutoff_at"), "information_cutoff_at")
        availability = _time(row.get("feature_max_available_at"), "feature_max_available_at")
        _require(model_created <= observation <= current_time and training_cutoff <= cutoff < observation
                 and availability <= cutoff, "current scoring chronology violates model/data cutoff")
        identity = (cik, observation.date())
        _require(identity not in identities, "duplicate current CIK/observation date")
        identities.add(identity)
        _features(row, names)
        eligible = row.get("risk_set_eligible") is True and not row.get("risk_set_exclusion_reason")
        score = decision_score(model, row["features"]) if eligible else None
        _require(score is None or math.isfinite(score), "current decision score is nonfinite")
        results.append({"cik": cik, "observation_at": observation.isoformat(), "risk_set_eligible": eligible,
                        "risk_set_exclusion_reason": None if eligible else row.get("risk_set_exclusion_reason") or "eligibility unconfirmed",
                        "score": score, "score_semantics": "uncalibrated_logistic_decision_score_for_research",
                        "deal_probability_12mo": None, "probability": None, "calibration_status": "unvalidated"})
    return {"schema_version": "baseline-current-research-scores-v1", "model_sha256": _digest(model),
            "input_sha256": _digest(data), "validated_predictive_edge": False, "observations": results}


def write_immutable_json(value: Any, output_dir: Path, prefix: str) -> Path:
    encoded = _canonical(value)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{prefix}-{hashlib.sha256(encoded).hexdigest()}.json"
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".baseline-", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            _require(path.read_bytes() == encoded, f"immutable artifact changed: {path}")
    finally:
        temporary.unlink(missing_ok=True)
    return path


def train_from_file(path: Path, output_dir: Path, config: TrainingConfig) -> dict[str, str]:
    _require(path.is_file(), f"missing eligible historical feature dataset: {path}")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TrainingBlocked("historical feature dataset is not valid JSON") from exc
    run = train_baseline(data, config)
    run["input_file_sha256"] = hashlib.sha256(raw).hexdigest()
    artifacts = {name: str(write_immutable_json(run[name], output_dir, name.replace("_", "-")))
                 for name in ("final_model", "prediction_panel", "evaluation")}
    artifacts["training_report"] = str(write_immutable_json(run, output_dir, "training-report"))
    return artifacts
