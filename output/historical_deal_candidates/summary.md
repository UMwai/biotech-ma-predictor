# Historical Biotech Transaction Candidate Audit

Generated: `2026-07-23T03:03:33+00:00`
SEC filing window: `2018-01-01` through `2026-07-22`

## Coverage

- SEC transaction documents fetched: **4077**
- Biotech transaction candidate clusters: **336**
- Schedule 14D-9 target candidates: **150**
- DEFM14A-only review candidates: **186**
- Model-label eligible rows: **0**

## Candidates by first SEC signal year

| Year | Candidates |
|---:|---:|
| 2018 | 25 |
| 2019 | 27 |
| 2020 | 30 |
| 2021 | 30 |
| 2022 | 44 |
| 2023 | 56 |
| 2024 | 40 |
| 2025 | 56 |
| 2026 | 28 |

## Historical annual reporting-company risk sets

| Observation year | Companies | Complete outcomes | Forward 14D-9 signals | Forward any candidates | 14D-9 incidence |
|---:|---:|---:|---:|---:|---:|
| 2018 | 472 | 472 | 9 | 22 | 1.91% |
| 2019 | 531 | 531 | 13 | 22 | 2.45% |
| 2020 | 575 | 575 | 8 | 25 | 1.39% |
| 2021 | 706 | 706 | 15 | 30 | 2.12% |
| 2022 | 813 | 813 | 21 | 49 | 2.58% |
| 2023 | 801 | 801 | 16 | 36 | 2.00% |
| 2024 | 755 | 755 | 29 | 52 | 3.84% |
| 2025 | 713 | 0 | 12 | 27 | censored |

## Label status

This is a primary-source candidate ledger, not a frozen acquisition-label dataset.
No candidate is model-label eligible until a reviewer verifies the target role,
change-of-control structure, and first public announcement timestamp. The SEC filing
date is retained as `sec_signal_date` and must not be silently substituted for the
announcement date in a predictive backtest.

The annual risk set uses contemporaneous biotech 10-K/20-F/40-F filers with
Exchange Act file numbers beginning `001-`. This removes current-survivor bias
from the denominator, but it is not a complete historical exchange-membership
reconstruction and contains no point-in-time model features.

Schedule 14D-9 candidates are high-confidence tender-offer target signals. DEFM14A-only
candidates remain an explicit adjudication queue because the filer can be the target,
buyer, SPAC, or another merger participant.
