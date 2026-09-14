# Historical company cohort and local assembly

The study population is all 100 additions named in Nasdaq's December 11, 2020
announcement, effective December 21, 2020. The downloaded original announcement,
its actual retrieval receipt, and the complete 100-name table are saved under
`data/history/panel_seed/`. A company remains in the coverage ledger when it is
later acquired, delisted, renamed, or inaccessible. This is a closed entry cohort,
not a complete historical census of every listed biotechnology company.

The predeclared observations are January 1 of 2021, 2023 and 2024, each with a 365-day
announcement horizon. The 2024 horizon ends December 31, 2024 because 2024 is a leap
year. Financial inputs are original annual cash, assets, operating cash flow and
R&D; cash burn is `max(-annual_operating_cashflow_usd,0)`. Missing values remain
null. The latest verified report available before the shared cutoff is selected;
its fiscal period remains visible, including stale annual reports. No market-cap
or clinical feature is fabricated from current data.

## Reproduce the local artifacts

The default environment can verify and assemble evidence without importing the
optional modeling stack:

```bash
.venv/bin/python scripts/assemble_research_panel.py --publish-to-seed
.venv/bin/python scripts/build_history_seed.py
.venv/bin/python scripts/run_local_research.py
.venv/bin/python run_api.py
```

Original source files are required for replay. They are retained locally and
excluded from Git and the small app snapshots. A clone containing only review
receipts cannot authenticate absent originals. The local app reads a sealed
snapshot and exposes the coverage report at
`/api/v1/research/historical-coverage`.

With the optional pinned modeling environment, assembly and fitting can be
requested together:

```bash
.venv-model/bin/python scripts/assemble_research_panel.py --publish-to-seed --train
```

The command writes content-addressed coverage and dataset artifacts before the
fit. Insufficient historical observations, classes, chronology, or source
provenance return exit 2. A successful evidence assembly does not imply that a
model was fitted. The trainer retains its fixed minimums of five distinct
positive events, twenty distinct negative issuers in each training fold, and two
consecutive held-out years. These are basic support floors, not statistical
proof of predictive power. See [BASELINE_TRAINING.md](BASELINE_TRAINING.md).

## What the counts mean

The September 8 checkpoint contains 38 original annual records across 28 issuers,
eight reviewed issuer-archive windows across four comparison issuers, and 18
assembled observations. Ten are positive examples: five from 2021, two from 2023
and three from 2024. Eight are comparison observations: ARQT/CRNX in all three
years and CDXS/STRO in 2021.

The first training fold has five qualifying acquisition events and two qualifying
comparison companies. CDXS/STRO now have additional accession-specific filing
reviews covering 92 material filings and 247 parent/exhibit documents, including
embedded exhibits. Their source-bound retrospective availability is April 1,
2022 at 12:00 UTC; actual September 2026 reviews remain preserved. The earlier
ARQT/CRNX labels retain actual 2026 availability and are purged from this fold.
Eighteen more distinct comparison companies are required before fitting can
begin. The later positive examples improve test-year coverage, but complete,
comparable later-year outcome coverage and an independent label audit remain
required.

- Annual financial records have verified identity, units, original publication
  dates, and saved review receipts. PDF-backed facts are checked against the
  original saved bytes. Browser-reviewed SEC facts explicitly lack original byte
  hashes; review hashes are not presented as hashes of SEC HTML.
- Archive-reviewed windows have a complete designated inventory, full-text
  screening and review of every acquisition/censoring trigger context. The
  declared method does not claim every untriggered article was read manually.
- Complete company observations additionally join reviewed historical membership,
  pending-transaction baseline, annual features, and an outcome label.
- Training-fold observations must also have mature outcomes and a permissible
  label clock before that fold's cutoff. A newly reviewed 2026 label does not
  automatically enter a 2023 training fold.

The explicit [retrospective timing protocol](PREDICTION_PANEL_FORMAT.md#retrospective-evidence-timing-protocol)
can reconstruct original evidence availability when its source/version receipts
are actually supplied. It retains actual review dates. Current issuer pages,
matching titles, filing existence, and searches with no hits do not by themselves
establish complete original-version outcome history. Until that additional
review is supported, rows retain their actual review availability and are purged
from earlier folds.

## September 13 source progress

Reviewed earlier security identity now covers the market lookback for all seven
previously restricted observations. Cohort entry remains December 21, 2020;
labels and the first-fold count of two comparison companies are unchanged.
Alpaca enrichment now yields 87 of 90 market-feature values across all 18 rows.

Exact SEC annual reports were recovered for all 18 remaining comparison
candidates. Broader capture covers APRE's 42 selected accessions and FREQ's 48;
substantive outcome/identity/exhibit review and source-verifier integration are
still required before admission. See [the source report](WEB_SOURCE_RESEARCH_20260913.md)
for current evidence, hashes and remaining work. Earlier failed routes below
remain historical observations rather than a claim that all routes are blocked.

## Source limitations and unresolved access

The original issuer archive sometimes contains a migrated empty article, wrong
article body, or wrong year. Saved replacements identify original syndicated
issuer releases and preserve the erroneous publisher copies. One Arcutis
campaign release is retained as an actual web-tool extracted-text response,
explicitly distinct from publisher HTML. Neither artifact is represented as a
contemporaneous historical web capture.

Removed or revised historical pages cannot independently be ruled out from
currently surviving archives. Partial MediciNova and Madrigal archives, and
failed Novavax, Altimmune, Avadel and Kiniksa access, remain recorded as unknown
coverage. A missing page never becomes a negative outcome.

The public SEC full-text search route works with padded CIKs. Forty-eight saved
annual/quarterly inventories cover the baseline, outcome and reporting-lag
intervals of sixteen additional financially prepared issuers; one extra STRO
interval is saved. Search metadata remains distinct from a reviewed negative
outcome. See [regulatory source review](REGULATORY_SOURCE_REVIEW.md) for replay
and transport limitations.

The direct SEC financial API request returned 403, and the public historical
listing demo did not supply the requested study dates. Provider access or saved
historical exports can unlock additional coverage; configuring a contact header
alone does not guarantee transport access. Existing free primary sources have
supplied genuine financial and event evidence, but do not currently meet the
historical training support and provenance requirements.

The current watchlist therefore continues to use its explicitly identified
heuristic baseline. No acquisition probability or predictive edge is established
by these collection, software, or replay checks.
