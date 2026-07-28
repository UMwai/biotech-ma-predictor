# Biotech Strategic Matrix Model Card

## Decision contract

The strategic pipeline preserves five different questions:

1. **M&A attractiveness:** Does the company have financeable, strategically
   useful assets that deserve acquisition review?
2. **Company execution risk:** Does the public record show repeated or severe
   failures in clinical, regulatory, manufacturing, financial-control,
   partnership, or capital delivery?
3. **Leadership role-accountability risk:** Did those events occur within the
   functional remit and tenure of the leadership team?
4. **Delivery upside:** How much observable asset progress exists, independent
   of current company-specific risk coverage?
5. **Historical precedent:** Which point-in-time execution marker has the
   closest observable feature fingerprint?

These axes are not interchangeable. Execution distress can increase the chance
of an asset sale while simultaneously reducing the attractiveness of a clean
whole-company acquisition.

## Language and attribution rules

The pipeline does not emit an `incompetent` label. That word compresses
different facts—bad outcomes, weak controls, ordinary scientific failure,
misconduct, and bad luck—into a subjective accusation.

Instead:

- `company` scope records an issuer-level event;
- `leadership_team` scope records role accountability during the event window,
  without claiming individual culpability; and
- `named_executive` is permitted only when an official authority publishes an
  individual enforcement finding.

Missing evidence is reported as `limited_no_detected_signals`, never as a clean
bill of health.

## Evidence families

The production collector should build append-only, point-in-time event records
from these sources:

| Domain | Objective events |
|---|---|
| Clinical delivery | Missed prespecified endpoints, terminated studies, unexplained enrollment or endpoint changes, repeated protocol deviations |
| Regulatory delivery | CRLs, clinical holds, refused-to-file actions, major review-cycle delays, withdrawn applications |
| Statistical governance | Post-study SAP changes, non-robust missing-data treatment, functional unblinding, inspection findings |
| Manufacturing and quality | Form 483 observations, warning letters, import alerts, recalls, comparability failures |
| Financial controls | Restatements, material weaknesses, late filings, auditor resignations, going-concern opinions |
| Capital execution | Runway deterioration, repeated emergency dilution, covenant breaches, restructuring |
| Guidance reliability | Timestamped management guidance compared with eventual delivery, with explicit revision history |
| Leadership stability | CEO, CFO, CMO, regulatory, quality, and clinical-development turnover clustered around material events |
| Partnership execution | Terminations, returned rights, material disputes, missed milestones, or partner walkaways |
| Enforcement and ethics | Final FDA, HHS ORI, SEC, DOJ, court, or exchange findings |

Market prices, social media, short reports, and unusual insider transactions can
create review candidates, but cannot independently become formal execution or
misconduct findings.

## Scoring

Execution signals carry:

- dated primary evidence;
- category and evidence status;
- severity and confidence;
- company, team, or officially adjudicated individual scope;
- accountable functions;
- issuer response and remediation; and
- point-in-time availability.

The score is a deterministic diligence priority from 0 to 100. The strongest
record in a category/event cell contributes to prevent duplicate descriptions
from inflating risk. Team role-accountability receives less weight than an
official individual finding.

Neither execution nor leadership scores are probabilities of failure.

## Strategic archetypes

| M&A axis | Risk axis | Output |
|---|---|---|
| High | Reviewed low | `strategic_target` |
| High | Elevated | `diligence_sensitive_target` |
| High | High | `distressed_or_structured_target` |
| Moderate | High | `distressed_asset_watch` |
| Low | High | `failure_watch` |
| High | No company-specific risk evidence | `ma_candidate_risk_unscreened` |

Transaction structure follows the archetype:

- clean whole-company diligence for reviewed strategic targets;
- staged diligence, milestones, representations, and CVRs for elevated risk;
- asset purchases, options, licenses, or contingent consideration for high-risk
  situations; and
- financing, restructuring, governance, and asset-sale monitoring for failure
  watches.

## Current coverage

The matrix joins all 760 companies in the current market evaluator. The
execution and leadership ledgers are initially populated only for the verified
Capricor case; the negative historical-marker library adds sourced Amylyx
downside evidence. Other rows remain unscreened until the broader collectors
are built. Every row now has an asset-progress upside proxy and explicit
risk-coverage grade. A high upside score on an unscreened row is not a
management-quality finding.

The current output must not be presented as a complete market-wide leadership
ranking.

## Run order

```bash
python3 scripts/evaluate_market.py
python3 scripts/evaluate_study_integrity.py
python3 scripts/evaluate_execution_risk.py
python3 scripts/build_execution_scorecard.py
python3 scripts/build_strategic_matrix.py
```

## Validation before predictive use

1. Reconstruct historical leadership tenures and event availability dates.
2. Freeze objective failure-event definitions before viewing returns or deals.
3. Measure source coverage and false-positive adjudication rates.
4. Backtest M&A and failure outcomes separately with contemporaneous controls.
5. Test whether risk signals improve transaction-structure selection without
   degrading clean-target lift.
6. Seal forward weekly predictions and retain every later correction.
