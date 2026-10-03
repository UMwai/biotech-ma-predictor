# M&A exploration checkpoint (2026-10-03)

This pass archived SEC primary sources and reviewed them. It did not admit any
labels. It authored no coverage receipt, timing attestation, rating or fit.
First-fold support is unchanged at 5 positives and 4/20 negatives. Admitting all
seven 2021 candidates would reach at most 11/20. The k=5 degenerate held-out
issue is still open. Every judgment was made after outcome inspection. The
registration and the finalized-plan addendum, with its pre-committed rules, are
in `data/research/ma_exploration_20261003/`.

## What was collected

- Raw bytes came from SEC Archives, `data.sec.gov`, and issuer or annual-report
  PDF hosts. They are content-addressed under `sec/raw/` (814 files, about 190 MB). Every GET has its
  own receipt under `sec/attempts/` (862), with no retries and no redirects. The
  collector is `scripts/collect_sec_accessions.py`.
- All 181 audited text documents carry exactly one CDN-injected `<script>` tag
  (123 bytes). Removing it restores the EDGAR index `Size`. Packets record the
  served hash and a script-stripped candidate hash. Matching length does not
  authenticate as-filed bytes.
- Byte-identical copies of the registration, root reconciliation, Fable result
  and root web-lead captures are in `inputs/` and `root_web_leads/`.

## Original capture vs corrected validation

Independent review (Sol) reproduced collector defects. Root accepted them,
and the corrected collector rejects these former bypasses:

1. Authority flags could be true.
2. Entries could contradict their receipts or index rows.
3. Plan hashes and targets were unbound.
4. A collection's completion clock could precede its retrievals.
5. An accession could be bound through an HTML comment.
6. `../` document URLs and cached foreign-host receipts were accepted.
7. Unsafe plan names could escape the evidence output directory.

The corrected collector derives every entry from the archived plan bytes,
attempt receipts and index bytes. Verification repeats that derivation without
network access and requires exact equality. Every URL must match a canonical SEC
accession route or an explicit direct route. An index must name the requested
accession in its `secNum` block and its complete-submission row, and must name
the requested CIK as a filer or subject company. Filer and subject companies are
recorded separately.

- **Original capture** is kept unchanged: the nine legacy v1
  `sec/sec-collection-*.json` files and the non-addressed `sec/plans/*.json`. All
  18 files hashed by the reviewer are byte-identical. Six of the nine legacy
  collections record producer `270770c9`. That exact snapshot is archived in
  `sec/producers/`, together with the unchanged helper `ma_evidence_io.py`
  (`34126412`). The other three record producers that are unavailable and were
  not reconstructed: `9bb2be0a` for the ARQT and CRNX audits, and `3a230e7f` for
  the first submissions run.
- **Corrected validation** lives in `sec/collections/`. Each legacy collection
  was re-derived in cache-only mode, with new clocks, against content-addressed
  plan copies. Every legacy entry matched its re-derivation. These are new
  validations, not in-place repairs. One new network collection (Akouos
  2020-11-12 8-K) used the corrected collector directly. That makes ten current
  bound collections: nine rebinds and one network capture recorded under
  collector `b5c1c32d`.
- **Final-review guards (after Sol's final review).** These changes fixed missing
  guards; the inspected values already satisfied them.
  - Every evidence and report write goes through descriptors that follow no
    symlinks. A symlinked directory or an existing symlinked file is rejected
    before anything is created or read.
  - The inherited frame ledger is evaluated only from the byte snapshot whose
    hash was verified.
  - Judgments must contain exactly the 15 inherited rows in order.
  - `authored_at` must be no later than the packet build clock and no earlier
    than every cited review (window, membership, exclusion and initial-listing
    citations).

  The pre-edit collector `b5c1c32d`, builder `3ba22fca` and tests `b44fa6f8` are
  archived in `sec/producers/`. The bound collections keep their recorded
  collector hash `b5c1c32d` as historical provenance; they were not repinned. The
  summary therefore honestly reports `recorded_collector_equals_running_source:
  false`. The latest summary's `final_validation_basis` binds the current
  collector, builder, helper and test sources, plus the unchanged collection,
  plan, producer, receipt and raw-file inputs. It does not verify the historical
  executable tree.

  Every digest in that basis comes from the snapshot this replay verified.
  Before any packet is written, and again before the summary is written, the
  builder checks the exact file sets and expected digests. A late replaced,
  added or removed input therefore fails the build instead of being certified.

## ARQT and CRNX 2021 timing audits (admission blocked)

Packets: `packets/arqt-*.json` and `packets/crnx-*.json`. The census is
`reports/ma_exploration_20261003/audit-document-census-*.csv`.

| | Retained parents | Parents full-read | Parents targeted only | Text exhibits closed / targeted / total | Graphics closed | XBRL closed |
|---|---:|---:|---:|---|---|---|
| ARQT | 30 | 20 | 10 | 37 / 8 / 45 | 1 / 80 | 4 / 98 |
| CRNX | 38 | 10 | 28 | 16 / 35 / 51 | 1 / 93 | 4 / 138 |

- Retained parents are listed in filing-date/accession order and match the
  inherited inventories under `EXCLUDED_FORMS` (30 and 38). The SEC index filing
  dates match every inventory date.
- One designated material accession per company is captured with every listed
  document and data file, and each item was reviewed:
  - ARQT `0001787306-21-000033`: SLR $225M loan and NDA acceptance.
  - CRNX `0001564590-21-039140`: Frazier $15M private placement.
  The complete-submission `.txt` aggregate was not fetched.
- Annual membership anchors are confirmed from the SEC indexes. The filing dates
  match the prior record declarations: ARQT FY2019 2020-03-19 and FY2021
  2022-02-22; CRNX FY2019 2020-03-09 and FY2021 2022-03-30. Initial listings:
  ARQT Form 8-A 2020-01-21 and 424B4 (Nasdaq GS); CRNX Form 8-A 2018-07-12. The
  four annual PDFs were refetched and are byte-identical to the 2026-09-08
  captures. That shows unchanged bytes only, not original-version evidence.
- No reviewed text disclosed a control transaction. That finding is not a
  negative label. Targeted-only bodies (10-K, 10-Q, prospectuses, contracts),
  graphics and XBRL items remain open.

## First-five fixed-frame batch

Packet: `packets/first-five-*.json`. It has 15 rows in inherited ledger order,
and horizons are 365 days (2024 → 2024-12-31).

- **AKUS 2023 and 2024: risk-set membership exclusion.** These are neither
  negative nor censored. Lilly signed the merger agreement on 2022-10-17. The
  tender was accepted on 2022-11-30 and the merger took effect on 2022-12-01. The
  Nasdaq Form 25-NSE is dated 2022-12-01 and the Form 15 was filed 2022-12-12.
- **AKUS 2021: unknown.** The Lilly deal falls after the 2022-01-01 horizon end.
  The fixed frame never places this acquisition inside a horizon.
- **ALVR 2024: reverse-merger control candidate, unadjudicated.** The Kalaris
  8-K was accepted 2024-11-08 (event date 2024-11-07). AlloVir is the legal
  survivor. Kalaris holders get about 74.95% fully diluted and six of nine board
  seats, and Kalaris's TH103 continues as the operating business. Nothing
  automatically makes this a positive. On 2023-12-22 AlloVir announced DSMB
  futility stops of three Phase 3 trials (no safety concerns identified) and a
  strategic-alternatives review.
- **ADAP: unknown.** The listed instrument is ADSs, each representing 6
  ordinary shares. Whether an ADS counts as common equity is undecided and goes
  to root. No share-count or valuation conversion is implied. In the 2023 TCR2
  deal ADAP was the acquirer, and its holders kept about 75%. Nasdaq bid-price
  notices did not delist the ADSs.
- **ABUS: unknown.** Roivant held 29.1% after its standstill expired in 2021.
  Whitefort's 2024 activist 13D is an engagement signal, not a control event.
  The inherited 2021 partial packet and its four sources verify by hash, and its
  issuer archive replays.
- **ALT: unknown.** The screened 2021 filings cover financing and
  manufacturing. No 2023 or 2024 filing matched the control-form screen.
- Window review is a fixed form/item screen. It is not a complete corpus.

## Optional example (outcome-chosen, not a score)

`packets/example-*.json` uses only pre-2021 sources:

- Akouos's 2020-11-12 release and Q3 2020 10-Q. They describe AK-OTOF AAV
  plans, a 2021 IND and a planned Phase 1/2 trial. These are preclinical plans,
  not results.
- Lilly's 2020-12-15 Prevail SC TO-C and release. They announce a definitive
  agreement that would establish a Lilly gene-therapy program. The deal had not
  closed by the cutoff.

The Akouos FY2020 10-K was published in 2021, so it is excluded. Broad platform
alignment does not establish target-specific engagement. Lilly is already one
of the 25 declared buyers. The example adds no rating and no buyer insertion.

## Next concrete admission step

1. Finish reading or format-reviewing every open ARQT and CRNX material item for
   2021 through 2022-Q1, including the graphics and XBRL. Make per-accession
   original-version judgments.
2. Implement an SEC-direct timing binder that consumes the bound
   `sec/collections/` v2 collections and the review log instead of the
   issuer-mirror layout. It needs its own Sol review.
3. Root resolves the ADS mapping and reverse-merger class questions in the
   handback.

A future negative reconstruction that uses these October 2026 reviews needs a
new label review ID and an actual review time at or after those reviews. The
September 2026 labels and their review dates stay immutable.

To replay, run `python scripts/collect_sec_accessions.py verify --evidence-root
data/research/ma_exploration_20261003`, then `python
scripts/build_ma_exploration_packet.py`. Tests are in
`tests/test_ma_exploration_sources.py`.
