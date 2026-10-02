# Independent Sol evidence checkpoint acceptance

**Verdict: PASS for the corrected partial evidence checkpoint.** Reviewer: GPT-6.1 Sol. Read-only review of `/tmp/biotech-ma-evidence-20261002-gxcbzh98/checkout`, base `c7f565750455d0f7db5c1ccdfc30524b02150e6f`, on 2026-10-02; final artifact/hash/clock checks measured at `2026-10-02T20:21:34.486716+00:00`. Both blockers in `sol-evidence-final-review.md` are resolved. No new blocking finding. This supersedes the REQUEST_CHANGES verdict for the corrected active code and new artifacts; earlier reviews and vulnerable historical artifacts remain unchanged.

This PASS covers mechanical ledger/source replay, provenance guards, chronology validation, the explicitly partial ABUS packet and local-only vendor custody. It does not approve a label, ordinal rating, original-version judgment, full source admission, fitted model, predictive/economic claim, independent human/blind review or capital authority. Buyer-universe implementation was excluded; Opus owns its independent review.

## Corrections verified

1. **Frozen protocol authority.** `build_abus_2021_packet_v2.py:100-107,132-133` reads the confined protocol once, enforces exact digest `8ae4550e…` and schema, and requires equality with the verified first packet and ledger before policy or clock use. I repeated the previous actual-main injection, changing `event_policy.positive` to `UNREGISTERED_TEST_RULE` under the fixed filename and deriving the digest from those same bytes. `main()` now rejects digest `0af4e223…` with `protocol bytes are not the frozen registration`. Output writes were intercepted; there were **zero writes**.

2. **Complete represented archive chronology.** `collect_ma_issuer_archive.py:82,109-130,281-332` validates probe/cache clocks and shares the archive validator between producer and consumer. It checks aware attempted/end clocks against measured now, bound raw bytes and attempt summaries, collection start/completion, and completion after every represented source clock. `build_abus_2021_packet_v2.py:164,167,210-214` consumes the returned clocks and adds first-checkpoint GET receipts and the other review dependencies. I repeated the previous invented fixture with a 2099 inventory receipt: the collector now rejects it **before any transport call**, without a successful collection artifact. Future, reversed and naive clocks, cached-attempt ordering, and consumer validation have meaningful regressions. Both real old/new collections validate 188 source clocks each; the new packet validates 258 represented review-source clocks.

The original four findings are resolved on active paths: confinement includes escaping symlinks; all 20 declared copies are validated with authoritative hashes/schema/cross-bindings; hash and parse/census use verified byte snapshots; actual review/source chronology is checked. No threshold or scientific/model gate was relaxed.

## Validation and unchanged evidence

- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_ma_evidence_integrity.py tests/test_ma_evidence_ledger.py`: **27 passed in 0.16s**, no skips or network. No unaffected model suites were rerun.
- Executed the final actual v2 `main()` with its authenticated recorded review time and intercepted its sole output write in memory. It reproduced packet `9cc529b1…` **byte for byte**, including all 258 clocks and current tool hashes; no repository file was written.
- Revalidated the old `b5de0f89…` and new `75e5039c…` archive collections from bound raw files/receipts. They differ only in `collector_sha256`, `started_at` and `completed_at`. All 60 attempt receipts and 64 raw files remain unchanged. The new collection's cached-only/no-request regeneration check is supplied by the implementer and supported by unchanged captures plus the cache/no-retry regressions.
- Compared new and prior v2 packets. Differences are exactly `reviewed_at`, `represented_source_clocks_checked`, `sources`, `supersedes_v2` and `tool_basis_new`. SEC findings, issuer body records, no-label/no-rating flags and source-review gaps are unchanged. Every current `tool_basis_new` digest matches its file.
- Reused my previous exact 300-row JSON/CSV rebuild, 20-copy/4,740,980-byte validation, original schema/frame/assembly/status/probe/vendor bindings, and SEC replay (67 index + 67 submission responses, 1,799 payload slices, 810 screened texts, 544 contexts). Their input artifacts and the ledger/screener/packet-helper functions are unchanged. The implementer additionally reproduced the same ledger/screener bytes in temporary outputs after adding chronology.
- Reused the unchanged inventory/body/receipt audit: 81 inventory entries (23/32/26), 60 selected bodies (23/32/5), all hash/identity/time bound. Of those, 31 match same-period SEC exhibits and 29 are issuer-only partial review. These are finite current-archive counts, not completeness or negative-label evidence.
- Reused the unchanged six public SEC strategy-lead raw/receipt checks and six ignored/untracked vendor-input/public-clone failure checks. `.gitignore` and those input bytes are unchanged. Missing licensed copies still block full ledger replay explicitly.
- Rehashed all content-addressed files in the evidence and report scope (158 and 2). Final artifact/code bindings and README links pass; `git diff --check` passes. Inspected the final README clarification that availability fields index the recorded original source root: ABUS archive count 0 there does not deny the separately owned 60-body archive or admit it into the canonical panel.

## Exact final basis

Stable final handback: `/tmp/biotech-ma-evidence-20261002-gxcbzh98/opus-evidence-final-fixes-handback.json`, SHA-256 `4ca810ecfa55eea33adabd6bac9c54225cef7ef543da1de9ebeaa1b104ef8bf5`. All code/test/ignore hashes match it. The final README has only the primary's subsequently inspected source-root clarification and the actual digest listed below.

| File | SHA-256 |
|---|---|
| `scripts/ma_evidence_io.py` | `3412641267705f8ff972c4d7f80d01ea8cc704d31f772b5d9c1dbf4bca8f8fcc` |
| `scripts/collect_ma_issuer_archive.py` | `d0d02c279d1ec900887ee4258705549b46917cbc68f3351212b4b343e6fdf1c5` |
| `scripts/ma_source_packet.py` | `7c73e3084245b5d7d4733daca1ae652fb16a3a5b30a517b88d0a58d52409dcb9` |
| `scripts/build_ma_evidence_ledger.py` | `0f18c88ca4aab5756825f17636094b67450f6c7beb1476734a5bd34405030410` |
| `scripts/screen_ma_source_packet.py` | `b7a3b392dd7bb3cff4be62372cd46384e4772417b7739263027d1a00bc1de860` |
| `data/research/ma_evidence_20261002/abus_2021/build_abus_2021_packet_v2.py` | `bdc8eadacc9cdd49c178d20e6592b3bbfc149077c8378736dd03111a59b7216e` |
| `tests/test_ma_evidence_integrity.py` | `7113a97ecc70199a108fc474b8a8d57195dbdc5829cd2a1d0997f8698a161fdf` |
| `tests/test_ma_evidence_ledger.py` | `352a8d25f51dfd749f43b3f10ef08a80d8c72ac1ebd589c298d2942f517a3f69` |
| `reports/ma_evidence_20261002/README.md` | `6f9a1bf2e8c0e242ffa76bf54bf732745d2629c3aede6353cf4536fbaceb8f79` |
| `.gitignore` | `2fd06a4d670d3236e6591a89d92952f828f2916efddb84c14107bd9c22616fd2` |

Final new artifacts under `data/research/ma_evidence_20261002/abus_2021/`:

- `issuer_archive/issuer-archive-collection-75e5039c4134cdb01ef8d191fb239f3571aaf52713e7d6060ab401cf3e8c4677.json`
- `abus-2021-partial-review-v2-9cc529b1dfb06507192f3657bfa2d526858b5ca9ed4c7cea721e8ea15f198f8d.json`, recorded review `2026-10-02T20:16:53+00:00`.

Unchanged chain: protocol `8ae4550ecf5bd7c8483d4b4ab60f701011f34bd667b6e82bd3595b1d8851b2e0`; snapshot `b87964831a19ef9d16b324d29e2fe3d9d6dc3ff153353ba7110abc55d6c1209c`; availability `cf648d67f368291d996e3549bf0f10f09829e142d9bf9b704d54e1b0b001ca5b`; ledger `c4cdf8060874505cd965b80ba7344c484c335e0344e63bd1f32783e14af1bf99`; CSV `78682d22fa8b55da5233990dd9cee445a033323c3620df551dd43e8eb997bcbe`; SEC screening `1fd3ddd7f4bc35276a2572400bcffb4031b0259b72f378d9291b75efb9d57577`; public strategy leads `e33b6f44bf9c80e3084476fc91cd743931d2f79cabf9988e395ba952e3722e1f`.

## Remaining limits

- The ledger and screener bind **their top-level script hashes only**, not the entire imported execution tree. Their `confined`/`read_once` dependencies are unchanged; the current v2 packet separately binds all new tool files, including shared IO. This is adequate for the reviewed partial checkpoint and verified replay, not a claim of a fully immutable standalone execution tree.
- Full ledger replay needs six local-only licensed vendor files. Full ABUS packet replay still depends on the unpublished original SEC collection/queue/tool basis and taskroot first-checkpoint GET/interruption receipts. It fails when those dependencies are missing; a public clone is not represented as self-contained.
- Retained vulnerable first/v2 builders and receipts are history, explicitly superseded. The active path never executes the first builder. Snapshot rereading of its own written availability file remains disclosed and checked fail-closed by the consumer.
- ABUS remains **blocked**: 623 SEC graphics (583 unique) and issuer images, 268 unsupported plus 98 empty-extraction payloads, incorporated references, per-accession/issuer-release original versions, SEC per-document subject identity, pre-2020 pending baseline, membership interval and complete outcome/timing review remain open. Current publisher pages cannot establish historical completeness or removed/unchanged releases.
- Current vendor vintage remains unverified; source feasibility does not support an ordinal valuation. Retrospective outcome exposure remains disclosed. First-fold support remains 5 positive events and 4 distinct negative companies; the full 20-row panel has 6 distinct negative companies. There is no new admitted row, negative label, rating, fit or predictive/economic result.

No implementation/source/original-tree edits, providers/agents, network fetches, broker actions, commits or pushes occurred during this review. The requested review file is the only persistent review output; invented fixtures and captured replay outputs stayed temporary or in memory.
