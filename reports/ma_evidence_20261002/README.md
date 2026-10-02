# Historical M&A evidence checkpoint (2026-10-02)

This checkpoint follows protocol
[`ma-collection-protocol-8ae4550e…`](../../data/research/ma_evidence_20261002/ma-collection-protocol-8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0.json).
It contains:

1. A ledger of all 300 frame rows (100 companies × 3 dates), recording outcome, source and valuation availability.
2. A superseding partial source review for the first frame row, ABUS 2021-01-01, which adds the recovered issuer press-release archive.

No labels, ordinal ratings, valuations or model fits were produced. No observation was newly admitted, and the canonical panel and model gates are unchanged. The evidence is retrospective and was gathered with outcomes already known. The reviewer is an agent (Claude Opus 5.5, session `eab10226-e465-4fd6-877d-68427f394405`), not an independent human.

## Current artifact chain

Every artifact is content-addressed: the filename contains the SHA-256 of its own bytes.

| Artifact | Path (under `data/research/ma_evidence_20261002/` unless noted) | SHA-256 |
|---|---|---|
| Input snapshot manifest | `input-snapshot-b8796483….json` | `b87964831a19ef9d16b324d29e2fe3d9d6dc3ff153353ba7110abc55d6c1209c` |
| Source-availability index | `source-availability-cf648d67….json` | `cf648d67f368291d996e3549bf0f10f09829e142d9bf9b704d54e1b0b001ca5b` |
| Frame ledger (JSON) | `ma-evidence-frame-ledger-c4cdf806….json` | `c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99` |
| Frame ledger (CSV, 300 rows) | [`reports/…/ma-evidence-frame-ledger-78682d22….csv`](ma-evidence-frame-ledger-78682d22fa8b55da5233990dd9cee445a033323c3620df551dd43e8eb997bcbe.csv) | `78682d22fa8b55da5233990dd9cee445a033323c3620df551dd43e8eb997bcbe` |
| ABUS SEC screening receipt | `abus_2021/sec-screening-ABUS-1fd3ddd7….json` | `1fd3ddd7f4bc35276a2572400bcffb4031b0259b72f378d9291b75efb9d57577` |
| ABUS issuer archive collection | `abus_2021/issuer_archive/issuer-archive-collection-75e5039c….json` (+ `raw/`, `attempts/`) | `75e5039c4134cdb01ef8d191fb239f3571aaf52713e7d6060ab401cf3e8c4677` |
| ABUS 2021 partial review v2 | `abus_2021/abus-2021-partial-review-v2-9cc529b1….json` | `9cc529b1dfb06507192f3657bfa2d526858b5ca9ed4c7cea721e8ea15f198f8d` |

**Retained history, superseded but never rewritten:**

- snapshot `ce6e8695…`
- availability index `71dd082d…`
- ledger `d1564758…`
- screening receipt `bd837220…`
- first packet `a21c5285…`, with its builder `build_abus_2021_packet.py` (`74e1c64a…`, unchanged)
- issuer archive collection `b5de0f89…`
- v2 packet `4bcff203…`

These superseded files were produced by code that the independent Sol reviews (two REQUEST_CHANGES rounds) found too permissive. The data content they hold is unchanged in the successors:

- the CSV is identical;
- the new availability scan's per-ticker content is identical;
- the screening receipt differs only in the screener hash;
- collection `75e5039c` was regenerated from the same verified cached captures and attempt receipts, with no network requests. It differs from `b5de0f89` only in collector hash and run clocks. `b5de0f89` also passes the new validator.
- v2 packet `9cc529b1` has the same SEC findings and issuer bodies as `4bcff203`. It differs only in its collection reference, review clock, clock count and code hashes. `4bcff203` was built before the frozen-protocol and complete-archive-clock guards existed.

## Replay and data custody

```bash
python3 scripts/build_ma_evidence_ledger.py snapshot --original-root /home/umwai/biotech-ma-predictor \
  --valuation-root <valuation_probe> --protocol <protocol.json> --output-dir data/research/ma_evidence_20261002
python3 scripts/build_ma_evidence_ledger.py build --snapshot <input-snapshot-*.json> --protocol <protocol.json> \
  --output-dir data/research/ma_evidence_20261002 --report-dir reports/ma_evidence_20261002
```

**What `build` validates.** It checks every one of the 20 byte copies declared in the snapshot, including copies the join does not use. Each check covers:

- path confinement inside the snapshot root, symlinks included;
- the SHA-256 and byte length;
- the content-addressed filename.

It then checks the authoritative original hashes, schemas and recorded cross-bindings:

- `assembly.input_sha256`;
- `status` coverage and panel hashes;
- the protocol and valuation-probe frame hash;
- the frame source receipt and its HTML;
- the probe-to-manifest-to-raw-vendor-page chain.

**What can and cannot be published.**

- **14 copies are publishable:** the original panel, frame and research inputs, plus the valuation probe summary.
- **6 copies stay local:** the licensed vendor quote payloads, i.e. 3 Alpaca raw bar pages and 3 parsed price manifests. They are listed in `.gitignore`, because the vendor terms restrict public redistribution.
- **Effect on a public clone:** the snapshot manifest still records all 20 hashes. On a public clone, `build` fails closed with `local-only licensed vendor inputs are not distributed and are missing here`. A complete replay needs the locally retained files; nothing pretends the ledger is self-contained.
- **No prices in the ledger:** it holds per-row coverage, counts, dates and hash references only.
- **Valuation flags:** `original_vendor_vintage_archived` is false, and no ordinal valuation is made. Current-vendor SIP bars show only that a quote existed, and the SIP data's version is not verified.

**ABUS source dependencies.**

- The SEC collection, review queue and original tools are read from the unpublished original checkout by path and hash. A full ABUS source replay depends on that checkout.
- The issuer press-release bodies are archived in this repository under `abus_2021/issuer_archive/raw/`: 60 bodies plus 4 inventory pages, about 3.9 MB, public issuer pages.

## Frame ledger (unchanged counts)

The ledger's source-availability fields index the original checkout named in the snapshot. The newly owned ABUS archive and partial packet supplement that snapshot; they are not promoted into the original checkout or canonical panel. For example, ABUS's `issuer_archive_collection_count` remains 0 for the original source root even though this checkpoint separately archives 60 issuer bodies.

| Status | Rows |
|---|---:|
| Admitted positive / negative (existing panel) | 10 / 10 |
| Censored, no binary label (CALA 2023) | 1 |
| Prior control announcement, verified CIK, disposition unreviewed | 12 |
| Prior control event matched by ticker only (AKUS, FMTX 2023/2024) | 4 |
| SEC candidate filing in horizon, matched by name only, unadjudicated | 9 |
| Outcome unknown / unreviewed | 254 |

**Training support before 2023.** There are 5 distinct positive events and 4 distinct negative companies; the floor is 20 negative companies.

**Identity.** 72 companies (216 rows) have no resolved CIK. Ticker or name matches never resolve identity.

**Candidates.** "In horizon" is based on the SEC filing date. A merger proxy or Schedule 14D-9 can follow an announcement made before the observation date, so the date alone does not place the event inside the window.

## ABUS 2021-01-01: superseding partial review v2

**Result:** still blocked. No row is admitted and there is no label.

### Issuer archive recovered

The archive comes from `arbutusbio.gcs-web.com`, a public publisher host operated for the issuer that was found in issuer-indexed material. It was reached through normal public URLs with no authentication or protection workaround.

**Inventory.** The year-selector inventory was reused from the primary's captures and rebuilt from the archived public year form:

| Year | Releases | Selected year verified | Next-page link |
|---|---:|---|---|
| 2020 | 23 | yes | none |
| 2021 | 32 | yes | none |
| 2022 | 26 | yes | none |

**Bodies collected.** All 60 releases dated inside the window were captured and identity-checked:

- **Window:** all of 2020, all of 2021, and 2022 Q1 only. 2022 bodies dated after Q1 were not fetched.
- **Fetch method:**
  - one `requests` GET per URL;
  - honest project User-Agent;
  - 10 s connect / 30 s read timeout;
  - no redirects followed, no retries;
  - every attempt persisted before the next request.
- **Identity checks:** each page's canonical link, og:url, headline and displayed date match the frozen inventory row.

**Comparison with SEC filings.** 31 bodies match a same-period SEC EX-99 exhibit (word coverage ≥ 0.99), which falls within the earlier SEC review. The other 29 are issuer-only releases, and I read them manually:

- results-call scheduling notices;
- investor-conference participation notices;
- Assembly/Antios clinical collaborations;
- EASL/AASLD abstract notices;
- an investor-relations VP appointment;
- the 2022-02-28 Moderna patent suit (lag window).

**Finding.** None of the 60 releases announces any of the following:

- a definitive agreement transferring more than 50% control;
- a pending transaction or a tender offer;
- a strategic-alternatives process;
- a listing exit or insolvency.

The only screening hits are two `business_combination` mentions in the 2020-03-05 release, which describe historical acquisition accounting.

**Still unproven:** archive completeness, removed releases, original body versions, PDF versions, images and linked documents.

### Collector history (disclosed)

1. **First checkpoint.** `www.arbutusbio.com` returned 200. Three requests timed out, each tried once: `investor.arbutusbio.com` twice and the GlobeNewswire organization page once. Those receipts are kept.
2. **First version of `scripts/collect_ma_issuer_archive.py` (urllib transport).** It ran for about 6 minutes and kept failures in memory. The primary interrupted it at 2026-10-02T19:51:25Z (`opus-worker-interruption.json`). Its individual body-attempt failure receipts, about 8 requests, were never written and are not reconstructed.
3. **Changed hypothesis.** The primary made an ordinary `requests` GET of the first body with the same honest agent, and it returned 200. The transport was changed to `requests`. This was a change of client, not a retry loop.

### SEC review (re-verified)

Every first-packet citation was re-cited through hash-verified extracted bytes, and the locators are identical. The 8-K item census is now computed from verified text: 45 primary 8-Ks, none with Item 1.02, 2.01, 3.01, 3.03, 5.01 or 5.03.

Roivant's position:

- 29.1% after the conversion on October 18, 2021, per 13D/A No. 11;
- 16.6% excluding preferred shares, or about 32% if converted, per the April 2021 proxy.

Qilu and Genevant are licence events, not control events.

### Excluded SEC forms

Relevance was adjudicated per form class against the registered control and exit definitions; the filings' contents were not reviewed. The window's inventory lists:

| Form | Count | Relevance to a control announcement |
|---|---:|---|
| 4 | 39 | Not an announcement channel |
| 3 | 2 | Not an announcement channel |
| SC 13G / 13G/A | 1 / 7 | Not a channel: by eligibility, 13G filers certify no control purpose |
| S-8 | 2 | Not an announcement channel |
| EFFECT | 3 | Not an announcement channel |
| CT ORDER | 2 | Not an announcement channel |
| CORRESP | 3 | Unknown |
| UPLOAD | 2 | Unknown |

No assumption is made that the issuer met every filing duty.

### Valuation-source lead (not a rating)

- The original S-3 (`0001104659-20-100169`, filed 2020-08-28) reports a Nasdaq last sale price of $2.92 on 2020-08-27. That price is 127 days old at the observation date.
- Two 424B5 filings (`…-20-000121` and `…-20-000124`, which contain the identical document) report $4.37 on 2020-08-06, 148 days old.

These prices are public source facts, separate from the licensed vendor data. They are not a December 31 quote, and no valuation rating has been made. Shares, cash, debt, rights and a dated comparable framework are still needed.

### Gates still open

- **Graphics:** 623 SEC graphic payloads (583 unique decoded) and the issuer-page images have not been reviewed.
- **Unreviewed SEC payloads:** 268 unsupported-format payloads and 98 with empty text extraction.
- **References:** incorporated references have not been reviewed.
- **Versions:** there are no per-accession original-version judgments; as-accepted byte identity remains false. The original version and completeness of the issuer releases are also unverified.
- **SEC subject identity:** no per-document subject-identity review has been done.
- **Pending baseline:** there is no pre-2020 pending-transaction baseline review.
- **Membership:** no membership interval has been adjudicated.
- **Outcome review:** there is no complete SEC outcome review and no historical timing receipt.

The excluded-forms gate is only partly reduced: relevance was adjudicated, but the contents were not reviewed.

## Code

| File | Role |
|---|---|
| `scripts/ma_evidence_io.py` | Path confinement, single-read hash and parse, measured review clocks |
| `scripts/build_ma_evidence_ledger.py` | Snapshot and ledger, with whole-manifest validation |
| `scripts/screen_ma_source_packet.py` | SEC replay and screening, confined and reading each file once |
| `scripts/ma_source_packet.py` | Verified-byte citations, 8-K census, release comparison |
| `scripts/collect_ma_issuer_archive.py` | Inventory freeze and incremental `requests` body capture |
| `data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet_v2.py` | Superseding packet builder; enforces the frozen protocol bytes |

The base-commit `scripts/collect_issuer_archives.py` supplies the HTML `Document`, `clean` and `drupal_*` parsers; it is imported, not copied.

**Tests.** `tests/test_ma_evidence_ledger.py` and `tests/test_ma_evidence_integrity.py` use invented fixtures or local snapshot copies.

- The collector tests use fake sessions and a stub `requests` module, so they run without network access or the client installed.
- The public-clone fail-closed test always runs.
- The tamper and escape tests on snapshot copies skip when the local-only inputs are absent.
- The integrity tests reference snapshot `b8796483…` by name and must be updated if the snapshot is regenerated.

**Clock and protocol guards.**

- **Protocol.** The v2 builder reads the registered protocol once, confined to its root, before any use of its policy or clocks. It requires:
  - the exact frozen SHA-256 `8ae4550e…`;
  - schema `ma-evidence-collection-protocol-v1`;
  - equality with the protocol bindings of the first packet and the ledger.

  A changed policy under the unchanged frozen filename is rejected.
- **Archive clocks.** `validate_archive` in `scripts/collect_ma_issuer_archive.py` is shared: the collector runs it before writing a collection, and the packet builder runs it when reading one. It covers:
  - the archive page, every year page and every recorded attempt receipt;
  - timezone-aware clocks ordered attempted ≤ retrieved/completed/failed ≤ measured now;
  - collection started ≤ completed, with completion at or after every represented source clock;
  - raw bytes and attempt-summary bindings, and identity re-parse.

  The collector checks primary probe receipts and cached attempts before reusing them.
- **Review time.** The packet's measured review time must follow all 258 represented source clocks: archive, year pages, attempts, the first-checkpoint GET receipts, the protocol registration, the first packet, the SEC queue, collection completion and the interruption receipt.
- **No repairs.** Invalid receipts are rejected; no timestamp is invented or corrected.

**Known limits:**

- The ledger and screener bind only their own script hashes, not the shared `scripts/ma_evidence_io.py` they import. The functions they use (`confined`, `read_once`) are unchanged since that file was introduced; this round only added `chronology`. Their artifacts reproduce byte-exact.

- `snapshot()` re-reads its own newly written, content-addressed availability file to take the manifest hash. `build` re-verifies that file's content address and hash, so the step fails closed. I did not regenerate the chain for this self-written file.
- The retained first-packet builder `build_abus_2021_packet.py` globs for exactly one ledger and one screening receipt. It is kept as history and no longer re-runs in this directory unchanged.
