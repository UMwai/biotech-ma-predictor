# Sol publication-policy addendum

**PASS.** Independent read-only inspection of the final staged `.gitattributes` delta in `/tmp/biotech-ma-evidence-20261002-gxcbzh98/checkout`. Final working and staged bytes match; SHA-256 is `65c4f38918254afcdc2ddd01658d44eed811e09528a9bccd2f4ef541812ab2c9`.

The five named research data/report trees receive `-text`, preserving content-addressed bytes under checkout line-ending settings. `-diff` is limited to captured raw-source locations and the single frame-source HTML input. The buyer `raw_sources` rule was narrowed to `*.html` and `*.txt` after my inspection found that its first version also hid nine receipt JSON diffs. Final staged attributes suppress diffs for exactly **80 raw HTML/submission bodies and zero JSON metadata files**. Receipt/manifest/report metadata remains text-diffable. Script, test and `src` code attributes remain unspecified, so normal code diffs and whitespace checks are retained. The existing reviewed-history CSV rule is unchanged.

Validation:

- `git diff --cached --check`: exit 0 on the final staged delta.
- Independently compared all **222 staged blobs** with their working files: byte-identical. The only subsequent change narrowed the `-diff` rule; final staged/working attribute bytes were separately rechecked.
- A temporary `checkout-index` with `core.autocrlf=true` preserved every byte of **210 staged data/report files**. The final narrowing changes diff presentation only; all `-text` settings are unchanged, so this result remains applicable.
- Final `git check-attr --cached` verifies all 80 raw-body exclusions, zero JSON binary diffs, all evidence `text: unset`, and code `diff/text: unspecified`.

This preserves original captured source whitespace instead of normalizing it. Hash verification and the previously accepted code/source gates remain unchanged. The six licensed inputs remain ignored; no code, archive, hash-bound artifact or README change is part of this delta. No application suites were rerun for unchanged code. No implementation edits, network/provider actions, commits or pushes occurred during this review.
