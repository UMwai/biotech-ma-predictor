# Historical acquisition seed

These files contain 54 source-reviewed definitive acquisition announcements from
2018–2025, linked to the existing SEC candidate ledger. They are a selected set of
positive examples, not an exhaustive acquisition census or a training population.
The review CSVs contain decisions; their companion JSON ledgers preserve primary
source URLs, contemporaneous ticker evidence, evidence paraphrases and limitations.
The reviewer is Codex. Independent label-quality review remains outstanding.

Run `.venv/bin/python scripts/build_history_seed.py` to verify each review/evidence
pair against its hashes and candidate identities, freeze the combined labels, and
write `status.json`. Each local research build copies this directory into its sealed
snapshot so the dashboard can show historical progress.

The separate [100-company cohort](../../docs/HISTORICAL_COHORT.md) is assembled
from the complete original exchange notice, reviewed annual financials and
source-bound company observations. Its current first-fold support is five
acquisition events and two qualifying comparison companies; training remains
blocked. The older `control_seed/` and `financial_seed/` directories are retained
as pilot evidence, not the complete current cohort.

Most sources establish a calendar date without a reliable first-publication time.
Those records retain null exact timestamps and conservative UTC uncertainty bounds.
No midnight publication time is invented. `transaction_status=pending` describes
the announcement document as of its date; it does not describe today's outcome.
The proposed post-transaction control percentage is distinct from tender acceptance
or the incremental stake purchased. Failed or withdrawn definitive agreements
still count as positive announcement events for this prediction target.

The next dataset needs public biotech common-equity membership at each historical
observation date, including companies later acquired or delisted; contemporaneously
published financial/market/clinical features; and fully observed, reviewed outcome
windows for both positive and negative companies. Annual SEC filer proxies and
today's surviving tickers cannot supply that historical universe. An unmatched
candidate is not a negative outcome. Announcement terms are label evidence and must
never become pre-announcement features.

Historical source availability and today's review timestamp are different fields.
Historical fitting must use when the underlying information became public, with
conservative bounds where necessary, while retaining today's review audit separately.
The baseline input contract and temporal fitting commands are documented in
[BASELINE_TRAINING.md](../../docs/BASELINE_TRAINING.md).
