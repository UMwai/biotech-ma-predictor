# Using Claude Fable 5 in the Biotech M&A Predictor

Assessment of where Anthropic's Claude Fable 5 model would add value in this
system, plus the cost, safety, and configuration constraints specific to a
biotech / life-sciences workload.

## Current State

The system is built with LLM use *in mind* but does not call one today:

- `src/config.py` and `config/config.template.env` already declare
  `ANTHROPIC_API_KEY` (commented "for analysis") and `OPENAI_API_KEY`.
- No module imports an LLM SDK, and `anthropic` is **not** in
  `requirements.txt`. This is a greenfield first integration, not a migration.

Everywhere the system currently makes a "judgment," it uses deterministic rules:

| Area | File | Today |
|------|------|-------|
| Sentiment | `src/market/sentiment.py` | Hand-built keyword lexicon (positive/negative word lists) |
| Reports | `src/reports/` | Jinja2 templates → HTML/PDF (data-fill, no prose) |
| Scoring | `src/scoring/engine.py` | Arithmetic over component scores |

These are precisely the places a strong reasoning model changes the *quality*
of the output rather than just the plumbing.

## Where Fable 5 Fits (best first)

### 1. Deep-dive analyst report narrative — highest value, lowest risk
- **Where:** `src/reports/generator.py` (`DeepDiveReport`).
- **Today:** a filled template.
- **Why Fable 5:** the target quality is already in the repo —
  `reports/XENON_AZETUKALNER_REPORT.md` is 1,600+ lines of rich human-written
  analyst synthesis. Generating that narrative from structured signals is
  Fable 5's documented strength ("end-to-end enterprise deliverables — financial
  analysis, docs").
- **Why start here:** a human reviews the output before it reaches a client, and
  volume is naturally low, so cost is a non-issue. You can grade output directly
  against the Xenon report.

### 2. Signal extraction from unstructured filings — high value, cost-sensitive
- **Where:** `src/ingestion/sec_edgar.py`, `fda.py`, `clinical_trials.py`.
- **What:** pull structured signals (risk-factor changes, catalysts,
  trial-outcome readouts) out of 10-Ks, 8-Ks, and trial text.
- **Caveat:** this is the high-volume, 24/7 path — see cost tiering below.

### 3. Sentiment — medium value
- **Where:** `src/market/sentiment.py`.
- **What:** replace the keyword lexicon with an LLM reading of news/filings to
  capture nuance (hedged guidance, "beat but guided down", sarcasm).

### 4. Investment thesis / acquirer-fit rationale
- **Where:** `src/targets/identifier.py` (`_generate_acquirer_matches`,
  `_generate_catalysts`).
- **What:** the quantitative match already exists; Fable 5 writes the *why*.

## Constraints Specific to This Repo

### Cost tiering is the key design decision
Fable 5 is **$10 / $50 per 1M tokens** (input / output) — 2× Opus 4.8 and
3–10× Sonnet 5 / Haiku 4.5. This system "runs 24/7," so **do not put Fable 5 on
the high-volume ingestion path.** Tier it:

| Model | Price (in/out per 1M) | Use for |
|-------|-----------------------|---------|
| Haiku 4.5 (`claude-haiku-4-5`) | $1 / $5 | Bulk classification, cheap extraction |
| Sonnet 5 (`claude-sonnet-5`) | $3 / $15 | Most extraction and structured reads |
| Opus 4.8 (`claude-opus-4-8`) | $5 / $25 | Hard reads; refusal fallback target |
| Fable 5 (`claude-fable-5`) | $10 / $50 | Low-frequency, high-value reasoning: deep-dive synthesis, final thesis |

### Biotech triggers Fable 5's safety classifiers
Fable 5 runs classifiers targeting research biology and cybersecurity, and
benign life-sciences work can produce **false-positive refusals** — returned as
an HTTP 200 with `stop_reason: "refusal"`, not an exception. For an app
reasoning over drug mechanisms and trial data:

- Always check `stop_reason` before reading `response.content`.
- Enable **server-side fallbacks to Opus 4.8** by default so a false refusal is
  rescued within the same call.

### Data retention
Fable 5 requires **≥30-day data retention** and is unavailable under
zero-data-retention — every request 400s otherwise. Confirm the org's retention
configuration before rollout.

### Install
Add `anthropic>=0.116` to `requirements.txt`. The API key is already wired into
`src/config.py` (`Settings.anthropic_api_key`).

## Integration Shape

Illustrative call for the deep-dive generator. Streaming because reports are long
output; fallbacks on by default for the refusal risk above.

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from settings

with client.beta.messages.stream(
    model="claude-fable-5",
    max_tokens=32000,
    output_config={"effort": "high"},          # no thinking/temperature params on Fable 5
    betas=["server-side-fallback-2026-06-01"],
    fallbacks=[{"model": "claude-opus-4-8"}],   # rescue biotech false-refusals
    system=ANALYST_SYSTEM_PROMPT,               # house style + the Xenon report as exemplar
    messages=[{"role": "user", "content": structured_signals_json}],
) as stream:
    report = stream.get_final_message()

if report.stop_reason == "refusal":
    handle_refusal(report)   # both Fable 5 and the fallback declined
```

Fable-5-specific API notes:
- Thinking is always on — omit the `thinking` parameter; control depth with
  `output_config.effort` (`low`/`medium`/`high`/`xhigh`/`max`).
- `temperature` / `top_p` / `top_k` are rejected (400). Steer with prompting.
- 1M-token context window, 128K max output. Stream for large outputs.

## Recommended Rollout

1. **Start with the deep-dive report narrative** as a new `src/analysis/`
   module wired into `reports/generator.py`. Highest value, human-in-the-loop,
   low volume; grade against `reports/XENON_AZETUKALNER_REPORT.md`.
2. **Then add the tiered extraction layer** (ingestion → scoring), with
   Sonnet 5 / Haiku 4.5 doing the bulk work and Fable 5 only on escalation.
