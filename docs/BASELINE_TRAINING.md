# Historical supervised baseline

The baseline **learns coefficients from reviewed historical outcomes**. It uses
L2-regularized logistic regression, training-only median imputation, a missing
indicator for every feature, and training-only standardization. This is a
supervised research baseline, separate from the existing hand-weighted ranking.

It requires an eligible historical dataset. SEC transaction candidates, annual
reporting-company proxies, current-company snapshots relabeled as history, and
unreviewed negative outcomes cannot satisfy that requirement. There is no
membership-incomplete exploratory fitting mode. Synthetic tests verify software
mechanics and provide no evidence of acquisition-prediction performance.

The local source-backed cohort can be assembled with
`python3 scripts/assemble_research_panel.py --publish-to-seed --train`.
See [HISTORICAL_COHORT.md](HISTORICAL_COHORT.md) for replay and coverage semantics.

Alpaca daily market features can be appended through a separate source-verified
assembly. See [ALPACA_MARKET_DATA.md](ALPACA_MARKET_DATA.md) for collection,
source/version limitations and the required `market_data_contract`. The fitted
portable model carries that contract and rejects current features from a
different feed, price basis or derivation policy.

## Fit from an external historical dataset

Model fitting uses the optional packages pinned in `requirements-model.txt`.
The default local application does not require those packages. The trainer
imports them only after validating the dataset and planning eligible folds.

```bash
python3 scripts/train_baseline.py \
  --dataset /path/to/historical-company-features.json \
  --test-start-year 2022 \
  --output-dir output/baseline_training
```

The input is a JSON object with these top-level fields:

| Field | Contract |
|---|---|
| `schema_version` | Exactly `historical-company-features-v1` |
| `data_as_of` | Timezone-aware information cutoff no later than current UTC |
| `feature_names` | Nonempty ordered array of unique numerical feature names |
| `feature_units` | Object containing a nonempty unit string for every feature name |
| `observations` | Nonempty array of reviewed historical company observations |

For example, a dataset may declare `cash_usd` in `USD` and
`burn_usd_per_quarter` in `USD/quarter`. Feature names and units are explicit
contracts; the trainer does not infer whether a number is dollars, millions of
dollars, a percentage, or a quarterly versus annual flow.

Each observation contains:

- `cik`, `observation_at`, `information_cutoff_at`, and `horizon_days`;
- `feature_max_available_at` and `features`, an object containing every declared
  feature as a finite number or null;
- explicit boolean `risk_set_eligible: true` with no exclusion reason;
- a verified `membership` object; and
- a reviewed `label` object with complete outcome coverage and actual label
  availability timestamps.

Membership, labels, observation uniqueness, horizon maturity, and feature
chronology follow the [prediction panel contract](PREDICTION_PANEL_FORMAT.md).
Use the exact historical-exchange-membership kind and actual source provenance;
changing a reporting proxy's name does not establish exchange membership.
The runner checks declared provenance and chronology but does not independently
authenticate the external source payloads.

Do not supply prediction scores, probabilities, training folds, or model
timestamps as evidence that training already happened. The trainer creates those
fields from its actual fitted folds. Its private pre-fit adapter merely reuses
the shared input-validation rules and is never published as a prediction.

## Chronological training and support gates

`--test-start-year` is mandatory. Every observed year from that start through the
last test year is evaluated, and a missing intermediate test year blocks the
run. The trainer does not skip a difficult or undersupported test fold.

For each annual holdout:

1. Set the fold cutoff to that year's earliest information cutoff.
2. Select only observations from earlier years.
3. Purge any selected observation whose complete forward horizon or effective
   label availability extends beyond the fold cutoff. The default uses recorded
   availability. Explicit source-backed retrospective receipts may reconstruct
   the original evidence clock; actual review and assembly times remain unchanged.
4. Fit imputation, scaling, and logistic coefficients on the remaining rows.
5. Score all eligible observations in the holdout year using that frozen model.

Default minimum support is **five distinct positive events**, **20 distinct
negative issuers**, and **two chronological test years**. Positive identity comes
from the reviewed event identity normalized by the shared validator; repeated
weekly observations of one acquisition do not become five acquisitions. These
floors protect basic fitting mechanics and are not a claim of adequate
statistical power.

The `--min-train-positive-events`, `--min-train-negative-companies`, and
`--min-test-years` options can increase these requirements. They cannot lower the
floors. Missing classes, insufficient support, temporal leakage, unsupported
membership, unreviewed labels, or optimizer nonconvergence block the run.

The regularization value defaults to `C=1`. `--regularization-c` permits an
explicit alternative; choose it before examining heldout results. There is no
hyperparameter search, random split, class balancing, or automatic promotion.

Fold reports distinguish `training_outcomes_available_through` from
`actual_label_assembly_available_through`; retrospective source reconstruction
never asserts a historical review or a forward prediction seal.

Each feature's median is fitted only on the training partition. A feature that
is entirely missing in training is filled with zero, and its missing indicator
remains explicit. The artifact records observed training counts, medians,
standardization parameters, coefficients, intercept, solver iterations, and
dependency versions. All numerical features are followed by all missing
indicators in the portable transformation order.

## Artifacts and evidence interpretation

A successful run writes immutable JSON files whose filenames contain their
content hashes:

- `final-model-*.json`: portable research model fitted on all eligible mature
  observations after chronological evaluation;
- `prediction-panel-*.json`: actual retrospective holdout predictions with fold,
  feature, training-dataset, model, and timestamp lineage;
- `evaluation-*.json`: cross-sectional cohort metrics, annual aggregates,
  deduplicated deal capture, and calibration diagnostics; and
- `training-report-*.json`: configuration, support, purged counts, training
  observation identifiers, fold models, final model, and complete evaluation.

Each fold also estimates a constant base rate from its **actual purged training
partition** and evaluates that unchanged constant on the same holdout rows.
The comparator records training-source hash, cutoff, support, observation IDs,
and label-availability lineage, with Brier score, log loss, and average precision.
Its top-k metrics are null because a constant has no ranking discrimination.
In trainer-produced annual evaluation, `past_only_base_rate_comparator` uses
this actual training evidence, including the first holdout year. The standalone
evaluator's narrower estimate from prior holdout rows is retained separately as
`heldout_history_base_rate_comparator`. Both rates describe company-observation
rows, not counts of unique acquisition events.

The complete report also stores the hash of the exact source file. JSON model
parameters can be applied without sklearn; no pickle or executable model format
is loaded. An existing artifact is never overwritten with differing content.
Reruns record actual creation times, so identical source data can produce another
immutable run even when learned numerical parameters are identical.

Heldout logistic estimates are included **only for retrospective probability
quality and calibration evaluation**. They are not declared calibrated
acquisition probabilities. The enclosing training report records that fitting
occurred; the nested evaluator records only its own evaluation work and does
not itself train a model.

The final research model is refitted after the holdout predictions have been
formed. Its later training observations do not replace the frozen fold models
used for historical evaluation. No fitted artifact is automatically activated
in the local app. `validated_predictive_edge` remains false and calibration
status remains unvalidated; the software does not promote a model merely because
it fitted successfully or produced attractive retrospective metrics.

## Apply a portable model to current feature rows

```bash
python3 scripts/train_baseline.py \
  --apply-model /path/to/final-model-HASH.json \
  --current-features /path/to/current-company-features.json \
  --output-dir output/baseline_training
```

The current input uses `schema_version: current-company-features-v1`, exactly
matching `feature_names` order and `feature_units`, and an `observations` array.
Each row provides `cik`, `observation_at`, `information_cutoff_at`,
`feature_max_available_at`, `features`, and explicit risk-set eligibility. No
future outcome label is supplied.

The observation must follow model creation, the information cutoff must cover
the model's training cutoff, and features must have been available by that
information cutoff. Future observations and duplicate CIK/date rows are
rejected. Excluded or unconfirmed issuers are retained with no score.

Eligible rows receive the **raw logistic decision score** for research; it is
unbounded and is not a 0–100 confidence score. `probability` and
`deal_probability_12mo` remain null. A separate calibration and promotion process
is required before any user-facing acquisition probability can be published.

Missing inputs or failed contracts return exit status **2** with an explicit
JSON blocker. Successful fitting or current research scoring returns **0** with
artifact paths. Neither operation changes the active application model.
