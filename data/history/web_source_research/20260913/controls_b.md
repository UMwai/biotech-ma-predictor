# Primary source research for nine comparison candidates

Archived original SEC annual reports for all nine assigned issuers. For Frequency Therapeutics, also archived **48 accession indexes and 139 filing or exhibit bodies** covering the designated January 2020 through March 2022 corpus. Verified all captured hashes, exact effective URLs and filing dates against the saved inventory. **No new negative acquisition label is assigned.**

| Issuer | Material candidates | Original annual source | Additional result |
|---|---:|---|---|
| FREQ | 48 | [10-K filed 2022-03-15](https://www.sec.gov/Archives/edgar/data/1703647/000095017022003655/freq-20211231.htm) | 48 accession indexes and 139 designated bodies archived; substantive outcome review remains. |
| AVDL | 54 | [10-K filed 2022-03-16](https://www.sec.gov/Archives/edgar/data/1012477/000101247722000004/avdl-20211231.htm) | Original SEC body succeeds. Historical issuer PDF redirects to the Alkermes homepage and is rejected. |
| HARP | 47 | [10-K filed 2022-03-10](https://www.sec.gov/Archives/edgar/data/1708493/000095017022003375/harp-20211231.htm) | Original SEC body succeeds despite the unavailable historical issuer host. |
| FULC | 53 | [10-K filed 2022-03-03](https://www.sec.gov/Archives/edgar/data/1680581/000095017022002727/fulc-20211231.htm) | Original SEC body and issuer prospectus PDF archived. Historical archive query opens current rows. |
| CNCE | 37 | [10-K filed 2022-03-03](https://www.sec.gov/Archives/edgar/data/1367920/000136792022000018/cnce-20211231.htm) | Original SEC body succeeds despite the unavailable historical issuer host. |
| KALA | 50 | [10-K filed 2022-03-29](https://www.sec.gov/Archives/edgar/data/1479419/000155837022004624/kala-20211231x10k.htm) | Original SEC body succeeds despite the unavailable historical issuer host. |
| KALV | 42 | [10-K filed 2021-07-13](https://www.sec.gov/Archives/edgar/data/1348911/000156459021036441/kalv-10k_20210430.htm) | Original SEC body succeeds. One issuer body open returned 403; historical archive query opens current rows. |
| KNSA | 52 | [10-K filed 2022-02-24](https://www.sec.gov/Archives/edgar/data/1730430/000155837022001932/knsa-20211231x10k.htm) | Original SEC body and issuer annual PDF archived. |
| KRYS | 55 | [10-K filed 2022-02-28](https://www.sec.gov/Archives/edgar/data/1711279/000171127922000004/krys-20211231.htm) | Original SEC annual and issuer 2021-05-10 8-K PDF archived; the PDF includes Exhibit 99.1. |

The designated window covers the pending transaction baseline, 2021 outcome and reporting lag through March 31, 2022. Actual download and review timestamps remain September 2026.

Every source URL, actual download clock, effective URL, SHA-256 and raw source location is in [controls_b.json](controls_b.json), [annual probes](controls_b_sec_annual_probes.json), and the [request journal](controls_b_sec_requests.jsonl). The [Frequency corpus](FREQ_sec_corpus_discovery.json) and [integrity receipt](FREQ_sec_corpus_integrity.json) bind the completed collection. Raw bytes are excluded from Git by existing repository rules.

These are captured current responses from SEC document URLs. SEC delivery markup appears in 138 of the 139 Frequency bodies: 137 are 364 bytes longer than the index size, one is 223 bytes longer, and the remaining XML body matches its index size. Both counts are preserved. The saved HTTP response hashes do not establish byte identity with the original filing as accepted; historical original vintage remains unverified.

The next gate is substantive review of transaction, censoring and identity contexts, plus historical inventory reconciliation, source publication binding and non-HTML exhibit review. Source downloads alone do not establish a negative outcome or an eligible training example.
