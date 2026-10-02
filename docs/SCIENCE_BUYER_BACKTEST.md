# Scientific and buyer M&A research v1

This model ranks operating biotech observations for the first definitive
whole-company acquisition announcement transferring more than 50% control within
365 days, using the existing reviewed labels. An announcement still counts if
the transaction later terminates. Licenses, minority investments, collaborations,
asset purchases, strategic-review statements and public interest are signals;
they are not acquisition labels. Public interest does not establish private
negotiations. Acquisition hit-rate does not establish investment return.

The checked-in weights are user-reviewable hypotheses, not trained deal
probabilities. Every weighted score has `probability: null`. The experiment
retains `outcome_exposed: true`, `validated_predictive_edge: false`,
`independent_confirmation: false`, and `return_backtest_performed: false`, even
for synthetic fixtures or self-disclosures of masked packets. This task assigns
no real historical science or buyer ratings through an LLM.

## Frozen hypothesis and rubric

Config schema is `ma-diligence-parameters-v1`; model and rubric version are
`ma-diligence-v1`. Inputs are integers 0 through 4, with higher positive ratings
indicating stronger hypothesized acquisition attractiveness. Unknown is **null
and blocks scoring**, including execution risk; missing evidence never means
low risk. Apply the rubric to evidence available at that observation's
information cutoff. Each field needs its own rationale, named actual reviewer,
actual review time, and one or more source records with locators.

| Field | Weight | 0 / 1 / 2 / 3 / 4 anchors | Evidence supporting interpretation |
|---|---:|---|---|
| clinical_evidence | .20 | No demonstrated clinical benefit or documented failed primary endpoint / human safety or activity only / controlled benefit with material uncertainty / convincing controlled efficacy and safety in a relevant population / replicated or pivotal confirmatory benefit | Original trial results, protocol and endpoint definitions, regulator reviews; distinguish exploratory analyses, sample size, comparators, durability and safety |
| clinical_differentiation | .15 | Documented inferior or undifferentiated profile / minor plausible advantage / clinically relevant potential advantage with mixed comparative support / compelling supported benefit, safety or administration advantage / strong comparative evidence of a major unmet-need advantage | Dated comparator studies, standards of care, original efficacy and safety disclosures; no unsupported cross-trial superiority |
| asset_rights | .10 | Material documented rights barrier / constrained geography or substantial encumbrance / partial but usable rights / broad transferable rights with manageable obligations / broad documented control and durable protection | Original licenses, patent filings, exclusivity, territory, consent, royalty and change-of-control clauses; review asset-specific limits |
| buyer_fit | .20 | Documented strategic mismatch / weak adjacency / credible portfolio or capability adjacency / strong supported portfolio and operating fit / explicit dated strategic priority with directly complementary capabilities | Candidate's original strategy, portfolio, trials, partnerships and filings at cutoff; never eventual acquirer or later deal rationale |
| buyer_capacity | .10 | Documented inability to fund or execute / severe funding or balance-sheet constraint / plausible capacity with meaningful constraints / sufficient supported financing and integration capacity / ample supported funding and execution capacity | Original cash, debt, financing commitments, transaction scale and operating disclosures; use comparable currency and dated fiscal periods |
| public_engagement | .10 | Reviewed defined public corpus shows no disclosed engagement signal / generic publicly expressed partnering interest / dated specific collaboration or licensing signal / explicit public strategic review or named interest / substantive publicly disclosed company-level pursuit still short of a definitive control announcement | Dated issuer, counterparty or regulator disclosures; absence requires reviewed corpus rationale, not a missing search result; private chronology revealed later is excluded |
| valuation_attractiveness | .15 | Documented valuation highly unattractive against stated dated framework / expensive with limited support / defensible but uncertain value / attractive against supported dated comparables / strongly attractive with supported risk-adjusted value | Historical market cap, enterprise value, net cash, rights economics and dated comparable assumptions. Explain units and denominator; never later acquisition premium or future prices |
| execution_risk | penalty .20 | Documented manageable risk / limited material risk / meaningful clinical, regulatory, rights, manufacturing or integration uncertainty / major supported impediments / severe documented impediments | Original safety, regulator, manufacturing, litigation, license and integration disclosures. Higher means greater risk; lack of evidence is null |

The full score is:

`100 * clamp(sum(weight[field] * rating[field] / 4) - .20 * execution_risk / 4, 0, 1)`.

Science-only retains clinical evidence, differentiation and rights weights.
Buyer-only retains buyer fit and buyer capacity weights; public engagement
belongs to the full model only.
Both descriptive ablations omit valuation and execution risk and retain the
full weights without renormalizing. They are not optimized alternative models.
These precise ablations, the buyer-selection rule, top-k tie policy and
undefined-metric policy are part of the immutable registered config.

Each observation supplies a dated finite candidate-buyer universe with source
provenance and an external completeness attestation. It need not exhaust every
possible buyer. Every declared candidate must have reviewed fit and capacity.
Select the maximum `.20 * buyer_fit + .10 * buyer_capacity`, breaking ties by
`buyer_id` ascending. The selected buyer and reason are saved; caller-selected
winners and eventual-acquirer fields are rejected. This mechanical selection
rule does not remove hindsight leakage in subjective ratings or universe choice.

## Registration and collection queue

Run from the repository root with `requirements-model.txt` installed:

```bash
python scripts/run_ma_experiment.py register \
  --parameters data/research/ma_parameter_set_v1.json --output-dir output/ma_v1
python scripts/run_ma_experiment.py template \
  --dataset data/history/panel_seed/panel.json \
  --registration output/ma_v1/ma-registration-<sha256>.json \
  --output-dir output/ma_v1
python scripts/run_ma_experiment.py run \
  --dataset data/history/panel_seed/panel.json \
  --registration output/ma_v1/ma-registration-<sha256>.json \
  --ratings collected-ratings.json --evidence-root /absolute/archived-evidence \
  --output-dir output/ma_v1
```

The registration reads only the parameter file and stores the full config,
exact raw JSON, raw and canonical parameter hashes, and actual registration
time. Content-addressed filename, canonical bytes and embedded parameter hashes
are verified when loading. It explicitly declares
`retrospective_development_parameters_after_outcome_inspection`. It is not a
historical preregistration or historical prediction seal. Parameter edits require
a new registration and experiment. Retain all prior outcomes, including blocked
attempts. V1 has no grid search, tuning loop, automated approval threshold or
predictivity pass rule.

The template enumerates every normalized observation ID from the shared dataset
validator, with bindings to the exact raw dataset, raw parameters, registration
artifact and rubric. It needs no evidence bytes to prepare. It is explicitly
incomplete and inadmissible. Make a separate filled sidecar and remove
`template_status: incomplete_inadmissible` only when collection is finished.
Fill one common nonempty `rating_batch_id`, each record's rubric,
`outcome_knowledge` (`exposed`, `masked_packet`, or `not_known`), six non-buyer
reviews and a source-bound candidate universe. Set `completeness_attested: true`
only as an actual external assertion, and provide `buyer_reviews` for every
`buyer_id` with both fit and capacity. Every normalized observation must occur
exactly once; no extra or unrated observations, duplicate IDs, or buyer subsets.
The template is the historical science/fit collection queue, not admitted data.

Each rating review has `value`, `rationale`, `reviewer`, `reviewed_at`, and
`sources`; the universe has the same review fields except `value`, plus
`buyer_ids` and `completeness_attested`. Each source has:

```json
{
  "source_uri": "https://publisher.example/original-document",
  "source_relative_path": "archive/original-document.html",
  "source_sha256": "<actual archived-byte sha256>",
  "source_locator": "specific table, passage, page or endpoint",
  "available_at": "2020-12-01T14:00:00+00:00",
  "retrieved_at": "2026-10-03T14:00:00+00:00",
  "version_status": "verified_original",
  "original_version_basis": "actual documented basis for original publication version"
}
```

These are schema examples, not evidence or fabricated historical ratings.
Only `available_at` is supported; no implicit `published_at` alias. Require
`available_at <= observation cutoff` and
`available_at <= retrieved_at <= reviewed_at <= actual now`.
Review must occur strictly after actual parameter registration. All timestamps
must include a timezone. Paths must be relative to the explicit evidence root;
path traversal and symlink escapes are rejected. Archived byte hashes must
match. The run defaults the evidence root to the dataset's parent if omitted.
Missing bytes, current-copy version status and missing source fields block.
Hash checks cannot establish original publication vintage, source completeness,
actual reviewer identity, impartial interpretation or authenticated masking.
Original-version assertions still require external audit.

## Retrospective comparison and blocked receipts

Readiness checks the shared membership, label and chronology contract, financial
features and units, ratings/source bindings, optional NumPy/sklearn availability,
and every planned annual fold before fitting. Errors accumulate, so missing
ratings do not conceal insufficient historical support. Financial inputs are
exactly `cash_usd`, `assets_usd` (USD), and `annual_operating_cashflow_usd`,
`annual_rd_usd`, `annual_cash_burn_usd` (USD/fiscal_year), copied without unit
conversion. Every feature field must be present for every supplied observation. Nullable
financial values use the existing baseline’s training-only median imputation
and missing indicators; every family retains the identical cohort. Unknown
qualitative ratings still block every family.

Annual heldouts start in 2023. Require at least two consecutive test years;
each training partition needs five distinct positive events and twenty distinct
negative companies. These floors are not adjustable. Match the trainer's exact
cutoffs: earliest information cutoff in the heldout year; only earlier-year
observations whose full horizon and effective label availability have matured
by that cutoff. Actual late label assembly and review times remain retained;
explicit original-source reconstruction is retrospective only. Preserve the
entire supplied cohort and all original membership/label/timing assertions.

Only when every gate passes does the runner call `train_baseline` with the
financial subset, fixed L2 regularization C=1, and the shared `TrainingConfig`.
The comparator's actual fit is separate from evaluation of frozen weighted
rankings. All four families share exact heldout membership and cutoffs. Saved
weighted panels have null probabilities and score/ablation parameter hashes;
actual creation/seal times remain late, not backdated. Weighted feature
availability is the conservative maximum across financial, all rating,
universe and every candidate source clock; actual rating review-through
is recorded separately and never substituted for historical availability. The full model's sole
primary metric is equal-observation-date mean cohort lift at 5. Cohorts without
positives have undefined lift and are omitted with explicit support counts.
Ties use observation ID ascending and effective k is bounded by cohort size.
The financial comparator and descriptive ablations use the same k=5 calculation.
`evaluate_panel` also retains its existing k=10/20 cohort diagnostics, AP,
precision/recall and financial probability/calibration diagnostics. Financial
probabilities are explicitly uncalibrated. No ROC or uncertainty claim is made.
Each year's constant base-rate comparator comes from its actual purged training
partition; the evaluator's heldout-history-only comparator is labelled separately.

Input-blocked runs return exit status 2 and save immutable receipts with no fit,
weighted evaluation, predictions or metrics, complete gaps and raw dataset,
ratings, registration, parameters and code hashes. Malformed inputs produce
failure receipts where possible. A comparator attempt that throws is recorded
as `comparator_fit_attempted`; a completed fit is reported separately, even if
a later evaluation failure blocks publication of predictions and metrics. Successful
model, score, panel, evaluation and overall experiment artifacts are immutable
and bind all inputs plus training, validation, metrics, the new modules and CLI.
No canonical source panel is mutated or published by these commands.

The current panel attempt is expected to remain blocked: missing qualitative
ratings and only four of the twenty first-fold negative-company floor. This
local-only dependency and its exact hash belong in the run receipt. A valid
20-row input contract is not enough support for model fitting or predictive
confirmation; synthetic successful runs validate mechanics only.

The October 2, 2026 attempt is retained with its
[parameter registration](../reports/ma_research_v1/ma-registration-4ba6d692e5149c505de575f3d1df314e51acc0729ca0d1df00adfcb74d0474fa.json),
[incomplete collection template](../reports/ma_research_v1/ma-ratings-template-dd331440526afe91d7a4e3bb99edfdc05b9b44314cb2939b71b9793f1653eff8.json)
and [blocked experiment receipt](../reports/ma_research_v1/ma-experiment-59daacd176b48d74ff0daa9b9233bbca8bbb10f1b33159f289c90c5a24961492.json).
Both 2023 and 2024 folds have five distinct training events and four of twenty
required negative training companies. The heldout cohorts contain only four
and five observations: top-five lift would not distinguish rankings on these
cohorts, so heldout coverage must expand as well as training support. No real
fit or metric was produced. These artifacts bind the separately maintained
local 20-row source panel; this feature branch does not distribute that input
or its source archive. Reproduction needs the exact input hash in the receipt,
and a changed input needs its own bound template and experiment.

## Separate evidence and open work

Licensing/partnering outputs, public-interest signals and control-acquisition
labels must remain distinct. There is no licensing prediction experiment or
investment-return calculation in v1. The model has inspected outcomes and uses
retrospectively reviewed qualitative evidence. Freeze-before-rating only limits
later parameter edits; it does not authenticate a blind review, remove sample
selection bias or establish predictive edge. See scikit-learn's
[common leakage pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)
and [nested versus non-nested selection example](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html)
for why preprocessing and model selection must respect evaluation boundaries.
V1 performs no selection search; any future parameter study requires a new
registration and retention of all results.

Forward source/rating custody, independently blinded review, untouched
confirmation, uncertainty inference, price-return economics (including timing,
entry/exit, costs, liquidity and benchmark comparisons), trading authority and
capital eligibility remain open. A high score, acquisition event, source hash,
or green synthetic test cannot satisfy those gates.
