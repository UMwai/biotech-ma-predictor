# Biotech M&A Prediction Implementation Plan

**Draft date:** 2026-07-22
**Scope:** Publicly traded U.S. drug and biotech companies
**Primary output:** A weekly, point-in-time ranking of companies by probability of an acquisition announcement within 12 months

## Implementation status (2026-07-22)

The current-market vertical slice is operational:

- the live U.S.-listed drug/biotech universe is built from current Nasdaq and SEC identifiers;
- marketed Orange Book and Drugs@FDA BLA assets are ingested and scored;
- active industry-sponsored ClinicalTrials.gov interventions are ingested and scored;
- public-company entity matches include confidence and an unmatched-owner backlog;
- recent SC 14D9 and DEFM14A filers are conservatively removed from the prediction risk set;
- raw responses are cached with retrieval metadata and hashes; and
- complete company, asset, exclusion, manifest, and summary artifacts are published under `output/market_evaluation/`.

The first historical-label foundation is also operational:

- SEC SC 14D-9 and DEFM14A filings are collected from 2018 forward with primary-document URLs;
- related amendments and filings are clustered into durable CIK/date candidates;
- Schedule 14D-9 target signals are separated from DEFM14A cases that require role adjudication;
- a reviewer template is generated without pre-filling unverified announcement facts;
- contemporaneous annual 10-K/20-F/40-F biotech reporting-company risk sets provide a historical comparison denominator; and
- rare-event ranking metrics keep arbitrary scores separate from probability metrics.

This completes a **current cross-sectional research ranking and provisional historical event/risk-set foundation**, not the historical probability model. Candidate adjudication, historical exchange membership, point-in-time feature panels, walk-forward training, calibration, and forward sealing remain required before the output can be called a validated M&A probability or edge.

## 1. Outcome we are building toward

Build a research system that can answer, as of a historical or current date:

> Among the eligible public biotech companies that existed on this date, which were most likely to announce a change-of-control transaction during the next 12 months, and why?

The first useful product is a ranked watchlist, not a claim that we can identify every future acquisition. Each prediction must include:

- calibrated 6-, 12-, and 24-month probabilities;
- rank and percentile within the eligible universe;
- the point-in-time feature values used by the model;
- the leading positive and negative drivers;
- data freshness and coverage flags; and
- a model and dataset version.

This is a research signal. It should not be presented as investment-ready until it passes both out-of-time backtesting and a forward paper-trading period.

## 2. Precise prediction contract

### Population

Begin with U.S.-listed, operating drug-development and biotechnology companies. A company enters the weekly risk set only when it:

- has an active common-equity listing;
- is identifiable by ticker, CIK, and a durable internal company ID;
- has a relevant biotech/pharma classification or an adjudicated inclusion;
- has sufficient public data to calculate the core features; and
- has not already announced a change-of-control transaction.

Historical constituents must be reconstructed as they existed at each observation date. A current ticker list is not an acceptable historical universe because it creates survivorship bias.

### Event label

The primary positive event is the **first public announcement date** of a definitive transaction expected to transfer control of more than 50% of the target company. Use announcement, not completion, because announcement is when the tradable price response normally occurs.

Include cash, stock, and mixed-consideration acquisitions and tender offers. Retain failed or later-terminated acquisitions as positive announcement events for this target definition. Store separate outcome fields for completed, terminated, withdrawn, and pending.

Do not silently mix these into the primary label:

- asset purchases;
- licensing or collaboration agreements;
- minority investments;
- reverse mergers used mainly as a listing mechanism;
- restructurings; or
- acquisitions in which the public biotech is the buyer.

Those should be separate event classes and can become later prediction targets.

### Observation cadence and horizons

- Create one observation per eligible company per Friday, or the prior trading day.
- Predict acquisition announcement within 26, 52, and 104 weeks.
- Use a one-trading-day information cutoff: a Friday snapshot may only use information publicly available by the previous market close.
- Censor companies when they leave the risk set because of delisting, liquidation, bankruptcy, or the end of the dataset.

## 3. Current repo assessment

The repository already contains useful building blocks:

- SEC, ClinicalTrials.gov, FDA, and financial ingestion modules;
- company, signal, score, report, and watchlist models;
- interpretable component scorers and target-ranking code;
- API, database, orchestration, reporting, and valuation scaffolding; and
- a small curated watchlist and historical-deal script.

It does **not yet contain validated predictive evidence**:

- `scripts/backtest.py` contains 11 known acquisition targets but no contemporaneous non-acquired companies.
- Several inputs are hand-entered after the deals are known, so their point-in-time availability is not proven.
- The backtest reports the percentage of known deals above a threshold, but cannot calculate false positives, precision, lift, calibration, or economic usefulness.
- Historical deals are compared with a current company universe, which mixes time periods and market regimes.
- `score_patent()` and `score_insider()` are placeholders in `scripts/score_companies.py`.
- The repo has multiple scoring paths and weight sets that are not yet governed by one versioned model contract.
- Several API routes still return mock data.
- The isolated market-research suite is green. The base branch's unrelated
  database suite still has a pre-existing SQLAlchemy declarative-name
  collection error and requires a separate database-layer fix before a clean
  full-suite result can be claimed for this branch.

The existing scores should therefore be labeled **heuristic research scores**, not acquisition probabilities.

## 4. Data foundation

### 4.1 Entity master and historical universe

Create a durable entity model before training:

| Entity | Required keys | Important relationships |
|---|---|---|
| Company | internal ID, CIK, LEI when available | tickers, names, listings, subsidiaries |
| Security | ticker, exchange, effective dates | company, price history |
| Drug/asset | normalized asset ID, generic/code names | owner history, sponsors, indications |
| Trial | NCT ID | drug, sponsor, indications, sites |
| Acquirer | internal ID, CIK | therapeutic portfolio, deal history |
| Deal | internal deal ID | target, acquirer, announcement and outcome dates |

Names and tickers change. All aliases and ownership relationships need effective start/end dates. Entity resolution must be auditable; fuzzy matches should be queued for manual review rather than automatically accepted at low confidence.

### 4.2 Point-in-time storage contract

Every raw record and derived feature must retain:

- `source_name` and source URL or accession ID;
- `effective_at`: when the fact describes the world;
- `published_at`: when the source first made it public;
- `ingested_at`: when our system received it;
- `available_at`: earliest timestamp the model is permitted to use it;
- source revision/version when applicable;
- content hash; and
- parser and feature-code versions.

Raw source payloads should be append-only. Corrections create new versions rather than overwriting the state used by an old prediction.

### 4.3 Source order

Use authoritative public data first and add licensed sources only where they materially improve history or coverage.

1. **SEC EDGAR**
   - Build the public-company universe and filing history from the submissions bulk/API data.
   - Derive cash, debt, R&D, operating cash flow, shares, dilution, and financing features from point-in-time XBRL facts.
   - Parse 8-K, 10-K, 10-Q, S-3, 424B, DEF 14A, SC 13D/G, and Form 4 text/events.
   - Use 8-K Item 1.01 and merger exhibits, Schedule TO, Schedule 14D-9, and merger proxies to build and verify deal labels.
   - Official reference: [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

2. **ClinicalTrials.gov**
   - Track trial phase, status, enrollment, primary completion, results, sponsor/collaborator changes, endpoints, and update velocity.
   - Retain snapshots or archived versions; querying only the current record would leak later revisions into historical training examples.
   - Official references: [ClinicalTrials.gov API](https://clinicaltrials.gov/data-api) and [study downloads and snapshot options](https://clinicaltrials.gov/data-api/how-download-study-records).

3. **FDA**
   - Track approvals, designations where reliably available, application ownership, exclusivity, and approved product portfolios.
   - Use the monthly historical files where available rather than applying the current product state to old dates.
   - Official references: [Orange Book files](https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files) and [Purple Book downloads](https://purplebooksearch.fda.gov/index.cfm?event=downloads).

4. **Market and security data**
   - Adjusted prices, volume, volatility, shares outstanding, financing dates, market capitalization, delistings, and corporate actions.
   - Select a provider with point-in-time delisted-security coverage. `yfinance` can support exploration but should not be the historical system of record.

5. **Patent data**
   - Patent families, assignees, remaining life, composition-of-matter coverage where identifiable, ownership changes, and litigation/challenges.
   - Treat patent-to-drug linking as a separate quality-controlled process. Development phase is not a valid substitute for patent strength.
   - Official starting point: [USPTO Patent Assignment Dataset](https://www.uspto.gov/ip-policy/economic-research/research-datasets/patent-assignment-dataset).

6. **Optional licensed/news data**
   - Historical press releases, earnings-call transcripts, investor presentations, analyst estimates, and comprehensive deal feeds.
   - Add only after confirming archive depth, publication timestamps, redistribution rights, and delisted-company coverage.

## 5. Label dataset and quality controls

Build `deal_events` as an independently auditable dataset before model training. Each row should include target/acquirer IDs, announced timestamp, transaction structure, headline and contingent value, status dates, source filings, and reviewer status.

Suggested label workflow:

1. Generate candidates from SEC filing types and merger-related exhibits/text.
2. Extract candidate target, acquirer, announcement date, structure, and value.
3. Deduplicate amendments and filings related to the same deal.
4. Require a high-confidence deterministic match or human adjudication.
5. Reconcile a sample—and ideally all positives—against an independent deal source.
6. Generate company-week outcomes only after the event table is frozen and versioned.

Quality gates:

- at least 99% of positive labels have a primary-source filing or issuer announcement;
- 100% of positives have a reviewed announcement date and target entity match;
- inter-reviewer agreement is measured on ambiguous event classes;
- label corrections are versioned; and
- a negative is never interpreted as “will never be acquired”—it means no event was observed within the selected horizon.

## 6. Feature families

Favor values and changes observable before announcement. Keep missingness indicators because absence of data can itself affect model confidence.

### Target and asset quality

- number and stage of owned clinical assets;
- recent phase transitions, trial starts, completions, enrollment changes, and result postings;
- asset differentiation using measurable evidence rather than unsupported labels;
- approved-product revenue concentration and growth;
- regulatory milestones and remaining exclusivity;
- patent life and ownership stability; and
- platform breadth versus single-asset concentration.

### Financing and seller state

- cash and marketable securities;
- trailing operating cash burn and modeled runway;
- debt, going-concern language, shelf capacity, ATM usage, and recent offerings;
- dilution and share-count acceleration;
- restructuring, layoffs, and strategic-review language when supported by timestamped filings; and
- enterprise value relative to cash and risk-adjusted pipeline value.

Financial stress must not be assumed to monotonically increase acquisition probability. The model should learn interactions between financing pressure and asset quality.

### Acquirer demand and pairwise strategic fit

- acquirer cash/debt capacity and historical deal-size distribution;
- therapeutic-area and modality deal history;
- marketed-product patent/exclusivity cliffs;
- pipeline gaps and recent trial failures;
- existing target partnerships, licenses, equity stakes, or board relationships;
- portfolio similarity/complementarity; and
- antitrust concentration proxies.

Start company-level prediction first. Add a separate target-acquirer pair model only after the target model has stable out-of-time lift.

### Market and regime context

- target returns, drawdown, volatility, liquidity, and abnormal volume;
- XBI/IBB and therapeutic-peer returns;
- sector financing conditions and IPO/follow-on activity;
- trailing biotech M&A count/value using only already-announced deals; and
- rates and broad risk regime.

## 7. Modeling sequence

### Model A: governed heuristic baseline

Rebuild the current score on point-in-time features. Remove placeholders, version the weights, and avoid calling the result a probability. This provides continuity with the current product and an interpretable benchmark.

### Model B: simple statistical baseline

Train a regularized discrete-time logistic hazard model on the company-week panel. This is the first probability model because it handles changing covariates, censoring, and varying time at risk while remaining inspectable.

### Model C: nonlinear challenger

Train a gradient-boosted tree model using the same feature contract and splits. Use constrained or monotonic behavior only where domain logic is genuinely defensible. Compare it with the statistical baseline; do not promote it merely because in-sample metrics are higher.

### Model D: optional survival and pair models

Evaluate survival forests/boosting and a target-acquirer pair ranker only after Models A-C are reproducible. NLP-derived filing and transcript features should be challengers with ablation evidence, never silent replacements for primary structured signals.

Probability calibration must use a held-out calibration interval inside each training window. Candidate methods are isotonic regression and Platt scaling, selected strictly out of sample.

## 8. Leakage-resistant validation

Use expanding-window walk-forward evaluation, for example:

- train: 2012-2018, validate/calibrate: 2019, test: 2020;
- train: 2012-2019, validate/calibrate: 2020, test: 2021;
- continue one year at a time through the last complete test year.

Apply a purge/embargo around split boundaries for overlapping 6/12/24-month labels. Model selection must never use the final test periods.

Required comparisons:

- random/base-rate ranking;
- market-cap and cash-runway-only baselines;
- the current governed heuristic;
- statistical hazard model; and
- nonlinear challenger.

Primary metrics:

| Category | Metrics |
|---|---|
| Ranking | precision@5/10/20, recall@k, lift@k over base rate, average precision/PR-AUC |
| Probability | Brier score, log loss, calibration slope/intercept, reliability by decile |
| Timing | median lead time for captured deals, recall by 6/12/24-month horizon |
| Stability | turnover, rank correlation, performance by year, market-cap band, and therapeutic area |
| Coverage | eligible-universe coverage, missing-feature rates, stale-data rates |

ROC-AUC can be reported but must not be the headline metric for this rare-event problem.

Economic simulation is a later gate. If added, it must use prices available after prediction publication, delisted securities, realistic execution delay/costs, position limits, and comparison with a biotech benchmark. It must separate acquisition returns from ordinary biotech beta and clinical-event exposure.

## 9. Promotion gates

### Research baseline complete

- versioned historical universe and deal labels exist;
- all training features satisfy the point-in-time contract;
- leakage tests and dataset manifests pass;
- walk-forward metrics beat simple baselines in most test folds; and
- predictions can be reproduced from a dataset and model version.

### Candidate model complete

- positive lift@10 and lift@20 is stable across multiple out-of-time years;
- calibration is acceptable or probabilities are explicitly withheld;
- results survive ablations, label audits, and reasonable universe definitions;
- no single deal or therapeutic area explains most of the measured lift; and
- the model card documents intended use, limitations, and failure modes.

### Investment-research ready

- at least one full 6-12 month forward paper period has run without retrospective edits;
- weekly predictions were sealed before outcomes;
- data freshness and operational failures are measured;
- watchlist turnover and capacity are practical; and
- realized forward lift is directionally consistent with backtests.

Until these gates pass, use “research ranking” or “heuristic score,” not “validated edge.”

## 10. Repository implementation map

Keep the current API/reporting shell, but introduce one canonical research path:

```text
src/
  data/
    entities.py
    point_in_time.py
    sources/
  labels/
    deal_events.py
    adjudication.py
  features/
    financial.py
    clinical.py
    regulatory.py
    patent.py
    acquirer_fit.py
    market.py
  prediction/
    contract.py
    heuristic.py
    hazard.py
    challenger.py
    calibration.py
    registry.py
  evaluation/
    splits.py
    metrics.py
    walk_forward.py
    leakage.py
scripts/
  build_entity_master.py
  build_deal_labels.py
  build_weekly_panel.py
  train_model.py
  run_walk_forward.py
  publish_research_watchlist.py
artifacts/                 # ignored generated outputs
  datasets/
  models/
  evaluations/
```

Each command should accept explicit date ranges and versions, emit a machine-readable manifest, and fail closed when required point-in-time fields are unavailable.

The existing `src/scoring` code can supply the governed heuristic baseline. `scripts/score_companies.py` and `scripts/backtest.py` should eventually become thin wrappers or be retired after parity tests, so weights and logic cannot drift across multiple implementations.

## 11. Phased delivery plan

### Sprint 0 — Contract and trustworthy baseline (2-3 days)

- Add the prediction/event/universe definitions as executable configuration.
- Fix the async database test harness and establish a green baseline.
- Mark current backtest output as heuristic-only.
- Inventory every feature, its source, historical start date, availability timestamp, and current implementation status.
- Choose the historical market-data source and licensing boundary.

**Exit:** Prediction contract is approved, tests are green, and no existing output is mistaken for validated probability.

### Sprint 1 — Deal labels and universe (1-2 weeks)

- Implement entity/ticker history.
- Create SEC-derived acquisition candidates and adjudication workflow.
- Build an initial 10-15 year deal-event dataset.
- Reconstruct eligible company-month/week risk sets, including delisted firms.
- Publish label coverage and ambiguity reports.

**Exit:** Frozen version 1 label dataset and historical universe with primary-source provenance.

### Sprint 2 — Point-in-time core features (2-4 weeks)

- Implement SEC financial snapshots and financing events.
- Implement versioned ClinicalTrials.gov snapshots and changes.
- Add FDA approval/product history.
- Add security prices, shares, delistings, and corporate actions.
- Produce a feature-availability and missingness report for every year.

**Exit:** Reproducible company-week panel whose rows use no future information.

### Sprint 3 — Baselines and honest backtest (1-2 weeks)

- Port the heuristic to the canonical feature store.
- Train the discrete-time hazard model.
- Add walk-forward splits, embargoes, calibration, and rare-event metrics.
- Produce per-fold predictions, metrics, calibration plots, and top-k case reviews.

**Exit:** First defensible answer to whether the repo has predictive lift beyond base rates.

### Sprint 4 — Challenger features/models (2-4 weeks)

- Add patent linkage, filing-text changes, regime features, and acquirer-demand features in isolated increments.
- Train nonlinear challenger and run feature-family ablations.
- Add target-acquirer matching only if target-ranking lift remains stable.

**Exit:** Promoted candidate beats the baseline out of time and the source of improvement is understood.

### Sprint 5 — Weekly shadow operation (minimum 6 months)

- Generate and cryptographically hash/seal weekly predictions before outcomes.
- Monitor freshness, missingness, drift, turnover, calibration, and captured events.
- Do not revise historical predictions; issue corrected model versions prospectively.
- Review performance monthly without tuning on each new deal.

**Exit:** Forward evidence supports—or rejects—investment-research use.

## 12. First implementation slice

The best first slice is not another scoring-factor adjustment. It is a small vertical backtest foundation:

1. Define `DealEvent`, `CompanyIdentity`, `UniverseMembership`, and `ObservationCutoff` models.
2. Seed 50-100 acquisition announcements from SEC primary sources with reviewed dates.
3. Build monthly historical risk sets for 2018-2025, including delisted names.
4. Add only four defensible point-in-time features: market cap, cash, trailing cash burn, and lead-asset clinical phase.
5. Train the heuristic and regularized hazard baseline.
6. Report base rate, precision/lift@10 and @20, PR-AUC, Brier score, and per-year results.
7. Stop and inspect leakage/entity errors before expanding features.

This slice will reveal whether data plumbing and labels are sound before the project spends time on NLP, patent mapping, premium estimation, dashboards, or additional model complexity.

## 13. Decisions needed before Sprint 1

1. **Market scope:** Recommend U.S.-listed public companies first. Private-company M&A requires different data and should be a separate project.
2. **Primary objective:** Recommend company change-of-control announcement. Asset deals and licensing should remain separate labels.
3. **Market data:** Choose a paid point-in-time/delisted-equity provider or explicitly accept a weaker research-only free-data MVP.
4. **History:** Recommend starting in 2012 if source coverage permits; use 2018 only for the first plumbing slice.
5. **Product cadence:** Recommend weekly rankings; daily scoring adds noise and operational cost before there is evidence it adds lift.

## 14. Principal risks

- **Rare events:** Small positive counts can make performance appear stronger than it is.
- **Survivorship bias:** Current-company lists erase acquired, bankrupt, and delisted controls.
- **Look-ahead leakage:** Revised trial records, restated filings, current patent ownership, and current classifications can contaminate historical rows.
- **Entity leakage:** Drug, sponsor, ticker, and company name changes can create false joins.
- **Label ambiguity:** Change of control, reverse merger, asset sale, and licensing events are economically different.
- **Market-regime drift:** Acquisition appetite, financing availability, and therapeutic-area demand change materially over time.
- **Narrative overfitting:** Post-deal rationales often sound predictive but were not measurable beforehand.
- **Probability misuse:** A useful ranking can still have poorly calibrated absolute probabilities.

The system should surface these risks in its artifacts rather than hide them behind a 0-100 score.
