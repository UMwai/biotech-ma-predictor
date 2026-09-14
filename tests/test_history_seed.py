"""Offline integrity regressions using copies of the actual two review batches."""

import csv
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.build_history_seed import build_seed, _verified_panel_progress, freeze_seed_labels
from src.research.adjudication import announcement_bounds, validate_reviews


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def history_root(tmp_path):
    for relative in ("output/historical_deal_candidates/candidates.csv",
                     "data/history/reviews_2018_2021.csv", "data/history/evidence_2018_2021.json",
                     "data/history/reviews_2022_2025.csv", "data/history/evidence_2022_2025.json"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    return tmp_path


def load_batch(root, suffix):
    directory = root / "data/history"
    with (directory / f"reviews_{suffix}.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, json.loads((directory / f"evidence_{suffix}.json").read_text())


def save_batch(root, suffix, rows, evidence, *, renew_record_hash=False):
    directory = root / "data/history"
    path = directory / f"reviews_{suffix}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if suffix == "2018_2021":
        evidence["review_csv_sha256"] = digest
    else:
        evidence["integrity"]["reviews_csv_sha256"] = digest
        if renew_record_hash:
            for record in evidence["records"]:
                unsigned = {key: value for key, value in record.items() if key != "review_record_sha256"}
                record["review_record_sha256"] = hashlib.sha256(
                    json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (directory / f"evidence_{suffix}.json").write_text(json.dumps(evidence))


def test_real_batches_freeze_49_with_truthful_dates_and_provenance(history_root):
    result = build_seed(history_root)
    frozen_path = history_root / "data/history/frozen_labels.json"
    original = frozen_path.read_bytes()
    labels = json.loads(original)["labels"]
    assert len(labels) == result["reviewed_positive_announcements"] == 49
    assert result["training_allowed"] is False
    assert result["model_trained_on_real_data"] is False
    assert result["reviewed_negative_company_windows"] == result["eligible_feature_observations"] == 0
    assert result["by_announcement_year"] == {"2018": 7, **{str(year): 6 for year in range(2019, 2026)}}
    assert sum(label["announced_at"] is None for label in labels) == 46
    assert all(label["source_retrieved_at"] and label["evidence_record_id"] for label in labels)
    assert all(label["transaction_status"] == "pending" for label in labels)
    assert all(label["transaction_status_as_of"] == label["announcement_date"] for label in labels)
    assert hashlib.sha256(original).hexdigest() == result["frozen_labels_sha256"]
    assert (history_root / result["frozen_labels_path"]).read_bytes() == original
    assert build_seed(history_root) == result
    assert frozen_path.read_bytes() == original


@pytest.mark.parametrize("suffix", ["2018_2021", "2022_2025"])
def test_modified_review_csv_rejected_without_replacing_published_seed(history_root, suffix):
    build_seed(history_root)
    published = history_root / "data/history/frozen_labels.json"
    before = published.read_bytes()
    path = history_root / f"data/history/reviews_{suffix}.csv"
    path.write_text(path.read_text().replace("pending", "completed", 1))
    with pytest.raises(ValueError, match="evidence receipt"):
        build_seed(history_root)
    assert published.read_bytes() == before


def test_label_freezing_can_precede_stale_derived_artifact_rebuild(history_root):
    status = build_seed(history_root)
    directory = history_root / "data/history"
    (directory / "financial_seed").mkdir()
    (directory / "financial_seed/feature_snapshot.json").write_text('{"stale":true}')
    original = (directory / "status.json").read_bytes()
    result, frozen, _ = freeze_seed_labels(history_root)
    assert result["reviewed_positive_count"] == 49
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == status["frozen_labels_sha256"]
    assert (directory / "status.json").read_bytes() == original


def test_candidate_ledger_change_rejected(history_root):
    path = history_root / "output/historical_deal_candidates/candidates.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="ledger changed"):
        build_seed(history_root)


def test_new_schema_record_tampering_rejected_even_with_matching_csv_hash(history_root):
    rows, evidence = load_batch(history_root, "2022_2025")
    evidence["records"][0]["primary_evidence_paraphrase"] = "Unsupported replacement evidence"
    save_batch(history_root, "2022_2025", rows, evidence)
    with pytest.raises(ValueError, match="record hash mismatch"):
        build_seed(history_root)


@pytest.mark.parametrize("suffix", ["2018_2021", "2022_2025"])
def test_duplicate_evidence_cannot_be_hidden_by_candidate_dict(history_root, suffix):
    rows, evidence = load_batch(history_root, suffix)
    evidence["records"].append(deepcopy(evidence["records"][0]))
    save_batch(history_root, suffix, rows, evidence)
    with pytest.raises(ValueError, match="duplicate evidence candidate"):
        build_seed(history_root)


@pytest.mark.parametrize("suffix", ["2018_2021", "2022_2025"])
def test_matching_but_wrong_cik_in_csv_and_evidence_cannot_relabel_candidate(history_root, suffix):
    rows, evidence = load_batch(history_root, suffix)
    rows[0]["reviewed_target_cik"] = "9999999"
    evidence["records"][0]["target_cik"] = "9999999"
    save_batch(history_root, suffix, rows, evidence, renew_record_hash=True)
    with pytest.raises(ValueError, match="CIK mismatch"):
        build_seed(history_root)


@pytest.mark.parametrize(("field", "replacement", "error"), [
    ("review_primary_source_url", "https://example.invalid/other", "source identity mismatch"),
    ("public_listing_evidence_url", "https://example.invalid/listing", "listing source identity mismatch"),
    ("evidence_record_id", "other-record", "record ID mismatch"),
    ("announcement_date", "2018-01-21", "announcement_date mismatch"),
    ("transaction_status", "completed", "transaction evidence mismatch"),
    ("first_public_announcement_at", "2018-01-22T00:00:00Z", "announcement timestamp mismatch"),
])
def test_resealed_csv_still_requires_corresponding_evidence(history_root, field, replacement, error):
    rows, evidence = load_batch(history_root, "2018_2021")
    rows[0][field] = replacement
    save_batch(history_root, "2018_2021", rows, evidence)
    with pytest.raises(ValueError, match=error):
        build_seed(history_root)


def test_new_schema_sec_lineage_url_must_match_original_candidate(history_root):
    rows, evidence = load_batch(history_root, "2022_2025")
    evidence["records"][0]["sec_candidate_lineage"]["candidate_source_urls"] = ["https://example.invalid/filing"]
    save_batch(history_root, "2022_2025", rows, evidence, renew_record_hash=True)
    with pytest.raises(ValueError, match="lineage candidate_source_urls mismatch"):
        build_seed(history_root)


def test_core_adjudication_rejects_candidate_cik_reassignment(history_root):
    rows, _ = load_batch(history_root, "2022_2025")
    with (history_root / "output/historical_deal_candidates/candidates.csv").open() as handle:
        candidates = list(csv.DictReader(handle))
    rows[0]["reviewed_target_cik"] = "9999999"
    with pytest.raises(ValueError, match="CIK"):
        validate_reviews(candidates, rows)


def test_frozen_timestamp_alias_preserves_exact_time_and_rejects_conflicts():
    exact = "2022-11-21T11:45:00+00:00"
    row = {"announced_at": exact, "announcement_date": "2022-11-21", "timestamp_precision": "timestamp"}
    at, _, lower, upper = announcement_bounds(row)
    assert at.isoformat() == exact
    assert at == lower == upper
    row["announcement_at"] = "2022-11-21T11:46:00+00:00"
    with pytest.raises(ValueError, match="contradict|inconsistent|conflict"):
        announcement_bounds(row)


@pytest.fixture
def published_panel(history_root):
    """Actual reviewed label seed plus a synthetic unknown-member coverage frame."""
    from src.research.panel_assembly import assemble_research_panel
    build_seed(history_root)
    directory=history_root/'data/history';seed=directory/'panel_seed';seed.mkdir()
    source=(b'<p>The following 1 securities will be added to the Index:</p><table><tr><td>EXCHANGE</td>'
            b'<td>SYMBOL</td><td>COMPANY NAME</td></tr><tr><td>Nasdaq</td><td>SYNTH</td><td>Synthetic issuer</td></tr></table>')
    (seed/'source.html').write_bytes(source)
    receipt=dict(source_uri='https://example.org/exchange',source_relative_path='source.html',
                 source_sha256=hashlib.sha256(source).hexdigest(),bytes=len(source),retrieved_at='2026-01-01T00:00:00Z')
    (seed/'nasdaq_source_receipt.json').write_text(json.dumps(receipt))
    frame=dict(schema_version='historical-sampling-frame-v1',frame_size=1,
               records=[dict(exchange='Nasdaq',historical_ticker='SYNTH',historical_issuer_name='Synthetic issuer')],
               cohort_plan=dict(observation_dates=['2021-01-01','2023-01-01','2024-01-01'],horizon_days=365,test_start_year=2023),
               historical_sampling_frame=dict(source_uri=receipt['source_uri'],source_sha256=receipt['source_sha256'],
                   selection_basis='predeclared_historical_sampling_frame',selection_rule='All named synthetic members',
                   source_locator='Synthetic table',uses_current_listing_status=False,uses_future_outcomes=False,
                   includes_subsequently_delisted=True,population_as_of_at='2020-12-21T00:00:00Z',
                   retrieved_at=receipt['retrieved_at'],reviewed_at='2026-01-02T00:00:00Z'))
    (seed/'sampling_frame.json').write_text(json.dumps(frame))
    report=assemble_research_panel(directory)
    report_bytes=json.dumps(report).encode();panel_bytes=json.dumps(report['panel']).encode()
    (seed/'assembly.json').write_bytes(report_bytes);(seed/'panel.json').write_bytes(panel_bytes)
    summary={k:v for k,v in report.items() if k not in ('coverage','panel','corpus_reviews')}
    summary.update(coverage_report_sha256=hashlib.sha256(report_bytes).hexdigest(),panel_sha256=hashlib.sha256(panel_bytes).hexdigest())
    (seed/'status.json').write_text(json.dumps(summary))
    return directory,seed,report


def test_current_panel_replays_before_history_publication(history_root,published_panel):
    result=build_seed(history_root)
    assert result['eligible_feature_observations']==0
    assert result['model_trained_on_real_data'] is False


@pytest.mark.parametrize('relative',['panel_seed/sampling_frame.json','panel_seed/observation_adjudications.json',
                                     'panel_financials/financial_records.json','panel_financials/positive_financial_records.json'])
def test_stale_panel_inputs_cannot_be_sealed_as_current(history_root,published_panel,relative):
    directory,_,_=published_panel
    old_status=(directory/'status.json').read_bytes();old_frozen=(directory/'frozen_labels.json').read_bytes()
    path=directory/relative;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(path.read_bytes()+b' ' if path.exists() else b'{}')
    with pytest.raises(ValueError,match='source inputs changed'):
        build_seed(history_root)
    assert (directory/'status.json').read_bytes()==old_status
    assert (directory/'frozen_labels.json').read_bytes()==old_frozen


def test_panel_is_bound_to_newly_frozen_labels_not_old_convenience_copy(published_panel,tmp_path):
    directory,_,_=published_panel
    fresh=tmp_path/'newly-frozen.json';fresh.write_bytes((directory/'frozen_labels.json').read_bytes()+b' ')
    with pytest.raises(ValueError,match='source inputs changed'):
        _verified_panel_progress(directory,fresh)


def test_transitive_original_source_tamper_blocks_publication(history_root,published_panel):
    _,seed,_=published_panel
    (seed/'source.html').write_bytes(b'changed original source')
    with pytest.raises(ValueError,match='SHA-256 mismatch'):
        build_seed(history_root)


def test_history_builder_rejects_forged_fold_summary(history_root,published_panel):
    _,seed,_=published_panel
    path=seed/'status.json';status=json.loads(path.read_text())
    status['pre_test_training_support']['distinct_negative_companies']=20
    path.write_text(json.dumps(status))
    with pytest.raises(ValueError,match='summary or feature panel differs'):
        build_seed(history_root)
