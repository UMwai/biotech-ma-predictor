"""Immutable, hindsight-disclosed retrospective M&A experiments with complete gates."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.research.ma_diligence import (BUYER_FIELDS, FINANCIAL_FEATURES, FINANCIAL_UNITS,
    NON_BUYER_FIELDS, SCIENCE_FIELDS, VERSION, score, validate_parameters, validate_ratings)
from src.research.metrics import RankedObservation, evaluate_rare_event_ranking
from src.research.training import (TrainingBlocked, TrainingConfig, _canonical, _digest,
    _require, _support, _time, train_baseline, validate_training_data, write_immutable_json)
from src.research.validation import evaluate_panel, validate_panel

DISCLOSURES = {"outcome_exposed": True, "validated_predictive_edge": False,
               "return_backtest_performed": False, "independent_confirmation": False}
CODE_FILES = ("src/research/training.py", "src/research/validation.py", "src/research/metrics.py",
              "src/research/ma_diligence.py", "src/research/ma_experiment.py", "scripts/run_ma_experiment.py")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register(parameter_path: Path, output_dir: Path, *, now: datetime | None = None) -> Path:
    parameter_bytes = parameter_path.read_bytes()
    config = validate_parameters(json.loads(parameter_bytes))
    receipt = {"schema_version": "ma-parameter-registration-v1", "config": config,
               "parameter_sha256": hashlib.sha256(parameter_bytes).hexdigest(), "parameter_raw_json": parameter_bytes.decode("utf-8"),
               "canonical_config_sha256": _digest(config),
               "registered_at": _time(now or datetime.now(timezone.utc), "now").isoformat(),
               "outcome_exposure": "retrospective_development_parameters_after_outcome_inspection",
               **DISCLOSURES}
    return write_immutable_json(receipt, output_dir, "ma-registration")


def load_registration(path: Path, *, now: datetime | None = None, snapshot: bytes | None = None) -> dict[str, Any]:
    """Validate exactly one byte snapshot, including its content-addressed path."""
    raw = path.read_bytes() if snapshot is None else snapshot
    receipt = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    _require(path.name == f"ma-registration-{digest}.json" and raw == _canonical(receipt), "registration content digest/filename mismatch")
    _require(isinstance(receipt, dict) and receipt.get("schema_version") == "ma-parameter-registration-v1", "registration schema mismatch")
    validate_parameters(receipt.get("config"))
    _require(receipt.get("canonical_config_sha256") == _digest(receipt["config"]), "embedded parameter canonical digest mismatch")
    raw_hash = receipt.get("parameter_sha256")
    _require(isinstance(raw_hash, str) and len(raw_hash) == 64 and all(c in "0123456789abcdef" for c in raw_hash), "embedded raw parameter digest required")
    parameter_raw = receipt.get("parameter_raw_json")
    _require(isinstance(parameter_raw, str) and hashlib.sha256(parameter_raw.encode()).hexdigest() == raw_hash
             and json.loads(parameter_raw.encode()) == receipt["config"], "embedded raw parameter digest/content mismatch")
    _require(receipt.get("outcome_exposure") == "retrospective_development_parameters_after_outcome_inspection"
             and all(receipt.get(key) == value for key, value in DISCLOSURES.items()), "registration outcome exposure disclosure mismatch")
    _require(_time(receipt.get("registered_at"), "registered_at") <= _time(now or datetime.now(timezone.utc), "now"), "future parameter registration")
    return receipt


def rating_template(dataset_path: Path, registration_path: Path, output_dir: Path, *, now: datetime | None = None) -> Path:
    registration_bytes = registration_path.read_bytes()
    receipt = load_registration(registration_path, now=now, snapshot=registration_bytes)
    dataset_bytes = dataset_path.read_bytes()
    _, rows = validate_training_data(json.loads(dataset_bytes), now=now)
    empty_review = {"value": None, "rationale": "", "reviewer": "", "reviewed_at": None, "sources": []}
    template = {"schema_version": "ma-diligence-ratings-v1", "template_status": "incomplete_inadmissible",
                "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(), "parameter_sha256": receipt["parameter_sha256"],
                "registration_sha256": hashlib.sha256(registration_bytes).hexdigest(), "rubric_version": VERSION,
                "records": [{"observation_id": row["observation_id"], "rating_batch_id": None,
                             "rubric_version": VERSION, "outcome_knowledge": None,
                             "ratings": {key: copy.deepcopy(empty_review) for key in NON_BUYER_FIELDS},
                             "candidate_buyer_universe": {"buyer_ids": [], "completeness_attested": False,
                                 "rationale": "", "reviewer": "", "reviewed_at": None, "sources": []},
                             "buyer_reviews": {}} for row in rows]}
    return write_immutable_json(template, output_dir, "ma-ratings-template")


def readiness(data: Any, config: dict[str, Any], *, now: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Report all fold floors and distinct missing-input gaps before invoking a fitter."""
    errors: list[str] = []
    financial_gaps = []
    if isinstance(data, dict):
        names, units = data.get("feature_names", []), data.get("feature_units", {})
        for name in FINANCIAL_FEATURES:
            if name not in names or units.get(name) != FINANCIAL_UNITS[name]:
                financial_gaps.append(f"financial feature/units missing or unsupported: {name} ({FINANCIAL_UNITS[name]})")
        for index, raw in enumerate(data.get("observations", []) if isinstance(data.get("observations"), list) else []):
            if isinstance(raw, dict):
                for name in FINANCIAL_FEATURES:
                    if not isinstance(raw.get("features"), dict) or name not in raw["features"]:
                        financial_gaps.append(f"observation {index}: missing financial field {name}; full matched cohort required")
    errors.extend(financial_gaps)
    rows = []
    try:
        _, rows = validate_training_data(data, now=now)
        if any(row.get("horizon_days") != config["horizon_days"] for row in data["observations"]):
            errors.append("all observation horizons must equal registered 365 days")
    except Exception as exc:  # Retain malformed dependency failures as reviewable attempts.
        errors.append(f"dataset provenance/chronology: {exc}")
    dependencies = {name: importlib.util.find_spec(name) is not None for name in ("numpy", "sklearn")}
    for name, available in dependencies.items():
        if not available:
            errors.append(f"optional modeling dependency unavailable: {name}")
    training_config = TrainingConfig(config["test_start_year"], regularization_c=config["regularization_c"])
    training_config.validate()
    years = sorted({row["observation_at"].year for row in rows if row["observation_at"].year >= training_config.test_start_year})
    if len(years) < training_config.min_test_years:
        errors.append(f"insufficient chronological test years ({len(years)}/{training_config.min_test_years})")
    if not years or years[0] != training_config.test_start_year:
        errors.append("test_start_year has no observations")
    if years and years != list(range(years[0], years[-1] + 1)):
        errors.append("missing year within declared annual test period")
    folds = []
    for year in years:
        test = [row for row in rows if row["observation_at"].year == year]
        cutoff = min(row["cutoff"] for row in test)
        prior = [row for row in rows if row["observation_at"].year < year]
        mature = [row for row in prior if row["horizon_end"] <= cutoff and row["label_training_available_at"] <= cutoff]
        support = _support(mature)
        fold_errors = []
        for key, floor in (("distinct_positive_events", 5), ("distinct_negative_companies", 20)):
            if support[key] < floor:
                fold_errors.append(f"fold-{year}: insufficient {key} ({support[key]}/{floor})")
        if len({row["label"] for row in mature}) < 2:
            fold_errors.append(f"fold-{year}: both training classes required")
        folds.append({"fold_id": f"annual-{year}", "test_year": year, "training_cutoff_at": cutoff.isoformat(),
                      "training_support": support, "purged_prior_observations": len(prior) - len(mature),
                      "training_observation_ids": [row["observation_id"] for row in mature],
                      "test_observation_ids": [row["observation_id"] for row in test],
                      "maturity_policy": "horizon_end and effective label_training_available_at <= earliest heldout information cutoff",
                      "errors": fold_errors})
        errors.extend(fold_errors)
    return {"ready": not errors, "errors": errors, "financial_gaps": financial_gaps,
            "observation_count": len(rows), "total_support": _support(rows), "planned_annual_folds": folds,
            "modeling_dependencies": dependencies, "evidence_floors": {"distinct_positive_events": 5,
            "distinct_negative_companies": 20, "consecutive_test_years": 2}}, rows


def _evaluate(panel: dict[str, Any], baseline: dict[str, Any], now: datetime) -> dict[str, Any]:
    evaluation = evaluate_panel(panel, input_sha256=_digest(panel), now=now)
    normalized = validate_panel(panel, now=now)
    cohorts = {}
    for row in normalized:
        cohorts.setdefault(row["observation_at"].date().isoformat(), []).append(row)
    primary = {}
    for day, rows in sorted(cohorts.items()):
        metrics = evaluate_rare_event_ranking([RankedObservation(row["observation_id"], row["score"], row["label"], row["probability"]) for row in rows], cutoffs=(5,))
        if not metrics["positives"]:
            metrics["top_k"]["5"]["recall"] = None
            metrics["top_k"]["5"]["lift_over_base_rate"] = None
        primary[day] = metrics
    supported = [metric["top_k"]["5"]["lift_over_base_rate"] for metric in primary.values() if metric["positives"]]
    evaluation["primary_metric"] = {"name": "mean_cohort_lift_at_5", "value": sum(supported) / len(supported) if supported else None,
        "weighting": "equal_weight_per_observation_date", "positive_supported_cohorts": len(supported),
        "cohort_count": len(primary), "undefined_policy": "omit cohorts without positive events and report their support",
        "tie_policy": "observation_id_ascending", "per_cohort": primary}
    for fold in baseline["folds"]:
        annual = evaluation["by_year"][str(fold["test_year"])]
        annual["heldout_history_base_rate_comparator"] = annual.pop("past_only_base_rate_comparator")
        annual["past_only_base_rate_comparator"] = copy.deepcopy(fold["training_base_rate_comparator"])
    evaluation.update(DISCLOSURES)
    evaluation["training_comparator_semantics"] = "actual_purged_fold_training_partition; heldout-history diagnostic retained separately"
    evaluation["other_metrics_status"] = "descriptive_only; logistic probabilities uncalibrated"
    return evaluation


def run_experiment(dataset_path: Path, registration_path: Path, output_dir: Path, *, ratings_path: Path | None = None,
                   evidence_root: Path | None = None, now: datetime | None = None) -> tuple[dict[str, Any], Path]:
    current = _time(now or datetime.now(timezone.utc), "now")
    root = Path(__file__).resolve().parents[2]
    report = {"schema_version": "ma-experiment-v1", "created_at": current.isoformat(), **DISCLOSURES,
              "status": "blocked", "model_training_performed": False, "weighted_model_evaluated": False,
              "predictions": None, "metrics": None, "artifacts": None, "readiness": {"ready": False, "errors": []},
              "hashes": {"dataset_sha256": None, "ratings_sha256": None, "registration_sha256": None,
                         "parameter_sha256": None, "code": {name: file_hash(root / name) for name in CODE_FILES}},
              "local_input_dependency": str(dataset_path.resolve()), "evidence_root": str((evidence_root or dataset_path.parent).resolve())}
    # Independently read each dependency so a malformed registration cannot hide missing inputs.
    loaded = {}
    for name, path in (("dataset", dataset_path), ("registration", registration_path), ("ratings", ratings_path)):
        if path is None:
            report["readiness"]["errors"].append(f"missing {name} sidecar")
            continue
        try:
            dependency_bytes = path.read_bytes()
            report["hashes"][f"{name}_sha256"] = hashlib.sha256(dependency_bytes).hexdigest()
            loaded[name] = load_registration(path, now=current, snapshot=dependency_bytes) if name == "registration" else json.loads(dependency_bytes)
        except Exception as exc:  # Retain malformed dependency failures as reviewable attempts.
            report["readiness"]["errors"].append(f"{name}: {exc}")
    if "registration" in loaded and "dataset" in loaded:
        registration = loaded["registration"]
        config = registration["config"]
        report["hashes"]["parameter_sha256"] = registration["parameter_sha256"]
        try:
            ready, rows = readiness(loaded["dataset"], config, now=current)
            prior_errors = report["readiness"]["errors"]
            report["readiness"] = ready
            report["readiness"]["errors"] = prior_errors + ready["errors"]
            scored, rating_errors = validate_ratings(loaded.get("ratings"), rows,
                dataset_sha256=report["hashes"]["dataset_sha256"], parameter_sha256=registration["parameter_sha256"],
                registration_sha256=report["hashes"]["registration_sha256"], registered_at=_time(registration["registered_at"], "registered_at"),
                now=current, evidence_root=evidence_root or dataset_path.parent)
            report["readiness"]["errors"].extend(rating_errors)
            report["readiness"]["ready"] = not report["readiness"]["errors"]
            if report["readiness"]["ready"]:
                data = copy.deepcopy(loaded["dataset"])
                data.pop("market_data_contract", None)  # All market features are excluded from this comparator.
                data["feature_names"] = list(FINANCIAL_FEATURES)
                data["feature_units"] = {key: data["feature_units"][key] for key in FINANCIAL_FEATURES}
                for row in data["observations"]:
                    row["features"] = {key: row["features"][key] for key in FINANCIAL_FEATURES}
                report["comparator_fit_attempted"] = True
                baseline = train_baseline(data, TrainingConfig(config["test_start_year"], regularization_c=config["regularization_c"]), now=current)
                report["model_training_performed"] = baseline["model_training_performed"]
                panels = {"financial": baseline["prediction_panel"]}
                ablation_hashes = {}
                for family in ("full", "science_only", "buyer_only"):
                    parameter_hash = _digest({"config": config, "family": family,
                        "fields": list(SCIENCE_FIELDS if family == "science_only" else BUYER_FIELDS if family == "buyer_only" else config["weights"]),
                        "ablation_semantics": "retained_full_weights_without_renormalization; risk and valuation only in full"})
                    ablation_hashes[family] = parameter_hash
                    panel = copy.deepcopy(baseline["prediction_panel"])
                    for raw in panel["observations"]:
                        identity = f"{int(raw['cik'])}:{_time(raw['observation_at'], 'observation_at').date().isoformat()}"
                        rating = scored[identity]
                        raw.update({"score": score(rating["values"], config, family), "probability": None,
                            "probability_semantics": "ordinal_ranking_only_no_deal_probability", "model_version": f"{VERSION}:{family}:{parameter_hash}",
                            "feature_snapshot_sha256": rating["record_sha256"], "selected_buyer": rating["selected_buyer"],
                            "buyer_selection_reason": rating["selection_reason"], "score_parameter_sha256": parameter_hash,
                            "feature_max_available_at": max(_time(raw["feature_max_available_at"], "financial feature time"),
                                _time(rating["rating_source_max_available_at"], "rating source time")).isoformat(),
                            "rating_source_max_available_at": rating["rating_source_max_available_at"],
                            "actual_rating_reviewed_through": rating["actual_rating_reviewed_through"]})
                    panel.update(DISCLOSURES)
                    panels[family] = panel
                for rating in scored.values():
                    rating["family_scores"] = {family: score(rating["values"], config, family) for family in ("full", "science_only", "buyer_only")}
                bindings = {"hashes": report["hashes"], "created_at": current.isoformat(), **DISCLOSURES}
                panels = {family: {**panel, **bindings} for family, panel in panels.items()}
                metrics = {family: _evaluate(panel, baseline, current) for family, panel in panels.items()}
                artifacts = {}
                for family, panel in panels.items():
                    artifacts[f"{family}_panel"] = str(write_immutable_json({**panel, **bindings}, output_dir, f"ma-{family}-panel"))
                    artifacts[f"{family}_evaluation"] = str(write_immutable_json({**metrics[family], **bindings}, output_dir, f"ma-{family}-evaluation"))
                artifacts["financial_training"] = str(write_immutable_json({**baseline, **bindings}, output_dir, "ma-financial-training"))
                artifacts["rating_scores"] = str(write_immutable_json({"scores": scored, "score_parameter_hashes": ablation_hashes, **bindings}, output_dir, "ma-rating-scores"))
                report.update({"status": "retrospective_experiment_evaluated_not_confirmed", "weighted_model_evaluated": True,
                    "predictions": {family: artifacts[f"{family}_panel"] for family in panels}, "metrics": metrics, "artifacts": artifacts,
                    "synthetic_test_fixture": data.get("synthetic_test_fixture") is True, "score_parameter_hashes": ablation_hashes})
        except Exception as exc:  # Retain unexpected model/evaluator failures; never publish empty success.
            report["status"] = "blocked"
            report["weighted_model_evaluated"] = False
            report["predictions"] = report["metrics"] = report["artifacts"] = None
            report["readiness"]["ready"] = False
            report["readiness"]["errors"].append(f"experiment failed: {exc}")
    return report, write_immutable_json(report, output_dir, "ma-experiment")
