"""Validate externally supplied historical prediction panels before evaluation.

This module trains no model and reconstructs no labels, features, or exchange
membership. It checks the supplied provenance and chronology; it cannot
independently authenticate a provider's historical data or a sealing timestamp.
Retrospective evaluation never qualifies as a forward performance record.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from src.research.metrics import RankedObservation, evaluate_rare_event_ranking
from src.research.adjudication import announcement_bounds

PANEL_SCHEMA = "sealed-company-predictions-v1"
EVALUATOR_VERSION = "historical-panel-validation-v4"
MODES = {"retrospective_out_of_time", "forward"}
RECORDED_LABEL_TIMING = "recorded_availability"
RETROSPECTIVE_LABEL_TIMING = "retrospective_primary_evidence_v1"
LABEL_TIMING_POLICIES = {RECORDED_LABEL_TIMING, RETROSPECTIVE_LABEL_TIMING}
PRIMARY_SOURCE_FAMILIES = {"issuer_news", "regulatory_filings", "exchange_notices"}


class PanelValidationError(ValueError):
    """The supplied panel cannot support an eligible evaluation."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PanelValidationError(message)


def _timestamp(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PanelValidationError(f"{field}: timezone-aware ISO timestamp required") from exc
    _require(parsed.tzinfo is not None, f"{field}: timezone required")
    return parsed.astimezone(timezone.utc)


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field}: nonempty string required")
    return value.strip()


def _hash(value: Any, field: str) -> str:
    value = _text(value, field)
    _require(len(value) == 64 and all(ch in "0123456789abcdef" for ch in value),
             f"{field}: lowercase SHA-256 required")
    return value


def _finite(value: Any, field: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{field}: finite number required")
    _require(math.isfinite(value), f"{field}: finite number required")
    return float(value)


def _provenance(value: Any, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{field}: provenance object required")
    _text(value.get("source_uri"), f"{field}.source_uri")
    _hash(value.get("source_sha256"), f"{field}.source_sha256")
    return value


def _json_sha256(value: Any) -> str:
    """Bind the source identities, versions and publication annotations together."""
    try:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise PanelValidationError("historical source manifest must be finite JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _https_source(value: Any, name: str):
    try:
        uri = urlsplit(_text(value, name))
        _require(uri.scheme == "https" and bool(uri.hostname) and not uri.username and not uri.password,
                 f"{name}: primary source must have a public HTTPS reference")
    except ValueError as exc:
        raise PanelValidationError(f"{name}: valid public HTTPS source required") from exc
    return uri


def _original_source_version(source: dict[str, Any], name: str, reviewed: datetime) -> None:
    _require(source.get("version_status") == "verified_original",
             f"{name}: unknown or revised source cannot inherit original publication time")
    kind = source.get("source_sha256_kind")
    if kind == "original_document_bytes":
        if source.get("original_source_sha256") is not None:
            _require(source["original_source_sha256"] == source["source_sha256"],
                     f"{name}: original source byte hash disagrees with source hash")
        return
    _require(kind == "source_review_receipt", f"{name}: original bytes or explicit browser review receipt required")
    _require("original_source_sha256" in source and source["original_source_sha256"] is None,
             f"{name}: browser review must explicitly leave original source hash unavailable")
    uri = _https_source(source.get("immutable_document_uri"), f"{name}.immutable_document_uri")
    parts = uri.path.strip("/").split("/")
    _require(source.get("immutable_document_uri") == source["source_uri"]
             and uri.scheme == "https" and uri.hostname in {"sec.gov", "www.sec.gov"}
             and not uri.query and not uri.fragment
             and len(parts) == 6 and parts[:3] == ["Archives", "edgar", "data"]
             and parts[3].isdigit() and len(parts[4]) == 18 and parts[4].isdigit()
             and source.get("source_family") == "regulatory_filings",
             f"{name}: browser-only receipt requires an immutable SEC accession/document reference")
    _text(source.get("review_receipt_uri"), f"{name}.review_receipt_uri")
    filer_cik = int(parts[3])
    if "document_filer_cik" in source:
        _require(isinstance(source["document_filer_cik"], int) and not isinstance(source["document_filer_cik"], bool)
                 and source["document_filer_cik"] == filer_cik, f"{name}: document filer CIK differs from accession path")
    different_filer = filer_cik != source["subject_cik"]
    if different_filer:
        _require(source.get("document_filer_cik") == filer_cik,
                 f"{name}: acquirer/other-filer source requires explicit document_filer_cik")
        identity = _provenance(source.get("subject_identity_evidence"), f"{name}.subject_identity_evidence")
        _text(identity.get("source_locator"), f"{name}.subject_identity_evidence.source_locator")
    annotation = source.get("review_annotation")
    _require(isinstance(annotation, dict), f"{name}: bound browser review annotation required")
    _require(_json_sha256(annotation) == source["source_sha256"], f"{name}: browser review annotation hash mismatch")
    for field in ("source_uri", "subject_cik", "version_status", "source_locator", "publication_basis",
                  "publication_timestamp_precision", "publication_date", "published_at", "retrieved_at"):
        _require(field in annotation and annotation[field] == source.get(field),
                 f"{name}: browser review annotation {field} mismatch")
    if different_filer:
        for field in ("document_filer_cik", "subject_identity_evidence"):
            _require(annotation.get(field) == source[field], f"{name}: browser review annotation {field} mismatch")
    _text(annotation.get("evidence_paraphrase"), f"{name}.review_annotation.evidence_paraphrase")
    _text(annotation.get("reviewer"), f"{name}.review_annotation.reviewer")
    annotated_at = _timestamp(annotation.get("reviewed_at"), f"{name}.review_annotation.reviewed_at")
    _require(_timestamp(source.get("retrieved_at"), f"{name}.retrieved_at") <= annotated_at <= reviewed,
             f"{name}: browser review annotation chronology is inconsistent")


def _retrospective_sampling(panel: dict[str, Any], data_as_of: datetime) -> datetime:
    sampling = _provenance(panel.get("historical_sampling_frame"), "historical_sampling_frame")
    _require(isinstance(sampling.get("selection_basis"), str)
             and sampling["selection_basis"] in {"historical_exchange_constituents", "predeclared_historical_sampling_frame"},
             "historical_sampling_frame: historical population selection required")
    for field in ("uses_current_listing_status", "uses_future_outcomes"):
        _require(sampling.get(field) is False, f"historical_sampling_frame.{field}: must explicitly be false")
    _require(sampling.get("includes_subsequently_delisted") is True,
             "historical_sampling_frame: subsequently delisted issuers must remain in the sampling frame")
    _text(sampling.get("selection_rule"), "historical_sampling_frame.selection_rule")
    _text(sampling.get("source_locator"), "historical_sampling_frame.source_locator")
    retrieved = _timestamp(sampling.get("retrieved_at"), "historical_sampling_frame.retrieved_at")
    reviewed = _timestamp(sampling.get("reviewed_at"), "historical_sampling_frame.reviewed_at")
    population_at = _timestamp(sampling.get("population_as_of_at"), "historical_sampling_frame.population_as_of_at")
    _require(population_at <= retrieved <= reviewed <= data_as_of,
             "historical_sampling_frame: population/retrieval/review chronology is inconsistent")
    return population_at


def _historical_label_timing(label: dict[str, Any], *, policy: str, cik: int,
                             observation_at: datetime, horizon_end: datetime,
                             announcement_lower: datetime | None, announcement_upper: datetime | None, available_at: datetime,
                             data_as_of: datetime, prefix: str) -> tuple[datetime, datetime | None]:
    """Derive a retrospective training clock; never replace the actual review clock.

    These are checked source attestations, not independently authenticated history.
    The current inventory can be reconstructed now. All underlying material needed
    for the outcome must have verified original-version publication provenance.
    """
    receipt = label.get("historical_evidence_timing")
    reviewed = None
    if label.get("reviewed_at") is not None:
        reviewed = _timestamp(label["reviewed_at"], f"{prefix}.reviewed_at")
        _require(reviewed <= available_at, f"{prefix}: assembled label availability precedes actual review")
    if label.get("retrieved_at") is not None:
        _require(_timestamp(label["retrieved_at"], f"{prefix}.retrieved_at") <= (reviewed or available_at),
                 f"{prefix}: label retrieval follows declared review/availability")
    if receipt is None:
        return available_at, reviewed
    _require(policy == RETROSPECTIVE_LABEL_TIMING,
             f"{prefix}: historical evidence timing requires explicit retrospective label policy")
    _require(isinstance(receipt, dict) and receipt.get("schema_version") == "retrospective-label-evidence-v1",
             f"{prefix}: unsupported historical label timing receipt")
    _require(reviewed is not None, f"{prefix}: actual reviewed_at required for reconstruction")
    _require(receipt.get("review_id") == label["review_id"]
             and receipt.get("label_source_sha256") == label["source_sha256"],
             f"{prefix}: historical receipt must bind the reviewed label")
    _require(not isinstance(receipt.get("cik"), bool) and str(receipt.get("cik")).isdigit()
             and int(receipt["cik"]) == cik, f"{prefix}: historical receipt CIK mismatch")
    _require(receipt.get("event_class") == label["event_class"], f"{prefix}: historical receipt event mismatch")
    _require(_timestamp(receipt.get("observation_at"), f"{prefix}.timing.observation_at") == observation_at
             and _timestamp(receipt.get("horizon_end_at"), f"{prefix}.timing.horizon_end_at") == horizon_end,
             f"{prefix}: historical receipt observation/window mismatch")
    _require(_timestamp(receipt.get("reviewed_at"), f"{prefix}.timing.reviewed_at") == reviewed,
             f"{prefix}: historical receipt actual review time mismatch")
    _text(receipt.get("reviewer"), f"{prefix}.timing.reviewer")
    _require(reviewed <= available_at <= data_as_of, f"{prefix}: actual review unavailable at dataset freeze")
    sources = receipt.get("sources")
    _require(isinstance(sources, list) and bool(sources), f"{prefix}: original primary sources required")
    _require(_hash(receipt.get("sources_sha256"), f"{prefix}.timing.sources_sha256") == _json_sha256(sources),
             f"{prefix}: historical source manifest hash mismatch")
    source_ids, families, publication_ends, publication_bounds = set(), set(), [], {}
    for index, raw_source in enumerate(sources):
        name = f"{prefix}.timing.sources[{index}]"
        source = _provenance(raw_source, name)
        source_id = _text(source.get("source_id"), f"{name}.source_id")
        _require(source_id not in source_ids, f"{name}: duplicate historical source ID")
        source_ids.add(source_id)
        _https_source(source["source_uri"], f"{name}.source_uri")
        _require(isinstance(source.get("source_family"), str) and source["source_family"] in PRIMARY_SOURCE_FAMILIES,
                 f"{name}: issuer, regulator or exchange primary source required")
        families.add(source["source_family"])
        _require(isinstance(source.get("subject_cik"), int) and not isinstance(source["subject_cik"], bool)
                 and source["subject_cik"] == cik,
                 f"{name}: primary source subject CIK mismatch")
        _original_source_version(source, name, reviewed)
        _text(source.get("source_locator"), f"{name}.source_locator")
        for field in ("publication_evidence", "original_version_evidence"):
            evidence = _provenance(source.get(field), f"{name}.{field}")
            _text(evidence.get("source_locator"), f"{name}.{field}.source_locator")
        _require(isinstance(source.get("publication_basis"), str)
                 and source["publication_basis"] in {"issuer_publication", "regulator_acceptance", "exchange_publication"},
                 f"{name}: original public disclosure date required; period ends and signatures are insufficient")
        _require(isinstance(source.get("publication_timestamp_precision"), str)
                 and source["publication_timestamp_precision"] in {"date", "timestamp"},
                 f"{name}: explicit publication timestamp precision required")
        try:
            _, _, lower, upper = announcement_bounds({
                "announcement_at": source.get("published_at"), "announcement_date": source.get("publication_date"),
                "timestamp_precision": source["publication_timestamp_precision"]})
        except (TypeError, ValueError) as exc:
            raise PanelValidationError(f"{name}: invalid original publication evidence: {exc}") from exc
        for field, expected in (("publication_lower_at", lower), ("publication_upper_at", upper)):
            if source.get(field) is not None:
                _require(_timestamp(source[field], f"{name}.{field}") == expected,
                         f"{name}: publication interval must preserve source date uncertainty")
        retrieved = _timestamp(source.get("retrieved_at"), f"{name}.retrieved_at")
        _require(upper <= retrieved <= reviewed, f"{name}: publication/retrieval/review chronology is inconsistent")
        publication_ends.append(upper)
        publication_bounds[source_id] = (lower, upper)
    if announcement_upper is None:
        coverage = _provenance(receipt.get("coverage"), f"{prefix}.timing.coverage")
        _require(coverage.get("kind") == "complete_designated_primary_corpus",
                 f"{prefix}: complete designated negative-outcome corpus required")
        for field in ("inventory_complete", "full_text_review_complete", "censoring_review_complete"):
            _require(coverage.get(field) is True, f"{prefix}.coverage.{field}: complete coverage required")
        for field in ("known_missing_sources", "qualifying_control_event_found", "censoring_event_found"):
            _require(coverage.get(field) is False, f"{prefix}.coverage.{field}: unresolved or contradictory negative coverage")
        _require(_timestamp(coverage.get("window_start_at"), f"{prefix}.coverage.window_start_at") <= observation_at
                 and _timestamp(coverage.get("window_end_at"), f"{prefix}.coverage.window_end_at") >= horizon_end,
                 f"{prefix}: negative coverage does not span the full outcome window")
        required_ids = coverage.get("required_source_ids")
        _require(isinstance(required_ids, list) and all(isinstance(value, str) for value in required_ids)
                 and len(required_ids) == len(set(required_ids)) and set(required_ids) == source_ids,
                 f"{prefix}: required coverage sources and original publication inventory differ")
        declared_families = coverage.get("source_families")
        _require(isinstance(declared_families, list) and all(isinstance(value, str) for value in declared_families)
                 and set(declared_families) == families,
                 f"{prefix}: negative source-family coverage mismatch")
        for field in ("scope", "removed_page_limitations"):
            _text(coverage.get(field), f"{prefix}.coverage.{field}")
        inventory_at = _timestamp(coverage.get("retrieved_at"), f"{prefix}.coverage.retrieved_at")
        coverage_end = _timestamp(coverage["window_end_at"], f"{prefix}.coverage.window_end_at")
        _require(horizon_end <= coverage_end <= inventory_at <= reviewed,
                 f"{prefix}: complete negative inventory must follow horizon maturity and precede review")
        # A declared reporting-lag search cannot become available before its
        # own endpoint, even when its last nonempty disclosure was earlier.
        publication_ends.append(coverage_end)
        if coverage.get("ascertainment_complete_at") is not None:
            ascertainment = _timestamp(coverage["ascertainment_complete_at"], f"{prefix}.coverage.ascertainment_complete_at")
            _require(coverage_end <= ascertainment <= inventory_at,
                     f"{prefix}: ascertainment completion must follow coverage end and precede actual inventory retrieval")
            publication_ends.append(ascertainment)
    else:
        _require(isinstance(receipt.get("announcement_source_id"), str)
                 and receipt["announcement_source_id"] in source_ids,
                 f"{prefix}: positive announcement must identify its original primary source")
        source_lower, source_upper = publication_bounds[receipt["announcement_source_id"]]
        _require(announcement_lower <= source_lower <= source_upper <= announcement_upper,
                 f"{prefix}: original announcement source publication does not substantiate the announcement interval")
    earliest = max(horizon_end, *publication_ends)
    _require(earliest <= reviewed, f"{prefix}: historical outcome evidence follows actual review")
    if receipt.get("historical_evidence_available_at") is not None:
        _require(_timestamp(receipt["historical_evidence_available_at"], f"{prefix}.timing.historical_evidence_available_at") == earliest,
                 f"{prefix}: historical availability must equal maturity and latest required original disclosure")
    return earliest, reviewed


def validate_panel(panel: Any, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Fail the entire panel on invalid rows; never silently select passing rows."""
    _require(isinstance(panel, dict), "panel must be a JSON object")
    _require(panel.get("schema_version") == PANEL_SCHEMA, f"schema_version must be {PANEL_SCHEMA}")
    mode = panel.get("evaluation_mode")
    _require(isinstance(mode, str) and mode in MODES, "evaluation_mode must explicitly be retrospective_out_of_time or forward")
    timing_policy = panel.get("label_timing_policy", RECORDED_LABEL_TIMING)
    _require(isinstance(timing_policy, str) and timing_policy in LABEL_TIMING_POLICIES,
             "unsupported label_timing_policy")
    _require(timing_policy != RETROSPECTIVE_LABEL_TIMING or mode == "retrospective_out_of_time",
             "retrospective label reconstruction cannot become forward evidence")
    data_as_of = _timestamp(panel.get("data_as_of"), "data_as_of")
    current_time = _timestamp(now or datetime.now(timezone.utc), "now")
    _require(data_as_of <= current_time, "data_as_of cannot be later than current UTC time")
    population_at = _retrospective_sampling(panel, data_as_of) if timing_policy == RETROSPECTIVE_LABEL_TIMING else None
    raw_rows = panel.get("observations")
    _require(isinstance(raw_rows, list) and bool(raw_rows), "no eligible historical prediction observations supplied")
    identities: set[tuple[int, str]] = set()
    folds: dict[str, tuple[datetime, str, str]] = {}
    cohort_cutoffs: dict[str, tuple[datetime, datetime]] = {}
    normalized: list[dict[str, Any]] = []
    horizon_set: set[int] = set()
    for index, row in enumerate(raw_rows):
        prefix = f"observations[{index}]"
        _require(isinstance(row, dict), f"{prefix}: object required")
        raw_cik = row.get("cik")
        _require(not isinstance(raw_cik, bool) and str(raw_cik).isdigit(), f"{prefix}.cik: positive integer required")
        cik = int(raw_cik)
        _require(cik > 0, f"{prefix}.cik: positive integer required")
        observation_at = _timestamp(row.get("observation_at"), f"{prefix}.observation_at")
        _require(population_at is None or population_at <= observation_at,
                 f"{prefix}: historical sampling frame follows observation")
        identity = (cik, observation_at.date().isoformat())
        _require(identity not in identities, f"{prefix}: duplicate CIK/observation date")
        identities.add(identity)
        cutoff = _timestamp(row.get("information_cutoff_at"), f"{prefix}.information_cutoff_at")
        cohort_key = observation_at.date().isoformat()
        cohort_contract = (observation_at, cutoff)
        _require(cohort_key not in cohort_cutoffs or cohort_cutoffs[cohort_key] == cohort_contract,
                 f"{prefix}: companies on an observation date must share the same observation and information cutoff")
        cohort_cutoffs[cohort_key] = cohort_contract
        feature_available = _timestamp(row.get("feature_max_available_at"), f"{prefix}.feature_max_available_at")
        training_cutoff = _timestamp(row.get("training_cutoff_at"), f"{prefix}.training_cutoff_at")
        training_available = _timestamp(row.get("training_outcomes_available_through"), f"{prefix}.training_outcomes_available_through")
        _require(feature_available <= cutoff < observation_at, f"{prefix}: features/cutoff must precede observation")
        _require(training_available <= training_cutoff <= cutoff, f"{prefix}: training outcomes leak beyond fold cutoff")
        _require(row.get("split_method") in ("expanding_window", "rolling_window"), f"{prefix}: chronological expanding/rolling window split required")
        fold_id = _text(row.get("fold_id"), f"{prefix}.fold_id")
        model_version = _text(row.get("model_version"), f"{prefix}.model_version")
        training_hash = _hash(row.get("training_dataset_sha256"), f"{prefix}.training_dataset_sha256")
        _hash(row.get("feature_snapshot_sha256"), f"{prefix}.feature_snapshot_sha256")
        fold_contract = (training_cutoff, training_hash, model_version)
        _require(fold_id not in folds or folds[fold_id] == fold_contract,
                 f"{prefix}: fold training lineage is inconsistent")
        folds[fold_id] = fold_contract
        generated = _timestamp(row.get("prediction_generated_at"), f"{prefix}.prediction_generated_at")
        sealed = _timestamp(row.get("prediction_sealed_at"), f"{prefix}.prediction_sealed_at")
        _require(cutoff <= generated <= sealed, f"{prefix}: generated/sealed timestamps are inconsistent with cutoff")
        _require(generated <= current_time and sealed <= current_time,
                 f"{prefix}: prediction generation/sealing cannot be later than current UTC time")
        if mode == "forward":
            _require(sealed <= observation_at, f"{prefix}: forward prediction was not sealed by observation")
        horizon = row.get("horizon_days")
        _require(isinstance(horizon, int) and not isinstance(horizon, bool) and 1 <= horizon <= 3650,
                 f"{prefix}.horizon_days: integer from 1 to 3650 required")
        horizon_set.add(horizon)
        horizon_end = observation_at + timedelta(days=horizon)
        _require(horizon_end <= data_as_of, f"{prefix}: censored or immature outcome horizon")
        _require(row.get("risk_set_eligible") is True and not row.get("risk_set_exclusion_reason"),
                 f"{prefix}: excluded or unconfirmed prediction risk-set eligibility")
        membership = _provenance(row.get("membership"), f"{prefix}.membership")
        _require(membership.get("kind") == "historical_exchange_membership",
                 f"{prefix}: actual historical exchange membership required; annual SEC proxies are ineligible")
        _require(membership.get("security_type") == "common_equity" and membership.get("biotech_eligible") is True,
                 f"{prefix}: historical operating biotech common-equity eligibility required")
        member_from = _timestamp(membership.get("valid_from"), f"{prefix}.membership.valid_from")
        member_until = _timestamp(membership.get("valid_until"), f"{prefix}.membership.valid_until")
        _require(member_from <= observation_at < member_until, f"{prefix}: issuer outside historical listing interval")
        label = _provenance(row.get("label"), f"{prefix}.label")
        _require(label.get("reviewed") is True, f"{prefix}: outcome label is not reviewed")
        _text(label.get("review_id"), f"{prefix}.label.review_id")
        observed_through = _timestamp(label.get("observed_through"), f"{prefix}.label.observed_through")
        _require(horizon_end <= observed_through <= data_as_of, f"{prefix}: label outcome window is censored or beyond data_as_of")
        label_available = _timestamp(label.get("available_at"), f"{prefix}.label.available_at")
        _require(label_available <= data_as_of, f"{prefix}: label unavailable by data_as_of")
        event_class = label.get("event_class")
        _require(event_class in ("change_of_control_announcement", "no_change_of_control_announcement"),
                 f"{prefix}: unadjudicated or unsupported event class")
        positive = event_class == "change_of_control_announcement"
        event_id = None
        lower = upper = None
        if positive:
            try:
                _, announcement_date, lower, upper = announcement_bounds(label)
            except ValueError as exc:
                raise PanelValidationError(f"{prefix}.label: {exc}") from exc
            for name, bound in (("announcement_lower_at", lower), ("announcement_upper_at", upper)):
                if label.get(name) is not None:
                    _require(_timestamp(label[name], name) == bound, f"{prefix}: announcement interval must preserve source date uncertainty")
            event_id = f"{cik}:{announcement_date}"
            _require(observation_at < lower and upper <= horizon_end, f"{prefix}: announcement must follow observation and fall in horizon, including date uncertainty")
            _require(upper < member_until and upper <= label_available,
                     f"{prefix}: announcement follows delisting or label availability")
            if mode == "forward":
                _require(sealed < lower, f"{prefix}: forward seal must precede outcome")
        else:
            _require(all(label.get(key) is None for key in ("announcement_at", "announced_at", "first_public_announcement_at", "announcement_date", "announcement_lower_at", "announcement_upper_at")),
                     f"{prefix}: negative label contradicts announcement timestamp or date")
            _require(member_until >= horizon_end, f"{prefix}: membership ends before horizon; competing-event/censoring treatment required")
            _require(horizon_end <= label_available, f"{prefix}: negative label available before horizon maturity")
        training_label_available, label_reviewed = _historical_label_timing(
            label, policy=timing_policy, cik=cik, observation_at=observation_at, horizon_end=horizon_end,
            announcement_lower=lower, announcement_upper=upper, available_at=label_available,
            data_as_of=data_as_of, prefix=f"{prefix}.label")
        score = _finite(row.get("score"), f"{prefix}.score")
        probability = row.get("probability")
        if probability is not None:
            probability = _finite(probability, f"{prefix}.probability")
            _require(0 <= probability <= 1, f"{prefix}.probability: outside [0, 1]")
        normalized.append({"cik": cik, "observation_at": observation_at,
                           "horizon_end": horizon_end, "label_available_at": label_available,
                           "label_training_available_at": training_label_available,
                           "label_reviewed_at": label_reviewed,
                           "label_timing_basis": RETROSPECTIVE_LABEL_TIMING if label.get("historical_evidence_timing") is not None else RECORDED_LABEL_TIMING,
                           "cutoff": cutoff, "fold_id": fold_id, "score": score,
                           "probability": probability, "label": positive,
                           "event_id": event_id,
                           "observation_id": f"{cik}:{identity[1]}"})
    _require(len(horizon_set) == 1, "mixed prediction horizons require separate evaluations")
    return sorted(normalized, key=lambda row: (row["observation_at"], row["cik"]))


def calibration_bins(observations: list[RankedObservation], bins: int = 10) -> list[dict[str, Any]] | None:
    """Report all equal-width bins, including empty bins with null rates."""
    if not observations or any(row.probability is None for row in observations):
        return None
    groups: dict[int, list[RankedObservation]] = defaultdict(list)
    for row in observations:
        groups[min(int(float(row.probability) * bins), bins - 1)].append(row)
    results = []
    for index in range(bins):
        group = groups[index]
        results.append({"lower": index / bins, "upper": (index + 1) / bins,
                        "count": len(group), "positives": sum(row.label for row in group),
                        "mean_probability": sum(float(row.probability) for row in group) / len(group) if group else None,
                        "observed_rate": sum(row.label for row in group) / len(group) if group else None})
    return results


def _metrics(rows: list[dict[str, Any]], *, cross_sectional: bool = False) -> dict[str, Any]:
    observations = [RankedObservation(row["observation_id"], row["score"], row["label"], row["probability"]) for row in rows]
    result = evaluate_rare_event_ranking(observations, cutoffs=(10, 20))
    result["calibration_bins"] = calibration_bins(observations)
    result["probability_rows"] = sum(row.probability is not None for row in observations)
    result["positive_support_status"] = "observed_positives" if result["positives"] else "no_positive_events"
    if not result["positives"]:
        for cutoff in result["top_k"].values():
            cutoff["recall"] = None
            cutoff["lift_over_base_rate"] = None
    result["sample_unit"] = "company_at_observation_cutoff" if cross_sectional else "company_observation"
    result["metric_semantics"] = "cross_sectional_watchlist" if cross_sectional else "pooled_row_diagnostics"
    if not cross_sectional:
        result["top_k"] = None
    return result


def _cohorts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cohorts[row["observation_at"].date().isoformat()].append(row)
    return dict(sorted(cohorts.items()))


def _cohort_aggregate(cohorts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    metrics = [_metrics(rows, cross_sectional=True) for rows in cohorts.values()]
    top_k = {}
    for k in ("10", "20"):
        supported = [result["top_k"][k] for result in metrics if result["positives"]]
        top_k[k] = {
            "mean_precision": sum(result["top_k"][k]["precision"] for result in metrics) / len(metrics),
            "mean_recall": sum(item["recall"] for item in supported) / len(supported) if supported else None,
            "mean_lift_over_base_rate": sum(item["lift_over_base_rate"] for item in supported) / len(supported) if supported else None,
            "positive_supported_cohorts": len(supported),
            "effective_k_min": min(result["top_k"][k]["effective_k"] for result in metrics),
            "effective_k_max": max(result["top_k"][k]["effective_k"] for result in metrics),
        }
    return {"cohort_count": len(metrics), "weighting": "equal_weight_per_observation_date",
            "undefined_metric_policy": "recall and lift omit cohorts without positive events; support counts are reported",
            "mean_company_observation_base_rate": sum(result["base_rate"] for result in metrics) / len(metrics),
            "top_k": top_k}


def _distinct_deal_capture(cohorts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    events = {row["event_id"] for rows in cohorts.values() for row in rows if row["event_id"]}
    result = {"event_identity": "CIK and source announcement calendar date (UTC date when source date absent)",
              "distinct_positive_events": len(events), "event_ids": sorted(events), "top_k": {}}
    for k in (10, 20):
        captured = set()
        for rows in cohorts.values():
            ranked = sorted(rows, key=lambda row: (-row["score"], row["observation_id"]))
            captured.update(row["event_id"] for row in ranked[:k] if row["event_id"])
        result["top_k"][str(k)] = {"distinct_events_captured": len(captured),
                                   "distinct_event_recall": len(captured) / len(events) if events else None,
                                   "captured_event_ids": sorted(captured)}
    return result


def evaluate_panel(panel: Any, *, input_sha256: str, now: datetime | None = None) -> dict[str, Any]:
    rows = validate_panel(panel, now=now)
    _hash(input_sha256, "input_sha256")
    years: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        years[str(row["observation_at"].year)].append(row)
    by_year: dict[str, Any] = {}
    for year, year_rows in sorted(years.items()):
        year_cohorts = _cohorts(year_rows)
        result = {"pooled_row_diagnostics": _metrics(year_rows),
                  "cohort_aggregate": _cohort_aggregate(year_cohorts),
                  "distinct_deal_capture": _distinct_deal_capture(year_cohorts)}
        cutoff = min(row["cutoff"] for row in year_rows)
        past = [row for row in rows if row["horizon_end"] <= cutoff
                and row["label_training_available_at"] <= cutoff
                and row["observation_at"] < year_rows[0]["observation_at"]]
        if past:
            base_rate = sum(row["label"] for row in past) / len(past)
            baseline = [{**row, "score": base_rate, "probability": base_rate} for row in year_rows]
            baseline_metrics = _metrics(baseline)
            baseline_metrics["top_k"] = None
            baseline_metrics["ranking_status"] = "constant_probability_has_no_ranking_discrimination"
            result["past_only_base_rate_comparator"] = {"training_observations": len(past), "probability": base_rate,
                                                        "probability_semantics": "mature_company_observation_event_rate; not a unique-deal rate",
                                                        "metrics": baseline_metrics}
        else:
            result["past_only_base_rate_comparator"] = {"training_observations": 0, "probability": None, "metrics": None,
                                                        "status": "unavailable_no_mature_prior_outcomes"}
        by_year[year] = result
    evaluation_id = hashlib.sha256(f"{EVALUATOR_VERSION}|{input_sha256}".encode()).hexdigest()
    return {"schema_version": EVALUATOR_VERSION, "evaluation_id": evaluation_id,
            "input_sha256": input_sha256, "evaluation_mode": panel["evaluation_mode"],
            "label_timing_policy": panel.get("label_timing_policy", RECORDED_LABEL_TIMING),
            "reconstructed_label_observations": sum(row["label_timing_basis"] == RETROSPECTIVE_LABEL_TIMING for row in rows),
            "label_timing_semantics": "Actual label availability is retained; explicit retrospective reconstruction uses horizon maturity and the latest required original primary disclosure for training chronology. It does not assert a historical review or forward seal.",
            "validation_status": "external_panel_contract_passed",
            "evidence_type": "forward_sealed_panel" if panel["evaluation_mode"] == "forward" else "retrospective_out_of_time_panel",
            "source_attestation": "externally supplied; payloads and sealing authority not independently authenticated",
            "validated_predictive_edge": False, "model_training_performed": False,
            "data_as_of": panel["data_as_of"], "horizon_days": panel["observations"][0]["horizon_days"],
            "folds": sorted({row["fold_id"] for row in rows}),
            "overall": {"pooled_row_diagnostics": _metrics(rows),
                        "cohort_aggregate": _cohort_aggregate(_cohorts(rows)),
                        "distinct_deal_capture": _distinct_deal_capture(_cohorts(rows))},
            "per_cohort": {key: {"observation_at": values[0]["observation_at"].isoformat(),
                                  "information_cutoff_at": values[0]["cutoff"].isoformat(),
                                  **_metrics(values, cross_sectional=True)}
                           for key, values in _cohorts(rows).items()},
            "by_year": by_year,
            "limitations": ["Passing the input contract does not establish predictive edge or capital eligibility.",
                            "Retrospective original-version, sampling and designated-source completeness assertions require external audit; present archives cannot independently rule out removed pages.",
                            "Top-k is calculated within each observation-date cohort and averaged with equal cohort weights.",
                            "Pooled AP, calibration, and base rates describe company-observation rows, not independent or unique deals.",
                            "Distinct event capture counts each CIK/announcement once across selected cohorts; per-year event totals may overlap.",
                            "No uncertainty intervals, model fitting, or economic-return validation is performed."]}


def write_evaluation(panel_path: Path, output_dir: Path) -> Path:
    """Write a deterministic immutable report addressed by version and input hash."""
    _require(panel_path.is_file(), f"missing eligible historical prediction panel: {panel_path}")
    raw = panel_path.read_bytes()
    try:
        panel = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PanelValidationError("prediction panel is not valid JSON") from exc
    report = evaluate_panel(panel, input_sha256=hashlib.sha256(raw).hexdigest())
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"evaluation-{report['evaluation_id']}.json"
    encoded = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".evaluation-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        try:
            os.link(temporary, path)
        except FileExistsError:
            _require(path.read_bytes() == encoded, f"immutable evaluation collision or altered report: {path}")
    finally:
        temporary.unlink(missing_ok=True)
    return path
