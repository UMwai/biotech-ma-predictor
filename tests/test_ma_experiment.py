"""Invented source bytes and ratings exercise mechanics, never real scientific evidence."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.run_ma_experiment import main
from src.research.ma_diligence import FINANCIAL_FEATURES, FINANCIAL_UNITS, NON_BUYER_FIELDS, score, validate_parameters
from src.research.ma_experiment import (file_hash, load_registration, rating_template, readiness,
                                       register, run_experiment)
from src.research.training import TrainingBlocked, train_baseline, TrainingConfig, validate_training_data, write_immutable_json
from test_training import synthetic_dataset

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
REGISTERED = NOW - timedelta(days=2)
REVIEWED = NOW - timedelta(days=1)
PARAMETERS = Path(__file__).resolve().parents[1] / "data/research/ma_parameter_set_v1.json"


def dataset():
    data = synthetic_dataset()
    for row in data["observations"]:
        year = int(row["observation_at"][:4])
        # Shift all synthetic clocks together to keep existing maturity semantics.
        for field in ("observation_at", "information_cutoff_at", "feature_max_available_at"):
            row[field] = row[field].replace(str(year), str(year + 2), 1)
        for field in ("announcement_at", "observed_through", "available_at"):
            if row["label"][field]:
                at = datetime.fromisoformat(row["label"][field])
                row["label"][field] = at.replace(year=at.year + 2).isoformat()
        row["membership"]["valid_until"] = "2027-01-01T00:00:00+00:00"
        row["features"] = {name: (1e9 if row["cik"] <= 5 else row["cik"] * 100) for name in FINANCIAL_FEATURES}
    data.update(feature_names=list(FINANCIAL_FEATURES), feature_units=FINANCIAL_UNITS,
                data_as_of="2026-01-01T00:00:00+00:00")
    return data


def prepared(tmp_path):
    data_path = tmp_path / "input.json"
    data_path.write_text(json.dumps(dataset()))
    registration = register(PARAMETERS, tmp_path / "artifacts", now=REGISTERED)
    template = json.loads(rating_template(data_path, registration, tmp_path / "artifacts", now=NOW).read_text())
    template.pop("template_status")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "source.txt").write_text("Invented source only: NOT real evidence")
    source = {"source_uri": "https://example.org/invented", "source_relative_path": "source.txt",
              "source_sha256": file_hash(evidence / "source.txt"), "source_locator": "invented page 1",
              "available_at": "2017-01-01T00:00:00+00:00", "retrieved_at": REGISTERED.isoformat(),
              "version_status": "verified_original", "original_version_basis": "synthetic fixture assertion only"}
    def review(value):
        return {"value": value, "rationale": "synthetic fixture mechanics only", "reviewer": "invented fixture reviewer",
                "reviewed_at": REVIEWED.isoformat(), "sources": [copy.deepcopy(source)]}
    for record in template["records"]:
        record.update(rating_batch_id="invented-batch", outcome_knowledge="exposed")
        high = int(record["observation_id"].split(":")[0]) <= 5
        record["ratings"] = {key: review(0 if key == "execution_risk" else 4 if high else 1) for key in NON_BUYER_FIELDS}
        universe = review(None)
        universe.pop("value")
        universe.update(buyer_ids=["zeta", "alpha"], completeness_attested=True)
        record["candidate_buyer_universe"] = universe
        record["buyer_reviews"] = {buyer: {"buyer_fit": review(4 if high else 1), "buyer_capacity": review(3)} for buyer in ("zeta", "alpha")}
    ratings = tmp_path / "ratings.json"
    ratings.write_text(json.dumps(template))
    return data_path, registration, ratings, evidence


def run_prepared(tmp_path, prepared_paths):
    data, registration, ratings, evidence = prepared_paths
    return run_experiment(data, registration, tmp_path / "runs", ratings_path=ratings, evidence_root=evidence, now=NOW)


def test_enough_support_end_to_end_same_folds_probability_null_and_immutable(tmp_path):
    paths = prepared(tmp_path)
    report, path = run_prepared(tmp_path, paths)
    assert report["status"] == "retrospective_experiment_evaluated_not_confirmed", report["readiness"]
    assert report["model_training_performed"] and report["weighted_model_evaluated"]
    assert report["outcome_exposed"] and not report["validated_predictive_edge"]
    assert not report["return_backtest_performed"] and not report["independent_confirmation"]
    financial = json.loads(Path(report["predictions"]["financial"]).read_text())
    for family in ("full", "science_only", "buyer_only"):
        panel = json.loads(Path(report["predictions"][family]).read_text())
        assert len(panel["observations"]) == len(financial["observations"]) == 50
        assert [(r["cik"], r["observation_at"], r["fold_id"], r["training_cutoff_at"]) for r in panel["observations"]] == [(r["cik"], r["observation_at"], r["fold_id"], r["training_cutoff_at"]) for r in financial["observations"]]
        assert all(r["probability"] is None and r["selected_buyer"] == "alpha" for r in panel["observations"])
        assert report["metrics"][family]["overall"]["pooled_row_diagnostics"]["probability_metrics"] is None
        assert report["metrics"][family]["input_sha256"] == file_hash(Path(report["predictions"][family]))
        assert report["metrics"][family]["primary_metric"]["value"] == 5
        baseline = report["metrics"][family]["by_year"]["2023"]["past_only_base_rate_comparator"]
        assert baseline["training_source"] == "actual_purged_fold_training_partition"
        assert baseline["training_observations"] == 25
    assert json.loads(path.read_text()) == report
    assert run_prepared(tmp_path, paths)[1] == path


@pytest.mark.parametrize("change,fragment", [
    ("future", "after observation"), ("missing", "No such file"), ("tampered", "hash mismatch"),
    ("outside", "escapes evidence_root"), ("symlink", "escapes evidence_root"),
    ("current_copy", "verified_original"), ("rubric", "rubric mismatch"),
    ("outcome", "outcome knowledge"), ("subset", "buyer subset"), ("before_registration", "after parameter registration"),
    ("retrieval_future", "retrieval"), ("null", "unknown/null"), ("boolean", "integer 0..4"),
    ("bindings", "binding mismatch"), ("hand_selected", "caller-selected"),
    ("duplicate", "duplicate observation"), ("universe", "unique candidate"),
])
def test_source_and_rating_gaps_block_every_family(tmp_path, change, fragment):
    paths = prepared(tmp_path)
    ratings = json.loads(paths[2].read_text())
    row = ratings["records"][0]
    rating = row["ratings"]["clinical_evidence"]
    source = rating["sources"][0]
    if change == "future": source["available_at"] = "2025-01-01T00:00:00+00:00"
    elif change == "missing": source["source_relative_path"] = "missing.txt"
    elif change == "tampered": (paths[3] / "source.txt").write_text("changed")
    elif change == "outside": source["source_relative_path"] = "../input.json"
    elif change == "symlink":
        (paths[3] / "escape").symlink_to(paths[0]); source["source_relative_path"] = "escape"
    elif change == "current_copy": source["version_status"] = "current_copy"
    elif change == "rubric": row["rubric_version"] = "different"
    elif change == "outcome": row["outcome_knowledge"] = None
    elif change == "subset": row["buyer_reviews"].pop("zeta")
    elif change == "before_registration": rating["reviewed_at"] = REGISTERED.isoformat()
    elif change == "retrieval_future": source["retrieved_at"] = NOW.isoformat()
    elif change == "null": rating["value"] = None
    elif change == "boolean": rating["value"] = True
    elif change == "bindings": ratings["dataset_sha256"] = "0" * 64
    elif change == "hand_selected": row["eventual_acquirer"] = "alpha"
    elif change == "duplicate": ratings["records"].append(copy.deepcopy(row))
    else: row["candidate_buyer_universe"]["buyer_ids"] = []
    paths[2].write_text(json.dumps(ratings))
    report, path = run_prepared(tmp_path, paths)
    assert fragment in " ".join(report["readiness"]["errors"])
    assert not report["model_training_performed"] and not report["weighted_model_evaluated"]
    assert report["predictions"] is report["metrics"] is None
    assert path.exists()


def test_parameters_and_registration_tamper_fail(tmp_path):
    config = json.loads(PARAMETERS.read_text())
    for key, value in (("k", True), ("horizon_days", 12), ("test_start_year", 2020), ("regularization_c", False)):
        invalid = {**config, key: value}
        with pytest.raises(TrainingBlocked): validate_parameters(invalid)
    config["weights"]["clinical_evidence"] = float("nan")
    with pytest.raises(TrainingBlocked): validate_parameters(config)
    paths = prepared(tmp_path)
    receipt = json.loads(paths[1].read_text())
    receipt["config"]["weights"]["clinical_evidence"] = .9
    paths[1].write_text(json.dumps(receipt))
    with pytest.raises(TrainingBlocked, match="digest/filename"): load_registration(paths[1], now=NOW)
    report, artifact = run_prepared(tmp_path, paths)
    assert report["metrics"] is None and artifact.exists()


def test_tampered_embedded_parameter_digest_even_rehashed_registration_blocks(tmp_path):
    paths = prepared(tmp_path)
    receipt = json.loads(paths[1].read_text())
    receipt["parameter_sha256"] = "0" * 64
    fake = write_immutable_json(receipt, tmp_path, "ma-registration")
    with pytest.raises(TrainingBlocked, match="embedded raw parameter digest"): load_registration(fake, now=NOW)


def test_readiness_reports_all_support_features_and_missing_ratings(tmp_path):
    paths = prepared(tmp_path)
    data = json.loads(paths[0].read_text())
    data["observations"] = [r for r in data["observations"] if r["cik"] <= 9]
    data["feature_names"].remove("assets_usd")
    data["feature_units"].pop("assets_usd")
    for row in data["observations"]:
        row["features"].pop("assets_usd")
    paths[0].write_text(json.dumps(data))
    report, _ = run_experiment(paths[0], paths[1], tmp_path / "runs", now=NOW)
    errors = " ".join(report["readiness"]["errors"])
    assert "missing ratings" in errors and "financial feature/units missing" in errors
    assert "fold-2023: insufficient distinct_negative_companies (4/20)" in errors
    assert "fold-2024: insufficient distinct_negative_companies (4/20)" in errors
    assert not report["model_training_performed"]


@pytest.mark.parametrize("change,fragment", [("single_class", "both training classes"), ("no_years", "(0/2)"), ("candidate", "unsupported event class")])
def test_class_year_and_candidate_failures(tmp_path, change, fragment):
    data = dataset()
    if change == "single_class": data["observations"] = [row for row in data["observations"] if row["cik"] <= 5]
    elif change == "no_years": data["observations"] = [row for row in data["observations"] if row["observation_at"][:4] < "2023"]
    else: data["observations"][0]["label"]["event_class"] = "licensing_interest"
    ready, _ = readiness(data, json.loads(PARAMETERS.read_text()), now=NOW)
    assert fragment in " ".join(ready["errors"])


def test_future_features_and_outcomes_do_not_change_earlier_fit():
    original = dataset()
    first = train_baseline(original, TrainingConfig(2023), now=NOW)["folds"][0]
    for row in original["observations"]:
        if row["observation_at"].startswith("2024"):
            row["features"] = {key: 1e12 for key in FINANCIAL_FEATURES}
            row["label"].update(event_class="no_change_of_control_announcement", announcement_at=None)
    later = train_baseline(original, TrainingConfig(2023), now=NOW)["folds"][0]
    assert first["model"] == later["model"]
    assert first["training_dataset_sha256"] == later["training_dataset_sha256"]


def test_new_regulator_basis_retains_other_publication_checks():
    from test_training import reconstructed_dataset
    from test_validation import reseal_sources
    data = reconstructed_dataset()
    label = data["observations"][0]["label"]
    source = label["historical_evidence_timing"]["sources"][0]
    source["publication_basis"] = "regulator_publication"
    reseal_sources(data["observations"][0])
    validate_training_data(data, now=NOW)
    source["publication_basis"] = "invented_publication"
    reseal_sources(data["observations"][0])
    with pytest.raises(TrainingBlocked, match="original public disclosure date"): validate_training_data(data, now=NOW)
    source["publication_basis"] = "regulator_publication"
    source["publication_date"] = "2027-01-01"
    reseal_sources(data["observations"][0])
    with pytest.raises(TrainingBlocked): validate_training_data(data, now=NOW)


def test_malformed_cli_inputs_persist_failure(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{ malformed")
    assert main(["register", "--parameters", str(bad), "--output-dir", str(tmp_path / "runs")]) == 2
    output = json.loads(capsys.readouterr().err)
    assert Path(output["artifact"]).exists() and output["metrics"] is None


def test_nullable_financial_features_preserve_imputation_and_full_cohort(tmp_path):
    paths = prepared(tmp_path)
    data = json.loads(paths[0].read_text())
    data["observations"][0]["features"]["cash_usd"] = None
    paths[0].write_text(json.dumps(data))
    ratings = json.loads(paths[2].read_text())
    ratings["dataset_sha256"] = file_hash(paths[0])
    paths[2].write_text(json.dumps(ratings))
    report, _ = run_prepared(tmp_path, paths)
    assert report["weighted_model_evaluated"], report["readiness"]
    training = json.loads(Path(report["artifacts"]["financial_training"]).read_text())
    assert training["folds"][0]["model"]["training_feature_observed_counts"][0] == 24
    assert all(len(json.loads(Path(path).read_text())["observations"]) == 50 for path in report["predictions"].values())


def test_weighted_clock_uses_all_candidate_sources_and_actual_review_separately(tmp_path):
    paths = prepared(tmp_path)
    ratings = json.loads(paths[2].read_text())
    heldout = next(row for row in ratings["records"] if row["observation_id"] == "1:2023-01-02")
    # Even the unselected tied candidate's source contributes to the conservative feature clock.
    heldout["buyer_reviews"]["zeta"]["buyer_capacity"]["sources"][0]["available_at"] = "2023-01-01T20:00:00+00:00"
    paths[2].write_text(json.dumps(ratings))
    report, _ = run_prepared(tmp_path, paths)
    assert report["weighted_model_evaluated"], report["readiness"]
    panel = json.loads(Path(report["predictions"]["full"]).read_text())
    raw = next(row for row in panel["observations"] if row["cik"] == 1 and row["observation_at"].startswith("2023"))
    assert raw["feature_max_available_at"] == raw["rating_source_max_available_at"] == "2023-01-01T20:00:00+00:00"
    assert raw["actual_rating_reviewed_through"] == REVIEWED.isoformat()
    assert raw["selected_buyer"] == "alpha"


@pytest.mark.parametrize("field,value", [("buyer_selection_rule", "eventual_acquirer"), ("score_families", {}),
    ("top_k_tie_policy", "custom"), ("undefined_metric_policy", "zero"), ("ablation_policy", "renormalize")])
def test_unregistered_selection_ablation_or_metric_policies_rejected(field, value):
    config = json.loads(PARAMETERS.read_text())
    config[field] = value
    with pytest.raises(TrainingBlocked, match="registered policy"):
        validate_parameters(config)


def test_unexpected_comparator_error_is_retained_without_empty_success(tmp_path, monkeypatch):
    import src.research.ma_experiment as experiment
    paths = prepared(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError("invented comparator failure")
    monkeypatch.setattr(experiment, "train_baseline", fail)
    report, artifact = run_prepared(tmp_path, paths)
    assert report["status"] == "blocked" and report["comparator_fit_attempted"]
    assert report["model_training_performed"] is False
    assert report["predictions"] is report["metrics"] is report["artifacts"] is None
    assert "invented comparator failure" in report["readiness"]["errors"][-1]
    assert artifact.exists()


def test_atomic_dataset_replacement_keeps_evaluated_bytes_and_digest_bound(tmp_path, monkeypatch):
    import hashlib
    paths = prepared(tmp_path)
    original_bytes = paths[0].read_bytes()
    original_digest = hashlib.sha256(original_bytes).hexdigest()
    original_data = json.loads(original_bytes)
    expected = train_baseline(original_data, TrainingConfig(2023), now=NOW)
    replacement_data = copy.deepcopy(original_data)
    replacement_data["observations"][0]["features"]["cash_usd"] = 5e12
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(replacement_data))
    read_bytes = Path.read_bytes
    replaced = False
    def replace_after_snapshot(path):
        nonlocal replaced
        snapshot = read_bytes(path)
        if path == paths[0] and not replaced:
            replacement.replace(paths[0])  # Deterministic atomic replacement; no timing assumptions.
            replaced = True
        return snapshot
    monkeypatch.setattr(Path, "read_bytes", replace_after_snapshot)
    report, artifact = run_prepared(tmp_path, paths)
    assert replaced and report["weighted_model_evaluated"], report["readiness"]
    assert report["hashes"]["dataset_sha256"] == original_digest
    assert file_hash(paths[0]) != original_digest
    training = json.loads(Path(report["artifacts"]["financial_training"]).read_text())
    assert training["hashes"]["dataset_sha256"] == original_digest
    assert training["dataset_sha256"] == expected["dataset_sha256"]
    assert training["folds"][0]["model"] == expected["folds"][0]["model"]
    assert json.loads(artifact.read_text())["hashes"]["dataset_sha256"] == original_digest


@pytest.mark.parametrize("family", ["full", "buyer_only"])
def test_exact_buyer_and_score_ties_obey_registered_id_order(tmp_path, family):
    from src.research.ma_diligence import POSITIVE_FIELDS, validate_ratings
    from src.research.metrics import RankedObservation, evaluate_rare_event_ranking
    config = json.loads(PARAMETERS.read_text())
    first = {name: 0 for name in (*POSITIVE_FIELDS, "execution_risk")}
    first.update(buyer_fit=4, buyer_capacity=1)
    second = {**first, "buyer_fit": 3, "buyer_capacity": 3}
    first_score, second_score = score(first, config, family), score(second, config, family)
    assert first_score == second_score == 22.5
    # Four higher-score rows put the mathematically tied pair at the primary k=5 boundary.
    # Reverse input order so only the registered observation ID policy selects the positive.
    ranked = [RankedObservation("2:2023-01-02", second_score, False),
              *(RankedObservation(f"higher-{index}", 100, False) for index in range(4)),
              RankedObservation("1:2023-01-02", first_score, True)]
    metrics = evaluate_rare_event_ranking(ranked, cutoffs=(5,))
    assert metrics["top_k"]["5"]["captured_positives"] == 1
    assert metrics["top_k"]["5"]["lift_over_base_rate"] == pytest.approx(1.2)
    paths = prepared(tmp_path)
    ratings = json.loads(paths[2].read_text())
    record = ratings["records"][0]
    record["buyer_reviews"]["alpha"]["buyer_fit"]["value"] = 4
    record["buyer_reviews"]["alpha"]["buyer_capacity"]["value"] = 1
    record["buyer_reviews"]["zeta"]["buyer_fit"]["value"] = 3
    record["buyer_reviews"]["zeta"]["buyer_capacity"]["value"] = 3
    _, rows = validate_training_data(json.loads(paths[0].read_bytes()), now=NOW)
    receipt = load_registration(paths[1], now=NOW)
    scored, errors = validate_ratings(ratings, rows, dataset_sha256=file_hash(paths[0]),
        parameter_sha256=receipt["parameter_sha256"], registration_sha256=file_hash(paths[1]),
        registered_at=REGISTERED, now=NOW, evidence_root=paths[3])
    assert not errors
    assert scored[record["observation_id"]]["selected_buyer"] == "alpha"


def test_valid_market_enriched_input_fits_financial_subset_without_market_contract(tmp_path):
    from src.research.market_contract import market_feature_contract
    from src.research.market_features import FEATURE_UNITS
    paths = prepared(tmp_path)
    data = json.loads(paths[0].read_bytes())
    data["feature_names"] += list(FEATURE_UNITS)
    data["feature_units"].update(FEATURE_UNITS)
    data["market_data_contract"] = market_feature_contract("sip")
    for row in data["observations"]:
        row["features"].update({name: None for name in FEATURE_UNITS})
    validate_training_data(data, now=NOW)  # Full input has an admissible market contract.
    paths[0].write_text(json.dumps(data))
    ratings = json.loads(paths[2].read_bytes())
    ratings["dataset_sha256"] = file_hash(paths[0])
    paths[2].write_text(json.dumps(ratings))
    report, _ = run_prepared(tmp_path, paths)
    assert report["weighted_model_evaluated"], report["readiness"]
    training = json.loads(Path(report["artifacts"]["financial_training"]).read_bytes())
    assert training["final_model"]["feature_names"] == list(FINANCIAL_FEATURES)
    assert "market_data_contract" not in training["final_model"]
    assert all("market_data_contract" not in fold["model"] for fold in training["folds"])
    assert all(len(json.loads(Path(path).read_bytes())["observations"]) == 50 for path in report["predictions"].values())
