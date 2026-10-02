# Independent Sol corrected evidence checkpoint review

**Verdict: REQUEST_CHANGES.** Read-only review of `/tmp/biotech-ma-evidence-20261002-gxcbzh98/checkout`, base `c7f565750455d0f7db5c1ccdfc30524b02150e6f`. Reviewer: GPT-6.1 Sol. Review completed against the hashes below on 2026-10-02 after actual source/review clock checks. No implementation, original checkout, broker, provider, source-fetch, commit or push action occurred. Buyer-universe implementation is excluded.

## Remaining blockers

1. **Medium: enforce the frozen protocol in the v2 packet builder.** `data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet_v2.py:113-114` reads and parses protocol bytes without checking the registered digest or schema. Line 197 records whichever digest was read, without equality to the first packet and ledger protocol bindings. A fixed content-addressed-looking filename is insufficient.

   **Reproduction:** imported the actual v2 builder, wrapped only its `read_once(PROTOCOL)` result, changed `event_policy.positive` to `UNREGISTERED_TEST_RULE`, and derived the digest from the same mutated bytes. Intercepted `Path.write_bytes` for its output in memory; no repository file was changed. The actual `main('2026-10-02T20:02:27+00:00')` completed. Its packet bound protocol `0af4e2238dabaff8d7d22fc0085c3835b58c2204b521598ce942201d872cda54`, while the referenced ledger remained bound to `8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0`.

   **Required fix:** read the confined protocol once; enforce the exact frozen digest and schema, and equality to the already verified first-packet and ledger bindings before using its policy or clock. Add one meaningful changed-protocol regression. Regenerate the code-bound v2 packet; preserve the old packet unchanged.

2. **Medium: validate all issuer source clocks, including inventory captures and cached attempts.** `scripts/collect_ma_issuer_archive.py:75-87` copies probe `attempted_at`/`retrieved_at` without validating awareness, order or actual-now bounds; `:108-124` similarly trusts clocks in cached attempt receipts. The v2 builder includes body retrieval clocks at `:166` and collection completion at `:186-189`, but omits the archive/year-page clocks that it presents at `:209`. Therefore its claim at `:200` that review follows every represented source clock is not enforced.

   **Reproduction:** used the existing invented `probe_fixture`, changed only its 2020 inventory receipt to aware `attempted_at=2099-01-01T00:00:00+00:00`, `retrieved_at=2099-01-01T00:00:01+00:00`, and ran the actual collector with its existing fake response/session classes and `pause=0`. It emitted a successful content-addressed collection with two identity-verified bodies, that future inventory retrieval, and actual `completed_at=2026-10-02T20:11:32.184765+00:00`. All work was in a temporary invented fixture; no network or repository write occurred.

   **Required fix:** validate aware probe and cached-attempt clocks, with attempted <= retrieval/completion/failure <= measured actual now, and collection/review chronology against every source represented (archive page, year pages, bodies and recorded attempts). Include those source clocks in the packet validation or use a shared verified-archive validator. Add a focused future/reversed source-clock regression. Do not repair historical receipts or invent timestamps. The current real artifacts have valid clocks; the missing guards are the defect.

## Prior findings and scope

- Prior findings 1–3 are resolved on the corrected active paths: shared confinement rejects traversal, outside absolute paths and escaping symlinks; all 20 input copies are read/hash/length verified; availability metadata, submission slices, citations and census use verified byte snapshots.
- Prior finding 4 has a valid aware/nonfuture review-clock helper and its current actual review is chronological. Complete represented-source coverage remains open as blocker 2 above.
- The original input hashes, schemas and frame/assembly/status/probe/vendor cross-bindings are checked. Exact original raw panel `147059f3…` is preserved; no source admission is inferred from hashes or presence.
- Superseded packets and vulnerable first builder remain explicitly identified as historical. The active v2 builder never executes the old builder. README also states that the old builder's one-ledger/one-screening glob no longer reruns unchanged with the retained history.
- Original SEC collection, queue and original tool basis remain explicit unpublished dependencies. This is not standalone full-source replay or original-version admission.
- The six licensed vendor inputs are ignored by `.gitignore` and are not tracked. A public-clone simulation omitting all six failed explicitly with the local-only-input message. Public ledger fields remain counts, dates, coverage and hash references; no licensed quote values are exported by the ledger.
- Six public SEC strategy lead captures and their six original receipt copies are hash/length/URL/time bound. Their lead manifest retains no-rating and pending-version flags. Buyer eligibility and original vintage are not attested.

## Validation used

- Current affected suites: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_ma_evidence_integrity.py tests/test_ma_evidence_ledger.py`: **22 passed in 0.34s**, with fake collector transport and no network. The new test/README delta was inspected after the immutable worker handback; actual final hashes are below. No unrelated model suites were rerun.
- Actual ledger rebuild in a temporary output directory reproduced final JSON and CSV bytes exactly: 300 rows, 100 companies x three dates, 20 verified copies totaling 4,740,980 bytes. Old/new rows, summary and availability ticker metadata are identical. Reused the previous unchanged-row financial/label/quote-clock and no-new-label findings. First-fold support remains 5 positive events and 4 distinct negative companies; the entire panel has 6 distinct negative companies.
- Actual SEC screen replay reproduced the saved receipt bytes exactly: 67 index responses, 67 submission responses, 1,799 payload slices, 810 screened texts, 544 contexts. The 45-row 8-K census matches; 12 current packet SEC/price citation records reproduce their recorded pattern, offset, hash and excerpt. New and original unpublished tool-basis hashes currently match.
- Independently rebuilt the inventory from archived year-form/page bytes: 23/32/26 releases = 81; selected 23/32/5 = 60. Every selected raw body reparses identically, and all 60 receipts match URL, status, hash, byte count and actual chronological clocks. The matched subset is 31, minimum recorded word coverage 0.9945; the other 29 remain issuer-only partial review. These counts are not completeness or negative-label evidence.
- Verified every content address in the scoped evidence, strategy-lead and report trees (156, 7 and 1 respectively). Verified final artifact/code bindings, strategy receipts, all six ignore entries and public-clone failure. `git diff --check` passed. No source I/O beyond existing files occurred.

## Exact reviewed basis

Stable worker handback: `/tmp/biotech-ma-evidence-20261002-gxcbzh98/opus-evidence-corrected-handback.json`, SHA-256 `560d6d64d952acacd420ca3d492765ec94fbf204928802c1b336d5f5e9e38c19`. Core implementation matches it; tests/README advanced to the actual hashes below before this review finished.

| File | SHA-256 |
|---|---|
| `scripts/ma_evidence_io.py` | `41c64798910fc0b48f11afd7ec7044cb616b24e5ec7331ab6aca66c9da08caa2` |
| `scripts/build_ma_evidence_ledger.py` | `0f18c88ca4aab5756825f17636094b67450f6c7beb1476734a5bd34405030410` |
| `scripts/screen_ma_source_packet.py` | `b7a3b392dd7bb3cff4be62372cd46384e4772417b7739263027d1a00bc1de860` |
| `scripts/ma_source_packet.py` | `7c73e3084245b5d7d4733daca1ae652fb16a3a5b30a517b88d0a58d52409dcb9` |
| `scripts/collect_ma_issuer_archive.py` | `bea4462ba6a81a3d246ad17475824d1d98c0f21cb3814be1e1d60199c4053699` |
| `data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet_v2.py` | `5f3abcfb7e4a6769cdfe67c2ad2e47448cc77c8724f02ddbb4a5e925dc6a51dc` |
| `tests/test_ma_evidence_integrity.py` | `9af5fc2874b89726d58577f0a4957b74642d690d1b123e70e3c286ee32f979ad` |
| `tests/test_ma_evidence_ledger.py` | `352a8d25f51dfd749f43b3f10ef08a80d8c72ac1ebd589c298d2942f517a3f69` |
| `reports/ma_evidence_20261002/README.md` | `6d3f7be5ad739ea251e95d1e47fb7b5301de408fbf1336b204e8945b47d3cc02` |
| `.gitignore` | `2fd06a4d670d3236e6591a89d92952f828f2916efddb84c14107bd9c22616fd2` |

Current artifacts read under `data/research/ma_evidence_20261002/` (full suffix is each artifact's digest): protocol `8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0`; input snapshot `b87964831a19ef9d16b324d29e2fe3d9d6dc3ff153353ba7110abc55d6c1209c`; availability `cf648d67f368291d996e3549bf0f10f09829e142d9bf9b704d54e1b0b001ca5b`; ledger `c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99`; ABUS screening `1fd3ddd7f4bc35276a2572400bcffb4031b0259b72f378d9291b75efb9d57577`; issuer collection `b5de0f893de5edde994bdc1c63593c7467d1c5bbaab32ff058bba784d4dd0d84`; v2 packet `4bcff2038f19dac3e58ddc6e3b0ed5b8873c2c13057661239f100746ea17325d`. Report CSV is `78682d22fa8b55da5233990dd9cee445a033323c3620df551dd43e8eb997bcbe`. Strategy lead manifest is `e33b6f44bf9c80e3084476fc91cd743931d2f79cabf9988e395ba952e3722e1f`.

The scoped read set also includes all 20 input copies, retained first snapshot/availability/ledger/screen/packet/builder, original ABUS collection/queue and hash-referenced raw/extracted payloads, archived issuer inventory/body/attempt files, primary inventory receipts and interruption receipt, and six strategy raw/receipt pairs. All are evidence dependencies, not newly admitted observations. No label, ordinal rating, fitted model, predictive/economic claim, original-version attestation or capital authority is approved by this review.
