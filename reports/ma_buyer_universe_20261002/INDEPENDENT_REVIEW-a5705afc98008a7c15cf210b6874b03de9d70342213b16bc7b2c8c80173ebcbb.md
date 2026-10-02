# Final independent review: Sol buyer-universe corrections

- **Reviewer:** Claude Opus 5.5 (`claude-opus-5-5`), Claude Code session `eab10226-e465-4fd6-877d-68427f394405`, subscription route. This is an agent review, not a human, blind or independent audit.
- **Review window (measured UTC):** 2026-10-02T20:09:27Z to 20:10:40Z.
- **Mode:** read-only. I edited, staged and committed nothing, and called no provider or agent.
- **Target:** `/tmp/biotech-ma-evidence-20261002-gxcbzh98/buyer-checkout`, base `c7f565750455d0f7db5c1ccdfc30524b02150e6f`. Only untracked buyer paths changed. `scripts/collect_issuer_archives.py` and `src/research/training.py` are identical to the base.
- **Prior review:** `opus-buyer-review.md` (`d7dd699d…`). That was a mechanical PASS with 5 non-blocking findings. Primary accepted 1, 2, 3 and 5; finding 4 is deferred.

## Verdict: PASS (mechanical scope). No blockers.

Accepted findings 1, 2, 3 and 5 are correctly fixed. Finding 4 is unchanged as instructed: acceptance date must still equal filing date, which fails closed (`ma_buyer_universe.py:97`). The README and report limits now disclose it.

The PASS covers:
- parsing and membership of the source-backed lagged September 30 schedules;
- integer reconciliation;
- official publication bounds;
- hash, receipt and root bindings;
- exact recomputation of current-delivery equality;
- the deterministic manifest and report.

The PASS does **not** cover:
- original vintage or as-accepted identity;
- January 1 eligibility or identity continuity;
- self-target exclusion;
- fit, capacity or financial ratings;
- probabilities, labels, models or predictive evidence.

## Basis hashes

| Artifact | SHA-256 |
|---|---|
| `src/research/ma_buyer_universe.py` | `e71fb9cb824f489c8f58e0a036706582c54b902db1046c92c4e542d82ce024af` |
| `tests/test_ma_buyer_universe.py` (42 tests collected) | `8045f76fb646685297d5df35f06ab1d7b4130ede2d88d87c4c746db57277d205` |
| `scripts/build_ma_buyer_universe.py` | `4df99a9d1a9eaeafdec78b6b65c62e0669b3865737754e1df141149e1741d7ac` |
| `scripts/collect_issuer_archives.py` (base) | `a4e8f08a4c7f11d6676e8d56c778ff79efaafe8552d387714855e724cf819182` |
| `src/research/training.py` (base) | `480d2892b53f8b2b7e8946ab9272b4150191a70079b2722990f347a00263e9d5` |
| `reports/ma_buyer_universe_20261002/README.md` | `e5f4015e7785e89eadc70e82a21da93905b8a88ab9395e0148415a8fa8eb491c` |
| Source manifest | `78eb9dfc4d589217341af2c73436b324be76f6d32ef68149f0d39765bb4f1d3d` |
| Delivery comparison (`compared_at` 19:30:17.345731Z) | `c67b895d372cb0eacdeb5be4839d84d139c272f7cc7fbf60846259f653c6c97e` |
| Replay manifest | `c21c957d93e11ea2bbeeacd28c1364027575495ae0b0a10a58b542a118de7981` |
| Universe report | `05b1cee39398cdb5a8bf834c242415a3ade1e1ea020d9f8296470dfbd5b9a7bd` |
| Execution (`executed_at` 19:52:59.095385Z) | `ee5752820fe8851d9d46e6ff5100ed91f3b1c7f22bc76c2d231e5be70937678d` |
| Second identical execution (19:53:00.031032Z) | `2e37371a396a370b311c4ab73a376c4b66addf149ed9ea3ad52b2f23fa71d397` |

## Evidence

1. **Bindings.**
   - Both executions bind replay manifest `c21c957d` and report `05b1cee3`.
   - The four `code_sha256` values in the report equal the current files, and `input_manifest_sha256` equals `78eb9dfc`.
   - I ran one focused check at 20:10:26Z: `replay()` in memory with current code, writing nothing. Its canonical serialization reproduces `c21c957d` and `05b1cee3` byte for byte.
   - I reused Sol's 42 passing tests rather than rerunning them.
2. **Delivery equality is recomputed, not trusted (finding 1 fixed; `ma_buyer_universe.py:129-170`, called at `:328`).**
   - The replay parses every `<DOCUMENT>` block of the archived complete submission and requires exactly one member whose header has `<FILENAME>` equal to the report filename and `<TYPE>N-CSR`.
   - It checks that member's length and SHA against the comparison record.
   - Each of the 4 recorded fragments must be a typed, non-empty UTF-8 string with matching length and hash. It must occur exactly once in the direct delivery and zero times in the complete submission, and be a complete `<script>…</script>` or `<noscript>…</noscript>` block, three scripts and one noscript.
   - The fragments must total the recorded extra bytes. Removing them exactly must leave bytes equal to the embedded block.
   - Fragments are matched by regex only; nothing is executed or rendered.
   - Real-data results are 2,297,777 / 2,700,412 / 2,994,150 bytes, 472 bytes removed in each year, with embedded SHAs `cf466c35…`, `fb3fb697…` and `7421049a…`. These equal my independent recompute in the prior review.
   - The comparison artifact's boolean is still required (`:327`) but no longer decides the outcome.
3. **Comparison clock (finding 2 fixed; `:284-285`, `:318-320`).**
   - `compared_at` must be ≤ actual now. It must also be ≥ the later of the direct-report and complete-submission retrieval clocks for each year.
   - Real values: compared at 19:30:17.35Z; latest compared-source retrieval is 19:28:49.55Z.
   - Index retrievals are not part of the byte comparison and are separately bounded by the publication and retrieval checks.
4. **Iterative terminal stripping (finding 3 fixed; `_issuer_name`, `:118-126`).**
   - Terminal `(ADR)`/`(USD)` and trailing whitespace, `*` or `†` are removed in a loop, regardless of order. Interior text is untouched.
   - Tests at `tests/test_ma_buyer_universe.py:236-250` cover `* (ADR)`, `*(ADR)`, `(ADR)*` and `(USD) †`.
   - On real data, all 75 displayed names, stripped issuer names, shares, values, countries, locators and row audits are identical to the previous report `3cb8a2cf`. So the fix changed no membership.
5. **README chain (finding 5 fixed).**
   - The README names the final chain: source `78eb9dfc` → replay manifest `c21c957d` → report `05b1cee3` → execution `ee575282`, plus identical second execution `2e37371a`.
   - It lists the superseded source `b14495bb`, manifests `579a7c76`/`57c825fd`/`a8a7c4a1`, reports `eb2abd47`/`dc8d0282`/`3cb8a2cf` and the earlier executions as retained history. All are still present.
6. **Membership and limits.**
   - Each year has 25 securities and 25 issuers.
   - Integer reconciliation is exact: 234,580,292 / 522,184,933 / 428,877,905.
   - There is no survivor, eventual-acquirer or current-name filtering or mapping. Mylan NV (2020), Viatris (2022/2023) and AstraZeneca Plc (all years) are kept as printed.
   - The report keeps:
     - `jan1_eligibility_verified: false`
     - `subsequent_dated_eligibility_review_required: true`
     - `as_accepted_byte_identity_verified: false`
     - `human_audit: false`
     - `original_version_judgement: pending_primary_and_independent_review`
     - `probability: null`
     - `validated_predictive_edge: false`
     - `model_training_performed: false`
     - `universe_exhaustive_pharma: false`
   - Its limits state that self-target exclusion (AZN is a frame member) and corporate exits need a later dated review.

## Non-blocking observations (no change required for this PASS)

1. **Unspecific test assertions.** `tests/test_ma_buyer_universe.py:225-226`: the 12 version-audit mutation cases assert only `TrainingBlocked`, with no `match=`. So a case could pass through a guard other than the one intended; for example, `contradictory_assertion` is caught by the binding check at `:327`, not the recompute. Adding fragment matches would show each guard firing. Low.
2. **Narrow marker set.** `_issuer_name` strips only `*`, `†`, `(ADR)` and `(USD)`. A future schedule using other footnote markers, such as `‡` or `§`, would keep them in the name. Current data has none, and the gap fails visibly as distinct names rather than as a silent merge. Low, latent.
3. **Equality is between current deliveries only.** The equality shown is between two current SEC deliveries. Neither the recompute nor the hashes establish original vintage, as-accepted bytes or corporate eligibility, and the artifacts do not claim otherwise.
