# Study-Integrity Diligence Model Card

## Purpose

The study-integrity lane identifies evidence that should change how much
confidence an analyst places in a biotech study. It is a diligence overlay,
not a fraud classifier and not an M&A probability.

The initial implementation consumes an append-only, source-linked evidence
ledger and produces:

- a company review queue;
- study- and category-level signals;
- an explicit distinction between concerns, pending inspections, formal
  regulatory findings, retractions, and confirmed research misconduct; and
- the issuer's response beside disputed evidence.

The discovery command also queries the official NCBI PubMed interface for
retracted publications and expressions of concern. By default, it emits only
records whose title, abstract, or PubMed metadata contains a ClinicalTrials.gov
identifier in the market inventory. An optional `--include-name-matches` mode
adds lower-confidence exact asset-name candidates. Every match remains a review
candidate until a human verifies study, sponsor, ownership, timing, and
retraction reason.

## Evidence contract

Every signal requires a dated HTTPS primary source, a source class, a factual
summary, severity, and confidence. The system may detect or queue an anomaly,
but only an adjudicated finding from a qualified authority may use
`confirmed_research_misconduct`.

The following evidence sources should be collected:

| Source | What it can establish | Default status |
|---|---|---|
| FDA review and advisory materials | Efficacy, trial-design, statistical, GCP, or data-reliability concerns | `regulatory_concern` |
| FDA Complete Response Letters | Formal regulatory deficiencies | `formal_regulatory_finding` |
| FDA BIMO and clinical-investigator actions | Inspection concerns or finalized compliance actions | `inspection_pending` or `formal_regulatory_finding` |
| HHS Office of Research Integrity findings | Adjudicated fabrication, falsification, or plagiarism | `confirmed_research_misconduct` |
| DOJ, SEC, or court records | Allegations, settlements, judgments, or convictions | Evidence-specific; never promote an allegation |
| ClinicalTrials.gov history | Registration, endpoint, enrollment, and results-reporting changes | `unverified_anomaly` until reviewed |
| PubMed and publisher records | Corrections, expressions of concern, and retractions | `publication_retraction` only when the record says so |
| Issuer or investigator response | Rebuttal, explanation, or remediation | Stored as a response, not as erasure of the source record |

## Scoring

The deterministic score is a triage priority from 0 to 100. Only the strongest
signal in a company/study/category cell contributes points, limiting duplicate
coverage of the same issue. Status, severity, and evidence confidence determine
points. Resolved signals remain auditable but contribute zero.

Interpretation:

- `review`: inspect the cited record;
- `elevated_diligence`: targeted statistical and regulatory review;
- `high_diligence`: source-document review before relying on the affected data;
- `critical_diligence`: pause reliance pending independent review.

No threshold means "fraud likely." A company may have a high diligence score
and zero confirmed misconduct findings.

## Capricor / deramiocel initial case

The July 2026 FDA briefing package is a high-severity integrity and efficacy
case because the Agency described failed prespecified endpoints, major
post-study analysis changes, non-robust missing-data handling, deviations from
the approved blinding workflow, and an ongoing BIMO inspection. Capricor
disputes FDA's analytical frame and says its final plan was completed before
formal unblinding.

The ledger therefore records severe regulatory concerns and a pending
inspection, while keeping `confirmed_research_misconduct` at zero. That status
must change only if an authority publishes a final qualifying finding.

## Required next collectors

1. Snapshot ClinicalTrials.gov records and version histories before catalysts.
2. Match NCT IDs, products, sponsors, investigators, publications, and public
   company entities with effective dates.
3. Poll FDA warning letters, BIMO actions, disqualification proceedings,
   advisory materials, and CRLs.
4. Poll HHS ORI, DOJ, SEC enforcement, PubMed retractions, expressions of
   concern, and corrections.
5. Create a human adjudication queue for endpoint changes, selective reporting,
   missing-data sensitivity, baseline imbalance, site outliers, and image or
   endpoint adjudication departures.
6. Backtest whether each signal was knowable before a regulatory or market
   event. Never use later enforcement or retraction data in earlier snapshots.

Run the current discovery pass with:

```bash
python3 scripts/discover_study_integrity.py
```

## M&A use

Study-integrity evidence should be a separate diligence overlay. It must not
automatically raise or lower acquisition likelihood: a concern can reduce asset
value, produce a distressed situation, or make a transaction impossible.
Estimate those effects only after point-in-time validation against historical
transactions and non-target controls.
