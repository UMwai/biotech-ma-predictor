# Local implementation status

Updated September 14, 2026. The product objective is to learn from historical
acquisition announcements and comparable public biotech/pharma companies, then
rank current public companies for a definitive acquisition announcement within
12 months. **No real-data model has been fitted or validated.** The local desk
continues to identify its scores as a heuristic baseline and publishes no
calibrated acquisition probabilities.

## September 14: SEC source verification implemented

The new offline verifier reconstructs the selected SEC accession inventory,
checks captured responses and parses complete submission containers. Actual
replay verified APRE's 42 accessions and 707 embedded payloads, and FREQ's
48 indexes and 139 captured bodies. FREQ's raw indexes identify 812 missing
document-format payloads, with additional unresolved differences between public
document counts and visible index entries. These remain explicit review gaps.

Both reports keep outcome review and label admission disabled. No labels or
training requirements changed: the first fold still has five positive events
and two of the required 20 comparison companies. Commands and source limitations
are in [the regulatory review guide](REGULATORY_SOURCE_REVIEW.md#verify-captured-sec-packages-offline).

Release verification passed from a fresh copy of the staged files: **621 tests
passed in the modeling environment** (11 optional or format-specific skips),
and **612 passed in the minimal environment** (20 such skips). Fatal-error lint,
snapshot assembly and five local HTTP routes passed. Both SEC collections
replayed against the local archive; a receipts-only clone correctly returned
exit 2 for missing source bytes. No credential values were included in Git.

Git excludes raw archives and generated caches. A clone builds the dated
research desk; historical source replay requires the matching local archives.

## September 13: web sources recovered and listing gaps resolved

Primary-source review extended the seven earlier security-identity intervals
without changing cohort entry, labels or observation dates. The rebuilt dataset
has market features for **18 of 18 observations**, with **87 of 90 values
present**. FPRX retains three long-window nulls because its November 2020 price
jump triggers the existing discontinuity check. KDMN's NYSE-to-Nasdaq transfer
is explicitly preserved.

Exact SEC annual-report bodies were recovered for **all 18 comparison
candidates**. APRE's 42 selected accession packages contain 707 embedded
documents; FREQ's 48 accession indexes and 139 designated bodies are archived.
Substantive outcome, identity and exhibit review is still required before these
captures can supply new negative labels. The actual training attempt therefore
still stops at **2/20 comparison companies**, with five positive events.

Source replay and all **567 model-environment tests** passed, with three optional
skips. Current datasets, source limitations, primary links and the next review
steps are in [the September 13 research report](WEB_SOURCE_RESEARCH_20260913.md).
The local app still uses the separately documented September 8 snapshot.

## September 13 earlier checkpoint: historical Alpaca data collected

The configured source at `~/.config/alpaca_creds.env` successfully accessed
historical SIP data and collected all three planned cutoff groups: **4,745 raw
daily bars, 14 distinct tickers, 18 ticker-window series and three response
pages**, with no failed group or empty symbol series. Real-time
SIP entitlement remains untested. Credential discovery now checks explicit
`--env-file`, an existing process credential pair, `ALPACA_CREDENTIALS_FILE`, then
the default shared file. An incomplete, conflicting or rejected source does not
cause automatic fallback. No credential values were printed or copied into this
repository, and no account, position or order endpoints were called.

The earlier rejected daytrader pair was not retried. Its September 12 receipts
remain separate from this successful source collection. Market data supplies
price/volume features; it does not supply the 18 additional reviewed comparison
outcomes still needed by the first training fold. See
[Alpaca setup and collection](ALPACA_MARKET_DATA.md).

The initial enrichment retained all 18 observations. Eleven had market features;
CDXS, CNST, FPRX, KDMN, PAND, STRO and VIE initially retained nulls for all five
additions. Their conservative identity intervals began December 21, leaving
only seven completed sessions before the 2021 cutoff. The later source review
documented above resolved these seven identity-history gaps. ARQT/CRNX's 2021
rows remain purged by their actual 2026 label-availability clocks.

The actual enriched training attempt stopped at the unchanged comparison gate
of **2/20**, with five qualifying positive events. No model was fitted, validated
or promoted. The enriched dataset preserves the original September 8 financial/
label freeze and records September 13 as its own assembly freeze.

- Successful collection: `output/alpaca_market_data/20260913-active/alpaca-panel-market-collection-eb4ba45b4875a90d703604f12dc676519df8e43960126c1cb8d726c527ff82db.json`.
- Enriched dataset: `output/alpaca_panels/20260913/market-enriched-company-features-4ba340f9094a74ea3a81c0bcecb67a84d41ea33d0f0a153f3b55a126affa5e25.json`.
- Market coverage: `output/alpaca_panels/20260913/market-panel-assembly-8892e4cb2955bdc6cddaacd8c41eef2d590246f3d54b9cbb1eab0f935f6ce8dd.json`.
- Actual blocked training attempt: `output/alpaca_panels/20260913/training-attempt-164b0bedc676409cce48049d888135e16d9eba8ecc1b717c95d928764936bee1.json`.

September 13 verification passed:

- Full modeling environment: **567 passed, three optional legacy checks skipped**.
- Minimal environment: **558 passed, 12 optional checks skipped**.
- Default discovery selected the verified shared credential source. A run without
  `--env-file` successfully replayed all three cached groups; an explicit offline
  replay also completed three groups with zero failures. Original source clocks
  were preserved. Exact replay receipts are in [ALPACA_MARKET_DATA.md](ALPACA_MARKET_DATA.md).
- Git whitespace/error checks passed.

## September 12: prior access-blocked Alpaca integration

The local model now has a read-only Alpaca stock-data collector, hashed page
replay, five guarded historical price/volume features and a separate enrichment
join. Fitted models carry the selected feed, price basis and derivation contract;
current scoring rejects a different contract. See [setup and commands](ALPACA_MARKET_DATA.md).

The key pair in the sibling daytrader configuration returned HTTP 401
on one bounded historical-SIP request. No further requests were made with that
pair, and no bars were downloaded in that attempt. The subsequent successful
collection uses the distinct September 13 source documented above.

The saved plan covers all 18 existing observations in three historical cutoff
groups. The explicit access-blocked collection preserved every group and every
company, leaving all new market features null. The actual enrichment/training
attempt retained the same first-fold support of five positive events and two
comparison companies; it produced no fitted model. Its dataset assembly freeze
is September 12 and its original financial/label freeze remains recorded
separately. Existing row-level cutoffs, labels and membership are unchanged.

- Full modeling environment: **558 passed, three optional legacy checks skipped**.
- Minimal environment: **549 passed, 12 optional checks skipped**.
- Original source assembly replay passed with 54 labels and 18 observations.
- Access receipt: `output/alpaca_market_data/access_probe_20260912/historical_sip.json`.
- Incomplete collection: `output/alpaca_market_data/alpaca-panel-market-collection-df1bd65fa9c2cb1b068d688fccd6a015d20e6151a7a3235be47379aa020470de.json`.
- Market coverage: `output/alpaca_panels/market-panel-assembly-bcc9906f75b03c354fda58a8c2d64d9cfbd04564f12c561d5f80a677f0d76eea.json`.
- Actual blocked training attempt: `output/alpaca_panels/training-attempt-237b3dbc801f1b81253f56cf44b82b97cac777e84a730af0307d27b372deaff1.json`.

The app snapshot and browser receipt documented below remain the September 8
checkpoint; the separate Alpaca integration has not published new market scores.

## Completed implementation and source work

- Local, read-only application, loopback launcher, minimal pinned dependencies,
  sealed reproducible snapshots, source freshness, company details and downloads.
  Cloud Build and automatic cloud deployment are removed from the supported path.
- Source-bound acquisition review and immutable label freezing: 54 reviewed
  announcements from 2018–2025; 282 candidate records remain pending.
- A fixed historical cohort preserving all 100 original December 2020 Nasdaq
  additions, including subsequently acquired/delisted companies. The 2021, 2023
  and 2024 observation dates produce 300 planned company-year rows.
- Thirty-eight reviewed annual financial records across 28 cohort issuers.
  Features are cash, assets, annual operating cash flow, annual R&D and derived
  cash burn, with original publication timing and explicit missing values. The
  separate older acquired-company seed retains eight reports and 33 observed
  financial entries. Old annual reports remain visibly dated.
- Eight reviewed issuer-archive outcome windows across four comparison issuers.
  Inventories, downloaded bodies, extracted text, publication datelines and
  acquisition/censoring trigger reviews are replayed against saved hashes.
  Migrated wrong-body and empty-page defects retain their evidence and replacements.
- Eighteen assembled company observations: ten positives across 2021, 2023 and
  2024; six ARQT/CRNX comparison observations and two CDXS/STRO 2021 comparisons.
  Original announcement and merger-background evidence supports the positive
  timing. CDXS/STRO have reviewed accession-specific mirrors of 92 material
  filings and 247 documents/exhibits, with explicit embedded-exhibit coverage.
  Actual September 2026 retrieval/review clocks remain preserved.
- Public SEC search inventory collection with padded CIKs, exact pagination,
  source-byte replay and no automatic outcome labels. Forty-eight discovery
  inventories cover three historical intervals for sixteen additional issuers;
  ARQT/CRNX inventories and one extra STRO interval are saved separately.
- Regularized logistic training, training-only preprocessing, annual holdouts,
  maturity/availability purging, past-only base-rate comparison, portable model
  artifacts, and separate training/evaluation/promotion status. Missing evidence
  prevents fitting; synthetic tests do not establish model quality.
- The local app displays cohort coverage and first-fold support and provides a
  source-bound JSON coverage download. Reports distinguish structural observation
  completeness from chronological training eligibility.

## Exact remaining data gate

The actual training attempt stopped with:

```text
fold-2023: insufficient distinct negative companies (2/20)
```

The pre-2023 training cutoff is December 31, 2022 at 23:59:59 UTC. Nine assembled
observations precede that cutoff. CDXS/STRO have a source-bound retrospective
label clock of April 1, 2022 at 12:00 UTC, including the complete reporting-lag
interval. The ARQT/CRNX labels retain actual 2026 availability and are purged.
**Five distinct acquisition events and two comparison companies qualify**, against
fixed requirements of five and 20. The later test years now include five matched
positive examples, but still need complete comparable outcome coverage.

Surviving issuer pages do not prove that original historical pages were never
removed or revised. The two filing-backed comparison observations qualify under
the explicit designated-corpus/version protocol and retain its limitations.
Unreviewed or partially downloaded histories remain unknown. Search inventories,
annual-filer existence and missing acquisition matches never supply negative
labels.

Remaining work, in dependency order:

1. Complete pending-deal baseline, identity, source-version and outcome review
   for 18 additional distinct comparison issuers before the first training cutoff.
   Start with the captured APRE and FREQ filing sets; collect the remaining
   designated bodies/exhibits for the other 16. Annual reports for all 18 are
   now archived. Complete comparable positive/negative coverage for the two
   held-out years and independently audit the labels and cohort exclusions.
   The seven existing rows' earlier identity intervals are now reviewed; the
   separate FPRX price-discontinuity exception remains visible.
2. Run the fixed chronological training/evaluation pipeline on that eligible
   dataset. Assess discrimination, calibration, rare-event uncertainty and
   improvement over the past-only base rate; fitting alone is not validation.
3. Join matching current financial features, apply a validated research model to
   the public-company watchlist, and freeze forward predictions before observing
   outcomes. Market-cap and clinical history are future source-backed feature
   additions, not substitutes for missing historical observations.

Public SEC filing search and the exact September 13 annual-report routes are
working. Earlier direct financial API and issuer-route failures remain recorded
separately; they do not establish that all SEC document routes are unavailable.
The public historical-listing demo returned no requested study dates. No paid
access was purchased, identifying contact invented or access block bypassed.

The earlier September 8 bounded follow-up checked distinct issuer filing routes for the
remaining financially prepared comparison companies. No additional complete
accession/exhibit corpus was demonstrated: observed outcomes include request
timeouts, retired historical hosts, and a working navigation page leading to an
already unavailable filing archive. Partial browser/PDF evidence and routes not
yet tested are kept separate from confirmed route failures. These receipts do
not claim that every alternate source is inaccessible. The
[18-company route ledger](../data/history/panel_seed/negative_reviews/CDXS_STRO_remaining_controls_route_ledger.md)
binds the actual receipts: eleven filing-route timeouts, five historical-host DNS
failures, one partial browser/PDF result and one navigation-only result. The
replayed discovery inventories identify 931 material-document candidates, still
requiring original-body/exhibit and outcome review.

## Reproduce and inspect

See [HISTORICAL_COHORT.md](HISTORICAL_COHORT.md) for assembly, source limitations
and download semantics, [REGULATORY_SOURCE_REVIEW.md](REGULATORY_SOURCE_REVIEW.md)
for filing discovery/review, and [BASELINE_TRAINING.md](BASELINE_TRAINING.md) for fitting.
Original raw source files are retained locally and excluded from Git and compact
app snapshots; a receipt-only clone cannot replay unavailable originals.

```bash
.venv/bin/python scripts/assemble_research_panel.py --publish-to-seed
.venv/bin/python scripts/build_history_seed.py
.venv/bin/python scripts/run_local_research.py
.venv/bin/python run_api.py

# Saves a precise blocking receipt and exits 2 until the data gate is met.
.venv-model/bin/python scripts/assemble_research_panel.py --publish-to-seed --train
```

Current cohort receipts:

- Coverage report: `output/historical_panels/20260913-listings/historical-panel-assembly-5aad78651e70d9ac4cce9800245c2e5f5a565c7b5483c9c900ac075b82b4cfae.json`.
- Dataset: `output/historical_panels/20260913-listings/historical-company-features-80a0388201a5e4d94ad3487e204286be364b5c219b9257ce64d44879e20de1a1.json`.
- Enriched blocked training attempt: `output/alpaca_panels/20260913-listings/training-attempt-44137d5a3cb42dc47b161d429bcfa9995aac197237d51e502c3bdb8991c4e0e4.json`.
- Frozen acquisition label SHA: `8e28d32782f9d8079d9e2c1e2c9594d794c4e57f9e280cc485d077c9466d6bd2`.

## Data freshness and operating limits

The supported local URL is http://127.0.0.1:8000. The current market snapshot has
759 companies: 752 included by the saved screen, seven excluded, 414 with matched
assets, and only two with company-specific risk evidence. Public market-source
receipts were retrieved September 8. Six SEC receipts remain from July 23 with
transaction screening through July 22; curated risk evidence is dated July 28.
Combined market freshness remains `stale_or_unknown`. A local rebuild does not
refresh SEC screening, curated risk evidence or historical outcome reviews.

There is no cloud deployment, brokerage account/order access, new paid data
purchase, validated investment performance or model promotion in this checkpoint. The legacy SaaS
and database integrations remain outside the supported local runtime.

## September 8 local checkpoint verification

- Optional modeling environment: **429 passed, three optional legacy checks skipped**.
- Minimal local environment: **421 passed, 11 optional checks skipped**.
- Source regression coverage includes cached-company identity, response redirects,
  pagination, date bounds, archived-byte tampering, accession/subject mismatches,
  embedded exhibits, actual review clocks, reporting-lag maturity, and stale
  derived artifacts. Successful fitting tests use synthetic fixtures.
- The actual source-backed training attempt saved the blocking receipt above and
  created no fitted model.
- A separate agent corroborated the CDXS/STRO listing and bounded pending-deal
  baseline citations against the archived text. This is explicitly neither an
  independent-human audit nor a repeat review of the entire filing corpus.
- Git whitespace/error checks passed.

- Published snapshot: `output/local_runs/20260908T203201Z-c1c833cc`. All **564**
  sealed artifact hashes verified. The local API serves 54 reviewed acquisition
  labels, 38 annual financial records, 18 assembled observations and the same
  five-positive/two-comparison first-fold support as the source report.
- Chromium desktop (1440 pixels) and mobile (390 pixels) checks passed: no
  JavaScript/resource errors or page overflow; company selection works, and
  both browser downloads match the sealed 941,552-byte coverage report.
- Verification receipt, screenshots and replay harness:
  `output/local_verification/20260908T203201Z-c1c833cc/`.
  The read-only server remains at http://127.0.0.1:8000.
