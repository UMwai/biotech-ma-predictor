# Regulatory source collection and outcome review

The public SEC full-text search endpoint supplies filing discovery independently
of the companyfacts/submissions transport. A successful search inventories
filings; it does not assign an acquisition outcome or establish historical
listing membership.

## Collect and replay a filing inventory

```bash
.venv/bin/python scripts/collect_regulatory_inventory.py \
  --cik 1745999 --ticker BEAM \
  --start 2021-01-01 --end 2021-12-31 \
  --output-dir data/history/panel_seed/regulatory_inventory/BEAM
```

The collector uses a ten-digit padded CIK, an unfiltered filing-date query, exact
result counts and complete pagination. The unpadded CIK query can return zero
where the padded query has filings. Regression tests preserve this distinction.
Split large or failed intervals explicitly; the collector does not automatically
retry a cached failure. Each page retains its URL, original downloaded bytes,
SHA-256 and actual retrieval timestamp. Existing manifests are replayed offline
before reuse and must match the requested company/date identity. New captures
record and verify the effective response URL before reading the body. Legacy
receipts without that captured URL explicitly return
`transport_identity_verified=false`; their original bytes and clocks remain
unchanged. An incomplete legacy page cache cannot be reused as newly verified
transport. `query_interval_closed` separately reports whether the entire date
interval had elapsed, with the conservative 36-hour date bound. Pagination
completion establishes neither transport identity nor historical completeness.

Timeout, shard failures, approximate totals, missing/overlapping
pages, identity discrepancies and changed raw bytes prevent completion.

Normalized records retain the actual search hit and all associated CIKs. A
candidate document URL still needs subject identity review: the first associated
CIK is not automatically the filing company's identity. A zero-result inventory
has a null outcome label. It never becomes a negative example.

The current-source limitation is explicit: SEC search/index data can reflect
post-acceptance corrections or removals. The saved inventory establishes the
observed query result, not an unchanged historical world snapshot. See the
[SEC access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

## September 13 original SEC source capture

Web research recovered exact SEC annual-report bodies for all 18 financially
prepared comparison candidates. APRE has 42 selected accession indexes and
complete submission containers, with 707 embedded documents; its fresh SEC
inventory selects the same accessions. FREQ has 48 accession indexes and all
139 designated parent/exhibit bodies. These are source-capture results and
assign no new labels. See [the research report](WEB_SOURCE_RESEARCH_20260913.md).

## Verify captured SEC packages offline

`src/research/sec_corpus.py` implements the SEC source replay contract. Run it
against either collection with its matching local source archive:

```bash
.venv/bin/python scripts/verify_sec_corpus.py \
  data/history/web_source_research/20260913/controls_a_APRE_complete_submission_collection.json \
  --output-dir output/sec_corpus

.venv/bin/python scripts/verify_sec_corpus.py \
  data/history/web_source_research/20260913/FREQ_sec_corpus_discovery.json \
  --output-dir output/sec_corpus
```

Verification reconstructs the accession selection from hashed discovery pages,
parses the captured SEC indexes, and checks response hashes, exact SEC URLs,
confined local paths and source clocks. Complete submissions additionally bind
header identities, document counts and every embedded document's byte range and
hash. Ownership filings can have different subject and reporting-fund CIKs;
the original index links and submission headers must establish that relationship.
Saved completion flags cannot substitute for these checks.

September 14 replay verified APRE's **42 accessions and 707 embedded payloads**,
with all document-format payloads present. FREQ's **48 indexes and 139 captured
bodies** verified, while the parsed indexes identified **812 missing
document-format payloads**. These are known missing attachments; the SEC public
document counts also exceed the visible index entries, leaving additional
coverage unresolved. The report retains missing attachments, data files, count
differences and differences between index-reported lengths and captured response
lengths. Container byte ranges describe encoded payloads; images still need
decoding and substantive review.

Success means `captured_sources_verified_review_required`. Every result retains
`outcome_review_complete=false` and `label_admission_allowed=false`; this command
assigns no outcome or historical label-availability clock. It performs no network
requests. Missing archives, tampering and invalid identities exit 2. Git contains
compact receipts, so a fresh clone needs the matching source archive to replay
these collections.

The outcome verifier below still supports issuer accession mirrors. SEC packages
need substantive outcome/identity review, exhibit coverage adjudication and
integration with historical label admission before supplying negative examples.
Downloaded SEC HTML can include current delivery markup; captured-byte hashes
do not establish byte identity with a filing as originally accepted, or prove
that the current SEC inventory is an unchanged historical inventory.

## Review the designated outcome corpus

`src/research/regulatory_corpus.py` verifies accession-specific issuer filing
mirrors. The initial reviewed corpora cover Codexis and Sutro from January 2020
through March 2022 for the January 2021 observation. The review binds:

- Every page of the issuer's all-form filing inventory and a fixed material-form
  selection, including potentially relevant ownership and registration filings.
- Every selected parent filing and HTML exhibit in the accession's document
  inventory; unlinked exhibits listed by an 8-K need explicit evidence of their
  inclusion in a reviewed document.
- Full extracted filing text and reviewed acquisition, pending-transaction and
  censoring contexts. The review records automated screening assistance and
  targeted substantive review; it does not claim every character was read
  manually.
- Original annual-report evidence for historical public common-share membership
  and the bounded pending-deal baseline, plus a completed observation horizon.

An issuer mirror's SHA identifies the bytes downloaded from that issuer URL.
The original SEC accession/document URI is a separate identity field. The
receipt explicitly states that original SEC-hosted document bytes were not
archived; the two hashes are never conflated. Current mirror availability alone
cannot rule out every correction, removal or omitted historical disclosure.
The scope and source-version limitations remain part of each review.

For a negative label, the retrospective availability clock is at least the full
horizon, every original publication bound, and the end of the designated
ascertainment interval. These corpora retain the March 31, 2022 interval plus
36 hours of date uncertainty, producing April 1, 2022 at 12:00 UTC. Actual
September 2026 download/review timestamps remain unchanged. Inventory discovery
without complete source review does not obtain that clock.

See [the timing contract](PREDICTION_PANEL_FORMAT.md#retrospective-evidence-timing-protocol)
and [cohort assembly](HISTORICAL_COHORT.md). Original source bytes are retained
locally and excluded from Git and compact app snapshots. A receipts-only clone
cannot replay missing original downloads.
