"""Synthetic contract fixtures; these rows are not historical research evidence."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts.evaluate_predictions import main
from src.research.validation import PanelValidationError, RETROSPECTIVE_LABEL_TIMING, evaluate_panel, validate_panel, write_evaluation


def timestamp(value):
    return value.isoformat()


def observation(cik=1, year=2022, positive=True, probability=0.5):
    at = datetime(year, 1, 2, 22, tzinfo=timezone.utc)
    horizon_end = at + timedelta(days=365)
    cutoff = at - timedelta(days=1)
    return {
        "cik": cik, "observation_at": timestamp(at), "horizon_days": 365,
        "information_cutoff_at": timestamp(cutoff),
        "feature_max_available_at": timestamp(cutoff - timedelta(hours=1)),
        "training_cutoff_at": timestamp(cutoff - timedelta(days=1)),
        "training_outcomes_available_through": timestamp(cutoff - timedelta(days=2)),
        "split_method": "expanding_window", "fold_id": f"fold-{year}",
        "model_version": "synthetic-test-model", "training_dataset_sha256": "a" * 64,
        "feature_snapshot_sha256": "b" * 64,
        "prediction_generated_at": "2025-01-01T00:00:00+00:00",
        "prediction_sealed_at": "2025-01-02T00:00:00+00:00",
        "risk_set_eligible": True, "risk_set_exclusion_reason": None,
        "membership": {
            "kind": "historical_exchange_membership", "source_uri": "synthetic://membership",
            "source_sha256": "c" * 64, "security_type": "common_equity", "biotech_eligible": True,
            "valid_from": "2020-01-01T00:00:00+00:00", "valid_until": "2027-01-01T00:00:00+00:00",
        },
        "label": {
            "reviewed": True, "review_id": f"synthetic-review-{cik}-{year}",
            "source_uri": "synthetic://adjudicated-outcome", "source_sha256": "d" * 64,
            "event_class": "change_of_control_announcement" if positive else "no_change_of_control_announcement",
            "announcement_at": timestamp(at + timedelta(days=100)) if positive else None,
            "observed_through": timestamp(horizon_end + timedelta(days=5)),
            "available_at": timestamp(horizon_end + timedelta(days=10)),
        },
        "score": 50, "probability": probability,
    }


def panel(*rows, mode="retrospective_out_of_time"):
    return {
        "schema_version": "sealed-company-predictions-v1", "evaluation_mode": mode,
        "data_as_of": "2026-01-01T00:00:00+00:00", "observations": list(rows),
    }


def evaluate(value):
    digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return evaluate_panel(value, input_sha256=digest)


def test_retrospective_generation_after_outcomes_is_never_called_forward():
    report = evaluate(panel(observation(), observation(cik=2, positive=False)))
    assert report["evaluation_mode"] == "retrospective_out_of_time"
    assert report["evidence_type"] == "retrospective_out_of_time_panel"
    assert report["model_training_performed"] is False
    assert report["validated_predictive_edge"] is False
    assert report["overall"]["pooled_row_diagnostics"]["observations"] == 2
    assert report["overall"]["pooled_row_diagnostics"]["base_rate"] == 0.5
    assert report["overall"]["pooled_row_diagnostics"]["average_precision"] == 0.5
    assert report["overall"]["pooled_row_diagnostics"]["probability_metrics"]["brier_score"] == 0.25
    bins = report["overall"]["pooled_row_diagnostics"]["calibration_bins"]
    assert len(bins) == 10 and sum(item["count"] for item in bins) == 2
    assert bins[5]["count"] == 2 and bins[5]["observed_rate"] == 0.5
    assert bins[0]["count"] == 0 and bins[0]["observed_rate"] is None


def test_forward_requires_actual_sealing_before_observation_and_outcome():
    row = observation()
    with pytest.raises(PanelValidationError, match="forward prediction was not sealed"):
        evaluate(panel(row, mode="forward"))
    row["prediction_generated_at"] = "2022-01-02T01:00:00+00:00"
    row["prediction_sealed_at"] = "2022-01-02T02:00:00+00:00"
    assert evaluate(panel(row, mode="forward"))["evidence_type"] == "forward_sealed_panel"


@pytest.mark.parametrize("field,value,error", [
    ("feature_max_available_at", "2022-01-03T00:00:00+00:00", "features/cutoff"),
    ("training_outcomes_available_through", "2022-01-03T00:00:00+00:00", "training outcomes leak"),
    ("split_method", "random_split", "chronological"),
    ("risk_set_eligible", False, "risk-set eligibility"),
    ("risk_set_eligible", "True", "risk-set eligibility"),
    ("risk_set_exclusion_reason", "transaction pending", "risk-set eligibility"),
    ("score", float("nan"), "finite number"),
    ("probability", float("inf"), "finite number"),
    ("probability", -0.1, "outside"),
    ("probability", 1.1, "outside"),
    ("observation_at", "2022-01-02T22:00:00", "timezone required"),
    ("training_dataset_sha256", "missing", "SHA-256"),
])
def test_contract_rejects_leaking_or_unusable_rows(field, value, error):
    row = observation()
    row[field] = value
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(panel(row))


@pytest.mark.parametrize("field,value,error", [
    ("reviewed", False, "not reviewed"),
    ("event_class", "tender_offer_target", "unsupported event class"),
    ("announcement_at", "2021-12-31T00:00:00+00:00", "announcement must follow"),
    ("observed_through", "2022-10-01T00:00:00+00:00", "censored"),
    ("available_at", "2022-01-03T00:00:00+00:00", "label availability"),
])
def test_unreviewed_or_invalid_labels_block(field, value, error):
    row = observation()
    row["label"][field] = value
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(panel(row))


def test_censored_horizon_and_reporting_proxy_membership_block():
    data = panel(observation())
    data["data_as_of"] = "2022-12-01T00:00:00+00:00"
    with pytest.raises(PanelValidationError, match="immature"):
        validate_panel(data)
    data = panel(observation())
    data["observations"][0]["membership"]["kind"] = "annual_sec_reporting_proxy"
    with pytest.raises(PanelValidationError, match="actual historical exchange"):
        validate_panel(data)


def test_delisting_is_not_a_negative_and_acquired_targets_remain_evaluable():
    row = observation(positive=False)
    row["membership"]["valid_until"] = "2022-10-01T00:00:00+00:00"
    with pytest.raises(PanelValidationError, match="competing-event/censoring"):
        validate_panel(panel(row))
    acquired = observation(positive=True)
    acquired["membership"]["valid_until"] = "2022-10-01T00:00:00+00:00"
    assert validate_panel(panel(acquired))[0]["label"] is True


def test_duplicate_cik_date_and_inconsistent_fold_lineage_block():
    first = observation()
    duplicate = copy.deepcopy(first)
    duplicate["cik"] = "0000001"
    duplicate["observation_at"] = "2022-01-02T23:00:00+00:00"
    with pytest.raises(PanelValidationError, match="duplicate CIK"):
        validate_panel(panel(first, duplicate))
    other = observation(cik=2)
    other["training_dataset_sha256"] = "e" * 64
    with pytest.raises(PanelValidationError, match="fold training lineage"):
        validate_panel(panel(first, other))


def test_empty_support_blocks_without_inventing_baseline_or_lift():
    with pytest.raises(PanelValidationError, match="no eligible"):
        validate_panel(panel())
    report = evaluate(panel(observation(positive=False, probability=None)))
    metrics = report["overall"]["pooled_row_diagnostics"]
    assert metrics["base_rate"] == 0
    assert metrics["positive_support_status"] == "no_positive_events"
    assert metrics["top_k"] is None
    assert report["per_cohort"]["2022-01-02"]["top_k"]["10"]["lift_over_base_rate"] is None
    assert metrics["probability_metrics"] is None and metrics["calibration_bins"] is None
    comparator = report["by_year"]["2022"]["past_only_base_rate_comparator"]
    assert comparator["training_observations"] == 0 and comparator["probability"] is None


def test_years_are_chronological_and_comparator_uses_only_mature_available_past_labels():
    rows = [observation(3, 2024), observation(1, 2022), observation(2, 2022, positive=False)]
    report = evaluate(panel(*rows))
    assert list(report["by_year"]) == ["2022", "2024"]
    comparator = report["by_year"]["2024"]["past_only_base_rate_comparator"]
    assert comparator["training_observations"] == 2
    assert comparator["probability"] == 0.5
    assert comparator["metrics"]["top_k"] is None
    assert comparator["metrics"]["ranking_status"] == "constant_probability_has_no_ranking_discrimination"
    # Outcome window completion is insufficient when the reviewed label arrived later.
    rows[1]["label"]["available_at"] = "2025-03-01T00:00:00+00:00"
    comparator = evaluate(panel(*rows))["by_year"]["2024"]["past_only_base_rate_comparator"]
    assert comparator["training_observations"] == 1 and comparator["probability"] == 0


def test_partial_probability_coverage_never_gets_partial_calibration():
    report = evaluate(panel(observation(), observation(cik=2, probability=None)))
    assert report["overall"]["pooled_row_diagnostics"]["probability_rows"] == 1
    assert report["overall"]["pooled_row_diagnostics"]["probability_metrics"] is None
    assert report["overall"]["pooled_row_diagnostics"]["calibration_bins"] is None


def test_reports_are_immutable_and_content_addressed_by_input(tmp_path):
    source = tmp_path / "panel.json"
    source.write_text(json.dumps(panel(observation())))
    output = tmp_path / "reports"
    first = write_evaluation(source, output)
    assert write_evaluation(source, output) == first
    original = first.read_bytes()
    source.write_text(json.dumps(panel(observation(cik=2))))
    assert write_evaluation(source, output) != first
    assert first.read_bytes() == original
    first.write_text("tampered")
    source.write_text(json.dumps(panel(observation())))
    with pytest.raises(PanelValidationError, match="immutable evaluation collision"):
        write_evaluation(source, output)


def test_cli_missing_dataset_is_explicit_nonzero_blocker(tmp_path, capsys):
    assert main(["--output-dir", str(tmp_path / "reports")]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "blocked"
    assert not (tmp_path / "reports").exists()
    assert main(["--panel", str(tmp_path / "absent.json")]) == 2
    assert "missing eligible historical prediction panel" in capsys.readouterr().err


def test_weekly_top_k_and_distinct_deal_capture_do_not_pool_repeated_targets():
    first_week = [observation(cik, positive=cik == 1) for cik in range(1, 12)]
    second_week = [observation(cik, positive=cik == 1) for cik in range(1, 22)]
    for row in first_week:
        row["score"] = 100 if row["cik"] == 1 else 90 - row["cik"]
    for row in second_week:
        row["score"] = -1 if row["cik"] == 1 else 90 - row["cik"]
        row["observation_at"] = "2022-01-09T22:00:00+00:00"
        row["information_cutoff_at"] = "2022-01-08T22:00:00+00:00"
        row["label"]["observed_through"] = "2023-01-20T00:00:00+00:00"
        row["label"]["available_at"] = "2023-01-21T00:00:00+00:00"
    report = evaluate(panel(*first_week, *second_week))
    assert report["per_cohort"]["2022-01-02"]["top_k"]["10"]["precision"] == 0.1
    assert report["per_cohort"]["2022-01-09"]["top_k"]["10"]["precision"] == 0
    annual = report["by_year"]["2022"]
    assert annual["pooled_row_diagnostics"]["observations"] == 32
    assert annual["pooled_row_diagnostics"]["positives"] == 2
    assert annual["pooled_row_diagnostics"]["top_k"] is None
    aggregate = annual["cohort_aggregate"]
    assert aggregate["weighting"] == "equal_weight_per_observation_date"
    assert aggregate["top_k"]["10"]["mean_precision"] == 0.05
    assert aggregate["mean_company_observation_base_rate"] == pytest.approx((1 / 11 + 1 / 21) / 2)
    capture = report["overall"]["distinct_deal_capture"]
    assert capture["distinct_positive_events"] == 1
    assert capture["top_k"]["10"]["distinct_events_captured"] == 1
    assert capture["top_k"]["20"]["distinct_events_captured"] == 1
    assert capture["top_k"]["10"]["distinct_event_recall"] == 1


def test_observation_date_requires_consistent_cross_section_cutoffs():
    first, second = observation(), observation(cik=2)
    second["information_cutoff_at"] = "2022-01-01T23:00:00+00:00"
    with pytest.raises(PanelValidationError, match="same observation and information cutoff"):
        validate_panel(panel(first, second))


def test_future_forward_panel_cannot_claim_matured_future_outcomes():
    row = observation(year=2030)
    row["prediction_generated_at"] = "2030-01-02T01:00:00+00:00"
    row["prediction_sealed_at"] = "2030-01-02T02:00:00+00:00"
    row["membership"]["valid_until"] = "2035-01-01T00:00:00+00:00"
    data = panel(row, mode="forward")
    data["data_as_of"] = "2032-01-01T00:00:00+00:00"
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    with pytest.raises(PanelValidationError, match="data_as_of cannot be later"):
        validate_panel(data, now=now)


@pytest.mark.parametrize("field", ["prediction_generated_at", "prediction_sealed_at"])
def test_retrospective_artifacts_cannot_be_generated_or_sealed_in_future(field):
    row = observation()
    row[field] = "2030-01-01T00:00:00+00:00"
    if field == "prediction_generated_at":
        row["prediction_sealed_at"] = "2030-01-02T00:00:00+00:00"
    with pytest.raises(PanelValidationError, match="generation/sealing cannot be later"):
        validate_panel(panel(row), now=datetime(2026, 9, 7, tzinfo=timezone.utc))


def test_date_only_announcement_requires_entire_uncertainty_interval_in_horizon():
    row = observation()
    row["label"].update(announcement_at=None, announcement_date="2022-04-12", timestamp_precision="date")
    assert validate_panel(panel(row))[0]["event_id"] == "1:2022-04-12"
    row["label"]["announcement_date"] = "2022-01-03"
    with pytest.raises(PanelValidationError, match="including date uncertainty"):
        validate_panel(panel(row))
    row["label"]["announcement_date"] = "2023-01-02"
    with pytest.raises(PanelValidationError, match="including date uncertainty"):
        validate_panel(panel(row))


def test_fabricated_narrow_date_interval_and_negative_date_are_rejected():
    row = observation()
    row["label"].update(announcement_at=None, announcement_date="2022-04-12", timestamp_precision="date",
                        announcement_lower_at="2022-04-12T00:00:00Z")
    with pytest.raises(PanelValidationError, match="preserve source date uncertainty"):
        validate_panel(panel(row))
    row = observation(positive=False)
    row["label"]["announcement_date"] = "2022-04-12"
    with pytest.raises(PanelValidationError, match="negative label contradicts"):
        validate_panel(panel(row))


@pytest.mark.parametrize("alias", ["announced_at", "first_public_announcement_at"])
def test_negative_label_cannot_hide_an_announcement_in_timestamp_alias(alias):
    row = observation(positive=False)
    row["label"][alias] = "2022-04-12T12:00:00Z"
    with pytest.raises(PanelValidationError, match="negative label contradicts"):
        validate_panel(panel(row))


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def reconstructed_panel(*rows):
    """Synthetic evidence annotations; these do not authenticate any real sources."""
    result = panel(*rows)
    result.update(label_timing_policy=RETROSPECTIVE_LABEL_TIMING, data_as_of="2026-02-01T00:00:00Z")
    result["historical_sampling_frame"] = {
        "source_uri": "synthetic://historical-frame", "source_sha256": "f" * 64,
        "selection_basis": "historical_exchange_constituents", "selection_rule": "All original cohort members; gaps retained in coverage ledger.",
        "source_locator": "Original dated constituent notice", "uses_current_listing_status": False,
        "uses_future_outcomes": False, "includes_subsequently_delisted": True,
        "population_as_of_at": "2020-01-01T00:00:00Z", "retrieved_at": "2026-01-01T00:00:00Z",
        "reviewed_at": "2026-01-02T00:00:00Z",
    }
    for row in rows:
        label = row["label"]
        label.update(reviewed_at="2026-01-02T00:00:00Z", available_at="2026-01-03T00:00:00Z")
        horizon_end = datetime.fromisoformat(row["observation_at"]) + timedelta(days=row["horizon_days"])
        source = {
            "source_id": "primary-1", "source_uri": "https://issuer.example/original-release",
            "source_sha256": "1" * 64, "source_sha256_kind": "original_document_bytes",
            "source_family": "issuer_news", "subject_cik": row["cik"], "version_status": "verified_original",
            "source_locator": "Dated original issuer release body", "publication_basis": "issuer_publication",
            "publication_timestamp_precision": "date", "publication_date": f"{horizon_end.year}-01-10", "published_at": None,
            "retrieved_at": "2026-01-01T00:00:00Z",
        }
        for field in ("publication_evidence", "original_version_evidence"):
            source[field] = {"source_uri": source["source_uri"], "source_sha256": source["source_sha256"],
                             "source_locator": "Primary publication header and original version identifier"}
        positive = label["event_class"] == "change_of_control_announcement"
        if positive:
            source.update(publication_timestamp_precision="timestamp", publication_date=None, published_at=label["announcement_at"])
        receipt = {
            "schema_version": "retrospective-label-evidence-v1", "review_id": label["review_id"],
            "label_source_sha256": label["source_sha256"], "cik": row["cik"], "event_class": label["event_class"],
            "observation_at": row["observation_at"], "horizon_end_at": horizon_end.isoformat(),
            "reviewed_at": label["reviewed_at"], "reviewer": "Synthetic test reviewer", "sources": [source],
        }
        if positive:
            receipt["announcement_source_id"] = source["source_id"]
        else:
            receipt["coverage"] = {
                "source_uri": "synthetic://complete-inventory", "source_sha256": "2" * 64,
                "kind": "complete_designated_primary_corpus", "inventory_complete": True,
                "full_text_review_complete": True, "censoring_review_complete": True,
                "known_missing_sources": False, "qualifying_control_event_found": False, "censoring_event_found": False,
                "window_start_at": row["observation_at"], "window_end_at": horizon_end.isoformat(),
                "required_source_ids": [source["source_id"]], "source_families": [source["source_family"]],
                "scope": "Complete designated issuer corpus", "removed_page_limitations": "Removed pages cannot independently be ruled out.",
                "retrieved_at": "2026-01-01T00:00:00Z",
            }
        receipt["sources_sha256"] = canonical_hash(receipt["sources"])
        label["historical_evidence_timing"] = receipt
    return result


def reseal_sources(row):
    receipt = row["label"]["historical_evidence_timing"]
    receipt["sources_sha256"] = canonical_hash(receipt["sources"])


def test_reconstruction_retains_actual_review_but_uses_mature_original_evidence_for_training():
    row = observation(positive=False)
    data = reconstructed_panel(row)
    normalized = validate_panel(data)[0]
    assert normalized["label_available_at"] == datetime(2026, 1, 3, tzinfo=timezone.utc)
    assert normalized["label_reviewed_at"] == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert normalized["label_training_available_at"] == datetime(2023, 1, 11, 12, tzinfo=timezone.utc)
    assert row["label"]["available_at"] == "2026-01-03T00:00:00Z"
    report = evaluate(data)
    assert report["reconstructed_label_observations"] == 1
    assert report["evidence_type"] == "retrospective_out_of_time_panel"
    assert report["validated_predictive_edge"] is False


def test_negative_reporting_lag_cannot_mature_before_covered_search_endpoint():
    row = observation(positive=False)
    data = reconstructed_panel(row)
    coverage = row["label"]["historical_evidence_timing"]["coverage"]
    coverage["window_end_at"] = "2023-04-01T00:00:00Z"
    assert validate_panel(data)[0]["label_training_available_at"] == datetime(2023, 4, 1, tzinfo=timezone.utc)
    coverage["ascertainment_complete_at"] = "2023-04-01T12:00:00Z"
    normalized = validate_panel(data)[0]
    assert normalized["label_training_available_at"] == datetime(2023, 4, 1, 12, tzinfo=timezone.utc)
    assert normalized["label_available_at"] == datetime(2026, 1, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize("bound", ["2023-03-31T23:59:59Z", "2026-01-02T00:00:00Z", "2027-01-01T00:00:00Z", "invalid", "2023-04-01"])
def test_invalid_negative_ascertainment_clock_is_rejected(bound):
    row = observation(positive=False)
    data = reconstructed_panel(row)
    coverage = row["label"]["historical_evidence_timing"]["coverage"]
    coverage.update(window_end_at="2023-04-01T00:00:00Z", ascertainment_complete_at=bound)
    with pytest.raises(PanelValidationError):
        validate_panel(data)


def test_reconstructed_comparator_excludes_post_cutoff_disclosures_even_for_mature_windows():
    first, later = observation(positive=False), observation(cik=2, year=2024)
    data = reconstructed_panel(first, later)
    assert evaluate(data)["by_year"]["2024"]["past_only_base_rate_comparator"]["training_observations"] == 1
    source = first["label"]["historical_evidence_timing"]["sources"][0]
    source["publication_date"] = "2024-02-01"
    reseal_sources(first)
    assert evaluate(data)["by_year"]["2024"]["past_only_base_rate_comparator"]["training_observations"] == 0


def test_positive_reconstruction_still_waits_for_whole_horizon_and_preserves_source_time():
    row = observation()
    normalized = validate_panel(reconstructed_panel(row))[0]
    assert normalized["label_training_available_at"] == normalized["horizon_end"]
    source = row["label"]["historical_evidence_timing"]["sources"][0]
    source["published_at"] = "2024-01-01T00:00:00Z"
    reseal_sources(row)
    with pytest.raises(PanelValidationError, match="does not substantiate"):
        validate_panel(reconstructed_data(row))


def reconstructed_data(row):
    # Preserve mutations while reusing only the panel/frame envelope.
    result = reconstructed_panel()
    result["observations"] = [row]
    return result


@pytest.mark.parametrize("field,value,error", [
    ("version_status", "unknown", "unknown or revised"),
    ("version_status", "revised", "unknown or revised"),
    ("publication_basis", "reporting_period_end", "period ends and signatures"),
    ("publication_basis", "signed_at", "period ends and signatures"),
    ("publication_timestamp_precision", None, "explicit publication"),
    ("publication_upper_at", "2023-01-10T00:00:00Z", "preserve source date uncertainty"),
    ("subject_cik", 999, "subject CIK mismatch"),
    ("retrieved_at", "2027-01-01T00:00:00Z", "chronology"),
])
def test_reconstruction_rejects_uncertain_versions_and_forged_publication_annotations(field, value, error):
    row = observation(positive=False)
    data = reconstructed_panel(row)
    row["label"]["historical_evidence_timing"]["sources"][0][field] = value
    reseal_sources(row)
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(data)


@pytest.mark.parametrize("field,value,error", [
    ("inventory_complete", False, "complete coverage"),
    ("full_text_review_complete", False, "complete coverage"),
    ("censoring_review_complete", None, "complete coverage"),
    ("known_missing_sources", True, "unresolved"),
    ("qualifying_control_event_found", True, "contradictory"),
    ("censoring_event_found", True, "contradictory"),
    ("required_source_ids", [], "inventory differ"),
    ("window_end_at", "2022-06-01T00:00:00Z", "full outcome window"),
    ("window_end_at", "2027-01-01T00:00:00Z", "precede review"),
    ("retrieved_at", "2020-01-01T00:00:00Z", "horizon maturity"),
])
def test_reconstructed_negative_requires_complete_mature_uncensored_inventory(field, value, error):
    row = observation(positive=False)
    data = reconstructed_panel(row)
    row["label"]["historical_evidence_timing"]["coverage"][field] = value
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(data)


@pytest.mark.parametrize("field,value", [("uses_current_listing_status", True), ("uses_future_outcomes", True),
                                          ("includes_subsequently_delisted", False), ("selection_basis", "current_survivors")])
def test_reconstructed_history_cannot_select_todays_survivors_or_known_outcomes(field, value):
    data = reconstructed_panel(observation())
    data["historical_sampling_frame"][field] = value
    with pytest.raises(PanelValidationError, match="historical_sampling_frame"):
        validate_panel(data)


def test_reconstruction_requires_explicit_mode_and_cannot_be_relabelled_as_forward():
    row = observation()
    data = reconstructed_panel(row)
    data.pop("label_timing_policy")
    with pytest.raises(PanelValidationError, match="explicit retrospective label policy"):
        validate_panel(data)
    data["label_timing_policy"] = RETROSPECTIVE_LABEL_TIMING
    data["evaluation_mode"] = "forward"
    row.update(prediction_generated_at="2022-01-02T01:00:00Z", prediction_sealed_at="2022-01-02T02:00:00Z")
    with pytest.raises(PanelValidationError, match="cannot become forward"):
        validate_panel(data)


def test_review_cannot_be_backdated_to_original_publication_or_hidden_in_forward_labels():
    row = observation()
    data = reconstructed_panel(row)
    row["label"]["reviewed_at"] = "2023-01-01T00:00:00Z"
    with pytest.raises(PanelValidationError, match="actual review time mismatch"):
        validate_panel(data)
    row = observation()
    row["label"]["reviewed_at"] = "2026-01-01T00:00:00Z"
    row.update(prediction_generated_at="2022-01-02T01:00:00Z", prediction_sealed_at="2022-01-02T02:00:00Z")
    with pytest.raises(PanelValidationError, match="availability precedes actual review"):
        validate_panel(panel(row, mode="forward"))


def test_receipt_binds_label_issuer_window_and_source_manifest():
    original = reconstructed_panel(observation(positive=False))
    for field, value, error in [("cik", 999, "CIK mismatch"), ("review_id", "different", "bind the reviewed label"),
                                ("observation_at", "2021-01-01T00:00:00Z", "window mismatch"),
                                ("historical_evidence_available_at", "2022-12-01T00:00:00Z", "latest required original")]:
        data = copy.deepcopy(original)
        data["observations"][0]["label"]["historical_evidence_timing"][field] = value
        with pytest.raises(PanelValidationError, match=error):
            validate_panel(data)
    original["observations"][0]["label"]["historical_evidence_timing"]["sources"][0]["publication_date"] = "2023-01-09"
    with pytest.raises(PanelValidationError, match="source manifest hash mismatch"):
        validate_panel(original)


def test_legacy_labels_keep_their_existing_availability_without_automatic_reconstruction():
    row = observation()
    original_available = datetime.fromisoformat(row["label"]["available_at"])
    normalized = validate_panel(panel(row))[0]
    assert normalized["label_training_available_at"] == normalized["label_available_at"] == original_available
    data = reconstructed_panel(row)
    row["label"].pop("historical_evidence_timing")
    normalized = validate_panel(data)[0]
    assert normalized["label_training_available_at"] == datetime(2026, 1, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize("mutation,error", [("risk_set", "risk-set eligibility"),
                                            ("membership", "annual SEC proxies"),
                                            ("features", "features/cutoff")])
def test_reconstruction_does_not_bypass_existing_eligibility_and_feature_gates(mutation, error):
    row = observation(positive=False)
    data = reconstructed_panel(row)
    if mutation == "risk_set":
        row["risk_set_eligible"] = None
    elif mutation == "membership":
        row["membership"]["kind"] = "annual_sec_reporting_proxy"
    else:
        row["feature_max_available_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(data)


def browser_receipt_source(row):
    source = row["label"]["historical_evidence_timing"]["sources"][0]
    source.update(source_family="regulatory_filings", publication_basis="regulator_acceptance",
                  source_uri="https://www.sec.gov/Archives/edgar/data/1/000000000123000001/original.htm",
                  source_sha256_kind="source_review_receipt", original_source_sha256=None,
                  review_receipt_uri="synthetic://saved-source-review.json")
    source["immutable_document_uri"] = source["source_uri"]
    annotation = {key: source.get(key) for key in (
        "source_uri", "subject_cik", "version_status", "source_locator", "publication_basis",
        "publication_timestamp_precision", "publication_date", "published_at", "retrieved_at")}
    annotation.update(evidence_paraphrase="Synthetic original accession disclosure review.",
                      reviewer="Synthetic test reviewer", reviewed_at="2026-01-02T00:00:00Z")
    source.update(review_annotation=annotation, source_sha256=canonical_hash(annotation))
    row["label"]["historical_evidence_timing"]["coverage"]["source_families"] = ["regulatory_filings"]
    reseal_sources(row)
    return source


def test_browser_only_sec_evidence_uses_real_review_hash_without_claiming_original_bytes():
    row = observation(positive=False)
    data = reconstructed_panel(row)
    source = browser_receipt_source(row)
    assert validate_panel(data)[0]["label_training_available_at"] == datetime(2023, 1, 11, 12, tzinfo=timezone.utc)
    assert source["original_source_sha256"] is None
    source["publication_date"] = "2023-01-05"
    reseal_sources(row)
    with pytest.raises(PanelValidationError, match="annotation publication_date mismatch"):
        validate_panel(data)


@pytest.mark.parametrize("mutation,error", [("source_hash", "annotation hash mismatch"),
                                            ("original_hash", "leave original source hash unavailable"),
                                            ("mutable_url", "immutable SEC accession")])
def test_browser_source_receipts_reject_fabricated_byte_hashes_and_mutable_sources(mutation, error):
    row = observation(positive=False)
    data = reconstructed_panel(row)
    source = browser_receipt_source(row)
    if mutation == "source_hash":
        source["source_sha256"] = "9" * 64
    elif mutation == "original_hash":
        source["original_source_sha256"] = "9" * 64
    else:
        source["immutable_document_uri"] = source["source_uri"] = "https://www.sec.gov/current/issuer.htm"
    reseal_sources(row)
    with pytest.raises(PanelValidationError, match=error):
        validate_panel(data)


def test_acquirer_filing_can_evidence_target_with_explicit_distinct_identity_binding():
    row = observation(cik=2, positive=False)
    data = reconstructed_panel(row)
    source = browser_receipt_source(row)  # Accession belongs to filer 1, subject is target 2.
    with pytest.raises(PanelValidationError, match="explicit document_filer_cik"):
        validate_panel(data)
    source["document_filer_cik"] = 1
    source["subject_identity_evidence"] = {
        "source_uri": "synthetic://target-identity-review", "source_sha256": "3" * 64,
        "source_locator": "Target legal name and CIK explicitly linked in the source review.",
    }
    for field in ("document_filer_cik", "subject_identity_evidence"):
        source["review_annotation"][field] = source[field]
    source["source_sha256"] = canonical_hash(source["review_annotation"])
    reseal_sources(row)
    assert validate_panel(data)[0]["cik"] == 2
    source["document_filer_cik"] = 9
    reseal_sources(row)
    with pytest.raises(PanelValidationError, match="differs from accession path"):
        validate_panel(data)
