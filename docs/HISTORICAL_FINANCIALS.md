# Point-in-time SEC financial inputs

The collector reads SEC companyfacts and submissions payloads through the
repository's hash-checked `HttpCache`. It produces historical **feature inputs**,
not acquisition labels, historical exchange membership, or a training-ready
dataset. Every output keeps `training_allowed: false`.

## Collect or replay source data

```bash
python3 scripts/collect_historical_financials.py \
  --ciks data/history/frozen_labels.json \
  --cutoff 2020-01-01 \
  --cutoff 2021-01-01 \
  --offline
```

The issuer input may be frozen-label JSON containing `labels[].target_cik`, a
JSON `ciks` array inside an object, or CSV with a `cik` or `target_cik` column.
This extracts identifiers only; it does not treat the input labels as proof of
historical exchange membership or create non-acquired controls.

Repeat `--cutoff` for several snapshots. A date alone means **UTC midnight at the
start of that date**. An explicit timezone-aware ISO timestamp supports an
intraday cutoff. Future cutoffs are rejected.

Live requests require an explicitly supplied `SEC_USER_AGENT` containing the
user's real contact email, or the corresponding `--user-agent` argument. No
identity or contact information is generated. A supplied contact does not
guarantee SEC access. Offline replay requires no contact and performs no network
requests. Add `--refresh` for new source retrievals; otherwise existing cached
bytes retain their original retrieval metadata. Offline and refresh cannot be
combined.

The collector requests:

- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`;
- `https://data.sec.gov/submissions/CIK##########.json`; and
- issuer-specific older submissions files named by the main submissions index.

At most ten historical submissions files are requested per issuer by default;
`--max-submission-files` can explicitly raise the limit. Requests are sequential
with pauses. An HTTP 403 stops the collection and writes a blocked status
receipt. It does not retry with another identity or assume authentication is the
cause. The shared cache may retry transient network errors, HTTP 429, or server
errors according to its bounded retry policy.

## Feature definitions

| Feature | Unit | Eligible source concepts, in priority order |
|---|---|---|
| `cash_usd` | USD | `us-gaap:CashAndCashEquivalentsAtCarryingValue`; `ifrs-full:CashAndCashEquivalents` |
| `assets_usd` | USD | `us-gaap:Assets`; `ifrs-full:Assets` |
| `annual_operating_cashflow_usd` | USD/fiscal_year | `us-gaap:NetCashProvidedByUsedInOperatingActivities`; `ifrs-full:CashFlowsFromUsedInOperatingActivities` |
| `annual_rd_usd` | USD/fiscal_year | `us-gaap:ResearchAndDevelopmentExpense`; `ifrs-full:ResearchAndDevelopmentExpense` |
| `annual_cash_burn_usd` | USD/fiscal_year | Derived as `max(-annual_operating_cashflow_usd, 0)` |

All raw facts must have SEC `USD` units. Cash and assets require instant facts.
Annual flows require a start date and **330–400 inclusive calendar days**. A
quarterly or year-to-date value is not multiplied into an invented annual value.
Reported annual totals are retained without annualizing their exact day count.

Missing values remain null. In particular, missing operating cash flow produces
missing burn, while an observed positive operating cash flow produces burn zero.
An explicit zero R&D expense also remains zero. Broader cash-plus-investment or
restricted-cash concepts are not silently substituted into `cash_usd`.

## Historical availability and restatements

Facts require a valid original accession number, filed date, eligible periodic
form, and a period end no later than cutoff. The collector does not use `fy`,
`fp`, `frame`, or the current source retrieval date as historical availability.

Feature availability uses a conservative **filed-date-plus-36-hours proxy**:
12:00 UTC on the following day, even when submissions contains an exact
acceptance timestamp. SEC acceptance is not public dissemination; the
[SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
describes a delay after acceptance that can increase. This daily research model
therefore does not use acceptance as an intraday public-availability timestamp.

When the original accession appears in recent or archived submissions, a
timezone-aware `acceptanceDateTime` whose filing date agrees is retained as
`accepted_at` and `acceptance_datetime_raw` provenance. It does not move feature
availability earlier than the proxy. Missing, naive, or inconsistent acceptance
metadata leaves `accepted_at` null. Each selected fact explicitly records
`public_availability_measured: false`: the proxy is a conservative assumption,
not a measured HTTP publication time or a guarantee about exceptional SEC delays.

Only facts available by cutoff can compete for selection. The most recent
eligible period wins; declared concept priority then applies, followed by the
latest filing available for that period. A restatement becomes usable only after
its own accession was available. Its later value cannot overwrite the earlier
snapshot. If the current feed retains only a later restated observation, the
earlier snapshot remains missing instead of being backfilled. Conflicting
values or periods at the same winning concept/availability remain missing and
are flagged for review.

This remains a reconstruction from the SEC facts retained in retrieved payloads.
Historical omissions and taxonomy coverage gaps cannot be recovered by this
collector. Exact original filing documents may still be needed for audit or
missing-concept extraction; source identity is preserved to support that work.

## Output and provenance

The default output directory is `output/historical_financials`; source cache is
`data/history/sec_financial_raw`. Both can be changed explicitly.

`financial-snapshots-HASH.json` contains:

- `schema_version: sec-financial-feature-snapshots-v1`;
- collection time, input issuer-file hash, `feature_names`, and `feature_units`;
- `observations`, with CIK, `information_cutoff_at`, `feature_max_available_at`,
  the feature dictionary, per-feature provenance, and missing-value reasons;
- actual source receipts and coverage counts; and
- explicit feature-only semantics with training disabled.

The feature-availability maximum is null when no source fact is available. Rows
do not invent decision timestamps, membership intervals, or future outcomes.
They must be joined to independently verified observation, membership, and label
records before constructing the trainer's historical-company-features schema.

Per-fact provenance includes concept, original accession, form, filed date,
period start/end, duration, value, availability method, and the companyfacts and
submissions receipts used. Receipt hashes are calculated from the actual raw
response bytes, not reserialized JSON. The existing cache retains immutable raw
blobs and retrieval receipts; refreshing does not erase old source versions.

A companion immutable manifest links the feature artifact by path and exact
content hash, retains source receipts, and summarizes coverage. Successful
collection returns exit status **0** even when some features are missing; coverage
must be inspected. Failed collection returns **2** and an immutable blocked
receipt. An HTTP failure receipt records the URL and status and explicitly says
no financial payload was received. It is not a substitute for financial data.
