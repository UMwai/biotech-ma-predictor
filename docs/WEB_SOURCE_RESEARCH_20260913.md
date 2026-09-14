# September 13 primary-source research

September 14 follow-up: an offline SEC package verifier now replays these
captures. See [the implementation and remaining review gates](REGULATORY_SOURCE_REVIEW.md#verify-captured-sec-packages-offline).
The source and test results below retain their September 13 dates.

Web search recovered the evidence needed to extend all seven historical
security-identity intervals. The rebuilt research dataset now has market features
for **18 of 18 observations**, up from 11. **87 of 90 market-feature values** are
present. FPRX retains three long-window nulls because its November 2020 price jump
triggers the existing discontinuity check. No price check or training requirement
was relaxed.

Five Prime's dated clinical-results announcement is a plausible catalyst for
that jump, but does not prove its cause or rule out a corporate action. The
[price-event research receipt](../data/history/web_source_research/20260913/FPRX_price_jump_review.json)
preserves that distinction; the three nulls remain.

Original SEC annual reports were also downloaded for **all 18 remaining
comparison candidates**. More extensive source capture covers APRE and FREQ.
These downloads do not assign negative outcomes: the first training fold remains
at **five positive events and two of the required 20 comparison companies**.

## Earlier security identity

All seven intervals now begin September 30, 2020, covering the required market
lookback. The fixed cohort still enters on December 21, 2020. Company identities,
outcome labels, label-availability clocks, financial values and observation dates
are unchanged. Earlier review files remain available; current adjudications
reference new immutable review files.

| Ticker | Primary evidence used |
|---|---|
| CDXS | [FY2021 issuer filing](https://ir.codexis.com/sec-filings/all-sec-filings/content/0001200375-22-000010/cdxs-20211231.htm), Item 5 common-stock history through 2021, plus the already verified 2020 material-filing corpus |
| STRO | [FY2021 SEC filing](https://www.sec.gov/Archives/edgar/data/1382101/000095017022002312/stro-20211231.htm), common-share history beginning September 2018, verified against archived issuer-mirror bytes and the 2020 material-filing corpus |
| CNST | [FY2020 filing](https://www.sec.gov/Archives/edgar/data/1434418/000156459021007783/cnst-10k_20201231.htm), Nasdaq trading and common-stock history through December 2020 |
| FPRX | [Original offer document](https://www.sec.gov/Archives/edgar/data/318154/000119312521084994/d137966dex99a1a.htm), quarterly Nasdaq common-stock history covering 2020 |
| KDMN | [FY2020 filing](https://www.sec.gov/Archives/edgar/data/1557142/000155714221000022/kdmn-20201231x10k.htm) and [September 2021 proxy](https://www.sec.gov/Archives/edgar/data/1557142/000114036121031968/ny20000668x1_prem14a.htm), same security's historical trading and actual exchange transfer |
| PAND | [FY2020 filing](https://www.sec.gov/Archives/edgar/data/1807901/000156459021012895/pand-10k_20201231.htm), public trading beginning July 17, 2020 |
| VIE | [Original offer document](https://www.sec.gov/Archives/edgar/data/1492426/000119312521039920/d118403dex99a1i.htm), quarterly Nasdaq common-stock history covering 2020 |

KDMN's interval explicitly records NYSE through October 23 and Nasdaq beginning
October 26, 2020. Its earlier prices are not described as Nasdaq prices.
Browser representations for the five positive companies are hashed separately
and explicitly distinguished from original HTML. The two comparison-company
reviews reuse verified original downloads from issuer accession mirrors. Actual
2026 retrieval/review clocks remain recorded.

The [join verification](../data/history/web_source_research/20260913/listing_join_verification.json)
binds all seven updates and checks that every other observation field is unchanged.

## Comparison-candidate source capture

All 18 FY2021 annual reports were downloaded from exact SEC accession URLs:
ARQT, CRNX, BEAM, ALT, APLT, APRE, CALA, ABUS, ARCT, FREQ, AVDL, HARP, FULC,
CNCE, KALA, KALV, KNSA and KRYS. Their acquisition outcomes remain unreviewed
for this new source batch.

| Candidate | Additional capture for January 2020 through March 2022 | Remaining review |
|---|---|---|
| APRE | 42 selected accession indexes and complete submission containers; 707 embedded documents, including all 257 document-format entries (117 non-graphic and 140 graphic); 57,198,252 submission bytes | Substantive pending-deal, acquisition/censoring and graphic review; integration of the SEC-container evidence verifier |
| FREQ | 48 accession indexes and all 139 designated parent/exhibit bodies, including its Form D XML primary | Subject/filer identity, acquisition/censoring, graphic and embedded-exhibit review; source-version and verifier integration |
| Remaining 16 | Exact SEC annual-report bodies | Complete designated baseline/outcome filing sets, exhibits, identity and substantive outcome review |

APRE's fresh SEC discovery has 124 all-form results across two pages and selects
the same 42 accessions. All 42 complete-submission lengths match their index
sizes. Container-derived document bytes retain their container hashes and byte
bounds; they are not presented as separately downloaded responses.

FREQ's returned HTML includes current SEC delivery markup: 138 bodies differ
from the index-reported byte count. Both lengths and the downloaded bytes are
preserved. Exact current SEC response hashes do not establish byte identity with
the filing as originally accepted. Neither corpus proves that the current SEC
inventory is an unchanged historical inventory.

Detailed evidence and failures are in [controls A](../data/history/web_source_research/20260913/controls_a.md)
and [controls B](../data/history/web_source_research/20260913/controls_b.md).
Prior timeout, DNS and HTTP-rejection receipts remain historical observations;
they no longer establish that these exact current routes are inaccessible.

## Rebuild and verification

The unchanged 4,745 Alpaca bars were replayed offline against the updated panel.
No additional credentials or market-data requests were needed.

- Base panel: `output/historical_panels/20260913-listings/historical-company-features-80a0388201a5e4d94ad3487e204286be364b5c219b9257ce64d44879e20de1a1.json`.
- Base coverage: `output/historical_panels/20260913-listings/historical-panel-assembly-5aad78651e70d9ac4cce9800245c2e5f5a565c7b5483c9c900ac075b82b4cfae.json`.
- Market replay: `output/alpaca_market_data/20260913-active/alpaca-panel-market-collection-ebf72165466938bc30253f810b68222f1d626e66f3af822a231b09c4a4ceeec4.json`.
- Enriched dataset: `output/alpaca_panels/20260913-listings/market-enriched-company-features-92831e8293cf36cb12b74dd2743dca39793a7c2e84f888a66ad66a3657c39463.json`.
- Market coverage: `output/alpaca_panels/20260913-listings/market-panel-assembly-e10500d1c8eb172dc88648325f8127137c05369b2f28b5ebafe3d0f076f449e1.json`.
- Blocked training attempt: `output/alpaca_panels/20260913-listings/training-attempt-44137d5a3cb42dc47b161d429bcfa9995aac197237d51e502c3bdb8991c4e0e4.json`.

Original-source assembly replay passed with 54 frozen acquisition labels and
18 observations. The model-environment test suite passed **567 tests**, with
three optional skips. The actual training attempt still exits 2 at the fixed
`fold-2023: insufficient distinct negative companies (2/20)` gate.

The independent [root replay receipt](../data/history/web_source_research/20260913/root_integrity_verification.json)
checks 289 captured response hashes and exact effective URLs, all 288 recorded
response lengths, and all 707 APRE embedded-document byte ranges and hashes.
One reused FREQ index receipt lacks a recorded length; its captured hash still
replays, and its actual current byte count is recorded separately in this audit.

The next data step is substantive review and replayable admission of the APRE
and FREQ evidence, followed by complete source collection/review for the other
16 comparison candidates and the held-out years. A search result, annual report,
or complete download by itself cannot establish a non-acquisition outcome.
