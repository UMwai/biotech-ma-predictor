# Biotech Execution Scorecard Model Card

## Decision contract

The scorecard answers four separate questions for every company in the current
market universe:

1. **Delivery upside:** How much observable asset progress is present?
2. **Execution downside:** How severe is the sourced company-specific execution,
   integrity, or role-accountability evidence?
3. **Historical similarity:** Which point-in-time precedent has the most similar
   observable event fingerprint?
4. **Evidence coverage:** Has company-specific risk evidence actually been
   collected, or is the row still unscreened?

No single combined number is presented as a probability of acquisition,
success, failure, fraud, or management competence.

## Scores

### Delivery-upside proxy

The 0–100 delivery-upside score combines:

- 35% of the existing asset-portfolio score;
- a logarithmic contribution from approved products;
- a logarithmic contribution from late-stage or approved assets; and
- 15% of market-data confidence.

This rewards observable regulatory and development progress without allowing a
large product count to grow the score without bound. It is an asset-progress
proxy, not a leadership-quality score. For an exact ticker match, a sourced
positive marker can establish a higher floor from anchor tags such as regulatory
approval, first-in-class delivery, differentiated mechanism, successful
remediation, or accelerated approval.

### Execution downside

The downside score is the maximum of:

- study-integrity diligence;
- company execution risk; and
- leadership role-accountability risk.
- an exact-ticker negative-marker evidence score derived from its anchor tags.

Using the maximum keeps independently described versions of the same event from
being added together. Existing evidence-status, confidence, attribution, and
deduplication controls remain in force. Negative marker points cover observable
events such as regulatory failure, confirmatory failure, product withdrawal,
safety or endpoint uncertainty, manufacturing quality, statistical governance,
and pending inspection. Later outcomes never contribute points.

### Execution balance

`execution_balance_score = delivery_upside_score - execution_downside_score`

The range is -100 to 100. Analysts must still inspect both raw axes: the same
balance can describe a weak company with no evidence or a strong company with
material risk.

## Historical markers

Each marker contains two strictly separated records:

- an **anchor fingerprint** made only from evidence observable on the anchor
  date; and
- a **later outcome label** used for evaluation.

The initial library includes:

- Capricor's pending regulatory and statistical-governance case;
- Amylyx's confirmatory failure and product withdrawal;
- Athenex's safety/endpoint CRL before bankruptcy and asset sale;
- Sesen Bio's clinical/statistical/CMC CRL before program abandonment;
- Verona Pharma's differentiated approval before acquisition by Merck;
- Provention Bio's successful remediation and approval before acquisition by
  Sanofi; and
- Madrigal's first-in-class MASH approval as a positive delivery control.

Marker similarity is Jaccard overlap between current observable tags and the
anchor fingerprint. A match requires at least two shared tags, and similarities
below 15% are suppressed. Marker anchors after the requested `--as-of` date are
excluded. Similarity is descriptive and is not a probability that the later
outcome will recur.

The implementation rejects bankruptcy, asset-sale, reverse-merger, and
acquisition tags in anchor fingerprints. Tests also verify that changing a
later outcome label cannot change a score or similarity.

## Coverage states

| State | Meaning |
|---|---|
| `company_specific_evidence` | At least one cited integrity or execution record is present |
| `market_only_risk_unscreened` | Asset data is usable, but the company-specific risk collectors have not cleared the issuer |
| `sparse_risk_unscreened` | Both asset depth and risk evidence are limited |

An unscreened company is never called low risk or competent.

An exact-ticker downside marker counts as company-specific sourced evidence.
An exact-ticker positive marker can support delivery upside but does not clear
the company of uncollected downside risk.

## Intended use

Use the scorecard to:

- prioritize primary-source diligence;
- distinguish strong assets from weak execution;
- choose whole-company, asset-purchase, option, license, milestone, or CVR
  structures;
- search for repeated event patterns before capital or regulatory distress; and
- test whether precedents improve M&A or failure-outcome ranking out of sample.

Do not use it to accuse a company or individual of fraud, misconduct, or
incompetence. Those claims require adjudicated evidence under the integrity and
execution ledgers.

## Run order

```bash
python3 scripts/evaluate_market.py
python3 scripts/evaluate_study_integrity.py
python3 scripts/evaluate_execution_risk.py
python3 scripts/build_execution_scorecard.py
python3 scripts/build_strategic_matrix.py
```

The scorecard writes company rows, marker rows, a coverage manifest, and a
human-readable summary under `output/execution_scorecard/`.

## Promotion gates

Before predictive use:

1. expand primary-source event collection beyond the manually verified seed
   cases;
2. reconstruct every event's public availability date and leadership tenure;
3. freeze tag definitions before inspecting later outcomes;
4. build contemporaneous company controls with equal source coverage;
5. evaluate M&A, bankruptcy, withdrawal, restructuring, and independent
   commercial success as separate labels;
6. measure calibration and precision by evidence-coverage tier; and
7. seal forward snapshots so later corrections cannot rewrite history.
