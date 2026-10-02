# PPH buyer candidate universe replay

The final mechanical artifact chain is:

- [Source manifest](../../data/research/ma_buyer_universe_20261002/ma-buyer-source-manifest-78eb9dfc4d589217341af2c73436b324be76f6d32ef68149f0d39765bb4f1d3d.json), binding the frozen protocol, original SEC report/index captures and receipts, complete submissions, and delivery comparison.
- [Replay manifest](ma-buyer-replay-manifest-c21c957d93e11ea2bbeeacd28c1364027575495ae0b0a10a58b542a118de7981.json), binding those inputs and final replay code hashes.
- [Universe report](ma-buyer-universe-05b1cee39398cdb5a8bf834c242415a3ade1e1ea020d9f8296470dfbd5b9a7bd.json), containing all three schedules, integer totals, row locators and recomputed delivery comparisons.
- [Actual execution receipt](ma-buyer-execution-ee5752820fe8851d9d46e6ff5100ed91f3b1c7f22bc76c2d231e5be70937678d.json), executed at 2026-10-02T19:52:59.095385+00:00. A [second execution](ma-buyer-execution-2e37371a396a370b311c4ab73a376c4b66addf149ed9ea3ad52b2f23fa71d397.json) produced the identical manifest/report bytes.

Each annual schedule contains 25 securities and 25 exact stripped issuer names. Parsed common-stock totals equal the printed totals: 2020 $234,580,292; 2022 $522,184,933; 2023 $428,877,905. Replay verifies the four recorded delivery insertions (three scripts and one noscript, totaling 472 bytes) and exact equality with the same-named N-CSR DOCUMENT in each archived complete submission. It never executes that content.

This is source-backed membership from lagged September 30 holdings. Original-version judgment, January 1 eligibility, identity continuity, self-target exclusion, and qualitative ratings remain pending. `as_accepted_byte_identity_verified` and `human_audit` remain false. For these three frozen captures, acceptance and filing dates must coincide; generalized SEC after-hours calendar handling remains outside scope.

Superseded immutable files remain as history. Source manifest `b14495bb…`, replay manifests `579a7c76…` and `57c825fd…`, and universe reports `eb2abd47…` and `dc8d0282…` precede the complete-submission audit material. Replay manifest `a8a7c4a1…`, universe report `3cb8a2cf…`, and executions `b52d33d2…`/`04668e7d…` precede recomputation of the delivery comparison and terminal-annotation fixes. All other execution receipts belong to those historical replay chains; the two receipts linked above identify the final code-bound replay.

Offline replay from this repository:

```sh
python scripts/build_ma_buyer_universe.py \
  --manifest data/research/ma_buyer_universe_20261002/ma-buyer-source-manifest-78eb9dfc4d589217341af2c73436b324be76f6d32ef68149f0d39765bb4f1d3d.json \
  --evidence-root data/research/ma_buyer_universe_20261002 \
  --output-dir reports/ma_buyer_universe_20261002
```
