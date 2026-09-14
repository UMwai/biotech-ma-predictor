"""Synthetic fixtures exercise mechanics only; they provide no acquisition evidence."""

import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts.train_baseline import main
from src.research.training import (
    TrainingBlocked, TrainingConfig, apply_baseline, decision_score, train_baseline,
    validate_training_data, write_immutable_json,
)

requires_model = pytest.mark.skipif(importlib.util.find_spec("sklearn") is None,
                                    reason="optional sklearn modeling dependency")
NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


def synthetic_dataset():
    rows = []
    for year in (2018, 2020, 2021, 2022):
        at = datetime(year, 1, 2, 22, tzinfo=timezone.utc)
        horizon_end = at + timedelta(days=365)
        for cik in range(1, 26):
            positive = cik <= 5
            rows.append({
                "cik": cik, "observation_at": at.isoformat(), "horizon_days": 365,
                "information_cutoff_at": (at - timedelta(days=1)).isoformat(),
                "feature_max_available_at": (at - timedelta(days=2)).isoformat(),
                "features": {"cash_usd": 1e9 if positive else float(cik * 100),
                             "burn_usd_per_quarter": None if cik % 3 == 0 else float(cik * 10)},
                "risk_set_eligible": True, "risk_set_exclusion_reason": None,
                "membership": {"kind": "historical_exchange_membership", "source_uri": "synthetic://membership",
                               "source_sha256": "a" * 64, "security_type": "common_equity", "biotech_eligible": True,
                               "valid_from": "2017-01-01T00:00:00+00:00", "valid_until": "2026-01-01T00:00:00+00:00"},
                "label": {"reviewed": True, "review_id": f"synthetic-{cik}-{year}",
                          "source_uri": "synthetic://outcome", "source_sha256": "b" * 64,
                          "event_class": "change_of_control_announcement" if positive else "no_change_of_control_announcement",
                          "announcement_at": (at + timedelta(days=100)).isoformat() if positive else None,
                          "observed_through": (horizon_end + timedelta(days=5)).isoformat(),
                          "available_at": (horizon_end + timedelta(days=10)).isoformat()},
            })
    return {"schema_version": "historical-company-features-v1", "data_as_of": "2026-01-01T00:00:00+00:00",
            "feature_names": ["cash_usd", "burn_usd_per_quarter"],
            "feature_units": {"cash_usd": "USD", "burn_usd_per_quarter": "USD/quarter"},
            "synthetic_test_fixture": True, "observations": rows}


@requires_model
def test_supervised_baseline_learns_and_preserves_research_only_contract():
    run = train_baseline(synthetic_dataset(), TrainingConfig(2021), now=NOW)
    assert [fold["test_year"] for fold in run["folds"]] == [2021, 2022]
    assert run["status"] == "retrospective_baseline_fitted_not_promoted"
    assert run["validated_predictive_edge"] is False
    assert run["model_training_performed"] is True and run["synthetic_test_fixture"] is True
    assert run["calibration_status"] == "unvalidated"
    assert run["evaluation"]["evidence_type"] == "retrospective_out_of_time_panel"
    assert run["evaluation"]["overall"]["pooled_row_diagnostics"]["probability_metrics"] is not None
    heldout = run["prediction_panel"]["observations"]
    assert len(heldout) == 50
    assert heldout[0]["score"] > heldout[24]["score"]
    assert heldout[0]["probability"] > heldout[24]["probability"]
    assert run["final_model"]["user_facing_probability"] is None


@requires_model
def test_imputation_and_scaling_fit_only_purged_training_rows():
    dataset = synthetic_dataset()
    run = train_baseline(dataset, TrainingConfig(2021), now=NOW)
    first = run["folds"][0]
    assert first["training_support"]["company_observations"] == 25
    assert first["purged_prior_observations"] == 25
    assert all(":2018-" in key for key in first["training_observation_ids"])
    assert first["model"]["feature_medians"][0] == 1800
    altered = copy.deepcopy(dataset)
    for row in altered["observations"]:
        if row["observation_at"].startswith("2021"):
            row["features"] = {"cash_usd": 1e12, "burn_usd_per_quarter": 1e12}
    other = train_baseline(altered, TrainingConfig(2021), now=NOW)
    assert first["model"] == other["folds"][0]["model"]


def test_label_availability_is_purged_even_after_horizon_maturity():
    dataset = synthetic_dataset()
    for row in dataset["observations"]:
        if row["observation_at"].startswith("2018") and row["cik"] == 1:
            row["label"]["available_at"] = "2021-06-01T00:00:00+00:00"
    with pytest.raises(TrainingBlocked, match="insufficient distinct positive events"):
        train_baseline(dataset, TrainingConfig(2021), now=NOW)


@pytest.mark.parametrize("change,error", [
    ("proxy_membership", "actual historical exchange membership"),
    ("unreviewed", "not reviewed"),
    ("candidate", "unsupported event class"),
    ("future_feature", "features/cutoff"),
    ("nan_feature", "finite number"),
    ("missing_units", "feature_units"),
])
def test_evidence_or_feature_gaps_block_before_fitting(change, error):
    dataset = synthetic_dataset()
    row = dataset["observations"][0]
    if change == "proxy_membership":
        row["membership"]["kind"] = "annual_sec_reporting_proxy"
    elif change == "unreviewed":
        row["label"]["reviewed"] = False
    elif change == "candidate":
        row["label"]["event_class"] = "tender_offer_target"
    elif change == "future_feature":
        row["feature_max_available_at"] = "2025-01-01T00:00:00+00:00"
    elif change == "nan_feature":
        row["features"]["cash_usd"] = float("nan")
    else:
        dataset.pop("feature_units")
    with pytest.raises(TrainingBlocked, match=error):
        validate_training_data(dataset, now=NOW)


def test_repeated_positive_weeks_do_not_satisfy_distinct_event_floor():
    dataset = synthetic_dataset()
    dataset["observations"] = [row for row in dataset["observations"] if row["cik"] == 1 or row["cik"] > 5]
    first_positive = copy.deepcopy(dataset["observations"][0])
    first_observation = datetime.fromisoformat(first_positive["observation_at"])
    for week in range(1, 6):
        repeated = copy.deepcopy(first_positive)
        at = first_observation + timedelta(weeks=week)
        repeated["observation_at"] = at.isoformat()
        repeated["information_cutoff_at"] = (at - timedelta(days=1)).isoformat()
        repeated["label"]["observed_through"] = "2019-03-01T00:00:00+00:00"
        repeated["label"]["available_at"] = "2019-03-02T00:00:00+00:00"
        dataset["observations"].append(repeated)
    with pytest.raises(TrainingBlocked, match="insufficient distinct positive events"):
        train_baseline(dataset, TrainingConfig(2021), now=NOW)


def test_single_class_and_insufficient_years_block():
    dataset = synthetic_dataset()
    dataset["observations"] = [row for row in dataset["observations"] if row["cik"] <= 5]
    with pytest.raises(TrainingBlocked, match="insufficient distinct negative companies"):
        train_baseline(dataset, TrainingConfig(2021), now=NOW)
    with pytest.raises(TrainingBlocked, match="insufficient chronological test years"):
        train_baseline(synthetic_dataset(), TrainingConfig(2022), now=NOW)
    with pytest.raises(TrainingBlocked, match="evidence floors cannot be relaxed"):
        train_baseline(synthetic_dataset(), TrainingConfig(2021, min_train_positive_events=1), now=NOW)


@requires_model
def test_portable_application_checks_units_and_withholds_probabilities():
    dataset = synthetic_dataset()
    model = train_baseline(dataset, TrainingConfig(2021), now=NOW)["final_model"]
    current = {"schema_version": "current-company-features-v1", "feature_names": dataset["feature_names"],
               "feature_units": dataset["feature_units"], "observations": [{
                   "cik": 999, "observation_at": "2026-09-09T22:00:00+00:00",
                   "information_cutoff_at": "2026-09-08T22:00:00+00:00",
                   "feature_max_available_at": "2026-09-08T20:00:00+00:00",
                   "features": {"cash_usd": 1e9, "burn_usd_per_quarter": None}, "risk_set_eligible": True,
               }]}
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    result = apply_baseline(model, current, now=now)["observations"][0]
    assert result["probability"] is None and result["deal_probability_12mo"] is None
    assert result["score"] == decision_score(model, current["observations"][0]["features"])
    current["observations"][0]["risk_set_eligible"] = False
    assert apply_baseline(model, current, now=now)["observations"][0]["score"] is None
    current["feature_units"] = {**dataset["feature_units"], "cash_usd": "USD millions"}
    with pytest.raises(TrainingBlocked, match="units differ"):
        apply_baseline(model, current, now=now)


def test_immutable_training_artifacts_and_missing_dataset_cli(tmp_path, capsys):
    value = {"synthetic_test_fixture": True, "model": "test only"}
    path = write_immutable_json(value, tmp_path, "test-model")
    assert write_immutable_json(value, tmp_path, "test-model") == path
    assert write_immutable_json({**value, "model": "changed"}, tmp_path, "test-model") != path
    path.write_text("tampered")
    with pytest.raises(TrainingBlocked, match="immutable artifact changed"):
        write_immutable_json(value, tmp_path, "test-model")
    assert main([]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "blocked"


@requires_model
def test_first_holdout_comparator_uses_actual_prior_training_evidence():
    run = train_baseline(synthetic_dataset(), TrainingConfig(2021), now=NOW)
    fold = run["folds"][0]
    baseline = fold["training_base_rate_comparator"]
    assert baseline["training_source"] == "actual_purged_fold_training_partition"
    assert baseline["training_observations"] == 25
    assert baseline["training_support"]["distinct_positive_events"] == 5
    assert baseline["probability"] == 0.2
    assert baseline["training_dataset_sha256"] == fold["training_dataset_sha256"]
    assert baseline["training_observation_ids"] == fold["training_observation_ids"]
    assert all(":2018-" in key for key in baseline["training_observation_ids"])
    assert all(":2021-" in key for key in baseline["evaluated_observation_ids"])
    assert baseline["metrics"]["average_precision"] == 0.2
    assert baseline["metrics"]["probability_metrics"]["brier_score"] == pytest.approx(0.16)
    assert baseline["metrics"]["probability_metrics"]["log_loss"] > 0
    assert baseline["metrics"]["top_k"] is None
    annual = run["evaluation"]["by_year"]["2021"]
    assert annual["past_only_base_rate_comparator"] == baseline
    assert annual["heldout_history_base_rate_comparator"]["training_observations"] == 0


@requires_model
def test_training_comparator_probability_does_not_change_with_holdout_labels():
    dataset = synthetic_dataset()
    original = train_baseline(dataset, TrainingConfig(2021), now=NOW)["folds"][0]["training_base_rate_comparator"]
    for row in dataset["observations"]:
        if row["observation_at"].startswith("2021"):
            row["label"]["event_class"] = "no_change_of_control_announcement"
            row["label"]["announcement_at"] = None
    altered = train_baseline(dataset, TrainingConfig(2021), now=NOW)["folds"][0]["training_base_rate_comparator"]
    assert altered["probability"] == original["probability"] == 0.2
    assert altered["training_dataset_sha256"] == original["training_dataset_sha256"]
    assert altered["metrics"]["average_precision"] == 0
    assert altered["metrics"]["probability_metrics"]["brier_score"] == pytest.approx(0.04)


@requires_model
def test_date_only_supervision_preserves_uncertainty_and_normalized_event_identity():
    dataset = synthetic_dataset()
    for row in dataset["observations"]:
        label = row["label"]
        if label["announcement_at"]:
            label["announcement_date"] = label.pop("announcement_at")[:10]
            label["timestamp_precision"] = "date"
    run = train_baseline(dataset, TrainingConfig(2021), now=NOW)
    assert run["folds"][0]["training_support"]["distinct_positive_events"] == 5
    heldout = run["prediction_panel"]["observations"][0]["label"]
    assert heldout["timestamp_precision"] == "date"
    assert heldout["announcement_date"] == "2021-04-12"
    assert "announcement_at" not in heldout


def reconstructed_dataset():
    # Shared protocol fixtures remain explicitly synthetic; only clocks differ.
    from test_validation import reconstructed_panel
    dataset = synthetic_dataset()
    protocol = reconstructed_panel(*dataset['observations'])
    dataset.update({key: protocol[key] for key in ('label_timing_policy', 'historical_sampling_frame', 'data_as_of')})
    dataset['historical_sampling_frame']['population_as_of_at'] = '2017-01-01T00:00:00Z'
    return dataset


@requires_model
def test_retrospective_training_uses_original_disclosure_clock_and_preserves_actual_review():
    run = train_baseline(reconstructed_dataset(), TrainingConfig(2021), now=NOW)
    assert run['folds'][0]['training_support']['company_observations'] == 30
    assert run['folds'][0]['actual_label_assembly_available_through'].startswith('2026-01-03')
    assert run['folds'][0]['training_outcomes_available_through'].startswith('2021-01-01')
    assert run['prediction_panel']['observations'][0]['label']['reviewed_at'].startswith('2026-01-02')
    assert run['evaluation']['label_timing_policy'] == 'retrospective_primary_evidence_v1'
    assert run['evaluation']['reconstructed_label_observations'] == 50
    comparator = run['folds'][0]['training_base_rate_comparator']
    assert comparator['training_outcomes_available_through'].startswith('2021-01-01')
    assert comparator['actual_label_assembly_available_through'].startswith('2026-01-03')


def test_later_required_source_purges_retrospectively_reconstructed_training_label():
    from test_validation import reseal_sources
    dataset = reconstructed_dataset()
    row = dataset['observations'][5]  # Exactly twenty negative issuers: delay one.
    row['label']['historical_evidence_timing']['sources'][0]['publication_date'] = '2021-06-01'
    reseal_sources(row)
    with pytest.raises(TrainingBlocked, match='insufficient distinct negative companies'):
        train_baseline(dataset, TrainingConfig(2021), now=NOW)


def test_newly_reviewed_labels_do_not_inherit_past_training_time_without_explicit_policy():
    dataset = synthetic_dataset()
    for row in dataset['observations']:
        row['label'].update(available_at='2026-01-01T00:00:00Z', reviewed_at='2026-01-01T00:00:00Z')
    with pytest.raises(TrainingBlocked, match='insufficient distinct positive events'):
        train_baseline(dataset, TrainingConfig(2021), now=NOW)
