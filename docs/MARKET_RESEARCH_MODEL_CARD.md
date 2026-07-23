# Market Research Evaluator Model Card

**Model version:** `market-research-0.1.0`
**Status:** Heuristic research baseline
**Probability output:** None

## Intended use

Rank observable drug assets and U.S.-listed drug/biotech companies for research
review. The evaluator helps an analyst decide which companies and assets deserve
deeper diligence. It does not estimate the probability that a company will be
acquired and is not an investment recommendation.

## Current population and sources

The current-company universe is the drug/biotech subset of the Nasdaq U.S.
health-care screener, enriched with SEC CIK identifiers. Asset coverage combines:

- current marketed Orange Book ingredient/applicant records;
- currently marketed BLA ingredient/sponsor records from Drugs@FDA; and
- active industry-sponsored drug, biological, combination-product, and genetic
  interventions from ClinicalTrials.gov.

Recent SC 14D-9 and DEFM14A filers are conservatively removed from the current
prediction risk set. These exclusions are review signals, not automatically
adjudicated acquisition labels.

## Score construction

Asset scores are deterministic combinations of observable source fields:

- marketed-product status, innovator/reference status, listed competition, and
  remaining Orange Book patent/exclusivity time;
- marketed-BLA reference status and sponsor competition; and
- active clinical phase, status, trial count, record freshness, and enrollment.

Company scores combine the strongest matched assets with an acquisition-size
feasibility curve, portfolio focus, and entity-match confidence. These weights
are expert-selected and have not been optimized on historical outcomes.

Scores are bounded from 0 to 100 solely for ranking convenience. They must not
be divided by 100 or otherwise presented as probabilities.

## Historical evidence status

The SEC history builder creates:

- an auditable 2018-present transaction-candidate ledger from SC 14D-9 and
  DEFM14A filings; and
- annual historical reporting-company risk sets from contemporaneous biotech
  10-K, 20-F, and 40-F filings with `001-` Exchange Act file numbers.

Schedule 14D-9 identifies the subject company of a tender offer and therefore
has strong provisional target provenance. DEFM14A alone requires review because
the filer can be a target, acquirer, SPAC, or reverse-merger participant.

The risk sets remove current-survivor bias from the comparison denominator, but
they are not complete historical exchange-membership reconstructions. No
historical row is eligible for model training until target role, change of
control, first public announcement time, and outcome class are reviewed.
Issuers with a transaction signal in the prior 365 days are conservatively
excluded; a continuing filer can re-enter after that cooldown so a failed or
misclassified candidate does not remove it permanently.
Risk-set rows also record whether the full forward outcome window is observable;
censored cohorts are not assigned a comparable negative-event rate.

There is currently no validated lift, calibration, or forward-performance
evidence.

## Known limitations

- Current asset files do not reconstruct historical ownership or source state.
- Subsidiary and licensed-asset rollups are incomplete.
- ClinicalTrials.gov sponsor association does not prove asset ownership.
- Purple Book-only CBER products and biologic patent coverage may be incomplete.
- Market capitalization is a current cross-section from the market screener.
- Private, preclinical-only, paused, completed, and ex-U.S.-only programs are
  outside or incompletely represented in the current asset scope.
- Unmatched applicants and sponsors remain in a separate entity-resolution
  backlog instead of being guessed into public parents.

## Promotion requirements

Do not promote the evaluator to a predictive model until:

1. deal candidates are adjudicated into frozen event labels;
2. historical exchange membership and delisted controls are reconstructed;
3. every feature has point-in-time availability timestamps;
4. expanding-window walk-forward results beat base-rate and simple baselines;
5. ranking lift and probability calibration are reported separately; and
6. sealed forward predictions run for at least one full 6-12 month paper period.
