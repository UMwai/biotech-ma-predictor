"""Synthetic audit fixtures verify cutoff joins, immutable facts and missingness."""
import hashlib
import json
from datetime import datetime, timezone

import pytest
from src.research.financial_seed import FEATURE_UNITS
from src.research.panel_financials import financials_at_cutoff, read_reviewed_financials


@pytest.fixture
def financial_input(tmp_path):
    payload = b'Synthetic annual report; no investment evidence'
    (tmp_path / 'original.pdf').write_bytes(payload)
    facts = {}
    for name, value in [('cash_usd', 10), ('annual_operating_cashflow_usd', -2)]:
        annual = name.startswith('annual_')
        facts[name] = dict(reported=True, reported_label=name, statement='Synthetic statement', printed_page='F3',
                           source_unit='USD thousands', unit_multiplier=1000, reported_value=value,
                           value_usd=value*1000, unit=FEATURE_UNITS[name],
                           period_type='annual' if annual else 'instant', period_start='2019-01-01' if annual else None,
                           period_end='2019-12-31')
    record = dict(record_id='synthetic', cik=123, ticker='SYNTH', filing_form='10-K', period_type='annual',
                  period_start='2019-01-01', period_end='2019-12-31', filed_date='2020-03-01', publication_date='2020-03-01',
                  publication_date_verified=True, publication_timestamp_precision='date', published_at=None,
                  publication_evidence=dict(url='https://example.org/original', evidence_paraphrase='Synthetic date evidence'),
                  available_at='2020-03-02T12:00:00Z', retrieved_at='2026-01-01T00:00:00Z', reviewed_at='2026-01-02T00:00:00Z',
                  source_url='https://example.org/original', raw_bytes_archived=True, source_relative_path='original.pdf',
                  source_sha256=hashlib.sha256(payload).hexdigest(), source_bytes=len(payload), facts=facts)
    path = tmp_path / 'records.json'
    def save(reseal=True):
        if reseal:
            review = {k: v for k, v in record.items() if k not in ('evidence_relative_path', 'evidence_sha256')}
            blob = json.dumps(dict(review, schema_version='manual-financial-evidence-v2')).encode()
            (tmp_path / 'review.json').write_bytes(blob)
            record.update(evidence_relative_path='review.json', evidence_sha256=hashlib.sha256(blob).hexdigest())
        path.write_text(json.dumps(dict(schema_version='reviewed-panel-annual-financials-v1', records=[record])))
    save()
    return path, record, save


def test_cutoff_and_missing_features_preserve_publication_uncertainty(financial_input):
    path, _, _ = financial_input
    rows = read_reviewed_financials([path])
    assert financials_at_cutoff(rows, 123, datetime(2020, 3, 2, 11, tzinfo=timezone.utc)) is None
    result = financials_at_cutoff(rows, 123, datetime(2020, 3, 2, 12, tzinfo=timezone.utc))
    assert result['features']['cash_usd'] == 10000
    assert result['features']['annual_cash_burn_usd'] == 2000
    assert result['features']['assets_usd'] is None
    assert financials_at_cutoff(rows, 999, datetime(2021, 1, 1, tzinfo=timezone.utc)) is None


def test_consistent_value_edits_cannot_rewrite_saved_review(financial_input):
    path, row, save = financial_input
    row['facts']['cash_usd'].update(reported_value=20, value_usd=20000)
    save(reseal=False)
    with pytest.raises(ValueError, match='disagree with review'):
        read_reviewed_financials([path])


def test_changed_original_bytes_block_replay(financial_input):
    path, _, _ = financial_input
    (path.parent / 'original.pdf').write_bytes(b'changed')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        read_reviewed_financials([path])


def test_units_and_annual_period_cannot_be_resealed_into_wrong_features(financial_input):
    path, row, save = financial_input
    row['facts']['cash_usd']['source_unit'] = 'USD'
    save()
    with pytest.raises(ValueError, match='source unit conversion'):
        read_reviewed_financials([path])
    row['facts']['cash_usd']['source_unit'] = 'USD thousands'
    row['facts']['annual_operating_cashflow_usd']['period_start'] = '2019-04-01'
    save()
    with pytest.raises(ValueError, match='flow/instant'):
        read_reviewed_financials([path])


def test_browser_receipts_cannot_claim_an_original_hash(financial_input):
    path, row, save = financial_input
    row['raw_bytes_archived'] = False
    save()
    with pytest.raises(ValueError, match='unarchived source'):
        read_reviewed_financials([path])


@pytest.mark.parametrize('tamper', [
    'different_table_host', 'different_accession', 'parent_path_escape', 'non_sec_original_host',
])
def test_statement_table_requires_original_sec_host_and_accession(financial_input, tamper):
    path, row, save = financial_input
    accession = 'https://www.sec.gov/Archives/edgar/data/123/000000012320000001'
    original = accession + '/synth-20191231.htm'
    row.update(source_url=original, original_sec_url=original, raw_bytes_archived=False,
               source_relative_path=None, source_sha256=None, source_bytes=None)
    fact = row['facts']['cash_usd']
    fact.update(printed_page=None, table_locator='R2.htm; Balance Sheets; cash row; 2019 column',
                source_url=accession + '/R2.htm')
    save()
    assert read_reviewed_financials([path])[0]['features']['cash_usd'] == 10000

    if tamper == 'different_table_host':
        fact['source_url'] = fact['source_url'].replace('www.sec.gov', 'sec.gov.example.test')
    elif tamper == 'different_accession':
        fact['source_url'] = fact['source_url'].replace('000000012320000001', '000000012320000099')
    elif tamper == 'parent_path_escape':
        fact['source_url'] = accession + '/../000000012320000099/R2.htm'
    else:
        row['source_url'] = row['original_sec_url'] = original.replace('www.sec.gov', 'sec.gov.example.test')
        fact['source_url'] = fact['source_url'].replace('www.sec.gov', 'sec.gov.example.test')
    # A new matching receipt must not bypass the structural source-identity check.
    save()
    with pytest.raises(ValueError):
        read_reviewed_financials([path])
