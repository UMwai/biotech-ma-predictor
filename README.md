# Biotech M&A Predictor

The objective is to learn from historical acquisitions and comparable companies
that were not acquired, then rank currently public biotech/pharma companies by
their likelihood of announcing an acquisition within the next 12 months. Inputs
must reflect what was known before each historical prediction date. Likely buyers
and strategic-fit explanations are supporting outputs.

The current local research desk supports building and inspecting that system.
Its current scores use hand-set heuristics; a model learned from acquisition
history, calibrated probabilities, and validated predictive performance are not
available yet. Current-data refresh and historical model development are separate
requirements; rebuilding local reports does not refresh their source data.

## Run locally

Use Python 3.12. The supported application uses local CSV/JSON artifacts and does
not need cloud services, PostgreSQL, Redis, RabbitMQ, Clerk, or API credentials.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python scripts/run_local_research.py
.venv/bin/python run_api.py
```

Open **http://127.0.0.1:8000**. The launcher refuses non-loopback addresses.
For runtime only, install `requirements.txt` instead of `requirements-dev.txt`.
If using uv, `uv venv --python 3.12` followed by
`uv pip sync --python .venv/bin/python requirements-dev.txt` provides the same environment.

A fresh clone can build the local desk from the committed, dated market artifacts.
Git includes compact historical review receipts and derived status, but excludes
raw source downloads, full-text extraction caches, Alpaca bars, sealed local runs
and browser verification artifacts. Replaying historical financial/outcome
evidence or rebuilding market features requires restoring the matching local
source archive, or collecting and reviewing new sources. Missing source bytes
fail verification; receipt files alone do not reproduce the historical dataset.
Artifact paths and results documented below describe local runs, not files
distributed in every clone.

The desk provides a searchable eligible watchlist, excluded-company review,
company asset/source details, evidence coverage, dated inputs, and downloadable
Markdown reports. Missing artifacts and unavailable evidence are explicit.
Source dates are shown separately for each layer. Rebuilding reports does not
make those inputs current; a public-source refresh leaves SEC screening and
curated risk evidence at their original dates until separately refreshed.

## Research snapshots

```bash
# Assemble saved market artifacts and evidence locally, with no provider calls.
.venv/bin/python scripts/run_local_research.py

# Re-evaluate cached raw inputs with hash and temporal checks, when caches exist.
.venv/bin/python scripts/run_local_research.py --rebuild-market

# Refresh exchange/FDA/trial data while retaining explicitly dated SEC caches.
.venv/bin/python scripts/run_local_research.py --refresh-public

# Fetch a new CURRENT market snapshot from public sources.
.venv/bin/python scripts/run_local_research.py --refresh \
  --user-agent "Your Name your-real-contact@your-domain.com"
```

Each successful build creates a new directory under `output/local_runs/` and
atomically updates `output/local_latest.json`. Failed builds preserve the prior
published snapshot. The manifest records artifact and code hashes, copied scoring
code, original input dates, and source retrieval freshness when available.
The dashboard follows the latest pointer on each request.

```bash
.venv/bin/python scripts/run_local_research.py --verify output/local_runs/RUN_ID
```

`--rebuild-market` deliberately permits stale cached inputs and labels them stale.
The raw cache retains content-addressed payloads and retrieval receipts across
refreshes. An old `--as-of` value does not reconstruct historical source state;
historical replay remains unavailable. Clinical records updated after the
requested cutoff are quarantined. Legacy artifacts without source lineage are
identified as unverified.

A `coverage_review.csv` in each run prioritizes ownership/linkage and company-risk
collection work. Source absence never clears a company of risk.

## Review acquisition labels

There are 54 primary-source announcement reviews from 2018–2025 in
[`data/history`](data/history/README.md). They are a selected positive seed;
complete historical comparison coverage remains unfinished. Verify and freeze
the seed with:

```bash
.venv/bin/python scripts/build_history_seed.py
```

When adding reviewed labels, rebuild dependent financial and cohort artifacts
in order before publishing a new local snapshot:

```bash
.venv/bin/python scripts/build_history_seed.py --freeze-labels-only
.venv/bin/python scripts/assemble_financial_seed.py --publish-to-seed
.venv/bin/python scripts/assemble_research_panel.py --publish-to-seed
.venv/bin/python scripts/build_history_seed.py
.venv/bin/python scripts/run_local_research.py
```

The label-only step verifies and freezes the new labels without publishing stale
derived status. The final full build checks all dependent source hashes.

The remaining SEC candidate ledger is a review queue. Work on
a copy of `output/historical_deal_candidates/adjudication_template.csv`.

```bash
.venv/bin/python scripts/adjudicate_deals.py --reviews path/to/reviews.csv
.venv/bin/python scripts/adjudicate_deals.py --reviews path/to/reviews.csv --freeze
```

Use `decision=include`, `exclude`, or `pending`. Completed decisions require a
reviewer, timezone-aware review timestamp, source URL, and review notes. Included
announcements also require reviewed target CIK/name, buyer, a sourced announcement
timestamp or explicit date-only precision, structure (`cash`, `stock`, `mixed`, or `tender_offer`),
control above 50%, and status (`pending`, `completed`, `terminated`, or `withdrawn`).
A terminated deal remains a positive announcement event. Pending cases are never
negative labels. Conflicting same-target/day events require review.

Freezes are content-addressed and cannot be overwritten. Freezing these
source-reviewed labels does not enable model training. Historical exchange
membership, delisted controls, dated features, complete outcome ascertainment,
and independent label-quality review remain required.

## Supervised baseline

The [historical cohort](docs/HISTORICAL_COHORT.md) preserves all 100 companies in
the original December 2020 Nasdaq addition notice and 300 planned observations.
It now contains 38 reviewed annual financial records across 28 issuers, eight
archive-reviewed outcome windows, and 18 assembled company observations.
Five acquisition events qualify for the first historical training fold;
**two of the required 20 comparison companies qualify**. Source review counts
and structurally complete observations are not interchangeable with training
support. No real-data model has been fitted.

Captured SEC indexes and submission packages can be verified offline with the
[source replay command](docs/REGULATORY_SOURCE_REVIEW.md#verify-captured-sec-packages-offline).
Verified downloads still require outcome, identity and exhibit review before
they can supply additional comparison labels.

```bash
.venv/bin/python scripts/assemble_research_panel.py --publish-to-seed
.venv/bin/python scripts/build_history_seed.py
.venv/bin/python scripts/run_local_research.py
```

The local desk displays these counts and downloads the source-bound coverage
report. The modeling environment can run the same assembly with `--train`;
it saves the precise blocking reason and produces no fitted model when the
evidence requirements are unmet.

The real-data financial seed now contains **eight pre-announcement annual reports
and 33 reviewed financial entries** in
[`data/history/financial_seed`](data/history/financial_seed/README.md). The
normalized feature artifact contains cash, assets, annual operating cash flow,
annual R&D when comparable, and derived annual cash burn. This is financial
evidence; it still needs historical company membership and reviewed outcomes for
both acquired and non-acquired companies before fitting.

```bash
.venv/bin/python scripts/assemble_financial_seed.py --publish-to-seed
.venv/bin/python scripts/build_history_seed.py
.venv/bin/python scripts/run_local_research.py
```

For larger SEC companyfacts/submissions collections with original-filing timing,
see [HISTORICAL_FINANCIALS.md](docs/HISTORICAL_FINANCIALS.md). Network collection
requires a real SEC contact header and stops on access denial. Saved source
exports can also be replayed offline. The current network probe returned HTTP403;
credentials/contact alone do not establish that this environment can reach SEC.

Public SEC filing-search inventories use a separate working route. See
[regulatory source review](docs/REGULATORY_SOURCE_REVIEW.md) for collection,
complete filing/exhibit replay and historical timing. Search results alone do not
provide negative labels.

The regularized logistic trainer learns coefficients from historical company
features using expanding annual splits and training-only preprocessing. It
requires mature, reviewed outcomes and actual historical listing membership;
the 54 positive seed labels alone cannot satisfy its input contract. No real-data
model has been fitted yet. Install the optional hashed `requirements-model.txt`
in a separate environment and follow [BASELINE_TRAINING.md](docs/BASELINE_TRAINING.md)
to train, compare later years against a past-only event-rate baseline, and apply
the portable model to matching current features. Current probability fields stay
null until calibration is validated.

The earlier [control research receipts](data/history/control_seed/README.md)
remain available as a separate pilot. The full cohort and its remaining gaps
are documented in [HISTORICAL_COHORT.md](docs/HISTORICAL_COHORT.md). Missing or
incomplete outcomes remain unknown.

## Alpaca market features

The historical model now has a local Alpaca collector and a separate verified
market-feature join for trailing price changes, volatility, volume and drawdown.
It preserves the reviewed labels and missing-data gaps and binds the selected
feed to fitted models. On September 13, the configured source at
`~/.config/alpaca_creds.env` successfully collected 4,745 historical SIP bars in
three cutoff groups. Subsequent primary-source review extended seven security
identity intervals without changing cohort entry or labels. All 18 observations
now have market features: 87 of 90 values are present, with three FPRX values
still withheld by the price-discontinuity check. Web research also recovered
annual reports for all 18 comparison candidates and broader filing sets for
APRE and FREQ. Their substantive outcome review remains incomplete, so the
first training fold still has two of the required 20 comparison companies.
See [source findings and current receipts](docs/WEB_SOURCE_RESEARCH_20260913.md).
See [Alpaca setup, credential precedence and collection](docs/ALPACA_MARKET_DATA.md).

## Validation and tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_predictions.py --help
```

The validation command accepts an explicitly documented prediction panel with
historical membership, feature/training cutoffs, reviewed outcomes, and provenance.
See the [prediction panel format](docs/PREDICTION_PANEL_FORMAT.md).
It rejects incomplete, censored, duplicate, unreviewed, or temporally invalid panels.
Retrospective out-of-time evaluations and forward sealed predictions have separate
contracts; neither is created by the old known-positive diagnostic.

Local checks cover artifact integrity, eligibility, unknown evidence, temporal
leakage, local API/report behavior, label review, and ranking metrics. Legacy
PostgreSQL/integration checks skip when their optional dependencies/services are
absent. The supported local workflow uses no database.

Dependencies are pinned with hashes. To intentionally update the locks:

```bash
uv pip compile requirements.in --python-version 3.12 --generate-hashes -o requirements.txt
uv pip compile requirements-dev.in --python-version 3.12 --generate-hashes -o requirements-dev.txt
```

## Optional container

```bash
docker compose up --build
```

This starts one local research service and publishes only `127.0.0.1:8000`.
It mounts `output/` read-only. Build a snapshot before starting the container.

## Scope and remaining work

See [local implementation status](docs/LOCAL_IMPLEMENTATION_STATUS.md) and the
[prediction implementation plan](docs/PREDICTION_IMPLEMENTATION_PLAN.md).
The older multi-service API, Streamlit dashboard, SaaS integrations, and deployment
scripts are legacy code, outside the supported local path. Their historical
requirements are retained in `requirements-legacy.txt`.

Cloud Build and GitHub deployment workflows are archived under
[`docs/archive/cloud/`](docs/archive/cloud/README.md). No automatic cloud deployment
runs from this working tree. Existing external cloud resources were not inspected
or changed.

## License

Proprietary — AIvestor Labs LLC
