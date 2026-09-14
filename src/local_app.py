"""Read-only local research desk backed by the repository's research artifacts.

This application deliberately has no imports from the legacy database, settings,
authentication, ingestion, or delivery modules. It never refreshes external data.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
UI_DIR = Path(__file__).with_name("local_ui")
TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,19}$")
SCORE_SEMANTICS = (
    "Cross-sectional research ranking on a 0–100 scale. "
    "Not a calibrated acquisition probability, forecast return, or investment recommendation."
)
RISK_SEMANTICS = (
    "Missing company-specific evidence means unscreened, not low risk. "
    "Diligence scores do not establish fraud or individual culpability."
)
LAYERS = {
    "strategic_matrix": "Strategic interpretation",
    "execution_scorecard": "Execution coverage",
    "execution_risk": "Execution evidence",
    "study_integrity": "Study integrity evidence",
}


class ArtifactError(ValueError):
    """An artifact is absent, unsafe, or unsuitable for use."""


def resolve_output_dir(output_dir: Path) -> Path:
    """Follow only a confined, local run pointer; fail closed on invalid pointers."""
    root = output_dir.resolve()
    pointer = root / "local_latest.json"
    if not pointer.exists():
        return root
    try:
        if pointer.is_symlink() or pointer.stat().st_size > 64 * 1024:
            raise ArtifactError("Invalid local_latest.json pointer file")
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        relative = payload.get("snapshot_directory") if isinstance(payload, dict) else None
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ArtifactError("Local snapshot pointer must contain a relative snapshot_directory")
        target = (root / relative).resolve()
        runs = root / "local_runs"
        if not target.is_relative_to(runs) or target == runs or not target.is_dir():
            raise ArtifactError("Local snapshot pointer must resolve to an existing directory within local_runs")
        expected = payload.get("snapshot_sha256")
        snapshot_path = target / "snapshot.json"
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ArtifactError("Local snapshot pointer must declare snapshot_sha256")
        if snapshot_path.is_symlink() or not snapshot_path.is_file() or snapshot_path.stat().st_size > 1024 * 1024:
            raise ArtifactError("Invalid sealed snapshot manifest")
        if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != expected:
            raise ArtifactError("Sealed snapshot manifest does not match the local pointer hash")
        return target
    except (OSError, UnicodeError, ValueError) as exc:
        raise ArtifactError("Cannot resolve local research snapshot pointer: " + str(exc)) from exc


def _number(value: Any, field: str, *, score: bool = False) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ArtifactError(f"Invalid numeric field: {field}") from exc
    if not math.isfinite(result) or (score and not 0 <= result <= 100):
        raise ArtifactError(f"Out-of-range numeric field: {field}")
    return result


def _list(value: Any, field: str) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError) as exc:
        raise ArtifactError(f"Invalid list field: {field}") from exc
    if not isinstance(parsed, list) or not all(isinstance(v, str) for v in parsed):
        raise ArtifactError(f"Expected a list of strings: {field}")
    return parsed


def _ticker(value: str) -> str:
    value = value.strip().upper()
    if not TICKER.fullmatch(value):
        raise ArtifactError("Ticker must contain only letters, numbers, dots, or hyphens")
    return value


def _safe_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return None


def _date(value: Any, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ArtifactError(f"Invalid date: {field}") from exc


class ArtifactStore:
    def __init__(self, output_dir: Path, stale_after_days: int = 14):
        self.root = output_dir.resolve()
        self.stale_after_days = stale_after_days
        self.seal: dict[str, str] | None = None
        self.run_id: str | None = None
        self.output_hashes: dict[str, str] = {}
        if (self.root / "snapshot.json").exists():
            try:
                payload = json.loads(self._path("snapshot.json").read_text(encoding="utf-8"))
                hashes = payload.get("artifact_sha256") if isinstance(payload, dict) else None
                if not isinstance(hashes, dict) or not hashes or not all(
                    isinstance(key, str) and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for key, value in hashes.items()
                ):
                    raise ArtifactError("Sealed snapshot must declare valid artifact_sha256 entries")
                self.seal = hashes
                self.run_id = payload.get("run_id")
            except (OSError, UnicodeError, ValueError) as exc:
                raise ArtifactError("Invalid sealed snapshot manifest: " + str(exc)) from exc

    def _path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ArtifactError(f"Artifact resolves outside the output directory: {relative}")
        if not path.is_file():
            raise ArtifactError(f"Missing artifact: {relative}")
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ArtifactError(f"Artifact exceeds the 64 MiB read limit: {relative}")
        return path

    def _read(self, relative: str) -> bytes:
        try:
            content = self._path(relative).read_bytes()
        except OSError as exc:
            raise ArtifactError(f"Cannot read artifact: {relative}") from exc
        actual = hashlib.sha256(content).hexdigest()
        if self.seal is not None and self.seal.get(relative) != actual:
            raise ArtifactError(f"Artifact fails sealed snapshot hash verification: {relative}")
        if relative in self.output_hashes and self.output_hashes[relative] != actual:
            raise ArtifactError(f"Artifact fails output hash verification: {relative}")
        return content

    def csv(self, relative: str, required: set[str]) -> list[dict[str, str]]:
        try:
            with io.StringIO(self._read(relative).decode("utf-8-sig"), newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames or []
                if len(fields) != len(set(fields)) or not required.issubset(fields):
                    raise ArtifactError(f"Invalid CSV schema: {relative}")
                rows = []
                for row in reader:
                    if None in row or any(value is None for value in row.values()):
                        raise ArtifactError(f"Malformed CSV row: {relative}")
                    rows.append(row)
                return rows
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ArtifactError(f"Cannot read CSV artifact: {relative}") from exc

    def manifest(self, layer: str) -> dict[str, Any]:
        relative = f"{layer}/manifest.json"
        try:
            value = json.loads(self._read(relative).decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ArtifactError(f"Cannot read manifest: {relative}") from exc
        if not isinstance(value, dict):
            raise ArtifactError(f"Manifest must be an object: {relative}")
        for key in ("known_gaps", "sources"):
            if not isinstance(value.get(key, []), list) or not all(isinstance(item, str) for item in value.get(key, [])):
                raise ArtifactError(f"Manifest {key} must be a list of strings: {relative}")
        output_hashes = value.get("output_sha256")
        if output_hashes is not None:
            if not isinstance(output_hashes, dict) or not output_hashes:
                raise ArtifactError(f"Invalid output_sha256: {relative}")
            for filename, digest in output_hashes.items():
                if not isinstance(filename, str) or Path(filename).name != filename or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ArtifactError(f"Invalid output hash entry: {relative}")
                self.output_hashes[f"{layer}/{filename}"] = digest
            if "companies.csv" not in output_hashes:
                raise ArtifactError(f"Output hashes must cover companies.csv: {relative}")
            if layer == "market_evaluation" and "assets.csv" not in output_hashes:
                raise ArtifactError("Market output hashes must cover assets.csv")
        generated = _date(value.get("generated_at"), "generated_at")
        source_date = _date(value.get("as_of") or value.get("evidence_as_of"), "as_of")
        if layer == "market_evaluation" and source_date is None:
            raise ArtifactError("Market manifest must declare as_of")
        today = datetime.now(timezone.utc).date()
        if (source_date and source_date > today) or (generated and generated > today):
            raise ArtifactError(f"Future-dated manifest: {relative}")
        age = (today - source_date).days if source_date else None
        warnings = []
        if source_date is None:
            warnings.append("Evidence cutoff date is absent; generation time is not source freshness.")
        elif age > self.stale_after_days:
            warnings.append(f"Research cutoff is {age} days old; review current source documents before relying on it.")
        retrievals = value.get("source_snapshots", [])
        if not isinstance(retrievals, list) or not all(isinstance(item, dict) for item in retrievals):
            raise ArtifactError(f"Invalid source_snapshots: {relative}")
        identity = [{key: item.get(key) for key in ("cache_key", "sha256", "snapshot_sha256")} for item in retrievals]
        expected_identity = value.get("source_snapshot_set_sha256")
        if expected_identity is not None and hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != expected_identity:
            raise ArtifactError(f"Source snapshot set hash mismatch: {relative}")
        observed_dates = []
        retrieval_metadata_valid = bool(retrievals and expected_identity and output_hashes)
        for item in retrievals:
            try:
                retrieved = datetime.fromisoformat(item["retrieved_at"].replace("Z", "+00:00"))
                if retrieved.tzinfo is None or retrieved > datetime.now(timezone.utc):
                    raise ValueError("Unusable retrieval timestamp")
                observed_dates.append(retrieved)
                if item.get("integrity_status") != "verified" or not all(
                    isinstance(item.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", item[key]) for key in ("sha256", "snapshot_sha256")
                ):
                    retrieval_metadata_valid = False
            except (KeyError, TypeError, AttributeError, ValueError):
                retrieval_metadata_valid = False
        freshness = "stale_or_unknown"
        oldest_retrieved = min(observed_dates) if observed_dates else None
        declared_freshness = value.get("freshness", {})
        if not isinstance(declared_freshness, dict):
            raise ArtifactError(f"Invalid source freshness metadata: {relative}")
        if not retrieval_metadata_valid:
            warnings.append("Retrieval provenance is unverified. The research cutoff and generation time do not establish source freshness.")
        elif oldest_retrieved and (datetime.now(timezone.utc) - oldest_retrieved).total_seconds() / 86400 <= self.stale_after_days and declared_freshness.get("status") == "fresh":
            freshness = "fresh"
        else:
            warnings.append("Recorded source retrievals are stale or marked unknown; the saved score is research-only.")
        sec_screening = value.get("sec_transaction_screening_status")
        if sec_screening is not None:
            if not isinstance(sec_screening, dict):
                raise ArtifactError("Invalid SEC screening status")
            if sec_screening.get("current") is not True:
                warnings.append(f"Acquisition exclusions use SEC screening through {value.get('sec_transaction_screening_as_of') or 'an unknown date'}; later announcements have not been screened.")
        return {
            "layer": layer,
            "status": "available",
            "as_of": source_date.isoformat() if source_date else None,
            "generated_at": value.get("generated_at"),
            "age_days": age,
            "freshness": freshness,
            "as_of_semantics": "Research/evidence cutoff; does not prove retrieval freshness or historical replay",
            "retrieval_provenance": "recorded" if retrieval_metadata_valid else "unverified",
            "oldest_retrieved_at": oldest_retrieved.isoformat() if oldest_retrieved else None,
            "sec_transaction_screening_as_of": value.get("sec_transaction_screening_as_of"),
            "sec_transaction_screening_status": sec_screening,
            "integrity": "sealed_hashes" if self.seal is not None else "output_hashes" if output_hashes else "unverified_legacy_outputs",
            "model_version": value.get("model_version") or value.get("schema_version"),
            "known_gaps": value.get("known_gaps", []),
            "sources": value.get("sources", []),
            "warnings": warnings,
        }

    def training_status(self) -> dict[str, Any]:
        """Expose saved research progress without implying a trained model."""
        try:
            value = json.loads(self._read("historical_training/status.json"))
            if not isinstance(value, dict) or value.get("schema_version") != "historical-training-readiness-v1":
                raise ArtifactError("Invalid historical training status")
            for key in ("reviewed_positive_announcements", "reviewed_negative_company_windows", "eligible_feature_observations", "pending_candidates"):
                if type(value.get(key)) is not int or value[key] < 0:
                    raise ArtifactError("Invalid historical training coverage")
            for key in ("historical_financial_records", "historical_financial_issuers"):
                if type(value.get(key, 0)) is not int or value.get(key, 0) < 0:
                    raise ArtifactError("Invalid historical financial coverage")
            if value.get("training_allowed") is not False or value.get("model_trained_on_real_data") is not False:
                raise ArtifactError("A research progress artifact cannot establish model availability")
            if not isinstance(value.get("blockers"), list) or not all(isinstance(item, str) for item in value["blockers"]):
                raise ArtifactError("Invalid historical training blockers")
            value["historical_panel"] = self.panel_status()
            return value
        except (ArtifactError, ValueError, TypeError) as exc:
            return {"status": "unavailable", "model_trained_on_real_data": False, "detail": str(exc)}

    def panel_status(self) -> dict[str, Any]:
        """A source-coverage report does not authorize a model or a forecast."""
        try:
            value = json.loads(self._read("historical_training/panel_seed/status.json"))
            if value.get("schema_version") != "historical-panel-assembly-v1":
                raise ArtifactError("Unsupported historical panel status")
            for key in ("frame_companies", "planned_observations", "reviewed_annual_financial_records",
                        "financial_issuers", "reviewed_negative_corpus_windows", "eligible_feature_observations"):
                if type(value.get(key)) is not int or value[key] < 0:
                    raise ArtifactError("Invalid historical panel coverage")
            if value.get("model_training_performed") is not False or value.get("validated_predictive_edge") is not False:
                raise ArtifactError("A panel coverage report cannot establish a fitted model")
            if value["eligible_feature_observations"] > value["planned_observations"]:
                raise ArtifactError("Panel observations exceed the declared frame")
            if not isinstance(value.get("gap_counts"), dict) or any(
                not isinstance(key, str) or type(count) is not int or count < 0
                for key, count in value["gap_counts"].items()
            ):
                raise ArtifactError("Invalid panel gap counts")
            report_bytes = self._read("historical_training/panel_seed/assembly.json")
            if hashlib.sha256(report_bytes).hexdigest() != value.get("coverage_report_sha256"):
                raise ArtifactError("Historical coverage report differs from its saved status")
            report = json.loads(report_bytes)
            if not isinstance(report, dict):
                raise ArtifactError("Invalid historical coverage report")
            summary = {key: item for key, item in report.items() if key not in ("coverage", "panel", "corpus_reviews")}
            if any(key not in value or value[key] != item for key, item in summary.items()):
                raise ArtifactError("Historical panel summary differs from its coverage report")
            for key in ("schema_version", "frame_companies", "planned_observations", "eligible_feature_observations",
                        "reviewed_annual_financial_records", "financial_issuers", "reviewed_negative_corpus_windows",
                        "model_training_performed", "validated_predictive_edge", "gap_counts", "pre_test_training_support"):
                if key not in summary or key not in value or value[key] != summary[key]:
                    raise ArtifactError("Historical panel display values are not bound to the coverage report")
            panel_bytes = self._read("historical_training/panel_seed/panel.json")
            if hashlib.sha256(panel_bytes).hexdigest() != value.get("panel_sha256"):
                raise ArtifactError("Historical feature panel differs from its saved status")
            panel = json.loads(panel_bytes)
            if not isinstance(panel, dict) or panel != report.get("panel"):
                raise ArtifactError("Historical feature panel differs from its coverage report")
            observations, coverage = panel.get("observations"), report.get("coverage")
            if (not isinstance(observations, list) or len(observations) != value["eligible_feature_observations"]
                    or not isinstance(coverage, list) or len(coverage) != value["planned_observations"]
                    or len({row["ticker"] for row in coverage}) != value["frame_companies"]):
                raise ArtifactError("Historical panel counts disagree with saved observations")
            support = value["pre_test_training_support"]
            fields = ("company_observations", "structurally_admitted_prior_observations", "distinct_positive_events",
                      "distinct_negative_companies", "purged_prior_observations", "purged_label_unavailable")
            if not isinstance(support, dict) or any(type(support.get(key)) is not int or support[key] < 0 for key in fields):
                raise ArtifactError("Invalid historical fold support")
            if (support["company_observations"] + support["purged_prior_observations"] != support["structurally_admitted_prior_observations"]
                    or support["structurally_admitted_prior_observations"] > value["eligible_feature_observations"]
                    or support["distinct_positive_events"] + support["distinct_negative_companies"] > support["company_observations"]
                    or support["purged_label_unavailable"] > support["purged_prior_observations"]):
                raise ArtifactError("Historical fold support disagrees with complete observations")
            return value
        except (ArtifactError, ValueError, TypeError, AttributeError, KeyError) as exc:
            return {"status": "unavailable", "model_training_performed": False, "detail": str(exc)}

    def snapshot(self) -> dict[str, Any]:
        market = self.manifest("market_evaluation")
        rows = self.csv("market_evaluation/companies.csv", {
            "ticker", "company_name", "research_score", "risk_set_eligible",
            "risk_set_exclusion_reason", "data_confidence",
        })
        if not rows:
            raise ArtifactError("Market company artifact contains no companies")
        sources = [market]
        layers: dict[str, dict[str, dict[str, str]]] = {}
        for layer in LAYERS:
            try:
                manifest = self.manifest(layer)
                required = {"ticker", "company_name"}
                if layer == "execution_scorecard":
                    required.add("evidence_coverage")
                if layer == "strategic_matrix":
                    required.add("risk_coverage")
                layer_rows = self.csv(f"{layer}/companies.csv", required)
                index = {}
                for row in layer_rows:
                    ticker = _ticker(row["ticker"])
                    if ticker in index:
                        raise ArtifactError(f"Duplicate ticker in {layer}: {ticker}")
                    index[ticker] = row
                layers[layer] = index
                sources.append(manifest)
            except ArtifactError as exc:
                layers[layer] = {}
                sources.append({"layer": layer, "status": "unavailable", "warnings": [str(exc)]})
        companies = []
        seen = set()
        for row in rows:
            ticker = _ticker(row["ticker"])
            if ticker in seen:
                raise ArtifactError(f"Duplicate company ticker: {ticker}")
            seen.add(ticker)
            if not row["company_name"].strip():
                raise ArtifactError(f"Company name is missing for {ticker}")
            eligibility = row["risk_set_eligible"].lower()
            if eligibility not in {"true", "false"}:
                raise ArtifactError(f"Invalid risk-set eligibility for {ticker}")
            if eligibility == "false" and not row["risk_set_exclusion_reason"].strip():
                raise ArtifactError(f"Excluded company lacks a reason: {ticker}")
            execution = layers["execution_scorecard"].get(ticker, {})
            strategic = layers["strategic_matrix"].get(ticker, {})
            risk = layers["execution_risk"].get(ticker, {})
            integrity = layers["study_integrity"].get(ticker, {})
            coverage = execution.get("evidence_coverage") or strategic.get("risk_coverage") or "unavailable"
            screened = coverage == "company_specific_evidence" or bool(risk) or bool(integrity)
            company = {
                "ticker": ticker, "company_name": row["company_name"],
                "research_score": _number(row["research_score"], "research_score", score=True),
                "data_confidence": _number(row["data_confidence"], "data_confidence", score=True),
                "market_cap_usd": _number(row.get("market_cap_usd"), "market_cap_usd"),
                "industry": row.get("industry") or "Unspecified", "exchange": row.get("exchange"),
                "risk_set_eligible": eligibility == "true",
                "risk_set_screening_current": (market.get("sec_transaction_screening_status") or {}).get("current"),
                "risk_set_screening_as_of": market.get("sec_transaction_screening_as_of"),
                "risk_set_exclusion_reason": row["risk_set_exclusion_reason"] or None,
                "as_of": market["as_of"], "evaluated_at": row.get("evaluated_at"),
                "model_version": row.get("model_version") or market["model_version"],
                "score_drivers": _list(row.get("score_drivers"), "score_drivers"),
                "top_assets": _list(row.get("top_assets"), "top_assets"),
                "approved_asset_count": _number(row.get("approved_asset_count"), "approved_asset_count"),
                "clinical_asset_count": _number(row.get("clinical_asset_count"), "clinical_asset_count"),
                "late_stage_asset_count": _number(row.get("late_stage_asset_count"), "late_stage_asset_count"),
                "risk_coverage": "company_specific_evidence" if screened else coverage,
                "risk_screened": screened,
                "combined_diligence_risk": _number(strategic.get("combined_diligence_risk"), "combined_diligence_risk", score=True) if screened else None,
                "execution_risk_score": _number(risk.get("execution_risk_score"), "execution_risk_score", score=True) if screened else None,
                "integrity_diligence_score": _number(integrity.get("diligence_score"), "diligence_score", score=True) if screened else None,
                "execution_outlook": execution.get("execution_outlook") or "unavailable",
                "strategic_archetype": strategic.get("strategic_archetype") or "unavailable",
                "decision_rule": strategic.get("decision_rule"),
                "primary_risk_drivers": _list(strategic.get("primary_risk_drivers"), "primary_risk_drivers"),
                "risk_interpretation": RISK_SEMANTICS,
            }
            companies.append(company)
        companies.sort(key=lambda c: (-(c["research_score"] if c["research_score"] is not None else -1), c["ticker"]))
        rank = 0
        for company in companies:
            company["rank"] = None
            if company["risk_set_eligible"] and company["research_score"] is not None:
                rank += 1
                company["rank"] = rank
        counts = {
            "companies": len(companies),
            "eligible": sum(c["risk_set_eligible"] for c in companies),
            "excluded": sum(not c["risk_set_eligible"] for c in companies),
            "with_company_specific_evidence": sum(c["risk_screened"] for c in companies),
            "unscreened": sum(not c["risk_screened"] for c in companies),
            "with_matched_assets": sum(bool((c["approved_asset_count"] or 0) + (c["clinical_asset_count"] or 0)) for c in companies),
        }
        return {"status": "available", "as_of": market["as_of"], "score_semantics": SCORE_SEMANTICS,
                "risk_semantics": RISK_SEMANTICS, "coverage": counts, "sources": sources,
                "companies": companies, "freshness": market["freshness"], "snapshot_id": self.run_id,
                "historical_training": self.training_status()}

    def detail(self, ticker: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        company = next((c for c in snapshot["companies"] if c["ticker"] == ticker), None)
        if company is None:
            raise HTTPException(404, "Company is absent from the local research universe")
        detail = dict(company)
        detail.update({"score_semantics": SCORE_SEMANTICS, "sources": snapshot["sources"], "snapshot_id": snapshot["snapshot_id"]})
        evidence = []
        for layer in ("execution_risk", "study_integrity"):
            try:
                manifest = next(s for s in snapshot["sources"] if s["layer"] == layer)
                if manifest["status"] != "available":
                    raise ArtifactError(f"{LAYERS[layer]} artifacts are unavailable")
                rows = self.csv(f"{layer}/signals.csv", {"ticker", "source_url", "summary", "evidence_status"})
                signals = [{key: row.get(key) for key in (
                    "signal_id", "category", "evidence_status", "summary", "source_title",
                    "source_organization", "source_date", "event_date", "review_notes", "response_summary",
                )} | {"source_url": _safe_url(row.get("source_url")), "response_url": _safe_url(row.get("response_url"))}
                    for row in rows if row["ticker"].upper() == ticker]
                evidence.append({"layer": layer, "status": "available" if signals else "unscreened", "signals": signals})
            except ArtifactError as exc:
                evidence.append({"layer": layer, "status": "unavailable", "signals": [], "reason": str(exc)})
        detail["evidence"] = evidence
        try:
            rows = self.csv("market_evaluation/assets.csv", {"owner_ticker", "asset_name", "source_url", "source_name"})
            assets = []
            for row in rows:
                if row["owner_ticker"].upper() != ticker:
                    continue
                assets.append({key: row.get(key) for key in (
                    "asset_id", "asset_name", "asset_type", "development_phase", "source_name",
                    "source_id", "published_at", "patent_expiry", "exclusivity_expiry",
                )} | {"source_url": _safe_url(row.get("source_url")),
                     "score": _number(row.get("score"), "asset score", score=True),
                     "owner_match_confidence": _number(row.get("owner_match_confidence"), "owner match confidence"),
                     "indications": _list(row.get("indications"), "indications"),
                     "score_drivers": _list(row.get("score_drivers"), "asset score_drivers")})
            assets.sort(key=lambda a: -(a["score"] if a["score"] is not None else -1))
            detail["assets"] = {"status": "available", "total": len(assets), "items": assets}
        except ArtifactError as exc:
            detail["assets"] = {"status": "unavailable", "total": None, "items": [], "reason": str(exc)}
        return detail


def _md(value: Any) -> str:
    return str(value if value is not None else "Unavailable").replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ")


def _report(detail: dict[str, Any]) -> str:
    lines = [f"# {_md(detail['ticker'])} — {_md(detail['company_name'])}", "",
             f"Research cutoff: {detail['as_of']}", "", SCORE_SEMANTICS, "", RISK_SEMANTICS, "",
             f"- Snapshot: {_md(detail['snapshot_id'])}",
             f"- Model: {_md(detail['model_version'])}",
             f"- Research score: {_md(detail['research_score'])}",
             f"- Market-data confidence: {_md(detail['data_confidence'])}",
             f"- Risk-set eligible: {detail['risk_set_eligible']}",
             f"- Exclusion reason: {_md(detail['risk_set_exclusion_reason'])}",
             f"- Company-specific risk evidence: {detail['risk_screened']}",
             f"- Evidence coverage: {_md(detail['risk_coverage'])}", "", "## Research drivers", ""]
    lines += [f"- {_md(item)}" for item in detail["score_drivers"]] or ["Unavailable."]
    lines += ["", "## Snapshot freshness", ""]
    for source in detail["sources"]:
        lines.append(f"- {_md(source['layer'])}: {_md(source['status'])}; research cutoff {_md(source.get('as_of'))}.")
        lines.append(f"  - Retrieval provenance: {_md(source.get('retrieval_provenance'))}; oldest retrieval: {_md(source.get('oldest_retrieved_at'))}.")
        lines += [f"  - {_md(warning)}" for warning in source.get("warnings", [])]
    lines += ["", "## Matched asset evidence", "", f"Status: {detail['assets']['status']}", ""]
    for asset in detail["assets"]["items"]:
        lines += [f"### {_md(asset['asset_name'])}", "",
                  f"Stage: {_md(asset['development_phase'])}. Source: {_md(asset['source_name'])}.", ""]
        lines += [f"- {_md(driver)}" for driver in asset["score_drivers"]]
        if asset["source_url"]:
            lines += ["", f"Source document: {asset['source_url']}"]
        lines.append("")
    if detail["assets"].get("reason"):
        lines.append(_md(detail["assets"]["reason"]))
    lines += ["", "## Company-specific diligence evidence", ""]
    for layer in detail["evidence"]:
        lines += [f"### {_md(layer['layer'])}: {layer['status']}", ""]
        if layer.get("reason"):
            lines.append(_md(layer["reason"]))
        for signal in layer["signals"]:
            lines += [f"- {_md(signal['evidence_status'])}: {_md(signal['summary'])}"]
            if signal["source_url"]:
                lines.append(f"  Source document: {signal['source_url']}")
            if signal.get("review_notes"):
                lines.append(f"  Review note: {_md(signal['review_notes'])}")
    return "\n".join(lines) + "\n"


def create_app(output_dir: Path | str = DEFAULT_OUTPUT_DIR) -> FastAPI:
    def current_store() -> ArtifactStore:
        # A new store per request follows atomic pointer updates without mixing
        # two run directories inside one response or requiring a restart.
        return ArtifactStore(resolve_output_dir(Path(output_dir)))

    app = FastAPI(title="Biotech Research Desk — local", version="1.0.0", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

    @app.middleware("http")
    async def local_response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.exception_handler(ArtifactError)
    async def unavailable(request, exc):
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(exc),
            "remediation": "Create or repair the local research artifacts, then reload. No external data refresh is performed by this app."})

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(UI_DIR / "index.html")

    @app.get("/health")
    def health():
        try:
            store = current_store()
            snap = store.snapshot()
            artifacts = {"status": "available", "as_of": snap["as_of"], "companies": snap["coverage"]["companies"]}
        except ArtifactError as exc:
            artifacts = {"status": "unavailable", "detail": str(exc)}
        return {"status": "alive", "mode": "local_read_only", "artifacts": artifacts}

    @app.get("/ready")
    def ready():
        store = current_store()
        snap = store.snapshot()
        return {"status": "ready", "mode": "local_read_only", "as_of": snap["as_of"],
                "freshness": snap["freshness"], "coverage": snap["coverage"], "sources": snap["sources"], "snapshot_id": snap["snapshot_id"],
                "historical_training": snap["historical_training"]}

    @app.get("/api/v1/predictions/watchlist")
    def watchlist(q: str = Query("", max_length=100), min_score: float = Query(0, ge=0, le=100),
                  eligibility: str = Query("eligible", pattern="^(eligible|excluded|all)$"),
                  coverage: str = Query("all", pattern="^(all|screened|unscreened)$"),
                  page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100)):
        store = current_store()
        snap = store.snapshot()
        companies = snap.pop("companies")
        selected = [c for c in companies
                    if (eligibility == "all" or c["risk_set_eligible"] == (eligibility == "eligible"))
                    and (coverage == "all" or c["risk_screened"] == (coverage == "screened"))
                    and (c["research_score"] >= min_score if c["research_score"] is not None else min_score == 0)
                    and (not q or q.lower() in (c["ticker"] + " " + c["company_name"] + " " + c["industry"]).lower())]
        start = (page - 1) * page_size
        return snap | {"watchlist": selected[start:start + page_size], "total": len(selected),
                       "page": page, "page_size": page_size, "eligibility": eligibility}

    @app.get("/api/v1/research/historical-coverage")
    def historical_coverage():
        store = current_store()
        status = store.panel_status()
        if status.get("status") == "unavailable":
            raise ArtifactError(status["detail"])
        payload = store._read("historical_training/panel_seed/assembly.json")
        if hashlib.sha256(payload).hexdigest() != status.get("coverage_report_sha256"):
            raise ArtifactError("Historical coverage report differs from its saved status")
        return Response(payload, media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="historical-company-coverage.json"'})

    def company_detail(ticker: str):
        try:
            normalized = _ticker(ticker)
        except ArtifactError as exc:
            raise HTTPException(422, str(exc)) from exc
        store = current_store()
        return store.detail(normalized, store.snapshot())

    @app.get("/api/v1/companies/{ticker}")
    def company(ticker: str):
        return company_detail(ticker)

    @app.get("/api/v1/companies/{ticker}/report")
    def report(ticker: str):
        detail = company_detail(ticker)
        return Response(_report(detail), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{detail["ticker"]}-research-{detail["as_of"]}.md"'})

    return app


app = create_app(os.environ.get("BIOTECH_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
