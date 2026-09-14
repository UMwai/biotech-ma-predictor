# Original annual financial evidence

`financial_records.json` contains 33 manually reviewed company-year records and
132 reported financial facts: cash and cash equivalents, total assets, annual
operating cash flow, and annual research and development expense. The records
cover 23 distinct issuers. Financial coverage alone does not establish historical
membership, a negative acquisition outcome, training eligibility, or model quality.

The collection comprises:

- FY2019 for 20 candidates: ABUS, ALT, APLT, APRE, ARCT, ARQT, AVDL, BEAM,
  CALA, CDXS, CNCE, CRNX, FREQ, FULC, HARP, KALA, KALV, KNSA, KRYS, and STRO.
- FY2021 and FY2022 for ARQT, CRNX, CDXS, and STRO.
- FY2021 for CNCE and PRVB, and FY2022 for FUSN, HARP, and PSTX, for the
  acquired-company holdout candidates.

Each `*_review.json` is an actual dated review receipt. Its SHA-256 binds the
exact values and provenance represented by the corresponding dataset record.
Fourteen records also have an archived original PDF under `raw/`, its actual
SHA-256 and byte count, and page text under `text/`. The other 19 records were
reviewed through the SEC browser and explicitly have null original-byte hashes.
A review receipt hash is not an original-document hash.

Every record identifies its original filing/publication date and primary source
for that date. Current retrieval and review timestamps remain separate.
`available_at` is a date-plus-36-hours public availability proxy, not a measured
historical dissemination timestamp. Publication evidence includes issuer filing
details, SEC filing indexes, original dated certifications explicitly referring
to filing on that date, or later primary documents confirming the original
filing date. Later financial comparatives are not backdated into earlier rows.

Cash excludes separately reported investments and restricted cash. Operating
cash flow is a signed annual flow. Positive values, including FREQ FY2019 and
CDXS/STRO FY2022, remain positive. No quarterly annualization is used. ALT and
APRE FY2019 report dollars; the other records report thousands of dollars. The
source unit and conversion multiplier are explicit for every fact. KALV FY2019
is the original fiscal year May 1, 2018 through April 30, 2019, filed July 16,
2019; its fiscal year is not silently converted to a calendar year.

FUSN FY2022 is reviewed from `R2.htm`, `R4.htm`, and `R6.htm` statement
attachments within original SEC accession `0000950170-23-008310`. The main
annual HTML exceeded the browser content-size limit. Per-fact source URLs and
table locators identify the actual reviewed tables. Printed/PDF page numbers
remain null because those attachments are not paginated. These are original
accession documents, not a modern company-facts feed.

`validation_report.json` records the current dataset hash and checks of exact
receipt binding, actual PDF hashes and byte counts, extracted page hashes and
row containment, annual durations, availability arithmetic, unit conversions,
and statement locators. All 33 records passed those checks at collection time.

`download_receipts.json` preserves actual public download attempts, including
failed requests. `scripts/collect_public_annual_reports.py` is a bounded,
explicit-year public PDF collector; it does not infer financial facts or
eligibility. Issuer-hosted PDFs were used where public mirrors were unavailable.
The collection contains no invented source bytes, source hashes, or financial
values. Review was performed by Codex, not an independent human auditor.
