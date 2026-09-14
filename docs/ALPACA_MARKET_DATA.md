# Alpaca market data for the acquisition model

The local historical panel can now add five market features to its verified
financial features. Alpaca collection, source replay, feature assembly and model
fitting are separate steps. They preserve the reviewed company identities,
acquisition labels, original observation cutoffs and every company row.

## Current connection result

On September 13, 2026, the configured pair in
`~/.config/alpaca_creds.env` successfully accessed historical SIP data. All three
planned historical cutoff groups were collected. This verifies historical
market-data access for that source; real-time SIP entitlement remains untested.
No credential values were printed or copied into this repository, and no
account, position or order endpoints were called.

The earlier September 12 request using the sibling `um-daytrader` configuration
returned **HTTP 401** and stopped without collecting bars. That rejected pair
was not retried. Its preserved access receipt is
`output/alpaca_market_data/access_probe_20260912/historical_sip.json`.
The earlier incomplete collection still records all three groups as unattempted
after that rejection; it is separate from the successful September 13 collection.

The September 13 collection contains **4,745 raw daily bars** for 14 distinct
tickers across 18 ticker-window series, in three response pages. All three
queries completed, with no failed group or empty symbol series.

| Historical symbol `asof` | Ticker series | Raw bars |
|---|---:|---:|
| 2020-12-31 | 9 | 2,275 |
| 2022-12-31 | 4 | 1,100 |
| 2023-12-31 | 5 | 1,370 |

The initial assembly populated 11 of 18 observations. Subsequent primary-source
review extended the verified security-identity intervals for CDXS, CNST, FPRX,
KDMN, PAND, STRO and VIE to September 30, 2020. The cohort still enters on
December 21; labels and observation cutoffs are unchanged. KDMN explicitly
records its NYSE-to-Nasdaq transfer within the lookback.

Offline replay now populates market features for **all 18 observations**,
with **87 of 90 values present**. FPRX's November 2020 price jump triggers the
existing discontinuity check, preserving three long-window nulls. The other
17 rows have all five values. ARQT/CRNX's 2021 labels remain unavailable before
their actual 2026 review clocks. See the [source review and current artifacts](WEB_SOURCE_RESEARCH_20260913.md).

The existing training period still has five qualifying acquisition events and
two qualifying comparison companies. More price history does not establish the
18 missing comparison outcomes. Alpaca corporate actions can help discover
candidates, but their date filter follows processing dates and their publication
latency is not guaranteed; missing records cannot establish that no definitive
acquisition was announced. [Alpaca corporate actions](https://docs.alpaca.markets/us/reference/corporateactions-1)

## Configure and collect locally

Credential discovery uses this order:

1. An explicit `--env-file`.
2. An existing credential pair in the process environment.
3. The file named by `ALPACA_CREDENTIALS_FILE`.
4. `~/.config/alpaca_creds.env`.

An incomplete or conflicting configured pair stops discovery. Rejected
credentials do not trigger fallback to another file, pair or feed. The supported
pairs are
`APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`, or
`ALPACA_API_KEY` / `ALPACA_SECRET_KEY`. Dotenv values are parsed as text, never
executed. Configuration is never copied into a research snapshot. For a separate
local configuration, copy `.env.alpaca.example` to the ignored `.env.alpaca` and
select it explicitly with `--env-file .env.alpaca`.

```bash
# No credentials or network needed: inspect all requested symbols and cutoffs.
.venv/bin/python scripts/collect_alpaca_market_data.py --plan

# Discover the configured source. Defaults: SIP, raw daily USD bars, 400-day lookback.
.venv/bin/python scripts/collect_alpaca_market_data.py \
  --output-dir output/alpaca_market_data/active

# Replay the same cached source pages with no credentials or network access.
.venv/bin/python scripts/collect_alpaca_market_data.py \
  --output-dir output/alpaca_market_data/active --offline
```

The collector prints the immutable collection manifest path. It returns exit 2
for incomplete collection and keeps an explicit gap for each affected cutoff.
A cached failure is not automatically retried; after correcting access, use a
new collection directory. `--refresh` requests a new vendor snapshot for a
previously successful query while preserving the older bytes. It does not
bypass cached access failures.

The feed is explicit. There is no SIP-to-IEX fallback. Historical data access and
real-time SIP entitlement are separate; a real-time subscription alone does not
prove this configuration can reach either endpoint. [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)

## Source and time semantics

Every response page retains the exact request/effective URL, actual retrieval
time, original bytes and hash. Replay checks page tokens, global symbol/time
ordering, duplicates, requested intervals, missing symbols, raw-byte integrity
and query identity. Redirects are rejected before credentials can be forwarded;
authentication and transport errors are sanitized and never log response bodies.

Queries declare `1Day`, `raw`, `USD`, a historical symbol `asof` and bounded
start/end times. Alpaca's `asof` controls symbol/entity mapping; it is not a data
vintage. The API sorts across symbols and may return a partial page even when
more data exists, so collection follows every returned pagination token.
[Historical bars reference](https://docs.alpaca.markets/us/reference/stockbars)

The source is today's vendor reconstruction of historical bars. Original
vendor-vintage evidence remains false. A daily bar timestamp marks the start of
its interval; features use only bars whose next New York midnight is at or before
the information cutoff. Today's actual retrieval time is retained separately from
this conservative completion policy. Enrichment advances the dataset assembly
freeze and preserves the original base freeze and every row-level label clock.

CIK identity comes from the reviewed listing/identity evidence, not from bars.
Data before that verified identity interval is excluded; cohort entry is a
separate selection date. Current tradability and missing
symbols never remove historical companies or create negative labels.

## Features and quality checks

| Feature | Definition |
|---|---|
| `raw_price_return_21_sessions` | Close ratio minus one over 21 sessions; needs 22 closes. |
| `raw_price_return_63_sessions` | Close ratio minus one over 63 sessions; needs 64 closes. |
| `raw_price_volatility_63_sessions` | Sample standard deviation of 63 log close ratios, annualized by square root of 252. |
| `mean_dollar_volume_21_sessions` | Mean close times volume over 21 sessions; a dollar-volume proxy. |
| `raw_price_drawdown_63_sessions` | Most negative running-peak decline within 63 closes. |

These are unadjusted price features, not total returns. Ratios of consecutive
closes at or beyond 0.5 or 2 flag a possible discontinuity and null affected
return/volatility/drawdown windows. This screen does not prove the absence of
corporate actions. Market capitalization still needs historical shares
outstanding and is not derived from prices alone.

The explicitly bounded 2016–2026 exchange-calendar policy includes normal
holidays and the documented Bush/Carter closures. Unknown calendar periods,
missing expected sessions, stale data and inadequate history remain explicit
quality gaps. No forward fill or invented bar is used. IEX dollar volume is
venue-only; SIP represents consolidated exchange coverage.

## Enrich, then attempt the existing trainer

```bash
.venv-model/bin/python scripts/assemble_alpaca_panel.py \
  --dataset data/history/panel_seed/panel.json \
  --market-collection PATH_PRINTED_BY_COLLECTOR.json \
  --output-dir output/alpaca_panels \
  --train --test-start-year 2023
```

This writes a separate enriched dataset, coverage report and training-attempt
receipt. It does not overwrite the original financial panel or publish model
probabilities. An unavailable market collection keeps all market features null.
Acquisition labels, censoring, membership and the fixed training floors remain
unchanged: five distinct positive events, 20 distinct negative issuers per
training fold, and two consecutive test years.

Fitted models retain a `market_data_contract`: feed, price adjustment, currency,
calendar and calculation/availability policies. Current scoring must supply the
same contract, preventing unnoticed changes from SIP to IEX or from raw to
adjusted prices. Successful synthetic tests establish these software mechanics;
actual collection and out-of-time model evaluation are separate requirements.

## September 13 initial source and training receipts

These are the initial connection checkpoint. The later listing review, rebuilt
dataset and training attempt are recorded in [WEB_SOURCE_RESEARCH_20260913.md](WEB_SOURCE_RESEARCH_20260913.md).

- Successful collection: `output/alpaca_market_data/20260913-active/alpaca-panel-market-collection-eb4ba45b4875a90d703604f12dc676519df8e43960126c1cb8d726c527ff82db.json`.
- Enriched dataset: `output/alpaca_panels/20260913/market-enriched-company-features-4ba340f9094a74ea3a81c0bcecb67a84d41ea33d0f0a153f3b55a126affa5e25.json`.
- Coverage report: `output/alpaca_panels/20260913/market-panel-assembly-8892e4cb2955bdc6cddaacd8c41eef2d590246f3d54b9cbb1eab0f935f6ce8dd.json`.
- Training attempt: `output/alpaca_panels/20260913/training-attempt-164b0bedc676409cce48049d888135e16d9eba8ecc1b717c95d928764936bee1.json`.

The actual attempt stopped at `fold-2023: insufficient distinct negative companies (2/20)`.
No model was fitted, validated or promoted. The source data remains a current
vendor reconstruction; original vendor-vintage evidence is still false.

Full tests passed with **567 tests and three optional legacy skips** in the
modeling environment, and **558 tests with 12 optional skips** in the minimal
environment. Default credential discovery selected the same verified shared
configuration. Running the collector without `--env-file` reused all three
cached windows successfully; an explicit `--offline` replay also completed all
three with zero failed groups. These replays do not establish a new vendor
retrieval or refresh the original source timestamps.

- Default-discovery cached replay: `output/alpaca_market_data/20260913-active/alpaca-panel-market-collection-06296672e41f68e172b4594974004ed5c787b4432670ece6d6f02076258ce6cf.json`.
- Offline replay: `output/alpaca_market_data/20260913-active/alpaca-panel-market-collection-78b7ebd7ede92ed8e5f9d0ca925383fcdb6fe940ab68b9e71136606781a24512.json`.

## Prior September 12 verification

The complete test suites passed: 558 in the optional modeling environment and
549 in the minimal environment. The original financial/label evidence replay
also passed. The actual unavailable-market assembly retained all 18 observations,
kept the five added features null, and stopped fitting at the unchanged first-fold
comparison gate of 2/20. That earlier checkpoint did not collect authenticated
market data or fit a real-data model. The successful September 13 collection is
a separate source result; it does not establish the missing acquisition outcomes.
