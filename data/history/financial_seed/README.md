# Pre-announcement financial source seed

`financial_records.json` contains eight real acquired-company annual reports and 33 manually reviewed statement entries. Values include cash and cash equivalents, total assets, annual operating cash flow, and annual R&D. Array reports two R&D components, preserved separately without creating a generic reported R&D total.

Five original issuer reports were downloaded from AnnualReports mirrors and archived under `raw/` with SHA-256 and retrieval receipts in `download_manifest.json`. Three other reports were reviewed using SEC web pages; their original bytes are **not archived** and `source_sha256` remains null. Their separately hashed review JSON records are manual evidence, not original HTTP payloads. Later mirror requests were rate-limited or failed; those outcomes remain in the download receipt.

Each record carries the fiscal period, reported label, table/page citation, reported USD-thousands value, factor of 1,000, normalized USD value, CIK, reviewed candidate identity, and original publication evidence. XBRL tags have not been independently extracted and remain null. Publication is date-only, with no invented timestamp. Original dates are supported by SEC filing indexes, issuer filing certifications, or pre-event primary documents explicitly identifying the earlier filing date. Acquisition releases provide no financial feature values.

Version 2 review receipts bind each record's CIK, ticker, fiscal period, original publication fields, and source metadata to the reviewed annotation. Original version 1 receipts remain unchanged and are linked by hash. This verifies internal consistency; it does not independently authenticate a web source.

This convenience sample is not a membership or outcome panel. It has no nonacquired controls and supports no fitted-model claim. It also does not establish that each annual report was the latest information available before the deal: the older Translate Bio and Acceleron reports need explicit staleness treatment. Annual flows must not be treated as quarter-only figures or immediately pre-event trailing twelve months. Positive operating cash flow is retained as positive, and acquired in-process R&D remains separate from recurring R&D where reported separately.

Validate local identity, hashes, periods, units, publication ordering, and the 20 facts linked to archived PDF table extractions:

```sh
python3 data/history/financial_seed/validate_seed.py
```

Reviewer: `Codex-primary-source-review`; no independent human review. No programmatic SEC requests were made.
