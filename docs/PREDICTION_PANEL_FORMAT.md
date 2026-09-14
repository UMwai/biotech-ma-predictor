# Historical prediction panel contract

`scripts/evaluate_predictions.py` evaluates an **externally supplied** JSON panel.
It does not train a model, reconstruct exchange membership, or promote SEC
transaction candidates into labels. The repository does not currently contain an
eligible historical prediction panel. Synthetic test fixtures are not research
evidence.

```bash
python3 scripts/evaluate_predictions.py \
  --panel /path/to/reviewed-predictions.json \
  --output-dir output/prediction_validation
```

Missing or invalid inputs return exit status **2**, print a JSON blocker, and do
not publish an evaluation. Passing inputs return **0** and an immutable report
path. The whole panel is rejected if any row fails; failing rows are not silently
removed to improve the result.

## Top-level JSON fields

| Field | Contract |
|---|---|
| `schema_version` | Exactly `sealed-company-predictions-v1` |
| `evaluation_mode` | `retrospective_out_of_time` or `forward` |
| `label_timing_policy` | Optional `recorded_availability` (default), or explicit `retrospective_primary_evidence_v1` in retrospective mode only |
| `historical_sampling_frame` | Required for the retrospective evidence timing policy; source-backed historical population and selection rules, described below |
| `data_as_of` | Latest observed information time; timezone-aware ISO timestamp, no later than current UTC |
| `observations` | Nonempty array of company-observation objects |

All timestamps must include a timezone and are normalized to UTC. Hash fields
contain 64 lowercase hexadecimal SHA-256 characters. These hashes and source
references record externally supplied provenance; the runner does not fetch or
independently authenticate those payloads or the authority behind sealing times.

## Observation fields

| Field | Contract |
|---|---|
| `cik` | Positive integer, or integer string; leading zeros normalize away |
| `observation_at` | Decision timestamp; one row per CIK and UTC observation date |
| `information_cutoff_at` | Latest information allowed for that prediction, strictly before observation |
| `horizon_days` | Integer from 1 to 3650; the same horizon for the entire panel |
| `feature_max_available_at` | Latest actual public availability among all feature inputs |
| `feature_snapshot_sha256` | Hash identifying the feature snapshot |
| `training_cutoff_at` | Historical cutoff for the fitted fold |
| `training_outcomes_available_through` | Latest eligible training-label time under the declared timing policy; actual availability by default, or checked original-evidence availability under explicit reconstruction |
| `training_dataset_sha256` | Hash identifying that fold's training dataset |
| `split_method` | `expanding_window` or `rolling_window`; random splits are rejected |
| `fold_id`, `model_version` | Nonempty identifiers; a fold must retain one training cutoff, dataset hash, and model version |
| `prediction_generated_at`, `prediction_sealed_at` | Actual creation and sealing timestamps; neither may be in the future |
| `risk_set_eligible` | JSON boolean `true`; missing, false, or string values are rejected |
| `risk_set_exclusion_reason` | Null, empty, or omitted for eligible rows; a supplied exclusion blocks evaluation |
| `score` | Finite numeric ranking score; not converted into a probability |
| `probability` | Optional finite number in `[0, 1]`; absent/null means unavailable |
| `membership`, `label` | Objects described below |

Companies on the same UTC observation date must share exactly the same
`observation_at` and `information_cutoff_at`. This defines a comparable
cross-sectional watchlist cohort. Weekly input produces weekly evaluation;
the runner does not manufacture missing weekly cohorts or missing constituents.

Required time ordering:

```text
feature_max_available_at <= information_cutoff_at < observation_at
training_outcomes_available_through <= training_cutoff_at <= information_cutoff_at
information_cutoff_at <= prediction_generated_at <= prediction_sealed_at <= current UTC
observation_at + horizon_days <= data_as_of <= current UTC
```

In **retrospective mode**, prediction files may be generated after historical
outcomes, but historical feature and training cutoffs still apply. These results
are explicitly retrospective and cannot become forward evidence by relabeling
their generation date.

In **forward mode**, `prediction_sealed_at <= observation_at` is also required,
and the seal must precede any positive announcement. The runner checks declared
timestamps; proof that a seal existed at the claimed time remains an external
evidence requirement.

## Historical membership object

| Field | Contract |
|---|---|
| `kind` | Exactly `historical_exchange_membership`; annual SEC reporting proxies are rejected |
| `source_uri`, `source_sha256` | Nonempty source reference and its SHA-256 |
| `security_type` | Exactly `common_equity` |
| `biotech_eligible` | JSON boolean `true`, established for the historical issuer |
| `valid_from`, `valid_until` | Verified listing interval containing observation: `valid_from <= observation_at < valid_until` |

For negative outcomes the listing interval must cover the complete forecast
horizon. Earlier delisting requires an explicit competing-event/censoring model,
which this runner does not implement, so such rows are rejected. A positive
announcement before delisting remains eligible; acquired targets are not
discarded merely because the later transaction removed their listing.

## Reviewed label object

| Field | Contract |
|---|---|
| `reviewed` | JSON boolean `true` |
| `review_id` | Nonempty identifier for the outcome adjudication |
| `source_uri`, `source_sha256` | Nonempty outcome-evidence reference and its SHA-256 |
| `event_class` | `change_of_control_announcement` or `no_change_of_control_announcement` |
| `announcement_at` | Positive: sourced first public announcement timestamp if known; negative: null or absent |
| `announcement_date`, `timestamp_precision` | For date-only evidence, use the sourced calendar date and `date`, with null `announcement_at`; exact evidence may declare `timestamp` |
| `announcement_lower_at`, `announcement_upper_at` | Optional explicit bounds, which must match the source uncertainty; date-only evidence spans midnight UTC minus 14 hours through midnight plus 36 hours |
| `observed_through` | Outcome coverage at least through the complete horizon, no later than `data_as_of` |
| `available_at` | Declared label availability, no later than `data_as_of`; retained unchanged. For newly assembled labels this is actual availability after review, never a fabricated historical review date |
| `reviewed_at`, `retrieved_at` | Optional actual review/retrieval times; supplied times must not follow label availability, and retrieval must not follow review. Actual `reviewed_at` is required for reconstruction |
| `historical_evidence_timing` | Optional explicit reconstruction receipt described below; never interpreted without the matching panel policy |

For a positive label, the announcement must follow observation, occur within the
horizon, precede delisting, and be no later than label availability. For a
negative label, label availability must be after horizon maturity. Transaction
candidate classes, asset deals, and unreviewed labels are not substitutes for
adjudicated whole-company announcement or mature negative outcomes.

## Retrospective evidence timing protocol

The default preserves legacy `available_at` values and uses that same time for
training eligibility. Missing provenance does not automatically turn an old event
date into a historically available training label. When actual review times are
supplied, a label cannot claim it was assembled before that review.

The explicit `retrospective_primary_evidence_v1` policy separates two clocks:

```text
label.available_at = actual assembled-label availability, retained unchanged
label.reviewed_at = actual review time, retained unchanged
label_training_available_at = max(outcome horizon end,
                                  every required original disclosure's publication upper bound,
                                  negative coverage endpoint,
                                  optional negative ascertainment completion)
```

The latter is a **reconstructed evidence eligibility time**, not proof that a
historical researcher had reviewed or stored the label then. Each training fold
must have both the complete horizon and `label_training_available_at` at or
before its cutoff. Later disclosures needed for an adjudication delay that
label's use: a report first published in 2024 cannot support training at a 2023
cutoff just because it discusses 2021. No feature, membership, risk-set,
censoring, support or holdout requirement is weakened.

The inventory and its review may be created today. This is a retrospective
assumption that the declared primary-source corpus and verified original
versions support reconstructing historical outcomes. It does not require a
contemporaneous crawl or a historical review. Conversely, today's surviving
web pages are not independent proof that none were removed. Known missing
material blocks a complete negative; unknown removal risk remains an explicit
limitation and needs external audit. Listing continuity, a current ticker list,
an annual report's existence, or a transaction keyword search alone is
insufficient negative evidence.

This distinction follows the general requirement to train only on information
eligible before the test period; ordinary chronological splitting alone does
not establish the availability of delayed labels. See scikit-learn's
[time-series splitting documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
and [data leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).
The detailed evidence protocol here is this repository's conservative research
contract, not a claim that those references authenticate its sources.

### Historical sampling frame

Supply `historical_sampling_frame` with `source_uri`, `source_sha256`,
`source_locator`, and a nonempty `selection_rule`, plus:

```json
{
  "selection_basis": "historical_exchange_constituents",
  "uses_current_listing_status": false,
  "uses_future_outcomes": false,
  "includes_subsequently_delisted": true,
  "population_as_of_at": "2020-12-11T00:00:00Z",
  "retrieved_at": "2026-09-08T12:00:00Z",
  "reviewed_at": "2026-09-08T13:00:00Z"
}
```

These dates illustrate the format; they are not research evidence.
`predeclared_historical_sampling_frame` is the other accepted selection basis.
Population time must precede every observation and actual retrieval/review must
precede the dataset freeze. Preserve the complete source-defined population,
including later acquisitions/delistings, in the coverage ledger. Unresolved
outcomes and unavailable features remain explicit gaps, not negative labels.
Source availability may still bias the assembled subset; the frame declaration
does not establish representative sampling or sufficient coverage by itself.

### Per-label receipt

`label.historical_evidence_timing` has these fields:

| Field | Requirement |
|---|---|
| `schema_version` | `retrospective-label-evidence-v1` |
| `review_id`, `label_source_sha256` | Exact bindings to the label's review ID and evidence hash |
| `cik`, `event_class` | Same issuer and reviewed event class as the observation |
| `observation_at`, `horizon_end_at` | Exact observation and computed full horizon |
| `reviewed_at`, `reviewer` | Actual review time matching `label.reviewed_at`; named reviewer |
| `sources` | Nonempty list containing every original primary disclosure needed to establish this outcome |
| `sources_sha256` | SHA-256 of the canonical source-list JSON, including version/date annotations |
| `historical_evidence_available_at` | Optional redundant assertion; must equal the derived maximum exactly |
| `announcement_source_id` | Positive labels: ID of the original announcement source, whose publication bounds substantiate the label's announcement interval |
| `coverage` | Negative labels: complete designated-corpus receipt described below |

Canonical hashing throughout this protocol uses exactly:

```python
payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")  # no trailing newline
digest = hashlib.sha256(payload).hexdigest()
```

Each source contains `source_id` (unique within the receipt), `source_uri`
(public HTTPS), `source_sha256`, `source_locator`, `subject_cik` (the integer
issuer being labeled), and the following publication/version fields:

| Field | Requirement |
|---|---|
| `source_family` | `issuer_news`, `regulatory_filings`, or `exchange_notices` |
| `version_status` | `verified_original`; unknown or revised versions cannot inherit an old publication date |
| `publication_basis` | `issuer_publication`, `regulator_acceptance`, or `exchange_publication`; a reporting period end or signing date is insufficient |
| `publication_timestamp_precision` | Explicit `date` or `timestamp` |
| `publication_date`, `published_at` | Original public calendar date and/or sourced exact timestamp; date-only evidence has null `published_at` |
| `publication_lower_at`, `publication_upper_at` | Optional exact derived bounds; date-only means midnight UTC minus 14 hours through midnight plus 36 hours |
| `retrieved_at` | Actual retrieval, after the conservative publication upper bound and no later than review |
| `publication_evidence`, `original_version_evidence` | Each has `source_uri`, `source_sha256`, and `source_locator` identifying the evidence for original publication and version |

Archive the exact source bytes where possible and use
`source_sha256_kind: "original_document_bytes"`. A hash of a review annotation
must not be labeled as a hash of original HTML. Date/version evidence must
identify the original public record, not merely a present page's heading or
a file modification time. A later original document may be included, but its
later publication bound delays training eligibility. A corrected/revised
document requires obtaining the original version or leaving its earlier
eligibility unverified; this protocol does not silently reuse its first-date
metadata.

For **browser-only SEC documents**, the alternative
`source_sha256_kind: "source_review_receipt"` is supported. It requires:

- `original_source_sha256: null`, explicitly recording unavailable HTML bytes;
- `immutable_document_uri`, identical to `source_uri`, identifying a specific
  SEC `/Archives/edgar/data/<CIK>/<18-digit-accession>/<document>` path;
- `review_receipt_uri`, pointing to the saved annotation, and
  `review_annotation`, its parsed object;
- `source_sha256` equal to the hash of the annotation's canonical bytes;
- annotation bindings for `source_uri`, `subject_cik`, `version_status`,
  `source_locator`, `publication_basis`, `publication_timestamp_precision`,
  `publication_date`, `published_at`, and `retrieved_at`, plus a nonempty
  `evidence_paraphrase`, `reviewer`, and actual `reviewed_at`.

The annotation's review must follow retrieval and precede or equal the label
review. Its hash binds the recorded interpretation to the precise accession;
it does not authenticate original HTML bytes. Specific SEC accessions supply a
version anchor, but original public date and subject identity still require
source-backed review. Acquirer-filed releases may legitimately discuss another
issuer. When the accession-path CIK differs from `subject_cik`, supply
`document_filer_cik` matching that path and `subject_identity_evidence` with
`source_uri`, `source_sha256`, and `source_locator` explicitly establishing the
target identity. Bind both additional fields into the review annotation. An
accession's filer must never silently become the acquisition target.
For mutable issuer pages with no original-version proof,
keep version status unknown rather than promoting a download timestamp or
review annotation into historical certainty.

### Negative coverage receipt

`coverage` requires `source_uri` and `source_sha256` identifying the complete
inventory/review receipt. It also requires:

```json
{
  "kind": "complete_designated_primary_corpus",
  "inventory_complete": true,
  "full_text_review_complete": true,
  "censoring_review_complete": true,
  "known_missing_sources": false,
  "qualifying_control_event_found": false,
  "censoring_event_found": false,
  "window_start_at": "2021-01-01T21:00:00Z",
  "window_end_at": "2022-01-01T21:00:00Z",
  "required_source_ids": ["issuer-release-1", "supporting-filing-1"],
  "source_families": ["issuer_news", "regulatory_filings"],
  "scope": "Describe the complete designated corpus actually reviewed",
  "removed_page_limitations": "Describe unresolved historical page-removal uncertainty",
  "retrieved_at": "2026-09-08T12:00:00Z"
}
```

The covered interval must contain the full observation horizon and mature
before inventory retrieval. Every required source ID must match the source
list exactly; families must also match. Include original full-text disclosures
and any later supporting document actually needed for the conclusion. Current
inventory retrieval is an actual provenance clock, not an original publication
time; it does not by itself delay the reconstructed clock to today.

For negative labels, the coverage endpoint is also a lower bound on the
reconstructed clock. Optional `coverage.ascertainment_complete_at` records an
additional conservative completion bound, such as date uncertainty after a
reporting-lag search. It must be at or after `window_end_at` and at or before
the actual inventory `retrieved_at`; it is included in the maximum above.
A corpus searched through March 31, 2022 cannot become eligible in February
merely because its last filing appeared then. The accession-mirror corpus
assembler requires March 31 plus 36 hours, or April 1 at 12:00 UTC, for that
inclusive date-only inventory endpoint. This is a reconstructed ascertainment
bound; actual retrieval and review remain in 2026.

The original-filing corpus replay stores issuer accession-mirror HTML bytes
under their actual issuer URLs, with `source_content_format` set to
`issuer_accession_filing_mirror_html`. Its `original_document_bytes` hash
identifies that retrieved filing presentation, including its current wrapper;
`original_sec_document_bytes_archived` is false and `original_source_sha256`
is null. The separately bound original-version annotation identifies the SEC
accession and document. It does not claim the mirror and SEC HTML have identical
bytes. Every selected parent filing, linked HTML exhibit, and explicitly
reviewed embedded exhibit must replay before a retrospective negative clock
can be supplied. Issuer archive dates can use `issuer_publication` as their
publication basis; they are not invented SEC acceptance timestamps.

The validator checks these declarations and bindings. It does not download
sources, parse a remote archive to prove completeness, authenticate a reviewer's
assertions, or independently verify the contents of the named external files.
The upstream assembler must verify saved bytes/receipts and match the full
source inventory before supplying this protocol. A fabricated but internally
consistent attestation cannot be detected by JSON validation alone.

### Training and forward compatibility

Normalized rows expose both unchanged `label_available_at` and derived
`label_training_available_at`, plus actual `label_reviewed_at` when supplied.
Training and past-only comparators must use `label_training_available_at` while
retaining the full-horizon purge. Model artifacts must retain the explicit
policy and actual creation times. Rows without a reconstruction receipt retain
recorded availability even inside an explicitly retrospective panel.

The reconstruction policy is rejected in `forward` mode, even if a caller
changes prediction timestamps to appear historical. A receipt without the
explicit policy also fails. Existing forward sealing and announcement bounds
remain mandatory. Outcomes reviewed later may evaluate genuinely forward
predictions using the default policy, but their review/availability clocks
must remain actual; they cannot train earlier forward folds.

## Report metrics and their units

The entire announcement interval must follow the observation, fall inside its
horizon, and precede delisting and label availability. Ambiguous boundary windows
are rejected. A negative label cannot contain an announcement date or interval.
Event identity uses CIK plus source calendar date (UTC date for exact timestamps
without a separately sourced calendar date), so repeated observation rows do not
inflate the distinct-deal count. Date-only evidence never becomes a made-up
midnight timestamp.

The report schema is `historical-panel-validation-v4`:

- `per_cohort` reports precision/recall/lift at 10 and 20 within each observation
  date. Effective k is capped by the cohort's company count. Ties at the selection
  boundary use observation-ID order and the policy is disclosed.
- `cohort_aggregate`, both overall and by observation year, averages each date
  equally. Precision includes all dates. Recall and lift omit dates with zero
  positive support; support counts are explicit.
- `pooled_row_diagnostics` contains company-observation base rates, average
  precision, and optional probability metrics. **Pooled top-k is unavailable.**
  Repeated weekly observations are correlated and these rates are not unique
  acquisition-event rates.
- `distinct_deal_capture` identifies events by normalized CIK plus source
  announcement calendar date. A deal captured on several watchlists counts once across the
  selected cohorts. Year-specific totals can overlap when one event appears in
  predictions from multiple observation years; the overall count is deduplicated.
- Average precision groups equal-score thresholds. Brier score, log loss, and
  ten calibration bins are emitted only when every row in the relevant group
  supplies a probability. Empty bins have count zero and null rates.
- The past-only base-rate comparator uses only prior company-observations whose
  entire horizons and policy-eligible label timing precede the observation year's
  earliest information cutoff. It reports no baseline without such support and
  does not assign ranking discrimination to a constant probability.
- `label_timing_policy`, `reconstructed_label_observations`, and
  `label_timing_semantics` disclose whether reconstruction affected eligibility;
  the report still makes no authenticated historical-availability or forward claim.

No confidence intervals, fitting, economic-return validation, or independent
source authentication is performed. A passing report states only that the
external panel contract passed; `validated_predictive_edge` and
`model_training_performed` remain false.

Reports are deterministically identified by evaluator version and the SHA-256 of
the exact input bytes. Publication is atomic and refuses to replace differing
content at an existing report path. An unchanged input/version reuses identical
content; changed inputs or evaluator versions create another report.
